"use strict";

const REPO = "https://github.com/b0gdaan/artem_klevie_masini";
const NS = "http://www.w3.org/2000/svg";
const METRIC = {
  position: "povprečni položaj", ctr_adjusted: "CTR, prilagojen položaju", clicks: "kliki",
  domain_authority: "Domain Authority", ctr_raw: "neprilagojen CTR",
};
const STATUS = {
  "podprta": ["good", "✓"], "ni podprta": ["critical", "✕"], "neodločeno": ["warning", "?"],
  "prag dosežen (opisno)": ["good", "✓"], "prag ni dosežen (opisno)": ["critical", "✕"],
  "neodločeno – obdobje še traja": ["warning", "…"], "ni dovolj podatkov": ["neutral", "–"],
};
const GROUP = { technical: "tehnična", content: "vsebinska", local: "lokalna", accessibility: "dostopnost", control: "kontrolna" };
const CATEGORY = { technical: "Tehnične", content: "Vsebinske", accessibility: "Dostopnost" };
const ISSUE = {
  http_error: "Stran vrne napako HTTP", missing_viewport: "Manjka meta viewport",
  missing_canonical: "Manjka kanonična povezava", noindex: "Stran ima noindex",
  broken_internal_link: "Pokvarjena notranja povezava", missing_title: "Manjka naslov (title)",
  title_too_short: "Prekratek naslov", title_too_long: "Predolg naslov (nad 60 znakov)",
  duplicate_title: "Podvojen naslov", missing_meta_description: "Manjka meta opis",
  meta_description_too_long: "Predolg meta opis", duplicate_meta_description: "Podvojen meta opis",
  missing_h1: "Manjka H1", multiple_h1: "Več naslovov H1", missing_structured_data: "Ni strukturiranih podatkov",
  invalid_structured_data: "Neveljavni strukturirani podatki", img_missing_alt: "Slika brez atributa alt",
  missing_lang: "Manjka atribut lang", heading_level_skip: "Preskok ravni naslovov",
  input_missing_label: "Polje obrazca brez oznake", empty_link_text: "Povezava brez besedila",
};

