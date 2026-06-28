from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from .database import SubjectDatabase


class Page(QWidget):
    changed = Signal()

    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__()
        self.database = database
        self.year_id = year_id

    def set_year(self, year_id: int | None) -> None:
        self.year_id = year_id
        self.refresh()

    def refresh(self) -> None:
        pass

    def on_activated(self) -> None:
        pass

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Schermuitleg",
            "intro": "Op dit scherm beheert u een onderdeel van uw vakbestand.",
            "steps": [
                {
                    "title": "Wat kunt u hier doen?",
                    "text": "Gebruik de knoppen bovenaan om gegevens toe te voegen of te wijzigen.",
                    "action": "Kies eerst het schooljaar en volg daarna de invoervelden van boven naar beneden.",
                    "tip": "Gegevens blijven in het geopende vakbestand opgeslagen.",
                },
            ],
        }

    def show_help_wizard(self) -> None:
        from .help_wizard import HelpWizardDialog, _build_help_faq, _enrich_help_steps

        content = self.help_content()
        title = str(content.get("title", "Schermuitleg"))
        steps = _enrich_help_steps(title, list(content.get("steps", [])))
        dialog = HelpWizardDialog(
            title=title,
            intro=str(content.get("intro", "")),
            steps=steps,
            faq=_build_help_faq(title, steps, list(content.get("faq", []))),
            screen_preview=self.grab(),
            parent=self,
        )
        dialog.exec()
