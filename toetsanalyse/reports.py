from __future__ import annotations

import base64
import json
import math
from io import BytesIO
from collections import defaultdict
from html import escape
from typing import Any

from .database import SubjectDatabase
from .results import QUESTION_ORDER_SQL


CHART_COLORS = [
    "#8d6bd1",
    "#4e8bd8",
    "#59b77c",
    "#ee6661",
    "#27a5a1",
    "#ed9632",
    "#55b6c3",
    "#f1b35e",
    "#8191a7",
]


def _distribution_display_title(title: str) -> str:
    if title == "RTTI":
        return "RTTI-niveaus"
    if title == "Vraagtype":
        return "Vraagtypes"
    if title.lower().startswith("domein"):
        return "Domeinen"
    return title


def _text(value: object, empty: str = "-") -> str:
    if value is None or str(value).strip() == "":
        return empty
    return str(value)


def _number(value: float) -> str:
    return f"{value:g}"


def _distribution(
    title: str,
    questions: list[dict[str, Any]],
    values: dict[int, str],
    total_points: float,
    include_missing_bucket: bool = True,
) -> dict[str, Any]:
    buckets: dict[str, dict[str, float | int]] = defaultdict(lambda: {"questions": 0, "points": 0.0})
    for question in questions:
        raw_name = values.get(question["id"])
        name = str(raw_name).strip() if raw_name is not None else ""
        if not name:
            if not include_missing_bucket:
                continue
            name = "Niet ingevuld"
        buckets[name]["questions"] += 1
        buckets[name]["points"] += question["maximum_score"]
    entries = []
    for name, values_for_name in sorted(
        buckets.items(), key=lambda entry: (-float(entry[1]["points"]), entry[0].lower())
    ):
        points = float(values_for_name["points"])
        entries.append(
            {
                "name": name,
                "questions": int(values_for_name["questions"]),
                "points": points,
                "percentage": (points / total_points * 100) if total_points else 0.0,
            }
        )
    return {"title": title, "entries": entries}


def matrix_report_data(database: SubjectDatabase, test_id: int) -> dict[str, Any]:
    tests = database.rows(
        "SELECT t.*, sy.name AS school_year, original.name AS original_name "
        "FROM tests t JOIN school_years sy ON sy.id=t.school_year_id "
        "LEFT JOIN tests original ON original.id=t.original_test_id WHERE t.id=?",
        (test_id,),
    )
    if not tests:
        raise ValueError("De geselecteerde toets bestaat niet meer.")
    test = dict(tests[0])
    groups = [
        row["name"]
        for row in database.rows(
            "SELECT c.name FROM test_classes tc JOIN classes c ON c.id=tc.class_id "
            "WHERE tc.test_id=? ORDER BY c.name",
            (test_id,),
        )
    ]
    taxonomies = [
        dict(row)
        for row in database.rows(
            "SELECT d.id, d.name FROM taxonomy_definitions d "
            "JOIN test_taxonomy_selections s ON s.taxonomy_id=d.id "
            "WHERE s.test_id=? ORDER BY d.id",
            (test_id,),
        )
    ]
    properties = [
        dict(row)
        for row in database.rows(
            "SELECT p.id, p.name, p.field_type FROM property_definitions p "
            "JOIN test_property_selections s ON s.property_id=p.id "
            "WHERE s.test_id=? AND p.is_active=1 ORDER BY p.id",
            (test_id,),
        )
    ]
    questions = [
        dict(row)
        for row in database.rows(
            "SELECT id, question_number || COALESCE(subquestion, '') AS label, maximum_score, "
            "short_description, expected_time_minutes "
            f"FROM matrix_questions WHERE test_id=? ORDER BY {QUESTION_ORDER_SQL}",
            (test_id,),
        )
    ]
    for question in questions:
        question["maximum_score"] = float(question["maximum_score"])

    taxonomy_values: dict[int, dict[int, str]] = {taxonomy["id"]: {} for taxonomy in taxonomies}
    for row in database.rows(
        "SELECT qtv.question_id, qtv.taxonomy_id, tv.name AS value_name "
        "FROM question_taxonomy_values qtv JOIN taxonomy_values tv ON tv.id=qtv.taxonomy_value_id "
        "JOIN matrix_questions q ON q.id=qtv.question_id WHERE q.test_id=?",
        (test_id,),
    ):
        taxonomy_values.setdefault(row["taxonomy_id"], {})[row["question_id"]] = row["value_name"]

    property_values: dict[int, dict[int, str]] = {definition["id"]: {} for definition in properties}
    for row in database.rows(
        "SELECT qpv.question_id, qpv.property_id, qpv.value FROM question_property_values qpv "
        "JOIN matrix_questions q ON q.id=qpv.question_id WHERE q.test_id=?",
        (test_id,),
    ):
        values_for_property = property_values.setdefault(row["property_id"], {})
        question_id = row["question_id"]
        incoming = str(row["value"]).strip() if row["value"] is not None else ""
        current = str(values_for_property.get(question_id)).strip() if values_for_property.get(question_id) is not None else ""
        if incoming or not current:
            values_for_property[question_id] = row["value"]

    total_points = sum(question["maximum_score"] for question in questions)
    timed_questions = [question for question in questions if question["expected_time_minutes"] is not None]
    expected_time = sum(float(question["expected_time_minutes"]) for question in timed_questions)
    expected_assignments = len(questions) * (len(taxonomies) + len(properties))
    completed_assignments = sum(
        1
        for taxonomy in taxonomies
        for question in questions
        if taxonomy_values.get(taxonomy["id"], {}).get(question["id"])
    ) + sum(
        1
        for definition in properties
        for question in questions
        if property_values.get(definition["id"], {}).get(question["id"])
    )
    distributions = [
        _distribution(taxonomy["name"], questions, taxonomy_values.get(taxonomy["id"], {}), total_points)
        for taxonomy in taxonomies
    ]
    distributions.extend(
        _distribution(
            definition["name"],
            questions,
            property_values.get(definition["id"], {}),
            total_points,
            include_missing_bucket=False,
        )
        for definition in properties
    )
    return {
        "subject": database.meta("subject_name", ""),
        "test": test,
        "groups": groups,
        "taxonomies": taxonomies,
        "properties": properties,
        "questions": questions,
        "taxonomy_values": taxonomy_values,
        "property_values": property_values,
        "total_points": total_points,
        "expected_time": expected_time,
        "timed_count": len(timed_questions),
        "coverage": (completed_assignments / expected_assignments * 100) if expected_assignments else None,
        "distributions": distributions,
    }


