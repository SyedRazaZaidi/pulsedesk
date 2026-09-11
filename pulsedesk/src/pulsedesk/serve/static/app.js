const $ = (id) => document.getElementById(id);
const state = {
  board: [],
  selected: 0,
  alpha: 0.8,
  pulse: null,
  series: null,
  hover: null,
  stores: [],
  skus: [],
  ledOffset: 0,
  commandReady: false,
  filter: "all",
  shock: 1,
  intel: { transfers: [], anomalies: [] },
  sister: [],
  theaterOpen: false,
};

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toast._t);
  toast._t = setTimeout(() => {
    el.hidden = true;
  }, 2400);
}

function esc(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function fmt(v) {
  return typeof v === "number" ? v.toFixed(2) : "—";
}

async function j(url, opts) {
  const r = await fetch(url, opts);
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("application/json") ? r.json() : r.text();
}

function fillSelect(el, rows, val, lab, extra) {
  const keep = extra || `<option value="">all</option>`;
  el.innerHTML = keep + rows.map((r) => `<option value="${r[val]}">${esc(r[lab])}</option>`).join("");
}

function fitCanvas(canvas, cssH) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = Math.max(canvas.clientWidth || canvas.parentElement.clientWidth, 100);
  const h = cssH || canvas.clientHeight || 140;
  canvas.width = Math.floor(w * dpr);
  canvas.height = Math.floor(h * dpr);
  canvas.style.height = `${h}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w, h };
}

function bootField() {
  const c = $("field");
  const lamps = [
    { x: 0.18, y: 0.72 },
    { x: 0.78, y: 0.68 },
  ];
  const dust = Array.from({ length: 70 }, () => ({
    x: Math.random(),
    y: Math.random(),
    v: 0.08 + Math.random() * 0.25,
    r: 0.6 + Math.random() * 1.2,
  }));
  let box = { ctx: null, w: 0, h: 0 };
  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = innerWidth;
    const h = innerHeight;
    c.width = Math.floor(w * dpr);
    c.height = Math.floor(h * dpr);
    const ctx = c.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    box = { ctx, w, h };
  };
  resize();
  addEventListener("resize", resize);
  function tick(t) {
    const { ctx, w, h } = box;
    if (!ctx) return requestAnimationFrame(tick);
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "rgba(8, 4, 14, 0.55)";
    const base = h * 0.78;
    let x = 0;
    while (x < w) {
      const bw = 18 + ((x * 13) % 40);
      const bh = 30 + ((x * 17) % 90);
      ctx.fillRect(x, base - bh, bw - 2, bh);
      x += bw;
    }
    lamps.forEach((l, i) => {
      const px = l.x * w;
      const py = l.y * h;
      const g = ctx.createRadialGradient(px, py, 0, px, py, 90);
      g.addColorStop(0, `rgba(255,176,32,${0.22 + Math.sin(t / 400 + i) * 0.06})`);
      g.addColorStop(1, "rgba(255,176,32,0)");
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(px, py, 90, 0, Math.PI * 2);
      ctx.fill();
    });
    dust.forEach((d) => {
      ctx.fillStyle = "rgba(244,231,200,0.22)";
      ctx.beginPath();
      ctx.arc(d.x * w, d.y * h, d.r, 0, Math.PI * 2);
      ctx.fill();
      d.y -= d.v * 0.00035;
      if (d.y < 0) d.y = 1;
    });
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

function tickClock() {
  const paint = () => {
    $("clock").textContent = new Date().toISOString().replace("T", "  ").slice(0, 19) + "Z";
  };
  paint();
  setInterval(paint, 1000);
}

function countUp(el, to, suffix = "%") {
  const start = performance.now();
  const step = (now) => {
    const p = Math.min(1, (now - start) / 1100);
    el.textContent = `${Math.round(to * (1 - (1 - p) ** 3))}${suffix}`;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function pageName() {
  const hash = (location.hash || "#/command").replace("#/", "").split("?")[0];
  return ["command", "ledger", "catalog", "stock", "lab", "tape"].includes(hash) ? hash : "command";
}

function showPage(name) {
  document.body.dataset.page = name;
  document.querySelectorAll(".page").forEach((el) => {
    el.hidden = el.id !== `page-${name}`;
  });
  document.querySelectorAll(".tabs a").forEach((a) => a.classList.toggle("on", a.dataset.page === name));
  if (name === "command") {
    bootCommand();
    if (state.pulse) requestAnimationFrame(() => paintCity(state.pulse.city || []));
    if (state.theaterOpen && state.series) {
      requestAnimationFrame(() => drawWave(state.series.history, state.series.forecast));
    }
  }
  if (name === "ledger") loadLedger();
  if (name === "catalog") loadCatalog();
  if (name === "stock") loadStock();
  if (name === "lab") loadLab();
  if (name === "tape") loadTape();
}

async function loadRefs() {
  const [stores, skus] = await Promise.all([j("/api/stores"), j("/api/skus")]);
  state.stores = stores.stores || [];
  state.skus = skus.skus || [];
  const storeOpts = state.stores;
  const skuOpts = state.skus;
  [
    ["ledStore", true],
    ["ledAddStore", false],
    ["stkStore", false],
    ["labStore", false],
  ].forEach(([id, all]) => {
    const el = $(id);
    if (el) fillSelect(el, storeOpts, "id", "name", all ? `<option value="">both nodes</option>` : "");
  });
  [
    ["ledSku", true],
    ["ledAddSku", false],
    ["stkSku", false],
    ["labSku", false],
  ].forEach(([id, all]) => {
    const el = $(id);
    if (el) fillSelect(el, skuOpts, "id", "sku", all ? `<option value="">all SKUs</option>` : "");
  });
}

async function boot() {
  bootField();
  tickClock();
  addEventListener("hashchange", () => showPage(pageName()));
  addEventListener("resize", () => {
    if (document.body.dataset.page !== "command") return;
    if (state.pulse) paintCity(state.pulse.city || []);
    if (state.theaterOpen && state.series) drawWave(state.series.history, state.series.forecast);
  });
  addEventListener("keydown", onKey);
  try {
    await loadRefs();
    bindWork();
    showPage(pageName());
  } catch (err) {
    $("status").textContent = "desk failed to boot";
    toast(String(err.message || err));
  }
}

function bindWork() {
  $("ledFilters").addEventListener("submit", (e) => {
    e.preventDefault();
    state.ledOffset = 0;
    loadLedger();
  });
  $("ledPrev").addEventListener("click", () => {
    state.ledOffset = Math.max(0, state.ledOffset - 40);
    loadLedger();
  });
  $("ledNext").addEventListener("click", () => {
    state.ledOffset += 40;
    loadLedger();
  });
  $("ledAdd").addEventListener("submit", saveNight);
  $("ledImport").addEventListener("submit", importCsv);
  $("catSku").addEventListener("submit", addSku);
  $("catStore").addEventListener("submit", addStore);
  $("stkMove").addEventListener("submit", moveStock);
  $("labWhat").addEventListener("submit", runWhat);
  $("labAlpha").addEventListener("input", () => {
    $("labAlphaOut").textContent = `p${$("labAlpha").value}`;
  });
  $("palQ").addEventListener("input", paintPalette);
  $("palList").addEventListener("click", (e) => {
    const li = e.target.closest("li");
    if (li) runPal(li.dataset.act, li.dataset.arg);
  });
}

async function bootCommand() {
  if (state.commandReady) {
    $("status").textContent = `${state.pulse?.open_recs ?? "—"} unsigned tickets`;
    return;
  }
  const [health, pulse, board, heat, drivers, alerts, intel] = await Promise.all([
    j("/api/health"),
    j("/api/pulse"),
    j("/api/board"),
    j("/api/heatmap"),
    j("/api/drivers"),
    j("/api/alerts"),
    j("/api/intel"),
  ]);
  state.pulse = pulse;
  state.board = board.items || [];
  state.intel = intel;
  $("status").textContent = `${Number(health.observations).toLocaleString()} nights · ${pulse.open_recs} unsigned`;
  if (pulse.lift_pct != null) countUp($("lift"), pulse.lift_pct);
  paintMeters(pulse);
  paintHarbors(pulse.nodes || []);
  paintCity(pulse.city || []);
  fillSelect($("store"), state.stores, "id", "name", `<option value="">both Karachi nodes</option>`);
  paintHeat(heat.cells || []);
  paintDrivers(drivers.items || [], "drivers");
  paintCats(pulse.categories || []);
  paintAlerts(alerts.items || []);
  paintIntel(intel);
  paintCards();
  $("store").addEventListener("change", reloadBoard);
  $("alpha").addEventListener("input", () => {
    state.alpha = Number($("alpha").value) / 100;
    $("alphaOut").textContent = `p${Math.round(state.alpha * 100)} cover`;
    paintCards();
    refreshMeta();
  });
  $("shock").addEventListener("input", () => {
    state.shock = 1 + Number($("shock").value) / 100;
    $("shockOut").textContent = state.shock === 1 ? "calm night" : `+${$("shock").value}% shock`;
    paintCards();
    refreshMeta();
  });
  $("okBtn").addEventListener("click", () => decide("accept"));
  $("skipBtn").addEventListener("click", () => decide("dismiss"));
  $("thClose").addEventListener("click", closeTheater);
  $("thScrim").addEventListener("click", closeTheater);
  $("packBtn").addEventListener("click", openPack);
  $("packScrim").addEventListener("click", () => {
    $("packBox").hidden = true;
  });
  $("ticketFilter").addEventListener("click", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    state.filter = btn.dataset.f;
    $("ticketFilter").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b === btn));
    paintCards();
  });
  $("wave").addEventListener("mousemove", onWaveHover);
  $("wave").addEventListener("mouseleave", () => {
    state.hover = null;
    if (state.series) drawWave(state.series.history, state.series.forecast);
  });
  state.commandReady = true;
}

function paintMeters(pulse) {
  const m = pulse.metrics || {};
  $("meters").innerHTML = [
    ["Model MAE", fmt(m.mae_model)],
    ["Naive MAE", fmt(m.mae_baseline)],
    ["p10–p90 cover", m.coverage_p10_p90 != null ? `${(m.coverage_p10_p90 * 100).toFixed(0)}%` : "—"],
    ["Unsigned orders", pulse.open_recs],
  ]
    .map(([k, v]) => `<div class="meter"><span>${k}</span><b>${v}</b></div>`)
    .join("");
}

function paintAlerts(items) {
  $("alerts").innerHTML = items
    .slice(0, 6)
    .map((a) => `<div class="alert">${esc(a.kind)} · ${esc(a.sku)} @ ${esc(a.store)}</div>`)
    .join("");
}

function paintHarbors(nodes) {
  $("harbors").innerHTML = nodes
    .map(
      (n) => `<button class="harbor" type="button" data-id="${n.id}">
        <i class="lamp"></i>
        <div>
          <b>${esc(n.name)}</b>
          <span>${esc(n.city)} · ${Math.round(n.units_7d).toLocaleString()} units / 7 nights</span>
        </div>
        <em>${n.open_recs} open</em>
      </button>`
    )
    .join("");
  $("harbors").querySelectorAll(".harbor").forEach((el) => {
    el.addEventListener("click", () => {
      $("store").value = el.dataset.id;
      $("harbors").querySelectorAll(".harbor").forEach((h) => h.classList.toggle("on", h === el));
      reloadBoard();
    });
  });
}

function paintCity(series) {
  const canvas = $("city");
  if (!canvas || canvas.offsetParent === null && document.body.dataset.page !== "command") return;
  const { ctx, w, h } = fitCanvas(canvas, 140);
  const vals = series.map((p) => Number(p.units));
  if (!vals.length) return;
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const pad = 12;
  const x = (i) => pad + (i / Math.max(vals.length - 1, 1)) * (w - pad * 2);
  const y = (v) => h - pad - ((v - min) / Math.max(max - min, 1)) * (h - pad * 2);
  ctx.clearRect(0, 0, w, h);
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, "rgba(255,176,32,0.28)");
  grad.addColorStop(1, "rgba(255,176,32,0)");
  ctx.beginPath();
  vals.forEach((v, i) => {
    if (i === 0) ctx.moveTo(x(i), y(v));
    else ctx.lineTo(x(i), y(v));
  });
  ctx.lineTo(x(vals.length - 1), h - pad);
  ctx.lineTo(x(0), h - pad);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.beginPath();
  vals.forEach((v, i) => {
    if (i === 0) ctx.moveTo(x(i), y(v));
    else ctx.lineTo(x(i), y(v));
  });
  ctx.strokeStyle = "#ffb020";
  ctx.lineWidth = 2;
  ctx.shadowColor = "#ffb020";
  ctx.shadowBlur = 12;
  ctx.stroke();
  ctx.shadowBlur = 0;
}

async function reloadBoard() {
  const id = $("store").value;
  const url = id ? `/api/board?store_id=${id}` : "/api/board";
  state.board = (await j(url)).items || [];
  paintHeat((await j(id ? `/api/heatmap?store_id=${id}` : "/api/heatmap")).cells || []);
  $("harbors").querySelectorAll(".harbor").forEach((h) => h.classList.toggle("on", h.dataset.id === id));
  paintCards();
  if (state.theaterOpen && state.board[state.selected]) openCard(state.selected);
}

function orderQty(row) {
  const mix = (row.need_p50 * (1 - state.alpha) + row.need_p90 * state.alpha) * state.shock;
  return Math.max(0, Math.round(mix - row.on_hand));
}

function visibleBoard() {
  return state.board
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => {
      if (state.filter === "hot") return r.risk > 0.45;
      if (state.filter === "open") return !r.last_action;
      return true;
    });
}

function paintCards() {
  $("cards").innerHTML = visibleBoard()
    .map(({ r, i }, n) => {
      const qty = orderQty(r);
      const hot = r.risk > 0.45;
      return `<article class="ticket" data-i="${i}" style="animation-delay:${n * 0.04}s">
        <div class="head">
          <div>
            <h3>${esc(r.name)}</h3>
            <div class="sku">${esc(r.sku)} · ${esc(r.store)} · ${esc(r.category)}${r.last_action ? ` · ${esc(r.last_action)}` : ""}</div>
          </div>
          <span class="risk ${hot ? "" : "ok"}">${hot ? "STOCKOUT" : "COVERED"}</span>
        </div>
        <svg class="spark" viewBox="0 0 120 28" data-sku="${r.sku_id}" data-store="${r.store_id}"></svg>
        <div class="nums"><span>on hand ${Math.round(r.on_hand)}</span><span class="need">order ${qty}</span></div>
      </article>`;
    })
    .join("");
  $("cards").querySelectorAll(".ticket").forEach((el) => el.addEventListener("click", () => openCard(Number(el.dataset.i))));
  sparkAll();
}

async function sparkAll() {
  const store = $("store").value;
  const pts = (await j(store ? `/api/sparks?store_id=${store}` : "/api/sparks")).points || [];
  const bag = {};
  pts.forEach((p) => {
    (bag[`${p.store_id}-${p.sku_id}`] ||= []).push(Number(p.units));
  });
  document.querySelectorAll(".spark").forEach((svg) => {
    const ys = (bag[`${svg.dataset.store}-${svg.dataset.sku}`] || []).slice(-21);
    if (!ys.length) return;
    const min = Math.min(...ys);
    const max = Math.max(...ys);
    const d = ys
      .map((v, i) => {
        const x = (i / Math.max(ys.length - 1, 1)) * 120;
        const y = 24 - ((v - min) / Math.max(max - min, 0.01)) * 20;
        return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
    svg.innerHTML = `<path d="${d}" fill="none" stroke="#8a4b00" stroke-width="1.6"/>`;
  });
}

function paintHeat(cells) {
  const days = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
  const by = {};
  let peak = 1;
  cells.forEach((c) => {
    (by[c.sku] ||= { name: c.name, v: Array(7).fill(0) });
    by[c.sku].v[Number(c.dow)] = Number(c.units);
    peak = Math.max(peak, Number(c.units));
  });
  $("heat").innerHTML =
    `<div class="heat-row"><div></div>${days.map((d) => `<div class="heat-lab">${d}</div>`).join("")}</div>` +
    Object.keys(by)
      .slice(0, 12)
      .map((sku, ri) => {
        const row = by[sku];
        return `<div class="heat-row"><div class="heat-lab">${esc(sku)}</div>${row.v
          .map((v, ci) => `<div class="cell" style="background:rgba(255,176,32,${0.08 + (v / peak) * 0.9});animation-delay:${(ri * 7 + ci) * 0.012}s" title="${esc(row.name)} · ${v.toFixed(1)}"></div>`)
          .join("")}</div>`;
      })
      .join("");
}

function paintDrivers(items, id) {
  $(id).innerHTML = items
    .slice(0, 7)
    .map((d) => `<li><span>${esc(d.name)}</span><b>${(d.share * 100).toFixed(0)}%</b><div class="bar"><i data-w="${(d.share * 100).toFixed(1)}%"></i></div></li>`)
    .join("");
  requestAnimationFrame(() => {
    document.querySelectorAll(`#${id} .bar i`).forEach((el) => {
      el.style.width = el.dataset.w;
    });
  });
}

