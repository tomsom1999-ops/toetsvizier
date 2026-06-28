from __future__ import annotations

import json
import html
import sqlite3
from collections import defaultdict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .analysis import analysis_data
from .database import SubjectDatabase
from .dialogs_base import FormDialog
from .matrix_page import MatrixPage
from .pages_base import Page
from .question_bank import (
    QUESTION_BANK_STATUSES,
    load_active_question_properties,
    load_all_taxonomies,
    question_database_latest_rows,
)
from .question_dialogs import QuestionDatabaseFilterPanel
from .results import ResultValidationError, normalize_multiple_choice_response, regrade_multiple_choice_question
from .ui_helpers import (
    configure_table,
    fit_to_available_screen,
    item,
    make_empty_state,
    make_page_header,
    set_button_role,
)


class QuestionDatabaseDialog(FormDialog):
    def __init__(
        self,
        taxonomies: list[dict],
        properties: list[dict],
        version: dict | None = None,
        subquestions: list[dict] | None = None,
        taxonomy_values: dict[int, int] | None = None,
        property_values: dict[int, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Databasevraag bewerken" if version else "Databasevraag toevoegen", parent)
        self.form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.taxonomies = list(taxonomies)
        self.properties = list(properties)
        self.subquestion_rows: list[dict[str, object]] = []
        self._rebuilding = False
        self.title = QLineEdit()
        self.question_text = QTextEdit()
        self.question_text.setMinimumHeight(120)
        self.short_description = QLineEdit()
        self.status = QComboBox()
        self.status.addItems(QUESTION_BANK_STATUSES)
        self.status.setCurrentText("Actief")
        self.maximum_score = QSpinBox()
        self.maximum_score.setRange(1, 1000)
        self.maximum_score.setValue(1)
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 600)
        self.minutes.setSpecialValueText("Niet ingevuld")
        self.is_multiple_choice = QCheckBox("Meerkeuzevraag")
        self.multiple_choice_answer = QLineEdit()
        self.multiple_choice_answer.setMaxLength(1)
        self.multiple_choice_answer.setPlaceholderText("Bijvoorbeeld A")
        self.structure_panel = QWidget()
        structure_layout = QHBoxLayout(self.structure_panel)
        structure_layout.setContentsMargins(0, 0, 0, 0)
        self.single_question = QRadioButton("Losse vraag")
        self.question_with_subquestions = QRadioButton("Hoofdvraag met subvragen")
        self.single_question.setChecked(True)
        structure_layout.addWidget(self.single_question)
        structure_layout.addWidget(self.question_with_subquestions)
        structure_layout.addStretch()
        self.structure_explanation = QLabel()
        self.structure_explanation.setWordWrap(True)
        self.structure_explanation.setObjectName("panel")
        self.subquestion_count = QSpinBox()
        self.subquestion_count.setRange(2, 26)
        self.subquestion_count.setValue(max(2, len(subquestions or []) or 2))
        self.taxonomy_widgets: dict[int, QComboBox] = {}
        self.taxonomy_skip_widgets: dict[int, QCheckBox] = {}
        self.property_widgets: dict[int, QWidget] = {}
        self.property_skip_widgets: dict[int, QCheckBox] = {}
        self.form.addRow("Titel *", self.title)
        self.form.addRow("Vraagstructuur *", self.structure_panel)
        self.form.addRow("", self.structure_explanation)
        self.form.addRow("Volledige vraagtekst", self.question_text)
        self.short_description.setPlaceholderText("Korte omschrijving voor zoeken en beheer in de vraagdatabase")
        self.short_description.setToolTip(
            "Deze databaseomschrijving staat los van de omschrijving die u per toets in het vragenoverzicht invult."
        )
        self.form.addRow("Korte databaseomschrijving", self.short_description)
        self.form.addRow("Status", self.status)
        self.form.addRow("Max. punten", self.maximum_score)
        self.form.addRow("Tijd (min.)", self.minutes)
        self.form.addRow("", self.is_multiple_choice)
        self.form.addRow("Standaardantwoord", self.multiple_choice_answer)
        self.multiple_choice_answer_label = self.form.labelForField(self.multiple_choice_answer)
        for taxonomy in self.taxonomies:
            combo = QComboBox()
            combo.addItem("")
            for value in taxonomy["values"]:
                combo.addItem(value["name"], value["id"])
            selected_value = (taxonomy_values or {}).get(int(taxonomy["id"]))
            if selected_value is not None:
                index = combo.findData(selected_value)
                if index >= 0:
                    combo.setCurrentIndex(index)
            self.taxonomy_widgets[int(taxonomy["id"])] = combo
            skip = self._metadata_skip_checkbox(combo)
            self.taxonomy_skip_widgets[int(taxonomy["id"])] = skip
            self.form.addRow(f"Taxonomie: {taxonomy['name']}", self._metadata_row(skip, combo))
        for definition in self.properties:
            widget = self._property_widget(definition, (property_values or {}).get(int(definition["id"]), ""))
            self.property_widgets[int(definition["id"])] = widget
            skip = self._metadata_skip_checkbox(widget)
            self.property_skip_widgets[int(definition["id"])] = skip
            self.form.addRow(definition["name"], self._metadata_row(skip, widget))
        self.form.addRow("Aantal subvragen", self.subquestion_count)
        self.subquestion_table = QWidget()
        self.subquestion_table.setToolTip(
            "Elke kaart is een subvraag. Gebruik de knop Metadata om taxonomieën en classificaties per subvraag te koppelen."
        )
        self.subquestion_cards_layout = QVBoxLayout(self.subquestion_table)
        self.subquestion_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.subquestion_cards_layout.setSpacing(12)
        self.form.addRow("Subvragen", self.subquestion_table)
        self._source_subquestions = [dict(row) for row in (subquestions or [])]
        if version:
            self.title.setText(str(version.get("title") or ""))
            self.question_text.setPlainText(str(version.get("question_text") or ""))
            self.short_description.setText(str(version.get("short_description") or ""))
            self.status.setCurrentText(str(version.get("status") or "Actief"))
            self.maximum_score.setValue(int(float(version.get("maximum_score") or 1)))
            self.minutes.setValue(int(float(version.get("expected_time_minutes") or 0)))
            self.is_multiple_choice.setChecked(bool(version.get("is_multiple_choice")))
            self.multiple_choice_answer.setText(str(version.get("multiple_choice_answer") or ""))
        if self._source_subquestions:
            self.question_with_subquestions.setChecked(True)
            self.subquestion_count.setValue(len(self._source_subquestions))
        self.is_multiple_choice.toggled.connect(self.update_visibility)
        self.single_question.toggled.connect(self.update_visibility)
        self.question_with_subquestions.toggled.connect(self.update_visibility)
        self.subquestion_count.valueChanged.connect(self.rebuild_subquestions)
        self.rebuild_subquestions()
        self.update_visibility()
        fit_to_available_screen(self, 980, 720)

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

    def uses_subquestions(self) -> bool:
        return self.question_with_subquestions.isChecked()

    def _set_form_row_visible(self, widget: QWidget, visible: bool) -> None:
        widget.setVisible(visible)
        label = self.form.labelForField(widget)
        if label:
            label.setVisible(visible)

    def update_visibility(self) -> None:
        uses_subquestions = self.uses_subquestions()
        show_answer = self.is_multiple_choice.isChecked() and not uses_subquestions
        self.multiple_choice_answer.setEnabled(show_answer)
        self.multiple_choice_answer.setVisible(show_answer)
        if self.multiple_choice_answer_label:
            self.multiple_choice_answer_label.setVisible(show_answer)
        if not show_answer:
            self.multiple_choice_answer.clear()
        if uses_subquestions:
            self.is_multiple_choice.setChecked(False)
            self.multiple_choice_answer.clear()
            self.structure_explanation.setText(
                "<b>Hoofdvraag met subvragen:</b> de hoofdvraag krijgt zelf geen score. "
                "Vul punten, tijd, metadata en een eventuele meerkeuzesleutel uitsluitend per subvraag in."
            )
        else:
            self.structure_explanation.setText(
                "<b>Losse vraag:</b> deze vraag krijgt één eigen score en bevat geen subvragen."
            )
        for widget in (self.maximum_score, self.minutes, self.is_multiple_choice, self.multiple_choice_answer):
            self._set_form_row_visible(widget, not uses_subquestions)
        self.multiple_choice_answer.setVisible(show_answer)
        if self.multiple_choice_answer_label:
            self.multiple_choice_answer_label.setVisible(show_answer)
        for widget in (self.subquestion_count, self.subquestion_table):
            self._set_form_row_visible(widget, uses_subquestions)
        question_text_label = self.form.labelForField(self.question_text)
        if question_text_label:
            question_text_label.setText("Tekst hoofdvraag" if uses_subquestions else "Volledige vraagtekst")

    def _snapshot_subquestions(self) -> list[dict[str, object]]:
        snapshots = []
        for row in self.subquestion_rows:
            snapshots.append(
                {
                    "id": row.get("id"),
                    "subquestion": row["subquestion"],
                    "question_text": row["question_text"].toPlainText(),
                    "maximum_score": row["maximum_score"].value(),
                    "short_description": row["short_description"].text(),
                    "expected_time_minutes": row["expected_time_minutes"].value(),
                    "taxonomy_values": dict(row.get("taxonomy_values") or {}),
                    "property_values": dict(row.get("property_values") or {}),
                    "is_multiple_choice": row["is_multiple_choice"].isChecked(),
                    "multiple_choice_answer": row["multiple_choice_answer"].text(),
                }
            )
        return snapshots

    def rebuild_subquestions(self) -> None:
        if self._rebuilding:
            return
        self._rebuilding = True
        snapshots = self._snapshot_subquestions()
        while len(snapshots) < self.subquestion_count.value():
            index = len(snapshots)
            source = self._source_subquestions[index] if index < len(self._source_subquestions) else None
            snapshots.append(
                {
                    "id": source.get("id") if source else None,
                    "subquestion": source.get("subquestion") if source else chr(ord("a") + index),
                    "question_text": source.get("question_text") if source else "",
                    "maximum_score": int(float(source.get("maximum_score") or 1)) if source else 1,
                    "short_description": source.get("short_description") if source else "",
                    "expected_time_minutes": int(float(source.get("expected_time_minutes") or 0)) if source else 0,
                    "taxonomy_values": source.get("taxonomy_values") if source else {},
                    "property_values": source.get("property_values") if source else {},
                    "is_multiple_choice": bool(source.get("is_multiple_choice")) if source else False,
                    "multiple_choice_answer": source.get("multiple_choice_answer") if source else "",
                }
            )
        snapshots = snapshots[: self.subquestion_count.value()]
        while self.subquestion_cards_layout.count():
            item = self.subquestion_cards_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.subquestion_rows = []
        for row_index, snapshot in enumerate(snapshots):
            subquestion = str(snapshot.get("subquestion") or chr(ord("a") + row_index))
            question_text = QTextEdit()
            question_text.setPlainText(str(snapshot.get("question_text") or ""))
            question_text.setMinimumHeight(80)
            question_text.setPlaceholderText(f"Vraagtekst voor subvraag {subquestion}")
            maximum_score = QSpinBox()
            maximum_score.setRange(1, 1000)
            maximum_score.setValue(int(snapshot.get("maximum_score") or 1))
            short_description = QLineEdit(str(snapshot.get("short_description") or ""))
            short_description.setPlaceholderText("Korte omschrijving voor deze subvraag")
            expected_time = QSpinBox()
            expected_time.setRange(0, 600)
            expected_time.setSpecialValueText("Niet ingevuld")
            expected_time.setValue(int(snapshot.get("expected_time_minutes") or 0))
            metadata_button = set_button_role(QPushButton("Metadata"), "secondary")
            metadata_button.setFixedHeight(32)
            is_multiple_choice = QCheckBox("Meerkeuzevraag")
            is_multiple_choice.setChecked(bool(snapshot.get("is_multiple_choice")))
            answer = QLineEdit(str(snapshot.get("multiple_choice_answer") or ""))
            answer.setMaxLength(1)
            answer.setPlaceholderText("Bijvoorbeeld A")
            answer_label = QLabel("Standaardantwoord")
            self._set_subquestion_answer_visible(answer, is_multiple_choice.isChecked(), answer_label)
            is_multiple_choice.toggled.connect(
                lambda checked, target=answer, label=answer_label: self._set_subquestion_answer_visible(
                    target,
                    checked,
                    label,
                )
            )

            card = QFrame()
            card.setObjectName("panel")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(10)

            header = QHBoxLayout()
            title = QLabel(f"<b>Subvraag {html.escape(subquestion)}</b>")
            title.setMinimumHeight(32)
            header.addWidget(title)
            header.addStretch()
            header.addWidget(metadata_button)
            card_layout.addLayout(header)

            card_layout.addWidget(QLabel("Vraagtekst"))
            card_layout.addWidget(question_text)

            details = QGridLayout()
            details.setContentsMargins(0, 0, 0, 0)
            details.setHorizontalSpacing(12)
            details.setVerticalSpacing(6)
            details.addWidget(QLabel("Max. punten"), 0, 0)
            details.addWidget(QLabel("Tijd (min.)"), 0, 1)
            details.addWidget(QLabel("Omschrijving"), 0, 2)
            details.addWidget(maximum_score, 1, 0)
            details.addWidget(expected_time, 1, 1)
            details.addWidget(short_description, 1, 2)
            details.setColumnStretch(0, 0)
            details.setColumnStretch(1, 0)
            details.setColumnStretch(2, 1)
            maximum_score.setMinimumWidth(110)
            expected_time.setMinimumWidth(120)
            card_layout.addLayout(details)

            mc_row = QHBoxLayout()
            mc_row.setContentsMargins(0, 0, 0, 0)
            mc_row.setSpacing(10)
            answer.setMinimumWidth(180)
            mc_row.addWidget(is_multiple_choice)
            mc_row.addWidget(answer_label)
            mc_row.addWidget(answer)
            mc_row.addStretch()
            card_layout.addLayout(mc_row)

            row_data = {
                "id": snapshot.get("id"),
                "subquestion": subquestion,
                "question_text": question_text,
                "maximum_score": maximum_score,
                "short_description": short_description,
                "expected_time_minutes": expected_time,
                "taxonomy_values": dict(snapshot.get("taxonomy_values") or {}),
                "property_values": dict(snapshot.get("property_values") or {}),
                "is_multiple_choice": is_multiple_choice,
                "multiple_choice_answer": answer,
            }
            metadata_button.setText(self._subquestion_metadata_button_text(row_data))
            metadata_button.clicked.connect(
                lambda _checked=False, row=row_data, button=metadata_button: self.edit_subquestion_metadata(row, button)
            )
            self.subquestion_rows.append(row_data)
            self.subquestion_cards_layout.addWidget(card)
        self.subquestion_cards_layout.addStretch()
        self._rebuilding = False

    def _set_subquestion_answer_visible(
        self,
        answer: QLineEdit,
        visible: bool,
        label: QLabel | None = None,
    ) -> None:
        if not visible:
            answer.clear()
        answer.setEnabled(visible)
        answer.setVisible(visible)
        if label:
            label.setVisible(visible)

    def _subquestion_metadata_button_text(self, row: dict[str, object]) -> str:
        count = len(dict(row.get("taxonomy_values") or {})) + len(dict(row.get("property_values") or {}))
        return "Metadata" if count == 0 else f"Metadata ({count})"

    def edit_subquestion_metadata(self, row: dict[str, object], button: QPushButton) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Metadata voor subvraag {row['subquestion']}")
        fit_to_available_screen(dialog, 820, 620)
        layout = QVBoxLayout(dialog)
        note = QLabel(
            "Koppel hier taxonomieën en classificaties specifiek aan deze subvraag. "
            "Vink 'Niet meenemen' aan als een onderdeel niet bij deze subvraag hoort."
        )
        note.setWordWrap(True)
        note.setObjectName("panel")
        layout.addWidget(note)
        taxonomy_widgets: dict[int, QComboBox] = {}
        taxonomy_skip_widgets: dict[int, QCheckBox] = {}
        property_widgets: dict[int, QWidget] = {}
        property_skip_widgets: dict[int, QCheckBox] = {}
        current_taxonomies = dict(row.get("taxonomy_values") or {})
        current_properties = dict(row.get("property_values") or {})
        for taxonomy in self.taxonomies:
            taxonomy_id = int(taxonomy["id"])
            widget = self._taxonomy_widget(taxonomy, current_taxonomies.get(taxonomy_id))
            skip = self._metadata_skip_checkbox(widget)
            taxonomy_widgets[taxonomy_id] = widget
            taxonomy_skip_widgets[taxonomy_id] = skip
            layout.addLayout(self._metadata_dialog_row(f"Taxonomie: {taxonomy['name']}", skip, widget))
        for definition in self.properties:
            property_id = int(definition["id"])
            widget = self._property_widget(definition, current_properties.get(property_id, ""))
            skip = self._metadata_skip_checkbox(widget)
            property_widgets[property_id] = widget
            property_skip_widgets[property_id] = skip
            layout.addLayout(self._metadata_dialog_row(str(definition["name"]), skip, widget))
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        row["taxonomy_values"] = {
            taxonomy_id: widget.currentData()
            for taxonomy_id, widget in taxonomy_widgets.items()
            if not (
                taxonomy_skip_widgets.get(taxonomy_id)
                and taxonomy_skip_widgets[taxonomy_id].isChecked()
            )
            and widget.currentData() is not None
        }
        row["property_values"] = {
            property_id: self._widget_text(widget)
            for property_id, widget in property_widgets.items()
            if not (
                property_skip_widgets.get(property_id)
                and property_skip_widgets[property_id].isChecked()
            )
            and self._widget_text(widget)
        }
        button.setText(self._subquestion_metadata_button_text(row))

    def _metadata_dialog_row(self, label_text: str, checkbox: QCheckBox, target: QWidget) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        label = QLabel(label_text)
        label.setMinimumWidth(220)
        target.setMinimumHeight(42)
        row.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(checkbox, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(target, 1, Qt.AlignmentFlag.AlignVCenter)
        return row

    def accept(self) -> None:
        if not self.required(self.title, "een titel"):
            return
        if self.is_multiple_choice.isChecked():
            try:
                normalize_multiple_choice_response(self.multiple_choice_answer.text())
            except ResultValidationError as error:
                QMessageBox.warning(self, "Antwoordsleutel ongeldig", str(error))
                return
        if self.uses_subquestions():
            if len(self.subquestion_rows) < 2:
                QMessageBox.warning(
                    self,
                    "Subvragen ontbreken",
                    "Een hoofdvraag met subvragen moet minimaal twee subvragen bevatten.",
                )
                return
            for row in self.subquestion_rows:
                if row["is_multiple_choice"].isChecked():
                    try:
                        normalize_multiple_choice_response(row["multiple_choice_answer"].text())
                    except ResultValidationError as error:
                        QMessageBox.warning(
                            self,
                            "Antwoordsleutel ongeldig",
                            f"Subvraag {row['subquestion']}: {error}",
                        )
                        return
        super().accept()

    def payload(self) -> dict[str, object]:
        taxonomy_values = {
            taxonomy_id: widget.currentData()
            for taxonomy_id, widget in self.taxonomy_widgets.items()
            if not (
                self.taxonomy_skip_widgets.get(taxonomy_id)
                and self.taxonomy_skip_widgets[taxonomy_id].isChecked()
            )
            and widget.currentData() is not None
        }
        property_values = {
            property_id: self._widget_text(widget)
            for property_id, widget in self.property_widgets.items()
            if not (
                self.property_skip_widgets.get(property_id)
                and self.property_skip_widgets[property_id].isChecked()
            )
            and self._widget_text(widget)
        }
        is_multiple_choice = self.is_multiple_choice.isChecked() and not self.uses_subquestions()
        subquestions = []
        if self.uses_subquestions():
            for order, row in enumerate(self.subquestion_rows):
                row_is_mc = row["is_multiple_choice"].isChecked()
                subquestions.append(
                    {
                        "id": row.get("id"),
                        "subquestion": row["subquestion"],
                        "question_text": row["question_text"].toPlainText().strip(),
                        "short_description": row["short_description"].text().strip(),
                        "maximum_score": row["maximum_score"].value(),
                        "expected_time_minutes": row["expected_time_minutes"].value() or None,
                        "taxonomy_values": dict(row.get("taxonomy_values") or {}),
                        "property_values": dict(row.get("property_values") or {}),
                        "is_multiple_choice": int(row_is_mc),
                        "multiple_choice_answer": normalize_multiple_choice_response(row["multiple_choice_answer"].text())
                        if row_is_mc else None,
                        "sort_order": order,
                    }
                )
        return {
            "title": self.title.text().strip(),
            "question_text": self.question_text.toPlainText().strip(),
            "short_description": self.short_description.text().strip(),
            "status": self.status.currentText(),
            "maximum_score": sum(float(row["maximum_score"]) for row in subquestions)
            if subquestions else self.maximum_score.value(),
            "expected_time_minutes": sum(float(row["expected_time_minutes"] or 0) for row in subquestions) or None
            if subquestions else self.minutes.value() or None,
            "is_multiple_choice": int(is_multiple_choice),
            "multiple_choice_answer": normalize_multiple_choice_response(self.multiple_choice_answer.text())
            if is_multiple_choice else None,
            "taxonomy_values": taxonomy_values,
            "property_values": property_values,
            "subquestions": subquestions,
        }



class QuestionDatabaseAnalysisDialog(QDialog):
    def __init__(
        self,
        database: SubjectDatabase,
        item_id: int,
        latest_version_id: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.item_id = item_id
        self.latest_version_id = latest_version_id
        item_row = database.rows("SELECT title, status FROM question_bank_items WHERE id=?", (item_id,))[0]
        self.setWindowTitle(f"Vraaganalyse - {item_row['title']}")
        fit_to_available_screen(self, 1100, 760)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel(f"Vraaganalyse - {item_row['title']}")
        title.setObjectName("pageTitle")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("Versies"))
        self.version_scope = QComboBox()
        self.version_scope.addItem("Nieuwste versie", "latest")
        self.version_scope.addItem("Alle versies", "all")
        self.version_scope.currentIndexChanged.connect(self.refresh)
        header.addWidget(self.version_scope)
        layout.addLayout(header)

        self.summary = QLabel()
        self.summary.setObjectName("panel")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        explanation = QLabel(
            "Dit dashboard gebruikt alle gekoppelde afnames van deze databasevraag. Bij een vraag met subvragen "
            "ziet u zowel de totaalanalyse van de hoofdvraag als de afzonderlijke subvragen."
        )
        explanation.setObjectName("panel")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.table = QTableWidget()
        configure_table(
            self.table,
            ["Onderdeel", "Afnames", "Gem. %", "P-waarde", "Rit", "Rir", "Conclusie"],
        )
        layout.addWidget(self.table, 1)

        occurrence_title = QLabel("<b>Afnames per toets</b>")
        layout.addWidget(occurrence_title)
        self.occurrence_table = QTableWidget()
        configure_table(
            self.occurrence_table,
            [
                "Schooljaar",
                "Toets",
                "Vraag",
                "Niveau",
                "Leerjaar",
                "Groep(en)",
                "Afnames",
                "% van punten",
                "P-waarde",
                "Rit",
                "Rir",
                "Conclusie",
            ],
        )
        layout.addWidget(self.occurrence_table, 1)

        breakdown_title = QLabel("<b>Verschillen tussen schooljaren, niveaus, leerjaren en groepen</b>")
        layout.addWidget(breakdown_title)
        self.breakdown_table = QTableWidget()
        configure_table(
            self.breakdown_table,
            ["Uitsplitsing", "Categorie", "Scores", "% van punten", "Gem. score", "P-waarde", "Rit", "Rir"],
        )
        layout.addWidget(self.breakdown_table, 1)

        self.usage = QLabel()
        self.usage.setObjectName("panel")
        self.usage.setWordWrap(True)
        layout.addWidget(self.usage)
        self.refresh()

    @staticmethod
    def _average(values: list[float]) -> float | None:
        return sum(values) / len(values) if values else None

    @staticmethod
    def _format_percentage(value: float | None) -> str:
        return "-" if value is None else f"{round(value)}%"

    @staticmethod
    def _format_decimal(value: float | None) -> str:
        return "-" if value is None else f"{value:.2f}".replace(".", ",")

    @staticmethod
    def _conclusion(p_value: float | None, rit: float | None, rir: float | None) -> str:
        concerns = []
        if p_value is not None and (p_value < 0.20 or p_value > 0.90):
            concerns.append("moeilijkheid controleren")
        if rit is not None and rit < 0.20:
            concerns.append("lage samenhang met totaalscore")
        if rir is not None and rir < 0.10:
            concerns.append("lage samenhang met rest van toets")
        return "Aandacht: " + ", ".join(concerns) if concerns else "Binnen advieswaarden"

    def _linked_rows(self) -> list[dict]:
        conditions = ["q.question_bank_id=?"]
        parameters: list[object] = [self.item_id]
        if self.version_scope.currentData() == "latest":
            conditions.append("q.question_bank_version_id=?")
            parameters.append(self.latest_version_id)
        return [
            dict(row)
            for row in self.database.rows(
                "SELECT q.id, q.test_id, q.question_number, q.subquestion, q.question_bank_version_id, "
                "t.name AS test_name, t.level, t.grade_year, sy.name AS school_year "
                "FROM matrix_questions q JOIN tests t ON t.id=q.test_id "
                "JOIN school_years sy ON sy.id=t.school_year_id "
                "WHERE " + " AND ".join(conditions) + " "
                "ORDER BY sy.name DESC, t.created_at DESC, CAST(q.question_number AS INTEGER), "
                "q.question_number, COALESCE(q.subquestion, '')",
                tuple(parameters),
            )
        ]

    def refresh(self) -> None:
        linked_rows = self._linked_rows()
        if not linked_rows:
            self.summary.setText("Deze versie is nog niet in een toets gebruikt.")
            self.table.setRowCount(0)
            self.occurrence_table.setRowCount(0)
            self.breakdown_table.setRowCount(0)
            self.usage.setText("")
            return
        metrics: dict[str, dict[str, object]] = {}
        tests = {int(row["test_id"]) for row in linked_rows}
        linked_by_test_question: dict[tuple[int, str], list[dict]] = defaultdict(list)
        linked_by_id = {int(row["id"]): row for row in linked_rows}
        for row in linked_rows:
            linked_by_test_question[(int(row["test_id"]), str(row["question_number"]))].append(row)

        for test_id in tests:
            try:
                data = analysis_data(self.database, test_id, include_resit=False)
            except Exception:
                continue
            item_by_id = {
                int(metric["id"]): metric
                for metric in data.get("item_analysis", [])
                if isinstance(metric.get("id"), int)
            }
            for (group_test_id, question_number), group_rows in linked_by_test_question.items():
                if group_test_id != test_id or not any(row.get("subquestion") for row in group_rows):
                    continue
                group_metric = next(
                    (
                        metric for metric in data.get("question_group_analysis", [])
                        if str(metric.get("question_number")) == str(question_number)
                        and metric.get("row_type") == "group"
                    ),
                    None,
                )
                if group_metric:
                    self._append_metric(metrics, "Hoofdvraag totaal", group_metric)
            for question_id, source_row in linked_by_id.items():
                if int(source_row["test_id"]) != test_id:
                    continue
                metric = item_by_id.get(question_id)
                if not metric:
                    continue
                label = (
                    f"Subvraag {source_row['subquestion']}"
                    if source_row.get("subquestion")
                    else "Losse vraag"
                )
                self._append_metric(metrics, label, metric)

        rows = []
        for label, bucket in metrics.items():
            p_values = bucket["p_values"]
            rit_values = bucket["rit_values"]
            rir_values = bucket["rir_values"]
            p = self._average(p_values)
            rit = self._average(rit_values)
            rir = self._average(rir_values)
            rows.append(
                {
                    "label": label,
                    "count": bucket["count"],
                    "percentage": p * 100 if p is not None else None,
                    "p": p,
                    "rit": rit,
                    "rir": rir,
                    "conclusion": self._conclusion(p, rit, rir),
                }
            )
        order = {"Hoofdvraag totaal": 0, "Losse vraag": 0}
        rows.sort(key=lambda row: (order.get(str(row["label"]), 1), str(row["label"])))
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["label"],
                row["count"],
                self._format_percentage(row["percentage"]),
                self._format_decimal(row["p"]),
                self._format_decimal(row["rit"]),
                self._format_decimal(row["rir"]),
                row["conclusion"],
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, item(value))
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.refresh_occurrence_table(linked_rows)
        self.refresh_breakdown_table(linked_rows)
        mean_percentages = [float(row["percentage"]) for row in rows if row["percentage"] is not None]
        summary_percentage = self._average(mean_percentages)
        used_versions = sorted({int(row["question_bank_version_id"]) for row in linked_rows if row["question_bank_version_id"]})
        self.summary.setText(
            f"<b>Gebruik:</b> {len(tests)} toets(en), {len(linked_rows)} gekoppelde vraagregel(s). "
            f"<b>Gemiddeld:</b> {self._format_percentage(summary_percentage)} van de punten. "
            f"<b>Versies in beeld:</b> {len(used_versions)}."
        )
        usage_lines = ["<b>Afnames:</b>"]
        seen = set()
        for row in linked_rows:
            key = (row["test_id"], row["question_number"])
            if key in seen:
                continue
            seen.add(key)
            label = f"{row['test_name']} ({row['school_year']}, {row['level'] or '-'} {row['grade_year'] or '-'})"
            usage_lines.append(f"- {html.escape(label)}, vraag {html.escape(str(row['question_number']))}")
        self.usage.setText("<br>".join(usage_lines))

    def _append_metric(self, metrics: dict[str, dict[str, object]], label: str, metric: dict[str, object]) -> None:
        bucket = metrics.setdefault(label, {"count": 0, "p_values": [], "rit_values": [], "rir_values": []})
        bucket["count"] = int(bucket["count"]) + 1
        for source_key, target_key in (("p_value", "p_values"), ("rit", "rit_values"), ("rir", "rir_values")):
            value = metric.get(source_key)
            if value is not None:
                bucket[target_key].append(float(value))

    def refresh_occurrence_table(self, linked_rows: list[dict]) -> None:
        entries = self.occurrence_entries(linked_rows)
        self.occurrence_table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            values = [
                entry["school_year"],
                entry["test_name"],
                entry["question_label"],
                entry["level"],
                entry["grade_year"],
                entry["groups"],
                entry["attempts"],
                self._format_percentage(entry["percentage"]),
                self._format_decimal(entry["p_value"]),
                self._format_decimal(entry["rit"]),
                self._format_decimal(entry["rir"]),
                entry["conclusion"],
            ]
            for column, value in enumerate(values):
                self.occurrence_table.setItem(row_index, column, item(value))
        self.occurrence_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def occurrence_entries(self, linked_rows: list[dict]) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = []
        group_names_by_test = self._group_names_by_test({int(row["test_id"]) for row in linked_rows})
        for test_id in sorted({int(row["test_id"]) for row in linked_rows}):
            try:
                data = analysis_data(self.database, test_id, include_resit=False)
            except Exception:
                continue
            item_by_id = {
                int(metric["id"]): metric
                for metric in data.get("item_analysis", [])
                if isinstance(metric.get("id"), int)
            }
            for row in linked_rows:
                if int(row["test_id"]) != test_id:
                    continue
                metric = item_by_id.get(int(row["id"]))
                percentage = (
                    float(metric["p_value"]) * 100
                    if metric and metric.get("p_value") is not None
                    else None
                )
                p_value = float(metric["p_value"]) if metric and metric.get("p_value") is not None else None
                rit = float(metric["rit"]) if metric and metric.get("rit") is not None else None
                rir = float(metric["rir"]) if metric and metric.get("rir") is not None else None
                entries.append(
                    {
                        "school_year": row.get("school_year") or "-",
                        "test_name": row.get("test_name") or "-",
                        "question_label": f"{row['question_number']}{row.get('subquestion') or ''}",
                        "level": row.get("level") or "-",
                        "grade_year": row.get("grade_year") or "-",
                        "groups": group_names_by_test.get(test_id) or "-",
                        "attempts": data.get("participant_count", 0),
                        "percentage": percentage,
                        "p_value": p_value,
                        "rit": rit,
                        "rir": rir,
                        "conclusion": self._conclusion(p_value, rit, rir) if metric else "Nog geen complete resultaten",
                    }
                )
        entries.sort(
            key=lambda entry: (
                str(entry["school_year"]),
                str(entry["test_name"]).casefold(),
                str(entry["question_label"]),
            ),
            reverse=True,
        )
        return entries

    def _group_names_by_test(self, test_ids: set[int]) -> dict[int, str]:
        if not test_ids:
            return {}
        placeholders = ",".join("?" for _ in test_ids)
        rows = self.database.rows(
            "SELECT tc.test_id, GROUP_CONCAT(c.name, ', ') AS group_names "
            "FROM test_classes tc JOIN classes c ON c.id=tc.class_id "
            f"WHERE tc.test_id IN ({placeholders}) GROUP BY tc.test_id",
            tuple(test_ids),
        )
        return {int(row["test_id"]): str(row["group_names"] or "") for row in rows}

    def refresh_breakdown_table(self, linked_rows: list[dict]) -> None:
        entries = self.breakdown_entries(linked_rows)
        self.breakdown_table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            values = [
                entry["dimension"],
                entry["category"],
                entry["count"],
                self._format_percentage(entry["percentage"]),
                self._format_decimal(entry["average_score"]),
                self._format_decimal(entry["p_value"]),
                self._format_decimal(entry["rit"]),
                self._format_decimal(entry["rir"]),
            ]
            for column, value in enumerate(values):
                self.breakdown_table.setItem(row_index, column, item(value))
        self.breakdown_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def breakdown_entries(self, linked_rows: list[dict]) -> list[dict[str, object]]:
        question_ids = sorted({int(row["id"]) for row in linked_rows})
        if not question_ids:
            return []
        placeholders = ",".join("?" for _ in question_ids)
        score_rows = self.database.rows(
            "SELECT sy.name AS school_year, "
            "COALESCE(NULLIF(t.level, ''), 'Onbekend') AS level, "
            "COALESCE(NULLIF(t.grade_year, ''), 'Onbekend') AS grade_year, "
            "COALESCE(NULLIF(c.name, ''), 'Onbekend') AS group_name, "
            "sc.score, q.maximum_score, a.total_score "
            "FROM scores sc "
            "JOIN test_attempts a ON a.id=sc.attempt_id "
            "JOIN matrix_questions q ON q.id=sc.question_id "
            "JOIN tests t ON t.id=q.test_id "
            "JOIN school_years sy ON sy.id=t.school_year_id "
            "LEFT JOIN enrollments e ON e.student_id=a.student_id AND e.school_year_id=t.school_year_id "
            "LEFT JOIN classes c ON c.id=e.class_id "
            f"WHERE q.id IN ({placeholders}) AND a.status='gemaakt' AND sc.score IS NOT NULL",
            tuple(question_ids),
        )
        buckets: dict[tuple[str, str], dict[str, object]] = defaultdict(
            lambda: {"count": 0.0, "score": 0.0, "maximum": 0.0, "scores": [], "totals": [], "rests": []}
        )
        for row in score_rows:
            dimensions = {
                "Schooljaar": str(row["school_year"] or "Onbekend"),
                "Niveau": str(row["level"] or "Onbekend"),
                "Leerjaar": str(row["grade_year"] or "Onbekend"),
                "Groep": str(row["group_name"] or "Onbekend"),
            }
            score = float(row["score"] or 0)
            maximum = float(row["maximum_score"] or 0)
            total_score = float(row["total_score"] or 0)
            for dimension, category in dimensions.items():
                bucket = buckets[(dimension, category)]
                bucket["count"] += 1
                bucket["score"] += score
                bucket["maximum"] += maximum
                bucket["scores"].append(score)
                bucket["totals"].append(total_score)
                bucket["rests"].append(total_score - score)
        entries = []
        dimension_order = {"Schooljaar": 0, "Niveau": 1, "Leerjaar": 2, "Groep": 3}
        for (dimension, category), bucket in buckets.items():
            maximum = bucket["maximum"]
            count = int(bucket["count"])
            p_value = bucket["score"] / maximum if maximum else None
            rit = self._pearson(bucket["scores"], bucket["totals"])
            rir = self._pearson(bucket["scores"], bucket["rests"])
            entries.append(
                {
                    "dimension": dimension,
                    "category": category,
                    "count": count,
                    "percentage": bucket["score"] / maximum * 100 if maximum else None,
                    "average_score": bucket["score"] / count if count else None,
                    "p_value": p_value,
                    "rit": rit,
                    "rir": rir,
                }
            )
        entries.sort(key=lambda entry: (dimension_order.get(str(entry["dimension"]), 99), str(entry["category"]).lower()))
        return entries

    @staticmethod
    def _pearson(left: list[float], right: list[float]) -> float | None:
        if len(left) < 2 or len(left) != len(right):
            return None
        mean_left = sum(left) / len(left)
        mean_right = sum(right) / len(right)
        numerator = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right))
        left_sum = sum((a - mean_left) ** 2 for a in left)
        right_sum = sum((b - mean_right) ** 2 for b in right)
        denominator = (left_sum * right_sum) ** 0.5
        if denominator == 0:
            return None
        return numerator / denominator



