from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap

_APP_BRAND_ICON: QIcon | None = None


def _paint_brand_emblem(painter: QPainter, size: int, *, dark_background: bool = False) -> None:
    primary = QColor("#1A3C63")
    cyan = QColor("#3FCFCF")
    green = QColor("#66CC66")
    card_bg = QColor("#F0F6FD") if not dark_background else QColor("#0F2C47")
    border = QColor("#D4E2F2") if not dark_background else QColor("#1E4A73")
    stroke = max(1, int(size * 0.048))
    pad = max(2, int(size * 0.12))
    painter.setPen(QPen(border, 1))
    painter.setBrush(card_bg)
    painter.drawRoundedRect(1, 1, size - 2, size - 2, size * 0.18, size * 0.18)

    chart_left = int(size * 0.54)
    chart_top = int(size * 0.3)
    chart_width = int(size * 0.29)
    chart_height = int(size * 0.46)
    painter.setPen(QPen(primary, max(1, stroke - 1)))
    painter.drawRoundedRect(chart_left, chart_top, chart_width, chart_height, 4, 4)

    bar_width = max(2, int(size * 0.055))
    bar_gap = max(2, int(size * 0.03))
    bar_bottom = int(size * 0.72)
    for index, bar_height in enumerate((int(size * 0.12), int(size * 0.2), int(size * 0.29))):
        x = chart_left + max(4, int(size * 0.05)) + index * (bar_width + bar_gap)
        y = bar_bottom - bar_height
        painter.fillRect(x, y, bar_width, bar_height, cyan if index < 2 else green)

    circle_left = pad
    circle_top = pad
    circle_size = int(size * 0.62)
    painter.setPen(QPen(primary, stroke, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(circle_left, circle_top, circle_size, circle_size)

    center_x = circle_left + circle_size // 2
    center_y = circle_top + circle_size // 2
    cross = int(size * 0.09)
    painter.drawLine(center_x, circle_top - cross // 2, center_x, circle_top + cross)
    painter.drawLine(center_x, circle_top + circle_size - cross, center_x, circle_top + circle_size + cross // 2)
    painter.drawLine(circle_left - cross // 2, center_y, circle_left + cross, center_y)
    painter.drawLine(circle_left + circle_size - cross, center_y, circle_left + circle_size + cross // 2, center_y)

    painter.setPen(QPen(green, max(2, stroke)))
    points = [
        (int(size * 0.24), int(size * 0.61)),
        (int(size * 0.34), int(size * 0.49)),
        (int(size * 0.44), int(size * 0.53)),
        (int(size * 0.56), int(size * 0.4)),
        (int(size * 0.68), int(size * 0.31)),
    ]
    for start, end in zip(points, points[1:]):
        painter.drawLine(start[0], start[1], end[0], end[1])
    painter.drawLine(points[-1][0], points[-1][1], points[-1][0] - int(size * 0.05), points[-1][1])
    painter.drawLine(points[-1][0], points[-1][1], points[-1][0], points[-1][1] + int(size * 0.05))


def draw_brand_emblem(size: int, dark_background: bool = False) -> QPixmap:
    size = max(24, size)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _paint_brand_emblem(painter, size, dark_background=dark_background)
    painter.end()
    return pixmap


def brand_app_icon() -> QIcon:
    global _APP_BRAND_ICON
    if _APP_BRAND_ICON is not None:
        return _APP_BRAND_ICON
    icon = QIcon()
    for icon_size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(draw_brand_emblem(icon_size))
    _APP_BRAND_ICON = icon
    return _APP_BRAND_ICON


def write_windows_icon(path: Path | str, size: int = 256) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _paint_brand_emblem(painter, size)
    painter.end()
    if not image.save(str(target)):
        raise RuntimeError(f"Kon Windows-icoon niet schrijven: {target}")
    return target
