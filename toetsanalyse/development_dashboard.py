from __future__ import annotations

import json


def build_development_dashboard_html(data: dict[str, object], plotly_asset: str = "plotly-2.35.2.min.js") -> str:
    payload = json.dumps(data, ensure_ascii=False)
    html = """
<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
  <script src="__PLOTLY__"></script>
  <style>
    :root {
      --bg: #f6f8fb;
      --card: #ffffff;
      --border: #e3eaf3;
      --text: #071f42;
      --muted: #62708a;
      --primary: #5b5ff1;
      --green: #2fa866;
      --red: #e24a4a;
      --amber: #e99b22;
      --shadow: 0 14px 36px rgba(15, 35, 70, .08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
    }
    .page {
      max-width: 1480px;
      margin: 0 auto;
      padding: 24px;
    }
    .hero {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
      margin-bottom: 18px;
    }
    h1 { margin: 0; font-size: 28px; letter-spacing: -.02em; }
    .subtitle { color: var(--muted); margin-top: 6px; line-height: 1.45; }
    .tabs {
      display: inline-flex;
      padding: 4px;
      background: #eef3fb;
      border: 1px solid var(--border);
      border-radius: 14px;
      gap: 4px;
    }
    .hero-actions {
      display: flex;
      gap: 10px;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }
    .action-btn {
      border: 1px solid #d7e0ec;
      background: #ffffff;
      color: var(--text);
      border-radius: 12px;
      padding: 10px 14px;
      font-weight: 800;
      cursor: pointer;
      box-shadow: 0 8px 18px rgba(15, 35, 70, .06);
    }
    .action-btn.primary {
      background: #071f42;
      border-color: #071f42;
      color: #ffffff;
    }
    .tab {
      border: 0;
      background: transparent;
      color: var(--muted);
      padding: 10px 16px;
      border-radius: 11px;
      font-weight: 700;
      cursor: pointer;
    }
    .tab.active {
      background: var(--card);
      color: var(--primary);
      box-shadow: 0 8px 18px rgba(15, 35, 70, .08);
    }
    .kpis {
      display: grid;
      grid-template-columns: repeat(6, minmax(130px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }
    .overview-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(170px, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: var(--shadow);
    }
    .kpi { padding: 16px; min-height: 96px; }
    .kpi .label { color: var(--muted); font-size: 12px; font-weight: 700; }
    .kpi .value { font-size: 25px; font-weight: 800; margin-top: 8px; letter-spacing: -.02em; }
    .kpi .note { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .overview-card {
      padding: 11px 13px;
      border-left: 4px solid var(--primary);
      min-height: 78px;
    }
    .overview-card.green { border-left-color: var(--green); }
    .overview-card.red { border-left-color: var(--red); }
    .overview-card.amber { border-left-color: var(--amber); }
    .overview-title { color: var(--muted); font-size: 10.5px; font-weight: 850; text-transform: uppercase; letter-spacing: .035em; }
    .overview-value { font-size: 18px; font-weight: 850; margin-top: 5px; line-height: 1.12; }
    .overview-detail { color: var(--muted); margin-top: 4px; line-height: 1.25; font-size: 12px; }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.65fr) minmax(360px, .75fr);
      gap: 16px;
      align-items: start;
    }
    .section { padding: 18px; }
    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .section-title { font-size: 18px; font-weight: 800; }
    .section-subtitle { color: var(--muted); font-size: 13px; margin-top: 3px; }
    .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    select, input {
      height: 38px;
      border: 1px solid #d7e0ec;
      border-radius: 11px;
      background: #fff;
      color: var(--text);
      padding: 0 12px;
      font: inherit;
      min-width: 190px;
    }
    .chart { width: 100%; height: 540px; }
    .small-chart { height: 300px; }
    .insight {
      border: 1px solid #dde7fb;
      background: #f5f7ff;
      border-radius: 14px;
      padding: 12px 14px;
      color: #314263;
      line-height: 1.45;
      margin-top: 12px;
    }
    .chart-legend {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 12px;
      align-items: center;
      border: 1px solid var(--border);
      background: #fbfdff;
      border-radius: 999px;
      padding: 8px 12px;
      color: #40516a;
      font-size: 12px;
      margin: 8px auto 0;
      width: fit-content;
      max-width: 100%;
    }
    .chart-legend span {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
    }
    .legend-dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      display: inline-block;
      box-shadow: 0 0 0 2px #fff;
    }
    .student-card {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      margin-top: 8px;
    }
    .mini {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      background: #fbfdff;
    }
    .mini .label { color: var(--muted); font-size: 12px; }
    .mini .value { font-weight: 800; font-size: 20px; margin-top: 4px; }
    .student-trend-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      margin-top: 10px;
    }
    .trend-mini {
      border-left: 4px solid #c8d3e4;
      min-width: 0;
    }
    .trend-mini.green { border-left-color:#2fa866; background:#f4fbf7; }
    .trend-mini.amber { border-left-color:#e99b22; background:#fff8ec; }
    .trend-mini.red { border-left-color:#e24a4a; background:#fff2f2; }
    .trend-mini .note { color: var(--muted); font-size: 11px; margin-top: 2px; line-height: 1.35; }
    .table-wrap {
      max-height: 380px;
      overflow: auto;
      border: 1px solid var(--border);
      border-radius: 14px;
      margin-top: 12px;
    }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th {
      position: sticky;
      top: 0;
      background: #edf3ff;
      color: #233755;
      text-align: left;
      padding: 10px;
      z-index: 1;
    }
    td { border-top: 1px solid var(--border); padding: 9px 10px; }
    tr:nth-child(even) td { background: #fafcff; }
    .pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      font-weight: 700;
      background: #eef3ff;
      color: #40516a;
    }
    .pill.green { background: #e8f7ed; color: #177344; }
    .pill.red { background: #fdecec; color: #b42b2b; }
    .pill.amber { background: #fff5df; color: #9a5b00; }
    .signal-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin-top: 10px;
    }
    .student-signal-board {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }
    .signal-stack {
      grid-template-columns: 1fr !important;
      margin-top: 8px;
    }
    .signal {
      border: 1px solid #dfe7f2;
      border-radius: 14px;
      padding: 12px;
      background: #fbfdff;
      min-width: 0;
      overflow-wrap: anywhere;
    }
    .signal .tag { font-size: 11px; font-weight: 850; color: var(--muted); text-transform: uppercase; letter-spacing:.03em; }
    .signal .subject { margin-top: 5px; font-weight: 850; }
    .signal .detail { color: var(--muted); margin-top: 4px; line-height: 1.35; }
    .signal.green { background:#f3fbf6; border-color:#cfeedd; }
    .signal.amber { background:#fff8ec; border-color:#f3dfb7; }
    .signal.red { background:#fff1f1; border-color:#f2cdcd; }
    .resit-metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 10px;
      margin: 4px 0 12px;
    }
    .split-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .split-grid > *, .student-signal-board > * { min-width: 0; }
    .trend-summary-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(150px, 1fr));
      gap: 10px;
      margin: 8px 0 14px;
    }
    .trend-summary-card {
      border: 1px solid var(--border);
      border-radius: 16px;
      background: #fbfdff;
      padding: 13px 14px;
      min-width: 0;
    }
    .trend-summary-card.green { background:#f3fbf6; border-color:#cfeedd; }
    .trend-summary-card.amber { background:#fff8ec; border-color:#f3dfb7; }
    .trend-summary-card.red { background:#fff1f1; border-color:#f2cdcd; }
    .trend-summary-card .label { color: var(--muted); font-size: 11px; font-weight: 850; text-transform: uppercase; }
    .trend-summary-card .value { font-size: 24px; font-weight: 850; margin-top: 4px; }
    .trend-summary-card .note { color: var(--muted); font-size: 12px; margin-top: 2px; }
    .trend-layout {
      display: grid;
      grid-template-columns: minmax(360px, .9fr) minmax(0, 1.1fr);
      gap: 14px;
      align-items: start;
    }
    .trend-panel {
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 14px;
      background: #fbfdff;
      min-width: 0;
    }
    .trend-table-wrap { max-height: 390px; }
    .sparkline {
      width: 82px;
      height: 24px;
      display: block;
    }
    .subheading {
      font-weight: 850;
      margin: 4px 0 8px;
      color: #233755;
    }
    .page-block { display: none; }
    .page-block.active { display: block; }
    .empty {
      padding: 42px;
      text-align: center;
      color: var(--muted);
    }
    @media (max-width: 1100px) {
      .kpis { grid-template-columns: repeat(3, 1fr); }
      .overview-grid, .resit-metrics { grid-template-columns: repeat(2, 1fr); }
      .signal-grid { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
      .trend-layout { grid-template-columns: 1fr; }
      .trend-summary-grid { grid-template-columns: 1fr; }
      .student-signal-board { grid-template-columns: 1fr; }
      .split-grid { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="page">
    <div class="hero">
      <div>
        <h1>Ontwikkelanalyse</h1>
        <div class="subtitle">Analyse over meerdere toetsen. Standaard wordt alle beschikbare data meegenomen; filters in de app beperken de selectie.</div>
      </div>
      <div class="hero-actions">
        <button class="action-btn primary" id="exportGroupReport">Groepsrapport PDF</button>
        <button class="action-btn" id="exportStudentReport">Leerlingrapport PDF</button>
        <div class="tabs">
          <button class="tab active" data-tab="group">Groep</button>
          <button class="tab" data-tab="student">Leerling</button>
        </div>
      </div>
    </div>

    <section class="kpis" id="kpis"></section>
    <section class="overview-grid" id="overviewCards"></section>

    <section id="empty" class="card empty" style="display:none">
      <h2>Geen complete resultaten gevonden</h2>
      <p>Voer resultaten in bij meerdere toetsen of verruim de filters om ontwikkelanalyse te tonen.</p>
    </section>

    <div id="student" class="page-block">
      <div class="grid">
        <section class="card section">
          <div class="section-header">
            <div>
              <div class="section-title">Verschillen per onderdeel</div>
              <div class="section-subtitle">Kies waarop u wilt kijken, bijvoorbeeld RTTI, domein, hoofdstuk of vraagtype. Hover over een bolletje of zoek een leerling om de lijn te tonen.</div>
            </div>
            <div class="controls">
              <select id="profileDimensionSelect"></select>
              <input id="studentSearch" placeholder="Leerling zoeken...">
              <select id="studentSelect"></select>
            </div>
          </div>
          <div id="profileChart" class="chart"></div>
          <div class="chart-legend" aria-label="Legenda profielgrafiek">
            <span><i class="legend-dot" style="background:#2fa866"></i>55% of hoger</span>
            <span><i class="legend-dot" style="background:#e24a4a"></i>onder 55%</span>
            <span><i class="legend-dot" style="background:#5b5ff1"></i>deze leerling</span>
          </div>
          <div class="insight" id="profileInsight"></div>
        </section>

        <aside class="card section">
          <div class="section-title">Geselecteerde leerling</div>
          <div id="studentDetails"></div>
          <div class="section-title" style="margin-top:18px">Toetsontwikkeling leerling vs groep</div>
          <div id="studentTestChart" class="small-chart"></div>
          <div class="insight" id="studentTrendInsight"></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Toets</th><th>% punten</th><th>Cijfer</th></tr></thead>
              <tbody id="studentTests"></tbody>
            </table>
          </div>
        </aside>
      </div>
      <section class="split-grid" style="margin-top:16px">
        <section class="card section">
          <div class="section-title">Positie in de groep door de tijd</div>
          <div class="section-subtitle">Bij de geselecteerde leerling: beter dan hoeveel procent van de leerlingen per toets.</div>
          <div id="studentPercentileChart" class="small-chart"></div>
          <div class="insight" id="studentPercentileInsight"></div>
        </section>
        <section class="card section">
          <div class="section-header">
            <div>
              <div class="section-title">Leerlingontwikkeling per onderdeel</div>
              <div class="section-subtitle">Kies bijvoorbeeld RTTI, domein, hoofdstuk of vraagtype.</div>
            </div>
            <select id="studentTrendDimensionSelect"></select>
          </div>
          <div id="studentDimensionTrendChart" class="small-chart"></div>
          <div class="insight" id="studentDimensionTrendInsight"></div>
        </section>
      </section>
      <section class="card section" style="margin-top:16px" id="resitSection">
        <div class="section-header">
          <div>
            <div class="section-title">Signalen voor deze leerling</div>
            <div class="section-subtitle">Een korte vertaling van de grafieken: wat gaat goed, wat valt op en waar zit verbetering?</div>
          </div>
        </div>
        <div class="student-signal-board">
          <div>
            <div class="subheading">Positief</div>
            <div class="signal-grid signal-stack" id="studentPositiveCards"></div>
          </div>
          <div>
            <div class="subheading">Opvallend</div>
            <div class="signal-grid signal-stack" id="studentNotableCards"></div>
          </div>
          <div>
            <div class="subheading">Verbeterpunten</div>
            <div class="signal-grid signal-stack" id="studentImprovementCards"></div>
          </div>
        </div>
      </section>
    </div>

    <div id="group" class="page-block active">
      <div class="grid">
        <section class="card section">
          <div class="section-header">
            <div>
              <div class="section-title">Groepsbeeld per onderdeel</div>
              <div class="section-subtitle">Gemiddelde prestaties per onderdeel, op basis van de geselecteerde totale dataset.</div>
            </div>
            <select id="dimensionSelect"></select>
          </div>
          <div id="groupDimensionChart" class="chart" style="height:420px"></div>
          <div class="insight" id="groupDimensionInsight"></div>
        </section>
        <aside class="card section">
          <div class="section-title">Toetsen in de selectie</div>
          <div id="testTrendChart" class="small-chart"></div>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Toets</th><th>Gem. %</th><th>Leerlingen</th></tr></thead>
              <tbody id="testRows"></tbody>
            </table>
          </div>
        </aside>
      </div>
      <section class="card section" style="margin-top:16px">
        <div class="section-header">
          <div>
            <div class="section-title">Leerlingontwikkeling-overzicht</div>
            <div class="section-subtitle">Samenvatting van de stap van vorige naar huidige toets, met een compacte lijst per leerling.</div>
          </div>
          <div class="controls">
            <select id="studentTrendOverviewFilter">
              <option value="all">Alle leerlingen</option>
              <option value="rising">Vooruitgang</option>
              <option value="falling">Terugval</option>
              <option value="attention">Aandacht nodig</option>
            </select>
            <select id="studentTrendOverviewSort">
              <option value="recentDesc">Sorteer: grootste vooruitgang sinds vorige</option>
              <option value="recentAsc">Sorteer: grootste terugval sinds vorige</option>
              <option value="currentDesc">Sorteer: hoogste huidige score</option>
              <option value="name">Sorteer: naam</option>
            </select>
          </div>
        </div>
        <div class="trend-summary-grid" id="studentTrendSummaryCards"></div>
        <div class="trend-panel">
          <div class="subheading">Ranglijst per leerling</div>
          <div class="table-wrap trend-table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Leerling</th>
                  <th>Vorige</th>
                  <th>Huidige</th>
                  <th>Verschil</th>
                  <th>Mini-trend</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody id="studentTrendOverviewRows"></tbody>
            </table>
          </div>
        </div>
        <div class="insight" id="studentTrendOverviewInsight"></div>
      </section>
      <section class="card section" style="margin-top:16px">
        <div class="section-header">
          <div>
            <div class="section-title">Ontwikkeling per onderdeel</div>
            <div class="section-subtitle">Kies waarop u wilt kijken om te zien welke onderdelen stijgen, dalen of stabiel blijven.</div>
          </div>
          <select id="groupTrendDimensionSelect"></select>
        </div>
        <div id="groupDimensionTrendChart" class="chart" style="height:420px"></div>
        <div class="insight" id="groupDimensionTrendInsight"></div>
      </section>
      <section class="card section" style="margin-top:16px">
        <div class="section-header">
          <div>
            <div class="section-title">Trends en aandachtspunten</div>
            <div class="section-subtitle">Gesplitst in positieve ontwikkelingen, leerlingen die opvallen en onderdelen die aandacht vragen.</div>
          </div>
        </div>
        <div class="split-grid">
          <div>
            <div class="subheading">Leerlingen</div>
            <div class="signal-grid" id="studentSignalCards"></div>
          </div>
          <div>
            <div class="subheading">Groep en onderdelen</div>
            <div class="signal-grid" id="groupSignalCards"></div>
          </div>
        </div>
      </section>
      <section class="card section" style="margin-top:16px">
        <div class="section-header">
          <div>
            <div class="section-title">Niet meegedaan of toets niet gemaakt</div>
            <div class="section-subtitle">Leerlingen die in deze selectie vaker een niet-gemaakte status hebben, bijvoorbeeld absent, ziek of vrijstelling.</div>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Leerling</th><th>Aantal</th><th>Meest voorkomend</th><th>Toetsen</th></tr></thead>
            <tbody id="attendanceRows"></tbody>
          </table>
        </div>
      </section>
      <section class="card section" style="margin-top:16px">
        <div class="section-header">
          <div>
            <div class="section-title">Herkansingen: ontwikkeling</div>
            <div class="section-subtitle">Originele toets vergeleken met herkansing; het dashboard gebruikt in analyses het eindresultaat.</div>
          </div>
          <span class="pill" id="resitSummary"></span>
        </div>
        <div class="resit-metrics" id="resitMetrics"></div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Leerling</th><th>Origineel</th><th>Herkansing</th><th>Verschil %</th><th>Verschil cijfer</th></tr></thead>
            <tbody id="resitRows"></tbody>
          </table>
        </div>
      </section>
    </div>
  </main>

  <script>
    const data = __DATA__;
    const students = data.students || [];
    const profile = data.profile_chart || {categories: [], dimension_blocks: [], points: []};
    const points = profile.points || [];
    let highlightedStudent = null;
    let currentProfileDimensionKey = null;
    let activeTab = "group";
    let developmentBridge = null;
    if (window.qt && window.QWebChannel) {
      new QWebChannel(qt.webChannelTransport, channel => { developmentBridge = channel.objects.developmentBridge; });
    }

    const fmtPct = value => value == null || Number.isNaN(Number(value)) ? "-" : `${Math.round(Number(value))}%`;
    const fmtNum = value => value == null || Number.isNaN(Number(value)) ? "-" : Number(value).toLocaleString("nl-NL", {maximumFractionDigits: 1});
    const htmlEntities = {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"};
    const esc = value => String(value ?? "").replace(/[&<>"']/g, character => htmlEntities[character]);
    function positionValue(item) {
      return item?.percentile == null ? "-" : `beter dan ${fmtPct(item.percentile)}`;
    }
    function positionDetail(item) {
      if (!item || item.rank == null) return "Nog geen groepspositie beschikbaar";
      if (Number(item.tied_count || 0) > 1) return item.rank_count ? `Plaats ${item.rank} gedeeld met ${item.tied_count} leerlingen van ${item.rank_count}` : `Plaats ${item.rank} gedeeld`;
      return item.rank_count ? `Plaats ${item.rank} van ${item.rank_count}` : `Plaats ${item.rank}`;
    }
    function positionTone(item) {
      const percentile = Number(item?.percentile);
      if (Number.isNaN(percentile)) return "";
      if (percentile >= 70) return "green";
      if (percentile < 25) return "red";
      return "amber";
    }
    const plotConfig = {responsive:true, displayModeBar:false, scrollZoom:false, doubleClick:false};
    function safePlot(targetId, traces, layout) {
      const prepared = {...layout, dragmode:false};
      ["xaxis", "yaxis", "xaxis2", "yaxis2"].forEach(axis => {
        if (prepared[axis]) prepared[axis] = {...prepared[axis], fixedrange:true};
      });
      return Plotly.newPlot(targetId, traces, prepared, plotConfig);
    }
    function shortLabel(value, maxLength = 20) {
      const text = String(value ?? "");
      return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
    }
    function markerSizeForWeight(weight) {
      const value = Number(weight);
      if (!Number.isFinite(value) || value <= 0) return 9;
      return Math.max(10, Math.min(26, 9 + Math.sqrt(value) * 6));
    }
    function markerColorForWeight(weight, fallback = "#5b5ff1") {
      return Number(weight) <= 0 ? "#a8b1c2" : fallback;
    }

    function profileDimensions() {
      const availableKeys = new Set((profile.categories || []).map(category => String(category.dimension_key)));
      return (data.group_dimensions || []).filter(dimension => availableKeys.has(String(dimension.key)));
    }

    function currentProfileDimension() {
      const dimensions = profileDimensions();
      if (!currentProfileDimensionKey && dimensions.length) currentProfileDimensionKey = String(dimensions[0].key);
      return dimensions.find(dimension => String(dimension.key) === String(currentProfileDimensionKey)) || dimensions[0] || null;
    }

    function currentProfileCategories() {
      const dimension = currentProfileDimension();
      if (!dimension) return [];
      return (profile.categories || []).filter(category => String(category.dimension_key) === String(dimension.key));
    }

    function currentProfilePoints() {
      const categories = currentProfileCategories();
      const xByCategory = new Map(categories.map((category, index) => [String(category.category), index]));
      const dimension = currentProfileDimension();
      if (!dimension) return [];
      return points
        .filter(point => String(point.dimension_key) === String(dimension.key))
        .map(point => {
          const baseX = xByCategory.get(String(point.category));
          const jitter = Number(point.x_jitter || 0) - Number(point.x || 0);
          return {...point, plot_x: Number(baseX ?? 0), plot_x_jitter: Number(baseX ?? 0) + jitter};
        });
    }

    function renderKpis() {
      const summary = data.summary || {};
      const items = [
        ["Leerlingen", summary.student_count ?? 0, "met complete resultaten"],
        ["Toetsen", summary.test_count ?? 0, "eindresultaat gebruikt"],
        ["Resultaten", summary.record_count ?? 0, "toetsafnames"],
        ["Onderdelen", summary.dimension_count ?? 0, "met data"],
        ["Gem. score", fmtPct(summary.mean_score_percentage), "% van punten"],
        ["Herkansingen", summary.resit_count ?? 0, "met vergelijking"],
      ];
      document.getElementById("kpis").innerHTML = items.map(([label, value, note]) => `
        <div class="card kpi"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="note">${esc(note)}</div></div>
      `).join("");
    }

    function studentOverviewCards(studentId) {
      const student = students.find(candidate => String(candidate.id) === String(studentId));
      if (!student) return [];
      const trend = student.trend || {};
      const studentPoints = points.filter(point => String(point.student_id) === String(student.id));
      const strongest = studentPoints.length
        ? [...studentPoints].sort((a, b) => Number(b.percentage || 0) - Number(a.percentage || 0))[0]
        : null;
      const weakest = studentPoints.length
        ? [...studentPoints].sort((a, b) => Number(a.percentage || 0) - Number(b.percentage || 0))[0]
        : null;
      const studentResits = (data.resits?.rows || []).filter(row => String(row.student_id) === String(student.id));
      const meanResitDelta = studentResits.length
        ? studentResits.reduce((sum, row) => sum + Number(row.delta_percentage || 0), 0) / studentResits.length
        : null;
      const cards = [
        {
          title: "Totaalbeeld leerling",
          value: fmtPct(student.score_percentage),
          detail: `${student.test_count} toets(en) in deze selectie`,
          tone: Number(student.score_percentage) >= 55 ? "green" : "red",
        },
        {
          title: "Positie in groep",
          value: positionValue(student),
          detail: positionDetail(student),
          tone: positionTone(student),
        },
        {
          title: "Ontwikkeling",
          value: trend.delta == null ? "-" : `${Number(trend.delta) >= 0 ? "+" : ""}${fmtPct(trend.delta)}`,
          detail: trend.delta == null ? "Minimaal twee toetsen nodig" : "Over alle gekozen toetsen",
          tone: trend.delta == null ? "" : Number(trend.delta) >= 0 ? "green" : "red",
        },
        {
          title: "Recente ontwikkeling",
          value: trend.recent_delta == null ? "-" : `${Number(trend.recent_delta) >= 0 ? "+" : ""}${fmtPct(trend.recent_delta)}`,
          detail: trend.recent_delta == null ? "Minimaal twee toetsen nodig" : "Verschil tussen vorige en huidige toets",
          tone: trend.recent_delta == null ? "" : Number(trend.recent_delta) >= 0 ? "green" : "red",
        },
        {
          title: "Stabiliteit",
          value: trend.stability == null ? "-" : `${Math.round(Number(trend.stability))} punten`,
          detail: trend.stability == null ? "Nog te weinig toetsen" : "Hoe lager, hoe gelijkmatiger",
          tone: trend.stability == null ? "" : Number(trend.stability) <= 10 ? "green" : Number(trend.stability) <= 15 ? "amber" : "red",
        },
        {
          title: "Positie in groep",
          value: trend.percentile_delta == null ? "-" : `${Number(trend.percentile_delta) >= 0 ? "+" : ""}${Math.round(Number(trend.percentile_delta))}%`,
          detail: trend.percentile_delta == null ? "Nog te weinig toetsen" : "Verandering vergeleken met klasgenoten",
          tone: trend.percentile_delta == null ? "" : Number(trend.percentile_delta) >= 0 ? "green" : "red",
        },
      ];
      if (strongest) {
        cards.push({
          title: "Sterk onderdeel",
          value: strongest.category,
          detail: `${strongest.dimension_title} · ${fmtPct(strongest.percentage)}`,
          tone: "green",
        });
      }
      if (weakest) {
        cards.push({
          title: "Aandachtspunt",
          value: weakest.category,
          detail: `${weakest.dimension_title} · ${fmtPct(weakest.percentage)}`,
          tone: Number(weakest.percentage) >= 55 ? "amber" : "red",
        });
      }
      if (studentResits.length) {
        cards.push({
          title: "Herkansing leerling",
          value: `${meanResitDelta >= 0 ? "+" : ""}${fmtPct(meanResitDelta)}`,
          detail: `${studentResits.length} gekoppelde herkansing(en)`,
          tone: meanResitDelta >= 0 ? "green" : "red",
        });
      }
      return cards;
    }

    function renderOverview(mode = activeTab, studentId = highlightedStudent) {
      const cards = mode === "student" ? studentOverviewCards(studentId) : (data.overview || []);
      document.getElementById("overviewCards").innerHTML = cards.map(card => `
        <article class="card overview-card ${esc(card.tone || "")}">
          <div class="overview-title">${esc(card.title)}</div>
          <div class="overview-value">${esc(card.value)}</div>
          <div class="overview-detail">${esc(card.detail)}</div>
        </article>
      `).join("");
      document.getElementById("overviewCards").style.display = cards.length ? "grid" : "none";
    }

    function renderSignals() {
      const signalHtml = signals => signals.map(signal => `
        <article class="signal ${esc(signal.tone || "")}">
          <div class="tag">${esc(signal.title)}</div>
          <div class="subject">${esc(signal.subject)}</div>
          <div class="detail">${esc(signal.detail)}</div>
        </article>
      `).join("") || "<div class='insight'>Er zijn nog geen signalen beschikbaar voor deze selectie.</div>";
      document.getElementById("studentSignalCards").innerHTML = signalHtml(data.student_signals || []);
      document.getElementById("groupSignalCards").innerHTML = signalHtml(data.group_signals || []);
    }

    function renderSignalList(targetId, signals, emptyText) {
      document.getElementById(targetId).innerHTML = signals.length
        ? signals.slice(0, 5).map(signal => `
            <article class="signal ${esc(signal.tone || "")}">
              <div class="tag">${esc(signal.title)}</div>
              <div class="subject">${esc(signal.subject)}</div>
              <div class="detail">${esc(signal.detail)}</div>
            </article>
          `).join("")
        : `<div class="insight">${esc(emptyText)}</div>`;
    }

    function selectedStudentAttendance(studentId) {
      return (data.attendance_issues || []).find(row => String(row.student_id) === String(studentId)) || null;
    }

    function buildStudentSignalGroups(student) {
      const trend = student.trend || {};
      const studentPoints = points.filter(point => String(point.student_id) === String(student.id));
      const strongest = studentPoints.length
        ? [...studentPoints].sort((a, b) => Number(b.percentage || 0) - Number(a.percentage || 0))[0]
        : null;
      const weakest = studentPoints.length
        ? [...studentPoints].sort((a, b) => Number(a.percentage || 0) - Number(b.percentage || 0))[0]
        : null;
      const strongestPoints = [...studentPoints].sort((a, b) => Number(b.percentage || 0) - Number(a.percentage || 0)).slice(0, 4);
      const weakestPoints = [...studentPoints].sort((a, b) => Number(a.percentage || 0) - Number(b.percentage || 0)).slice(0, 5);
      const dimensionTrendEntries = (student.dimension_trends || []).flatMap(dimension =>
        (dimension.entries || []).map(entry => ({...entry, dimensionTitle: dimension.title}))
      );
      const studentResits = (data.resits?.rows || []).filter(row => String(row.student_id) === String(student.id));
      const meanResitDelta = studentResits.length
        ? studentResits.reduce((sum, row) => sum + Number(row.delta_percentage || 0), 0) / studentResits.length
        : null;
      const attendance = selectedStudentAttendance(student.id);
      const totalTests = Number(data.summary?.test_count || 0);
      const positive = [];
      const notable = [];
      const improvements = [];

      if (Number(student.score_percentage) >= 70) {
        positive.push({title:"Sterk totaalbeeld", subject:fmtPct(student.score_percentage), detail:"Gemiddeld hoog over de gekozen toetsen.", tone:"green"});
      }
      if (trend.delta != null && Number(trend.delta) >= 10) {
        positive.push({title:"Duidelijke vooruitgang", subject:`${Number(trend.delta) >= 0 ? "+" : ""}${fmtPct(trend.delta)}`, detail:"Over alle gekozen toetsen.", tone:"green"});
      }
      if (trend.recent_delta != null && Number(trend.recent_delta) >= 10) {
        positive.push({title:"Recente groei", subject:`+${fmtPct(trend.recent_delta)}`, detail:"Tussen vorige en huidige toets.", tone:"green"});
      }
      if (trend.percentile_delta != null && Number(trend.percentile_delta) >= 10) {
        positive.push({title:"Sterkere positie", subject:`+${Math.round(Number(trend.percentile_delta))}%`, detail:"Hoger ten opzichte van klasgenoten.", tone:"green"});
      }
      strongestPoints.forEach(point => {
        if (Number(point.percentage) >= 70) {
          positive.push({
            title:`Sterk onderdeel: ${point.dimension_title}`,
            subject:point.category,
            detail:`${fmtPct(point.percentage)} van de punten · beter dan ${fmtPct(point.percentile)} van de leerlingen`,
            tone:"green"
          });
        }
      });
      dimensionTrendEntries
        .filter(entry => entry.delta != null && Number(entry.delta) >= 10)
        .sort((a, b) => Number(b.delta) - Number(a.delta))
        .slice(0, 3)
        .forEach(entry => positive.push({
          title:`Groei in ${entry.dimensionTitle}`,
          subject:entry.name,
          detail:`+${fmtPct(entry.delta)} over de gekozen toetsen.`,
          tone:"green"
        }));
      if (meanResitDelta != null && meanResitDelta > 0) {
        positive.push({title:"Herkansing hielp", subject:`+${fmtPct(meanResitDelta)}`, detail:`Gemiddeld verschil over ${studentResits.length} herkansing(en).`, tone:"green"});
      }

      if (attendance) {
        notable.push({title:"Niet alles gemaakt", subject:`${attendance.count} van ${attendance.total_tests}`, detail:`Meest voorkomend: ${statusLabel(attendance.most_common_status)}.`, tone:"amber"});
      }
      if (totalTests && Number(student.test_count || 0) < totalTests) {
        notable.push({title:"Minder toetsdata", subject:`${student.test_count} van ${totalTests} toetsen`, detail:"Daardoor is de ontwikkeling minder stevig te beoordelen.", tone:"amber"});
      }
      if (trend.stability != null && Number(trend.stability) >= 15) {
        notable.push({title:"Wisselend beeld", subject:`${Math.round(Number(trend.stability))} punten`, detail:"De resultaten verschillen sterk tussen toetsen.", tone:"amber"});
      }
      if (studentResits.length) {
        notable.push({title:"Herkansing meegenomen", subject:`${studentResits.length} keer`, detail:"In analyses telt het eindresultaat.", tone:"amber"});
      }
      if (student.percentile != null && Number(student.percentile) >= 90) {
        notable.push({title:"Hoog in de groep", subject:positionValue(student), detail:"Deze leerling hoort in deze selectie bij de hogere scores.", tone:"green"});
      }

      if (Number(student.score_percentage) < 55) {
        improvements.push({title:"Totaal onder 55%", subject:fmtPct(student.score_percentage), detail:"Gemiddeld onder de voldoendegrens op scorepercentage.", tone:"red"});
      }
      if (trend.delta != null && Number(trend.delta) <= -10) {
        improvements.push({title:"Dalende lijn", subject:fmtPct(trend.delta), detail:"Over alle gekozen toetsen.", tone:Number(trend.delta) <= -20 ? "red" : "amber"});
      }
      if (trend.recent_delta != null && Number(trend.recent_delta) <= -10) {
        improvements.push({title:"Recente terugval", subject:fmtPct(trend.recent_delta), detail:"Tussen vorige en huidige toets.", tone:Number(trend.recent_delta) <= -20 ? "red" : "amber"});
      }
      if (trend.percentile_delta != null && Number(trend.percentile_delta) <= -10) {
        improvements.push({title:"Positie zakt", subject:`${Math.round(Number(trend.percentile_delta))}%`, detail:"Lager ten opzichte van klasgenoten.", tone:Number(trend.percentile_delta) <= -20 ? "red" : "amber"});
      }
      weakestPoints.forEach(point => {
        if (Number(point.percentage) < 55) {
          improvements.push({
            title:`Oefenen: ${point.dimension_title}`,
            subject:point.category,
            detail:`${fmtPct(point.percentage)} van de punten · beter dan ${fmtPct(point.percentile)} van de leerlingen`,
            tone:Number(point.percentage) < 45 ? "red" : "amber"
          });
        }
      });
      dimensionTrendEntries
        .filter(entry => entry.delta != null && Number(entry.delta) <= -10)
        .sort((a, b) => Number(a.delta) - Number(b.delta))
        .slice(0, 3)
        .forEach(entry => improvements.push({
          title:`Terugval in ${entry.dimensionTitle}`,
          subject:entry.name,
          detail:`${fmtPct(entry.delta)} over de gekozen toetsen.`,
          tone:Number(entry.delta) <= -20 ? "red" : "amber"
        }));

      return {positive, notable, improvements};
    }

    function renderSelectedStudentSignals(studentId) {
      const student = students.find(candidate => String(candidate.id) === String(studentId));
      if (!student) {
        renderSignalList("studentPositiveCards", [], "Selecteer eerst een leerling.");
        renderSignalList("studentNotableCards", [], "Selecteer eerst een leerling.");
        renderSignalList("studentImprovementCards", [], "Selecteer eerst een leerling.");
        return;
      }
      const groups = buildStudentSignalGroups(student);
      renderSignalList("studentPositiveCards", groups.positive, "Geen duidelijke positieve uitschieter gevonden. Kijk vooral naar de grafieken voor nuance.");
      renderSignalList("studentNotableCards", groups.notable, "Geen opvallende bijzonderheden gevonden.");
      renderSignalList("studentImprovementCards", groups.improvements, "Geen duidelijk verbeterpunt gevonden binnen deze selectie.");
    }

    function trendColor(index) {
      const colors = ["#5b5ff1", "#2fa866", "#e99b22", "#e24a4a", "#35a7b8", "#8a63d2", "#65758b"];
      return colors[index % colors.length];
    }

    function statusLabel(status) {
      const labels = {
        "niet analyseren": "Niet analyseren",
        "niet gemaakt": "Niet gemaakt",
        "absent": "Absent",
        "ziek": "Ziek",
        "geoorloofd afwezig": "Geoorloofd afwezig",
        "ongeoorloofd afwezig": "Ongeoorloofd afwezig",
        "vrijstelling": "Vrijstelling",
        "ongeldig": "Ongeldig",
        "onregelmatigheid": "Onregelmatigheid",
      };
      return labels[String(status || "").toLowerCase()] || String(status || "-");
    }

    function renderAttendanceIssues() {
      const rows = data.attendance_issues || [];
      document.getElementById("attendanceRows").innerHTML = rows.length
        ? rows.slice(0, 30).map(row => {
            const tests = (row.tests || []).slice(0, 4).map(test =>
              `${esc(test.name)} (${esc(statusLabel(test.status))})`
            ).join("<br>");
            const more = (row.tests || []).length > 4 ? `<br><span style="color:#6b7890">+${row.tests.length - 4} meer</span>` : "";
            return `
              <tr>
                <td>${esc(row.student_name)}</td>
                <td><span class="pill amber">${esc(row.count)} van ${esc(row.total_tests)}</span></td>
                <td>${esc(statusLabel(row.most_common_status))}</td>
                <td>${tests}${more}</td>
              </tr>
            `;
          }).join("")
        : "<tr><td colspan='4'>Geen leerlingen gevonden die in deze selectie vaak afwezig waren of de toets niet hebben gemaakt.</td></tr>";
    }

    function nonNullValues(series) {
      return (series || []).map(item => item.percentage).filter(value => value != null && !Number.isNaN(Number(value))).map(Number);
    }

    function renderTrendLines(targetId, entries, titlePrefix = "") {
      const traces = (entries || []).map((entry, index) => ({
        type: "scatter",
        mode: "lines+markers",
        name: entry.name,
        x: (entry.series || []).map((_point, pointIndex) => pointIndex),
        y: (entry.series || []).map(point => point.percentage),
        connectgaps: false,
        customdata: (entry.series || []).map(point => [point.test_name, point.period, point.school_year, point.student_count]),
        line: {color: trendColor(index), width: 2.5},
        marker: {size: 8, color: trendColor(index), line: {color: "#fff", width: 1}},
        hovertemplate: `<b>${esc(titlePrefix)}${esc(entry.name)}</b><br>%{customdata[0]}<br>%{y:.0f}% van punten<extra></extra>`,
      }));
      const firstEntry = entries?.[0];
      const ticktext = (firstEntry?.series || []).map(point => esc(shortLabel(point.test_name, 14)));
      const tickvals = ticktext.map((_label, index) => index);
      safePlot(targetId, traces, {
        margin:{l:42,r:16,t:18,b:84},
        paper_bgcolor:"rgba(0,0,0,0)",
        plot_bgcolor:"#fff",
        hovermode:"closest",
        showlegend:true,
        legend:{orientation:"h", x:.5, xanchor:"center", y:-.35},
        xaxis:{tickmode:"array", tickvals, ticktext, tickangle:-24, automargin:true, gridcolor:"#edf2f8"},
        yaxis:{range:[0,100], ticksuffix:"%", gridcolor:"#dfe7f2"},
      });
    }

    function showExportResult(rawResponse) {
      let response = {};
      try { response = JSON.parse(rawResponse || "{}"); } catch (error) { response = {ok:false, message:String(rawResponse || error)}; }
      if (response.cancelled) return;
      alert(response.message || (response.ok ? "Export opgeslagen." : "Export mislukt."));
    }

    function exportDevelopmentReport(kind) {
      if (!developmentBridge) {
        alert("De exportkoppeling is nog niet beschikbaar. Probeer het scherm opnieuw te openen.");
        return;
      }
      const studentId = document.getElementById("studentSelect")?.value || "";
      developmentBridge.exportDevelopmentReport(kind, String(studentId), showExportResult);
    }

    function pointTrace(list, color, name) {
      return {
        type: "scatter",
        mode: "markers",
        name,
        x: list.map(point => point.plot_x_jitter ?? point.x_jitter),
        y: list.map(point => point.percentage),
        customdata: list.map(point => [
          point.student_id,
          point.student_name,
          point.dimension_title,
          point.category,
          point.achieved,
          point.possible,
          point.percentile,
          point.top_percentage,
          point.test_count,
          point.tied_count,
        ]),
        marker: {
          size: 9,
          color,
          opacity: .68,
          line: {color: "#ffffff", width: 1.2},
        },
        hovertemplate:
          "<b>%{customdata[1]}</b><br>" +
          "%{customdata[2]}: %{customdata[3]}<br>" +
          "%{y:.0f}% van de punten<br>" +
          "%{customdata[4]:.1f} / %{customdata[5]:.1f} punten<br>" +
          "Beter dan %{customdata[6]}% van de leerlingen<br>" +
          "%{customdata[9]:.0f} leerling(en) op deze positie<br>" +
          "%{customdata[8]} toets(en)<extra></extra>",
      };
    }

    function lineDataForStudent(studentId) {
      return currentProfilePoints()
        .filter(point => String(point.student_id) === String(studentId))
        .sort((left, right) => Number(left.plot_x) - Number(right.plot_x));
    }

    function highlightStudent(studentId) {
      if (!studentId) return;
      highlightedStudent = String(studentId);
      const selected = lineDataForStudent(studentId);
      Plotly.restyle("profileChart", {
        x: [selected.map(point => point.plot_x_jitter ?? point.x_jitter)],
        y: [selected.map(point => point.percentage)],
        customdata: [selected.map(point => [
          point.student_id,
          point.student_name,
          point.dimension_title,
          point.category,
          point.achieved,
          point.possible,
          point.percentile,
          point.top_percentage,
          point.test_count,
          point.tied_count,
        ])],
        name: [selected.length ? selected[0].student_name : "Geselecteerde leerling"],
      }, [2]);
      const select = document.getElementById("studentSelect");
      if (select.value !== String(studentId)) select.value = String(studentId);
      renderStudentDetails(studentId);
      if (activeTab === "student") renderOverview("student", studentId);
      const name = selected.length ? selected[0].student_name : "";
      const dimension = currentProfileDimension();
      document.getElementById("profileInsight").innerHTML =
        selected.length
          ? `<b>${esc(name)}</b> is met een stippellijn verbonden binnen <b>${esc(dimension?.title || "het gekozen onderdeel")}</b>. Groen betekent minimaal 55% van de punten; rood daaronder.`
          : "Selecteer of hover over een leerling om de profielroute zichtbaar te maken.";
    }

    function renderProfileChart() {
      const chartPoints = currentProfilePoints();
      const categories = currentProfileCategories();
      const dimension = currentProfileDimension();
      if (!chartPoints.length || !categories.length) {
        safePlot("profileChart", [], {
          annotations:[{text:"Geen gegevens voor dit onderdeel.", showarrow:false, x:.5, y:.5, xref:"paper", yref:"paper"}],
          paper_bgcolor:"rgba(0,0,0,0)",
          plot_bgcolor:"#fff",
        });
        return;
      }
      const sufficient = chartPoints.filter(point => point.sufficient);
      const insufficient = chartPoints.filter(point => !point.sufficient);
      const tickvals = categories.map((_category, index) => index);
      const ticktext = categories.map(category => esc(shortLabel(category.label, 18)));
      const shapes = [
        {type:"line", x0: -0.6, x1: Math.max(...tickvals, 0) + .6, y0:55, y1:55, xref:"x", yref:"y", line:{color:"#9aa8bd", width:1, dash:"dash"}},
      ];
      const annotations = [{
        x:.5, y:1.1, xref:"paper", yref:"paper", text:`<b>${esc(dimension?.title || "Onderdeel")}</b>`,
        showarrow:false, font:{size:13, color:"#40516a"}, align:"center",
      }];
      const traces = [
        pointTrace(insufficient, "#e24a4a", "Onder 55%"),
        pointTrace(sufficient, "#2fa866", "55% of hoger"),
        {
          type:"scatter",
          mode:"lines+markers",
          name:"Geselecteerde leerling",
          x:[],
          y:[],
          customdata:[],
          line:{color:"#5b5ff1", width:3, dash:"dot"},
          marker:{size:12, color:"#5b5ff1", line:{color:"#fff", width:2}},
          hovertemplate:
            "<b>%{customdata[1]}</b><br>%{customdata[2]}: %{customdata[3]}<br>%{y:.0f}% van de punten<extra></extra>",
        },
      ];
      const selectedId = highlightedStudent || document.getElementById("studentSelect")?.value;
      safePlot("profileChart", traces, {
        margin:{l:52,r:20,t:72,b:105},
        paper_bgcolor:"rgba(0,0,0,0)",
        plot_bgcolor:"#fff",
        hovermode:"closest",
        showlegend:false,
        xaxis:{tickmode:"array", tickvals, ticktext, tickangle:-28, gridcolor:"#edf2f8", zeroline:false, automargin:true},
        yaxis:{title:"% van de punten", range:[0,100], ticksuffix:"%", gridcolor:"#dfe7f2", zeroline:false},
        shapes,
        annotations,
      }).then(() => {
        const chart = document.getElementById("profileChart");
        chart.removeAllListeners?.("plotly_hover");
        chart.on("plotly_hover", event => {
          const custom = event.points?.[0]?.customdata;
          if (custom && custom[0] != null) highlightStudent(custom[0]);
        });
        if (selectedId) highlightStudent(selectedId);
      });
    }

    function populateProfileDimensionControls() {
      const select = document.getElementById("profileDimensionSelect");
      const dimensions = profileDimensions();
      select.innerHTML = dimensions.map(dimension => `<option value="${esc(dimension.key)}">${esc(dimension.title)}</option>`).join("");
      if (dimensions.length) {
        currentProfileDimensionKey = String(dimensions[0].key);
        select.value = currentProfileDimensionKey;
      }
      select.addEventListener("change", () => {
        currentProfileDimensionKey = select.value;
        renderProfileChart();
      });
    }

    function populateStudentControls() {
      const select = document.getElementById("studentSelect");
      select.innerHTML = students.map(student => `<option value="${student.id}">${esc(student.name)}</option>`).join("");
      select.addEventListener("change", () => highlightStudent(select.value));
      document.getElementById("studentSearch").addEventListener("input", event => {
        const query = event.target.value.trim().toLowerCase();
        const matches = students.filter(student => student.name.toLowerCase().includes(query));
        select.innerHTML = matches.map(student => `<option value="${student.id}">${esc(student.name)}</option>`).join("");
        if (matches.length) highlightStudent(matches[0].id);
      });
      if (students.length) highlightStudent(students[0].id);
    }

    function renderStudentDetails(studentId) {
      const student = students.find(candidate => String(candidate.id) === String(studentId));
      if (!student) return;
      const trend = student.trend || {};
      const trendToneClass = value => {
        if (value == null || Number.isNaN(Number(value))) return "";
        if (Number(value) >= 5) return "green";
        if (Number(value) <= -5) return "red";
        return "amber";
      };
      const stabilityToneClass = value => {
        if (value == null || Number.isNaN(Number(value))) return "";
        if (Number(value) <= 10) return "green";
        if (Number(value) <= 15) return "amber";
        return "red";
      };
      const trendCards = [
        ["Over alle toetsen", signedPct(trend.delta), "hele selectie", trendToneClass(trend.delta)],
        ["Sinds vorige toets", signedPct(trend.recent_delta), "vorige naar huidige", trendToneClass(trend.recent_delta)],
        ["Positie in groep", signedPct(trend.percentile_delta), "vergeleken met klasgenoten", trendToneClass(trend.percentile_delta)],
        ["Stabiliteit", trend.stability == null ? "-" : `${Math.round(Number(trend.stability))} punten`, "lager is gelijkmatiger", stabilityToneClass(trend.stability)],
      ];
      document.getElementById("studentDetails").innerHTML = `
        <h2 style="margin:10px 0 4px">${esc(student.name)}</h2>
        <div class="student-card">
          <div class="mini"><div class="label">% van punten</div><div class="value">${fmtPct(student.score_percentage)}</div></div>
          <div class="mini"><div class="label">Gem. cijfer</div><div class="value">${fmtNum(student.mean_grade)}</div></div>
          <div class="mini"><div class="label">Toetsen</div><div class="value">${student.test_count}</div></div>
          <div class="mini"><div class="label">Positie</div><div class="value">${esc(positionValue(student))}</div><div class="note">${esc(positionDetail(student))}</div></div>
        </div>
        <div class="student-trend-grid">
          ${trendCards.map(([label, value, note, tone]) => `
            <div class="mini trend-mini ${esc(tone)}">
              <div class="label">${esc(label)}</div>
              <div class="value">${esc(value)}</div>
              <div class="note">${esc(note)}</div>
            </div>
          `).join("")}
        </div>
      `;
      const rows = (student.tests || []).map(test => `
        <tr>
          <td>${esc(test.name)}<br><span style="color:#6b7890">${esc(test.school_year)} · ${esc(test.period)} · weging ${fmtNum(test.weight)}${test.is_resit ? " · herkansing" : ""}</span></td>
          <td>${fmtPct(test.score_percentage)}</td>
          <td>${fmtNum(test.grade)}</td>
        </tr>
      `).join("");
      document.getElementById("studentTests").innerHTML = rows || "<tr><td colspan='3'>Geen toetsgegevens.</td></tr>";
      const studentTests = student.tests || [];
      const xValues = studentTests.map((_test, index) => index);
      const lowerBand = studentTests.map(test => test.group_min_score_percentage);
      const upperBand = studentTests.map(test => test.group_max_score_percentage);
      const groupMeans = studentTests.map(test => test.group_mean_score_percentage);
      const traces = [
        {
          type:"scatter", mode:"lines",
          x:xValues,
          y:lowerBand,
          line:{width:0},
          hoverinfo:"skip",
          showlegend:false,
        },
        {
          type:"scatter", mode:"lines",
          name:"Groepsbandbreedte",
          x:xValues,
          y:upperBand,
          fill:"tonexty",
          fillcolor:"rgba(91, 95, 241, .11)",
          line:{width:0},
          hoverinfo:"skip",
        },
        {
          type:"scatter", mode:"lines+markers",
          name:"Groepsgemiddelde",
          x:xValues,
          y:groupMeans,
          line:{color:"#9aa8bd", width:2, dash:"dash"},
          marker:{size:7, color:"#9aa8bd"},
          hovertemplate:"Groepsgemiddelde<br>%{y:.0f}% van punten<extra></extra>",
        },
        {
        type:"scatter", mode:"lines+markers",
        name:student.name,
        x:xValues,
        y:studentTests.map(test => test.score_percentage),
        customdata:studentTests.map(test => [test.name, test.school_year, test.period, test.weight, test.grade]),
        line:{color:"#5b5ff1", width:2},
        marker:{
          size:studentTests.map(test => markerSizeForWeight(test.weight)),
          color:studentTests.map(test => markerColorForWeight(test.weight)),
          line:{color:"#ffffff", width:1.5},
        },
        hovertemplate:"<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>%{y:.0f}% van punten<br>Weging: %{customdata[3]}<br>Cijfer: %{customdata[4]:.1f}<extra></extra>",
      }];
      safePlot("studentTestChart", traces, {
        margin:{l:42,r:10,t:18,b:86},
        paper_bgcolor:"rgba(0,0,0,0)",
        plot_bgcolor:"#fff",
        showlegend:true,
        legend:{orientation:"h", x:.5, xanchor:"center", y:-.35},
        xaxis:{
          tickmode:"array",
          tickvals:studentTests.map((_test, index) => index),
          ticktext:studentTests.map(test => esc(shortLabel(test.name, 16))),
          tickangle:-24,
          automargin:true,
          gridcolor:"#edf2f8",
        },
        yaxis:{range:[0,100], ticksuffix:"%", gridcolor:"#dfe7f2"},
      });
      document.getElementById("studentTrendInsight").innerHTML =
        trend.delta == null
          ? "Voor trendinformatie zijn minimaal twee toetsen nodig."
          : `<b>${esc(student.name)}</b>: ${Number(trend.delta) >= 0 ? "+" : ""}${fmtPct(trend.delta)} over alle gekozen toetsen. De grijze band toont de laagste en hoogste groepsscore per toets.`;
      renderStudentPercentileChart(student);
      renderStudentDimensionTrendChart(student);
      renderSelectedStudentSignals(student.id);
    }

    function renderStudentPercentileChart(student) {
      const tests = student.tests || [];
      safePlot("studentPercentileChart", [{
        type:"scatter",
        mode:"lines+markers",
        name:"Positie in de groep",
        x:tests.map((_test, index) => index),
        y:tests.map(test => test.percentile),
        customdata:tests.map(test => [test.name, test.period, test.score_percentage]),
        line:{color:"#5b5ff1", width:2.5},
        marker:{size:9, color:"#5b5ff1", line:{color:"#fff", width:1.5}},
        hovertemplate:"<b>%{customdata[0]}</b><br>Beter dan %{y:.0f}% van de leerlingen<br>Score: %{customdata[2]:.0f}%<extra></extra>",
      }], {
        margin:{l:42,r:12,t:18,b:72},
        paper_bgcolor:"rgba(0,0,0,0)",
        plot_bgcolor:"#fff",
        xaxis:{
          tickmode:"array",
          tickvals:tests.map((_test, index) => index),
          ticktext:tests.map(test => esc(shortLabel(test.name, 14))),
          tickangle:-24,
          automargin:true,
          gridcolor:"#edf2f8",
        },
        yaxis:{range:[0,100], title:"Beter dan ...%", ticksuffix:"%", gridcolor:"#dfe7f2"},
      });
      const trend = student.trend || {};
      document.getElementById("studentPercentileInsight").innerHTML =
        trend.percentile_delta == null
          ? "Voor deze positieontwikkeling zijn minimaal twee toetsen met groepsdata nodig."
          : `Positie in de groep: ${Number(trend.percentile_delta) >= 0 ? "+" : ""}${Math.round(Number(trend.percentile_delta))}% verschil over de gekozen toetsen.`;
    }

    function renderStudentDimensionTrendChart(student) {
      const dimensions = student.dimension_trends || [];
      const select = document.getElementById("studentTrendDimensionSelect");
      const previous = select.value;
      select.innerHTML = dimensions.map((dimension, index) => `<option value="${index}">${esc(dimension.title)}</option>`).join("");
      if (previous && Number(previous) < dimensions.length) select.value = previous;
      select.onchange = () => renderStudentDimensionTrendChart(student);
      const dimension = dimensions[Number(select.value || 0)];
      if (!dimension) {
        safePlot("studentDimensionTrendChart", [], {
          annotations:[{text:"Geen ontwikkeling per onderdeel voor deze leerling.", showarrow:false, x:.5, y:.5, xref:"paper", yref:"paper"}],
          paper_bgcolor:"rgba(0,0,0,0)",
          plot_bgcolor:"#fff",
        });
        document.getElementById("studentDimensionTrendInsight").textContent = "Geen gegevens beschikbaar.";
        return;
      }
      renderTrendLines("studentDimensionTrendChart", dimension.entries || [], "");
      const entries = (dimension.entries || []).filter(entry => entry.delta != null);
      const strongest = entries.length ? [...entries].sort((a,b)=>Number(b.delta)-Number(a.delta))[0] : null;
      const weakest = entries.length ? [...entries].sort((a,b)=>Number(a.delta)-Number(b.delta))[0] : null;
      document.getElementById("studentDimensionTrendInsight").innerHTML =
        strongest && weakest
          ? `<b>${esc(dimension.title)}</b>: sterkste ontwikkeling ${esc(strongest.name)} (${Number(strongest.delta) >= 0 ? "+" : ""}${fmtPct(strongest.delta)}), aandachtspunt ${esc(weakest.name)} (${Number(weakest.delta) >= 0 ? "+" : ""}${fmtPct(weakest.delta)}).`
          : `Voor <b>${esc(dimension.title)}</b> is nog te weinig trenddata.`;
    }

    function renderGroupDimensionChart() {
      const dimensions = data.group_dimensions || [];
      const select = document.getElementById("dimensionSelect");
      select.innerHTML = dimensions.map((dimension, index) => `<option value="${index}">${esc(dimension.title)}</option>`).join("");
      const draw = () => {
        const dimension = dimensions[Number(select.value || 0)];
        if (!dimension) return;
        const entries = [...(dimension.entries || [])].sort((a,b)=>Number(a.percentage||0)-Number(b.percentage||0));
        const strongest = [...entries].sort((a,b)=>Number(b.percentage||0)-Number(a.percentage||0))[0];
        const weakest = entries[0];
        document.getElementById("groupDimensionInsight").innerHTML =
          strongest && weakest
            ? `Sterkste onderdeel: <b>${esc(strongest.name)}</b> (${fmtPct(strongest.percentage)}). Aandachtspunt: <b>${esc(weakest.name)}</b> (${fmtPct(weakest.percentage)}).`
            : "Nog onvoldoende data voor een samenvatting.";
        safePlot("groupDimensionChart", [{
          type:"bar", orientation:"h",
          y:entries.map(entry => entry.name),
          x:entries.map(entry => entry.percentage),
          width:0.48,
          text:entries.map(entry => fmtPct(entry.percentage)),
          textposition:"outside",
          marker:{color:entries.map(entry => Number(entry.percentage) >= 55 ? "#2fa866" : "#e24a4a")},
          hovertemplate:"%{y}<br>%{x:.0f}% van punten<extra></extra>",
        }], {
          margin:{l:150,r:42,t:18,b:42},
          bargap:.42,
          paper_bgcolor:"rgba(0,0,0,0)",
          plot_bgcolor:"#fff",
          xaxis:{range:[0,100], ticksuffix:"%", gridcolor:"#dfe7f2"},
          yaxis:{automargin:true},
        });
      };
      select.addEventListener("change", draw);
      draw();
    }

    function renderGroupDimensionTrendChart() {
      const dimensions = data.dimension_trends || [];
      const select = document.getElementById("groupTrendDimensionSelect");
      select.innerHTML = dimensions.map((dimension, index) => `<option value="${index}">${esc(dimension.title)}</option>`).join("");
      const draw = () => {
        const dimension = dimensions[Number(select.value || 0)];
        if (!dimension) {
          safePlot("groupDimensionTrendChart", [], {
            annotations:[{text:"Geen ontwikkeling per onderdeel beschikbaar.", showarrow:false, x:.5, y:.5, xref:"paper", yref:"paper"}],
            paper_bgcolor:"rgba(0,0,0,0)",
            plot_bgcolor:"#fff",
          });
          document.getElementById("groupDimensionTrendInsight").textContent = "Voeg meerdere toetsen met hetzelfde onderdeeltype toe om ontwikkeling te zien.";
          return;
        }
        renderTrendLines("groupDimensionTrendChart", dimension.entries || [], "");
        const entries = (dimension.entries || []).filter(entry => entry.delta != null);
        const strongest = entries.length ? [...entries].sort((a,b)=>Number(b.delta)-Number(a.delta))[0] : null;
        const weakest = entries.length ? [...entries].sort((a,b)=>Number(a.delta)-Number(b.delta))[0] : null;
        document.getElementById("groupDimensionTrendInsight").innerHTML =
          strongest && weakest
            ? `<b>${esc(dimension.title)}</b>: sterkste stijging ${esc(strongest.name)} (${Number(strongest.delta) >= 0 ? "+" : ""}${fmtPct(strongest.delta)}), grootste daling ${esc(weakest.name)} (${Number(weakest.delta) >= 0 ? "+" : ""}${fmtPct(weakest.delta)}).`
            : `Voor <b>${esc(dimension.title)}</b> is nog te weinig trenddata.`;
      };
      select.onchange = draw;
      draw();
    }

    function studentTrendSeries(student, tests) {
      const byTest = new Map((student.tests || []).map(test => [String(test.logical_test_id || test.test_id), test]));
      const y = tests.map(test => {
        const item = byTest.get(String(test.test_id));
        return item && item.score_percentage != null ? Number(item.score_percentage) : null;
      });
      const values = y.filter(value => value != null && Number.isFinite(Number(value))).map(Number);
      const first = values.length ? values[0] : null;
      const last = values.length ? values[values.length - 1] : null;
      const previous = values.length >= 2 ? values[values.length - 2] : null;
      const current = last;
      const delta = values.length >= 2 ? last - first : null;
      const recent = values.length >= 2 ? current - previous : null;
      return {student, y, values, first, last, previous, current, delta, recent, count: values.length};
    }

    function trendToneForDelta(delta) {
      if (delta == null || Math.abs(Number(delta)) < 5) return "stable";
      return Number(delta) > 0 ? "rising" : "falling";
    }

    function trendColorForTone(tone) {
      if (tone === "rising") return "#2fa866";
      if (tone === "falling") return "#e24a4a";
      return "#8a98ad";
    }

    function signedPct(value) {
      if (value == null || Number.isNaN(Number(value))) return "-";
      return `${Number(value) >= 0 ? "+" : ""}${Math.round(Number(value))}%`;
    }

    function studentTrendStatus(series) {
      if (Number(series.current) < 55 || Number(series.recent) <= -10) {
        return {label:"Aandacht", tone:"amber"};
      }
      if (Number(series.recent) >= 5) return {label:"Vooruitgang", tone:"green"};
      if (Number(series.recent) <= -5) return {label:"Terugval", tone:"red"};
      return {label:"Stabiel", tone:""};
    }

    function sparkline(values, color) {
      const usable = (values || []).filter(value => value != null && Number.isFinite(Number(value))).map(Number);
      if (usable.length < 2) return "-";
      const width = 82;
      const height = 24;
      const pointsText = usable.map((value, index) => {
        const x = usable.length === 1 ? width / 2 : index / (usable.length - 1) * width;
        const y = height - Math.max(0, Math.min(100, value)) / 100 * height;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ");
      return `<svg class="sparkline" viewBox="0 0 ${width} ${height}" aria-hidden="true">
        <polyline fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${pointsText}"></polyline>
      </svg>`;
    }

    function renderStudentTrendOverviewChart() {
      const tests = data.test_summaries || [];
      const filter = document.getElementById("studentTrendOverviewFilter")?.value || "all";
      const sortMode = document.getElementById("studentTrendOverviewSort")?.value || "recentDesc";
      const allSeries = students
        .map(student => studentTrendSeries(student, tests))
        .filter(series => series.count >= 2);
      const visibleSeries = allSeries.filter(series => {
        if (filter === "rising") return Number(series.recent) >= 5;
        if (filter === "falling") return Number(series.recent) <= -5;
        if (filter === "attention") return Number(series.current) < 55 || Number(series.recent) <= -10;
        return true;
      });
      const rising = allSeries.filter(series => Number(series.recent) >= 5).length;
      const falling = allSeries.filter(series => Number(series.recent) <= -5).length;
      const stable = Math.max(0, allSeries.length - rising - falling);
      document.getElementById("studentTrendSummaryCards").innerHTML = [
        ["Vooruitgang", rising, "duidelijk hoger dan de vorige toets", "green"],
        ["Stabiel", stable, "ongeveer gelijk gebleven", "amber"],
        ["Terugval", falling, "duidelijk lager dan de vorige toets", "red"],
      ].map(([label, value, note, tone]) => `
        <article class="trend-summary-card ${tone}">
          <div class="label">${esc(label)}</div>
          <div class="value">${esc(value)}</div>
          <div class="note">${esc(note)}</div>
        </article>
      `).join("");

      if (!tests.length || !visibleSeries.length) {
        document.getElementById("studentTrendOverviewRows").innerHTML =
          "<tr><td colspan='6'>Nog te weinig leerlingontwikkeling om te tonen.</td></tr>";
        document.getElementById("studentTrendOverviewInsight").textContent =
          "Deze weergave heeft minimaal twee toetsen met resultaten per leerling nodig.";
        return;
      }

      const sortedRows = [...visibleSeries].sort((a, b) => {
        if (sortMode === "recentAsc") return Number(a.recent || 0) - Number(b.recent || 0);
        if (sortMode === "currentDesc") return Number(b.current || 0) - Number(a.current || 0);
        if (sortMode === "name") return String(a.student.name).localeCompare(String(b.student.name), "nl");
        return Number(b.recent || 0) - Number(a.recent || 0);
      });

      document.getElementById("studentTrendOverviewRows").innerHTML = sortedRows.map(series => {
        const status = studentTrendStatus(series);
        const color = trendColorForTone(trendToneForDelta(series.recent));
        return `
          <tr>
            <td>${esc(series.student.name)}</td>
            <td>${fmtPct(series.previous)}</td>
            <td>${fmtPct(series.current)}</td>
            <td><b>${signedPct(series.recent)}</b></td>
            <td>${sparkline(series.values, color)}</td>
            <td><span class="pill ${esc(status.tone)}">${esc(status.label)}</span></td>
          </tr>
        `;
      }).join("");

      document.getElementById("studentTrendOverviewInsight").innerHTML =
        `De tabel vergelijkt steeds de vorige en huidige toets. De mini-trend laat alle toetsen in deze selectie zien.`;
    }

    function renderTestAndResits() {
      const tests = data.test_summaries || [];
      safePlot("testTrendChart", [{
        type:"scatter", mode:"lines+markers",
        x:tests.map((_test, index) => index),
        y:tests.map(test => test.mean_score_percentage),
        customdata:tests.map(test => [test.name, test.school_year, test.period, test.weight, test.participant_count]),
        line:{color:"#5b5ff1", width:2},
        marker:{
          size:tests.map(test => markerSizeForWeight(test.weight)),
          color:tests.map(test => markerColorForWeight(test.weight)),
          line:{color:"#ffffff", width:1.5},
        },
        hovertemplate:"<b>%{customdata[0]}</b><br>%{customdata[1]} · %{customdata[2]}<br>Gemiddeld %{y:.0f}%<br>Weging: %{customdata[3]}<br>Leerlingen: %{customdata[4]}<extra></extra>",
      }], {
        margin:{l:42,r:10,t:16,b:92},
        paper_bgcolor:"rgba(0,0,0,0)",
        plot_bgcolor:"#fff",
        xaxis:{
          tickmode:"array",
          tickvals:tests.map((_test, index) => index),
          ticktext:tests.map(test => esc(shortLabel(test.name, 16))),
          tickangle:-24,
          automargin:true,
          gridcolor:"#edf2f8",
        },
        yaxis:{range:[0,100], ticksuffix:"%", gridcolor:"#dfe7f2"},
      });
      document.getElementById("testRows").innerHTML = tests.map(test => `
        <tr><td>${esc(test.name)}<br><span style="color:#6b7890">${esc(test.school_year)} · ${esc(test.period)} · weging ${fmtNum(test.weight)}</span></td><td>${fmtPct(test.mean_score_percentage)}</td><td>${test.participant_count}</td></tr>
      `).join("") || "<tr><td colspan='3'>Geen toetsen.</td></tr>";

      const resits = data.resits || {rows:[]};
      const resitRows = Array.isArray(resits.rows) ? resits.rows : [];
      const resitSection = document.getElementById("resitSection");
      if (resitSection) {
        resitSection.style.display = resitRows.length ? "" : "none";
      }
      document.getElementById("resitSummary").textContent =
        `${resitRows.length || 0} herkansingen · gemiddeld ${fmtPct(resits.mean_delta_percentage)} verschil`;
      const improved = Number(resits.improved_count || 0);
      const total = Number(resitRows.length || 0);
      const declined = Math.max(0, total - improved);
      document.getElementById("resitMetrics").innerHTML = [
        ["Aantal herkansingen", total, "gekoppelde afnames"],
        ["Verbeterd", improved, `${total ? Math.round(improved / total * 100) : 0}% van herkansers`],
        ["Niet verbeterd", declined, "zelfde of lager"],
        ["Gem. verschil", fmtPct(resits.mean_delta_percentage), "scorepercentage"],
      ].map(([label, value, note]) => `
        <div class="mini"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div><div class="note">${esc(note)}</div></div>
      `).join("");
      document.getElementById("resitRows").innerHTML = resitRows.slice(0, 80).map(row => `
        <tr>
          <td>${esc(row.student_name)}</td>
          <td>${fmtPct(row.original_percentage)}<br><span style="color:#6b7890">${esc(row.original_test)}</span></td>
          <td>${fmtPct(row.resit_percentage)}<br><span style="color:#6b7890">${esc(row.resit_test)}</span></td>
          <td><span class="pill ${Number(row.delta_percentage) >= 0 ? "green" : "red"}">${Number(row.delta_percentage) >= 0 ? "+" : ""}${fmtPct(row.delta_percentage)}</span></td>
          <td>${row.delta_grade == null ? "-" : (Number(row.delta_grade) >= 0 ? "+" : "") + fmtNum(row.delta_grade)}</td>
        </tr>
      `).join("") || "<tr><td colspan='5'>Geen gekoppelde herkansingen gevonden.</td></tr>";
    }

    function initTabs() {
      document.querySelectorAll(".tab").forEach(button => {
        button.addEventListener("click", () => {
          document.querySelectorAll(".tab").forEach(tab => tab.classList.remove("active"));
          document.querySelectorAll(".page-block").forEach(block => block.classList.remove("active"));
          button.classList.add("active");
          activeTab = button.dataset.tab;
          renderOverview(activeTab, document.getElementById("studentSelect")?.value || highlightedStudent);
          document.getElementById(button.dataset.tab).classList.add("active");
          setTimeout(() => {
            [
              "profileChart",
              "studentTestChart",
              "studentPercentileChart",
              "studentDimensionTrendChart",
              "groupDimensionChart",
              "groupDimensionTrendChart",
              "testTrendChart",
            ].forEach(id => {
              const element = document.getElementById(id);
              if (element) Plotly.Plots.resize(element);
            });
          }, 60);
        });
      });
      document.getElementById("exportGroupReport").addEventListener("click", () => exportDevelopmentReport("group"));
      document.getElementById("exportStudentReport").addEventListener("click", () => exportDevelopmentReport("student"));
    }

    renderKpis();
    renderOverview();
    renderSignals();
    renderAttendanceIssues();
    initTabs();
    if (!points.length) {
      document.getElementById("empty").style.display = "block";
    } else {
      populateProfileDimensionControls();
      renderProfileChart();
      populateStudentControls();
      renderGroupDimensionChart();
      renderGroupDimensionTrendChart();
      document.getElementById("studentTrendOverviewFilter")?.addEventListener("change", renderStudentTrendOverviewChart);
      document.getElementById("studentTrendOverviewSort")?.addEventListener("change", renderStudentTrendOverviewChart);
      renderStudentTrendOverviewChart();
      renderTestAndResits();
    }
  </script>
</body>
</html>
"""
    return html.replace("__DATA__", payload).replace("__PLOTLY__", plotly_asset)