function paintCats(items) {
  const max = Math.max(...items.map((c) => Number(c.qty) || 0), 1);
  $("cats").innerHTML = items
    .map((c) => `<li><span>${esc(c.category)}</span><b>${Math.round(c.qty)}</b><div class="bar"><i data-w="${((Number(c.qty) / max) * 100).toFixed(1)}%"></i></div></li>`)
    .join("");
  requestAnimationFrame(() => {
    document.querySelectorAll("#cats .bar i").forEach((el) => {
      el.style.width = el.dataset.w;
    });
  });
}

function refreshMeta() {
  const r = state.board[state.selected];
  if (!r || !state.series) return;
  const qty = orderQty(r);
  $("thMeta").textContent = `${r.reason} · suggested ${qty} at p${Math.round(state.alpha * 100)}`;
  $("signQty").value = qty;
  const daily = floatSafe(r.need_p50) / 14;
  const cover = daily ? (r.on_hand / daily).toFixed(1) : "—";
  $("thExplain").textContent =
    `On hand ${Math.round(r.on_hand)} covers ~${cover} days at p50. ` +
    `The band is ${Math.round(r.need_p50)}–${Math.round(r.need_p90)} over 14 nights. ` +
    `Service p${Math.round(state.alpha * 100)} mixes those ends` +
    (state.shock > 1 ? ` then applies a ${Math.round((state.shock - 1) * 100)}% shock` : "") +
    `. Order is cover minus shelf, not a guess.`;
}

