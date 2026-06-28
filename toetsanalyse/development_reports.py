from __future__ import annotations

import html


def _escape(value: object) -> str:
    return html.escape(str(value or ""))


def _number(value: object, decimals: int = 1) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{decimals}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "-"


def _percentage(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{round(float(value))}%"
    except (TypeError, ValueError):
        return "-"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number:
            return default
        return number
    except (TypeError, ValueError):
        return default


def _clamp(value: object, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, _safe_float(value)))


def _signed_percentage(value: object) -> str:
    if value is None:
        return "-"
    number = _safe_float(value)
    return f"{'+' if number >= 0 else ''}{round(number)}%"


def _short_label(value: object, max_length: int = 24) -> str:
    text = str(value or "")
    if len(text) <= max_length:
        return text
    return text[: max(0, max_length - 1)].rstrip() + "…"


def _wrap_label(value: object, max_chars: int = 18, max_lines: int = 2) -> list[str]:
    words = str(value or "").replace("/", "/ ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
        else:
            current = candidate
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if not lines:
        lines = [str(value or "")]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    joined = " ".join(words)
    visible = " ".join(lines)
    if len(joined) > len(visible):
        lines[-1] = _short_label(lines[-1], max(4, max_chars))
    return [_short_label(line, max_chars) for line in lines]


def _svg_multiline_text(
    value: object,
    x: float,
    y: float,
    *,
    max_chars: int = 18,
    max_lines: int = 2,
    font_size: int = 11,
    color: str = "#40516a",
) -> str:
    lines = _wrap_label(value, max_chars=max_chars, max_lines=max_lines)
    tspans = []
    for index, line in enumerate(lines):
        dy = 0 if index == 0 else font_size + 3
        tspans.append(
            f'<tspan x="{x:.1f}" dy="{dy}">{_escape(line)}</tspan>'
        )
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" '
        f'fill="{color}" font-size="{font_size}">' + "".join(tspans) + "</text>"
    )


def _option(options: dict[str, object] | None, key: str, default: bool = True) -> bool:
    if options is None:
        return default
    return bool(options.get(key, default))


