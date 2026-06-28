from __future__ import annotations

import json
import sqlite3
from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None

from .database import SubjectDatabase
from .pages_base import Page
from .paths import PDF_EXPORT_DIR
from .pdf_export import PdfExportError, browser_report_html, export_html_to_pdf
from .question_bank import (
    load_active_question_properties,
    load_all_taxonomies,
    question_database_enabled,
    question_database_latest_rows,
)
from .question_dialogs import (
    LinkedDatabaseQuestionDialog,
    QuestionDatabaseImportDialog,
    QuestionDatabaseSelectionDialog,
    QuestionDialog,
)
from .report_documents import formatted_report_document
from .reports import build_matrix_report_html
from .results import normalize_multiple_choice_response, regrade_multiple_choice_question, score_limit_conflicts
from .ui_helpers import (
    compact_action_button,
    configure_table,
    item,
    make_empty_state,
    make_page_header,
    make_responsive_filter_card,
    set_button_role,
    slug,
)


def analysis_parts_enabled(database: SubjectDatabase) -> bool:
    return database.meta("analysis_parts_enabled", "0") == "1"


class AnalysisSplitDialog(QDialog):
    def __init__(
        self,
        questions: list[dict],
        parts: list[dict],
        assignments: dict[int, int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Toets opsplitsen voor analyse")
        self.questions = questions
        self.assignments = assignments
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Geef de deeltoetsen een duidelijke naam en wijs daarna elke vraag of subvraag toe. "
            "De originele toets en resultaten blijven ongewijzigd; dit is alleen een analyse-indeling."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Aantal deeltoetsen"))
        self.count = QSpinBox()
        self.count.setRange(2, 12)
        self.count.setValue(max(2, len(parts) or 2))
        count_row.addWidget(self.count)
        count_row.addStretch()
        layout.addLayout(count_row)

        self.names_container = QWidget()
        self.names_layout = QVBoxLayout(self.names_container)
        self.names_layout.setContentsMargins(0, 0, 0, 0)
        self.names_layout.setSpacing(6)
        layout.addWidget(self.names_container)

        self.question_cards = QWidget()
        self.question_cards_layout = QVBoxLayout(self.question_cards)
        self.question_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.question_cards_layout.setSpacing(10)
        self.question_scroll = QScrollArea()
        self.question_scroll.setWidgetResizable(True)
        self.question_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.question_scroll.setWidget(self.question_cards)
        layout.addWidget(self.question_scroll, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name_fields: list[QLineEdit] = []
        self.combos: dict[int, QComboBox] = {}
        self.existing_names = {
            int(part["sort_order"]): str(part["name"])
            for part in parts
        }
        self.count.valueChanged.connect(self.rebuild_names)
        self.rebuild_names()
        self.populate_questions()
        self.resize(900, 620)

    def rebuild_names(self) -> None:
        current_names = self.names()
        while self.names_layout.count():
            child = self.names_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.name_fields = []
        for order in range(self.count.value()):
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Naam deeltoets {order + 1}"))
            field = QLineEdit()
            field.setPlaceholderText(f"Deeltoets {order + 1}")
            field.setText(
                current_names[order]
                if order < len(current_names)
                else self.existing_names.get(order, f"Deeltoets {order + 1}")
            )
            field.textChanged.connect(self.refresh_combo_labels)
            row.addWidget(field, 1)
            wrapper = QWidget()
            wrapper.setLayout(row)
            self.names_layout.addWidget(wrapper)
            self.name_fields.append(field)
        self.refresh_combo_labels()

    def names(self) -> list[str]:
        names: list[str] = []
        for index, field in enumerate(getattr(self, "name_fields", [])):
            names.append(field.text().strip() or f"Deeltoets {index + 1}")
        return names

    def populate_questions(self) -> None:
        while self.question_cards_layout.count():
            child = self.question_cards_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.combos = {}
        names = self.names()
        for question in self.questions:
            question_id = int(question["id"])
            label = f"{question['question_number']}{question['subquestion'] or ''}"
            card = QFrame()
            card.setObjectName("questionInputCard")
            card.setStyleSheet(
                """
                QFrame#questionInputCard {
                    background:#ffffff;
                    border:1px solid #dce4ef;
                    border-radius:14px;
                }
                """
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 12, 12, 12)
            card_layout.setSpacing(8)
            title = QLabel(f"Vraag {label}")
            title.setStyleSheet("font-weight:700; font-size:14px; color:#17243c;")
            card_layout.addWidget(title)
            meta = QLabel(
                f"Max. {question['maximum_score']:g} punten"
                + (f"  |  {question['short_description']}" if question["short_description"] else "")
            )
            meta.setWordWrap(True)
            meta.setStyleSheet("color:#66748e;")
            card_layout.addWidget(meta)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(10)
            row.addWidget(QLabel("Deeltoets"))
            combo = QComboBox()
            combo.setMinimumWidth(220)
            for order, name in enumerate(names):
                combo.addItem(name, order)
            combo.setCurrentIndex(max(0, min(len(names) - 1, self.assignments.get(question_id, 0))))
            row.addWidget(combo, 1)
            card_layout.addLayout(row)
            self.question_cards_layout.addWidget(card)
            self.combos[question_id] = combo
        self.question_cards_layout.addStretch(1)

    def refresh_combo_labels(self) -> None:
        names = self.names()
        for combo in getattr(self, "combos", {}).values():
            selected = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            for order, name in enumerate(names):
                combo.addItem(name, order)
            index = combo.findData(selected)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def payload(self) -> tuple[list[str], dict[int, int]]:
        assignments: dict[int, int] = {}
        for question_id, combo in self.combos.items():
            assignments[question_id] = int(combo.currentData()) if isinstance(combo, QComboBox) else 0
        return self.names(), assignments


class MatrixPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 24)
        content_layout.setSpacing(12)
        self.level_filter = QComboBox()
        self.level_filter.setMinimumWidth(150)
        self.level_filter.setMaximumWidth(220)
        self.level_filter.currentIndexChanged.connect(self.refresh)
        self.grade_filter = QComboBox()
        self.grade_filter.setMinimumWidth(150)
        self.grade_filter.setMaximumWidth(220)
        self.grade_filter.currentIndexChanged.connect(self.refresh)
        self.test = QComboBox()
        self.test.setMinimumWidth(260)
        self.test.setMaximumWidth(500)
        self.test.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.test.currentIndexChanged.connect(self.refresh_questions)
        add = compact_action_button(set_button_role(QPushButton("Vraag toevoegen"), "primary"), "Voeg een losse vraag of vraag met subvragen toe.", 135)
        add.clicked.connect(self.add_question)
        edit = compact_action_button(set_button_role(QPushButton("Vraag bewerken"), "secondary"), "Bewerk de geselecteerde vraag of vraaggroep.", 135)
        edit.clicked.connect(self.edit_question)
        delete = compact_action_button(set_button_role(QPushButton("Vraag verwijderen"), "danger"), "Verwijder de geselecteerde vraag of vraaggroep.", 140)
        delete.clicked.connect(self.delete_question)
        add_from_database = compact_action_button(
            set_button_role(QPushButton("Uit vraagdatabase"), "secondary"),
            "Voeg een vraag uit de vraagdatabase toe aan deze toets.",
            150,
        )
        add_from_database.clicked.connect(self.add_question_from_database)
        add_to_database = compact_action_button(
            set_button_role(QPushButton("Naar vraagdatabase"), "secondary"),
            "Sla de geselecteerde toetsvraag op in de vraagdatabase.",
            150,
        )
        add_to_database.clicked.connect(self.add_selected_question_to_database)
        self.question_database_buttons = [add_from_database, add_to_database]
        split_analysis = compact_action_button(
            set_button_role(QPushButton("Opsplitsen voor analyse"), "secondary"),
            "Deel deze toets voor analyse op in herkenbare deeltoetsen.",
            170,
        )
        split_analysis.clicked.connect(self.open_analysis_split_dialog)
        self.analysis_split_button = split_analysis
        split_remove = compact_action_button(
            set_button_role(QPushButton("Opknipping verwijderen"), "danger"),
            "Verwijder de opknipping van deze toets en zet de analyse weer terug op de totaaltoets.",
            180,
        )
        split_remove.clicked.connect(self.remove_analysis_split)
        self.analysis_split_remove_button = split_remove
        report = compact_action_button(
            set_button_role(QPushButton("Matrijsrapport"), "secondary"),
            "Genereer de grafische toetsmatrijs met verdelingen.",
            135,
        )
        report.clicked.connect(self.generate_report)
        content_layout.addWidget(
            make_page_header(
                "Vragenoverzicht",
                "Kies een toets en beheer vragen, subvragen, punten, taxonomieën en vraagclassificaties.",
                [report, split_analysis, split_remove, add_from_database, add_to_database, delete, edit, add],
            )
        )
        content_layout.addWidget(
            make_responsive_filter_card(
                "Filter en toetskeuze",
                [
                    ("Niveau", self.level_filter),
                    ("Jaarlaag", self.grade_filter),
                    ("Toets", self.test),
                ],
                minimum_field_width=240,
                maximum_columns=3,
            )
        )
        self.summary = QLabel()
        self.summary.setObjectName("panel")
        content_layout.addWidget(self.summary)
        self.empty_state = make_empty_state(
            "Kies eerst een toets",
            "Selecteer bovenaan de toets waarvoor u vragen wilt bekijken of invoeren. Daarna verschijnt de toetsmatrijs.",
        )
        content_layout.addWidget(self.empty_state)
        self.table = QTableWidget()
        self.table.cellDoubleClicked.connect(lambda row, column: self.edit_question(row))
        self.table.setMinimumHeight(420)
        content_layout.addWidget(self.table)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.refresh()

    def help_content(self) -> dict[str, object]:
        steps = [
            {
                "title": "De juiste toets openen",
                "text": "Dit scherm opent bewust zonder geselecteerde toets, zodat u niet per ongeluk vragen aan de verkeerde toets toevoegt.",
                "action": "Kies indien nodig eerst 'Niveau' en 'Jaarlaag' en selecteer daarna bij 'Toets' de juiste toets.",
                "tip": "De balk onder de knoppen toont daarna het aantal vragen, punten en de ingevulde tijdindicatie.",
            },
            {
                "title": "Een vraag invoeren",
                "text": "Elke losse vraag krijgt een automatisch voorgesteld hoofdnummer, maximumscore en verplicht een keuze binnen iedere geselecteerde taxonomie. De omschrijving voor deze toets en tijd zijn optioneel.",
                "action": "Klik op 'Vraag toevoegen'. Laat 'Deze vraag heeft subvragen' uit als het een gewone losse vraag is.",
                "tip": "De toetsomschrijving staat los van de korte databaseomschrijving, maar blijft bij databasevragen wel als gebruiksmetadata gekoppeld.",
            },
            {
                "title": "Een vraag met subvragen invoeren",
                "text": "Als een hoofdvraag uit onderdelen bestaat, bijvoorbeeld 3a, 3b en 3c, maakt u deze in een keer aan. De hoofdvraag zelf krijgt dan geen aparte score.",
                "action": "Vink 'Deze vraag heeft subvragen' aan, kies het aantal subvragen en vul per subvraag de punten, taxonomieën, eigenschappen en eventueel meerkeuzegegevens in.",
                "tip": "In het vragenoverzicht staan de subvragen als losse regels, maar de kolom 'Vraaggroep' laat zien dat ze bij dezelfde hoofdvraag horen.",
            },
        ]
        if analysis_parts_enabled(self.database):
            steps.append(
                {
                    "title": "Toets opsplitsen voor analyse",
                    "text": "Als de opknipping via geavanceerde instellingen aan staat, kunt u deze toets in herkenbare deeltoetsen verdelen. Zo kunt u later analyseren per deeltoets in plaats van alleen op de totaaltoets.",
                    "action": "Klik op 'Opknipping beheren' om deeltoetsen te benoemen en vragen of subvragen toe te wijzen. Verwijderen kan via de rode knop als u weer terug wilt naar één totaaltoets.",
                    "tip": "Bij een opknipping blijft de totaaltoets bestaan; alleen de analysekijk verandert. De hulp- en analyseschermen leggen dan expliciet uit welke kaarten bij de deeltoets horen.",
                }
            )
        steps.extend(
            [
                {
                    "title": "Een vraaggroep bewerken",
                    "text": "Wanneer u een subvraag zoals 3a of 3b selecteert, opent het bewerkvenster automatisch de hele vraaggroep.",
                    "action": "Selecteer een van de subvragen en klik op 'Vraag bewerken'. Pas daarna alle subvragen van dezelfde hoofdvraag in hetzelfde venster aan.",
                    "tip": "Zo voorkomt u dat een hoofdvraag deels als losse vraag en deels als subvraag wordt beheerd.",
                },
                {
                    "title": "Een vraag verwijderen",
                    "text": "Met 'Vraag verwijderen' verwijdert u een losse vraag of de volledige geselecteerde vraaggroep uit deze toets.",
                    "action": "Selecteer de vraag en bevestig dat u deze wilt verwijderen.",
                    "tip": "Een vraag met ingevoerde resultaten kan niet worden verwijderd. Een gekoppelde databasevraag blijft wel in de Vraagdatabase bestaan.",
                },
                {
                    "title": "Classificaties gebruiken",
                    "text": "Velden zoals hoofdstuk, domein of vraagtype maken analyses per onderdeel mogelijk.",
                    "action": "Vul bij elke vraag de eigenschappen in die u voor deze toets heeft aangezet.",
                    "tip": "Ontbrekende eigenschappen kunnen in verdelingsrapporten als 'Niet ingevuld' verschijnen.",
                },
                {
                    "title": "Een meerkeuzevraag instellen",
                    "text": "Bij vraaginvoer vult de docent alleen de standaard antwoordsleutel in: precies één letter. Tijdens resultateninvoer voert u het antwoord van de leerling in en worden punten automatisch toegekend.",
                    "action": "Vink in de vraag 'meerkeuze' aan en voer één standaardletter in, bijvoorbeeld A of F. Neutraliseren of extra opties goedtellen doet u later via 'MC-sleutels' bij resultateninvoer.",
                    "tip": "Als u later de antwoordsleutel wijzigt, worden opgeslagen antwoorden opnieuw nagekeken.",
                },
                {
                    "title": "Toetsmatrijsrapport maken",
                    "text": "Het toetsmatrijsrapport laat de opbouw en verdeling van punten overzichtelijk zien.",
                    "action": "Controleer of alle vragen compleet zijn en klik daarna op 'Toetsmatrijs genereren' voor preview en PDF-export.",
                    "tip": "Neem het rapport door vóór de afname, vooral de verdelingen per taxonomie en extra eigenschap.",
                },
            ]
        )
        return {
            "title": "Vragenoverzicht",
            "intro": "In het vragenoverzicht beschrijft u waaruit een toets bestaat: vragen, punten, taxonomie en uw eigen classificaties.",
            "steps": steps,
        }

    def properties(self, test_id: int | None) -> list:
        if test_id is None:
            return []
        properties = [
            dict(row) for row in self.database.rows(
            "SELECT p.id, p.name, p.field_type, p.choices_json FROM property_definitions p "
            "JOIN test_property_selections s ON s.property_id=p.id "
            "WHERE s.test_id=? AND p.is_active=1 ORDER BY p.id",
            (test_id,),
            )
        ]
        for definition in properties:
            selected_options = [
                row["value"]
                for row in self.database.rows(
                    "SELECT value FROM test_property_option_selections "
                    "WHERE test_id=? AND property_id=? ORDER BY rowid",
                    (test_id, definition["id"]),
                )
            ]
            if selected_options:
                definition["choices_json"] = json.dumps(selected_options)
        return properties

    def taxonomies(self, test_id: int | None) -> list[dict]:
        if test_id is None:
            return []
        taxonomies = self.database.rows(
            "SELECT d.id, d.name FROM taxonomy_definitions d "
            "JOIN test_taxonomy_selections s ON s.taxonomy_id=d.id WHERE s.test_id=? ORDER BY d.id",
            (test_id,),
        )
        return [
            {
                "id": taxonomy["id"],
                "name": taxonomy["name"],
                "values": self.database.rows(
                    "SELECT id, name FROM taxonomy_values WHERE taxonomy_id=? ORDER BY sort_order",
                    (taxonomy["id"],),
                ),
            }
            for taxonomy in taxonomies
        ]

    def refresh(self) -> None:
        self.update_question_database_visibility()
        self.update_analysis_split_visibility()
        selected_id = self.test.currentData()
        selected_level = self.level_filter.currentData()
        selected_grade = self.grade_filter.currentData()
        self.level_filter.blockSignals(True)
        self.level_filter.clear()
        self.level_filter.addItem("Alle niveaus", None)
        self.grade_filter.blockSignals(True)
        self.grade_filter.clear()
        self.grade_filter.addItem("Alle jaarlagen", None)
        filter_values = self.database.rows(
            "SELECT DISTINCT COALESCE(level, '') AS level, COALESCE(grade_year, '') AS grade_year "
            "FROM tests WHERE school_year_id=?",
            (self.year_id,),
        ) if self.year_id else []
        for level in sorted({row["level"] for row in filter_values if row["level"]}, key=str.lower):
            self.level_filter.addItem(level, level)
        for grade in sorted({row["grade_year"] for row in filter_values if row["grade_year"]}, key=str.lower):
            self.grade_filter.addItem(grade, grade)
        if selected_level is not None:
            level_index = self.level_filter.findData(selected_level)
            if level_index >= 0:
                self.level_filter.setCurrentIndex(level_index)
        if selected_grade is not None:
            grade_index = self.grade_filter.findData(selected_grade)
            if grade_index >= 0:
                self.grade_filter.setCurrentIndex(grade_index)
        self.level_filter.blockSignals(False)
        self.grade_filter.blockSignals(False)
        self.test.blockSignals(True)
        self.test.clear()
        self.test.addItem("Kies toets...", None)
        conditions = ["school_year_id=?"]
        parameters: list[object] = [self.year_id]
        if self.level_filter.currentData():
            conditions.append("level=?")
            parameters.append(self.level_filter.currentData())
        if self.grade_filter.currentData():
            conditions.append("grade_year=?")
            parameters.append(self.grade_filter.currentData())
        tests = self.database.rows(
            "SELECT id, name FROM tests WHERE " + " AND ".join(conditions) + " ORDER BY created_at DESC",
            tuple(parameters),
        ) if self.year_id else []
        for test in tests:
            self.test.addItem(test["name"], test["id"])
        if selected_id is not None:
            position = self.test.findData(selected_id)
            if position >= 0:
                self.test.setCurrentIndex(position)
            else:
                self.test.setCurrentIndex(0)
        else:
            self.test.setCurrentIndex(0)
        self.test.blockSignals(False)
        self.refresh_questions()

    def update_question_database_visibility(self) -> None:
        enabled = question_database_enabled(self.database)
        for button in getattr(self, "question_database_buttons", []):
            button.setVisible(enabled)

    def update_analysis_split_visibility(self) -> None:
        enabled = analysis_parts_enabled(self.database)
        has_parts = bool(self.analysis_parts_for_test(self.test.currentData()))
        if hasattr(self, "analysis_split_button"):
            self.analysis_split_button.setVisible(enabled)
            self.analysis_split_button.setText("Opknipping beheren" if has_parts else "Opsplitsen voor analyse")
            self.analysis_split_button.setToolTip(
                "Bewerk de deeltoetsindeling." if has_parts else "Deel deze toets voor analyse op in herkenbare deeltoetsen."
            )
        if hasattr(self, "analysis_split_remove_button"):
            self.analysis_split_remove_button.setVisible(enabled and has_parts)

    def on_activated(self) -> None:
        self.update_analysis_split_visibility()
        self.test.blockSignals(True)
        if self.test.count():
            self.test.setCurrentIndex(0)
        self.test.blockSignals(False)
        self.refresh_questions()

    def refresh_questions(self) -> None:
        test_id = self.test.currentData()
        self.update_analysis_split_visibility()
        has_test = test_id is not None
        self.empty_state.setVisible(not has_test)
        self.table.setVisible(has_test)
        properties = self.properties(test_id)
        taxonomies = self.taxonomies(test_id)
        analysis_parts = self.analysis_parts_for_test(test_id)
        show_analysis_parts = bool(analysis_parts)
        configure_table(
            self.table,
            ["Label", "Vraaggroep", "Bron", "Maximumscore", "Omschrijving voor deze toets", "Tijd (min.)"]
            + (["Deeltoets"] if show_analysis_parts else [])
            + [taxonomy["name"] for taxonomy in taxonomies]
            + [definition["name"] for definition in properties],
        )
        rows = self.database.rows(
            "SELECT id, question_number, subquestion, question_number || COALESCE(subquestion, '') AS label, "
            "maximum_score, short_description, expected_time_minutes, question_bank_id FROM matrix_questions WHERE test_id=? "
            "ORDER BY CAST(question_number AS INTEGER), question_number, COALESCE(subquestion, '')",
            (test_id,),
        ) if test_id else []
        group_counts: dict[str, int] = {}
        for row in rows:
            if row["subquestion"]:
                group_counts[str(row["question_number"])] = group_counts.get(str(row["question_number"]), 0) + 1
        seen_groups: set[str] = set()
        self.table.setRowCount(len(rows))
        total_points = 0.0
        total_time = 0.0
        timed_questions = 0
        part_names_by_question = self.analysis_part_names_by_question(test_id) if show_analysis_parts else {}
        for row_number, row in enumerate(rows):
            total_points += float(row["maximum_score"])
            if row["expected_time_minutes"] is not None:
                total_time += float(row["expected_time_minutes"])
                timed_questions += 1
            group_text = (
                f"Vraag {row['question_number']} ({group_counts[str(row['question_number'])]} subvragen)"
                if row["subquestion"]
                else "Losse vraag"
            )
            if row["subquestion"]:
                group_key = str(row["question_number"])
                label_text = f"Vraag {group_key}\n    {row['subquestion']}" if group_key not in seen_groups else f"    {row['subquestion']}"
                seen_groups.add(group_key)
            else:
                label_text = f"Vraag {row['question_number']}"
            values = (
                label_text,
                group_text,
                "Vraagdatabase" if row["question_bank_id"] else "Los",
                row["maximum_score"],
                row["short_description"],
                row["expected_time_minutes"],
            )
            for column, value in enumerate(values):
                self.table.setItem(row_number, column, item(value))
            metadata_start_column = 6
            if show_analysis_parts:
                self.table.setItem(row_number, 6, item(part_names_by_question.get(int(row["id"]), "")))
                metadata_start_column = 7
            self.table.resizeRowToContents(row_number)
            self.table.item(row_number, 0).setData(Qt.ItemDataRole.UserRole, row["id"])
            if row["subquestion"]:
                for column in range(self.table.columnCount()):
                    cell = self.table.item(row_number, column)
                    if cell is not None:
                        cell.setBackground(QColor("#f6f8fb"))
            taxonomy_values = {
                value["taxonomy_id"]: value["value_name"]
                for value in self.database.rows(
                    "SELECT qtv.taxonomy_id, tv.name AS value_name FROM question_taxonomy_values qtv "
                    "JOIN taxonomy_values tv ON tv.id=qtv.taxonomy_value_id WHERE qtv.question_id=?",
                    (row["id"],),
                )
            }
            for column, taxonomy in enumerate(taxonomies, start=metadata_start_column):
                self.table.setItem(row_number, column, item(taxonomy_values.get(taxonomy["id"], "")))
            stored_values = {
                value["property_id"]: value["value"]
                for value in self.database.rows(
                    "SELECT property_id, value FROM question_property_values WHERE question_id=?", (row["id"],)
                )
            }
            for column, property_definition in enumerate(properties, start=metadata_start_column + len(taxonomies)):
                self.table.setItem(row_number, column, item(stored_values.get(property_definition["id"], "")))
        time_text = f"{total_time:g} minuten geraamd" if timed_questions else "geen tijdindicatie ingevuld"
        split_text = f" | {len(analysis_parts)} deeltoetsen voor analyse" if analysis_parts else ""
        self.summary.setText(f"{len(rows)} vragen | {total_points:g} punten | {time_text}{split_text}")

    def analysis_parts_for_test(self, test_id: int | None) -> list[dict]:
        if test_id is None:
            return []
        return [
            dict(row)
            for row in self.database.rows(
                "SELECT id, name, sort_order FROM test_analysis_parts WHERE test_id=? ORDER BY sort_order",
                (test_id,),
            )
        ]

    def analysis_part_names_by_question(self, test_id: int | None) -> dict[int, str]:
        if test_id is None:
            return {}
        return {
            int(row["question_id"]): str(row["name"])
            for row in self.database.rows(
                "SELECT qap.question_id, tap.name FROM question_analysis_parts qap "
                "JOIN test_analysis_parts tap ON tap.id=qap.part_id WHERE tap.test_id=?",
                (test_id,),
            )
        }

    def open_analysis_split_dialog(self) -> None:
        if not analysis_parts_enabled(self.database):
            return
        test_id = self.test.currentData()
        if test_id is None:
            QMessageBox.information(self, "Geen toets", "Kies eerst een toets om op te splitsen voor analyse.")
            return
        questions = [
            dict(row)
            for row in self.database.rows(
                "SELECT id, question_number, subquestion, maximum_score, short_description "
                "FROM matrix_questions WHERE test_id=? "
                "ORDER BY CAST(question_number AS INTEGER), question_number, COALESCE(subquestion, '')",
                (test_id,),
            )
        ]
        if not questions:
            QMessageBox.information(
                self,
                "Geen vragen",
                "Voeg eerst vragen toe voordat u de toets kunt opsplitsen voor analyse.",
            )
            return
        parts = self.analysis_parts_for_test(test_id)
        part_order_by_id = {int(part["id"]): int(part["sort_order"]) for part in parts}
        assignments = {
            int(row["question_id"]): part_order_by_id.get(int(row["part_id"]), 0)
            for row in self.database.rows(
                "SELECT qap.question_id, qap.part_id FROM question_analysis_parts qap "
                "JOIN test_analysis_parts tap ON tap.id=qap.part_id WHERE tap.test_id=?",
                (test_id,),
            )
        }
        dialog = AnalysisSplitDialog(questions, parts, assignments, self)
        dialog.setWindowTitle("Opknipping beheren" if parts else "Toets opsplitsen voor analyse")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        names, assignments = dialog.payload()
        try:
            self.database.connection.execute(
                "DELETE FROM test_analysis_parts WHERE test_id=? AND sort_order>=?",
                (test_id, len(names)),
            )
            for order, name in enumerate(names):
                self.database.connection.execute(
                    "INSERT INTO test_analysis_parts(test_id, name, sort_order) VALUES(?, ?, ?) "
                    "ON CONFLICT(test_id, sort_order) DO UPDATE SET name=excluded.name, updated_at=CURRENT_TIMESTAMP",
                    (test_id, name, order),
                )
            saved_parts = self.database.rows(
                "SELECT id, sort_order FROM test_analysis_parts WHERE test_id=?",
                (test_id,),
            )
            part_id_by_order = {int(row["sort_order"]): int(row["id"]) for row in saved_parts}
            for question_id, order in assignments.items():
                part_id = part_id_by_order.get(int(order))
                if part_id is None:
                    continue
                self.database.connection.execute(
                    "INSERT INTO question_analysis_parts(question_id, part_id) VALUES(?, ?) "
                    "ON CONFLICT(question_id) DO UPDATE SET part_id=excluded.part_id",
                    (question_id, part_id),
                )
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Opsplitsing niet opgeslagen", str(error))
            return
        self.refresh_questions()
        self.changed.emit()

    def remove_analysis_split(self) -> None:
        if not analysis_parts_enabled(self.database):
            return
        test_id = self.test.currentData()
        if test_id is None:
            return
        parts = self.analysis_parts_for_test(test_id)
        if not parts:
            QMessageBox.information(self, "Geen opknipping", "Deze toets heeft nog geen opknipping om te verwijderen.")
            return
        choice = QMessageBox.question(
            self,
            "Opknipping verwijderen",
            "Weet u zeker dat u de opknipping van deze toets wilt verwijderen? "
            "De deeltoetsindeling wordt dan uit de analyse gehaald.",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.connection.execute(
                "DELETE FROM question_analysis_parts WHERE part_id IN (SELECT id FROM test_analysis_parts WHERE test_id=?)",
                (test_id,),
            )
            self.database.connection.execute("DELETE FROM test_analysis_parts WHERE test_id=?", (test_id,))
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Opknipping niet verwijderd", str(error))
            return
        self.refresh_questions()
        self.changed.emit()

    def next_question_number(self, test_id: int) -> str:
        numbers = []
        for row in self.database.rows("SELECT DISTINCT question_number FROM matrix_questions WHERE test_id=?", (test_id,)):
            try:
                numbers.append(int(str(row["question_number"]).strip()))
            except ValueError:
                continue
        return str((max(numbers) if numbers else 0) + 1)

    def question_rows_for_number(self, test_id: int, number: str) -> list[dict]:
        return [
            dict(row)
            for row in self.database.rows(
                "SELECT id, question_number, subquestion, maximum_score, short_description, expected_time_minutes, "
                "is_multiple_choice, multiple_choice_answer, question_bank_id, question_bank_version_id, "
                "question_bank_subquestion_id FROM matrix_questions "
                "WHERE test_id=? AND question_number=? ORDER BY COALESCE(subquestion, '')",
                (test_id, number),
            )
        ]

    def question_has_scores(self, question_id: int) -> bool:
        return bool(
            self.database.scalar(
                "SELECT COUNT(*) FROM scores WHERE question_id=? "
                "AND (score IS NOT NULL OR TRIM(COALESCE(response_text, '')) <> '')",
                (question_id,),
            )
            or 0
        )

    def scores_fit_new_maximum(self, question_id: int, maximum_score: float, label: str) -> bool:
        conflicts = score_limit_conflicts(
            self.database,
            self.test.currentData(),
            question_id,
            float(maximum_score),
        )
        if not conflicts["count"]:
            return True
        highest = conflicts["highest_score"]
        examples = conflicts.get("examples", [])
        example_text = ""
        if examples:
            lines = [
                f"- {row['display_name']}: {float(row['score']):g} punten"
                for row in examples
            ]
            if int(conflicts["count"]) > len(examples):
                lines.append(f"... en {int(conflicts['count']) - len(examples)} meer.")
            example_text = "\n\nVoorbeelden:\n" + "\n".join(lines)
        QMessageBox.warning(
            self,
            "Maximumscore niet aangepast",
            f"De maximumscore van {label} kan niet worden verlaagd naar {float(maximum_score):g}.\n\n"
            f"Er zijn al {int(conflicts['count'])} score(s) hoger dan {float(maximum_score):g} ingevoerd.\n"
            f"Hoogste bestaande score: {float(highest):g}.\n\n"
            "Pas eerst deze scores aan of kies een hogere maximumscore."
            f"{example_text}",
        )
        return False

    def value_maps_for_questions(
        self, question_ids: list[int]
    ) -> tuple[dict[int, dict[int, str]], dict[int, dict[int, int]]]:
        if not question_ids:
            return {}, {}
        placeholders = ",".join("?" for _ in question_ids)
        property_values: dict[int, dict[int, str]] = defaultdict(dict)
        for row in self.database.rows(
            f"SELECT question_id, property_id, value FROM question_property_values WHERE question_id IN ({placeholders})",
            tuple(question_ids),
        ):
            property_values[int(row["question_id"])][int(row["property_id"])] = row["value"]
        taxonomy_values: dict[int, dict[int, int]] = defaultdict(dict)
        for row in self.database.rows(
            f"SELECT question_id, taxonomy_id, taxonomy_value_id FROM question_taxonomy_values "
            f"WHERE question_id IN ({placeholders})",
            tuple(question_ids),
        ):
            taxonomy_values[int(row["question_id"])][int(row["taxonomy_id"])] = int(row["taxonomy_value_id"])
        return dict(property_values), dict(taxonomy_values)

    def normal_question_entry(self, dialog: QuestionDialog) -> dict[str, object]:
        return {
            "question_number": dialog.number.text().strip(),
            "subquestion": None,
            "maximum_score": dialog.maximum_score.value(),
            "short_description": dialog.description.text().strip(),
            "expected_time_minutes": dialog.minutes.value() or None,
            "is_multiple_choice": int(dialog.is_multiple_choice.isChecked()),
            "multiple_choice_answer": normalize_multiple_choice_response(dialog.multiple_choice_answer.text())
            if dialog.is_multiple_choice.isChecked()
            else None,
            "question_bank_id": None,
            "question_bank_version_id": None,
            "question_bank_subquestion_id": None,
            "taxonomy_values": {
                taxonomy["id"]: dialog.taxonomy_value(taxonomy["id"])
                for taxonomy in self.taxonomies(self.test.currentData())
            },
            "property_values": {
                definition["id"]: dialog.property_value(definition["id"])
                for definition in self.properties(self.test.currentData())
            },
        }

    def insert_question_entry(self, test_id: int, entry: dict[str, object]) -> int:
        cursor = self.database.connection.execute(
            "INSERT INTO matrix_questions(test_id, question_number, subquestion, maximum_score, "
            "short_description, expected_time_minutes, is_multiple_choice, multiple_choice_answer, "
            "question_bank_id, question_bank_version_id, question_bank_subquestion_id) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                test_id,
                entry["question_number"],
                entry["subquestion"],
                entry["maximum_score"],
                entry["short_description"],
                entry["expected_time_minutes"],
                entry["is_multiple_choice"],
                entry["multiple_choice_answer"],
                entry.get("question_bank_id"),
                entry.get("question_bank_version_id"),
                entry.get("question_bank_subquestion_id"),
            ),
        )
        question_id = int(cursor.lastrowid)
        self.save_question_classifications(question_id, entry)
        return question_id

    def update_question_entry(self, question_id: int, entry: dict[str, object]) -> None:
        self.database.connection.execute(
            "UPDATE matrix_questions SET question_number=?, subquestion=?, maximum_score=?, "
            "short_description=?, expected_time_minutes=?, is_multiple_choice=?, multiple_choice_answer=?, "
            "question_bank_id=?, question_bank_version_id=?, question_bank_subquestion_id=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                entry["question_number"],
                entry["subquestion"],
                entry["maximum_score"],
                entry["short_description"],
                entry["expected_time_minutes"],
                entry["is_multiple_choice"],
                entry["multiple_choice_answer"],
                entry.get("question_bank_id"),
                entry.get("question_bank_version_id"),
                entry.get("question_bank_subquestion_id"),
                question_id,
            ),
        )
        self.save_question_classifications(question_id, entry)

    def save_question_classifications(self, question_id: int, entry: dict[str, object]) -> None:
        self.database.connection.execute("DELETE FROM question_taxonomy_values WHERE question_id=?", (question_id,))
        for taxonomy_id, taxonomy_value_id in dict(entry["taxonomy_values"]).items():
            self.database.connection.execute(
                "INSERT INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
                (question_id, taxonomy_id, taxonomy_value_id),
            )
        for property_id, value in dict(entry["property_values"]).items():
            if value:
                self.database.connection.execute(
                    "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?) "
                    "ON CONFLICT(question_id, property_id) DO UPDATE SET value=excluded.value",
                    (question_id, property_id, value),
                )
            else:
                self.database.connection.execute(
                    "DELETE FROM question_property_values WHERE question_id=? AND property_id=?",
                    (question_id, property_id),
                )

    def add_question(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            QMessageBox.information(self, "Geen toets", "Kies eerst een toets om vragen toe te voegen.")
            return
        taxonomies = self.taxonomies(test_id)
        if not taxonomies:
            QMessageBox.information(
                self, "Taxonomie nodig", "Bewerk eerst de toets en selecteer minimaal een taxonomie."
            )
            return
        properties = self.properties(test_id)
        dialog = QuestionDialog(properties, taxonomies, parent=self, default_number=self.next_question_number(test_id))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            if dialog.has_subquestion_batch():
                entries = dialog.subquestion_entries() or []
                existing_rows = self.question_rows_for_number(test_id, dialog.number.text().strip())
                if existing_rows:
                    QMessageBox.warning(
                        self,
                        "Vraagnummer bestaat al",
                        "Dit hoofdnummer bestaat al. Selecteer een bestaande subvraag en kies 'Vraag bewerken' om de hele vraaggroep te wijzigen.",
                    )
                    return
                for entry in entries:
                    self.insert_question_entry(test_id, entry)
            else:
                entry = self.normal_question_entry(dialog)
                existing_rows = self.question_rows_for_number(test_id, str(entry["question_number"]))
                if entry["subquestion"] is None and any(not row["subquestion"] for row in existing_rows):
                    QMessageBox.warning(
                        self,
                        "Vraagnummer bestaat al",
                        "Dit hoofdnummer bestaat al als losse vraag. Kies een nieuw nummer of bewerk de bestaande vraag.",
                    )
                    return
                if entry["subquestion"] is None and any(row["subquestion"] for row in existing_rows):
                    QMessageBox.warning(
                        self,
                        "Vraaggroep bestaat al",
                        "Dit hoofdnummer heeft al subvragen. Bewerk de vraaggroep of kies een nieuw hoofdnummer.",
                    )
                    return
                if entry["subquestion"] is not None and any(row["subquestion"] == entry["subquestion"] for row in existing_rows):
                    QMessageBox.warning(
                        self,
                        "Subvraag bestaat al",
                        "Deze subvraag bestaat al. Bewerk de bestaande vraag of kies een andere letter.",
                    )
                    return
                if entry["subquestion"] is not None and any(not row["subquestion"] for row in existing_rows):
                    QMessageBox.warning(
                        self,
                        "Losse vraag bestaat al",
                        "Dit hoofdnummer bestaat al als losse vraag. Gebruik de subvraagmodus om een vraaggroep te maken.",
                    )
                    return
                self.insert_question_entry(test_id, entry)
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraag niet opgeslagen", str(error))
            return
        self.refresh_questions()
        self.changed.emit()

    def edit_question(self, row: int | None = None) -> None:
        if isinstance(row, bool):
            row = None
        row = self.table.currentRow() if row is None else row
        if row < 0:
            QMessageBox.information(self, "Geen vraag geselecteerd", "Selecteer eerst een vraag om te bewerken.")
            return
        question_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        questions = [
            dict(question)
            for question in self.database.rows(
                "SELECT id, question_number, subquestion, maximum_score, short_description, expected_time_minutes, "
                "is_multiple_choice, multiple_choice_answer, question_bank_id, question_bank_version_id, "
                "question_bank_subquestion_id "
                "FROM matrix_questions WHERE id=? AND test_id=?",
                (question_id, self.test.currentData()),
            )
        ]
        if not questions:
            QMessageBox.warning(self, "Vraag niet gevonden", "De geselecteerde vraag bestaat niet meer.")
            self.refresh_questions()
            return
        if questions[0].get("question_bank_id"):
            self.edit_linked_database_question_group(questions[0])
            return
        properties = self.properties(self.test.currentData())
        taxonomies = self.taxonomies(self.test.currentData())
        if not taxonomies:
            QMessageBox.information(
                self, "Taxonomie nodig", "Bewerk eerst de toets en selecteer minimaal een taxonomie."
            )
            return
        group_rows = (
            self.question_rows_for_number(self.test.currentData(), str(questions[0]["question_number"]))
            if questions[0]["subquestion"]
            else []
        )
        group_rows = [row for row in group_rows if row["subquestion"]]
        if group_rows:
            self.edit_subquestion_group(group_rows, properties, taxonomies)
            return
        values = {
            value["property_id"]: value["value"]
            for value in self.database.rows(
                "SELECT property_id, value FROM question_property_values WHERE question_id=?", (question_id,)
            )
        }
        taxonomy_values = {
            row["taxonomy_id"]: row["taxonomy_value_id"]
            for row in self.database.rows(
                "SELECT taxonomy_id, taxonomy_value_id FROM question_taxonomy_values WHERE question_id=?",
                (question_id,),
            )
        }
        dialog = QuestionDialog(properties, taxonomies, questions[0], values, taxonomy_values, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if dialog.has_subquestion_batch():
            if self.question_has_scores(question_id):
                QMessageBox.warning(
                    self,
                    "Vraag heeft resultaten",
                    "Deze losse vraag heeft al ingevoerde resultaten en kan daarom niet worden omgezet naar subvragen.",
                )
                return
            entries = dialog.subquestion_entries() or []
            try:
                self.database.connection.execute("DELETE FROM matrix_questions WHERE id=?", (question_id,))
                for entry in entries:
                    self.insert_question_entry(self.test.currentData(), entry)
                self.database.connection.commit()
            except Exception as error:
                self.database.connection.rollback()
                QMessageBox.warning(self, "Vraag niet opgeslagen", str(error))
                return
            self.refresh_questions()
            self.changed.emit()
            return
        old_is_multiple_choice = bool(questions[0].get("is_multiple_choice"))
        old_answer = normalize_multiple_choice_response(str(questions[0].get("multiple_choice_answer") or ""))
        entry = self.normal_question_entry(dialog)
        new_is_multiple_choice = bool(entry["is_multiple_choice"])
        new_answer = entry["multiple_choice_answer"]
        if not self.scores_fit_new_maximum(question_id, float(entry["maximum_score"]), f"vraag {entry['question_number']}"):
            return
        regraded_count = 0
        try:
            conflicts = [
                row for row in self.question_rows_for_number(self.test.currentData(), str(entry["question_number"]))
                if int(row["id"]) != int(question_id)
                and (row["subquestion"] or None) == entry["subquestion"]
            ]
            if conflicts:
                QMessageBox.warning(
                    self,
                    "Vraagnummer bestaat al",
                    "Er bestaat al een vraag met dit nummer en deze subvraag.",
                )
                return
            self.update_question_entry(question_id, entry)
            self.database.connection.commit()
            if new_is_multiple_choice and (not old_is_multiple_choice or old_answer != new_answer):
                regraded_count = regrade_multiple_choice_question(self.database, self.test.currentData(), question_id)
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraag niet opgeslagen", str(error))
            return
        self.refresh_questions()
        self.changed.emit()
        if regraded_count:
            QMessageBox.information(
                self,
                "Meerkeuze opnieuw nagekeken",
                f"De antwoordsleutel is aangepast. {regraded_count} score(s) zijn opnieuw nagekeken.",
            )

    def delete_question(self) -> None:
        rows = self.selected_question_group_rows()
        if not rows:
            QMessageBox.information(self, "Geen vraag geselecteerd", "Selecteer eerst een vraag om te verwijderen.")
            return
        blocked = [row for row in rows if self.question_has_scores(int(row["id"]))]
        if blocked:
            QMessageBox.warning(
                self,
                "Vraag niet verwijderd",
                "Deze vraag of vraaggroep heeft al ingevoerde resultaten en kan daarom niet worden verwijderd.",
            )
            return
        number = str(rows[0]["question_number"])
        label = f"vraag {number}"
        if any(row.get("subquestion") for row in rows):
            label = f"vraaggroep {number} ({len(rows)} subvragen)"
        linked_note = (
            "\n\nDe gekoppelde databasevraag blijft in de Vraagdatabase bestaan."
            if any(row.get("question_bank_id") for row in rows)
            else ""
        )
        choice = QMessageBox.question(
            self,
            "Vraag verwijderen",
            f"Weet u zeker dat u {label} uit deze toets wilt verwijderen?{linked_note}",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            for row in rows:
                self.database.connection.execute("DELETE FROM matrix_questions WHERE id=?", (row["id"],))
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraag niet verwijderd", str(error))
            return
        self.refresh_questions()
        self.changed.emit()

    def edit_subquestion_group(self, group_rows: list[dict], properties: list, taxonomies: list) -> None:
        question_ids = [int(row["id"]) for row in group_rows]
        property_values, taxonomy_values = self.value_maps_for_questions(question_ids)
        dialog = QuestionDialog(
            properties,
            taxonomies,
            parent=self,
            subquestion_questions=group_rows,
            subquestion_values=property_values,
            subquestion_taxonomy_values=taxonomy_values,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entries = dialog.subquestion_entries() or []
        remaining_ids = {int(entry["id"]) for entry in entries if entry.get("id")}
        deleted_ids = [question_id for question_id in question_ids if question_id not in remaining_ids]
        blocked = [question_id for question_id in deleted_ids if self.question_has_scores(question_id)]
        if blocked:
            QMessageBox.warning(
                self,
                "Subvraag heeft resultaten",
                "Een of meer verwijderde subvragen hebben al ingevoerde resultaten. Verwijder die resultaten eerst of laat de subvraag bestaan.",
            )
            return
        for entry in entries:
            if entry.get("id"):
                label = f"vraag {entry['question_number']}{entry.get('subquestion') or ''}"
                if not self.scores_fit_new_maximum(int(entry["id"]), float(entry["maximum_score"]), label):
                    return
        regrade_ids: list[int] = []
        try:
            for entry in entries:
                if entry.get("id"):
                    question_id = int(entry["id"])
                    self.update_question_entry(question_id, entry)
                    if entry["is_multiple_choice"]:
                        regrade_ids.append(question_id)
                else:
                    self.insert_question_entry(self.test.currentData(), entry)
            for question_id in deleted_ids:
                self.database.connection.execute("DELETE FROM matrix_questions WHERE id=?", (question_id,))
            self.database.connection.commit()
            regraded_count = 0
            for question_id in regrade_ids:
                regraded_count += regrade_multiple_choice_question(self.database, self.test.currentData(), question_id)
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraaggroep niet opgeslagen", str(error))
            return
        self.refresh_questions()
        self.changed.emit()
        if regraded_count:
            QMessageBox.information(
                self,
                "Meerkeuze opnieuw nagekeken",
                f"De antwoordsleutel is aangepast. {regraded_count} score(s) zijn opnieuw nagekeken.",
            )

    def latest_question_database_rows(self) -> list[sqlite3.Row]:
        return question_database_latest_rows(self.database)

    def load_question_database_version(
        self, version_id: int
    ) -> tuple[dict, list[dict], dict[int, int], dict[int, str]]:
        version = dict(
            self.database.rows(
                "SELECT v.*, COALESCE(i.status, 'Actief') AS status "
                "FROM question_bank_versions v JOIN question_bank_items i ON i.id=v.item_id "
                "WHERE v.id=?",
                (version_id,),
            )[0]
        )
        subquestions = [
            dict(row) for row in self.database.rows(
                "SELECT * FROM question_bank_subquestions WHERE version_id=? ORDER BY sort_order, subquestion",
                (version_id,),
            )
        ]
        subquestion_ids = [int(row["id"]) for row in subquestions]
        if subquestion_ids:
            placeholders = ",".join("?" for _ in subquestion_ids)
            taxonomy_maps: dict[int, dict[int, int]] = defaultdict(dict)
            for row in self.database.rows(
                f"SELECT subquestion_id, taxonomy_id, taxonomy_value_id "
                f"FROM question_bank_subquestion_taxonomy_values WHERE subquestion_id IN ({placeholders})",
                tuple(subquestion_ids),
            ):
                taxonomy_maps[int(row["subquestion_id"])][int(row["taxonomy_id"])] = int(row["taxonomy_value_id"])
            property_maps: dict[int, dict[int, str]] = defaultdict(dict)
            for row in self.database.rows(
                f"SELECT subquestion_id, property_id, value "
                f"FROM question_bank_subquestion_property_values WHERE subquestion_id IN ({placeholders})",
                tuple(subquestion_ids),
            ):
                property_maps[int(row["subquestion_id"])][int(row["property_id"])] = str(row["value"] or "")
            for subquestion in subquestions:
                subquestion["taxonomy_values"] = taxonomy_maps.get(int(subquestion["id"]), {})
                subquestion["property_values"] = property_maps.get(int(subquestion["id"]), {})
        taxonomy_values = {
            int(row["taxonomy_id"]): int(row["taxonomy_value_id"])
            for row in self.database.rows(
                "SELECT taxonomy_id, taxonomy_value_id FROM question_bank_version_taxonomy_values WHERE version_id=?",
                (version_id,),
            )
        }
        property_values = {
            int(row["property_id"]): str(row["value"] or "")
            for row in self.database.rows(
                "SELECT property_id, value FROM question_bank_version_property_values WHERE version_id=?",
                (version_id,),
            )
        }
        return version, subquestions, taxonomy_values, property_values

    @staticmethod
    def filter_database_question_classifications_for_test(
        database: SubjectDatabase,
        test_id: int,
        taxonomy_values: dict[int, int],
        property_values: dict[int, str],
    ) -> tuple[dict[int, int], dict[int, str]]:
        selected_taxonomy_ids = {
            int(row["taxonomy_id"])
            for row in database.rows(
                "SELECT taxonomy_id FROM test_taxonomy_selections WHERE test_id=?",
                (test_id,),
            )
        }
        selected_property_ids = {
            int(row["property_id"])
            for row in database.rows(
                "SELECT property_id FROM test_property_selections WHERE test_id=?",
                (test_id,),
            )
        }
        selected_property_options: dict[int, set[str]] = defaultdict(set)
        for row in database.rows(
            "SELECT property_id, value FROM test_property_option_selections WHERE test_id=?",
            (test_id,),
        ):
            selected_property_options[int(row["property_id"])].add(str(row["value"]))

        filtered_taxonomy_values = {
            int(taxonomy_id): int(value_id)
            for taxonomy_id, value_id in taxonomy_values.items()
            if int(taxonomy_id) in selected_taxonomy_ids
        }
        filtered_property_values: dict[int, str] = {}
        for property_id, value in property_values.items():
            property_id = int(property_id)
            value = str(value or "").strip()
            if not value or property_id not in selected_property_ids:
                continue
            allowed_options = selected_property_options.get(property_id, set())
            if allowed_options and value not in allowed_options:
                continue
            filtered_property_values[property_id] = value
        return filtered_taxonomy_values, filtered_property_values

    @staticmethod
    def save_database_question_classifications(
        database: SubjectDatabase,
        question_id: int,
        taxonomy_values: dict[int, int],
        property_values: dict[int, str],
    ) -> None:
        database.connection.execute("DELETE FROM question_taxonomy_values WHERE question_id=?", (question_id,))
        for taxonomy_id, taxonomy_value_id in taxonomy_values.items():
            database.connection.execute(
                "INSERT INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
                (question_id, taxonomy_id, taxonomy_value_id),
            )
        database.connection.execute("DELETE FROM question_property_values WHERE question_id=?", (question_id,))
        for property_id, value in property_values.items():
            if value:
                database.connection.execute(
                    "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
                    (question_id, property_id, value),
                )

    @staticmethod
    def insert_database_question_rows(
        database: SubjectDatabase,
        test_id: int,
        question_number: str,
        item_id: int,
        version_id: int,
        version: dict,
        subquestions: list[dict],
        taxonomy_values: dict[int, int],
        property_values: dict[int, str],
    ) -> list[int]:
        fallback_taxonomy_values, fallback_property_values = MatrixPage.filter_database_question_classifications_for_test(
            database, test_id, taxonomy_values, property_values
        )
        inserted_ids: list[int] = []
        rows = subquestions or [
            {
                "id": None,
                "subquestion": None,
                "maximum_score": version.get("maximum_score"),
                "expected_time_minutes": version.get("expected_time_minutes"),
                "is_multiple_choice": version.get("is_multiple_choice"),
                "multiple_choice_answer": version.get("multiple_choice_answer"),
            }
        ]
        for row in rows:
            row_taxonomy_source = (
                dict(row.get("taxonomy_values") or {})
                if "taxonomy_values" in row else fallback_taxonomy_values
            )
            row_property_source = (
                dict(row.get("property_values") or {})
                if "property_values" in row else fallback_property_values
            )
            row_taxonomy_values, row_property_values = MatrixPage.filter_database_question_classifications_for_test(
                database,
                test_id,
                row_taxonomy_source,
                row_property_source,
            )
            cursor = database.connection.execute(
                "INSERT INTO matrix_questions(test_id, question_number, subquestion, maximum_score, "
                "short_description, expected_time_minutes, is_multiple_choice, multiple_choice_answer, "
                "question_bank_id, question_bank_version_id, question_bank_subquestion_id) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    test_id,
                    question_number,
                    row.get("subquestion"),
                    row.get("maximum_score"),
                    "",
                    row.get("expected_time_minutes"),
                    int(row.get("is_multiple_choice") or 0),
                    row.get("multiple_choice_answer"),
                    item_id,
                    version_id,
                    row.get("id"),
                ),
            )
            question_id = int(cursor.lastrowid)
            inserted_ids.append(question_id)
            MatrixPage.save_database_question_classifications(database, question_id, row_taxonomy_values, row_property_values)
        return inserted_ids

    def add_question_from_database(self) -> None:
        if not question_database_enabled(self.database):
            return
        test_id = self.test.currentData()
        if test_id is None:
            QMessageBox.information(self, "Geen toets", "Kies eerst een toets om vragen toe te voegen.")
            return
        rows = self.latest_question_database_rows()
        if not rows:
            QMessageBox.information(
                self,
                "Vraagdatabase leeg",
                "Maak eerst een vraag aan in de module Vraagdatabase.",
            )
            return
        dialog = QuestionDatabaseSelectionDialog(rows, self.database, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.selected() is None:
            return
        item_id, version_id = dialog.selected()
        default_number = self.next_question_number(test_id)
        number, ok = QInputDialog.getText(
            self,
            "Vraagnummer kiezen",
            "Welk vraagnummer krijgt deze databasevraag in de toets?",
            QLineEdit.EchoMode.Normal,
            default_number,
        )
        if not ok or not number.strip():
            return
        number = number.strip()
        if self.question_rows_for_number(test_id, number):
            QMessageBox.warning(self, "Vraagnummer bestaat al", "Kies een vraagnummer dat nog niet in deze toets staat.")
            return
        version, subquestions, taxonomy_values, property_values = self.load_question_database_version(version_id)
        try:
            self.insert_database_question_rows(
                self.database, test_id, number, item_id, version_id, version, subquestions, taxonomy_values, property_values
            )
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraag niet toegevoegd", str(error))
            return
        self.refresh()
        position = self.test.findData(test_id)
        if position >= 0:
            self.test.setCurrentIndex(position)
        self.changed.emit()

    def selected_question_group_rows(self) -> list[dict]:
        row = self.table.currentRow()
        if row < 0:
            return []
        question_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        question = self.database.rows(
            "SELECT * FROM matrix_questions WHERE id=? AND test_id=?",
            (question_id, self.test.currentData()),
        )
        if not question:
            return []
        number = str(question[0]["question_number"])
        rows = self.question_rows_for_number(self.test.currentData(), number)
        if any(row["subquestion"] for row in rows):
            return [row for row in rows if row["subquestion"]]
        return [dict(question[0])]

    def add_selected_question_to_database(self) -> None:
        if not question_database_enabled(self.database):
            return
        rows = self.selected_question_group_rows()
        if not rows:
            QMessageBox.information(self, "Geen vraag geselecteerd", "Selecteer eerst een vraag om toe te voegen.")
            return
        if any(row.get("question_bank_id") for row in rows):
            QMessageBox.information(
                self,
                "Al gekoppeld",
                "Deze vraag is al gekoppeld aan de vraagdatabase.",
            )
            return
        question_ids = [int(row["id"]) for row in rows]
        property_values_by_question, taxonomy_values_by_question = self.value_maps_for_questions(question_ids)
        title_default = rows[0].get("short_description") or f"Vraag {rows[0]['question_number']}"
        dialog = QuestionDatabaseImportDialog(
            str(title_default),
            load_all_taxonomies(self.database),
            load_active_question_properties(self.database),
            rows,
            taxonomy_values_by_question,
            property_values_by_question,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        try:
            self.create_question_database_item_from_rows(
                str(payload["title"]),
                str(payload["short_description"]),
                rows,
                str(payload["status"]),
                dict(payload["taxonomy_values"]),
                dict(payload["property_values"]),
                dict(payload["subquestion_metadata"]),
                question_text=str(payload["question_text"]),
            )
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraag niet toegevoegd", str(error))
            return
        self.refresh_questions()
        self.changed.emit()

    def create_question_database_item_from_rows(
        self,
        title: str,
        database_description: str,
        rows: list[dict],
        status: str = "Actief",
        database_taxonomy_values: dict[int, int] | None = None,
        database_property_values: dict[int, str] | None = None,
        subquestion_metadata: dict[int, dict[str, dict[int, object]]] | None = None,
        question_text: str = "",
    ) -> int:
        question_ids = [int(row["id"]) for row in rows]
        property_values, taxonomy_values_by_question = self.value_maps_for_questions(question_ids)
        first_taxonomy_values = database_taxonomy_values if database_taxonomy_values is not None else taxonomy_values_by_question.get(question_ids[0], {})
        first_property_values = database_property_values if database_property_values is not None else property_values.get(question_ids[0], {})
        subquestion_metadata = subquestion_metadata or {}
        total_score = sum(float(row["maximum_score"]) for row in rows)
        total_time = sum(float(row["expected_time_minutes"] or 0) for row in rows) or None
        cursor = self.database.connection.execute(
            "INSERT INTO question_bank_items(title, short_description, status, maximum_score, expected_time_minutes) "
            "VALUES(?, ?, ?, ?, ?)",
            (title, database_description, status, total_score, total_time),
        )
        item_id = int(cursor.lastrowid)
        cursor = self.database.connection.execute(
            "INSERT INTO question_bank_versions(item_id, version_number, title, question_text, short_description, "
            "maximum_score, expected_time_minutes, is_multiple_choice, multiple_choice_answer) "
            "VALUES(?, 1, ?, ?, ?, ?, ?, ?, ?)",
            (
                item_id,
                title,
                question_text,
                database_description,
                total_score,
                total_time,
                int(rows[0].get("is_multiple_choice") or 0) if len(rows) == 1 else 0,
                rows[0].get("multiple_choice_answer") if len(rows) == 1 else None,
            ),
        )
        version_id = int(cursor.lastrowid)
        for taxonomy_id, value_id in first_taxonomy_values.items():
            self.database.connection.execute(
                "INSERT INTO question_bank_version_taxonomy_values(version_id, taxonomy_id, taxonomy_value_id) "
                "VALUES(?, ?, ?)",
                (version_id, taxonomy_id, value_id),
            )
        for property_id, value in first_property_values.items():
            self.database.connection.execute(
                "INSERT INTO question_bank_version_property_values(version_id, property_id, value) VALUES(?, ?, ?)",
                (version_id, property_id, value),
            )
        if len(rows) == 1 and not rows[0].get("subquestion"):
            self.database.connection.execute(
                "UPDATE matrix_questions SET question_bank_id=?, question_bank_version_id=?, question_bank_subquestion_id=NULL "
                "WHERE id=?",
                (item_id, version_id, rows[0]["id"]),
            )
            return item_id
        for order, row in enumerate(rows):
            cursor = self.database.connection.execute(
                "INSERT INTO question_bank_subquestions(version_id, subquestion, question_text, short_description, maximum_score, "
                "expected_time_minutes, is_multiple_choice, multiple_choice_answer, sort_order) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    version_id,
                    row.get("subquestion") or chr(ord("a") + order),
                    str((subquestion_metadata.get(int(row["id"]), {}) or {}).get("question_text") or ""),
                    str((subquestion_metadata.get(int(row["id"]), {}) or {}).get("short_description") or row.get("short_description") or ""),
                    row.get("maximum_score"),
                    row.get("expected_time_minutes"),
                    int(row.get("is_multiple_choice") or 0),
                    row.get("multiple_choice_answer"),
                    order,
                ),
            )
            subquestion_id = int(cursor.lastrowid)
            row_metadata = subquestion_metadata.get(int(row["id"]), {})
            row_taxonomy_values = dict(row_metadata.get("taxonomy_values") or taxonomy_values_by_question.get(int(row["id"]), {}))
            row_property_values = dict(row_metadata.get("property_values") or property_values.get(int(row["id"]), {}))
            for taxonomy_id, value_id in row_taxonomy_values.items():
                self.database.connection.execute(
                    "INSERT INTO question_bank_subquestion_taxonomy_values(subquestion_id, taxonomy_id, taxonomy_value_id) "
                    "VALUES(?, ?, ?)",
                    (subquestion_id, int(taxonomy_id), int(value_id)),
                )
            for property_id, value in row_property_values.items():
                if value:
                    self.database.connection.execute(
                        "INSERT INTO question_bank_subquestion_property_values(subquestion_id, property_id, value) "
                        "VALUES(?, ?, ?)",
                        (subquestion_id, int(property_id), str(value)),
                    )
            self.database.connection.execute(
                "UPDATE matrix_questions SET question_bank_id=?, question_bank_version_id=?, question_bank_subquestion_id=? "
                "WHERE id=?",
                (item_id, version_id, subquestion_id, row["id"]),
            )
        return item_id

    def edit_linked_database_question_group(self, question: dict) -> None:
        old_number = str(question["question_number"])
        rows = [
            row
            for row in self.question_rows_for_number(self.test.currentData(), old_number)
            if row.get("question_bank_id") == question.get("question_bank_id")
        ]
        dialog = LinkedDatabaseQuestionDialog(rows, question_database_enabled(self.database), self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_number = dialog.number.text().strip()
        if not new_number:
            QMessageBox.warning(self, "Vraagnummer ontbreekt", "Vul een vraagnummer in.")
            return
        if new_number != old_number and self.question_rows_for_number(self.test.currentData(), new_number):
            QMessageBox.warning(self, "Vraagnummer bestaat al", "Kies een vraagnummer dat nog niet in deze toets staat.")
            return
        try:
            descriptions = dialog.descriptions()
            for row in rows:
                self.database.connection.execute(
                    "UPDATE matrix_questions SET question_number=?, short_description=?, updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=?",
                    (new_number, descriptions.get(int(row["id"]), ""), row["id"]),
                )
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraag niet aangepast", str(error))
            return
        self.refresh_questions()
        self.changed.emit()

    def generate_report(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            QMessageBox.information(self, "Geen toets", "Kies eerst een toets voor de toetsmatrijs.")
            return
        try:
            html = build_matrix_report_html(self.database, test_id)
        except Exception as error:
            QMessageBox.warning(self, "Rapport niet gemaakt", str(error))
            return
        MatrixReportPreviewDialog(self.database, test_id, self.test.currentText(), html, self).exec()



class MatrixReportPreviewDialog(QDialog):
    def __init__(
        self,
        database: SubjectDatabase,
        test_id: int,
        test_name: str,
        html: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.test_id = test_id
        self.test_name = test_name
        self.html = html
        self.setWindowTitle(f"Preview toetsmatrijs - {test_name}")
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            width = min(1120, max(620, available.width() - 80))
            height = min(820, max(420, available.height() - 80))
            self.resize(width, height)
            self.move(
                available.x() + (available.width() - width) // 2,
                available.y() + (available.height() - height) // 2,
            )
        else:
            self.resize(960, 680)
        layout = QVBoxLayout(self)
        actions = QHBoxLayout()
        actions.addWidget(QLabel("Preview toetsmatrijsrapport"))
        actions.addStretch()
        buttons = QDialogButtonBox()
        save = buttons.addButton("PDF exporteren", QDialogButtonBox.ButtonRole.AcceptRole)
        close = buttons.addButton("Sluiten", QDialogButtonBox.ButtonRole.RejectRole)
        save.clicked.connect(self.save_pdf)
        close.clicked.connect(self.reject)
        actions.addWidget(buttons)
        layout.addLayout(actions)
        if QWebEngineView is not None:
            self.preview_stack = QStackedWidget()
            loading = QLabel("Dashboard wordt gegenereerd...")
            loading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            loading.setStyleSheet(
                "background: #f6f8fb; color: #506582; font-size: 15px; "
                "font-weight: 600; padding: 36px;"
            )
            self.preview = QWebEngineView()
            self.preview_stack.addWidget(loading)
            self.preview_stack.addWidget(self.preview)
            self.preview.loadFinished.connect(lambda _ok: self.preview_stack.setCurrentWidget(self.preview))
            self.preview.setHtml(browser_report_html(html))
            layout.addWidget(self.preview_stack)
        else:
            self.preview = QTextBrowser()
            self.preview.setDocument(formatted_report_document(html, self.preview))
            layout.addWidget(self.preview)

    def save_pdf(self) -> None:
        PDF_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        suggested = PDF_EXPORT_DIR / f"{slug(self.test_name)}_toetsmatrijs.pdf"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Toetsmatrijs opslaan als PDF",
            str(suggested),
            "PDF-bestanden (*.pdf)",
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".pdf"):
            file_name += ".pdf"
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            export_html_to_pdf(self.html, file_name)
        except PdfExportError as error:
            QMessageBox.warning(self, "PDF niet opgeslagen", str(error))
            return
        finally:
            QApplication.restoreOverrideCursor()
        try:
            self.database.execute(
                "INSERT INTO report_exports(report_type, test_id, file_path) VALUES(?, ?, ?)",
                ("toetsmatrijsrapport", self.test_id, file_name),
            )
        except Exception:
            pass
        QMessageBox.information(self, "PDF opgeslagen", f"De toetsmatrijs is opgeslagen als:\n{file_name}")