const $ = (selector) => document.querySelector(selector);
const decimal = (value, digits = 1) => value.toFixed(digits).replace(".", ",").replace("-", "−");
const pct = (value, digits = 1) => {
  if (value == null) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value * 100).toFixed(digits).replace(".", ",")} %`;
};

function node(tag, attrs = {}, children = []) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (key === "text") element.textContent = value;
    else element.setAttribute(key, value);
  }
  for (const child of [].concat(children)) if (child != null) element.append(child);
  return element;
}

function svg(tag, attrs, parent) {
  const element = document.createElementNS(NS, tag);
  for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, value);
  if (parent) parent.appendChild(element);
  return element;
}

function text(parent, x, y, content, attrs = {}) {
  const element = svg("text", { x, y, ...attrs }, parent);
  element.textContent = content;
  return element;
}

const scale = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);

function niceTicks(min, max, count) {
  const raw = (max - min || 1) / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw);
  const ticks = [];
  for (let v = Math.floor(min / step) * step; v <= max + step * 1e-9; v += step) ticks.push(+v.toFixed(10));
  if (ticks[ticks.length - 1] < max) ticks.push(+(ticks[ticks.length - 1] + step).toFixed(10));
  return ticks;
}

/* Tooltip ---------------------------------------------------------------- */
const tip = $("#tooltip");

function showTip(event, title, rows) {
  tip.replaceChildren(node("strong", { text: title }), ...rows.map((row) => {
    const line = node("div", { class: "row" });
    if (row.color) line.append(node("span", { class: "dot", style: `background:${row.color}` }));
    line.append(node("span", { text: row.text }));
    return line;
  }));
  tip.hidden = false;
  let x;
  let y;
  if (event.clientX !== undefined && event.type.startsWith("pointer")) {
    x = event.clientX;
    y = event.clientY;
  } else {
    const rect = (event.anchor || event.target).getBoundingClientRect();
    x = rect.left + rect.width / 2;
    y = rect.top + 8;
  }
  const width = tip.offsetWidth;
  const height = tip.offsetHeight;
  let left = x + 14;
  let top = y - height - 12;
  if (left + width > window.innerWidth - 8) left = x - width - 14;
  if (top < 8) top = y + 18;
  tip.style.left = `${Math.max(8, left)}px`;
  tip.style.top = `${top}px`;
}

const hideTip = () => { tip.hidden = true; };

function bindTip(target, title, rows) {
  target.addEventListener("pointermove", (event) => showTip(event, title, rows));
  target.addEventListener("pointerleave", hideTip);
  target.addEventListener("focus", (event) => showTip(event, title, rows));
  target.addEventListener("blur", hideTip);
}

function badge(decision) {
  const [kind, icon] = STATUS[decision] || ["neutral", "–"];
  return node("span", { class: `badge ${kind}` }, [node("i", { "aria-hidden": "true", text: icon }), decision]);
}

function fillTable(table, headers, rows) {
  const head = node("tr", {}, headers.map((h) => node("th", { class: h.num ? "num" : "", scope: "col", text: h.label })));
  table.tHead.replaceChildren(head);
  table.tBodies[0].replaceChildren(...rows.map((cells) => node("tr", {}, cells.map((cell, i) => {
    const td = node("td", { class: headers[i].num ? "num" : headers[i].cls || "" });
    if (cell instanceof Node) td.append(cell);
    else td.textContent = cell;
    return td;
  }))));
}

/* Header ----------------------------------------------------------------- */
function renderMeta(data, release) {
  $("#mode-label").textContent = `Način: ${data.mode_label}`;
  if (data.mode !== "synthetic") $("#mode-note").textContent = "Rezultati izhajajo iz shranjenega posnetka podatkov.";
  $("#meta-run").textContent = data.run_id;
  const commit = $("#meta-commit");
  if (/^[0-9a-f]{40}$/.test(data.code_commit)) {
    commit.replaceChildren(node("a", { href: `${REPO}/commit/${data.code_commit}`, text: data.code_commit.slice(0, 10) }));
  } else {
    commit.textContent = data.code_commit;
  }
  if (data.working_tree_dirty) commit.append(" (nepotrjene spremembe)");
  $("#meta-model").textContent = `${data.model_version}, bootstrap ${data.bootstrap_reps.toLocaleString("sl-SI")}`;
  $("#meta-period").textContent = `${data.data_period.start} – ${data.data_period.end}`;
  $("#meta-cutoff").textContent = `${data.analysis_cutoff} (končno do ${data.available_until})`;
  $("#meta-data-sha").textContent = data.data_sha256.slice(0, 16);
  if (release && release.tests) {
    const t = release.tests;
    $("#meta-tests").textContent = `${t.passed} uspešnih, ${t.failures + t.errors} neuspešnih, ${t.skipped} preskočenih`;
  }
}

/* Hypotheses ------------------------------------------------------------- */
function renderHypotheses(data) {
  const truth = data.truth || null;
  const headers = [{ label: "ID" }, { label: "Trditev", cls: "statement" }, { label: "Ocena", num: true },
    { label: "Bonferroni IZ", num: true }, { label: "Prag", num: true }, { label: "Odločitev" }];
  if (truth) headers.splice(3, 0, { label: "Vneseni učinek", num: true });
  const rows = data.hypotheses.map((h) => {
    const descriptive = h.kind === "descriptive";
    const estimate = h.estimate == null ? "—" : descriptive ? `${h.estimate > 0 ? "+" : ""}${decimal(h.estimate, 0)} točk` : pct(h.estimate);
    const interval = h.status === "estimated" ? `${pct(h.ci_low_adj)} … ${pct(h.ci_high_adj)}` : "—";
    const threshold = descriptive ? `${decimal(h.threshold, 0)} točk` : pct(h.threshold);
    const cells = [h.hypothesis_id, h.statement, estimate, interval, threshold, badge(h.decision)];
    if (truth) cells.splice(3, 0, truth[h.hypothesis_id] == null ? "—" : pct(truth[h.hypothesis_id]));
    return cells;
  });
  fillTable($("#hyp-table"), headers, rows);
}

function renderEffects(data) {
  const box = $("#effects-chart");
  box.replaceChildren();
  const rows = data.hypotheses.filter((h) => h.status === "estimated");
  if (!rows.length) return;
  const W = Math.max(box.clientWidth, 320);
  const narrow = W < 560;
  const m = { top: 8, right: 18, bottom: 34, left: narrow ? 44 : 200 };
  const rowHeight = 54;
  const H = m.top + m.bottom + rowHeight * rows.length;
  const values = rows.flatMap((r) => [r.ci_low_adj, r.ci_high_adj, r.threshold, 0]).map((v) => v * 100);
  const ticks = niceTicks(Math.min(...values), Math.max(...values), narrow ? 4 : 6);
  const x = scale(ticks[0] / 100, ticks[ticks.length - 1] / 100, m.left, W - m.right);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": "Ocenjeni učinki hipotez z intervali zaupanja in pragovi" }, box);
  for (const t of ticks) {
    const px = x(t / 100);
    svg("line", { x1: px, x2: px, y1: m.top, y2: H - m.bottom, class: t === 0 ? "axis" : "grid" }, root);
    text(root, px, H - m.bottom + 20, `${decimal(t, Number.isInteger(t) ? 0 : 1)} %`, { "text-anchor": "middle" });
  }
  rows.forEach((r, i) => {
    const y = m.top + rowHeight * i + rowHeight / 2;
    text(root, m.left - 12, y + 4, narrow ? r.hypothesis_id : `${r.hypothesis_id} · ${METRIC[r.metric]}`,
      { "text-anchor": "end", class: "label" });
    svg("line", { x1: x(r.ci_low), x2: x(r.ci_high), y1: y, y2: y, class: "ci-wide" }, root);
    svg("line", { x1: x(r.ci_low_adj), x2: x(r.ci_high_adj), y1: y, y2: y, class: "ci-adj" }, root);
    svg("line", { x1: x(r.threshold), x2: x(r.threshold), y1: y - 11, y2: y + 11, class: "threshold" }, root);
    svg("circle", { cx: x(r.estimate), cy: y, r: 5.5, class: "estimate" }, root);
    const hit = svg("rect", { x: 0, y: y - rowHeight / 2, width: W, height: rowHeight, class: "hit", tabindex: 0,
      "aria-label": `${r.hypothesis_id}: ocena ${pct(r.estimate)}, ${r.decision}` }, root);
    bindTip(hit, `${r.hypothesis_id} · ${METRIC[r.metric]}`, [
      { text: `Ocena: ${pct(r.estimate)}` },
      { text: `${Math.round(r.ci_level * 100)} % IZ: ${pct(r.ci_low)} … ${pct(r.ci_high)}` },
      { text: `Bonferroni ${decimal(r.ci_level_adj * 100, 2)} % IZ: ${pct(r.ci_low_adj)} … ${pct(r.ci_high_adj)}` },
      { text: `Prag: ${pct(r.threshold)} → ${r.decision}` },
      { text: `Strani: ${r.n_treated} obravnavanih, ${r.n_control} kontrolnih` },
    ]);
  });
}

/* Time series ------------------------------------------------------------ */
let selectedSeries = 0;

function seriesColors(item) {
  let treated = 0;
  return item.series.map((line) => line.role === "control" ? "var(--muted)"
    : (treated++ === 0 ? "var(--series-1)" : "var(--series-3)"));
}

function renderSeriesTabs(data) {
  const tabs = $("#series-tabs");
  tabs.replaceChildren(...data.series.map((item, i) => {
    const button = node("button", { type: "button", role: "tab", "aria-selected": String(i === selectedSeries),
      text: `${item.hypothesis_id} · ${item.metric_label}` });
    button.addEventListener("click", () => {
      selectedSeries = i;
      renderSeriesTabs(data);
      renderSeries(data);
      tabs.children[i].focus();
    });
    return button;
  }));
}

function renderSeries(data) {
  const item = data.series[selectedSeries];
  const box = $("#series-chart");
  box.replaceChildren();
  if (!item) return;
  const colors = seriesColors(item);
  $("#series-legend").replaceChildren(...item.series.map((line, i) =>
    node("span", { class: "chip" }, [node("i", { class: "swatch", style: `background:${colors[i]}` }), line.name])));

  const W = Math.max(box.clientWidth, 320);
  const narrow = W < 640;
  const m = { top: 22, right: narrow ? 16 : 190, bottom: 40, left: 46 };
  const H = narrow ? 280 : 340;
  const all = item.series.flatMap((l) => l.values).filter((v) => v != null);
  const ticks = niceTicks(Math.min(100, ...all), Math.max(100, ...all), 5);
  const weeks = item.weeks;
  const x = scale(weeks[0], weeks[weeks.length - 1], m.left, W - m.right);
  const y = scale(ticks[0], ticks[ticks.length - 1], H - m.bottom, m.top);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
    "aria-label": `${item.hypothesis_id}: tedenski indeks za obravnavane in kontrolne strani` }, box);

  svg("rect", { x: x(0), y: m.top, width: x(item.ramp_weeks) - x(0), height: H - m.top - m.bottom, class: "band" }, root);
  for (const t of ticks) {
    svg("line", { x1: m.left, x2: W - m.right, y1: y(t), y2: y(t), class: t === 100 ? "axis" : "grid" }, root);
    text(root, m.left - 8, y(t) + 4, decimal(t, 0), { "text-anchor": "end" });
  }
  for (const w of weeks.filter((w) => w % 2 === 0)) text(root, x(w), H - m.bottom + 18, String(w).replace("-", "−"), { "text-anchor": "middle" });
  text(root, (m.left + W - m.right) / 2, H - 6, "tedni glede na uvedbo", { "text-anchor": "middle" });
  svg("line", { x1: x(0), x2: x(0), y1: m.top - 6, y2: H - m.bottom, class: "event" }, root);
  text(root, x(0) + 6, m.top - 8, item.lower_is_better ? "uvedba · nižje = bolje" : "uvedba");

  const ends = [];
  item.series.forEach((line, i) => {
    let d = "";
    let pen = false;
    line.values.forEach((v, k) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${x(weeks[k]).toFixed(1)},${y(v).toFixed(1)}`;
      pen = true;
    });
    svg("path", { d, class: "line", stroke: colors[i] }, root);
    const last = line.values.map((v, k) => [v, k]).filter(([v]) => v != null).pop();
    if (last) ends.push({ name: line.name, color: colors[i], px: x(weeks[last[1]]), py: y(last[0]) });
  });
  if (!narrow) {
    ends.sort((a, b) => a.py - b.py);
    for (let i = 1; i < ends.length; i++) ends[i].py = Math.max(ends[i].py, ends[i - 1].py + 16);
    for (const end of ends) {
      svg("line", { x1: end.px + 6, x2: end.px + 16, y1: end.py, y2: end.py, stroke: end.color, "stroke-width": 2 }, root);
      text(root, end.px + 20, end.py + 4, end.name.replace("Obravnavane strani – ", ""));
    }
  }

  const cross = svg("g", { visibility: "hidden" }, root);
  const crossLine = svg("line", { y1: m.top, y2: H - m.bottom, class: "crosshair" }, cross);
  const markers = item.series.map((_, i) => svg("circle", { r: 4.5, fill: colors[i], class: "marker" }, cross));
  const overlay = svg("rect", { x: m.left, y: m.top, width: W - m.left - m.right, height: H - m.top - m.bottom,
    class: "hit", tabindex: 0, "aria-label": "Premikajte se po tednih s puščicama levo in desno" }, root);
  let focusWeek = 0;
  const show = (week, event) => {
    focusWeek = Math.min(Math.max(week, weeks[0]), weeks[weeks.length - 1]);
    const k = weeks.indexOf(focusWeek);
    crossLine.setAttribute("x1", x(focusWeek));
    crossLine.setAttribute("x2", x(focusWeek));
    item.series.forEach((line, i) => {
      const v = line.values[k];
      markers[i].setAttribute("visibility", v == null ? "hidden" : "visible");
      if (v != null) { markers[i].setAttribute("cx", x(focusWeek)); markers[i].setAttribute("cy", y(v)); }
    });
    cross.setAttribute("visibility", "visible");
    showTip(event, `Teden ${String(focusWeek).replace("-", "−")}`, item.series.map((line, i) => ({
      color: colors[i], text: `${line.name}: ${line.values[k] == null ? "—" : decimal(line.values[k], 1)}` })));
  };
  const hide = () => { cross.setAttribute("visibility", "hidden"); hideTip(); };
  overlay.addEventListener("pointermove", (event) => {
    const rect = root.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / rect.width) * W;
    const week = Math.round(weeks[0] + ((px - m.left) / (W - m.left - m.right)) * (weeks[weeks.length - 1] - weeks[0]));
    show(week, event);
  });
  overlay.addEventListener("pointerleave", hide);
  overlay.addEventListener("blur", hide);
  overlay.addEventListener("focus", () => show(focusWeek, { type: "focus", anchor: overlay }));
  overlay.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      event.preventDefault();
      show(focusWeek + (event.key === "ArrowLeft" ? -1 : 1), { type: "key", anchor: markers[0] });
    }
  });

  fillTable($("#series-table"), [{ label: "Teden", num: true }, ...item.series.map((l) => ({ label: l.name, num: true }))],
    weeks.map((w, k) => [String(w).replace("-", "−"), ...item.series.map((l) => l.values[k] == null ? "—" : decimal(l.values[k], 1))]));
}

