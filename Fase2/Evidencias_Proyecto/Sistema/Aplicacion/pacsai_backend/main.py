
from __future__ import annotations

import importlib
import os
import threading
import traceback
from typing import List, Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


import sys
from pathlib import Path

# Asegurar que el directorio padre (Aplicacion) esté en sys.path,
# así Python puede importar tanto `pacsai_backend` como `pacs_ai_deploy`.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --------------------
# Logging helper
# --------------------
def log(msg: str):
    print(msg, flush=True)

# ====================
# Config
# ====================
ORTHANC_URL = os.getenv("ORTHANC_URL", "http://127.0.0.1:8042").rstrip("/")
TIMEOUT = float(os.getenv("ORTHANC_TIMEOUT", "20"))  # seconds
APP_VERSION = "0.4.1 (analyze-on-click, logs, safe-model)"

# Model entrypoint: module:function que devuelve bytes DICOM SEG
# Por defecto usamos el segmentador 3D multi-nódulo
MODEL_ENTRYPOINT = os.getenv(
    "PACSAI_MODEL_ENTRYPOINT",
    "pacs_ai_deploy.backend.backend_inference:build_seg_from_meta",
).strip()


app = FastAPI(title="PACS-AI Assist Backend", version=APP_VERSION)

# CORS so the viewer (Orthanc UI @8042) can call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8042",
        "http://localhost:8042",
        "http://localhost:8042/",
        "http://127.0.0.1:8042/",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====================
# Pydantic payloads
# ====================
class AnalyzeIn(BaseModel):
    StudyInstanceUID: str
    orthanc: Optional[str] = None
    replace_existing: bool = True

class AnalyzeAck(BaseModel):
    queued: bool
    study_uid: str
    message: str

# ====================
# Orthanc helpers
# ====================
def _rq(method: str, path: str, *, orthanc: Optional[str] = None, **kwargs) -> requests.Response:
    base = (orthanc or ORTHANC_URL).rstrip("/")
    url = f"{base}{path}"
    return requests.request(method, url, timeout=TIMEOUT, **kwargs)

def resolve_study_id(study_uid: str, *, orthanc: Optional[str] = None) -> str:
    r = _rq("POST", "/tools/find", orthanc=orthanc, json={"Level":"Study","Query":{"StudyInstanceUID": study_uid}})
    r.raise_for_status()
    ids = r.json()
    if not ids:
        raise HTTPException(404, f"StudyInstanceUID {study_uid} no encontrado en Orthanc")
    return ids[0]

def list_ct_series_ids(study_id: str, *, orthanc: Optional[str] = None) -> List[str]:
    r = _rq("GET", f"/studies/{study_id}/series", orthanc=orthanc)
    r.raise_for_status()
    series = r.json()

    ct_ids = []
    for s in series:
        mtags = s.get("MainDicomTags", {})
        mod = (mtags.get("Modality") or "").upper().strip()
        desc = (mtags.get("SeriesDescription") or "").lower()
        sop_uid = None
        insts = s.get("Instances", [])
        if insts:
            try:
                inst_info = _rq("GET", f"/instances/{insts[0]}", orthanc=orthanc).json()
                sop_uid = inst_info.get("MainDicomTags", {}).get("SOPClassUID")
            except Exception:
                pass

        # Excluir SEG o SR
        if "seg" in desc or "SR" in mod:
            continue

        # Incluir CT estándar o Enhanced
        if mod == "CT" or sop_uid in ("1.2.840.10008.5.1.4.1.1.2", "1.2.840.10008.5.1.4.1.1.2.1"):
            ct_ids.append(s["ID"])

    if not ct_ids:
        log("[DEBUG] No se encontró serie CT. Series disponibles:")
        for s in series:
            log(str(s.get("MainDicomTags", {})))
        raise RuntimeError("No se encontró una serie CT en el estudio")

    return ct_ids


def list_instance_ids(series_id: str, *, orthanc: Optional[str] = None) -> List[str]:
    r = _rq("GET", f"/series/{series_id}/instances", orthanc=orthanc)
    r.raise_for_status()
    instances = r.json()
    def _key(it):
        try:
            return int(it.get("MainDicomTags", {}).get("InstanceNumber", "0"))
        except Exception:
            return 0
    instances = sorted(instances, key=_key)
    return [i["ID"] for i in instances]

def fetch_instance_simplified_tags(instance_id: str, *, orthanc: Optional[str] = None) -> dict:
    r = _rq("GET", f"/instances/{instance_id}/simplified-tags?short=true", orthanc=orthanc)
    r.raise_for_status()
    return r.json()

def upload_dicom(dicom_bytes: bytes, *, orthanc: Optional[str] = None) -> str:
    r = _rq("POST", "/instances", orthanc=orthanc, data=dicom_bytes, headers={"Content-Type":"application/dicom"})
    r.raise_for_status()
    return r.json()["ID"]

