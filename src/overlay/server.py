from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn, asyncio, json, os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"]
)

# === NEW: servir carpeta "static" y demo.html en "/"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def demo():
    return FileResponse(os.path.join(STATIC_DIR, "demo.html"))

# === WS + REST como ya tenías
clients: set[WebSocket] = set()

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            await ws.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        clients.discard(ws)

async def broadcast(payload: dict):
    msg = json.dumps(payload)
    dead = []
    for c in list(clients):
        try:
            await c.send_text(msg)
        except:
            dead.append(c)
    for d in dead:
        clients.discard(d)

class BBox(BaseModel):
    x: float; y: float; w: float; h: float
    label: str | None = None
    score: float | None = None

class InferenceMsg(BaseModel):
    type: str = "bbox"
    sopInstanceUID: str
    boxes: list[BBox] = []
    meta: dict | None = None

@app.post("/push")
async def push_inference(msg: InferenceMsg):
    await broadcast(msg.model_dump())
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