function floatSafe(v) {
  return Number(v) || 0;
}

function closeTheater() {
  state.theaterOpen = false;
  $("theater").hidden = true;
}

async function openCard(i) {
  if (!state.board[i]) return;
  state.selected = i;
  document.querySelectorAll(".ticket").forEach((el) => el.classList.toggle("on", Number(el.dataset.i) === i));
  const r = state.board[i];
  const data = await j(`/api/series?store_id=${r.store_id}&sku_id=${r.sku_id}`);
  state.series = data;
  const sisterId = state.stores.find((s) => s.id !== r.store_id)?.id;
  state.sister = [];
  if (sisterId) {
    try {
      const other = await j(`/api/series?store_id=${sisterId}&sku_id=${r.sku_id}`);
      state.sister = (other.history || []).slice(-56).map((p) => Number(p.units));
    } catch {
      state.sister = [];
    }
  }
  $("thKicker").textContent = `${data.store.name} · ${r.category}`;
  $("thTitle").textContent = data.sku.name;
  $("signNote").value = "";
  refreshMeta();
  $("theater").hidden = false;
  state.theaterOpen = true;
  requestAnimationFrame(() => drawWave(data.history, data.forecast));
}

function onWaveHover(ev) {
  if (!state.series) return;
  const rect = ev.currentTarget.getBoundingClientRect();
  state.hover = (ev.clientX - rect.left) / rect.width;
  drawWave(state.series.history, state.series.forecast);
}

