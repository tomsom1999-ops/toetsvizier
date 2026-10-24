"""Step-by-step, illustrated help for the single-test input screen."""
import math

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from .ui_helpers import set_button_role


TOPICS = [
    ("Aantallen instellen", "<p>Boven uw tabel staan <b>Aantal vragen</b> en <b>Aantal leerlingen</b>. "
     "U kunt deze aantallen later aanpassen. Een hoger aantal maakt extra kolommen of rijen zichtbaar.</p>"
     "<p><b>Een lager aantal wist niets.</b> Voorbeeld: van 25 naar 20 leerlingen verbergt de laatste vijf rijen. "
     "Terug naar 25 laat hun namen en scores weer zien. Dit geldt ook voor vragen, indelingen en antwoordsleutels.</p>"
     "<p>Normeren, analyseren en exporteren gebruiken alleen de zichtbare aantallen. "
     "Na wijziging van het aantal vragen moet u de normering opnieuw vaststellen.</p>", "counts"),
    ("Maximumscores en namen", "<p><b>1.</b> Vul in de bovenste blauwe rij het maximumaantal punten per vraag in. "
     "Bij een vraag van maximaal drie punten typt u <b>3</b>.</p>"
     "<p><b>2.</b> Vervang links in de kolom <b>Leerlingnaam</b> de voorbeeldnamen door uw leerlingnamen. "
     "Namen blijven ook links naast de tabel zichtbaar als u naar andere vragen schuift.</p>"
     "<p><b>Afwezige leerlingen neemt u niet op.</b> Wilt u een leerling echt verwijderen? Selecteer de rij en kies "
     "Leerling verwijderen. Dat is anders dan het aantal verlagen: verwijderen haalt de leerling en scores weg, "
     "na uw bevestiging. Een vergissing kunt u herstellen met Ongedaan maken.</p>", "names"),
    ("Punten, nul, N of een letter", "<p>Typ de behaalde punten in de cel van de leerling en de vraag. "
     "Bij <b>hele punten</b> springt u automatisch verder als het maximum <b>voor die vraag hoogstens 9</b> is. "
     "Heeft de vraag een hoger maximum? Bevestig uw score met <b>Enter</b> of <b>Tab</b>. "
     "Bij decimalen bevestigt u met Enter of Tab.</p>"
     "<p><b>Delete (Del) of Backspace</b> wist de geselecteerde scores, ook tijdens het bewerken. "
     "De cellen worden weer leeg, niet nul. Met <b>Ctrl+Z</b> herstelt u een vergissing.</p>"
     "<p><b>2</b> = twee punten. <b>0</b> = de vraag is gemaakt, maar levert geen punten op. "
     "<b>N</b> = niet gemaakt: nul punten, maar apart herkenbaar in de analyse. "
     "Een <b>lege cel</b> betekent dat u nog iets moet invullen.</p>"
     "<p>Standaard gebruikt u <b>hele punten</b>. Kies Halve punten, Kwartpunten of Tiende punten als dat nodig is; "
     "voer dan bijvoorbeeld <b>1,5</b> in. U kunt nooit meer punten geven dan de maximumscore.</p>"
     "<p>Bij een ingestelde meerkeuzevraag voert u de <b>gekozen antwoordletter</b> in. "
     "Boven de vraag staat de antwoordsleutel, bijvoorbeeld <b>Vraag 3 · Sleutel: B</b>. "
     "Na een antwoordletter of <b>N</b> springt u direct door, ook als u halve punten gebruikt. "
     "Goed meerkeuzeantwoord = groen; fout antwoord = lichtrood. Gewone punten blijven wit, ook bij nul. "
     "N is lichtoranje. De actieve leerling en vraag en een volledig ingevuld totaal zijn blauw.</p>"
     "<p>Is de invoer ongeldig? De cel krijgt een rode rand en bovenaan staat wat u moet corrigeren. "
     "Met Ga naar de eerste ontbrekende invoer springt u ook naar zo'n cel.</p>", "scores"),
    ("Vanuit Excel plakken", "<p><b>Alleen scores:</b> kopieer bijvoorbeeld twee rijen met elk drie scores uit Excel. "
     "Klik in Toetsvizier op de scorecel van de <b>eerste leerling, vraag 1</b> en druk op <b>Ctrl+V</b>.</p>"
     "<p><b>Namen én scores:</b> kopieer bijvoorbeeld <b>Sam | 2 | 0 | N</b> en <b>Alex | 1 | 2 | 2</b> "
     "uit Excel. De verticale streepjes stellen kolommen voor. Klik op de <b>eerste leerlingnaam</b> en druk op Ctrl+V. "
     "Selecteer hieronder welk voorbeeld u wilt zien: de markering wijst de begincel aan.</p>"
     "<p>Kopieer bij voorkeur alleen de gewenste cellen, zonder kolomkoppen of totaalkolommen. "
     "Maximumscores plakt u apart vanaf de blauwe cel onder Vraag 1. Lege scorecellen blijven leeg; "
     "nullen worden als echte scores overgenomen.</p>"
     "<p><b>Verkeerd geplakt?</b> Gebruik Ongedaan maken of Ctrl+Z. Als een waarde ongeldig is, "
     "wordt het blok niet gedeeltelijk opgeslagen: corrigeer het blok en plak opnieuw.</p>", "paste"),
    ("Horizontaal, verticaal of gecombineerd", "<p><b>Horizontaal (per leerling):</b> werk van links naar rechts door de vragen van één leerling. "
     "Na de laatste vraag gaat u naar de volgende leerling.</p>"
     "<p><b>Verticaal (per vraag):</b> kies Omlaag of Omhoog. Aan het einde van de leerlingen "
     "gaat u in de volgende vraag in de andere richting verder: omlaag, omhoog, omlaag.</p>"
     "<p><b>Gecombineerd:</b> kies een <b>Beginvraag</b> en een blokgrootte, bijvoorbeeld twee vragen. "
     "Voer vraag 1 en 2 in voor de eerste leerling, dan vraag 1 en 2 voor de volgende leerling. "
     "Na alle leerlingen schuift Beginvraag automatisch naar het volgende blok en keert de richting om.</p>"
     "<p>De invoer blijft bij de scorecellen en stopt bij het einde van de toets. De pijlen in het voorbeeld tonen de route.</p>"
     "<p><b>Groot invoerscherm</b> geeft de tabel zo veel mogelijk ruimte en toont alleen de bediening die u tijdens het invoeren nodig heeft. "
     "Met Uitleg invoerscherm opent u deze uitleg ook vanuit die grote weergave. "
     "Keer terug met Terug naar hoofdscherm; uw gegevens en instellingen blijven behouden. "
     "De voortgangsteller laat zien hoeveel scores ingevuld en nog open zijn.</p>", "direction"),
    ("Meerkeuze en vragen indelen", "<p>Deze extra's zijn <b>optioneel</b>. U hoeft ze niet te gebruiken om een analyse te maken.</p>"
     "<p><b>Meerkeuze instellen:</b> vink een vraag aan en kies de juiste antwoordletter, bijvoorbeeld B. "
     "Daarna typt u per leerling diens gekozen letter. Toetsvizier kent automatisch nul of de maximumscore toe. "
     "Zonder vinkje voert u zelf punten in, ook als de vraag meerkeuze is. N blijft beschikbaar.</p>"
     "<p>Heeft u al punten ingevuld? Wis die eerst voordat u naar antwoordletters wisselt, "
     "zodat punten niet per ongeluk als antwoorden worden geïnterpreteerd.</p>"
     "<p><b>Vragen indelen:</b> vink eerst aan welke verdelingen u wilt meenemen, bijvoorbeeld RTTI, OBIT of Bloom. "
     "Alleen aangevinkte verdelingen verschijnen als kolom en gaan mee in analyse en Excel-export. "
     "Uitvinken bewaart eerder gekozen categorieën; opnieuw aanvinken toont ze weer. "
     "Een fout aangemaakte eigen indeling kunt u met <b>Eigen indeling verwijderen</b> verwijderen. "
     "Na bevestiging wordt dit bij Opslaan uitgevoerd, inclusief categorieën en koppelingen aan verborgen vragen. "
     "Annuleren bewaart de indeling; RTTI, OBIT en Bloom kunt u alleen uitvinken. "
     "Met Eigen indeling toevoegen kiest u zelf een naam en de categorieën. "
     "Hoofdstuk, paragraaf, vraagstuk en leerdoel zijn alleen voorbeelden. "
     "U vindt deze verdelingen terug onder Groepsniveau: dat gaat over de deelnemers van uw toets.</p>", "extras"),
    ("Opslaan, exporteren en verdergaan", "<p><b>Automatisch opslaan:</b> bij het aanmaken kiest u eerst een naam en locatie voor uw <b>.tviz-analysebestand</b>. "
     "De bestandsnaam wordt de titel van uw analyse. Geldige wijzigingen worden vanaf het begin automatisch in dat bestand bewaard. "
     "Met Opslaan kunt u ook zelf de huidige invoer bevestigen. Onderaan staat of alles opgeslagen is. "
     "Invoer met een rode rand wordt niet bewaard: corrigeer die eerst.</p>"
     "<p><b>Opslaan als:</b> maak een andere kopie en werk daarin verder. "
     "<b>Exporteren naar Excel:</b> maak een Excelbestand met de zichtbare tabel en vraaginstellingen. "
     "Om later verder te werken in Toetsvizier opent u het .tviz-bestand via Analyse openen.</p>"
     "<p><b>Normeren en Analyseren</b> worden beschikbaar zodra alle zichtbare maximumscores en scores geldig zijn ingevuld. "
     "N en 0 tellen mee als ingevuld; lege cellen niet.</p>"
     "<p>Een <b>oranje analyseknop</b> betekent: u kunt de scores en vragen al analyseren, maar cijfers en "
     "cijferafhankelijke onderdelen volgen pas na Normering vaststellen. Met Meer informatie ziet u technische details.</p>"
     "<p>U kunt deze handleiding altijd opnieuw openen met <b>Uitleg</b> en rechtstreeks een onderwerp kiezen.</p>", "save"),
]


