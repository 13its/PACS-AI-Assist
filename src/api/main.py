
from fastapi import FastAPI
from .routes_pipeline import router as pipeline_router

app = FastAPI(title="PACS-AI Assist - Pipeline")
app.include_router(pipeline_router)

@app.get("/health")
def health(): return {"ok": True}
