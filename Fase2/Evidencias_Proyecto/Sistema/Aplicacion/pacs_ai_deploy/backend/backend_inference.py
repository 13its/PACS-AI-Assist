from __future__ import annotations

import io
import os
import math
from typing import List, Tuple

import numpy as np
import pydicom
import requests
import json

# IA
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.layers import Conv3DTranspose as _Conv3DTranspose


# DICOM SEG
from highdicom.seg import Segmentation
from highdicom.seg.content import SegmentDescription
from highdicom.sr.coding import Code
from pydicom.uid import generate_uid
from pydicom.multival import MultiValue
from pydicom.valuerep import IS
from highdicom import AlgorithmIdentificationSequence

_AI_ALGO = AlgorithmIdentificationSequence(
    name="PACS-AI Lung Nodule Segmenter",
    family=Code("713663001", "SCT", "Deep learning"),
    version="0.1.0",
    source="PACS-AI Assist"
)
# Reusamos utilidades robustas que ya construiste en pacsai_model
from pacs_ai_deploy.pacsai_model import (
    _download_source_images,
    _dedupe_and_sort_images,
    _ensure_sources_uploaded,
    _inject_slice_thickness,
)
# ======================
# MÉTRICAS Y FUNCIONES
# ======================

def dice_coef(y_true, y_pred, smooth=1e-6):
    y_true_f = tf.reshape(tf.cast(y_true, tf.float32), [-1])
    y_pred_f = tf.reshape(tf.cast(y_pred, tf.float32), [-1])
    intersection = tf.reduce_sum(y_true_f * y_pred_f)
    return (2. * intersection + smooth) / (tf.reduce_sum(y_true_f) + tf.reduce_sum(y_pred_f) + smooth)

def dice_loss(y_true, y_pred):
    return 1.0 - dice_coef(y_true, y_pred)

def bce_dice_loss(y_true, y_pred):
    bce = tf.keras.losses.BinaryCrossentropy()
    d = dice_loss(y_true, y_pred)
    return 0.7 * bce(y_true, y_pred) + 0.3 * d

class Conv3DTransposeCompat(_Conv3DTranspose):
    """
    Versión compatible de Conv3DTranspose que ignora el argumento 'groups'
    que viene en el .h5 exportado desde otra versión de Keras.
    """
    def __init__(self, *args, **kwargs):
        # Si el config trae 'groups', lo sacamos para que Keras 2.10 no se queje
        kwargs.pop("groups", None)
        super().__init__(*args, **kwargs)

# === HU, ventana y utilidades ===

def _to_hu(vol, slope: float, intercept: float):
    return vol.astype(np.float32) * float(slope) + float(intercept)


def _window_and_norm(vol_hu: np.ndarray, lo: float = -1000.0, hi: float = 400.0):
    vol = np.clip(vol_hu, lo, hi)
    vol = (vol - lo) / (hi - lo)
    return vol.astype(np.float32)


def _voxel_metrics_simple(images):
    ds0 = images[0]
    sx, sy = getattr(ds0, "PixelSpacing", [1.0, 1.0])
    thk = float(getattr(ds0, "SliceThickness", getattr(ds0, "SpacingBetweenSlices", 1.0)))
    return float(sx), float(sy), float(thk)


def _min_voxels_for_diameter_mm_simple(images, d_mm: float = 3.0) -> int:
    sx, sy, thk = _voxel_metrics_simple(images)
    v_voxel = max(sx * sy * thk, 1e-6)
    v_sphere = (4.0 / 3.0) * math.pi * (d_mm / 2.0) ** 3
    mv = int(round(v_sphere / v_voxel))
    # límites sanos
    return max(8, min(mv, 500))


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
from pathlib import Path

# Carpeta donde está este backend_inference.py
BASE_DIR = Path(__file__).resolve().parent

# Nombre del modelo (el .h5 nuevo)
DEFAULT_MODEL_PATH = BASE_DIR / "pacsai_unet3d_TF210.h5"

