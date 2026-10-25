import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
                              QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget,
                              QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .results import test_questions, test_students
from .test_versions import assign_students, save_question_mapping, student_version, versions


class AlternativeMappingDialog(QDialog):
    def __init__(self, forms, existing, base_answer, parent=None, reference_version_id=None):
        super().__init__(parent)
        self.forms, self.existing, self.base_answer = forms, existing, base_answer
        self.option_maps = {}
        self.setWindowTitle("Dezelfde antwoordalternatieven koppelen")
        self.resize(700, 460)
        layout = QVBoxLayout(self)
        note = QLabel("Koppel antwoorden met dezelfde inhoud. Bijvoorbeeld: het antwoord dat in versie A "
                      "bij letter A staat, kan in versie B bij letter C staan. Kies die letters op dezelfde rij. "
                      "De juiste antwoordletter wordt automatisch afgeleid van de antwoordsleutel van de vraag.")
        note.setWordWrap(True)
        layout.addWidget(note)
        reference_row = QHBoxLayout()
        reference_row.addWidget(QLabel("Welke versie bepaalt de letters in de gezamenlijke analyse?"))
        self.reference = QComboBox()
        for vid,name in forms:
            self.reference.addItem(name,vid)
        position = self.reference.findData(reference_version_id)
        self.reference.setCurrentIndex(max(position,0))
        reference_row.addWidget(self.reference)
        layout.addLayout(reference_row)
        canonical = sorted({value for options in existing.values() for value in options.values()}) or list("ABCD")
        if base_answer and base_answer not in canonical:
            canonical.append(base_answer)
        self.options = QLineEdit(", ".join(canonical))
        line = QHBoxLayout()
        line.addWidget(QLabel("Letters bij de standaardvolgorde van de vraag"))
        line.addWidget(self.options)
        update = QPushButton("Tabel bijwerken")
        update.clicked.connect(self.rebuild)
        line.addWidget(update)
        layout.addLayout(line)
        self.table = QTableWidget()
        layout.addWidget(self.table)
        self.example = QLabel()
        self.example.setTextFormat(Qt.TextFormat.PlainText)
        self.example.setWordWrap(True)
        layout.addWidget(self.example)
        self.mapping_status = QLabel()
        self.mapping_status.setWordWrap(True)
        layout.addWidget(self.mapping_status)
        self.reference.currentIndexChanged.connect(self.update_example)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.use_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.use_button.setText("Koppeling gebruiken")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuleren")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.rebuild()

    def rebuild(self):
        previous = {(vid,canonical):combo.currentText() for (vid,canonical),combo in getattr(self,"combos",{}).items()}
        self.canonical = [value.strip().upper() for value in self.options.text().split(",")]
        if len(self.canonical) < 2 or len(set(self.canonical)) != len(self.canonical) or any(len(value) != 1 or not value.isascii() or not value.isalpha() for value in self.canonical):
            QMessageBox.warning(self,"Alternatieven","Vul minstens twee unieke letters in, gescheiden door komma's.")
            self.canonical = []
            self.use_button.setEnabled(False)
            return
        self.table.setRowCount(len(self.canonical))
        self.table.setColumnCount(len(self.forms) + 1)
        self.table.setHorizontalHeaderLabels(["Antwoord in standaardvolgorde"] + [f"Letter in versie {name}" for _,name in self.forms])
        self.combos = {}
        for row, canonical in enumerate(self.canonical):
            cell = QTableWidgetItem(canonical + (" — juist" if canonical == self.base_answer else ""))
            cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row,0,cell)
            for col,(vid,_) in enumerate(self.forms,1):
                combo = QComboBox()
                combo.addItems(self.canonical)
                option_map = self.existing.get(vid,{})
                letter = previous.get((vid,canonical),next((letter for letter,value in option_map.items() if value == canonical),canonical))
                combo.setCurrentText(letter)
                combo.currentTextChanged.connect(self.update_example)
                self.table.setCellWidget(row,col,combo)
                self.combos[vid,canonical] = combo
        self.table.resizeColumnsToContents()
        self.update_example()

    def update_example(self, *_):
        if not getattr(self,"canonical",None) or not hasattr(self,"combos"):
            return
        rows = []
        for canonical in self.canonical:
            letters = [f"{self.combos[vid,canonical].currentText()} in versie {name}" for vid,name in self.forms if (vid,canonical) in self.combos]
            rows.append(" = ".join(letters) + (" (juist antwoord)" if canonical == self.base_answer else ""))
        self.example.setText("Zo worden dezelfde antwoorden samengevoegd:\n" + "\n".join(rows) +
                             f"\nDe analyse toont de letters van versie {self.reference.currentText()}.")
        problems = []
        for vid,name in self.forms:
            letters = [self.combos[vid,canonical].currentText() for canonical in self.canonical if (vid,canonical) in self.combos]
            duplicates = sorted({letter for letter in letters if letters.count(letter)>1})
            if duplicates:
                problems.append(f"Versie {name}: letter {', '.join(duplicates)} wordt meer dan één keer gebruikt.")
        valid = not problems and self.base_answer in self.canonical and len(self.combos) == len(self.canonical)*len(self.forms)
        self.mapping_status.setText("\n".join(problems) if problems else "Elke antwoordletter is één keer gekoppeld." if valid else "Neem de standaard antwoordsleutel op in de letters.")
        self.use_button.setEnabled(valid)
        self.table.setHorizontalHeaderLabels(["Antwoord in standaardvolgorde"] +
            [f"Letter in versie {name}" + (" (leidend)" if vid == self.reference.currentData() else "") for vid,name in self.forms])

    def accept(self):
        if [value.strip().upper() for value in self.options.text().split(",")] != self.canonical:
            QMessageBox.warning(self,"Tabel bijwerken","Klik eerst op Tabel bijwerken om de gewijzigde basisalternatieven te gebruiken.")
            return
        if not self.canonical or self.base_answer not in self.canonical:
            QMessageBox.warning(self,"Antwoord ontbreekt","Neem de standaard antwoordsleutel op in de basisalternatieven.")
            return
        maps = {}
        for vid,_ in self.forms:
            option_map = {self.combos[vid,canonical].currentText():canonical for canonical in self.canonical}
            if len(option_map) != len(self.canonical):
                QMessageBox.warning(self,"Dubbele letter","Gebruik binnen elke versie elke antwoordletter precies één keer.")
                return
            maps[vid] = option_map
        self.option_maps = maps
        super().accept()


