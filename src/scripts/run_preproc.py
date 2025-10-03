import argparse, sys, traceback
from pathlib import Path
from src.core.dicom_io import load_series_from_folder
from src.core.preprocessing import run_preprocess
from src.core.utils import log_json, make_outdir

def process_dir(d):
    try:
        img, meta = load_series_from_folder(Path(d))
        out_dir = make_outdir(meta)
        res = run_preprocess(img, meta, out_dir)
        log_json({"level":"INFO","event":"preprocess_ok","input":str(d),"out_dir":res["out_dir"],"timings":res["timings"]})
        return True
    except Exception as e:
        log_json({"level":"ERROR","event":"preprocess_fail","input":str(d),"error":str(e),"trace":traceback.format_exc()})
        return False

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_dir", help="Carpeta con DICOMs; puede repetirse", action="append")
    args = ap.parse_args()
    if not args.input_dir: 
        print("Debes pasar al menos un --input_dir", file=sys.stderr); sys.exit(1)
    oks=0; fails=0
    for d in args.input_dir:
        (oks:=oks+1) if process_dir(d) else (fails:=fails+1)
    print(f"[Resumen] OK={oks} FAIL={fails}")
    sys.exit(0 if fails==0 else 2)
