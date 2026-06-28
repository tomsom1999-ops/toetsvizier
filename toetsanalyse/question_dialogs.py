from __future__ import annotations

import json
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .database import SubjectDatabase
from .dialogs_base import FormDialog
from .question_bank import (
    QUESTION_BANK_STATUSES,
    load_active_question_properties,
    load_all_taxonomies,
    question_database_distinct_property_values,
)
from .results import ResultValidationError, normalize_multiple_choice_response
from .ui_helpers import configure_table, fit_to_available_screen, item, set_button_role


class QuestionDialog(FormDialog):
    def __init__(
        self, properties: list, taxonomies: list, question=None, values=None, taxonomy_values=None,
        parent: QWidget | None = None, default_number: str | None = None,
        subquestion_questions: list[dict] | None = None,
        subquestion_values: dict[int, dict[int, str]] | None = None,
        subquestion_taxonomy_values: dict[int, dict[int, int]] | None = None,
    ) -> None:
        super().__init__("Vraag bewerken" if question or subquestion_questions else "Vraag toevoegen", parent)
        if question is not None and not isinstance(question, dict):
            question = dict(question)
        self.properties = list(properties)
        self.taxonomies = list(taxonomies)
        self.subquestion_questions = [dict(row) for row in (subquestion_questions or [])]
        self.subquestion_values = subquestion_values or {}
        self.subquestion_taxonomy_values = subquestion_taxonomy_values or {}
        self.subquestion_row_widgets: list[dict[str, object]] = []
        self._rebuilding_subquestions = False
        self.property_widgets: dict[int, QWidget] = {}
        self.taxonomy_widgets: dict[int, QComboBox] = {}
        self.number = QLineEdit()
        if default_number:
            self.number.setText(default_number)
        self.subquestion = QLineEdit()
        self.maximum_score = QSpinBox()
        self.maximum_score.setRange(1, 1000)
        self.maximum_score.setValue(1)
        self.description = QLineEdit()
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 300)
        self.minutes.setSpecialValueText("Niet ingevuld")
        self.is_multiple_choice = QCheckBox("Deze vraag is meerkeuze (een antwoord goed)")
        self.multiple_choice_answer = QLineEdit()
        self.multiple_choice_answer.setMaxLength(1)
        self.multiple_choice_answer.setPlaceholderText("Bijvoorbeeld: A, B, C, D, E, ...")
        self.has_subquestions = QCheckBox("Deze vraag heeft subvragen")
        self.subquestion_count = QSpinBox()
        self.subquestion_count.setRange(1, 26)
        self.subquestion_count.setValue(max(2, len(self.subquestion_questions) or 2))
        self.single_question_panel = QFrame()
        self.single_question_panel.setObjectName("panel")
        self.single_question_layout = QVBoxLayout(self.single_question_panel)
        self.single_question_layout.setContentsMargins(10, 10, 10, 10)
        self.single_question_layout.setSpacing(10)
        single_question_note = QLabel(
            "Vul de gegevens van deze losse vraag hieronder in. De taxonomiekeuze is verplicht; "
            "extra classificaties en tijd zijn optioneel."
        )
        single_question_note.setWordWrap(True)
        self.single_question_layout.addWidget(single_question_note)
        self.subquestion_panel = QFrame()
        self.subquestion_panel.setObjectName("panel")
        self.subquestion_layout = QVBoxLayout(self.subquestion_panel)
        self.subquestion_layout.setContentsMargins(10, 10, 10, 10)
        self.subquestion_layout.setSpacing(10)
        subquestion_note = QLabel(
            "Vul per subvraag de gegevens in. Iedere kaart is een aparte subvraag, bijvoorbeeld 3a, 3b en 3c. "
            "Punten en taxonomie zijn per subvraag verplicht; extra classificaties zijn optioneel."
        )
        subquestion_note.setWordWrap(True)
        self.subquestion_layout.addWidget(subquestion_note)
        self.subquestion_cards = QWidget()
        self.subquestion_cards_layout = QVBoxLayout(self.subquestion_cards)
        self.subquestion_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.subquestion_cards_layout.setSpacing(12)
        self.subquestion_scroll = QScrollArea()
        self.subquestion_scroll.setWidgetResizable(True)
        self.subquestion_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.subquestion_scroll.setWidget(self.subquestion_cards)
        self.subquestion_layout.addWidget(self.subquestion_scroll)
        screen = QApplication.primaryScreen()
        if screen:
            available = screen.availableGeometry()
            dialog_width = min(1180, max(760, available.width() - 96))
            dialog_height = min(760, max(520, available.height() - 96))
            self.setMinimumWidth(min(760, dialog_width))
            self.resize(dialog_width, dialog_height)
        self.form.addRow("Vraagnummer *", self.number)
        self.form.addRow("", self.has_subquestions)
        self.form.addRow("", self.single_question_panel)
        self.form.addRow("Aantal subvragen", self.subquestion_count)
        self.form.addRow("", self.subquestion_panel)
        self.is_multiple_choice.toggled.connect(self.update_multiple_choice_fields)
        self.has_subquestions.toggled.connect(self.update_subquestion_mode)
        self.subquestion_count.valueChanged.connect(self.rebuild_subquestion_rows)
        self.number.textChanged.connect(self.update_single_question_label)
        for taxonomy in taxonomies:
            widget = QComboBox()
            widget.addItem("")
            for taxonomy_value in taxonomy["values"]:
                widget.addItem(taxonomy_value["name"], taxonomy_value["id"])
            selected_value = (taxonomy_values or {}).get(taxonomy["id"])
            if selected_value is not None:
                widget.setCurrentIndex(widget.findData(selected_value))
            self.taxonomy_widgets[taxonomy["id"]] = widget
        for property_definition in properties:
            choices = []
            if property_definition["choices_json"]:
                choices = json.loads(property_definition["choices_json"])
            if property_definition["field_type"] in ("keuzelijst", "meerkeuze") and choices:
                widget = QComboBox()
                widget.addItem("")
                widget.addItems(choices)
            elif property_definition["field_type"] == "ja/nee":
                widget = QComboBox()
                widget.addItems(["", "Ja", "Nee"])
            else:
                widget = QLineEdit()
            stored = (values or {}).get(property_definition["id"], "")
            if isinstance(widget, QComboBox):
                widget.setCurrentText(stored)
            else:
                widget.setText(stored)
            self.property_widgets[property_definition["id"]] = widget
        if question:
            self.number.setText(question["question_number"])
            self.subquestion.setText(question["subquestion"] or "")
            self.maximum_score.setValue(int(question["maximum_score"]))
            self.description.setText(question["short_description"] or "")
            self.minutes.setValue(int(question["expected_time_minutes"] or 0))
            self.is_multiple_choice.setChecked(bool(question.get("is_multiple_choice")))
            self.multiple_choice_answer.setText(str(question.get("multiple_choice_answer") or ""))
        if self.subquestion_questions:
            first = self.subquestion_questions[0]
            self.number.setText(str(first["question_number"]))
            self.has_subquestions.setChecked(True)
            self.has_subquestions.setEnabled(False)
            self.subquestion_count.setValue(len(self.subquestion_questions))
        self.build_single_question_row()
        self.update_multiple_choice_fields()
        self.rebuild_subquestion_rows()
        self.update_subquestion_mode()

    def accept(self) -> None:
        if not self.required(self.number, "een vraagnummer"):
            return
        if not self.taxonomy_widgets:
            QMessageBox.warning(self, "Taxonomie ontbreekt", "Selecteer eerst minimaal een taxonomie bij de toets.")
            return
        if self.has_subquestion_batch():
            entries = self.subquestion_entries(validate=True)
            if entries is None:
                return
            if not entries:
                QMessageBox.warning(self, "Subvragen ontbreken", "Vul minimaal een subvraag in.")
                return
            super().accept()
            return
        for widget in self.taxonomy_widgets.values():
            if widget.currentData() is None:
                QMessageBox.warning(
                    self, "Taxonomiekeuze ontbreekt", "Kies binnen iedere taxonomie een waarde voor deze vraag."
                )
                return
        if self.is_multiple_choice.isChecked():
            try:
                normalize_multiple_choice_response(self.multiple_choice_answer.text())
            except ResultValidationError as error:
                QMessageBox.warning(self, "Antwoordsleutel ongeldig", str(error))
                return
        super().accept()

    def update_multiple_choice_fields(self) -> None:
        enabled = self.is_multiple_choice.isChecked()
        if self.has_subquestion_batch():
            enabled = False
        self.multiple_choice_answer.setEnabled(enabled)
        if not enabled:
            self.multiple_choice_answer.clear()

    def has_subquestion_batch(self) -> bool:
        return self.has_subquestions.isChecked()

    def update_subquestion_mode(self) -> None:
        enabled = self.has_subquestion_batch()
        self._set_form_row_visible(self.single_question_panel, not enabled)
        self._set_form_row_visible(self.subquestion_count, enabled)
        self._set_form_row_visible(self.subquestion_panel, enabled)
        self.update_multiple_choice_fields()

    def build_single_question_row(self) -> None:
        self._clear_layout(self.single_question_layout, keep_first=1)
        self.maximum_score.setToolTip("Maximumscore voor deze vraag.")
        self.description.setPlaceholderText("Omschrijving voor deze toets")
        self.description.setToolTip("Deze omschrijving hoort bij het gebruik van de vraag in deze toets.")
        self.minutes.setToolTip("Verwachte tijd in minuten. Niet verplicht.")
        self.is_multiple_choice.setToolTip("Vink aan als deze vraag automatisch als meerkeuzevraag nagekeken moet worden.")
        self.multiple_choice_answer.setPlaceholderText("A")
        self.multiple_choice_answer.setToolTip(
            "Vul hier precies een standaardletter in. Neutraliseren of extra opties goedtellen doe je bij Resultateninvoer > MC-sleutels."
        )

        card, grid = self._question_card("Vraag")
        self.single_question_title = card.findChild(QLabel, "questionCardTitle")
        self._add_field(grid, 0, 0, "Max. punten", self.maximum_score)
        self._add_field(grid, 0, 1, "Tijd (min.)", self.minutes)
        self._add_field(grid, 1, 0, "Omschrijving voor deze toets", self.description, column_span=2)
        row = 2
        column = 0
        for taxonomy in self.taxonomies:
            widget = self.taxonomy_widgets[taxonomy["id"]]
            widget.setToolTip(f"Verplichte taxonomiekeuze voor {taxonomy['name']}.")
            self._add_field(grid, row, column, f"Taxonomie: {taxonomy['name']} *", widget)
            row, column = self._next_grid_position(row, column)
        for definition in self.properties:
            widget = self.property_widgets[definition["id"]]
            widget.setToolTip(f"Classificatie: {definition['name']}.")
            self._add_field(grid, row, column, definition["name"], widget)
            row, column = self._next_grid_position(row, column)
        row = row + 1 if column else row
        self._add_field(grid, row, 0, "Meerkeuze", self.is_multiple_choice)
        self._add_field(grid, row, 1, "Standaardantwoord", self.multiple_choice_answer)
        self.single_question_layout.addWidget(card)
        self.update_single_question_label()

    def update_single_question_label(self) -> None:
        if not hasattr(self, "single_question_title"):
            return
        number = self.number.text().strip()
        self.single_question_title.setText(f"Vraag {number}" if number else "Vraag")

    def _clear_layout(self, layout: QVBoxLayout, keep_first: int = 0) -> None:
        while layout.count() > keep_first:
            item = layout.takeAt(keep_first)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def _question_card(self, title: str) -> tuple[QFrame, QGridLayout]:
        card = QFrame()
        card.setObjectName("questionInputCard")
        card.setStyleSheet(
            """
            QFrame#questionInputCard {
                background: #ffffff;
                border: 1px solid #dbe5f1;
                border-radius: 14px;
            }
            QLabel#questionCardTitle {
                color: #001f45;
                font-weight: 700;
                font-size: 16px;
            }
            QLabel#fieldLabel {
                color: #51627a;
                font-weight: 600;
            }
            """
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(12)
        title_label = QLabel(title)
        title_label.setObjectName("questionCardTitle")
        outer.addWidget(title_label)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        outer.addLayout(grid)
        return card, grid

    def _add_field(
        self, grid: QGridLayout, row: int, column: int, label_text: str, widget: QWidget, column_span: int = 1
    ) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setWordWrap(True)
        widget.setMinimumHeight(34)
        if isinstance(widget, (QLineEdit, QComboBox)):
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(label)
        layout.addWidget(widget)
        grid.addWidget(container, row, column, 1, column_span)

    def _next_grid_position(self, row: int, column: int) -> tuple[int, int]:
        column += 1
        if column >= 2:
            return row + 1, 0
        return row, column

    def _set_form_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self.form.labelForField(widget)
        if label is not None:
            label.setVisible(visible)

    def _property_widget(self, property_definition: dict, value: str = "") -> QWidget:
        choices = json.loads(property_definition["choices_json"]) if property_definition["choices_json"] else []
        if property_definition["field_type"] in ("keuzelijst", "meerkeuze") and choices:
            widget = QComboBox()
            widget.addItem("")
            widget.addItems(choices)
            widget.setCurrentText(value)
            return widget
        if property_definition["field_type"] == "ja/nee":
            widget = QComboBox()
            widget.addItems(["", "Ja", "Nee"])
            widget.setCurrentText(value)
            return widget
        widget = QLineEdit()
        widget.setText(value)
        return widget

    def _taxonomy_widget(self, taxonomy: dict, selected_value: int | None = None) -> QComboBox:
        widget = QComboBox()
        widget.addItem("")
        for taxonomy_value in taxonomy["values"]:
            widget.addItem(taxonomy_value["name"], taxonomy_value["id"])
        if selected_value is not None:
            index = widget.findData(selected_value)
            if index >= 0:
                widget.setCurrentIndex(index)
        return widget

    def _snapshot_subquestions(self) -> list[dict[str, object]]:
        snapshots = []
        for row in self.subquestion_row_widgets:
            snapshots.append(
                {
                    "id": row.get("id"),
                    "subquestion": row["subquestion"],
                    "maximum_score": row["maximum_score"].value(),
                    "description": row["description"].text(),
                    "minutes": row["minutes"].value(),
                    "is_multiple_choice": row["is_multiple_choice"].isChecked(),
                    "multiple_choice_answer": row["multiple_choice_answer"].text(),
                    "taxonomy_values": {
                        taxonomy["id"]: row["taxonomies"][taxonomy["id"]].currentData()
                        for taxonomy in self.taxonomies
                    },
                    "property_values": {
                        definition["id"]: self._widget_text(row["properties"][definition["id"]])
                        for definition in self.properties
                    },
                }
            )
        return snapshots

    def rebuild_subquestion_rows(self) -> None:
        if self._rebuilding_subquestions:
            return
        self._rebuilding_subquestions = True
        snapshots = self._snapshot_subquestions()
        while len(snapshots) < self.subquestion_count.value():
            index = len(snapshots)
            existing_question = self.subquestion_questions[index] if index < len(self.subquestion_questions) else None
            question_id = int(existing_question["id"]) if existing_question else None
            snapshots.append(
                {
                    "id": question_id,
                    "subquestion": existing_question["subquestion"] if existing_question else chr(ord("a") + index),
                    "maximum_score": int(existing_question["maximum_score"]) if existing_question else 1,
                    "description": existing_question["short_description"] if existing_question else "",
                    "minutes": int(existing_question["expected_time_minutes"] or 0) if existing_question else 0,
                    "is_multiple_choice": bool(existing_question.get("is_multiple_choice")) if existing_question else False,
                    "multiple_choice_answer": str(existing_question.get("multiple_choice_answer") or "") if existing_question else "",
                    "taxonomy_values": self.subquestion_taxonomy_values.get(question_id or -1, {}),
                    "property_values": self.subquestion_values.get(question_id or -1, {}),
                }
            )
        snapshots = snapshots[: self.subquestion_count.value()]
        self.subquestion_row_widgets = []
        self._clear_layout(self.subquestion_cards_layout)
        for row_index, snapshot in enumerate(snapshots):
            subquestion = str(snapshot["subquestion"] or chr(ord("a") + row_index))
            maximum_score = QSpinBox()
            maximum_score.setRange(1, 1000)
            maximum_score.setValue(int(snapshot["maximum_score"] or 1))
            maximum_score.setToolTip("Maximumscore voor deze subvraag.")
            description = QLineEdit()
            description.setText(str(snapshot["description"] or ""))
            description.setPlaceholderText("Omschrijving voor deze toets")
            description.setToolTip("Deze omschrijving hoort bij het gebruik van de subvraag in deze toets.")
            minutes = QSpinBox()
            minutes.setRange(0, 300)
            minutes.setSpecialValueText("Niet ingevuld")
            minutes.setValue(int(snapshot["minutes"] or 0))
            minutes.setToolTip("Verwachte tijd in minuten. Niet verplicht.")

            card, grid = self._question_card(f"Subvraag {subquestion}")
            self._add_field(grid, 0, 0, "Max. punten", maximum_score)
            self._add_field(grid, 0, 1, "Tijd (min.)", minutes)
            self._add_field(grid, 1, 0, "Omschrijving voor deze toets", description, column_span=2)
            grid_row = 2
            grid_column = 0
            taxonomy_widgets = {}
            for taxonomy in self.taxonomies:
                widget = self._taxonomy_widget(taxonomy, dict(snapshot["taxonomy_values"]).get(taxonomy["id"]))
                widget.setToolTip(f"Verplichte taxonomiekeuze voor {taxonomy['name']}.")
                taxonomy_widgets[taxonomy["id"]] = widget
                self._add_field(grid, grid_row, grid_column, f"Taxonomie: {taxonomy['name']} *", widget)
                grid_row, grid_column = self._next_grid_position(grid_row, grid_column)
            property_widgets = {}
            for definition in self.properties:
                widget = self._property_widget(definition, dict(snapshot["property_values"]).get(definition["id"], ""))
                widget.setToolTip(f"Classificatie: {definition['name']}.")
                property_widgets[definition["id"]] = widget
                self._add_field(grid, grid_row, grid_column, definition["name"], widget)
                grid_row, grid_column = self._next_grid_position(grid_row, grid_column)
            is_multiple_choice = QCheckBox()
            is_multiple_choice.setChecked(bool(snapshot["is_multiple_choice"]))
            is_multiple_choice.setToolTip("Vink aan als deze subvraag automatisch als meerkeuzevraag nagekeken moet worden.")
            answer = QLineEdit()
            answer.setMaxLength(1)
            answer.setPlaceholderText("A")
            answer.setText(str(snapshot["multiple_choice_answer"] or ""))
            answer.setToolTip(
                "Vul hier precies een standaardletter in. Neutraliseren of extra opties goedtellen doe je bij Resultateninvoer > MC-sleutels."
            )
            answer.setEnabled(is_multiple_choice.isChecked())
            is_multiple_choice.toggled.connect(answer.setEnabled)
            is_multiple_choice.toggled.connect(lambda checked, target=answer: target.clear() if not checked else None)
            grid_row = grid_row + 1 if grid_column else grid_row
            self._add_field(grid, grid_row, 0, "Meerkeuze", is_multiple_choice)
            self._add_field(grid, grid_row, 1, "Standaardantwoord", answer)
            self.subquestion_cards_layout.addWidget(card)
            self.subquestion_row_widgets.append(
                {
                    "id": snapshot["id"],
                    "subquestion": subquestion,
                    "maximum_score": maximum_score,
                    "description": description,
                    "minutes": minutes,
                    "taxonomies": taxonomy_widgets,
                    "properties": property_widgets,
                    "is_multiple_choice": is_multiple_choice,
                    "multiple_choice_answer": answer,
                }
            )
        self.subquestion_cards_layout.addStretch(1)
        self.subquestion_scroll.setMinimumHeight(min(520, max(260, 230 * len(snapshots))))
        self._rebuilding_subquestions = False

    def property_value(self, property_id: int) -> str:
        widget = self.property_widgets[property_id]
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return widget.text().strip()

    def taxonomy_value(self, taxonomy_id: int) -> int:
        return self.taxonomy_widgets[taxonomy_id].currentData()

    def _widget_text(self, widget: QWidget) -> str:
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        return ""

    def subquestion_entries(self, validate: bool = False) -> list[dict[str, object]] | None:
        entries = []
        for row_index, row in enumerate(self.subquestion_row_widgets, start=1):
            taxonomy_values = {}
            for taxonomy in self.taxonomies:
                value = row["taxonomies"][taxonomy["id"]].currentData()
                if validate and value is None:
                    QMessageBox.warning(
                        self,
                        "Taxonomiekeuze ontbreekt",
                        f"Kies bij subvraag {row['subquestion']} binnen iedere taxonomie een waarde.",
                    )
                    return None
                taxonomy_values[taxonomy["id"]] = value
            is_multiple_choice = row["is_multiple_choice"].isChecked()
            answer = None
            if is_multiple_choice:
                try:
                    answer = normalize_multiple_choice_response(row["multiple_choice_answer"].text())
                except ResultValidationError as error:
                    QMessageBox.warning(
                        self,
                        "Antwoordsleutel ongeldig",
                        f"Subvraag {row['subquestion']}: {error}",
                    )
                    return None
            entries.append(
                {
                "id": row.get("id"),
                "question_number": self.number.text().strip(),
                "subquestion": str(row["subquestion"]),
                "maximum_score": row["maximum_score"].value(),
                "short_description": row["description"].text().strip(),
                "expected_time_minutes": row["minutes"].value() or None,
                "is_multiple_choice": int(is_multiple_choice),
                "multiple_choice_answer": answer,
                "question_bank_id": row.get("question_bank_id"),
                "question_bank_version_id": row.get("question_bank_version_id"),
                "question_bank_subquestion_id": row.get("question_bank_subquestion_id"),
                "taxonomy_values": taxonomy_values,
                "property_values": {
                        definition["id"]: self._widget_text(row["properties"][definition["id"]])
                        for definition in self.properties
                    },
                }
            )
        return entries



class QuestionDatabaseFilterPanel(QFrame):
    changed = Signal()

    def __init__(self, database: SubjectDatabase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self.setObjectName("filterCard")
        self.taxonomy_filters: dict[int, QComboBox] = {}
        self.property_filters: dict[int, QComboBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(260)
        self.setMaximumHeight(260)

        title = QLabel("<b>Zoeken en filteren</b>")
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Zoek op titel, korte databaseomschrijving, vraagtekst, taxonomie of classificatie..."
        )
        self.search.setMinimumHeight(42)
        self.search.textChanged.connect(lambda _text: self.changed.emit())
        layout.addWidget(title)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(10)
        search_row.addWidget(self.search, 1)

        self.advanced_button = set_button_role(QPushButton("Taxonomieën / classificaties"), "secondary")
        self.advanced_button.setMinimumWidth(230)
        self.advanced_button.setMaximumWidth(280)
        self.advanced_button.setToolTip(
            "Open extra filters voor taxonomieën en vraagclassificaties, zoals RTTI, domein, leerdoel of vraagtype."
        )
        self.advanced_button.clicked.connect(self.open_advanced_filters)
        search_row.addWidget(self.advanced_button)

        self.clear_button = set_button_role(QPushButton("Filters wissen"), "secondary")
        self.clear_button.setMinimumWidth(140)
        self.clear_button.setMaximumWidth(180)
        self.clear_button.clicked.connect(self.clear_filters)
        search_row.addWidget(self.clear_button)
        layout.addLayout(search_row)

        fixed_grid = QGridLayout()
        fixed_grid.setContentsMargins(0, 0, 0, 0)
        fixed_grid.setHorizontalSpacing(14)
        fixed_grid.setVerticalSpacing(10)
        layout.addLayout(fixed_grid)

        self.multiple_choice = QComboBox()
        self._prepare_combo(self.multiple_choice)
        self.multiple_choice.addItem("Alle vraagvormen", None)
        self.multiple_choice.addItem("Alleen meerkeuze", 1)
        self.multiple_choice.addItem("Geen meerkeuze", 0)
        self.multiple_choice.currentIndexChanged.connect(lambda _index: self.changed.emit())

        self.status = QComboBox()
        self._prepare_combo(self.status)
        self.status.addItem("Alle statussen", None)
        for status in QUESTION_BANK_STATUSES:
            self.status.addItem(status, status)
        self.status.currentIndexChanged.connect(lambda _index: self.changed.emit())

        self.subquestions = QComboBox()
        self._prepare_combo(self.subquestions)
        self.subquestions.addItem("Alle vraagstructuren", None)
        self.subquestions.addItem("Met subvragen", "with")
        self.subquestions.addItem("Zonder subvragen", "without")
        self.subquestions.currentIndexChanged.connect(lambda _index: self.changed.emit())

        self.usage = QComboBox()
        self._prepare_combo(self.usage)
        self.usage.addItem("Alle vragen", None)
        self.usage.addItem("Al gebruikt", "used")
        self.usage.addItem("Nog niet gebruikt", "unused")
        self.usage.currentIndexChanged.connect(lambda _index: self.changed.emit())

        fixed_filters = [
            ("Vraagvorm", self.multiple_choice),
            ("Status", self.status),
            ("Structuur", self.subquestions),
            ("Gebruik", self.usage),
        ]
        for index, (label, widget) in enumerate(fixed_filters):
            fixed_grid.addWidget(self._filter_field(label, widget), index // 4, index % 4)
        for column in range(4):
            fixed_grid.setColumnStretch(column, 1)

        self.advanced_dialog = QDialog(self)
        self.advanced_dialog.setWindowTitle("Taxonomieën en classificaties filteren")
        fit_to_available_screen(self.advanced_dialog, 920, 620)
        advanced_layout = QVBoxLayout(self.advanced_dialog)
        advanced_note = QLabel(
            "Kies hier extra filters. Deze metadatafilters worden alleen toegepast op de vraagdatabase; "
            "ze nemen geen ruimte in op het hoofdscherm."
        )
        advanced_note.setWordWrap(True)
        advanced_note.setObjectName("panel")
        advanced_layout.addWidget(advanced_note)
        self.dynamic_filter_area = QScrollArea()
        self.dynamic_filter_area.setWidgetResizable(True)
        self.dynamic_filter_area.setFrameShape(QFrame.Shape.NoFrame)
        self.dynamic_filter_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        dynamic_container = QWidget()
        dynamic_grid = QGridLayout()
        dynamic_grid.setContentsMargins(8, 8, 8, 8)
        dynamic_grid.setHorizontalSpacing(14)
        dynamic_grid.setVerticalSpacing(10)
        dynamic_container.setLayout(dynamic_grid)
        self.dynamic_filter_area.setWidget(dynamic_container)
        advanced_layout.addWidget(self.dynamic_filter_area, 1)
        advanced_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        advanced_buttons.rejected.connect(self.advanced_dialog.reject)
        advanced_buttons.accepted.connect(self.advanced_dialog.accept)
        advanced_layout.addWidget(advanced_buttons)

        row = 0
        column = 0
        for taxonomy in load_all_taxonomies(database):
            combo = QComboBox()
            self._prepare_combo(combo)
            combo.addItem(f"Alle {taxonomy['name']}", None)
            for value in taxonomy["values"]:
                combo.addItem(str(value["name"]), int(value["id"]))
            combo.currentIndexChanged.connect(lambda _index: self._advanced_filter_changed())
            dynamic_grid.addWidget(self._filter_field(str(taxonomy["name"]), combo), row, column)
            self.taxonomy_filters[int(taxonomy["id"])] = combo
            column += 1
            if column >= 2:
                row += 1
                column = 0

        for definition in load_active_question_properties(database):
            property_id = int(definition["id"])
            values = question_database_distinct_property_values(database, property_id)
            if column >= 2:
                row += 1
                column = 0
            combo = QComboBox()
            self._prepare_combo(combo)
            combo.addItem(f"Alle {definition['name']}", None)
            for value in values:
                combo.addItem(value, value.strip().casefold())
            combo.currentIndexChanged.connect(lambda _index: self._advanced_filter_changed())
            dynamic_grid.addWidget(self._filter_field(str(definition["name"]), combo), row, column)
            self.property_filters[property_id] = combo
            column += 1
        self.update_advanced_button_text()

    def open_advanced_filters(self) -> None:
        self.advanced_dialog.exec()

    def _advanced_filter_changed(self) -> None:
        self.update_advanced_button_text()
        self.changed.emit()

    def update_advanced_button_text(self) -> None:
        active = sum(
            1
            for combo in [*self.taxonomy_filters.values(), *self.property_filters.values()]
            if combo.currentData() is not None
        )
        if active:
            self.advanced_button.setText(f"Extra filters ({active} actief)")
        else:
            self.advanced_button.setText("Taxonomieën / classificaties")

    def _prepare_combo(self, combo: QComboBox) -> None:
        combo.setMinimumContentsLength(14)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumWidth(150)
        combo.setMaximumWidth(320)
        combo.setMinimumHeight(42)
        combo.setFixedHeight(42)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _filter_field(self, label_text: str, widget: QComboBox) -> QWidget:
        field = QWidget()
        field.setObjectName("filterField")
        field.setMinimumHeight(82)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        field_layout = QVBoxLayout(field)
        field_layout.setContentsMargins(0, 0, 0, 0)
        field_layout.setSpacing(6)
        label = QLabel(label_text)
        label.setWordWrap(False)
        label.setMinimumHeight(22)
        label.setMaximumHeight(24)
        label.setToolTip(label_text)
        widget.setToolTip(label_text)
        field_layout.addWidget(label)
        field_layout.addWidget(widget)
        return field

    def refresh_property_choices(self) -> None:
        for definition in load_active_question_properties(self.database):
            property_id = int(definition["id"])
            combo = self.property_filters.get(property_id)
            if combo is None:
                continue
            current = combo.currentData()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(f"Alle {definition['name']}", None)
            for value in question_database_distinct_property_values(self.database, property_id):
                combo.addItem(value, value.strip().casefold())
            if current is not None:
                index = combo.findData(current)
                combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def clear_filters(self) -> None:
        self.search.clear()
        for combo in [
            self.multiple_choice,
            self.status,
            self.subquestions,
            self.usage,
            *self.taxonomy_filters.values(),
            *self.property_filters.values(),
        ]:
            combo.setCurrentIndex(0)
        self.update_advanced_button_text()
        self.changed.emit()

    @staticmethod
    def _tokens(row: dict[str, object], key: str) -> set[str]:
        return {part for part in str(row.get(key) or "").split("|") if part}

    def matches(self, row: dict[str, object]) -> bool:
        query = self.search.text().strip().casefold()
        if query:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in (
                    "title",
                    "short_description",
                    "question_text",
                    "usage_description_summary",
                    "taxonomy_summary",
                    "property_summary",
                )
            ).casefold()
            if query not in haystack:
                return False

        multiple_choice = self.multiple_choice.currentData()
        if multiple_choice is not None and int(row.get("is_multiple_choice") or 0) != int(multiple_choice):
            return False

        status = self.status.currentData()
        if status is not None and str(row.get("status") or "Actief") != str(status):
            return False

        subquestion_filter = self.subquestions.currentData()
        subquestion_count = int(row.get("subquestion_count") or 0)
        if subquestion_filter == "with" and subquestion_count == 0:
            return False
        if subquestion_filter == "without" and subquestion_count > 0:
            return False

        usage_filter = self.usage.currentData()
        usage_count = int(row.get("usage_count") or 0)
        if usage_filter == "used" and usage_count == 0:
            return False
        if usage_filter == "unused" and usage_count > 0:
            return False

        taxonomy_tokens = self._tokens(row, "taxonomy_filters")
        for taxonomy_id, combo in self.taxonomy_filters.items():
            value_id = combo.currentData()
            if value_id is not None and f"{taxonomy_id}={int(value_id)}" not in taxonomy_tokens:
                return False

        property_tokens = self._tokens(row, "property_filters")
        for property_id, combo in self.property_filters.items():
            value = combo.currentData()
            if value is not None and f"{property_id}={str(value).casefold()}" not in property_tokens:
                return False

        return True



class QuestionDatabaseSelectionDialog(QDialog):
    def __init__(
        self,
        rows: list[sqlite3.Row],
        database: SubjectDatabase,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.all_rows = [dict(row) for row in rows]
        self.visible_rows: list[dict[str, object]] = []
        self.setWindowTitle("Vraag uit vraagdatabase kiezen")
        fit_to_available_screen(self, 980, 680)
        layout = QVBoxLayout(self)
        explanation = QLabel("Kies een databasevraag. De inhoud en antwoordsleutel worden uit de vraagdatabase overgenomen.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.filters = QuestionDatabaseFilterPanel(database, self)
        self.filters.changed.connect(self.refresh_table)
        layout.addWidget(self.filters)
        self.count_label = QLabel()
        layout.addWidget(self.count_label)
        self.table = QTableWidget()
        self.table.cellDoubleClicked.connect(lambda row, column: self.accept())
        layout.addWidget(self.table, 1)
        self.refresh_table()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def refresh_table(self) -> None:
        self.visible_rows = [row for row in self.all_rows if self.filters.matches(row)]
        configure_table(
            self.table,
            [
                "Titel",
                "Versie",
                "Punten",
                "Subvragen",
                "Taxonomie",
                "Classificaties",
                "Korte databaseomschrijving",
            ],
        )
        self.table.setRowCount(len(self.visible_rows))
        for row_index, row in enumerate(self.visible_rows):
            values = [
                row["title"],
                row["version_number"],
                f"{float(row['maximum_score']):g}",
                row["subquestion_count"],
                row.get("taxonomy_summary") or "-",
                row.get("property_summary") or "-",
                row["short_description"] or "",
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, item(value))
            self.table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row["item_id"])
            self.table.item(row_index, 0).setData(int(Qt.ItemDataRole.UserRole) + 1, row["version_id"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.count_label.setText(f"{len(self.visible_rows)} van {len(self.all_rows)} vragen zichtbaar")

    def selected(self) -> tuple[int, int] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        version_id = self.table.item(row, 0).data(int(Qt.ItemDataRole.UserRole) + 1)
        return int(item_id), int(version_id)



class QuestionDatabaseImportDialog(FormDialog):
    def __init__(
        self,
        default_title: str,
        taxonomies: list[dict] | None = None,
        properties: list[dict] | None = None,
        rows: list[dict] | None = None,
        taxonomy_values_by_question: dict[int, dict[int, int]] | None = None,
        property_values_by_question: dict[int, dict[int, str]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Toevoegen aan vraagdatabase", parent)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.taxonomies = list(taxonomies or [])
        self.properties = list(properties or [])
        self.rows = [dict(row) for row in (rows or [])]
        self.taxonomy_values_by_question = taxonomy_values_by_question or {}
        self.property_values_by_question = property_values_by_question or {}
        first_question_id = int(self.rows[0]["id"]) if self.rows else -1
        self.taxonomy_widgets: dict[int, QComboBox] = {}
        self.taxonomy_skip_widgets: dict[int, QCheckBox] = {}
        self.property_widgets: dict[int, QWidget] = {}
        self.property_skip_widgets: dict[int, QCheckBox] = {}
        self.subquestion_widgets: dict[int, dict[str, dict[int, QWidget]]] = {}
        self.title = QLineEdit(default_title)
        self.question_text = QTextEdit()
        self.question_text.setMinimumHeight(110)
        self.question_text.setPlaceholderText(
            "Plak of typ hier de volledige vraagtekst. Bij een hoofdvraag met subvragen is dit de tekst van de hoofdvraag."
        )
        self.short_description = QLineEdit()
        self.short_description.setPlaceholderText("Omschrijving voor zoeken en beheer in de vraagdatabase")
        self.status = QComboBox()
        self.status.addItems(QUESTION_BANK_STATUSES)
        self.status.setCurrentText("Actief")
        self.form.addRow("Titel *", self.title)
        self.form.addRow("Vraagtekst / hoofdvraag", self.question_text)
        self.form.addRow("Korte databaseomschrijving", self.short_description)
        self.form.addRow("Status", self.status)
        explanation = QLabel(
            "Vul hier metadata voor de vraagdatabase in. U ziet ook taxonomieën en classificaties die niet "
            "aan de huidige toets gekoppeld zijn; die worden alleen in de vraagdatabase opgeslagen. "
            "De omschrijving uit de toets blijft daarnaast als gebruiksmetadata bij deze afname bewaard."
        )
        explanation.setWordWrap(True)
        explanation.setObjectName("panel")
        self.form.addRow("", explanation)
        for taxonomy in self.taxonomies:
            combo = self._taxonomy_widget(
                taxonomy,
                self.taxonomy_values_by_question.get(first_question_id, {}).get(int(taxonomy["id"])),
            )
            self.taxonomy_widgets[int(taxonomy["id"])] = combo
            skip = self._metadata_skip_checkbox(combo)
            self.taxonomy_skip_widgets[int(taxonomy["id"])] = skip
            self.form.addRow(f"Database-taxonomie: {taxonomy['name']}", self._metadata_row(skip, combo))
        for definition in self.properties:
            widget = self._property_widget(
                definition,
                self.property_values_by_question.get(first_question_id, {}).get(int(definition["id"]), ""),
            )
            self.property_widgets[int(definition["id"])] = widget
            skip = self._metadata_skip_checkbox(widget)
            self.property_skip_widgets[int(definition["id"])] = skip
            self.form.addRow(f"Database-classificatie: {definition['name']}", self._metadata_row(skip, widget))
        if len(self.rows) > 1 or any(row.get("subquestion") for row in self.rows):
            self.subquestion_panel = QFrame()
            self.subquestion_panel.setObjectName("panel")
            subquestion_layout = QVBoxLayout(self.subquestion_panel)
            subquestion_layout.setContentsMargins(10, 10, 10, 10)
            subquestion_layout.setSpacing(10)
            note = QLabel(
                "Vul per subvraag de databasegegevens in. Metadata die u niet wilt opslaan in de "
                "vraagdatabase kunt u per veld uitzetten met 'Niet meenemen'."
            )
            note.setWordWrap(True)
            subquestion_layout.addWidget(note)
            self.subquestion_cards = QWidget()
            self.subquestion_cards_layout = QVBoxLayout(self.subquestion_cards)
            self.subquestion_cards_layout.setContentsMargins(0, 0, 0, 0)
            self.subquestion_cards_layout.setSpacing(12)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(self.subquestion_cards)
            subquestion_layout.addWidget(scroll)
            self._build_subquestion_metadata_table()
            self.form.addRow("Metadata per subvraag", self.subquestion_panel)

    def accept(self) -> None:
        if self.required(self.title, "een herkenbare titel"):
            super().accept()

    def _taxonomy_widget(self, taxonomy: dict, selected_value: int | None = None) -> QComboBox:
        widget = QComboBox()
        widget.addItem("")
        for taxonomy_value in taxonomy["values"]:
            widget.addItem(taxonomy_value["name"], taxonomy_value["id"])
        if selected_value is not None:
            index = widget.findData(selected_value)
            if index >= 0:
                widget.setCurrentIndex(index)
        return widget

    def _property_widget(self, definition: dict, value: str = "") -> QWidget:
        choices = json.loads(definition["choices_json"]) if definition.get("choices_json") else []
        if definition["field_type"] in ("keuzelijst", "meerkeuze") and choices:
            widget = QComboBox()
            widget.addItem("")
            widget.addItems(choices)
            widget.setCurrentText(value)
            return widget
        if definition["field_type"] == "ja/nee":
            widget = QComboBox()
            widget.addItems(["", "Ja", "Nee"])
            widget.setCurrentText(value)
            return widget
        widget = QLineEdit()
        widget.setText(value)
        return widget

    def _metadata_skip_checkbox(self, target: QWidget) -> QCheckBox:
        checkbox = QCheckBox("Niet meenemen")
        checkbox.setMinimumWidth(150)
        checkbox.setMaximumWidth(170)
        checkbox.setToolTip(
            "Vink dit aan als deze taxonomie of classificatie niet bij deze databasevraag hoort. "
            "Het invoerveld wordt dan geblokkeerd en niet opgeslagen."
        )
        checkbox.toggled.connect(lambda checked, widget=target: self._set_metadata_skipped(widget, checked))
        return checkbox

    def _metadata_row(self, checkbox: QCheckBox, target: QWidget) -> QWidget:
        row = QWidget()
        row.setMinimumHeight(46)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        target.setMinimumHeight(42)
        layout.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(target, 1, Qt.AlignmentFlag.AlignVCenter)
        return row

    def _set_metadata_skipped(self, widget: QWidget, skipped: bool) -> None:
        if skipped:
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QLineEdit):
                widget.clear()
        widget.setEnabled(not skipped)
        self._style_metadata_widget(widget, skipped)

    def _style_metadata_widget(self, widget: QWidget, skipped: bool) -> None:
        if skipped:
            widget.setStyleSheet(
                "QComboBox, QLineEdit {"
                "background: #eef2f7; color: #7a8797; border: 1px dashed #b9c5d6; border-radius: 7px;"
                "}"
                "QComboBox::drop-down {"
                "border-left: 1px dashed #b9c5d6; background: #e4ebf5; width: 30px;"
                "}"
            )
            widget.setToolTip("Niet meegenomen bij deze databasevraag.")
        else:
            widget.setStyleSheet("")
            widget.setToolTip("")

    def _widget_text(self, widget: QWidget) -> str:
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        return ""

    def _database_card(self, title: str) -> tuple[QFrame, QGridLayout]:
        card = QFrame()
        card.setObjectName("questionInputCard")
        card.setStyleSheet(
            """
            QFrame#questionInputCard {
                background: #ffffff;
                border: 1px solid #dbe5f1;
                border-radius: 14px;
            }
            QLabel#questionCardTitle {
                color: #001f45;
                font-weight: 700;
                font-size: 16px;
            }
            QLabel#fieldLabel {
                color: #51627a;
                font-weight: 600;
            }
            """
        )
        outer = QVBoxLayout(card)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(12)
        title_label = QLabel(title)
        title_label.setObjectName("questionCardTitle")
        outer.addWidget(title_label)
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        outer.addLayout(grid)
        return card, grid

    def _add_database_field(
        self, grid: QGridLayout, row: int, column: int, label_text: str, widget: QWidget, column_span: int = 1
    ) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setWordWrap(True)
        widget.setMinimumHeight(40)
        if isinstance(widget, (QLineEdit, QComboBox)):
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(label)
        layout.addWidget(widget)
        grid.addWidget(container, row, column, 1, column_span)

    def _next_metadata_grid_position(self, row: int, column: int) -> tuple[int, int]:
        column += 1
        if column >= 2:
            return row + 1, 0
        return row, column

    def _build_subquestion_metadata_table(self) -> None:
        while self.subquestion_cards_layout.count():
            item_to_remove = self.subquestion_cards_layout.takeAt(0)
            widget_to_remove = item_to_remove.widget()
            if widget_to_remove is not None:
                widget_to_remove.setParent(None)
        for row_index, row in enumerate(self.rows):
            question_id = int(row["id"])
            label = str(row.get("subquestion") or row.get("question_number") or "")
            card, grid = self._database_card(f"Subvraag {label}" if row.get("subquestion") else f"Vraag {label}")
            question_text = QLineEdit()
            question_text.setPlaceholderText(f"Tekst van subvraag {label}")
            short_description = QLineEdit(str(row.get("short_description") or ""))
            short_description.setPlaceholderText("Korte databaseomschrijving voor deze subvraag")
            self._add_database_field(grid, 0, 0, "Vraagtekst", question_text)
            self._add_database_field(grid, 0, 1, "Korte databaseomschrijving", short_description)
            grid_row = 1
            grid_column = 0
            taxonomy_widgets = {}
            taxonomy_skip_widgets = {}
            property_widgets = {}
            property_skip_widgets = {}
            for taxonomy in self.taxonomies:
                taxonomy_id = int(taxonomy["id"])
                widget = self._taxonomy_widget(
                    taxonomy,
                    self.taxonomy_values_by_question.get(question_id, {}).get(taxonomy_id),
                )
                skip = self._metadata_skip_checkbox(widget)
                taxonomy_widgets[taxonomy_id] = widget
                taxonomy_skip_widgets[taxonomy_id] = skip
                self._add_database_field(
                    grid,
                    grid_row,
                    grid_column,
                    f"Database-taxonomie: {taxonomy['name']}",
                    self._metadata_row(skip, widget),
                )
                grid_row, grid_column = self._next_metadata_grid_position(grid_row, grid_column)
            for definition in self.properties:
                property_id = int(definition["id"])
                widget = self._property_widget(
                    definition,
                    self.property_values_by_question.get(question_id, {}).get(property_id, ""),
                )
                skip = self._metadata_skip_checkbox(widget)
                property_widgets[property_id] = widget
                property_skip_widgets[property_id] = skip
                self._add_database_field(
                    grid,
                    grid_row,
                    grid_column,
                    f"Database-classificatie: {definition['name']}",
                    self._metadata_row(skip, widget),
                )
                grid_row, grid_column = self._next_metadata_grid_position(grid_row, grid_column)
            self.subquestion_cards_layout.addWidget(card)
            self.subquestion_widgets[question_id] = {
                "question_text": question_text,
                "short_description": short_description,
                "taxonomies": taxonomy_widgets,
                "taxonomy_skips": taxonomy_skip_widgets,
                "properties": property_widgets,
                "property_skips": property_skip_widgets,
            }
        self.subquestion_cards_layout.addStretch(1)

    def payload(self) -> dict[str, object]:
        return {
            "title": self.title.text().strip(),
            "question_text": self.question_text.toPlainText().strip(),
            "short_description": self.short_description.text().strip(),
            "status": self.status.currentText(),
            "taxonomy_values": {
                taxonomy_id: widget.currentData()
                for taxonomy_id, widget in self.taxonomy_widgets.items()
                if not (
                    self.taxonomy_skip_widgets.get(taxonomy_id)
                    and self.taxonomy_skip_widgets[taxonomy_id].isChecked()
                )
                and widget.currentData() is not None
            },
            "property_values": {
                property_id: self._widget_text(widget)
                for property_id, widget in self.property_widgets.items()
                if not (
                    self.property_skip_widgets.get(property_id)
                    and self.property_skip_widgets[property_id].isChecked()
                )
                and self._widget_text(widget)
            },
            "subquestion_metadata": self.subquestion_metadata(),
        }

    def subquestion_metadata(self) -> dict[int, dict[str, dict[int, object]]]:
        metadata = {}
        for question_id, widgets in self.subquestion_widgets.items():
            metadata[question_id] = {
                "question_text": widgets["question_text"].text().strip(),
                "short_description": widgets["short_description"].text().strip(),
                "taxonomy_values": {
                    taxonomy_id: widget.currentData()
                    for taxonomy_id, widget in widgets["taxonomies"].items()
                    if not (
                        widgets.get("taxonomy_skips", {}).get(taxonomy_id)
                        and widgets["taxonomy_skips"][taxonomy_id].isChecked()
                    )
                    and widget.currentData() is not None
                },
                "property_values": {
                    property_id: self._widget_text(widget)
                    for property_id, widget in widgets["properties"].items()
                    if not (
                        widgets.get("property_skips", {}).get(property_id)
                        and widgets["property_skips"][property_id].isChecked()
                    )
                    and self._widget_text(widget)
                },
            }
        return metadata



class LinkedDatabaseQuestionDialog(QDialog):
    def __init__(self, rows: list[dict], database_enabled: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows = [dict(row) for row in rows]
        self.description_widgets: dict[int, QLineEdit] = {}
        self.setWindowTitle("Databasevraag in deze toets bewerken")
        fit_to_available_screen(self, 820, 520)
        layout = QVBoxLayout(self)

        explanation = QLabel(
            "De inhoud, punten, antwoordsleutel en korte databaseomschrijving worden beheerd in de "
            "Vraagdatabase. Hier kunt u alleen het vraagnummer en de omschrijving voor deze toets aanpassen."
        )
        if not database_enabled:
            explanation.setText(
                explanation.text()
                + " De module Vraagdatabase staat momenteel uit; bestaande databasekoppelingen blijven behouden."
            )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        number_row = QHBoxLayout()
        number_row.addWidget(QLabel("Vraagnummer"))
        self.number = QLineEdit(str(self.rows[0]["question_number"]) if self.rows else "")
        self.number.setMaximumWidth(180)
        number_row.addWidget(self.number)
        number_row.addStretch()
        layout.addLayout(number_row)

        self.table = QTableWidget()
        configure_table(self.table, ["Vraag", "Omschrijving voor deze toets"])
        self.table.setRowCount(len(self.rows))
        for row_index, row in enumerate(self.rows):
            label = f"{row['question_number']}{row.get('subquestion') or ''}"
            self.table.setItem(row_index, 0, item(label))
            description = QLineEdit(str(row.get("short_description") or ""))
            description.setPlaceholderText("Optionele omschrijving in de toetsmatrijs en analyses")
            self.table.setCellWidget(row_index, 1, description)
            self.description_widgets[int(row["id"])] = description
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def descriptions(self) -> dict[int, str]:
        return {
            question_id: widget.text().strip()
            for question_id, widget in self.description_widgets.items()
        }

