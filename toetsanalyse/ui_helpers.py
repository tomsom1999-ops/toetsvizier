from __future__ import annotations

import re

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QPolygon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionComboBox,
    QStylePainter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


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
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setStretchLastSection(False)
    table.setCornerButtonEnabled(False)


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
    widget.move(
        available.x() + (available.width() - width) // 2,
        available.y() + (available.height() - height) // 2,
    )
    if hasattr(widget, "setSizeGripEnabled"):
        widget.setSizeGripEnabled(True)


def compact_action_button(button: QPushButton, tooltip: str | None = None, width: int | None = None) -> QPushButton:
    button.setFixedHeight(34)
    if width is not None:
        button.setFixedWidth(width)
    button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    if tooltip:
        button.setToolTip(tooltip)
    return button


def set_button_role(button: QPushButton, role: str = "primary") -> QPushButton:
    names = {
        "primary": "primaryButton",
        "secondary": "secondaryButton",
        "danger": "dangerButton",
        "ghost": "ghostButton",
    }
    button.setObjectName(names.get(role, "primaryButton"))
    if role in {"secondary", "ghost"}:
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    return button


class DashboardZoomBar(QFrame):
    zoom_out_requested = Signal()
    zoom_reset_requested = Signal()
    zoom_in_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("zoomBar")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        label = QLabel("Zoom")
        label.setObjectName("zoomBarTitle")
        label.setFixedHeight(28)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("zoomBarValue")
        self.zoom_label.setMinimumWidth(42)
        self.zoom_label.setFixedHeight(28)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        zoom_out = set_button_role(QPushButton("-"), "secondary")
        zoom_reset = set_button_role(QPushButton("Reset"), "secondary")
        zoom_in = set_button_role(QPushButton("+"), "secondary")
        compact_action_button(zoom_out, "Dashboard kleiner weergeven", 30)
        compact_action_button(zoom_reset, "Dashboard terugzetten naar 100%", 54)
        compact_action_button(zoom_in, "Dashboard groter weergeven", 30)
        for button in (zoom_out, zoom_reset, zoom_in):
            button.setFixedHeight(28)
        zoom_out.clicked.connect(self.zoom_out_requested.emit)
        zoom_reset.clicked.connect(self.zoom_reset_requested.emit)
        zoom_in.clicked.connect(self.zoom_in_requested.emit)
        layout.addWidget(label)
        layout.addWidget(zoom_out)
        layout.addWidget(self.zoom_label)
        layout.addWidget(zoom_in)
        layout.addWidget(zoom_reset)

    def set_zoom_factor(self, factor: float) -> None:
        self.zoom_label.setText(f"{round(factor * 100):.0f}%")


def make_page_header(title: str, subtitle: str = "", actions: list[QPushButton] | None = None) -> QFrame:
    header = QFrame()
    header.setObjectName("pageHeader")
    layout = QVBoxLayout(header)
    layout.setContentsMargins(0, 0, 0, 4)
    layout.setSpacing(8)
    top_row = QHBoxLayout()
    top_row.setContentsMargins(0, 0, 0, 0)
    top_row.setSpacing(12)
    text_column = QVBoxLayout()
    text_column.setContentsMargins(0, 0, 0, 0)
    text_column.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    text_column.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        subtitle_label.setWordWrap(True)
        text_column.addWidget(subtitle_label)
    top_row.addLayout(text_column, 1)
    if actions and len(actions) <= 3:
        for action in actions:
            action.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            top_row.addWidget(action)
    layout.addLayout(top_row)
    if actions and len(actions) > 3:
        action_bar = QFrame()
        action_bar.setObjectName("actionBar")
        action_layout = QVBoxLayout(action_bar)
        action_layout.setContentsMargins(8, 6, 8, 6)
        action_layout.setSpacing(6)
        for start in range(0, len(actions), 4):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            for action in actions[start : start + 4]:
                action.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                row.addWidget(action)
            row.addStretch()
            action_layout.addLayout(row)
        layout.addWidget(action_bar)
    return header


class ResponsiveFilterCard(QFrame):
    def __init__(
        self,
        title: str | None = None,
        fields: list[tuple[str, QWidget]] | None = None,
        minimum_field_width: int = 230,
        maximum_columns: int = 4,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("filterCard")
        self.minimum_field_width = max(150, minimum_field_width)
        self.maximum_columns = max(1, maximum_columns)
        self.current_columns = 0
        self.field_widgets: list[QWidget] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 8, 10, 8)
        outer.setSpacing(6)
        if title:
            label = QLabel(f"<b>{title}</b>")
            outer.addWidget(label)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(6)
        outer.addLayout(self.grid)
        self.set_fields(fields or [])

    def set_fields(self, fields: list[tuple[str, QWidget]]) -> None:
        self.field_widgets = [make_filter_field(label, widget) for label, widget in fields]
        self.current_columns = 0
        self.reflow()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.reflow()

    def reflow(self) -> None:
        available_width = max(1, self.width() - 28)
        columns = max(1, min(self.maximum_columns, available_width // self.minimum_field_width))
        if columns == self.current_columns and self.grid.count() == len(self.field_widgets):
            return
        while self.grid.count():
            self.grid.takeAt(0)
        for index, widget in enumerate(self.field_widgets):
            row = index // columns
            column = index % columns
            self.grid.addWidget(widget, row, column)
        for column in range(self.maximum_columns):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        self.current_columns = columns


def make_responsive_filter_card(
    title: str,
    fields: list[tuple[str, QWidget]],
    minimum_field_width: int = 230,
    maximum_columns: int = 4,
) -> ResponsiveFilterCard:
    return ResponsiveFilterCard(title, fields, minimum_field_width, maximum_columns)


def make_filter_card(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("filterCard")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(10)
    if title:
        label = QLabel(f"<b>{title}</b>")
        layout.addWidget(label)
    return card, layout


def make_filter_field(label_text: str, widget: QWidget) -> QWidget:
    field = QWidget()
    field.setObjectName("filterField")
    field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    field.setMinimumWidth(0)
    layout = QVBoxLayout(field)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    label = QLabel(label_text)
    label.setObjectName("filterLabel")
    label.setToolTip(label_text)
    label.setWordWrap(False)
    layout.addWidget(label)
    widget.setMinimumWidth(0)
    layout.addWidget(widget)
    return field


def make_empty_state(title: str, text: str, action: QPushButton | None = None) -> QFrame:
    card = QFrame()
    card.setObjectName("emptyState")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(8)
    title_label = QLabel(f"<b>{title}</b>")
    title_label.setObjectName("emptyStateTitle")
    body = QLabel(text)
    body.setWordWrap(True)
    body.setObjectName("emptyStateText")
    layout.addWidget(title_label)
    layout.addWidget(body)
    if action is not None:
        row = QHBoxLayout()
        row.addWidget(action)
        row.addStretch()
        layout.addLayout(row)
    return card


def make_info_banner(text: str, kind: str = "info") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setObjectName(f"{kind}Banner")
    return label