def _report_shell(title: str, subtitle: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <style>
    @page {{ size: A4 landscape; margin: 10mm; }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: #f6f8fb;
      color: #071f42;
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      font-size: 12px;
      -webkit-print-color-adjust: exact;
      print-color-adjust: exact;
    }}
    .page {{ max-width: 1320px; margin: 0 auto; padding: 12px; }}
    .hero {{
      display: flex; justify-content: space-between; gap: 18px; align-items: flex-start;
      margin-bottom: 14px; break-inside: avoid;
    }}
    h1 {{ margin: 0; font-size: 28px; letter-spacing: -.02em; }}
    h2 {{ margin: 0 0 10px; font-size: 17px; }}
    h3 {{ margin: 12px 0 8px; font-size: 14px; }}
    .subtitle {{ color: #62708a; margin-top: 5px; line-height: 1.45; }}
    .stamp {{ color: #62708a; font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 12px; }}
    .card {{
      background: #fff; border: 1px solid #e3eaf3; border-radius: 16px;
      box-shadow: 0 12px 30px rgba(15,35,70,.08); padding: 14px;
      break-inside: avoid; page-break-inside: avoid;
    }}
    .kpi-label {{ color: #62708a; font-size: 11px; font-weight: 700; }}
    .kpi-value {{ font-size: 23px; font-weight: 800; margin-top: 5px; }}
    .section {{ margin-bottom: 12px; }}
    .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th {{ background: #edf3ff; color: #233755; text-align: left; padding: 8px; }}
    td {{ border-top: 1px solid #e3eaf3; padding: 7px 8px; vertical-align: top; }}
    tr:nth-child(even) td {{ background: #fafcff; }}
    .bar-row {{ display: grid; grid-template-columns: 185px 1fr 64px; gap: 10px; align-items: center; margin: 8px 0; }}
    .bar-label {{ color: #34435e; font-weight: 650; overflow-wrap: anywhere; }}
    .bar-track {{ height: 15px; border-radius: 999px; background: #edf2f8; overflow: hidden; position: relative; }}
    .bar-fill {{ height: 100%; border-radius: 999px; background: #2fa866; }}
    .bar-fill.warn {{ background: #e99b22; }}
    .bar-fill.bad {{ background: #e24a4a; }}
    .compare-track {{ height: 22px; border-radius: 999px; background: #edf2f8; position: relative; overflow: hidden; }}
    .compare-group {{ position:absolute; top:3px; height:6px; border-radius:999px; background:#b8c4d6; }}
    .compare-student {{ position:absolute; bottom:3px; height:9px; border-radius:999px; background:#5b5ff1; }}
    .svg-chart {{
      width: 100%; height: auto; display: block; border: 1px solid #edf2f8;
      border-radius: 14px; background: #fff; margin-top: 8px;
    }}
    .legend {{
      display: flex; flex-wrap: wrap; gap: 12px; align-items: center;
      justify-content: center; color: #40516a; font-size: 11px;
      margin: 8px auto 8px; padding: 7px 11px; width: fit-content; max-width: 100%;
      background: #fbfdff; border: 1px solid #e3eaf3; border-radius: 999px;
    }}
    .legend span {{ display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }}
    .dot {{ width: 9px; height: 9px; border-radius: 999px; display: inline-block; }}
    .trend-card-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 10px 0 12px; }}
    .trend-card {{
      border: 1px solid #e3eaf3; border-radius: 14px; padding: 11px 12px; background: #fbfdff;
    }}
    .trend-card.good {{ background:#f2fbf5; border-color:#cfeedd; }}
    .trend-card.warn {{ background:#fff8ec; border-color:#f3dfb7; }}
    .trend-card.bad {{ background:#fff1f1; border-color:#f2cdcd; }}
    .trend-card .label {{ color: #62708a; font-size: 10px; font-weight: 850; text-transform: uppercase; }}
    .trend-card .value {{ font-size: 20px; font-weight: 850; margin-top: 4px; }}
    .signal-board {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }}
    .signal-column h3 {{ margin-top: 0; color:#233755; }}
    .signal-card {{
      border: 1px solid #e3eaf3; border-radius: 14px; padding: 10px 11px;
      background: #fbfdff; margin-bottom: 8px;
    }}
    .signal-card.good {{ background:#f2fbf5; border-color:#cfeedd; }}
    .signal-card.warn {{ background:#fff8ec; border-color:#f3dfb7; }}
    .signal-card.bad {{ background:#fff1f1; border-color:#f2cdcd; }}
    .signal-card .tag {{ color:#62708a; font-size:10px; font-weight:850; text-transform:uppercase; }}
    .signal-card .subject {{ font-size:15px; font-weight:850; margin-top:4px; }}
    .signal-card .detail {{ color:#40516a; line-height:1.35; margin-top:3px; }}
    .guide {{ color: #62708a; line-height: 1.45; margin: 0 0 10px; }}
    .pill {{
      display: inline-block; border-radius: 999px; padding: 4px 8px; font-weight: 800;
      background: #eef3ff; color: #40516a;
    }}
    .pill.good {{ background:#e8f7ed; color:#177344; }}
    .pill.bad {{ background:#fdecec; color:#b42b2b; }}
    .dim-section {{ break-inside: avoid; page-break-inside: avoid; }}
    .fit-page-card {{ break-inside: avoid-page; page-break-inside: avoid; overflow: hidden; }}
    @media print {{
      .page {{ padding: 0; max-width: none; }}
      .hero {{ margin-bottom: 8px; }}
      h1 {{ font-size: 24px; }}
      h2 {{ font-size: 15px; margin-bottom: 7px; }}
      h3 {{ font-size: 12px; margin: 8px 0 6px; }}
      .card {{ box-shadow: none; padding: 10px; border-radius: 13px; }}
      .section {{ margin-bottom: 8px; }}
      .guide {{ line-height: 1.28; margin-bottom: 6px; }}
      .trend-card-grid {{ gap: 7px; margin: 6px 0 8px; }}
      .trend-card {{ padding: 8px 9px; }}
      .trend-card .value {{ font-size: 17px; margin-top: 2px; }}
      .signal-board {{ gap: 7px; }}
      .signal-card {{ padding: 7px 8px; margin-bottom: 5px; }}
      .signal-card .subject {{ font-size: 13px; margin-top: 2px; }}
      .bar-row {{ grid-template-columns: 158px 1fr 54px; gap: 7px; margin: 4px 0; }}
      .bar-track {{ height: 12px; }}
      .compare-track {{ height: 17px; }}
      .svg-chart {{ max-height: 255px; margin-top: 5px; }}
      .fit-page-card {{ zoom: .88; }}
      .dim-section.fit-page-card {{ zoom: .74; }}
      .dim-section.fit-page-card .svg-chart {{ max-height: 238px; }}
    }}
  </style>
</head>
<body>
  <main class="page">
    <div class="hero">
      <div>
        <h1>{_escape(title)}</h1>
        <div class="subtitle">{_escape(subtitle)}</div>
      </div>
      <div class="stamp">ToetsVizier · Ontwikkelanalyse</div>
    </div>
    {body}
  </main>
  <script>window.__chartsReady = true;</script>
</body>
</html>"""


def _bar_rows(entries: list[dict[str, object]], label_key: str = "name", value_key: str = "percentage") -> str:
    rows = []
    for entry in entries:
        value = max(0.0, min(100.0, float(entry.get(value_key) or 0.0)))
        cls = "bad" if value < 55 else "warn" if value < 70 else ""
        rows.append(
            '<div class="bar-row">'
            f'<div class="bar-label">{_escape(entry.get(label_key, "-"))}</div>'
            f'<div class="bar-track"><div class="bar-fill {cls}" style="width:{value:.1f}%"></div></div>'
            f'<div><b>{_percentage(value)}</b></div>'
            '</div>'
        )
    return "".join(rows)


def _overview_cards(cards: list[dict[str, object]]) -> str:
    if not cards:
        return ""
    return (
        '<section class="grid">'
        + "".join(
            '<article class="card">'
            f'<div class="kpi-label">{_escape(card.get("title"))}</div>'
            f'<div class="kpi-value" style="font-size:18px">{_escape(card.get("value"))}</div>'
            f'<div class="guide">{_escape(card.get("detail"))}</div>'
            '</article>'
            for card in cards[:8]
        )
        + '</section>'
    )


def _signal_rows(signals: list[dict[str, object]]) -> str:
    if not signals:
        return '<tr><td colspan="3">Geen signalen beschikbaar.</td></tr>'
    return "".join(
        "<tr>"
        f"<td><span class=\"pill {'good' if signal.get('tone') == 'green' else 'bad' if signal.get('tone') == 'red' else ''}\">{_escape(signal.get('title'))}</span></td>"
        f"<td>{_escape(signal.get('subject'))}</td>"
        f"<td>{_escape(signal.get('detail'))}</td>"
        "</tr>"
        for signal in signals
    )


def _status_label(status: object) -> str:
    labels = {
        "niet analyseren": "Niet analyseren",
        "niet gemaakt": "Niet gemaakt",
        "absent": "Absent",
        "ziek": "Ziek",
        "geoorloofd afwezig": "Geoorloofd afwezig",
        "ongeoorloofd afwezig": "Ongeoorloofd afwezig",
        "vrijstelling": "Vrijstelling",
        "ongeldig": "Ongeldig",
        "onregelmatigheid": "Onregelmatigheid",
    }
    return labels.get(str(status or "").lower(), str(status or "-"))


def _attendance_rows(rows: list[dict[str, object]]) -> str:
    if not rows:
        return '<tr><td colspan="4">Geen leerlingen gevonden die in deze selectie vaak afwezig waren of de toets niet hebben gemaakt.</td></tr>'
    html_rows = []
    for row in rows[:60]:
        tests = []
        for test in list(row.get("tests", []))[:4]:
            tests.append(f"{_escape(test.get('name'))} ({_escape(_status_label(test.get('status')))})")
        if len(row.get("tests", [])) > 4:
            tests.append(f"+{len(row.get('tests', [])) - 4} meer")
        html_rows.append(
            "<tr>"
            f"<td>{_escape(row.get('student_name'))}</td>"
            f"<td><span class=\"pill\">{_escape(row.get('count'))} van {_escape(row.get('total_tests'))}</span></td>"
            f"<td>{_escape(_status_label(row.get('most_common_status')))}</td>"
            f"<td>{'<br>'.join(tests)}</td>"
            "</tr>"
        )
    return "".join(html_rows)


def _test_rows(tests: list[dict[str, object]]) -> str:
    return "".join(
        "<tr>"
        f"<td>{_escape(test.get('name'))}<br><span class=\"guide\">{_escape(test.get('school_year'))} · {_escape(test.get('period'))}</span></td>"
        f"<td>{_percentage(test.get('mean_score_percentage', test.get('score_percentage')))}</td>"
        f"<td>{_number(test.get('mean_grade', test.get('grade')))}</td>"
        f"<td>{_escape(test.get('participant_count', ''))}</td>"
        "</tr>"
        for test in tests
    )


def _resit_rows(rows: list[dict[str, object]]) -> str:
    if not rows:
        return '<tr><td colspan="5">Geen gekoppelde herkansingen gevonden.</td></tr>'
    html_rows = []
    for row in rows[:120]:
        delta = float(row.get("delta_percentage") or 0)
        html_rows.append(
            "<tr>"
            f"<td>{_escape(row.get('student_name'))}</td>"
            f"<td>{_percentage(row.get('original_percentage'))}<br><span class=\"guide\">{_escape(row.get('original_test'))}</span></td>"
            f"<td>{_percentage(row.get('resit_percentage'))}<br><span class=\"guide\">{_escape(row.get('resit_test'))}</span></td>"
            f"<td><span class=\"pill {'good' if delta >= 0 else 'bad'}\">{'+' if delta >= 0 else ''}{_percentage(delta)}</span></td>"
            f"<td>{'-' if row.get('delta_grade') is None else ('+' if float(row['delta_grade']) >= 0 else '') + _number(row.get('delta_grade'))}</td>"
            "</tr>"
        )
    return "".join(html_rows)


def build_development_group_report_html(data: dict[str, object], options: dict[str, object] | None = None) -> str:
    summary = data.get("summary", {})
    resit_rows = list(data.get("resits", {}).get("rows", []))
    kpis = [
        ("Leerlingen", summary.get("student_count"), "met complete resultaten"),
        ("Toetsen", summary.get("test_count"), "eindresultaat gebruikt"),
        ("Gemiddelde score", _percentage(summary.get("mean_score_percentage")), "% van punten"),
        ("Gemiddeld cijfer", _number(summary.get("mean_grade")), "alleen vastgestelde normeringen"),
    ]
    body: list[str] = []
    if _option(options, "summary"):
        body.extend(
            [
                '<section class="grid">',
                *[
                    '<article class="card"><div class="kpi-label">'
                    f'{_escape(label)}</div><div class="kpi-value">{_escape(value)}</div><div class="guide">{_escape(note)}</div></article>'
                    for label, value, note in kpis
                ],
                '</section>',
                _overview_cards(list(data.get("overview", []))),
            ]
        )
    show_tests = _option(options, "tests")
    show_resits = _option(options, "resits") and bool(resit_rows)
    if show_tests or show_resits:
        body.append('<section class="two-col section">')
        if show_tests:
            body.extend(
                [
                    '<article class="card"><h2>Ontwikkeling per toets</h2><p class="guide">Gemiddelde scorepercentages per toets in de huidige selectie.</p>'
                    '<table><thead><tr><th>Toets</th><th>Gem. %</th><th>Gem. cijfer</th><th>Leerlingen</th></tr></thead><tbody>',
                    _test_rows(list(data.get("test_summaries", []))),
                    '</tbody></table></article>',
                ]
            )
        if show_resits:
            body.extend(
                [
                    '<article class="card"><h2>Herkansingen</h2><p class="guide">Originele toets vergeleken met herkansing. In de analyse telt het eindresultaat.</p>'
                    '<table><thead><tr><th>Leerling</th><th>Origineel</th><th>Herkansing</th><th>Verschil %</th><th>Verschil cijfer</th></tr></thead><tbody>',
                    _resit_rows(resit_rows),
                    '</tbody></table></article>',
                ]
            )
        body.append('</section>')
    if _option(options, "signals"):
        body.extend(
            [
                '<section class="two-col section">',
                '<article class="card"><h2>Leerlinggerichte trends en signalen</h2>'
                '<p class="guide">Leerlingen met duidelijke vooruitgang, terugval, wisselende resultaten of een opvallende positie in de groep.</p>'
                '<table><thead><tr><th>Type</th><th>Onderwerp</th><th>Onderbouwing</th></tr></thead><tbody>',
                _signal_rows(list(data.get("student_signals", data.get("signals", [])))),
                '</tbody></table></article>',
                '<article class="card"><h2>Groep en onderdelen</h2>'
                '<p class="guide">Positieve en negatieve ontwikkelingen die in de totale selectie opvallen.</p>'
                '<table><thead><tr><th>Type</th><th>Onderwerp</th><th>Onderbouwing</th></tr></thead><tbody>',
                _signal_rows(list(data.get("group_signals", []))),
                '</tbody></table></article>',
                '</section>',
            ]
        )
        body.extend(
            [
                '<section class="card section"><h2>Niet meegedaan of toets niet gemaakt</h2>'
                '<p class="guide">Leerlingen die in deze selectie vaker een niet-gemaakte status hebben, zoals absent, ziek of vrijstelling.</p>'
                '<table><thead><tr><th>Leerling</th><th>Aantal</th><th>Meest voorkomend</th><th>Toetsen</th></tr></thead><tbody>',
                _attendance_rows(list(data.get("attendance_issues", []))),
                '</tbody></table></section>',
            ]
        )
    if _option(options, "classifications"):
        for dimension in data.get("group_dimensions", []):
            entries = list(dimension.get("entries", []))
            if not entries:
                continue
            strongest = max(entries, key=lambda entry: float(entry.get("percentage") or 0))
            weakest = min(entries, key=lambda entry: float(entry.get("percentage") or 0))
            body.append(
                '<section class="card section dim-section">'
                f'<h2>{_escape(dimension.get("title"))}</h2>'
                f'<p class="guide">Sterkste onderdeel: <b>{_escape(strongest.get("name"))}</b> ({_percentage(strongest.get("percentage"))}). '
                f'Aandachtspunt: <b>{_escape(weakest.get("name"))}</b> ({_percentage(weakest.get("percentage"))}).</p>'
                f'{_bar_rows(entries)}'
                '</section>'
            )
    return _report_shell(
        "Groepsontwikkelrapport",
        "Ontwikkeling over meerdere toetsen op basis van scorepercentages en vastgestelde cijfers waar beschikbaar.",
        "".join(body),
    )


def _student_dimension_entries(data: dict[str, object], student_id: int) -> list[dict[str, object]]:
    points = [
        point
        for point in data.get("profile_chart", {}).get("points", [])
        if int(point.get("student_id", -1)) == int(student_id)
    ]
    by_dimension: dict[str, dict[str, object]] = {}
    group_dimensions = {str(dimension["key"]): dimension for dimension in data.get("group_dimensions", [])}
    group_lookup: dict[tuple[str, str], float] = {}
    for dimension in data.get("group_dimensions", []):
        for entry in dimension.get("entries", []):
            group_lookup[(str(dimension["key"]), str(entry["name"]))] = float(entry.get("percentage") or 0)
    for point in points:
        key = str(point["dimension_key"])
        dimension = by_dimension.setdefault(
            key,
            {
                "key": key,
                "title": group_dimensions.get(key, {}).get("title", point.get("dimension_title")),
                "entries": [],
            },
        )
        dimension["entries"].append(
            {
                "name": point["category"],
                "percentage": point["percentage"],
                "group_percentage": group_lookup.get((key, str(point["category"]))),
                "percentile": point.get("percentile"),
            }
        )
    return list(by_dimension.values())


def _student_compare_rows(entries: list[dict[str, object]]) -> str:
    rows = []
    for entry in entries:
        pupil = max(0.0, min(100.0, float(entry.get("percentage") or 0)))
        group = max(0.0, min(100.0, float(entry.get("group_percentage") or 0)))
        rows.append(
            '<div class="bar-row">'
            f'<div class="bar-label">{_escape(entry.get("name"))}<br><span class="guide">beter dan {_percentage(entry.get("percentile"))} van de leerlingen</span></div>'
            '<div class="compare-track">'
            f'<div class="compare-group" style="left:0;width:{group:.1f}%"></div>'
            f'<div class="compare-student" style="left:0;width:{pupil:.1f}%"></div>'
            '</div>'
            f'<div><b>{_percentage(pupil)}</b></div>'
            '</div>'
        )
    return "".join(rows)


def _tone_class(tone: object) -> str:
    if str(tone) == "green":
        return "good"
    if str(tone) == "red":
        return "bad"
    if str(tone) == "amber":
        return "warn"
    return ""


def _trend_tone(value: object, *, stability: bool = False) -> str:
    if value is None:
        return ""
    number = _safe_float(value)
    if stability:
        if number <= 10:
            return "good"
        if number <= 15:
            return "warn"
        return "bad"
    if number >= 5:
        return "good"
    if number <= -5:
        return "bad"
    return "warn"


def _position_value(item: dict[str, object]) -> str:
    return "-" if item.get("percentile") is None else f"beter dan {_percentage(item.get('percentile'))}"


def _position_detail(item: dict[str, object]) -> str:
    if item.get("rank") is None:
        return "Nog geen groepspositie beschikbaar."
    if item.get("tied_count") is not None and _safe_float(item.get("tied_count")) > 1:
        if item.get("rank_count") is not None:
            return f"Plaats {item.get('rank')} gedeeld met {item.get('tied_count')} leerlingen van {item.get('rank_count')} binnen deze selectie."
        return f"Plaats {item.get('rank')} gedeeld binnen deze selectie."
    if item.get("rank_count") is not None:
        return f"Plaats {item.get('rank')} van {item.get('rank_count')} binnen deze selectie."
    return f"Plaats {item.get('rank')} binnen deze selectie."


def _trend_card_html(label: str, value: object, detail: str, tone: str = "") -> str:
    return (
        f'<article class="trend-card {tone}">'
        f'<div class="label">{_escape(label)}</div>'
        f'<div class="value">{_escape(value)}</div>'
        f'<div class="guide" style="margin:3px 0 0">{_escape(detail)}</div>'
        '</article>'
    )


def _student_trend_cards(student: dict[str, object]) -> str:
    trend = student.get("trend", {}) if isinstance(student.get("trend"), dict) else {}
    cards = [
        _trend_card_html(
            "Over alle toetsen",
            _signed_percentage(trend.get("delta")),
            "Ontwikkeling over de gekozen toetsen.",
            _trend_tone(trend.get("delta")),
        ),
        _trend_card_html(
            "Sinds vorige toets",
            _signed_percentage(trend.get("recent_delta")),
            "Verschil tussen vorige en huidige toets.",
            _trend_tone(trend.get("recent_delta")),
        ),
        _trend_card_html(
            "Positie in de groep",
            _signed_percentage(trend.get("percentile_delta")),
            "Verandering ten opzichte van klasgenoten.",
            _trend_tone(trend.get("percentile_delta")),
        ),
        _trend_card_html(
            "Stabiliteit",
            f"{round(_safe_float(trend.get('stability')))} punten" if trend.get("stability") is not None else "-",
            "Lager betekent gelijkmatiger.",
            _trend_tone(trend.get("stability"), stability=True),
        ),
    ]
    return '<div class="trend-card-grid">' + "".join(cards) + '</div>'


def _line_chart_svg(student: dict[str, object]) -> str:
    tests = list(student.get("tests", []))
    if not tests:
        return '<p class="guide">Er zijn geen toetsresultaten beschikbaar voor deze leerling.</p>'
    width, height = 980, 360
    left, top, plot_w, plot_h = 58, 28, 865, 195

    def x_pos(index: int) -> float:
        if len(tests) <= 1:
            return left + plot_w / 2
        return left + index / (len(tests) - 1) * plot_w

    def y_pos(value: object) -> float:
        return top + (100 - _clamp(value)) / 100 * plot_h

    grid = []
    for tick in range(0, 101, 20):
        y = y_pos(tick)
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#dfe7f2"/>')
        grid.append(f'<text x="{left - 10}" y="{y + 4:.1f}" text-anchor="end" fill="#40516a" font-size="12">{tick}%</text>')
    grid.append(
        f'<line x1="{left}" y1="{y_pos(55):.1f}" x2="{left + plot_w}" y2="{y_pos(55):.1f}" '
        'stroke="#9aa8bd" stroke-width="1.4" stroke-dasharray="8 9"/>'
    )

    label_nodes = []
    for index, test in enumerate(tests):
        x = x_pos(index)
        if len(tests) <= 5:
            label_nodes.append(_svg_multiline_text(test.get("name"), x, height - 94, max_chars=18, font_size=11))
        else:
            label_nodes.append(
                f'<text x="{x:.1f}" y="{height - 86}" text-anchor="end" transform="rotate(-25 {x:.1f} {height - 86})" '
                f'fill="#40516a" font-size="10">{_escape(_short_label(test.get("name"), 14))}</text>'
            )

    def polyline(values: list[object]) -> str:
        points = [
            f"{x_pos(index):.1f},{y_pos(value):.1f}"
            for index, value in enumerate(values)
            if value is not None
        ]
        return " ".join(points)

    student_values = [test.get("score_percentage") for test in tests]
    group_values = [test.get("group_mean_score_percentage") for test in tests]
    student_points = "".join(
        f'<circle cx="{x_pos(index):.1f}" cy="{y_pos(value):.1f}" r="5.2" fill="#5b5ff1" stroke="#fff" stroke-width="1.5"/>'
        for index, value in enumerate(student_values)
        if value is not None
    )
    group_points = "".join(
        f'<circle cx="{x_pos(index):.1f}" cy="{y_pos(value):.1f}" r="4.2" fill="#9aa8bd" stroke="#fff" stroke-width="1.2"/>'
        for index, value in enumerate(group_values)
        if value is not None
    )
    return (
        '<svg class="svg-chart" viewBox="0 0 980 360" role="img" aria-label="Trendontwikkeling per toets">'
        '<rect x="0" y="0" width="980" height="360" fill="#fff"/>'
        + "".join(grid)
        + f'<polyline points="{polyline(group_values)}" fill="none" stroke="#9aa8bd" stroke-width="2.4" stroke-dasharray="7 7"/>'
        + f'<polyline points="{polyline(student_values)}" fill="none" stroke="#5b5ff1" stroke-width="3.2"/>'
        + group_points
        + student_points
        + "".join(label_nodes)
        + f'<text x="{left}" y="16" fill="#40516a" font-size="12" font-weight="700">% van de punten</text>'
        + '</svg>'
    )


def _profile_categories(data: dict[str, object], dimension_key: str) -> list[str]:
    categories = [
        str(item.get("category"))
        for item in data.get("profile_chart", {}).get("categories", [])
        if str(item.get("dimension_key")) == str(dimension_key)
    ]
    if categories:
        return categories
    seen: list[str] = []
    for point in data.get("profile_chart", {}).get("points", []):
        if str(point.get("dimension_key")) == str(dimension_key):
            category = str(point.get("category"))
            if category not in seen:
                seen.append(category)
    return seen


def _student_profile_chart_svg(data: dict[str, object], student_id: int, dimension_key: str) -> str:
    categories = _profile_categories(data, dimension_key)
    points = [
        point
        for point in data.get("profile_chart", {}).get("points", [])
        if str(point.get("dimension_key")) == str(dimension_key) and str(point.get("category")) in categories
    ]
    if not categories or not points:
        return '<p class="guide">Geen profielgrafiek beschikbaar voor dit onderdeel.</p>'
    x_lookup = {category: index for index, category in enumerate(categories)}
    width, height = 980, 470
    left, top, plot_w, plot_h = 62, 38, 858, 245

    def x_pos(index: int) -> float:
        if len(categories) <= 1:
            return left + plot_w / 2
        return left + index / (len(categories) - 1) * plot_w

    def y_pos(value: object) -> float:
        return top + (100 - _clamp(value)) / 100 * plot_h

    grid = []
    max_label_chars = 22 if len(categories) <= 4 else 16 if len(categories) <= 6 else 11
    for tick in range(0, 101, 20):
        y = y_pos(tick)
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" stroke="#dfe7f2"/>')
        grid.append(f'<text x="{left - 11}" y="{y + 4:.1f}" text-anchor="end" fill="#40516a" font-size="12">{tick}%</text>')
    for index, category in enumerate(categories):
        x = x_pos(index)
        grid.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{top + plot_h}" stroke="#edf2f8"/>')
        if len(categories) <= 7:
            grid.append(_svg_multiline_text(category, x, height - 128, max_chars=max_label_chars, font_size=11))
        else:
            grid.append(
                f'<text x="{x:.1f}" y="{height - 126}" text-anchor="end" transform="rotate(-32 {x:.1f} {height - 126})" '
                f'fill="#40516a" font-size="10">{_escape(_short_label(category, max_label_chars))}</text>'
            )
    grid.append(
        f'<line x1="{left}" y1="{y_pos(55):.1f}" x2="{left + plot_w}" y2="{y_pos(55):.1f}" '
        'stroke="#9aa8bd" stroke-width="1.4" stroke-dasharray="8 9"/>'
    )

    circles = []
    selected = []
    for point in points:
        category = str(point.get("category"))
        index = x_lookup.get(category)
        if index is None:
            continue
        jitter = _safe_float(point.get("x_jitter"), index) - _safe_float(point.get("x"), index)
        jitter = max(-0.22, min(0.22, jitter))
        x = x_pos(index) + jitter * 52
        y = y_pos(point.get("percentage"))
        is_selected = int(point.get("student_id", -1)) == int(student_id)
        if is_selected:
            selected.append((index, point))
        else:
            color = "#2fa866" if bool(point.get("sufficient")) else "#e24a4a"
            circles.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.7" fill="{color}" fill-opacity=".65" stroke="#fff" stroke-width="1"/>'
            )
    selected.sort(key=lambda item: item[0])
    selected_polyline = " ".join(
        f"{x_pos(index):.1f},{y_pos(point.get('percentage')):.1f}"
        for index, point in selected
    )
    selected_nodes = "".join(
        f'<circle cx="{x_pos(index):.1f}" cy="{y_pos(point.get("percentage")):.1f}" r="7" fill="#5b5ff1" stroke="#fff" stroke-width="2"/>'
        for index, point in selected
    )
    return (
        '<svg class="svg-chart" viewBox="0 0 980 470" role="img" aria-label="Profielgrafiek per onderdeel">'
        '<rect x="0" y="0" width="980" height="470" fill="#fff"/>'
        + "".join(grid)
        + "".join(circles)
        + (
            f'<polyline points="{selected_polyline}" fill="none" stroke="#5b5ff1" stroke-width="3.2" stroke-dasharray="5 6"/>'
            if selected_polyline else ""
        )
        + selected_nodes
        + f'<text x="{left}" y="20" fill="#40516a" font-size="12" font-weight="700">% van de punten</text>'
        + '</svg>'
    )


def _selected_student_attendance(data: dict[str, object], student_id: int) -> dict[str, object] | None:
    for row in data.get("attendance_issues", []):
        if int(row.get("student_id", -1)) == int(student_id):
            return row
    return None


def _student_signal_groups(data: dict[str, object], student: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    student_id = int(student.get("id", -1))
    trend = student.get("trend", {}) if isinstance(student.get("trend"), dict) else {}
    points = [
        point for point in data.get("profile_chart", {}).get("points", [])
        if int(point.get("student_id", -1)) == student_id
    ]
    student_resits = [
        row for row in data.get("resits", {}).get("rows", [])
        if int(row.get("student_id", -1)) == student_id
    ]
    attendance = _selected_student_attendance(data, student_id)
    total_tests = int(_safe_float(data.get("summary", {}).get("test_count"), 0))
    positive: list[dict[str, object]] = []
    notable: list[dict[str, object]] = []
    improvements: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()

    def add(target: list[dict[str, object]], title: str, subject: object, detail: str, tone: str) -> None:
        key = (title, str(subject))
        if key in seen:
            return
        seen.add(key)
        target.append({"title": title, "subject": subject, "detail": detail, "tone": tone})

    if _safe_float(student.get("score_percentage")) >= 70:
        add(positive, "Sterk totaalbeeld", _percentage(student.get("score_percentage")), "Gemiddeld hoog over de gekozen toetsen.", "green")
    if trend.get("delta") is not None and _safe_float(trend.get("delta")) >= 10:
        add(positive, "Duidelijke vooruitgang", _signed_percentage(trend.get("delta")), "Over alle gekozen toetsen.", "green")
    if trend.get("recent_delta") is not None and _safe_float(trend.get("recent_delta")) >= 10:
        add(positive, "Recente groei", _signed_percentage(trend.get("recent_delta")), "Tussen vorige en huidige toets.", "green")
    if trend.get("percentile_delta") is not None and _safe_float(trend.get("percentile_delta")) >= 10:
        add(positive, "Sterkere positie", _signed_percentage(trend.get("percentile_delta")), "Hoger ten opzichte van klasgenoten.", "green")

    for point in sorted(points, key=lambda item: _safe_float(item.get("percentage")), reverse=True)[:4]:
        if _safe_float(point.get("percentage")) >= 70:
            add(
                positive,
                f"Sterk onderdeel: {point.get('dimension_title')}",
                point.get("category"),
                f"{_percentage(point.get('percentage'))} van de punten; beter dan {_percentage(point.get('percentile'))} van de leerlingen.",
                "green",
            )
    for dimension in student.get("dimension_trends", []):
        for entry in sorted(dimension.get("entries", []), key=lambda item: _safe_float(item.get("delta")), reverse=True)[:3]:
            if entry.get("delta") is not None and _safe_float(entry.get("delta")) >= 10:
                add(
                    positive,
                    f"Groei in {dimension.get('title')}",
                    entry.get("name"),
                    f"{_signed_percentage(entry.get('delta'))} over de gekozen toetsen.",
                    "green",
                )

    if attendance:
        add(notable, "Niet alles gemaakt", f"{attendance.get('count')} van {attendance.get('total_tests')}", f"Meest voorkomend: {_status_label(attendance.get('most_common_status'))}.", "amber")
    if total_tests and int(_safe_float(student.get("test_count"))) < total_tests:
        add(notable, "Minder toetsdata", f"{student.get('test_count')} van {total_tests} toetsen", "Daardoor is de ontwikkeling minder stevig te beoordelen.", "amber")
    if trend.get("stability") is not None and _safe_float(trend.get("stability")) >= 15:
        add(notable, "Wisselend beeld", f"{round(_safe_float(trend.get('stability')))} punten", "De resultaten verschillen sterk tussen toetsen.", "amber")
    if student_resits:
        mean_delta = sum(_safe_float(row.get("delta_percentage")) for row in student_resits) / len(student_resits)
        add(notable, "Herkansing meegenomen", f"{len(student_resits)} keer", f"Gemiddeld verschil: {_signed_percentage(mean_delta)}.", "amber" if mean_delta < 0 else "green")
    if student.get("percentile") is not None and _safe_float(student.get("percentile")) >= 90:
        add(notable, "Hoog in de groep", _position_value(student), "Deze leerling hoort in deze selectie bij de hogere scores.", "green")

    if _safe_float(student.get("score_percentage")) < 55:
        add(improvements, "Totaal onder 55%", _percentage(student.get("score_percentage")), "Gemiddeld onder de voldoendegrens op scorepercentage.", "red")
    if trend.get("delta") is not None and _safe_float(trend.get("delta")) <= -10:
        add(improvements, "Dalende lijn", _signed_percentage(trend.get("delta")), "Over alle gekozen toetsen.", "red" if _safe_float(trend.get("delta")) <= -20 else "amber")
    if trend.get("recent_delta") is not None and _safe_float(trend.get("recent_delta")) <= -10:
        add(improvements, "Recente terugval", _signed_percentage(trend.get("recent_delta")), "Tussen vorige en huidige toets.", "red" if _safe_float(trend.get("recent_delta")) <= -20 else "amber")
    if trend.get("percentile_delta") is not None and _safe_float(trend.get("percentile_delta")) <= -10:
        add(improvements, "Positie zakt", _signed_percentage(trend.get("percentile_delta")), "Lager ten opzichte van klasgenoten.", "red" if _safe_float(trend.get("percentile_delta")) <= -20 else "amber")
    for point in sorted(points, key=lambda item: _safe_float(item.get("percentage")))[:5]:
        if _safe_float(point.get("percentage")) < 55:
            add(
                improvements,
                f"Oefenen: {point.get('dimension_title')}",
                point.get("category"),
                f"{_percentage(point.get('percentage'))} van de punten; beter dan {_percentage(point.get('percentile'))} van de leerlingen.",
                "red" if _safe_float(point.get("percentage")) < 45 else "amber",
            )
    for dimension in student.get("dimension_trends", []):
        for entry in sorted(dimension.get("entries", []), key=lambda item: _safe_float(item.get("delta")))[:3]:
            if entry.get("delta") is not None and _safe_float(entry.get("delta")) <= -10:
                add(
                    improvements,
                    f"Terugval in {dimension.get('title')}",
                    entry.get("name"),
                    f"{_signed_percentage(entry.get('delta'))} over de gekozen toetsen.",
                    "red" if _safe_float(entry.get("delta")) <= -20 else "amber",
                )

    return {"positive": positive[:6], "notable": notable[:6], "improvements": improvements[:6]}


def _student_signal_section(data: dict[str, object], student: dict[str, object]) -> str:
    groups = _student_signal_groups(data, student)

    def cards(items: list[dict[str, object]], empty: str) -> str:
        if not items:
            return f'<p class="guide">{_escape(empty)}</p>'
        return "".join(
            f'<article class="signal-card {_tone_class(item.get("tone"))}">'
            f'<div class="tag">{_escape(item.get("title"))}</div>'
            f'<div class="subject">{_escape(item.get("subject"))}</div>'
            f'<div class="detail">{_escape(item.get("detail"))}</div>'
            '</article>'
            for item in items
        )

    return (
        '<section class="card section fit-page-card">'
        '<h2>Signalen voor deze leerling</h2>'
        '<p class="guide">Deze kaarten vertalen de grafieken naar gewone taal. Ze combineren totaalscore, recente ontwikkeling, positie in de groep en onderdelen zoals taxonomie, domein, hoofdstuk en vraagtype.</p>'
        '<div class="signal-board">'
        '<div class="signal-column"><h3>Positief</h3>'
        + cards(groups["positive"], "Geen duidelijke positieve uitschieter gevonden.")
        + '</div><div class="signal-column"><h3>Opvallend</h3>'
        + cards(groups["notable"], "Geen opvallende bijzonderheden gevonden.")
        + '</div><div class="signal-column"><h3>Verbeterpunten</h3>'
        + cards(groups["improvements"], "Geen duidelijk verbeterpunt gevonden binnen deze selectie.")
        + '</div></div></section>'
    )


def _student_resit_rows(data: dict[str, object], student_id: int) -> str:
    rows = [
        row for row in data.get("resits", {}).get("rows", [])
        if int(row.get("student_id", -1)) == int(student_id)
    ]
    return _resit_rows(rows)


def build_development_student_report_html(
    data: dict[str, object],
    student_id: int,
    options: dict[str, object] | None = None,
) -> str:
    student = next((item for item in data.get("students", []) if int(item.get("id", -1)) == int(student_id)), None)
    if not student:
        raise ValueError("De gekozen leerling is niet gevonden in de ontwikkelanalyse.")
    student_resit_rows = [
        row for row in list(data.get("resits", {}).get("rows", []))
        if int(row.get("student_id") or 0) == int(student_id)
    ]
    kpis = [
        ("% van punten", _percentage(student.get("score_percentage")), "over de geselecteerde toetsen"),
        ("Gemiddeld cijfer", _number(student.get("mean_grade")), "alleen vastgestelde normeringen"),
        ("Toetsen", student.get("test_count"), "met complete resultaten"),
        ("Positie", _position_value(student), _position_detail(student)),
    ]
    body: list[str] = []
    if _option(options, "summary"):
        body.extend(
            [
                '<section class="grid">',
                *[
                    '<article class="card"><div class="kpi-label">'
                    f'{_escape(label)}</div><div class="kpi-value">{_escape(value)}</div><div class="guide">{_escape(note)}</div></article>'
                    for label, value, note in kpis
                ],
                '</section>',
            ]
        )
    if _option(options, "signals"):
        body.append(_student_signal_section(data, student))
    if _option(options, "tests"):
        body.extend(
            [
                '<section class="card section fit-page-card"><h2>Ontwikkeling per toets</h2>'
                '<p class="guide">De blauwe lijn is de leerling. De grijze stippellijn is het groepsgemiddelde. Zo ziet u of de leerling mee beweegt met de groep of juist afwijkt.</p>'
                f'{_student_trend_cards(student)}'
                f'{_line_chart_svg(student)}'
                '<div class="legend"><span><i class="dot" style="background:#5b5ff1"></i>leerling</span>'
                '<span><i class="dot" style="background:#9aa8bd"></i>groepsgemiddelde</span>'
                '<span>De horizontale stippellijn ligt op 55%.</span></div>'
                '<h3>Toetsen in deze selectie</h3>'
                '<p class="guide">Per toets staat het behaalde percentage van de punten. Cijfers verschijnen alleen bij vastgestelde normering.</p>'
                '<table><thead><tr><th>Toets</th><th>% punten</th><th>Cijfer</th><th></th></tr></thead><tbody>',
                _test_rows(list(student.get("tests", []))),
                '</tbody></table></section>',
            ]
        )
    dimension_entries = _student_dimension_entries(data, int(student["id"]))
    if _option(options, "classifications"):
        for dimension in dimension_entries:
            entries = list(dimension.get("entries", []))
            if not entries:
                continue
            strongest = max(entries, key=lambda entry: float(entry.get("percentage") or 0))
            weakest = min(entries, key=lambda entry: float(entry.get("percentage") or 0))
            body.append(
                '<section class="card section dim-section fit-page-card">'
                f'<h2>{_escape(dimension.get("title"))}</h2>'
                '<p class="guide">Elke stip is een leerling binnen deze selectie. Groen betekent minimaal 55% van de punten, rood betekent daaronder. '
                'De blauwe stippellijn verbindt de onderdelen van deze leerling, zodat het profiel in één oogopslag zichtbaar wordt. '
                f'Sterkste onderdeel: <b>{_escape(strongest.get("name"))}</b> ({_percentage(strongest.get("percentage"))}). '
                f'Aandachtspunt: <b>{_escape(weakest.get("name"))}</b> ({_percentage(weakest.get("percentage"))}).</p>'
                f'{_student_profile_chart_svg(data, int(student["id"]), str(dimension.get("key")))}'
                '<div class="legend"><span><i class="dot" style="background:#2fa866"></i>55% of hoger</span>'
                '<span><i class="dot" style="background:#e24a4a"></i>onder 55%</span>'
                '<span><i class="dot" style="background:#5b5ff1"></i>deze leerling</span></div>'
                '<p class="guide">De balken hieronder vergelijken dezelfde onderdelen nog compacter: blauw is de leerling, grijs is het groepsgemiddelde. '
                'Achter elk onderdeel staat hoeveel procent van de leerlingen lager scoorde.</p>'
                f'{_student_compare_rows(entries)}'
                '</section>'
            )
    if _option(options, "resits") and student_resit_rows:
        body.extend(
            [
                '<section class="card section fit-page-card"><h2>Herkansingen</h2>'
                '<p class="guide">Originele toets vergeleken met herkansing voor deze leerling.</p>'
                '<table><thead><tr><th>Leerling</th><th>Origineel</th><th>Herkansing</th><th>Verschil %</th><th>Verschil cijfer</th></tr></thead><tbody>',
                _resit_rows(student_resit_rows),
                '</tbody></table></section>',
            ]
        )
    return _report_shell(
        f"Leerlingontwikkelrapport - {student['name']}",
        "Ontwikkeling over meerdere toetsen, vergeleken met de groep/selectie.",
        "".join(body),
    )
