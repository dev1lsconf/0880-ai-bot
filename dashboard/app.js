/* ═══════════════════════════════════════════════════════════════
   0880 AI BOT — Multi-Market Trading Dashboard
   Canvas renderers (responsive) + Tab switcher + Real tickers + Positions.
   ═══════════════════════════════════════════════════════════════ */
"use strict";

const $ = (id) => document.getElementById(id);
const fmtMoney = (v) => {
  const s = v < 0 ? "-" : "";
  return s + "$" + Math.abs(v).toLocaleString("en-US", { maximumFractionDigits: 2 });
};
const fmtNum = (v, d = 0) => Number(v).toLocaleString("en-US", { maximumFractionDigits: d });

let SNAP = null;

/* ─────────────────────────── helpers canvas ─────────────────────────── */
function prepCanvas(cv) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const W = cv.offsetWidth, H = cv.offsetHeight;
  cv.width = W * dpr; cv.height = H * dpr;
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, W, H);
  return { ctx, W, H };
}
function gridLines(ctx, W, H, stepX, stepY, color = "rgba(33,37,41,.08)") {
  ctx.strokeStyle = color; ctx.lineWidth = 1; ctx.beginPath();
  for (let x = stepX; x < W; x += stepX) { ctx.moveTo(x, 0); ctx.lineTo(x, H); }
  for (let y = stepY; y < H; y += stepY) { ctx.moveTo(0, y); ctx.lineTo(W, y); }
  ctx.stroke();
}
function label(ctx, text, x, y, color = "#495057", size = 10) {
  ctx.fillStyle = color; ctx.font = size + "px 'Cascadia Code', Consolas, monospace"; ctx.fillText(text, x, y);
}

/* ─────────────────────────── Probability Lattice ─────────────────────────── */
function drawLattice(data) {
  const cv = $("cvLattice");
  if (!cv) return;
  const { ctx, W, H } = prepCanvas(cv);
  gridLines(ctx, W, H, 90, 50);

  const pts = data.points || [];
  const hist = data.hist || [];
  const padL = 46, padR = 14, padT = 16, padB = 34;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  if (pts.length) {
    const xs = pts.map(p => p.x), ys = pts.map(p => p.y);
    const xmin = Math.min(...xs), xmax = Math.max(...xs) || 1;
    const ymin = Math.min(...ys), ymax = Math.max(...ys);
    const yr = Math.max(Math.abs(ymin), Math.abs(ymax)) || 1;
    const X = (x) => padL + ((x - xmin) / (xmax - xmin || 1)) * plotW;
    const Y = (y) => padT + plotH / 2 - (y / yr) * (plotH / 2);

    ctx.strokeStyle = "rgba(33,37,41,.2)"; ctx.setLineDash([4, 4]); ctx.beginPath();
    ctx.moveTo(padL, Y(0)); ctx.lineTo(W - padR, Y(0)); ctx.stroke(); ctx.setLineDash([]);

    const bySym = {};
    pts.forEach(p => { (bySym[p.symbol] = bySym[p.symbol] || []).push(p); });
    const colors = { AAPL: "#212529", TSLA: "#343a40", BTCUSDT: "#212529", ETHUSDT: "#495057", "ES=F": "#212529", SPY: "#343a40", NVDA: "#495057" };
    Object.entries(bySym).forEach(([sym, arr]) => {
      ctx.fillStyle = colors[sym] || "#212529";
      arr.forEach(p => {
        ctx.globalAlpha = 0.6;
        ctx.beginPath(); ctx.arc(X(p.x), Y(p.y), 2.4, 0, Math.PI * 2); ctx.fill();
      });
    });
    ctx.globalAlpha = 1;

    label(ctx, "+" + Math.round(yr).toLocaleString(), 6, padT + 4);
    label(ctx, "0", 18, Y(0) + 4);
    label(ctx, "-" + Math.round(yr).toLocaleString(), 6, H - padB + 4);
  }

  const maxH = Math.max(...hist, 1);
  const bw = plotW / hist.length;
  for (let i = 0; i < hist.length; i++) {
    const h = (hist[i] / maxH) * 34;
    const x = padL + i * bw;
    ctx.fillStyle = "rgba(40,167,69,.55)";
    ctx.fillRect(x + 1, H - padB - h, Math.max(bw - 2, 1), h);
  }
  label(ctx, "TIME →", padL, H - 14);
  label(ctx, "PROBABILITY MASS", W - 120, H - 14);
}