def _duration(data: dict[str, Any]) -> str:
    if not data["timed_count"]:
        return "Niet ingevuld"
    return f'{_number(data["expected_time"])} minuten'


def _chip(value: object, style: str = "neutral") -> str:
    if value is None or str(value).strip() == "":
        return '<span class="chip empty-chip">-</span>'
    return f'<span class="chip {style}">{escape(str(value))}</span>'


def _time_distribution(questions: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, dict[str, float | int]] = defaultdict(lambda: {"questions": 0, "points": 0.0})
    for question in questions:
        if question["expected_time_minutes"] is None:
            continue
        minutes = float(question["expected_time_minutes"])
        if minutes <= 2:
            label = "0-2 minuten"
        elif minutes <= 5:
            label = "2-5 minuten"
        else:
            label = "5+ minuten"
        buckets[label]["questions"] += 1
        buckets[label]["points"] += minutes
    total_minutes = sum(float(values["points"]) for values in buckets.values())
    entries = []
    for name, values in buckets.items():
        minutes = float(values["points"])
        entries.append(
            {
                "name": name,
                "questions": int(values["questions"]),
                "points": minutes,
                "percentage": (minutes / total_minutes * 100) if total_minutes else 0.0,
            }
        )
    entries.sort(key=lambda entry: -float(entry["points"]))
    return {"title": "Tijdsverdeling", "entries": entries}


def _legend_marker_source(color: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 10 10">'
        f'<rect x="0.5" y="0.5" width="9" height="9" rx="2" ry="2" fill="{color}" '
        'stroke="rgba(16,35,58,.25)" stroke-width="1"/></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _info_cell(label: str, value: object, colspan: int = 1) -> str:
    span = f' colspan="{colspan}"' if colspan > 1 else ""
    return (
        f'<td class="info-cell"{span}><div class="info-label">{escape(label)}</div>'
        f'<div class="info-value">{escape(_text(value))}</div></td>'
    )


def _svg_pie_chart_source(entries: list[dict[str, Any]], colors: dict[str, str] | None = None) -> str:
    size = 220
    center = size / 2
    radius = 86
    total_points = sum(float(entry["points"]) for entry in entries)
    shapes = [
        '<rect width="100%" height="100%" fill="#ffffff" />',
        f'<circle cx="{center:g}" cy="{center:g}" r="{radius}" fill="#edf2f7" />',
    ]
    if total_points:
        angle = -math.pi / 2
        for index, entry in enumerate(entries):
            points = float(entry["points"])
            if not points:
                continue
            fraction = points / total_points
            color = (colors or {}).get(entry["name"], CHART_COLORS[index % len(CHART_COLORS)])
            if fraction >= 0.999999:
                shapes.append(
                    f'<circle cx="{center:g}" cy="{center:g}" r="{radius}" '
                    f'fill="{color}" stroke="#ffffff" stroke-width="2.5" />'
                )
                shapes.append(f'<text x="{center:g}" y="{center + 4:g}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="#ffffff">100%</text>')
                break
            end_angle = angle + fraction * math.tau
            x1 = center + radius * math.cos(angle)
            y1 = center + radius * math.sin(angle)
            x2 = center + radius * math.cos(end_angle)
            y2 = center + radius * math.sin(end_angle)
            large_arc = 1 if fraction > 0.5 else 0
            shapes.append(
                f'<path d="M {center} {center} L {x1:.2f} {y1:.2f} '
                f'A {radius} {radius} 0 {large_arc} 1 {x2:.2f} {y2:.2f} Z" '
                f'fill="{color}" stroke="#ffffff" stroke-width="2.5" />'
            )
            if fraction >= 0.09:
                text_angle = angle + fraction * math.pi
                text_radius = 54
                text_x = center + text_radius * math.cos(text_angle)
                text_y = center + text_radius * math.sin(text_angle) + 4
                shapes.append(
                    f'<text x="{text_x:.2f}" y="{text_y:.2f}" text-anchor="middle" '
                    f'font-family="Arial, sans-serif" font-size="11" font-weight="bold" '
                    f'fill="#ffffff">{fraction * 100:.0f}%</text>'
                )
            angle = end_angle
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
        + "".join(shapes)
        + "</svg>"
    )
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _pie_chart_source(entries: list[dict[str, Any]], colors: dict[str, str] | None = None) -> str:
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError:
        return _svg_pie_chart_source(entries, colors)

    values = [float(entry["points"]) for entry in entries]
    total_points = sum(values)
    palette = [
        (colors or {}).get(entry["name"], CHART_COLORS[index % len(CHART_COLORS)])
        for index, entry in enumerate(entries)
    ]
    figure = Figure(figsize=(2.3, 2.3), dpi=180, facecolor="white")
    FigureCanvasAgg(figure)
    axis = figure.add_subplot(111)
    if total_points:
        axis.pie(
            values,
            colors=palette,
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "white", "linewidth": 1.5},
            autopct=lambda percentage: f"{percentage:.0f}%" if percentage >= 8 else "",
            pctdistance=0.63,
            textprops={"color": "white", "fontsize": 9, "fontweight": "bold"},
        )
    else:
        axis.pie([1], colors=["#edf2f7"], wedgeprops={"edgecolor": "white"})
    axis.set_aspect("equal")
    output = BytesIO()
    figure.savefig(output, format="png", bbox_inches="tight", pad_inches=0.06, facecolor="white")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def _chart_card_content(
    distribution: dict[str, Any],
    title: str,
    unit: str = "punten",
    colors_by_name: dict[str, str] | None = None,
) -> str:
    entries = distribution["entries"]
    colors = [
        (colors_by_name or {}).get(entry["name"], CHART_COLORS[index % len(CHART_COLORS)])
        for index, entry in enumerate(entries)
    ]
    fallback_colors = {
        entry["name"]: colors[index]
        for index, entry in enumerate(entries)
    }
    fallback_chart = _pie_chart_source(entries, fallback_colors)
    amount_suffix = "min" if unit == "minuten" else "pnt"
    legend_rows = []
    for index, entry in enumerate(entries):
        marker_source = _legend_marker_source(colors[index])
        legend_rows.append(
            '<tr class="legend-row"><td class="legend-swatch"><img class="marker" width="10" height="10" src="'
            + marker_source
            + '" alt=""></td><td class="legend-label">'
            + escape(entry["name"])
            + '</td><td class="legend-amount">'
            + f'{entry["percentage"]:.0f}% ({_number(entry["points"])} {amount_suffix})'
            + "</td></tr>"
        )
    total = sum(float(entry["points"]) for entry in entries)
    total_value = f'{_number(total)} {unit}'
    chart_payload = {
        "labels": [entry["name"] for entry in entries],
        "series": [float(entry["points"]) for entry in entries],
        "colors": colors,
        "unit": unit,
    }
    return (
        '<table class="distribution-card-shell" width="100%"><tr><td class="distribution-card-cell"><div class="distribution-card"><h3>'
        + escape(title)
        + "</h3>"
        + f'<div class="distribution-chart" data-chart=\'{escape(json.dumps(chart_payload, ensure_ascii=True))}\'><img class="distribution-chart-fallback" width="180" height="180" src="{fallback_chart}" alt="Verdeling {escape(title)}"></div>'
        + '<table class="distribution-legend"><tbody>'
        + "".join(legend_rows)
        + '</tbody></table><div class="distribution-total">Totaal: '
        + escape(total_value)
        + "</div></div></td></tr></table></td>"
    )


