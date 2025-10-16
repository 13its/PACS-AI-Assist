import React from "react";

/** ===========================
 *  Cliente WS simple
 *  =========================== */
function createWSClient(url: string, onBoxes: (payload: any) => void) {
  let ws: WebSocket | null = null;
  let status: "connecting" | "open" | "closed" = "connecting";
  const subs = new Set<(s: typeof status) => void>();

  const setStatus = (s: typeof status) => {
    status = s;
    subs.forEach((cb) => cb(s));
  };

  const connect = () => {
    setStatus("connecting");
    ws = new WebSocket(url);
    ws.onopen = () => setStatus("open");
    ws.onclose = () => {
      setStatus("closed");
      setTimeout(connect, 1200);
    };
    ws.onerror = () => setStatus("closed");
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data?.type === "bbox") onBoxes(data);
      } catch {}
    };
  };

  const onStatus = (cb: (s: typeof status) => void) => {
    subs.add(cb);
    cb(status);
    return () => subs.delete(cb);
  };

  return { connect, onStatus };
}

/** ===========================
 *  Botón toolbar (Figma styles)
 *  =========================== */
const PacsAIButton: React.FC<{ onClick: () => void; status: string; active: boolean }> = ({
  onClick,
  status,
  active,
}) => {
  const fill = active ? "#2B75D8" : "#041C4A";
  const txt = active ? "#041C4A" : "#3082EC";
  return (
    <button
      title="PACS-AI Assist"
      onClick={onClick}
      style={{
        width: 114,
        height: 20,
        borderRadius: 3,
        border: "1px solid #3082EC",
        background: fill,
        color: txt,
        fontFamily: "Inter, system-ui, sans-serif",
        fontWeight: 400,
        fontSize: 12,
        lineHeight: "18px",
        padding: 0,
        boxShadow: "0 4px 4px rgba(0,0,0,0.25)",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        cursor: "pointer",
      }}
    >
      PACS-AI Assist
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          display: "inline-block",
          marginLeft: 6,
          boxShadow: "0 0 0 1px rgba(0,0,0,.25) inset",
          background:
            status === "open" ? "#22c55e" : status === "connecting" ? "#ffaa00" : "#ef4444",
        }}
      />
    </button>
  );
};

/** ===========================
 *  Panel lateral (lista por SOP)
 *  =========================== */
const PacsAIPanel: React.FC<{
  servicesManager: any;
  wsStatus: string;
  inbox: Record<string, any[]>;
  setCurrentSOP: (s: string) => void;
  currentSOP: string | null;
}> = ({ wsStatus, inbox, currentSOP, setCurrentSOP }) => {
  return (
    <div style={{ padding: 10, color: "#e5e7eb", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div style={{ fontWeight: 600 }}>Predicciones de nódulos</div>
        <div
          style={{
            padding: "2px 6px",
            borderRadius: 6,
            fontSize: 12,
            background: wsStatus === "open" ? "#064e3b" : wsStatus === "connecting" ? "#78350f" : "#7f1d1d",
            color: wsStatus === "open" ? "#bbf7d0" : wsStatus === "connecting" ? "#fde68a" : "#fecaca",
          }}
        >
          WS: {wsStatus}
        </div>
      </div>

      <div style={{ overflow: "auto", maxHeight: "calc(100vh - 140px)" }}>
        {Object.keys(inbox).length === 0 && (
          <div style={{ opacity: 0.7, fontSize: 13 }}>
            Aún no hay predicciones. Envía cajas a <code>POST /push</code>.
          </div>
        )}
        {Object.entries(inbox).map(([sop, boxes]) => (
          <div
            key={sop}
            onClick={() => setCurrentSOP(sop)}
            style={{
              background: "#0b152d",
              border: "1px solid #203356",
              borderRadius: 8,
              padding: 8,
              marginBottom: 8,
              cursor: "pointer",
              outline: currentSOP === sop ? "2px solid #3082EC" : "none",
            }}
          >
            <div style={{ fontSize: 12, opacity: 0.9 }}>SOP: {sop}</div>
            <div style={{ fontSize: 12, opacity: 0.7 }}>{(boxes as any[]).length} hallazgos</div>
          </div>
        ))}
      </div>
    </div>
  );
};

/** ===========================
 *  Overlay Canvas (sobre viewport)
 *  =========================== */
const OverlayCanvas: React.FC<{ boxesRef: React.MutableRefObject<any[]> }> = ({ boxesRef }) => {
  const ref = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const draw = () => {
      const canvas = ref.current!;
      if (!canvas) return;
      const ctx = canvas.getContext("2d")!;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // localiza canvas de Cornerstone más grande
      const cvs = Array.from(document.querySelectorAll("canvas")) as HTMLCanvasElement[];
      let target: DOMRect | null = null;
      let area = 0;
      for (const c of cvs) {
        const r = c.getBoundingClientRect();
        const a = r.width * r.height;
        if (a > area && r.width > 300 && r.height > 300) {
          area = a;
          target = r;
        }
      }
      if (!target) return;

      const imgW = 512,
        imgH = 512;
      const sx = target.width / imgW;
      const sy = target.height / imgH;

      for (const b of boxesRef.current) {
        const x = target.left + b.x * sx;
        const y = target.top + b.y * sy;
        const w = b.w * sx;
        const h = b.h * sy;

        ctx.lineWidth = 2;
        ctx.strokeStyle = "rgba(255,215,0,.95)";
        ctx.strokeRect(x, y, w, h);

        const tag = `${b.label ?? "Nódulo"}${b.score != null ? " " + Math.round(b.score * 100) + "%" : ""}`;
        ctx.font = "12px Inter, system-ui, sans-serif";
        const tw = ctx.measureText(tag).width + 8,
          th = 18;
        ctx.fillStyle = "rgba(255,215,0,.95)";
        ctx.fillRect(x, Math.max(0, y - th), tw, th);
        ctx.fillStyle = "#041C4A";
        ctx.fillText(tag, x + 4, Math.max(12, y - 4));
      }

      requestAnimationFrame(draw);
    };

    const id = requestAnimationFrame(draw);
    const onResize = () => draw();
    window.addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(id);
      window.removeEventListener("resize", onResize);
    };
  }, [boxesRef]);

  return (
    <canvas
      ref={ref}
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        pointerEvents: "none",
        zIndex: 5000,
      }}
    />
  );
};

