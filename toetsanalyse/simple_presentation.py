"""A plain-language entry point into the existing full dashboards."""

PLAIN_ANALYSIS_HELP = """<script>
function simpleItemExplanation(item) {
 if (item.correction_enabled && item.correction_mode === 'neutralize') return 'Deze vraag is geneutraliseerd: alle ingevoerde antwoorden tellen goed.';
 if (item.response_count === 0) return 'Er zijn geen gekozen antwoordletters om te vergelijken. Bekijk ook het aantal niet-gemaakte vragen.';
 if (item.p_value === null || item.p_value === undefined) return 'Er zijn nog geen resultaten voor deze vraag om te beoordelen.';
 const notes=[];
 if (item.p_value < .3) notes.push('Op deze vraag zijn weinig punten behaald. Bekijk of de vraag past bij wat u heeft behandeld.');
 else if (item.p_value > .9) notes.push('Op deze vraag zijn veel punten behaald. Bekijk of deze vraag voldoende uitdaging biedt.');
 if ((item.rit !== null && item.rit < 0) || (item.rir !== null && item.rir < 0)) notes.push('Leerlingen die op de rest van de toets goed scoren, halen hier niet vanzelf meer punten. Controleer de vraag en de beoordeling.');
 else if ((item.rit !== null && item.rit < .2) || (item.rir !== null && item.rir < .1)) notes.push('Deze vraag maakt weinig onderscheid tussen leerlingen met hogere en lagere toetsscores. Bekijk of dat past bij het doel van de vraag.');
 else if (item.rit === null || item.rir === null) notes.push('Er zijn te weinig resultaten of te weinig verschillen in scores om het onderscheid tussen leerlingen goed te beoordelen.');
 return notes.length ? notes.join(' ') : 'Deze vraag geeft op basis van de scores geen direct aandachtspunt. Controleer ook zelf of de inhoud en beoordeling passen bij uw leerdoel.';
}
function simpleBadge(item) {
 const status=item.status || {};
 return '<span class="badge '+esc(status.level || 'neutral')+'" title="Bekijk de uitleg bij deze vraag">'+esc(status.label || 'Bekijken')+'</span>';
}
</script>"""

NORMING_HELP_SCRIPT = """
const scoreExample = document.getElementById('simpleScoreExample');
scoreExample.max=String(maximum);
scoreExample.value=String(Math.round(maximum/2));
function updateSimpleNormHelp() {
 const texts={
  n_term:'Met de N-term bepaalt u hoe punten naar cijfers worden omgezet. Een hogere N-term geeft bij dezelfde score doorgaans een hoger cijfer. Een lagere N-term is strenger. Aan de grenzen kan het cijfer gelijk blijven.',
  fouten_per_punt:'U kiest hoeveel van het cijfer afgaat voor elk gemist punt. Meer aftrek per gemist punt geeft lagere cijfers.',
  cvte_cesuur:'U kiest hoeveel punten bij een 5,5 horen. Een hogere puntengrens is strenger; er zijn dan meer punten nodig voor een voldoende.',
  cesuur:'U kiest het aantal punten voor een 5,5. Bekijk in het voorbeeld welk cijfer een andere score krijgt. Een hogere voldoendegrens is strenger.',
  cesuur_knik:'U kiest het aantal punten voor een 5,5. Onder en boven deze grens worden punten naar cijfers omgerekend. Een hogere voldoendegrens is strenger.',
  percentage_voldoende:'U kiest welk percentage van de punten bij een 5,5 hoort. Een hoger percentage betekent dat meer punten nodig zijn voor een voldoende.'
 };
 document.getElementById('simpleMethodExplanation').textContent=texts[state.method] || 'Bekijk hoe uw gekozen methode punten naar cijfers omzet.';
 const value=Number(scoreExample.value);
 const output=document.getElementById('simpleGradeExample');
 if (scoreExample.value==='' || !Number.isFinite(value) || value<0 || value>maximum) {
  output.textContent='Vul een score tussen 0 en '+format(maximum,maximum%1?1:0)+' in.';
 } else {
  output.textContent='Met deze instellingen levert '+format(value,value%1?1:0)+' van '+format(maximum,maximum%1?1:0)+' punten het cijfer '+displayGrade(grade(value))+' op.';
 }
}
document.addEventListener('input',updateSimpleNormHelp);
document.addEventListener('change',updateSimpleNormHelp);
document.addEventListener('click',event=>{if(event.target.closest('.method')) updateSimpleNormHelp();});
updateSimpleNormHelp();
"""