# Permitir override por variable de entorno (opcional)
MODEL_PATH = Path(os.environ.get("PACSAI_MODEL_PATH", str(DEFAULT_MODEL_PATH)))

print(f"[DEBUG] BASE_DIR: {BASE_DIR}")
print(f"[DEBUG] MODEL_PATH: {MODEL_PATH} is_file? {MODEL_PATH.is_file()}")




# Intentamos leer el umbral desde model_meta.json
META_PATH = os.path.join(os.path.dirname(__file__), "model_meta.json")
_default_thresh = 0.2
try:
    with open(META_PATH, "r") as f:
        meta = json.load(f)
        _default_thresh = float(meta.get("threshold", _default_thresh))
        print(f"[MODEL] Umbral leído de model_meta.json: {_default_thresh}")
except Exception as e:
    print(f"[MODEL] No se pudo leer model_meta.json, uso umbral por defecto: {_default_thresh} ({e})")

HU_WINDOW = (-1000.0, 400.0)   # ventana rápida para CT tórax

# Permite sobreescribir por variable de entorno PACSAI_THRESH
THRESHOLD = float(os.getenv("PACSAI_THRESH", str(_default_thresh)))
print(f"[MODEL] THRESHOLD efectivo = {THRESHOLD}")

SERIES_DESC = "PACS-AI Segmentation"

# ---------------------------------------------------------------------
# Utils de pre/post-procesamiento (sin scipy)
# ---------------------------------------------------------------------
def _clip_and_norm(volume_hu: np.ndarray) -> np.ndarray:
    lo, hi = HU_WINDOW
    v = np.clip(volume_hu.astype(np.float32), lo, hi)
    v = (v - lo) / (hi - lo)   # [0,1]
    return v


def _as_volume_from_images(images: List[pydicom.dataset.Dataset]) -> np.ndarray:
    """Apila a (D,H,W) usando pixel_array ya ordenado; rellena NaN con 0."""
    stack = []
    for ds in images:
        arr = ds.pixel_array
        if arr.ndim == 3:       # improbable en CT single-frame
            arr = arr[..., 0]
        stack.append(arr)
    vol = np.stack(stack, axis=0)  # (D, H, W)
    vol = np.nan_to_num(vol, nan=0.0)
    return vol


def _fit_depth_nearest(vol: np.ndarray, target_d: int) -> Tuple[np.ndarray, np.ndarray]:
    """Ajusta profundidad con muestreo uniforme sin scipy. Devuelve vol' y los índices usados."""
    D, H, W = vol.shape
    if target_d == D:
        idx = np.arange(D)
        return vol, idx
    # indices equiespaciados
    idx = np.linspace(0, D - 1, num=target_d)
    idx_round = np.clip(np.round(idx).astype(int), 0, D - 1)
    return vol[idx_round, :, :], idx_round


def _fit_hw_center(vol: np.ndarray, target_h: int, target_w: int) -> Tuple[np.ndarray, Tuple[slice, slice]]:
    """Pad/crop centrado para H y W (sin interpolación)."""
    D, H, W = vol.shape
    # pad/crop H
    if H >= target_h:
        top = (H - target_h) // 2
        vol = vol[:, top:top + target_h, :]
        h_slice = slice(top, top + target_h)
    else:
        pad_top = (target_h - H) // 2
        pad_bot = target_h - H - pad_top
        vol = np.pad(vol, ((0, 0), (pad_top, pad_bot), (0, 0)), mode="edge")
        h_slice = slice(0, H)  # para revertir, solo informativo

    # pad/crop W
    D, H2, W2 = vol.shape
    if W2 >= target_w:
        left = (W2 - target_w) // 2
        vol = vol[:, :, left:left + target_w]
        w_slice = slice(left, left + target_w)
    else:
        pad_left = (target_w - W2) // 2
        pad_right = target_w - W2 - pad_left
        vol = np.pad(vol, ((0, 0), (0, 0), (pad_left, pad_right)), mode="edge")
        w_slice = slice(0, W2)

    return vol, (h_slice, w_slice)


