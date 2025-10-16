        // Renderiza la flecha y el círculo apuntando a la imagen
        function ArrowAndCircle({ markerPos }: { markerPos: { x: number; y: number } }) {
            const cardX = Math.max(8, markerPos.x - 320);
            const cardY = Math.max(8, markerPos.y - 18);
            const startX = cardX + 300;
            const startY = cardY + 24;
            const endX = markerPos.x;
            const endY = markerPos.y;
            const midX = (startX + endX) / 2;
            const path = `M ${startX} ${startY} C ${midX} ${startY} ${midX} ${endY} ${endX} ${endY}`;
            return (
                <>
                    <svg className="connector-svg" xmlns="http://www.w3.org/2000/svg">
                        <g>
                            <path d={path} stroke="rgba(255,215,0,0.95)" strokeWidth={3} fill="none" strokeLinecap="round" strokeLinejoin="round" />
                            <circle cx={endX} cy={endY} r={10} fill="none" stroke="rgba(255,215,0,0.98)" strokeWidth={4}/>
                        </g>
                    </svg>
                    <div className="marker" style={{ left: markerPos.x, top: markerPos.y }}>
                        <div className="marker-circle" style={{width:32,height:32,borderWidth:4}}>
                            <div className="marker-center" />
                        </div>
                    </div>
                </>
            );
        }
    import React, { useEffect, useRef, useState } from "react";

type Box = { x: number; y: number; w: number; h: number; label?: string; score?: number };
type Msg = { type: "bbox"; sopInstanceUID: string; boxes: Box[]; meta?: Record<string, any> };

type Props = {
  ohifUrl?: string;             // URL inicial (explorer o viewer)
  wsUrl?: string;               // ws del backend
};

