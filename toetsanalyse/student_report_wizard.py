from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .student_reports import report_dimensions
from .ui_helpers import fit_to_available_screen


class StudentReportWizardDialog(QDialog):
    def __init__(
        self,
        data: dict[str, object],
        for_all_students: bool,
        parent: QWidget | None = None,
        selected_student_id: int | str | None = None,
        report_context: str = "toets",
    ) -> None:
        super().__init__(parent)
        self.dimensions = report_dimensions(data)
        self.participants = list(data.get("participants", []))
        self.for_all_students = for_all_students
        self.setWindowTitle("Leerlingrapportage samenstellen")
        self.setMinimumWidth(560)
        self.setMinimumHeight(530)
        fit_to_available_screen(self, 760, 680)
        layout = QVBoxLayout(self)

        context_label = "ontwikkeling" if report_context == "ontwikkeling" else "toets"
        title = QLabel(
            f"Leerlingrapportage ({context_label}) - alle leerlingen"
            if for_all_students
            else f"Leerlingrapportage ({context_label})"
        )
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        explanation = QLabel(
            "Kies voor wie de rapportage is en welke onderdelen worden opgenomen. "
            "Algemene gegevens en het resultaat staan altijd bovenaan."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        fixed = QFrame()
        fixed_layout = QVBoxLayout(fixed)
        if not for_all_students:
            student_row = QHBoxLayout()
            student_row.addWidget(QLabel("Leerling"))
            self.student_selector = QComboBox()
            for participant in self.participants:
                self.student_selector.addItem(
                    str(participant.get("name", "Leerling")),
                    int(participant.get("student_id")),
                )
            if selected_student_id is not None:
                try:
                    index = self.student_selector.findData(int(selected_student_id))
                except (TypeError, ValueError):
                    index = -1
                if index >= 0:
                    self.student_selector.setCurrentIndex(index)
            student_row.addWidget(self.student_selector, 1)
            fixed_layout.addLayout(student_row)
        else:
            self.student_selector = None
        fixed_layout.addWidget(QLabel("<b>Algemene gegevens</b> - toets, leerling, score, cijfer en resultaat"))
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Rapportthema"))
        self.report_theme = QComboBox()
        self.report_theme.addItem("Leerlingvriendelijk rapport", "student")
        self.report_theme.addItem("Intern docentrapport", "teacher")
        self.report_theme.addItem("Sectierapport", "section")
        theme_row.addWidget(self.report_theme, 1)
        fixed_layout.addLayout(theme_row)
        layout.addWidget(fixed)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        options_layout = QVBoxLayout(content)
        options_layout.addWidget(QLabel("<b>Grafieken per onderdeel</b>"))
        self.profile_checks: dict[str, QCheckBox] = {}
        for dimension in self.dimensions:
            check = QCheckBox(str(dimension["title"]))
            check.setChecked(True)
            self.profile_checks[str(dimension["key"])] = check
            options_layout.addWidget(check)
        if not self.dimensions:
            options_layout.addWidget(QLabel("Er zijn geen onderdelen ingevuld voor deze toets."))

        options_layout.addSpacing(8)
        options_layout.addWidget(QLabel("<b>Aanvullende onderdelen</b>"))
        self.strengths = QCheckBox("Sterke punten en aandachtspunten")
        self.strengths.setChecked(True)
        self.questions = QCheckBox("Vraaganalyse per vraag")
        self.questions.setChecked(True)
        self.heatmap = QCheckBox("Geanonimiseerde positiekaart")
        self.heatmap.setChecked(True)
        options_layout.addWidget(self.strengths)
        options_layout.addWidget(self.questions)
        options_layout.addWidget(self.heatmap)

        heatmap_row = QHBoxLayout()
        heatmap_row.addSpacing(22)
        heatmap_row.addWidget(QLabel("Positiekaart op basis van:"))
        self.heatmap_dimension = QComboBox()
        self.heatmap_dimension.addItem("Algemene score", "overall")
        for dimension in self.dimensions:
            self.heatmap_dimension.addItem(str(dimension["title"]), str(dimension["key"]))
        if self.dimensions:
            self.heatmap_dimension.setCurrentIndex(1)
        heatmap_row.addWidget(self.heatmap_dimension, 1)
        options_layout.addLayout(heatmap_row)

        self.second_heatmap = QCheckBox("Tweede geanonimiseerde positiekaart toevoegen")
        self.second_heatmap.setChecked(False)
        options_layout.addWidget(self.second_heatmap)
        second_heatmap_row = QHBoxLayout()
        second_heatmap_row.addSpacing(22)
        second_heatmap_row.addWidget(QLabel("Tweede positiekaart op basis van:"))
        self.second_heatmap_dimension = QComboBox()
        self.second_heatmap_dimension.addItem("Algemene score", "overall")
        for dimension in self.dimensions:
            self.second_heatmap_dimension.addItem(str(dimension["title"]), str(dimension["key"]))
        self.second_heatmap_dimension.setEnabled(False)
        second_heatmap_row.addWidget(self.second_heatmap_dimension, 1)
        options_layout.addLayout(second_heatmap_row)
        def update_heatmap_controls() -> None:
            include_heatmap = self.heatmap.isChecked()
            self.heatmap_dimension.setEnabled(include_heatmap)
            self.second_heatmap.setEnabled(include_heatmap)
            if not include_heatmap:
                self.second_heatmap.setChecked(False)
            self.second_heatmap_dimension.setEnabled(
                include_heatmap and self.second_heatmap.isChecked()
            )

        self.heatmap.stateChanged.connect(lambda _state: update_heatmap_controls())
        self.second_heatmap.stateChanged.connect(lambda _state: update_heatmap_controls())
        update_heatmap_controls()

        if not for_all_students:
            options_layout.addSpacing(8)
            options_layout.addWidget(QLabel("<b>Persoonlijke feedback</b>"))
            self.feedback = QCheckBox("Ik wil feedback/opmerking voor de leerling toevoegen aan de kaart")
            self.feedback.setChecked(False)
            options_layout.addWidget(self.feedback)
            self.feedback_text = QTextEdit()
            self.feedback_text.setPlaceholderText(
                "Typ hier persoonlijke feedback, een compliment of een aandachtspunt voor de leerling..."
            )
            self.feedback_text.setMinimumHeight(95)
            self.feedback_text.setVisible(False)
            options_layout.addWidget(self.feedback_text)
            self.feedback.stateChanged.connect(
                lambda state: self.feedback_text.setVisible(state == Qt.CheckState.Checked.value)
            )
        else:
            self.feedback = None
            self.feedback_text = None
        options_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        note = QLabel(
            "Bij RTTI, OBIT en Bloom wordt automatisch een korte uitleg van de taxonomie "
            "in het rapport opgenomen."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "PDF's genereren" if for_all_students else "PDF genereren"
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_options(self) -> dict[str, object]:
        defaults = {
            "profile_keys": [
                key for key, check in self.profile_checks.items() if check.isChecked()
            ],
            "include_question_analysis": self.questions.isChecked(),
            "include_strengths": self.strengths.isChecked(),
            "include_heatmap": self.heatmap.isChecked(),
            "heatmap_key": self.heatmap_dimension.currentData() or "overall",
            "include_second_heatmap": self.second_heatmap.isChecked(),
            "second_heatmap_key": self.second_heatmap_dimension.currentData() or "overall",
            "include_feedback": bool(self.feedback and self.feedback.isChecked()),
            "feedback_text": (
                self.feedback_text.toPlainText().strip()
                if self.feedback and self.feedback.isChecked() and self.feedback_text
                else ""
            ),
            "report_theme": self.report_theme.currentData() or "student",
        }
        return defaults

    def selected_student_id(self) -> int | None:
        if self.student_selector is None:
            return None
        value = self.student_selector.currentData()
        return int(value) if value is not None else None

