# main.py
from __future__ import annotations

import os
import threading
import traceback
from io import BytesIO
from typing import List, Optional

import numpy as np
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import pydicom
from highdicom.seg.sop import Segmentation
from highdicom.seg.content import SegmentDescription, AlgorithmIdentificationSequence
from highdicom.seg.enum import SegmentationTypeValues, SegmentAlgorithmTypeValues
from highdicom.sr.coding import CodedConcept
from highdicom.uid import UID

# =======================
# Config
# =======================
DEFAULT_ORTHANC = os.getenv("ORTHANC_URL", "http://127.0.0.1:8042")
TIMEOUT = float(os.getenv("ORTHANC_TIMEOUT", "20"))  # s
MAX_FRAMES = int(os.getenv("SEG_MAX_FRAMES", "220"))  # para la demo; ajusta si lo necesitas

app = FastAPI(title="PACS-AI Assist Backend", version="0.2.0 (dummy-seg-fast)")


# =======================
# Modelos de request
# =======================
class AnalyzePayload(BaseModel):
    study_uid: Optional[str] = None
    StudyInstanceUID: Optional[str] = None
    series_uid: Optional[str] = None
    SeriesInstanceUID: Optional[str] = None
    sop_uid: Optional[str] = None
    SOPInstanceUID: Optional[str] = None
    orthanc: Optional[str] = None
    background: Optional[bool] = True


# =======================
# Helpers REST Orthanc
# =======================
def _r(orthanc: str, method: str, path: str, **kwargs) -> requests.Response:
    url = f"{orthanc.rstrip('/')}{path}"
    return requests.request(method, url, timeout=TIMEOUT, **kwargs)

def resolve_study_id_by_uid(orthanc: str, study_uid: str) -> str:
    # /tools/find es O(#studies filtradas); con UID único suele ser inmediato
    resp = _r(orthanc, "POST", "/tools/find", json={"Level": "Study", "Query": {"StudyInstanceUID": study_uid}})
    resp.raise_for_status()
    ids = resp.json()
    if not ids:
        raise HTTPException(404, detail=f"StudyInstanceUID {study_uid} no encontrado en Orthanc")
    return ids[0]

def get_series_ids_ct(orthanc: str, study_uid: str) -> List[str]:
    study_id = resolve_study_id_by_uid(orthanc, study_uid)
    resp = _r(orthanc, "GET", f"/studies/{study_id}/series")
    resp.raise_for_status()
    series = resp.json()
    return [s["ID"] for s in series if s.get("MainDicomTags", {}).get("Modality") == "CT"]

def get_instances_of_series(orthanc: str, series_id: str) -> List[str]:
    resp = _r(orthanc, "GET", f"/series/{series_id}/instances")
    resp.raise_for_status()
    inst = resp.json()
    # Ordena por InstanceNumber si existe
    def _key(it):
        try:
            return int(it.get("MainDicomTags", {}).get("InstanceNumber", "0"))
        except Exception:
            return 0
    inst_sorted = sorted(inst, key=_key)
    return [i["ID"] for i in inst_sorted]

def get_instance_tags(orthanc: str, instance_id: str) -> dict:
    resp = _r(orthanc, "GET", f"/instances/{instance_id}/simplified-tags?short=true")
    resp.raise_for_status()
    return resp.json()

def upload_dicom(orthanc: str, dicom_bytes: bytes) -> str:
    headers = {"Content-Type": "application/dicom"}
    resp = _r(orthanc, "POST", "/instances", data=dicom_bytes, headers=headers)
    resp.raise_for_status()
    return resp.json()["ID"]

# === Helpers de parseo seguros (añádelos cerca de los helpers de REST) ===
def _to_int(val, default: int = 0) -> int:
    try:
        if val is None:
            return default
        s = str(val)
        if "\\" in s:
            s = s.split("\\", 1)[0]
        s = s.strip()
        if s == "" or s == ".":
            return default
        return int(float(s))
    except Exception:
        return default