def delete_existing_seg_series(study_id: str, *, orthanc: Optional[str] = None, series_description: str = "PACS-AI Segmentation"):
    try:
        r = _rq("GET", f"/studies/{study_id}/series", orthanc=orthanc)
        r.raise_for_status()
        for se in r.json():
            if se.get("MainDicomTags", {}).get("SeriesDescription") == series_description:
                _rq("DELETE", f"/series/{se['ID']}", orthanc=orthanc)
    except Exception as e:
        log(f"[WARN] No se pudo limpiar series previas: {e}")

# ====================
# Metadata collection
# ====================
def _to_int(val, default=0):
    try:
        s = str(val or "").strip()
        if "\\" in s:
            s = s.split("\\", 1)[0]
        return int(float(s))
    except Exception:
        return default

def collect_instances_meta(instance_ids: List[str], *, orthanc: Optional[str] = None) -> List[dict]:
    metas = []
    for iid in instance_ids:
        tags = fetch_instance_simplified_tags(iid, orthanc=orthanc)
        metas.append({
            "sop_instance_uid": tags.get("SOPInstanceUID"),
            "series_instance_uid": tags.get("SeriesInstanceUID"),
            "study_instance_uid": tags.get("StudyInstanceUID"),
            "frame_of_reference_uid": tags.get("FrameOfReferenceUID"),
            "rows": _to_int(tags.get("Rows"), 512),
            "cols": _to_int(tags.get("Columns"), 512),
            "pixel_spacing": tags.get("PixelSpacing"),
            "image_orientation": tags.get("ImageOrientationPatient"),
            "image_position": tags.get("ImagePositionPatient"),
            "patient_id": tags.get("PatientID"),
            "patient_name": tags.get("PatientName"),
            "patient_birth_date": tags.get("PatientBirthDate"),
            "patient_sex": tags.get("PatientSex"),
            "study_date": tags.get("StudyDate"),
            "study_time": tags.get("StudyTime"),
            "accession_number": tags.get("AccessionNumber"),
            "study_id": tags.get("StudyID"),
            "study_description": tags.get("StudyDescription"),
            "instance_number": _to_int(tags.get("InstanceNumber"), 0),
        })
    metas.sort(key=lambda m: m["instance_number"])
    return metas

# ====================
# Pluggable model loader
# ====================
def _load_model_entrypoint():
    if not MODEL_ENTRYPOINT:
        return None
    try:
        module_name, func_name = MODEL_ENTRYPOINT.split(":", 1)
        mod = importlib.import_module(module_name)
        fn = getattr(mod, func_name)
        return fn
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar el entrypoint '{MODEL_ENTRYPOINT}': {e}")

# ====================
# Worker (background)
# ====================
def _worker_analyze(study_uid: str, orthanc: Optional[str], replace_existing: bool):
    try:
        log(f"[WORKER] start study_uid={study_uid}")
        study_id = resolve_study_id(study_uid, orthanc=orthanc)
        series_ids = list_ct_series_ids(study_id, orthanc=orthanc)
        if not series_ids:
            raise RuntimeError("No se encontró una serie CT en el estudio")
        series_id = series_ids[0]
        log(f"[WORKER] series_id={series_id}")

        instance_ids = list_instance_ids(series_id, orthanc=orthanc)
        if not instance_ids:
            raise RuntimeError("La serie CT no contiene instancias")
        log(f"[WORKER] instances={len(instance_ids)}")

        metas = collect_instances_meta(instance_ids, orthanc=orthanc)
        log("[WORKER] meta recolectada")

        entrypoint = _load_model_entrypoint()
        if entrypoint is None:
            log("[WORKER] MODEL_ENTRYPOINT no configurado; flujo OK (no se corre IA)")
            return

        log(f"[WORKER] ejecutando modelo: {MODEL_ENTRYPOINT}")
        seg_bytes = entrypoint(metas, (orthanc or ORTHANC_URL))

        if replace_existing:
            delete_existing_seg_series(study_id, orthanc=orthanc)

        new_id = upload_dicom(seg_bytes, orthanc=orthanc)
        log(f"[WORKER] SEG subido: {new_id} (StudyUID={study_uid})")
    except Exception as e:
        log(f"[WORKER] ERROR: {e}")
        log(traceback.format_exc())

# ====================
# API
# ====================
@app.get("/health")
def health():
    return {"status":"ok", "orthanc": ORTHANC_URL, "version": APP_VERSION, "model": MODEL_ENTRYPOINT or "(no configurado)"}

@app.post("/analyze", response_model=AnalyzeAck)
def analyze(req: AnalyzeIn):
    study_uid = (req.StudyInstanceUID or "").strip()
    if not study_uid:
        raise HTTPException(400, "Falta StudyInstanceUID")

    orthanc = (req.orthanc or ORTHANC_URL).rstrip("/")
    log(f"[API] /analyze queued study_uid={study_uid} orthanc={orthanc} replace={req.replace_existing}")

    th = threading.Thread(target=_worker_analyze, args=(study_uid, orthanc, req.replace_existing), daemon=True)
    th.start()

    return AnalyzeAck(queued=True, study_uid=study_uid, message="Análisis encolado (disparado por botón).")