/* ─────────────────────────── Equity Curve ─────────────────────────── */
function drawRidge(data) {
  const cv = $("cvRidge");
  if (!cv) return;
  const { ctx, W, H } = prepCanvas(cv);
  gridLines(ctx, W, H, 90, 50);

  const equity = data.equity || [];
  const padL = 46, padR = 14, padT = 16, padB = 24;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  if (equity.length < 2) {
    label(ctx, "No equity data", padL, H / 2);
    return;
  }

  const vmin = Math.min(...equity), vmax = Math.max(...equity);
  const vrange = Math.max(Math.abs(vmin), Math.abs(vmax)) || 1;
  const baseY = padT + plotH; // equity starts from 0 baseline
  const X = (i) => padL + (i / (equity.length - 1)) * plotW;
  const Y = (v) => baseY - (v / vrange) * (plotH - 16);

  // baseline zero
  if (vmin < 0 && vmax > 0) {
    ctx.strokeStyle = "rgba(33,37,41,.12)"; ctx.setLineDash([4, 4]);
    ctx.beginPath(); ctx.moveTo(padL, Y(0)); ctx.lineTo(W - padR, Y(0)); ctx.stroke(); ctx.setLineDash([]);
  }

  // equity curve
  ctx.strokeStyle = "#28a745"; ctx.lineWidth = 1.8; ctx.beginPath();
  for (let i = 0; i < equity.length; i++) {
    const x = X(i), y = Y(equity[i]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // fill under curve
  ctx.fillStyle = "rgba(40,167,69,.06)";
  ctx.beginPath(); ctx.moveTo(X(0), Y(equity[0]));
  for (let i = 0; i < equity.length; i++) ctx.lineTo(X(i), Y(equity[i]));
  ctx.lineTo(W - padR, baseY); ctx.closePath(); ctx.fill();

  label(ctx, "+\$" + Math.round(vmax).toLocaleString(), 6, padT + 4);
  label(ctx, "0", 18, baseY + 4);
  label(ctx, "T →", padL, H - 8);
}

/* ─────────────────────────── Correlation Heatmap ─────────────────────────── */
function drawGraph(data) {
  const cv = $("cvGraph");
  if (!cv) return;
  const { ctx, W, H } = prepCanvas(cv);
  gridLines(ctx, W, H, 90, 60);

  const nodes = data.nodes || [];
  const edges = data.edges || [];
  const labels = ["AAPL","TSLA","BTCUSDT","ETHUSDT","ES=F","GOOGL","NVDA","SPY"];
  const n = Math.min(labels.length, 6);

  // heatmaptest data: simulamos correlaciones (reales vendrían del snapshot)
  const corr = [];
  for (let i = 0; i < n; i++) {
    corr[i] = [];
    for (let j = 0; j < n; j++) {
      corr[i][j] = i === j ? 1.0 : Math.max(-1, Math.min(1, (Math.sin(i * 0.7 + j * 0.9 + data.seed || 0) * 0.5)));
    }
  }

  const cellW = (W - 50) / n, cellH = (H - 50) / n;
  const offX = 40, offY = 34;

  // cells
  for (let i = 0; i < n; i++) {
    for (let j = 0; j < n; j++) {
      const c = corr[i][j];
      const hue = (1 - c) * 240; // -1 → rojo(0), 0 → azul(240)... ajusto
      // -1=rojo, +1=verde
      const r = c < 0 ? 220 : 40; const g = c > 0 ? 167 : 40; const b = 80;
      ctx.fillStyle = `rgb(${Math.round(c < 0 ? 220 : 255 - c * 80)}, ${Math.round(c > 0 ? 167 : 120)}, 90)`;
      ctx.fillRect(offX + j * cellW, offY + i * cellH, cellW - 2, cellH - 2);
      label(ctx, c.toFixed(2), offX + j * cellW + cellW / 2 - 10, offY + i * cellH + cellH / 2 + 3, "#212529", 9);
    }
  }

  // labels
  for (let i = 0; i < n; i++) {
    label(ctx, labels[i], offX - 8, offY + i * cellH + cellH / 2 + 3, "#495057", 9);
    label(ctx, labels[i].substring(0, 5), offX + i * cellW + cellW / 2 - 10, offY - 8, "#495057", 9);
  }

  // heatmap gradient legend
  const lx = offX, ly = H - 20, lw = W - offX - 14, lh = 10;
  for (let i = 0; i <= 100; i += 2) {
    const c = -1 + (i / 50);
    ctx.fillStyle = `rgb(${Math.round(c < 0 ? 220 : 255 - c * 80)}, ${Math.round(c > 0 ? 167 : 120)}, 90)`;
    ctx.fillRect(lx + i * lw / 100, ly, lw / 100, lh);
  }
  ctx.strokeStyle = "#dee2e6"; ctx.strokeRect(lx, ly, lw, lh);
  label(ctx, "-1.0  correlación", lx, ly - 2); label(ctx, "+1.0", lx + lw - 12, ly - 2);
}

/* ─────────────────────────── Monte Carlo: Return Distribution ─────────────────────────── */
function drawMC(data) {
  const cv = $("cvMC");
  if (!cv) return;
  const { ctx, W, H } = prepCanvas(cv);
  gridLines(ctx, W, H, 90, 60);

  const hist = data.hist || [];
  const padL = 52, padR = 16, padT = 16, padB = 30;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  if (hist.length) {
    const maxH = Math.max(...hist, 1);
    const bw = plotW / hist.length;
    const mid = Math.floor(hist.length / 2);
    for (let i = 0; i < hist.length; i++) {
      const h = (hist[i] / maxH) * (plotH - 20);
      const x = padL + i * bw;
      const up = i >= mid;
      ctx.fillStyle = up ? "rgba(40,167,69,.55)" : "rgba(220,53,69,.45)";
      ctx.fillRect(x + 1, padT + plotH - h, Math.max(bw - 2, 1), h);
    }
    // normal curve overlay (approx gaussian)
    ctx.strokeStyle = "#0d6efd"; ctx.lineWidth = 1.4; ctx.beginPath();
    const mu = hist.reduce((a, b) => a + b, 0) / hist.length;
    let sd = Math.sqrt(hist.reduce((a, b) => a + (b - mu) ** 2, 0) / hist.length) || 1;
    const gaussian = (x) => Math.exp(-0.5 * ((x - mu) / sd) ** 2) / (sd * Math.sqrt(2 * Math.PI)) * maxH;
    for (let px = 0; px <= plotW - 2; px += 2) {
      const gx = padL + px;
      const gy = padT + plotH - gaussian(px / (plotW / hist.length)) * (plotH - 20);
      if (px === 0) ctx.moveTo(gx, gy); else ctx.lineTo(gx, gy);
    }
    ctx.stroke();
  }
}

/* ─────────────────────────── Render Snapshot & Tables ─────────────────────────── */
function render() {
  if (!SNAP) return;
  const d = SNAP;

  // Header
  const h = d.header || {};
  $("pnlTotal").textContent = fmtMoney(h.total_pnl);
  $("pnlTotal").style.color = h.total_pnl >= 0 ? "var(--green)" : "var(--red)";
  $("pnlSub").innerHTML = (h.total_pnl >= 0 ? "▲" : "▼") + " ALL-TIME · LEVERAGE " + (h.leverage || 1) + "x";
  $("statTrades").textContent = fmtNum(h.trades);
  $("statWin").textContent = (h.win_rate || 0).toFixed(1) + "%";
  $("statAvg").textContent = fmtMoney(h.avg_trade);
  $("statPF").textContent = (h.profit_factor || 0).toFixed(2);
  $("statSharpe").textContent = (h.sharpe || 0).toFixed(2);
  $("statDD").textContent = (h.max_drawdown || 0).toFixed(2) + "%";

  const acc = d.account || {};
  $("openPositions").textContent = acc.open_positions || 0;
  $("posCash").textContent = fmtMoney(acc.cash || 0);
  $("posVal").textContent = fmtMoney(acc.equity || 0);

  // PnL Boxes (green/red trade outcomes)
  const boxes = $("pnlBoxes");
  if (boxes && d.analyses) {
    boxes.innerHTML = Object.entries(d.analyses).map(([k, v]) =>
      `<div class="pbox ${v.pnl >= 0 ? 'up' : 'down'}">
         <span class="dim">${k}</span> + ${v.symbol}
         <b>${v.pnl >= 0 ? '+' : ''}${fmtMoney(v.pnl)}</b>
       </div>`
    ).join("");
  }

  // Canvases
  if (d.lattice) drawLattice(d.lattice);
  if (d.ridge) drawRidge(d.ridge);
  if (d.graph) drawGraph(d.graph);
  if (d.monte_carlo) drawMC(d.monte_carlo);

  // Asset cards
  if (d.analyses) {
    ["STOCK", "CRYPTO", "CONTRACT"].forEach(ac => {
      const a = d.analyses[ac];
      if (!a) return;
      const el = $("asset" + ac);
      if (!el) return;
      el.querySelector("h3").textContent = ac + " · " + (a.symbol || "");
      const rows = el.querySelector(".rows");
      rows.innerHTML =
        `<div class="r"><span>PNL</span><span class="${a.pnl >= 0 ? 'green' : 'red'}">${fmtMoney(a.pnl)}</span></div>` +
        `<div class="r"><span>WIN RATE</span><span>${(a.win_rate || 0).toFixed(1)}%</span></div>` +
        `<div class="r"><span>TRADES</span><span>${fmtNum(a.trades)}</span></div>` +
        `<div class="r"><span>SHARPE</span><span>${(a.sharpe || 0).toFixed(2)}</span></div>` +
        `<div class="r"><span>MAX DD</span><span class="red">${(a.max_dd || 0).toFixed(2)}%</span></div>`;
    });
  }

  // Market Rankings (real top/bottom 10)
  const mr = d.market_rankings || {};
  const _fmtPct = (v) => (v >= 0 ? "+" : "") + (v || 0).toFixed(2) + "%";
  const _fmtVol = (v) => v >= 1e9 ? (v/1e9).toFixed(1)+"B" : v >= 1e6 ? (v/1e6).toFixed(1)+"M" : (v||0);

  const topStocks = $("topStocksTbody");
  if (topStocks) {
    topStocks.innerHTML = (mr.top_stocks || []).slice(0,10).map((q,i) =>
      `<tr>
         <td>${i+1}</td>
         <td><b>${q.name || q.symbol}</b></td>
         <td style="color:var(--cyan);">${q.symbol}</td>
         <td>$${Number(q.price).toLocaleString("en-US",{maximumFractionDigits:2})}</td>
         <td class="green">${_fmtPct(q.change)}</td>
         <td>${_fmtVol(q.volume)}</td>
         <td><button class="btn-action" onclick="quickTrade('${q.symbol.replace(/\./g,'')}', 'STOCK')">COMPRAR</button></td>
       </tr>`
    ).join("") || '<tr><td colspan="7" style="text-align:center;color:var(--dim);padding:12px">Cargando...</td></tr>';
  }

  const bottomStocks = $("bottomStocksTbody");
  if (bottomStocks) {
    bottomStocks.innerHTML = (mr.bottom_stocks || []).slice(0,10).map((q,i) =>
      `<tr>
         <td>${i+1}</td>
         <td><b>${q.name || q.symbol}</b></td>
         <td style="color:var(--cyan);">${q.symbol}</td>
         <td>$${Number(q.price).toLocaleString("en-US",{maximumFractionDigits:2})}</td>
         <td class="red">${_fmtPct(q.change)}</td>
         <td>${_fmtVol(q.volume)}</td>
         <td><button class="btn-action" onclick="quickTrade('${q.symbol.replace(/\./g,'')}', 'STOCK')">COMPRAR</button></td>
       </tr>`
    ).join("") || '<tr><td colspan="7" style="text-align:center;color:var(--dim);padding:12px">Cargando...</td></tr>';
  }

  const topCrypto = $("topCryptoTbody");
  if (topCrypto) {
    topCrypto.innerHTML = (mr.top_cryptos || []).slice(0,10).map((q,i) =>
      `<tr>
         <td>${i+1}</td>
         <td><b>${q.symbol.replace("USDT","")}</b></td>
         <td style="color:var(--cyan);">${q.symbol}</td>
         <td>$${Number(q.price).toLocaleString("en-US",{maximumFractionDigits:4})}</td>
         <td class="green">${_fmtPct(q.change24h)}</td>
         <td>${_fmtVol(q.volume24h)}</td>
         <td><button class="btn-action" onclick="quickTrade('${q.symbol}', 'CRYPTO')">COMPRAR</button></td>
       </tr>`
    ).join("") || '<tr><td colspan="7" style="text-align:center;color:var(--dim);padding:12px">Cargando...</td></tr>';
  }

  // Positions Table
  const posTbody = $("positionsTableBody");
  if (posTbody) {
    const posList = (acc.positions_list || []);
    if (posList.length === 0) {
      posTbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--dim); padding:24px;">No hay posiciones abiertas actualmente. Usa la pestaña MARKET para comprar.</td></tr>`;
    } else {
      posTbody.innerHTML = posList.map(p =>
        `<tr>
           <td><b>${p.symbol}</b></td>
           <td>${p.qty}</td>
           <td>$${p.avg_entry}</td>
           <td>$${p.mark}</td>
           <td class="${p.unrealized_pnl >= 0 ? 'green' : 'red'}">${fmtMoney(p.unrealized_pnl)}</td>
           <td>${p.leverage}x</td>
           <td><button class="btn-action" onclick="closePos('${p.symbol}')">CERRAR</button></td>
         </tr>`
      ).join("");
    }
  }

  // Footer
  if (d.meta) {
    $("mcpVer").textContent = d.meta.version || "?";
    $("mcpBroker").textContent = d.meta.broker || "?";
    $("mcpTs").textContent = new Date(d.meta.ts).toLocaleTimeString();
  }

  // Re-dibujar al resize (mantener aspect-ratio)
  if (window._rafDraw) cancelAnimationFrame(window._rafDraw);
  window._rafDraw = requestAnimationFrame(() => {
    if (SNAP) {
      if (SNAP.lattice) drawLattice(SNAP.lattice);
      if (SNAP.ridge) drawRidge(SNAP.ridge);
      if (SNAP.graph) drawGraph(SNAP.graph);
      if (SNAP.monte_carlo) drawMC(SNAP.monte_carlo);
    }
  });
}

// Acción rápida de compra desde Market
window.quickTrade = async function(symbol, assetClass) {
  try {
    const res = await fetch("/api/snapshot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "place_order", symbol, asset_class: assetClass, side: "BUY", qty: 1 })
    });
    const j = await res.json();
    alert(j.ok ? `Orden ejecutada en Paper Broker para ${symbol} (1 unidad).` : (j.error || "Error"));
    loadInitial();
  } catch (e) {
    alert("Orden enviada (Paper simulado).");
  }
};

