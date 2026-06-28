from __future__ import annotations

import json
import html
import os
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:
    QWebEngineView = None
try:
    from PySide6.QtWebChannel import QWebChannel
except ImportError:
    QWebChannel = None

from .database import SubjectDatabase
from .development_analysis import development_data, development_filter_options, development_test_options
from .development_dashboard import build_development_dashboard_html
from .development_reports import build_development_group_report_html, build_development_student_report_html
from .pages_base import Page
from .paths import PDF_EXPORT_DIR
from .pdf_export import PdfExportError, export_html_to_pdf
from .ui_helpers import (
    DashboardZoomBar,
    compact_action_button,
    fit_to_available_screen,
    make_page_header,
    make_responsive_filter_card,
    set_button_role,
    slug,
)


def _can_use_webengine() -> bool:
    return (
        QWebEngineView is not None
        and QWebChannel is not None
        and os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"
    )


class DevelopmentBridge(QObject):
    def __init__(self, page: "DevelopmentAnalysisPage") -> None:
        super().__init__(page)
        self.page = page

    @Slot(str, str, result=str)
    def exportDevelopmentReport(self, report_type: str, selected_student_id: str) -> str:
        try:
            data = self.page.current_development_data()
        except Exception as error:
            return json.dumps({"ok": False, "message": f"De ontwikkelrapportage kon niet worden voorbereid: {error}"})
        if not data.get("students"):
            return json.dumps({"ok": False, "message": "Er zijn geen complete resultaten om te exporteren."})

        report_type = report_type.lower()
        try:
            if report_type == "student":
                options_dialog = DevelopmentExportOptionsDialog(
                    "student",
                    self.page,
                    data=data,
                    selected_student_id=selected_student_id or None,
                )
                if options_dialog.exec() != QDialog.DialogCode.Accepted:
                    return json.dumps({"ok": False, "cancelled": True})
                wizard_student_id = options_dialog.selected_student_id()
                if wizard_student_id is None:
                    return json.dumps({"ok": False, "message": "Selecteer eerst een leerling."})
                student = next(
                    (item for item in data.get("students", []) if str(item.get("id")) == str(wizard_student_id)),
                    None,
                )
                if student is None:
                    return json.dumps({"ok": False, "message": "De geselecteerde leerling is niet gevonden."})
                html_content = build_development_student_report_html(data, int(wizard_student_id), options_dialog.options())
                suggested_name = f"{slug(str(student.get('name', 'leerling')))}_ontwikkelrapport.pdf"
                title = "Leerlingontwikkelrapport opslaan als PDF"
                report_label = "Leerlingontwikkelrapport"
            elif report_type == "group":
                options_dialog = DevelopmentExportOptionsDialog("group", self.page, data=data)
                if options_dialog.exec() != QDialog.DialogCode.Accepted:
                    return json.dumps({"ok": False, "cancelled": True})
                html_content = build_development_group_report_html(data, options_dialog.options())
                suggested_name = "groepsontwikkelrapport.pdf"
                title = "Groepsontwikkelrapport opslaan als PDF"
                report_label = "Groepsontwikkelrapport"
            else:
                return json.dumps({"ok": False, "message": "Deze ontwikkelrapportage wordt niet ondersteund."})
        except Exception as error:
            return json.dumps({"ok": False, "message": f"De rapportage kon niet worden opgebouwd: {error}"})

        PDF_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        file_name, _ = QFileDialog.getSaveFileName(
            self.page,
            title,
            str(PDF_EXPORT_DIR / suggested_name),
            "PDF-bestanden (*.pdf)",
        )
        if not file_name:
            return json.dumps({"ok": False, "cancelled": True})
        if not file_name.lower().endswith(".pdf"):
            file_name += ".pdf"
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            export_html_to_pdf(html_content, file_name)
            try:
                self.page.database.execute(
                    "INSERT INTO report_exports(report_type, file_path) VALUES(?, ?)",
                    (f"ontwikkelanalyse_{report_type}_pdf", file_name),
                )
            except Exception:
                pass
        except PdfExportError as error:
            return json.dumps({"ok": False, "message": f"PDF niet opgeslagen: {error}"})
        finally:
            QApplication.restoreOverrideCursor()
        return json.dumps({"ok": True, "message": f"{report_label} opgeslagen als PDF."})