class DemoOverlay(QWidget):
    def __init__(self, demo):
        super().__init__(demo)
        self.demo = demo
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#d97706"), 3))
        painter.setBrush(QColor(251, 191, 36, 35))
        for rect in self.demo.highlights():
            painter.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 4, 4)
        painter.setBrush(QColor("#047857"))
        painter.setPen(QPen(QColor("#047857"), 3))
        for start, end in self.demo.arrows():
            painter.drawLine(start, end)
            angle = math.atan2(end.y() - start.y(), end.x() - start.x())
            head = [end, QPointF(end.x() - 10 * math.cos(angle - .5), end.y() - 10 * math.sin(angle - .5)),
                    QPointF(end.x() - 10 * math.cos(angle + .5), end.y() - 10 * math.sin(angle + .5))]
            painter.drawPolygon(QPolygonF(head))


class InputDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.focus_area = "counts"
        self.variant = 0
        self.setMinimumHeight(430)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        def button(text, role='secondary'):
            result = set_button_role(QPushButton(text), role)
            result.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            return result

        self.files = QWidget()
        file_row = QHBoxLayout(self.files)
        file_row.setContentsMargins(0, 0, 0, 0)
        file_row.addWidget(QLabel('<b>Simpel · één losse toets</b>'))
        for text, role in (("Opslaan", "primary"), ("Opslaan als", "secondary"),
                           ("Exporteren naar Excel", "secondary"), ("Uitleg", "secondary"),
                           ("Sluiten", "secondary")):
            file_row.addWidget(button(text, role))
        file_row.addStretch()
        layout.addWidget(self.files)

        self.steps = QWidget()
        step_row = QHBoxLayout(self.steps)
        step_row.setContentsMargins(0, 0, 0, 0)
        for text, role in (("1. Gegevens invullen", "primary"), ("2. Normeren", "secondary"),
                           ("3. Analyseren", "secondary")):
            step_row.addWidget(button(text, role), 1)
        layout.addWidget(self.steps)

        self.counts = QWidget()
        count_row = QHBoxLayout(self.counts)
        count_row.setContentsMargins(0, 0, 0, 0)
        for prefix, value in (("Aantal vragen: ", 3), ("Aantal leerlingen: ", 2)):
            counter = QSpinBox()
            counter.setPrefix(prefix)
            counter.setRange(0, 1000)
            counter.setValue(value)
            counter.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            count_row.addWidget(counter)
        count_row.addWidget(QLabel("Lager aantal? Extra gegevens blijven bewaard."))
        count_row.addStretch()
        layout.addWidget(QLabel('<b>Toets instellen</b>'))
        layout.addWidget(self.counts)
        self.extras = QWidget()
        extras_row = QHBoxLayout(self.extras)
        extras_row.setContentsMargins(0, 0, 0, 0)
        self.metadata = button("Vragen indelen")
        self.multiple_choice = button("Meerkeuze instellen")
        extras_row.addWidget(self.metadata)
        extras_row.addWidget(self.multiple_choice)
        extras_row.addStretch()
        layout.addWidget(self.extras)

        self.routes = QWidget()
        route_row = QHBoxLayout(self.routes)
        route_row.setContentsMargins(0, 0, 0, 0)
        route_row.addWidget(QLabel('<b>Invoerroute:</b>'))
        self.route_choice = QComboBox()
        self.route_choice.addItems(["Horizontaal (per leerling)", "Verticaal (per vraag)", "Gecombineerd"])
        self.route_choice.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        route_row.addWidget(self.route_choice)
        precision = QComboBox()
        precision.addItems(["Hele punten", "Halve punten", "Kwartpunten", "Tiende punten"])
        precision.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        route_row.addWidget(precision)
        route_row.addStretch()
        layout.addWidget(self.routes)

        self.progress = QWidget()
        progress_row = QHBoxLayout(self.progress)
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.addWidget(QLabel("2 lln · 3 vragen · 5 van 6 · 1 open"), 1)
        progress_row.addWidget(button("Ongedaan maken"))
        progress_row.addWidget(button("Groot invoerscherm"))
        layout.addWidget(self.progress)

        self.table = QTableWidget(3, 5)
        self.table.setHorizontalHeaderLabels(["Leerlingnaam", "Vraag 1", "Vraag 2", "Vraag 3\nSleutel: B", "Totaal"])
        self.table.horizontalHeader().setMinimumHeight(42)
        self.table.verticalHeader().hide()
        values_by_row = (["Maximaal aantal punten", "3", "2", "1", "6"],
                         ["Sam", "2", "N", "B", "3"],
                         ["Alex", "1", "2", "A", "3"])
        for r, values in enumerate(values_by_row):
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                color = "#dbeafe" if r == 0 or c == 4 else "#fff8ed" if value == "N" else \
                        "#e8f7e8" if value == "B" else "#fdecec" if value == "A" and c == 3 else "#ffffff"
                item.setBackground(QColor(color))
                self.table.setItem(r, c, item)
        self.table.setColumnWidth(0, 185)
        for c in range(1, 5):
            self.table.setColumnWidth(c, 80)
        self.table.setMinimumHeight(150)
        layout.addWidget(self.table, 1)
        self.legend = QLabel("Kleurenlegenda: blauw = actief/maximum/totaal · wit = punten · groen = goed antwoord · "
                             "lichtrood = fout antwoord · lichtoranje = N · rode rand = ongeldige invoer")
        self.legend.setWordWrap(True)
        layout.addWidget(self.legend)
        self.overlay = DemoOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.rect())
        self.overlay.raise_()

    def cell_rect(self, row, column):
        cell = self.table.visualItemRect(self.table.item(row, column))
        corner = self.table.viewport().mapTo(self, cell.topLeft())
        return QRectF(corner.x(), corner.y(), cell.width(), cell.height())

    def widget_rect(self, widget):
        top_left = widget.mapTo(self, QPoint(0, 0))
        return QRectF(top_left.x(), top_left.y(), widget.width(), widget.height())

    def highlights(self):
        area = self.focus_area
        if area == "counts": return [self.widget_rect(self.counts)]
        if area == "names": return [self.cell_rect(0, 1).united(self.cell_rect(0, 3)), self.cell_rect(1, 0).united(self.cell_rect(2, 0))]
        if area == "scores": return [self.cell_rect(1, 1).united(self.cell_rect(2, 3))]
        if area == "paste": return [self.cell_rect(1, 1 if self.variant == 0 else 0)]
        if area == "direction": return [self.widget_rect(self.routes)]
        if area == "extras": return [self.widget_rect(self.metadata), self.widget_rect(self.multiple_choice)]
        return [self.widget_rect(self.files)]

    def arrows(self):
        if self.focus_area != "direction": return []
        cells = ([(1, 1), (1, 3)] if self.variant == 0 else [(1, 1), (2, 1), (2, 2), (1, 2)] if self.variant == 1 else [(1, 1), (1, 2), (2, 1), (2, 2), (2, 3), (1, 3)])
        points = [self.cell_rect(r, c).center() for r, c in cells]
        return list(zip(points, points[1:]))