function drawWave(history, forecast) {
  const canvas = $("wave");
  const { ctx, w, h } = fitCanvas(canvas, 168);
  const pad = 28;
  const hist = history.slice(-56);
  const vals = hist.map((p) => Number(p.units)).concat(forecast.flatMap((p) => [Number(p.p10), Number(p.p90), Number(p.p50)]));
  const min = Math.min(...vals, 0);
  const max = Math.max(...vals, 1);
  const n = hist.length + forecast.length;
  const x = (i) => pad + (i / Math.max(n - 1, 1)) * (w - pad * 2);
  const y = (v) => h - pad - ((v - min) / (max - min)) * (h - pad * 2);
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#0a0610";
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = "rgba(255,176,32,0.08)";
  for (let g = 0; g < 4; g++) {
    const yy = pad + g * ((h - pad * 2) / 3);
    ctx.beginPath();
    ctx.moveTo(pad, yy);
    ctx.lineTo(w - pad, yy);
    ctx.stroke();
  }
  if (forecast.length) {
    ctx.beginPath();
    forecast.forEach((p, i) => (i === 0 ? ctx.moveTo(x(hist.length + i), y(p.p90)) : ctx.lineTo(x(hist.length + i), y(p.p90))));
    for (let i = forecast.length - 1; i >= 0; i--) ctx.lineTo(x(hist.length + i), y(forecast[i].p10));
    ctx.closePath();
    ctx.fillStyle = "rgba(125,255,195,0.16)";
    ctx.fill();
  }
  const stroke = (arr, color, width, start) => {
    ctx.beginPath();
    arr.forEach((v, i) => (i === 0 ? ctx.moveTo(x(start + i), y(v)) : ctx.lineTo(x(start + i), y(v))));
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.stroke();
  };
  stroke(hist.map((p) => Number(p.units)), "#ffb020", 2, 0);
  if (state.sister.length) stroke(state.sister.slice(-hist.length), "#c9b89a", 1.2, 0);
  stroke(forecast.map((p) => Number(p.p50)), "#7dffc3", 2.2, hist.length);
  stroke(forecast.map((p) => Number(p.baseline)), "#6a5a70", 1.3, hist.length);
  if (hist.length) {
    ctx.strokeStyle = "rgba(244,231,200,0.2)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(x(hist.length - 1), pad);
    ctx.lineTo(x(hist.length - 1), h - pad);
    ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.fillStyle = "#c9b89a";
  ctx.font = "11px IBM Plex Mono, monospace";
  ctx.fillText(max.toFixed(0), 6, pad + 4);
  ctx.fillText(min.toFixed(0), 6, h - pad);
  if (state.hover != null && n > 1) {
    const idx = Math.round(state.hover * (n - 1));
    const px = x(idx);
    ctx.strokeStyle = "rgba(244,231,200,0.35)";
    ctx.beginPath();
    ctx.moveTo(px, pad);
    ctx.lineTo(px, h - pad);
    ctx.stroke();
    let label = "";
    if (idx < hist.length) label = `${hist[idx].day}  actual ${Number(hist[idx].units).toFixed(1)}`;
    else {
      const f = forecast[idx - hist.length];
      if (f) label = `${f.day}  p50 ${Number(f.p50).toFixed(1)}  [${Number(f.p10).toFixed(0)}–${Number(f.p90).toFixed(0)}]`;
    }
    if (label) {
      ctx.fillStyle = "#f4e7c8";
      ctx.fillText(label, Math.min(px + 8, w - 280), 16);
    }
  }
}

async function decide(action) {
  const r = state.board[state.selected];
  if (!r) return;
  const qty = Number($("signQty").value || orderQty(r));
  const note = $("signNote").value.trim();
  await j("/api/decide", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rec_id: r.id, action: action === "accept" && qty !== orderQty(r) ? "edit" : action, qty, note }),
  });
  toast(action === "dismiss" ? "skipped" : "signed");
  const pulse = await j("/api/pulse");
  state.pulse = pulse;
  paintMeters(pulse);
  paintHarbors(pulse.nodes || []);
  paintCats(pulse.categories || []);
  paintAlerts((await j("/api/alerts")).items || []);
  state.intel = await j("/api/intel");
  paintIntel(state.intel);
  $("status").textContent = `${pulse.open_recs} unsigned tickets`;
  await reloadBoard();
  closeTheater();
}

