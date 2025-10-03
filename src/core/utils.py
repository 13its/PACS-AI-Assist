from pathlib import Path
import json, os, time, platform

LOGS = Path("logs"); LOGS.mkdir(exist_ok=True)

def log_json(event: dict):
    event |= {"ts": time.time(), "host": platform.node()}
    with open(LOGS/"pipeline.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")

def make_outdir(meta: dict):
    # puedes mejorar con UIDs si los tienes en meta
    base = Path("artifacts")/time.strftime("%Y%m%d") 
    base.mkdir(parents=True, exist_ok=True)
    # carpeta simple por timestamp
    return base/str(int(time.time()))
