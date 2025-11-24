# pacs_ai_deploy/pacsai_model.py
from __future__ import annotations

import copy
import io
from collections import defaultdict
from typing import List

import numpy as np
import pydicom
import requests
from highdicom.seg import Segmentation
from highdicom.seg.content import SegmentDescription
from highdicom.sr.coding import Code
from pydicom.uid import generate_uid


# ============================================================
# Utilidades geométricas / helpers
# ============================================================
def _as_floats(x):
    return [float(v) for v in (list(x) if isinstance(x, (list, tuple)) else [x])]

def _get_iop(ds):
    iop = getattr(ds, "ImageOrientationPatient", None)
    if not iop or len(iop) != 6:
        raise RuntimeError("IOP inválido o ausente en una imagen.")
    return [float(v) for v in iop]

def _get_ipp(ds):
    ipp = getattr(ds, "ImagePositionPatient", None)
    if not ipp or len(ipp) != 3:
        raise RuntimeError("IPP inválido o ausente en una imagen.")
    return [float(v) for v in ipp]

def _cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]

def _dot(a, b):
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]

def _norm(v):
    import math
    n = math.sqrt(_dot(v, v))
    return [vi/n for vi in v] if n else v

def _project_distance_along_normal(ipp, origin, normal):
    return _dot([ipp[0]-origin[0], ipp[1]-origin[1], ipp[2]-origin[2]], normal)

def _dedupe_and_sort_images(images, mm_tol=1e-3):
    """Ordena por la normal del volumen y elimina duplicados (misma posición)."""
    if not images:
        return images
    iop0 = _get_iop(images[0])
    row = iop0[0:3]; col = iop0[3:6]
    normal = _norm(_cross(row, col))
    origin = _get_ipp(images[0])

    def _same_iop(ds):
        iop = _get_iop(ds)
        return all(abs(iop[i]-iop0[i]) < 1e-6 for i in range(6))

    imgs = [im for im in images if _same_iop(im)]

    tmp = []
    for im in imgs:
        d = _project_distance_along_normal(_get_ipp(im), origin, normal)
        tmp.append((d, im))
    tmp.sort(key=lambda t: t[0])

    dedup, last_d = [], None
    for d, im in tmp:
        if last_d is None or abs(d-last_d) > mm_tol:
            dedup.append(im); last_d = d
    return dedup