/* Robustness tables ------------------------------------------------------ */
function renderRobustness(data) {
  fillTable($("#ablation-table"),
    [{ label: "ID" }, { label: "Model" }, { label: "Ocena", num: true }, { label: "95 % IZ", num: true }],
    data.ablation.map((r) => [r.hypothesis_id, r.model_label, pct(r.estimate), `${pct(r.ci_low)} … ${pct(r.ci_high)}`]));
  fillTable($("#placebo-table"),
    [{ label: "ID" }, { label: "Ocena", num: true }, { label: "95 % IZ", num: true }, { label: "IZ vsebuje 0" }],
    data.placebo.map((r) => [r.hypothesis_id, pct(r.estimate), `${pct(r.ci_low)} … ${pct(r.ci_high)}`,
      node("span", { class: `badge ${r.contains_zero ? "good" : "critical"}` },
        [node("i", { "aria-hidden": "true", text: r.contains_zero ? "✓" : "✕" }), r.contains_zero ? "da" : "ne"])]));
}

/* Audit ------------------------------------------------------------------ */
function barPath(x0, y, width, height, radius = 4) {
  const r = Math.min(radius, width / 2, height / 2);
  if (width <= 0) return "";
  return `M${x0},${y}H${x0 + width - r}Q${x0 + width},${y} ${x0 + width},${y + r}V${y + height - r}` +
    `Q${x0 + width},${y + height} ${x0 + width - r},${y + height}H${x0}Z`;
}

