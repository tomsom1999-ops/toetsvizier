from __future__ import annotations

import html


def _escape(value: object) -> str:
    return html.escape(str(value or ""))


def _number(value: float | int | None, decimals: int = 1) -> str:
    if value is None:
        return "-"
    return f"{float(value):.{decimals}f}".replace(".", ",")


def _percentage(value: float | int | None) -> str:
    return "-" if value is None else f"{round(float(value))}%"


def _known_taxonomy_explanation(title: str) -> str | None:
    taxonomy = title.split(":", 1)[-1].strip().casefold()
    if taxonomy == "rtti":
        return (
            "RTTI beschrijft het type denkwerk: R = reproductie, T1 = toepassen in een "
            "bekende situatie, T2 = toepassen in een nieuwe situatie en I = inzicht."
        )
    if taxonomy == "obit":
        return (
            "OBIT beschrijft het leerproces: onthouden, begrijpen, integreren en toepassen. "
            "Samen laten deze onderdelen zien op welk denkniveau de leerling punten behaalt."
        )
    if taxonomy == "bloom":
        return (
            "Bloom ordent denkvaardigheden van onthouden en begrijpen via toepassen en "
            "analyseren tot evalueren en creeren."
        )
    return None


def report_dimensions(data: dict[str, object]) -> list[dict[str, object]]:
    group_by_key = {
        str(dimension["key"]): dimension
        for dimension in data.get("group_dimensions", [])
    }
    shown_by_title: dict[str, dict[str, object]] = {}
    for dimension in data.get("student_dimensions", []):
        key = str(dimension["key"])
        source = group_by_key.get(key, dimension)
        raw_title = str(dimension.get("title", "Classificatie")).strip()
        source_entries = list(source.get("entries", []))
        display_title = f"Taxonomie: {raw_title}" if dimension.get("kind") == "taxonomy" else raw_title
        entries = [
            {"source": str(entry["name"]), "label": str(entry["name"])}
            for entry in source_entries
        ]
        if raw_title.casefold() == "taxonomie" and entries:
            split_values = [
                entry["source"].split(":", 1) if ":" in str(entry["source"]) else []
                for entry in entries
            ]
            if all(len(value) == 2 for value in split_values):
                prefix = split_values[0][0].strip()
                if all(value[0].strip().casefold() == prefix.casefold() for value in split_values):
                    display_title = f"Taxonomie: {prefix}"
                    entries = [
                        {"source": entry["source"], "label": value[1].strip()}
                        for entry, value in zip(entries, split_values)
                    ]
        presented = {
            "key": key,
            "title": display_title,
            "kind": dimension.get("kind", "property"),
            "entries": entries,
        }
        shown_by_title[display_title.casefold()] = presented
    return list(shown_by_title.values())


def default_report_options(data: dict[str, object]) -> dict[str, object]:
    dimensions = report_dimensions(data)
    return {
        "profile_keys": [str(dimension["key"]) for dimension in dimensions],
        "include_question_analysis": True,
        "include_strengths": True,
        "include_heatmap": True,
        "heatmap_key": str(dimensions[0]["key"]) if dimensions else "overall",
        "include_second_heatmap": False,
        "second_heatmap_key": "overall",
        "include_feedback": False,
        "feedback_text": "",
        "report_theme": "student",
    }


def _profile_rows(student: dict[str, object], dimension: dict[str, object]) -> list[dict[str, object]]:
    source_rows = {
        str(entry["name"]): entry
        for entry in student.get("profiles", {}).get(str(dimension["key"]), [])
    }
    return [
        {
            "label": entry["label"],
            "percentage": source_rows.get(str(entry["source"]), {}).get("percentage"),
            "group_percentage": source_rows.get(str(entry["source"]), {}).get("group_percentage"),
            "percentile": source_rows.get(str(entry["source"]), {}).get("percentile"),
        }
        for entry in dimension["entries"]
    ]