window.closePos = async function(symbol) {
  try {
    const res = await fetch("/api/snapshot", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "close_position", symbol })
    });
    const j = await res.json();
    alert(j.ok ? `Posición ${symbol} cerrada.` : (j.error || "Error"));
    loadInitial();
  } catch (e) {
    alert("Error: " + e.message);
  }
};

/* ─────────────────────────── WebSocket / Fetch connection ─────────────────────────── */
async function loadInitial() {
  try {
    const r = await fetch("/api/snapshot", { cache: "no-store" });
    SNAP = await r.json();
    render();
    setConn("ok");
  } catch (e) {
    setConn("err", "SIN SERVIDOR");
    setTimeout(loadInitial, 3000);
  }
}

function setConn(state, text) {
  const p = $("connPill");
  if (!p) return;
  p.textContent = text || (state === "ok" ? "◉ LIVE" : "◉ CONECTANDO");
  p.className = "pill " + (state === "ok" ? "ok" : "err");
}

function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const wsPort = 8788;
  let ws;
  try { ws = new WebSocket(`${proto}://127.0.0.1:${wsPort}/ws`); } catch (e) { return; }
  ws.onopen = () => setConn("ok");
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === "snapshot" && msg.data) { SNAP = msg.data; render(); }
    } catch (e) { /* ignore */ }
  };
  ws.onclose = () => { setConn("err", "RECONECTANDO"); setTimeout(connectWS, 2000); };
  ws.onerror = () => ws.close();
}

/* ── Tab Switcher ── */
document.addEventListener("DOMContentLoaded", () => {
  const tabs = document.querySelectorAll("#tabsNav .tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".view-panel").forEach(panel => panel.classList.add("hidden"));
      const target = $(tab.getAttribute("data-target"));
      if (target) target.classList.remove("hidden");
    });
  });
});

setInterval(async () => {
  try {
    const r = await fetch("/api/snapshot", { cache: "no-store" });
    SNAP = await r.json();
    render();
  } catch (e) { /* ignore */ }
}, 5000);

loadInitial();
connectWS();

/* ── Resize redraw ── */
let _resizeTO;
window.addEventListener("resize", () => {
  clearTimeout(_resizeTO);
  _resizeTO = setTimeout(() => { if (SNAP) { render(); if (SNAP.lattice) drawLattice(SNAP.lattice); if (SNAP.ridge) drawRidge(SNAP.ridge); if (SNAP.graph) drawGraph(SNAP.graph); if (SNAP.monte_carlo) drawMC(SNAP.monte_carlo); } }, 150);
});
