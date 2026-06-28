from __future__ import annotations

import html
import json
import os
import re
import shutil
import sqlite3
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path


def _configure_display_environment() -> None:
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_SCALE_FACTOR_ROUNDING_POLICY", "PassThrough")
    if os.environ.get("QSG_RHI_BACKEND", "").strip().casefold() == "software":
        os.environ.pop("QSG_RHI_BACKEND", None)
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
    except Exception:
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def _configure_qtwebengine_environment() -> None:
    if not sys.platform.startswith("win"):
        return
    # Deze flags moeten gezet zijn voordat QtWebEngine geladen wordt.
    existing_flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    force_software = os.environ.get("TOETSVIZIER_FORCE_SOFTWARE_RENDERING", "").strip().casefold()
    force_software = force_software in {"1", "true", "yes", "ja"}
    required_flags = [
        "--disable-direct-composition",
        "--disable-features=UseHDRTransferFunction,DirectCompositionVideoOverlays,VizDisplayCompositor",
        "--disable-breakpad",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--noerrdialogs",
        "--disable-logging",
        "--log-level=3",
        "--v=0",
    ]
    if force_software:
        required_flags.extend(
            [
                "--disable-gpu",
                "--disable-gpu-compositing",
                "--disable-gpu-rasterization",
                "--disable-gpu-vsync",
                "--disable-accelerated-2d-canvas",
                "--disable-accelerated-video-decode",
                "--disable-webgl",
                "--disable-3d-apis",
            ]
        )
    merged_flags = existing_flags.split() if existing_flags else []
    for flag in required_flags:
        if flag not in merged_flags:
            merged_flags.append(flag)
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(merged_flags).strip()
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    if force_software:
        os.environ.setdefault("QTWEBENGINE_DISABLE_GPU", "1")
        os.environ.setdefault("QT_OPENGL", "software")
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
    existing_rules = os.environ.get("QT_LOGGING_RULES", "").strip()
    quiet_rules = "qt.webenginecontext.debug=false;qt.webenginecontext.warning=false"
    os.environ["QT_LOGGING_RULES"] = f"{existing_rules};{quiet_rules}" if existing_rules else quiet_rules


_configure_display_environment()
_configure_qtwebengine_environment()


from PySide6.QtCore import QDate, QEvent, QObject, QPoint, QSettings, QThread, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QFont,
    QFontMetrics,
    QIcon,
    QPainter,
    QPen,
    QPixmap,
    QPolygon,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QToolTip,
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


def _can_use_webengine() -> bool:
    return (
        QWebEngineView is not None
        and QWebChannel is not None
        and os.environ.get("QT_QPA_PLATFORM", "").casefold() != "offscreen"
    )


from .database import SubjectDatabase
from .name_sorting import student_sort_key
from .analysis_page import AnalysisPage
from .dialogs_base import FormDialog
from .help_wizard import HelpWizardDialog, _build_help_faq, _enrich_help_steps
from .development_analysis import development_analysis_enabled
from .development_page import DevelopmentAnalysisPage
from .importers import (
    StudentImportError,
    import_students,
    read_magister_students,
)
from .logging_setup import configure_logging, install_exception_hook, log_exception
from .paths import DATA_DIR, EXCEL_EXPORT_DIR, PDF_EXPORT_DIR, ensure_app_directories
from .norming import dashboard_data, has_active_normalization, load_normalization, remove_normalization, save_normalization
from .norming_dashboard import build_norming_dashboard_html
from .norming_exports import build_participant_overview_html, export_participant_overview_xlsx, participant_rows
from .pages_base import Page
from .matrix_page import MatrixPage
from .pdf_export import PdfExportError, browser_report_html, export_html_to_pdf
from .question_bank import (
    QUESTION_BANK_STATUSES,
    load_active_question_properties,
    load_all_taxonomies,
    question_database_distinct_property_values,
    question_database_enabled,
    question_database_latest_rows,
)
from .question_database_page import (
    QuestionDatabaseAnalysisDialog,
    QuestionDatabaseDialog,
    QuestionDatabasePage,
)
from .question_dialogs import (
    LinkedDatabaseQuestionDialog,
    QuestionDatabaseFilterPanel,
    QuestionDatabaseImportDialog,
    QuestionDatabaseSelectionDialog,
    QuestionDialog,
)
from .results import (
    ResultValidationError,
    normalize_multiple_choice_response,
    regrade_multiple_choice_question,
)
from .student_report_wizard import StudentReportWizardDialog
from .results_page import ResultsPage
from .self_update import SelfUpdateError, download_update_installer, launch_installer
from .student_attribute_analysis import (
    GROUP_ATTRIBUTE_KEY,
    analyzable_student_attributes,
    available_attribute_dimensions,
    available_attribute_values,
    student_attribute_analysis_enabled,
    student_attribute_grade_distribution,
    student_attribute_dimension_summary,
    student_attribute_summary,
    student_attribute_year_comparison,
)
from .update_checker import (
    DEFAULT_UPDATE_MANIFEST_URL,
    UPDATE_AUTO_CHECK_KEY,
    UPDATE_MANIFEST_URL_KEY,
    UpdateCheckError,
    UpdateInfo,
    check_for_update,
    semantic_version_explanation,
)
from .branding import brand_app_icon, draw_brand_emblem
from .ui_helpers import (
    DashboardZoomBar,
    compact_action_button,
    make_empty_state,
    make_info_banner,
    make_page_header,
    make_responsive_filter_card,
    set_button_role,
)
from .version import APP_VERSION


LEVEL_OPTIONS = [
    "",
    "vmbo basis kader",
    "vmbo kader",
    "mavo",
    "havo",
    "vwo",
    "basis/kader",
    "kader/mavo",
    "mavo/havo",
    "havo/vwo",
]
BRAND_TITLE = "TOETSVIZIER"
BRAND_SUBTITLE = "Inzicht in toetskwaliteit, leerlingontwikkeling en resultaten."
BRAND_COPYRIGHT = "©Tom Sommers"
UPDATE_MANIFEST_EDIT_UNLOCK_KEY = "updates/manifest_url_edit_unlocked"


def settings_bool(settings: QSettings, key: str, default: bool = False) -> bool:
    value = settings.value(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "ja", "aan"}


class UpdateCheckThread(QThread):
    result_ready = Signal(object)
    error_ready = Signal(str)

    def __init__(
        self,
        manifest_url: str,
        current_version: str,
        timeout: int = 8,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.manifest_url = manifest_url
        self.current_version = current_version
        self.timeout = timeout

    def run(self) -> None:
        try:
            result = check_for_update(
                self.manifest_url,
                current_version=self.current_version,
                timeout=self.timeout,
            )
        except UpdateCheckError as error:
            self.error_ready.emit(str(error))
        except Exception as error:
            self.error_ready.emit(f"Updatecontrole is mislukt: {error}")
        else:
            self.result_ready.emit(result)


class UpdateDownloadThread(QThread):
    progress_ready = Signal(int, object)
    result_ready = Signal(str)
    error_ready = Signal(str)

    def __init__(
        self,
        info: UpdateInfo,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.info = info

    def run(self) -> None:
        try:
            installer_path = download_update_installer(
                self.info.installer_url,
                version=self.info.latest_version,
                expected_sha256=self.info.installer_sha256,
                progress_callback=self._emit_progress,
            )
        except SelfUpdateError as error:
            self.error_ready.emit(str(error))
        except Exception as error:
            self.error_ready.emit(f"De update kon niet worden voorbereid: {error}")
        else:
            self.result_ready.emit(str(installer_path))

    def _emit_progress(self, received: int, total: int | None) -> None:
        self.progress_ready.emit(received, total)


def update_manifest_url_from_settings(settings: QSettings) -> str:
    if not settings_bool(settings, UPDATE_MANIFEST_EDIT_UNLOCK_KEY, False):
        return DEFAULT_UPDATE_MANIFEST_URL
    value = str(settings.value(UPDATE_MANIFEST_URL_KEY, DEFAULT_UPDATE_MANIFEST_URL)).strip()
    return value or DEFAULT_UPDATE_MANIFEST_URL


class UpdateAvailableDialog(QDialog):
    def __init__(self, info: UpdateInfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.info = info
        self.download_thread: UpdateDownloadThread | None = None
        self.downloaded_installer: Path | None = None
        self.setWindowTitle("Update beschikbaar")
        self.setMinimumSize(560, 420)
        layout = QVBoxLayout(self)
        title = QLabel(f"<h2>ToetsVizier {html.escape(info.latest_version)} is beschikbaar</h2>")
        title.setWordWrap(True)
        intro = QLabel(
            f"U gebruikt versie <b>{html.escape(info.current_version)}</b>. "
            f"De nieuwste versie is <b>{html.escape(info.latest_version)}</b>."
        )
        intro.setWordWrap(True)
        version_hint = QLabel(
            "Versienummers werken als <b>1.2.3</b>: "
            "1 = grote update, 2 = middelgrote update, 3 = kleine update/patch."
        )
        version_hint.setWordWrap(True)
        notes = QTextBrowser()
        notes.setOpenExternalLinks(True)
        notes.setHtml(self._release_notes_html())
        notes.setMinimumHeight(210)
        self.status_label = QLabel(
            "Kies 'Downloaden en installeren' om de nieuwe versie binnen te halen. "
            "Na het downloaden sluit ToetsVizier af en start de installer."
        )
        self.status_label.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        buttons = QDialogButtonBox()
        self.download_button = buttons.addButton("Downloaden en installeren", QDialogButtonBox.ButtonRole.AcceptRole)
        self.release_page_button = buttons.addButton("Releasepagina openen", QDialogButtonBox.ButtonRole.ActionRole)
        self.later_button = buttons.addButton("Later", QDialogButtonBox.ButtonRole.RejectRole)
        self.download_button.clicked.connect(self.download_or_install)
        self.release_page_button.clicked.connect(self.open_download)
        self.later_button.clicked.connect(self.reject)
        layout.addWidget(title)
        layout.addWidget(intro)
        layout.addWidget(version_hint)
        layout.addWidget(notes, 1)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress)
        layout.addWidget(buttons)

    def _release_notes_html(self) -> str:
        blocks = [
            "<style>"
            "body{font-family:Segoe UI,sans-serif;color:#172538;}"
            ".meta{color:#526884;margin-bottom:10px;}"
            ".version{border:1px solid #d7e2f2;border-radius:12px;padding:12px;margin:10px 0;background:#f8fbff;}"
            ".title{font-weight:700;color:#082653;}"
            ".type{display:inline-block;background:#eaf1ff;color:#2457d6;border-radius:999px;padding:2px 8px;margin-left:6px;font-size:12px;}"
            "li{margin-bottom:5px;}"
            "</style>"
        ]
        blocks.append(
            f"<p class='meta'>{html.escape(semantic_version_explanation(self.info.latest_version))}</p>"
        )
        if self.info.release_notes:
            blocks.append(f"<p>{html.escape(self.info.release_notes).replace(chr(10), '<br>')}</p>")
        if self.info.version_changes:
            blocks.append("<h3>Wijzigingen per versie</h3>")
            for change in self.info.version_changes:
                title = change.title or "Wijzigingen"
                block = (
                    "<div class='version'>"
                    f"<div><span class='title'>Versie {html.escape(change.version)} - {html.escape(title)}</span>"
                )
                if change.change_type:
                    block += f"<span class='type'>{html.escape(change.change_type)}</span>"
                block += "</div>"
                if change.changes:
                    block += "<ul>"
                    for item in change.changes:
                        block += f"<li>{html.escape(item)}</li>"
                    block += "</ul>"
                block += "</div>"
                blocks.append(block)
        else:
            blocks.append("<p>Er zijn voor deze versie nog geen gedetailleerde wijzigingsregels ingevuld.</p>")
        return "".join(blocks)

    def open_download(self) -> None:
        QDesktopServices.openUrl(QUrl(self.info.download_url))

    def download_or_install(self) -> None:
        if self.downloaded_installer is not None:
            self.confirm_and_install()
            return
        if self.download_thread and self.download_thread.isRunning():
            return
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)
        self.status_label.setText("De update wordt gedownload. Dit kan even duren.")
        self.download_button.setEnabled(False)
        self.release_page_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.download_thread = UpdateDownloadThread(self.info, self)
        self.download_thread.progress_ready.connect(self.update_progress)
        self.download_thread.result_ready.connect(self.download_finished)
        self.download_thread.error_ready.connect(self.download_failed)
        self.download_thread.finished.connect(self.finish_download)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        self.download_thread.start()

    def update_progress(self, received: int, total: object) -> None:
        total_bytes = int(total) if isinstance(total, int) and total > 0 else None
        if total_bytes is None:
            self.progress.setRange(0, 0)
            self.status_label.setText(
                f"De update wordt gedownload ({received / (1024 * 1024):.1f} MB ontvangen)."
            )
            return
        self.progress.setRange(0, total_bytes)
        self.progress.setValue(min(received, total_bytes))
        percentage = round(received / total_bytes * 100) if total_bytes else 0
        self.status_label.setText(
            f"De update wordt gedownload ({percentage}% - "
            f"{received / (1024 * 1024):.1f} van {total_bytes / (1024 * 1024):.1f} MB)."
        )

    def download_finished(self, installer_path: str) -> None:
        self.downloaded_installer = Path(installer_path)
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.status_label.setText(
            f"De installer is klaar: {self.downloaded_installer.name}. "
            "Sla open werk op en start daarna de installatie."
        )
        self.download_button.setText("Installer starten")
        self.confirm_and_install()

    def download_failed(self, message: str) -> None:
        self.progress.setVisible(False)
        self.status_label.setText(message)
        QMessageBox.warning(self, "Update downloaden mislukt", message)

    def finish_download(self) -> None:
        self.download_button.setEnabled(True)
        self.release_page_button.setEnabled(True)
        self.later_button.setEnabled(True)
        self.download_thread = None

    def confirm_and_install(self) -> None:
        if self.downloaded_installer is None:
            return
        answer = QMessageBox.question(
            self,
            "Update installeren",
            "De update is gedownload.\n\n"
            "De installer wordt nu gestart. Die kan ToetsVizier daarna zelf afsluiten als dat nodig is. "
            "Sla eerst open werk op.\n\n"
            "Nu doorgaan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            launch_installer(self.downloaded_installer)
        except SelfUpdateError as error:
            QMessageBox.warning(self, "Installer starten mislukt", str(error))
            return
        self.accept()

    def reject(self) -> None:
        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.information(
                self,
                "Download actief",
                "Wacht tot het downloaden klaar is voordat u dit venster sluit.",
            )
            return
        super().reject()


def show_update_result(parent: QWidget, info: UpdateInfo, *, silent_when_current: bool = False) -> None:
    if not info.is_newer:
        if not silent_when_current:
            QMessageBox.information(
                parent,
                "Geen update gevonden",
                f"U gebruikt de nieuwste bekende versie ({info.current_version}).",
            )
        return
    UpdateAvailableDialog(info, parent).exec()


def build_brand_banner(width: int = 640, height: int = 170) -> QPixmap:
    width = max(460, width)
    height = max(130, height)
    pixmap = QPixmap(width, height)
    pixmap.fill(QColor("#F8FBFF"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(0, 0, width, height, QColor("#F8FBFF"))

    emblem_size = int(height * 0.62)
    emblem = draw_brand_emblem(emblem_size)
    emblem_x = int(width * 0.035)
    emblem_y = int((height - emblem_size) * 0.26)
    painter.drawPixmap(emblem_x, emblem_y, emblem)

    text_x = emblem_x + emblem_size + 16
    right_padding = int(width * 0.035)
    text_width = max(140, width - text_x - right_padding)

    title_font = QFont("Segoe UI", max(12, int(height * 0.21)))
    title_font.setWeight(QFont.Weight.Bold)
    for point_size in range(max(12, int(height * 0.21)), 11, -1):
        candidate = QFont("Segoe UI", point_size)
        candidate.setWeight(QFont.Weight.Bold)
        if QFontMetrics(candidate).horizontalAdvance(BRAND_TITLE) <= text_width:
            title_font = candidate
            break
    painter.setFont(title_font)
    painter.setPen(QColor("#1A3C63"))
    title_text = QFontMetrics(title_font).elidedText(BRAND_TITLE, Qt.TextElideMode.ElideRight, text_width)
    painter.drawText(text_x, int(height * 0.44), title_text)

    subtitle_font = QFont("Segoe UI", max(8, int(height * 0.1)))
    subtitle_font.setWeight(QFont.Weight.Medium)
    for point_size in range(max(8, int(height * 0.1)), 7, -1):
        candidate = QFont("Segoe UI", point_size)
        candidate.setWeight(QFont.Weight.Medium)
        if QFontMetrics(candidate).horizontalAdvance(BRAND_SUBTITLE) <= text_width:
            subtitle_font = candidate
            break
    painter.setFont(subtitle_font)
    painter.setPen(QColor("#2C3A4D"))
    subtitle_text = QFontMetrics(subtitle_font).elidedText(
        BRAND_SUBTITLE, Qt.TextElideMode.ElideRight, text_width
    )
    painter.drawText(text_x, int(height * 0.62), subtitle_text)

    accent_top = height - 12
    section = width // 3
    painter.fillRect(0, accent_top, section, 8, QColor("#1A3C63"))
    painter.fillRect(section, accent_top, section, 8, QColor("#3FCFCF"))
    painter.fillRect(section * 2, accent_top, width - (section * 2), 8, QColor("#66CC66"))
    painter.end()
    return pixmap


def slug(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip().lower())
    return cleaned.strip("_") or "vak"


def item(value: object) -> QTableWidgetItem:
    cell = QTableWidgetItem("" if value is None else str(value))
    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return cell


class CenteredComboBox(QComboBox):
    def paintEvent(self, event) -> None:
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        option.currentText = ""
        painter = QStylePainter(self)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        text_rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxEditField,
            self,
        )
        text_rect.adjust(4, 0, -4, 0)
        painter.setPen(self.palette().text().color())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.currentText())
        center_x = self.width() - 14
        center_y = self.height() // 2 + 1
        arrow_color = QColor("#40516a") if self.currentText() in {"gemaakt", "niet analyseren"} else QColor("#ffffff")
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(arrow_color)
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(center_x - 5, center_y - 3),
                    QPoint(center_x + 5, center_y - 3),
                    QPoint(center_x, center_y + 4),
                ]
            )
        )


def configure_table(table: QTableWidget, headers: list[str]) -> None:
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    header.setDefaultSectionSize(150)
    header.setMinimumSectionSize(72)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setWordWrap(False)
    table.verticalHeader().setVisible(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)


def fit_to_available_screen(
    widget: QWidget,
    preferred_width: int = 900,
    preferred_height: int = 640,
    margin: int = 72,
) -> None:
    screen = widget.screen() or QApplication.primaryScreen()
    if not screen:
        widget.resize(preferred_width, preferred_height)
        return
    available = screen.availableGeometry()
    width = min(preferred_width, max(420, available.width() - margin))
    height = min(preferred_height, max(360, available.height() - margin))
    widget.setMaximumSize(max(420, available.width() - 24), max(360, available.height() - 24))
    widget.resize(width, height)


def compact_action_button(button: QPushButton, tooltip: str | None = None, width: int | None = None) -> QPushButton:
    button.setFixedHeight(34)
    if width is not None:
        button.setFixedWidth(width)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    if tooltip:
        button.setToolTip(tooltip)
    return button


class NewSubjectDialog(FormDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Nieuw vak aanmaken", parent)
        current = date.today()
        start_year = current.year if current.month >= 8 else current.year - 1
        self.subject = QLineEdit()
        self.school_year = QLineEdit(f"{start_year}-{start_year + 1}")
        self.form.addRow("Vaknaam *", self.subject)
        self.form.addRow("Eerste schooljaar *", self.school_year)

    def accept(self) -> None:
        if self.required(self.subject, "een vaknaam") and self.required(self.school_year, "een schooljaar"):
            super().accept()


class ClassDialog(FormDialog):
    def __init__(self, classroom=None, parent: QWidget | None = None) -> None:
        super().__init__("Klas of groep bewerken" if classroom else "Klas of groep toevoegen", parent)
        self.name = QLineEdit()
        self.level = QComboBox()
        self.level.addItems(LEVEL_OPTIONS)
        self.grade = QComboBox()
        self.grade.addItems(["", "1", "2", "3", "4", "5", "6"])
        self.form.addRow("Naam *", self.name)
        self.form.addRow("Niveau", self.level)
        self.form.addRow("Leerjaar", self.grade)
        if classroom:
            self.name.setText(classroom["name"])
            self.level.setCurrentText(classroom["level"] or "")
            self.grade.setCurrentText(classroom["grade_year"] or "")

    def accept(self) -> None:
        if self.required(self.name, "een klasnaam"):
            super().accept()


class StudentDialog(FormDialog):
    def __init__(
        self, classes: list, attributes: list | None = None, student=None, attribute_values=None,
        parent: QWidget | None = None
    ) -> None:
        super().__init__("Leerling bewerken" if student else "Leerling toevoegen", parent)
        self.attribute_widgets: dict[int, QWidget] = {}
        self.display_name = QLineEdit()
        self.student_number = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.student_class = QComboBox()
        self.student_class.addItem("Geen klas gekoppeld", None)
        for classroom in classes:
            self.student_class.addItem(classroom["name"], classroom["id"])
        self.form.addRow("Weergavenaam *", self.display_name)
        self.form.addRow("Leerlingnummer", self.student_number)
        self.form.addRow("Voornaam", self.first_name)
        self.form.addRow("Achternaam", self.last_name)
        self.form.addRow("Klas/groep", self.student_class)
        for attribute in attributes or []:
            if attribute["field_type"] == "ja/nee":
                widget = QComboBox()
                widget.addItems(["", "Ja", "Nee"])
            elif attribute["field_type"] == "keuzelijst":
                widget = QComboBox()
                choices = json.loads(attribute["options_json"]) if attribute["options_json"] else []
                widget.addItem("")
                widget.addItems(choices)
            else:
                widget = QLineEdit()
            value = (attribute_values or {}).get(attribute["id"], "")
            if isinstance(widget, QComboBox):
                if value and widget.findText(value) < 0:
                    widget.addItem(value)
                widget.setCurrentText(value)
            else:
                widget.setText(value)
            self.attribute_widgets[attribute["id"]] = widget
            self.form.addRow(attribute["name"], widget)
        if student:
            self.display_name.setText(student["display_name"])
            self.student_number.setText(student["student_number"] or "")
            self.first_name.setText(student["first_name"] or "")
            self.last_name.setText(student["last_name"] or "")
            selected_class = self.student_class.findData(student["class_id"])
            if selected_class >= 0:
                self.student_class.setCurrentIndex(selected_class)

    def accept(self) -> None:
        if self.required(self.display_name, "een weergavenaam"):
            super().accept()

    def attribute_value(self, attribute_id: int) -> str:
        widget = self.attribute_widgets[attribute_id]
        if isinstance(widget, QComboBox):
            return widget.currentText()
        return widget.text().strip()


class StudentAttributeDialog(FormDialog):
    def __init__(self, attribute=None, parent: QWidget | None = None) -> None:
        super().__init__("Leerlingeigenschap bewerken" if attribute else "Leerlingeigenschap toevoegen", parent)
        self.name = QLineEdit()
        self.field_type = QComboBox()
        self.field_type.addItems(["tekst", "keuzelijst", "getal", "ja/nee", "opmerking"])
        self.choices = QListWidget()
        self.choices.setMinimumHeight(120)
        self.choices_panel = QFrame()
        self.choices_panel.setObjectName("panel")
        choices_layout = QVBoxLayout(self.choices_panel)
        choices_layout.setContentsMargins(10, 10, 10, 10)
        choices_layout.setSpacing(8)
        choices_note = QLabel(
            "Voeg de vaste keuzes toe die u later bij leerlingen kunt selecteren. "
            "Alleen keuzelijsten, ja/nee en getallen kunnen in de eigenschapsanalyse worden gebruikt."
        )
        choices_note.setWordWrap(True)
        choices_layout.addWidget(choices_note)
        choices_layout.addWidget(self.choices)
        choice_buttons = QHBoxLayout()
        add_choice = QPushButton("Optie toevoegen")
        add_choice.clicked.connect(self.add_choice)
        delete_choice = QPushButton("Optie verwijderen")
        delete_choice.clicked.connect(self.delete_choice)
        choice_buttons.addStretch()
        choice_buttons.addWidget(delete_choice)
        choice_buttons.addWidget(add_choice)
        choices_layout.addLayout(choice_buttons)
        self.form.addRow("Naam *", self.name)
        self.form.addRow("Type", self.field_type)
        self.form.addRow("Opties", self.choices_panel)
        self.field_type.currentTextChanged.connect(self.update_choice_visibility)
        if attribute:
            self.name.setText(attribute["name"])
            self.field_type.setCurrentText(attribute["field_type"])
            choices = json.loads(attribute["options_json"]) if attribute["options_json"] else []
            for choice in choices:
                self.choices.addItem(choice)
        self.update_choice_visibility()

    def add_choice(self) -> None:
        value, ok = QInputDialog.getText(self, "Optie toevoegen", "Nieuwe optie:")
        value = value.strip()
        if not ok or not value:
            return
        if value in self.choice_values():
            QMessageBox.warning(self, "Optie bestaat al", "Deze optie staat al in de lijst.")
            return
        self.choices.addItem(value)

    def delete_choice(self) -> None:
        row = self.choices.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen optie geselecteerd", "Selecteer eerst een optie om te verwijderen.")
            return
        value = self.choices.item(row).text()
        choice = QMessageBox.question(
            self, "Optie verwijderen", f"Weet u zeker dat u de optie {value} wilt verwijderen?"
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        self.choices.takeItem(row)

    def choice_values(self) -> list[str]:
        return [self.choices.item(index).text() for index in range(self.choices.count())]

    def update_choice_visibility(self) -> None:
        enabled = self.field_type.currentText() == "keuzelijst"
        self.choices_panel.setVisible(enabled)
        label = self.form.labelForField(self.choices_panel)
        if label is not None:
            label.setVisible(enabled)

    def accept(self) -> None:
        if not self.required(self.name, "een naam"):
            return
        if self.field_type.currentText() == "keuzelijst" and not self.choice_values():
            QMessageBox.warning(self, "Opties ontbreken", "Voeg minimaal één optie toe voor deze keuzelijst.")
            return
        super().accept()


class StudentImportDialog(FormDialog):
    def __init__(self, classes: list, parent: QWidget | None = None) -> None:
        super().__init__("Leerlingen importeren uit Excel", parent)
        self.setMinimumWidth(560)
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        browse = QPushButton("Excelbestand kiezen")
        browse.clicked.connect(self.choose_file)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_path, 1)
        file_row.addWidget(browse)
        self.student_class = QComboBox()
        for classroom in classes:
            self.student_class.addItem(classroom["name"], classroom["id"])
        explanation = QLabel(
            "Het programma zoekt de Magister-kopregel automatisch. Ondersteund: Stamnummer, Roepnaam, "
            "Tussenvoegsel, Achternaam en optioneel Email. De kolom Klas uit Magister wordt genegeerd; "
            "kies hieronder de cluster/groep voor dit vak."
        )
        explanation.setWordWrap(True)
        self.form.addRow(explanation)
        self.form.addRow("Excelbestand *", file_row)
        self.form.addRow("Cluster/groep *", self.student_class)

    def choose_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Magister-export selecteren", "", "Excelbestand (*.xlsx *.xlsm)"
        )
        if selected:
            self.file_path.setText(selected)

    def accept(self) -> None:
        if not self.file_path.text().strip():
            QMessageBox.warning(self, "Bestand ontbreekt", "Kies eerst een Excelbestand.")
            return
        if self.student_class.currentData() is None:
            QMessageBox.warning(self, "Groep ontbreekt", "Kies een cluster/groep voor de leerlingen.")
            return
        super().accept()