/** ===========================
 *  MÓDULO DE EXTENSIÓN OHIF
 *  (export default requerido por OHIF)
 *  =========================== */
export default function pacsAIExtension({ servicesManager }: any) {
  const pubSub = servicesManager?.services?.pubSubService;

  // Estado compartido
  const wsUrl = "ws://localhost:8000/ws";
  const wsClient = createWSClient(wsUrl, (payload) => {
    // Distribuye a overlay/panel via PubSub de OHIF
    pubSub?.publish("pacsai:boxes", payload);
  });
  wsClient.connect();

  // Memoria simple en este módulo
  let wsStatus: "connecting" | "open" | "closed" = "connecting";
  wsClient.onStatus((s) => {
    wsStatus = s;
    pubSub?.publish("pacsai:status", s);
  });

  const boxesRef = { current: [] as any[] };
  pubSub?.subscribe?.("pacsai:boxes", (payload: any) => {
    // Si quieres separar por SOP, puedes añadir lógica aquí
    boxesRef.current = payload?.boxes || [];
  });

  // Toolbar module
  const getToolbarModule = () => [
    {
      name: "PacsAIButton",
      defaultComponent: (props: any) => {
        const [active, setActive] = React.useState(false);
        const [status, setStatus] = React.useState(wsStatus);
        React.useEffect(() => {
          const sub = pubSub?.subscribe?.("pacsai:status", (s: any) => setStatus(s));
          return () => sub?.unsubscribe?.();
        }, []);
        const panelService = servicesManager.services.panelService;
        const onClick = () => {
          setActive((a) => !a);
          const open = !active;
          if (open) panelService.openPanel("PacsAIPanel", { width: 320 });
          else panelService.closePanel("PacsAIPanel");
        };
        return <PacsAIButton onClick={onClick} status={status} active={active} />;
      },
      tooltip: "PACS-AI Assist",
    },
  ];

  // Panel module
  const getPanelModule = () => [
    {
      name: "PacsAIPanel",
      iconName: "list-bullets",
      label: "PACS-AI Assist",
      defaultComponent: (props: any) => {
        const [status, setStatus] = React.useState(wsStatus);
        const [inbox, setInbox] = React.useState<Record<string, any[]>>({});
        const [currentSOP, setCurrentSOP] = React.useState<string | null>(null);

        React.useEffect(() => {
          const s1 = pubSub?.subscribe?.("pacsai:status", (s: any) => setStatus(s));
          const s2 = pubSub?.subscribe?.("pacsai:boxes", (p: any) => {
            setInbox((prev) => ({ ...prev, [p.sopInstanceUID]: p.boxes || [] }));
            if (!currentSOP) setCurrentSOP(p.sopInstanceUID);
          });
          return () => {
            s1?.unsubscribe?.();
            s2?.unsubscribe?.();
          };
          // eslint-disable-next-line
        }, []);

        return (
          <PacsAIPanel
            servicesManager={servicesManager}
            wsStatus={status}
            inbox={inbox}
            currentSOP={currentSOP}
            setCurrentSOP={setCurrentSOP}
          />
        );
      },
    },
  ];

  // Viewport module: agrega overlay canvas
  const getViewportModule = () => [
    {
      name: "PacsAIOverlay",
      components: [
        {
          id: "pacsai-overlay-canvas",
          component: () => <OverlayCanvas boxesRef={boxesRef} />,
        },
      ],
    },
  ];

  return {
    id: "ohif-extension-pacsai",
    getToolbarModule,
    getPanelModule,
    getViewportModule,
  };
}
