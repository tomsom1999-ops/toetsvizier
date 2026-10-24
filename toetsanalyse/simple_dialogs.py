from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout)

from .results import test_questions
from .simple_model import active_questions
from .simple_widgets import fit_table_controls, dutch_buttons, text_input


from .simple_help import InputIntroduction


class MultipleChoiceDialog(QDialog):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Meerkeuzevragen en antwoordsleutels")
        self.resize(660, 510)
        self.questions = active_questions(database)
        self.controls = {}
        layout = QVBoxLayout(self)
        note = QLabel("Vink een vraag aan om automatisch na te kijken. Kies de juiste antwoordletter. "
                      "Daarna typt u bij elke leerling de letter van het gekozen antwoord.\n\n"
                      "Niet aangevinkt? Dan vult u zelf het behaalde puntenaantal in, ook bij een meerkeuzevraag. "
                      "N blijft beschikbaar voor een niet-gemaakte vraag.")
        note.setWordWrap(True)
        layout.addWidget(note)
        table = QTableWidget(len(self.questions), 3)
        table.setHorizontalHeaderLabels(["Vraag", "Antwoordsleutel gebruiken", "Juiste antwoordletter"])
        for row, q in enumerate(self.questions):
            label = QTableWidgetItem(q["label"])
            label.setFlags(label.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row, 0, label)
            check = QCheckBox()
            check.setChecked(bool(q["is_multiple_choice"]))
            combo = QComboBox()
            combo.addItems([""] + list("ABCDEFGHIJKLMOPQRSTUVWXYZ"))
            combo.setCurrentText(q["multiple_choice_answer"] or "")
            combo.setEnabled(check.isChecked())
            check.toggled.connect(combo.setEnabled)
            table.setCellWidget(row, 1, check)
            table.setCellWidget(row, 2, combo)
            self.controls[q["id"]] = (check, combo)
        fit_table_controls(table)
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        dutch_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        if any(check.isChecked() and not combo.currentText() for check, combo in self.controls.values()):
            QMessageBox.warning(self, "Antwoordletter ontbreekt", "Kies bij elke aangevinkte vraag de juiste antwoordletter.")
            return
        super().accept()


