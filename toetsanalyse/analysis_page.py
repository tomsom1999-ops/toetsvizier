from __future__ import annotations

import html
import json
import os
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Slot
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None
try:
    from PySide6.QtWebChannel import QWebChannel
except ImportError:
    QWebChannel = None

from .analysis import analysis_data
from .analysis_dashboard import build_analysis_dashboard_html
from .analysis_export_wizard import AnalysisExportWizardDialog
from .analysis_exports import build_section_analysis_report_html
from .database import SubjectDatabase
from .pages_base import Page
from .paths import PDF_EXPORT_DIR
from .pdf_export import PdfExportError, export_html_to_pdf
from .matrix_page import analysis_parts_enabled
from .student_reports import build_student_report_html
from .student_report_wizard import StudentReportWizardDialog
from .ui_helpers import DashboardZoomBar, compact_action_button, make_page_header, make_responsive_filter_card, set_button_role, slug


def _can_use_webengine() -> bool:
    return (
        QWebEngineView is not None
        and QWebChannel is not None
        and os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"
    )


class AnalysisBridge(QObject):
    def __init__(self, page: "AnalysisPage") -> None:
        super().__init__(page)
        self.page = page

    @Slot(str, str, result=str)
    def exportStudentReports(self, scope: str, selected_student_id: str) -> str:
        test_id = self.page.test.currentData()
        if test_id is None:
            return json.dumps({"ok": False, "message": "Selecteer eerst een toets."})
        try:
            data = analysis_data(self.page.database, test_id)
        except Exception as error:
            return json.dumps({"ok": False, "message": f"Het rapport kon niet worden voorbereid: {error}"})
        participants = list(data.get("participants", []))
        if not participants:
            return json.dumps({"ok": False, "message": "Er zijn geen complete leerlingresultaten om te exporteren."})
        for_all = scope == "all"
        dialog = StudentReportWizardDialog(
            data,
            for_all,
            self.page,
            selected_student_id=selected_student_id or None,
            report_context="toets",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return json.dumps({"ok": False, "cancelled": True})
        options = dialog.selected_options()
        if for_all:
            selected_participants = participants
        else:
            wizard_student_id = dialog.selected_student_id()
            if wizard_student_id is None:
                return json.dumps({"ok": False, "message": "Selecteer eerst een leerling."})
            selected_participants = [
                participant
                for participant in participants
                if str(participant.get("student_id")) == str(wizard_student_id)
            ]
            if not selected_participants:
                return json.dumps({"ok": False, "message": "De gekozen leerling is niet gevonden."})
        test_name = str(data.get("test", {}).get("name", "toets"))
        PDF_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        targets: list[tuple[dict[str, object], Path]] = []
        if for_all:
            directory = QFileDialog.getExistingDirectory(
                self.page,
                "Map kiezen voor leerlingrapporten",
                str(PDF_EXPORT_DIR),
            )
            if not directory:
                return json.dumps({"ok": False, "cancelled": True})
            used_names: set[str] = set()
            for participant in selected_participants:
                filename = f"{slug(str(participant['name']))}_{slug(test_name)}_leerlingrapport.pdf"
                if filename in used_names:
                    filename = (
                        f"{slug(str(participant['name']))}_{participant['student_id']}_"
                        f"{slug(test_name)}_leerlingrapport.pdf"
                    )
                used_names.add(filename)
                targets.append((participant, Path(directory) / filename))
        else:
            participant = selected_participants[0]
            suggested = PDF_EXPORT_DIR / (
                f"{slug(str(participant['name']))}_{slug(test_name)}_leerlingrapport.pdf"
            )
            file_name, _ = QFileDialog.getSaveFileName(
                self.page,
                "Leerlingrapport opslaan als PDF",
                str(suggested),
                "PDF-bestanden (*.pdf)",
            )
            if not file_name:
                return json.dumps({"ok": False, "cancelled": True})
            if not file_name.lower().endswith(".pdf"):
                file_name += ".pdf"
            targets.append((participant, Path(file_name)))
        progress = None
        if for_all and len(targets) > 1:
            progress = QProgressDialog(
                f"Bezig met genereren: 0 / {len(targets)}",
                "Annuleren",
                0,
                len(targets),
                self.page,
            )
            progress.setWindowTitle("Leerlingrapporten genereren")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setAutoClose(True)
            progress.setValue(0)
            progress.show()
            QApplication.processEvents()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        exported = 0
        batch_cancelled = False
        try:
            for index, (participant, path) in enumerate(targets, start=1):
                if progress and progress.wasCanceled():
                    batch_cancelled = True
                    break
                if progress:
                    progress.setLabelText(
                        f"Bezig met genereren: {index} / {len(targets)}\n"
                        f"{participant['name']}"
                    )
                    QApplication.processEvents()
                report_html = build_student_report_html(data, participant, options)
                export_html_to_pdf(report_html, path)
                exported += 1
                try:
                    self.page.database.execute(
                        "INSERT INTO report_exports(report_type, test_id, file_path) VALUES(?, ?, ?)",
                        ("leerlingrapport_pdf", test_id, str(path)),
                    )
                except Exception:
                    pass
                if progress:
                    progress.setValue(index)
                    QApplication.processEvents()
        except PdfExportError as error:
            return json.dumps({"ok": False, "message": f"PDF niet opgeslagen: {error}"})
        finally:
            QApplication.restoreOverrideCursor()
            if progress:
                progress.close()
        if batch_cancelled and exported < len(targets):
            return json.dumps(
                {
                    "ok": True,
                    "message": f"Export gestopt. {exported} van {len(targets)} leerlingrapporten zijn opgeslagen.",
                }
            )
        if for_all:
            return json.dumps({"ok": True, "message": f"{exported} leerlingrapporten als PDF opgeslagen."})
        return json.dumps({"ok": True, "message": "Leerlingrapport als PDF opgeslagen."})



class AnalysisPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        self.dashboard_zoom = 1.0
        self.level_filter = QComboBox()
        self.level_filter.currentIndexChanged.connect(self.refresh)
        self.grade_filter = QComboBox()
        self.grade_filter.currentIndexChanged.connect(self.refresh)
        self.test = QComboBox()
        self.test.setMinimumWidth(300)
        self.test.currentIndexChanged.connect(self.test_changed)
        self.analysis_scope = QComboBox()
        self.analysis_scope.setMinimumWidth(260)
        self.analysis_scope.currentIndexChanged.connect(self.load_dashboard)
        self.export_button = compact_action_button(
            set_button_role(QPushButton("Algemene analyse exporteren"), "secondary"),
            "Maak een grafisch sectierapport als PDF met p-waarden, Rit/Rir, meerkeuzeanalyse en groepsanalyses.",
            190,
        )
        self.export_button.clicked.connect(self.export_analysis)
        layout.addWidget(
            make_page_header(
                "Toetsanalyse",
                "Analyseer één afgenomen toets op algemeen, groeps- en leerlingniveau.",
                actions=[self.export_button],
            )
        )
        layout.addWidget(
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
        self.analysis_scope_panel = QFrame()
        self.analysis_scope_panel.setObjectName("panel")
        scope_layout = QHBoxLayout(self.analysis_scope_panel)
        scope_layout.setContentsMargins(14, 10, 14, 10)
        scope_layout.setSpacing(10)
        scope_layout.addWidget(QLabel("Analyse"))
        scope_layout.addWidget(self.analysis_scope)
        scope_layout.addStretch()
        self.analysis_scope_panel.setVisible(False)
        layout.addWidget(self.analysis_scope_panel)
        if _can_use_webengine():
            self.dashboard = QWebEngineView()
            self.channel = QWebChannel(self.dashboard.page())
            self.bridge = AnalysisBridge(self)
            self.channel.registerObject("analysisBridge", self.bridge)
            self.dashboard.page().setWebChannel(self.channel)
            self.zoom_bar = DashboardZoomBar()
            self.zoom_bar.zoom_out_requested.connect(lambda: self.change_dashboard_zoom(-0.1))
            self.zoom_bar.zoom_reset_requested.connect(lambda: self.set_dashboard_zoom(1.0))
            self.zoom_bar.zoom_in_requested.connect(lambda: self.change_dashboard_zoom(0.1))
            zoom_row = QVBoxLayout()
            zoom_row.setContentsMargins(0, 0, 0, 0)
            zoom_row.addWidget(self.zoom_bar, alignment=Qt.AlignmentFlag.AlignRight)
            layout.addLayout(zoom_row)
            layout.addWidget(self.dashboard, 1)
        else:
            self.dashboard = QTextBrowser()
            layout.addWidget(self.dashboard, 1)
        self.refresh()

    def export_analysis(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            QMessageBox.information(self, "Geen toets", "Kies eerst een toets om analysegegevens te exporteren.")
            return
        current_part_id = self.selected_analysis_part_id()
        try:
            preview_data = analysis_data(self.database, int(test_id), analysis_part_id=current_part_id)
        except Exception as error:
            QMessageBox.warning(self, "Export niet mogelijk", f"De analyse kon niet worden voorbereid: {error}")
            return
        dialog = AnalysisExportWizardDialog(
            self,
            analysis_parts=list(preview_data.get("analysis_parts", [])),
            selected_part_id=current_part_id,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        options = dialog.selected_options()
        if not any(options.values()):
            QMessageBox.information(self, "Niets gekozen", "Vink minimaal één onderdeel aan om te exporteren.")
            return
        try:
            selected_part_id = dialog.selected_scope_part_id()
            data = analysis_data(self.database, int(test_id), analysis_part_id=selected_part_id)
        except Exception as error:
            QMessageBox.warning(self, "Export niet mogelijk", f"De analyse kon niet worden voorbereid: {error}")
            return
        PDF_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        test_name = str(data.get("test", {}).get("name", self.test.currentText()))
        suggested = PDF_EXPORT_DIR / f"{slug(test_name)}_sectierapport_toetsanalyse.pdf"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Sectierapport opslaan als PDF",
            str(suggested),
            "PDF-bestanden (*.pdf)",
        )
        if not file_name:
            return
        if not file_name.lower().endswith(".pdf"):
            file_name += ".pdf"
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            report_html = build_section_analysis_report_html(data, options)
            output = Path(file_name)
            export_html_to_pdf(report_html, output)
            try:
                self.database.execute(
                    "INSERT INTO report_exports(report_type, test_id, file_path) VALUES(?, ?, ?)",
                    ("toetsanalyse_sectierapport_pdf", test_id, str(output)),
                )
            except Exception:
                pass
        except PdfExportError as error:
            QMessageBox.warning(self, "PDF niet opgeslagen", str(error))
            return
        except Exception as error:
            QMessageBox.warning(self, "Export mislukt", str(error))
            return
        finally:
            QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Export voltooid", f"Sectierapport opgeslagen:\n{output}")

    def set_dashboard_zoom(self, factor: float) -> None:
        self.dashboard_zoom = max(0.7, min(1.6, round(factor / 0.05) * 0.05))
        if QWebEngineView is not None and isinstance(self.dashboard, QWebEngineView):
            self.dashboard.setZoomFactor(self.dashboard_zoom)
        if hasattr(self, "zoom_bar"):
            self.zoom_bar.set_zoom_factor(self.dashboard_zoom)

    def change_dashboard_zoom(self, delta: float) -> None:
        self.set_dashboard_zoom(self.dashboard_zoom + delta)

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Toetsanalyse",
            "intro": "De toetsanalyse helpt u begrijpen hoe één afgenomen toets is gemaakt, welke vragen werken en waar leerlingen moeite mee hebben.",
            "steps": [
                {
                    "title": "De juiste toets openen",
                    "text": "De analyse gaat altijd over één toets. Kies bovenaan de toets en gebruik eventueel niveau en jaarlaag om de lijst te beperken.",
                    "action": "Selecteer de toets waarvan resultaten volledig zijn ingevoerd en, voor cijferinformatie, de normering is vastgesteld.",
                    "tip": "Deze pagina vergelijkt geen toetsen over meerdere jaren; dat hoort bij een latere aparte module.",
                },
                {
                    "title": "Algemeen: kwaliteit van de toets",
                    "text": "In 'Algemeen' ziet u scores en kwaliteitsmaten. P-waarde zegt hoe goed een vraag gemaakt is; Rit en Rir tonen hoe goed een vraag onderscheid maakt; Cronbach's alpha gaat over samenhang van de toets; SEM gaat over meetonnauwkeurigheid.",
                    "action": "Beweeg over informatie-icoontjes en bekijk de kleur/status bij elke vraag.",
                    "tip": "Een aandachtspunt is een signaal om naar een vraag te kijken, geen automatische conclusie dat de vraag fout is.",
                },
                {
                    "title": "Groepsniveau: patronen in de klas",
                    "text": "In 'Groepsniveau' ziet u prestaties per ingevuld onderdeel, zoals taxonomie, hoofdstuk of vraagtype, plus de verdeling van cijfers en de heatmap met namen.",
                    "action": "Zoek onderdelen waarop de groep sterk of zwak scoort en bekijk de positiekaart voor verschillen tussen leerlingen.",
                    "tip": "Een onderdeel verschijnt alleen als het bij vragen is ingevuld.",
                },
                {
                    "title": "Leerlingniveau: bespreken met een leerling",
                    "text": "In 'Leerlingniveau' kiest u één leerling en ziet u het resultaat, onderdelen ten opzichte van de groep, vragenoverzicht en een geanonimiseerde positiekaart.",
                    "action": "Kies een leerling en gebruik de analyse als basis voor feedback of bespreking.",
                    "tip": "In de geanonimiseerde heatmap zijn andere leerlingen genummerd; de geselecteerde leerling blijft herkenbaar.",
                },
                {
                    "title": "Een leerlingrapport exporteren",
                    "text": "U kunt een PDF maken voor één leerling of voor alle leerlingen. In de wizard bepaalt u welke onderdelen worden opgenomen en kunt u bij een individueel rapport een persoonlijke opmerking toevoegen.",
                    "action": "Gebruik de rapportknoppen in het leerlingtabblad, kies de gewenste kaarten en start de generatie.",
                    "tip": "Bij een grote batch toont het programma de voortgang. Controleer één voorbeeldrapport voordat u alles deelt.",
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
            index = self.level_filter.findData(selected_level)
            if index >= 0:
                self.level_filter.setCurrentIndex(index)
        if selected_grade is not None:
            index = self.grade_filter.findData(selected_grade)
            if index >= 0:
                self.grade_filter.setCurrentIndex(index)
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
            index = self.test.findData(selected_id)
            self.test.setCurrentIndex(index if index >= 0 else 0)
        else:
            self.test.setCurrentIndex(0)
        self.test.blockSignals(False)
        self.refresh_analysis_scope()
        self.load_dashboard()

    def test_changed(self) -> None:
        self.refresh_analysis_scope()
        self.load_dashboard()

    def selected_analysis_part_id(self) -> int | None:
        if not analysis_parts_enabled(self.database):
            return None
        value = self.analysis_scope.currentData()
        return int(value) if value is not None else None

    def refresh_analysis_scope(self) -> None:
        selected = self.analysis_scope.currentData()
        test_id = self.test.currentData()
        enabled = analysis_parts_enabled(self.database)
        self.analysis_scope.blockSignals(True)
        self.analysis_scope.clear()
        self.analysis_scope.addItem("Totaaltoets", None)
        parts = []
        if enabled and test_id is not None:
            parts = [
                dict(row)
                for row in self.database.rows(
                    "SELECT id, name FROM test_analysis_parts WHERE test_id=? ORDER BY sort_order",
                    (test_id,),
                )
            ]
            for part in parts:
                self.analysis_scope.addItem(f"Deeltoets: {part['name']}", int(part["id"]))
        index = self.analysis_scope.findData(selected)
        self.analysis_scope.setCurrentIndex(index if index >= 0 else 0)
        self.analysis_scope.blockSignals(False)
        self.analysis_scope_panel.setVisible(enabled and bool(parts))

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
                "De geselecteerde toets kon niet in toetsanalyse worden geopend. Controleer het schooljaar.",
            )

    def load_dashboard(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            self.dashboard.setHtml(
                "<style>body{font:14px 'Segoe UI';background:#f7f8fc;color:#66748e;padding:40px}</style>"
                "<h2>Kies een toets voor toetsanalyse</h2>"
                "<p>De analyse toont uitsluitend resultaten, items en leerlingprofielen van een geselecteerde toets.</p>"
            )
            return
        try:
            data = analysis_data(self.database, test_id, analysis_part_id=self.selected_analysis_part_id())
            if QWebEngineView is not None and isinstance(self.dashboard, QWebEngineView):
                asset_directory = Path(__file__).parent / "assets"
                self.dashboard.setHtml(
                    build_analysis_dashboard_html(data, "plotly-2.35.2.min.js"),
                    QUrl.fromLocalFile(str(asset_directory.resolve()) + "/"),
                )
                self.set_dashboard_zoom(self.dashboard_zoom)
            else:
                self.dashboard.setHtml(
                    f"<h2>Toetsanalyse - {html.escape(data['test']['name'])}</h2>"
                    "<p>Voor de interactieve analyses is PySide6 WebEngine nodig.</p>"
                )
        except Exception as error:
            self.dashboard.setHtml(f"<p>De toetsanalyse kon niet worden geladen: {html.escape(str(error))}</p>")