function paintIntel(intel) {
  const transfers = intel.transfers || [];
  const anomalies = intel.anomalies || [];
  $("intel").innerHTML = `
    <article>
      <h3>Transfer radar</h3>
      ${
        transfers
          .map(
            (t, i) => `<li>${esc(t.sku)} · ${esc(t.from_store)} → ${esc(t.to_store)} · ${t.qty}
              <button class="go xfer" data-i="${i}" type="button">Move</button></li>`
          )
          .join("") || "<p class='hint'>No imbalance fat enough to move.</p>"
      }
    </article>
    <article>
      <h3>Demand shocks</h3>
      ${
        anomalies
          .slice(0, 6)
          .map(
            (a) => `<li>${esc(a.kind)} · ${esc(a.sku)} @ ${esc(a.store)} · ${(a.ratio * 100).toFixed(0)}% of 28d</li>`
          )
          .join("") || "<p class='hint'>Last week sits on the 28-day mean.</p>"
      }
    </article>`;
  $("intel").querySelectorAll(".xfer").forEach((btn) =>
    btn.addEventListener("click", () => runTransfer(transfers[Number(btn.dataset.i)]))
  );
}

async function runTransfer(t) {
  if (!t) return;
  await j("/api/transfer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sku_id: t.sku_id,
      from_store_id: t.from_store_id,
      to_store_id: t.to_store_id,
      qty: t.qty,
    }),
  });
  toast(`moved ${t.qty} ${t.sku}`);
  state.intel = await j("/api/intel");
  paintIntel(state.intel);
  await reloadBoard();
}