def _inject_slice_thickness(images):
    """Calcula/inserta SliceThickness y SpacingBetweenSlices si faltan."""
    if not images:
        return
    if len(images) == 1:
        if not hasattr(images[0], "SliceThickness"):
            images[0].SliceThickness = 1.0
        if not hasattr(images[0], "SpacingBetweenSlices"):
            images[0].SpacingBetweenSlices = float(images[0].SliceThickness)
        return
    iop0 = _get_iop(images[0])
    n = _norm(_cross(iop0[:3], iop0[3:]))
    dists = []
    prev = _get_ipp(images[0])
    for ds in images[1:]:
        cur = _get_ipp(ds)
        d = _dot([cur[0]-prev[0], cur[1]-prev[1], cur[2]-prev[2]], n)
        if abs(d) > 1e-5:
            dists.append(abs(d))
        prev = cur
    thick = 1.0 if not dists else (sorted(dists)[len(dists)//2])
    for ds in images:
        if not hasattr(ds, "SliceThickness"):
            ds.SliceThickness = float(thick)
        if not hasattr(ds, "SpacingBetweenSlices"):
            ds.SpacingBetweenSlices = float(thick)


# ============================================================
# HTTP utils contra Orthanc
# ============================================================
def _rq(base, method, path, **kw):
    return requests.request(method, f"{base.rstrip('/')}{path}", timeout=20, **kw)

def _find_instance_id_by_sop(orthanc_url: str, sop_uid: str) -> str:
    r = _rq(orthanc_url, "POST", "/tools/find",
            json={"Level": "Instance", "Query": {"SOPInstanceUID": sop_uid}})
    r.raise_for_status()
    ids = r.json()
    if not ids:
        raise RuntimeError(f"No se encontró instance para SOPInstanceUID={sop_uid}")
    return ids[0]

def _find_instance_id_optional(orthanc_url: str, sop_uid: str) -> str | None:
    r = _rq(orthanc_url, "POST", "/tools/find",
            json={"Level": "Instance", "Query": {"SOPInstanceUID": sop_uid}})
    r.raise_for_status()
    ids = r.json()
    return ids[0] if ids else None

def _upload_ds_to_orthanc(orthanc_url: str, ds: pydicom.dataset.Dataset) -> str:
    buf = io.BytesIO()
    ds.save_as(buf, write_like_original=False)
    r = _rq(orthanc_url, "POST", "/instances",
            data=buf.getvalue(),
            headers={"Content-Type": "application/dicom"})
    r.raise_for_status()
    return r.json()["ID"]

def _ensure_sources_uploaded(orthanc_url: str, images: list[pydicom.dataset.Dataset]) -> None:
    for ds in images:
        sop = str(ds.SOPInstanceUID)
        if _find_instance_id_optional(orthanc_url, sop) is None:
            _upload_ds_to_orthanc(orthanc_url, ds)


# ============================================================
# Metadatos desde backend
# ============================================================
def _group_metas_by_series(metas: List[dict]):
    g = defaultdict(list)
    for m in metas:
        g[m["series_instance_uid"]].append(m)
    for sid in g:
        g[sid] = sorted(g[sid], key=lambda x: x.get("instance_number", 0))
    return g


# ============================================================
# Functional Groups helpers
# ============================================================
def _ds_get(ds, name, default=None):
    try:
        return getattr(ds, name)
    except Exception:
        return default

def _from_shared_fg(ds):
    sfg = _ds_get(ds, "SharedFunctionalGroupsSequence")
    if sfg and len(sfg) > 0:
        return sfg[0]
    return None

def _from_perframe_fg(ds):
    return _ds_get(ds, "PerFrameFunctionalGroupsSequence") or []

def _ensure_root_geom(ds: pydicom.FileDataset, fallback_meta: dict):
    """Asegura IOP, PixelSpacing y FrameOfReference en el nivel raíz."""
    sfg = _from_shared_fg(ds)
    if not hasattr(ds, "ImageOrientationPatient") and sfg and hasattr(sfg, "PlaneOrientationSequence"):
        ds.ImageOrientationPatient = list(sfg.PlaneOrientationSequence[0].ImageOrientationPatient)
    if not hasattr(ds, "PixelSpacing") and sfg and hasattr(sfg, "PixelMeasuresSequence"):
        pm = sfg.PixelMeasuresSequence[0]
        ds.PixelSpacing = [float(pm.PixelSpacing[0]), float(pm.PixelSpacing[1])]
    if not hasattr(ds, "FrameOfReferenceUID") and fallback_meta.get("frame_of_reference_uid"):
        ds.FrameOfReferenceUID = str(fallback_meta["frame_of_reference_uid"])
    return _from_perframe_fg(ds)


# ============================================================
# Multi-frame → single-frame
# ============================================================
def _explode_multiframe_to_single_frames(ds: pydicom.FileDataset, metas_first: dict):
    """Convierte un CT multi-frame a lista de datasets single-frame."""
    pfg = _ensure_root_geom(ds, metas_first)
    nframes = int(_ds_get(ds, "NumberOfFrames", 1))
    if nframes <= 1:
        return [ds]

    try:
        arr = ds.pixel_array
    except Exception as e:
        raise RuntimeError(
            "No se pudo leer PixelData (transfer syntax comprimida?). "
            "Instala decoders: pylibjpeg + pylibjpeg-libjpeg + pylibjpeg-openjpeg o gdcm"
        ) from e

    if arr.ndim == 4:
        arr = arr[..., 0]
    if arr.ndim != 3:
        raise RuntimeError(f"Dimensión de pixel_array inesperada: {arr.shape}")

    rows = int(ds.Rows); cols = int(ds.Columns)
    iop = list(_ds_get(ds, "ImageOrientationPatient"))
    ps  = list(_ds_get(ds, "PixelSpacing"))

    singles = []
    for idx in range(nframes):
        dsi = pydicom.dataset.FileDataset(
            filename_or_obj=None,
            dataset=copy.deepcopy(ds),
            preamble=ds.preamble,
            file_meta=copy.deepcopy(ds.file_meta),
        )
        for attr in ["NumberOfFrames", "PerFrameFunctionalGroupsSequence", "SharedFunctionalGroupsSequence"]:
            if hasattr(dsi, attr):
                delattr(dsi, attr)

        dsi.SOPClassUID = "1.2.840.10008.5.1.4.1.1.2"  # CT Image Storage
        dsi.SOPInstanceUID = generate_uid()

        dsi.ImageOrientationPatient = iop
        if pfg and len(pfg) > idx and hasattr(pfg[idx], "PlanePositionSequence"):
            ipp = list(pfg[idx].PlanePositionSequence[0].ImagePositionPatient)
        else:
            raise RuntimeError("No se pudo obtener ImagePositionPatient por frame.")
        dsi.ImagePositionPatient = ipp
        dsi.PixelSpacing = ps
        dsi.Rows = rows
        dsi.Columns = cols

        dsi.SamplesPerPixel = 1
        dsi.PhotometricInterpretation = "MONOCHROME2"
        dsi.BitsAllocated = int(_ds_get(ds, "BitsAllocated", 16))
        dsi.BitsStored = int(_ds_get(ds, "BitsStored", 12))
        dsi.HighBit = int(_ds_get(ds, "HighBit", dsi.BitsStored - 1))
        dsi.PixelRepresentation = int(_ds_get(ds, "PixelRepresentation", 0))
        dsi.is_little_endian = True
        dsi.is_implicit_VR = False

        dsi.PixelData = arr[idx].astype(arr.dtype, copy=False).tobytes(order="C")
        dsi.InstanceNumber = idx + 1

        singles.append(dsi)

    return singles


def _download_source_images(orthanc_url: str, metas_sorted: list[dict]):
    """Descarga cada instancia; si es multi-frame, la explota a single-frame."""
    dsets_all = []
    for m in metas_sorted:
        iid = _find_instance_id_by_sop(orthanc_url, m["sop_instance_uid"])
        f = _rq(orthanc_url, "GET", f"/instances/{iid}/file")
        f.raise_for_status()
        ds = pydicom.dcmread(io.BytesIO(f.content))
        singles = _explode_multiframe_to_single_frames(ds, m)
        dsets_all.extend(singles)
    dsets_all.sort(key=lambda d: int(getattr(d, "InstanceNumber", 0)))
    return dsets_all


# ============================================================
# Construcción de DICOM SEG
# ============================================================
def _build_empty_seg(source_images: list, series_desc: str) -> bytes:
    rows = int(source_images[0].Rows)
    cols = int(source_images[0].Columns)
    num  = len(source_images)

    # 1 bit/píxel → SEG liviano
    mask = np.zeros((num, rows, cols), dtype=bool)

    seg_desc = [
        SegmentDescription(
            segment_number=1,
            segment_label="No Finding (Demo)",
            segmented_property_category=Code("49755003", "SCT", "Morphologically Altered Structure"),
            segmented_property_type=Code("364665006", "SCT", "Anatomical or Acquired Body Structure"),
            # Mantener MANUAL para no exigir AlgorithmIdentification
            algorithm_type="MANUAL",
        )
    ]

    seg = Segmentation(
        source_images=source_images,
        pixel_array=mask,
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

    # Guardar como DICOM (en versiones nuevas Segmentation ya es Dataset)
    buf = io.BytesIO()
    ds = seg if isinstance(seg, pydicom.dataset.Dataset) else seg.to_dataset()
    ds.save_as(buf, write_like_original=False)
    return buf.getvalue()


# ============================================================
# ENTRYPOINT para main.py
# ============================================================
def build_seg_from_meta(metas: List[dict], orthanc_url: str) -> bytes:
    groups = _group_metas_by_series(metas)
    best_sid, best_metas = max(groups.items(), key=lambda kv: len(kv[1]))

    # Descargar imágenes y preparar
    src_images = _download_source_images(orthanc_url, best_metas)
    src_images = _dedupe_and_sort_images(src_images, mm_tol=1e-3)

    # Subir single-frame a Orthanc para que OHIF pueda resolver referencias
    _ensure_sources_uploaded(orthanc_url, src_images)

    # Inyectar SliceThickness/SpacingBetweenSlices si faltan
    _inject_slice_thickness(src_images)

    if len(src_images) < 2:
        print(f"[MODEL] Advertencia: solo {len(src_images)} slice(s) tras dedupe.")

    # Construir y retornar el SEG
    seg_bytes = _build_empty_seg(src_images, "PACS-AI Segmentation")
    return seg_bytes