class MetadataDialog(QDialog):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.questions = active_questions(database)
        self.definitions = []
        for row in database.rows("SELECT * FROM taxonomy_definitions ORDER BY id"):
            self.definitions.append({"name": row["name"], "standard": bool(row["is_standard"]),
                                     "values": [v["name"] for v in database.rows("SELECT name FROM taxonomy_values WHERE taxonomy_id=? ORDER BY sort_order,id", (row["id"],))]})
        self.selected = {(q["question_id"], q["definition"]): q["value"] for q in database.rows(
            "SELECT qtv.question_id,d.name AS definition,v.name AS value FROM question_taxonomy_values qtv "
            "JOIN taxonomy_definitions d ON d.id=qtv.taxonomy_id JOIN taxonomy_values v ON v.id=qtv.taxonomy_value_id")}
        self.setWindowTitle("Vragen indelen — optioneel")
        self.resize(940, 600)
        layout = QVBoxLayout(self)
        note = QLabel("RTTI, OBIT en Bloom zijn beschikbaar. U hoeft niet alle kolommen in te vullen. "
                      "Maak ook zelf een indeling en de categorieën daarbinnen. Hoofdstuk, paragraaf, leerdoel en "
                      "vraagstuk zijn voorbeelden: u kiest zelf de naam en de inhoud.")
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        add = QPushButton("Eigen indeling toevoegen")
        add.clicked.connect(self.add_distribution)
        edit = QPushButton("Categorieën van eigen indeling wijzigen")
        edit.clicked.connect(self.edit_distribution)
        actions.addWidget(add)
        actions.addWidget(edit)
        layout.addLayout(actions)
        self.table = QTableWidget()
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        dutch_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.build()

    def capture(self):
        for (qid, name), combo in getattr(self, "combos", {}).items():
            self.selected[qid, name] = combo.currentText() if combo.currentIndex() > 0 else ""

    def build(self):
        self.table.setColumnCount(len(self.definitions) + 1)
        self.table.setRowCount(len(self.questions))
        self.table.setHorizontalHeaderLabels(["Vraag"] + [d["name"] for d in self.definitions])
        self.combos = {}
        for row, q in enumerate(self.questions):
            cell = QTableWidgetItem(q["label"])
            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, cell)
            for col, definition in enumerate(self.definitions, 1):
                combo = QComboBox()
                combo.addItem("Niet ingedeeld")
                combo.addItems(definition["values"])
                position = combo.findText(self.selected.get((q["id"], definition["name"]), ""))
                combo.setCurrentIndex(max(0, position))
                self.table.setCellWidget(row, col, combo)
                self.combos[q["id"], definition["name"]] = combo
        fit_table_controls(self.table)

    def category_input(self, title, text=""):
        value = text_input(self, title, "Eén categorie per regel. U mag zelf namen kiezen.", text, multiline=True)
        if value is None:
            return None
        categories = [v.strip() for v in value.splitlines() if v.strip()]
        if not categories or len(set(categories)) != len(categories):
            QMessageBox.warning(self, "Categorieën", "Vul minstens één categorie in en gebruik elke naam één keer.")
            return None
        return categories

    def add_distribution(self):
        name = text_input(self, "Eigen indeling", "Naam van uw indeling (bijvoorbeeld hoofdstuk, paragraaf, leerdoel of vraagstuk)")
        if not name or not name.strip():
            return
        name = name.strip()
        if any(d["name"].casefold() == name.casefold() for d in self.definitions):
            QMessageBox.warning(self, "Naam bestaat al", "Kies een andere naam voor deze indeling.")
            return
        categories = self.category_input("Categorieën toevoegen")
        if categories:
            self.capture()
            self.definitions.append({"name": name, "standard": False, "values": categories})
            self.build()

    def edit_distribution(self):
        custom = [d for d in self.definitions if not d["standard"]]
        if not custom:
            QMessageBox.information(self, "Eigen indeling", "Voeg eerst een eigen indeling toe.")
            return
        name = text_input(self, "Indeling kiezen", "Welke categorieën wilt u wijzigen?", choices=[d["name"] for d in custom])
        if name is None:
            return
        definition = next(d for d in custom if d["name"] == name)
        categories = self.category_input("Categorieën wijzigen", "\n".join(definition["values"]))
        if categories:
            self.capture()
            definition["values"] = categories
            self.build()

    def apply(self):
        self.capture()
        connection = self.database.connection
        for q in self.questions:
            connection.execute("DELETE FROM question_taxonomy_values WHERE question_id=?", (q["id"],))
        for definition in self.definitions:
            connection.execute("INSERT OR IGNORE INTO taxonomy_definitions(name,is_standard) VALUES(?,?)", (definition["name"], int(definition["standard"])))
            tid = self.database.scalar("SELECT id FROM taxonomy_definitions WHERE name=?", (definition["name"],))
            connection.execute("INSERT OR IGNORE INTO test_taxonomy_selections VALUES(1,?)", (tid,))
            if not definition["standard"]:
                current = self.database.rows("SELECT id,name FROM taxonomy_values WHERE taxonomy_id=?", (tid,))
                for row in current:
                    if row["name"] not in definition["values"]:
                        connection.execute("DELETE FROM taxonomy_values WHERE id=?", (row["id"],))
            for index, value in enumerate(definition["values"]):
                connection.execute("INSERT OR IGNORE INTO taxonomy_values(taxonomy_id,name,sort_order) VALUES(?,?,?)", (tid, value, index))
            for q in self.questions:
                value = self.selected.get((q["id"], definition["name"]))
                if value in definition["values"]:
                    value_id = self.database.scalar("SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name=?", (tid, value))
                    connection.execute("INSERT INTO question_taxonomy_values VALUES(?,?,?)", (q["id"], tid, value_id))