def _chart_card(
    distribution: dict[str, Any],
    title: str,
    unit: str = "punten",
    colors_by_name: dict[str, str] | None = None,
) -> str:
    return (
        '<td class="chart-cell" width="32%">'
        + _chart_card_content(distribution, title, unit=unit, colors_by_name=colors_by_name)
        + "</td>"
    )


def _comparison_color_map(*entry_groups: list[dict[str, Any]]) -> dict[str, str]:
    names: list[str] = []
    seen: set[str] = set()
    for group in entry_groups:
        for entry in group:
            name = str(entry["name"])
            if name not in seen:
                seen.add(name)
                names.append(name)
    return {
        name: CHART_COLORS[index % len(CHART_COLORS)]
        for index, name in enumerate(names)
    }


def _render_distributions(data: dict[str, Any]) -> str:
    distribution_cards = []
    for distribution in data["distributions"]:
        title = _distribution_display_title(distribution["title"])
        distribution_cards.append(_chart_card(distribution, title))
    time_distribution = _time_distribution(data["questions"])
    if time_distribution["entries"]:
        distribution_cards.append(_chart_card(time_distribution, "Tijdsverdeling", "minuten"))
    if not distribution_cards:
        return '<div class="distribution-empty">Kies taxonomieën of classificaties om verdelingen te tonen.</div>'
    rows = []
    cards_per_row = 3
    for start in range(0, len(distribution_cards), cards_per_row):
        cards = distribution_cards[start : start + cards_per_row]
        if len(cards) == 1:
            cards = ['<td class="chart-placeholder" width="32%">&nbsp;</td>'] + cards
        cells = []
        for index, card in enumerate(cards):
            if index:
                cells.append('<td class="chart-spacer" width="2%">&nbsp;</td>')
            cells.append(card)
        while len(cards) < cards_per_row:
            if cells:
                cells.append('<td class="chart-spacer" width="2%">&nbsp;</td>')
            cells.append('<td class="chart-placeholder" width="32%">&nbsp;</td>')
            cards.append("")
        page_break = (
            '<p class="pdf-break">[[PAGE_BREAK]]</p>'
            if rows
            else ""
        )
        rows.append(
            page_break
            + '<table class="chart-grid" width="100%" cellspacing="0" cellpadding="0"><tr>'
            + "".join(cells)
            + "</tr></table>"
        )
    script = """
<script src="https://cdn.jsdelivr.net/npm/apexcharts"></script>
<script>
(function () {
  function renderDistributionCharts() {
    var chartNodes = Array.prototype.slice.call(document.querySelectorAll(".distribution-chart[data-chart]"));
    if (!chartNodes.length) {
      window.__chartsReady = true;
      return;
    }
    if (typeof ApexCharts === "undefined") {
      chartNodes.forEach(function (node) {
        if (!node.querySelector(".distribution-chart-fallback")) {
          node.innerHTML = '<div class="chart-fallback">ApexCharts kon niet laden. Bundel ApexCharts lokaal voor offline/PDF-exports.</div>';
        }
      });
      window.__chartsReady = true;
      return;
    }
    var renderJobs = chartNodes.map(function (node) {
      var payload = JSON.parse(node.getAttribute("data-chart") || "{}");
      var options = {
        chart: {
          type: "donut",
          width: 180,
          height: 180,
          animations: { enabled: false },
          toolbar: { show: false }
        },
        labels: payload.labels || [],
        series: payload.series || [],
        colors: payload.colors || [],
        legend: { show: false },
        dataLabels: {
          enabled: true,
          formatter: function (value) { return value >= 8 ? Math.round(value) + "%" : ""; },
          style: { fontSize: "11px", fontWeight: 600, colors: ["#ffffff"] }
        },
        stroke: { width: 2, colors: ["#ffffff"] },
        states: { hover: { filter: { type: "none" } }, active: { filter: { type: "none" } } },
        plotOptions: {
          pie: {
            donut: { size: "62%" },
            expandOnClick: false
          }
        },
        tooltip: { enabled: true, y: { formatter: function (value) { return value + " " + (payload.unit || "punten"); } } }
      };
      var chart = new ApexCharts(node, options);
      return chart.render().then(function () {
        var fallback = node.querySelector(".distribution-chart-fallback");
        if (fallback) {
          fallback.style.display = "none";
        }
      });
    });
    Promise.all(renderJobs)
      .then(function () { window.__chartsReady = true; })
      .catch(function () { window.__chartsReady = true; });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderDistributionCharts);
  } else {
    renderDistributionCharts();
  }
})();
</script>
"""
    return '<div class="distribution-cards">' + "".join(rows) + "</div>" + script


