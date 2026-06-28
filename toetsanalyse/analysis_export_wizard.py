from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from .analysis_exports import DEFAULT_ANALYSIS_EXPORT_OPTIONS
from .ui_helpers import fit_to_available_screen


class AnalysisExportWizardDialog(QDialog):
    def __init__(self, parent=None, analysis_parts: list[dict[str, object]] | None = None, selected_part_id: int | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sectierapport toetsanalyse")
        fit_to_available_screen(self, 520, 420)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Kies welke onderdelen u wilt meenemen in de grafische PDF voor de vaksectie. "
            "Het rapport is bedoeld voor kwaliteitszorg, sectiebespreking en toetsverbetering."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.scope_select = QComboBox()
        self.scope_select.addItem("Totaaltoets", None)
        self.analysis_parts = list(analysis_parts or [])
        for part in self.analysis_parts:
            self.scope_select.addItem(f"Deeltoets: {part.get('name')}", int(part.get("id") or 0))
        if selected_part_id is None:
            self.scope_select.setCurrentIndex(0)
        else:
            index = self.scope_select.findData(int(selected_part_id))
            self.scope_select.setCurrentIndex(index if index >= 0 else 0)
        if self.analysis_parts:
            layout.addWidget(QLabel("Rapportscope"))
            layout.addWidget(self.scope_select)

        self.checkboxes: dict[str, QCheckBox] = {}
        labels = {
            "summary": "Samenvatting en kwaliteitsmaten",
            "item_analysis": "Itemanalyse: p-waarden, Rit, Rir en status per vraag",
            "multiple_choice": "Meerkeuzeanalyse: opties, aantallen, N-scores en conclusies",
            "group_analysis": "Analyse per taxonomie/classificatie/onderdeel",
            "participants": "Deelnemersoverzicht met score, cijfer en positie",
        }
        for key, label in labels.items():
            checkbox = QCheckBox(label)
            checkbox.setChecked(DEFAULT_ANALYSIS_EXPORT_OPTIONS.get(key, False))
            layout.addWidget(checkbox)
            self.checkboxes[key] = checkbox

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("PDF genereren")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_options(self) -> dict[str, bool]:
        return {key: checkbox.isChecked() for key, checkbox in self.checkboxes.items()}

    def selected_scope_part_id(self) -> int | None:
        value = self.scope_select.currentData() if hasattr(self, "scope_select") else None
        return None if value in {None, ""} else int(value)