class InputIntroduction(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Uitleg bij het invoerscherm")
        self.resize(850, 720)
        layout = QVBoxLayout(self)
        self.topic = QComboBox()
        for index, (name, _, _) in enumerate(TOPICS, 1):
            self.topic.addItem(f"{index}. {name}")
        layout.addWidget(QLabel("Kies een onderwerp of gebruik Vorige en Volgende."))
        layout.addWidget(self.topic)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        body = QWidget()
        content = QVBoxLayout(body)
        self.title = QLabel()
        self.title.setWordWrap(True)
        content.addWidget(self.title)
        self.variant = QComboBox()
        self.variant.currentIndexChanged.connect(self.change_variant)
        content.addWidget(self.variant)
        self.demo = InputDemo()
        content.addWidget(self.demo)
        self.caption = QLabel()
        self.caption.setWordWrap(True)
        content.addWidget(self.caption)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content.addWidget(self.text)
        content.addStretch()
        scroll.setWidget(body)
        self.scroll = scroll
        layout.addWidget(scroll, 1)
        self.skip = QCheckBox("Deze uitleg voortaan overslaan bij het starten")
        layout.addWidget(self.skip)
        navigation = QHBoxLayout()
        self.previous = QPushButton("Vorige")
        self.previous.clicked.connect(lambda: self.topic.setCurrentIndex(self.topic.currentIndex() - 1))
        self.next_button = QPushButton("Volgende")
        self.next_button.clicked.connect(self.next_step)
        self.skip_button = QPushButton("Uitleg overslaan")
        self.skip_button.setToolTip("Sla deze uitleg nu over. U kunt haar later opnieuw openen via Uitleg.")
        self.skip_button.clicked.connect(self.accept)
        start = QPushButton("Naar het invoerscherm")
        start.clicked.connect(self.accept)
        for button in (self.previous, self.next_button, self.skip_button, start): navigation.addWidget(button)
        for button in (self.previous, self.skip_button, start):
            set_button_role(button, 'secondary')
        set_button_role(self.next_button, 'primary')
        layout.addLayout(navigation)
        self.topic.currentIndexChanged.connect(self.show_step)
        self.show_step(0)

    def show_step(self, index):
        name, text, area = TOPICS[index]
        self.title.setText(f"<h2>Stap {index + 1} van {len(TOPICS)}: {name}</h2>")
        self.text.setText(text)
        self.variant.blockSignals(True)
        self.variant.clear()
        if area == "paste": self.variant.addItems(["Voorbeeld: alleen scores", "Voorbeeld: namen én scores"])
        if area == "direction": self.variant.addItems(["Horizontaal (per leerling)", "Verticaal (per vraag)", "Gecombineerd, twee vragen per blok"])
        self.variant.setVisible(area in {"paste", "direction"})
        self.variant.blockSignals(False)
        self.demo.focus_area, self.demo.variant = area, 0
        self.demo.route_choice.setCurrentIndex(0)
        self.caption.setText("De oranje cel is de begincel voor uw plakactie." if area == "paste" else
                             "De groene pijlen laten zien waar Enter of Tab u naartoe brengt." if area == "direction" else
                             "Voorbeeldscherm: de oranje omlijning wijst het besproken onderdeel aan.")
        self.demo.overlay.update()
        self.previous.setEnabled(index > 0)
        self.next_button.setText("Klaar voor invoer" if index == len(TOPICS) - 1 else "Volgende")
        self.scroll.verticalScrollBar().setValue(0)

    def change_variant(self, index):
        if hasattr(self, "demo"):
            self.demo.variant = max(index, 0)
            if self.demo.focus_area == "direction":
                self.demo.route_choice.setCurrentIndex(max(index, 0))
            self.demo.overlay.update()

    def next_step(self):
        if self.topic.currentIndex() == len(TOPICS) - 1: self.accept()
        else: self.topic.setCurrentIndex(self.topic.currentIndex() + 1)
