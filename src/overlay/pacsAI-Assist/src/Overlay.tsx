    import React, { useEffect, useRef, useState } from "react";

    type Box = { x: number; y: number; w: number; h: number; label?: string; score?: number };
    type Msg = { type: "bbox"; sopInstanceUID: string; boxes: Box[]; meta?: Record<string, any> };

    type Props = {
    ohifUrl?: string;             // URL inicial (explorer o viewer)
    wsUrl?: string;               // ws del backend
    };

    export default function OverlayApp({
    ohifUrl = "http://localhost:8042/app/explorer.html",
    wsUrl = "ws://localhost:8000/ws",
    }: Props) {
    // Iframe + Canvas para las cajas
    const iframeRef = useRef<HTMLIFrameElement>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    // Estado UI
    const [iframeSrc, setIframeSrc] = useState<string>(ohifUrl);
    const [wsStatus, setWsStatus] = useState<"connecting"|"open"|"closed">("connecting");
    const [assistOpen, setAssistOpen] = useState(false);

    // Datos IA
    const [currentSOP, setCurrentSOP] = useState<string | null>(null);
    const [boxes, setBoxes] = useState<Box[]>([]);
    const [inbox, setInbox] = useState<Record<string, Box[]>>({}); // { sopUid: boxes[] }

    // Conexión WS
    useEffect(() => {
        const ws = new WebSocket(wsUrl);
        ws.onopen = () => setWsStatus("open");
        ws.onclose = () => setWsStatus("closed");
        ws.onerror = () => setWsStatus("closed");
        ws.onmessage = (ev) => {
        try {
            const m = JSON.parse(ev.data) as Msg;
            if (m.type === "bbox" && Array.isArray(m.boxes)) {
            setInbox(prev => ({ ...prev, [m.sopInstanceUID]: m.boxes }));
            // si no seguimos un SOP específico, muestra el último recibido
            if (currentSOP === null) {
                setCurrentSOP(m.sopInstanceUID);
                setBoxes(m.boxes);
            } else if (m.sopInstanceUID === currentSOP) {
                setBoxes(m.boxes);
            }
            }
        } catch {}
        };
        return () => ws.close();
    }, [wsUrl, currentSOP]);

    // Dibujo de cajas sobre el viewer (mapeo simple 512x512)
    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d")!;
        let raf = 0;

        const draw = () => {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const ifr = iframeRef.current;
        if (!ifr) { raf = requestAnimationFrame(draw); return; }
        const r = ifr.getBoundingClientRect();

        const imgW = 512, imgH = 512; // tamaño base
        const scaleX = r.width / imgW;
        const scaleY = r.height / imgH;

        for (const b of boxes) {
            const x = r.left + b.x * scaleX;
            const y = r.top  + b.y * scaleY;
            const w = b.w * scaleX;
            const h = b.h * scaleY;

            // círculo + flecha opcional: usamos rect básico y etiqueta
            ctx.lineWidth = 2;
            ctx.strokeStyle = "rgba(255,215,0,0.95)"; // amarillo dorado
            ctx.strokeRect(x, y, w, h);

            const tag = `${b.label ?? "Nódulo"}${b.score != null ? " " + Math.round(b.score*100) + "%" : ""}`;
            ctx.font = "12px Inter, system-ui, sans-serif";
            const tw = ctx.measureText(tag).width + 8;
            const th = 18;
            ctx.fillStyle = "rgba(255,215,0,0.95)";
            ctx.fillRect(x, Math.max(0, y - th), tw, th);
            ctx.fillStyle = "#041C4A";
            ctx.fillText(tag, x + 4, Math.max(12, y - 4));
        }

        raf = requestAnimationFrame(draw);
        };

        const onResize = () => {};
        window.addEventListener("resize", onResize);
        raf = requestAnimationFrame(draw);
        return () => {
        cancelAnimationFrame(raf);
        window.removeEventListener("resize", onResize);
        };
    }, [boxes]);

    // Cambiar SOP desde la lista del panel
    const selectSOP = (sop: string) => {
        setCurrentSOP(sop);
        setBoxes(inbox[sop] || []);
        setAssistOpen(true);
    };

    return (
        <>
        {/* Botón PACS-AI Assist (siempre visible sobre el viewer) */}
        <button
            className={`pacsai-btn ${assistOpen ? "active" : ""}`}
            onClick={() => setAssistOpen(v => !v)}
            title="Abrir panel PACS-AI Assist"
        >
            PACS-AI Assist
            <span className={`ws-dot ${wsStatus}`}/>
        </button>

        {/* Botón de soporte IA - solo visible cuando el panel está abierto */}
        {assistOpen && (
            <div className="ai-support-container">
                <button
                    className="ai-support-btn"
                    onClick={() => setAssistOpen(false)}
                    title="Soporte con IA"
                >
                    ¿Quieres soporte de IA?
                    <button 
                        className="ver-mas-btn"
                        onClick={() => setAssistOpen(false)}
                    >
                        Sí, ver hallazgo
                    </button>
                </button>
            </div>
        )}

        {/* Panel lateral de IA */}
        <aside className={`assist-panel ${assistOpen ? "open" : ""}`}>
            <div className="assist-header">
            <div className="title">Predicciones de nódulos</div>
            <div className={`ws-chip ${wsStatus}`}>WS: {wsStatus}</div>
            </div>

            {/* selector manual de URL viewer (por si entras desde Explorer) */}
            <div className="row">
            <input
                placeholder="Pega URL del viewer (opcional)"
                className="inp"
                onKeyDown={e=>{
                if(e.key==="Enter"){
                    const value = (e.target as HTMLInputElement).value.trim();
                    if (value) setIframeSrc(value);
                }
                }}
            />
            </div>

            {/* lista de SOPs recibidos */}
            <div className="list">
            {Object.keys(inbox).length === 0 && (
                <div className="empty">Aún no hay predicciones. Envía cajas a <code>POST /push</code>.</div>
            )}
            {Object.entries(inbox).map(([sop, bs]) => (
                <div key={sop} className={`card ${sop===currentSOP ? "sel":""}`} onClick={()=>selectSOP(sop)}>
                <div className="sop">SOP: {sop}</div>
                <div className="meta">{bs.length} hallazgos</div>
                </div>
            ))}
            </div>
        </aside>

        {/* Iframe del visor */}
        <iframe ref={iframeRef} src={iframeSrc} className="viewer" title="OHIF" />

        {/* Capa de overlay */}
        <canvas ref={canvasRef} className="overlay" />
        </>
    );
    }
