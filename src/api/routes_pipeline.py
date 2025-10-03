from fastapi import APIRouter
from pydantic import BaseModel
from pathlib import Path
from ..core.dicom_io import load_series_from_folder
from ..core.preprocessing import run_preprocess
from ..core.utils import make_outdir

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

class PreprocReq(BaseModel):
    input_dir: str

@router.post("/preprocess")
def preprocess(req: PreprocReq):
    img, meta = load_series_from_folder(Path(req.input_dir))
    out_dir = make_outdir(meta)
    result = run_preprocess(img, meta, out_dir)
    return {"status": "ok", "out_dir": str(out_dir), "timings": result["timings"]}