def _profile_chart_svg(rows: list[dict[str, object]]) -> str:
    width = 940
    left = 155
    bar_width = 500
    row_height = 48
    height = max(95, 42 + len(rows) * row_height)
    parts = [
        f'<svg class="profile-svg" viewBox="0 0 {width} {height}" aria-hidden="true">',
        '<g font-family="Inter, Segoe UI, Arial" font-size="11" fill="#66748e">',
    ]
    for mark in range(0, 101, 20):
        x = left + bar_width * mark / 100
        parts.append(f'<line x1="{x:.1f}" y1="22" x2="{x:.1f}" y2="{height - 24}" stroke="#edf1f7"/>')
        parts.append(f'<text x="{x:.1f}" y="{height - 6}" text-anchor="middle">{mark}%</text>')
    for index, row in enumerate(rows):
        y = 31 + index * row_height
        pupil = float(row["percentage"] or 0)
        group = float(row["group_percentage"] or 0)
        parts.append(f'<text x="0" y="{y + 10}" fill="#34435e">{_escape(row["label"])}</text>')
        parts.append(
            f'<rect x="{left}" y="{y}" width="{bar_width * group / 100:.1f}" height="12" rx="6" fill="#d5dcea"/>'
        )
        parts.append(
            f'<rect x="{left}" y="{y + 16}" width="{bar_width * pupil / 100:.1f}" height="15" rx="7" fill="#6256ea"/>'
        )
        score_label = _percentage(pupil)
        if row["percentile"] is not None:
            score_label += f" | beter dan {round(float(row['percentile']))}% van de leerlingen"
        parts.append(
            f'<text x="{left + bar_width * pupil / 100 + 7:.1f}" y="{y + 28}" fill="#17243c">'
            f'{_escape(score_label)}</text>'
        )
    parts.append("</g></svg>")
    return "".join(parts)


def _metric_value(student: dict[str, object], key: str, source: str | None = None) -> float | None:
    if key == "overall":
        return float(student.get("score_percentage", 0))
    for entry in student.get("profiles", {}).get(key, []):
        if str(entry.get("name")) == source:
            return float(entry.get("percentage", 0))
    return None


def _heat_color(value: float | None) -> str:
    if value is None:
        return "#f5f7fa"
    if value >= 75:
        return "#2f9950"
    if value >= 50:
        return "#70b877"
    if value >= 25:
        return "#b5d9b9"
    return "#e7f2e8"


def _heatmap_html(
    data: dict[str, object],
    student: dict[str, object],
    dimension_key: str,
    dimensions: list[dict[str, object]],
) -> str:
    selected_dimension = next(
        (dimension for dimension in dimensions if dimension["key"] == dimension_key),
        None,
    )
    if selected_dimension:
        title = str(selected_dimension["title"])
        columns = [
            (str(entry["label"]), str(entry["source"]))
            for entry in selected_dimension["entries"]
        ]
    else:
        title = "Algemene score"
        columns = [("Totale score", None)]
        dimension_key = "overall"
    participants = list(data.get("participants", []))
    ranked_columns: list[list[dict[str, object]]] = []
    for _, source in columns:
        ranked_columns.append(
            sorted(
                participants,
                key=lambda participant: (
                    -float(_metric_value(participant, dimension_key, source) or -1),
                    str(participant.get("name", "")).casefold(),
                ),
            )
        )
    headers = "".join(f"<th>{_escape(label)}</th>" for label, _ in columns)
    rows: list[str] = []
    for position in range(len(participants)):
        cells = []
        for column_index, (_, source) in enumerate(columns):
            participant = ranked_columns[column_index][position]
            value = _metric_value(participant, dimension_key, source)
            is_selected = int(participant.get("student_id", -1)) == int(student.get("student_id", -2))
            text = str(participant["name"]) if is_selected else str(position + 1)
            css_class = " own" if is_selected else ""
            cells.append(
                f'<td class="heat-cell{css_class}" style="background:{_heat_color(value)}">'
                f'<span>{_escape(text)}</span></td>'
            )
        rows.append(f'<tr><th class="position">{position + 1}</th>{"".join(cells)}</tr>')
    return (
        f'<section class="report-section heat-section scalable-card"><h2>Geanonimiseerde positiekaart - {_escape(title)}</h2>'
        "<p class=\"guide\">Elke kolom is apart gerangschikt. Een lager positienummer betekent dat "
        "een groter percentage van de beschikbare punten is behaald. Alleen de eigen naam is zichtbaar.</p>"
        '<div class="heatmap-fit"><table class="heatmap"><thead><tr><th class="position">Positie</th>'
        f"{headers}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        '<div class="heat-legend"><span>Lagere score</span><i></i><i></i><i></i><i></i><span>Hogere score</span></div></div>'
        "</section>"
    )