async function openPack() {
  const data = await j(`/api/pack?alpha=${state.alpha}&shock=${state.shock}`);
  $("packMeta").textContent = `${data.lines.length} lines · ${data.units} units · cost ${Math.round(data.cost).toLocaleString()}`;
  $("packCsv").href = `/api/export/pack.csv?alpha=${state.alpha}&shock=${state.shock}`;
  $("packLines").innerHTML = (data.by_sku || [])
    .map((l) => `<li>${esc(l.sku)} · ${l.qty} · ${esc(l.stores.join(", "))}</li>`)
    .join("") || "<li>Nothing left to buy.</li>";
  $("packBox").hidden = false;
}

function palItems() {
  const q = ($("palQ").value || "").toLowerCase();
  const acts = [
    { act: "page", arg: "command", label: "Go to Command" },
    { act: "page", arg: "ledger", label: "Go to Ledger" },
    { act: "page", arg: "catalog", label: "Go to Catalog" },
    { act: "page", arg: "stock", label: "Go to Stock" },
    { act: "page", arg: "lab", label: "Go to Lab" },
    { act: "page", arg: "tape", label: "Go to Tape" },
    { act: "pack", arg: "", label: "Open buyer pack" },
    ...state.board.map((r, i) => ({ act: "ticket", arg: String(i), label: `Open ${r.name} @ ${r.store}` })),
    ...state.intel.transfers.map((t, i) => ({
      act: "xfer",
      arg: String(i),
      label: `Transfer ${t.qty} ${t.sku} ${t.from_store} → ${t.to_store}`,
    })),
  ];
  return acts.filter((a) => a.label.toLowerCase().includes(q)).slice(0, 12);
}

function paintPalette() {
  $("palList").innerHTML = palItems()
    .map((a, i) => `<li class="${i === 0 ? "on" : ""}" data-act="${a.act}" data-arg="${esc(a.arg)}">${esc(a.label)}</li>`)
    .join("");
}

function runPal(act, arg) {
  $("palette").hidden = true;
  if (act === "page") location.hash = `#/${arg}`;
  if (act === "pack") openPack();
  if (act === "ticket") openCard(Number(arg));
  if (act === "xfer") runTransfer(state.intel.transfers[Number(arg)]);
}

function onKey(e) {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    $("palette").hidden = !$("palette").hidden;
    if (!$("palette").hidden) {
      $("palQ").value = "";
      paintPalette();
      $("palQ").focus();
    }
    return;
  }
  if (e.key === "Escape") {
    if (!$("palette").hidden) {
      $("palette").hidden = true;
      return;
    }
    if (!$("packBox").hidden) {
      $("packBox").hidden = true;
      return;
    }
    if (state.theaterOpen) closeTheater();
    return;
  }
  if (e.target === $("palQ") && e.key === "Enter") {
    const first = palItems()[0];
    if (first) runPal(first.act, first.arg);
    return;
  }
  if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  if (document.body.dataset.page !== "command" || !state.theaterOpen) return;
  if (e.key === "ArrowRight") openCard(Math.min(state.board.length - 1, state.selected + 1));
  if (e.key === "ArrowLeft") openCard(Math.max(0, state.selected - 1));
  if (e.key === "Enter") decide("accept");
  if (e.key.toLowerCase() === "x") decide("dismiss");
}