def simplify_dashboard(document: str, kind: str, *, normalization_finalized: bool = False) -> str:
    if kind == "analysis":
        intro = "Bekijk hoe de toets is gemaakt, welke vragen opvallen en hoe leerlingen scoren. Groepsniveau gaat over de deelnemers aan deze toets; daar vindt u ook de indelingen."
        if not normalization_finalized:
            intro = "<strong>Nog geen vastgestelde normering.</strong> U kunt scores en toetsvragen al analyseren. Cijfers en cijferafhankelijke onderdelen zijn nog niet beschikbaar. Stel eerst de normering vast om die te bekijken.<br>" + intro
        button = "Meer informatie en technische details"
        selectors = ".metric-help, .mc-metrics, .mc-summary .mc-stat:nth-child(2), .mc-summary .mc-stat:nth-child(3), .item-card th:nth-child(3), .item-card th:nth-child(4), .item-card td:nth-child(3), .item-card td:nth-child(4)"
        document = document.replace("${metricChip(item.p_value, item.p_status)}", "${percentage(item.p_value === null ? null : item.p_value * 100)}")
        document = document.replace(">P-waarde <span", ">Gemiddeld behaald <span")
        document = document.replace("Moeilijkheid: het gemiddeld behaalde aandeel van de punten. Advieszone: 0,30 tot 0,80.", "Het gemiddelde percentage van de maximumscore dat op deze vraag is behaald.")
        document = document.replace("${badge(item.status)}", "${simpleBadge(item)}")
        document = document.replace("${esc(item.status.reason)}<br>${esc(item.status.advice)}",
            '<span class="simple-explanation">${esc(simpleItemExplanation(item))}</span><span class="technical-detail">${esc(item.status.reason)}<br>${esc(item.status.advice)}</span>')
        document = document.replace('${esc(item.conclusion.text)}<br><span class="kpi-note">P-waarde = moeilijkheid, Rit/Rir = onderscheidend vermogen binnen deze toets.</span>',
            '<span class="simple-explanation">${esc(simpleItemExplanation(item))}</span><span class="technical-detail">${esc(item.conclusion.text)}<br><span class="kpi-note">P-waarde = moeilijkheid, Rit/Rir = onderscheidend vermogen binnen deze toets.</span></span>')
        extra = """
const quality = document.getElementById('qualityCards');
if (quality) {
  const warning = document.getElementById('sampleWarning');
  const kpis = document.getElementById('generalKpis');
  if (warning && kpis) kpis.after(warning);
  quality.closest('article').classList.add('technical-detail');
}
const reliability = document.getElementById('reliabilityText');
if (reliability) reliability.closest('article').classList.add('technical-detail');
"""
    else:
        intro = "Hier zet u punten om in cijfers. U begint met N-term 1,0, tenzij u al een normering heeft opgeslagen. Bekijk de cijfers en kies Normering vaststellen als u tevreden bent."
        button = "Andere normeringsmogelijkheden en meer uitleg"
        selectors = ".metric-help"
        extra = NORMING_HELP_SCRIPT
    styles = """<style>
.simple-guide{padding:14px 20px;background:#edf3ff;border-bottom:1px solid #c9daf9;font:14px 'Segoe UI',sans-serif;line-height:1.6}
.simple-guide button{display:block;margin-top:8px;padding:10px 14px;border:1px solid #a6bce8;border-radius:7px;background:white;color:#17243c;cursor:pointer}
.simple-guide.simple-no-norm{background:#fff3d6;border-color:#d97706}
body.simple-view:not(.show-details) .technical-detail{display:none!important}
body.simple-view.show-details .simple-explanation{display:none!important}
.simple-norm-help{margin-top:10px;padding:10px;border:1px solid #c9daf9;border-radius:6px;background:white}
.simple-norm-help input{margin:5px 8px;padding:6px;width:90px;font:inherit;border:1px solid #a6bce8;border-radius:4px}
.simple-norm-help output{display:block;font-weight:600;margin-top:6px}
body.simple-view:not(.show-details) .mc-summary{grid-template-columns:repeat(2,minmax(0,1fr))}
""" + ("body.simple-view:not(.show-details) .method:not(.active){display:none!important}" if kind == "norm" else "") + "</style>"
    hidden_selectors = ",".join("body.simple-view:not(.show-details) " + selector.strip() for selector in selectors.split(","))
    styles = styles.replace("</style>", hidden_selectors + "{display:none!important}</style>")
    notice = " simple-no-norm" if kind == "analysis" and not normalization_finalized else ""
    norm_help = '<section class="simple-norm-help"><div id="simpleMethodExplanation"></div><label for="simpleScoreExample">Probeer een score:</label><input id="simpleScoreExample" type="number" min="0" step="any"><output id="simpleGradeExample" aria-live="polite"></output><small>Dit voorbeeld verandert geen leerlingenscores. Pas de normeringsinstelling aan om het effect te zien.</small></section>' if kind == "norm" else ""
    guide = f'<div class="simple-guide{notice}">{intro}{norm_help}<button type="button" id="simpleDetails" aria-expanded="false">{button}</button></div>'
    script = """<script>
document.body.classList.add('simple-view');
%s
document.getElementById('simpleDetails').addEventListener('click',function(){
 const expanded = document.body.classList.toggle('show-details');
 this.setAttribute('aria-expanded',String(expanded));
 this.textContent=expanded?'Technische details verbergen':%s;
 window.dispatchEvent(new Event('resize'));
});
</script>"""
    import json
    script %= (extra, json.dumps(button))
    helpers = PLAIN_ANALYSIS_HELP if kind == "analysis" else ""
    return document.replace("</head>", styles + helpers + "</head>", 1).replace("<body>", "<body>" + guide, 1).replace("</body>", script + "</body>")
