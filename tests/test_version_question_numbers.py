import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from toetsanalyse.database import SubjectDatabase
from toetsanalyse.matrix_page import MatrixPage
from toetsanalyse.question_dialogs import QuestionDialog
from toetsanalyse.test_versions import create_versions, mapped_questions, save_question_mapping, versions
from toetsanalyse.version_dialog import NewQuestionVersionFields


class VersionQuestionNumbers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = SubjectDatabase.create(Path(self.temp.name) / "test.db", "Natuurkunde", "2026-2027")
        self.test_id = self.db.connection.execute(
            "INSERT INTO tests(school_year_id,name,period,test_type) VALUES(1,'SE1','1','SE')"
        ).lastrowid
        create_versions(self.db, self.test_id, ["TA", "ML", "Optica"])
        self.forms = versions(self.db, self.test_id)
        self.db.connection.commit()
        self.page = MatrixPage(self.db, 1)
        self.page.test.setCurrentIndex(self.page.test.findData(self.test_id))

    def tearDown(self):
        self.page.close()
        self.db.close()
        self.temp.cleanup()

    def add(self, version_id, *, batch=False):
        def accept(dialog):
            dialog.number.setText("1")
            fields = dialog.version_fields
            fields.kind.setCurrentIndex(fields.kind.findData("specific"))
            fields.specific_version.setCurrentIndex(fields.specific_version.findData(version_id))
            fields.entries[version_id][1].setText("1")
            return QDialog.DialogCode.Accepted

        entry = {
            "question_number": "1",
            "subquestion": None,
            "maximum_score": 2,
            "short_description": "Test",
            "expected_time_minutes": None,
            "is_multiple_choice": 0,
            "multiple_choice_answer": None,
            "taxonomy_values": {},
            "property_values": {},
        }

        def normal(dialog):
            return dict(entry, question_number=dialog.number.text())

        def entries(dialog, *args, **kwargs):
            return [
                dict(entry, question_number=dialog.number.text(), subquestion=letter)
                for letter in ("a", "b")
            ]

        with (
            patch.object(self.page, "taxonomies", return_value=[{"id": 1, "name": "Test", "values": []}]),
            patch.object(self.page, "normal_question_entry", side_effect=normal),
            patch.object(QuestionDialog, "exec", accept),
            patch.object(QuestionDialog, "has_subquestion_batch", return_value=batch),
            patch.object(QuestionDialog, "subquestion_entries", entries),
            patch.object(QMessageBox, "warning") as warning,
        ):
            self.page.add_question()
        return warning

    def test_same_number_allowed_in_distinct_versions_and_table_names_them(self):
        for form in self.forms:
            self.add(form["id"]).assert_not_called()
        self.assertEqual(3, self.db.scalar("SELECT COUNT(*) FROM matrix_questions"))
        for form in self.forms:
            self.assertEqual(["1"], [q["label"] for q in mapped_questions(self.db, self.test_id, form["id"])])
        labels = [self.page.table.item(row, 0).text() for row in range(3)]
        self.assertEqual({"Vraag 1 – TA", "Vraag 1 – ML", "Vraag 1 – Optica"}, set(labels))

    def test_duplicate_in_same_version_rolls_back_question(self):
        self.add(self.forms[0]["id"])
        self.add(self.forms[0]["id"]).assert_called_once()
        self.assertEqual(1, self.db.scalar("SELECT COUNT(*) FROM matrix_questions"))

    def test_subquestion_groups_can_restart_at_one_in_each_version(self):
        for form in self.forms:
            self.add(form["id"], batch=True).assert_not_called()
            self.assertEqual(
                ["1a", "1b"],
                [q["label"] for q in mapped_questions(self.db, self.test_id, form["id"])],
            )

    def test_version_dialog_hides_internal_number_and_excludes_unchecked_version(self):
        dialog = QuestionDialog([], [], default_number="42")
        fields = NewQuestionVersionFields(self.db, self.test_id, dialog)
        self.assertTrue(dialog.number.isHidden())
        self.assertTrue(dialog.form.labelForField(dialog.number).isHidden())
        self.assertEqual("Vraaggegevens", dialog.single_question_title.text())

        excluded_id = self.forms[1]["id"]
        fields.title.setText("Gedeelde vraag")
        for form in self.forms:
            check, number, _ = fields.entries[form["id"]]
            check.setChecked(form["id"] != excluded_id)
            number.setText("1")
        self.assertTrue(fields.validate())

        question_id = self.db.connection.execute(
            "INSERT INTO matrix_questions(test_id,question_number,maximum_score) VALUES(?,?,?)",
            (self.test_id, "42", 1),
        ).lastrowid
        fields.save({question_id})
        self.db.connection.commit()
        self.assertEqual(
            ["TA", "Optica"],
            [
                form["name"]
                for form in self.forms
                if mapped_questions(self.db, self.test_id, form["id"])
            ],
        )
        dialog.close()

    def test_edit_question_can_change_version_membership_and_visible_numbers(self):
        question_id = self.db.connection.execute(
            "INSERT INTO matrix_questions(test_id,question_number,maximum_score,short_description) VALUES(?,?,?,?)",
            (self.test_id, "42", 2, "Spanningsdeler"),
        ).lastrowid
        save_question_mapping(
            self.db,
            self.test_id,
            {(form["id"], question_id): ("6", None) for form in self.forms},
            titles={question_id: "Spanningsdeler"},
        )
        self.page.refresh_questions()
        row = next(
            row
            for row in range(self.page.table.rowCount())
            if self.page.table.item(row, 0).data(256) == question_id
        )
        excluded_id = self.forms[1]["id"]

        def accept(dialog):
            self.assertTrue(dialog.number.isHidden())
            fields = dialog.version_fields
            self.assertEqual(3, sum(check.isChecked() for check, _, _ in fields.entries.values()))
            fields.entries[excluded_id][0].setChecked(False)
            fields.entries[self.forms[0]["id"]][1].setText("8")
            fields.entries[self.forms[2]["id"]][1].setText("9")
            return QDialog.DialogCode.Accepted

        entry = {
            "question_number": "42",
            "subquestion": None,
            "maximum_score": 2,
            "short_description": "Spanningsdeler",
            "expected_time_minutes": None,
            "is_multiple_choice": 0,
            "multiple_choice_answer": None,
            "taxonomy_values": {},
            "property_values": {},
        }
        with (
            patch.object(self.page, "taxonomies", return_value=[{"id": 1, "name": "Test", "values": []}]),
            patch.object(self.page, "properties", return_value=[]),
            patch.object(self.page, "normal_question_entry", return_value=entry),
            patch.object(QuestionDialog, "exec", accept),
            patch.object(QMessageBox, "warning") as warning,
        ):
            self.page.edit_question(row)
        warning.assert_not_called()
        self.assertEqual(["8"], [q["label"] for q in mapped_questions(self.db, self.test_id, self.forms[0]["id"])])
        self.assertEqual([], mapped_questions(self.db, self.test_id, excluded_id))
        self.assertEqual(["9"], [q["label"] for q in mapped_questions(self.db, self.test_id, self.forms[2]["id"])])

    def test_overview_uses_natural_order_of_visible_version_numbers(self):
        mapping = {}
        for internal_number, visible_number in (("1", "10"), ("2", "2"), ("3", "1")):
            question_id = self.db.connection.execute(
                "INSERT INTO matrix_questions(test_id,question_number,maximum_score) VALUES(?,?,?)",
                (self.test_id, internal_number, 1),
            ).lastrowid
            mapping[self.forms[0]["id"], question_id] = (visible_number, None)
        save_question_mapping(self.db, self.test_id, mapping)
        self.page.refresh_questions()
        self.assertEqual(
            ["Vraag 1 – TA", "Vraag 2 – TA", "Vraag 10 – TA"],
            [self.page.table.item(row, 0).text() for row in range(self.page.table.rowCount())],
        )

    def test_edit_button_opens_question_from_selected_visible_row(self):
        mapping = {}
        question_ids = {}
        for form in self.forms:
            question_id = self.db.connection.execute(
                "INSERT INTO matrix_questions(test_id,question_number,maximum_score) VALUES(?,?,?)",
                (self.test_id, str(len(question_ids) + 1), 1),
            ).lastrowid
            question_ids[form["name"]] = question_id
            mapping[form["id"], question_id] = ("1", None)
        for visible_number in range(2, 11):
            question_id = self.db.connection.execute(
                "INSERT INTO matrix_questions(test_id,question_number,maximum_score) VALUES(?,?,?)",
                (self.test_id, str(visible_number + 10), 1),
            ).lastrowid
            mapping[self.forms[0]["id"], question_id] = (str(visible_number), None)
        save_question_mapping(self.db, self.test_id, mapping)
        self.page.refresh_questions()
        target_row = next(
            row
            for row in range(self.page.table.rowCount())
            if self.page.table.item(row, 0).text() == "Vraag 1 – ML"
        )
        self.page.table.setCurrentCell(target_row, 0)
        self.assertEqual(
            question_ids["ML"],
            self.page.table.item(target_row, 0).data(256),
        )

        opened = []
        def cancel(dialog):
            selected = [
                form["name"]
                for form in self.forms
                if dialog.version_fields.entries[form["id"]][0].isChecked()
            ]
            opened.extend(selected)
            return QDialog.DialogCode.Rejected

        with (
            patch.object(self.page, "taxonomies", return_value=[{"id": 1, "name": "Test", "values": []}]),
            patch.object(self.page, "properties", return_value=[]),
            patch.object(QuestionDialog, "exec", cancel),
        ):
            self.page.edit_question()
        self.assertEqual(["ML"], opened)


if __name__ == "__main__":
    unittest.main()
