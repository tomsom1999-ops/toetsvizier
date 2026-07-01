from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import SubjectDatabase
from .importers import (
    ResultImportError,
    import_results,
    preview_results_import,
    read_results_rows,
    suggest_results_mapping,
)
from .pages_base import Page
from .paths import EXCEL_EXPORT_DIR
from .results import (
    QUESTION_ORDER_SQL,
    RESULT_STATUSES,
    ResultExportError,
    ResultValidationError,
    export_scores_xlsx,
    is_not_made_score,
    normalize_multiple_choice_option_list,
    normalize_multiple_choice_response,
    regrade_multiple_choice_question,
    save_score,
    save_status,
    stored_results,
    test_questions,
    test_students,
)
from .ui_helpers import (
    CenteredComboBox,
    compact_action_button,
    fit_to_available_screen,
    item,
    make_empty_state,
    make_filter_field,
    make_info_banner,
    make_page_header,
    make_responsive_filter_card,
    set_button_role,
    slug,
)


class ResultsImportDialog(QDialog):
    def __init__(self, database: SubjectDatabase, test_id: int, questions: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self.test_id = test_id
        self.questions = questions
        self.rows: list[dict[str, str]] = []
        self.headers: list[str] = []
        self.preview_ready = False
        self.fuzzy_overrides: dict[str, str] = {}
        self.setWindowTitle("Resultaten importeren")
        fit_to_available_screen(self, 1200, 820, margin=40)
        outer_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        file_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        pick = QPushButton("Bestand kiezen")
        pick.clicked.connect(self.choose_file)
        file_row.addWidget(self.file_path, 1)
        file_row.addWidget(pick)
        layout.addLayout(file_row)
        mapper = QGridLayout()
        self.student_number_column = QComboBox()
        self.student_name_column = QComboBox()
        self.status_column = QComboBox()
        mapper.addWidget(QLabel("Leerlingnummer kolom"), 0, 0)
        mapper.addWidget(self.student_number_column, 0, 1)
        mapper.addWidget(QLabel("Naamkolom"), 1, 0)
        mapper.addWidget(self.student_name_column, 1, 1)
        mapper.addWidget(QLabel("Statuskolom"), 2, 0)
        mapper.addWidget(self.status_column, 2, 1)
        layout.addLayout(mapper)
        layout.addWidget(QLabel("Koppel vraagkolommen (automatisch voorgesteld, handmatig aanpasbaar):"))
        self.question_map = QTableWidget()
        self.question_map.setColumnCount(3)
        self.question_map.setHorizontalHeaderLabels(["Vraag", "Max", "Kolom in bestand"])
        self.question_map.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.question_map.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.question_map.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.question_map.verticalHeader().setVisible(False)
        self.question_map.setMinimumHeight(180)
        layout.addWidget(self.question_map, 1)
        controls = QHBoxLayout()
        self.check_button = QPushButton("Import controleren")
        self.check_button.clicked.connect(self.check_import)
        controls.addWidget(self.check_button)
        controls.addStretch()
        layout.addLayout(controls)
        self.summary = QLabel("Kies eerst een Excel- of CSV-bestand.")
        self.summary.setObjectName("panel")
        layout.addWidget(self.summary)
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setMinimumHeight(220)
        layout.addWidget(self.preview_table, 1)
        scroll.setWidget(content)
        outer_layout.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Definitief importeren")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer_layout.addWidget(buttons)
        self.save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.save_button.setEnabled(False)
        self.fill_mapping_options()
        self.populate_question_rows({})

    def fill_mapping_options(self) -> None:
        options = ["Niet koppelen"] + self.headers
        for combo in (self.student_number_column, self.student_name_column, self.status_column):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(options)
            if current:
                index = combo.findText(current)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def populate_question_rows(self, suggestion: dict[str, object]) -> None:
        question_columns = dict(suggestion.get("questions", {}))
        self.question_map.setRowCount(len(self.questions))
        for row, question in enumerate(self.questions):
            self.question_map.setItem(row, 0, item(question["label"]))
            self.question_map.item(row, 0).setData(Qt.ItemDataRole.UserRole, question["id"])
            self.question_map.setItem(row, 1, item(f'{float(question["maximum_score"]):g}'))
            combo = QComboBox()
            combo.addItem("Niet koppelen")
            combo.addItems(self.headers)
            suggested = question_columns.get(question["id"])
            if suggested:
                index = combo.findText(str(suggested))
                if index >= 0:
                    combo.setCurrentIndex(index)
            self.question_map.setCellWidget(row, 2, combo)

    def choose_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Resultaatbestand kiezen", "", "Bestanden (*.xlsx *.xlsm *.csv)"
        )
        if not selected:
            return
        try:
            self.headers, self.rows = read_results_rows(Path(selected))
        except ResultImportError as error:
            QMessageBox.warning(self, "Importbestand niet gelezen", str(error))
            return
        self.file_path.setText(selected)
        suggestion = suggest_results_mapping(self.headers, self.questions)
        self.fill_mapping_options()
        for key, combo in (
            ("student_number", self.student_number_column),
            ("student_name", self.student_name_column),
            ("status", self.status_column),
        ):
            value = suggestion.get(key)
            if value:
                index = combo.findText(str(value))
                if index >= 0:
                    combo.setCurrentIndex(index)
        self.populate_question_rows(suggestion)
        self.preview_ready = False
        self.fuzzy_overrides = {}
        self.save_button.setEnabled(False)
        self.summary.setText(f"Bestand geladen: {len(self.rows)} rijen. Controleer de kolomkoppeling en klik op Import controleren.")

    def mapping(self) -> dict[str, object]:
        mapping = {
            "student_number": self.student_number_column.currentText() if self.student_number_column.currentIndex() > 0 else None,
            "student_name": self.student_name_column.currentText() if self.student_name_column.currentIndex() > 0 else None,
            "status": self.status_column.currentText() if self.status_column.currentIndex() > 0 else None,
            "questions": {},
            "fuzzy_overrides": dict(self.fuzzy_overrides),
        }
        for row in range(self.question_map.rowCount()):
            question_id = self.question_map.item(row, 0).data(Qt.ItemDataRole.UserRole)
            combo = self.question_map.cellWidget(row, 2)
            mapping["questions"][question_id] = combo.currentText() if combo.currentIndex() > 0 else None
        return mapping

    def check_import(self) -> None:
        if not self.rows:
            QMessageBox.warning(self, "Geen bestand", "Kies eerst een Excel- of CSV-bestand.")
            return
        mapping = self.mapping()
        if not mapping["student_number"] and not mapping["student_name"]:
            QMessageBox.warning(self, "Leerlingkoppeling ontbreekt", "Koppel minimaal leerlingnummer of naam.")
            return
        try:
            checked = preview_results_import(self.database, self.test_id, self.rows, mapping)
        except Exception as error:
            QMessageBox.warning(self, "Importcontrole mislukt", str(error))
            return
        preview_rows = checked["preview_rows"]
        columns = ["leerling"] + [question["label"] for question in self.questions if mapping["questions"].get(question["id"])]
        self.preview_table.setColumnCount(len(columns))
        self.preview_table.setHorizontalHeaderLabels(columns)
        self.preview_table.setRowCount(len(preview_rows))
        for row_number, preview_row in enumerate(preview_rows):
            for column_number, column_name in enumerate(columns):
                self.preview_table.setItem(row_number, column_number, item(preview_row.get(column_name, "")))
        self.preview_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.summary.setText(
            f"Controle: {checked['matched_rows']} rijen gekoppeld, {checked['score_cells']} scorecellen gevonden, "
            f"{checked['unknown_students']} rijen zonder leerlingmatch."
        )
        invalid_statuses = checked.get("invalid_statuses", [])
        if invalid_statuses:
            lines = []
            for entry in invalid_statuses[:20]:
                lines.append(
                    f"- rij {entry.get('row')}: {entry.get('student')} heeft status '{entry.get('status')}'"
                )
            extra = ""
            if len(invalid_statuses) > 20:
                extra = f"\n... en {len(invalid_statuses) - 20} meer."
            self.summary.setText(
                self.summary.text()
                + f" {len(invalid_statuses)} onbekende statuswaarde(n) gevonden; importeren is nog geblokkeerd."
            )
            QMessageBox.warning(
                self,
                "Onbekende status gevonden",
                "De statuskolom bevat waarden die ToetsVizier niet kent. Pas deze eerst aan of koppel de statuskolom niet.\n\n"
                + "\n".join(lines)
                + extra,
            )
            self.preview_ready = False
            self.save_button.setEnabled(False)
            return
        unmatched = checked.get("unmatched_students", [])
        if unmatched:
            preview_names = "\n".join(f"- {name}" for name in unmatched[:20])
            extra = ""
            if len(unmatched) > 20:
                extra = f"\n... en {len(unmatched) - 20} meer."
            QMessageBox.information(
                self,
                "Geen leerlingmatch gevonden",
                "Voor de volgende leerling(en) is geen match gevonden:\n\n"
                f"{preview_names}{extra}",
            )
        self.fuzzy_overrides = {}
        fuzzy_matches = checked.get("fuzzy_matches", [])
        if fuzzy_matches:
            unique_pairs = []
            seen = set()
            for entry in fuzzy_matches:
                key = (entry["input"].strip().lower(), entry["matched_to"].strip().lower())
                if key in seen:
                    continue
                seen.add(key)
                unique_pairs.append(entry)
            for entry in unique_pairs:
                answer = QMessageBox.question(
                    self,
                    "Fuzzy koppeling bevestigen",
                    f"Geen exacte naammatch:\n\n'{entry['input']}'\n\nVoorstel koppeling:\n'{entry['matched_to']}'\n\n"
                    "Wil je deze koppeling gebruiken?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if answer == QMessageBox.StandardButton.Yes:
                    self.fuzzy_overrides[entry["input"].strip().lower()] = entry["matched_to"].strip().lower()
            rejected = len(unique_pairs) - len(self.fuzzy_overrides)
            self.summary.setText(
                self.summary.text()
                + f" Fuzzy bevestigd: {len(self.fuzzy_overrides)}"
                + (f", afgewezen: {rejected}." if rejected else ".")
            )
        self.preview_ready = True
        self.save_button.setEnabled(True)

    def accept(self) -> None:
        if not self.preview_ready:
            QMessageBox.warning(self, "Controle ontbreekt", "Voer eerst een importcontrole uit.")
            return
        super().accept()


class MultipleChoiceKeysDialog(QDialog):
    def __init__(self, questions: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Antwoordsleutel meerkeuzevragen beheren")
        fit_to_available_screen(self, 820, 620)
        self.rows: list[dict] = []
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Beheer hier per meerkeuzevraag de antwoordsleutel en eventuele correctie op nakijken."
        )
        intro.setWordWrap(True)
        intro.setObjectName("panel")
        layout.addWidget(intro)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        for question in questions:
            frame = QFrame()
            frame.setObjectName("panel")
            frame_layout = QFormLayout(frame)
            frame_layout.addRow(QLabel(f"<b>Vraag {question['label']}</b>"))
            key = QLineEdit(str(question.get("multiple_choice_answer") or ""))
            key.setMaxLength(1)
            key.setPlaceholderText("Bijv. A")
            frame_layout.addRow("Goede antwoordoptie", key)
            correction = QCheckBox("Correctie op nakijken")
            correction.setChecked(bool(question.get("multiple_choice_correction_enabled")))
            frame_layout.addRow("", correction)
            neutralize = QRadioButton("Vraag neutraliseren (alles goedtellen)")
            extra = QRadioButton("Andere optie(s) ook goedtellen")
            mode = str(question.get("multiple_choice_correction_mode") or "none")
            if mode == "neutralize":
                neutralize.setChecked(True)
            elif mode == "extra":
                extra.setChecked(True)
            frame_layout.addRow("", neutralize)
            frame_layout.addRow("", extra)
            extra_options = QLineEdit(str(question.get("multiple_choice_extra_answers") or ""))
            extra_options.setPlaceholderText("Bijvoorbeeld: B,D,F")
            frame_layout.addRow("Extra goede opties", extra_options)

            def update_controls() -> None:
                enabled = correction.isChecked()
                if enabled and not neutralize.isChecked() and not extra.isChecked():
                    neutralize.setChecked(True)
                neutralize.setEnabled(enabled)
                extra.setEnabled(enabled)
                extra_options.setEnabled(enabled and extra.isChecked())

            correction.toggled.connect(update_controls)
            extra.toggled.connect(update_controls)
            update_controls()
            content_layout.addWidget(frame)
            self.rows.append(
                {
                    "id": question["id"],
                    "label": question["label"],
                    "key": key,
                    "correction": correction,
                    "neutralize": neutralize,
                    "extra": extra,
                    "extra_options": extra_options,
                }
            )
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def updates(self) -> list[dict]:
        output: list[dict] = []
        for row in self.rows:
            key = normalize_multiple_choice_response(row["key"].text())
            if key is None:
                raise ResultValidationError(f"Vul een geldige antwoordsleutel in voor vraag {row['label']}.")
            correction_enabled = row["correction"].isChecked()
            mode = "none"
            extras = ""
            if correction_enabled:
                if row["neutralize"].isChecked():
                    mode = "neutralize"
                elif row["extra"].isChecked():
                    mode = "extra"
                    options = normalize_multiple_choice_option_list(row["extra_options"].text())
                    options = [option for option in options if option != key]
                    if not options:
                        raise ResultValidationError(
                            f"Voer minimaal een extra optie in voor vraag {row['label']}."
                        )
                    extras = ",".join(options)
            output.append(
                {
                    "id": row["id"],
                    "answer": key,
                    "correction_enabled": int(correction_enabled),
                    "correction_mode": mode,
                    "extra_answers": extras,
                }
            )
        return output


class ResultsPage(Page):
    SCORE_START_COLUMN = 3
    FILTER_ALL_STATUSES = "__all__"
    FILTER_MADE = "gemaakt"
    FILTER_NOT_MADE = "__not_made__"

    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        self.questions: list[dict] = []
        self.students: list[dict] = []
        self.all_students: list[dict] = []
        self.loading = False
        self.quick_entry_possible = False
        self.active_student_row = -1
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)
        title = QLabel("Resultateninvoer")
        title.setObjectName("pageTitle")
        self.test = QComboBox()
        self.test.setMinimumWidth(260)
        self.test.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.test.currentIndexChanged.connect(self.refresh_scores)
        self.level_filter = QComboBox()
        self.level_filter.setMinimumWidth(140)
        self.level_filter.currentIndexChanged.connect(self.refresh)
        self.grade_filter = QComboBox()
        self.grade_filter.setMinimumWidth(140)
        self.grade_filter.currentIndexChanged.connect(self.refresh)
        self.direction = QComboBox()
        self.direction.setMinimumWidth(210)
        self.direction.setMaximumWidth(250)
        self.direction.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.direction.addItem("Per leerling (horizontaal)", "horizontal")
        self.direction.addItem("Per vraag (verticaal)", "vertical")
        self.direction.currentIndexChanged.connect(self.update_vertical_direction_visibility)
        self.vertical_direction = QComboBox()
        self.vertical_direction.setMinimumWidth(140)
        self.vertical_direction.setMaximumWidth(180)
        self.vertical_direction.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.vertical_direction.addItem("Omlaag", "down")
        self.vertical_direction.addItem("Omhoog", "up")
        self._large_vertical_direction: QComboBox | None = None
        self.half_points = QCheckBox("Halve punten mogelijk")
        self.half_points.setMinimumWidth(170)
        self.half_points.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.half_points.setChecked(False)
        self.half_points.toggled.connect(self.update_summary)
        self.class_filter = QComboBox()
        self.class_filter.setMinimumWidth(160)
        self.class_filter.setMaximumWidth(220)
        self.class_filter.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.class_filter.currentIndexChanged.connect(self.refresh_scores)
        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(170)
        self.status_filter.setMaximumWidth(220)
        self.status_filter.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.status_filter.addItem("Alle statussen", self.FILTER_ALL_STATUSES)
        self.status_filter.addItem("Gemaakt", self.FILTER_MADE)
        self.status_filter.addItem("Alle niet gemaakte statussen", self.FILTER_NOT_MADE)
        self.status_filter.setCurrentIndex(0)
        self.status_filter.currentIndexChanged.connect(self.refresh_scores)
        import_button = compact_action_button(
            set_button_role(QPushButton("Scores importeren"), "secondary"),
            "Scores importeren uit Excel of CSV.",
            150,
        )
        import_button.clicked.connect(self.import_results)
        export_button = compact_action_button(
            set_button_role(QPushButton("Scores exporteren"), "secondary"),
            "Scores per leerling en per vraag exporteren naar Excel.",
            150,
        )
        export_button.clicked.connect(self.export_scores)
        manage_keys_button = compact_action_button(
            set_button_role(QPushButton("Meerkeuzesleutel bewerken"), "secondary"),
            "Antwoordsleutels van meerkeuzevragen beheren, vragen neutraliseren of extra opties goedtellen.",
            210,
        )
        manage_keys_button.clicked.connect(self.manage_multiple_choice_keys)

        layout.addWidget(
            make_page_header(
                "Resultateninvoer",
                "Voer scores in per leerling of per vraag. Niet-gemaakte rijen worden automatisch vergrendeld.",
                [import_button, export_button, manage_keys_button],
            )
        )

        self.filter_card = make_responsive_filter_card(
            "Filter en toetskeuze",
            [
                ("Niveau", self.level_filter),
                ("Jaarlaag", self.grade_filter),
                ("Toets", self.test),
                ("Klas/groep", self.class_filter),
                ("Status", self.status_filter),
                ("Invoerrichting", self.direction),
                ("Verticaal", self.vertical_direction),
                ("Opties", self.half_points),
            ],
            minimum_field_width=220,
            maximum_columns=4,
        )
        layout.addWidget(self.filter_card)
        self.vertical_direction_field = self.vertical_direction.parentWidget()
        self.update_vertical_direction_visibility()
        self.summary = QLabel()
        self.summary.setStyleSheet("font-weight:600; color:#071f42;")
        self.empty_state = make_empty_state(
            "Kies eerst een toets",
            "Selecteer hierboven een toets om scores in te voeren. Daarna verschijnen automatisch de leerlingen, "
            "vragen, statussen en totaalscores.",
        )
        layout.addWidget(self.empty_state)
        self.score_panel = QFrame()
        self.score_panel.setObjectName("panel")
        self.score_layout = QVBoxLayout(self.score_panel)
        self.score_layout.setContentsMargins(12, 12, 12, 12)
        self.score_layout.setSpacing(10)
        score_header = QHBoxLayout()
        score_header.setContentsMargins(0, 0, 0, 0)
        score_header.setSpacing(8)
        score_header.addWidget(self.summary, 1, Qt.AlignmentFlag.AlignVCenter)
        self.large_input_button = compact_action_button(
            set_button_role(QPushButton("Groot invoerscherm"), "secondary"),
            "Open dezelfde scoretabel in een groot venster voor kleine schermen of brede toetsen.",
            170,
        )
        self.large_input_button.clicked.connect(self.open_large_input_dialog)
        header_row_height = self.large_input_button.height()
        self.summary.setMinimumHeight(header_row_height)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        score_header.addWidget(self.large_input_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.score_layout.addLayout(score_header)
        self.summary.setVisible(False)
        self.table = QTableWidget()
        self.table.setVisible(False)
        self.table.setMinimumHeight(360)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.itemChanged.connect(self.score_changed)
        self.table.currentCellChanged.connect(self.current_score_cell_changed)
        self.table.installEventFilter(self)
        self.score_layout.addWidget(self.table)
        self.score_panel.setVisible(False)
        self.score_host = QWidget()
        self.score_host_layout = QVBoxLayout(self.score_host)
        self.score_host_layout.setContentsMargins(0, 0, 0, 0)
        self.score_host_layout.setSpacing(0)
        self.score_host_layout.addWidget(self.score_panel)
        layout.addWidget(self.score_host)
        help_text = QLabel(
            "Voer scores in en druk op Enter. Als alle vragen maximaal 9 punten hebben en "
            "'Halve punten mogelijk' op nee staat, springt de invoer direct zonder Enter door. "
            "Een score moet tussen 0 en de maximumscore van de vraag liggen. "
            "Bij een niet-gemaakte status wordt de rij vergrendeld en tellen die velden niet mee als open invoer. "
            "'Niet analyseren' houdt scores bewaard maar sluit de leerling uit van analyses. "
            "Gebruik in een scorecel de letter N als een leerling alleen die vraag niet heeft gemaakt; "
            "dit telt als 0 punten en blijft in de analyse herkenbaar als N-score."
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("panel")
        layout.addWidget(help_text)
        self.refresh()

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Resultateninvoer",
            "intro": "Hier legt u vast wat leerlingen per vraag hebben gescoord. Deze gegevens vormen de basis voor cijfers en analyses.",
            "steps": [
                {
                    "title": "Een toets en leerlingen tonen",
                    "text": "Selecteer eerst niveau, jaarlaag en vervolgens de toets. Daarna kunt u met groep en status bepalen welke leerlingen in beeld staan.",
                    "action": "Kies bij 'Toets' de afgenomen toets en laat voor de eerste controle 'Alle statussen' geselecteerd.",
                    "tip": "Dit scherm opent steeds zonder geselecteerde toets om invoer bij de verkeerde toets te voorkomen.",
                },
                {
                    "title": "Scores handmatig invoeren",
                    "text": "U kunt invoeren per leerling of per vraag. Een getal mag niet lager zijn dan nul en niet hoger dan het maximum van de vraag.",
                    "action": "Kies de invoerrichting die bij uw nakijkwerk past en typ de scores in de cellen. Met Delete wist u een score.",
                    "tip": "Typ N wanneer een leerling een losse vraag niet heeft gemaakt. Dit telt als 0 punten, maar blijft zichtbaar als bewuste N-invoer.",
                },
                {
                    "title": "Groot invoerscherm gebruiken",
                    "text": "Op een klein scherm of bij veel vragen kunt u dezelfde scoretabel tijdelijk in een vergroot venster openen.",
                    "action": "Klik boven de tabel op 'Groot invoerscherm'. Sluit het venster met de knop 'Vergroot venster sluiten' wanneer u klaar bent.",
                    "tip": "Dit is geen kopie van de tabel: alles wat u in het grote venster invoert, wordt direct op dezelfde manier opgeslagen.",
                },
                {
                    "title": "Status van een leerling",
                    "text": "Standaard staat een leerling op 'gemaakt'. Bij absentie, ziekte, vrijstelling, onregelmatigheid, 'niet gemaakt' of 'niet analyseren' gebruikt u een andere status.",
                    "action": "Wijzig de status in de rij wanneer een leerling de toets niet geldig heeft gemaakt of buiten de analyse moet blijven.",
                    "tip": "Bij 'niet analyseren' blijven scores bewaard, maar de leerling telt niet mee in analyses of open invoer.",
                },
                {
                    "title": "Scores importeren uit Excel",
                    "text": "De importwizard probeert namen of leerlingnummers en vraagkolommen automatisch te koppelen. Bij een naam die slechts ongeveer overeenkomt, vraagt het programma om bevestiging.",
                    "action": "Klik op 'Scores importeren', controleer de voorgestelde koppelingen en importeer pas daarna definitief.",
                    "tip": "Let in de controle vooral op leerlingen zonder match en op de gekoppelde vraagkolommen.",
                },
                {
                    "title": "Scores exporteren naar Excel",
                    "text": "U kunt het invoerblad exporteren als Excelbestand. Elke rij is een leerling en elke vraag krijgt een eigen scorekolom.",
                    "action": "Klik op 'Scores exporteren' en kies waar het Excelbestand moet worden opgeslagen.",
                    "tip": "De eerste kolommen blijven leerlingnummer, leerling, groep en status; daarna volgen de vragen in dezelfde volgorde als in de toetsmatrijs.",
                },
                {
                    "title": "Meerkeuze invoeren en corrigeren",
                    "text": "Voor een meerkeuzevraag voert u de letter van het antwoord van de leerling in. Goed krijgt automatisch de volledige maximumscore, fout nul punten. Typ N als de leerling geen antwoord op deze meerkeuzevraag heeft gegeven.",
                    "action": "Gebruik 'MC-sleutels' voor een gewijzigde sleutel, neutraliseren of het goed rekenen van extra antwoordopties.",
                    "tip": "N telt als 0 punten, maar wordt in de meerkeuzeanalyse niet als antwoordalternatief A/B/C/... meegenomen.",
                },
                {
                    "title": "Controleren of u klaar bent",
                    "text": "Een volledig ingevulde rij krijgt een groene totaalscore. De samenvatting boven de tabel meldt hoeveel invoervelden nog ontbreken.",
                    "action": "Controleer aan het eind alle statussen en of elke gemaakte toets een complete rij heeft.",
                    "tip": "Pas na complete resultaten is normering en toetsanalyse betrouwbaar.",
                },
            ],
        }

    def refresh(self) -> None:
        selected_id = self.test.currentData()
        selected_level = self.level_filter.currentData()
        selected_grade = self.grade_filter.currentData()
        self.level_filter.blockSignals(True)
        self.level_filter.clear()
        self.level_filter.addItem("Alle niveaus", None)
        self.grade_filter.blockSignals(True)
        self.grade_filter.clear()
        self.grade_filter.addItem("Alle jaarlagen", None)
        tests_for_filters = self.database.rows(
            "SELECT DISTINCT COALESCE(level, '') AS level, COALESCE(grade_year, '') AS grade_year "
            "FROM tests WHERE school_year_id=?",
            (self.year_id,),
        ) if self.year_id else []
        levels = sorted({row["level"] for row in tests_for_filters if row["level"]}, key=str.lower)
        grades = sorted({row["grade_year"] for row in tests_for_filters if row["grade_year"]}, key=str.lower)
        for level in levels:
            self.level_filter.addItem(level, level)
        for grade in grades:
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
        self.class_filter.blockSignals(True)
        self.class_filter.clear()
        self.class_filter.addItem("Alle groepen", None)
        self.class_filter.blockSignals(False)
        self.refresh_scores()

    def on_activated(self) -> None:
        self.test.blockSignals(True)
        if self.test.count():
            self.test.setCurrentIndex(0)
        self.test.blockSignals(False)
        self.refresh_scores()

    def select_test(self, test_id: int) -> None:
        for combo in (self.level_filter, self.grade_filter):
            combo.blockSignals(True)
            if combo.count():
                combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.refresh()
        index = self.test.findData(test_id)
        if index >= 0:
            self.test.setCurrentIndex(index)
        else:
            QMessageBox.warning(
                self,
                "Toets niet gevonden",
                "De geselecteerde toets kon niet in resultateninvoer worden geopend. Controleer het schooljaar.",
            )

    def update_entry_visibility(self) -> None:
        has_test = self.test.currentData() is not None
        if hasattr(self, "empty_state"):
            self.empty_state.setVisible(not has_test)
        if hasattr(self, "score_panel"):
            self.score_panel.setVisible(has_test)
        if hasattr(self, "summary"):
            self.summary.setVisible(has_test)
        if hasattr(self, "table"):
            self.table.setVisible(has_test)

    def update_vertical_direction_visibility(self, _index: int | None = None) -> None:
        visible = self.direction.currentData() == "vertical"
        field = getattr(self, "vertical_direction_field", None)
        if field is not None:
            field.setVisible(visible)
        self.vertical_direction.setVisible(visible)

    def set_vertical_entry_direction(self, value: str) -> None:
        for combo in (self.vertical_direction, self._large_vertical_direction):
            if combo is None:
                continue
            index = combo.findData(value)
            if index < 0 or combo.currentIndex() == index:
                continue
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def open_large_input_dialog(self) -> None:
        if self.test.currentData() is None or not self.score_panel.isVisible():
            QMessageBox.information(
                self,
                "Geen toets gekozen",
                "Kies eerst een toets. Daarna kunt u de scoretabel in een groot venster openen.",
            )
            return
        if getattr(self, "_large_input_dialog_open", False):
            return
        self._large_input_dialog_open = True
        dialog = QDialog(self)
        dialog.setWindowTitle("Groot invoerscherm resultaten")
        fit_to_available_screen(dialog, 1500, 900, margin=32)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(14, 14, 14, 14)
        dialog_layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(10)
        heading = QLabel(
            "<b>Groot invoerscherm resultaten</b><br>"
            "U werkt hieronder in dezelfde scoretabel als op de normale pagina. Ingevoerde scores worden direct opgeslagen."
        )
        heading.setWordWrap(True)
        header_row.addWidget(heading, 1)
        large_direction = QComboBox()
        large_direction.addItem("Per leerling (horizontaal)", "horizontal")
        large_direction.addItem("Per vraag (verticaal)", "vertical")
        large_direction.setMinimumWidth(220)
        large_direction.setMaximumWidth(280)
        large_vertical_direction = QComboBox()
        large_vertical_direction.addItem("Omlaag", "down")
        large_vertical_direction.addItem("Omhoog", "up")
        large_vertical_direction.setMinimumWidth(120)
        large_vertical_direction.setMaximumWidth(150)
        self._large_vertical_direction = large_vertical_direction
        large_direction_index = large_direction.findData(self.direction.currentData())
        if large_direction_index >= 0:
            large_direction.setCurrentIndex(large_direction_index)
        large_vertical_index = large_vertical_direction.findData(self.vertical_direction.currentData())
        if large_vertical_index >= 0:
            large_vertical_direction.setCurrentIndex(large_vertical_index)

        def sync_large_direction(_index: int) -> None:
            direction_index = self.direction.findData(large_direction.currentData())
            if direction_index >= 0:
                self.direction.setCurrentIndex(direction_index)
            large_vertical_field.setVisible(large_direction.currentData() == "vertical")

        def sync_large_vertical_direction(_index: int) -> None:
            self.set_vertical_entry_direction(str(large_vertical_direction.currentData()))

        large_direction.currentIndexChanged.connect(sync_large_direction)
        header_row.addWidget(make_filter_field("Invoerrichting", large_direction))
        large_vertical_field = make_filter_field("Verticaal", large_vertical_direction)
        large_vertical_field.setVisible(large_direction.currentData() == "vertical")
        large_vertical_direction.currentIndexChanged.connect(sync_large_vertical_direction)
        header_row.addWidget(large_vertical_field)
        close_button = compact_action_button(
            set_button_role(QPushButton("Vergroot venster sluiten"), "primary"),
            "Sluit het vergrote invoerscherm en plaats de tabel terug op de gewone pagina.",
            210,
        )
        close_button.clicked.connect(dialog.accept)
        header_row.addWidget(close_button)
        dialog_layout.addLayout(header_row)
        dialog_layout.addWidget(
            make_info_banner(
                "Tip: gebruik dit venster wanneer een toets veel vragen heeft of wanneer het gewone scherm te weinig ruimte biedt.",
                "info",
            )
        )

        placeholder = make_info_banner(
            "Het invoerscherm staat open in een vergroot venster. Sluit dat venster om de tabel hier terug te plaatsen.",
            "info",
        )
        self.score_host_layout.removeWidget(self.score_panel)
        self.score_panel.setParent(dialog)
        dialog_layout.addWidget(self.score_panel, 1)
        self.score_host_layout.addWidget(placeholder)
        self.score_panel.setVisible(True)
        self.summary.setVisible(True)
        self.table.setVisible(True)
        self.large_input_button.setVisible(False)

        try:
            dialog.setWindowState(dialog.windowState() | Qt.WindowState.WindowMaximized)
            dialog.exec()
        finally:
            dialog_layout.removeWidget(self.score_panel)
            self.score_panel.setParent(self.score_host)
            self.score_host_layout.removeWidget(placeholder)
            placeholder.deleteLater()
            self.score_host_layout.addWidget(self.score_panel)
            self.large_input_button.setVisible(True)
            self._large_vertical_direction = None
            self._large_input_dialog_open = False
            self.update_entry_visibility()

    def refresh_scores(self) -> None:
        self.update_entry_visibility()
        test_id = self.test.currentData()
        selected_class = self.class_filter.currentData()
        selected_status_filter = self.status_filter.currentData()
        self.loading = True
        self.active_student_row = -1
        self.table.clear()
        self.questions = test_questions(self.database, test_id) if test_id is not None else []
        self.all_students = test_students(self.database, test_id) if test_id is not None else []
        class_names = sorted(
            {name for student in self.all_students for name in self.group_names(student.get("groups", ""))},
            key=str.lower,
        )
        self.class_filter.blockSignals(True)
        self.class_filter.clear()
        self.class_filter.addItem("Alle groepen", None)
        for class_name in class_names:
            self.class_filter.addItem(class_name, class_name)
        if selected_class is not None:
            index = self.class_filter.findData(selected_class)
            if index >= 0:
                self.class_filter.setCurrentIndex(index)
        self.class_filter.blockSignals(False)
        self.students = self.filtered_students(
            self.all_students,
            self.class_filter.currentData(),
            selected_status_filter,
            test_id,
        )
        self.quick_entry_possible = bool(self.questions) and max(
            float(question["maximum_score"]) for question in self.questions
        ) <= 9
        headers = ["Leerling", "Groep", "Status"]
        for question in self.questions:
            maximum = float(question["maximum_score"])
            if bool(question.get("is_multiple_choice")):
                answer_key = str(question.get("multiple_choice_answer") or "").strip().upper()
                suffix = answer_key if answer_key else "sleutel ontbreekt"
                correction_enabled = bool(question.get("multiple_choice_correction_enabled"))
                correction_mode = str(question.get("multiple_choice_correction_mode") or "none")
                if correction_enabled and correction_mode == "neutralize":
                    suffix = f"{suffix} | geneutraliseerd"
                elif correction_enabled and correction_mode == "extra":
                    suffix = f"{suffix} | extra opties"
                headers.append(f'{question["label"]}\n/{maximum:g} | {suffix}')
            else:
                headers.append(f'{question["label"]}\n/{maximum:g}')
        headers.append("Totaal")
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.verticalHeader().setMinimumSectionSize(34)
        self.table.setAlternatingRowColors(True)
        self.table.setRowCount(len(self.students))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for column in range(self.SCORE_START_COLUMN, self.SCORE_START_COLUMN + len(self.questions)):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            question = self.questions[column - self.SCORE_START_COLUMN]
            self.table.setColumnWidth(column, 84 if bool(question.get("is_multiple_choice")) else 64)
        total_column = self.SCORE_START_COLUMN + len(self.questions)
        self.table.horizontalHeader().setSectionResizeMode(total_column, QHeaderView.ResizeMode.ResizeToContents)
        attempts, scores, responses = stored_results(self.database, test_id) if test_id is not None else ({}, {}, {})
        for row_number, student in enumerate(self.students):
            name = item(student["display_name"])
            name.setData(Qt.ItemDataRole.UserRole, student["id"])
            self.table.setItem(row_number, 0, name)
            header_item = QTableWidgetItem(student["display_name"])
            header_item.setToolTip(student["display_name"])
            self.table.setVerticalHeaderItem(row_number, header_item)
            self.table.setItem(row_number, 1, item(student["groups"] or ""))
            status = CenteredComboBox()
            status.setObjectName("scoreStatusCombo")
            status.addItems(RESULT_STATUSES)
            status.setEditable(False)
            status.setFixedHeight(28)
            status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            status.setCurrentText(attempts.get(student["id"], {}).get("status", self.FILTER_MADE))
            status.setStyleSheet(self.status_combo_stylesheet(status.currentText()))
            status.setProperty("previous_status", status.currentText())
            status.currentTextChanged.connect(
                lambda value, student_id=student["id"], widget=status: self.status_changed(student_id, widget, value)
            )
            status_container = QWidget()
            status_layout = QHBoxLayout(status_container)
            status_layout.setContentsMargins(4, 0, 4, 0)
            status_layout.setSpacing(0)
            status.setMaximumWidth(190)
            status_layout.addStretch()
            status_layout.addWidget(status, 0, Qt.AlignmentFlag.AlignCenter)
            status_layout.addStretch()
            self.table.setCellWidget(row_number, 2, status_container)
            for offset, question in enumerate(self.questions):
                column = self.SCORE_START_COLUMN + offset
                stored = scores.get((student["id"], question["id"]))
                text = responses.get((student["id"], question["id"]), "") if bool(question.get("is_multiple_choice")) else ("" if stored is None else f"{stored:g}")
                score_cell = QTableWidgetItem(text)
                score_cell.setData(Qt.ItemDataRole.UserRole, text)
                score_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if bool(question.get("is_multiple_choice")):
                    score_cell.setToolTip(
                        "Voer één letter in (bijvoorbeeld A of E). "
                        "Het systeem kijkt automatisch na op basis van de antwoordsleutel."
                    )
                self.table.setItem(row_number, column, score_cell)
            total = attempts.get(student["id"], {}).get("total_score")
            total_cell = item("" if total is None else f"{float(total):g}")
            total_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_number, total_column, total_cell)
            self.apply_row_style(row_number)
        self.table.resizeColumnToContents(0)
        self.table.setColumnWidth(0, max(self.table.columnWidth(0), 180))
        self.table.setColumnHidden(0, True)
        header_width = max(
            180,
            min(
                360,
                max((self.table.fontMetrics().horizontalAdvance(student["display_name"]) for student in self.students), default=120)
                + 24,
            ),
        )
        self.table.verticalHeader().setFixedWidth(header_width)
        self.loading = False
        self.update_summary()

    def current_score_cell_changed(
        self,
        current_row: int,
        _current_column: int,
        previous_row: int,
        _previous_column: int,
    ) -> None:
        if self.loading:
            return
        if previous_row != current_row:
            self.set_student_name_active(previous_row, False)
        self.active_student_row = current_row
        self.set_student_name_active(current_row, True)

    def set_student_name_active(self, row: int, active: bool) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        for name_item in (self.table.verticalHeaderItem(row), self.table.item(row, 0)):
            if name_item is None:
                continue
            font = QFont(name_item.font())
            font.setBold(active)
            name_item.setFont(font)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.table and event.type() == QEvent.Type.KeyPress:
            row = self.table.currentRow()
            column = self.table.currentColumn()
            first = self.SCORE_START_COLUMN
            last = first + len(self.questions) - 1
            if row >= 0 and first <= column <= last and event.modifiers() == Qt.KeyboardModifier.NoModifier:
                if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                    cell = self.table.item(row, column)
                    if cell is not None:
                        cell.setText("")
                        return True
                offset = column - first
                question = self.questions[offset] if 0 <= offset < len(self.questions) else None
                if event.text().strip().casefold() == "n":
                    cell = self.table.item(row, column)
                    if cell is not None:
                        cell.setText("N")
                        return True
                if question and bool(question.get("is_multiple_choice")) and Qt.Key.Key_A <= event.key() <= Qt.Key.Key_Z:
                    cell = self.table.item(row, column)
                    if cell is not None:
                        cell.setText(chr(event.key()).upper())
                        return True
                if self.should_quick_advance() and Qt.Key.Key_0 <= event.key() <= Qt.Key.Key_9:
                    digit = chr(event.key())
                    cell = self.table.item(row, column)
                    if cell is not None:
                        cell.setText(digit)
                        return True
        return super().eventFilter(watched, event)

    def score_changed(self, cell: QTableWidgetItem) -> None:
        if self.loading:
            return
        offset = cell.column() - self.SCORE_START_COLUMN
        if offset < 0 or offset >= len(self.questions):
            return
        student_id = self.table.item(cell.row(), 0).data(Qt.ItemDataRole.UserRole)
        question = self.questions[offset]
        previous = str(cell.data(Qt.ItemDataRole.UserRole) or "")
        try:
            total = save_score(
                self.database,
                self.test.currentData(),
                student_id,
                question["id"],
                cell.text(),
                allow_half_points=self.half_points.isChecked(),
            )
        except ResultValidationError as error:
            self.loading = True
            cell.setText(previous)
            self.loading = False
            QMessageBox.warning(self, "Score niet opgeslagen", str(error))
            self.table.setCurrentCell(cell.row(), cell.column())
            return
        normalized = cell.text().strip().replace(",", ".")
        if is_not_made_score(normalized):
            normalized = "N"
        elif bool(question.get("is_multiple_choice")):
            normalized = normalized.upper()
        else:
            normalized = f"{float(normalized):g}" if normalized else ""
        self.loading = True
        cell.setText(normalized)
        cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        cell.setData(Qt.ItemDataRole.UserRole, normalized)
        total_column = self.SCORE_START_COLUMN + len(self.questions)
        total_cell = self.table.item(cell.row(), total_column)
        total_cell.setText("" if total is None else f"{total:g}")
        total_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        status = self.status_widget_for_row(cell.row())
        if normalized and status is not None and status.currentText() != "gemaakt":
            status.setCurrentText("gemaakt")
            status.setProperty("previous_status", "gemaakt")
        self.loading = False
        self.apply_row_style(cell.row())
        self.update_summary()
        if normalized and self.should_quick_advance():
            self.advance_after_entry(cell.row(), cell.column())

    def should_quick_advance(self) -> bool:
        return self.quick_entry_possible and not self.half_points.isChecked()

    @staticmethod
    def status_combo_stylesheet(status: str) -> str:
        if status == "gemaakt":
            return (
                "QComboBox#scoreStatusCombo {"
                "background: white; color: #071f42; border: 1px solid #d6dfec; border-radius: 6px; "
                "padding: 0 30px 0 6px; min-height: 24px; max-height: 24px;"
                "}"
                "QComboBox#scoreStatusCombo::drop-down {"
                "subcontrol-origin: padding; subcontrol-position: top right; width: 28px; "
                "border-left: 1px solid #d6dfec; border-top-right-radius: 6px; border-bottom-right-radius: 6px; "
                "background: #eef4fb;"
                "}"
                "QComboBox#scoreStatusCombo::down-arrow {"
                "image: none; width: 0px; height: 0px;"
                "}"
                "QComboBox#scoreStatusCombo QAbstractItemView {"
                "background: white; color: #071f42; border: 1px solid #d6dfec; "
                "selection-background-color: #d9e7ff; selection-color: #071f42;"
                "}"
            )
        if status == "niet analyseren":
            return (
                "QComboBox#scoreStatusCombo {"
                "background: #d9e2ee; color: #314766; border: 1px solid #b6c3d4; border-radius: 6px; "
                "padding: 0 30px 0 6px; min-height: 24px; max-height: 24px;"
                "}"
                "QComboBox#scoreStatusCombo::drop-down {"
                "subcontrol-origin: padding; subcontrol-position: top right; width: 28px; "
                "border-left: 1px solid #b6c3d4; border-top-right-radius: 6px; border-bottom-right-radius: 6px; "
                "background: #c8d2df;"
                "}"
                "QComboBox#scoreStatusCombo::down-arrow {"
                "image: none; width: 0px; height: 0px;"
                "}"
                "QComboBox#scoreStatusCombo QAbstractItemView {"
                "background: white; color: #071f42; border: 1px solid #d6dfec; "
                "selection-background-color: #d9e7ff; selection-color: #071f42;"
                "}"
            )
        return (
            "QComboBox#scoreStatusCombo {"
            "background: #6f1d1b; color: white; border: 1px solid #5a1715; border-radius: 6px; "
            "padding: 0 30px 0 6px; min-height: 24px; max-height: 24px;"
            "}"
            "QComboBox#scoreStatusCombo::drop-down {"
            "subcontrol-origin: padding; subcontrol-position: top right; width: 28px; "
            "border-left: 1px solid #8f2a28; border-top-right-radius: 6px; border-bottom-right-radius: 6px; "
            "background: #5f1716;"
            "}"
            "QComboBox#scoreStatusCombo::down-arrow {"
            "image: none; width: 0px; height: 0px;"
            "}"
            "QComboBox#scoreStatusCombo QAbstractItemView {"
            "background: white; color: #071f42; border: 1px solid #d6dfec; "
            "selection-background-color: #d9e7ff; selection-color: #071f42;"
            "}"
        )

    def status_widget_for_row(self, row: int) -> QComboBox | None:
        widget = self.table.cellWidget(row, 2)
        if isinstance(widget, QComboBox):
            return widget
        if isinstance(widget, QWidget):
            combo = widget.findChild(QComboBox)
            if isinstance(combo, QComboBox):
                return combo
        return None

    def row_for_status_widget(self, widget: QComboBox) -> int:
        for row in range(self.table.rowCount()):
            if self.status_widget_for_row(row) is widget:
                return row
        return -1

    def row_has_entered_scores(self, row: int) -> bool:
        first = self.SCORE_START_COLUMN
        last = first + len(self.questions)
        for column in range(first, last):
            cell = self.table.item(row, column)
            if cell is not None and cell.text().strip():
                return True
        return False

    def restore_status_widget(self, widget: QComboBox, status: str) -> None:
        self.loading = True
        widget.setCurrentText(status)
        widget.setProperty("previous_status", status)
        widget.setStyleSheet(self.status_combo_stylesheet(status))
        self.loading = False

    def status_changed(self, student_id: int, widget: QComboBox, status: str) -> None:
        if self.loading:
            return
        previous_status = str(widget.property("previous_status") or self.FILTER_MADE)
        row = self.row_for_status_widget(widget)
        if (
            status != self.FILTER_MADE
            and previous_status == self.FILTER_MADE
            and row >= 0
            and self.row_has_entered_scores(row)
            and status != "niet analyseren"
        ):
            answer = QMessageBox.question(
                self,
                "Scores verwijderen?",
                "Er zijn al scores ingevoerd voor deze leerling.\n\n"
                f"Als u de status wijzigt naar '{status}', worden deze scores verwijderd en telt de leerling "
                "niet mee als open invoer.\n\n"
                "Wilt u doorgaan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.restore_status_widget(widget, previous_status)
                return
        if status == "niet analyseren" and previous_status == self.FILTER_MADE and row >= 0 and self.row_has_entered_scores(row):
            QMessageBox.information(
                self,
                "Niet analyseren",
                "Deze leerling blijft bewaard met de ingevoerde scores, maar wordt niet meegenomen in analyses of open invoer.",
            )
        try:
            save_status(self.database, self.test.currentData(), student_id, status)
        except ResultValidationError as error:
            QMessageBox.warning(self, "Status niet opgeslagen", str(error))
            self.restore_status_widget(widget, previous_status)
            return
        widget.setProperty("previous_status", status)
        widget.setStyleSheet(self.status_combo_stylesheet(status))
        if row >= 0:
            self.refresh_row_data_from_database(row, student_id)
            self.apply_row_style(row)
        self.update_summary()

    def advance_after_entry(self, row: int, column: int) -> None:
        first = self.SCORE_START_COLUMN
        last = first + len(self.questions) - 1
        if last < first:
            return
        row_count = self.table.rowCount()
        direction = self.direction.currentData()
        vertical_direction = str(self.vertical_direction.currentData() or "down")
        next_row, next_column = row, column
        for _ in range(max(1, row_count * len(self.questions))):
            if direction == "vertical":
                if vertical_direction == "up":
                    next_row -= 1
                    if next_row < 0:
                        next_column += 1
                        if next_column > last:
                            return
                        next_row = 0
                        vertical_direction = "down"
                        self.set_vertical_entry_direction(vertical_direction)
                else:
                    next_row += 1
                    if next_row >= row_count:
                        next_column += 1
                        if next_column > last:
                            return
                        next_row = row_count - 1
                        vertical_direction = "up"
                        self.set_vertical_entry_direction(vertical_direction)
            else:
                next_column += 1
                if next_column > last:
                    next_column = first
                    next_row += 1
            if next_row >= row_count or next_column > last:
                return
            status_widget = self.status_widget_for_row(next_row)
            if isinstance(status_widget, QComboBox) and status_widget.currentText() != self.FILTER_MADE:
                continue
            next_cell = self.table.item(next_row, next_column)
            if next_cell is None:
                continue
            if not bool(next_cell.flags() & Qt.ItemFlag.ItemIsEditable):
                continue
            QTimer.singleShot(0, lambda r=next_row, c=next_column: self.activate_score_cell(r, c))
            return

    def activate_score_cell(self, row: int, column: int) -> None:
        self.table.setCurrentCell(row, column)
        self.table.setFocus()

    @staticmethod
    def group_names(raw_groups: str) -> list[str]:
        return [name.strip() for name in str(raw_groups).split(",") if name.strip()]

    def filtered_students(
        self,
        students: list[dict],
        selected_class: str | None,
        selected_status_filter: str | None,
        test_id: int | None,
    ) -> list[dict]:
        attempts, _, _ = stored_results(self.database, test_id) if test_id is not None else ({}, {}, {})
        filtered = []
        for student in students:
            if selected_class and selected_class not in self.group_names(student.get("groups", "")):
                continue
            current_status = attempts.get(student["id"], {}).get("status", self.FILTER_MADE)
            if selected_status_filter == self.FILTER_MADE and current_status != self.FILTER_MADE:
                continue
            if selected_status_filter == self.FILTER_NOT_MADE and current_status == self.FILTER_MADE:
                continue
            filtered.append(student)
        return filtered

    def update_summary(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            self.summary.setText("Kies een toets om scores in te voeren.")
            return
        if not self.questions:
            self.summary.setText("Deze toets heeft nog geen vragen in de toetsmatrijs.")
            return
        if not self.students:
            self.summary.setText("Aan de gekoppelde groepen van deze toets zijn nog geen leerlingen toegevoegd.")
            return
        attempts, scores, _ = stored_results(self.database, test_id)
        made_student_ids = {
            student["id"]
            for student in self.students
            if attempts.get(student["id"], {}).get("status", self.FILTER_MADE) == self.FILTER_MADE
        }
        entered = sum(1 for student_id, _question_id in scores if student_id in made_student_ids)
        needed_students = len(made_student_ids)
        expected = needed_students * len(self.questions)
        self.summary.setText(
            f"{len(self.students)} leerlingen | {len(self.questions)} vragen | "
            f"{entered} van {expected} scores ingevoerd | {max(0, expected - entered)} nog open | "
            f"halve punten: {'ja' if self.half_points.isChecked() else 'nee'}"
        )
        if any(bool(question.get("is_multiple_choice")) for question in self.questions):
            self.summary.setText(
                self.summary.text()
                + " | Meerkeuze: voer een antwoordletter in; N = vraag niet gemaakt, telt 0 punten."
            )

    def refresh_row_data_from_database(self, row: int, student_id: int) -> None:
        attempts, scores, responses = stored_results(self.database, self.test.currentData())
        for offset, question in enumerate(self.questions):
            column = self.SCORE_START_COLUMN + offset
            if bool(question.get("is_multiple_choice")):
                text = responses.get((student_id, question["id"]), "")
            else:
                value = scores.get((student_id, question["id"]))
                text = "" if value is None else f"{value:g}"
            cell = self.table.item(row, column)
            if cell is None:
                cell = QTableWidgetItem("")
                self.table.setItem(row, column, cell)
            self.loading = True
            cell.setText(text)
            cell.setData(Qt.ItemDataRole.UserRole, text)
            cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.loading = False
        total_column = self.SCORE_START_COLUMN + len(self.questions)
        total = attempts.get(student_id, {}).get("total_score")
        total_cell = self.table.item(row, total_column)
        if total_cell is None:
            total_cell = item("")
            self.table.setItem(row, total_column, total_cell)
        total_cell.setText("" if total is None else f"{float(total):g}")
        total_cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def apply_frozen_row_style(self, row: int) -> None:
        frozen_tables = [
            getattr(self, name, None)
            for name in (
                "frozen_table",
                "frozen_names",
                "name_table",
                "names_table",
                "student_name_table",
                "student_names_table",
                "student_table",
                "student_column_table",
                "frozen_column_table",
                "fixed_column_table",
                "locked_table",
                "locked_column_table",
                "left_table",
            )
        ]
        frozen_tables = [table for table in frozen_tables if isinstance(table, QTableWidget)]
        if not frozen_tables or row < 0 or row >= self.table.rowCount():
            return
        status_widget = self.status_widget_for_row(row)
        status = status_widget.currentText() if isinstance(status_widget, QComboBox) else ""
        locked = status and status != "gemaakt"
        if status == "niet analyseren":
            background = QColor("#d9e2ee")
            foreground = QColor("#314766")
        else:
            background = QColor("#7f1d1d") if locked else QColor("#eaf2ff")
            foreground = QColor("#ffffff") if locked else QColor("#071f42")
        row_height = self.table.rowHeight(row)
        for frozen_table in frozen_tables:
            if row >= frozen_table.rowCount():
                continue
            frozen_table.setRowHeight(row, row_height)
            for column in range(frozen_table.columnCount()):
                cell = frozen_table.item(row, column)
                if cell is None:
                    continue
                cell.setBackground(background)
                cell.setForeground(foreground)
                font = cell.font()
                font.setBold(True)
                cell.setFont(font)

    def apply_row_style(self, row: int) -> None:
        self.apply_frozen_row_style(row)
        status_widget = self.status_widget_for_row(row)
        if not isinstance(status_widget, QComboBox):
            return
        was_loading = self.loading
        self.loading = True
        self.table.blockSignals(True)
        try:
            status = status_widget.currentText()
            score_columns = range(self.SCORE_START_COLUMN, self.SCORE_START_COLUMN + len(self.questions))
            total_column = self.SCORE_START_COLUMN + len(self.questions)
            is_made = status == self.FILTER_MADE
            is_excluded = status == "niet analyseren"
            score_values = []
            for column in score_columns:
                cell = self.table.item(row, column)
                if cell is None:
                    continue
                offset = column - self.SCORE_START_COLUMN
                question = self.questions[offset] if 0 <= offset < len(self.questions) else None
                if is_made:
                    cell.setFlags(cell.flags() | Qt.ItemFlag.ItemIsEditable)
                    if question and bool(question.get("is_multiple_choice")) and cell.text().strip():
                        try:
                            raw_response = cell.text().strip()
                            response = "N" if is_not_made_score(raw_response) else normalize_multiple_choice_response(raw_response)
                            key = normalize_multiple_choice_response(str(question.get("multiple_choice_answer") or ""))
                            correction_enabled = bool(question.get("multiple_choice_correction_enabled"))
                            correction_mode = str(question.get("multiple_choice_correction_mode") or "none")
                            extra = set(
                                normalize_multiple_choice_option_list(
                                    str(question.get("multiple_choice_extra_answers") or "")
                                )
                            )
                        except ResultValidationError:
                            response = None
                            key = None
                            correction_enabled = False
                            correction_mode = "none"
                            extra = set()
                        is_correct = False
                        if response == "N":
                            cell.setBackground(QColor("#fff7e6"))
                            cell.setForeground(QColor("#8a5a00"))
                        elif response and key:
                            if correction_enabled and correction_mode == "neutralize":
                                is_correct = True
                            elif correction_enabled and correction_mode == "extra":
                                is_correct = response == key or response in extra
                            else:
                                is_correct = response == key
                        if response != "N" and is_correct:
                            cell.setBackground(QColor("#e8f7e8"))
                            cell.setForeground(QColor("#1f7a1f"))
                        elif response != "N":
                            cell.setBackground(QColor("#fdecec"))
                            cell.setForeground(QColor("#a02828"))
                    else:
                        cell.setBackground(QColor("white"))
                        cell.setForeground(QColor("#1f3352"))
                else:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    cell.setBackground(QColor("#6f1d1b"))
                    cell.setForeground(QColor("white"))
                score_values.append(cell.text().strip())
            if is_made:
                status_widget.setStyleSheet(self.status_combo_stylesheet("gemaakt"))
            elif is_excluded:
                status_widget.setStyleSheet(self.status_combo_stylesheet("niet analyseren"))
            else:
                status_widget.setStyleSheet(self.status_combo_stylesheet(status))
            for column in (0, 1, 2, total_column):
                cell = self.table.item(row, column)
                if cell is not None:
                    if is_made:
                        cell.setBackground(QColor("white"))
                        cell.setForeground(QColor("#1f3352"))
                    elif is_excluded:
                        cell.setBackground(QColor("#edf2f7"))
                        cell.setForeground(QColor("#314766"))
                    else:
                        cell.setBackground(QColor("#6f1d1b"))
                        cell.setForeground(QColor("white"))
            total_cell = self.table.item(row, total_column)
            if total_cell is None:
                return
            font = QFont(total_cell.font())
            complete = is_made and len(self.questions) > 0 and all(value != "" for value in score_values[: len(self.questions)])
            if complete:
                total_cell.setForeground(QColor("#1f7a1f"))
                total_cell.setBackground(QColor("#eaf9ea"))
                font.setBold(True)
            else:
                font.setBold(False)
                if is_made:
                    total_cell.setForeground(QColor("#1f3352"))
                    total_cell.setBackground(QColor("white"))
                elif is_excluded:
                    total_cell.setForeground(QColor("#314766"))
                    total_cell.setBackground(QColor("#edf2f7"))
            total_cell.setFont(font)
            self.set_student_name_active(row, row == self.active_student_row)
        finally:
            self.table.blockSignals(False)
            self.loading = was_loading

    def import_results(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            QMessageBox.information(self, "Geen toets", "Kies eerst een toets om resultaten te importeren.")
            return
        if not self.questions:
            QMessageBox.warning(self, "Geen vragen", "Deze toets heeft nog geen vragen in de toetsmatrijs.")
            return
        dialog = ResultsImportDialog(self.database, test_id, self.questions, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            summary = import_results(
                self.database,
                test_id,
                dialog.rows,
                dialog.mapping(),
                allow_half_points=self.half_points.isChecked(),
            )
        except Exception as error:
            QMessageBox.warning(self, "Import mislukt", str(error))
            return
        self.refresh_scores()
        QMessageBox.information(
            self,
            "Resultaten geimporteerd",
            f"Scores bijgewerkt: {summary.updated_scores}\n"
            f"Scores gewist: {summary.cleared_scores}\n"
            f"Statusupdates: {summary.status_updates}\n"
            f"Overgeslagen rijen: {summary.skipped_rows}",
        )

    def export_scores(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            QMessageBox.information(self, "Geen toets", "Kies eerst een toets om scores te exporteren.")
            return
        if not self.questions:
            QMessageBox.warning(self, "Geen vragen", "Deze toets heeft nog geen vragen in de toetsmatrijs.")
            return
        EXCEL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        suggested = EXCEL_EXPORT_DIR / f"{slug(self.test.currentText())}_scores.xlsx"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Scores opslaan als Excel",
            str(suggested),
            "Excelbestand (*.xlsx)",
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".xlsx"):
            file_name += ".xlsx"
        try:
            output = export_scores_xlsx(self.database, int(test_id), file_name)
        except ResultExportError as error:
            QMessageBox.warning(self, "Export mislukt", str(error))
            return
        except Exception as error:
            QMessageBox.warning(self, "Export mislukt", f"Het Excelbestand kon niet worden opgeslagen: {error}")
            return
        self.database.connection.execute(
            "INSERT INTO report_exports(report_type, test_id, file_path) VALUES(?, ?, ?)",
            ("scores_excel", test_id, str(output)),
        )
        self.database.connection.commit()
        QMessageBox.information(self, "Scores geexporteerd", f"Het Excelbestand is opgeslagen:\n{output}")

    def manage_multiple_choice_keys(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            QMessageBox.information(self, "Geen toets", "Kies eerst een toets.")
            return
        questions = [
            dict(row)
            for row in self.database.rows(
                "SELECT id, question_number || COALESCE(subquestion, '') AS label, multiple_choice_answer, "
                "multiple_choice_correction_enabled, multiple_choice_correction_mode, multiple_choice_extra_answers "
                f"FROM matrix_questions WHERE test_id=? AND is_multiple_choice=1 ORDER BY {QUESTION_ORDER_SQL}",
                (test_id,),
            )
        ]
        if not questions:
            QMessageBox.information(
                self,
                "Geen meerkeuzevragen",
                "Deze toets bevat nog geen vragen die als meerkeuze zijn gemarkeerd.",
            )
            return
        dialog = MultipleChoiceKeysDialog(questions, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updates = dialog.updates()
        except ResultValidationError as error:
            QMessageBox.warning(self, "Instellingen ongeldig", str(error))
            return
        changed = 0
        try:
            for update in updates:
                self.database.connection.execute(
                    "UPDATE matrix_questions SET multiple_choice_answer=?, "
                    "multiple_choice_correction_enabled=?, multiple_choice_correction_mode=?, "
                    "multiple_choice_extra_answers=?, updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=? AND test_id=?",
                    (
                        update["answer"],
                        update["correction_enabled"],
                        update["correction_mode"],
                        update["extra_answers"] or None,
                        update["id"],
                        test_id,
                    ),
                )
            self.database.connection.commit()
            for update in updates:
                changed += regrade_multiple_choice_question(self.database, test_id, update["id"])
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Niet opgeslagen", str(error))
            return
        self.refresh_scores()
        QMessageBox.information(
            self,
            "Antwoordsleutels bijgewerkt",
            f"Instellingen opgeslagen. {changed} score(s) opnieuw nagekeken.",
        )