class TestDialog(FormDialog):
    def __init__(
        self, classes: list, available_original_tests=None, taxonomies=None, properties=None, test=None,
        selected_class_ids=None, selected_taxonomy_ids=None, selected_property_ids=None,
        selected_property_options=None, selected_question_types=None,
        students=None, selected_extra_student_ids=None,
        parent: QWidget | None = None
    ) -> None:
        super().__init__("Toets bewerken" if test else "Nieuwe toets", parent)
        self._loading_test_config = True
        self._property_definitions = [dict(property_definition) for property_definition in (properties or [])]
        self.property_option_lists: dict[int, QListWidget] = {}
        self.property_option_labels: dict[int, QLabel] = {}
        self.property_names: dict[int, str] = {}
        self.question_type_property_id = None
        self.question_types = None
        self.name = QLineEdit()
        self.period = QComboBox()
        self.period.addItems(
            [
                "Periode 1",
                "Periode 2",
                "Periode 3",
                "Periode 4",
                "Toetsweek 1",
                "Toetsweek 2",
                "Toetsweek 3",
                "Anders",
            ]
        )
        self.test_type = QComboBox()
        self.test_type.addItems(["Proefwerk", "SO", "SE", "Diagnostisch", "Formatief", "Herkansing"])
        self.test_type.currentTextChanged.connect(self.update_resit_fields)
        self.original_test = QComboBox()
        self.original_test.addItem("Kies de oorspronkelijke toets", None)
        for original in available_original_tests or []:
            self.original_test.addItem(original["name"], original["id"])
        self.level = QComboBox()
        self.level.addItems(LEVEL_OPTIONS)
        self.grade = QComboBox()
        self.grade.addItems(["", "1", "2", "3", "4", "5", "6"])
        self.test_date = QDateEdit()
        self.test_date.setCalendarPopup(True)
        self.test_date.setDate(QDate.currentDate())
        self.minutes = QSpinBox()
        self.minutes.setRange(0, 600)
        self.minutes.setSpecialValueText("Niet ingevuld")
        self.weight = QDoubleSpinBox()
        self.weight.setRange(0, 1000)
        self.weight.setDecimals(2)
        self.weight.setSingleStep(0.1)
        self.weight.setValue(1)
        self.weight.setToolTip("Deze weging kan later worden gebruikt voor analyses over meerdere toetsen.")
        self.classes = QListWidget()
        for classroom in classes:
            self.classes.addItem(classroom["name"])
            entry = self.classes.item(self.classes.count() - 1)
            entry.setData(Qt.ItemDataRole.UserRole, classroom["id"])
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Unchecked)
        self.extra_students = QListWidget()
        self.extra_students.setMinimumHeight(140)
        self.extra_students.setToolTip("Gebruik dit voor leerlingen die niet via een gekoppelde klas/groep in deze toets zitten.")
        for student in students or []:
            label = student["display_name"]
            if student.get("student_number"):
                label = f"{label} ({student['student_number']})"
            self.extra_students.addItem(label)
            entry = self.extra_students.item(self.extra_students.count() - 1)
            entry.setData(Qt.ItemDataRole.UserRole, student["id"])
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Unchecked)
        self.taxonomies = QListWidget()
        for taxonomy in taxonomies or []:
            self.taxonomies.addItem(taxonomy["name"])
            entry = self.taxonomies.item(self.taxonomies.count() - 1)
            entry.setData(Qt.ItemDataRole.UserRole, taxonomy["id"])
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Unchecked)
        self.properties = QListWidget()
        self.properties.setMinimumHeight(160)
        for property_definition in self._property_definitions:
            property_id = int(property_definition["id"])
            self.property_names[property_id] = property_definition["name"]
            choices = json.loads(property_definition["choices_json"]) if property_definition["choices_json"] else []
            if property_definition["name"] == "Vraagtype":
                self.question_type_property_id = property_id
            field_label = property_definition["name"]
            if property_definition["choices_json"]:
                field_label += " (keuzelijst)"
            self.properties.addItem(field_label)
            entry = self.properties.item(self.properties.count() - 1)
            entry.setData(Qt.ItemDataRole.UserRole, property_id)
            entry.setData(int(Qt.ItemDataRole.UserRole) + 1, property_definition["name"])
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Unchecked)
            if choices:
                options = QListWidget()
                options.setMinimumHeight(92)
                options.setMaximumHeight(150)
                for choice in choices:
                    options.addItem(choice)
                    option = options.item(options.count() - 1)
                    option.setFlags(option.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    option.setCheckState(Qt.CheckState.Unchecked)
                self.property_option_lists[property_id] = options
                if property_definition["name"] == "Vraagtype":
                    self.question_types = options
        self.form.addRow("Naam *", self.name)
        self.form.addRow("Periode *", self.period)
        self.form.addRow("Toetssoort *", self.test_type)
        self.resit_label = QLabel("Herkansing van *")
        self.form.addRow(self.resit_label, self.original_test)
        self.form.addRow("Niveau", self.level)
        self.form.addRow("Jaarlaag", self.grade)
        self.form.addRow("Datum", self.test_date)
        self.form.addRow("Duur in minuten", self.minutes)
        self.form.addRow("Weging", self.weight)
        self.form.addRow("Klassen/groepen *", self.classes)
        self.form.addRow("Extra leerlingen", self.extra_students)
        self.form.addRow("Taxonomieën *", self.taxonomies)
        self.form.addRow("Velden toevoegen aan vragen", self.properties)
        for property_id, options in self.property_option_lists.items():
            label = QLabel(f"Opties voor {self.property_names[property_id]}")
            self.property_option_labels[property_id] = label
            self.form.addRow(label, options)
        self.properties.itemChanged.connect(self.update_property_option_sections)
        if test:
            self.name.setText(test["name"])
            self.period.setCurrentText(test["period"])
            self.test_type.setCurrentText(test["test_type"])
            original_index = self.original_test.findData(test["original_test_id"])
            if original_index >= 0:
                self.original_test.setCurrentIndex(original_index)
            self.level.setCurrentText(test["level"] or "")
            self.grade.setCurrentText(test["grade_year"] or "")
            if test["test_date"]:
                self.test_date.setDate(QDate.fromString(test["test_date"], "yyyy-MM-dd"))
            self.minutes.setValue(test["available_time_minutes"] or 0)
            self.weight.setValue(float(test["weight"]) if test["weight"] is not None else 1)
            selected_class_ids = set(selected_class_ids or [])
            for index in range(self.classes.count()):
                entry = self.classes.item(index)
                if entry.data(Qt.ItemDataRole.UserRole) in selected_class_ids:
                    entry.setCheckState(Qt.CheckState.Checked)
            selected_extra_student_ids = set(selected_extra_student_ids or [])
            for index in range(self.extra_students.count()):
                entry = self.extra_students.item(index)
                if entry.data(Qt.ItemDataRole.UserRole) in selected_extra_student_ids:
                    entry.setCheckState(Qt.CheckState.Checked)
            selected_taxonomy_ids = set(selected_taxonomy_ids or [])
            for index in range(self.taxonomies.count()):
                entry = self.taxonomies.item(index)
                if entry.data(Qt.ItemDataRole.UserRole) in selected_taxonomy_ids:
                    entry.setCheckState(Qt.CheckState.Checked)
            selected_property_ids = set(selected_property_ids or [])
            for index in range(self.properties.count()):
                entry = self.properties.item(index)
                if entry.data(Qt.ItemDataRole.UserRole) in selected_property_ids:
                    entry.setCheckState(Qt.CheckState.Checked)
            selected_property_options = selected_property_options or {}
            if selected_question_types and self.question_type_property_id is not None:
                selected_property_options = {
                    **selected_property_options,
                    self.question_type_property_id: selected_question_types,
                }
            for property_id, options in self.property_option_lists.items():
                selected_options = set(selected_property_options.get(property_id, []))
                for index in range(options.count()):
                    option = options.item(index)
                    if option.text() in selected_options:
                        option.setCheckState(Qt.CheckState.Checked)
        self.update_resit_fields()
        self._loading_test_config = False
        self.update_property_option_sections()

    def accept(self) -> None:
        if not self.required(self.name, "een toetsnaam"):
            return
        if self.test_type.currentText() == "Herkansing" and self.original_test.currentData() is None:
            QMessageBox.warning(self, "Oorspronkelijke toets ontbreekt", "Kies van welke toets dit een herkansing is.")
            return
        if not self.checked_class_ids():
            QMessageBox.warning(self, "Groep ontbreekt", "Vink minimaal een klas of groep aan voor deze toets.")
            return
        if not self.checked_taxonomy_ids():
            QMessageBox.warning(self, "Taxonomie ontbreekt", "Selecteer minimaal een taxonomie voor deze toets.")
            return
        checked_property_ids = set(self.checked_property_ids())
        for property_id, options in self.property_option_lists.items():
            if property_id in checked_property_ids and not self.checked_property_options().get(property_id):
                QMessageBox.warning(
                    self,
                    "Classificatie-opties ontbreken",
                    f"Vink minimaal een toegestane optie aan voor {self.property_names[property_id]}, "
                    "of vink deze classificatie uit.",
                )
                return
        super().accept()

    def update_resit_fields(self) -> None:
        is_resit = self.test_type.currentText() == "Herkansing"
        self.resit_label.setVisible(is_resit)
        self.original_test.setVisible(is_resit)
        self.original_test.setEnabled(is_resit)
        if not is_resit:
            self.original_test.setCurrentIndex(0)

    def checked_taxonomy_ids(self) -> list[int]:
        return [
            self.taxonomies.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.taxonomies.count())
            if self.taxonomies.item(index).checkState() == Qt.CheckState.Checked
        ]

    def checked_class_ids(self) -> list[int]:
        return [
            self.classes.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.classes.count())
            if self.classes.item(index).checkState() == Qt.CheckState.Checked
        ]

    def checked_extra_student_ids(self) -> list[int]:
        return [
            self.extra_students.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.extra_students.count())
            if self.extra_students.item(index).checkState() == Qt.CheckState.Checked
        ]

    def checked_property_ids(self) -> list[int]:
        return [
            self.properties.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.properties.count())
            if self.properties.item(index).checkState() == Qt.CheckState.Checked
        ]

    def checked_question_types(self) -> list[str]:
        if self.question_type_property_id is None:
            return []
        return self.checked_property_options().get(self.question_type_property_id, [])

    def checked_property_options(self) -> dict[int, list[str]]:
        selected: dict[int, list[str]] = {}
        for property_id, options in self.property_option_lists.items():
            values = [
                options.item(index).text()
                for index in range(options.count())
                if options.item(index).checkState() == Qt.CheckState.Checked
            ]
            if values:
                selected[property_id] = values
        return selected

    def update_property_option_sections(self, changed_item=None) -> None:
        checked_property_ids = set(self.checked_property_ids())
        for property_id, options in self.property_option_lists.items():
            enabled = property_id in checked_property_ids
            label = self.property_option_labels[property_id]
            label.setVisible(enabled)
            options.setVisible(enabled)
            options.setEnabled(enabled)
            if not enabled:
                for index in range(options.count()):
                    options.item(index).setCheckState(Qt.CheckState.Unchecked)
            elif not self._loading_test_config:
                has_selection = any(
                    options.item(index).checkState() == Qt.CheckState.Checked
                    for index in range(options.count())
                )
                if not has_selection:
                    for index in range(options.count()):
                        options.item(index).setCheckState(Qt.CheckState.Checked)

    def update_question_type_options(self, changed_item=None) -> None:
        self.update_property_option_sections(changed_item)




class QuestionPropertyDialog(FormDialog):
    def __init__(self, definition=None, parent: QWidget | None = None) -> None:
        super().__init__("Classificatie bewerken" if definition else "Vraageigenschap toevoegen", parent)
        self.name = QLineEdit()
        self.field_type = QComboBox()
        self.field_type.addItems(["tekst", "keuzelijst", "getal", "ja/nee", "opmerking"])
        self.choices = QListWidget()
        self.choices.setMinimumHeight(120)
        self.choices_panel = QFrame()
        self.choices_panel.setObjectName("panel")
        choices_layout = QVBoxLayout(self.choices_panel)
        choices_layout.setContentsMargins(10, 10, 10, 10)
        choices_layout.setSpacing(8)
        choices_note = QLabel("Beheer hier de opties die later bij vraaginvoer gekozen kunnen worden.")
        choices_note.setWordWrap(True)
        choices_layout.addWidget(choices_note)
        choices_layout.addWidget(self.choices)
        choice_buttons = QHBoxLayout()
        add_choice = QPushButton("Optie toevoegen")
        add_choice.clicked.connect(self.add_choice)
        delete_choice = QPushButton("Optie verwijderen")
        delete_choice.clicked.connect(self.delete_choice)
        choice_buttons.addStretch()
        choice_buttons.addWidget(delete_choice)
        choice_buttons.addWidget(add_choice)
        choices_layout.addLayout(choice_buttons)
        self.form.addRow("Naam *", self.name)
        self.form.addRow("Type", self.field_type)
        self.form.addRow("Opties", self.choices_panel)
        self.field_type.currentTextChanged.connect(self.update_choice_visibility)
        if definition:
            self.name.setText(definition["name"])
            self.field_type.setCurrentText(definition["field_type"])
            choices = json.loads(definition["choices_json"]) if definition["choices_json"] else []
            for choice in choices:
                self.choices.addItem(choice)
        self.update_choice_visibility()

    def add_choice(self) -> None:
        value, ok = QInputDialog.getText(self, "Optie toevoegen", "Nieuwe optie:")
        value = value.strip()
        if not ok or not value:
            return
        if value in self.choice_values():
            QMessageBox.warning(self, "Optie bestaat al", "Deze optie staat al in de lijst.")
            return
        self.choices.addItem(value)

    def delete_choice(self) -> None:
        row = self.choices.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen optie geselecteerd", "Selecteer eerst een optie om te verwijderen.")
            return
        value = self.choices.item(row).text()
        choice = QMessageBox.question(self, "Optie verwijderen", f"Weet u zeker dat u de optie {value} wilt verwijderen?")
        if choice != QMessageBox.StandardButton.Yes:
            return
        self.choices.takeItem(row)

    def choice_values(self) -> list[str]:
        return [self.choices.item(index).text() for index in range(self.choices.count())]

    def update_choice_visibility(self) -> None:
        enabled = self.field_type.currentText() in ("keuzelijst", "meerkeuze")
        self.choices_panel.setVisible(enabled)
        label = self.form.labelForField(self.choices_panel)
        if label is not None:
            label.setVisible(enabled)

    def accept(self) -> None:
        if not self.required(self.name, "een naam"):
            return
        if self.field_type.currentText() in ("keuzelijst", "meerkeuze") and not self.choice_values():
            QMessageBox.warning(self, "Opties ontbreken", "Voeg minimaal één optie toe voor deze keuzelijst.")
            return
        super().accept()


class TaxonomyDialog(FormDialog):
    def __init__(self, taxonomy=None, parent: QWidget | None = None) -> None:
        super().__init__("Taxonomie bewerken" if taxonomy else "Taxonomie toevoegen", parent)
        self.name = QLineEdit()
        self.values = QListWidget()
        self.values.setMinimumHeight(150)
        values_panel = QFrame()
        values_panel.setObjectName("panel")
        values_layout = QVBoxLayout(values_panel)
        values_layout.setContentsMargins(10, 10, 10, 10)
        values_layout.setSpacing(8)
        values_note = QLabel("Voeg de waarden toe waaruit u later per vraag kiest.")
        values_note.setWordWrap(True)
        values_layout.addWidget(values_note)
        values_layout.addWidget(self.values)
        value_buttons = QHBoxLayout()
        add_value = QPushButton("Waarde toevoegen")
        add_value.clicked.connect(self.add_value)
        delete_value = QPushButton("Waarde verwijderen")
        delete_value.clicked.connect(self.delete_value)
        value_buttons.addStretch()
        value_buttons.addWidget(delete_value)
        value_buttons.addWidget(add_value)
        values_layout.addLayout(value_buttons)
        self.form.addRow("Naam *", self.name)
        self.form.addRow("Waarden *", values_panel)
        if taxonomy:
            self.name.setText(taxonomy["name"])
            for value in taxonomy.get("values", []):
                self.values.addItem(value)

    def add_value(self) -> None:
        value, ok = QInputDialog.getText(self, "Waarde toevoegen", "Nieuwe waarde:")
        value = value.strip()
        if not ok or not value:
            return
        if value in self.value_list():
            QMessageBox.warning(self, "Waarde bestaat al", "Deze waarde staat al in de lijst.")
            return
        self.values.addItem(value)

    def delete_value(self) -> None:
        row = self.values.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen waarde geselecteerd", "Selecteer eerst een waarde om te verwijderen.")
            return
        value = self.values.item(row).text()
        choice = QMessageBox.question(self, "Waarde verwijderen", f"Weet u zeker dat u de waarde {value} wilt verwijderen?")
        if choice != QMessageBox.StandardButton.Yes:
            return
        self.values.takeItem(row)

    def value_list(self) -> list[str]:
        return [self.values.item(index).text() for index in range(self.values.count())]

    def accept(self) -> None:
        if not self.required(self.name, "een naam"):
            return
        if not self.value_list():
            QMessageBox.warning(self, "Waarden ontbreken", "Geef minimaal een waarde op.")
            return
        super().accept()


class ChoiceOptionDialog(FormDialog):
    def __init__(self, title: str, value: str = "", parent: QWidget | None = None) -> None:
        super().__init__(title, parent)
        self.value = QLineEdit(value)
        self.form.addRow("Optie *", self.value)

    def accept(self) -> None:
        if self.required(self.value, "een optie"):
            super().accept()
















class DashboardPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        self.cards: dict[str, QLabel] = {}
        layout = QVBoxLayout(self)
        title = QLabel("Overzicht")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        grid = QGridLayout()
        for index, (key, caption) in enumerate(
            [
                ("tests", "Toetsen"),
                ("classes", "Klassen/groepen"),
                ("students", "Leerlingen"),
                ("unfinished", "Toetsen zonder vragen"),
            ]
        ):
            frame = QFrame()
            frame.setObjectName("dashboardCard")
            card_layout = QVBoxLayout(frame)
            value = QLabel("0")
            value.setObjectName("cardValue")
            card_layout.addWidget(value)
            card_layout.addWidget(QLabel(caption))
            grid.addWidget(frame, index // 2, index % 2)
            self.cards[key] = value
        layout.addLayout(grid)
        self.status = QLabel()
        self.status.setObjectName("panel")
        layout.addWidget(self.status)
        layout.addStretch()
        self.refresh()

    def refresh(self) -> None:
        if not self.year_id:
            return
        params = (self.year_id,)
        self.cards["tests"].setText(str(self.database.scalar("SELECT COUNT(*) FROM tests WHERE school_year_id=?", params)))
        self.cards["classes"].setText(
            str(self.database.scalar("SELECT COUNT(*) FROM classes WHERE school_year_id=?", params))
        )
        self.cards["students"].setText(
            str(
                self.database.scalar(
                    "SELECT COUNT(DISTINCT student_id) FROM enrollments WHERE school_year_id=?", params
                )
            )
        )
        self.cards["unfinished"].setText(
            str(
                self.database.scalar(
                    "SELECT COUNT(*) FROM tests t WHERE t.school_year_id=? "
                    "AND NOT EXISTS (SELECT 1 FROM matrix_questions q WHERE q.test_id=t.id)",
                    params,
                )
            )
        )
        self.status.setText(
            f"Vakdatabase: {self.database.meta('subject_name', self.database.path.stem)}\n"
            f"Bestand: {self.database.path}"
        )

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Dashboard",
            "intro": "Dit is de startpagina van het geopende vak. U ziet hier in een oogopslag wat er al is ingevoerd in het gekozen schooljaar.",
            "steps": [
                {
                    "title": "Het juiste schooljaar controleren",
                    "text": "Bovenin staat het schooljaar waarvan u de gegevens bekijkt. Klassen, leerlingen en toetsen worden per schooljaar weergegeven.",
                    "action": "Kies een ander schooljaar in de keuzelijst bovenin wanneer u gegevens van een ander jaar nodig heeft.",
                    "tip": "Een leerling kan in een nieuw schooljaar in een andere groep zitten en toch dezelfde leerling blijven voor analyses.",
                },
                {
                    "title": "De vier overzichtskaarten lezen",
                    "text": "De kaarten tellen uw toetsen, klassen/groepen, ingeschreven leerlingen en toetsen waar nog geen vragen voor zijn gemaakt.",
                    "action": "Ziet u een toets zonder vragen? Open dan 'Vragenoverzicht' en voeg de toetsvragen toe.",
                    "tip": "Deze kaarten zijn controles; u hoeft hier niets in te voeren.",
                },
                {
                    "title": "Een logische werkvolgorde",
                    "text": "Meestal maakt u eerst groepen en leerlingen, daarna een toets en het vragenoverzicht, vervolgens voert u resultaten in.",
                    "action": "Werk via het menu links: Klassen, Leerlingen, Toetsen, Vragenoverzicht, Resultateninvoer, Normering en Toetsanalyse.",
                    "tip": "U mag onderdelen later opnieuw openen en aanpassen.",
                },
                {
                    "title": "Veilig bewaren",
                    "text": "Onderin staat welk vakbestand actief is. De knop 'Back-up maken' bovenin maakt een reservekopie van uw database.",
                    "action": "Maak in ieder geval een back-up na grotere invoeracties of voordat u veel gegevens wijzigt.",
                    "tip": "Een back-up helpt wanneer u per ongeluk een verkeerde wijziging heeft opgeslagen.",
                },
            ],
        }


class ClassesPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        add = set_button_role(QPushButton("Klas toevoegen"), "primary")
        add.clicked.connect(self.add_class)
        edit = set_button_role(QPushButton("Bewerken"), "secondary")
        edit.clicked.connect(self.edit_class)
        delete = set_button_role(QPushButton("Verwijderen"), "danger")
        delete.clicked.connect(self.delete_class)
        layout.addWidget(
            make_page_header(
                "Klassen en groepen",
                "Beheer lesgroepen, clusters en jaargroepen voor het gekozen schooljaar.",
                [delete, edit, add],
            )
        )
        self.empty_state = make_empty_state(
            "Nog geen groepen in dit schooljaar",
            "Maak eerst een klas, cluster of lesgroep. Daarna kunt u leerlingen aan deze groep koppelen.",
        )
        layout.addWidget(self.empty_state)
        self.table = QTableWidget()
        configure_table(self.table, ["Naam", "Niveau", "Leerjaar", "Leerlingen"])
        self.table.cellDoubleClicked.connect(lambda row, column: self.edit_class(row))
        layout.addWidget(self.table)
        self.refresh()

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Klassen en Groepen",
            "intro": "In dit scherm maakt u de groepen waarin leerlingen voor dit vak gevolgd worden. Dat kunnen klassen zijn, maar ook clusters.",
            "steps": [
                {
                    "title": "Wat is een groep?",
                    "text": "Een groep is de verzameling leerlingen waarvoor u resultaten wilt kunnen filteren, bijvoorbeeld 'H4 natuurkunde cluster A'.",
                    "action": "Maak groepen die aansluiten bij uw lesgroepen, ook als deze anders zijn dan de administratieve klas.",
                    "tip": "Een groep hoort bij het schooljaar dat bovenin is gekozen.",
                },
                {
                    "title": "Een groep toevoegen",
                    "text": "Bij een groep vult u minimaal een naam in. Niveau en leerjaar maken later filteren eenvoudiger.",
                    "action": "Klik op 'Klas toevoegen', vul de gegevens in en kies opslaan.",
                    "tip": "Gebruik herkenbare namen, bijvoorbeeld 'H4-NA cluster 1'.",
                },
                {
                    "title": "Een bestaande groep wijzigen",
                    "text": "U kunt de naam, het niveau of het leerjaar corrigeren zonder leerlingen opnieuw toe te voegen.",
                    "action": "Selecteer de rij en klik op 'Bewerken', of dubbelklik op de rij.",
                    "tip": "Wijzigen van de groepsnaam verwijdert geen resultaten.",
                },
                {
                    "title": "Een groep verwijderen",
                    "text": "Een groep kan alleen verwijderd worden als er geen leerlingen of toetsen meer aan gekoppeld zijn.",
                    "action": "Selecteer de groep en klik op 'Verwijderen'. U krijgt eerst een bevestigingsvraag.",
                    "tip": "Kunt u niet verwijderen? Verplaats of ontkoppel eerst de gekoppelde gegevens.",
                },
            ],
        }

    def refresh(self) -> None:
        rows = self.database.rows(
            "SELECT c.id, c.name, c.level, c.grade_year, COUNT(e.id) AS student_count "
            "FROM classes c LEFT JOIN enrollments e ON e.class_id=c.id "
            "WHERE c.school_year_id=? GROUP BY c.id ORDER BY c.name",
            (self.year_id,),
        ) if self.year_id else []
        self.empty_state.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.table.setRowCount(len(rows))
        for row_number, row in enumerate(rows):
            first_cell = item(row["name"])
            first_cell.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.table.setItem(row_number, 0, first_cell)
            for column, value in enumerate((row["level"], row["grade_year"], row["student_count"]), start=1):
                self.table.setItem(row_number, column, item(value))

    def add_class(self) -> None:
        dialog = ClassDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.database.execute(
                "INSERT INTO classes(school_year_id, name, level, grade_year) VALUES(?, ?, ?, ?)",
                (self.year_id, dialog.name.text().strip(), dialog.level.currentText(), dialog.grade.currentText()),
            )
        except Exception as error:
            QMessageBox.warning(self, "Klas niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def delete_class(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen klas geselecteerd", "Selecteer eerst een klas/groep om te verwijderen.")
            return
        class_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        name = self.table.item(row, 0).text()
        student_count = self.database.scalar("SELECT COUNT(*) FROM enrollments WHERE class_id=?", (class_id,))
        test_count = self.database.scalar("SELECT COUNT(*) FROM test_classes WHERE class_id=?", (class_id,))
        if student_count or test_count:
            QMessageBox.warning(
                self,
                "Klas/groep niet verwijderd",
                f"{name} kan niet worden verwijderd omdat er nog {student_count} leerling(en) "
                f"en {test_count} toets(en) aan gekoppeld zijn.",
            )
            return
        choice = QMessageBox.question(
            self,
            "Klas/groep verwijderen",
            f"Weet u zeker dat u {name} wilt verwijderen?",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        self.database.execute("DELETE FROM classes WHERE id=?", (class_id,))
        self.refresh()
        self.changed.emit()

    def edit_class(self, row: int | None = None) -> None:
        if isinstance(row, bool):
            row = None
        row = self.table.currentRow() if row is None else row
        if row < 0:
            QMessageBox.information(self, "Geen klas geselecteerd", "Selecteer eerst een klas om te bewerken.")
            return
        class_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        classroom = self.database.rows(
            "SELECT id, name, level, grade_year FROM classes WHERE id=? AND school_year_id=?",
            (class_id, self.year_id),
        )[0]
        dialog = ClassDialog(classroom, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.database.execute(
                "UPDATE classes SET name=?, level=?, grade_year=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (dialog.name.text().strip(), dialog.level.currentText(), dialog.grade.currentText(), class_id),
            )
        except Exception as error:
            QMessageBox.warning(self, "Klas niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()


class StudentsPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        add = set_button_role(QPushButton("Leerling toevoegen"), "primary")
        add.clicked.connect(self.add_student)
        import_button = set_button_role(QPushButton("Importeren uit Excel"), "secondary")
        import_button.clicked.connect(self.import_from_excel)
        edit = set_button_role(QPushButton("Bewerken"), "secondary")
        edit.clicked.connect(self.edit_student)
        delete = set_button_role(QPushButton("Verwijderen"), "danger")
        delete.clicked.connect(self.delete_student)
        self.add_attribute_button = set_button_role(QPushButton("Eigenschap toevoegen"), "secondary")
        self.add_attribute_button.clicked.connect(self.add_attribute)
        self.edit_attribute_button = set_button_role(QPushButton("Eigenschap bewerken"), "secondary")
        self.edit_attribute_button.clicked.connect(self.edit_attribute)
        self.delete_attribute_button = set_button_role(QPushButton("Eigenschap verwijderen"), "danger")
        self.delete_attribute_button.clicked.connect(self.delete_attribute)
        layout.addWidget(
            make_page_header(
                "Leerlingen",
                "Beheer leerlingen per groep en schooljaar. Filters veranderen alleen de weergave.",
                [delete, edit, import_button, add],
            )
        )
        self.class_filter = QComboBox()
        self.class_filter.currentIndexChanged.connect(self.refresh)
        self.level_filter = QComboBox()
        self.level_filter.currentIndexChanged.connect(self.refresh)
        self.grade_filter = QComboBox()
        self.grade_filter.currentIndexChanged.connect(self.refresh)
        layout.addWidget(
            make_responsive_filter_card(
                "Filter en controle",
                [
                    ("Cluster/groep", self.class_filter),
                    ("Niveau", self.level_filter),
                    ("Leerjaar", self.grade_filter),
                ],
                minimum_field_width=220,
                maximum_columns=3,
            )
        )
        properties_panel = QFrame()
        properties_panel.setObjectName("filterCard")
        properties_layout = QHBoxLayout(properties_panel)
        properties_layout.setContentsMargins(12, 10, 12, 10)
        properties_layout.setSpacing(10)
        properties_text = QVBoxLayout()
        properties_text.setContentsMargins(0, 0, 0, 0)
        properties_text.setSpacing(2)
        properties_title = QLabel("<b>Leerlingeigenschappen</b>")
        self.attribute_summary = QLabel()
        self.attribute_summary.setWordWrap(True)
        self.attribute_summary.setObjectName("pageSubtitle")
        properties_text.addWidget(properties_title)
        properties_text.addWidget(self.attribute_summary)
        properties_layout.addLayout(properties_text, 1)
        properties_layout.addWidget(self.delete_attribute_button)
        properties_layout.addWidget(self.edit_attribute_button)
        properties_layout.addWidget(self.add_attribute_button)
        layout.addWidget(properties_panel)
        self.empty_state = make_empty_state(
            "Geen leerlingen zichtbaar",
            "Er zijn geen leerlingen voor deze selectie. Kies andere filters of voeg leerlingen toe/importeer ze uit Excel.",
        )
        layout.addWidget(self.empty_state)
        self.table = QTableWidget()
        self.table.cellDoubleClicked.connect(lambda row, column: self.edit_student(row))
        layout.addWidget(self.table)
        self.reload_filters()
        self.refresh()

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Leerlingen",
            "intro": "Hier koppelt u leerlingen aan een groep in het gekozen schooljaar. Dezelfde leerling kan in een volgend jaar in een andere groep terechtkomen.",
            "steps": [
                {
                    "title": "Handmatig een leerling toevoegen",
                    "text": "Een leerling heeft minimaal een weergavenaam en een groep nodig. Een leerlingnummer maakt herkenning bij import en latere schooljaren betrouwbaarder.",
                    "action": "Klik op 'Leerling toevoegen', kies de juiste groep en sla de leerling op.",
                    "tip": "Vul waar mogelijk het leerlingnummer in; daarmee wordt een bestaande leerling beter herkend.",
                },
                {
                    "title": "Leerlingen importeren uit Magister",
                    "text": "De Excel-import leest leerlingnamen en leerlingnummers uit het Magister-formaat. U bepaalt zelf in welke cluster/groep de leerlingen komen.",
                    "action": "Klik op 'Importeren uit Excel', kies de doelgroep en selecteer het Excelbestand.",
                    "tip": "De rij 'Totaal' wordt niet als leerling geïmporteerd. Controleer na import het aantal leerlingen.",
                },
                {
                    "title": "Bestaande leerlingen over jaren",
                    "text": "Een leerling die opnieuw wordt toegevoegd kan aan een andere groep worden gekoppeld, terwijl historische gegevens bruikbaar blijven.",
                    "action": "Gebruik steeds hetzelfde leerlingnummer bij import of handmatige invoer.",
                    "tip": "De groep is per schooljaar; de leerlingidentiteit loopt over de jaren door.",
                },
                {
                    "title": "Filteren en controleren",
                    "text": "De filters tonen alleen leerlingen uit een gekozen groep, niveau of leerjaar.",
                    "action": "Kies filters boven de tabel om te controleren of elke groep compleet is.",
                    "tip": "Filters verwijderen geen gegevens; kies 'Alle groepen' om alles weer te zien.",
                },
                {
                    "title": "Bewerken, verwijderen en eigen velden",
                    "text": "Met 'Bewerken' wijzigt u leerlinggegevens of de groep. Met 'Eigenschap toevoegen' maakt u extra velden zoals profiel of extra tijd.",
                    "action": "Selecteer eerst een leerling voor bewerken of verwijderen. Bij verwijderen bevestigt u altijd expliciet.",
                    "tip": "Verwijderen uit dit schooljaar laat historische koppelingen uit andere jaren intact.",
                },
            ],
        }

    def set_year(self, year_id: int | None) -> None:
        self.year_id = year_id
        self.reload_filters()
        self.refresh()

    def attributes(self) -> list:
        return self.database.rows("SELECT id, name, field_type, options_json FROM student_attributes ORDER BY name")

    def update_attribute_summary(self, attributes: list | None = None) -> None:
        attributes = self.attributes() if attributes is None else attributes
        if not hasattr(self, "attribute_summary"):
            return
        if not attributes:
            self.attribute_summary.setText("Nog geen extra eigenschappen. Voeg bijvoorbeeld profiel, mentor of extra tijd toe.")
            return
        names = ", ".join(attribute["name"] for attribute in attributes[:5])
        suffix = "" if len(attributes) <= 5 else f" + {len(attributes) - 5} meer"
        self.attribute_summary.setText(f"{len(attributes)} extra eigenschap(pen): {names}{suffix}.")

    def reload_filters(self) -> None:
        current_class = self.class_filter.currentData() if hasattr(self, "class_filter") else None
        current_level = self.level_filter.currentData() if hasattr(self, "level_filter") else None
        current_grade = self.grade_filter.currentData() if hasattr(self, "grade_filter") else None
        for combo in (self.class_filter, self.level_filter, self.grade_filter):
            combo.blockSignals(True)
            combo.clear()
        self.class_filter.addItem("Alle groepen", None)
        for classroom in self.database.rows(
            "SELECT id, name FROM classes WHERE school_year_id=? ORDER BY name", (self.year_id,)
        ) if self.year_id else []:
            self.class_filter.addItem(classroom["name"], classroom["id"])
        self.level_filter.addItem("Alle niveaus", None)
        self.grade_filter.addItem("Alle leerjaren", None)
        for level in self.database.rows(
            "SELECT DISTINCT level FROM classes WHERE school_year_id=? AND level<>'' ORDER BY level", (self.year_id,)
        ) if self.year_id else []:
            self.level_filter.addItem(level["level"], level["level"])
        for grade in self.database.rows(
            "SELECT DISTINCT grade_year FROM classes WHERE school_year_id=? AND grade_year<>'' ORDER BY grade_year",
            (self.year_id,),
        ) if self.year_id else []:
            self.grade_filter.addItem(grade["grade_year"], grade["grade_year"])
        for combo, value in (
            (self.class_filter, current_class),
            (self.level_filter, current_level),
            (self.grade_filter, current_grade),
        ):
            index = combo.findData(value)
            combo.setCurrentIndex(index if index >= 0 else 0)
            combo.blockSignals(False)

    def refresh(self) -> None:
        attributes = self.attributes()
        self.update_attribute_summary(attributes)
        headers = ["Weergavenaam", "Leerlingnummer", "Klas/groep", "Niveau", "Leerjaar"]
        headers.extend(attribute["name"] for attribute in attributes)
        configure_table(self.table, headers)
        conditions = ["e.school_year_id=?"]
        parameters: list[object] = [self.year_id]
        if self.class_filter.currentData() is not None:
            conditions.append("c.id=?")
            parameters.append(self.class_filter.currentData())
        if self.level_filter.currentData() is not None:
            conditions.append("c.level=?")
            parameters.append(self.level_filter.currentData())
        if self.grade_filter.currentData() is not None:
            conditions.append("c.grade_year=?")
            parameters.append(self.grade_filter.currentData())
        rows = self.database.rows(
            "SELECT s.id, e.id AS enrollment_id, s.display_name, s.student_number, "
            "COALESCE(s.first_name, '') AS first_name, COALESCE(s.last_name, '') AS last_name, c.name, "
            "COALESCE(c.level, s.level) AS effective_level, "
            "COALESCE(c.grade_year, s.grade_year) AS effective_grade_year FROM students s "
            "JOIN enrollments e ON e.student_id=s.id "
            "LEFT JOIN classes c ON c.id=e.class_id WHERE " + " AND ".join(conditions) + " ORDER BY s.display_name",
            parameters,
        ) if self.year_id else []
        rows = sorted(rows, key=lambda row: student_sort_key(row["display_name"], row["first_name"], row["last_name"]))
        self.empty_state.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.table.setRowCount(len(rows))
        for row_number, row in enumerate(rows):
            first_cell = item(row["display_name"])
            first_cell.setData(Qt.ItemDataRole.UserRole, row["id"])
            first_cell.setData(int(Qt.ItemDataRole.UserRole) + 1, row["enrollment_id"])
            self.table.setItem(row_number, 0, first_cell)
            for column, value in enumerate(
                (row["student_number"], row["name"], row["effective_level"], row["effective_grade_year"]),
                start=1,
            ):
                self.table.setItem(row_number, column, item(value))
            values = {
                value["attribute_id"]: value["value"]
                for value in self.database.rows(
                    "SELECT attribute_id, value FROM student_attribute_values WHERE student_id=?", (row["id"],)
                )
            }
            for column, attribute in enumerate(attributes, start=5):
                self.table.setItem(row_number, column, item(values.get(attribute["id"], "")))

    def add_student(self) -> None:
        classes = self.database.rows("SELECT id, name FROM classes WHERE school_year_id=? ORDER BY name", (self.year_id,))
        attributes = self.attributes()
        dialog = StudentDialog(classes, attributes, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        class_id = dialog.student_class.currentData()
        if class_id is None:
            QMessageBox.information(self, "Klas nodig", "Maak eerst een klas of kies een bestaande klas.")
            return
        try:
            cursor = self.database.connection.execute(
                "INSERT INTO students(display_name, student_number, first_name, last_name) VALUES(?, ?, ?, ?)",
                (
                    dialog.display_name.text().strip(),
                    dialog.student_number.text().strip(),
                    dialog.first_name.text().strip(),
                    dialog.last_name.text().strip(),
                ),
            )
            student_id = cursor.lastrowid
            self.database.connection.execute(
                "INSERT INTO enrollments(student_id, class_id, school_year_id) VALUES(?, ?, ?)",
                (student_id, class_id, self.year_id),
            )
            for attribute in attributes:
                value = dialog.attribute_value(attribute["id"])
                if value:
                    self.database.connection.execute(
                        "INSERT INTO student_attribute_values(student_id, attribute_id, value) VALUES(?, ?, ?)",
                        (student_id, attribute["id"], value),
                    )
            self.database.connection.commit()
        except sqlite3.IntegrityError as error:
            self.database.connection.rollback()
            QMessageBox.warning(
                self,
                "Leerling niet opgeslagen",
                "Dit leerlingnummer is al gekoppeld aan een bestaande leerling. "
                "Bewerk de bestaande leerling of gebruik een ander leerlingnummer.",
            )
            return
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Leerling niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def edit_student(self, row: int | None = None) -> None:
        if isinstance(row, bool):
            row = None
        row = self.table.currentRow() if row is None else row
        if row < 0:
            QMessageBox.information(self, "Geen leerling geselecteerd", "Selecteer eerst een leerling om te bewerken.")
            return
        student_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        enrollment_id = self.table.item(row, 0).data(int(Qt.ItemDataRole.UserRole) + 1)
        students = self.database.rows(
            "SELECT s.id, s.display_name, s.student_number, s.first_name, s.last_name, e.class_id "
            "FROM students s JOIN enrollments e ON e.student_id=s.id "
            "WHERE s.id=? AND e.id=? AND e.school_year_id=?",
            (student_id, enrollment_id, self.year_id),
        )
        if not students:
            QMessageBox.warning(self, "Leerling niet gevonden", "De geselecteerde leerling bestaat niet meer.")
            self.refresh()
            return
        classes = self.database.rows("SELECT id, name FROM classes WHERE school_year_id=? ORDER BY name", (self.year_id,))
        attributes = self.attributes()
        attribute_values = {
            row["attribute_id"]: row["value"]
            for row in self.database.rows(
                "SELECT attribute_id, value FROM student_attribute_values WHERE student_id=?", (student_id,)
            )
        }
        dialog = StudentDialog(classes, attributes, students[0], attribute_values, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        class_id = dialog.student_class.currentData()
        if class_id is None:
            QMessageBox.information(self, "Klas nodig", "Kies een klas voor deze leerling.")
            return
        try:
            self.database.connection.execute(
                "UPDATE students SET display_name=?, student_number=?, first_name=?, last_name=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    dialog.display_name.text().strip(),
                    dialog.student_number.text().strip(),
                    dialog.first_name.text().strip(),
                    dialog.last_name.text().strip(),
                    student_id,
                ),
            )
            self.database.connection.execute(
                "UPDATE enrollments SET class_id=? WHERE id=? AND school_year_id=?",
                (class_id, enrollment_id, self.year_id),
            )
            for attribute in attributes:
                value = dialog.attribute_value(attribute["id"])
                self.database.connection.execute(
                    "INSERT INTO student_attribute_values(student_id, attribute_id, value) VALUES(?, ?, ?) "
                    "ON CONFLICT(student_id, attribute_id) DO UPDATE SET value=excluded.value",
                    (student_id, attribute["id"], value),
                )
            self.database.connection.commit()
        except sqlite3.IntegrityError:
            self.database.connection.rollback()
            QMessageBox.warning(
                self,
                "Leerling niet opgeslagen",
                "Dit leerlingnummer is al gekoppeld aan een bestaande leerling. "
                "Bewerk de bestaande leerling of gebruik een ander leerlingnummer.",
            )
            return
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Leerling niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def delete_student(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen leerling geselecteerd", "Selecteer eerst een leerling om te verwijderen.")
            return
        student_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        enrollment_id = self.table.item(row, 0).data(int(Qt.ItemDataRole.UserRole) + 1)
        name = self.table.item(row, 0).text()
        choice = QMessageBox.question(
            self,
            "Leerling verwijderen",
            f"Weet u zeker dat u {name} uit dit schooljaar wilt verwijderen?\n\n"
            "Historische gegevens uit andere schooljaren blijven bewaard.",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        self.database.connection.execute("DELETE FROM enrollments WHERE id=?", (enrollment_id,))
        remaining_enrollments = self.database.scalar(
            "SELECT COUNT(*) FROM enrollments WHERE student_id=?", (student_id,)
        )
        attempts = self.database.scalar("SELECT COUNT(*) FROM test_attempts WHERE student_id=?", (student_id,))
        if remaining_enrollments == 0 and attempts == 0:
            self.database.connection.execute("DELETE FROM students WHERE id=?", (student_id,))
        self.database.connection.commit()
        self.refresh()
        self.changed.emit()

    def add_attribute(self) -> None:
        dialog = StudentAttributeDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        choices = dialog.choice_values() if dialog.field_type.currentText() == "keuzelijst" else []
        choices_json = json.dumps(choices) if choices else None
        try:
            self.database.execute(
                "INSERT INTO student_attributes(name, field_type, options_json) VALUES(?, ?, ?)",
                (dialog.name.text().strip(), dialog.field_type.currentText(), choices_json),
            )
        except Exception as error:
            QMessageBox.warning(self, "Eigenschap niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def select_attribute(self, title: str) -> sqlite3.Row | None:
        attributes = self.attributes()
        if not attributes:
            QMessageBox.information(self, "Geen eigenschappen", "Er zijn nog geen extra eigenschappen.")
            return None
        names = [attribute["name"] for attribute in attributes]
        name, accepted = QInputDialog.getItem(self, title, "Kies eigenschap:", names, 0, False)
        if not accepted or not name:
            return None
        return next((attribute for attribute in attributes if attribute["name"] == name), None)

    def edit_attribute(self) -> None:
        selected = self.select_attribute("Eigenschap bewerken")
        if not selected:
            return
        dialog = StudentAttributeDialog(selected, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        old_choices = json.loads(selected["options_json"]) if selected["options_json"] else []
        new_choices = dialog.choice_values() if dialog.field_type.currentText() == "keuzelijst" else []
        removed_choices = [choice for choice in old_choices if choice not in new_choices]
        if removed_choices:
            placeholders = ",".join("?" for _ in removed_choices)
            used = self.database.scalar(
                "SELECT COUNT(*) FROM student_attribute_values WHERE attribute_id=? "
                "AND value IN (" + placeholders + ")",
                (selected["id"], *removed_choices),
            )
            if used:
                QMessageBox.warning(
                    self,
                    "Optie niet verwijderd",
                    "Een of meer verwijderde opties worden al gebruikt bij leerlingen. "
                    "Wijzig die leerlingwaarden eerst of laat de optie bestaan.",
                )
                return
        choices_json = json.dumps(new_choices) if new_choices else None
        try:
            self.database.execute(
                "UPDATE student_attributes SET name=?, field_type=?, options_json=? WHERE id=?",
                (
                    dialog.name.text().strip(),
                    dialog.field_type.currentText(),
                    choices_json,
                    selected["id"],
                ),
            )
        except Exception as error:
            QMessageBox.warning(self, "Eigenschap niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def delete_attribute(self) -> None:
        selected = self.select_attribute("Eigenschap verwijderen")
        if not selected:
            return
        name = selected["name"]
        value_count = int(
            self.database.scalar(
                "SELECT COUNT(*) FROM student_attribute_values WHERE attribute_id=?", (selected["id"],)
            )
            or 0
        )
        choice = QMessageBox.question(
            self,
            "Eigenschap verwijderen",
            f"Weet u zeker dat u de leerlingeigenschap '{name}' wilt verwijderen?\n\n"
            f"Ook {value_count} ingevulde waarde(n) voor deze eigenschap worden definitief verwijderd.",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.execute("DELETE FROM student_attributes WHERE id=?", (selected["id"],))
        except Exception as error:
            QMessageBox.warning(self, "Eigenschap niet verwijderd", str(error))
            return
        self.refresh()
        self.changed.emit()

    def import_from_excel(self) -> None:
        classes = self.database.rows("SELECT id, name FROM classes WHERE school_year_id=? ORDER BY name", (self.year_id,))
        if not classes:
            QMessageBox.information(
                self, "Groep nodig", "Maak eerst de cluster/groep aan waarin deze leerlingen geplaatst worden."
            )
            return
        dialog = StudentImportDialog(classes, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            students, skipped = read_magister_students(Path(dialog.file_path.text()))
            result = import_students(
                self.database,
                self.year_id,
                dialog.student_class.currentData(),
                students,
                skipped,
            )
        except StudentImportError as error:
            QMessageBox.warning(self, "Importeren niet gelukt", str(error))
            return
        except Exception as error:
            QMessageBox.warning(self, "Importeren niet gelukt", f"De leerlingen konden niet worden opgeslagen: {error}")
            return
        self.reload_filters()
        self.refresh()
        self.changed.emit()
        QMessageBox.information(
            self,
            "Import afgerond",
            f"{result.added} leerlingen toegevoegd.\n"
            f"{result.updated} bestaande leerlingen bijgewerkt.\n"
            f"{result.skipped} rijen overgeslagen.",
        )


class TestsPage(Page):
    open_test_page = Signal(str, int)

    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        add = compact_action_button(
            set_button_role(QPushButton("Nieuwe toets"), "primary"),
            "Maak een nieuwe toets aan.",
            135,
        )
        add.clicked.connect(self.add_test)
        edit = compact_action_button(
            set_button_role(QPushButton("Bewerken"), "secondary"),
            "Bewerk de geselecteerde toets.",
            115,
        )
        edit.clicked.connect(self.edit_test)
        delete = compact_action_button(
            set_button_role(QPushButton("Verwijderen"), "danger"),
            "Verwijder de geselecteerde toets.",
            125,
        )
        delete.clicked.connect(self.delete_test)
        to_results = compact_action_button(
            set_button_role(QPushButton("Naar resultateninvoer"), "secondary"),
            "Open resultateninvoer voor de geselecteerde toets.",
            180,
        )
        to_results.clicked.connect(lambda: self.open_selected_test_page("Resultateninvoer"))
        to_norming = compact_action_button(
            set_button_role(QPushButton("Naar normeren"), "secondary"),
            "Open normering voor de geselecteerde toets.",
            145,
        )
        to_norming.clicked.connect(lambda: self.open_selected_test_page("Normering"))
        to_analysis = compact_action_button(
            set_button_role(QPushButton("Naar analyse"), "secondary"),
            "Open toetsanalyse voor de geselecteerde toets.",
            130,
        )
        to_analysis.clicked.connect(lambda: self.open_selected_test_page("Toetsanalyse"))
        layout.addWidget(
            make_page_header(
                "Toetsen",
                "Maak toetsen aan, koppel groepen en kies welke taxonomieën en vraagclassificaties u gebruikt.",
            )
        )
        action_panel = QFrame()
        action_panel.setObjectName("filterCard")
        action_layout = QGridLayout(action_panel)
        action_layout.setContentsMargins(14, 10, 14, 10)
        action_layout.setHorizontalSpacing(10)
        action_layout.setVerticalSpacing(10)
        action_layout.setColumnMinimumWidth(0, 300)
        action_layout.setColumnStretch(4, 1)
        row_height = add.height()
        manage_label = QLabel("<b>Toets beheren</b>")
        manage_label.setFixedSize(300, row_height)
        manage_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        continue_label = QLabel("<b>Doorgaan met geselecteerde toets</b>")
        continue_label.setFixedSize(300, row_height)
        continue_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        action_layout.setRowMinimumHeight(0, row_height)
        action_layout.setRowMinimumHeight(1, row_height)
        row_alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        action_layout.addWidget(manage_label, 0, 0, row_alignment)
        action_layout.addWidget(add, 0, 1, row_alignment)
        action_layout.addWidget(edit, 0, 2, row_alignment)
        action_layout.addWidget(delete, 0, 3, row_alignment)
        action_layout.addWidget(continue_label, 1, 0, row_alignment)
        action_layout.addWidget(to_results, 1, 1, row_alignment)
        action_layout.addWidget(to_norming, 1, 2, row_alignment)
        action_layout.addWidget(to_analysis, 1, 3, row_alignment)
        layout.addWidget(action_panel)
        self.empty_state = make_empty_state(
            "Nog geen toetsen in dit schooljaar",
            "Maak eerst een toets. Daarna kunt u het vragenoverzicht, resultateninvoer en analyses gebruiken.",
        )
        layout.addWidget(self.empty_state)
        self.table = QTableWidget()
        configure_table(
            self.table,
            ["Naam", "Periode", "Soort", "Herkansing van", "Niveau", "Jaarlaag", "Weging", "Vragen", "Punten"],
        )
        self.table.cellDoubleClicked.connect(lambda row, column: self.edit_test(row))
        layout.addWidget(self.table)
        self.refresh()

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Toetsen",
            "intro": "Dit scherm bevat de basisgegevens van elke toets. Vragen en scores worden daarna in de volgende schermen toegevoegd.",
            "steps": [
                {
                    "title": "Een toets aanmaken",
                    "text": "Geef de toets een duidelijke naam, periode en toetssoort. Niveau en jaarlaag helpen om toetsen later snel terug te vinden.",
                    "action": "Klik op 'Nieuwe toets' en vul eerst de algemene velden in.",
                    "tip": "De periode bevat ook Toetsweek 1, 2 en 3.",
                },
                {
                    "title": "Groepen koppelen",
                    "text": "Een toets kan voor een of meerdere groepen gelden. Alleen gekoppelde leerlingen kunnen later scores krijgen.",
                    "action": "Vink bij het aanmaken alle groepen aan die deze toets maken.",
                    "tip": "Mist later een leerling in resultateninvoer? Controleer eerst deze groepskoppeling.",
                },
                {
                    "title": "Taxonomieën en extra velden kiezen",
                    "text": "Een taxonomie is een indeling van vragen, bijvoorbeeld RTTI. Extra velden zijn bijvoorbeeld vraagtype of hoofdstuk.",
                    "action": "Kies minimaal één taxonomie en vink alleen extra velden aan die u bij de vragen wilt invullen.",
                    "tip": "Bij een keuzelijst verschijnen de mogelijke opties pas nadat u die classificatie aanvinkt.",
                },
                {
                    "title": "Herkansing en weging",
                    "text": "Bij een herkansing verschijnt het veld 'Herkansing van', zodat de nieuwe toets met de oorspronkelijke toets verbonden is. Weging bewaart het relatieve belang van de toets.",
                    "action": "Kies toetssoort 'Herkansing' en selecteer vervolgens de oorspronkelijke toets.",
                    "tip": "Een herkansing krijgt een eigen vragenoverzicht en eigen resultaten.",
                },
                {
                    "title": "Wijzigen of verwijderen",
                    "text": "U kunt een bestaande toets selecteren om gegevens aan te passen. Verwijderen wist ook de gekoppelde toetsgegevens.",
                    "action": "Selecteer de toets in de tabel en gebruik 'Bewerken' of 'Verwijderen'.",
                    "tip": "Bij verwijderen wordt altijd eerst om bevestiging gevraagd.",
                },
                {
                    "title": "Direct doorgaan met een toets",
                    "text": "Na het selecteren van een toets kunt u direct naar resultateninvoer, normering of toetsanalyse.",
                    "action": "Selecteer een toets en klik op 'Naar resultateninvoer', 'Naar normeren' of 'Naar analyse'.",
                    "tip": "Het doelmenu opent meteen met dezelfde toets geselecteerd.",
                },
            ],
            "faq": [
                {
                    "question": "Waarom moet ik eerst een toets selecteren?",
                    "answer": "De vervolgknoppen moeten weten met welke toets u verder wilt. Klik daarom eerst op een rij in de toetsentabel.",
                },
                {
                    "question": "Wat is het verschil tussen de drie vervolgknoppen?",
                    "answer": "Naar resultateninvoer opent score-invoer, Naar normeren opent cijferomzetting en Naar analyse opent de toetsanalyse voor dezelfde toets.",
                },
            ],
        }

    def selected_test_id(self, action: str) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen toets geselecteerd", f"Selecteer eerst een toets om {action}.")
            return None
        cell = self.table.item(row, 0)
        if cell is None:
            QMessageBox.information(self, "Geen toets geselecteerd", f"Selecteer eerst een toets om {action}.")
            return None
        return int(cell.data(Qt.ItemDataRole.UserRole))

    def open_selected_test_page(self, page_label: str) -> None:
        test_id = self.selected_test_id("door te gaan")
        if test_id is None:
            return
        self.open_test_page.emit(page_label, test_id)

    def refresh(self) -> None:
        rows = self.database.rows(
            "SELECT t.id, t.name, t.period, t.test_type, original.name AS original_name, t.level, "
            "t.grade_year, t.weight, COUNT(q.id) AS question_count, "
            "COALESCE(SUM(q.maximum_score), 0) AS total_points FROM tests t "
            "LEFT JOIN tests original ON original.id=t.original_test_id "
            "LEFT JOIN matrix_questions q ON q.test_id=t.id WHERE t.school_year_id=? "
            "GROUP BY t.id ORDER BY t.created_at DESC",
            (self.year_id,),
        ) if self.year_id else []
        self.empty_state.setVisible(not rows)
        self.table.setVisible(bool(rows))
        self.table.setRowCount(len(rows))
        for row_number, row in enumerate(rows):
            first_cell = item(row["name"])
            first_cell.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.table.setItem(row_number, 0, first_cell)
            for column, value in enumerate(
                (
                    row["period"],
                    row["test_type"],
                    row["original_name"],
                    row["level"],
                    row["grade_year"],
                    f"{row['weight']:g}".replace(".", ","),
                    row["question_count"],
                    row["total_points"],
                ),
                start=1,
            ):
                self.table.setItem(row_number, column, item(value))

    def add_test(self) -> None:
        classes = self.database.rows("SELECT id, name FROM classes WHERE school_year_id=? ORDER BY name", (self.year_id,))
        students = [
            dict(row)
            for row in self.database.rows(
                "SELECT s.id, s.display_name, COALESCE(s.student_number, '') AS student_number, "
                "COALESCE(s.first_name, '') AS first_name, COALESCE(s.last_name, '') AS last_name "
                "FROM students s ORDER BY s.display_name",
            )
        ]
        students.sort(key=lambda student: student_sort_key(student["display_name"], student["first_name"], student["last_name"]))
        originals = self.database.rows(
            "SELECT id, name FROM tests WHERE school_year_id=? AND is_resit=0 ORDER BY created_at DESC",
            (self.year_id,),
        )
        taxonomies = self.database.rows("SELECT id, name FROM taxonomy_definitions ORDER BY id")
        properties = self.database.rows(
            "SELECT id, name, choices_json FROM property_definitions WHERE is_active=1 ORDER BY id"
        )
        dialog = TestDialog(classes, originals, taxonomies, properties, students=students, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        minutes = dialog.minutes.value() or None
        cursor = self.database.connection.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year, test_date, "
            "available_time_minutes, weight, is_resit, original_test_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.year_id,
                dialog.name.text().strip(),
                dialog.period.currentText(),
                dialog.test_type.currentText(),
                dialog.level.currentText(),
                dialog.grade.currentText(),
                dialog.test_date.date().toString("yyyy-MM-dd"),
                minutes,
                dialog.weight.value(),
                int(dialog.test_type.currentText() == "Herkansing"),
                dialog.original_test.currentData() if dialog.test_type.currentText() == "Herkansing" else None,
            ),
        )
        test_id = cursor.lastrowid
        for class_id in dialog.checked_class_ids():
            self.database.connection.execute(
                "INSERT INTO test_classes(test_id, class_id) VALUES(?, ?)",
                (test_id, class_id),
            )
        selected_class_ids = set(dialog.checked_class_ids())
        for student_id in dialog.checked_extra_student_ids():
            linked_to_selected_class = self.database.scalar(
                "SELECT COUNT(*) FROM enrollments WHERE student_id=? AND school_year_id=? "
                f"AND class_id IN ({','.join('?' for _ in selected_class_ids)})" if selected_class_ids else "SELECT 0",
                (student_id, self.year_id, *selected_class_ids) if selected_class_ids else (),
            )
            if not linked_to_selected_class:
                self.database.connection.execute(
                    "INSERT OR IGNORE INTO test_students(test_id, student_id) VALUES(?, ?)",
                    (test_id, student_id),
                )
        for taxonomy_id in dialog.checked_taxonomy_ids():
            self.database.connection.execute(
                "INSERT INTO test_taxonomy_selections(test_id, taxonomy_id) VALUES(?, ?)", (test_id, taxonomy_id)
            )
        for property_id in dialog.checked_property_ids():
            self.database.connection.execute(
                "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)", (test_id, property_id)
            )
        checked_property_ids = set(dialog.checked_property_ids())
        for property_id, values in dialog.checked_property_options().items():
            if property_id in checked_property_ids:
                for value in values:
                    self.database.connection.execute(
                        "INSERT INTO test_property_option_selections(test_id, property_id, value) VALUES(?, ?, ?)",
                        (test_id, property_id, value),
                    )
        self.database.connection.commit()
        self.refresh()
        self.changed.emit()

    def selected_property_options_for_test(self, test_id: int) -> dict[int, list[str]]:
        selections: dict[int, list[str]] = defaultdict(list)
        for row in self.database.rows(
            "SELECT property_id, value FROM test_property_option_selections "
            "WHERE test_id=? ORDER BY property_id, rowid",
            (test_id,),
        ):
            selections[int(row["property_id"])].append(row["value"])
        return dict(selections)

    def edit_test(self, row: int | None = None) -> None:
        if isinstance(row, bool):
            row = None
        row = self.table.currentRow() if row is None else row
        if row < 0:
            QMessageBox.information(self, "Geen toets geselecteerd", "Selecteer eerst een toets om te bewerken.")
            return
        test_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        tests = self.database.rows(
            "SELECT id, name, period, test_type, level, grade_year, test_date, available_time_minutes, "
            "weight, original_test_id "
            "FROM tests WHERE id=? AND school_year_id=?",
            (test_id, self.year_id),
        )
        if not tests:
            QMessageBox.warning(self, "Toets niet gevonden", "De geselecteerde toets bestaat niet meer.")
            self.refresh()
            return
        classes = self.database.rows("SELECT id, name FROM classes WHERE school_year_id=? ORDER BY name", (self.year_id,))
        students = [
            dict(row)
            for row in self.database.rows(
                "SELECT s.id, s.display_name, COALESCE(s.student_number, '') AS student_number, "
                "COALESCE(s.first_name, '') AS first_name, COALESCE(s.last_name, '') AS last_name "
                "FROM students s ORDER BY s.display_name",
            )
        ]
        students.sort(key=lambda student: student_sort_key(student["display_name"], student["first_name"], student["last_name"]))
        originals = self.database.rows(
            "SELECT id, name FROM tests WHERE school_year_id=? AND id<>? AND is_resit=0 ORDER BY created_at DESC",
            (self.year_id, test_id),
        )
        selected_class_ids = [
            row["class_id"] for row in self.database.rows("SELECT class_id FROM test_classes WHERE test_id=?", (test_id,))
        ]
        selected_extra_student_ids = [
            row["student_id"] for row in self.database.rows("SELECT student_id FROM test_students WHERE test_id=?", (test_id,))
        ]
        taxonomies = self.database.rows("SELECT id, name FROM taxonomy_definitions ORDER BY id")
        properties = self.database.rows(
            "SELECT id, name, choices_json FROM property_definitions WHERE is_active=1 ORDER BY id"
        )
        selected_taxonomy_ids = [
            row["taxonomy_id"]
            for row in self.database.rows("SELECT taxonomy_id FROM test_taxonomy_selections WHERE test_id=?", (test_id,))
        ]
        selected_property_ids = [
            row["property_id"]
            for row in self.database.rows("SELECT property_id FROM test_property_selections WHERE test_id=?", (test_id,))
        ]
        selected_property_options = self.selected_property_options_for_test(test_id)
        dialog = TestDialog(
            classes,
            originals,
            taxonomies,
            properties,
            tests[0],
            selected_class_ids,
            selected_taxonomy_ids,
            selected_property_ids,
            selected_property_options,
            students=students,
            selected_extra_student_ids=selected_extra_student_ids,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.database.connection.execute(
                "UPDATE tests SET name=?, period=?, test_type=?, level=?, grade_year=?, test_date=?, "
                "available_time_minutes=?, weight=?, is_resit=?, original_test_id=?, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    dialog.name.text().strip(),
                    dialog.period.currentText(),
                    dialog.test_type.currentText(),
                    dialog.level.currentText(),
                    dialog.grade.currentText(),
                    dialog.test_date.date().toString("yyyy-MM-dd"),
                    dialog.minutes.value() or None,
                    dialog.weight.value(),
                    int(dialog.test_type.currentText() == "Herkansing"),
                    dialog.original_test.currentData() if dialog.test_type.currentText() == "Herkansing" else None,
                    test_id,
                ),
            )
            self.database.connection.execute("DELETE FROM test_classes WHERE test_id=?", (test_id,))
            for class_id in dialog.checked_class_ids():
                self.database.connection.execute(
                    "INSERT INTO test_classes(test_id, class_id) VALUES(?, ?)",
                    (test_id, class_id),
                )
            self.database.connection.execute("DELETE FROM test_students WHERE test_id=?", (test_id,))
            selected_class_ids = set(dialog.checked_class_ids())
            for student_id in dialog.checked_extra_student_ids():
                linked_to_selected_class = self.database.scalar(
                    "SELECT COUNT(*) FROM enrollments WHERE student_id=? AND school_year_id=? "
                    f"AND class_id IN ({','.join('?' for _ in selected_class_ids)})" if selected_class_ids else "SELECT 0",
                    (student_id, self.year_id, *selected_class_ids) if selected_class_ids else (),
                )
                if not linked_to_selected_class:
                    self.database.connection.execute(
                        "INSERT OR IGNORE INTO test_students(test_id, student_id) VALUES(?, ?)",
                        (test_id, student_id),
                    )
            self.database.connection.execute("DELETE FROM test_taxonomy_selections WHERE test_id=?", (test_id,))
            for taxonomy_id in dialog.checked_taxonomy_ids():
                self.database.connection.execute(
                    "INSERT INTO test_taxonomy_selections(test_id, taxonomy_id) VALUES(?, ?)", (test_id, taxonomy_id)
                )
            self.database.connection.execute("DELETE FROM test_property_selections WHERE test_id=?", (test_id,))
            for property_id in dialog.checked_property_ids():
                self.database.connection.execute(
                    "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)", (test_id, property_id)
                )
            self.database.connection.execute("DELETE FROM test_property_option_selections WHERE test_id=?", (test_id,))
            checked_property_ids = set(dialog.checked_property_ids())
            for property_id, values in dialog.checked_property_options().items():
                if property_id in checked_property_ids:
                    for value in values:
                        self.database.connection.execute(
                            "INSERT INTO test_property_option_selections(test_id, property_id, value) VALUES(?, ?, ?)",
                            (test_id, property_id, value),
                        )
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Toets niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def delete_test(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Geen toets geselecteerd", "Selecteer eerst een toets om te verwijderen.")
            return
        test_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        name = self.table.item(row, 0).text()
        resits = self.database.scalar("SELECT COUNT(*) FROM tests WHERE original_test_id=?", (test_id,))
        if resits:
            QMessageBox.warning(
                self,
                "Toets niet verwijderd",
                "Deze toets heeft een gekoppelde herkansing. Verwijder of wijzig eerst die koppeling.",
            )
            return
        choice = QMessageBox.question(
            self,
            "Toets verwijderen",
            f"Weet u zeker dat u de toets {name} wilt verwijderen?\n\n"
            "Gekoppelde toetsmatrijsvragen en ingevoerde toetsgegevens worden ook verwijderd.",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.execute("DELETE FROM tests WHERE id=?", (test_id,))
        except Exception as error:
            QMessageBox.warning(self, "Toets niet verwijderd", str(error))
            return
        self.refresh()
        self.changed.emit()








class TaxonomyPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        add = set_button_role(QPushButton("Taxonomie toevoegen"), "primary")
        add.clicked.connect(self.add_taxonomy)
        edit = set_button_role(QPushButton("Taxonomie bewerken"), "secondary")
        edit.clicked.connect(self.edit_taxonomy)
        delete = set_button_role(QPushButton("Taxonomie verwijderen"), "danger")
        delete.clicked.connect(self.delete_taxonomy)
        layout.addWidget(
            make_page_header(
                "Taxonomieën",
                "Beheer denkniveaus zoals RTTI, OBIT, Bloom of een eigen taxonomie.",
                [delete, edit, add],
            )
        )
        self.table = QTableWidget()
        configure_table(self.table, ["Taxonomie", "Waarden", "Type"])
        self.table.cellDoubleClicked.connect(lambda row, column: self.edit_taxonomy(row))
        layout.addWidget(self.table)
        self.refresh()

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Taxonomieën",
            "intro": "Een taxonomie deelt vragen in naar denkniveau, bijvoorbeeld RTTI, OBIT of Bloom. Hierdoor ziet u later welk type denken leerlingen goed beheersen.",
            "steps": [
                {
                    "title": "Standaardtaxonomieën begrijpen",
                    "text": "RTTI, OBIT en Bloom zijn vooraf beschikbaar. RTTI gebruikt bijvoorbeeld R, T1, T2 en I om vragen te onderscheiden.",
                    "action": "Bekijk de aanwezige taxonomieën en kies later bij een toets welke u wilt gebruiken.",
                    "tip": "RTTI, OBIT en Bloom zijn vergrendeld en kunnen niet worden bewerkt of verwijderd.",
                },
                {
                    "title": "Een eigen taxonomie toevoegen",
                    "text": "U kunt ook een eigen didactische indeling toevoegen, passend bij uw sectie of methode.",
                    "action": "Klik op 'Taxonomie toevoegen', voer de naam en de mogelijke waarden in en sla op.",
                    "tip": "Gebruik korte, duidelijke waarden die collega's en leerlingen kunnen begrijpen.",
                },
                {
                    "title": "Taxonomie in een toets gebruiken",
                    "text": "Een taxonomie wordt pas zichtbaar bij vragen wanneer deze bij het aanmaken of bewerken van een toets is geselecteerd.",
                    "action": "Ga naar 'Toetsen', bewerk een toets en vink de gewenste taxonomie aan.",
                    "tip": "Gebruik alleen taxonomieën die u daadwerkelijk wilt analyseren; dat houdt invoer overzichtelijk.",
                },
            ],
        }

    def refresh(self) -> None:
        rows = self.database.rows(
            "SELECT d.id, d.name, COALESCE(GROUP_CONCAT(v.name, ', '), ''), "
            "CASE WHEN d.is_standard=1 THEN 'Standaard' ELSE 'Eigen' END, d.is_standard "
            "FROM taxonomy_definitions d LEFT JOIN taxonomy_values v ON v.taxonomy_id=d.id "
            "GROUP BY d.id ORDER BY d.is_standard DESC, d.name"
        )
        self.table.setRowCount(len(rows))
        for row_number, row in enumerate(rows):
            first_cell = item(row["name"])
            first_cell.setData(Qt.ItemDataRole.UserRole, row["id"])
            first_cell.setData(int(Qt.ItemDataRole.UserRole) + 1, row["is_standard"])
            self.table.setItem(row_number, 0, first_cell)
            for column, value in enumerate((row[2], row[3]), start=1):
                self.table.setItem(row_number, column, item(value))

    def add_taxonomy(self) -> None:
        dialog = TaxonomyDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.value_list()
        try:
            cursor = self.database.connection.execute(
                "INSERT INTO taxonomy_definitions(name, is_standard) VALUES(?, 0)",
                (dialog.name.text().strip(),),
            )
            for order, value in enumerate(values):
                self.database.connection.execute(
                    "INSERT INTO taxonomy_values(taxonomy_id, name, sort_order) VALUES(?, ?, ?)",
                    (cursor.lastrowid, value, order),
                )
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Taxonomie niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def selected_taxonomy(self, row: int | None = None):
        if isinstance(row, bool):
            row = None
        row = self.table.currentRow() if row is None else row
        if row < 0:
            QMessageBox.information(self, "Geen taxonomie geselecteerd", "Selecteer eerst een taxonomie.")
            return None
        cell = self.table.item(row, 0)
        taxonomy_id = cell.data(Qt.ItemDataRole.UserRole)
        if taxonomy_id is None:
            return None
        records = self.database.rows(
            "SELECT id, name, is_standard FROM taxonomy_definitions WHERE id=?",
            (taxonomy_id,),
        )
        if not records:
            self.refresh()
            return None
        taxonomy = dict(records[0])
        taxonomy["values"] = [
            record["name"]
            for record in self.database.rows(
                "SELECT name FROM taxonomy_values WHERE taxonomy_id=? ORDER BY sort_order",
                (taxonomy_id,),
            )
        ]
        return taxonomy

    def edit_taxonomy(self, row: int | None = None) -> None:
        taxonomy = self.selected_taxonomy(row)
        if not taxonomy:
            return
        if taxonomy["is_standard"]:
            QMessageBox.information(
                self,
                "Taxonomie vergrendeld",
                f"{taxonomy['name']} is vergrendeld en kan niet worden bewerkt.",
            )
            return
        dialog = TaxonomyDialog(taxonomy, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.value_list()
        try:
            existing_values = self.database.rows(
                "SELECT id, name FROM taxonomy_values WHERE taxonomy_id=? ORDER BY sort_order",
                (taxonomy["id"],),
            )
            self.database.connection.execute(
                "UPDATE taxonomy_definitions SET name=? WHERE id=?",
                (dialog.name.text().strip(), taxonomy["id"]),
            )
            existing_by_name = {record["name"]: record["id"] for record in existing_values}
            removed = [record for record in existing_values if record["name"] not in values]
            if removed:
                removable_ids = [record["id"] for record in removed]
                placeholders = ",".join("?" for _ in removable_ids)
                used_count = self.database.scalar(
                    "SELECT COUNT(*) FROM question_taxonomy_values WHERE taxonomy_value_id IN (" + placeholders + ")",
                    tuple(removable_ids),
                )
                if used_count:
                    self.database.connection.rollback()
                    QMessageBox.warning(
                        self,
                        "Taxonomiewaarde in gebruik",
                        "Een of meer te verwijderen waarden zijn nog gekoppeld aan vragen. "
                        "Pas eerst de vraagindeling aan in het vragenoverzicht.",
                    )
                    return
                self.database.connection.execute(
                    "DELETE FROM taxonomy_values WHERE id IN (" + placeholders + ")",
                    tuple(removable_ids),
                )
            for order, value in enumerate(values):
                if value in existing_by_name:
                    self.database.connection.execute(
                        "UPDATE taxonomy_values SET sort_order=? WHERE id=?",
                        (order, existing_by_name[value]),
                    )
                else:
                    self.database.connection.execute(
                        "INSERT INTO taxonomy_values(taxonomy_id, name, sort_order) VALUES(?, ?, ?)",
                        (taxonomy["id"], value, order),
                    )
            for order, record in enumerate(
                self.database.rows(
                    "SELECT id FROM taxonomy_values WHERE taxonomy_id=? ORDER BY sort_order, id",
                    (taxonomy["id"],),
                )
            ):
                self.database.connection.execute(
                    "UPDATE taxonomy_values SET sort_order=? WHERE id=?",
                    (order, record["id"]),
                )
            self.database.connection.commit()
        except Exception as error:
            self.database.connection.rollback()
            QMessageBox.warning(self, "Taxonomie niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def delete_taxonomy(self) -> None:
        taxonomy = self.selected_taxonomy()
        if not taxonomy:
            return
        if taxonomy["is_standard"]:
            QMessageBox.information(
                self,
                "Taxonomie vergrendeld",
                f"{taxonomy['name']} is vergrendeld en kan niet worden verwijderd.",
            )
            return
        linked_tests = self.database.scalar(
            "SELECT COUNT(*) FROM test_taxonomy_selections WHERE taxonomy_id=?",
            (taxonomy["id"],),
        )
        if linked_tests:
            QMessageBox.warning(
                self,
                "Taxonomie gekoppeld",
                "Je kan geen taxonomie verwijderen waar een toets aan is gekoppeld.\n"
                f"{taxonomy['name']} is nog gekoppeld aan {linked_tests} toets(en).",
            )
            return
        choice = QMessageBox.question(
            self,
            "Taxonomie verwijderen",
            f"Weet u zeker dat u {taxonomy['name']} wilt verwijderen?",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.execute("DELETE FROM taxonomy_definitions WHERE id=?", (taxonomy["id"],))
        except Exception as error:
            QMessageBox.warning(self, "Taxonomie niet verwijderd", str(error))
            return
        self.refresh()
        self.changed.emit()


class ClassificationPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        add = set_button_role(QPushButton("Classificatie toevoegen"), "primary")
        add.clicked.connect(self.add_classification)
        edit = set_button_role(QPushButton("Classificatie bewerken"), "secondary")
        edit.clicked.connect(self.edit_classification)
        delete = set_button_role(QPushButton("Classificatie verwijderen"), "danger")
        delete.clicked.connect(self.delete_classification)
        layout.addWidget(
            make_page_header(
                "Vraagclassificaties",
                "Beheer extra kenmerken zoals domein, hoofdstuk, leerdoel of vraagtype.",
                [delete, edit, add],
            )
        )
        note = QLabel(
            "Stel hier keuzelijsten voor toetsvragen in, bijvoorbeeld Vraagtype: Leg uit, Bereken, Bepaal, Teken."
        )
        note.setObjectName("panel")
        layout.addWidget(note)
        self.table = QTableWidget()
        configure_table(self.table, ["Classificatie", "Type", "Keuzewaarden"])
        self.table.cellDoubleClicked.connect(lambda row, column: self.edit_classification(row))
        layout.addWidget(self.table)
        self.refresh()

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Vraagclassificaties",
            "intro": "Vraagclassificaties zijn extra kenmerken waarmee u vragen indeelt, bijvoorbeeld op hoofdstuk, domein of vraagtype.",
            "steps": [
                {
                    "title": "Waarom classificaties gebruiken?",
                    "text": "Met classificaties kunt u in rapporten zien hoe punten en resultaten verdeeld zijn over onderdelen, bijvoorbeeld 'Bereken' of 'Hoofdstuk 5'.",
                    "action": "Bedenk vooraf welke verdelingen u later in de toetsanalyse wilt terugzien.",
                    "tip": "Een classificatie is niet verplicht bij elke toets; u zet deze per toets aan.",
                },
                {
                    "title": "Een classificatie aanmaken",
                    "text": "Kies een naam en veldtype. Een keuzelijst is geschikt wanneer iedere vraag één vaste waarde krijgt.",
                    "action": "Klik op 'Classificatie toevoegen' en maak bijvoorbeeld 'Hoofdstuk' met de gewenste opties.",
                    "tip": "Voor Vraagtype kunt u opties instellen zoals Leg uit, Bereken, Bepaal of Teken.",
                },
                {
                    "title": "Opties later aanpassen",
                    "text": "Bij een keuzelijst kunt u waarden toevoegen of verwijderen in de bewerk-popup.",
                    "action": "Selecteer de classificatie en klik op 'Classificatie bewerken'. Beheer daarna de opties in hetzelfde venster.",
                    "tip": "Pas benamingen zorgvuldig aan als ze al bij bestaande vragen zijn gebruikt.",
                },
                {
                    "title": "Beschikbaar maken in vragen",
                    "text": "Een classificatie verschijnt in het vragenoverzicht nadat u haar bij een specifieke toets heeft aangevinkt.",
                    "action": "Open 'Toetsen', bewerk de toets en vink bij 'Velden toevoegen aan vragen' de gewenste classificaties aan.",
                    "tip": "Nieuwe classificaties kunnen zo ook achteraf aan een bestaande toets worden toegevoegd.",
                },
            ],
        }

    def refresh(self) -> None:
        rows = self.database.rows(
            "SELECT id, name, field_type, choices_json FROM property_definitions "
            "WHERE is_active=1 ORDER BY id"
        )
        self.table.setRowCount(len(rows))
        for row_number, row in enumerate(rows):
            choices = ", ".join(json.loads(row["choices_json"])) if row["choices_json"] else ""
            first_cell = item(row["name"])
            first_cell.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.table.setItem(row_number, 0, first_cell)
            self.table.setItem(row_number, 1, item(row["field_type"]))
            self.table.setItem(row_number, 2, item(choices))

    def add_classification(self) -> None:
        dialog = QuestionPropertyDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        choices = dialog.choice_values()
        choices_json = json.dumps(choices) if choices else None
        name = dialog.name.text().strip()
        try:
            existing = self.database.rows(
                "SELECT id, is_active FROM property_definitions WHERE name=?", (name,)
            )
            if existing and not int(existing[0]["is_active"]):
                self.database.execute(
                    "UPDATE property_definitions SET field_type=?, choices_json=?, is_active=1 WHERE id=?",
                    (dialog.field_type.currentText(), choices_json, existing[0]["id"]),
                )
            else:
                self.database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    (name, dialog.field_type.currentText(), choices_json),
                )
        except Exception as error:
            QMessageBox.warning(self, "Classificatie niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def selected_definition(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        property_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        definitions = self.database.rows(
            "SELECT id, name, field_type, choices_json FROM property_definitions WHERE id=?", (property_id,)
        )
        return definitions[0] if definitions else None

    def edit_classification(self, row: int | None = None) -> None:
        if isinstance(row, bool):
            row = None
        if row is not None:
            self.table.selectRow(row)
        row = self.table.currentRow() if row is None else row
        if row < 0:
            QMessageBox.information(
                self, "Geen classificatie geselecteerd", "Selecteer eerst een classificatie om te bewerken."
            )
            return
        definition = self.selected_definition()
        if not definition:
            return
        if definition["name"] == "Taxonomie":
            QMessageBox.information(
                self,
                "Gebruik Taxonomieën",
                "Taxonomiewaarden beheert u via het tabblad Taxonomieën.",
            )
            return
        dialog = QuestionPropertyDialog(definition, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_choices = dialog.choice_values() if dialog.field_type.currentText() in ("keuzelijst", "meerkeuze") else []
        old_choices = json.loads(definition["choices_json"]) if definition["choices_json"] else []
        removed_choices = [choice for choice in old_choices if choice not in new_choices]
        if removed_choices:
            placeholders = ",".join("?" for _ in removed_choices)
            used = self.database.scalar(
                "SELECT COUNT(*) FROM question_property_values WHERE property_id=? "
                "AND value IN (" + placeholders + ")",
                (definition["id"], *removed_choices),
            )
            if used:
                QMessageBox.warning(
                    self,
                    "Optie niet verwijderd",
                    "Een of meer verwijderde opties worden al gebruikt bij vragen. "
                    "Wijzig die vragen eerst of laat de optie bestaan.",
                )
                return
        choices_json = json.dumps(new_choices) if new_choices else None
        try:
            self.database.execute(
                "UPDATE property_definitions SET name=?, field_type=?, choices_json=? WHERE id=?",
                (
                    dialog.name.text().strip(),
                    dialog.field_type.currentText(),
                    choices_json,
                    definition["id"],
                ),
            )
        except Exception as error:
            QMessageBox.warning(self, "Classificatie niet opgeslagen", str(error))
            return
        self.refresh()
        self.changed.emit()

    def classification_usage_counts(self, property_id: int) -> dict[str, int]:
        question_count = int(
            self.database.scalar("SELECT COUNT(*) FROM question_property_values WHERE property_id=?", (property_id,))
            or 0
        )
        selected_count = int(
            self.database.scalar("SELECT COUNT(*) FROM test_property_selections WHERE property_id=?", (property_id,))
            or 0
        ) + int(
            self.database.scalar(
                "SELECT COUNT(*) FROM test_property_option_selections WHERE property_id=?", (property_id,)
            )
            or 0
        )
        database_count = int(
            self.database.scalar(
                "SELECT COUNT(*) FROM question_bank_version_property_values WHERE property_id=?", (property_id,)
            )
            or 0
        ) + int(
            self.database.scalar(
                "SELECT COUNT(*) FROM question_bank_subquestion_property_values WHERE property_id=?", (property_id,)
            )
            or 0
        )
        return {
            "toetsen": selected_count,
            "toetsvragen": question_count,
            "vraagdatabase": database_count,
        }

    def delete_classification(self) -> None:
        definition = self.selected_definition()
        if not definition:
            QMessageBox.information(
                self, "Geen classificatie geselecteerd", "Selecteer eerst een classificatie om te verwijderen."
            )
            return
        if definition["name"] == "Taxonomie":
            QMessageBox.information(
                self,
                "Gebruik Taxonomieën",
                "Taxonomiewaarden beheert u via het tabblad Taxonomieën.",
            )
            return
        usage_counts = self.classification_usage_counts(int(definition["id"]))
        if any(usage_counts.values()):
            details = []
            if usage_counts["toetsen"]:
                details.append(f"- gekoppeld aan toetsinstellingen: {usage_counts['toetsen']}")
            if usage_counts["toetsvragen"]:
                details.append(f"- ingevuld bij toetsvragen: {usage_counts['toetsvragen']}")
            if usage_counts["vraagdatabase"]:
                details.append(f"- ingevuld in de vraagdatabase: {usage_counts['vraagdatabase']}")
            QMessageBox.warning(
                self,
                "Classificatie niet verwijderd",
                f"{definition['name']} kan niet worden verwijderd omdat deze al gebruikt wordt.\n\n"
                + "\n".join(details)
                + "\n\nVerwijder of ontkoppel deze gegevens eerst, of laat de classificatie bestaan.",
            )
            return
        choice = QMessageBox.question(
            self,
            "Classificatie verwijderen",
            f"Weet u zeker dat u {definition['name']} wilt verwijderen?\n\n"
            "De classificatie verdwijnt uit toetsinvoer en vraagbeheer.",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return
        try:
            self.database.execute("UPDATE property_definitions SET is_active=0 WHERE id=?", (definition["id"],))
        except Exception as error:
            QMessageBox.warning(self, "Classificatie niet verwijderd", str(error))
            return
        self.refresh()
        self.changed.emit()

class ClassesStudentsPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Klassen && Leerlingen")
        title.setObjectName("pageTitle")
        self.classes_button = QPushButton("Klassen beheren")
        self.classes_button.setCheckable(True)
        self.classes_button.clicked.connect(lambda: self.show_child(0))
        self.students_button = QPushButton("Leerlingen beheren")
        self.students_button.setCheckable(True)
        self.students_button.clicked.connect(lambda: self.show_child(1))
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.classes_button)
        header.addWidget(self.students_button)
        layout.addLayout(header)
        self.stack = QStackedWidget()
        self.choice_page = self.build_choice_page(
            "Wat wilt u beheren?",
            "Kies eerst of u groepen/clusters of leerlingen wilt aanpassen.",
            ("Klassen beheren", "Maak, bewerk of verwijder klassen, clusters en groepen.", 0),
            ("Leerlingen beheren", "Importeer, filter, bewerk of verwijder leerlingen.", 1),
        )
        self.stack.addWidget(self.choice_page)
        self.classes_page = ClassesPage(database, year_id)
        self.students_page = StudentsPage(database, year_id)
        self.children_pages = [self.classes_page, self.students_page]
        for page in self.children_pages:
            page.changed.connect(lambda: self.changed.emit())
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

    def build_choice_page(
        self,
        title: str,
        intro: str,
        first: tuple[str, str, int],
        second: tuple[str, str, int],
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        panel = QFrame()
        panel.setObjectName("startPanel")
        panel.setMaximumWidth(720)
        panel_layout = QVBoxLayout(panel)
        heading = QLabel(f"<h2>{title}</h2><p>{intro}</p>")
        heading.setWordWrap(True)
        panel_layout.addWidget(heading)
        cards = QHBoxLayout()
        for label, description, index in (first, second):
            card = QFrame()
            card.setObjectName("dashboardCard")
            card_layout = QVBoxLayout(card)
            card_title = QLabel(f"<b>{label}</b>")
            card_title.setWordWrap(True)
            card_description = QLabel(description)
            card_description.setWordWrap(True)
            button = QPushButton("Openen")
            button.setToolTip(label)
            button.clicked.connect(lambda checked=False, i=index: self.show_child(i))
            card_layout.addWidget(card_title)
            card_layout.addWidget(card_description, 1)
            card_layout.addWidget(button)
            cards.addWidget(card)
        panel_layout.addLayout(cards)
        layout.addWidget(panel, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        return page

    def show_child(self, index: int) -> None:
        self.stack.setCurrentIndex(index + 1)
        self.classes_button.setChecked(index == 0)
        self.students_button.setChecked(index == 1)
        self.children_pages[index].on_activated()

    def set_year(self, year_id: int | None) -> None:
        self.year_id = year_id
        for page in self.children_pages:
            page.set_year(year_id)

    def refresh(self) -> None:
        self.classes_page.refresh()
        self.students_page.reload_filters()
        self.students_page.refresh()

    def on_activated(self) -> None:
        self.stack.setCurrentIndex(0)
        self.classes_button.setChecked(False)
        self.students_button.setChecked(False)

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Klassen & Leerlingen",
            "intro": "Dit scherm bundelt groepsbeheer en leerlingenbeheer. U kiest bovenaan welk deel u wilt openen.",
            "steps": [
                {
                    "title": "Klassen of clusters beheren",
                    "text": "Gebruik 'Klassen beheren' voor lesgroepen, clusters of andere groepen waarin leerlingen resultaten invoeren.",
                    "action": "Maak eerst de groepen aan die bij het gekozen schooljaar horen.",
                    "tip": "Een groep hoeft niet precies gelijk te zijn aan een administratieve Magisterklas.",
                },
                {
                    "title": "Leerlingen beheren",
                    "text": "Gebruik 'Leerlingen beheren' om leerlingen handmatig toe te voegen, te importeren, te filteren of te verwijderen.",
                    "action": "Koppel iedere leerling aan de juiste groep of cluster voor dit schooljaar.",
                    "tip": "Een leerling kan in een volgend schooljaar in een andere groep zitten en toch dezelfde leerling blijven voor analyse.",
                },
                {
                    "title": "Eigen leerlingvelden",
                    "text": "Bij leerlingen kunt u extra eigenschappen toevoegen, bijvoorbeeld profiel, mentor, extra tijd of ondersteuningsgroep.",
                    "action": "Open 'Leerlingen beheren' en gebruik de knoppen voor eigenschappen.",
                    "tip": "Verwijderen van een eigenschap wist de bijbehorende data definitief; de app vraagt daarom eerst om bevestiging.",
                },
            ],
        }


class TaxonomiesClassificationsPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Taxonomieën en Vraagclassificaties")
        title.setObjectName("pageTitle")
        self.taxonomies_button = QPushButton("Taxonomieën beheren")
        self.taxonomies_button.setCheckable(True)
        self.taxonomies_button.clicked.connect(lambda: self.show_child(0))
        self.classifications_button = QPushButton("Vraagclassificaties beheren")
        self.classifications_button.setCheckable(True)
        self.classifications_button.clicked.connect(lambda: self.show_child(1))
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.taxonomies_button)
        header.addWidget(self.classifications_button)
        layout.addLayout(header)
        self.stack = QStackedWidget()
        self.choice_page = self.build_choice_page(
            "Wat wilt u beheren?",
            "Kies eerst of u denkniveaus/taxonomieën of extra vraagclassificaties wilt aanpassen.",
            ("Taxonomieën beheren", "Beheer denkniveaus zoals RTTI, OBIT, Bloom of eigen taxonomieën.", 0),
            ("Vraagclassificaties beheren", "Beheer metadata zoals domein, hoofdstuk, leerdoel of vraagtype.", 1),
        )
        self.stack.addWidget(self.choice_page)
        self.taxonomy_page = TaxonomyPage(database, year_id)
        self.classification_page = ClassificationPage(database, year_id)
        self.children_pages = [self.taxonomy_page, self.classification_page]
        for page in self.children_pages:
            page.changed.connect(lambda: self.changed.emit())
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

    def build_choice_page(
        self,
        title: str,
        intro: str,
        first: tuple[str, str, int],
        second: tuple[str, str, int],
    ) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        panel = QFrame()
        panel.setObjectName("startPanel")
        panel.setMaximumWidth(760)
        panel_layout = QVBoxLayout(panel)
        heading = QLabel(f"<h2>{title}</h2><p>{intro}</p>")
        heading.setWordWrap(True)
        panel_layout.addWidget(heading)
        cards = QHBoxLayout()
        for label, description, index in (first, second):
            card = QFrame()
            card.setObjectName("dashboardCard")
            card_layout = QVBoxLayout(card)
            card_title = QLabel(f"<b>{label}</b>")
            card_title.setWordWrap(True)
            card_description = QLabel(description)
            card_description.setWordWrap(True)
            button = QPushButton("Openen")
            button.setToolTip(label)
            button.clicked.connect(lambda checked=False, i=index: self.show_child(i))
            card_layout.addWidget(card_title)
            card_layout.addWidget(card_description, 1)
            card_layout.addWidget(button)
            cards.addWidget(card)
        panel_layout.addLayout(cards)
        layout.addWidget(panel, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch()
        return page

    def show_child(self, index: int) -> None:
        self.stack.setCurrentIndex(index + 1)
        self.taxonomies_button.setChecked(index == 0)
        self.classifications_button.setChecked(index == 1)
        self.children_pages[index].on_activated()

    def set_year(self, year_id: int | None) -> None:
        self.year_id = year_id
        for page in self.children_pages:
            page.set_year(year_id)

    def refresh(self) -> None:
        self.taxonomy_page.refresh()
        self.classification_page.refresh()

    def on_activated(self) -> None:
        self.stack.setCurrentIndex(0)
        self.taxonomies_button.setChecked(False)
        self.classifications_button.setChecked(False)

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Taxonomieën en vraagclassificaties",
            "intro": "Hier beheert u de indelingen die bij vragen gebruikt kunnen worden. Taxonomieën en classificaties lijken op elkaar, maar hebben een andere rol.",
            "steps": [
                {
                    "title": "Taxonomie",
                    "text": "Een taxonomie beschrijft het denkniveau van een vraag, bijvoorbeeld RTTI, OBIT of Bloom.",
                    "action": "Gebruik 'Taxonomieën beheren' om te bekijken welke taxonomieën beschikbaar zijn of om een eigen taxonomie toe te voegen.",
                    "tip": "RTTI, OBIT en Bloom zijn standaard aanwezig en vergrendeld.",
                },
                {
                    "title": "Vraagclassificatie",
                    "text": "Een vraagclassificatie is extra metadata bij een vraag, bijvoorbeeld domein, hoofdstuk, leerdoel of vraagtype.",
                    "action": "Gebruik 'Vraagclassificaties beheren' om keuzelijsten en opties te maken.",
                    "tip": "Deze opties kunt u later per toets aanvinken, zodat alleen relevante keuzes zichtbaar zijn bij vraaginvoer.",
                },
                {
                    "title": "Gebruik in een toets",
                    "text": "Bij het aanmaken of bewerken van een toets kiest u welke taxonomieën en classificaties u in die toets wilt gebruiken.",
                    "action": "Ga naar 'Toetsen', open de toets en vink de gewenste onderdelen aan.",
                    "tip": "Kies bewust: minder velden maakt vraaginvoer sneller, meer velden maakt analyse rijker.",
                },
            ],
        }


class AdvancedSettingsPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        self.settings = QSettings("ToetsAnalyse", "ToetsAnalyse")
        self.update_thread: UpdateCheckThread | None = None
        layout = QVBoxLayout(self)
        layout.addWidget(
            make_page_header(
                "Geavanceerde instellingen",
                "Zet extra modules aan of uit. Uitgeschakelde modules verdwijnen uit het menu, gegevens blijven bewaard.",
            )
        )
        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        explanation = QLabel(
            "Deze opties zijn bedoeld voor uitgebreidere workflows. Zet alleen aan wat u ook echt gebruikt; "
            "bestaande koppelingen blijven bewaard als u een module later weer verbergt."
        )
        explanation.setWordWrap(True)
        self.question_database = QCheckBox("Vraagdatabase meenemen")
        self.question_database.setToolTip(
            "Toont de module Vraagdatabase en maakt het mogelijk om toetsvragen aan databasevragen te koppelen."
        )
        self.development_analysis = QCheckBox("Ontwikkelanalyse meenemen")
        self.development_analysis.setToolTip(
            "Toont de module Ontwikkelanalyse voor analyse over meerdere toetsen."
        )
        self.student_attribute_analysis = QCheckBox("Analyse op leerlingeigenschappen meenemen")
        self.student_attribute_analysis.setToolTip(
            "Toont een aparte module om resultaten te vergelijken op basis van leerlingkenmerken zoals profiel of extra tijd."
        )
        self.analysis_parts = QCheckBox("Toets opsplitsen voor analyse meenemen")
        self.analysis_parts.setToolTip(
            "Toont in het vragenoverzicht een knop om een toets voor analyse op te knippen in deeltoetsen."
        )
        self.question_database.toggled.connect(self.save_settings)
        self.development_analysis.toggled.connect(self.save_settings)
        self.student_attribute_analysis.toggled.connect(self.save_settings)
        self.analysis_parts.toggled.connect(self.save_settings)
        panel_layout.addWidget(explanation)
        panel_layout.addWidget(self.question_database)
        panel_layout.addWidget(self.development_analysis)
        panel_layout.addWidget(self.student_attribute_analysis)
        panel_layout.addWidget(self.analysis_parts)
        layout.addWidget(panel)

        update_panel = QFrame()
        update_panel.setObjectName("panel")
        update_layout = QVBoxLayout(update_panel)
        update_title = QLabel("<b>Updates</b>")
        update_explanation = QLabel(
            "Hier stelt u in waar ToetsVizier mag controleren of er een nieuwe versie beschikbaar is. "
            "Bij een nieuwe versie downloadt ToetsVizier eerst de installer en sluit daarna af om de update te starten."
        )
        update_explanation.setWordWrap(True)
        self.version_label = QLabel(
            f"<b>Huidige versie:</b> {APP_VERSION}<br>"
            "Versienummering: <b>1.2.3</b> betekent 1 grote update, 2 middelgrote update, 3 kleine update/patch."
        )
        self.version_label.setWordWrap(True)
        self.update_manifest_url = QLineEdit()
        self.update_manifest_url.setPlaceholderText(DEFAULT_UPDATE_MANIFEST_URL)
        self.update_manifest_unlock = QCheckBox("Updatebron handmatig aanpassen")
        self.update_manifest_unlock.setToolTip(
            "Laat dit uitgeschakeld voor de vaste GitHub-updatebron. Vink dit alleen aan als u bewust een andere updatebron wilt invullen."
        )
        self.update_auto_check = QCheckBox("Bij starten automatisch controleren op updates")
        self.update_auto_check.setToolTip(
            "Controleert op de achtergrond of het updatebestand een nieuwere versie meldt."
        )
        self.update_button = QPushButton("Nu controleren op updates")
        set_button_role(self.update_button, "secondary")
        self.update_manifest_url.editingFinished.connect(self.save_update_settings)
        self.update_manifest_unlock.toggled.connect(self.update_manifest_source_lock_state)
        self.update_manifest_unlock.toggled.connect(self.save_update_settings)
        self.update_auto_check.toggled.connect(self.save_update_settings)
        self.update_button.clicked.connect(self.check_updates_now)
        update_form = QFormLayout()
        update_form.addRow("Updatebron", self.update_manifest_url)
        update_layout.addWidget(update_title)
        update_layout.addWidget(update_explanation)
        update_layout.addWidget(self.version_label)
        update_layout.addLayout(update_form)
        update_layout.addWidget(self.update_manifest_unlock)
        update_layout.addWidget(self.update_auto_check)
        update_layout.addWidget(self.update_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(update_panel)
        layout.addStretch()
        self.refresh()

    def refresh(self) -> None:
        self.question_database.blockSignals(True)
        self.development_analysis.blockSignals(True)
        self.student_attribute_analysis.blockSignals(True)
        self.analysis_parts.blockSignals(True)
        self.update_manifest_url.blockSignals(True)
        self.update_manifest_unlock.blockSignals(True)
        self.update_auto_check.blockSignals(True)
        self.question_database.setChecked(question_database_enabled(self.database))
        self.development_analysis.setChecked(development_analysis_enabled(self.database))
        self.student_attribute_analysis.setChecked(student_attribute_analysis_enabled(self.database))
        self.analysis_parts.setChecked(self.database.meta("analysis_parts_enabled", "0") == "1")
        source_unlocked = settings_bool(self.settings, UPDATE_MANIFEST_EDIT_UNLOCK_KEY, False)
        self.update_manifest_unlock.setChecked(source_unlocked)
        if source_unlocked:
            self.update_manifest_url.setText(update_manifest_url_from_settings(self.settings))
        else:
            self.update_manifest_url.setText(DEFAULT_UPDATE_MANIFEST_URL)
        self.update_auto_check.setChecked(settings_bool(self.settings, UPDATE_AUTO_CHECK_KEY, False))
        self.question_database.blockSignals(False)
        self.development_analysis.blockSignals(False)
        self.student_attribute_analysis.blockSignals(False)
        self.analysis_parts.blockSignals(False)
        self.update_manifest_url.blockSignals(False)
        self.update_manifest_unlock.blockSignals(False)
        self.update_auto_check.blockSignals(False)
        self.update_manifest_source_lock_state()

    def save_settings(self) -> None:
        self.database.set_meta("question_database_enabled", "1" if self.question_database.isChecked() else "0")
        self.database.set_meta("development_analysis_enabled", "1" if self.development_analysis.isChecked() else "0")
        self.database.set_meta(
            "student_attribute_analysis_enabled",
            "1" if self.student_attribute_analysis.isChecked() else "0",
        )
        self.database.set_meta("analysis_parts_enabled", "1" if self.analysis_parts.isChecked() else "0")
        self.database.connection.commit()
        self.save_update_settings()
        self.changed.emit()

    def save_update_settings(self) -> None:
        source_unlocked = self.update_manifest_unlock.isChecked()
        manifest_url = (
            self.update_manifest_url.text().strip() or DEFAULT_UPDATE_MANIFEST_URL
            if source_unlocked
            else DEFAULT_UPDATE_MANIFEST_URL
        )
        self.settings.setValue(UPDATE_MANIFEST_URL_KEY, manifest_url)
        self.settings.setValue(UPDATE_MANIFEST_EDIT_UNLOCK_KEY, source_unlocked)
        self.settings.setValue(UPDATE_AUTO_CHECK_KEY, self.update_auto_check.isChecked())

    def update_manifest_source_lock_state(self) -> None:
        source_unlocked = self.update_manifest_unlock.isChecked()
        self.update_manifest_url.setEnabled(source_unlocked)
        self.update_manifest_url.setReadOnly(not source_unlocked)
        if not source_unlocked:
            self.update_manifest_url.blockSignals(True)
            self.update_manifest_url.setText(DEFAULT_UPDATE_MANIFEST_URL)
            self.update_manifest_url.blockSignals(False)
        self.update_manifest_url.setToolTip(
            "De vaste GitHub-updatebron is vergrendeld."
            if not source_unlocked
            else "U kunt nu handmatig een andere updatebron invullen."
        )

    def check_updates_now(self) -> None:
        self.save_update_settings()
        manifest_url = update_manifest_url_from_settings(self.settings)
        if not manifest_url:
            QMessageBox.warning(
                self,
                "Updatebron ontbreekt",
                "Vul eerst de link naar het updatebestand in. Dit is een klein JSON-bestand met de nieuwste versie, installerlink en releasenotities.",
            )
            return
        if self.update_thread and self.update_thread.isRunning():
            return
        self.update_button.setEnabled(False)
        self.update_button.setText("Controleren...")
        self.update_thread = UpdateCheckThread(manifest_url, APP_VERSION, 10, self)
        self.update_thread.result_ready.connect(lambda result: show_update_result(self, result, silent_when_current=False))
        self.update_thread.error_ready.connect(self.show_update_error)
        self.update_thread.finished.connect(self.finish_update_check)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.start()

    def show_update_error(self, message: str) -> None:
        QMessageBox.warning(self, "Updatecontrole mislukt", message)

    def finish_update_check(self) -> None:
        self.update_button.setEnabled(True)
        self.update_button.setText("Nu controleren op updates")
        self.update_thread = None

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Geavanceerde instellingen",
            "intro": "Hier zet u extra modules aan of uit. Uitgeschakelde modules verdwijnen uit het menu, maar bestaande gegevens blijven bewaard.",
            "steps": [
                {
                    "title": "Vraagdatabase meenemen",
                    "text": "Met deze optie verschijnt de module Vraagdatabase. Daarin kunt u vaste vragen beheren en die later in toetsen gebruiken.",
                    "action": "Vink 'Vraagdatabase meenemen' aan om de module zichtbaar te maken.",
                    "tip": "Als u de optie later uitzet, blijven bestaande koppelingen tussen toetsvragen en databasevragen gewoon opgeslagen.",
                },
                {
                    "title": "Ontwikkelanalyse meenemen",
                    "text": "Met deze optie verschijnt de module Ontwikkelanalyse. Daarin analyseert u groepen en leerlingen over meerdere toetsen.",
                    "action": "Vink 'Ontwikkelanalyse meenemen' aan om de module zichtbaar te maken.",
                    "tip": "De datastructuur verandert niet. De optie bepaalt alleen of het menu zichtbaar is.",
                },
                {
                    "title": "Analyse op leerlingeigenschappen",
                    "text": "Met deze optie verschijnt een apart analysepaneel voor leerlingkenmerken zoals profiel, extra tijd of ondersteuningsgroep.",
                    "action": "Gebruik bij leerlingen bij voorkeur keuzelijsten; vrije tekst en opmerkingen worden niet als analysegroep gebruikt.",
                    "tip": "Kleine groepjes worden afgeschermd: standaard toont de analyse geen groep met minder dan drie leerlingen.",
                },
                {
                    "title": "Automatische updates",
                    "text": "ToetsVizier kan bij het starten controleren of er een nieuwere versie beschikbaar is.",
                    "action": "Laat de updatebron normaal vergrendeld staan. Vink 'Updatebron handmatig aanpassen' alleen aan als u bewust een andere bron wilt gebruiken.",
                    "tip": "Zonder ontgrendeling gebruikt ToetsVizier altijd de vaste GitHub-bron. Het updatebestand bevat latest_version, installer_url, download_url, release_notes en optioneel wijzigingen per versie.",
                },
            ],
        }








class StudentAttributeGradeDistributionChart(QWidget):
    COLORS = ["#ef4444", "#f59e0b", "#60a5fa", "#22c55e", "#15803d"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: list[dict[str, object]] = []
        self.bins: list[str] = []
        self.segments: list[tuple[tuple[int, int, int, int], str]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def set_distribution(self, distribution: dict[str, object]) -> None:
        self.rows = list(distribution.get("rows", []))
        self.bins = list(distribution.get("bins", []))
        self.setMinimumHeight(max(220, 96 + len(self.rows) * 38))
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self.segments = []
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QColor("#0b2345"))
        if not self.rows:
            painter.drawText(
                self.rect().adjusted(16, 16, -16, -16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                "Nog geen cijferdata zichtbaar. Cijfers verschijnen pas als er normering is vastgesteld.",
            )
            return

        left = 18
        top = 18
        bottom = 48
        label_width = min(240, max(150, int(self.width() * 0.24)))
        count_width = 72
        bar_left = left + label_width
        bar_width = max(120, self.width() - bar_left - count_width - 22)
        row_height = 34

        painter.setFont(QFont("Segoe UI", 9))
        for row_index, row in enumerate(self.rows):
            y = top + row_index * row_height
            label = str(row["value"])
            painter.setPen(QColor("#0b2345"))
            painter.drawText(left, y + 20, label[:32])
            bins = [int(value) for value in row.get("bins", [])]
            total = sum(bins)
            if total <= 0:
                painter.setPen(QColor("#66748e"))
                painter.drawText(bar_left, y + 20, "Geen cijfers")
                continue
            x = bar_left
            for bin_index, count in enumerate(bins):
                width = int(round(bar_width * count / total))
                if count and width < 3:
                    width = 3
                if width <= 0:
                    continue
                rect = (x, y + 6, max(1, width), 18)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(self.COLORS[bin_index % len(self.COLORS)]))
                painter.drawRoundedRect(*rect, 4, 4)
                percentage = count / total * 100
                mean_grade = row.get("mean_grade")
                mean_text = "" if mean_grade is None else f"<br>Gemiddeld cijfer: <b>{float(mean_grade):.1f}</b>"
                self.segments.append(
                    (
                        rect,
                        "<b>Cijferverdeling</b>"
                        f"<br>Eigenschapswaarde: <b>{html.escape(label)}</b>"
                        f"<br>Cijferbereik: <b>{html.escape(str(self.bins[bin_index]))}</b>"
                        f"<br>Aantal cijfers: <b>{count}</b> van {total}"
                        f"<br>Aandeel binnen deze groep: <b>{percentage:.0f}%</b>"
                        + mean_text,
                    )
                )
                x += width
            painter.setPen(QColor("#66748e"))
            painter.drawText(bar_left + bar_width + 10, y + 20, f"{total} cijfer(s)")

        legend_y = max(top + len(self.rows) * row_height + 14, self.height() - bottom + 8)
        legend_x = left
        painter.setFont(QFont("Segoe UI", 8))
        for index, label in enumerate(self.bins):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.COLORS[index % len(self.COLORS)]))
            painter.drawRoundedRect(legend_x, legend_y, 10, 10, 2, 2)
            painter.setPen(QColor("#40516a"))
            painter.drawText(legend_x + 14, legend_y + 10, label)
            legend_x += 105

    def mouseMoveEvent(self, event) -> None:
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        for rect, tooltip in self.segments:
            x, y, width, height = rect
            if x <= position.x() <= x + width and y <= position.y() <= y + height:
                global_position = (
                    event.globalPosition().toPoint()
                    if hasattr(event, "globalPosition")
                    else event.globalPos()
                )
                QToolTip.showText(global_position, tooltip, self)
                return
        QToolTip.hideText()

    def leaveEvent(self, event) -> None:
        QToolTip.hideText()
        super().leaveEvent(event)


class StudentAttributeDimensionHeatmap(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: list[dict[str, object]] = []
        self.cells: list[tuple[tuple[int, int, int, int], dict[str, object]]] = []
        self.setMouseTracking(True)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        self.rows = list(rows)
        values = self._unique("value")
        self.setMinimumHeight(max(240, 128 + len(values) * 40))
        self.update()

    def _unique(self, key: str) -> list[str]:
        seen: set[str] = set()
        values: list[str] = []
        for row in self.rows:
            value = str(row.get(key) or "")
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        return values

    @staticmethod
    def _dimension_sort_key(value: str) -> tuple[int, str]:
        preferred = {
            "R": 0,
            "T1": 1,
            "T2": 2,
            "I": 3,
            "Onthouden": 10,
            "Begrijpen": 11,
            "Toepassen": 12,
            "Analyseren": 13,
            "Evalueren": 14,
            "Creeren": 15,
            "Creëren": 15,
        }
        return (preferred.get(value, 100), value.lower())

    @staticmethod
    def _color_for_percentage(value: object) -> QColor:
        if value is None:
            return QColor("#eef2f7")
        percentage = float(value)
        if percentage < 40:
            return QColor("#ef4444")
        if percentage < 55:
            return QColor("#f59e0b")
        if percentage < 70:
            return QColor("#60a5fa")
        return QColor("#22c55e")

    @staticmethod
    def _contrast_color(value: object) -> QColor:
        if value is None:
            return QColor("#66748e")
        percentage = float(value)
        return QColor("#ffffff") if percentage < 70 else QColor("#062047")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        self.cells = []
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QColor("#0b2345"))

        if not self.rows:
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                self.rect().adjusted(16, 18, -16, -16),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                "Kies een onderdeelanalyse om hier een grafisch overzicht te zien.",
            )
            return

        values = sorted(self._unique("value"), key=str.lower)
        dimensions = sorted(self._unique("dimension"), key=self._dimension_sort_key)
        lookup = {
            (str(row.get("value") or ""), str(row.get("dimension") or "")): row
            for row in self.rows
        }
        if not values or not dimensions:
            return

        left = min(220, max(128, int(self.width() * 0.20)))
        right = 18
        top = 48
        header_height = 40
        row_height = 36
        bottom = 52
        available_width = max(120, self.width() - left - right)
        cell_width = max(48, int(available_width / max(1, len(dimensions))))
        total_width = cell_width * len(dimensions)
        grid_left = left
        metrics = QFontMetrics(QFont("Segoe UI", 9))

        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        painter.setPen(QColor("#40516a"))
        painter.drawText(16, top + 25, "Eigenschapswaarde")
        for column, dimension in enumerate(dimensions):
            x = grid_left + column * cell_width
            painter.fillRect(x, top, cell_width - 2, header_height, QColor("#f3f6fb"))
            painter.setPen(QColor("#40516a"))
            painter.drawText(
                x + 6,
                top + 24,
                metrics.elidedText(dimension, Qt.TextElideMode.ElideRight, cell_width - 12),
            )

        painter.setFont(QFont("Segoe UI", 9))
        for row_index, value in enumerate(values):
            y = top + header_height + row_index * row_height
            painter.setPen(QColor("#0b2345"))
            painter.drawText(
                16,
                y + 23,
                metrics.elidedText(value, Qt.TextElideMode.ElideRight, left - 28),
            )
            for column, dimension in enumerate(dimensions):
                x = grid_left + column * cell_width
                row = lookup.get((value, dimension))
                percentage = row.get("mean_percentage") if row else None
                color = self._color_for_percentage(percentage)
                rect = (x + 2, y + 4, max(24, cell_width - 6), row_height - 8)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawRoundedRect(*rect, 7, 7)
                painter.setPen(self._contrast_color(percentage))
                text = "-" if percentage is None else f"{float(percentage):.0f}%"
                painter.drawText(
                    rect[0],
                    rect[1],
                    rect[2],
                    rect[3],
                    Qt.AlignmentFlag.AlignCenter,
                    text,
                )
                if row:
                    self.cells.append((rect, row))

        legend_y = top + header_height + len(values) * row_height + 16
        legend_items = [
            ("laag", "#ef4444"),
            ("aandacht", "#f59e0b"),
            ("voldoende", "#60a5fa"),
            ("sterk", "#22c55e"),
        ]
        painter.setFont(QFont("Segoe UI", 8))
        legend_x = max(16, grid_left)
        for label, color in legend_items:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(legend_x, legend_y, 11, 11, 3, 3)
            painter.setPen(QColor("#40516a"))
            painter.drawText(legend_x + 16, legend_y + 11, label)
            legend_x += 92
        painter.setPen(QColor("#66748e"))
        painter.drawText(
            16,
            min(self.height() - 12, legend_y + 32),
            "Hover over een vakje voor leerlingen, scorecellen en het exacte percentage.",
        )

    def mouseMoveEvent(self, event) -> None:
        position = event.position().toPoint() if hasattr(event, "position") else event.pos()
        for rect, row in self.cells:
            x, y, width, height = rect
            if x <= position.x() <= x + width and y <= position.y() <= y + height:
                percentage = row.get("mean_percentage")
                percentage_text = "-" if percentage is None else f"{float(percentage):.1f}%"
                tooltip = (
                    "<b>Prestatie per onderdeel</b>"
                    f"<br>Eigenschapswaarde: <b>{html.escape(str(row.get('value') or '-'))}</b>"
                    f"<br>Onderdeel: <b>{html.escape(str(row.get('dimension') or '-'))}</b>"
                    f"<br>% van de punten: <b>{percentage_text}</b>"
                    f"<br>Leerlingen: <b>{row.get('students', '-')}</b>"
                    f"<br>Scorecellen: <b>{row.get('score_count', '-')}</b>"
                )
                global_position = (
                    event.globalPosition().toPoint()
                    if hasattr(event, "globalPosition")
                    else event.globalPos()
                )
                QToolTip.showText(global_position, tooltip, self)
                return
        QToolTip.hideText()

    def leaveEvent(self, event) -> None:
        QToolTip.hideText()
        super().leaveEvent(event)


class StudentAttributeAnalysisPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        self.loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll)
        content = QWidget()
        self.scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 10, 12)
        layout.setSpacing(10)
        layout.addWidget(
            make_page_header(
                "Eigenschappenanalyse",
                "Vergelijk toetsresultaten op basis van leerlingeigenschappen zoals profiel, extra tijd of ondersteuningsgroep.",
            )
        )
        self.level_filter = QComboBox()
        self.level_filter.currentIndexChanged.connect(self.refresh)
        self.grade_filter = QComboBox()
        self.grade_filter.currentIndexChanged.connect(self.refresh)
        self.class_filter = QComboBox()
        self.class_filter.currentIndexChanged.connect(self.load_analysis)
        self.test_filter = QComboBox()
        self.test_filter.currentIndexChanged.connect(self.load_analysis)
        self.compare_year_filter = QComboBox()
        self.compare_year_filter.currentIndexChanged.connect(self.load_analysis)
        self.attribute_filter = QComboBox()
        self.attribute_filter.currentIndexChanged.connect(self.attribute_changed)
        self.value_filter = QComboBox()
        self.value_filter.currentIndexChanged.connect(self.load_analysis)
        self.dimension_filter = QComboBox()
        self.dimension_filter.currentIndexChanged.connect(self.load_analysis)
        for combo in (
            self.level_filter,
            self.grade_filter,
            self.class_filter,
            self.test_filter,
            self.compare_year_filter,
            self.attribute_filter,
            self.value_filter,
            self.dimension_filter,
        ):
            combo.setMinimumHeight(34)
        self.filter_card = make_responsive_filter_card(
            "Filter en analysekeuze",
            [
                ("Niveau", self.level_filter),
                ("Leerjaar", self.grade_filter),
                ("Groep", self.class_filter),
                ("Toets", self.test_filter),
                ("Vergelijk met", self.compare_year_filter),
                ("Leerlingeigenschap", self.attribute_filter),
                ("Waarde filter", self.value_filter),
                ("Onderdeelanalyse", self.dimension_filter),
            ],
            minimum_field_width=240,
            maximum_columns=4,
        )
        self.filter_card.setMinimumHeight(150)
        self.filter_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout.addWidget(self.filter_card)
        self.info = QLabel()
        self.info.setObjectName("infoBanner")
        self.info.setWordWrap(True)
        self.info.setMinimumHeight(42)
        layout.addWidget(self.info)
        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.students_card = self.metric_card("Leerlingen")
        self.attempts_card = self.metric_card("Afnames")
        self.mean_card = self.metric_card("Gemiddeld")
        self.privacy_card = self.metric_card("Privacy")
        for card in (self.students_card, self.attempts_card, self.mean_card, self.privacy_card):
            cards.addWidget(card)
        layout.addLayout(cards)
        self.summary_table = QTableWidget()
        configure_table(
            self.summary_table,
            [
                "Eigenschapwaarde",
                "Leerlingen",
                "Afnames",
                "Gem. % van punten",
                "Verschil met totaal",
                "Gem. cijfer",
                "% voldoende",
            ],
        )
        self.summary_table.setMinimumHeight(170)
        self.summary_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.year_comparison_table = QTableWidget()
        configure_table(
            self.year_comparison_table,
            [
                "Eigenschapwaarde",
                "Huidig schooljaar",
                "Vergelijkingsjaar",
                "Verschil",
                "Leerlingen huidig",
                "Leerlingen vergelijkingsjaar",
            ],
        )
        self.year_comparison_table.setMinimumHeight(150)
        self.year_comparison_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.grade_distribution_chart = StudentAttributeGradeDistributionChart()
        self.dimension_heatmap = StudentAttributeDimensionHeatmap()
        layout.addWidget(QLabel("<b>Samenvatting per eigenschapswaarde</b>"))
        layout.addWidget(self.summary_table)
        layout.addWidget(QLabel("<b>Schooljaarvergelijking per eigenschapswaarde</b>"))
        layout.addWidget(self.year_comparison_table)
        layout.addWidget(QLabel("<b>Cijferverdeling per eigenschapswaarde</b>"))
        layout.addWidget(self.grade_distribution_chart)
        layout.addWidget(QLabel("<b>Prestatie per gekozen onderdeel</b>"))
        layout.addWidget(self.dimension_heatmap)
        layout.addStretch()
        self.refresh()

    def metric_card(self, title: str) -> QLabel:
        label = QLabel()
        label.setObjectName("dashboardCard")
        label.setMinimumHeight(72)
        label.setMaximumHeight(88)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        label.setText(f"<b>{title}</b><br>-")
        return label

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Eigenschappenanalyse",
            "intro": "Deze optionele analyse vergelijkt resultaten van groepen leerlingen op basis van een leerlingkenmerk.",
            "steps": [
                {
                    "title": "Leerlingeigenschap kiezen",
                    "text": "Kies eerst een eigenschap zoals profiel, extra tijd of ondersteuningsgroep. Vrije tekst en opmerkingen worden niet gebruikt als analysegroep.",
                    "action": "Maak bij leerlingen bij voorkeur een keuzelijst als u dit onderdeel wilt analyseren.",
                    "tip": "Keuzelijsten zijn beter vergelijkbaar dan losse tekst die per leerling anders gespeld kan zijn.",
                },
                {
                    "title": "Filters gebruiken",
                    "text": "Met niveau, leerjaar, groep, toets en waarde filtert u welke resultaten worden meegenomen.",
                    "action": "Gebruik 'Alle toetsen' voor een brede analyse of kies één toets voor een gerichte controle.",
                    "tip": "De groep mag op 'Alle groepen' blijven staan.",
                },
                {
                    "title": "Schooljaren vergelijken",
                    "text": "Met 'Vergelijk met' zet u het gekozen schooljaar naast een ander schooljaar, bijvoorbeeld 2025-2026 tegenover 2026-2027.",
                    "action": "Kies eerst de eigenschap en selecteer daarna het vergelijkingsjaar.",
                    "tip": "De jaarvergelijking gebruikt alle toetsen binnen de gekozen filters. Een groep wordt op naam gematcht tussen schooljaren.",
                },
                {
                    "title": "Privacygrens",
                    "text": "De app toont geen analysegroepjes met minder dan drie leerlingen.",
                    "action": "Gebruik bredere filters wanneer er te weinig leerlingen zichtbaar zijn.",
                    "tip": "Zo voorkomt u dat kleine groepjes te makkelijk herleidbaar zijn.",
                },
                {
                    "title": "Onderdeelanalyse",
                    "text": "Onderaan kiest u of u wilt uitsplitsen naar bijvoorbeeld RTTI, domein, hoofdstuk of vraagtype.",
                    "action": "Kies een onderdeel bij 'Onderdeelanalyse' om te zien waar verschillen zitten.",
                    "tip": "Deze analyse gebruikt alleen vragen waar dat onderdeel daadwerkelijk is ingevuld.",
                },
            ],
        }

    @staticmethod
    def pct(value: object) -> str:
        if value is None:
            return "-"
        return f"{float(value):.0f}%"

    @staticmethod
    def signed_pct(value: object) -> str:
        if value is None:
            return "-"
        number = float(value)
        sign = "+" if number >= 0 else ""
        return f"{sign}{number:.0f}%"

    def set_year(self, year_id: int | None) -> None:
        self.year_id = year_id
        self.refresh()

    def refresh(self) -> None:
        if self.loading:
            return
        self.loading = True
        selected_level = self.level_filter.currentData()
        selected_grade = self.grade_filter.currentData()
        selected_class = self.class_filter.currentData()
        selected_test = self.test_filter.currentData()
        selected_compare_year = self.compare_year_filter.currentData()
        selected_attribute = self.attribute_filter.currentData()
        selected_value = self.value_filter.currentData()
        selected_dimension = self.dimension_filter.currentData()
        combos = (
            self.level_filter,
            self.grade_filter,
            self.class_filter,
            self.test_filter,
            self.compare_year_filter,
            self.attribute_filter,
            self.value_filter,
            self.dimension_filter,
        )
        for combo in combos:
            combo.blockSignals(True)
            combo.clear()
        self.level_filter.addItem("Alle niveaus", None)
        self.grade_filter.addItem("Alle leerjaren", None)
        filter_values = self.database.rows(
            "SELECT DISTINCT COALESCE(level, '') AS level, COALESCE(grade_year, '') AS grade_year "
            "FROM tests WHERE school_year_id=?",
            (self.year_id,),
        ) if self.year_id else []
        for level in sorted({row["level"] for row in filter_values if row["level"]}, key=str.lower):
            self.level_filter.addItem(level, level)
        for grade in sorted({row["grade_year"] for row in filter_values if row["grade_year"]}, key=str.lower):
            self.grade_filter.addItem(grade, grade)
        self.restore_combo_value(self.level_filter, selected_level)
        self.restore_combo_value(self.grade_filter, selected_grade)
        self.class_filter.addItem("Alle groepen", None)
        for classroom in self.database.rows(
            "SELECT id, name FROM classes WHERE school_year_id=? ORDER BY name", (self.year_id,)
        ) if self.year_id else []:
            self.class_filter.addItem(classroom["name"], classroom["id"])
        self.restore_combo_value(self.class_filter, selected_class)
        self.test_filter.addItem("Alle toetsen", None)
        conditions = ["school_year_id=?"]
        parameters: list[object] = [self.year_id]
        if self.level_filter.currentData():
            conditions.append("level=?")
            parameters.append(self.level_filter.currentData())
        if self.grade_filter.currentData():
            conditions.append("grade_year=?")
            parameters.append(self.grade_filter.currentData())
        for test in self.database.rows(
            "SELECT id, name FROM tests WHERE " + " AND ".join(conditions) + " ORDER BY created_at DESC",
            parameters,
        ) if self.year_id else []:
            self.test_filter.addItem(test["name"], test["id"])
        self.restore_combo_value(self.test_filter, selected_test)
        self.compare_year_filter.addItem("Geen vergelijking", None)
        for year in self.database.rows("SELECT id, name FROM school_years ORDER BY name DESC"):
            if self.year_id is not None and int(year["id"]) == int(self.year_id):
                continue
            self.compare_year_filter.addItem(year["name"], int(year["id"]))
        self.restore_combo_value(self.compare_year_filter, selected_compare_year)
        self.attribute_filter.addItem("Kies eigenschap...", None)
        self.attribute_filter.addItem("Groep / cluster", GROUP_ATTRIBUTE_KEY)
        for attribute in analyzable_student_attributes(self.database):
            self.attribute_filter.addItem(attribute["name"], attribute["id"])
        self.restore_combo_value(self.attribute_filter, selected_attribute)
        self.dimension_filter.addItem("Kies onderdeel...", None)
        for dimension in available_attribute_dimensions(self.database):
            self.dimension_filter.addItem(dimension["label"], f"{dimension['kind']}:{dimension['id']}")
        self.restore_combo_value(self.dimension_filter, selected_dimension)
        self.reload_values(selected_value)
        for combo in combos:
            combo.blockSignals(False)
        self.loading = False
        self.load_analysis()

    def restore_combo_value(self, combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def attribute_changed(self) -> None:
        if self.loading:
            return
        self.value_filter.blockSignals(True)
        self.reload_values(None)
        self.value_filter.blockSignals(False)
        self.load_analysis()

    def reload_values(self, selected_value: object) -> None:
        self.value_filter.clear()
        self.value_filter.addItem("Alle waarden", None)
        attribute_id = self.attribute_filter.currentData()
        if attribute_id is None:
            self.value_filter.setCurrentIndex(0)
            return
        for value in available_attribute_values(self.database, attribute_id, self.year_id):
            self.value_filter.addItem(value, value)
        self.restore_combo_value(self.value_filter, selected_value)

    def load_analysis(self) -> None:
        if self.loading:
            return
        attribute_id = self.attribute_filter.currentData()
        if attribute_id is None:
            self.info.setText(
                "Kies een leerlingeigenschap of Groep / cluster om te analyseren. Alleen keuzelijst, ja/nee en getal worden getoond."
            )
            self.update_metric_cards(None)
            self.summary_table.setRowCount(0)
            self.year_comparison_table.setRowCount(0)
            self.grade_distribution_chart.set_distribution({"rows": [], "bins": []})
            self.dimension_heatmap.set_rows([])
            return
        context = {
            "year_id": self.year_id,
            "test_id": self.test_filter.currentData(),
            "level": self.level_filter.currentData(),
            "grade_year": self.grade_filter.currentData(),
            "class_id": self.class_filter.currentData(),
            "attribute_value": self.value_filter.currentData(),
        }
        summary = student_attribute_summary(self.database, attribute_id=attribute_id, **context)
        self.update_metric_cards(summary)
        self.fill_summary_table(summary["rows"])
        self.fill_year_comparison_table(attribute_id)
        distribution = student_attribute_grade_distribution(self.database, attribute_id=attribute_id, **context)
        self.grade_distribution_chart.set_distribution(distribution)
        dimension_data = self.dimension_filter.currentData()
        if dimension_data is None:
            self.dimension_heatmap.set_rows([])
            self.info.setText(
                f"Privacygrens: groepen met minder dan {summary['minimum_students']} leerlingen worden verborgen. "
                "Kies een onderdeelanalyse om ook prestaties per RTTI, domein of vraagtype te zien."
            )
            return
        kind, raw_id = str(dimension_data).split(":", 1)
        dimension = student_attribute_dimension_summary(
            self.database,
            attribute_id=attribute_id,
            dimension_kind=kind,
            dimension_id=int(raw_id),
            **context,
        )
        self.dimension_heatmap.set_rows(dimension["rows"])
        hidden = int(summary["hidden_groups"]) + int(dimension["hidden_groups"])
        self.info.setText(
            f"Privacygrens: groepen met minder dan {summary['minimum_students']} leerlingen worden verborgen. "
            f"Verborgen groepjes in deze selectie: {hidden}."
        )

    def year_name(self, year_id: int | None) -> str:
        if year_id is None:
            return "-"
        return str(self.database.scalar("SELECT name FROM school_years WHERE id=?", (year_id,)) or "-")

    def fill_year_comparison_table(self, attribute_id: int | str) -> None:
        comparison_year_id = self.compare_year_filter.currentData()
        if self.year_id is None or comparison_year_id is None:
            self.year_comparison_table.setHorizontalHeaderLabels(
                [
                    "Eigenschapwaarde",
                    "Huidig schooljaar",
                    "Vergelijkingsjaar",
                    "Verschil",
                    "Leerlingen huidig",
                    "Leerlingen vergelijkingsjaar",
                ]
            )
            self.year_comparison_table.setRowCount(0)
            return
        comparison = student_attribute_year_comparison(
            self.database,
            attribute_id=attribute_id,
            base_year_id=int(self.year_id),
            comparison_year_id=int(comparison_year_id),
            level=self.level_filter.currentData(),
            grade_year=self.grade_filter.currentData(),
            class_id=self.class_filter.currentData(),
            attribute_value=self.value_filter.currentData(),
        )
        base_label = self.year_name(self.year_id)
        comparison_label = self.year_name(int(comparison_year_id))
        self.year_comparison_table.setHorizontalHeaderLabels(
            [
                "Eigenschapwaarde",
                base_label,
                comparison_label,
                "Verschil",
                f"Leerlingen {base_label}",
                f"Leerlingen {comparison_label}",
            ]
        )
        rows = list(comparison["rows"])
        self.year_comparison_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["value"],
                self.pct(row["base_mean_percentage"]),
                self.pct(row["comparison_mean_percentage"]),
                self.signed_pct(row["difference"]),
                "-" if row["base_students"] is None else row["base_students"],
                "-" if row["comparison_students"] is None else row["comparison_students"],
            ]
            for column, value in enumerate(values):
                self.year_comparison_table.setItem(row_index, column, item(value))

    def update_metric_cards(self, summary: dict[str, object] | None) -> None:
        if not summary:
            values = [("Leerlingen", "-"), ("Afnames", "-"), ("Gemiddeld", "-"), ("Privacy", "min. 3 leerlingen")]
        else:
            values = [
                ("Leerlingen", str(summary["total_students"])),
                ("Afnames", str(summary["total_attempts"])),
                ("Gemiddeld", self.pct(summary["total_mean_percentage"])),
                ("Privacy", f"{summary['hidden_groups']} verborgen"),
            ]
        for card, (title, value) in zip(
            (self.students_card, self.attempts_card, self.mean_card, self.privacy_card),
            values,
        ):
            card.setText(f"<b>{title}</b><br><span style='font-size:20px'>{value}</span>")

    def fill_summary_table(self, rows: list[dict[str, object]]) -> None:
        self.summary_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["value"],
                row["students"],
                row["attempts"],
                self.pct(row["mean_percentage"]),
                self.signed_pct(row["difference_from_total"]),
                "-" if row["mean_grade"] is None else f"{float(row['mean_grade']):.1f}",
                self.pct(row["sufficient_percentage"]),
            ]
            for column, value in enumerate(values):
                self.summary_table.setItem(row_index, column, item(value))


class NormingBridge(QObject):
    def __init__(self, page: "NormingPage") -> None:
        super().__init__(page)
        self.page = page

    @Slot(str, result=str)
    def finalizeNormalization(self, settings_json: str) -> str:
        test_id = self.page.test.currentData()
        if test_id is None:
            return json.dumps({"ok": False, "message": "Selecteer eerst een toets."})
        try:
            save_normalization(self.page.database, test_id, json.loads(settings_json))
        except Exception as error:
            return json.dumps({"ok": False, "message": str(error)})
        return json.dumps({"ok": True, "message": "Normering vastgesteld en vergrendeld."})

    @Slot(result=str)
    def removeNormalization(self) -> str:
        test_id = self.page.test.currentData()
        if test_id is None:
            return json.dumps({"ok": False, "message": "Selecteer eerst een toets."})
        answer = QMessageBox.question(
            self.page,
            "Vastgestelde normering opheffen",
            "Weet u zeker dat u de vastgestelde normering wilt opheffen?\n\n"
            "De opgeslagen normeringswaarden en berekende cijfers worden verwijderd.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return json.dumps({"ok": False, "cancelled": True, "message": "Opheffen geannuleerd."})
        try:
            remove_normalization(self.page.database, test_id)
            settings = load_normalization(self.page.database, test_id)
        except Exception as error:
            return json.dumps({"ok": False, "message": str(error)})
        return json.dumps(
            {
                "ok": True,
                "message": "Normering opgeheven. De getoonde berekening is weer een concept.",
                "settings": settings,
            }
        )

    @Slot(str, str, result=str)
    def exportParticipants(self, export_format: str, request_json: str) -> str:
        test_id = self.page.test.currentData()
        if test_id is None:
            return json.dumps({"ok": False, "message": "Selecteer eerst een toets."})
        try:
            request = json.loads(request_json)
            rows = participant_rows(request.get("rows", []))
            data = dashboard_data(self.page.database, test_id)
            test = data["test"]
            maximum = float(data["maximum_score"])
            method = str(request.get("method", "Normering"))
            is_finalized = bool(request.get("is_finalized", False))
        except Exception as error:
            return json.dumps({"ok": False, "message": f"Het overzicht kon niet worden verwerkt: {error}"})
        if not rows:
            return json.dumps({"ok": False, "message": "Er zijn geen deelnemers met complete scores om te exporteren."})
        export_format = export_format.lower()
        if export_format == "excel":
            EXCEL_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            suggested = EXCEL_EXPORT_DIR / f"{slug(str(test['name']))}_deelnemersoverzicht.xlsx"
            file_name, _ = QFileDialog.getSaveFileName(
                self.page,
                "Deelnemersoverzicht opslaan als Excel",
                str(suggested),
                "Excelbestand (*.xlsx)",
            )
            if not file_name:
                return json.dumps({"ok": False, "cancelled": True})
            if not file_name.lower().endswith(".xlsx"):
                file_name += ".xlsx"
            try:
                export_participant_overview_xlsx(file_name, test, maximum, rows, method, is_finalized)
            except Exception as error:
                return json.dumps({"ok": False, "message": f"Excelbestand niet opgeslagen: {error}"})
            report_type = "deelnemersoverzicht_excel"
        elif export_format == "pdf":
            PDF_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            suggested = PDF_EXPORT_DIR / f"{slug(str(test['name']))}_deelnemersoverzicht.pdf"
            file_name, _ = QFileDialog.getSaveFileName(
                self.page,
                "Deelnemersoverzicht opslaan als PDF",
                str(suggested),
                "PDF-bestanden (*.pdf)",
            )
            if not file_name:
                return json.dumps({"ok": False, "cancelled": True})
            if not file_name.lower().endswith(".pdf"):
                file_name += ".pdf"
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                report_html = build_participant_overview_html(test, maximum, rows, method, is_finalized)
                export_html_to_pdf(report_html, file_name)
            except PdfExportError as error:
                return json.dumps({"ok": False, "message": f"PDF niet opgeslagen: {error}"})
            finally:
                QApplication.restoreOverrideCursor()
            report_type = "deelnemersoverzicht_pdf"
        else:
            return json.dumps({"ok": False, "message": "Deze exportvorm wordt niet ondersteund."})
        try:
            self.page.database.execute(
                "INSERT INTO report_exports(report_type, test_id, file_path) VALUES(?, ?, ?)",
                (report_type, test_id, file_name),
            )
        except Exception:
            pass
        return json.dumps({"ok": True, "message": f"Overzicht opgeslagen als {export_format.upper()}."})


class NormingPage(Page):
    def __init__(self, database: SubjectDatabase, year_id: int | None) -> None:
        super().__init__(database, year_id)
        layout = QVBoxLayout(self)
        self.dashboard_zoom = 1.0
        selector = QHBoxLayout()
        title = QLabel("Normering")
        title.setObjectName("pageTitle")
        self.level_filter = QComboBox()
        self.level_filter.currentIndexChanged.connect(self.refresh)
        self.grade_filter = QComboBox()
        self.grade_filter.currentIndexChanged.connect(self.refresh)
        self.test = QComboBox()
        self.test.setMinimumWidth(320)
        self.test.currentIndexChanged.connect(self.load_dashboard)
        selector.addWidget(title)
        selector.addStretch()
        selector.addWidget(QLabel("Niveau"))
        selector.addWidget(self.level_filter)
        selector.addWidget(QLabel("Jaarlaag"))
        selector.addWidget(self.grade_filter)
        selector.addWidget(QLabel("Toets"))
        selector.addWidget(self.test)
        layout.addLayout(selector)
        if _can_use_webengine():
            self.dashboard = QWebEngineView()
            self.channel = QWebChannel(self.dashboard.page())
            self.bridge = NormingBridge(self)
            self.channel.registerObject("normingBridge", self.bridge)
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
                "<h2>Interactief normeringsdashboard</h2>"
                "<p>Voor de grafische normeringsmodule is PySide6 WebEngine nodig.</p>"
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

    def help_content(self) -> dict[str, object]:
        return {
            "title": "Normering",
            "intro": "Met normering zet u behaalde punten om in cijfers. Dit scherm laat direct zien wat een gekozen norm doet met de resultaten.",
            "steps": [
                {
                    "title": "Eerst de toets selecteren",
                    "text": "Normeren kan pas als er een toets met ingevoerde resultaten is gekozen. Filters op niveau en jaarlaag helpen de juiste toets te vinden.",
                    "action": "Kies de toets bovenaan. Controleer of u de juiste naam en doelgroep ziet.",
                    "tip": "Vul resultaten zo volledig mogelijk in voordat u een definitieve normering vastlegt.",
                },
                {
                    "title": "Een normeringsmethode kiezen",
                    "text": "Links kiest u de methode, zoals N-term, cesuur of een vereiste percentage goed voor een 5,5. De instellingen bepalen de cijferomzetting.",
                    "action": "Selecteer een methode en wijzig de invoervelden of schuifregelaars totdat de gewenste voldoendegrens ontstaat.",
                    "tip": "De voldoendegrens vertelt vanaf hoeveel punten een leerling een 5,5 haalt.",
                },
                {
                    "title": "De grafieken lezen",
                    "text": "In de cijferverdeling staat iedere leerling als bolletje: groen is voldoende en rood onvoldoende. Het histogram toont hoeveel leerlingen een bepaalde ruwe score behaalden.",
                    "action": "Bekijk of de cijferverdeling aansluit bij uw beoordeling van de toetsmoeilijkheid.",
                    "tip": "Met Dashboardzoom maakt u de hele weergave groter of kleiner. De losse grafiekzoom blijft bewust uit, zodat u niet per ongeluk in een grafiek vastzit.",
                },
                {
                    "title": "Deelnemers en export",
                    "text": "De tabel onderaan toont per leerling score, percentage goed, cijfer en status. U kunt deze sorteren en exporteren.",
                    "action": "Controleer enkele leerlingen handmatig en gebruik daarna de PDF- of Excel-export wanneer nodig.",
                    "tip": "Cijfers zijn pas definitief nadat u de normering vaststelt.",
                },
                {
                    "title": "Normering vaststellen of opheffen",
                    "text": "Een vastgestelde normering wordt opgeslagen en maakt cijfergerelateerde onderdelen in rapportages beschikbaar.",
                    "action": "Klik op 'Normering vaststellen' als de norm akkoord is. Gebruik 'Vastgestelde normering opheffen' wanneer u opnieuw wilt normeren.",
                    "tip": "Wanneer nog geen norm is vastgesteld, toont de analyse bewust geen definitieve cijferstatistieken.",
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
        levels = sorted({row["level"] for row in filter_values if row["level"]}, key=str.lower)
        grades = sorted({row["grade_year"] for row in filter_values if row["grade_year"]}, key=str.lower)
        for level in levels:
            self.level_filter.addItem(level, level)
        for grade in grades:
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
            position = self.test.findData(selected_id)
            if position >= 0:
                self.test.setCurrentIndex(position)
            else:
                self.test.setCurrentIndex(0)
        else:
            self.test.setCurrentIndex(0)
        self.test.blockSignals(False)
        self.load_dashboard()

    def select_test(self, test_id: int) -> None:
        for combo in (self.level_filter, self.grade_filter):
            combo.blockSignals(True)
            if combo.count():
                combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.refresh()
        position = self.test.findData(test_id)
        if position >= 0:
            self.test.setCurrentIndex(position)
        else:
            QMessageBox.warning(
                self,
                "Toets niet gevonden",
                "De geselecteerde toets kon niet in normering worden geopend. Controleer het schooljaar.",
            )

    def load_dashboard(self) -> None:
        test_id = self.test.currentData()
        if test_id is None:
            if QWebEngineView is not None and isinstance(self.dashboard, QWebEngineView):
                self.dashboard.setHtml(
                    "<style>body{font:14px 'Segoe UI';background:#f7f8fc;color:#66748e;padding:40px}</style>"
                    "<h2>Kies een toets om te normeren</h2>"
                    "<p>Na de keuze verschijnen de scoreverdeling, cijfercurve en deelnemerstabel.</p>"
                )
            return
        if QWebEngineView is None or not isinstance(self.dashboard, QWebEngineView):
            return
        try:
            data = dashboard_data(self.database, test_id)
            data["is_finalized"] = has_active_normalization(self.database, test_id)
            settings = load_normalization(self.database, test_id)
            asset_directory = Path(__file__).parent / "assets"
            html_content = build_norming_dashboard_html(data, settings, "plotly-2.35.2.min.js")
            self.dashboard.setHtml(
                html_content,
                QUrl.fromLocalFile(str(asset_directory.resolve()) + "/"),
            )
            self.set_dashboard_zoom(self.dashboard_zoom)
        except Exception as error:
            self.dashboard.setHtml(f"<p>Het normeringsdashboard kon niet worden geladen: {html.escape(str(error))}</p>")












class SubjectWorkspace(QWidget):
    back_to_start = Signal()

    def __init__(self, database: SubjectDatabase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 8)
        root.setSpacing(8)
        header_frame = QFrame()
        header_frame.setObjectName("subjectHeader")
        header = QHBoxLayout(header_frame)
        header.setContentsMargins(8, 4, 8, 4)
        header.setSpacing(8)
        subject = QLabel(database.meta("subject_name", database.path.stem))
        subject.setObjectName("subjectTitle")
        self.years = QComboBox()
        self.years.setFixedHeight(32)
        self.years.setMinimumWidth(120)
        self.years.setMaximumWidth(150)
        self.years.currentIndexChanged.connect(self.change_year)
        add_year = QPushButton("Schooljaar toevoegen")
        compact_action_button(add_year, width=150)
        add_year.clicked.connect(self.add_year)
        backup = QPushButton("Back-up maken")
        compact_action_button(backup, width=120)
        backup.clicked.connect(self.make_backup)
        self.help_button = QPushButton("Help")
        compact_action_button(self.help_button, "Help bij dit scherm", width=78)
        self.help_button.clicked.connect(self.show_current_help)
        close = QPushButton("Sluiten")
        compact_action_button(close, "Vak sluiten", width=82)
        close.clicked.connect(self.back_to_start.emit)
        header.addWidget(subject)
        header.addStretch()
        header.addWidget(QLabel("Schooljaar"))
        header.addWidget(self.years)
        header.addWidget(add_year)
        header.addWidget(backup)
        header.addWidget(self.help_button)
        header.addWidget(close)
        root.addWidget(header_frame)
        body = QHBoxLayout()
        navigation = QVBoxLayout()
        nav_panel = QWidget()
        nav_panel.setLayout(navigation)
        nav_panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        nav_panel.setMinimumWidth(180)
        nav_panel.setMaximumWidth(260)
        self.pages_stack = QStackedWidget()
        self.pages_stack.currentChanged.connect(self.page_changed)
        self.pages_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pages: list[Page] = []
        self.page_labels: list[str] = []
        self.nav_buttons: list[QPushButton] = []
        for label, page_type in [
            ("Dashboard", DashboardPage),
            ("Klassen && Leerlingen", ClassesStudentsPage),
            ("Toetsen", TestsPage),
            ("Vragenoverzicht", MatrixPage),
            ("Resultateninvoer", ResultsPage),
            ("Normering", NormingPage),
            ("Toetsanalyse", AnalysisPage),
            ("Ontwikkelanalyse", DevelopmentAnalysisPage),
            ("Eigenschappenanalyse", StudentAttributeAnalysisPage),
            ("Vraagdatabase", QuestionDatabasePage),
            ("Taxonomieën &&\nVraagclassificaties", TaxonomiesClassificationsPage),
            ("Geavanceerde instellingen", AdvancedSettingsPage),
        ]:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setMinimumHeight(44 if "\n" in label else 36)
            index = len(self.pages)
            button.clicked.connect(lambda checked=False, i=index: self.show_page(i))
            navigation.addWidget(button)
            page = page_type(database, None)
            page.changed.connect(self.refresh_all)
            if isinstance(page, TestsPage):
                page.open_test_page.connect(self.open_test_page)
            self.page_labels.append(label.replace("&&", "&").replace("\n", " "))
            self.nav_buttons.append(button)
            self.pages.append(page)
            self.pages_stack.addWidget(page)
        navigation.addStretch()
        body.addWidget(nav_panel)
        body.addWidget(self.pages_stack, 1)
        body.setStretch(0, 0)
        body.setStretch(1, 1)
        root.addLayout(body, 1)
        self.reload_years()
        self.update_navigation_visibility()

    def reload_years(self) -> None:
        current_id = self.years.currentData()
        self.years.blockSignals(True)
        self.years.clear()
        years = self.database.rows("SELECT id, name, is_active FROM school_years ORDER BY name DESC")
        selected = 0
        for index, year in enumerate(years):
            self.years.addItem(year["name"], year["id"])
            if year["id"] == current_id or (current_id is None and year["is_active"]):
                selected = index
        self.years.setCurrentIndex(selected)
        self.years.blockSignals(False)
        self.change_year()

    def change_year(self) -> None:
        for page in self.pages:
            page.set_year(self.years.currentData())

    def refresh_all(self) -> None:
        for page in self.pages:
            if isinstance(page, StudentsPage):
                page.reload_filters()
            page.refresh()
        self.update_navigation_visibility()

    def show_page(self, index: int) -> None:
        self.pages_stack.setCurrentIndex(index)

    def open_test_page(self, page_label: str, test_id: int) -> None:
        for index, label in enumerate(self.page_labels):
            if label != page_label:
                continue
            self.show_page(index)
            page = self.pages[index]
            selector = getattr(page, "select_test", None)
            if callable(selector):
                selector(test_id)
            return
        QMessageBox.warning(self, "Pagina niet gevonden", f"Het menu '{page_label}' kon niet worden geopend.")

    def page_changed(self, index: int) -> None:
        if 0 <= index < len(self.pages):
            self.pages[index].on_activated()

    def update_navigation_visibility(self) -> None:
        question_database_visible = question_database_enabled(self.database)
        development_analysis_visible = development_analysis_enabled(self.database)
        student_attribute_analysis_visible = student_attribute_analysis_enabled(self.database)
        for index, label in enumerate(self.page_labels):
            if label == "Vraagdatabase":
                self.nav_buttons[index].setVisible(question_database_visible)
                if not question_database_visible and self.pages_stack.currentIndex() == index:
                    self.show_page(0)
            if label == "Ontwikkelanalyse":
                self.nav_buttons[index].setVisible(development_analysis_visible)
                if not development_analysis_visible and self.pages_stack.currentIndex() == index:
                    self.show_page(0)
            if label == "Eigenschappenanalyse":
                self.nav_buttons[index].setVisible(student_attribute_analysis_visible)
                if not student_attribute_analysis_visible and self.pages_stack.currentIndex() == index:
                    self.show_page(0)

    def show_current_help(self) -> None:
        index = self.pages_stack.currentIndex()
        if 0 <= index < len(self.pages):
            self.pages[index].show_help_wizard()

    def add_year(self) -> None:
        dialog = FormDialog("Schooljaar toevoegen", self)
        year = QLineEdit()
        dialog.form.addRow("Schooljaar *", year)
        if dialog.exec() == QDialog.DialogCode.Accepted and year.text().strip():
            self.database.add_school_year(year.text().strip(), active=False)
            self.reload_years()

    def make_backup(self) -> None:
        target = self.database.backup(automatic=False)
        QMessageBox.information(self, "Back-up gemaakt", f"Back-up opgeslagen als:\n{target.name}")


class StartPage(QWidget):
    new_subject = Signal()
    open_subject = Signal()
    last_subject = Signal()
    restore_backup = Signal()

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        outer = QVBoxLayout(self)
        outer.addStretch()
        panel = QFrame()
        panel.setObjectName("startPanel")
        panel.setMaximumWidth(760)
        self.panel = panel
        layout = QVBoxLayout(panel)
        self.banner = QLabel()
        self.banner.setObjectName("brandBanner")
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setMinimumHeight(170)
        layout.addWidget(self.banner)
        new_button = QPushButton("Nieuw vak aanmaken")
        new_button.clicked.connect(self.new_subject.emit)
        open_button = QPushButton("Bestaand vak openen")
        open_button.clicked.connect(self.open_subject.emit)
        self.last_button = QPushButton("Laatste vak openen")
        self.last_button.clicked.connect(self.last_subject.emit)
        restore_button = QPushButton("Back-up terugzetten")
        restore_button.clicked.connect(self.restore_backup.emit)
        help_button = QPushButton("Help bij dit scherm")
        help_button.clicked.connect(self.show_help_wizard)
        layout.addWidget(new_button)
        layout.addWidget(open_button)
        layout.addWidget(self.last_button)
        layout.addWidget(restore_button)
        layout.addWidget(help_button)
        self.refresh()
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(panel)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch()
        self.update_banner()

    def refresh(self) -> None:
        last = self.settings.value("last_database", "")
        self.last_button.setEnabled(bool(last) and Path(str(last)).exists())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_banner()

    def update_banner(self) -> None:
        available_width = max(460, min(700, self.panel.width() - 32))
        self.banner.setPixmap(build_brand_banner(available_width, 182))

    def show_help_wizard(self) -> None:
        title = "Startscherm"
        steps = _enrich_help_steps(title, [
            {
                "title": "Nieuw vak aanmaken",
                "text": "Een vakbestand is de lokale database waarin alle schooljaren, leerlingen, toetsen en analyses voor één vak worden bewaard.",
                "action": "Klik op 'Nieuw vak aanmaken', voer de vaknaam en het eerste schooljaar in en kies waar het bestand wordt opgeslagen.",
                "tip": "Gebruik één database per vak, bijvoorbeeld één voor Natuurkunde en één voor Scheikunde.",
            },
            {
                "title": "Een bestaand vak openen",
                "text": "Heeft u al gewerkt in het programma, dan kunt u uw bestaande database opnieuw openen.",
                "action": "Klik op 'Bestaand vak openen' of gebruik 'Laatste vak openen' om direct verder te gaan.",
                "tip": "Het programma bewaart uw gegevens lokaal op uw eigen computer.",
            },
            {
                "title": "Een back-up terugzetten",
                "text": "Met een back-up herstelt u een eerder opgeslagen kopie van een vakdatabase.",
                "action": "Klik op 'Back-up terugzetten', kies het back-upbestand en sla het herstelde bestand onder een nieuwe naam op.",
                "tip": "Gebruik een teruggezette database alleen nadat u gecontroleerd heeft dat de gewenste gegevens aanwezig zijn.",
            },
            {
                "title": "Na het openen beginnen",
                "text": "In een nieuw vak begint u met groepen en leerlingen, daarna maakt u toetsen en vragen aan.",
                "action": "Open het vak en volg daarna de Help bij dit scherm-knop op iedere pagina voor begeleiding.",
                "tip": "De meest gebruikte volgorde is: Klassen, Leerlingen, Toetsen, Vragenoverzicht, Resultateninvoer, Normering, Toetsanalyse.",
            },
        ])
        HelpWizardDialog(
            title,
            "Vanaf dit scherm opent u een bestaand vak of maakt u een nieuw vakbestand voor uw analyses.",
            steps,
            faq=_build_help_faq(title, steps),
            screen_preview=self.grab(),
            parent=self,
        ).exec()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"ToetsVizier {APP_VERSION} ({BRAND_COPYRIGHT})")
        self.setWindowIcon(brand_app_icon())
        self.setMinimumSize(980, 640)
        self.resize(1280, 800)
        self.settings = QSettings("ToetsAnalyse", "ToetsAnalyse")
        self.database: SubjectDatabase | None = None
        self.update_thread: UpdateCheckThread | None = None
        self.stack = QStackedWidget()
        self.start = StartPage(self.settings)
        self.start.new_subject.connect(self.create_subject)
        self.start.open_subject.connect(self.choose_subject)
        self.start.last_subject.connect(self.open_last_subject)
        self.start.restore_backup.connect(self.restore_backup)
        self.stack.addWidget(self.start)
        self.setCentralWidget(self.stack)
        geometry = self.settings.value("window_geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.showMaximized()
        QTimer.singleShot(1400, self.check_updates_on_start)

    def check_updates_on_start(self) -> None:
        if not settings_bool(self.settings, UPDATE_AUTO_CHECK_KEY, False):
            return
        manifest_url = update_manifest_url_from_settings(self.settings)
        if not manifest_url or (self.update_thread and self.update_thread.isRunning()):
            return
        self.update_thread = UpdateCheckThread(manifest_url, APP_VERSION, 8, self)
        self.update_thread.result_ready.connect(
            lambda result: show_update_result(self, result, silent_when_current=True)
        )
        self.update_thread.finished.connect(self.finish_start_update_check)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.start()

    def finish_start_update_check(self) -> None:
        self.update_thread = None

    def create_subject(self) -> None:
        dialog = NewSubjectDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        default_path = DATA_DIR / f"{slug(dialog.subject.text())}.db"
        selected, _ = QFileDialog.getSaveFileName(
            self, "Vakdatabase opslaan", str(default_path), "SQLite-database (*.db)"
        )
        if not selected:
            return
        path = Path(selected)
        if path.exists():
            QMessageBox.warning(self, "Bestand bestaat al", "Kies een nieuwe bestandsnaam of open het bestaande vak.")
            return
        database = SubjectDatabase.create(path, dialog.subject.text(), dialog.school_year.text())
        self.show_subject(database)

    def choose_subject(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Vakdatabase openen", str(DATA_DIR), "SQLite-database (*.db)"
        )
        if selected:
            self.open_subject(Path(selected))

    def open_last_subject(self) -> None:
        last = Path(str(self.settings.value("last_database", "")))
        if last.exists():
            self.open_subject(last)
        else:
            self.start.refresh()

    def restore_backup(self) -> None:
        from .paths import BACKUP_DIR

        source, _ = QFileDialog.getOpenFileName(
            self, "Back-up selecteren", str(BACKUP_DIR), "SQLite-database (*.db)"
        )
        if not source:
            return
        default_target = DATA_DIR / Path(source).name.replace("-", "_hersteld_", 1)
        target, _ = QFileDialog.getSaveFileName(
            self, "Herstelde vakdatabase opslaan", str(default_target), "SQLite-database (*.db)"
        )
        if not target:
            return
        if Path(target).exists():
            QMessageBox.warning(self, "Bestand bestaat al", "Kies een nieuwe bestandsnaam voor de herstelde database.")
            return
        shutil.copy2(source, target)
        self.open_subject(Path(target))

    def open_subject(self, path: Path) -> None:
        try:
            database = SubjectDatabase.open(path)
        except Exception as error:
            log_exception("Database kon niet worden geopend.")
            QMessageBox.critical(self, "Database kan niet worden geopend", str(error))
            return
        self.show_subject(database)

    def show_subject(self, database: SubjectDatabase) -> None:
        if self.database:
            self.database.close()
        self.database = database
        self.settings.setValue("last_database", str(database.path))
        workspace = SubjectWorkspace(database)
        workspace.back_to_start.connect(self.show_start)
        if self.stack.count() > 1:
            old = self.stack.widget(1)
            self.stack.removeWidget(old)
            old.deleteLater()
        self.stack.addWidget(workspace)
        self.stack.setCurrentWidget(workspace)

    def show_start(self) -> None:
        if self.database:
            try:
                self.database.backup(automatic=True)
            except Exception:
                log_exception("Automatische back-up bij sluiten van vak is mislukt.")
            self.database.close()
            self.database = None
        self.start.refresh()
        self.stack.setCurrentWidget(self.start)

    def closeEvent(self, event) -> None:
        self.settings.setValue("window_geometry", self.saveGeometry())
        if self.database:
            try:
                self.database.backup(automatic=True)
            except Exception:
                log_exception("Automatische back-up bij afsluiten is mislukt.")
            self.database.close()
        super().closeEvent(event)


STYLESHEET = """
QWidget {
    color: #172538;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QWidget {
    background: #f4f7fb;
}
QPushButton {
    background: #2463eb;
    border: none;
    border-radius: 7px;
    color: white;
    padding: 8px 14px;
    min-height: 36px;
}
QPushButton:hover { background: #164fc9; }
QPushButton:disabled { background: #b6c4df; }
QPushButton#primaryButton {
    background: #2463eb;
    color: white;
}
QPushButton#secondaryButton, QPushButton#ghostButton {
    background: #ffffff;
    border: 1px solid #d6dfec;
    color: #102340;
}
QPushButton#secondaryButton:hover, QPushButton#ghostButton:hover {
    background: #edf3fc;
}
QPushButton#dangerButton {
    background: #ffffff;
    border: 1px solid #f3b8b8;
    color: #b42318;
}
QPushButton#dangerButton:hover {
    background: #fff1f1;
}
QPushButton#navButton {
    min-width: 130px;
    text-align: left;
    background: #ffffff;
    color: #172538;
}
QPushButton#navButton:hover { background: #e5edfd; }
QPushButton#helpSecondaryButton {
    background: #ffffff;
    border: 1px solid #d6dfec;
    color: #31445f;
}
QPushButton#helpSecondaryButton:hover { background: #edf3fc; }
QFrame#startPanel, QFrame#dashboardCard, QFrame#panel, QLabel#panel,
QFrame#filterCard, QFrame#emptyState, QFrame#actionBar {
    background: #ffffff;
    border: 1px solid #e3e9f2;
    border-radius: 12px;
    padding: 16px;
}
QFrame#subjectHeader {
    background: #f4f7fb;
    border: none;
    padding: 0;
}
QFrame#actionBar {
    background: #f8fbff;
    padding: 8px;
}
QFrame#filterCard {
    padding: 8px;
}
QFrame#zoomBar {
    background: #ffffff;
    border: 1px solid #dbe5f1;
    border-radius: 10px;
    padding: 2px;
}
QFrame#zoomBar QPushButton {
    min-height: 24px;
    padding: 2px 8px;
    border-radius: 7px;
}
QLabel#zoomBarTitle {
    background: transparent;
    color: #5d6b82;
    font-size: 8.5pt;
    font-weight: 600;
    padding: 0 4px 0 2px;
}
QLabel#zoomBarValue {
    background: transparent;
    color: #102340;
    font-size: 9pt;
    font-weight: 700;
    padding: 0 4px;
}
QLabel#heroTitle { font-size: 28pt; font-weight: 700; color: #102340; }
QLabel#subjectTitle { font-size: 15pt; font-weight: 650; color: #102340; padding-right: 10px; }
QLabel#pageTitle { font-size: 18pt; font-weight: 650; padding-bottom: 8px; }
QLabel#pageSubtitle {
    color: #5e718d;
    font-size: 10.5pt;
}
QLabel#filterLabel {
    color: #31445f;
    font-size: 9.5pt;
    font-weight: 600;
}
QLabel#emptyStateText {
    color: #536782;
}
QLabel#infoBanner {
    background: #f3f7ff;
    border: 1px solid #d8e4ff;
    border-radius: 10px;
    padding: 12px;
    color: #244061;
}
QLabel#warningBanner {
    background: #fff8ed;
    border: 1px solid #f0dcc0;
    border-radius: 10px;
    padding: 12px;
    color: #5c3d10;
}
QLabel#cardValue { font-size: 27pt; font-weight: 700; color: #2463eb; }
QLabel#brandBanner {
    background: #ffffff;
    border: 1px solid #dce6f2;
    border-radius: 14px;
    padding: 4px;
}
QLabel#copyrightLabel {
    color: #5e718d;
    font-size: 9pt;
    font-weight: 600;
    padding-left: 8px;
    padding-right: 8px;
}
QLabel#helpSubtitle {
    color: #5c6f8b;
    font-size: 10pt;
}
QLabel#helpMarker {
    color: #2463eb;
    font-size: 9pt;
    font-weight: 700;
}
QLabel#helpStepTitle {
    color: #102340;
    font-size: 17pt;
    font-weight: 650;
}
QLabel#helpDescription {
    color: #31445f;
    font-size: 11pt;
}
QLabel#helpCardTitle {
    color: #102340;
    font-weight: 650;
}
QLabel#helpProgress {
    color: #5c6f8b;
    font-weight: 600;
}
QListWidget#helpSteps {
    background: #f6f8fb;
    border: 1px solid #e3e9f2;
    border-radius: 12px;
    padding: 8px;
}
QListWidget#helpSteps::item {
    border-radius: 8px;
    color: #435672;
    padding: 12px 8px;
}
QListWidget#helpSteps::item:selected {
    background: #e7efff;
    color: #174fc7;
    font-weight: 600;
}
QFrame#helpImageCard {
    background: #f6f8fb;
    border: 1px solid #e3e9f2;
    border-radius: 12px;
    padding: 8px;
}
QFrame#helpActionCard {
    background: #eef5ff;
    border: 1px solid #d5e3fc;
    border-radius: 12px;
    padding: 8px;
}
QFrame#helpWhyCard {
    background: #f8fafc;
    border: 1px solid #dfe7f1;
    border-radius: 12px;
    padding: 8px;
}
QFrame#helpResultCard {
    background: #f3f8ff;
    border: 1px solid #d9e8ff;
    border-radius: 12px;
    padding: 8px;
}
QFrame#helpChecklistCard {
    background: #f6fbf8;
    border: 1px solid #d8eadf;
    border-radius: 12px;
    padding: 8px;
}
QFrame#helpWarningCard {
    background: #fff8ed;
    border: 1px solid #f0dcc0;
    border-radius: 12px;
    padding: 8px;
}
QFrame#helpTipCard {
    background: #f2faf5;
    border: 1px solid #d9ebdf;
    border-radius: 12px;
    padding: 8px;
}
QFrame#helpNextCard {
    background: #f6f3ff;
    border: 1px solid #ded7fb;
    border-radius: 12px;
    padding: 8px;
}
QFrame#helpFaqCard {
    background: #ffffff;
    border: 1px solid #dfe7f1;
    border-radius: 12px;
    padding: 10px;
}
QTabWidget#helpTabs::pane {
    border: 1px solid #e3e9f2;
    border-radius: 12px;
    background: #ffffff;
    top: -1px;
}
QTabWidget#helpTabs QTabBar::tab {
    background: #f6f8fb;
    border: 1px solid #e3e9f2;
    border-bottom: none;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    padding: 9px 18px;
    color: #435672;
}
QTabWidget#helpTabs QTabBar::tab:selected {
    background: #ffffff;
    color: #174fc7;
    font-weight: 650;
}
QLineEdit, QComboBox, QDateEdit, QSpinBox, QTableWidget, QListWidget {
    background: white;
    border: 1px solid #d6dfec;
    border-radius: 6px;
    padding: 5px;
}
QPushButton {
    min-height: 34px;
    padding-left: 14px;
    padding-right: 14px;
}

QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit {
    min-height: 34px;
}

QHeaderView::section {
    background: #eaf0fb;
    border: none;
    padding: 8px;
    font-weight: 600;
}
"""


def run() -> int:
    ensure_app_directories()
    configure_logging()
    install_exception_hook()
    if sys.platform.startswith("win"):
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TomSommers.ToetsVizier")
        except Exception:
            pass
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName("ToetsVizier")
    app.setOrganizationName("Tom Sommers")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(brand_app_icon())
    window = MainWindow()
    window.show()
    return app.exec()