function ledQuery() {
  const p = new URLSearchParams();
  if ($("ledStore").value) p.set("store_id", $("ledStore").value);
  if ($("ledSku").value) p.set("sku_id", $("ledSku").value);
  if ($("ledFrom").value) p.set("day_from", $("ledFrom").value);
  if ($("ledTo").value) p.set("day_to", $("ledTo").value);
  if ($("ledQ").value.trim()) p.set("q", $("ledQ").value.trim());
  if ($("ledPromo").checked) p.set("promo", "1");
  p.set("limit", "40");
  p.set("offset", String(state.ledOffset));
  return p;
}

async function loadLedger() {
  const p = ledQuery();
  const data = await j(`/api/observations?${p}`);
  $("ledMeta").textContent = `${data.total.toLocaleString()} nights · showing ${data.offset + 1}–${Math.min(data.offset + data.items.length, data.total)}`;
  $("ledExport").href = `/api/export/observations.csv?${new URLSearchParams([...p.entries()].filter(([k]) => !["limit", "offset"].includes(k)))}`;
  $("ledBody").innerHTML = data.items
    .map(
      (r) => `<tr>
        <td>${esc(r.day)}</td><td>${esc(r.store)}</td><td>${esc(r.sku)}</td>
        <td><input data-k="units" data-store="${r.store_id}" data-sku="${r.sku_id}" data-day="${r.day}" value="${r.units}" /></td>
        <td><input data-k="on_hand" data-store="${r.store_id}" data-sku="${r.sku_id}" data-day="${r.day}" value="${r.on_hand}" /></td>
        <td>${r.promo ? "yes" : "no"}</td>
        <td><button class="ghost save-row" type="button" data-promo="${r.promo}">Save</button></td>
      </tr>`
    )
    .join("");
  $("ledBody").querySelectorAll(".save-row").forEach((btn) => btn.addEventListener("click", saveRow));
}

async function saveRow(e) {
  const tr = e.target.closest("tr");
  const inputs = [...tr.querySelectorAll("input")];
  const base = inputs[0].dataset;
  const units = Number(tr.querySelector('[data-k="units"]').value);
  const on_hand = Number(tr.querySelector('[data-k="on_hand"]').value);
  await j("/api/observations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      store_id: Number(base.store),
      sku_id: Number(base.sku),
      day: base.day,
      units,
      on_hand,
      promo: Number(e.target.dataset.promo || 0),
    }),
  });
  toast("night saved");
}

async function saveNight(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  await j("/api/observations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      store_id: Number(fd.get("store_id")),
      sku_id: Number(fd.get("sku_id")),
      day: fd.get("day"),
      units: Number(fd.get("units")),
      on_hand: Number(fd.get("on_hand")),
      promo: e.target.promo.checked ? 1 : 0,
    }),
  });
  toast("night written");
  e.target.reset();
  loadLedger();
}

async function importCsv(e) {
  e.preventDefault();
  const file = e.target.file.files[0];
  if (!file) return;
  const body = new FormData();
  body.append("file", file);
  const res = await fetch("/api/import/observations", { method: "POST", body });
  const data = await res.json();
  if (!res.ok) return toast(data.detail || "import failed");
  toast(`imported ${data.rows} rows`);
  e.target.reset();
  loadLedger();
}

async function loadCatalog() {
  await loadRefs();
  $("catBody").innerHTML = state.skus
    .map(
      (s) => `<tr>
        <td>${esc(s.sku)}</td>
        <td><input data-id="${s.id}" data-k="name" value="${esc(s.name)}" /></td>
        <td><input data-id="${s.id}" data-k="category" value="${esc(s.category)}" /></td>
        <td><input data-id="${s.id}" data-k="unit_cost" type="number" value="${s.unit_cost}" /></td>
        <td><input data-id="${s.id}" data-k="lead_days" type="number" value="${s.lead_days}" /></td>
        <td><button class="ghost cat-save" data-id="${s.id}" type="button">Save</button></td>
      </tr>`
    )
    .join("");
  $("catBody").querySelectorAll(".cat-save").forEach((btn) => btn.addEventListener("click", saveSku));
  $("catStores").innerHTML = state.stores.map((s) => `<li>${esc(s.name)} · ${esc(s.city)}</li>`).join("");
}