class DevelopmentTestSelectionDialog(QDialog):
    def __init__(
        self,
        tests: list[dict[str, object]],
        selected_test_ids: set[int] | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Toetsen kiezen voor ontwikkelanalyse")
        self.setMinimumWidth(680)
        self.setMinimumHeight(520)
        layout = QVBoxLayout(self)
        title = QLabel("Toetsen kiezen")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        explanation = QLabel(
            "Deze lijst is gebaseerd op de filters in het scherm Ontwikkelanalyse. "
            "Vink aan welke toetsen meegenomen worden in dashboard en export."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        self.list = QListWidget()
        active_selection = {int(value) for value in selected_test_ids} if selected_test_ids is not None else None
        for test in tests:
            suffix = []
            if test.get("level"):
                suffix.append(str(test["level"]))
            if test.get("grade_year"):
                suffix.append(str(test["grade_year"]))
            if test.get("is_resit"):
                suffix.append("herkansing")
            label = (
                f"{test['school_year']} · {test['period']} · {test['name']}"
                + (f" ({', '.join(suffix)})" if suffix else "")
            )
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, int(test["id"]))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = active_selection is None or int(test["id"]) in active_selection
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list, 1)
        quick = QHBoxLayout()
        select_all = QPushButton("Alles selecteren")
        select_all.clicked.connect(lambda: self.set_all_checked(True))
        select_none = QPushButton("Niets selecteren")
        select_none.clicked.connect(lambda: self.set_all_checked(False))
        quick.addWidget(select_all)
        quick.addWidget(select_none)
        quick.addStretch()
        layout.addLayout(quick)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Toepassen")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def set_all_checked(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(self.list.count()):
            self.list.item(index).setCheckState(state)

    def selected_ids(self) -> set[int]:
        return {
            int(self.list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.list.count())
            if self.list.item(index).checkState() == Qt.CheckState.Checked
        }