def _question_analysis_html(student: dict[str, object]) -> str:
    rows = []
    for entry in student.get("items", []):
        score = float(entry.get("score", 0))
        maximum = float(entry.get("maximum_score", 0))
        level = "good" if maximum > 0 and score >= maximum else "attention" if score > 0 else "bad"
        result = "Goed" if level == "good" else "Deels goed" if level == "attention" else "Fout"
        rows.append(
            "<tr>"
            f"<td>{_escape(entry.get('label', '-'))}</td>"
            f"<td>{_escape(entry.get('component', '-'))}</td>"
            f"<td>{_number(score)} / {_number(maximum)}</td>"
            f'<td><span class="badge {level}">{result}</span></td>'
            "</tr>"
        )
    return (
        '<section class="report-section table-section scalable-card"><h2>Vraaganalyse</h2>'
        '<p class="guide">Per vraag staat hoeveel punten zijn behaald. Zo is zichtbaar waar het antwoord volledig, deels of niet juist was.</p>'
        '<table class="questions"><thead><tr><th>Vraag</th><th>Onderdeel</th><th>Score</th><th>Resultaat</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></section>"
    )


def _strengths_html(student: dict[str, object], dimensions: list[dict[str, object]]) -> str:
    profile_rows: list[dict[str, object]] = []
    for dimension in dimensions:
        for row in _profile_rows(student, dimension):
            row = dict(row)
            row["dimension"] = dimension["title"]
            profile_rows.append(row)
    strengths = sorted(
        (
            row for row in profile_rows
            if row["percentage"] is not None
            and row["group_percentage"] is not None
            and float(row["percentage"]) >= float(row["group_percentage"])
            and float(row["percentage"]) >= 60
        ),
        key=lambda row: -float(row["percentage"]),
    )[:3]
    concerns = sorted(
        (
            row for row in profile_rows
            if row["percentage"] is not None
            and row["group_percentage"] is not None
            and (float(row["percentage"]) < float(row["group_percentage"]) or float(row["percentage"]) < 50)
        ),
        key=lambda row: float(row["percentage"]),
    )[:3]
    strong_items = "".join(
        f'<li><strong>{_escape(row["dimension"])}</strong>: {_escape(row["label"])} ({_percentage(row["percentage"])})</li>'
        for row in strengths
    ) or "<li>Geen uitgesproken sterk onderdeel op basis van deze toets.</li>"
    concern_items = "".join(
        f'<li><strong>{_escape(row["dimension"])}</strong>: {_escape(row["label"])} ({_percentage(row["percentage"])})</li>'
        for row in concerns
    ) or "<li>Geen uitgesproken aandachtspunt op basis van deze toets.</li>"
    return (
        '<section class="report-section insights scalable-card"><h2>Sterke punten en aandachtspunten</h2>'
        '<p class="guide">Deze samenvatting vergelijkt de behaalde punten met het groepsgemiddelde binnen dezelfde onderdelen.</p>'
        '<div class="insight-grid"><div class="positive"><h3>Sterke punten</h3><ul>'
        f"{strong_items}</ul></div><div class=\"warning\"><h3>Aandachtspunten</h3><ul>{concern_items}</ul></div></div></section>"
    )