def _to_float_list(val, expected_len: int, fallback):
    """Convierte un tag DICOM (list o string con '\' o espacios) a lista de floats.
       Si hay '.', '', o longitudes inesperadas, aplica fallback o repite único valor."""
    if val is None:
        return list(fallback)
    if isinstance(val, list):
        parts = val
    else:
        s = str(val).replace(",", ".")
        parts = s.split("\\") if "\\" in s else s.split()
    out = []
    for p in parts:
        p = str(p).strip()
        if p in ("", "."):
            continue
        try:
            out.append(float(p))
        except Exception:
            pass
    if len(out) == expected_len:
        return out
    if len(out) == 1:
        return out * expected_len
    return list(fallback)

# === Sustituye COMPLETAMENTE tu collect_instances_meta por esta versión ===
def _clean_date(val: str, default="19000101"):
    try:
        s = (val or "").strip()
        s = s.replace("-", "")
        # aceptar YYYYMMDD (8) o YYYY.MM.DD -> limpiar puntos
        s = s.replace(".", "")
        return s if len(s) == 8 and s.isdigit() else default
    except Exception:
        return default

def _clean_time(val: str, default="000000"):
    try:
        s = (val or "").strip()
        s = s.replace(":", "")
        # aceptar HHMMSS[.ffffff]
        if "." in s:
            s = s.split(".", 1)[0]
        return s if len(s) >= 2 else default  # con HH basta; DICOM permite precisiones variables
    except Exception:
        return default

def collect_instances_meta(orthanc: str, inst_ids: List[str]) -> List[dict]:
    metas = []
    temp = []
    first_tags = None

    for iid in inst_ids:
        tags = get_instance_tags(orthanc, iid)
        if first_tags is None:
            first_tags = tags
        inst_no = _to_int(tags.get("InstanceNumber"), 0)
        temp.append((inst_no, tags))

    temp.sort(key=lambda t: t[0])

    # Paciente/estudio base (del primer tag disponible)
    patient_id    = (first_tags or {}).get("PatientID") or "PACS-AI-UNKNOWN"
    patient_name  = (first_tags or {}).get("PatientName") or "PACS^AI"
    patient_birth = _clean_date((first_tags or {}).get("PatientBirthDate"), "19000101")
    patient_sex   = (first_tags or {}).get("PatientSex") or "O"  # M/F/O

    study_date    = _clean_date((first_tags or {}).get("StudyDate"), "19000101")
    study_time    = _clean_time((first_tags or {}).get("StudyTime"), "000000")
    accession_no  = (first_tags or {}).get("AccessionNumber") or ""   # puede ser vacío
    study_id      = (first_tags or {}).get("StudyID") or "1"          # entero/str válido para DICOM
    study_desc    = (first_tags or {}).get("StudyDescription") or ""  # opcional

    for _, tags in temp:
        ps = _to_float_list(tags.get("PixelSpacing"), 2, fallback=[1.0, 1.0])
        io = _to_float_list(tags.get("ImageOrientationPatient"), 6, fallback=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0])
        ip = _to_float_list(tags.get("ImagePositionPatient"), 3, fallback=[0.0, 0.0, 0.0])

        metas.append({
            "sop_instance_uid":        tags.get("SOPInstanceUID"),
            "series_instance_uid":     tags.get("SeriesInstanceUID"),
            "study_instance_uid":      tags.get("StudyInstanceUID"),
            "frame_of_reference_uid":  tags.get("FrameOfReferenceUID"),
            "rows":                    _to_int(tags.get("Rows"), 512),
            "cols":                    _to_int(tags.get("Columns"), 512),
            "pixel_spacing":           ps,
            "image_orientation":       io,
            "image_position":          ip,
            # —— paciente / estudio (para tu highdicom) ——
            "patient_id":              patient_id,
            "patient_name":            patient_name,
            "patient_birth_date":      patient_birth,
            "patient_sex":             patient_sex,
            "study_date":              study_date,
            "study_time":              study_time,
            "accession_number":        accession_no,
            "study_id":                study_id,
            "study_description":       study_desc,
        })
    return metas