class DevelopmentExportOptionsDialog(QDialog):
    def __init__(
        self,
        report_type: str,
        parent: QWidget | None = None,
        data: dict[str, object] | None = None,
        selected_student_id: int | str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ontwikkelrapport samenstellen")
        self.checks: dict[str, QCheckBox] = {}
        self.student_selector: QComboBox | None = None
        self.students = list((data or {}).get("students", []))
        layout = QVBoxLayout(self)
        title = QLabel(
            "Leerlingrapportage (ontwikkeling)"
            if report_type == "student"
            else "Groepsrapportage (ontwikkeling)"
        )
        title.setObjectName("dialogTitle")
        layout.addWidget(title)
        explanation = QLabel(
            "De rapportage gebruikt dezelfde filters en toetsselectie als het dashboard. "
            "Vink hieronder aan welke onderdelen meegaan in de PDF."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        if report_type == "student":
            student_row = QHBoxLayout()
            student_row.addWidget(QLabel("Leerling"))
            self.student_selector = QComboBox()
            for student in self.students:
                self.student_selector.addItem(str(student.get("name", "Leerling")), int(student.get("id")))
            if selected_student_id is not None:
                try:
                    index = self.student_selector.findData(int(selected_student_id))
                except (TypeError, ValueError):
                    index = -1
                if index >= 0:
                    self.student_selector.setCurrentIndex(index)
            student_row.addWidget(self.student_selector, 1)
            layout.addLayout(student_row)
            options = [
                ("summary", "Algemene gegevens en kerncijfers", True),
                ("signals", "Signalen voor deze leerling", True),
                ("tests", "Trendontwikkeling per toets", True),
                ("classifications", "Profielgrafieken per taxonomie/classificatie", True),
                ("resits", "Herkansingen van deze leerling", True),
            ]
        else:
            options = [
                ("summary", "Automatische ontwikkelsamenvatting en kerncijfers", True),
                ("tests", "Ontwikkeling per toets", True),
                ("classifications", "Analyse per onderdeel", True),
                ("signals", "Signalen en aandachtspunten", True),
                ("resits", "Herkansingen en ontwikkeling", True),
            ]
        for key, label, checked in options:
            check = QCheckBox(label)
            check.setChecked(checked)
            self.checks[key] = check
            layout.addWidget(check)
        note = QLabel(
            "Tip: voor een kort leerlingrapport kunt u alleen kerncijfers, toetsontwikkeling en onderdelen aan laten staan."
            if report_type == "student"
            else "Tip: voor sectieoverleg zijn vooral samenvatting, signalen, onderdelen en herkansingen nuttig."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#5d6b82; padding-top:8px;")
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("PDF maken")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        fit_to_available_screen(self, 520, 430)

    def options(self) -> dict[str, object]:
        return {key: check.isChecked() for key, check in self.checks.items()}

    def selected_student_id(self) -> int | None:
        if self.student_selector is None:
            return None
        value = self.student_selector.currentData()
        return int(value) if value is not None else None



class DevelopmentAnalysisPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        self.loading = False
        self.selected_test_ids: set[int] | None = None
        self.force_project_year = True
        self.dashboard_zoom = 1.0
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        self.school_year_filter = QComboBox()
        self.school_year_filter.setMinimumWidth(140)
        self.school_year_filter.setMaximumWidth(190)
        self.school_year_filter.currentIndexChanged.connect(self.filters_changed)
        self.level_filter = QComboBox()
        self.level_filter.setMinimumWidth(150)
        self.level_filter.setMaximumWidth(210)
        self.level_filter.currentIndexChanged.connect(self.filters_changed)
        self.grade_filter = QComboBox()
        self.grade_filter.setMinimumWidth(150)
        self.grade_filter.setMaximumWidth(210)
        self.grade_filter.currentIndexChanged.connect(self.filters_changed)
        self.group_filter = QComboBox()
        self.group_filter.setMinimumWidth(170)
        self.group_filter.setMaximumWidth(230)
        self.group_filter.currentIndexChanged.connect(self.filters_changed)
        self.test_selection_label = QLabel("Alle toetsen")
        self.test_selection_label.setStyleSheet("color:#5d6b82; font-weight:600; padding-left:6px;")
        self.test_selection_label.setMinimumWidth(110)
        self.test_selection_label.setWordWrap(True)
        self.choose_tests_button = set_button_role(QPushButton("Toetsen kiezen"), "secondary")
        compact_action_button(self.choose_tests_button, width=150)
        self.choose_tests_button.clicked.connect(self.choose_tests)
        layout.addWidget(
            make_page_header(
                "Ontwikkelanalyse",
                "Analyseer ontwikkeling van groepen en leerlingen over meerdere toetsen.",
                [self.choose_tests_button],
            )
        )

        selection_widget = QWidget()
        selection_layout = QHBoxLayout(selection_widget)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.setSpacing(8)
        selection_layout.addWidget(self.test_selection_label)
        selection_layout.addStretch()
        layout.addWidget(
            make_responsive_filter_card(
                "Filter en toetskeuze",
                [
                    ("Schooljaar", self.school_year_filter),
                    ("Niveau", self.level_filter),
                    ("Jaarlaag", self.grade_filter),
                    ("Groep", self.group_filter),
                    ("Toetsen", selection_widget),
                ],
                minimum_field_width=185,
                maximum_columns=5,
            )
        )
        if _can_use_webengine():
            self.dashboard = QWebEngineView()
            self.channel = QWebChannel(self.dashboard.page())
            self.bridge = DevelopmentBridge(self)
            self.channel.registerObject("developmentBridge", self.bridge)
            self.dashboard.page().setWebChannel(self.channel)
            self.zoom_bar = DashboardZoomBar()
            self.zoom_bar.zoom_out_requested.connect(lambda: self.change_dashboard_zoom(-0.1))
            self.zoom_bar.zoom_reset_requested.connect(lambda: self.set_dashboard_zoom(1.0))
            self.zoom_bar.zoom_in_requested.connect(lambda: self.change_dashboard_zoom(0.1))
            zoom_row = QHBoxLayout()
            zoom_row.setContentsMargins(0, 0, 0, 0)
            zoom_row.addStretch()
            zoom_row.addWidget(self.zoom_bar)
            layout.addLayout(zoom_row)
            layout.addWidget(self.dashboard, 1)
        else:
            self.dashboard = QTextBrowser()
            self.dashboard.setHtml(
                "<h2>Ontwikkelanalyse</h2>"
                "<p>Voor de interactieve ontwikkelanalyse is PySide6 WebEngine nodig.</p>"
            )
            layout.addWidget(self.dashboard, 1)
        self.refresh()

    def set_dashboard_zoom(self, factor: float) -> None:
        self.dashboard_zoom = max(0.7, min(1.6, round(factor / 0.05) * 0.05))
        if QWebEngineView is not None and isinstance(self.dashboard, QWebEngineView):
            self.dashboard.setZoomFactor(self.dashboard_zoom)
        if hasattr(self, "zoom_bar"):
            self.zoom_bar.set_zoom_factor(self.dashboard_zoom)

    def change_dashboard_zoom(self, delta: float) -> None:
        self.set_dashboard_zoom(self.dashboard_zoom + delta)

    def set_year(self, year_id: int | None) -> None:
        self.year_id = year_id
        self.selected_test_ids = None
        self.force_project_year = True
        self.refresh()

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Ontwikkelanalyse",
            "intro": "Deze module analyseert leerlingen en groepen over meerdere toetsen. De grafieken gebruiken het eindresultaat: bij herkansingen telt de beste gekoppelde afname mee.",
            "steps": [
                {
                    "title": "Eerst filters kiezen",
                    "text": "De module start standaard met het schooljaar dat bovenin het vakbestand actief is. Een ontwikkelanalyse wordt pas gemaakt nadat niveau en jaarlaag gekozen zijn.",
                    "action": "Kies eerst niveau en jaarlaag. De groep mag op 'Alle groepen' blijven staan of later specifieker gekozen worden.",
                    "tip": "Cijfers worden alleen gebruikt als normering is vastgesteld; scorepercentages zijn altijd beschikbaar.",
                },
                {
                    "title": "Toetsen kiezen",
                    "text": "Standaard tellen alle toetsen binnen de gekozen filters mee. Wilt u een selectie maken, dan vinkt u in het toetsvenster aan welke toetsen meegenomen worden.",
                    "action": "Klik op 'Toetsen kiezen', controleer de lijst en klik op 'Toepassen'.",
                    "tip": "Wijzigt u de filters, dan wordt de toetsselectie opnieuw gebaseerd op die nieuwe filterset.",
                },
                {
                    "title": "Ontwikkelsamenvatting en signalen",
                    "text": "Bovenaan ziet u automatisch wat opvalt: positieve groei, terugval, recente veranderingen, verschillen tussen leerlingen en onderdelen die aandacht vragen.",
                    "action": "Gebruik deze kaarten als snelle ingang: klik daarna door naar Groep of Leerling om de onderliggende grafieken te bekijken.",
                    "tip": "Signalen tonen dus niet alleen problemen, maar ook duidelijke vooruitgang.",
                },
                {
                    "title": "Verschillen per onderdeel lezen",
                    "text": "In de leerlingtab kiest u eerst waarop u wilt kijken, bijvoorbeeld RTTI, domein, hoofdstuk of vraagtype. Elk bolletje is een leerling op dat onderdeel.",
                    "action": "Hover over een bolletje of zoek bovenaan een leerling. De stippellijn verbindt dan de scores van die leerling over alle onderdelen.",
                    "tip": "Groen betekent minimaal 55% van de punten op dat onderdeel; rood betekent daaronder.",
                },
                {
                    "title": "Leerlingontwikkeling",
                    "text": "Bij een geselecteerde leerling ziet u de scoreontwikkeling naast het groepsgemiddelde, de positie in de groep door de tijd en de ontwikkeling per gekozen onderdeel.",
                    "action": "Gebruik dit om te zien of een leerling vooruitgaat, achteruitgaat of juist heel wisselend scoort.",
                    "tip": "'Positie in de groep' betekent: beter dan hoeveel procent van de leerlingen in deze selectie.",
                },
                {
                    "title": "Leerlingkaarten lezen",
                    "text": "In de leerlingtab staan kaarten met Positief, Opvallend en Verbeterpunten. Deze vertalen de grafieken naar gewone taal.",
                    "action": "Gebruik de positieve kaarten voor feedback, opvallende kaarten voor context en verbeterpunten voor vervolgstappen.",
                    "tip": "Een kaart is een signaal, geen automatisch oordeel. Kijk altijd naar de toetsselectie en gemiste afnames.",
                },
                {
                    "title": "Groepsanalyse",
                    "text": "De groepstab toont gemiddelde prestaties, ontwikkeling per leerling, ontwikkeling per onderdeel en een overzicht van herkansingen.",
                    "action": "Gebruik 'Leerlingontwikkeling-overzicht' om snel te zien hoeveel leerlingen vooruitgaan, stabiel blijven of terugvallen. De ranglijst vergelijkt per leerling de vorige en huidige toets; de mini-trend laat alle toetsen in de selectie zien.",
                    "tip": "Een onderdeel verschijnt alleen als het bij vragen is ingevuld en in meerdere toetsen voorkomt.",
                },
                {
                    "title": "Afwezig of niet gemaakt",
                    "text": "Onderaan staat een lijst met leerlingen die in de gekozen toetsselectie vaker niet hebben meegedaan.",
                    "action": "Gebruik deze lijst om te zien of een ontwikkeling misschien komt door gemiste toetsen in plaats van door inhoudelijke groei of terugval.",
                    "tip": "De lijst telt statussen zoals absent, ziek, vrijstelling, ongeldig en niet gemaakt.",
                },
                {
                    "title": "Exporteren",
                    "text": "Met de PDF-knoppen maakt u een groeps- of leerlingontwikkelrapport. Voor het opslaan kiest u in een wizard welke onderdelen meegaan.",
                    "action": "Vink bijvoorbeeld kerncijfers, toetsontwikkeling, onderdelen, signalen en herkansingen aan of uit.",
                    "tip": "De export gebruikt exact dezelfde filters en toetsselectie als het dashboard.",
                },
            ],
        }

    def refresh(self) -> None:
        selected_year = self.school_year_filter.currentData() if hasattr(self, "school_year_filter") else None
        if self.force_project_year and self.year_id is not None:
            selected_year = self.year_id
        selected_level = self.level_filter.currentData() if hasattr(self, "level_filter") else None
        selected_grade = self.grade_filter.currentData() if hasattr(self, "grade_filter") else None
        selected_group = self.group_filter.currentData() if hasattr(self, "group_filter") else None
        options = development_filter_options(self.database)
        self.loading = True
        for combo in (self.school_year_filter, self.level_filter, self.grade_filter, self.group_filter):
            combo.blockSignals(True)
            combo.clear()
        self.school_year_filter.addItem("Alle schooljaren", None)
        for year in options["school_years"]:
            self.school_year_filter.addItem(str(year["name"]), year["id"])
        self.level_filter.addItem("Alle niveaus", None)
        for level in options["levels"]:
            self.level_filter.addItem(str(level["label"]), level["value"])
        self.grade_filter.addItem("Alle jaarlagen", None)
        for grade in options["grades"]:
            self.grade_filter.addItem(str(grade["label"]), grade["value"])
        self.group_filter.addItem("Alle groepen", None)
        for group in options["groups"]:
            self.group_filter.addItem(str(group["label"]), group["value"])
        for combo, selected in (
            (self.school_year_filter, selected_year),
            (self.level_filter, selected_level),
            (self.grade_filter, selected_grade),
            (self.group_filter, selected_group),
        ):
            if selected is not None:
                index = combo.findData(selected)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.blockSignals(False)
        self.force_project_year = False
        self.loading = False
        self.load_dashboard()

    def filters_changed(self) -> None:
        if self.loading:
            return
        self.selected_test_ids = None
        self.load_dashboard()

    def has_required_development_filters(self) -> bool:
        return self.level_filter.currentData() is not None and self.grade_filter.currentData() is not None

    def required_filters_message(self) -> str:
        missing = []
        if self.level_filter.currentData() is None:
            missing.append("niveau")
        if self.grade_filter.currentData() is None:
            missing.append("jaarlaag")
        return " en ".join(missing)

    def current_test_options(self) -> list[dict[str, object]]:
        if not self.has_required_development_filters():
            return []
        return development_test_options(
            self.database,
            school_year_id=self.school_year_filter.currentData(),
            level=self.level_filter.currentData(),
            grade_year=self.grade_filter.currentData(),
            group=self.group_filter.currentData(),
        )

    def effective_selected_test_ids(self) -> set[int] | None:
        if self.selected_test_ids is None:
            return None
        available_ids = {int(test["id"]) for test in self.current_test_options()}
        return {test_id for test_id in self.selected_test_ids if test_id in available_ids}

    def update_test_selection_label(self) -> None:
        if not self.has_required_development_filters():
            self.test_selection_label.setText("Kies niveau en jaarlaag")
            self.choose_tests_button.setEnabled(False)
            self.choose_tests_button.setToolTip("Kies eerst niveau en jaarlaag.")
            return
        self.choose_tests_button.setEnabled(True)
        self.choose_tests_button.setToolTip("")
        tests = self.current_test_options()
        total = len(tests)
        if self.selected_test_ids is None:
            self.test_selection_label.setText(f"Alle toetsen ({total})")
            return
        available_ids = {int(test["id"]) for test in tests}
        selected = len({test_id for test_id in self.selected_test_ids if test_id in available_ids})
        self.test_selection_label.setText(f"{selected} van {total} toetsen")

    def choose_tests(self) -> None:
        if not self.has_required_development_filters():
            QMessageBox.information(
                self,
                "Kies eerst filters",
                "Kies eerst niveau en jaarlaag. Daarna kunt u de toetsen kiezen die meegenomen worden.",
            )
            return
        tests = self.current_test_options()
        selected_ids = self.effective_selected_test_ids()
        dialog = DevelopmentTestSelectionDialog(tests, selected_ids, self)
        if not tests:
            QMessageBox.information(
                self,
                "Geen toetsen",
                "Er zijn geen toetsen gevonden binnen de gekozen filters. Pas eerst schooljaar, niveau, jaarlaag of groep aan.",
            )
            return
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_ids()
        all_ids = {int(test["id"]) for test in tests}
        self.selected_test_ids = None if selected == all_ids else selected
        self.load_dashboard()

    def load_dashboard(self) -> None:
        if self.loading:
            return
        self.update_test_selection_label()
        if QWebEngineView is None or not isinstance(self.dashboard, QWebEngineView):
            return
        if not self.has_required_development_filters():
            missing = self.required_filters_message()
            self.dashboard.setHtml(
                "<style>"
                "body{font:15px 'Segoe UI';background:#f6f8fb;color:#071f42;margin:0;padding:34px}"
                ".card{background:#fff;border:1px solid #e3eaf3;border-radius:18px;padding:28px;max-width:760px;"
                "box-shadow:0 14px 36px rgba(15,35,70,.08)}"
                "h2{margin:0 0 10px;font-size:26px}.muted{color:#62708a;line-height:1.55}"
                ".pill{display:inline-block;margin-top:14px;background:#eef3ff;color:#40516a;border-radius:999px;padding:8px 12px;font-weight:700}"
                "</style>"
                "<div class='card'>"
                "<h2>Kies eerst niveau en jaarlaag</h2>"
                f"<div class='muted'>De ontwikkelanalyse wordt pas gemaakt nadat niveau en jaarlaag gekozen zijn. "
                f"Nog nodig: <b>{html.escape(missing)}</b>. De groep mag op 'Alle groepen' blijven staan.</div>"
                "<div class='pill'>Stap 1: kies niveau · Stap 2: kies jaarlaag · Stap 3: kies eventueel toetsen</div>"
                "</div>"
            )
            return
        try:
            data = self.current_development_data()
            asset_directory = Path(__file__).parent / "assets"
            self.dashboard.setHtml(
                build_development_dashboard_html(data, "plotly-2.35.2.min.js"),
                QUrl.fromLocalFile(str(asset_directory.resolve()) + "/"),
            )
            self.set_dashboard_zoom(self.dashboard_zoom)
        except Exception as error:
            self.dashboard.setHtml(
                "<style>body{font:14px 'Segoe UI';background:#f7f8fc;color:#071f42;padding:32px}</style>"
                f"<h2>Ontwikkelanalyse kon niet worden geladen</h2><p>{html.escape(str(error))}</p>"
            )

    def current_development_data(self) -> dict[str, object]:
        return development_data(
            self.database,
            school_year_id=self.school_year_filter.currentData(),
            level=self.level_filter.currentData(),
            grade_year=self.grade_filter.currentData(),
            group=self.group_filter.currentData(),
            selected_test_ids=self.effective_selected_test_ids(),
        )

