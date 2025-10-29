(function () {
  // === utilidades ==========================
  function waitFor(sel, timeout = 15000) {
    return new Promise((resolve) => {
      const t0 = Date.now();
      const it = setInterval(() => {
        const el = document.querySelector(sel);
        if (el) { clearInterval(it); resolve(el); }
        if (Date.now() - t0 > timeout) { clearInterval(it); resolve(null); }
      }, 300);
    });
  }
  function getStudyUID() {
    try {
      const u = new URL(location.href);
      return u.searchParams.get('StudyInstanceUIDs') || u.searchParams.get('studyInstanceUID');
    } catch { return null; }
  }
  async function callBackend() {
    const sid = getStudyUID();
    if (!sid) { alert('No pude detectar StudyInstanceUID'); return; }
    try {
      const r = await fetch('http://127.0.0.1:8001/analyze/download-only', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orthanc_url: 'http://127.0.0.1:8042', study_uid: sid })
      });
      if (r.ok) alert('✅ Enviado a IA');
      else alert('❌ Error: ' + await r.text());
    } catch (e) {
      alert('❌ Error red: ' + e);
    }
  }

  // === botón estilizado =====================
  function makeButton() {
    const b = document.createElement('button');
    b.id = 'pacs-ai-btn';
    b.textContent = 'Enviar a IA';
    b.style.cssText = `
      padding:6px 10px; margin-left:8px;
      border-radius:8px; border:1px solid #3b82f6; 
      background:#1e3a8a; color:#fff; cursor:pointer; 
      font-weight:600;
    `;
    b.onclick = callBackend;
    return b;
  }

  // === intento A: insertar en toolbar =================
  async function tryToolbarMount() {
    // OHIF v3 cambia clases a menudo; probamos varios selectores típicos
    const candidates = [
      '[data-cy="ohif-toolbar"]',
      '[data-cy="StudyToolbar"]',
      '.ViewerHeader .right',
      '.ToolbarRow',
      'div[role="toolbar"]'
    ];
    for (const sel of candidates) {
      const host = await waitFor(sel, 3000);
      if (host) {
        if (!document.getElementById('pacs-ai-btn')) host.appendChild(makeButton());
        return true;
      }
    }
    return false;
  }

  // === intento B: botón flotante si no hay toolbar =====
  function mountFloating() {
    if (document.getElementById('pacs-ai-fab')) return;
    const fab = document.createElement('button');
    fab.id = 'pacs-ai-fab';
    fab.textContent = 'Enviar a IA';
    fab.style.cssText = `
      position:fixed; right:18px; bottom:18px; z-index: 99999;
      padding:10px 14px; border-radius:999px; 
      background:#1e3a8a; color:#fff; border:1px solid #3b82f6;
      box-shadow:0 6px 18px rgba(0,0,0,.25); font-weight:700; cursor:pointer;
    `;
    fab.onclick = callBackend;
    document.body.appendChild(fab);
  }

  (async () => {
    // evitamos dobles inyecciones
    if (window.__pacs_ai_injected__) return;
    window.__pacs_ai_injected__ = true;

    const mounted = await tryToolbarMount();
    if (!mounted) mountFloating();
    console.log('[PACS-AI] inject listo.');
  })();
})();
