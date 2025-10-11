(function () {
  const WS_HOST = location.hostname;
  const WS_PORT = 8000;
  const wsUrl =
    (location.protocol === "https:" ? "wss://" : "ws://") +
    WS_HOST + ":" + WS_PORT + "/ws";

  // Badge de estado
  const badge = document.createElement("div");
  Object.assign(badge.style, {
    position: "fixed", left: "10px", top: "10px", zIndex: 99999,
    background: "#000a", color: "#fff", padding: "4px 8px",
    borderRadius: "6px", font: "12px system-ui"
  });
  badge.textContent = "Overlay: conectando…";
  document.body.appendChild(badge);

  // Canvas overlay full screen
  const canvas = document.createElement("canvas");
  Object.assign(canvas.style, {
    position: "fixed", inset: "0", width: "100vw", height: "100vh",
    pointerEvents: "none", zIndex: 9999
  });
  canvas.width = innerWidth; canvas.height = innerHeight;
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d");

  let scaleX = 1, scaleY = 1, offsetX = 0, offsetY = 0;
  let lastBoxes = [];
  let currentSOP = null;

  // === Helpers Cornerstone/OHIF ==========================
  function getViewportCanvas() {
    // OHIF v3 suele usar canvas con data-cornerstone
    return (
      document.querySelector('canvas[data-cornerstone]') ||
      document.querySelector('.cornerstone-canvas') ||
      document.querySelector('.ViewportPane canvas') ||
      document.querySelector('canvas')
    );
  }

  function getEnabledElement() {
    try {
      if (window.cornerstone) {
        const el = getViewportCanvas();
        if (!el) return null;
        return window.cornerstone.getEnabledElement(el);
      }
    } catch {}
    return null;
  }

  function getImageDims() {
    // Devuelve {imgW,imgH} del frame actual
    const ee = getEnabledElement();
    if (ee?.image?.width && ee?.image?.height) {
      return { imgW: ee.image.width, imgH: ee.image.height };
    }
    // Intento por metadatos (por si acaso)
    try {
      const el = getViewportCanvas();
      const imageId = ee?.image?.imageId;
      const cs = window.cornerstone;
      const cols = cs?.metaData?.get?.("columns", imageId);
      const rows = cs?.metaData?.get?.("rows", imageId);
      if (cols && rows) return { imgW: cols, imgH: rows };
    } catch {}
    // Fallback: usa tamaño renderizado (menos preciso, pero sirve)
    const r = getViewportCanvas()?.getBoundingClientRect();
    return r ? { imgW: r.width, imgH: r.height } : { imgW: 512, imgH: 512 };
  }

  function getViewportRect() {
    const el = getViewportCanvas();
    return el ? el.getBoundingClientRect() : null;
  }

  function trySetCurrentSOP() {
    try {
      const ee = getEnabledElement();
      const imageId = ee?.image?.imageId;
      const cs = window.cornerstone;
      const sop = cs?.metaData?.get?.("SOPInstanceUID", imageId);
      if (sop) currentSOP = sop;
    } catch {}
  }

  function updateMapping() {
    const rect = getViewportRect();
    if (!rect) return;
    const { imgW, imgH } = getImageDims();
    scaleX = rect.width / imgW;
    scaleY = rect.height / imgH;
    offsetX = rect.left;
    offsetY = rect.top;
  }

  // Observa cambios en el DOM (cambios de layout) y re-mapea
  const mo = new MutationObserver(() => {
    updateMapping();
    trySetCurrentSOP();
  });
  mo.observe(document.body, { childList: true, subtree: true, attributes: true });

  // Poll suave por si Cornerstone no emite eventos accesibles
  const poll = setInterval(() => { updateMapping(); trySetCurrentSOP(); }, 300);

  // Redimensiona canvas cuando cambia la ventana
  addEventListener("resize", () => {
    canvas.width = innerWidth; canvas.height = innerHeight;
    updateMapping();
  });

  // === WebSocket ========================================
  const ws = new WebSocket(wsUrl);
  ws.onopen = () => { badge.textContent = "Overlay: WS conectado"; };
  ws.onclose = () => { badge.textContent = "Overlay: WS cerrado"; };
  ws.onerror = () => { badge.textContent = "Overlay: WS error"; };

  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "bbox" && Array.isArray(msg.boxes)) {
        if (!currentSOP || msg.sopInstanceUID === currentSOP) {
          lastBoxes = msg.boxes;
        }
      }
      // (si agregas heatmap, dibuja aquí)
    } catch {}
  };

  // === Dibujado =========================================
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const b of lastBoxes) {
      const x = offsetX + b.x * scaleX, y = offsetY + b.y * scaleY;
      const w = b.w * scaleX, h = b.h * scaleY;

      ctx.lineWidth = 2;
      ctx.strokeStyle = "rgba(255,0,0,0.95)";
      ctx.strokeRect(x, y, w, h);

      const tag = `${b.label ?? "obj"}${b.score != null ? " " + Math.round(b.score * 100) + "%" : ""}`;
      ctx.font = "12px sans-serif";
      const tw = ctx.measureText(tag).width + 8, th = 16;
      ctx.fillStyle = "rgba(255,0,0,0.95)";
      ctx.fillRect(x, Math.max(0, y - th), tw, th);
      ctx.fillStyle = "#fff";
      ctx.fillText(tag, x + 4, Math.max(12, y - 4));
    }
    requestAnimationFrame(draw);
  }
  requestAnimationFrame(draw);

  // API pública (útil en consola)
  window.PACSOverlay = {
    setCurrentSOP: (uid) => { currentSOP = uid; },
    clear: () => { lastBoxes = []; },
    setViewportMapping: ({ imgW, imgH, viewX, viewY, viewW, viewH }) => {
      scaleX = viewW / imgW; scaleY = viewH / imgH; offsetX = viewX; offsetY = viewY;
    },
    _debug: { updateMapping, trySetCurrentSOP, getEnabledElement, getViewportCanvas, getImageDims }
  };

  // Primer mapeo/sync
  updateMapping();
  trySetCurrentSOP();
})();
