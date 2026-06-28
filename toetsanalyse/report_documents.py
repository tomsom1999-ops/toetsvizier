from __future__ import annotations

from PySide6.QtGui import QTextCursor, QTextDocument, QTextFormat
from PySide6.QtWidgets import QWidget


def formatted_report_document(html: str, parent: QWidget | None = None) -> QTextDocument:
    document = QTextDocument(parent)
    document.setHtml(html)
    cursor = QTextCursor(document)
    marker_ranges: list[tuple[int, int]] = []
    while True:
        cursor = document.find("[[PAGE_BREAK]]", cursor)
        if cursor.isNull():
            break
        marker_ranges.append((cursor.selectionStart(), cursor.selectionEnd()))
        target_block = cursor.block().next()
        while target_block.isValid() and not target_block.text().strip():
            target_block = target_block.next()
        if target_block.isValid():
            target_cursor = QTextCursor(target_block)
            block_format = target_cursor.blockFormat()
            block_format.setPageBreakPolicy(QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
            block_format.setTopMargin(0)
            block_format.setBottomMargin(0)
            target_cursor.setBlockFormat(block_format)
    for start, end in reversed(marker_ranges):
        marker_cursor = QTextCursor(document)
        marker_cursor.setPosition(start)
        marker_cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        marker_cursor.removeSelectedText()
    return document