def _render_distribution_comparison(
    current_data: dict[str, Any],
    original_data: dict[str, Any],
) -> str:
    original_by_title = {
        str(distribution["title"]): distribution
        for distribution in original_data["distributions"]
    }
    sections: list[str] = []
    for distribution in current_data["distributions"]:
        raw_title = str(distribution["title"])
        original_distribution = original_by_title.get(raw_title)
        if original_distribution is None:
            continue
        display_title = _distribution_display_title(raw_title)
        colors_by_name = _comparison_color_map(
            list(original_distribution["entries"]),
            list(distribution["entries"]),
        )
        sections.append(
            '<div class="comparison-block">'
            + f'<h3 class="comparison-block-title">{escape(display_title)}</h3>'
            + '<table class="comparison-grid" width="100%" cellspacing="0" cellpadding="0"><tr>'
            + '<td class="comparison-chart-cell" width="49%">'
            + _chart_card_content(
                original_distribution,
                f'Originele toets - {original_data["test"]["name"]}',
                colors_by_name=colors_by_name,
            )
            + "</td>"
            + '<td class="comparison-gap" width="2%">&nbsp;</td>'
            + '<td class="comparison-chart-cell" width="49%">'
            + _chart_card_content(
                distribution,
                f'Herkansing - {current_data["test"]["name"]}',
                colors_by_name=colors_by_name,
            )
            + "</td>"
            + "</tr></table></div>"
        )
    if not sections:
        return ""
    return (
        '<p class="pdf-break">[[PAGE_BREAK]]</p>'
        '<div class="section section-heading comparison-section">'
        '<div class="section-title">4. Vergelijking met originele toets</div>'
        f'<p class="comparison-note">Vergelijk de verdeling van taxonomieen en classificaties tussen '
        f'<b>{escape(original_data["test"]["name"])}</b> en <b>{escape(current_data["test"]["name"])}</b>.</p>'
        + "".join(sections)
        + "</div>"
    )