function renderAudit(data) {
  const box = $("#audit-chart");
  box.replaceChildren();
  const totals = Object.keys(CATEGORY).map((key) => {
    const rows = data.audit.filter((a) => a.category === key);
    return { key, before: rows.reduce((s, a) => s + a.before, 0), after: rows.reduce((s, a) => s + a.after, 0) };
  });
  const W = Math.max(box.clientWidth, 320);
  const m = { top: 4, right: 40, bottom: 30, left: 96 };
  const bar = 16;
  const group = bar * 2 + 2 + 20;
  const H = m.top + m.bottom + group * totals.length;
  const ticks = niceTicks(0, Math.max(...totals.map((t) => t.before), 1), 5);
  const x = scale(0, ticks[ticks.length - 1], m.left, W - m.right);
  const root = svg("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Število težav pred in po optimizaciji" }, box);
  for (const t of ticks) {
    svg("line", { x1: x(t), x2: x(t), y1: m.top, y2: H - m.bottom, class: t === 0 ? "axis" : "grid" }, root);
    text(root, x(t), H - m.bottom + 18, String(t), { "text-anchor": "middle" });
  }
  totals.forEach((t, i) => {
    const top = m.top + i * group + 10;
    text(root, m.left - 10, top + bar + 5, CATEGORY[t.key], { "text-anchor": "end", class: "label" });
    [["before", "var(--series-2)", "Pred optimizacijo"], ["after", "var(--series-1)", "Po optimizaciji"]].forEach(([field, color, label], j) => {
      const y = top + j * (bar + 2);
      const width = x(t[field]) - x(0);
      svg("path", { d: barPath(x(0), y, width, bar), fill: color }, root);
      text(root, x(0) + width + 6, y + bar - 3, String(t[field]));
      const hit = svg("rect", { x: m.left, y: y - 1, width: W - m.left - m.right, height: bar + 2, class: "hit", tabindex: 0,
        "aria-label": `${CATEGORY[t.key]}, ${label}: ${t[field]}` }, root);
      bindTip(hit, CATEGORY[t.key], [{ color, text: `${label}: ${t[field]} težav` }]);
    });
  });

  fillTable($("#audit-table"), [{ label: "Kategorija" }, { label: "Težava" }, { label: "Pred", num: true }, { label: "Po", num: true }],
    data.audit.map((a) => [CATEGORY[a.category] || a.category, ISSUE[a.issue] || a.issue, String(a.before), String(a.after)]));
  fillTable($("#lighthouse-table"),
    [{ label: "Skupina" }, { label: "Posnetek" }, { label: "Zmogljivost", num: true }, { label: "Dostopnost", num: true },
      { label: "SEO", num: true }, { label: "LCP (s)", num: true }, { label: "CLS", num: true }],
    data.lighthouse.map((r) => [GROUP[r.design_group] || r.design_group, r.snapshot === "before" ? "pred" : "po",
      decimal(r.performance, 0), decimal(r.accessibility, 0), decimal(r.seo, 0), decimal(r.lcp_ms / 1000, 2), decimal(r.cls, 3)]));
}

/* Boot ------------------------------------------------------------------- */
function renderCharts(data) {
  renderEffects(data);
  renderSeries(data);
  renderAudit(data);
}

async function main() {
  try {
    const response = await fetch("data/demo_public.json", { cache: "no-cache" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const release = await fetch("data/release.json", { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    renderMeta(data, release);
    renderHypotheses(data);
    renderSeriesTabs(data);
    renderRobustness(data);
    renderCharts(data);
    let timer;
    window.addEventListener("resize", () => {
      clearTimeout(timer);
      timer = setTimeout(() => renderCharts(data), 150);
    });
  } catch (error) {
    const box = $("#load-error");
    box.textContent = `Podatkov zagona ni bilo mogoče naložiti (${error.message}). Stran je treba zgraditi z ukazom release.`;
    box.hidden = false;
    $("#mode-label").textContent = "Podatki niso na voljo";
  }
}

main();
