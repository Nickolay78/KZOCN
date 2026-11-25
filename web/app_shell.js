/**
 * KZOSN Unified Web Application Shell (SPA State & Global Navigation Bar)
 * Connects all modules into a cohesive analytical web application with:
 *  - Shared persistent state (localStorage + URL Hash Deep-Linking)
 *  - Global Active Norm Context Bar (1-click cross-module jumps preserving selected norm, year, and section)
 *  - Instant Deep-Link Share button ("Скопіювати посилання на поточний зріз")
 */
(function () {
  const STORAGE_KEY = "KZOSN_APP_STATE_V1";

  function parseHashParams() {
    const h = window.location.hash.replace(/^#\/?/, "");
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
    return {
      ed: fromHash.ed || saved.ed || "2025",
      sec: fromHash.sec || saved.sec || "ALL",
      norm: fromHash.norm || saved.norm || "185|4",
      rad: fromHash.rad !== undefined ? Number(fromHash.rad) : saved.rad !== undefined ? Number(saved.rad) : 1,
      decile: fromHash.decile !== undefined ? Number(fromHash.decile) : saved.decile !== undefined ? Number(saved.decile) : 1,
    };
  }

  let state = loadInitialState();

  function saveState(patch = {}) {
    state = { ...state, ...patch };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch (e) {}
    updateUrlHash();
    updateContextRibbonUI();
  }

  function updateUrlHash() {
    const p = new URLSearchParams();
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
    const DATA = window.KZOCN_DATA;
    const barEl = document.getElementById("kzosn-global-context-info");
    if (!barEl || !DATA) return;

    const rec = getNormRecord(state.ed, state.norm);
    if (rec) {
      const title = (DATA.titles && DATA.titles[rec[9]]) || "";
      const convStr =
        rec[12] !== null && rec[12] !== undefined
          ? ` | Засуджено: <b style="color:#f0abfc">${rec[12].toLocaleString("uk-UA")} ос.</b>`
          : "";
      barEl.innerHTML = `
        <span style="color:#94a3b8;">Активна норма:</span>
        <b style="color:#38bdf8;">${rec[4]}</b>
        <span style="color:#cbd5e1;">(${title.slice(0, 42)}${title.length > 42 ? "…" : ""})</span>
        <span style="color:#64748b;">|</span>
        <span>Рік: <b style="color:#fde047;">${state.ed === "current" ? "2026" : state.ed}</b></span>
        <span style="color:#64748b;">|</span>
        <span>I<sub>КЗОСН</sub> = <b style="color:#4ade80;">${rec[5].toFixed(2)}</b> (#${rec[6]}/${rec[7]})</span>
        ${convStr}
      `;
    }
  }

  function injectGlobalAppShell() {
    // Remove old static .top-nav if present so all pages share the identical unified App Shell header
    const oldNav = document.querySelector(".top-nav");
    if (oldNav) oldNav.remove();

    const path = window.location.pathname.split("/").pop() || "index.html";

    const style = document.createElement("style");
    style.textContent = `
      .agy-app-shell {
        width: 100%;
        background: linear-gradient(90deg, #060b16 0%, #0b1326 50%, #060b16 100%);
        border-bottom: 1px solid rgba(56, 189, 248, 0.28);
        padding: 6px 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 10px;
        z-index: 60;
        flex-shrink: 0;
        font-family: 'Segoe UI', system-ui, sans-serif;
      }
      .agy-nav-modules {
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
      }
      .agy-mod-link {
        text-decoration: none;
        color: #cbd5e1;
        font-size: 12px;
        font-weight: 600;
        padding: 5px 11px;
        border-radius: 7px;
        background: rgba(30, 41, 59, 0.72);
        border: 1px solid rgba(148, 163, 184, 0.22);
        transition: all 0.14s;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        white-space: nowrap;
      }
      .agy-mod-link:hover {
        border-color: #38bdf8;
        color: #fff;
        background: rgba(56, 189, 248, 0.18);
      }
      .agy-mod-link.active {
        background: linear-gradient(135deg, #0284c7, #6366f1);
        color: #fff;
        border-color: #7dd3fc;
        box-shadow: 0 2px 12px rgba(56, 189, 248, 0.35);
      }
      .agy-context-right {
        display: flex;
        align-items: center;
        gap: 10px;
        font-size: 11.5px;
        color: #e2e8f0;
        flex-wrap: wrap;
      }
      .agy-share-btn {
        background: rgba(56, 189, 248, 0.15);
        border: 1px solid rgba(56, 189, 248, 0.45);
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
    `;
    document.head.appendChild(style);

    const modules = [
      { file: "index.html",      label: "🌐 1. 3D-Атлас КК" },
      { file: "deciles.html",    label: "🏛 2. 10 Децилів (3D + 2D)" },
      { file: "comparator.html", label: "⚖️ 3. Компаратор (±1..5%)" },
      { file: "calculator.html", label: "🧪 4. Калькулятор санкції" },
      { file: "fb_post_v2.html", label: "✨ 5. Інфографіка v2 (FB)" },
      { file: "fb_post_2d.html", label: "📊 6. Постер v1" },
    ];

    const shell = document.createElement("nav");
    shell.className = "agy-app-shell";

    const navHtml = modules
      .map((m) => {
        const isAct = path === m.file || (path === "" && m.file === "index.html");
        return `<a href="${m.file}" class="agy-mod-link ${isAct ? "active" : ""}" data-target="${m.file}">${m.label}</a>`;
      })
      .join("");

    shell.innerHTML = `
      <div class="agy-nav-modules">${navHtml}</div>
      <div class="agy-context-right">
        <div id="kzosn-global-context-info"></div>
        <button class="agy-share-btn" id="kzosn-share-link-btn" title="Скопіювати пряме посилання на поточний рік та обрану статтю">🔗 Посилання на зріз</button>
      </div>
    `;

    document.body.insertBefore(shell, document.body.firstChild);

    // Ensure module links carry current hash parameters for seamless transition
    shell.querySelectorAll(".agy-mod-link").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        updateUrlHash();
        window.location.href = a.dataset.target + window.location.hash;
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
  }

  window.KZOSN_SHELL = {
    getState: () => ({ ...state }),
    setState: (patch) => saveState(patch),
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectGlobalAppShell);
  } else {
    injectGlobalAppShell();
  }
})();