async function saveSku(e) {
  const id = e.target.dataset.id;
  const tr = e.target.closest("tr");
  const body = {};
  tr.querySelectorAll("input").forEach((inp) => {
    body[inp.dataset.k] = inp.dataset.k === "name" || inp.dataset.k === "category" ? inp.value : Number(inp.value);
  });
  await j(`/api/skus/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  toast("sku updated");
}

async function addSku(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  await j("/api/skus", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      sku: fd.get("sku"),
      name: fd.get("name"),
      category: fd.get("category"),
      unit_cost: Number(fd.get("unit_cost")),
      lead_days: Number(fd.get("lead_days") || 3),
    }),
  });
  toast("sku added");
  e.target.reset();
  loadCatalog();
}

async function addStore(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  await j("/api/stores", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: fd.get("name"), city: fd.get("city") }),
  });
  toast("node opened");
  e.target.reset();
  loadCatalog();
}

async function loadStock() {
  await loadRefs();
  const data = await j("/api/stock");
  const value = data.items.reduce((s, r) => s + Number(r.value || 0), 0);
  $("stkValue").textContent = `shelf value ${value.toLocaleString(undefined, { maximumFractionDigits: 0 })} PKR-units`;
  $("stkBody").innerHTML = data.items
    .map(
      (r) => `<tr>
        <td>${esc(r.store)}</td><td>${esc(r.sku)} · ${esc(r.name)}</td>
        <td>${Math.round(r.on_hand)}</td><td>${Math.round(r.value)}</td>
        <td>${r.need_p90 != null ? Number(r.need_p90).toFixed(0) : "—"}</td>
        <td>${(r.risk * 100).toFixed(0)}%</td><td>${esc(r.day)}</td>
      </tr>`
    )
    .join("");
  const moves = await j("/api/stock/moves");
  $("stkMoves").innerHTML =
    moves.items.map((m) => `<li>${esc(m.reason)} · ${m.qty} · ${esc(m.sku)} · ${esc(m.store)}</li>`).join("") ||
    "<li>No moves yet.</li>";
}

async function moveStock(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const res = await j("/api/stock", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      store_id: Number(fd.get("store_id")),
      sku_id: Number(fd.get("sku_id")),
      qty: Number(fd.get("qty")),
      reason: fd.get("reason"),
    }),
  });
  toast(`on hand now ${Math.round(res.on_hand)}`);
  e.target.reset();
  loadStock();
}

async function loadLab() {
  await loadRefs();
  const [pulse, evals, drivers] = await Promise.all([j("/api/pulse"), j("/api/eval"), j("/api/drivers")]);
  const m = pulse.metrics || {};
  $("labMeters").innerHTML = [
    ["Model MAE", fmt(m.mae_model)],
    ["Naive MAE", fmt(m.mae_baseline)],
    ["MAPE", m.mape_model != null ? `${(m.mape_model * 100).toFixed(1)}%` : "—"],
    ["Coverage", m.coverage_p10_p90 != null ? `${(m.coverage_p10_p90 * 100).toFixed(0)}%` : "—"],
  ]
    .map(([k, v]) => `<div class="meter"><span>${k}</span><b>${v}</b></div>`)
    .join("");
  $("labEval").innerHTML =
    evals.items
      .map((e) => `<li>${esc(e.created_at)} · n=${e.n_points} · MAE ${Number(e.mae_model).toFixed(2)} vs ${Number(e.mae_baseline).toFixed(2)}</li>`)
      .join("") || "<li>Run pulsedesk train to stamp an eval.</li>";
  paintDrivers(drivers.items || [], "labDrivers");
}

async function runWhat(e) {
  e.preventDefault();
  const on = $("labOn").value;
  const data = await j("/api/whatif", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      store_id: Number($("labStore").value),
      sku_id: Number($("labSku").value),
      alpha: Number($("labAlpha").value) / 100,
      on_hand: on === "" ? null : Number(on),
    }),
  });
  $("labOut").innerHTML = `${esc(data.name)} @ ${esc(data.store)}<br>order <b>${data.suggested_qty}</b> · risk ${(data.risk * 100).toFixed(0)}% · on hand ${Math.round(data.on_hand)}<br>band ${Number(data.need_p50).toFixed(0)}–${Number(data.need_p90).toFixed(0)}`;
}

async function loadTape() {
  const [dec, audit] = await Promise.all([j("/api/decisions?limit=80"), j("/api/audit")]);
  $("tapeBody").innerHTML = dec.items
    .map(
      (d) => `<tr>
        <td>${esc(d.created_at)}</td><td>${esc(d.action)}</td>
        <td>${esc(d.sku)} · ${esc(d.sku_name)}</td><td>${esc(d.store)}</td>
        <td>${d.qty ?? "—"}</td>
        <td><input data-id="${d.id}" value="${esc(d.note || "")}" /></td>
        <td><button class="ghost note-save" data-id="${d.id}" type="button">Note</button></td>
      </tr>`
    )
    .join("");
  $("tapeBody").querySelectorAll(".note-save").forEach((btn) =>
    btn.addEventListener("click", async (e) => {
      const id = e.target.dataset.id;
      const note = e.target.closest("tr").querySelector("input").value;
      await j(`/api/decisions/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note }),
      });
      toast("note saved");
    })
  );
  $("auditBody").innerHTML =
    audit.items.map((a) => `<li>${esc(a.kind)} · ${esc(a.detail)} · ${esc(a.created_at)}</li>`).join("") ||
    "<li>Empty tape.</li>";
}

boot();