def build_student_report_html(
    data: dict[str, object],
    student: dict[str, object],
    options: dict[str, object] | None = None,
) -> str:
    settings = default_report_options(data)
    if options:
        settings.update(options)
    theme_key = str(settings.get("report_theme", "student"))
    themes = {
        "student": {
            "class": "theme-student",
            "title": "Leerlingrapport",
            "badge": "Leerlingvriendelijk rapport",
            "intro": "Dit rapport laat zien welke resultaten op deze toets zijn behaald en op welke onderdelen verdere groei mogelijk is.",
            "note": "",
        },
        "teacher": {
            "class": "theme-teacher",
            "title": "Intern docentrapport",
            "badge": "Intern docentrapport",
            "intro": "Dit interne rapport bundelt leerlingresultaat, onderdeelprofielen en gerichte aandachtspunten voor begeleiding en bespreking.",
            "note": "Interne variant: bedoeld voor docent, mentor of vaksectie. Deel deze versie niet zonder context met leerlingen.",
        },
        "section": {
            "class": "theme-section",
            "title": "Sectierapport",
            "badge": "Sectierapport",
            "intro": "Deze rapportage is opgesteld als compacte bijlage voor sectieanalyse en kwaliteitszorg.",
            "note": "Sectievariant: formuleert neutraler en legt nadruk op onderdelen, positie en interpretatie.",
        },
    }
    theme = themes.get(theme_key, themes["student"])
    dimensions = report_dimensions(data)
    chosen_keys = set(settings["profile_keys"])
    chosen_dimensions = [dimension for dimension in dimensions if dimension["key"] in chosen_keys]
    test = data.get("test", {})
    maximum = float(data.get("maximum_score", 0))
    context = " | ".join(
        _escape(value)
        for value in (test.get("school_year"), test.get("level"), test.get("grade_year"), test.get("period"))
        if value
    )
    status = "Voldoende" if student.get("sufficient") else "Onvoldoende"
    show_grades = bool(data.get("normalization_finalized"))
    feedback_section = ""
    feedback_text = str(settings.get("feedback_text", "")).strip()
    if settings.get("include_feedback") and feedback_text:
        feedback_section = (
            '<section class="report-section feedback scalable-card"><h2>Feedback van de docent</h2>'
            '<p class="guide">Persoonlijke feedback bij deze toets.</p>'
            f'<div class="feedback-text">{_escape(feedback_text).replace(chr(10), "<br>")}</div>'
            "</section>"
        )
    theme_note = (
        f'<section class="report-section theme-note scalable-card"><strong>{_escape(theme["badge"])}</strong><br>{_escape(theme["note"])}</section>'
        if theme["note"]
        else ""
    )
    profile_sections: list[str] = []
    for dimension in chosen_dimensions:
        rows = _profile_rows(student, dimension)
        taxonomy_text = _known_taxonomy_explanation(str(dimension["title"]))
        explanation = taxonomy_text or (
            "Deze grafiek toont per onderdeel welk percentage van de beschikbare punten is behaald."
        )
        profile_sections.append(
            f'<section class="report-section profile scalable-card"><h2>{_escape(dimension["title"])}</h2>'
            f'<p class="guide">{_escape(explanation)} De paarse balk toont de leerling; de grijze balk het groepsgemiddelde.</p>'
            f'{_profile_chart_svg(rows)}'
            '<div class="legend"><span class="pupil"></span> Leerling <span class="group"></span> Groepsgemiddelde</div></section>'
        )
    additional_sections = "".join(profile_sections)
    if settings.get("include_strengths"):
        additional_sections += _strengths_html(student, chosen_dimensions or dimensions)
    if settings.get("include_question_analysis"):
        additional_sections += _question_analysis_html(student)
    if settings.get("include_heatmap"):
        additional_sections += _heatmap_html(data, student, str(settings.get("heatmap_key", "overall")), dimensions)
    if settings.get("include_second_heatmap"):
        additional_sections += _heatmap_html(
            data,
            student,
            str(settings.get("second_heatmap_key", "overall")),
            dimensions,
        )
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<style>
@page {{ size:A4 portrait; margin:14mm; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:#17243c; background:#f6f8fb; font:11px "Inter","Segoe UI",Arial,sans-serif; }}
body.theme-teacher {{ background:#f4f7fb; }}
body.theme-section {{ background:#f7f8fb; }}
.page {{ padding:22px; }}
.hero {{ background:#fff; border:1px solid #e5eaf1; border-radius:16px; padding:22px; margin-bottom:14px; }}
body.theme-teacher .hero {{ border-top:4px solid #1a3c63; }}
body.theme-section .hero {{ border-top:4px solid #3fcfcf; }}
h1 {{ margin:0 0 6px; font-size:23px; line-height:1.2; }}
.subtitle {{ color:#66748e; }}
.theme-badge {{ display:inline-block; margin-top:10px; padding:5px 10px; border-radius:999px; background:#f0edff; color:#6256ea; font-weight:650; }}
body.theme-teacher .theme-badge {{ background:#eaf1f8; color:#1a3c63; }}
body.theme-section .theme-badge {{ background:#e9fbfb; color:#177f88; }}
.student-name {{ font-size:15px; font-weight:650; margin-top:14px; }}
.report-section {{ background:#fff; border:1px solid #e5eaf1; border-radius:14px; padding:17px; margin-bottom:12px; break-inside:avoid-page !important; page-break-inside:avoid !important; transform-origin:top left; }}
.theme-note {{ border-color:#d8e3f3; background:#fbfdff; color:#53637e; line-height:1.55; }}
.heat-section {{ break-before:page; page-break-before:always; }}
h2 {{ font-size:15px; margin:0 0 8px; }}
h3 {{ font-size:12px; margin:0 0 8px; }}
.guide {{ margin:0 0 14px; color:#5e6e88; line-height:1.5; }}
.kpis {{ display:grid; grid-template-columns:repeat(4,1fr); gap:8px; }}
.kpi {{ background:#fff; border:1px solid #e5eaf1; border-radius:12px; padding:12px; }}
.label {{ color:#66748e; font-size:10px; margin-bottom:5px; }}
.value {{ font-size:18px; font-weight:650; }}
.good-text {{ color:#21924b; }} .bad-text {{ color:#dd4141; }}
.profile-svg {{ width:100%; height:auto; display:block; }}
.legend {{ display:flex; align-items:center; justify-content:center; gap:8px; color:#66748e; margin-top:5px; }}
.legend span {{ width:13px; height:8px; border-radius:4px; display:inline-block; }}
.legend .pupil {{ background:#6256ea; }} .legend .group {{ background:#d5dcea; margin-left:14px; }}
.insight-grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
.insight-grid > div {{ border-radius:10px; padding:12px; }}
.positive {{ background:#f0faf3; border:1px solid #dceee2; }}
.warning {{ background:#fff7ee; border:1px solid #f5e2c7; }}
.feedback {{ border-color:#dfe3fb; background:#fff; }}
.feedback-text {{ background:#f8f8ff; border:1px solid #e3e4fb; border-radius:10px; padding:14px; color:#253553; font-size:12px; line-height:1.65; white-space:normal; }}
ul {{ margin:0; padding-left:18px; line-height:1.75; }}
table {{ width:100%; border-collapse:collapse; }}
thead {{ display:table-header-group; }}
th {{ text-align:left; color:#66748e; background:#fafbfe; font-weight:600; }}
td, th {{ padding:8px 10px; border-bottom:1px solid #edf1f7; }}
.badge {{ display:inline-block; padding:3px 10px; border-radius:8px; font-weight:600; }}
.badge.good {{ color:#20914a; background:#e9f7ee; }}
.badge.attention {{ color:#d77e00; background:#fff2e2; }}
.badge.bad {{ color:#e03939; background:#fdecec; }}
.heatmap {{ table-layout:fixed; }}
.heatmap .position {{ width:58px; text-align:center; }}
.heat-cell {{ height:27px; text-align:center; color:#17243c; font-weight:600; padding:3px; }}
.heat-cell.own {{ border:3px solid #f04491; color:#17243c; }}
.heat-cell span {{ display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.heat-legend {{ display:flex; align-items:center; justify-content:flex-end; gap:5px; color:#66748e; margin-top:9px; }}
.heat-legend i {{ width:22px; height:9px; border-radius:3px; background:#e7f2e8; }}
.heat-legend i:nth-of-type(2) {{ background:#b5d9b9; }}
.heat-legend i:nth-of-type(3) {{ background:#70b877; }}
.heat-legend i:nth-of-type(4) {{ background:#2f9950; }}
</style>
</head>
<body class="{_escape(theme["class"])}"><div class="page">
<header class="hero">
  <h1>{_escape(theme["title"])} - {_escape(test.get("name", "Toets"))}</h1>
  <div class="subtitle">{context}</div>
  <div class="theme-badge">{_escape(theme["badge"])}</div>
  <div class="student-name">{_escape(student.get("name", "Leerling"))}</div>
</header>
{theme_note}
<section class="report-section">
  <h2>Algemene gegevens</h2>
  <p class="guide">{_escape(theme["intro"])}</p>
  <div class="kpis">
    <div class="kpi"><div class="label">Score</div><div class="value">{_number(student.get("total_score"))} / {_number(maximum)}</div></div>
    <div class="kpi"><div class="label">% van de punten gescoord</div><div class="value">{_percentage(student.get("score_percentage"))}</div></div>
    {f'<div class="kpi"><div class="label">Cijfer</div><div class="value">{_number(student.get("grade"))}</div></div>' if show_grades else '<div class="kpi"><div class="label">Normering</div><div class="value">Nog niet vastgesteld</div></div>'}
    {f'<div class="kpi"><div class="label">Resultaat</div><div class="value {"good-text" if status == "Voldoende" else "bad-text"}">{status}</div></div>' if show_grades else '<div class="kpi"><div class="label">Resultaat</div><div class="value">Nog niet beschikbaar</div></div>'}
  </div>
</section>
{feedback_section}
{additional_sections}
</div><script>
function fitReportCards() {{
  const usableHeight = (297 - 28) * (96 / 25.4) - 28;
  document.querySelectorAll(".report-section, .hero").forEach(card => {{
    card.style.zoom = "1";
    const height = card.getBoundingClientRect().height;
    if (height > usableHeight) {{
      card.style.zoom = String((usableHeight / height) * 0.97);
    }}
  }});
}}
window.addEventListener("load", () => {{
  fitReportCards();
  window.__chartsReady = true;
}});
</script></body></html>"""
