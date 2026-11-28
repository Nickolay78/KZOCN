/**
 * KZOSN Unified Single-Page Web Application Shell (True Persistent Top Menu & View Deck)
 * - Keeps a single, motionless persistent top navigation bar across all 6 modules
 * - Switches between modules instantaneously in-place without page reloads (preserving 3D camera & WebGL contexts)
 * - Synchronizes state (edition, norm, section, radius, decile) in real time across all modules
 */
(function () {
  const STORAGE_KEY = "KZOSN_APP_STATE_V1";
  const isEmbeddedView =
    window.self !== window.top || new URLSearchParams(window.location.search).get("spa") === "1";

  const MODULES = [
    { id: "atlas",      file: "index.html",      label: "🌐 1. 3D-Атлас КК" },
    { id: "deciles",    file: "deciles.html",    label: "🏛 2. 10 Децилів (3D + 2D)" },
    { id: "comparator", file: "comparator.html", label: "⚖️ 3. Компаратор (±1..5%)" },
    { id: "calculator", file: "calculator.html", label: "🧪 4. Калькулятор санкції" },
    { id: "poster_v2",  file: "fb_post_v2.html", label: "✨ 5. Інфографіка v2 (FB)" },
    { id: "poster_v1",  file: "fb_post_2d.html", label: "📊 6. Постер v1" },
    { id: "structure",  file: "structure.html",     label: "📈 7. Структура редакцій" },
    { id: "punish3d",   file: "punishments_3d.html", label: "🎯 8. 3D Покарання" },
  ];

  function getCurrentFileName() {
    const p = window.location.pathname.split("/").pop();
    return p && p.endsWith(".html") ? p : "index.html";
  }

  function parseHashParams() {
    const h = window.top.location.hash.replace(/^#\/?/, "");
    if (!h) return {};
    const params = new URLSearchParams(h);
    const obj = {};
    for (const [k, v] of params.entries()) {
      obj[k] = v;
    }
    return obj;
  }

  function loadInitialState() {
    let saved = {};
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) saved = JSON.parse(raw);
    } catch (e) {}
    const fromHash = parseHashParams();
    const curFile = getCurrentFileName();
    const defaultMod = MODULES.find((m) => m.file === curFile)?.id || "atlas";
    return {
      mod: fromHash.mod || defaultMod,
      ed: fromHash.ed || saved.ed || "2025",
      sec: fromHash.sec || saved.sec || "ALL",
      norm: fromHash.norm || saved.norm || "185|4",
      rad: fromHash.rad !== undefined ? Number(fromHash.rad) : saved.rad !== undefined ? Number(saved.rad) : 1,
      decile: fromHash.decile !== undefined ? Number(fromHash.decile) : saved.decile !== undefined ? Number(saved.decile) : 1,
    };
  }

  let state = loadInitialState();
  const listeners = [];

  function notifyListeners(newState) {
    listeners.forEach((fn) => {
      try {
        fn(newState);
      } catch (e) {}
    });
  }

  function saveState(patch = {}, broadcast = true) {
    const changed = Object.keys(patch).some((k) => state[k] !== patch[k]);
    if (!changed && !patch.force) return;
    state = { ...state, ...patch };
    delete state.force;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {}

    if (isEmbeddedView) {
      if (broadcast && window.top && window.top !== window.self) {
        window.top.postMessage({ type: "KZOSN_STATE_UPDATE", state }, "*");
      }
    } else {
      updateUrlHash();
      updateContextRibbonUI();
      if (broadcast) {
        broadcastToFrames();
      }
    }
  }

  function updateUrlHash() {
    if (isEmbeddedView) return;
    const p = new URLSearchParams();
    if (state.mod) p.set("mod", state.mod);
    if (state.ed) p.set("ed", state.ed);
    if (state.norm) p.set("norm", state.norm);
    if (state.sec && state.sec !== "ALL") p.set("sec", state.sec);
    if (state.rad !== undefined) p.set("rad", String(state.rad));
    const newHash = "#" + p.toString();
    if (window.location.hash !== newHash) {
      history.replaceState(null, "", newHash);
    }
  }

  function getNormRecord(edId, normKey) {
    const DATA = window.KZOCN_DATA;
    if (!DATA || !DATA.byEdition) return null;
    const recs = DATA.byEdition[edId] || DATA.byEdition["2025"] || [];
    return recs.find((r) => `${r[1]}|${r[3]}` === normKey) || null;
  }

  function updateContextRibbonUI() {
    if (isEmbeddedView) return;
    const DATA = window.KZOCN_DATA;
    const barEl = document.getElementById("kzosn-global-context-info");
    if (!barEl || !DATA) return;

    const rec = getNormRecord(state.ed, state.norm);
    if (rec) {
      const title = (DATA.titles && DATA.titles[rec[9]]) || "";
      const convStr =
        rec[12] !== null && rec[12] !== undefined
          ? ` <span style="color:#475569;">|</span> Засуджено: <b style="color:#f0abfc">${rec[12].toLocaleString("uk-UA")} ос.</b>`
          : "";
      barEl.innerHTML = `
        <span style="color:#94a3b8;">Норма:</span>
        <b style="color:#38bdf8;">${rec[4]}</b>
        <span style="color:#cbd5e1;" title="${title}">(${title.slice(0, 32)}${title.length > 32 ? "…" : ""})</span>
        <span style="color:#475569;">|</span>
        <span>Рік: <b style="color:#fde047;">${state.ed === "current" ? "2026" : state.ed}</b></span>
        <span style="color:#475569;">|</span>
        <span>I<sub>КЗОСН</sub> = <b style="color:#4ade80;">${rec[5].toFixed(2)}</b> (#${rec[6]}/${rec[7]})</span>${convStr}
      `;
    }
  }

  const mountedFrames = {}; // modId -> HTMLIFrameElement

  function broadcastToFrames() {
    Object.values(mountedFrames).forEach((ifr) => {
      if (ifr && ifr.contentWindow) {
        ifr.contentWindow.postMessage({ type: "KZOSN_STATE_SYNC", state }, "*");
      }
    });
  }

  window.addEventListener("message", (e) => {
    if (!e.data || typeof e.data !== "object") return;
    if (e.data.type === "KZOSN_STATE_UPDATE" && !isEmbeddedView) {
      state = { ...state, ...e.data.state };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch (err) {}
      updateUrlHash();
      updateContextRibbonUI();
      notifyListeners(state);
      broadcastToFrames();
    } else if (e.data.type === "KZOSN_STATE_SYNC" && isEmbeddedView) {
      state = { ...state, ...e.data.state };
      notifyListeners(state);
    }
  });

  function switchActiveModule(targetModId) {
    const hostFile = getCurrentFileName();
    const hostModId = MODULES.find((m) => m.file === hostFile)?.id || "atlas";
    state.mod = targetModId;
    updateUrlHash();

    // Update top nav active tab button
    document.querySelectorAll(".agy-mod-link").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.mod === targetModId);
    });

    const deckEl = document.getElementById("agy-spa-iframe-deck");
    if (!deckEl) return;

    if (targetModId === hostModId) {
      // Show the host page's native content directly
      deckEl.style.display = "none";
      notifyListeners(state);
      window.dispatchEvent(new Event("resize"));
    } else {
      // Show the persistent SPA iframe deck on top of host content (below the 48px persistent header)
      deckEl.style.display = "block";
      const modMeta = MODULES.find((m) => m.id === targetModId);
      if (!modMeta) return;

      if (!mountedFrames[targetModId]) {
        const ifr = document.createElement("iframe");
        ifr.src = `${modMeta.file}?spa=1${window.location.hash}`;
        ifr.style.cssText = "width:100%; height:100%; border:none; display:block; background:#050811;";
        ifr.addEventListener("load", () => {
          if (ifr.contentWindow) {
            ifr.contentWindow.postMessage({ type: "KZOSN_STATE_SYNC", state }, "*");
          }
        });
        deckEl.appendChild(ifr);
        mountedFrames[targetModId] = ifr;
      }

      Object.entries(mountedFrames).forEach(([mId, ifr]) => {
        const show = mId === targetModId;
        ifr.style.display = show ? "block" : "none";
        if (show && ifr.contentWindow) {
          ifr.contentWindow.postMessage({ type: "KZOSN_STATE_SYNC", state }, "*");
        }
      });
    }
  }

  function initShellDOM() {
    // Always remove any legacy per-page .top-nav so there is only ONE unified persistent menu
    const oldNav = document.querySelector(".top-nav");
    if (oldNav) oldNav.remove();

    if (isEmbeddedView) {
      // Inside an embedded SPA module view, hide any redundant top nav and let the parent's persistent menu govern
      return;
    }

    const hostFile = getCurrentFileName();
    const hostModId = MODULES.find((m) => m.file === hostFile)?.id || "atlas";

    const style = document.createElement("style");
    style.textContent = `
      body {
        padding-top: 48px !important;
      }
      .toolbar {
        top: 48px !important;
      }
      .agy-app-shell {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 48px;
        background: linear-gradient(90deg, #060b17 0%, #0d162c 50%, #060b17 100%);
        border-bottom: 1px solid rgba(56, 189, 248, 0.35);
        padding: 0 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        z-index: 10000;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.65);
        font-family: 'Segoe UI', system-ui, sans-serif;
      }
      .agy-nav-modules {
        display: flex;
        align-items: center;
        gap: 5px;
        overflow-x: auto;
        flex-shrink: 0;
      }
      .agy-mod-link {
        text-decoration: none;
        color: #cbd5e1;
        font-size: 11.5px;
        font-weight: 600;
        padding: 5px 9px;
        border-radius: 7px;
        background: rgba(30, 41, 59, 0.75);
        border: 1px solid rgba(148, 163, 184, 0.24);
        transition: all 0.14s;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        white-space: nowrap;
        cursor: pointer;
      }
      .agy-mod-link:hover {
        border-color: #38bdf8;
        color: #fff;
        background: rgba(56, 189, 248, 0.2);
      }
      .agy-mod-link.active {
        background: linear-gradient(135deg, #0284c7, #6366f1);
        color: #fff;
        border-color: #7dd3fc;
        box-shadow: 0 2px 12px rgba(56, 189, 248, 0.4);
      }
      .agy-context-right {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 11px;
        color: #e2e8f0;
        white-space: nowrap;
        min-width: 0;
        overflow: hidden;
      }
      #kzosn-global-context-info {
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
      }
      .agy-share-btn {
        background: rgba(56, 189, 248, 0.16);
        border: 1px solid rgba(56, 189, 248, 0.48);
        color: #7dd3fc;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 11.5px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.15s;
      }
      .agy-share-btn:hover {
        background: #38bdf8;
        color: #090d16;
      }
      #agy-spa-iframe-deck {
        position: fixed;
        top: 48px;
        left: 0;
        right: 0;
        bottom: 0;
        background: #050811;
        z-index: 9500;
        display: none;
      }
    `;
    document.head.appendChild(style);

    const shell = document.createElement("nav");
    shell.className = "agy-app-shell";

    const navHtml = MODULES.map((m) => {
      const isAct = m.id === (state.mod || hostModId);
      return `<button type="button" class="agy-mod-link ${isAct ? "active" : ""}" data-mod="${m.id}">${m.label}</button>`;
    }).join("");

    shell.innerHTML = `
      <div class="agy-nav-modules">${navHtml}</div>
      <div class="agy-context-right">
        <div id="kzosn-global-context-info"></div>
        <button type="button" class="agy-share-btn" id="kzosn-share-link-btn" title="Скопіювати пряме посилання на поточний модуль, рік та обрану статтю">🔗 Посилання на зріз</button>
      </div>
    `;
    document.body.insertBefore(shell, document.body.firstChild);

    const deck = document.createElement("div");
    deck.id = "agy-spa-iframe-deck";
    document.body.appendChild(deck);

    shell.querySelectorAll(".agy-mod-link").forEach((btn) => {
      btn.addEventListener("click", () => {
        switchActiveModule(btn.dataset.mod);
      });
    });

    const shareBtn = document.getElementById("kzosn-share-link-btn");
    if (shareBtn) {
      shareBtn.addEventListener("click", () => {
        updateUrlHash();
        navigator.clipboard.writeText(window.location.href).then(() => {
          const orig = shareBtn.textContent;
          shareBtn.textContent = "✓ Скопійовано!";
          setTimeout(() => (shareBtn.textContent = orig), 1800);
        });
      });
    }

    updateContextRibbonUI();

    // If URL hash requested a different module than the host HTML file, switch to it immediately
    if (state.mod && state.mod !== hostModId) {
      switchActiveModule(state.mod);
    }
  }

  window.KZOSN_SHELL = {
    getState: () => ({ ...state }),
    setState: (patch) => saveState(patch, true),
    onStateChange: (fn) => listeners.push(fn),
    switchModule: (modId) => {
      if (isEmbeddedView && window.top && window.top.KZOSN_SHELL) {
        window.top.KZOSN_SHELL.switchModule(modId);
      } else {
        switchActiveModule(modId);
      }
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initShellDOM);
  } else {
    initShellDOM();
  }
})();
