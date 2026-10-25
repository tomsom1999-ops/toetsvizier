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
from toetsanalyse.test_versions import create_versions, mapped_questions, versions


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


if __name__ == "__main__":
    unittest.main()