def build_dummy_seg_fast(instances_meta: List[dict]) -> bytes:
    rows = int(instances_meta[0]["rows"])
    cols = int(instances_meta[0]["cols"])
    n    = len(instances_meta)

    # Máscara dummy vectorizada (círculo)
    yy, xx = np.ogrid[:rows, :cols]
    cy, cx = rows // 2, cols // 2
    r = int(min(rows, cols) * 0.18)
    circle = ((yy - cy) ** 2 + (xx - cx) ** 2) <= r * r
    mask = np.repeat(circle[np.newaxis, ...], n, axis=0).astype(np.uint8)

    orientation = np.asarray(instances_meta[0]["image_orientation"], dtype=float)
    spacing     = np.asarray(instances_meta[0]["pixel_spacing"], dtype=float)
    positions   = np.asarray([m["image_position"] for m in instances_meta], dtype=float)
    sop_uids    = [m["sop_instance_uid"] for m in instances_meta]

    from highdicom.sr.coding import CodedConcept, Code
    from highdicom.seg.content import SegmentDescription
    from highdicom.seg.enum import SegmentAlgorithmTypeValues

    # ...

    # Identificación del algoritmo: family debe ser un Code (no string)
    algo = AlgorithmIdentificationSequence(
        name="PACS-AI Dummy",
        version="0.1.0",
        family=Code("PACSALG", "99PACS", "AI Segmentation")  # <- Code(value, scheme, meaning)
    )

    # SegmentDescription con algorithm_identification (requerido si AUTOMATIC)
    seg_desc = SegmentDescription(
        segment_number=1,
        segment_label="Dummy ROI",
        segmented_property_category=CodedConcept("49755003", "SCT", "Anatomical Structure"),
        segmented_property_type=CodedConcept("39607008", "SCT", "Lesion"),
        algorithm_type=SegmentAlgorithmTypeValues.AUTOMATIC,
        algorithm_identification=algo,
    )


    # === calcular SliceThickness desde la geometría ===
    orientation = np.asarray(instances_meta[0]["image_orientation"], dtype=float)
    row = orientation[:3]
    col = orientation[3:6]
    normal = np.cross(row, col)
    positions = np.asarray([m["image_position"] for m in instances_meta], dtype=float)

    dz = []
    for i in range(len(positions) - 1):
        v = positions[i + 1] - positions[i]
        dz.append(abs(float(np.dot(v, normal))))
    thickness = float(np.median(dz)) if len(dz) > 0 and np.median(dz) > 0 else 1.0


    # Referencias mínimas a imágenes fuente (sin leer píxeles)
    from pydicom.uid import UID

    ct_sop_class = UID("1.2.840.10008.5.1.4.1.1.2")  # CT Image Storage
    series_uid   = instances_meta[0]["series_instance_uid"]
    study_uid    = instances_meta[0]["study_instance_uid"]
    for_uid      = instances_meta[0]["frame_of_reference_uid"]

    patient_id    = instances_meta[0].get("patient_id", "PACS-AI-UNKNOWN")
    patient_name  = instances_meta[0].get("patient_name", "PACS^AI")
    patient_birth = instances_meta[0].get("patient_birth_date", "19000101")
    patient_sex   = instances_meta[0].get("patient_sex", "O")

    study_date    = instances_meta[0].get("study_date", "19000101")
    study_time    = instances_meta[0].get("study_time", "000000")
    accession_no  = instances_meta[0].get("accession_number", "")
    study_id      = instances_meta[0].get("study_id", "1")
    study_desc    = instances_meta[0].get("study_description", "")

    src_images = []
    for i, m in enumerate(instances_meta):
        d = pydicom.Dataset()
        # Identificación
        d.SOPClassUID = ct_sop_class
        d.SOPInstanceUID = m["sop_instance_uid"]
        d.StudyInstanceUID = study_uid
        d.SeriesInstanceUID = series_uid
        d.FrameOfReferenceUID = for_uid
        d.Modality = "CT"
        # Paciente
        d.PatientID = patient_id
        d.PatientName = patient_name
        d.PatientBirthDate = patient_birth
        d.PatientSex = patient_sex
        # Estudio
        d.StudyDate = study_date
        d.StudyTime = study_time
        d.AccessionNumber = accession_no
        d.StudyID = study_id
        d.StudyDescription = study_desc
        # Geometría mínima
        d.Rows = int(m["rows"])
        d.Columns = int(m["cols"])
        d.PixelSpacing = [float(x) for x in m["pixel_spacing"]]
        d.ImageOrientationPatient = [float(x) for x in m["image_orientation"]]
        d.ImagePositionPatient = [float(x) for x in m["image_position"]]
        d.SliceThickness = thickness
        d.SpacingBetweenSlices = thickness

        # Orden sugerido
        d.InstanceNumber = i + 1
        src_images.append(d)




    from pydicom.uid import generate_uid  # ponlo junto a los imports de arriba


    seg = Segmentation(
        source_images=src_images,
        pixel_array=mask,
        segmentation_type=SegmentationTypeValues.BINARY,
        segment_descriptions=[seg_desc],

        # >>> tu versión exige esto:
        series_instance_uid=series_uid,
        series_number=999,
        sop_instance_uid=generate_uid(),
        instance_number=1,
        manufacturer="PACS-AI Assist",
        manufacturer_model_name="PACS-AI Dummy",
        software_versions="0.1.0",
        device_serial_number="PACS-AI-0001",
    )

    # Color recomendado (opcional)
    try:
        seg.SegmentSequence[0].RecommendedDisplayCIELabValue = [40000, 20000, 20000]
    except Exception:
        pass

    seg.is_little_endian = True
    seg.is_implicit_VR = False
    buf = BytesIO()
    seg.save_as(buf, write_like_original=True)
    return bytes(buf.getvalue())