def _legacy_build_matrix_report_html(database: SubjectDatabase, test_id: int) -> str:
    data = matrix_report_data(database, test_id)
    test = data["test"]
    questions = data["questions"]
    taxonomies = data["taxonomies"]
    properties = data["properties"]
    taxonomy_names = ", ".join(taxonomy["name"] for taxonomy in taxonomies) or "Niet geselecteerd"
    property_names = ", ".join(definition["name"] for definition in properties) or "Geen extra velden"
    metadata = "".join(
        [
            _metadata_panel("Toetsinformatie", [("Vak", data["subject"]), ("Type", test["test_type"])]),
            _metadata_panel("Planning", [("Periode", test["period"]), ("Datum", test["test_date"])]),
            _metadata_panel(
                "Doelgroep",
                [("Niveau / jaarlaag", f'{_text(test["level"])} / {_text(test["grade_year"])}'), ("Groepen", ", ".join(data["groups"]) or None)],
            ),
            _metadata_panel(
                "Analysekader",
                [("Taxonomie", taxonomy_names), ("Classificaties", property_names)],
            ),
        ]
    )
    if test["original_name"]:
        context = '<div class="resit-tag">Herkansing van&nbsp;&nbsp; ' + escape(test["original_name"]) + "</div>"
    else:
        context = '<div class="report-tag">TOETSMATRIJS &middot; KWALITEITSOVERZICHT</div>'

    coverage = f'{data["coverage"]:.0f}%' if data["coverage"] is not None else "-"
    kpis = "".join(
        [
            _kpi_card("Omvang", len(questions), "vragen"),
            _kpi_card("Maximale score", _number(data["total_points"]), "punten"),
            _kpi_card("Tijdindicatie", _duration(data), "vragenraming"),
            _kpi_card("Metadata ingevuld", coverage, "taxonomie en classificatie"),
        ]
    )

    headers = ["Vraag", "Punten", "Omschrijving", "Tijd (min.)"]
    headers.extend(taxonomy["name"] for taxonomy in taxonomies)
    headers.extend(definition["name"] for definition in properties)
    table_head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    table_rows = []
    for question in questions:
        cells = [
            f'<td class="question-label">{escape(question["label"])}</td>',
            f'<td class="points">{_number(question["maximum_score"])}</td>',
            f'<td class="description">{escape(_text(question["short_description"], ""))}</td>',
            f'<td class="time">{escape(_text(question["expected_time_minutes"], ""))}</td>',
        ]
        cells.extend(
            '<td>' + _chip(data["taxonomy_values"].get(taxonomy["id"], {}).get(question["id"]), "taxonomy") + "</td>"
            for taxonomy in taxonomies
        )
        for definition in properties:
            value = data["property_values"].get(definition["id"], {}).get(question["id"])
            style = "type" if definition["name"] == "Vraagtype" else "domain" if definition["name"].lower().startswith("domein") else "neutral"
            cells.append("<td>" + _chip(value, style) + "</td>")
        table_rows.append("<tr>" + "".join(cells) + "</tr>")
    if not table_rows:
        table_rows.append(f'<tr><td class="empty" colspan="{len(headers)}">Er zijn nog geen vragen ingevuld.</td></tr>')

    statistics = _render_distributions(data["distributions"])
    comparison = ""
    if test["original_test_id"]:
        comparison = _comparison_html(data, matrix_report_data(database, test["original_test_id"]))

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; }}
body {{ background: #f5f7fb; color: #243247; font-family: Inter, Aptos, "Segoe UI", Arial, sans-serif; font-size: 9.5pt; line-height: 1.45; margin: 26px; }}
table {{ border-collapse: collapse; width: 100%; }}
.hero {{ background: #142a43; border-radius: 14px; color: #ffffff; padding: 25px 28px 22px; }}
.hero-layout td {{ border: 0; vertical-align: top; }}
.hero-main {{ width: 67%; }}
.eyebrow {{ color: #9fb6cf; font-size: 8pt; font-weight: bold; letter-spacing: 1.5px; }}
h1 {{ font-size: 24pt; font-weight: 600; letter-spacing: -.4px; margin: 8px 0 7px; }}
.subtitle {{ color: #d3dfed; font-size: 10.5pt; margin: 0; }}
.hero-context {{ text-align: right; width: 33%; }}
.report-tag, .resit-tag {{ background: #203b56; border: 1px solid #36516b; border-radius: 15px; color: #d9e5f1; display: inline-block; font-size: 7.5pt; font-weight: bold; letter-spacing: .8px; padding: 7px 11px; text-transform: uppercase; }}
.resit-tag {{ background: #314158; color: #f0e4ca; }}
.section-header {{ margin: 25px 0 12px; }}
.section-kicker {{ color: #66809b; font-size: 7.5pt; font-weight: bold; letter-spacing: 1.3px; margin-bottom: 5px; }}
h2 {{ color: #142a43; font-size: 15pt; font-weight: 600; margin: 0 0 4px; }}
.section-description {{ color: #64758a; margin: 0; }}
.metadata-grid {{ border-collapse: separate; border-spacing: 8px 0; margin: 0 -8px; }}
.meta-panel {{ background: #ffffff; border: 1px solid #e3e9f0; border-radius: 10px; padding: 12px 13px; vertical-align: top; width: 25%; }}
.meta-title {{ color: #142a43; font-size: 9pt; font-weight: bold; margin-bottom: 9px; }}
.meta-table td {{ border: 0; padding: 3px 0; vertical-align: top; }}
.meta-label {{ color: #75849a; font-size: 8pt; width: 39%; }}
.meta-value {{ color: #27384d; font-size: 8.5pt; font-weight: 600; }}
.kpi-grid {{ border-collapse: separate; border-spacing: 8px 0; margin: 15px -8px 0; }}
.kpi {{ background: #ffffff; border: 1px solid #e3e9f0; border-radius: 10px; padding: 13px 15px; vertical-align: top; width: 25%; }}
.kpi-label {{ color: #73849a; font-size: 7.5pt; font-weight: bold; letter-spacing: .8px; text-transform: uppercase; }}
.kpi-value {{ color: #142a43; font-size: 19pt; font-weight: 600; margin: 5px 0 2px; }}
.kpi-note {{ color: #78889c; font-size: 8pt; }}
.matrix-card {{ background: #ffffff; border: 1px solid #dbe4ed; font-size: 8.3pt; }}
.matrix-table {{ font-size: 8.3pt; }}
.matrix-table th {{ background: #243b53; border-bottom: 1px solid #1b3046; color: #ffffff; font-size: 7.5pt; font-weight: bold; letter-spacing: .5px; padding: 10px 8px; text-align: left; text-transform: uppercase; white-space: nowrap; }}
.matrix-table td {{ border-bottom: 1px solid #edf1f5; padding: 8px 8px; vertical-align: middle; }}
.matrix-table tr:nth-child(even) td {{ background: #fbfcfd; }}
.question-label {{ color: #142a43; font-size: 9pt; font-weight: bold; }}
.points {{ color: #142a43; font-weight: bold; text-align: right; }}
.description {{ color: #47596e; min-width: 125px; }}
.time {{ color: #60748c; text-align: right; }}
.chip {{ border-radius: 10px; display: inline-block; font-size: 7.5pt; font-weight: 600; padding: 3px 8px; white-space: nowrap; }}
.taxonomy {{ background: #e9f1fb; color: #36608b; }}
.domain {{ background: #e9f5ef; color: #30704c; }}
.type {{ background: #f3edfa; color: #66518c; }}
.neutral {{ background: #eef2f6; color: #596a7e; }}
.empty-chip {{ background: #f4f6f8; color: #9aa6b5; }}
.analysis-section {{ page-break-before: always; }}
.analysis-card {{ background: #ffffff; border: 1px solid #dfe7ef; margin-bottom: 14px; page-break-inside: avoid; width: 100%; }}
.analysis-pad {{ padding: 14px 16px; }}
.analysis-heading td {{ border: 0; padding: 0 0 10px; }}
.analysis-heading h3 {{ color: #142a43; font-size: 12pt; font-weight: 600; margin: 0; }}
.insight-cell {{ text-align: right; }}
.insight {{ background: #eff5fa; border-radius: 12px; color: #587089; font-size: 8pt; padding: 5px 10px; }}
.stacked-bar {{ border-collapse: separate; border-radius: 5px; height: 9px; margin: 0 0 15px; overflow: hidden; }}
.stacked-bar td {{ border: 0; height: 9px; padding: 0; }}
.analysis-layout td {{ border: 0; vertical-align: top; }}
.distribution-table {{ padding-right: 22px; width: 64%; }}
.summary-table {{ font-size: 8.2pt; }}
.summary-table th, .comparison th {{ background: #e6edf5; border-bottom: 1px solid #ced9e5; color: #334a62; font-size: 7.4pt; font-weight: bold; letter-spacing: .25px; padding: 8px 6px; text-align: left; text-transform: uppercase; white-space: nowrap; }}
.summary-table td, .comparison td {{ border-bottom: 1px solid #eef2f6; color: #36495f; padding: 8px; }}
.summary-table td:first-child {{ padding-right: 14px; }}
.summary-table td:nth-child(2), .summary-table td:nth-child(3), .summary-table td:nth-child(4) {{ text-align: right; }}
.pie-column {{ border-left: 1px solid #edf1f5 !important; padding: 0 0 0 18px !important; text-align: center; width: 36%; }}
.pie {{ margin: 3px auto 7px; }}
.pie-title, .legend-title {{ color: #78899e; font-size: 7.3pt; font-weight: bold; letter-spacing: .8px; text-transform: uppercase; }}
.legend-title {{ margin-top: 4px; text-align: left; }}
.legend-item {{ color: #4d6076; display: inline-block; font-size: 7.8pt; margin: 6px 10px 0 0; text-align: left; white-space: nowrap; }}
.marker {{ border-radius: 4px; display: inline-block; height: 8px; margin-right: 7px; width: 8px; }}
.empty, .empty-panel {{ color: #71849a; font-style: italic; padding: 14px; }}
.comparison-header {{ margin-top: 28px; }}
.comparison-banner {{ background: #edf3f8; border-left: 3px solid #4c78a8; color: #4e6278; margin: 12px 0; padding: 10px 13px; }}
.comparison {{ background: #ffffff; border: 1px solid #e3e9f0; margin: 0 0 15px; }}
.comparison td:first-child {{ font-weight: bold; }}
.comparison-title {{ color: #142a43; font-size: 11pt; margin: 0 0 9px; }}
.comparison-charts {{ background: #ffffff; border: 1px solid #e3e9f0; margin: -8px 0 20px; }}
.comparison-charts td {{ background: #ffffff; border: 0; padding: 12px; text-align: center; vertical-align: top; width: 34%; }}
.comparison-charts .comparison-legend {{ text-align: left; width: 32%; }}
</style>
</head>
<body>
<div class="hero">
 <table class="hero-layout"><tr>
  <td class="hero-main"><div class="eyebrow">ASSESSMENT ANALYTICS / TOETSMATRIJS</div>
  <h1>{escape(test["name"])}</h1>
  <p class="subtitle">{escape(data["subject"])} &nbsp;&middot;&nbsp; {escape(test["school_year"])} &nbsp;&middot;&nbsp; {escape(test["period"])}</p></td>
  <td class="hero-context">{context}</td>
 </tr></table>
</div>
<div class="section-header"><div class="section-kicker">CONTEXT</div><h2>Algemene informatie over deze toets</h2>
<p class="section-description">Kerngegevens en gekozen analysekaders voor kwaliteitsbespreking.</p></div>
<table class="metadata-grid"><tr>{metadata}</tr></table>
<table class="kpi-grid"><tr>{kpis}</tr></table>
<div class="section-header"><div class="section-kicker">CONSTRUCTIE</div><h2>Toetsmatrijs</h2>
<p class="section-description">Vraagopbouw, puntengewicht en inhoudelijke classificatie.</p></div>
<table class="matrix-card matrix-table"><thead><tr>{table_head}</tr></thead><tbody>{''.join(table_rows)}</tbody></table>
<div class="section-header analysis-section"><div class="section-kicker">ANALYSE</div><h2>Verdeling van de toets</h2>
<p class="section-description">Puntenbalans over taxonomieën, domeinen en vraagtypen.</p></div>
{statistics}
{comparison}
</body>
</html>"""


def build_matrix_report_html(database: SubjectDatabase, test_id: int) -> str:
    data = matrix_report_data(database, test_id)
    test = data["test"]
    questions = data["questions"]
    taxonomies = data["taxonomies"]
    properties = data["properties"]
    audience = " ".join(value for value in (_text(test["level"], ""), _text(test["grade_year"], "")) if value)
    groups = ", ".join(data["groups"]) or "-"
    info_rows = [
        [
            ("Vak", data["subject"]),
            ("Toetsnaam", test["name"]),
            ("Niveau", audience or "-"),
        ],
        [
            ("Schooljaar", test["school_year"]),
            ("Periode", test["period"]),
            ("Totale punten", _number(data["total_points"])),
        ],
        [
            ("Aangemaakt op", _text(test.get("created_at"))),
            ("Aantal vragen", len(questions)),
            ("Geschatte tijdsduur", _duration(data)),
        ],
        [
            ("Groepen", groups),
            ("Toetssoort", test["test_type"]),
            ("Herkansing van", test["original_name"]) if test["original_name"] else ("Datum", test["test_date"]),
        ],
    ]
    info_grid = "".join(
        "<tr>" + "".join(_info_cell(label, value) for label, value in row) + "</tr>"
        for row in info_rows
    )

    headers = ["Vraag", "Punten"]
    headers.extend(taxonomy["name"] for taxonomy in taxonomies)
    headers.extend(definition["name"] for definition in properties)
    headers.extend(["Tijd (min)", "Omschrijving"])
    table_head = "".join(f"<th>{escape(header)}</th>" for header in headers)
    table_rows = []
    for question in questions:
        cells = [
            f'<td class="question-label">{escape(question["label"])}</td>',
            f'<td class="points">{_number(question["maximum_score"])}</td>',
        ]
        cells.extend(
            '<td>' + _chip(data["taxonomy_values"].get(taxonomy["id"], {}).get(question["id"]), "taxonomy") + "</td>"
            for taxonomy in taxonomies
        )
        for definition in properties:
            value = data["property_values"].get(definition["id"], {}).get(question["id"])
            style = (
                "type"
                if definition["name"] == "Vraagtype"
                else "domain"
                if definition["name"].lower().startswith("domein")
                else "neutral"
            )
            cells.append("<td>" + _chip(value, style) + "</td>")
        cells.extend(
            [
                f'<td class="time">{escape(_text(question["expected_time_minutes"], ""))}</td>',
                f'<td class="description">{escape(_text(question["short_description"], ""))}</td>',
            ]
        )
        table_rows.append("<tr>" + "".join(cells) + "</tr>")
    if not table_rows:
        table_rows.append(f'<tr><td class="no-data" colspan="{len(headers)}">Er zijn nog geen vragen ingevuld.</td></tr>')
    # Qt's rich text printer ignores CSS transforms; shrink printable table metrics instead.
    matrix_rows = max(len(questions), 1)
    matrix_columns = max(len(headers), 1)
    estimated_height = 90 + matrix_rows * 24
    estimated_width = 240 + matrix_columns * 115
    height_scale = min(1.0, 400 / estimated_height)
    width_scale = min(1.0, 1020 / estimated_width)
    matrix_scale = max(0.55, min(1.0, height_scale, width_scale))
    matrix_font_size = max(5.1, 7.7 * matrix_scale)
    matrix_header_size = max(5.0, 7.2 * matrix_scale)
    matrix_cell_padding = max(2.5, 6.0 * matrix_scale)
    matrix_chip_size = max(5.0, 7.4 * matrix_scale)
    matrix_chip_padding = max(2.0, 3.0 * matrix_scale)
    if matrix_rows >= 12:
        matrix_font_size = min(matrix_font_size, 6.35)
        matrix_header_size = min(matrix_header_size, 6.05)
        matrix_cell_padding = min(matrix_cell_padding, 3.1)
        matrix_chip_size = min(matrix_chip_size, 5.9)
        matrix_chip_padding = min(matrix_chip_padding, 1.4)

    comparison = ""
    if test.get("original_test_id"):
        comparison = _render_distribution_comparison(
            data,
            matrix_report_data(database, int(test["original_test_id"])),
        )

    return f"""<!DOCTYPE html>
<html lang="nl">
<head>
<meta charset="utf-8">
<style>
@page {{ size: A4 landscape; margin: 10mm; }}
* {{ box-sizing: border-box; }}
body {{ background: #f6f8fb; color: #172c4a; font-family: Inter, Aptos, "Segoe UI", Arial, sans-serif; font-size: 9pt; line-height: 1.38; margin: 0; padding: 16px; }}
table {{ border-collapse: collapse; width: 100%; }}
.report {{ margin: 0 auto; max-width: 1120px; }}
.report-header {{ margin: 0 0 16px; }}
h1 {{ color: #112947; font-size: 23pt; font-weight: 650; letter-spacing: -.45px; margin: 0 0 8px; }}
.subtitle {{ color: #586d88; font-size: 10pt; margin: 0; }}
.subtitle .dot {{ color: #c1ccda; padding: 0 10px; }}
.section {{ background: #ffffff; border: 1px solid #dfe7f0; border-radius: 12px; margin-bottom: 14px; padding: 14px 12px; }}
.section-title {{ color: #122a48; font-size: 13pt; font-weight: 650; margin: 0 0 14px 8px; }}
.section-heading {{ margin-bottom: 12px; padding: 14px 12px; }}
.section-heading .section-title {{ margin: 0 0 0 8px; }}
.info-grid {{ border: 1px solid #e4ebf3; border-radius: 9px; table-layout: fixed; }}
.info-cell {{ border-bottom: 1px solid #e7edf4; border-right: 1px solid #e7edf4; padding: 12px 15px; vertical-align: top; width: 33.333%; }}
.info-grid tr:last-child .info-cell {{ border-bottom: 0; }}
.info-grid .info-cell:last-child {{ border-right: 0; }}
.info-label {{ color: #647793; font-size: 7.7pt; font-weight: 600; margin-bottom: 5px; }}
.info-value {{ color: #203855; font-size: 9pt; font-weight: 500; }}
.pdf-break {{ margin: 0; padding: 0; font-size: 1px; line-height: 1px; color: #f6f8fb; -qt-paragraph-type:empty; }}
.matrix-section {{ break-inside: avoid-page; page-break-inside: avoid; }}
.table-wrap {{ border: 1px solid #e2e9f1; border-radius: 8px; overflow: hidden; break-inside: avoid-page; page-break-inside: avoid; }}
.matrix-table {{ background: #ffffff; font-size: {matrix_font_size:.2f}pt; table-layout: auto; break-inside: avoid-page; page-break-inside: avoid; }}
.matrix-table th {{ background: #f5f7fb; border-bottom: 1px solid #e2e9f1; color: #415573; font-size: {matrix_header_size:.2f}pt; font-weight: 650; padding: {matrix_cell_padding:.2f}px; text-align: left; white-space: nowrap; word-break: normal; }}
.matrix-table td {{ border-bottom: 1px solid #edf1f6; color: #384d69; padding: {matrix_cell_padding:.2f}px; vertical-align: middle; word-break: normal; }}
.matrix-table tbody tr:nth-child(even) td {{ background: #fbfcfe; }}
.matrix-table tbody tr:last-child td {{ border-bottom: 0; }}
.question-label {{ color: #213856; font-weight: 600; white-space: nowrap; }}
.points {{ color: #213856; font-weight: 600; white-space: nowrap; }}
.time {{ white-space: nowrap; }}
.description {{ min-width: 130px; }}
.chip {{ border-radius: 12px; display: inline-block; font-size: {matrix_chip_size:.2f}pt; font-weight: 600; padding: {matrix_chip_padding:.2f}px 7px; white-space: nowrap; }}
.taxonomy {{ background: #efe8fb; color: #6542ad; }}
.domain {{ background: #fff0df; color: #bd5c14; }}
.type {{ background: #e4f5f6; color: #16747d; }}
.neutral {{ background: #edf2f7; color: #52677f; }}
.empty-chip {{ background: #f2f5f8; color: #96a4b5; }}
.distribution-cards {{ margin-top: 3px; }}
.chart-grid {{ border-collapse: collapse; margin: 0; table-layout: fixed; width: 100%; }}
.chart-grid tr {{ page-break-inside: avoid; break-inside: avoid-page; }}
.chart-grid:last-child {{ margin-bottom: 0; }}
.chart-cell {{ break-inside: avoid-page; page-break-inside: avoid; padding: 0; vertical-align: top; }}
.chart-spacer, .chart-placeholder {{ background: transparent; border: 0; }}
.distribution-card-shell {{ border-collapse: collapse; page-break-inside: avoid; break-inside: avoid-page; table-layout: fixed; width: 100%; }}
.distribution-card-shell td {{ page-break-inside: avoid; break-inside: avoid-page; }}
.distribution-card-cell {{ background: #ffffff; border: 1px solid #e5eaf1; padding: 0; }}
.distribution-card {{ background: #ffffff; border: 1px solid #e5eaf1; border-radius: 16px; box-shadow: 0 6px 18px rgba(22, 42, 70, .05); min-height: 330px; overflow: hidden; padding: 20px 20px 0; page-break-inside: avoid; break-inside: avoid-page; }}
.distribution-card h3 {{ color: #182e4d; font-size: 11pt; font-weight: 650; letter-spacing: -.1px; margin: 0 0 12px; }}
.distribution-chart {{ height: 180px; margin: 0 auto 14px; width: 180px; }}
.distribution-chart-fallback {{ display: block; height: 180px; width: 180px; }}
.distribution-legend {{ border-collapse: separate; border-spacing: 0 8px; font-size: 8pt; margin: 8px 0 18px; table-layout: fixed; }}
.distribution-legend td {{ border: 0; padding: 3px 0; vertical-align: middle; word-break: normal; overflow-wrap: normal; }}
.legend-swatch {{ padding-right: 12px !important; width: 28px; }}
.legend-label {{ color: #2f4763; font-weight: 500; letter-spacing: .05px; padding-right: 16px !important; width: 48%; }}
.legend-amount {{ color: #2a415d; font-weight: 600; text-align: left; white-space: nowrap; width: 52%; }}
.marker {{ border-radius: 3px; display: inline-block; height: 12px; width: 12px; }}
.distribution-total {{ border-top: 1px solid #e8edf4; color: #283f5d; font-size: 8.2pt; font-weight: 650; margin: 7px -20px 0; padding: 12px 20px 14px; }}
.chart-fallback {{ align-items: center; color: #6a7f98; display: flex; font-size: 8pt; height: 180px; justify-content: center; line-height: 1.35; text-align: center; width: 180px; }}
.distribution-empty {{ background: #ffffff; border: 1px solid #e5eaf1; border-radius: 16px; color: #71849b; padding: 24px; }}
.comparison-section {{ margin-top: 14px; }}
.comparison-note {{ color: #5f738e; margin: 0 0 16px 8px; }}
.comparison-block {{ margin: 0 0 18px; }}
.comparison-block:last-child {{ margin-bottom: 0; }}
.comparison-block-title {{ color: #213856; font-size: 10.5pt; font-weight: 650; margin: 0 0 10px 8px; }}
.comparison-grid {{ table-layout: fixed; width: 100%; }}
.comparison-grid td {{ border: 0; padding: 0; vertical-align: top; }}
.comparison-chart-cell {{ vertical-align: top; }}
.comparison-gap {{ background: transparent; }}
.no-data {{ color: #7b8ca2; font-style: italic; padding: 13px; }}
</style>
</head>
<body>
<div class="report">
 <div class="report-header">
  <h1>{escape(test["name"])}</h1>
  <p class="subtitle">{escape(data["subject"])}<span class="dot">&middot;</span>{escape(audience or "-")}<span class="dot">&middot;</span>{escape(_text(test["period"]))}</p>
 </div>
 <div class="section">
  <div class="section-title">1. Algemene gegevens over de toets</div>
  <table class="info-grid">{info_grid}</table>
 </div>
 <p class="pdf-break">[[PAGE_BREAK]]</p>
 <div class="matrix-section">
  <div class="section section-heading"><div class="section-title">2. Toetsmatrijs</div></div>
  <div class="table-wrap">
   <table class="matrix-table"><thead><tr>{table_head}</tr></thead><tbody>{''.join(table_rows)}</tbody></table>
  </div>
 </div>
 <p class="pdf-break">[[PAGE_BREAK]]</p>
 <div class="section section-heading"><div class="section-title">3. Verdeling op basis van onderdelen</div></div>
  {_render_distributions(data)}
  {comparison}
</div>
</body>
</html>"""
