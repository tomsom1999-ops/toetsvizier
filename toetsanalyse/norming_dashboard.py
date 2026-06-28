from __future__ import annotations

import html
import json


def build_norming_dashboard_html(data: dict[str, object], settings: dict[str, object], plotly_source: str) -> str:
    payload = json.dumps({"data": data, "settings": settings}, ensure_ascii=True).replace("<", "\\u003c")
    source = html.escape(plotly_source, quote=True)
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="{source}"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
:root {{
  --bg: #f7f8fc; --card: #ffffff; --border: #e4e8f1; --navy: #17243c;
  --muted: #66748e; --primary: #6256ea; --primary-soft: #f0edff;
  --green: #2da65a; --green-soft: #e9f8ee; --red: #e64141; --red-soft: #fdf0f0;
  --shadow: 0 2px 10px rgba(26, 38, 64, .045);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--navy);
  font-family: "Inter", "Segoe UI", Arial, sans-serif; font-size: 13px;
}}
.page {{ padding: 20px; }}
.toolbar {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:14px; }}
h1 {{ font-size:22px; margin:0; font-weight:700; letter-spacing:-.02em; }}
.subtitle {{ color:var(--muted); margin-top:4px; }}
.actions {{ display:flex; gap:8px; align-items:center; }}
button, select, input, textarea {{ font:inherit; }}
.ghost-button, .save-button {{
  border-radius:8px; height:38px; padding:0 16px; background:#fff;
  border:1px solid var(--border); color:var(--navy);
}}
.active-pill {{
  border-radius:8px; padding:10px 14px; background:#fff;
  border:1px solid var(--border); color:var(--muted);
}}
.save-button {{ background:var(--primary); color:white; border-color:var(--primary); cursor:pointer; }}
.save-button:hover {{ background:#5345dc; }}
.danger-button {{ color:var(--red); background:#fff; border-color:#f1d6d6; cursor:pointer; }}
.danger-button:hover {{ background:var(--red-soft); }}
.save-button:disabled, .danger-button:disabled {{
  opacity:.48; cursor:not-allowed;
}}
.save-button:disabled:hover {{ background:var(--primary); }}
.danger-button:disabled:hover {{ background:#fff; }}
.save-message {{ color:var(--green); font-weight:600; opacity:0; transition: opacity .25s; }}
.save-message.visible {{ opacity:1; }}
.layout {{ display:grid; grid-template-columns:274px minmax(0, 1fr); gap:14px; align-items:start; }}
.workspace {{ display:grid; gap:14px; min-width:0; }}
.analytics-grid {{ display:grid; grid-template-columns:minmax(470px, 1fr) 318px; gap:14px; align-items:start; }}
.card {{
  background:var(--card); border:1px solid var(--border); border-radius:12px;
  padding:14px; box-shadow:var(--shadow);
}}
.section-title {{ font-size:15px; font-weight:700; margin:0 0 12px; }}
.methods {{ display:flex; flex-direction:column; gap:8px; }}
.method {{
  display:flex; flex-direction:column; align-items:flex-start; width:100%;
  background:#fff; border:1px solid var(--border); border-radius:9px; padding:10px 12px;
  color:var(--navy); cursor:pointer; text-align:left;
}}
.method strong {{ font-size:13px; font-weight:600; }}
.method span {{ color:var(--muted); font-size:11px; margin-top:3px; }}
.method.active {{ border-color:#d9d2ff; background:var(--primary-soft); }}
.method.active strong, .method.active span {{ color:var(--primary); }}
.side-card {{ margin-bottom:12px; }}
.settings-row {{ margin:10px 0; }}
.settings-label {{ display:flex; justify-content:space-between; color:var(--muted); font-size:12px; margin-bottom:7px; }}
.settings-value {{
  color:var(--navy); padding:5px 9px; min-width:56px; text-align:right;
  border:1px solid var(--border); border-radius:7px; background:#fff;
}}
input[type=range] {{ width:100%; accent-color:var(--primary); }}
input[type=number], select, textarea {{
  width:100%; border:1px solid var(--border); background:#fff; border-radius:7px; padding:7px 9px; color:var(--navy);
}}
textarea {{ height:72px; resize:vertical; line-height:1.45; }}
.axis-labels {{ display:flex; justify-content:space-between; color:var(--muted); font-size:11px; margin-top:3px; }}
.pass-card {{
  text-align:center; margin-top:12px; padding:12px 8px; border-radius:9px;
  background:linear-gradient(135deg, #fbfffc, #eef9f2); border:1px solid #e0f1e6;
}}
.pass-card span {{ color:var(--muted); font-size:12px; }}
.pass-card strong {{ display:block; font-size:18px; margin-top:5px; }}
.kpis {{ display:grid; grid-template-columns:repeat(6, minmax(108px,1fr)); gap:8px; }}
.kpi {{ padding:12px; min-height:75px; }}
.kpi-label {{ color:var(--muted); font-size:11px; }}
.kpi-value {{ font-size:23px; font-weight:600; margin:5px 0 0; }}
.kpi-note {{ color:var(--muted); font-size:11px; }}
.kpi.red .kpi-value {{ color:var(--red); }}
.kpi.green .kpi-value {{ color:var(--green); }}
.right {{ display:flex; flex-direction:column; gap:10px; }}
.chart-title {{ display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:3px; }}
.chart-title h2 {{ font-size:15px; margin:0; }}
.chart-note {{ color:var(--muted); font-size:11px; }}
.chart-actions {{ display:flex; align-items:center; gap:8px; }}
.chart-control {{ display:flex; align-items:center; gap:6px; color:var(--muted); font-size:11px; }}
.histogram-controls {{
  display:flex; align-items:center; justify-content:flex-end; margin:8px 0 2px;
}}
.compact-select {{
  width:auto; min-width:92px; height:32px; padding:5px 8px; border-radius:7px;
}}
.expand-button {{
  height:32px; min-width:32px; padding:0 10px; border:1px solid var(--border);
  border-radius:8px; background:#fff; color:var(--muted); cursor:pointer;
}}
.expand-button:hover {{ color:var(--primary); border-color:#d7d0ff; background:var(--primary-soft); }}
#scatter {{ height:388px; width:100%; touch-action:pan-y; }}
#histogram {{ height:238px; width:100%; touch-action:pan-y; }}
#curve {{ height:188px; width:100%; touch-action:pan-y; }}
.summary-row {{ display:flex; justify-content:space-between; padding:4px 0; color:#35445d; }}
.summary-row span:first-child {{ color:var(--muted); }}
.curve-key {{ display:flex; justify-content:flex-end; gap:12px; color:var(--muted); font-size:11px; margin-top:-4px; }}
.line {{ display:inline-block; width:18px; border-top:2px solid var(--primary); margin-right:4px; vertical-align:middle; }}
.line.ref {{ border-color:#b9c6dd; border-top-style:dashed; }}
.table-card {{ padding:0; overflow:hidden; }}
.table-bar {{
  display:flex; justify-content:space-between; align-items:center; gap:14px; padding:13px 14px;
  border-bottom:1px solid var(--border);
}}
.table-bar h2 {{ font-size:15px; margin:0; }}
.table-tools {{ display:flex; justify-content:flex-end; align-items:center; gap:8px; flex-wrap:wrap; }}
.sort-select {{ width:190px; height:34px; padding:6px 10px; }}
.search {{ width:240px; height:34px; padding-left:12px; border:1px solid var(--border); border-radius:8px; }}
.export-button {{
  height:34px; border-radius:8px; border:1px solid var(--border); background:#fff;
  color:var(--navy); padding:0 12px; cursor:pointer;
}}
.export-button:hover {{ background:#f6f8fc; border-color:#d7deeb; }}
.table-wrap {{ max-height:258px; overflow:auto; }}
table {{ border-collapse:collapse; width:100%; }}
th {{ position:sticky; top:0; background:#fafbfe; z-index:1; text-align:left; color:var(--muted); font-weight:600; font-size:12px; }}
td, th {{ padding:9px 14px; border-bottom:1px solid #edf0f6; }}
td.number {{ font-variant-numeric:tabular-nums; }}
.sufficient {{ color:var(--green); }}
.insufficient {{ color:var(--red); }}
.badge {{
  display:inline-block; border-radius:6px; padding:3px 12px; font-size:12px;
  background:var(--green-soft); color:var(--green);
}}
.badge.bad {{ background:var(--red-soft); color:var(--red); }}
.pagination {{ display:flex; align-items:center; justify-content:center; gap:4px; padding:10px; }}
.page-btn {{ border:0; background:#fff; color:var(--muted); height:29px; min-width:29px; border-radius:6px; cursor:pointer; }}
.page-btn.active {{ background:var(--primary); color:#fff; }}
.empty {{
  height:300px; display:flex; align-items:center; justify-content:center; flex-direction:column;
  color:var(--muted); text-align:center;
}}
.offline {{ display:none; padding:12px; color:var(--red); background:var(--red-soft); border-radius:8px; margin:10px 0; }}
.chart-modal {{
  position:fixed; inset:0; z-index:20; display:none; align-items:center; justify-content:center;
  padding:34px; background:rgba(23,36,60,.38); backdrop-filter:blur(2px);
}}
.chart-modal.open {{ display:flex; }}
.chart-modal-card {{
  width:min(1120px, 96vw); height:min(760px, 92vh); display:flex; flex-direction:column;
  background:#fff; border:1px solid var(--border); border-radius:16px; box-shadow:0 20px 70px rgba(23,36,60,.18);
  padding:18px 20px 16px;
}}
.chart-modal-head {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }}
.chart-modal-head h2 {{ margin:0; font-size:19px; }}
.close-button {{
  border:1px solid var(--border); border-radius:8px; background:#fff; height:36px;
  padding:0 13px; color:var(--navy); cursor:pointer;
}}
.close-button:hover {{ background:#f5f7fb; }}
#expandedChart {{ flex:1; min-height:0; width:100%; touch-action:pan-y; }}
@media (max-width:1260px) {{
  .layout {{ grid-template-columns:260px minmax(0, 1fr); }}
  .kpis {{ grid-template-columns:repeat(3, 1fr); }}
  .analytics-grid {{ grid-template-columns:1fr; }}
  .right {{ display:grid; grid-template-columns:repeat(2, minmax(240px, 1fr)); gap:14px; }}
}}
@media (max-width:920px) {{
  .page {{ padding:12px; }}
  .layout {{ display:flex; flex-direction:column; }}
  .workspace, .analytics-grid, .center, .right, .table-card {{ width:100%; }}
  .kpis {{ grid-template-columns:repeat(2, 1fr); }}
  .right {{ display:flex; }}
  .toolbar {{ flex-wrap:wrap; gap:12px; }}
  .table-bar {{ align-items:flex-start; flex-direction:column; }}
  .table-tools {{ justify-content:flex-start; }}
}}
</style>
</head>
<body>
<div class="page">
  <header class="toolbar">
    <div>
      <h1 id="pageTitle">Normeren</h1>
      <div class="subtitle" id="context"></div>
    </div>
    <div class="actions">
      <span id="saveMessage" class="save-message">Opgeslagen</span>
      <button id="finalizeButton" class="save-button">Normering vaststellen</button>
      <button id="reopenButton" class="ghost-button danger-button">Vastgestelde normering opheffen</button>
      <span id="activeMethod" class="active-pill">Methode</span>
    </div>
  </header>
  <div id="plotlyUnavailable" class="offline">De grafieken konden niet worden geladen. Controleer de lokale Plotly-bibliotheek.</div>
  <main class="layout">
    <aside class="controls">
      <section class="card side-card">
        <h2 class="section-title">1. Normeringsmethode</h2>
        <div class="methods">
          <button class="method" data-method="fouten_per_punt"><strong>Fouten per punt</strong><span>Aftrek per fout</span></button>
          <button class="method" data-method="cvte_cesuur"><strong>CvTE-methode</strong><span>Via 5,5-score</span></button>
          <button class="method" data-method="n_term"><strong>N-term</strong><span>Officiele N-term</span></button>
          <button class="method" data-method="cesuur"><strong>Lineaire methode</strong><span>Vanaf voldoende naar 10,0</span></button>
          <button class="method" data-method="cesuur_knik"><strong>Lineaire methode met knik</strong><span>Twee lineaire delen</span></button>
          <button class="method" data-method="percentage_voldoende"><strong>% van de punten gescoord voor 5,5</strong><span>Grens op percentage</span></button>
        </div>
      </section>
      <section class="card side-card">
        <h2 id="settingsTitle" class="section-title">2. Instellingen</h2>
        <div id="methodSettings"></div>
        <div class="settings-row">
          <div class="settings-label"><span>Afronden op</span></div>
          <select id="rounding">
            <option value="standaard:0">Hele cijfers (standaard)</option>
            <option value="standaard:1">1 decimaal</option>
            <option value="standaard:2">2 decimalen</option>
            <option value="halve cijfers:1">Halve cijfers</option>
            <option value="hele cijfers:0">Hele cijfers</option>
            <option value="naar boven:1">Naar boven (1 decimaal)</option>
            <option value="naar beneden:1">Naar beneden (1 decimaal)</option>
          </select>
        </div>
        <div class="pass-card">
          <span>Voldoende (5,5) vanaf</span>
          <strong id="passCardValue">-</strong>
        </div>
      </section>
      <section class="card">
        <div class="chart-title">
          <h2 class="section-title" style="margin-bottom:0">3. Normeringscurve</h2>
          <button class="expand-button" data-expand="curve" title="Vergrote weergave">Vergroot</button>
        </div>
        <div id="curve"></div>
        <div class="curve-key"><span><i class="line"></i>Huidig</span><span><i class="line ref"></i>Lineair</span></div>
      </section>
    </aside>
    <div class="workspace">
      <section class="kpis" id="kpis"></section>
      <div class="analytics-grid">
        <section class="card center">
          <div class="chart-title">
            <h2>4. Cijferverdeling (per leerling)</h2>
            <div class="chart-actions"><span class="chart-note">Hover over een punt voor details</span><button class="expand-button" data-expand="scatter" title="Vergrote weergave">Vergroot</button></div>
          </div>
          <div id="scatter"></div>
        </section>
        <aside class="right">
          <section class="card">
            <div class="chart-title">
              <h2>5. Scoreverdeling</h2>
              <button class="expand-button" data-expand="histogram" title="Vergrote weergave">Vergroot</button>
            </div>
            <div class="histogram-controls">
              <label class="chart-control">Balkbreedte
                <select id="histogramBinSize" class="compact-select">
                  <option value="1">1 punt</option>
                  <option value="2">2 punten</option>
                  <option value="3">3 punten</option>
                  <option value="4" selected>4 punten</option>
                </select>
              </label>
            </div>
            <div id="histogram"></div>
          </section>
          <section class="card summary">
            <h2 class="section-title">Samenvatting</h2>
            <div id="summaryRows"></div>
          </section>
        </aside>
      </div>
      <section class="card table-card">
        <div class="table-bar">
          <h2 id="tableTitle">6. Overzicht deelnemers</h2>
          <div class="table-tools">
            <select id="participantSort" class="sort-select" aria-label="Sorteren">
              <option value="alphabetical">Alfabetisch (achternaam)</option>
              <option value="score_desc">Score hoog naar laag</option>
              <option value="score_asc">Score laag naar hoog</option>
            </select>
            <input id="search" class="search" placeholder="Zoek deelnemer...">
            <button id="exportExcel" class="export-button">Excel exporteren</button>
            <button id="exportPdf" class="export-button">PDF exporteren</button>
          </div>
        </div>
        <div class="table-wrap">
          <table><thead><tr><th>#</th><th>Deelnemer</th><th>Score (punten)</th><th>% van de punten gescoord</th><th>Cijfer</th><th>Status</th></tr></thead><tbody id="participantRows"></tbody></table>
        </div>
        <div id="pagination" class="pagination"></div>
      </section>
    </div>
  </main>
  <div id="chartModal" class="chart-modal" aria-hidden="true" inert>
    <section class="chart-modal-card" role="dialog" aria-modal="true" aria-labelledby="expandedTitle">
      <header class="chart-modal-head">
        <h2 id="expandedTitle">Vergrote grafiek</h2>
        <button id="closeExpandedChart" class="close-button">Sluiten</button>
      </header>
      <div id="expandedChart"></div>
    </section>
  </div>
</div>
<script>
const payload = {payload};
const data = payload.data;
const maximum = Number(data.maximum_score || 0);
const state = Object.assign({{}}, payload.settings);
state.method = state.method || "n_term";
state.rounding_method = state.rounding_method || "standaard";
let finalized = Boolean(data.is_finalized);
let bridge = null;
let page = 1;
const pageSize = 8;
let histogramBinSize = 4;
const colors = {{ purple:"#6256ea", green:"#36ab61", red:"#e34646", grid:"#e6eaf2", slate:"#65728b" }};
const chartConfig = {{displayModeBar:false, responsive:true, scrollZoom:false, doubleClick:false}};
const chartDefinitions = {{}};
let expandedChartName = null;
let expandedChartTrigger = null;

if (window.qt && window.QWebChannel) {{
  new QWebChannel(qt.webChannelTransport, channel => {{ bridge = channel.objects.normingBridge; }});
}}
function format(value, decimals=1) {{ return Number(value).toFixed(decimals).replace(".", ","); }}
function clamp(value) {{ return Math.max(1, Math.min(10, value)); }}
function rawGrade(score) {{
  if (!maximum) return 1;
  let pass = Math.max(.1, Math.min(maximum, Number(state.pass_score || maximum * .55)));
  if (state.method === "percentage_voldoende") pass = maximum * Number(state.pass_percentage || 55) / 100;
  let grade = 1;
  if (state.method === "fouten_per_punt") grade = 10 - (maximum - score) * Number(state.deduction || .25);
  if (state.method === "cvte_cesuur" || state.method === "n_term") {{
    const nTerm = state.method === "cvte_cesuur" ? 5.45 - (9 * pass / maximum) : Number(state.n_term === undefined ? 1 : state.n_term);
    const main = 9 * score / maximum + nTerm;
    if (nTerm > 1) {{
      grade = Math.min(main, 1 + score * (9 / maximum) * 2, 10 - (maximum - score) * (9 / maximum) * .5);
    }} else if (nTerm < 1) {{
      grade = Math.max(main, 1 + score * (9 / maximum) * .5, 10 - (maximum - score) * (9 / maximum) * 2);
    }} else {{
      grade = main;
    }}
  }}
  if (state.method === "cesuur") grade = 10 - (maximum - score) * (4.5 / Math.max(.1, maximum - pass));
  if (state.method === "cesuur_knik") grade = score <= pass ? 1 + 4.5 * score / pass : 5.5 + 4.5 * (score-pass) / Math.max(.1, maximum-pass);
  if (state.method === "percentage_voldoende") grade = score <= pass ? 1 + 4.5 * score / pass : 5.5 + 4.5 * (score-pass) / Math.max(.1, maximum-pass);
  return clamp(grade);
}}
function grade(score) {{
  const raw = rawGrade(score);
  if (state.rounding_method === "halve cijfers") return Math.round(raw * 2) / 2;
  if (state.rounding_method === "hele cijfers") return Math.round(raw);
  const factor = Math.pow(10, Number(state.decimal_places === undefined ? 1 : state.decimal_places));
  if (state.rounding_method === "naar boven") return Math.ceil(raw * factor) / factor;
  if (state.rounding_method === "naar beneden") return Math.floor(raw * factor) / factor;
  return Math.round((raw + Number.EPSILON) * factor) / factor;
}}
function gradeDecimals() {{
  if (state.rounding_method === "hele cijfers") return 0;
  if (state.rounding_method === "halve cijfers") return 1;
  return Number(state.decimal_places === undefined ? 1 : state.decimal_places);
}}
function displayGrade(value) {{ return format(value, gradeDecimals()); }}
function passScore() {{
  for (let value=0; value <= maximum + .001; value += .5) if (grade(value) >= 5.5) return value;
  return null;
}}
function calculated() {{
  return data.participants.map((participant, index) => {{
    const cijfer = grade(participant.score);
    return Object.assign({{}}, participant, {{index:index+1, grade:cijfer, percentage: maximum ? participant.score/maximum*100 : 0, sufficient:cijfer >= 5.5}});
  }});
}}
function mean(values) {{ return values.length ? values.reduce((a,b)=>a+b,0)/values.length : 0; }}
function median(values) {{
  if (!values.length) return 0;
  const sorted = [...values].sort((a,b)=>a-b); const middle = Math.floor(sorted.length/2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle-1]+sorted[middle])/2;
}}
function sd(values) {{
  if (values.length < 2) return 0;
  const avg = mean(values); return Math.sqrt(values.reduce((value,current)=>value + Math.pow(current-avg, 2),0)/(values.length-1));
}}
function methodName() {{
  return {{fouten_per_punt:"Fouten per punt", cvte_cesuur:"CvTE-methode", n_term:"N-term", cesuur:"Lineaire methode", cesuur_knik:"Lineaire methode met knik", percentage_voldoende:"% van de punten gescoord voor 5,5"}}[state.method];
}}
function setLockState() {{
  document.querySelectorAll(".method, #methodSettings input, #methodSettings textarea, #methodSettings select, #rounding").forEach(control => {{
    control.disabled = finalized;
  }});
  document.getElementById("finalizeButton").disabled = finalized;
  document.getElementById("reopenButton").disabled = !finalized;
  document.getElementById("activeMethod").textContent =
    (finalized ? "Vastgesteld: " : "Concept: ") + methodName();
}}
function renderMethodControls() {{
  document.querySelectorAll(".method").forEach(button => button.classList.toggle("active", button.dataset.method === state.method));
  document.getElementById("settingsTitle").textContent = "2. Instellingen - " + methodName();
  let html = "";
  if (state.method === "n_term") html = `<div class="settings-row"><div class="settings-label"><span>N-term</span><strong class="settings-value" id="nLabel">${{format(state.n_term,1)}}</strong></div><input id="nTerm" type="range" min="0" max="4" step="0.1" value="${{state.n_term}}"><div class="axis-labels"><span>0,0</span><span>1,0</span><span>2,0 regulier</span><span>4,0</span></div><div class="chart-note" style="margin-top:9px">Officiele CE-berekening met grensrelaties en afronding op 1 decimaal. Boven 2,0 is alleen uitzonderlijk gebruik.</div></div>`;
  if (state.method === "fouten_per_punt") html = `<div class="settings-row"><div class="settings-label"><span>Aftrek per gemist punt</span></div><input id="deduction" type="number" min="0.05" max="2" step="0.05" value="${{state.deduction}}"></div>`;
  if (state.method === "cvte_cesuur") html = `<div class="settings-row"><div class="settings-label"><span>Aantal punten voor een 5,5</span></div><input id="passInput" type="number" min="${{maximum/4}}" max="${{maximum*3/4}}" step="0.1" value="${{state.pass_score}}"><div class="chart-note" style="margin-top:9px">Cito/CvTE-methode. De 5,5-score ligt tussen 25% en 75%; afronding is officieel op 1 decimaal.</div></div>`;
  if (state.method === "cesuur" || state.method === "cesuur_knik") html = `<div class="settings-row"><div class="settings-label"><span>Aantal punten voor een 5,5</span></div><input id="passInput" type="number" min="0.5" max="${{maximum}}" step="0.5" value="${{state.pass_score}}"><div class="chart-note" style="margin-top:9px">De kaart hieronder toont de feitelijke voldoendegrens na afronding.</div></div>`;
  if (state.method === "percentage_voldoende") html = `<div class="settings-row"><div class="settings-label"><span>% van de punten gescoord gelijk aan 5,5</span><strong class="settings-value" id="percentageLabel">${{format(state.pass_percentage || 55,1)}}%</strong></div><input id="percentageInput" type="range" min="1" max="99" step="0.5" value="${{state.pass_percentage || 55}}"><div class="axis-labels"><span>1%</span><span>50%</span><span>99%</span></div><div class="chart-note" style="margin-top:9px">Gebaseerd op de lineaire methode met knik: 0% = 1,0 en 100% = 10,0.</div></div>`;
  html += `<div class="settings-row"><div class="settings-label"><span>Maximum score</span><strong class="settings-value">${{format(maximum, maximum % 1 ? 1 : 0)}}</strong></div></div>`;
  document.getElementById("methodSettings").innerHTML = html;
  const nTerm = document.getElementById("nTerm");
  if (nTerm) nTerm.addEventListener("input", event => {{ state.n_term = Number(event.target.value); document.getElementById("nLabel").textContent = format(state.n_term,1); renderAll(); }});
  const deduction = document.getElementById("deduction");
  if (deduction) deduction.addEventListener("input", event => {{ state.deduction = Number(event.target.value); renderAll(); }});
  const passInput = document.getElementById("passInput");
  if (passInput) passInput.addEventListener("input", event => {{ state.pass_score = Number(event.target.value); renderAll(); }});
  const percentageInput = document.getElementById("percentageInput");
  if (percentageInput) percentageInput.addEventListener("input", event => {{ state.pass_percentage = Number(event.target.value); document.getElementById("percentageLabel").textContent = format(state.pass_percentage,1) + "%"; renderAll(); }});
  setLockState();
}}
function renderKpis(rows) {{
  const grades = rows.map(row => row.grade);
  const failed = rows.filter(row => !row.sufficient).length;
  const pass = passScore();
  const highest = grades.length ? Math.max(...grades) : 0;
  const lowest = grades.length ? Math.min(...grades) : 0;
  const cards = [
    ["Gemiddeld cijfer", grades.length ? displayGrade(mean(grades)) : "-", ""],
    ["Mediaan", grades.length ? displayGrade(median(grades)) : "-", ""],
    ["% Onvoldoende", rows.length ? Math.round(failed/rows.length*100) + "%" : "-", "red"],
    ["Voldoende vanaf", pass === null ? "-" : format(pass, pass % 1 ? 1 : 0) + " pnt", "green"],
    ["Hoogste cijfer", grades.length ? displayGrade(highest) : "-", "green"],
    ["Aantal deelnemers", String(rows.length), ""]
  ];
  document.getElementById("kpis").innerHTML = cards.map(card => `<article class="card kpi ${{card[2]}}"><div class="kpi-label">${{card[0]}}</div><div class="kpi-value">${{card[1]}}</div></article>`).join("");
}}
function compactStripPositions(rows) {{
  const positions = {{}};
  const occupied = {{}};
  let furthestSlot = 0;
  const verticalClearance = .42;
  const horizontalStep = .011;
  [...rows].sort((left, right) => left.grade - right.grade || left.index - right.index).forEach(row => {{
    let slot = 0;
    let placed = false;
    for (let offset=0; offset<=rows.length && !placed; offset++) {{
      const candidates = offset === 0 ? [0] : [-offset, offset];
      for (const candidate of candidates) {{
        const used = occupied[String(candidate)] || [];
        if (used.every(gradeValue => Math.abs(gradeValue - row.grade) >= verticalClearance)) {{
          slot = candidate;
          occupied[String(candidate)] = used.concat(row.grade);
          placed = true;
          break;
        }}
      }}
    }}
    positions[row.index] = slot * horizontalStep;
    furthestSlot = Math.max(furthestSlot, Math.abs(slot));
  }});
  return {{positions, range: Math.max(.23, (furthestSlot + 1.3) * horizontalStep)}};
}}
function renderExpandedChart(name) {{
  const definition = chartDefinitions[name];
  if (!window.Plotly || !definition) return;
  document.getElementById("expandedTitle").textContent = definition.title;
  const layout = Object.assign({{}}, definition.layout, {{
    autosize: true,
    margin: {{l:58, r:28, t:22, b:58}}
  }});
  Plotly.react("expandedChart", definition.data, layout, chartConfig);
}}
function openExpandedChart(name, trigger) {{
  expandedChartName = name;
  expandedChartTrigger = trigger || document.activeElement;
  const modal = document.getElementById("chartModal");
  modal.removeAttribute("inert");
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  renderExpandedChart(name);
  document.getElementById("closeExpandedChart").focus();
}}
function closeExpandedChart() {{
  expandedChartName = null;
  const modal = document.getElementById("chartModal");
  const restoreFocus = expandedChartTrigger;
  expandedChartTrigger = null;
  if (restoreFocus && document.contains(restoreFocus)) {{
    restoreFocus.focus();
  }} else if (modal.contains(document.activeElement)) {{
    document.activeElement.blur();
  }}
  modal.setAttribute("inert", "");
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  if (window.Plotly) Plotly.purge("expandedChart");
}}
function renderPlots(rows) {{
  if (!window.Plotly) {{ document.getElementById("plotlyUnavailable").style.display = "block"; return; }}
  const pass = passScore();
  const strip = compactStripPositions(rows);
  const passRows = rows.filter(row => row.sufficient);
  const failRows = rows.filter(row => !row.sufficient);
  const pointTrace = (source, color) => ({{
    x: source.map(row => strip.positions[row.index]), y: source.map(row => row.grade),
    customdata: source.map(row => [row.name, row.score, displayGrade(row.grade), row.percentage]),
    mode:"markers", type:"scatter", name: source === passRows ? "Voldoende" : "Onvoldoende",
    marker:{{color, size:12, line:{{color:"#fff", width:1.4}}}},
    hovertemplate:"<b>%{{customdata[0]}}</b><br>Score: %{{customdata[1]}} / " + maximum + "<br>Cijfer: %{{customdata[2]}}<br>% van de punten gescoord: %{{customdata[3]:.0f}}%<extra></extra>"
  }});
  const box = {{x: rows.map(()=>0), y: rows.map(row=>row.grade), type:"box", name:"Spreiding", boxpoints:false, fillcolor:"rgba(98,86,234,.035)", line:{{color:"#8390a7",width:1}}, width:.18, hoverinfo:"skip"}};
  const baseLayout = {{dragmode:false, font:{{family:"Inter, Segoe UI, sans-serif", color:"#52627e", size:12}}, paper_bgcolor:"transparent", plot_bgcolor:"transparent", margin:{{l:42,r:18,t:14,b:38}}, hovermode:"closest", showlegend:true, legend:{{orientation:"h", x:.3, y:-.1}}, yaxis:{{title:"Cijfer", range:[.8,10.3], dtick:1, gridcolor:colors.grid, zeroline:false, fixedrange:true}}, xaxis:{{showticklabels:false, range:[-strip.range,strip.range], gridcolor:"transparent", zeroline:false, fixedrange:true}}, shapes:[{{type:"line", x0:-strip.range, x1:strip.range, y0:5.5, y1:5.5, line:{{color:"#9ca9bc", dash:"dash", width:1}}}}], annotations:[{{x:strip.range*.95,y:5.5,text:"5,5",showarrow:false,bgcolor:"#fff",bordercolor:"#dfe5ef",font:{{size:11}}}}]}};
  chartDefinitions.scatter = {{title:"Cijferverdeling (per leerling)", data:[box, pointTrace(passRows, colors.green), pointTrace(failRows, colors.red)], layout:baseLayout}};
  Plotly.react("scatter", chartDefinitions.scatter.data, chartDefinitions.scatter.layout, chartConfig);
  const histogramEnd = Math.ceil(maximum / histogramBinSize) * histogramBinSize;
  const histLayout = {{dragmode:false, font:{{family:"Inter, Segoe UI, sans-serif", color:"#52627e", size:11}}, paper_bgcolor:"transparent", plot_bgcolor:"transparent", margin:{{l:36,r:8,t:12,b:42}}, bargap:.08, showlegend:false, xaxis:{{title:"Score (punten)", range:[0,histogramEnd], tick0:0, dtick:histogramBinSize, gridcolor:"transparent", fixedrange:true}}, yaxis:{{title:"Aantal", gridcolor:colors.grid, zeroline:false, fixedrange:true}}, shapes: pass === null ? [] : [{{type:"line", x0:pass,x1:pass,y0:0,y1:1,yref:"paper",line:{{color:colors.green,dash:"dash",width:2}}}}], annotations: pass === null ? [] : [{{x:pass,y:1,xref:"x",yref:"paper",text:"Voldoende vanaf<br>" + format(pass, pass % 1 ? 1 : 0) + " punten",showarrow:false,xanchor:"left",yanchor:"top",bgcolor:"#f0faf3",bordercolor:"#d9eee0",font:{{color:colors.green,size:10}}}}]}};
  chartDefinitions.histogram = {{title:"Scoreverdeling", data:[{{x:rows.map(row=>row.score), type:"histogram", marker:{{color:"#7165ed", line:{{color:"#fff",width:1}}}}, xbins:{{start:0,end:histogramEnd,size:histogramBinSize}}}}], layout:histLayout}};
  Plotly.react("histogram", chartDefinitions.histogram.data, chartDefinitions.histogram.layout, chartConfig);
  const step = maximum ? maximum / 80 : 1; const x = []; for(let value=0; value<=maximum+.001; value+=step) x.push(value); if (maximum && x[x.length-1] !== maximum) x.push(maximum);
  const curveTick = maximum <= 20 ? 2 : maximum <= 50 ? 5 : maximum <= 100 ? 10 : 20;
  const curveLayout = {{dragmode:false, font:{{family:"Inter, Segoe UI, sans-serif", color:"#52627e",size:10}}, paper_bgcolor:"transparent",plot_bgcolor:"transparent",margin:{{l:32,r:10,t:6,b:35}},showlegend:false,xaxis:{{title:"Score",range:[0,maximum],tick0:0,dtick:curveTick,gridcolor:colors.grid,fixedrange:true}},yaxis:{{title:"Cijfer",range:[.8,10.3],dtick:2,gridcolor:colors.grid,fixedrange:true}},shapes:pass === null ? [] : [{{type:"line",x0:pass,x1:pass,y0:1,y1:10,line:{{color:"#9ca9bc",dash:"dot"}}}},{{type:"line",x0:0,x1:maximum,y0:5.5,y1:5.5,line:{{color:"#9ca9bc",dash:"dot"}}}}]}};
  chartDefinitions.curve = {{title:"Normeringscurve", data:[{{x,y:x.map(value=>rawGrade(value)),type:"scatter",mode:"lines",line:{{color:colors.purple,width:2}}}},{{x,y:x.map(value=>maximum ? 1+9*value/maximum : 1),type:"scatter",mode:"lines",line:{{color:"#bdc8da",width:1,dash:"dash"}}}}], layout:curveLayout}};
  Plotly.react("curve", chartDefinitions.curve.data, chartDefinitions.curve.layout, chartConfig);
  if (expandedChartName) renderExpandedChart(expandedChartName);
  window.__chartsReady = true;
}}
function renderSummary(rows) {{
  const scores = rows.map(row=>row.score);
  const entries = [
    ["Maximum score", format(maximum, maximum % 1 ? 1 : 0)],
    ["Gemiddelde score", scores.length ? format(mean(scores)) : "-"],
    ["Mediaan score", scores.length ? format(median(scores)) : "-"],
    ["Standaarddeviatie", scores.length > 1 ? format(sd(scores)) : "-"],
    ["Betrouwbaarheid (alpha)", data.reliability === null ? "-" : Number(data.reliability).toFixed(2)]
  ];
  document.getElementById("summaryRows").innerHTML = entries.map(entry=>`<div class="summary-row"><span>${{entry[0]}}</span><strong>${{entry[1]}}</strong></div>`).join("");
}}
function sortedRows(rows) {{
  const order = document.getElementById("participantSort").value;
  const sorted = [...rows];
  if (order === "score_desc") return sorted.sort((left, right) => right.score - left.score || left.index - right.index);
  if (order === "score_asc") return sorted.sort((left, right) => left.score - right.score || left.index - right.index);
  return sorted.sort((left, right) => left.index - right.index);
}}
function renderTable(rows) {{
  const query = document.getElementById("search").value.trim().toLowerCase();
  const filtered = sortedRows(rows).filter(row => row.name.toLowerCase().includes(query));
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize)); page = Math.min(page, pages);
  const visible = filtered.slice((page-1)*pageSize, page*pageSize);
  document.getElementById("tableTitle").textContent = "6. Overzicht deelnemers (" + rows.length + ")";
  document.getElementById("participantRows").innerHTML = visible.map((row,index)=>`<tr><td>${{(page-1)*pageSize+index+1}}</td><td>${{row.name}}</td><td class="number ${{row.sufficient?"sufficient":"insufficient"}}">${{format(row.score, row.score % 1 ? 1 : 0)}} / ${{format(maximum, maximum % 1 ? 1 : 0)}}</td><td class="number ${{row.sufficient?"sufficient":"insufficient"}}">${{Math.round(row.percentage)}}%</td><td class="number ${{row.sufficient?"sufficient":"insufficient"}}">${{displayGrade(row.grade)}}</td><td><span class="badge ${{row.sufficient?"":"bad"}}">${{row.sufficient?"Voldoende":"Onvoldoende"}}</span></td></tr>`).join("");
  let buttons = ""; for(let i=1; i<=pages; i++) buttons += `<button class="page-btn ${{i===page?"active":""}}" data-page="${{i}}">${{i}}</button>`;
  document.getElementById("pagination").innerHTML = buttons;
  document.querySelectorAll(".page-btn").forEach(button => button.addEventListener("click", () => {{ page = Number(button.dataset.page); renderTable(rows); }}));
}}
function renderAll() {{
  const rows = calculated(); const pass = passScore();
  document.getElementById("passCardValue").textContent = pass === null || !maximum ? "-" : format(pass, pass % 1 ? 1 : 0) + " punten (" + Math.round(pass/maximum*100) + "%)";
  renderKpis(rows); renderSummary(rows); renderTable(rows); renderPlots(rows);
}}
document.getElementById("pageTitle").textContent = "Normeren - " + data.test.name;
document.getElementById("context").textContent = [data.test.school_year, data.test.level, data.test.grade_year, data.test.period].filter(Boolean).join("  |  ")
  + (data.incomplete_count ? "  |  " + data.incomplete_count + " onvolledig resultaat uitgesloten" : "");
function synchronizeRoundingControl() {{
  const rounding = document.getElementById("rounding");
  if (state.method === "n_term" || state.method === "cvte_cesuur") {{
    state.rounding_method = "standaard";
    state.decimal_places = 1;
    rounding.disabled = true;
  }} else {{
    rounding.disabled = false;
  }}
  rounding.value = state.rounding_method + ":" + Number(state.decimal_places === undefined ? 1 : state.decimal_places);
  setLockState();
}}
document.querySelectorAll(".method").forEach(button => button.addEventListener("click", () => {{
  state.method = button.dataset.method;
  synchronizeRoundingControl();
  renderMethodControls();
  renderAll();
}}));
synchronizeRoundingControl();
document.getElementById("rounding").addEventListener("change", event => {{
  const parts = event.target.value.split(":");
  state.rounding_method = parts[0];
  state.decimal_places = Number(parts[1]);
  renderAll();
}});
document.getElementById("search").addEventListener("input", () => {{ page = 1; renderTable(calculated()); }});
document.getElementById("participantSort").addEventListener("change", () => {{ page = 1; renderTable(calculated()); }});
document.getElementById("histogramBinSize").addEventListener("change", event => {{
  histogramBinSize = Number(event.target.value);
  renderPlots(calculated());
}});
document.querySelectorAll(".expand-button").forEach(button => button.addEventListener("click", () => {{
  openExpandedChart(button.dataset.expand, button);
}}));
document.getElementById("closeExpandedChart").addEventListener("click", closeExpandedChart);
document.getElementById("chartModal").addEventListener("click", event => {{
  if (event.target.id === "chartModal") closeExpandedChart();
}});
document.addEventListener("keydown", event => {{
  if (event.key === "Escape" && expandedChartName) closeExpandedChart();
}});
function showSaveMessage(text, ok) {{
  const message = document.getElementById("saveMessage");
  message.textContent = text;
  message.style.color = ok ? "var(--green)" : "var(--red)";
  message.classList.add("visible");
  setTimeout(() => message.classList.remove("visible"), 3400);
}}
function exportParticipants(formatName) {{
  if (!bridge) return;
  const rows = sortedRows(calculated()).map(row => ({{
    name: row.name, score: row.score, percentage: row.percentage, grade: row.grade
  }}));
  const request = JSON.stringify({{rows, method: methodName(), is_finalized: finalized}});
  bridge.exportParticipants(formatName, request, response => {{
    const result = JSON.parse(response);
    if (result.cancelled) return;
    showSaveMessage(result.message, result.ok);
  }});
}}
document.getElementById("exportExcel").addEventListener("click", () => exportParticipants("excel"));
document.getElementById("exportPdf").addEventListener("click", () => exportParticipants("pdf"));
document.getElementById("finalizeButton").addEventListener("click", () => {{
  if (!bridge) return;
  bridge.finalizeNormalization(JSON.stringify(state), response => {{
    const result = JSON.parse(response);
    if (result.ok) {{
      finalized = true;
      setLockState();
    }}
    showSaveMessage(result.message, result.ok);
  }});
}});
document.getElementById("reopenButton").addEventListener("click", () => {{
  if (!bridge) return;
  bridge.removeNormalization(response => {{
    const result = JSON.parse(response);
    if (result.cancelled) return;
    if (result.ok) {{
      Object.assign(state, result.settings);
      finalized = false;
      synchronizeRoundingControl();
      renderMethodControls();
      renderAll();
    }}
    showSaveMessage(result.message, result.ok);
  }});
}});
renderMethodControls();
renderAll();
</script>
</body>
</html>"""
