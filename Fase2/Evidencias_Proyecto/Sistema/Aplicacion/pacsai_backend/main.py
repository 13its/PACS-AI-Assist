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

# 1) ---- Schema primero ----
class AnalyzeDownloadOnlyReq(BaseModel):
    StudyInstanceUID: str
    SeriesInstanceUID: Optional[str] = None
    SOPInstanceUID: Optional[str] = None
    download_only: bool = True

# 2) ---- Endpoints ----
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
def analyze_download_only(req: AnalyzeDownloadOnlyReq):
    study_uid  = req.StudyInstanceUID
    series_uid = req.SeriesInstanceUID
    sop_uid    = req.SOPInstanceUID
    try:
        # Autocompletar si faltan
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

        # Valida que el SOP exista en Orthanc (si no, revienta aquí)
        #_ = lookup_instance_id(sop_uid)

        # Descarga/ordenación (prueba de flujo)
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

    except HTTPException:
        raise
    except requests.HTTPError as e:
        return JSONResponse(status_code=e.response.status_code,
                            content={"error": "HTTPError desde Orthanc", "body": e.response.text})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, f"Error interno: {e}")