class QuestionDatabasePage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        scroll_area.setWidget(content)
        outer_layout.addWidget(scroll_area)
        add = set_button_role(QPushButton("Vraag toevoegen"), "primary")
        add.clicked.connect(self.add_question)
        analyse = set_button_role(QPushButton("Vraaganalyse openen"), "secondary")
        analyse.clicked.connect(self.open_question_analysis)
        edit = set_button_role(QPushButton("Vraag bewerken"), "secondary")
        edit.clicked.connect(self.edit_question)
        delete = set_button_role(QPushButton("Verwijderen"), "danger")
        delete.clicked.connect(self.delete_question)
        layout.addWidget(
            make_page_header(
                "Vraagdatabase",
                "Beheer vaste vragen en volg vraagkwaliteit over afnames heen.",
                [delete, edit, analyse, add],
            )
        )
        intro = QLabel(
            "Beheer vaste vragen die u later in toetsen kunt gebruiken. Scores uit toetsen blijven gekoppeld, "
            "zodat u de kwaliteit van een vraag over afnames heen kunt bekijken."
        )
        intro.setObjectName("panel")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.filters = QuestionDatabaseFilterPanel(database, self)
        self.filters.changed.connect(self.refresh)
        layout.addWidget(self.filters)
        self.count_label = QLabel()
        self.count_label.setContentsMargins(0, 2, 0, 2)
        layout.addWidget(self.count_label)
        self.empty_state = make_empty_state(
            "Geen databasevragen zichtbaar",
            "Voeg een vraag toe of pas de filters aan. Extra filters voor taxonomieën en classificaties staan achter de filterknop.",
        )
        layout.addWidget(self.empty_state)
        self.table = QTableWidget()
        self.table.setMinimumHeight(260)
        self.table.cellDoubleClicked.connect(lambda row, column: self.edit_question(row))
        layout.addWidget(self.table, 1)
        self.usage = QLabel()
        self.usage.setObjectName("panel")
        self.usage.setWordWrap(True)
        layout.addWidget(self.usage)
        layout.addStretch(1)
        self.refresh()

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Vraagdatabase",
            "intro": "In de vraagdatabase bewaart u vragen die u vaker wilt gebruiken of over meerdere jaren wilt analyseren.",
            "steps": [
                {
                    "title": "Een databasevraag maken",
                    "text": "Kies eerst of u één losse vraag maakt of één hoofdvraag met subvragen. Deze twee structuren kunnen niet tegelijk binnen dezelfde databasevraag voorkomen.",
                    "action": "Klik op 'Vraag toevoegen', kies de vraagstructuur en vul daarna alleen de getoonde velden in.",
                    "tip": "Bij een hoofdvraag met subvragen krijgt de hoofdvraag zelf geen score. Punten, tijd en meerkeuzegegevens vult u uitsluitend per subvraag in.",
                },
                {
                    "title": "Vragen terugvinden",
                    "text": "Gebruik de filterbalk om snel te zoeken op titel, vraagtekst, taxonomie, vraagclassificatie, meerkeuze, subvragen of gebruik.",
                    "action": "Kies één of meer filters; de tabel toont direct alleen de passende databasevragen.",
                    "tip": "Dezelfde filters ziet u ook wanneer u vanuit een toets een vraag uit de vraagdatabase toevoegt.",
                },
                {
                    "title": "Gebruiken in een toets",
                    "text": "In het vragenoverzicht kunt u een vraag uit de vraagdatabase toevoegen. De inhoud wordt overgenomen en de score blijft gekoppeld aan de databasevraag.",
                    "action": "Ga naar Vragenoverzicht en kies 'Vraag uit vraagdatabase'.",
                    "tip": "Alleen taxonomieën en classificaties die in deze toets aanstaan worden aan de toetsvraag gekoppeld. Andere metadata blijft alleen in de Vraagdatabase staan.",
                },
                {
                    "title": "Kwaliteit bekijken",
                    "text": "De tabel toont gebruik, gemiddeld percentage goed en toetsstatistieken zoals P-waarde, Rit en Rir op basis van gekoppelde afnames.",
                    "action": "Selecteer een vraag en klik op 'Vraaganalyse openen' voor een apart dashboard met de nieuwste versie of alle versies.",
                    "tip": "Bij tekst- of puntenwijzigingen ontstaat pas na bevestiging een nieuwe versie. Metadata, status en omschrijving blijven binnen dezelfde versie.",
                },
            ],
        }

    def latest_versions(self) -> list[sqlite3.Row]:
        return question_database_latest_rows(self.database)

    def refresh(self) -> None:
        self.filters.refresh_property_choices()
        configure_table(
            self.table,
            [
                "Titel",
                "Korte databaseomschrijving",
                "Status",
                "Versie",
                "Punten",
                "Subvragen",
                "Taxonomie",
                "Classificaties",
                "Gebruikt",
                "Gem. %",
                "P",
                "Rit",
                "Rir",
            ],
        )
        all_rows = [dict(row) for row in self.latest_versions()]
        rows = [row for row in all_rows if self.filters.matches(row)]
        self.empty_state.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            quality = self.quality_for_item(int(row["item_id"]))
            values = [
                row["title"],
                row.get("short_description") or "-",
                row.get("status") or "Actief",
                row["version_number"],
                f"{float(row['maximum_score']):g}",
                row["subquestion_count"],
                row.get("taxonomy_summary") or "-",
                row.get("property_summary") or "-",
                quality["usage_count"],
                self.format_optional_percentage(quality["mean_percentage"]),
                self.format_optional_decimal(quality["p_value"]),
                self.format_optional_decimal(quality["rit"]),
                self.format_optional_decimal(quality["rir"]),
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, item(value))
            self.table.item(row_index, 0).setData(Qt.ItemDataRole.UserRole, row["item_id"])
            self.table.item(row_index, 0).setData(int(Qt.ItemDataRole.UserRole) + 1, row["version_id"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.count_label.setText(f"{len(rows)} van {len(all_rows)} vragen zichtbaar")
        self.update_usage()

    def format_optional_percentage(self, value: object) -> str:
        return "-" if value is None else f"{round(float(value))}%"

    def format_optional_decimal(self, value: object) -> str:
        return "-" if value is None else f"{float(value):.2f}".replace(".", ",")

    def current_item(self) -> tuple[int, int] | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        return (
            int(self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)),
            int(self.table.item(row, 0).data(int(Qt.ItemDataRole.UserRole) + 1)),
        )

    def quality_for_item(self, item_id: int) -> dict[str, object]:
        linked = self.database.rows(
            "SELECT q.id, q.test_id, q.maximum_score FROM matrix_questions q WHERE q.question_bank_id=?",
            (item_id,),
        )
        usage_count = len({int(row["test_id"]) for row in linked})
        score_rows = self.database.rows(
            "SELECT s.score, q.maximum_score FROM scores s "
            "JOIN matrix_questions q ON q.id=s.question_id "
            "JOIN test_attempts a ON a.id=s.attempt_id "
            "WHERE q.question_bank_id=? AND a.status='gemaakt' AND s.score IS NOT NULL",
            (item_id,),
        )
        percentages = [
            float(row["score"]) / float(row["maximum_score"]) * 100
            for row in score_rows
            if row["maximum_score"]
        ]
        metric_values = {"p_value": [], "rit": [], "rir": []}
        question_ids_by_test: dict[int, set[int]] = defaultdict(set)
        for row in linked:
            question_ids_by_test[int(row["test_id"])].add(int(row["id"]))
        for test_id, question_ids in question_ids_by_test.items():
            try:
                data = analysis_data(self.database, test_id, include_resit=False)
            except Exception:
                continue
            for metric in data.get("item_analysis", []):
                if int(metric.get("id")) in question_ids:
                    for key in metric_values:
                        if metric.get(key) is not None:
                            metric_values[key].append(float(metric[key]))
        return {
            "usage_count": usage_count,
            "mean_percentage": sum(percentages) / len(percentages) if percentages else None,
            "p_value": sum(metric_values["p_value"]) / len(metric_values["p_value"]) if metric_values["p_value"] else None,
            "rit": sum(metric_values["rit"]) / len(metric_values["rit"]) if metric_values["rit"] else None,
            "rir": sum(metric_values["rir"]) / len(metric_values["rir"]) if metric_values["rir"] else None,
        }

    def update_usage(self) -> None:
        current = self.current_item()
        if current is None:
            self.usage.setText("Selecteer een vraag om gebruiksgeschiedenis te bekijken.")
            return
        item_id, _version_id = current
        rows = self.database.rows(
            "SELECT t.name, t.period, sy.name AS school_year, q.question_number, q.subquestion, "
            "q.short_description AS usage_description "
            "FROM matrix_questions q JOIN tests t ON t.id=q.test_id "
            "JOIN school_years sy ON sy.id=t.school_year_id "
            "WHERE q.question_bank_id=? "
            "ORDER BY sy.name DESC, t.created_at DESC, CAST(q.question_number AS INTEGER), "
            "q.question_number, COALESCE(q.subquestion, '')",
            (item_id,),
        )
        if not rows:
            self.usage.setText("Deze vraag is nog niet in een toets gebruikt.")
            return
        lines = ["<b>Gebruikt in:</b>"]
        for row in rows:
            label = f"{row['question_number']}{row['subquestion'] or ''}"
            description = str(row["usage_description"] or "").strip()
            metadata = f" - {html.escape(description)}" if description else ""
            lines.append(
                f"- {html.escape(row['name'])} ({html.escape(row['school_year'])}, "
                f"{html.escape(row['period'])}), vraag {html.escape(label)}{metadata}"
            )
        self.usage.setText("<br>".join(lines))

    def on_activated(self) -> None:
        self.refresh()

    def load_version(self, version_id: int) -> tuple[dict, list[dict], dict[int, int], dict[int, str]]:
        version = dict(self.database.rows("SELECT * FROM question_bank_versions WHERE id=?", (version_id,))[0])
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

    def add_question(self) -> None:
        dialog = QuestionDatabaseDialog(load_all_taxonomies(self.database), load_active_question_properties(self.database), parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.save_new_question(dialog.payload())
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraag niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def edit_question(self, row: int | None = None) -> None:
        if isinstance(row, bool):
            row = None
        current = self.current_item()
        if current is None:
            QMessageBox.information(self, "Geen vraag geselecteerd", "Selecteer eerst een vraag om te bewerken.")
            return
        item_id, version_id = current
        version, subquestions, taxonomy_values, property_values = self.load_version(version_id)
        dialog = QuestionDatabaseDialog(
            load_all_taxonomies(self.database),
            load_active_question_properties(self.database),
            version,
            subquestions,
            taxonomy_values,
            property_values,
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        linked_count = int(self.database.scalar(
            "SELECT COUNT(*) FROM matrix_questions WHERE question_bank_id=?",
            (item_id,),
        ) or 0)
        if linked_count:
            old_labels = [str(row["subquestion"]) for row in subquestions]
            new_labels = [str(row["subquestion"]) for row in payload.get("subquestions", [])]
            if old_labels != new_labels:
                QMessageBox.warning(
                    self,
                    "Structuur niet aangepast",
                    "Deze databasevraag is al gekoppeld aan toetsvragen. U kunt tekst, punten en antwoordsleutel "
                    "aanpassen, maar niet wisselen tussen losse vraag en subvragen of subvraagletters wijzigen. "
                    "Maak hiervoor een nieuwe databasevraag.",
                )
                return
        significant = self.is_significant_version_change(
            version, subquestions, taxonomy_values, property_values, payload
        )
        if significant:
            message = (
                "Door een wijziging in vraagtekst of punten ontstaat een nieuwe versie van deze databasevraag.\n\n"
                "Bestaande toetsen blijven gekoppeld aan de versie die daar al gebruikt werd. Nieuwe toevoegingen "
                "gebruiken de nieuwste versie.\n\n"
                "Wilt u deze nieuwe versie opslaan?"
            )
            if QMessageBox.question(
                self,
                "Nieuwe vraagversie opslaan",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            ) != QMessageBox.StandardButton.Yes:
                return
        try:
            if significant:
                new_version_id = self.save_new_version(item_id, payload)
                if not linked_count:
                    self.sync_linked_questions(item_id, new_version_id)
            else:
                self.update_existing_version(version_id, item_id, payload)
                self.sync_linked_questions(item_id, version_id)
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Vraag niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def delete_question(self) -> None:
        current = self.current_item()
        if current is None:
            QMessageBox.information(self, "Geen vraag geselecteerd", "Selecteer eerst een vraag om te verwijderen.")
            return
        item_id, _version_id = current
        linked = self.database.scalar("SELECT COUNT(*) FROM matrix_questions WHERE question_bank_id=?", (item_id,))
        if linked:
            QMessageBox.warning(
                self,
                "Vraag in gebruik",
                "Deze vraag is al gekoppeld aan een toets en kan daarom niet worden verwijderd.",
            )
            return
        title = self.table.item(self.table.currentRow(), 0).text()
        answer = QMessageBox.question(
            self,
            "Vraag verwijderen",
            f"Weet u zeker dat u '{title}' uit de vraagdatabase wilt verwijderen?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.database.execute("DELETE FROM question_bank_items WHERE id=?", (item_id,))
        self.refresh()
        self.changed.emit()

    def open_question_analysis(self) -> None:
        current = self.current_item()
        if current is None:
            QMessageBox.information(self, "Geen vraag geselecteerd", "Selecteer eerst een vraag voor de analyse.")
            return
        item_id, version_id = current
        dialog = QuestionDatabaseAnalysisDialog(self.database, item_id, version_id, self)
        dialog.exec()

    def save_new_question(self, payload: dict[str, object]) -> int:
        cursor = self.database.connection.execute(
            "INSERT INTO question_bank_items(title, short_description, status, maximum_score, expected_time_minutes) "
            "VALUES(?, ?, ?, ?, ?)",
            (
                payload["title"],
                payload["short_description"],
                payload.get("status", "Actief"),
                payload["maximum_score"],
                payload["expected_time_minutes"],
            ),
        )
        item_id = int(cursor.lastrowid)
        self.save_new_version(item_id, payload, version_number=1)
        self.database.connection.commit()
        return item_id

    def normalized_version_signature(
        self,
        version: dict[str, object],
        subquestions: list[dict[str, object]],
        taxonomy_values: dict[int, int],
        property_values: dict[int, str],
    ) -> dict[str, object]:
        if subquestions:
            question_shape = [
                {
                    "subquestion": str(row.get("subquestion") or "").strip().lower(),
                    "question_text": str(row.get("question_text") or "").strip(),
                    "maximum_score": float(row.get("maximum_score") or 0),
                }
                for row in subquestions
            ]
        else:
            question_shape = [
                {
                    "subquestion": "",
                    "question_text": str(version.get("question_text") or "").strip(),
                    "maximum_score": float(version.get("maximum_score") or 0),
                }
            ]
        return {"question_shape": question_shape}

    def payload_version_signature(self, payload: dict[str, object]) -> dict[str, object]:
        return self.normalized_version_signature(
            {
                "question_text": payload.get("question_text"),
                "maximum_score": payload.get("maximum_score"),
                "expected_time_minutes": payload.get("expected_time_minutes"),
                "is_multiple_choice": payload.get("is_multiple_choice"),
                "multiple_choice_answer": payload.get("multiple_choice_answer"),
            },
            list(payload.get("subquestions", [])),
            dict(payload.get("taxonomy_values", {})),
            dict(payload.get("property_values", {})),
        )

    def is_significant_version_change(
        self,
        version: dict[str, object],
        subquestions: list[dict[str, object]],
        taxonomy_values: dict[int, int],
        property_values: dict[int, str],
        payload: dict[str, object],
    ) -> bool:
        current_signature = self.normalized_version_signature(
            version, subquestions, taxonomy_values, property_values
        )
        new_signature = self.payload_version_signature(payload)
        return current_signature != new_signature

    def update_existing_version(self, version_id: int, item_id: int, payload: dict[str, object]) -> None:
        self.database.connection.execute(
            "UPDATE question_bank_versions SET title=?, question_text=?, short_description=?, maximum_score=?, "
            "expected_time_minutes=?, is_multiple_choice=?, multiple_choice_answer=?, updated_at=CURRENT_TIMESTAMP "
            "WHERE id=?",
            (
                payload["title"],
                payload["question_text"],
                payload["short_description"],
                payload["maximum_score"],
                payload["expected_time_minutes"],
                payload["is_multiple_choice"],
                payload["multiple_choice_answer"],
                version_id,
            ),
        )
        self.database.connection.execute(
            "UPDATE question_bank_items SET title=?, short_description=?, status=?, maximum_score=?, expected_time_minutes=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                payload["title"],
                payload["short_description"],
                payload.get("status", "Actief"),
                payload["maximum_score"],
                payload["expected_time_minutes"],
                item_id,
            ),
        )
        self.database.connection.execute(
            "DELETE FROM question_bank_version_taxonomy_values WHERE version_id=?", (version_id,)
        )
        self.database.connection.execute(
            "DELETE FROM question_bank_version_property_values WHERE version_id=?", (version_id,)
        )
        for taxonomy_id, value_id in dict(payload["taxonomy_values"]).items():
            self.database.connection.execute(
                "INSERT INTO question_bank_version_taxonomy_values(version_id, taxonomy_id, taxonomy_value_id) "
                "VALUES(?, ?, ?)",
                (version_id, taxonomy_id, value_id),
            )
        for property_id, value in dict(payload["property_values"]).items():
            self.database.connection.execute(
                "INSERT INTO question_bank_version_property_values(version_id, property_id, value) VALUES(?, ?, ?)",
                (version_id, property_id, value),
            )
        if payload.get("subquestions"):
            for row in payload["subquestions"]:
                self.database.connection.execute(
                    "UPDATE question_bank_subquestions SET question_text=?, short_description=?, maximum_score=?, "
                    "expected_time_minutes=?, is_multiple_choice=?, multiple_choice_answer=?, sort_order=?, "
                    "updated_at=CURRENT_TIMESTAMP WHERE version_id=? AND subquestion=?",
                    (
                        row["question_text"],
                        row["short_description"],
                        row["maximum_score"],
                        row["expected_time_minutes"],
                        row["is_multiple_choice"],
                        row["multiple_choice_answer"],
                        row["sort_order"],
                        version_id,
                        row["subquestion"],
                    ),
                )
                subquestion_id = self.database.scalar(
                    "SELECT id FROM question_bank_subquestions WHERE version_id=? AND subquestion=?",
                    (version_id, row["subquestion"]),
                )
                if subquestion_id is None:
                    continue
                self.database.connection.execute(
                    "DELETE FROM question_bank_subquestion_taxonomy_values WHERE subquestion_id=?",
                    (subquestion_id,),
                )
                for taxonomy_id, value_id in dict(row.get("taxonomy_values") or {}).items():
                    self.database.connection.execute(
                        "INSERT INTO question_bank_subquestion_taxonomy_values(subquestion_id, taxonomy_id, taxonomy_value_id) "
                        "VALUES(?, ?, ?)",
                        (subquestion_id, taxonomy_id, value_id),
                    )
                self.database.connection.execute(
                    "DELETE FROM question_bank_subquestion_property_values WHERE subquestion_id=?",
                    (subquestion_id,),
                )
                for property_id, value in dict(row.get("property_values") or {}).items():
                    if value:
                        self.database.connection.execute(
                            "INSERT INTO question_bank_subquestion_property_values(subquestion_id, property_id, value) "
                            "VALUES(?, ?, ?)",
                            (subquestion_id, property_id, value),
                        )

    def save_new_version(self, item_id: int, payload: dict[str, object], version_number: int | None = None) -> int:
        if version_number is None:
            version_number = int(self.database.scalar(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM question_bank_versions WHERE item_id=?",
                (item_id,),
            ) or 1)
        cursor = self.database.connection.execute(
            "INSERT INTO question_bank_versions(item_id, version_number, title, question_text, short_description, "
            "maximum_score, expected_time_minutes, is_multiple_choice, multiple_choice_answer) "
            "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item_id,
                version_number,
                payload["title"],
                payload["question_text"],
                payload["short_description"],
                payload["maximum_score"],
                payload["expected_time_minutes"],
                payload["is_multiple_choice"],
                payload["multiple_choice_answer"],
            ),
        )
        version_id = int(cursor.lastrowid)
        self.database.connection.execute(
            "UPDATE question_bank_items SET title=?, short_description=?, status=?, maximum_score=?, expected_time_minutes=?, "
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                payload["title"],
                payload["short_description"],
                payload.get("status", "Actief"),
                payload["maximum_score"],
                payload["expected_time_minutes"],
                item_id,
            ),
        )
        for taxonomy_id, value_id in dict(payload["taxonomy_values"]).items():
            self.database.connection.execute(
                "INSERT INTO question_bank_version_taxonomy_values(version_id, taxonomy_id, taxonomy_value_id) "
                "VALUES(?, ?, ?)",
                (version_id, taxonomy_id, value_id),
            )
        for property_id, value in dict(payload["property_values"]).items():
            self.database.connection.execute(
                "INSERT INTO question_bank_version_property_values(version_id, property_id, value) VALUES(?, ?, ?)",
                (version_id, property_id, value),
            )
        for subquestion in payload.get("subquestions", []):
            cursor = self.database.connection.execute(
                "INSERT INTO question_bank_subquestions(version_id, subquestion, question_text, short_description, "
                "maximum_score, expected_time_minutes, is_multiple_choice, multiple_choice_answer, sort_order) "
                "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    version_id,
                    subquestion["subquestion"],
                    subquestion["question_text"],
                    subquestion["short_description"],
                    subquestion["maximum_score"],
                    subquestion["expected_time_minutes"],
                    subquestion["is_multiple_choice"],
                    subquestion["multiple_choice_answer"],
                    subquestion["sort_order"],
                ),
            )
            subquestion_id = int(cursor.lastrowid)
            subquestion_taxonomy_values = (
                dict(subquestion.get("taxonomy_values") or {})
                if "taxonomy_values" in subquestion else dict(payload["taxonomy_values"])
            )
            for taxonomy_id, value_id in subquestion_taxonomy_values.items():
                self.database.connection.execute(
                    "INSERT INTO question_bank_subquestion_taxonomy_values(subquestion_id, taxonomy_id, taxonomy_value_id) "
                    "VALUES(?, ?, ?)",
                    (subquestion_id, taxonomy_id, value_id),
                )
            subquestion_property_values = (
                dict(subquestion.get("property_values") or {})
                if "property_values" in subquestion else dict(payload["property_values"])
            )
            for property_id, value in subquestion_property_values.items():
                if value:
                    self.database.connection.execute(
                        "INSERT INTO question_bank_subquestion_property_values(subquestion_id, property_id, value) VALUES(?, ?, ?)",
                        (subquestion_id, property_id, value),
                    )
        return version_id

    def sync_linked_questions(self, item_id: int, version_id: int) -> None:
        version, subquestions, taxonomy_values, property_values = self.load_version(version_id)
        linked_tests = self.database.rows(
            "SELECT DISTINCT test_id, question_number FROM matrix_questions WHERE question_bank_id=?",
            (item_id,),
        )
        for linked in linked_tests:
            test_id = int(linked["test_id"])
            number = str(linked["question_number"])
            existing_rows = [
                dict(row) for row in self.database.rows(
                    "SELECT * FROM matrix_questions WHERE test_id=? AND question_number=? AND question_bank_id=? "
                    "ORDER BY COALESCE(subquestion, ''), id",
                    (test_id, number, item_id),
                )
            ]
            if not subquestions:
                target = existing_rows[0] if existing_rows else None
                if target:
                    self.update_linked_matrix_question(
                        int(target["id"]),
                        number,
                        None,
                        version,
                        item_id,
                        version_id,
                        None,
                        taxonomy_values,
                        property_values,
                    )
                else:
                    MatrixPage.insert_database_question_rows(
                        self.database, test_id, number, item_id, version_id, version, [], taxonomy_values, property_values
                    )
                continue
            existing_by_subquestion = {
                str(row["subquestion"]): row for row in existing_rows if row.get("subquestion")
            }
            for subquestion in subquestions:
                label = str(subquestion["subquestion"])
                target = existing_by_subquestion.get(label)
                if target:
                    self.update_linked_matrix_question(
                        int(target["id"]),
                        number,
                        label,
                        subquestion,
                        item_id,
                        version_id,
                        int(subquestion["id"]),
                        taxonomy_values,
                        property_values,
                    )
                else:
                    MatrixPage.insert_database_question_rows(
                        self.database, test_id, number, item_id, version_id, version, [subquestion], taxonomy_values, property_values
                    )

    def update_linked_matrix_question(
        self,
        question_id: int,
        question_number: str,
        subquestion: str | None,
        source: dict,
        item_id: int,
        version_id: int,
        subquestion_id: int | None,
        taxonomy_values: dict[int, int],
        property_values: dict[int, str],
    ) -> None:
        test_id = int(self.database.scalar("SELECT test_id FROM matrix_questions WHERE id=?", (question_id,)) or 0)
        source_taxonomy_values = (
            dict(source.get("taxonomy_values") or {})
            if "taxonomy_values" in source else dict(taxonomy_values)
        )
        source_property_values = (
            dict(source.get("property_values") or {})
            if "property_values" in source else dict(property_values)
        )
        taxonomy_values, property_values = MatrixPage.filter_database_question_classifications_for_test(
            self.database, test_id, source_taxonomy_values, source_property_values
        )
        self.database.connection.execute(
            "UPDATE matrix_questions SET question_number=?, subquestion=?, maximum_score=?, "
            "expected_time_minutes=?, is_multiple_choice=?, multiple_choice_answer=?, question_bank_id=?, "
            "question_bank_version_id=?, question_bank_subquestion_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                question_number,
                subquestion,
                source.get("maximum_score"),
                source.get("expected_time_minutes"),
                int(source.get("is_multiple_choice") or 0),
                source.get("multiple_choice_answer"),
                item_id,
                version_id,
                subquestion_id,
                question_id,
            ),
        )
        MatrixPage.save_database_question_classifications(
            self.database, question_id, taxonomy_values, property_values
        )
        if int(source.get("is_multiple_choice") or 0):
            regrade_multiple_choice_question(
                self.database,
                int(self.database.scalar("SELECT test_id FROM matrix_questions WHERE id=?", (question_id,))),
                question_id,
            )

