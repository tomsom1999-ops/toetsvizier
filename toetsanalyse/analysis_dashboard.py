from __future__ import annotations

import html
import json


def build_analysis_dashboard_html(data: dict[str, object], plotly_source: str) -> str:
    payload = json.dumps(data, ensure_ascii=True).replace("<", "\\u003c")
    source = html.escape(plotly_source, quote=True)
    subtest_context = data.get("subtest_context")
    has_subtest = bool(subtest_context)
    comparison_tab = '<button class="tab" data-tab="comparison">Vergelijking</button>' if has_subtest else ""
    comparison_view = """
  <section id="comparison" class="view">
    <div id="comparisonBanner" class="card analysis-scope-banner"></div>
    <div class="comparison-grid">
      <article class="card comparison-card">
        <h2 class="section-title">Deeltoets versus totaaltoets</h2>
        <div id="comparisonChart" class="comparison-chart"></div>
        <div class="chart-note">De balken tonen het gemiddelde percentage van deze deeltoets naast de hele toets.</div>
      </article>
      <article class="card comparison-card">
        <h2 class="section-title">Belangrijkste verschillen</h2>
        <div id="comparisonMetrics"></div>
      </article>
    </div>
  </section>
""" if has_subtest else ""
    scope_label = "Deeltoetsanalyse" if has_subtest else "Een toetsanalyse"
    scope_text = f"Deeltoets: {html.escape(str(subtest_context.get('name')), quote=False)}" if has_subtest else scope_label
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="{source}"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<style>
:root {{
  --bg:#f7f8fc; --card:#fff; --border:#e4e9f2; --navy:#17243c; --muted:#66748e;
  --primary:#6256ea; --primary-soft:#f0edff; --green:#2da65a; --green-soft:#eaf7ee;
  --orange:#e8941b; --orange-soft:#fff5e9; --red:#e64141; --red-soft:#fdeeee;
  --blue:#4e8bd8; --shadow:0 2px 10px rgba(25,39,64,.04);
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--navy); font:13px "Inter","Segoe UI",Arial,sans-serif; }}
.page {{ padding:18px; }}
.header {{ display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:12px; }}
h1 {{ font-size:23px; margin:0 0 5px; letter-spacing:-.02em; }}
.subtitle {{ color:var(--muted); }}
.scope {{ background:var(--primary-soft); color:var(--primary); padding:9px 14px; border-radius:9px; font-weight:600; }}
.tabs {{ display:flex; gap:28px; border-bottom:1px solid var(--border); margin-bottom:16px; }}
.tab {{
  background:none; border:0; padding:12px 4px 13px; color:var(--muted); cursor:pointer; font-weight:600;
  border-bottom:2px solid transparent;
}}
.tab.active {{ color:var(--primary); border-bottom-color:var(--primary); }}
.view {{ display:none; }}
.view.active {{ display:block; }}
.card {{ background:var(--card); border:1px solid var(--border); border-radius:12px; padding:14px; box-shadow:var(--shadow); }}
.kpis {{ display:grid; grid-template-columns:repeat(6,minmax(102px,1fr)); gap:8px; margin-bottom:10px; }}
.kpi {{ min-height:78px; padding:10px 13px; }}
.kpi-label {{ color:var(--muted); font-size:11px; }}
.kpi-value {{ font-size:20px; font-weight:650; margin:4px 0 2px; line-height:1.15; }}
.kpi-note {{ color:var(--muted); font-size:11px; }}
.kpi.green .kpi-value {{ color:var(--green); }}
.kpi.red .kpi-value {{ color:var(--red); }}
.subtest-insight {{ margin-bottom:10px; display:none; }}
.subtest-grid {{ display:grid; grid-template-columns:1.35fr repeat(4,minmax(105px,1fr)); gap:8px; align-items:stretch; }}
.subtest-title {{ font-size:15px; font-weight:700; margin-bottom:4px; }}
.subtest-copy {{ color:var(--muted); line-height:1.45; font-size:12px; }}
.subtest-metric {{ border:1px solid #edf1f7; background:#fcfdff; border-radius:10px; padding:10px 12px; }}
.subtest-metric strong {{ display:block; font-size:18px; margin-top:4px; }}
.analysis-scope-banner {{ margin-bottom:10px; }}
.analysis-scope-banner .analysis-scope-top {{ display:flex; justify-content:space-between; gap:14px; align-items:flex-start; }}
.analysis-scope-banner .analysis-scope-title {{ font-size:17px; font-weight:750; margin-bottom:4px; }}
.analysis-scope-banner .analysis-scope-note {{ color:var(--muted); line-height:1.45; font-size:12px; max-width:820px; }}
.analysis-scope-banner .analysis-scope-badge {{ background:var(--primary-soft); color:var(--primary); border-radius:999px; padding:5px 10px; font-weight:700; font-size:11px; white-space:nowrap; }}
.analysis-scope-banner .analysis-scope-grid {{ display:grid; grid-template-columns:repeat(4,minmax(110px,1fr)); gap:8px; margin-top:10px; }}
.analysis-scope-banner .analysis-scope-metric {{ border:1px solid #edf1f7; background:#fcfdff; border-radius:10px; padding:10px 12px; }}
.analysis-scope-banner .analysis-scope-metric strong {{ display:block; font-size:18px; margin-top:4px; }}
.comparison-grid {{ display:grid; grid-template-columns:minmax(360px,1.15fr) minmax(300px,.85fr); gap:10px; }}
.comparison-card {{ min-height:280px; }}
.comparison-chart {{ height:220px; }}
.comparison-list {{ display:grid; gap:8px; }}
.comparison-item {{ border:1px solid #edf1f7; background:#fcfdff; border-radius:10px; padding:10px 12px; }}
.comparison-item .label {{ color:var(--muted); font-size:11px; margin-bottom:3px; }}
.comparison-item .value {{ font-size:21px; font-weight:750; }}
.comparison-item .note {{ color:var(--muted); font-size:11px; line-height:1.45; margin-top:3px; }}
.general-grid {{ display:grid; grid-template-columns:minmax(715px,1.65fr) minmax(330px,.92fr); gap:10px; }}
.section-title {{ font-size:15px; font-weight:700; margin:0 0 13px; display:flex; align-items:center; gap:7px; overflow-wrap:anywhere; }}
.info {{ color:#8b96a9; font-size:12px; }}
.quality-grid {{ display:grid; grid-template-columns:repeat(5,minmax(116px,1fr)); gap:8px; margin-bottom:12px; }}
.quality {{ padding:11px 10px; border:1px solid #edf1f7; background:#fcfdff; border-radius:10px; min-height:126px; }}
.quality-name {{ color:var(--muted); font-size:11px; }}
.quality-value {{ font-size:21px; font-weight:650; margin:6px 0; }}
.quality-range {{ font-size:10px; margin-top:8px; color:var(--muted); }}
.quality-advice {{ font-size:10px; margin-top:4px; line-height:1.35; color:#53637e; }}
.badge {{ padding:3px 10px; display:inline-block; border-radius:7px; font-size:11px; font-weight:600; }}
.good {{ color:var(--green); background:var(--green-soft); }}
.excellent {{ color:#087f4b; background:#e3f6ec; }}
.attention {{ color:var(--orange); background:var(--orange-soft); }}
.bad {{ color:var(--red); background:var(--red-soft); }}
.overlap {{ color:var(--primary); background:var(--primary-soft); }}
.neutral {{ color:var(--muted); background:#f1f4f8; }}
.explanation {{
  border:1px solid #e7ecf5; background:#fafbfe; color:#53637e; line-height:1.55;
  border-radius:9px; padding:10px 12px; font-size:12px;
}}
.sample-warning {{
  border:1px solid #f0d49f; background:#fff8ed; color:#8a560c; line-height:1.45;
  border-radius:9px; padding:9px 11px; font-size:12px; margin-bottom:10px;
}}
.item-card {{ margin-top:10px; padding:0; overflow:hidden; }}
.item-head {{ padding:14px 15px 10px; }}
.table-wrap {{ max-height:390px; overflow:auto; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ position:sticky; top:0; background:#fafbfe; z-index:1; color:var(--muted); font-size:11px; font-weight:600; text-align:left; }}
td, th {{ padding:9px 13px; border-bottom:1px solid #edf0f6; }}
td.num {{ font-variant-numeric:tabular-nums; }}
.metric-chip {{ display:inline-block; min-width:48px; padding:3px 7px; border-radius:6px; text-align:center; font-weight:600; }}
.decision {{ min-width:218px; }}
.decision-detail {{ font-size:10px; color:var(--muted); line-height:1.35; margin-top:4px; }}
.item-main-row td {{ background:#fcfdff; font-weight:600; }}
.item-sub-row td {{ background:#fff; }}
.item-label-main {{ display:inline-flex; align-items:center; gap:7px; font-weight:700; color:var(--navy); }}
.item-label-main::before {{ content:""; width:8px; height:8px; border-radius:3px; background:var(--primary); opacity:.75; }}
.item-label-sub {{ display:inline-flex; align-items:center; gap:9px; padding-left:24px; color:#53637e; font-weight:600; }}
.item-label-sub::before {{ content:""; width:16px; height:1px; background:#b9c3d4; }}
.item-guide {{ padding:10px 14px 12px; display:flex; gap:18px; flex-wrap:wrap; color:var(--muted); font-size:11px; background:#fafbfe; }}
.guide-item {{ display:flex; align-items:center; gap:6px; }}
.guide-dot {{ width:8px; height:8px; border-radius:50%; display:inline-block; }}
.guide-dot.good {{ background:var(--green); }}
.guide-dot.attention {{ background:var(--orange); }}
.guide-dot.bad {{ background:var(--red); }}
.mc-card {{ margin-top:10px; }}
.mc-summary {{ display:grid; grid-template-columns:repeat(4,minmax(105px,1fr)); gap:8px; margin-bottom:10px; }}
.mc-stat {{ border:1px solid #edf1f7; background:#fcfdff; border-radius:9px; padding:9px 10px; }}
.mc-stat-value {{ font-size:18px; font-weight:650; margin-top:3px; }}
.mc-list {{ display:flex; flex-direction:column; gap:9px; }}
.mc-question {{ border:1px solid #edf1f7; border-radius:10px; padding:10px; background:#fff; }}
.mc-question-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:8px; }}
.mc-question-title {{ font-weight:700; }}
.mc-description {{ color:var(--muted); font-size:11px; margin-top:2px; }}
.mc-metrics {{ display:flex; gap:6px; flex-wrap:wrap; align-items:center; }}
.mc-options {{ display:grid; grid-template-columns:minmax(180px,.8fr) minmax(220px,1fr); gap:8px; align-items:start; }}
.mc-option-list {{ display:flex; flex-direction:column; gap:6px; }}
.mc-option-row {{ display:grid; grid-template-columns:34px 1fr 58px; gap:8px; align-items:center; font-size:11px; }}
.mc-option-letter {{ font-weight:700; color:var(--navy); }}
.mc-option-bar {{ height:8px; border-radius:999px; background:#edf1f7; overflow:hidden; }}
.mc-option-fill {{ height:100%; border-radius:999px; background:var(--muted); }}
.mc-option-fill.correct {{ background:var(--green); }}
.mc-conclusion {{ border:1px solid #e7ecf5; background:#fafbfe; border-radius:9px; padding:9px 10px; line-height:1.45; color:#53637e; font-size:11px; }}
#generalScores {{ height:270px; }}
.side-stack {{ display:flex; flex-direction:column; gap:10px; }}
.metric-help {{ display:grid; grid-template-columns:repeat(2,1fr); gap:8px; margin-top:8px; }}
.mini-note {{ padding:9px; background:#fafbfe; border:1px solid #eef1f6; border-radius:8px; font-size:11px; color:var(--muted); line-height:1.4; }}
.difficulty-list {{ display:grid; grid-template-columns:1fr 1fr; gap:14px; }}
.difficulty-list h3 {{ margin:0 0 8px; font-size:12px; color:var(--green); }}
.difficulty-list h3.weak {{ color:var(--red); }}
.question-line {{ display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #f0f2f6; }}
.group-grid {{ display:grid; grid-template-columns:repeat(3,minmax(280px,1fr)); gap:10px; }}
#groupDimensionCards {{ display:contents; }}
.chart-card {{ min-height:308px; }}
.chart {{ height:238px; }}
.chart-note {{ margin-top:5px; border:1px solid #e4e9fa; background:#f8f9ff; padding:9px 11px; border-radius:8px; color:#52627e; font-size:12px; }}
.resit-card {{ margin-bottom:10px; }}
.resit-summary {{ display:grid; grid-template-columns:repeat(4,minmax(120px,1fr)); gap:8px; }}
.resit-stat {{ border:1px solid #edf1f7; background:#fcfdff; border-radius:10px; padding:10px 12px; }}
.resit-stat strong {{ display:block; font-size:20px; margin-top:3px; }}
.resit-grid {{ display:grid; grid-template-columns:minmax(460px,1.1fr) minmax(330px,.9fr); gap:10px; margin-top:10px; align-items:start; }}
.resit-list {{ display:flex; flex-direction:column; gap:7px; }}
.resit-part {{ display:grid; grid-template-columns:1fr auto; gap:10px; align-items:center; padding:8px 10px; border:1px solid #edf1f7; border-radius:9px; background:#fff; }}
.resit-change {{ font-weight:700; }}
.resit-change.up {{ color:var(--green); }}
.resit-change.down {{ color:var(--red); }}
.empty {{ height:212px; display:flex; align-items:center; justify-content:center; color:var(--muted); text-align:center; }}
.heatmap-card {{ margin-bottom:10px; padding:14px 16px 13px; }}
.heatmap-head {{ display:flex; align-items:flex-start; justify-content:space-between; gap:22px; margin-bottom:6px; }}
.heatmap-head .section-title {{ margin-bottom:3px; }}
.heatmap-description {{ color:var(--muted); font-size:11px; }}
.heatmap-control {{ display:flex; align-items:center; gap:9px; flex:0 0 auto; color:var(--muted); font-size:11px; }}
.heatmap-control select {{ min-width:225px; padding:8px 10px; }}
.heatmap-chart {{ min-height:280px; }}
.student-layout {{ display:flex; flex-direction:column; gap:10px; }}
.student-overview {{ display:grid; grid-template-columns:255px minmax(650px,1fr); gap:18px; align-items:center; }}
.student-overview-stats {{ display:grid; grid-template-columns:repeat(5,minmax(105px,1fr)) minmax(190px,1.4fr); gap:0; align-items:center; }}
.overview-stat {{ padding:4px 14px; min-height:54px; border-left:1px solid #edf0f6; }}
.overview-stat:first-child {{ border-left:0; }}
.overview-value {{ font-size:20px; font-weight:650; margin-top:4px; }}
.overview-message {{ padding-left:16px; }}
.overview-message .callout {{ margin-top:0; font-size:11px; }}
.select-label {{ color:var(--muted); font-size:11px; margin-bottom:8px; }}
select {{ font:inherit; width:100%; border:1px solid var(--border); background:#fff; border-radius:8px; padding:10px; color:var(--navy); }}
.student-main {{ display:flex; flex-direction:column; gap:10px; }}
.student-profile-grid {{ display:grid; grid-template-columns:repeat(2,minmax(320px,1fr)); gap:10px; }}
.profile-card {{ min-height:354px; }}
.profile-header {{ display:flex; justify-content:space-between; gap:10px; align-items:flex-start; margin-bottom:3px; }}
.profile-header .section-title {{ margin-bottom:0; }}
.profile-chart {{ height:300px; }}
.student-bottom {{ display:grid; grid-template-columns:minmax(630px,1fr) 285px; gap:10px; align-items:start; }}
.insight-stack {{ display:flex; flex-direction:column; gap:10px; }}
.student-items {{ padding:0; overflow:hidden; }}
.student-item-head {{ padding:14px 15px 8px; }}
.side-title {{ font-size:14px; margin:0 0 10px; }}
.point {{ display:flex; gap:8px; padding:6px 0; line-height:1.4; }}
.dot {{ width:8px; height:8px; margin-top:5px; border-radius:50%; background:var(--green); flex:0 0 auto; }}
.dot.attention {{ background:var(--orange); }}
.callout {{ border-radius:9px; padding:10px; margin-top:10px; line-height:1.45; }}
.callout.good {{ border:1px solid #dfefe4; }}
.callout.attention {{ border:1px solid #f3e3c8; }}
.report-toolbar {{ display:flex; align-items:center; justify-content:space-between; gap:18px; padding:12px 14px; }}
.report-toolbar-title {{ font-weight:700; font-size:14px; margin-bottom:3px; }}
.report-toolbar-note {{ color:var(--muted); font-size:11px; }}
.report-actions {{ display:flex; align-items:center; gap:8px; }}
.report-button {{
 border:1px solid #d9e0ec; background:#fff; border-radius:9px; color:var(--navy);
 font:inherit; font-weight:600; padding:10px 14px; cursor:pointer; white-space:nowrap;
}}
.report-button.primary {{ color:#fff; background:var(--primary); border-color:var(--primary); }}
.report-message {{ min-height:16px; margin-top:4px; font-size:11px; color:var(--muted); text-align:right; }}
@media (max-width:1200px) {{
 .kpis {{ grid-template-columns:repeat(3,1fr); }}
 .quality-grid {{ grid-template-columns:repeat(3,1fr); }}
 .general-grid {{ display:flex; flex-direction:column; }}
 .student-overview, .student-overview-stats {{ display:flex; flex-direction:column; align-items:stretch; }}
 .overview-stat {{ border-left:0; border-top:1px solid #edf0f6; padding:9px 0; }}
 .group-grid, .student-profile-grid, .student-bottom {{ grid-template-columns:1fr; }}
 .heatmap-head {{ flex-direction:column; }}
.report-toolbar, .report-actions {{ flex-direction:column; align-items:stretch; }}
 .analysis-scope-banner .analysis-scope-top {{ flex-direction:column; }}
 .analysis-scope-banner .analysis-scope-grid, .comparison-grid {{ grid-template-columns:1fr; }}
}}
</style>
</head>
<body>
<div class="page">
  <header class="header">
    <div><h1 id="title">Toetsanalyse</h1><div id="context" class="subtitle"></div></div>
    <div id="scopeBadge" class="scope">{scope_text}</div>
  </header>
  <nav class="tabs">
    <button class="tab active" data-tab="general">Algemeen</button>
    <button class="tab" data-tab="group">Groepsniveau</button>
    <button class="tab" data-tab="student">Leerlingniveau</button>
    {comparison_tab}
  </nav>
  <section id="general" class="view active">
    <div id="generalKpis" class="kpis"></div>
    <article id="subtestInsight" class="card subtest-insight"></article>
    <div class="general-grid">
      <div>
        <article class="card">
          <h2 class="section-title">Toetskwaliteit in een oogopslag <span class="info" title="Compact overzicht van betrouwbaarheid, moeilijkheid en onderscheidend vermogen.">i</span></h2>
          <div id="sampleWarning" class="sample-warning" style="display:none;"></div>
          <div id="qualityCards" class="quality-grid"></div>
          <div class="explanation"><strong>Zo lees je dit:</strong> P-waarde toont de moeilijkheid (% behaald); Rit en Rir tonen of een vraag goed onderscheid maakt. Cronbach's alpha toont de interne betrouwbaarheid. SEM toont de meetonzekerheid als percentage van het totaal: lager is preciezer.</div>
        </article>
        <article class="card item-card">
          <div class="item-head"><h2 class="section-title">Itemanalyse - hoofdvragen en subvragen <span class="info" title="Hoofdvragen met subvragen krijgen een totaalregel. Daaronder staan de afzonderlijke subvragen.">i</span></h2></div>
          <div class="table-wrap"><table><thead><tr>
            <th>Vraag</th>
            <th title="Moeilijkheid: het gemiddeld behaalde aandeel van de punten. Advieszone: 0,30 tot 0,80.">P-waarde <span class="info">i</span></th>
            <th title="Item-toetscorrelatie: samenhang tussen de vraag en de totaalscore. Goed vanaf 0,30.">Rit <span class="info">i</span></th>
            <th title="Item-restcorrelatie: samenhang tussen de vraag en de rest van de toets. Goed vanaf 0,30.">Rir <span class="info">i</span></th>
            <th title="De status volgt uit P-waarde, Rit en Rir. Een rode waarde maakt de vraag een controlepunt.">Status en onderbouwing <span class="info">i</span></th>
          </tr></thead><tbody id="itemRows"></tbody></table></div>
          <div class="item-guide">
            <span class="guide-item"><i class="guide-dot good"></i> Groen: binnen advieswaarde</span>
            <span class="guide-item"><i class="guide-dot attention"></i> Oranje: aandacht of mogelijke verbetering</span>
            <span class="guide-item"><i class="guide-dot bad"></i> Rood: direct controlepunt</span>
            <span>Bij subvragen toont de hoofdregel de statistiek over de opgetelde score van alle subvragen samen.</span>
          </div>
        </article>
        <article class="card mc-card">
          <h2 class="section-title">Meerkeuzeanalyse <span class="info" title="Overzicht van meerkeuzevragen, antwoordverdeling, toetsstatistieken en interpretatie.">i</span></h2>
          <div id="mcAnalysis"></div>
        </article>
      </div>
      <aside class="side-stack">
        <article class="card"><h2 class="section-title">Verdeling van scores</h2><div id="generalScores"></div></article>
        <article class="card">
          <h2 class="section-title">Betrouwbaarheid en interpretatie</h2>
          <div id="reliabilityText" class="explanation"></div>
          <div class="metric-help">
            <div class="mini-note"><strong>P-waarde</strong><br>Goed: 0,30 - 0,80.</div>
            <div class="mini-note"><strong>Rit</strong><br>Goed: vanaf 0,30.</div>
            <div class="mini-note"><strong>Rir</strong><br>Goed: vanaf 0,30.</div>
            <div class="mini-note"><strong>SEM</strong><br>Klein: minder dan 5%.</div>
          </div>
        </article>
        <article class="card">
          <h2 class="section-title">Makkelijkste en moeilijkste vragen</h2>
          <div class="difficulty-list"><div><h3>Makkelijkste</h3><div id="easyItems"></div></div><div><h3 class="weak">Moeilijkste</h3><div id="difficultItems"></div></div></div>
        </article>
      </aside>
    </div>
  </section>
  <section id="group" class="view">
    <div id="groupKpis" class="kpis"></div>
    <article id="groupScopeBanner" class="card analysis-scope-banner"></article>
    <article id="resitAnalysisCard" class="card resit-card" style="display:none;"></article>
    <div class="group-grid">
      <div id="groupDimensionCards"></div>
      <article id="groupGradesCard" class="card chart-card"><h2 class="section-title">Verdeling cijfers (normering)</h2><div id="groupGrades" class="chart"></div><div id="groupGradesLegend" class="chart-note"></div></article>
      <article id="groupCumulativeCard" class="card chart-card"><h2 class="section-title">Cumulatieve frequentie (cijfers)</h2><div id="groupCumulative" class="chart"></div><div class="chart-note">Toont per cijfergrens welk percentage leerlingen daaronder of gelijk scoort.</div></article>
      <article id="groupGradesPendingCard" class="card chart-card"><h2 class="section-title">Cijferanalyse</h2><div class="empty">Er moet nog een normering worden vastgesteld voordat cijfergrafieken en cijferstatistieken zichtbaar worden.</div></article>
      <article class="card chart-card"><h2 class="section-title">Vragen die aandacht vragen</h2><div id="attentionItems"></div></article>
    </div>
    <article class="card heatmap-card" style="margin-top:10px;">
      <div class="heatmap-head">
        <div><h2 class="section-title">Heatmap per leerling</h2><div class="heatmap-description">Rangorde en relatieve score per gekozen classificatie. De leerlingnamen staan in de vakken.</div></div>
        <label class="heatmap-control">Toon
          <select id="groupHeatmapSelect"></select>
        </label>
      </div>
      <div id="groupHeatmap" class="heatmap-chart"></div>
    </article>
  </section>
  <section id="student" class="view">
    <div class="student-layout">
      <article class="card student-overview">
        <div>
          <div class="select-label">Selecteer leerling</div>
          <select id="studentSelect"></select>
        </div>
        <div id="studentScore" class="student-overview-stats"></div>
      </article>
      <article id="studentScopeBanner" class="card analysis-scope-banner"></article>
      <article class="card report-toolbar">
        <div>
          <div class="report-toolbar-title">Leerlingrapportage (toets) exporteren</div>
          <div class="report-toolbar-note">Kies in de volgende stap het rapportthema, de analyses en de uitleg in de PDF.</div>
        </div>
        <div>
          <div class="report-actions">
            <button id="exportCurrentStudent" class="report-button primary">PDF genereren voor deze leerling</button>
            <button id="exportAllStudents" class="report-button">PDF genereren voor alle leerlingen</button>
          </div>
          <div id="studentReportMessage" class="report-message"></div>
        </div>
      </article>
      <div class="student-main">
        <div id="studentProfileCards" class="student-profile-grid"></div>
        <div class="student-bottom">
          <article class="card student-items">
            <div class="student-item-head"><h2 class="section-title">Vraaganalyse - overzicht <span class="info" title="Resultaat per vraag van de geselecteerde leerling.">i</span></h2></div>
            <div class="table-wrap"><table><thead><tr><th>Vraag</th><th>Onderdeel</th><th>Score</th><th>Max.</th><th>Resultaat</th></tr></thead><tbody id="studentItemRows"></tbody></table></div>
          </article>
          <aside class="insight-stack">
            <article class="card"><h2 class="side-title">Sterke punten</h2><div id="strengths"></div><div id="strengthCallout"></div></article>
            <article class="card"><h2 class="side-title">Aandachtspunten</h2><div id="concerns"></div><div id="concernCallout"></div></article>
          </aside>
        </div>
        <article class="card heatmap-card">
          <div class="heatmap-head">
            <div><h2 class="section-title">Geanonimiseerde heatmap</h2><div class="heatmap-description">Vergelijk de positie van de geselecteerde leerling zonder de namen van klasgenoten te tonen.</div></div>
            <label class="heatmap-control">Toon
              <select id="studentHeatmapSelect"></select>
            </label>
          </div>
          <div id="studentHeatmap" class="heatmap-chart"></div>
        </article>
      </div>
    </div>
  </section>
  {comparison_view}
</div>
<script>
const data = {payload};
const gradesVisible = Boolean(data.normalization_finalized);
const gradeAnalysisVisible = gradesVisible && !data.subtest_context;
const colors = {{purple:"#6256ea", blue:"#4e8bd8", green:"#3ca35c", orange:"#e69a21", red:"#de4848", grid:"#e7ebf3", muted:"#66748e"}};
const plotConfig = {{displayModeBar:false, responsive:true, scrollZoom:false, doubleClick:false}};
let analysisBridge = null;
if (window.qt && window.QWebChannel) {{
  new QWebChannel(qt.webChannelTransport, channel => {{ analysisBridge = channel.objects.analysisBridge; }});
}}
function esc(value) {{ return String(value ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;"); }}
function number(value, decimals=1) {{ return value === null || value === undefined ? "-" : Number(value).toFixed(decimals).replace(".", ","); }}
function percentage(value) {{ return value === null || value === undefined ? "-" : Math.round(Number(value)) + "%"; }}
function qualityValue(value) {{ return value === null || value === undefined ? "-" : number(value, 2); }}
function statusTitle(status) {{
  return [status.label, status.range && status.range !== "-" ? "Bereik: " + status.range : "", status.reason || "", status.advice || ""].filter(Boolean).join(" | ");
}}
function badge(status) {{ return `<span class="badge ${{status.level}}" title="${{esc(statusTitle(status))}}">${{esc(status.label)}}</span>`; }}
function metricChip(value, status) {{
  return `<span class="metric-chip ${{status.level}}" title="${{esc(statusTitle(status))}}">${{qualityValue(value)}}</span>`;
}}
function activate(name) {{
  document.querySelectorAll(".tab").forEach(tab => tab.classList.toggle("active", tab.dataset.tab === name));
  document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === name));
  if (name === "group") renderGroupCharts();
  if (name === "student") renderStudent();
  if (name === "comparison") renderComparison();
}}
document.querySelectorAll(".tab").forEach(button => button.addEventListener("click", () => activate(button.dataset.tab)));
document.getElementById("title").textContent = "Toetsanalyse - " + data.test.name;
document.getElementById("context").textContent = [data.test.school_year, data.test.level, data.test.grade_year, data.test.period].filter(Boolean).join("  |  ") + (data.normalization_finalized ? "  |  Vastgestelde normering" : "  |  Cijfers volgens conceptnormering");
document.getElementById("scopeBadge").textContent = data.subtest_context ? ("Deeltoetsanalyse · " + data.subtest_context.name) : "Een toetsanalyse";
function renderKpis(target, cards) {{
  document.getElementById(target).innerHTML = cards.map(card => `<article class="card kpi ${{card.level || ""}}"><div class="kpi-label">${{esc(card.label)}}</div><div class="kpi-value">${{card.value}}</div><div class="kpi-note">${{card.note || ""}}</div></article>`).join("");
}}
function scopeBanner(title, note, metrics) {{
  const badge = data.subtest_context ? '<div class="analysis-scope-badge">Opknippingsdeel</div>' : '';
  return `
    <div class="analysis-scope-top">
      <div>
        <div class="analysis-scope-title">${{esc(title)}}</div>
        <div class="analysis-scope-note">${{esc(note)}}</div>
      </div>
      ${{badge}}
    </div>
    <div class="analysis-scope-grid">
      ${{metrics.map(metric => `
        <div class="analysis-scope-metric">
          <span class="kpi-label">${{esc(metric.label)}}</span>
          <strong>${{esc(metric.value)}}</strong>
          <span class="kpi-note">${{esc(metric.note || '')}}</span>
        </div>
      `).join('')}}
    </div>`;
}}
function renderSubtestInsight() {{
  const target = document.getElementById("subtestInsight");
  const context = data.subtest_context;
  if (!target || !context) {{
    if (target) target.style.display = "none";
    return;
  }}
  target.style.display = "block";
  const delta = context.difference_percentage;
  const deltaClass = delta === null || delta === undefined ? "" : (delta >= 0 ? "green" : "red");
  target.innerHTML = `
    <div class="subtest-grid">
      <div>
        <div class="subtest-title">Deeltoets: ${{esc(context.name)}}</div>
        <div class="subtest-copy">Deze analyse gebruikt alleen de vragen die aan deze deeltoets zijn gekoppeld. Voor vergelijking met de hele toets is er een aparte tab.</div>
      </div>
      <div class="subtest-metric"><span class="kpi-label">Vragen</span><strong>${{context.question_count}}</strong><span class="kpi-note">in deze deeltoets</span></div>
      <div class="subtest-metric"><span class="kpi-label">Punten</span><strong>${{number(context.maximum_score, 0)}} / ${{number(context.total_test_maximum, 0)}}</strong><span class="kpi-note">deel / totaal</span></div>
      <div class="subtest-metric"><span class="kpi-label">Gemiddeld</span><strong>${{percentage(context.mean_percentage)}}</strong><span class="kpi-note">van de deeltoetspunten</span></div>
      <div class="subtest-metric ${{deltaClass}}"><span class="kpi-label">T.o.v. totaaltoets</span><strong>${{delta === null || delta === undefined ? "-" : (delta >= 0 ? "+" : "") + number(delta) + "%"}}</strong><span class="kpi-note">verschil in gemiddeld %</span></div>
    </div>`;
}}
function renderScopeBanners() {{
  const context = data.subtest_context;
  const groupBanner = document.getElementById("groupScopeBanner");
  const studentBanner = document.getElementById("studentScopeBanner");
  const comparisonBanner = document.getElementById("comparisonBanner");
  if (!context) {{
    if (groupBanner) groupBanner.style.display = "none";
    if (studentBanner) studentBanner.style.display = "none";
    if (comparisonBanner) comparisonBanner.style.display = "none";
    return;
  }}
  const percentText = context.mean_percentage === null || context.mean_percentage === undefined ? "-" : percentage(context.mean_percentage);
  if (groupBanner) {{
    groupBanner.style.display = "block";
    groupBanner.innerHTML = scopeBanner(
      "Groepsanalyse van de deeltoets " + context.name,
      "Deze kaart toont alleen de resultaten die bij deze opknipping horen. De cijfers hieronder zijn dus niet van de totaaltoets.",
      [
        {{label:"Vragen in deze deeltoets", value:String(context.question_count), note:"alleen de gekoppelde vragen"}},
        {{label:"Gemiddelde score", value:percentText, note:"voor dit deel"}},
        {{label:"Totaaltoets", value:percentage(context.total_mean_percentage), note:"ter vergelijking"}},
        {{label:"Samenhang", value:context.correlation_with_total === null || context.correlation_with_total === undefined ? "-" : number(context.correlation_with_total, 2), note:"deel tegenover totaal"}}
      ]
    );
  }}
  if (studentBanner) {{
    studentBanner.style.display = "block";
    studentBanner.innerHTML = scopeBanner(
      "Leerlinganalyse van de deeltoets " + context.name,
      "De positie, score en signalen hieronder gaan over deze opknipping. Voor de vergelijking met de hele toets kun je naar de tab Vergelijking.",
      [
        {{label:"Deeltoets", value:percentText, note:"score van dit deel"}},
        {{label:"Totaaltoets", value:percentage(context.total_mean_percentage), note:"gemiddeld totaal"}},
        {{label:"Verschil", value:context.difference_percentage === null || context.difference_percentage === undefined ? "-" : (context.difference_percentage >= 0 ? "+" : "") + number(context.difference_percentage) + "%", note:"deel minus totaal"}},
        {{label:"Samenhang", value:context.correlation_with_total === null || context.correlation_with_total === undefined ? "-" : number(context.correlation_with_total, 2), note:"met de hele toets"}}
      ]
    );
  }}
  if (comparisonBanner) {{
    comparisonBanner.style.display = "block";
    comparisonBanner.innerHTML = scopeBanner(
      "Vergelijking deeltoets en totaaltoets",
      "Deze tab laat zien hoe dit deel zich verhoudt tot de volledige toets.",
      [
        {{label:"Deeltoets", value:percentText, note:"gemiddeld %"}},
        {{label:"Totaaltoets", value:percentage(context.total_mean_percentage), note:"gemiddeld %"}},
        {{label:"Verschil", value:context.difference_percentage === null || context.difference_percentage === undefined ? "-" : (context.difference_percentage >= 0 ? "+" : "") + number(context.difference_percentage) + "%", note:"verschil in gemiddelde"}},
        {{label:"Samenhang", value:context.correlation_with_total === null || context.correlation_with_total === undefined ? "-" : number(context.correlation_with_total, 2), note:"correlatie met totaalscore"}}
      ]
    );
  }}
}}
function modeText(summary) {{
  if (summary.mode_score === null || summary.mode_score === undefined || !summary.mode_count) return "-";
  return number(summary.mode_score) + " (" + String(summary.mode_count) + "x)";
}}
function scoreDistribution(values, maximumScore, step) {{
  const safeStep = Math.max(1, Math.round(Number(step || 1)));
  const safeMax = Math.max(1, Math.ceil(Number(maximumScore || 0)));
  const labels = [];
  const counts = [];
  for (let start = 0; start <= safeMax; start += safeStep) {{
    const end = Math.min(safeMax, start + safeStep - 1);
    labels.push(safeStep === 1 ? String(start) : `${{start}}-${{end}}`);
    const upperExclusive = start + safeStep;
    const count = values.filter(value => {{
      const numericValue = Number(value);
      if (Number.isNaN(numericValue)) return false;
      if (numericValue < start) return false;
      if (start + safeStep > safeMax) return numericValue <= safeMax;
      return numericValue < upperExclusive;
    }}).length;
    counts.push(count);
  }}
  return {{labels, counts}};
}}
function wrapCategoryLabel(value, maxChars=22) {{
  const text = String(value ?? "").trim();
  if (text.length <= maxChars) return text;
  const words = text.split(/\\s+/);
  const lines = [];
  let current = "";
  words.forEach(word => {{
    const candidate = current ? `${{current}} ${{word}}` : word;
    if (candidate.length <= maxChars) {{
      current = candidate;
      return;
    }}
    if (current) lines.push(current);
    current = word;
  }});
  if (current) lines.push(current);
  return lines.join("<br>");
}}
function renderGeneral() {{
  const summary = data.summary;
  const sampleWarning = document.getElementById("sampleWarning");
  if (data.sample && data.sample.is_small_group) {{
    sampleWarning.style.display = "block";
    sampleWarning.innerHTML = `<strong>Kleine groep:</strong> ${{esc(data.sample.message)}}`;
  }} else {{
    sampleWarning.style.display = "none";
  }}
  const cards = [
    {{label:"Gemiddelde score", value:number(summary.mean_score) + " / " + number(data.maximum_score, 0), note:summary.mean_score === null || !data.maximum_score ? "-" : percentage(summary.mean_score / data.maximum_score * 100)}},
    {{label:"Mediaan", value:number(summary.median_score), note:"Middelste score"}},
    {{label:"Modus", value:modeText(summary), note:"Vaakst voorkomende score"}},
    {{label:"Hoogste score", value:number(summary.highest_score) + " / " + number(data.maximum_score, 0), level:"green"}},
    {{label:"Laagste score", value:number(summary.lowest_score) + " / " + number(data.maximum_score, 0), level:"red"}}
  ];
  if (gradeAnalysisVisible) {{
    cards.splice(3, 0, {{label:"Gemiddeld cijfer", value:number(summary.mean_grade), note:summary.sd_grade === null ? "" : "(spreiding " + number(summary.sd_grade) + ")"}});
  }}
  renderKpis("generalKpis", cards);
  renderSubtestInsight();
  const names = [
    {{key:"alpha", label:"Cronbach's alpha"}},
    {{key:"sem", label:"SEM"}},
    {{key:"p_value", label:"Gem. P-waarde"}},
    {{key:"rit", label:"Gem. Rit"}},
    {{key:"rir", label:"Gem. Rir"}}
  ];
  document.getElementById("qualityCards").innerHTML = names.map(item => {{
    const metric = data.quality[item.key];
    let value = metric.value === null || metric.value === undefined ? "-" : qualityValue(metric.value);
    if (item.key === "sem" && metric.score_value !== null && metric.score_value !== undefined) {{
      value = value + "% (" + qualityValue(metric.score_value) + " pt)";
    }}
    return `<div class="quality"><div class="quality-name">${{item.label}}</div><div class="quality-value">${{value}}</div>${{badge(metric.status)}}<div class="quality-range">Bereik: ${{esc(metric.status.range)}}</div><div class="quality-advice">${{esc(metric.status.advice)}}</div></div>`;
  }}).join("");
  document.getElementById("itemRows").innerHTML = itemAnalysisRows();
  renderMultipleChoiceAnalysis();
  const alpha = data.quality.alpha;
  const sem = data.quality.sem;
  document.getElementById("reliabilityText").innerHTML = alpha.value === null ? "Er zijn nog niet genoeg complete resultaten om betrouwbaarheid en SEM te berekenen." : `Cronbach's alpha is <strong>${{qualityValue(alpha.value)}}</strong> (${{esc(alpha.status.label)}}). SEM is <strong>${{sem.value === null ? "-" : qualityValue(sem.value) + "% (" + qualityValue(sem.score_value) + " pt)"}}</strong> (${{esc(sem.status.label)}}). ${{esc(alpha.status.advice)}} ${{esc(sem.status.advice)}}`;
  const line = item => `<div class="question-line"><span>Vraag ${{esc(item.label)}}</span><strong>${{qualityValue(item.p_value)}}</strong></div>`;
  document.getElementById("easyItems").innerHTML = data.easy_items.map(line).join("");
  document.getElementById("difficultItems").innerHTML = data.difficult_items.map(line).join("");
  if (window.Plotly) {{
    const scoreBin = Math.max(1, Math.ceil(Number(data.maximum_score || 1) / 12));
    const scoreMaximum = Math.max(1, Number(data.maximum_score || 0));
    const distribution = scoreDistribution(data.participants.map(p => p.total_score), scoreMaximum, scoreBin);
    Plotly.react("generalScores", [{{x:distribution.labels, y:distribution.counts, type:"bar", marker:{{color:colors.purple}}}}], scoreBarLayout("Scorebereik"), plotConfig);
  }}
}}
function itemAnalysisRows() {{
  const source = data.question_group_analysis || data.item_analysis || [];
  const rows = [];
  source.forEach(item => {{
    rows.push(item);
    (item.children || []).forEach(child => rows.push(child));
  }});
  return rows.map(item => {{
    const isSub = item.row_type === "subquestion";
    const label = isSub
      ? `<span class="item-label-sub">${{esc(item.display_label || item.label)}}</span>`
      : `<span class="item-label-main">${{esc(item.display_label || ("Vraag " + item.label))}}</span>`;
    return `<tr class="${{isSub ? "item-sub-row" : "item-main-row"}}"><td>${{label}}</td><td class="num">${{metricChip(item.p_value, item.p_status)}}</td><td class="num">${{metricChip(item.rit, item.rit_status)}}</td><td class="num">${{metricChip(item.rir, item.rir_status)}}</td><td class="decision">${{badge(item.status)}}<div class="decision-detail">${{esc(item.status.reason)}}<br>${{esc(item.status.advice)}}</div></td></tr>`;
  }}).join("");
}}
function renderMultipleChoiceAnalysis() {{
  const target = document.getElementById("mcAnalysis");
  const mc = data.multiple_choice || {{summary:{{question_count:0}}, items:[]}};
  const items = mc.items || [];
  if (!items.length) {{
    target.innerHTML = '<div class="empty">Deze toets bevat geen meerkeuzevragen.</div>';
    return;
  }}
  const summary = mc.summary || {{}};
  const stats = [
    {{label:"Meerkeuzevragen", value:String(summary.question_count || items.length)}},
    {{label:"Gem. P-waarde", value:qualityValue(summary.mean_p_value)}},
    {{label:"Gem. Rit", value:qualityValue(summary.mean_rit)}},
    {{label:"Aandachtspunten", value:String(summary.attention_count || 0)}}
  ];
  const summaryHtml = `<div class="mc-summary">${{stats.map(stat => `<div class="mc-stat"><div class="kpi-label">${{esc(stat.label)}}</div><div class="mc-stat-value">${{esc(stat.value)}}</div></div>`).join("")}}</div>`;
  const rows = items.map(item => {{
    const answerText = (item.accepted_answers || []).length ? item.accepted_answers.join(", ") : "-";
    const correctPercentage = item.response_count ? item.correct_count / item.response_count * 100 : null;
    const notMadeText = Number(item.not_made_count || 0) > 0
      ? `<div class="mc-description"><strong>Niet gemaakt:</strong> ${{item.not_made_count}} leerling(en) (${{percentage(item.not_made_percentage)}}). Deze tellen niet mee als antwoordalternatief.</div>`
      : "";
    const options = (item.responses || []).map(response => {{
      const fillWidth = Math.max(0, Math.min(100, Number(response.percentage || 0)));
      return `<div class="mc-option-row" title="${{esc(response.accepted ? "Goedgekeurd antwoord" : "Afleider of fout antwoord")}}">
        <div class="mc-option-letter">${{esc(response.option)}}${{response.accepted ? " (goed)" : ""}}</div>
        <div class="mc-option-bar"><div class="mc-option-fill ${{response.accepted ? "correct" : ""}}" style="width:${{fillWidth}}%"></div></div>
        <div class="num">${{response.count}} (${{percentage(response.percentage)}})</div>
      </div>`;
    }}).join("");
    return `<section class="mc-question">
      <div class="mc-question-head">
        <div><div class="mc-question-title">Vraag ${{esc(item.label)}} · sleutel: ${{esc(answerText)}} · juist: ${{percentage(correctPercentage)}}</div><div class="mc-description">${{esc(item.description || "Geen omschrijving ingevuld.")}}</div>${{notMadeText}}</div>
        <div class="mc-metrics">${{metricChip(item.p_value, item.p_status)}} ${{metricChip(item.rit, item.rit_status)}} ${{metricChip(item.rir, item.rir_status)}} ${{badge(item.conclusion)}}</div>
      </div>
      <div class="mc-options">
        <div class="mc-option-list">${{options}}</div>
        <div class="mc-conclusion"><strong>Conclusie:</strong> ${{esc(item.conclusion.text)}}<br><span class="kpi-note">P-waarde = moeilijkheid, Rit/Rir = onderscheidend vermogen binnen deze toets.</span></div>
      </div>
    </section>`;
  }}).join("");
  target.innerHTML = summaryHtml + `<div class="mc-list">${{rows}}</div>`;
}}
function baseLayout() {{ return {{dragmode:false, paper_bgcolor:"transparent", plot_bgcolor:"transparent", font:{{family:"Inter, Segoe UI, sans-serif", color:colors.muted, size:11}}, margin:{{l:40,r:14,t:10,b:38}}, showlegend:false, xaxis:{{fixedrange:true, gridcolor:colors.grid}}, yaxis:{{fixedrange:true, gridcolor:colors.grid, zeroline:false}}}}; }}
function histogramLayout(label, start, end) {{
  const layout = baseLayout();
  layout.xaxis = {{title:label, range:[start,end], dtick:1, fixedrange:true, gridcolor:"transparent"}};
  layout.yaxis.title = "Aantal";
  return layout;
}}
function scoreBarLayout(label) {{
  const layout = baseLayout();
  layout.xaxis = {{title:label, type:"category", tickangle:-30, fixedrange:true, gridcolor:"transparent"}};
  layout.yaxis.title = "Aantal";
  return layout;
}}
function dimensionChart(id, dimension, horizontal=false) {{
  const entries = dimension.entries || [];
  const target = document.getElementById(id);
  if (!window.Plotly) return;
  if (!entries.length) {{ target.innerHTML = '<div class="empty">Geen ingevulde classificaties voor deze toets.</div>'; return; }}
  const names = entries.map(entry => wrapCategoryLabel(entry.name));
  const values = entries.map(entry => entry.percentage);
  const palette = values.map(value => value >= 60 ? colors.green : value >= 40 ? colors.orange : colors.red);
  const trace = horizontal ? {{x:values, y:names, type:"bar", orientation:"h", marker:{{color:palette}}, text:values.map(value=>Math.round(value)+"%"), textposition:"outside"}} : {{x:names, y:values, type:"bar", marker:{{color:palette}}, text:values.map(value=>Math.round(value)+"%"), textposition:"outside"}};
  const layout = baseLayout();
  if (horizontal) {{
    const longestLabel = names.reduce((length, label) => Math.max(length, String(label).replaceAll("<br>", " ").length), 0);
    const leftMargin = Math.min(230, Math.max(130, 8 * longestLabel));
    layout.margin = {{l:leftMargin,r:35,t:8,b:34}};
    layout.xaxis = {{range:[0,100], ticksuffix:"%", fixedrange:true, gridcolor:colors.grid}};
    layout.yaxis = {{fixedrange:true, autorange:"reversed"}};
  }}
  else {{ layout.yaxis = {{range:[0,108], ticksuffix:"%", fixedrange:true, gridcolor:colors.grid, zeroline:false}}; }}
  Plotly.react(id, [trace], layout, plotConfig);
}}
function gradeBands(grades) {{
  const bands = [
    {{label:"1 - 3,9", min:1.0, max:3.99, color:"#de5757"}},
    {{label:"4,0 - 4,9", min:4.0, max:4.99, color:"#e7952a"}},
    {{label:"5,0 - 5,9", min:5.0, max:5.99, color:"#e1bc34"}},
    {{label:"6,0 - 6,9", min:6.0, max:6.99, color:"#53b06c"}},
    {{label:"7,0 - 10", min:7.0, max:10.0, color:"#2f9350"}},
  ];
  const total = grades.length || 1;
  return bands.map(band => {{
    const count = grades.filter(value => value >= band.min && value <= band.max).length;
    return {{
      ...band,
      count,
      percentage: Math.round((count / total) * 100),
    }};
  }}).filter(band => band.count > 0);
}}
function noteFor(dimension) {{
  const entries = dimension.entries || [];
  if (!entries.length) return "Vul classificaties in de toetsmatrijs in om deze analyse te tonen.";
  const ranked = [...entries].sort((left, right) => right.percentage - left.percentage);
  return "Sterkste onderdeel: " + ranked[0].name + " (" + percentage(ranked[0].percentage) + "). Aandachtspunt: " + ranked[ranked.length-1].name + " (" + percentage(ranked[ranked.length-1].percentage) + ").";
}}
function signedPercentage(value) {{
  if (value === null || value === undefined) return "-";
  const numeric = Number(value);
  return (numeric > 0 ? "+" : "") + Math.round(numeric) + "%";
}}
function signedNumber(value) {{
  if (value === null || value === undefined) return "-";
  const numeric = Number(value);
  return (numeric > 0 ? "+" : "") + number(numeric);
}}
function renderResitAnalysis() {{
  const card = document.getElementById("resitAnalysisCard");
  const resit = data.resit_analysis;
  if (!card || !resit) {{
    if (card) card.style.display = "none";
    return;
  }}
  card.style.display = "";
  const originalName = resit.original_test?.name || "Originele toets";
  const resitName = resit.resit_test?.name || "Herkansing";
  if (!resit.comparison_count) {{
    card.innerHTML = `<h2 class="section-title">Herkansingsanalyse</h2><div class="explanation">Er is een herkansing gekoppeld aan <strong>${{esc(originalName)}}</strong>, maar er zijn nog geen leerlingen met complete resultaten op beide afnames.</div>`;
    return;
  }}
  const gradeMode = Boolean(resit.grade_available);
  const effectLabel = gradeMode ? "Eindcijfer stijgt" : "Eindscore stijgt";
  const effectNote = gradeMode ? "hoogste cijfer telt" : "hoogste scorepercentage telt";
  const studentRows = (resit.students || []).slice(0, 8).map(row => {{
    const delta = gradeMode ? row.delta_grade : row.delta_percentage;
    const deltaText = gradeMode ? signedNumber(delta) : signedPercentage(delta);
    const originalValue = gradeMode ? number(row.original_grade) : percentage(row.original_percentage);
    const resitValue = gradeMode ? number(row.resit_grade) : percentage(row.resit_percentage);
    return `<tr><td>${{esc(row.name)}}</td><td>${{originalValue}}</td><td>${{resitValue}}</td><td><span class="resit-change ${{Number(delta) >= 0 ? "up" : "down"}}">${{deltaText}}</span></td><td>${{row.final_improved ? "Herkansing telt" : "Origineel blijft staan"}}</td></tr>`;
  }}).join("");
  const categoryRows = (resit.categories || []).slice(0, 8).map(entry => {{
    const delta = Number(entry.mean_delta_percentage || 0);
    return `<div class="resit-part"><span><strong>${{esc(entry.dimension)}}:</strong> ${{esc(entry.category)}}<br><span class="kpi-note">${{entry.student_count}} leerling(en) vergeleken</span></span><span class="resit-change ${{delta >= 0 ? "up" : "down"}}">${{signedPercentage(delta)}}</span></div>`;
  }}).join("") || '<div class="mini-note">Er zijn nog geen vergelijkbare onderdelen tussen origineel en herkansing gevonden.</div>';
  card.innerHTML = `
    <h2 class="section-title">Herkansingsanalyse</h2>
    <div class="explanation">Vergelijking tussen <strong>${{esc(originalName)}}</strong> en <strong>${{esc(resitName)}}</strong>. Dit laat zien wie vooruitgaat, op welke onderdelen de herkansing effect heeft en welk resultaat uiteindelijk meetelt.</div>
    <div class="resit-summary">
      <div class="resit-stat"><div class="kpi-label">Leerlingen vergeleken</div><strong>${{resit.comparison_count}}</strong></div>
      <div class="resit-stat"><div class="kpi-label">Gaan vooruit</div><strong class="good">${{resit.improved_count}}</strong><div class="kpi-note">${{resit.lower_count}} lager, ${{resit.same_count}} gelijk</div></div>
      <div class="resit-stat"><div class="kpi-label">Gem. verandering</div><strong class="${{Number(resit.mean_delta_percentage || 0) >= 0 ? "good" : "bad"}}">${{signedPercentage(resit.mean_delta_percentage)}}</strong><div class="kpi-note">${{gradeMode ? "cijfer: " + signedNumber(resit.mean_delta_grade) : "% van de punten"}}</div></div>
      <div class="resit-stat"><div class="kpi-label">${{effectLabel}}</div><strong>${{resit.final_effect_count}}</strong><div class="kpi-note">${{effectNote}}</div></div>
    </div>
    <div class="resit-grid">
      <div><h3 class="side-title">Leerlingen met grootste verandering</h3><div class="table-wrap"><table><thead><tr><th>Leerling</th><th>Origineel</th><th>Herkansing</th><th>Verschil</th><th>Eindresultaat</th></tr></thead><tbody>${{studentRows}}</tbody></table></div></div>
      <div><h3 class="side-title">Onderdelen met meeste verschil</h3><div class="resit-list">${{categoryRows}}</div></div>
    </div>`;
}}
function groupDimensionPresentation(dimension) {{
  const entries = dimension.entries || [];
  const title = String(dimension.title || "").trim();
  if (!/^taxonomie(?:\\s*:\\s*.*)?$/i.test(title) || !entries.length) return dimension;
  const splitEntries = entries.map(entry => {{
    const match = String(entry.name || "").match(/^([^:]+):\\s*(.+)$/);
    return match ? {{prefix:match[1].trim(), label:match[2].trim()}} : null;
  }});
  if (splitEntries.some(entry => !entry)) return dimension;
  const prefix = splitEntries[0].prefix;
  if (!splitEntries.every(entry => entry.prefix.toLowerCase() === prefix.toLowerCase())) return dimension;
  return {{
    ...dimension,
    title:"Taxonomie: " + prefix,
    entries:entries.map((entry, index) => ({{...entry, name:splitEntries[index].label}}))
  }};
}}
function groupReportDimensions() {{
  const dimensions = data.group_dimensions || [];
  const hasTaxonomyRtti = dimensions.some(dimension => groupDimensionPresentation(dimension).title.toLowerCase() === "taxonomie: rtti");
  return dimensions.filter(dimension => !(hasTaxonomyRtti && String(dimension.title || "").trim().toLowerCase() === "rtti"));
}}
function renderGroupDimensionCards() {{
  const dimensions = groupReportDimensions();
  const container = document.getElementById("groupDimensionCards");
  if (!container) return;
  if (!dimensions.length) {{
    container.innerHTML = '<article class="card chart-card"><h2 class="section-title">Classificaties</h2><div class="empty">Geen ingevulde classificaties voor deze toets.</div></article>';
    return;
  }}
  container.innerHTML = dimensions.map(dimension => {{
    const presented = groupDimensionPresentation(dimension);
    const chartId = `dim_${{dimension.key}}`;
    const noteId = `note_${{dimension.key}}`;
    return `<article class="card chart-card"><h2 class="section-title">${{esc(presented.title)}} (% van de punten gescoord)</h2><div id="${{chartId}}" class="chart"></div><div id="${{noteId}}" class="chart-note"></div></article>`;
  }}).join("");
  dimensions.forEach(dimension => {{
    const presented = groupDimensionPresentation(dimension);
    dimensionChart(`dim_${{dimension.key}}`, presented, presented.orientation === "horizontal");
    const note = document.getElementById(`note_${{dimension.key}}`);
    if (note) note.textContent = noteFor(presented);
  }});
}}
function heatmapOptions(groupReport=false) {{
  const options = [{{key:"overall", title:"Algemene score", columns:["Totale score"]}}];
  const dimensions = groupReport ? groupReportDimensions() : (data.group_dimensions || []);
  dimensions.forEach(dimension => {{
    const presented = groupReport ? groupDimensionPresentation(dimension) : dimension;
    options.push({{
    key:dimension.key,
    title:presented.title,
    columns:(presented.entries || []).map(entry => String(entry.name)),
    sourceColumns:(dimension.entries || []).map(entry => String(entry.name))
  }})}});
  return options.filter(option => option.columns.length);
}}
function fillHeatmapSelect(id, groupReport=false) {{
  const select = document.getElementById(id);
  if (!select) return;
  const current = select.value;
  const options = heatmapOptions(groupReport);
  select.innerHTML = options.map(option => `<option value="${{esc(option.key)}}">${{esc(option.title)}}</option>`).join("");
  if (options.some(option => option.key === current)) select.value = current;
}}
function heatmapCell(student, option, column, columnIndex=0) {{
  if (option.key === "overall") return {{percentage:student.score_percentage, rank:student.rank, rank_count:student.rank_count, rank_end:student.rank_end, tied_count:student.tied_count}};
  const entries = (student.profiles || {{}})[option.key] || [];
  const sourceColumn = (option.sourceColumns || option.columns)[columnIndex] || column;
  return entries.find(entry => String(entry.name) === sourceColumn) || {{percentage:null, rank:null, rank_count:null, rank_end:null, tied_count:null}};
}}
function rankText(cell, fallbackIndex) {{
  if (!cell || cell.rank == null) return "Positie " + String(fallbackIndex + 1);
  const tied = Number(cell.tied_count || 0);
  return tied > 1 ? "Positie " + String(cell.rank) + " gedeeld" : "Positie " + String(cell.rank);
}}
function renderHeatmap(targetId, selectId, anonymous, selectedStudentId=null, groupReport=false) {{
  const target = document.getElementById(targetId);
  if (!target || !window.Plotly) return;
  const options = heatmapOptions(groupReport);
  const selection = document.getElementById(selectId);
  const option = options.find(candidate => candidate.key === (selection ? selection.value : "")) || options[0];
  if (!option || !data.participants.length) {{
    target.innerHTML = '<div class="empty">Geen complete resultaten beschikbaar voor deze heatmap.</div>';
    return;
  }}
  const rankedColumns = option.columns.map(column => [...data.participants].sort((left, right) => {{
    const columnIndex = option.columns.indexOf(column);
    const leftValue = heatmapCell(left, option, column, columnIndex).percentage;
    const rightValue = heatmapCell(right, option, column, columnIndex).percentage;
    const difference = Number(rightValue ?? -1) - Number(leftValue ?? -1);
    return difference || String(left.name).localeCompare(String(right.name));
  }}));
  const positions = data.participants.map((_, index) => "Positie " + String(index + 1));
  const values = positions.map((_, rowIndex) => option.columns.map((column, columnIndex) =>
    heatmapCell(rankedColumns[columnIndex][rowIndex], option, column, columnIndex).percentage));
  const cellText = positions.map((_, rowIndex) => option.columns.map((column, columnIndex) => {{
    const student = rankedColumns[columnIndex][rowIndex];
    const cell = heatmapCell(student, option, column, columnIndex);
    return anonymous && student.student_id !== selectedStudentId ? String(cell.rank ?? rowIndex + 1) : student.name;
  }}));
  const hoverData = positions.map((_, rowIndex) => option.columns.map((column, columnIndex) => {{
    const student = rankedColumns[columnIndex][rowIndex];
    const cell = heatmapCell(student, option, column, columnIndex);
    return [
      anonymous && student.student_id !== selectedStudentId ? rankText(cell, rowIndex) : student.name,
      rankText(cell, rowIndex),
      column,
      cell.tied_count || 1
    ];
  }}));
  const selectedCells = anonymous ? rankedColumns.flatMap((students, columnIndex) => {{
    const rowIndex = students.findIndex(student => student.student_id === selectedStudentId);
    return rowIndex < 0 ? [] : [{{columnIndex, rowIndex}}];
  }}) : [];
  const chartHeight = Math.min(760, Math.max(285, positions.length * 25 + 92));
  target.style.height = String(chartHeight) + "px";
  Plotly.react(targetId, [{{
    x:option.columns.map((_, index) => index),
    y:positions.map((_, index) => index),
    z:values,
    text:cellText,
    customdata:hoverData,
    type:"heatmap",
    zmin:0,
    zmax:100,
    colorscale:[[0,"#eff6f0"],[0.25,"#d0e8d2"],[0.5,"#91c893"],[0.75,"#4aa558"],[1,"#148229"]],
    xgap:1,
    ygap:1,
    texttemplate:"%{{text}}",
    textfont:{{size:anonymous ? 11 : 10}},
    hovertemplate:"%{{customdata[0]}}<br>%{{customdata[2]}}: %{{z:.0f}}%<br>%{{customdata[1]}}<extra></extra>",
    colorbar:{{title:"% van de punten<br>gescoord", ticksuffix:"%", thickness:14, len:.86}}
  }}], {{
    dragmode:false,
    paper_bgcolor:"transparent",
    plot_bgcolor:"transparent",
    font:{{family:"Inter, Segoe UI, sans-serif", color:colors.muted, size:11}},
    margin:{{l:74, r:70, t:10, b:54}},
    xaxis:{{title:option.key === "overall" ? "" : option.title, fixedrange:true, side:"bottom", gridcolor:"transparent", tickmode:"array", tickvals:option.columns.map((_, index) => index), ticktext:option.columns.map(column => wrapCategoryLabel(column, 28))}},
    yaxis:{{fixedrange:true, autorange:"reversed", automargin:true, gridcolor:"transparent", tickmode:"array", tickvals:positions.map((_, index) => index), ticktext:positions}},
    shapes:selectedCells.map(cell => ({{
      type:"rect", xref:"x", x0:cell.columnIndex - .5, x1:cell.columnIndex + .5, yref:"y",
      y0:cell.rowIndex - .5, y1:cell.rowIndex + .5,
      line:{{color:"#f04491", width:4}}
    }}))
  }}, plotConfig);
}}
function renderGroupCharts() {{
  renderScopeBanners();
  const summary = data.summary;
  const failed = data.participants.filter(p => !p.sufficient).length;
  const cards = gradeAnalysisVisible ? [
    {{label:"Aantal leerlingen", value:String(data.participant_count)}},
    {{label:"Gemiddelde score", value:number(summary.mean_score) + " / " + number(data.maximum_score,0)}},
    {{label:"Gemiddeld cijfer", value:number(summary.mean_grade)}},
    {{label:"Voldoende", value:percentage(summary.sufficient_percentage), level:"green"}},
    {{label:"Onvoldoende", value:percentage(data.participant_count ? failed/data.participant_count*100 : null), level:"red"}}
  ] : [
    {{label:"Aantal leerlingen", value:String(data.participant_count)}},
    {{label:"Gemiddelde score", value:number(summary.mean_score) + " / " + number(data.maximum_score,0)}},
    {{label:"Mediaan score", value:number(summary.median_score)}},
    {{label:"Hoogste score", value:number(summary.highest_score) + " / " + number(data.maximum_score,0), level:"green"}},
    {{label:"Laagste score", value:number(summary.lowest_score) + " / " + number(data.maximum_score,0), level:"red"}}
  ];
  renderKpis("groupKpis", cards);
  renderResitAnalysis();
  const gradesCard = document.getElementById("groupGradesCard");
  const cumulativeCard = document.getElementById("groupCumulativeCard");
  const pendingCard = document.getElementById("groupGradesPendingCard");
  if (gradesCard) gradesCard.style.display = gradesVisible ? "" : "none";
  if (cumulativeCard) cumulativeCard.style.display = gradesVisible ? "" : "none";
  if (data.subtest_context) {{
    if (gradesCard) gradesCard.style.display = "none";
    if (cumulativeCard) cumulativeCard.style.display = "none";
  }}
  if (pendingCard) {{
    // pendingCard.style.display = gradesVisible ? "none" : "";
    if (gradeAnalysisVisible) {{
      pendingCard.style.display = "none";
    }} else {{
      pendingCard.style.display = "";
      pendingCard.innerHTML = data.subtest_context
        ? '<h2 class="section-title">Cijferanalyse</h2><div class="empty">Bij een deeltoets wordt geen cijferverdeling getoond. Cijfers horen alleen bij de totaaltoets.</div>'
        : '<h2 class="section-title">Cijferanalyse</h2><div class="empty">Er moet nog een normering worden vastgesteld voordat cijfergrafieken en cijferstatistieken zichtbaar worden.</div>';
    }}
  }}
  renderGroupDimensionCards();
  renderHeatmap("groupHeatmap", "groupHeatmapSelect", false, null, true);
  if (window.Plotly && gradesVisible) {{
    if (data.subtest_context) return;
    const grades = data.participants.map(p => Number(p.grade)).filter(value => !Number.isNaN(value));
    const bands = gradeBands(grades);
    Plotly.react("groupGrades", [{{
      values: bands.map(b => b.count),
      labels: bands.map(b => b.label),
      type:"pie",
      hole:.56,
      marker: {{colors: bands.map(b => b.color)}},
      textinfo:"none",
      sort:false
    }}], Object.assign(baseLayout(), {{showlegend:false, margin:{{l:12,r:12,t:8,b:8}}}}), plotConfig);
    const legend = document.getElementById("groupGradesLegend");
    if (legend) {{
      legend.innerHTML = bands.map(band => `<div class="question-line"><span><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${{band.color}};margin-right:7px;"></span>${{band.label}}</span><strong>${{band.count}} leerlingen (${{band.percentage}}%)</strong></div>`).join("");
    }}
    const cumulative = [];
    for (let grade = 1; grade <= 10; grade += 1) {{
      const count = grades.filter(value => value <= grade).length;
      cumulative.push({{grade, percentage: grades.length ? (count / grades.length) * 100 : 0}});
    }}
    Plotly.react("groupCumulative", [{{
      x: cumulative.map(point => point.grade),
      y: cumulative.map(point => point.percentage),
      type:"scatter",
      mode:"lines+markers",
      line:{{color:"#2f9350", width:2}},
      marker:{{size:6, color:"#2f9350"}},
      hovertemplate:"Cijfer <= %{{x}}: %{{y:.1f}}%<extra></extra>"
    }}], Object.assign(baseLayout(), {{
      xaxis: {{title:"Cijfergrens", dtick:1, range:[1,10], fixedrange:true, gridcolor:colors.grid}},
      yaxis: {{title:"Cumulatief %", range:[0,100], ticksuffix:"%", fixedrange:true, gridcolor:colors.grid, zeroline:false}}
    }}), plotConfig);
  }}
  const attention = data.item_analysis.filter(item => item.status.level !== "good").slice(0, 8);
  document.getElementById("attentionItems").innerHTML = attention.length ? attention.map(item => `<div class="question-line"><span>Vraag ${{esc(item.label)}}</span>${{badge(item.status)}}</div>`).join("") : '<div class="callout good">Geen opvallende items op basis van P-waarde en Rir.</div>';
}}
function renderComparison() {{
  renderScopeBanners();
  const targetMetrics = document.getElementById("comparisonMetrics");
  if (!data.subtest_context || !targetMetrics) return;
  const context = data.subtest_context;
  const comparisonCards = [
    {{label:"Gemiddelde deeltoets", value:percentage(context.mean_percentage), note:"alleen de geselecteerde opknipping"}},
    {{label:"Gemiddelde totaaltoets", value:percentage(context.total_mean_percentage), note:"alle volledige resultaten"}},
    {{label:"Verschil", value:context.difference_percentage === null || context.difference_percentage === undefined ? "-" : (context.difference_percentage >= 0 ? "+" : "") + number(context.difference_percentage) + "%", note:"deel minus totaal"}},
    {{label:"Samenhang", value:context.correlation_with_total === null || context.correlation_with_total === undefined ? "-" : number(context.correlation_with_total, 2), note:"hoe sterk deel en totaal samen bewegen"}},
    {{label:"Vragen", value:String(context.question_count), note:"gekoppeld aan deze deeltoets"}},
    {{label:"Punten", value:number(context.maximum_score, 0) + " / " + number(context.total_test_maximum, 0), note:"deel / totaal"}}
  ];
  targetMetrics.innerHTML = `<div class="comparison-list">${{comparisonCards.map(card => `
    <div class="comparison-item">
      <div class="label">${{esc(card.label)}}</div>
      <div class="value">${{esc(card.value)}}</div>
      <div class="note">${{esc(card.note)}}</div>
    </div>
  `).join("")}}</div>`;
  if (window.Plotly) {{
    Plotly.react("comparisonChart", [{{
      x:["Deeltoets","Totaaltoets"],
      y:[Number(context.mean_percentage || 0), Number(context.total_mean_percentage || 0)],
      type:"bar",
      marker:{{color:[colors.primary, colors.blue]}},
      text:[percentage(context.mean_percentage), percentage(context.total_mean_percentage)],
      textposition:"auto",
      hovertemplate:"%{{x}}<br>% van de punten: %{{y:.0f}}%<extra></extra>"
    }}], {{
      dragmode:false,
      paper_bgcolor:"transparent",
      plot_bgcolor:"transparent",
      font:{{family:"Inter, Segoe UI, sans-serif", color:colors.muted, size:11}},
      margin:{{l:36,r:18,t:12,b:36}},
      showlegend:false,
      xaxis:{{fixedrange:true, gridcolor:"transparent"}},
      yaxis:{{fixedrange:true, range:[0,100], ticksuffix:"%", gridcolor:colors.grid, zeroline:false}}
    }}, plotConfig);
  }} else {{
    const chart = document.getElementById("comparisonChart");
    if (chart) chart.innerHTML = '<div class="empty">Grafiekweergave is niet beschikbaar.</div>';
  }}
}}
function studentBarProfileChart(id, entries, studentName, categoryPrefix) {{
  if (!window.Plotly) return;
  const target = document.getElementById(id);
  if (!entries.length) {{ target.innerHTML = '<div class="empty">Geen profielgegevens beschikbaar.</div>'; return; }}
  const labels = entries.map(entry => wrapCategoryLabel(categoryPrefix + ": " + entry.name, 22));
  const longestLabel = labels.reduce((length, label) => Math.max(length, String(label).replaceAll("<br>", " ").length), 0);
  Plotly.react(id, [
    {{
      x:entries.map(entry => entry.percentage), y:labels, type:"bar", orientation:"h",
      name:studentName, marker:{{color:colors.purple}},
      text:entries.map(entry => percentage(entry.percentage) + (entry.percentile === null || entry.percentile === undefined ? "" : " | beter dan " + entry.percentile + "% van de leerlingen")),
      textposition:"outside", cliponaxis:false,
      customdata:entries.map(entry => [entry.group_percentage, entry.percentile]),
      hovertemplate:"%{{y}}<br>Leerling: %{{x:.0f}}%<br>Groepsniveau: %{{customdata[0]:.0f}}%<br>Beter dan %{{customdata[1]}}% van de groep<extra></extra>"
    }},
    {{
      x:entries.map(entry => entry.group_percentage), y:labels, type:"bar", orientation:"h",
      name:"Groepsniveau", marker:{{color:"#c4ccda"}},
      hovertemplate:"%{{y}}<br>Groepsniveau: %{{x:.0f}}%<extra></extra>"
    }}
  ], {{
    barmode:"group", dragmode:false, paper_bgcolor:"transparent", plot_bgcolor:"transparent",
    font:{{family:"Inter, Segoe UI, sans-serif", color:colors.muted, size:10}},
    margin:{{l:Math.min(185, Math.max(92, longestLabel * 7)),r:105,t:10,b:52}},
    showlegend:true, legend:{{orientation:"h", x:0, y:-.22}},
    xaxis:{{range:[0,108], ticksuffix:"%", fixedrange:true, gridcolor:colors.grid}},
    yaxis:{{fixedrange:true, autorange:"reversed", gridcolor:"transparent"}}
  }}, plotConfig);
}}
function renderStudentProfiles(student) {{
  const dimensions = data.student_dimensions || [];
  const target = document.getElementById("studentProfileCards");
  if (!dimensions.length) {{
    target.innerHTML = '<article class="card"><h2 class="section-title">Profielen</h2><div class="empty">Er zijn geen classificaties aan de toetsvragen gekoppeld.</div></article>';
    return;
  }}
  target.innerHTML = dimensions.map(dimension => {{
    return `<article class="card profile-card"><div class="profile-header"><h2 class="section-title">${{esc(dimension.title)}}-profiel</h2></div><div class="profile-chart" id="student_bars_${{dimension.key}}"></div></article>`;
  }}).join("");
  dimensions.forEach(dimension => {{
    const entries = student.profiles[dimension.key] || [];
    studentBarProfileChart("student_bars_" + dimension.key, entries, student.name, dimension.title);
  }});
}}
function rankDisplay(item, total) {{
  if (!item || item.rank == null) return "-";
  const count = item.rank_count || total || data.participant_count;
  return Number(item.tied_count || 0) > 1 ? `${{item.rank}} gedeeld / ${{count}}` : `${{item.rank}} / ${{count}}`;
}}
function renderStudent() {{
  if (!data.participants.length) return;
  renderScopeBanners();
  const index = Number(document.getElementById("studentSelect").value || 0);
  const student = data.participants[index];
  const meanScore = data.summary.mean_score || 0;
  const scoreDifference = student.total_score - meanScore;
  const aboveAverage = scoreDifference >= 0;
  const gradeBlock = gradeAnalysisVisible
    ? `<div class="overview-stat"><div class="kpi-label">Cijfer</div><div class="overview-value">${{number(student.grade)}}</div><div class="kpi-note">${{student.sufficient ? "Voldoende" : "Onvoldoende"}}</div></div>`
    : "";
  const differenceLabel = gradeAnalysisVisible ? "Verschil met groep (cijfer)" : "Verschil met groep (score)";
  const differenceValue = scoreDifference;
  const differenceSuffix = gradeAnalysisVisible ? "" : " punt";
  const calloutText = gradeAnalysisVisible
    ? (aboveAverage ? "Boven gemiddeld resultaat. Deze leerling scoort hoger dan het groepsgemiddelde." : "Aandachtspunt. Deze leerling scoort lager dan het groepsgemiddelde.")
    : (aboveAverage ? "Boven gemiddeld resultaat op score." : "Aandachtspunt: score ligt onder het groepsgemiddelde.");
  document.getElementById("studentScore").innerHTML = `<div class="overview-stat"><div class="kpi-label">Score</div><div class="overview-value">${{number(student.total_score)}} / ${{number(data.maximum_score,0)}}</div><div class="kpi-note">${{percentage(student.score_percentage)}}</div></div>${{gradeBlock}}<div class="overview-stat"><div class="kpi-label">Percentiel</div><div class="overview-value">${{student.percentile ?? "-"}}</div><div class="kpi-note">Beter dan ${{percentage(student.percentile)}}</div></div><div class="overview-stat"><div class="kpi-label">Rang</div><div class="overview-value">${{rankDisplay(student, data.participant_count)}}</div></div><div class="overview-stat"><div class="kpi-label">${{differenceLabel}}</div><div class="overview-value ${{aboveAverage ? "good" : "bad"}}">${{aboveAverage ? "+" : ""}}${{number(differenceValue)}}${{differenceSuffix}}</div></div><div class="overview-message"><div class="callout ${{aboveAverage ? "good" : "attention"}}">${{calloutText}}</div></div>${{gradeAnalysisVisible ? "" : '<div class="overview-stat"><div class="kpi-note">Cijfers worden zichtbaar zodra de normering is vastgesteld.</div></div>'}}`;
  renderStudentProfiles(student);
  renderHeatmap("studentHeatmap", "studentHeatmapSelect", true, student.student_id);
  document.getElementById("studentItemRows").innerHTML = student.items.map(item => {{
    const level = item.maximum_score > 0 && item.score >= item.maximum_score ? "good" : item.score > 0 ? "attention" : "bad";
    const label = level === "good" ? "Goed" : level === "attention" ? "Deels goed" : "Fout";
    return `<tr><td>${{esc(item.label)}}</td><td>${{esc(item.component || "-")}}</td><td class="num">${{number(item.score)}}</td><td class="num">${{number(item.maximum_score)}}</td><td>${{badge({{level, label}})}}</td></tr>`;
  }}).join("");
  const profile = (data.student_dimensions || []).flatMap(dimension => (student.profiles[dimension.key] || []).map(item => ({{...item, dimension:dimension.title}})));
  const strong = profile.filter(item => item.percentage >= item.group_percentage && item.percentage >= 60).sort((a,b)=>b.percentage-a.percentage).slice(0,3);
  const concerns = profile.filter(item => item.percentage < item.group_percentage || item.percentage < 50).sort((a,b)=>a.percentage-b.percentage).slice(0,3);
  document.getElementById("strengths").innerHTML = strong.length ? strong.map(item=>`<div class="point"><span class="dot"></span><span>${{esc(item.dimension)}}: ${{esc(item.name)}} (${{percentage(item.percentage)}})</span></div>`).join("") : '<div class="mini-note">Nog geen duidelijk sterk onderdeel.</div>';
  document.getElementById("concerns").innerHTML = concerns.length ? concerns.map(item=>`<div class="point"><span class="dot attention"></span><span>${{esc(item.dimension)}}: ${{esc(item.name)}} (${{percentage(item.percentage)}})</span></div>`).join("") : '<div class="mini-note">Geen duidelijk aandachtspunt.</div>';
  document.getElementById("strengthCallout").innerHTML = aboveAverage ? '<div class="callout good">Deze leerling presteert op of boven het groepsgemiddelde.</div>' : "";
  document.getElementById("concernCallout").innerHTML = concerns.length ? '<div class="callout attention">Gebruik de vraaganalyse om gerichte feedback te geven.</div>' : "";
}}
function initialiseStudents() {{
  const select = document.getElementById("studentSelect");
  if (!data.participants.length) {{ select.innerHTML = '<option>Geen complete resultaten</option>'; return; }}
  select.innerHTML = data.participants.map((student,index)=>`<option value="${{index}}">${{esc(student.name)}}</option>`).join("");
  select.addEventListener("change", renderStudent);
}}
function initialiseHeatmaps() {{
  fillHeatmapSelect("groupHeatmapSelect", true);
  fillHeatmapSelect("studentHeatmapSelect");
  document.getElementById("groupHeatmapSelect").addEventListener("change", () => renderHeatmap("groupHeatmap", "groupHeatmapSelect", false, null, true));
  document.getElementById("studentHeatmapSelect").addEventListener("change", renderStudent);
}}
function showReportMessage(message, ok) {{
  const target = document.getElementById("studentReportMessage");
  target.textContent = message || "";
  target.style.color = ok ? colors.green : colors.red;
}}
function exportStudentReport(scope) {{
  if (!analysisBridge) {{
    showReportMessage("De exportfunctie wordt nog geladen. Probeer het opnieuw.", false);
    return;
  }}
  if (!data.participants.length) {{
    showReportMessage("Er zijn geen complete leerlingresultaten om te exporteren.", false);
    return;
  }}
  const index = Number(document.getElementById("studentSelect").value || 0);
  const student = data.participants[index];
  analysisBridge.exportStudentReports(scope, String(student.student_id), response => {{
    const result = JSON.parse(response);
    if (result.cancelled) return;
    showReportMessage(result.message, result.ok);
  }});
}}
document.getElementById("exportCurrentStudent").addEventListener("click", () => exportStudentReport("single"));
document.getElementById("exportAllStudents").addEventListener("click", () => exportStudentReport("all"));
renderGeneral();
initialiseHeatmaps();
renderGroupCharts();
initialiseStudents();
renderStudent();
</script>
</body>
</html>"""