def _restore_to_original(mask_small: np.ndarray,
                         idx_depth: np.ndarray,
                         orig_shape: Tuple[int, int, int]) -> np.ndarray:
    """Devuelve máscara (D,H,W) del volumen original.
       Tolera entradas 0D/2D/3D/4D y canal al final. Fallback seguro."""
    D0, H0, W0 = orig_shape
    m = np.asarray(mask_small)

    # Normalización de forma
    if m.ndim == 0:
        # salida escalar (p.ej. clasificador) -> máscara vacía
        return np.zeros((D0, H0, W0), dtype=bool)
    if m.ndim == 1:
        # vector -> expandimos como profundidad con 1x1
        m = m[:, None, None]
    if m.ndim == 2:
        # 2D -> asumimos 1 slice
        m = m[None, ...]
    if m.ndim == 4 and m.shape[-1] == 1:
        m = m[..., 0]
    if m.ndim != 3:
        # cualquier otra forma rara -> vacío
        return np.zeros((D0, H0, W0), dtype=bool)

    D1, H1, W1 = m.shape

    # 1) expandir a profundidad D0 usando asignación por índice más cercano
    pos_orig = np.arange(D0, dtype=np.float32)
    pos_used = np.linspace(0, D0 - 1, num=D1).astype(np.float32)
    inv_map = np.abs(pos_orig[:, None] - pos_used[None, :]).argmin(axis=1)
    depth_restored = m[inv_map, :, :]  # (D0, H1, W1)

    # 2) Ajuste centrado en H y W
    out = depth_restored
    # H
    if H1 >= H0:
        top = (H1 - H0) // 2
        out = out[:, top:top + H0, :]
    else:
        pad_top = (H0 - H1) // 2
        pad_bot = H0 - H1 - pad_top
        out = np.pad(out, ((0, 0), (pad_top, pad_bot), (0, 0)), mode="edge")
    # W
    _, H2, W2 = out.shape
    if W2 >= W0:
        left = (W2 - W0) // 2
        out = out[:, :, left:left + W0]
    else:
        pad_left = (W0 - W2) // 2
        pad_right = W0 - W2 - pad_left
        out = np.pad(out, ((0, 0), (0, 0), (pad_left, pad_right)), mode="edge")

    return out.astype(bool)


def _voxel_metrics(images):
    """Retorna (ps_x, ps_y, thk) en mm, usando promedio/backup si faltan tags."""
    ps_x, ps_y, thk = [], [], []
    for ds in images:
        try:
            if hasattr(ds, "PixelSpacing"):
                ps_x.append(float(ds.PixelSpacing[0]))
                ps_y.append(float(ds.PixelSpacing[1]))
        except Exception:
            pass
        try:
            # puede que lo hayas inyectado con _inject_slice_thickness
            thk.append(float(getattr(ds, "SliceThickness")))
        except Exception:
            pass

    def _avg_or(defv, vals):
        return (float(np.mean(vals)) if len(vals) else defv)

    return _avg_or(1.0, ps_x), _avg_or(1.0, ps_y), _avg_or(1.0, thk)


def _min_voxels_for_diameter_mm(images, d_mm: float) -> int:
    """Mínimo de vóxeles equivalente a una esfera de diámetro d_mm."""
    psx, psy, thk = _voxel_metrics(images)
    voxel_vol = max(psx * psy * thk, 1e-6)              # mm^3
    sphere_vol = (math.pi / 6.0) * (d_mm ** 3)          # mm^3
    nvox = int(math.ceil(sphere_vol / voxel_vol))
    # mínima sanidad para no borrar todo
    return max(nvox, 8)