// Componente para renderizar la flecha y el círculo
function ArrowAndCircle({ markerPos }: { markerPos: { x: number; y: number } }) {
  return (
    <>
      <svg className="connector-svg" xmlns="http://www.w3.org/2000/svg">
        <g>
          <path 
            d={`M ${markerPos.x - 260} ${markerPos.y} L ${markerPos.x - 10} ${markerPos.y}`} 
            stroke="rgba(255,215,0,0.95)" 
            strokeWidth={3} 
            fill="none" 
            strokeLinecap="round" 
            strokeLinejoin="round" 
          />
          <circle cx={markerPos.x} cy={markerPos.y} r={10} fill="none" stroke="rgba(255,215,0,0.98)" strokeWidth={4}/>
        </g>
      </svg>
      <div className="marker" style={{ left: markerPos.x, top: markerPos.y }}>
        <div className="marker-circle" style={{width:32,height:32,borderWidth:4}}>
          <div className="marker-center" />
        </div>
      </div>
    </>
  );    export default function OverlayApp({
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
    // Paso del overlay: 'intro' (mensaje inicial), 'detalle' (marcador+flecha+detalle)
    const [overlayStep, setOverlayStep] = useState<'intro'|'detalle'|null>(null);

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

    // Posiciones en pantalla de los markers (para tarjeta y flecha)
    const [markerPos, setMarkerPos] = useState<{x:number,y:number,box?:Box}|null>(null);
    const [cardOpen, setCardOpen] = useState(false);

    // recalcula posiciones de markers cuando cambian boxes o tamaño
    useEffect(()=>{
        const ifr = iframeRef.current;
        if (!ifr) { setMarkerPos(null); return; }
        const r = ifr.getBoundingClientRect();
        const imgW = 512, imgH = 512;
        const scaleX = r.width / imgW;
        const scaleY = r.height / imgH;
        // tomamos el primer box (si hay) como marcador activo
        if (boxes.length===0){ setMarkerPos(null); return; }
        const b = boxes[0];
        const x = r.left + (b.x + b.w/2) * scaleX;
        const y = r.top  + (b.y + b.h/2) * scaleY;
        setMarkerPos({ x, y, box: b });
    }, [boxes, iframeRef.current]);

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
            onClick={() => {
                setAssistOpen(v => {
                  const next = !v;
                  if (next) setOverlayStep('intro');
                  else setOverlayStep(null);
                  return next;
                });
            }}
            title="Abrir panel PACS-AI Assist"
        >
            PACS-AI Assist
            <span className={`ws-dot ${wsStatus}`}/>
        </button>

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

                        {/* UI overlay: paso 1: mensaje inicial */}
                        {assistOpen && overlayStep === 'intro' && (
                            <div className="overlay-ui" style={{display:'flex',alignItems:'center',justifyContent:'center'}}>
                                <div style={{background:'#0b152d',color:'#e5e7eb',padding:'28px 32px',borderRadius:12,border:'2px solid #3082EC',boxShadow:'0 8px 32px #000a',fontSize:20,maxWidth:400,textAlign:'center'}}>
                                    ¿Quieres soporte de IA?
                                    <div style={{marginTop:24}}>
                                                        <button 
                  className="btn-link" 
                  style={{fontSize:18}} 
                  onClick={()=>{
                    setOverlayStep('detalle');
                    // Establecer posición del marcador (coordenadas del ejemplo)
                    setMarkerPos({x: window.innerWidth/2, y: window.innerHeight/2, box: {
                      x: 250, y: 300, w: 20, h: 20,
                      label: "Nódulo",
                      score: 0.75
                    }});
                  }}
                >
                  Sí, ver hallazgo
                </button>
               </div>
             </div>
           </div>
         )}

        {/* UI overlay: paso 2: marcador, flecha y caja de detalle */}
        {assistOpen && overlayStep === 'detalle' && (
          <div className="overlay-ui" aria-hidden={false}>
            {markerPos && <ArrowAndCircle markerPos={markerPos} />}
            <div
              className="detail-card"
              style={{
                position: 'absolute',
                left: markerPos ? Math.max(8, markerPos.x - 320) : 8,
                top: markerPos ? Math.max(8, markerPos.y - 32) : 8,
                background: '#183a5a',
                color: '#e5e7eb',
                border: '2px solid #6ec1e4',
                borderRadius: 8,
                padding: '24px',
                minWidth: 280,
                maxWidth: 420,
                fontSize: 14,
                lineHeight: 1.6,
                boxShadow: '0 8px 32px rgba(0,0,0,0.5)'
              }}
            >
              <div style={{fontWeight:600,marginBottom:8}}>Probabilidad de malignidad: 75%</div>
              <div>Clasificación del hallazgo: maligno</div>
              <div>Tamaño: diámetro mayor 2mm</div>
                                    </div>
                                </div>
                            </div>
                        )}

                                {/* UI overlay: paso 2: solo caja de texto centrada con el detalle */}
                                {assistOpen && overlayStep === 'detalle' && (
                                    <div className="overlay-ui" style={{display:'flex',alignItems:'center',justifyContent:'center'}}>
                                        <div style={{background:'#183a5a', color:'#e5e7eb', border:'2px solid #6ec1e4', borderRadius:12, boxShadow:'0 8px 32px #000a', fontSize:16, minWidth:320, maxWidth:480, padding:'32px 36px', textAlign:'left', lineHeight:1.7}}>
                                            <div style={{fontWeight:600,marginBottom:8}}>Probabilidad de malignidad: 75%</div>
                                            <div>Clasificación del hallazgo: maligno</div>
                                            <div>Tamaño: diámetro mayor 2mm</div>
                                            <div>Volumen estimado: 2mm³.</div>
                                            <div>Ubicación anatómica: Lóbulo inferior derecho, segmento pulmonar posterior</div>
                                            <div>Profundidad / relación pleural: Subpleural (adyacente a la pleura).</div>
                                            <div>Contraste / densidad: Promedio y desviación aún por calcular en HU.</div>
                                            <div>Características morfológicas: Nódulo sólido con aspecto en vidrio esmerilado.</div>
                                            <div>Contornos: Espiculados, sin ser completamente lisos.</div>
                                            <div>Crecimiento temporal: No hay estudios previos</div>
                                            <div>Porcentaje de confianza de la IA en cada etiqueta: 70% sólido, 25% GGO (ground-glass opacity).</div>
                                        </div>
                                    </div>
                                )}
        </>
    );
    }
