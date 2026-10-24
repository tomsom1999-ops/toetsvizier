"""Small native controls shared by the simple mode."""
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import (QLayout, QDialog, QDialogButtonBox, QInputDialog,
                              QMessageBox)


class WrappingLayout(QLayout):
    def __init__(self, spacing=6):
        super().__init__()
        self.items = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item):
        self.items.append(item)

    def count(self):
        return len(self.items)

    def itemAt(self, index):
        return self.items[index] if 0 <= index < len(self.items) else None

    def takeAt(self, index):
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self.arrange(QRect(0, 0, width, 0), True)

    def minimumSize(self):
        size = QSize()
        for item in self.items:
            if not item.isEmpty():
                size = size.expandedTo(item.minimumSize())
        return size

    def sizeHint(self):
        return self.minimumSize()

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.arrange(rect, False)

    def arrange(self, rect, measure):
        x, y, height = rect.x(), rect.y(), 0
        for item in self.items:
            if item.isEmpty():
                continue
            size = item.sizeHint()
            width = min(size.width(), rect.width())
            if item.hasHeightForWidth():
                size.setHeight(item.heightForWidth(width))
            if x > rect.x() and x + width > rect.right() + 1:
                x, y, height = rect.x(), y + height + self.spacing(), 0
            if not measure:
                item.setGeometry(QRect(x, y, width, size.height()))
            x += width + self.spacing()
            height = max(height, size.height())
        return y - rect.y() + height


def fit_table_controls(table):
    for row in range(table.rowCount()):
        height = max(38, table.fontMetrics().height() + 16)
        for column in range(table.columnCount()):
            widget = table.cellWidget(row, column)
            if widget is not None:
                widget.ensurePolished()
                height = max(height, widget.sizeHint().height() + 8, widget.minimumSizeHint().height() + 8)
        table.setRowHeight(row, height)
    table.resizeColumnsToContents()


def dutch_buttons(box):
    from .ui_helpers import set_button_role
    names = {QDialogButtonBox.StandardButton.Save: "Opslaan", QDialogButtonBox.StandardButton.Cancel: "Annuleren",
             QDialogButtonBox.StandardButton.Ok: "OK", QDialogButtonBox.StandardButton.Close: "Sluiten"}
    for role, label in names.items():
        if box.button(role):
            box.button(role).setText(label)
            set_button_role(box.button(role), 'secondary' if role in {
                QDialogButtonBox.StandardButton.Cancel, QDialogButtonBox.StandardButton.Close
            } else 'primary')


def question(parent, title, text, buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
             default=QMessageBox.StandardButton.No):
    box = QMessageBox(QMessageBox.Icon.Question, title, text, buttons, parent)
    for role, label in ((QMessageBox.StandardButton.Yes, "Ja"), (QMessageBox.StandardButton.No, "Nee"),
                        (QMessageBox.StandardButton.Save, "Opslaan"), (QMessageBox.StandardButton.Discard, "Niet opslaan"),
                        (QMessageBox.StandardButton.Cancel, "Annuleren")):
        if box.button(role):
            box.button(role).setText(label)
    box.setDefaultButton(default)
    return QMessageBox.StandardButton(box.exec())


def text_input(parent, title, label, value="", *, multiline=False, choices=None):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    dialog.setOkButtonText("Toepassen")
    dialog.setCancelButtonText("Annuleren")
    if choices is not None:
        dialog.setComboBoxItems(choices)
        dialog.setComboBoxEditable(False)
        value = value or choices[0]
    if multiline:
        dialog.setOption(QInputDialog.InputDialogOption.UsePlainTextEditForTextInput)
    dialog.setTextValue(value)
    return dialog.textValue() if dialog.exec() == QDialog.DialogCode.Accepted else None