class NewQuestionVersionFields(QWidget):
    """Version membership is part of entering a new question."""
    def __init__(self, database, test_id, dialog, question_ids=None):
        super().__init__(dialog)
        from .test_versions import has_results
        self.database, self.test_id = database, test_id
        self.dialog = dialog
        self.question_ids = {int(question_id) for question_id in (question_ids or [])}
        dialog.version_fields = self
        self.entries = {}
        self.version_rows = {}
        self.alternatives = {}
        self.reference_version_id = None
        existing_membership = {}
        existing_answers = {}
        if self.question_ids:
            placeholders = ",".join("?" for _ in self.question_ids)
            for row in self.database.rows(
                f"SELECT version_id, question_id, label, answer, alternatives_json FROM version_questions "
                f"WHERE question_id IN ({placeholders})",
                tuple(self.question_ids),
            ):
                question = self.database.rows(
                    "SELECT subquestion FROM matrix_questions WHERE id=?", (row["question_id"],)
                )[0]
                suffix = str(question["subquestion"] or "")
                label = str(row["label"])
                existing_membership[int(row["version_id"])] = label[:-len(suffix)] if suffix and label.endswith(suffix) else label
                existing_answers[int(row["version_id"])] = str(row["answer"] or "")
                option_map = json.loads(row["alternatives_json"] or "{}")
                if option_map:
                    self.alternatives[int(row["version_id"])] = option_map
            reference = self.database.scalar(
                f"SELECT version_id FROM question_alternative_references WHERE question_id IN ({placeholders}) LIMIT 1",
                tuple(self.question_ids),
            )
            self.reference_version_id = int(reference) if reference is not None else None
        layout = QVBoxLayout(self)
        note = QLabel("Kies of deze vraag gedeeld wordt of bij één versie hoort. Vink bij 'Meedoen' alleen "
                      "de versies aan waarin de vraag voorkomt en vul daarvoor het vraagnummer in. "
                      "Bij een vraaggroep worden de subvraagletters toegevoegd.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.kind = QComboBox()
        self.kind.addItem("Gedeelde vraag — meerdere versies", "shared")
        self.kind.addItem("Versiespecifieke vraag — één versie", "specific")
        layout.addWidget(self.kind)
        self.specific_version = QComboBox()
        for form in versions(database,test_id):
            if not has_results(database,test_id,form["id"]):
                self.specific_version.addItem(form["name"],form["id"])
        layout.addWidget(self.specific_version)
        self.title = QLineEdit()
        self.title.setPlaceholderText("Herkenbare titel — verplicht voor een gedeelde vraag")
        layout.addWidget(self.title)
        self.different = QCheckBox("De antwoordvolgorde verschilt per versie")
        layout.addWidget(self.different)
        link_options = QPushButton("Dezelfde antwoorden per versie koppelen…")
        self.link_options = link_options
        link_options.setEnabled(False)
        self.different.toggled.connect(link_options.setEnabled)
        link_options.clicked.connect(lambda: self.link_alternatives(dialog))
        layout.addWidget(link_options)
        dialog.is_multiple_choice.toggled.connect(self.different.setEnabled)
        self.different.setEnabled(dialog.is_multiple_choice.isChecked())
        membership_label = QLabel("Versies waarin deze vraag meedoet")
        membership_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(membership_label)
        for form in versions(database, test_id):
            row_widget = QWidget()
            line = QHBoxLayout(row_widget)
            line.setContentsMargins(0,0,0,0)
            check = QCheckBox(f"Meedoen — {form['name']}")
            locked = has_results(database, test_id, form["id"])
            check.setChecked(form["id"] in existing_membership if self.question_ids else not locked)
            check.setEnabled(not locked)
            if locked:
                check.setToolTip("Deze versie heeft resultaten; toevoegen is geblokkeerd.")
            number = QLineEdit(existing_membership.get(form["id"], dialog.number.text()))
            number.setPlaceholderText("Vraagnummer in deze versie")
            number.setEnabled(check.isChecked() and check.isEnabled())
            check.toggled.connect(lambda checked, number=number, check=check: number.setEnabled(checked and check.isEnabled()))
            answer = QComboBox()
            answer.addItems([""] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
            answer.setCurrentText(existing_answers.get(form["id"], ""))
            answer.setEnabled(False)
            def update(_=None, check=check, answer=answer):
                answer.setVisible(check.isChecked() and self.different.isChecked() and dialog.is_multiple_choice.isChecked())
                answer.setEnabled(False)
                answer.setToolTip("Wordt automatisch bepaald door de gekoppelde antwoorden.")
            check.toggled.connect(update)
            self.different.toggled.connect(update)
            dialog.is_multiple_choice.toggled.connect(update)
            for widget in (check, number, answer):
                line.addWidget(widget)
            layout.addWidget(row_widget)
            self.version_rows[form["id"]] = row_widget
            self.entries[form["id"]] = (check, number, answer)
            check.toggled.connect(self.update_question_hint)
        self.question_hint = QLabel()
        self.question_hint.setWordWrap(True)
        layout.addWidget(self.question_hint)
        self._shared_selection = {vid for vid,(check,_,_) in self.entries.items() if check.isChecked()}
        if self.question_ids:
            title = self.database.scalar(
                "SELECT shared_title FROM matrix_questions WHERE id=?", (next(iter(self.question_ids)),)
            )
            self.title.setText(str(title or ""))
            self.different.setChecked(bool(self.alternatives))
        self.kind.currentIndexChanged.connect(self.change_kind)
        self.specific_version.currentIndexChanged.connect(self.update_mode)
        self.different.toggled.connect(self.update_mode)
        dialog.is_multiple_choice.toggled.connect(self.update_mode)
        if len(self._shared_selection) == 1:
            selected_version_id = next(iter(self._shared_selection))
            selected_index = self.specific_version.findData(selected_version_id)
            if selected_index >= 0:
                self.specific_version.setCurrentIndex(selected_index)
            self.kind.setCurrentIndex(self.kind.findData("specific"))
        self.update_mode()
        dialog.form.insertRow(0,"Toetsversies", self)
        dialog.number.setVisible(False)
        number_label = dialog.form.labelForField(dialog.number)
        if number_label is not None:
            number_label.setVisible(False)
        if hasattr(dialog, "single_question_title"):
            dialog.single_question_title.setText("Vraaggegevens")

    def change_kind(self):
        if self.kind.currentData() == "specific":
            self._shared_selection = {vid for vid,(check,_,_) in self.entries.items() if check.isChecked()}
        else:
            for vid,(check,_,_) in self.entries.items():
                check.setChecked(vid in self._shared_selection)
        self.update_mode()

    def update_mode(self, *_):
        shared = self.kind.currentData() == "shared"
        self.specific_version.setVisible(not shared)
        self.title.setVisible(shared)
        mc = self.dialog.is_multiple_choice.isChecked()
        self.different.setVisible(shared and mc)
        if not shared or not mc:
            self.different.setChecked(False)
        self.link_options.setVisible(shared and mc and self.different.isChecked())
        for vid,(check,number,answer) in self.entries.items():
            if not shared:
                check.setChecked(vid == self.specific_version.currentData() and check.isEnabled())
            check.setVisible(shared)
            self.version_rows[vid].setVisible(shared or vid == self.specific_version.currentData())
            number.setEnabled(check.isChecked() and check.isEnabled())
            answer.setVisible(shared and mc and self.different.isChecked() and check.isChecked())
        self.update_question_hint()

    def update_question_hint(self, *_):
        if not hasattr(self,"question_hint"):
            return
        names = [form["name"] for form in versions(self.database,self.test_id) if self.entries[form["id"]][0].isChecked()]
        self.question_hint.setText("Deze vraag komt voor in: " + (", ".join(names) or "nog geen versie") +
                                  (". Geef de gedeelde vraag een herkenbare titel." if self.kind.currentData() == "shared" else "."))

    def validate(self):
        selected = [(vid,number) for vid,(check,number,_) in self.entries.items() if check.isChecked()]
        message = ""
        if not selected:
            message = "Vink minstens één versie aan voor de nieuwe vraag."
        elif self.kind.currentData() == "shared" and len(selected) < 2:
            message = "Kies minstens twee versies, of kies 'Versiespecifieke vraag' als de vraag bij één versie hoort."
        elif any(not number.text().strip() for _,number in selected):
            message = "Vul per geselecteerde versie het vraagnummer in."
        elif len(selected) > 1 and not self.title.text().strip():
            message = "Geef deze gedeelde vraag een herkenbare titel."
        elif self.different.isChecked() and self.dialog.is_multiple_choice.isChecked() and any(not self.alternatives.get(vid) for vid,_ in selected):
            message = "Koppel eerst alle antwoordalternatieven per geselecteerde versie."
        if message:
            QMessageBox.warning(self,"Toetsversies",message)
            return False
        return True

    def link_alternatives(self, dialog):
        if not dialog.multiple_choice_answer.text().strip():
            QMessageBox.information(self,"Antwoordsleutel invullen","Vul eerst de juiste antwoordletter bij de vraag in. Daarna kunt u dezelfde antwoorden per versie koppelen.")
            dialog.multiple_choice_answer.setFocus()
            return
        selected = [(form["id"],form["name"]) for form in versions(self.database,self.test_id) if self.entries[form["id"]][0].isChecked()]
        if not selected:
            return
        editor = AlternativeMappingDialog(selected,self.alternatives,dialog.multiple_choice_answer.text().strip().upper(),self,reference_version_id=self.reference_version_id)
        if editor.exec() == QDialog.DialogCode.Accepted:
            self.alternatives = editor.option_maps
            self.reference_version_id = editor.reference.currentData()
            for vid,option_map in self.alternatives.items():
                answer = next(letter for letter,canonical in option_map.items() if canonical == editor.base_answer)
                self.entries[vid][2].setCurrentText(answer)

    def save(self, question_ids, *, commit=True):
        question_ids = {int(question_id) for question_id in question_ids}
        old = {(r["version_id"], r["question_id"]): (r["label"], r["answer"]) for r in self.database.rows(
            "SELECT vq.* FROM version_questions vq JOIN test_versions v ON v.id=vq.version_id WHERE v.test_id=?", (self.test_id,))}
        old = {key: value for key, value in old.items() if int(key[1]) not in question_ids}
        selected = [(vid, number.text().strip(), answer.currentText()) for vid, (check, number, answer) in self.entries.items() if check.isChecked()]
        alternatives = {(r["version_id"],r["question_id"]):json.loads(r["alternatives_json"]) for r in self.database.rows(
            "SELECT vq.* FROM version_questions vq JOIN test_versions v ON v.id=vq.version_id WHERE v.test_id=?",(self.test_id,))}
        titles = {row["id"]:row["shared_title"] for row in self.database.rows("SELECT id,shared_title FROM matrix_questions WHERE test_id=?",(self.test_id,))}
        references = {row["question_id"]:row["version_id"] for row in self.database.rows(
            "SELECT r.* FROM question_alternative_references r JOIN matrix_questions q ON q.id=r.question_id WHERE q.test_id=?",(self.test_id,))}
        references = {qid: vid for qid, vid in references.items() if int(qid) not in question_ids}
        if not selected:
            raise ValueError("Vink minstens één versie aan voor de nieuwe vraag.")
        for qid in question_ids:
            titles[qid] = self.title.text().strip()
            if self.different.isChecked() and any(vid == self.reference_version_id for vid,_,_ in selected):
                references[qid] = self.reference_version_id
            question = self.database.rows("SELECT subquestion,is_multiple_choice FROM matrix_questions WHERE id=?", (qid,))[0]
            for vid, label, answer in selected:
                if not label:
                    raise ValueError("Vul voor elke geselecteerde versie een vraagnummer in.")
                different = self.different.isChecked() and question["is_multiple_choice"]
                if different and not answer:
                    raise ValueError("Kies per versie een antwoordletter.")
                if different and not self.alternatives.get(vid):
                    raise ValueError("Koppel eerst de antwoordalternatieven van de geselecteerde versies.")
                old[vid, qid] = (label + (question["subquestion"] or ""), answer if different else None)
                alternatives[vid,qid] = self.alternatives.get(vid,{}) if different else {}
        save_question_mapping(self.database, self.test_id, old, alternatives, references, titles, commit=commit)


class VersionDialog(QDialog):
    def __init__(self, database, test_id, parent=None):
        super().__init__(parent)
        self.database, self.test_id = database, test_id
        self.forms = versions(database, test_id)
        from .test_versions import has_results
        self.locked_versions = {form["id"] for form in self.forms if has_results(database,test_id,form["id"])}
        self.setWindowTitle("Toetsversies — vragen en leerlingen")
        self.resize(1100, 720)
        layout = QVBoxLayout(self)
        note = QLabel("Voer eerst gedeelde vragen in via Vraag toevoegen, daarna specifieke vragen. "
                      "Vink hieronder per vraag de versies aan en vul hun vraagnummer in (bijvoorbeeld 3a). "
                      "Het basisnummer identificeert de vraag; leerlingen zien het nummer van hun versie. "
                      "Sla vragen en leerlingtoewijzingen samen op met Alles opslaan.")
        note.setWordWrap(True)
        layout.addWidget(note)
        tabs = QTabWidget()
        self.tabs = tabs
        layout.addWidget(tabs)
        overview = QWidget()
        overview_layout = QVBoxLayout(overview)
        self.progress = QLabel()
        self.progress.setWordWrap(True)
        self.progress.setTextFormat(Qt.TextFormat.PlainText)
        self.progress.setAlignment(Qt.AlignmentFlag.AlignTop)
        overview_layout.addWidget(self.progress)
        jump = QHBoxLayout()
        check_questions = QPushButton("Vragen controleren")
        check_questions.clicked.connect(lambda: tabs.setCurrentIndex(1))
        check_students = QPushButton("Leerlingen toewijzen")
        check_students.clicked.connect(lambda: tabs.setCurrentIndex(2))
        jump.addWidget(check_questions)
        jump.addWidget(check_students)
        overview_layout.addLayout(jump)
        overview_layout.addStretch()
        tabs.addTab(overview,"Overzicht")
        question_tab = QWidget()
        qlayout = QVBoxLayout(question_tab)
        self.questions = test_questions(database, test_id)
        self.cells = {}
        self.overrides = {}
        self.titles = {}
        self.reference_versions = {row["question_id"]:row["version_id"] for row in database.rows(
            "SELECT r.* FROM question_alternative_references r JOIN matrix_questions q ON q.id=r.question_id WHERE q.test_id=?",(test_id,))}
        existing = {(r["version_id"], r["question_id"]): dict(r) for r in database.rows(
            "SELECT vq.* FROM version_questions vq JOIN test_versions v ON v.id=vq.version_id WHERE v.test_id=?", (test_id,))}
        self.alternatives = {key:json.loads(entry["alternatives_json"]) for key,entry in existing.items()}
        table = QTableWidget(len(self.questions), 2 + len(self.forms) * 3)
        headers = ["Vraag / herkenbare titel", "Andere MC-volgorde"]
        for form in self.forms:
            headers.extend([f"{form['name']} ✓", f"Nr. {form['name']}", f"Antwoord {form['name']}"])
        table.setHorizontalHeaderLabels(headers)
        for row, question in enumerate(self.questions):
            title_widget = QWidget()
            title_layout = QVBoxLayout(title_widget)
            title_layout.setContentsMargins(0,0,0,0)
            title_layout.addWidget(QLabel(f"{question['label']} — {question['maximum_score']:g} p"))
            title = QLineEdit(question.get("shared_title") or "")
            title.setPlaceholderText("Titel gedeelde vraag")
            title_layout.addWidget(title)
            self.titles[question["id"]] = title
            table.setCellWidget(row,0,title_widget)
            table.setRowHeight(row,65)
            override = QCheckBox()
            override.setEnabled(bool(question["is_multiple_choice"]))
            override.setChecked(any(existing.get((f["id"], question["id"]), {}).get("answer") for f in self.forms))
            if any((vid,question["id"]) in existing for vid in self.locked_versions):
                override.setEnabled(False)
                override.setToolTip("Deze vraag heeft een versie met resultaten. De antwoordkoppeling kan pas na het wissen van die resultaten worden gewijzigd.")
            option_widget = QWidget()
            option_layout = QHBoxLayout(option_widget)
            option_layout.setContentsMargins(0,0,0,0)
            option_layout.addWidget(override)
            link = QPushButton("Koppelen")
            link.setEnabled(override.isChecked())
            override.toggled.connect(link.setEnabled)
            link.clicked.connect(lambda _=False,question=question:self.link_alternatives(question))
            option_layout.addWidget(link)
            table.setCellWidget(row, 1, option_widget)
            self.overrides[question["id"]] = override
            for offset, form in enumerate(self.forms):
                entry = existing.get((form["id"], question["id"]))
                check = QCheckBox()
                check.setChecked(entry is not None)
                check.setEnabled(form["id"] not in self.locked_versions)
                if form["id"] in self.locked_versions:
                    check.setToolTip("Deze versie heeft resultaten. Vragen toevoegen of verwijderen is geblokkeerd.")
                number = QLineEdit(entry["label"] if entry else question["label"])
                answer = QComboBox()
                answer.addItems([""] + list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
                answer.setCurrentText((entry or {}).get("answer") or question.get("multiple_choice_answer") or "")
                number.setEnabled(check.isChecked())
                answer.setEnabled(False)
                answer.setToolTip("De juiste letter volgt automatisch uit de gekoppelde antwoorden.")
                check.toggled.connect(number.setEnabled)
                def update_answer(_=None, check=check, override=override, answer=answer):
                    answer.setEnabled(False)
                check.toggled.connect(update_answer)
                override.toggled.connect(update_answer)
                col = 2 + offset * 3
                for index, widget in enumerate((check, number, answer)):
                    table.setCellWidget(row, col + index, widget)
                self.cells[form["id"], question["id"]] = (check, number, answer)
        table.setColumnWidth(0, 210)
        table.setColumnWidth(1, 150)
        for offset in range(len(self.forms)):
            for index, width in enumerate((65, 85, 95)):
                table.setColumnWidth(2 + offset * 3 + index, width)
        qlayout.addWidget(table)
        tabs.addTab(question_tab, "1. Gedeelde en specifieke vragen")
        pupil_tab = QWidget()
        playout = QVBoxLayout(pupil_tab)
        self.students = test_students(database, test_id)
        self.student_choices = {}
        self.pupils = QTableWidget(len(self.students), 3)
        self.pupils.setHorizontalHeaderLabels(["Leerling", "Klas/groep", "Versie"])
        self.pupils.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.pupils.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        for row, student in enumerate(self.students):
            for col, value in enumerate((student["display_name"], student["groups"])):
                cell = QTableWidgetItem(value)
                cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.pupils.setItem(row, col, cell)
            combo = self.version_combo()
            index = combo.findData(student_version(database, test_id, student["id"]))
            combo.setCurrentIndex(max(index, 0))
            if database.scalar("SELECT COUNT(*) FROM scores s JOIN test_attempts a ON a.id=s.attempt_id WHERE a.test_id=? AND a.student_id=? AND (s.score IS NOT NULL OR COALESCE(s.response_text,'')<>'')",(test_id,student["id"])):
                combo.setEnabled(False)
                combo.setToolTip("Wis eerst de resultaten van deze leerling om de versie te wijzigen.")
            self.pupils.setCellWidget(row, 2, combo)
            self.student_choices[student["id"]] = combo
        playout.addWidget(self.pupils)
        bulk = QHBoxLayout()
        self.target = self.version_combo()
        self.group = QComboBox()
        self.group.addItem("Kies klas/groep")
        self.group.addItems(sorted({g.strip() for s in self.students for g in s["groups"].split(",") if g.strip()}))
        selected = QPushButton("Toewijzen aan selectie")
        selected.clicked.connect(lambda: self.bulk_assign(False))
        classroom = QPushButton("Toewijzen aan klas/groep")
        classroom.clicked.connect(lambda: self.bulk_assign(True))
        for widget in (self.target, selected, self.group, classroom):
            bulk.addWidget(widget)
        playout.addLayout(bulk)
        tabs.addTab(pupil_tab, "2. Leerlingen toewijzen")
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self.save_state = QLabel()
        layout.addWidget(self.save_state)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText("Alles opslaan")
        self.buttons.button(QDialogButtonBox.StandardButton.Close).setText("Sluiten")
        self.buttons.accepted.connect(self.save_all)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._saved_state = self.state()
        for widget in self.titles.values():
            widget.textChanged.connect(self.refresh_progress)
        for check,number,answer in self.cells.values():
            check.toggled.connect(self.refresh_progress)
            number.textChanged.connect(self.refresh_progress)
            answer.currentTextChanged.connect(self.refresh_progress)
        for widget in self.overrides.values():
            widget.toggled.connect(self.refresh_progress)
        for widget in self.student_choices.values():
            widget.currentIndexChanged.connect(self.refresh_progress)
        self.refresh_progress()

    def version_combo(self):
        combo = QComboBox()
        combo.addItem("Nog niet toegewezen", None)
        for form in self.forms:
            combo.addItem(form["name"], form["id"])
        return combo

    def bulk_assign(self, by_class):
        selected = {index.row() for index in self.pupils.selectionModel().selectedRows()}
        changed = locked = 0
        for row, student in enumerate(self.students):
            include = self.group.currentIndex() > 0 and self.group.currentText() in [g.strip() for g in student["groups"].split(",")] if by_class else row in selected
            if include:
                combo = self.student_choices[student["id"]]
                if not combo.isEnabled():
                    locked += 1
                    continue
                combo.setCurrentIndex(combo.findData(self.target.currentData()))
                changed += 1
        self.feedback.setText(f"{changed} leerlingen ingesteld; {locked} overgeslagen vanwege ingevoerde resultaten. Klik op Alles opslaan om te bewaren."
                              if changed or locked else "Kies eerst een klas/groep of selecteer leerlingregels in de tabel.")

    def question_configuration(self):
        mapping, alternatives = {}, {}
        for key,(check,number,answer) in self.cells.items():
            if not check.isChecked():
                continue
            different = self.overrides[key[1]].isChecked()
            if different and not self.alternatives.get(key):
                self.tabs.setCurrentIndex(1)
                raise ValueError("Koppel eerst de antwoorden voor elke geselecteerde versie van de meerkeuzevraag.")
            mapping[key] = (number.text().strip(),answer.currentText() if different else None)
            alternatives[key] = self.alternatives.get(key,{}) if different else {}
        references = {qid:vid for qid,vid in self.reference_versions.items() if (vid,qid) in mapping}
        return mapping,alternatives,references,{qid:widget.text().strip() for qid,widget in self.titles.items()}

    def state(self):
        return (
            tuple((key,check.isChecked(),number.text(),answer.currentText()) for key,(check,number,answer) in self.cells.items()),
            tuple((qid,widget.text()) for qid,widget in self.titles.items()),
            tuple((qid,widget.isChecked()) for qid,widget in self.overrides.items()),
            tuple((sid,widget.currentData()) for sid,widget in self.student_choices.items()),
            repr(sorted((key,sorted(value.items())) for key,value in self.alternatives.items())),
            tuple(sorted(self.reference_versions.items())),
        )

    def save_all(self):
        try:
            mapping,alternatives,references,titles = self.question_configuration()
            assignments = {sid:combo.currentData() for sid,combo in self.student_choices.items()}
            with self.database.connection:
                save_question_mapping(self.database,self.test_id,mapping,alternatives,references,titles,commit=False)
                assign_students(self.database,self.test_id,assignments,commit=False)
        except Exception as error:
            self.feedback.setText("Niet opgeslagen: " + str(error))
            QMessageBox.warning(self,"Wijzigingen niet opgeslagen",str(error))
            return False
        self._saved_state = self.state()
        self.feedback.setText("Vragen en leerlingtoewijzingen zijn samen opgeslagen.")
        self.refresh_progress()
        return True

    def reject(self):
        if hasattr(self,"_saved_state") and self.state() != self._saved_state:
            choice = QMessageBox.question(self,"Niet-opgeslagen wijzigingen",
                "Wilt u uw wijzigingen in vragen en leerlingtoewijzingen opslaan?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save)
            if choice == QMessageBox.StandardButton.Cancel:
                return
            if choice == QMessageBox.StandardButton.Save and not self.save_all():
                return
        super().reject()

    def refresh_progress(self, *_):
        issues = []
        missing_titles,missing_numbers,missing_links,unmapped = [],[],[],[]
        used = {}
        counts = {form["id"]:[0,0] for form in self.forms}
        for question in self.questions:
            qid = question["id"]
            label = self.titles[qid].text().strip() or f"Vraag {question['label']}"
            selected = [(vid,number.text().strip()) for (vid,question_id),(check,number,_) in self.cells.items() if question_id == qid and check.isChecked()]
            if not selected:
                unmapped.append(label)
            if len(selected)>1 and not self.titles[qid].text().strip():
                missing_titles.append(label)
            for vid,number in selected:
                counts[vid][0] += 1
                if not number or (vid,number) in used:
                    missing_numbers.append(label)
                used[vid,number] = qid
                if self.overrides[qid].isChecked() and not self.alternatives.get((vid,qid)):
                    missing_links.append(label)
        unassigned = []
        for student in self.students:
            vid = self.student_choices[student["id"]].currentData()
            if vid is None:
                unassigned.append(student["display_name"])
            else:
                counts[vid][1] += 1
        categories = [("Gedeelde vragen zonder titel",missing_titles),("Vragen zonder versie",unmapped),
                      ("Ontbrekende of dubbele vraagnummers",missing_numbers),("Antwoordkoppelingen ontbreken",missing_links),
                      ("Leerlingen zonder versie",unassigned)]
        for description,entries in categories:
            if entries:
                names = list(dict.fromkeys(entries))
                issues.append(f"• {description}: {len(entries)} — {', '.join(names[:5])}" + ("…" if len(names)>5 else ""))
        question_issues = sum(len(entries) for _,entries in categories[:-1])
        status = "Nog te regelen" if issues else "Alles is ingevuld"
        per_form = [f"Versie {form['name']}: {counts[form['id']][0]} " + ("vraag" if counts[form['id']][0]==1 else "vragen") +
                    f" · {counts[form['id']][1]} " + ("leerling" if counts[form['id']][1]==1 else "leerlingen") for form in self.forms]
        empty_forms = [form['name'] for form in self.forms if counts[form['id']][0]==0]
        if empty_forms:
            issues.append("• Nog geen vragen in versie: " + ", ".join(empty_forms))
            status = "Nog te regelen"
        self.progress.setText(status + "\n\n" + "\n".join(per_form) + "\n\n" +
                              ("\n".join(issues) if issues else "U kunt per versie resultaten invoeren. Alles opslaan bewaart uw wijzigingen.") +
                              "\n\nDit overzicht volgt uw invoer. Wijzigingen worden pas bewaard met Alles opslaan.")
        self.tabs.setTabText(1,f"1. Vragen ({question_issues} aandachtspunten)" if question_issues else "1. Vragen")
        self.tabs.setTabText(2,f"2. Leerlingen ({len(unassigned)} zonder versie)" if unassigned else "2. Leerlingen")
        dirty = self.state() != self._saved_state
        self.save_state.setText("Niet-opgeslagen wijzigingen" if dirty else "Alles opgeslagen")
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(dirty)

    def link_alternatives(self, question):
        qid = question["id"]
        selected = [(form["id"],form["name"]) for form in self.forms if self.cells[form["id"],qid][0].isChecked()]
        if not selected:
            return
        existing = {vid:self.alternatives.get((vid,qid),{}) for vid,_ in selected}
        editor = AlternativeMappingDialog(selected,existing,question["multiple_choice_answer"],self,reference_version_id=self.reference_versions.get(qid))
        if editor.exec() == QDialog.DialogCode.Accepted:
            self.reference_versions[qid] = editor.reference.currentData()
            for vid,option_map in editor.option_maps.items():
                self.alternatives[vid,qid] = option_map
                self.cells[vid,qid][2].setCurrentText(next(letter for letter,canonical in option_map.items() if canonical == editor.base_answer))
            self.refresh_progress()



def fill_version_combo(combo, database, test_id, *, combined=False):
    """Preserve selection only while staying on the same test."""
    forms = versions(database, test_id)
    previous = combo.currentData() if combo.property("test_id") == test_id else None
    combo.blockSignals(True)
    combo.clear()
    if combined:
        combo.addItem("Alle versies samen", None)
    for form in forms:
        combo.addItem(form["name"], form["id"])
    index = combo.findData(previous)
    combo.setCurrentIndex(index if index >= 0 else 0)
    combo.setProperty("test_id", test_id)
    combo.setVisible(bool(forms))
    combo.blockSignals(False)
    return forms
