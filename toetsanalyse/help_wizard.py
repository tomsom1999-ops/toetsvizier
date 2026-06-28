from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class HelpWizardDialog(QDialog):
    def __init__(
        self,
        title: str,
        intro: str,
        steps: list[dict[str, object]],
        faq: list[dict[str, object]] | None = None,
        screen_preview: QPixmap | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Hulp bij dit scherm - {title}")
        screen = parent.screen() if parent is not None else QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            maximum_width = max(420, available.width() - 64)
            maximum_height = max(380, available.height() - 64)
            dialog_width = min(980, maximum_width)
            dialog_height = min(720, maximum_height)
            self.setMinimumSize(min(680, dialog_width), min(460, dialog_height))
            self.setMaximumSize(maximum_width, maximum_height)
            self.resize(dialog_width, dialog_height)
            self.move(
                available.x() + (available.width() - dialog_width) // 2,
                available.y() + (available.height() - dialog_height) // 2,
            )
        else:
            dialog_width = 900
            dialog_height = 650
            self.setMinimumSize(680, 460)
            self.resize(dialog_width, dialog_height)
        self.preview_width = min(690, max(270, dialog_width - 325))
        self.preview_height = min(305, max(150, dialog_height - 360))
        self.steps = list(steps)
        overview: dict[str, object] = {
            "title": "Waar ben ik?",
            "text": intro,
            "result": "Na deze hulp weet u wat u eerst moet kiezen, welke knoppen belangrijk zijn en waar u op moet controleren voordat u verdergaat.",
            "action": "Begin links bij stap 1. Klik daarna steeds op Volgende. U hoeft in de wizard niets in te vullen; hij legt alleen uit.",
            "checklist": [
                "Controleer eerst of u in het juiste vak en schooljaar werkt.",
                "Gebruik de stappen links van boven naar beneden als u dit scherm voor het eerst gebruikt.",
                "Gebruik de FAQ-tab als u vastloopt of niet weet waarom iets niet zichtbaar is.",
            ],
            "tip": "U kunt deze hulp altijd sluiten en opnieuw openen. De wizard wijzigt zelf geen gegevens.",
        }
        if screen_preview is not None and not screen_preview.isNull():
            overview["image"] = screen_preview
        self.steps.insert(0, overview)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(16)
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        subtitle = QLabel("Rustige stap-voor-stap uitleg: wat doet dit scherm, wat klikt u aan en wat controleert u daarna?")
        subtitle.setObjectName("helpSubtitle")
        subtitle.setWordWrap(True)
        header = QVBoxLayout()
        header.addWidget(heading)
        header.addWidget(subtitle)
        root.addLayout(header)

        tabs = QTabWidget()
        tabs.setObjectName("helpTabs")
        steps_tab = QWidget()
        steps_layout = QVBoxLayout(steps_tab)
        steps_layout.setContentsMargins(0, 0, 0, 0)
        steps_layout.setSpacing(14)

        body = QHBoxLayout()
        body.setSpacing(18)
        self.step_list = QListWidget()
        self.step_list.setObjectName("helpSteps")
        self.step_list.setMaximumWidth(238 if dialog_width >= 780 else 185)
        self.step_list.setMinimumWidth(210 if dialog_width >= 780 else 160)
        self.step_stack = QStackedWidget()
        self.step_stack.setObjectName("helpStepStack")
        for index, step in enumerate(self.steps, start=1):
            self.step_list.addItem(f"{index}. {step.get('title', '')}")
            self.step_list.item(index - 1).setToolTip(str(step.get("title", "")))
            self.step_stack.addWidget(self._step_widget(index, step))
        self.step_list.currentRowChanged.connect(self.show_step)
        body.addWidget(self.step_list)
        body.addWidget(self.step_stack, 1)
        steps_layout.addLayout(body, 1)

        footer = QHBoxLayout()
        self.progress = QLabel()
        self.progress.setObjectName("helpProgress")
        self.back_button = QPushButton("Vorige")
        self.back_button.setObjectName("helpSecondaryButton")
        self.back_button.clicked.connect(lambda: self.show_step(self.step_stack.currentIndex() - 1))
        self.next_button = QPushButton("Volgende")
        self.next_button.clicked.connect(lambda: self.show_step(self.step_stack.currentIndex() + 1))
        self.close_button = QPushButton("Sluiten")
        self.close_button.setObjectName("helpSecondaryButton")
        self.close_button.clicked.connect(self.accept)
        footer.addWidget(self.progress)
        footer.addStretch()
        footer.addWidget(self.back_button)
        footer.addWidget(self.next_button)
        footer.addWidget(self.close_button)
        steps_layout.addLayout(footer)
        tabs.addTab(steps_tab, "Stappen")
        tabs.addTab(self._faq_widget(faq or []), "FAQ")
        root.addWidget(tabs, 1)
        self.show_step(0)

    def _step_widget(self, index: int, step: dict[str, object]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        content = QVBoxLayout(container)
        content.setContentsMargins(20, 18, 20, 18)
        content.setSpacing(14)

        marker = QLabel(f"STAP {index}")
        marker.setObjectName("helpMarker")
        content.addWidget(marker)
        title = QLabel(str(step.get("title", "")))
        title.setObjectName("helpStepTitle")
        title.setWordWrap(True)
        content.addWidget(title)
        description = QLabel(str(step.get("text", "")))
        description.setObjectName("helpDescription")
        description.setWordWrap(True)
        content.addWidget(description)

        result = str(step.get("result", "")).strip()
        if result:
            content.addWidget(self._information_card("Wat levert dit op?", result, "helpResultCard"))

        image_value = step.get("image")
        pixmap = image_value if isinstance(image_value, QPixmap) else QPixmap(str(image_value)) if image_value else None
        if pixmap is not None and not pixmap.isNull():
            preview_card = QFrame()
            preview_card.setObjectName("helpImageCard")
            preview_layout = QVBoxLayout(preview_card)
            preview = QLabel()
            preview.setObjectName("helpImage")
            preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview.setPixmap(
                pixmap.scaled(
                    self.preview_width,
                    self.preview_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            preview_layout.addWidget(preview)
            content.addWidget(preview_card)

        why = str(step.get("why", "")).strip()
        if why:
            content.addWidget(self._information_card("Waarom is dit belangrijk?", why, "helpWhyCard"))
        action = str(step.get("action", "")).strip()
        if action:
            content.addWidget(self._information_card("Zo doet u dat", action, "helpActionCard"))
        checklist = step.get("checklist", [])
        if isinstance(checklist, str):
            checklist = [checklist]
        if checklist:
            content.addWidget(self._list_card("Controleer dit", checklist, "helpChecklistCard"))
        warning = step.get("warning", [])
        if isinstance(warning, str):
            warning = [warning]
        if warning:
            content.addWidget(self._list_card("Let op", warning, "helpWarningCard"))
        tip = str(step.get("tip", "")).strip()
        if tip:
            content.addWidget(self._information_card("Goed om te weten", tip, "helpTipCard"))
        next_step = str(step.get("next", "")).strip()
        if next_step:
            content.addWidget(self._information_card("Daarna", next_step, "helpNextCard"))
        content.addStretch()
        scroll.setWidget(container)
        return scroll

    def _information_card(self, heading: str, text: str, object_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        layout = QVBoxLayout(card)
        title = QLabel(heading)
        title.setObjectName("helpCardTitle")
        detail = QLabel(text)
        detail.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(detail)
        return card

    def _list_card(self, heading: str, values: object, object_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        layout = QVBoxLayout(card)
        layout.setSpacing(6)
        title = QLabel(heading)
        title.setObjectName("helpCardTitle")
        layout.addWidget(title)
        for value in values:
            line = QLabel(f"- {value}")
            line.setWordWrap(True)
            layout.addWidget(line)
        return card

    def _faq_widget(self, faq: list[dict[str, object]]) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        intro = QLabel(
            "Korte antwoorden op vragen die gebruikers vaak hebben. "
            "Gebruik dit tabblad als u even niet weet waarom iets niet zichtbaar is of welke keuze veilig is."
        )
        intro.setWordWrap(True)
        intro.setObjectName("helpDescription")
        layout.addWidget(intro)
        for item in faq:
            question = str(item.get("question") or item.get("title") or "").strip()
            answer = str(item.get("answer") or item.get("text") or "").strip()
            if question and answer:
                layout.addWidget(self._information_card(question, answer, "helpFaqCard"))
        if not faq:
            layout.addWidget(
                self._information_card(
                    "Ik zie geen veelgestelde vragen. Wat nu?",
                    "Doorloop de stappen op het eerste tabblad. Die volgen de normale werkwijze op dit scherm.",
                    "helpFaqCard",
                )
            )
        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def show_step(self, index: int) -> None:
        if not self.steps:
            return
        index = min(max(index, 0), len(self.steps) - 1)
        self.step_stack.setCurrentIndex(index)
        self.step_list.blockSignals(True)
        self.step_list.setCurrentRow(index)
        self.step_list.blockSignals(False)
        self.progress.setText(f"Stap {index + 1} van {len(self.steps)}")
        self.back_button.setEnabled(index > 0)
        self.next_button.setVisible(index < len(self.steps) - 1)



HELP_STEP_EXTRAS: dict[str, dict[str, dict[str, object]]] = {
    "Startscherm": {
        "Nieuw vak aanmaken": {
            "why": "Een vakbestand is de basis van alles wat u later analyseert. Per vak blijft de database overzichtelijk en portable.",
            "checklist": [
                "Gebruik een herkenbare vaknaam.",
                "Controleer het eerste schooljaar.",
                "Bewaar het bestand op een plek waar u het terugvindt.",
            ],
            "next": "Open het vak en begin met groepen en leerlingen.",
        },
        "Een bestaand vak openen": {
            "checklist": [
                "Controleer of de vaknaam klopt.",
                "Controleer bovenin het geopende vak het actieve schooljaar.",
            ],
            "warning": "Open geen oude back-up als u eigenlijk in het actuele bestand wilt verderwerken.",
        },
        "Een back-up terugzetten": {
            "warning": [
                "Zet een back-up bij voorkeur terug onder een nieuwe bestandsnaam.",
                "Controleer daarna eerst of de juiste gegevens aanwezig zijn.",
            ],
        },
    },
    "Dashboard": {
        "Het juiste schooljaar controleren": {
            "checklist": [
                "Schooljaar bovenin klopt.",
                "Aantal groepen en leerlingen past bij uw verwachting.",
                "U werkt in de juiste vakdatabase.",
            ],
        },
        "Een logische werkvolgorde": {
            "result": "Als u deze volgorde aanhoudt, ontstaan analyses later vanzelf uit de ingevoerde toets, vragen en scores.",
            "checklist": [
                "Eerst groepen en leerlingen.",
                "Daarna toetsen en vragen.",
                "Daarna resultaten, normering en analyse.",
            ],
        },
        "Veilig bewaren": {
            "warning": "Maak vooral een back-up voordat u veel importeert, verwijdert of oude gegevens herstelt.",
        },
    },
    "Klassen en Groepen": {
        "Wat is een groep?": {
            "why": "De groep bepaalt welke leerlingen bij een toets beschikbaar zijn en waarop u later kunt filteren.",
            "checklist": [
                "Naam is herkenbaar voor u.",
                "Niveau is ingevuld als u daarop wilt filteren.",
                "Leerjaar is ingevuld als u daarop wilt filteren.",
            ],
        },
        "Een groep verwijderen": {
            "warning": [
                "Verwijderen kan alleen zonder gekoppelde leerlingen of toetsen.",
                "Controleer of u niet per ongeluk een cluster verwijdert dat nog nodig is voor analyses.",
            ],
        },
    },
    "Leerlingen": {
        "Handmatig een leerling toevoegen": {
            "why": "Een betrouwbare leerlingidentiteit voorkomt dubbele leerlingen en maakt analyse over schooljaren mogelijk.",
            "checklist": [
                "Weergavenaam is ingevuld.",
                "Leerlingnummer is ingevuld als u dat heeft.",
                "De juiste groep voor dit schooljaar is gekozen.",
            ],
        },
        "Leerlingen importeren uit Magister": {
            "checklist": [
                "Het importbestand bevat Stamnummer, Roepnaam, Tussenvoegsel en Achternaam.",
                "De juiste cluster/groep is gekozen.",
                "De controle na import toont geen onverwachte leerlingen.",
            ],
            "warning": "De administratieve klas uit Magister hoeft niet dezelfde groep te zijn als uw cluster. Kies daarom bewust de groep in de importwizard.",
        },
        "Bewerken, verwijderen en eigen velden": {
            "checklist": [
                "Selecteer eerst de juiste leerling.",
                "Gebruik extra eigenschappen alleen voor gegevens die u later echt wilt terugzien.",
                "Bij verwijderen leest u de bevestiging goed door.",
            ],
            "warning": "Een eigenschap verwijderen wist ook de ingevulde waarden van die eigenschap.",
        },
    },
    "Toetsen": {
        "Een toets aanmaken": {
            "checklist": [
                "Naam, periode en toetssoort zijn duidelijk.",
                "Niveau en jaarlaag zijn ingevuld als u later wilt filteren.",
                "Weging is ingevuld voor later gebruik.",
            ],
        },
        "Groepen koppelen": {
            "why": "Alleen leerlingen uit gekoppelde groepen verschijnen later bij resultateninvoer.",
            "checklist": [
                "Alle betrokken clusters/groepen zijn aangevinkt.",
                "Een toets voor meerdere groepen hoeft maar een keer te worden aangemaakt.",
            ],
        },
        "Taxonomieën en extra velden kiezen": {
            "checklist": [
                "Minimaal een taxonomie gekozen.",
                "Per gekozen taxonomie vult u later bij elke vraag een waarde in.",
                "Vraagtypen alleen aanvinken als u die bij deze toets wilt gebruiken.",
            ],
        },
        "Herkansing en weging": {
            "warning": "Het veld 'Herkansing van' is alleen relevant bij toetssoort herkansing.",
            "next": "Maak daarna voor de herkansing een eigen vragenoverzicht en voer eigen resultaten in.",
        },
    },
    "Vragenoverzicht": {
        "De juiste toets openen": {
            "checklist": [
                "Toetsnaam klopt.",
                "Aantal vragen en totaalpunten onder de knoppen passen bij uw verwachting.",
                "U ziet de juiste niveau- en jaarlaagfilter.",
            ],
        },
        "Een vraag invoeren": {
            "checklist": [
                "Vraagnummer klopt; bij een nieuwe vraag wordt het hoofdnummer automatisch voorgesteld.",
                "Laat 'Deze vraag heeft subvragen' uit voor een losse vraag.",
                "Vink 'Deze vraag heeft subvragen' aan als de hoofdvraag alleen uit a, b, c enzovoort bestaat.",
                "Maximumscore is per vraag of subvraag ingevuld.",
                "Elke verplichte taxonomie heeft een waarde.",
            ],
            "warning": "Een fout maximumaantal punten werkt later door in resultateninvoer, normering en analyse.",
        },
        "Classificaties gebruiken": {
            "why": "Classificaties maken de verdelingen en groepsanalyse betekenisvol: bijvoorbeeld per hoofdstuk, domein of vraagtype.",
            "checklist": [
                "Vul classificaties consequent in.",
                "Laat een waarde alleen leeg als die echt niet van toepassing is.",
            ],
        },
        "Een meerkeuzevraag instellen": {
            "checklist": [
                "Meerkeuze is aangevinkt.",
                "De antwoordsleutel bevat de juiste optie(s).",
                "Bij resultateninvoer voert u de leerlingrespons in, niet de punten.",
            ],
        },
    },
    "Taxonomieën": {
        "Standaardtaxonomieën begrijpen": {
            "result": "RTTI, OBIT en Bloom kunt u direct gebruiken bij toetsen zonder extra inrichting.",
            "checklist": [
                "Kies de taxonomie die past bij uw sectieafspraken.",
                "Gebruik niet onnodig meerdere taxonomieën tegelijk.",
            ],
        },
        "Een eigen taxonomie toevoegen": {
            "checklist": [
                "Naam is kort en duidelijk.",
                "Waarden zijn gescheiden met komma's.",
                "Waarden zijn bruikbaar bij elke vraag waarvoor u deze taxonomie kiest.",
            ],
        },
        "Taxonomie in een toets gebruiken": {
            "warning": "Een eigen taxonomie die al aan een toets is gekoppeld kan niet zomaar verwijderd worden.",
        },
    },
    "Vraagclassificaties": {
        "Waarom classificaties gebruiken?": {
            "result": "Elke ingevulde classificatie kan later een eigen grafiek, tabel of filter opleveren.",
            "checklist": [
                "Gebruik classificaties voor onderdelen waarop u echt wilt analyseren.",
                "Houd namen kort, bijvoorbeeld Hoofdstuk, Domein of Vraagtype.",
            ],
        },
        "Een classificatie aanmaken": {
            "checklist": [
                "Keuzelijst voor vaste opties.",
                "Vrije tekst alleen als waarden niet vooraf vastliggen.",
                "Vraagtype gebruikt u voor opties zoals Bereken, Leg uit of Teken.",
            ],
        },
        "Opties later aanpassen": {
            "warning": [
                "Bewerk opties voorzichtig als ze al in bestaande vragen gebruikt zijn.",
                "Verwijderen van opties kan bestaande vraaggegevens raken.",
            ],
        },
    },
    "Resultateninvoer": {
        "Een toets en leerlingen tonen": {
            "checklist": [
                "Niveau en jaarlaag beperken de toetslijst.",
                "Toets is bewust geselecteerd.",
                "Groepfilter toont de juiste leerlingen.",
            ],
        },
        "Scores handmatig invoeren": {
            "why": "Nauwkeurige score-invoer is de basis voor normering, cijferberekening en alle analyses.",
            "checklist": [
                "Kies horizontaal per leerling of verticaal per vraag.",
                "Controleer maximumscore in de kolomkop.",
                "Een groene totaalscore betekent dat de rij compleet is.",
            ],
        },
        "Groot invoerscherm": {
            "why": "Bij kleine schermen of toetsen met veel vragen is de gewone pagina soms te krap.",
            "checklist": [
                "Kies eerst een toets.",
                "Klik boven de scoretabel op Groot invoerscherm.",
                "Voer scores in zoals normaal; het is dezelfde tabel en dezelfde opslag.",
                "Sluit het venster met Vergroot venster sluiten om terug te keren.",
            ],
        },
        "Status van een leerling": {
            "checklist": [
                "Iedereen staat standaard op gemaakt.",
                "Niet-gemaakte statussen vergrendelen de rij.",
                "Vergrendelde rijen tellen niet mee als open invoer.",
                "Niet analyseren blijft bewaard, maar telt niet mee in analyses.",
            ],
        },
        "Scores importeren uit Excel": {
            "checklist": [
                "Controleer leerlingmatches, vooral fuzzy matches.",
                "Controleer of vraagkolommen aan de juiste vragen gekoppeld zijn.",
                "Importeer pas definitief na de controle.",
            ],
            "warning": "Een leerling zonder match wordt niet automatisch gekoppeld. Los dat op voordat u definitief importeert.",
        },
        "Meerkeuze invoeren en corrigeren": {
            "checklist": [
                "Voer bij meerkeuze de antwoordletter van de leerling in.",
                "Beheer correcties via de antwoordsleutelknop.",
                "Bij aanpassen wordt opnieuw nagekeken.",
            ],
        },
    },
    "Normering": {
        "Eerst de toets selecteren": {
            "checklist": [
                "Resultaten zijn volledig genoeg ingevoerd.",
                "Niet-gemaakte leerlingen hebben een passende status.",
                "De juiste toets staat bovenaan geselecteerd.",
            ],
        },
        "Een normeringsmethode kiezen": {
            "why": "De methode bepaalt hoe ruwe scorepunten worden vertaald naar cijfers.",
            "checklist": [
                "Controleer de voldoendegrens.",
                "Bekijk het percentage onvoldoende.",
                "Vergelijk de curve met de lineaire referentie.",
            ],
        },
        "Normering vaststellen of opheffen": {
            "result": "Na vaststellen worden cijfergerelateerde grafieken, statistieken en rapportonderdelen definitief zichtbaar.",
            "warning": "Opheffen verwijdert de opgeslagen normeringswaarden en de definitieve cijfers.",
        },
    },
    "Toetsanalyse": {
        "De juiste toets openen": {
            "checklist": [
                "Resultaten zijn ingevoerd.",
                "Normering is vastgesteld als u cijfers wilt zien.",
                "De analyse gaat over een toets tegelijk.",
            ],
        },
        "Algemeen: kwaliteit van de toets": {
            "checklist": [
                "Bekijk P-waarde voor moeilijkheid.",
                "Bekijk Rit en Rir voor onderscheidend vermogen.",
                "Gebruik SEM en betrouwbaarheid als nuance, niet als los oordeel.",
            ],
        },
        "Groepsniveau: patronen in de klas": {
            "result": "U ziet per ingevulde classificatie waar de groep relatief sterk of zwak op scoort.",
            "checklist": [
                "Controleer sterkste en zwakste onderdelen.",
                "Gebruik de heatmap om patronen tussen leerlingen te zien.",
            ],
        },
        "Leerlingniveau: bespreken met een leerling": {
            "checklist": [
                "Kies de juiste leerling.",
                "Vergelijk leerlingpercentages met groepsniveau.",
                "Gebruik het vragenoverzicht voor concrete feedback.",
            ],
        },
        "Een leerlingrapport exporteren": {
            "checklist": [
                "Kies alleen onderdelen die u met leerlingen wilt delen.",
                "Voeg persoonlijke feedback toe bij een individueel rapport als dat nodig is.",
                "Controleer een voorbeeld voordat u een batch deelt.",
            ],
        },
    },
}


GENERAL_HELP_FAQ: list[dict[str, str]] = [
    {
        "question": "Kan ik iets kapotmaken door de help te openen?",
        "answer": "Nee. De helpwizard verandert niets aan uw gegevens. U kunt hem veilig openen, sluiten en opnieuw openen.",
    },
    {
        "question": "Waarom zie ik soms geen gegevens?",
        "answer": "Meestal staat er nog een filter aan, is er geen toets gekozen of werkt u in een ander schooljaar. Controleer bovenaan eerst schooljaar, niveau, jaarlaag, groep en toets.",
    },
    {
        "question": "Wat betekenen de blauwe en witte knoppen?",
        "answer": "Blauwe knoppen starten meestal een hoofdactie, zoals toevoegen, openen of importeren. Witte knoppen zijn meestal bewerken, exporteren of een extra scherm openen. Rode tekst of rode knoppen betekenen: eerst goed controleren.",
    },
    {
        "question": "Moet ik ergens apart opslaan?",
        "answer": "Bij invoervensters gebruikt u Opslaan of OK. Veel tabellen slaan wijzigingen direct op zodra u een waarde invoert. Twijfelt u, controleer dan of de samenvatting of tabel de wijziging meteen laat zien.",
    },
    {
        "question": "Wat doe ik als het scherm te klein is?",
        "answer": "Maak het venster groter of gebruik de scrollbalk. Bij resultateninvoer is er ook een groot invoerscherm, bedoeld voor kleine schermen en toetsen met veel vragen.",
    },
    {
        "question": "Wanneer gebruik ik verwijderen?",
        "answer": "Alleen als u zeker weet dat het onderdeel echt weg mag. Lees de bevestigingsmelding rustig. Als iets al gebruikt is in toetsen, resultaten of analyses, kan verwijderen bewust geblokkeerd worden.",
    },
]


HELP_FAQ_EXTRAS: dict[str, list[dict[str, str]]] = {
    "Startscherm": [
        {
            "question": "Moet ik steeds een nieuw vak maken?",
            "answer": "Nee. Een vak maakt u meestal eenmalig aan. Daarna opent u hetzelfde vakbestand opnieuw met Bestaand vak openen of Laatste vak openen.",
        },
        {
            "question": "Wat is een vakdatabase?",
            "answer": "Dat is het lokale bestand waarin alles van één vak staat: schooljaren, groepen, leerlingen, toetsen, resultaten en analyses.",
        },
    ],
    "Dashboard": [
        {
            "question": "Waar begin ik in een nieuw vak?",
            "answer": "Begin met Klassen & Leerlingen. Daarna maakt u toetsen aan, vult u het vragenoverzicht, voert u resultaten in en stelt u de normering vast.",
        },
        {
            "question": "Waarom klopt een aantal op het dashboard niet?",
            "answer": "Controleer eerst het geselecteerde schooljaar bovenaan. Het dashboard toont gegevens voor dat schooljaar.",
        },
    ],
    "Klassen & Leerlingen": [
        {
            "question": "Wat is het verschil tussen klas en groep?",
            "answer": "Een groep mag ook een cluster zijn. Gebruik de indeling waarin u toetsen afneemt, niet per se de administratieve klas uit Magister.",
        },
        {
            "question": "Moet ik eerst klassen of leerlingen doen?",
            "answer": "Maak eerst de groepen of clusters aan. Daarna kunt u leerlingen handmatig toevoegen of importeren en meteen aan de juiste groep koppelen.",
        },
    ],
    "Klassen en Groepen": [
        {
            "question": "Mag een groep een cluster zijn?",
            "answer": "Ja. Gebruik groepen zoals u ze in de praktijk nodig heeft, bijvoorbeeld h4.na1 of een toetscluster.",
        },
    ],
    "Leerlingen": [
        {
            "question": "Hoe herkent het programma dezelfde leerling in een nieuw schooljaar?",
            "answer": "Vooral via leerlingnummer. Daarom is het verstandig om Stamnummer of leerlingnummer mee te importeren.",
        },
        {
            "question": "Waarom moet ik na import controleren?",
            "answer": "Zo voorkomt u dubbele leerlingen, verkeerd gekoppelde groepen en namen die net anders gespeld zijn.",
        },
    ],
    "Toetsen": [
        {
            "question": "Waarom moet ik groepen koppelen aan een toets?",
            "answer": "Alleen leerlingen uit gekoppelde groepen verschijnen later bij resultateninvoer.",
        },
        {
            "question": "Wanneer kies ik herkansing?",
            "answer": "Alleen als deze toets een herkansing is van een eerdere toets. Dan verschijnt het veld waarin u de originele toets koppelt.",
        },
    ],
    "Vragenoverzicht": [
        {
            "question": "Wat is het verschil tussen een losse vraag en subvragen?",
            "answer": "Een losse vraag krijgt één score. Bij subvragen is de hoofdvraag alleen een container en krijgen a, b, c enzovoort elk eigen punten en metadata.",
        },
        {
            "question": "Waarom moet taxonomie verplicht ingevuld worden?",
            "answer": "Omdat de analyse anders niet betrouwbaar kan laten zien hoe leerlingen scoren op bijvoorbeeld R, T1, T2 en I.",
        },
        {
            "question": "Waar stel ik meerkeuze-antwoorden in?",
            "answer": "Bij de vraag zelf vult u de normale antwoordsleutel in. Correcties, neutraliseren en extra goed te rekenen opties doet u later bij resultateninvoer.",
        },
    ],
    "Resultateninvoer": [
        {
            "question": "Wat is horizontaal en verticaal invoeren?",
            "answer": "Horizontaal betekent: u vult per leerling alle vragen na elkaar in. Verticaal betekent: u vult per vraag alle leerlingen onder elkaar in.",
        },
        {
            "question": "Waarom kan ik in een rij niets invoeren?",
            "answer": "Dan staat de leerling waarschijnlijk op een niet-gemaakte status. Zet de status op gemaakt als de leerling de toets wel gemaakt heeft.",
        },
        {
            "question": "Wat doet de status niet analyseren?",
            "answer": "Die status houdt de leerling uit alle analyses. Scores kunnen bewaard blijven, maar worden niet meegeteld in gemiddelden, grafieken en rapportages.",
        },
        {
            "question": "Waarom springt de invoer automatisch door?",
            "answer": "Als halve punten uit staan en alle vragen maximaal 9 punten hebben, gaat het programma na één cijfer direct naar de volgende cel.",
        },
        {
            "question": "Wanneer gebruik ik N in een scorecel?",
            "answer": "Gebruik N als een leerling een losse vraag niet heeft gemaakt. De vraag telt dan als ingevoerd met 0 punten. Bij meerkeuze wordt N apart bijgehouden en niet als antwoordalternatief gezien.",
        },
        {
            "question": "Wat doe ik met een fuzzy match bij import?",
            "answer": "Controleer of de voorgestelde leerling echt dezelfde persoon is. Bevestig alleen als u zeker bent.",
        },
    ],
    "Normering": [
        {
            "question": "Waarom zie ik nog geen cijfergrafieken?",
            "answer": "Cijfergrafieken verschijnen pas nadat een normering is vastgesteld. Eerst zijn alleen scores betrouwbaar bekend.",
        },
        {
            "question": "Wat betekent normering vaststellen?",
            "answer": "U slaat de gekozen omzetting van score naar cijfer vast. Daarna gebruikt de analyse die normering consequent.",
        },
    ],
    "Toetsanalyse": [
        {
            "question": "Moet ik alle statistieken begrijpen?",
            "answer": "Nee. Gebruik de kleur en de korte uitleg als eerste richting. P-waarde gaat over moeilijkheid; Rit en Rir over onderscheidend vermogen; alpha en SEM over betrouwbaarheid.",
        },
        {
            "question": "Waarom zijn cijferonderdelen soms niet zichtbaar?",
            "answer": "Omdat er dan nog geen normering is vastgesteld. Scores zijn er al, maar cijfers nog niet definitief.",
        },
    ],
    "Ontwikkelanalyse": [
        {
            "question": "Waarom moet ik eerst niveau en jaarlaag kiezen?",
            "answer": "Anders vergelijkt u te brede groepen met elkaar. Door eerst niveau en jaarlaag te kiezen wordt de ontwikkeling eerlijker en overzichtelijker.",
        },
        {
            "question": "Wat betekent positie in de groep?",
            "answer": "Dat laat in gewone taal zien hoe een leerling het doet vergeleken met klasgenoten, bijvoorbeeld 'beter dan 70% van de groep'.",
        },
    ],
    "Taxonomieën en vraagclassificaties": [
        {
            "question": "Wat is het verschil tussen taxonomie en classificatie?",
            "answer": "Een taxonomie is een denk- of vaardigheidsniveau, zoals RTTI. Een classificatie is extra indeling, zoals hoofdstuk, domein of vraagtype.",
        },
    ],
    "Taxonomieën": [
        {
            "question": "Waarom zijn RTTI, OBIT en Bloom vergrendeld?",
            "answer": "Dit zijn vaste standaardtaxonomieën. U kunt ze gebruiken, maar niet verwijderen, zodat bestaande analyses stabiel blijven.",
        },
    ],
    "Vraagclassificaties": [
        {
            "question": "Wanneer maak ik een classificatie aan?",
            "answer": "Als u later wilt analyseren op dat onderdeel. Voorbeelden zijn hoofdstuk, domein, leerdoel, vraagtype of examenprogramma.",
        },
    ],
    "Vraagdatabase": [
        {
            "question": "Moet elke toetsvraag uit de vraagdatabase komen?",
            "answer": "Nee. De vraagdatabase is optioneel. U gebruikt hem alleen voor vragen die u vaker wilt hergebruiken of over jaren wilt volgen.",
        },
        {
            "question": "Waarom kan metadata niet automatisch meekomen in een toets?",
            "answer": "Omdat een vraag in de database metadata voor meerdere contexten kan hebben. Bij toevoegen kiest u bewust welke metadata voor deze toets relevant is.",
        },
        {
            "question": "Wanneer ontstaat een nieuwe versie?",
            "answer": "Alleen bij een betekenisvolle wijziging in vraagtekst of punten. Kleine beheerwijzigingen hoeven geen nieuwe versie te maken.",
        },
    ],
    "Geavanceerde instellingen": [
        {
            "question": "Waarom staan sommige menu's verborgen?",
            "answer": "Geavanceerde modules worden pas zichtbaar als u ze aanzet. Zo blijft de app voor dagelijks gebruik rustiger.",
        },
        {
            "question": "Wat doet 'Toets opsplitsen voor analyse meenemen'?",
            "answer": "Als u deze optie aanzet, verschijnt bij toetsen een extra functie om een toets op te knippen in deeltoetsen. Die deeltoetsen kunt u daarna apart analyseren, terwijl de totaaltoets gewoon beschikbaar blijft.",
        },
    ],
}



def _merge_help_value(existing: object, extra: object) -> object:
    if existing is None or existing == "":
        return extra
    if isinstance(existing, list) or isinstance(extra, list):
        existing_values = existing if isinstance(existing, list) else [existing]
        extra_values = extra if isinstance(extra, list) else [extra]
        return [*existing_values, *extra_values]
    return existing



def _enrich_help_steps(title: str, steps: list[dict[str, object]]) -> list[dict[str, object]]:
    page_extras = HELP_STEP_EXTRAS.get(title, {})
    enriched_steps: list[dict[str, object]] = []
    for step in steps:
        enriched = dict(step)
        extras = page_extras.get(str(step.get("title", "")), {})
        for key, value in extras.items():
            enriched[key] = _merge_help_value(enriched.get(key), value)
        enriched_steps.append(enriched)
    return enriched_steps


def _as_faq_item(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    question = str(value.get("question") or value.get("title") or "").strip()
    answer = str(value.get("answer") or value.get("text") or "").strip()
    if not question or not answer:
        return None
    return {"question": question, "answer": answer}


def _build_help_faq(
    title: str,
    steps: list[dict[str, object]],
    custom_faq: list[dict[str, object]] | None = None,
) -> list[dict[str, str]]:
    faq: list[dict[str, str]] = []
    step_titles = [str(step.get("title", "")).strip() for step in steps if str(step.get("title", "")).strip()]
    if step_titles:
        faq.append(
            {
                "question": "Wat is hier de normale volgorde?",
                "answer": "Werk rustig van boven naar beneden: " + " -> ".join(step_titles[:7]) + ".",
            }
        )
    checklist_items: list[str] = []
    for step in steps:
        values = step.get("checklist", [])
        if isinstance(values, str):
            values = [values]
        if isinstance(values, list):
            checklist_items.extend(str(value) for value in values if str(value).strip())
    if checklist_items:
        faq.append(
            {
                "question": "Wat moet ik controleren voordat ik verderga?",
                "answer": "Controleer vooral: " + "; ".join(checklist_items[:5]) + ".",
            }
        )
    for item in HELP_FAQ_EXTRAS.get(title, []):
        faq.append(dict(item))
    for item in custom_faq or []:
        normalised = _as_faq_item(item)
        if normalised:
            faq.append(normalised)
    faq.extend(dict(item) for item in GENERAL_HELP_FAQ)
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in faq:
        key = item["question"].casefold()
        if key not in seen:
            unique.append(item)
            seen.add(key)
    return unique