# =======================
# Worker (background)
# =======================
def process_study_background(orthanc_url: str, study_uid: str):
    try:
        series_ids = get_series_ids_ct(orthanc_url, study_uid)
        if not series_ids:
            print(f"[AI] Study {study_uid}: no hay series CT"); return

        series_id = series_ids[0]
        inst_ids = get_instances_of_series(orthanc_url, series_id)
        if not inst_ids:
            print(f"[AI] Study {study_uid}: serie CT sin instancias"); return

        # Limita frames para demo si se configuró MAX_FRAMES
        if MAX_FRAMES > 0:
            inst_ids = inst_ids[:MAX_FRAMES]

        metas = collect_instances_meta(orthanc_url, inst_ids)
        seg_bytes = build_dummy_seg_fast(metas)
        new_id = upload_dicom(orthanc_url, seg_bytes)
        print(f"[AI] SEG subido: {new_id} (Study {study_uid})")
    except Exception:
        print("[AI] Error background:\n", traceback.format_exc())


# =======================
# Endpoints
# =======================
@app.get("/health")
def health():
    return {"status": "ok", "orthanc": DEFAULT_ORTHANC}

@app.post("/analyze/download-only")
def analyze_download_only(payload: AnalyzePayload):
    try:
        study_uid = payload.study_uid or payload.StudyInstanceUID
        if not study_uid:
            raise HTTPException(status_code=400, detail="Falta 'study_uid' (o 'StudyInstanceUID').")

        orthanc = (payload.orthanc or DEFAULT_ORTHANC).rstrip("/")
        background = True if payload.background is None else payload.background

        if background:
            threading.Thread(
                target=process_study_background,
                args=(orthanc, study_uid),
                daemon=True,
            ).start()
            return {"status": "queued", "StudyInstanceUID": study_uid, "orthanc": orthanc}

        # Procesamiento síncrono (por si quieres forzarlo)
        series_ids = get_series_ids_ct(orthanc, study_uid)
        if not series_ids:
            raise HTTPException(404, detail="No se encontró serie CT en el estudio.")
        inst_ids = get_instances_of_series(orthanc, series_ids[0])
        if not inst_ids:
            raise HTTPException(404, detail="La serie CT no tiene instancias.")
        if MAX_FRAMES > 0:
            inst_ids = inst_ids[:MAX_FRAMES]

        metas = collect_instances_meta(orthanc, inst_ids)
        seg_bytes = build_dummy_seg_fast(metas)
        new_id = upload_dicom(orthanc, seg_bytes)
        return {"status": "done", "StudyInstanceUID": study_uid, "seg_instance_id": new_id, "orthanc": orthanc}

    except HTTPException:
        raise
    except Exception as e:
        print("[AI] Error request:\n", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# =======================
# Run (local)
# =======================
# Ejecuta con:
# uvicorn main:app --host 127.0.0.1 --port 8001 --reload