def _remove_small_components(mask: np.ndarray, min_voxels: int) -> np.ndarray:
    """Labeling 3D 6-conectado sin scipy; elimina componentes con < min_voxels."""
    D, H, W = mask.shape
    lab = np.zeros((D, H, W), dtype=np.int32)
    out = np.zeros_like(mask, dtype=bool)
    cur = 0
    # offsets 6-conectados (z,y,x)
    nbrs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0),
            (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    it = np.argwhere(mask)
    seen = np.zeros(mask.size, dtype=bool)

    for z, y, x in it:
        idx = (z * H + y) * W + x
        if seen[idx]:
            continue
        cur += 1
        stack = [(z, y, x)]
        count = 0
        while stack:
            zz, yy, xx = stack.pop()
            ii = (zz * H + yy) * W + xx
            if seen[ii] or not mask[zz, yy, xx]:
                continue
            seen[ii] = True
            lab[zz, yy, xx] = cur
            count += 1
            for dz, dy, dx in nbrs:
                z2, y2, x2 = zz + dz, yy + dy, xx + dx
                jj = (z2 * H + y2) * W + x2
                if 0 <= z2 < D and 0 <= y2 < H and 0 <= x2 < W \
                        and not seen[jj] and mask[z2, y2, x2]:
                    stack.append((z2, y2, x2))
        if count >= min_voxels:
            out[lab == cur] = True
    return out


# ---------- helpers multi-nódulo -------------------------------------
def _label_components(mask: np.ndarray):
    """Labeling 3D 6-conectado, devuelve (labels, counts)."""
    D, H, W = mask.shape
    labels = np.zeros((D, H, W), dtype=np.int32)
    counts = {}
    current = 0
    nbrs = [(1, 0, 0), (-1, 0, 0), (0, 1, 0),
            (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    it = np.argwhere(mask)
    seen = np.zeros(mask.size, dtype=bool)

    for z, y, x in it:
        idx = (z * H + y) * W + x
        if seen[idx]:
            continue
        current += 1
        stack = [(z, y, x)]
        count = 0
        while stack:
            zz, yy, xx = stack.pop()
            ii = (zz * H + yy) * W + xx
            if seen[ii] or not mask[zz, yy, xx]:
                continue
            seen[ii] = True
            labels[zz, yy, xx] = current
            count += 1
            for dz, dy, dx in nbrs:
                z2, y2, x2 = zz + dz, yy + dy, xx + dx
                jj = (z2 * H + y2) * W + x2
                if 0 <= z2 < D and 0 <= y2 < H and 0 <= x2 < W \
                        and not seen[jj] and mask[z2, y2, x2]:
                    stack.append((z2, y2, x2))
        counts[current] = count
    return labels, counts


def _equivalent_diameter_mm(n_vox: int, images) -> float:
    """Diámetro equivalente (mm) suponiendo esfera con n_vox voxels."""
    psx, psy, thk = _voxel_metrics(images)
    voxel_vol = max(psx * psy * thk, 1e-6)
    sphere_vol = n_vox * voxel_vol
    d_mm = ((6.0 * sphere_vol) / math.pi) ** (1.0 / 3.0)
    return float(d_mm)


# ---------------------------------------------------------------------
# Construcción del SEG (1 segmento / fallback)
# ---------------------------------------------------------------------
def _build_seg_from_mask(source_images, mask_bool, series_desc,
                         is_malignant=False, score=None) -> bytes:
    # Validaciones mínimas
    d, h, w = mask_bool.shape
    assert d == len(source_images), f"mask depth {d} != num images {len(source_images)}"
    assert int(source_images[0].Rows) == h and int(source_images[0].Columns) == w, \
        "mask HxW no coincide con imágenes fuente"

    seg_desc = [
        SegmentDescription(
            segment_number=1,
            segment_label="AI Nodule",
            segmented_property_category=Code(
                "49755003", "SCT", "Morphologically Altered Structure"
            ),
            segmented_property_type=Code("67734004", "SCT", "Nodule"),
            algorithm_type="AUTOMATIC",
            algorithm_identification=_AI_ALGO,
        )
    ]

    seg = Segmentation(
        source_images=source_images,
        pixel_array=mask_bool,  # (D,H,W) bool
        segmentation_type="BINARY",
        segment_descriptions=seg_desc,
        series_instance_uid=generate_uid(),
        series_number=9501,
        series_description=series_desc,
        sop_instance_uid=generate_uid(),
        instance_number=1,
        manufacturer="PACS-AI Assist",
        manufacturer_model_name="PACS-AI Demo",
        software_versions="0.1.0",
        device_serial_number="PACS-AI-0001",
        omit_empty_frames=False,
    )

    buf = io.BytesIO()
    ds = seg if isinstance(seg, pydicom.dataset.Dataset) else seg.to_dataset()

    _apply_color_and_label(ds, is_malignant=is_malignant, score=score)

    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()


# ---------------------------------------------------------------------
# Construcción del SEG multi-nódulo
# ---------------------------------------------------------------------
def _build_multi_nodule_seg(
    source_images,
    seg_mask: np.ndarray,          # (D,H,W) con labels 0..K
    series_desc: str,
    nodule_sizes,                  # [(seg_num, d_mm), ...]
    is_malignant: bool,
    score: float | None = None,
) -> bytes:
    d, h, w = seg_mask.shape
    assert d == len(source_images), "seg_mask depth != num images"
    assert int(source_images[0].Rows) == h and int(source_images[0].Columns) == w

    max_label = int(seg_mask.max())
    assert max_label == len(nodule_sizes)
    seg_desc = []
    for seg_num, d_mm in nodule_sizes:
        seg_desc.append(
            SegmentDescription(
                segment_number=seg_num,
                segment_label=f"Nodule #{seg_num} ({d_mm:.1f} mm)",
                segmented_property_category=Code(
                    "49755003", "SCT", "Morphologically Altered Structure"
                ),
                segmented_property_type=Code("67734004", "SCT", "Nodule"),
                algorithm_type="AUTOMATIC",
                algorithm_identification=_AI_ALGO,
            )
        )


    # pixel_array (N, D, H, W) bool
    seg_masks = np.zeros((len(nodule_sizes), d, h, w), dtype=bool)
    for i, (seg_num, _) in enumerate(nodule_sizes):
        seg_masks[i] = (seg_mask == seg_num)

    seg = Segmentation(
        source_images=source_images,
        pixel_array=seg_masks,
        segmentation_type="BINARY",
        segment_descriptions=seg_desc,
        series_instance_uid=generate_uid(),
        series_number=9501,
        series_description=series_desc,
        sop_instance_uid=generate_uid(),
        instance_number=1,
        manufacturer="PACS-AI Assist",
        manufacturer_model_name="PACS-AI Demo",
        software_versions="0.1.0",
        device_serial_number="PACS-AI-0001",
        omit_empty_frames=False,
    )

    buf = io.BytesIO()
    ds = seg if isinstance(seg, pydicom.dataset.Dataset) else seg.to_dataset()

    _apply_color_and_label(ds, is_malignant=is_malignant, score=score)

    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()


# ---------------------------------------------------------------------
# COLOR / LABEL (no pisar nombres)
# ---------------------------------------------------------------------
def _apply_color_and_label(ds, is_malignant: bool, score: float | None = None):
    COLOR_RED = [65535, 32768, 32768]
    COLOR_BLUE = [32768, 49152, 65535]

    color = COLOR_RED if is_malignant else COLOR_BLUE
    dx_txt = "Malignant" if is_malignant else "Benign"

    # aplicamos color a TODOS los segmentos sin cambiar sus labels
    for seg_item in ds.SegmentSequence:
        seg_item.RecommendedDisplayCIELabValue = MultiValue(int, color)
        if hasattr(seg_item, "SegmentIdentificationSequence"):
            for si in seg_item.SegmentIdentificationSequence:
                try:
                    si.RecommendedDisplayCIELabValue = MultiValue(int, color)
                except Exception:
                    pass

    if score is not None:
        base = getattr(ds, "SeriesDescription", "PACS-AI Segmentation")
        ds.SeriesDescription = f"{base} | Dx:{dx_txt} (score={score:.3f})"

    print(f"[SEG] Color aplicado: {'RED' if is_malignant else 'BLUE'}  score={score}")


# ---------------------------------------------------------------------
# MAIN ENTRYPOINT
# ---------------------------------------------------------------------
def build_seg_from_meta(metas: List[dict], orthanc_url: str) -> bytes:
    # 1) Descarga y preparación
    groups = {}
    for m in metas:
        groups.setdefault(m["series_instance_uid"], []).append(m)
    best_sid, best_metas = max(groups.items(), key=lambda kv: len(kv[1]))

    images = _download_source_images(
        orthanc_url,
        sorted(best_metas, key=lambda x: x.get("instance_number", 0)),
    )
    images = _dedupe_and_sort_images(images, mm_tol=1e-3)
    _ensure_sources_uploaded(orthanc_url, images)
    _inject_slice_thickness(images)
    
    # 2) Volumen en HU normalizado [0,1]
    vol_raw = _as_volume_from_images(images)   # valores crudos del CT
    orig_shape = vol_raw.shape

    slope = float(getattr(images[0], "RescaleSlope", 1.0))
    inter = float(getattr(images[0], "RescaleIntercept", 0.0))

    # Convertimos a HU y luego aplicamos ventana [-1000, 400]
    vol_hu = _to_hu(vol_raw, slope, inter)
    vol_n = _window_and_norm(vol_hu, lo=-1000.0, hi=400.0)
    
    # 3) Modelo e input shape
    print(f"[MODEL] Cargando modelo desde: {MODEL_PATH}")
    model = load_model(
    str(MODEL_PATH),
    compile=False,
    custom_objects={
        "dice_coef": dice_coef,
        "dice_loss": dice_loss,
        "bce_dice_loss": bce_dice_loss,
        # parche para capas Conv3DTranspose con 'groups'
        "Conv3DTranspose": Conv3DTransposeCompat,
    },
    )


    ishape = model.inputs[0].shape
        # (None, D,H,W,C) o similar
    dims = [int(x) if x is not None else None for x in ishape]

    if len(dims) != 5:
        raise RuntimeError(f"Modelo con input no soportado: {ishape}")


    C = dims[-1] if dims[-1] else 1
    target_d = dims[1] or vol_n.shape[0]
    target_h = dims[2] or vol_n.shape[1]
    target_w = dims[3] or vol_n.shape[2]


    # ordenar por Z
    def _z_key(ds):
        if hasattr(ds, "ImagePositionPatient"):
            ipp = ds.ImagePositionPatient
            return float(ipp[2]) if len(ipp) >= 3 else float(getattr(ds, "InstanceNumber", 0))
        return float(getattr(ds, "InstanceNumber", 0))

    images = sorted(images, key=_z_key)
    vol_d, idx_depth = _fit_depth_nearest(vol_n, target_d)
    vol_dhw, _ = _fit_hw_center(vol_d, target_h, target_w)

    batch = vol_dhw[np.newaxis, ..., np.newaxis]  # (1,D',H',W',1)

    # 4) Inferencia
    score = None
    try:
        pred = model.predict(batch, verbose=0)
        pred = np.asarray(pred)

        # ===== DEBUG GROTESCO =====
        print(
            f"[DEBUG] pred shape={pred.shape}, "
            f"min={np.nanmin(pred):.4f}, "
            f"max={np.nanmax(pred):.4f}, "
            f"mean={np.nanmean(pred):.44f}"
        )
        # ==========================

        if pred.ndim == 0:
            score = float(pred)
        elif pred.ndim == 1 and pred.size == 1:
            score = float(pred[0])
        elif pred.ndim == 2 and pred.shape == (1, 1):
            score = float(pred[0, 0])
    except Exception as e:
        print(f"[MODEL] ERROR llamando a predict(): {e}. SEG vacío.")
        empty = np.zeros(orig_shape, dtype=bool)
        return _build_seg_from_mask(images, empty, SERIES_DESC,
                                    is_malignant=False, score=None)

    if pred.ndim >= 1 and pred.shape[0] == 1:
        pred = pred[0]
    if pred.ndim >= 4 and pred.shape[-1] == 1:
        pred = pred[..., 0]

    pred = pred.astype(np.float32)

    # ===== DEBUG ANTES DE NORMALIZAR / SIGMOID =====
    print(
        f"[DEBUG] tras squeeze shape={pred.shape}, "
        f"min={np.nanmin(pred):.4f}, "
        f"max={np.nanmax(pred):.4f}, "
        f"mean={np.nanmean(pred):.4f}"
    )
    # ===============================================

    if np.nanmax(pred) > 1.0 or np.nanmin(pred) < 0.0:
        pred = 1.0 / (1.0 + np.exp(-pred))

    # ===== DEBUG TRAS SIGMOID (si aplica) ==========
    print(
        f"[DEBUG] tras sigmoid (si aplica) shape={pred.shape}, "
        f"min={np.nanmin(pred):.4f}, "
        f"max={np.nanmax(pred):.4f}, "
        f"mean={np.nanmean(pred):.4f}"
    )
    # ===============================================

    if pred.ndim == 2:
        pred = pred[None, ...]


    if pred.ndim < 3:
        is_malignant = (score is not None and score >= THRESHOLD)
        empty = np.zeros(orig_shape, dtype=bool)
        return _build_seg_from_mask(images, empty, SERIES_DESC,
                                    is_malignant=is_malignant, score=score)

    pred = (pred >= THRESHOLD).astype(np.uint8)

    # 5) Volver al tamaño original
    mask_back = _restore_to_original(pred, idx_depth, orig_shape)  # (D,H,W) bool

    # 6) Filtrar componentes < 3 mm
    min_vox = _min_voxels_for_diameter_mm(images, 3.0)
    print(f"[POST] min_vox@3mm={min_vox}")

    before = int(np.count_nonzero(mask_back))
    mask_back = _remove_small_components(mask_back.astype(bool), min_voxels=min_vox)
    after = int(np.count_nonzero(mask_back))
    print(f"[POST] voxels antes={before}  después={after}")

    if after < max(20, before // 10):
        min_vox_relaxed = max(4, min_vox // 2)
        print(f"[POST] relajando filtro a min_vox={min_vox_relaxed}")
        mask_back = _remove_small_components(mask_back.astype(bool), min_voxels=min_vox_relaxed)

    is_malignant = (score is not None and score >= THRESHOLD)

    # 7) Multi-nódulo: componentes conectadas → un segmento por nódulo ≥ 3mm
    labels, counts = _label_components(mask_back.astype(bool))
    seg_mask = np.zeros_like(labels, dtype=np.uint16)
    seg_num = 0
    nodule_sizes = []

    for comp_id, vox in counts.items():
        if vox <= 0:
            continue
        d_mm = _equivalent_diameter_mm(vox, images)
        if d_mm < 3.0:
            continue
        seg_num += 1
        seg_mask[labels == comp_id] = seg_num
        nodule_sizes.append((seg_num, d_mm))

    if seg_num == 0:
        print("[POST] No se encontraron nódulos > 3mm, usando máscara completa como fallback.")
        return _build_seg_from_mask(images, mask_back.astype(bool), SERIES_DESC,
                                    is_malignant=is_malignant, score=score)

    series_desc = f"AI Seg: Nodules >3mm"
    return _build_multi_nodule_seg(
        images,
        seg_mask,
        series_desc,
        nodule_sizes,
        is_malignant=is_malignant,
        score=score,
    )
