# main.py
from typing import Optional
import traceback, requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from settings import DICOMWEB
from orthanc_client import (
    qido_series, pick_ct_series, load_volume_sorted,
    lookup_instance_id, find_series_ids_ct, get_series_uid,
    get_instances_of_series, get_instance_tags
)

app = FastAPI(title="PACS-AI Assist Backend")

# 1) ---- Schemas ----
class AnalyzeDownloadOnlyReq(BaseModel):
    StudyInstanceUID: str
    SeriesInstanceUID: Optional[str] = None
    SOPInstanceUID: Optional[str] = None
    download_only: bool = True

# Body que manda tu Lua actual (con "study_uid")
class HookReq(BaseModel):
    orthanc: Optional[str] = None
    study_uid: str

# --- Core de la lógica de análisis ---
def _analyze_core(study_uid: str,
                  series_uid: Optional[str],
                  sop_uid: Optional[str]):
    if not series_uid or not sop_uid:
        series_ids = find_series_ids_ct(study_uid)
        if not series_ids:
            raise HTTPException(404, "No hay series CT para ese Study")

        series_id  = series_ids[0]
        series_uid = series_uid or get_series_uid(series_id)

        inst_ids = get_instances_of_series(series_id)
        if not inst_ids:
            raise HTTPException(404, "La serie CT no tiene instancias")

        if not sop_uid:
            tags = get_instance_tags(inst_ids[0])
            sop_uid = tags.get("SOPInstanceUID")
            if not sop_uid:
                raise HTTPException(404, "No pude leer SOPInstanceUID de la instancia")

    # Descarga/ordenación (flujo de prueba)
    volume, _ = load_volume_sorted(study_uid, series_uid)
    z, y, x = map(int, volume.shape)
    return {
        "status": "downloaded",
        "StudyInstanceUID": study_uid,
        "SeriesInstanceUID": series_uid,
        "SOPInstanceUID": sop_uid,
        "slices": z,
        "shape": [z, y, x],
    }

# ---- Endpoints ----
@app.get("/ping")
def ping():
    return {"ok": True, "dicomweb": DICOMWEB}

@app.get("/debug/series/{study_uid}")
def debug_series(study_uid: str):
    try:
        data = qido_series(study_uid)
        return {"count": len(data), "sample": data[0] if data else None}
    except requests.HTTPError as e:
        return JSONResponse(status_code=e.response.status_code, content={"error": e.response.text})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/analyze/download-only")
def analyze_download_only(payload: dict):
    try:
        study_uid  = payload.get("StudyInstanceUID") or payload.get("study_uid")
        series_uid = payload.get("SeriesInstanceUID") or payload.get("series_uid")
        sop_uid    = payload.get("SOPInstanceUID")    or payload.get("sop_uid")

        if not study_uid:
            raise HTTPException(400, "Payload inválido: falta StudyInstanceUID/study_uid")

        return _analyze_core(study_uid, series_uid, sop_uid)

    except HTTPException:
        raise
    except requests.HTTPError as e:
        return JSONResponse(status_code=e.response.status_code,
                            content={"error": "HTTPError desde Orthanc", "body": e.response.text})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error interno: {e}")

