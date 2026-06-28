import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap, QTextFormat
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QScrollArea

    from toetsanalyse.app import (
        AdvancedSettingsPage,
        ClassificationPage,
        NewSubjectDialog,
        HelpWizardDialog,
        MatrixPage,
        QuestionPropertyDialog,
        QuestionDatabaseAnalysisDialog,
        QuestionDatabaseDialog,
        QuestionDatabaseImportDialog,
        QuestionDatabasePage,
        QuestionDatabaseSelectionDialog,
        ResultsPage,
        StudentAttributeDialog,
        StudentAttributeAnalysisPage,
        StudentDialog,
        StudentReportWizardDialog,
        StudentsPage,
        TestDialog,
    )
    from toetsanalyse.database import SubjectDatabase
    from toetsanalyse.report_documents import formatted_report_document
except ModuleNotFoundError:
    QApplication = None
    Qt = None
    QTextFormat = None
    QPixmap = None
    QScrollArea = None
    QMessageBox = None
    QPushButton = None
    AdvancedSettingsPage = None
    ClassificationPage = None
    NewSubjectDialog = None
    HelpWizardDialog = None
    MatrixPage = None
    QuestionPropertyDialog = None
    QuestionDatabaseAnalysisDialog = None
    QuestionDatabaseDialog = None
    QuestionDatabaseImportDialog = None
    QuestionDatabasePage = None
    QuestionDatabaseSelectionDialog = None
    ResultsPage = None
    StudentAttributeDialog = None
    StudentAttributeAnalysisPage = None
    StudentDialog = None
    StudentReportWizardDialog = None
    StudentsPage = None
    TestDialog = None
    formatted_report_document = None
    SubjectDatabase = None


@unittest.skipIf(QApplication is None, "PySide6 is niet beschikbaar in deze Python-omgeving.")
class NewSubjectDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_sets_a_default_school_year(self) -> None:
        dialog = NewSubjectDialog()
        self.assertRegex(dialog.school_year.text(), r"^\d{4}-\d{4}$")
        dialog.close()

    def test_new_classification_dialog_opens_without_existing_definition(self) -> None:
        dialog = QuestionPropertyDialog()
        self.assertEqual("Vraageigenschap toevoegen", dialog.windowTitle())
        dialog.close()

    def test_long_test_form_uses_scrollable_content(self) -> None:
        dialog = TestDialog([], [], [], [])
        self.assertTrue(dialog.findChildren(QScrollArea))
        self.assertEqual(1, dialog.weight.value())
        dialog.close()

    def test_advanced_settings_remember_development_analysis_choice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                page = AdvancedSettingsPage(database, None)
                self.assertFalse(page.development_analysis.isChecked())
                self.assertFalse(page.student_attribute_analysis.isChecked())
                page.development_analysis.setChecked(True)
                page.student_attribute_analysis.setChecked(True)
                page.close()

                reopened = AdvancedSettingsPage(database, None)
                self.assertTrue(reopened.development_analysis.isChecked())
                self.assertTrue(reopened.student_attribute_analysis.isChecked())
                reopened.close()
            finally:
                database.close()

    def test_student_attribute_dialog_supports_choice_lists(self) -> None:
        dialog = StudentAttributeDialog()
        dialog.name.setText("Profiel")
        dialog.field_type.setCurrentText("keuzelijst")
        dialog.choices.addItem("N&T")
        dialog.choices.addItem("N&G")
        self.assertEqual(["N&T", "N&G"], dialog.choice_values())
        dialog.close()

    def test_student_dialog_uses_dropdown_for_choice_attribute(self) -> None:
        attributes = [
            {"id": 1, "name": "Profiel", "field_type": "keuzelijst", "options_json": '["N&T", "N&G"]'}
        ]
        dialog = StudentDialog([], attributes, attribute_values={1: "N&G"})
        widget = dialog.attribute_widgets[1]
        self.assertEqual("N&G", widget.currentText())
        self.assertEqual(3, widget.count())
        dialog.close()

    def test_student_attribute_analysis_group_filter_loads_group_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute("INSERT INTO classes(school_year_id, name) VALUES(?, ?)", (year_id, "ha4.na1"))
                page = StudentAttributeAnalysisPage(database, year_id)
                page.attribute_filter.setCurrentIndex(page.attribute_filter.findData("__group__"))
                page.reload_values(None)
                values = [page.value_filter.itemText(index) for index in range(page.value_filter.count())]
                self.assertIn("ha4.na1", values)
                page.close()
            finally:
                database.close()

    def test_question_type_is_available_as_extra_test_field(self) -> None:
        properties = [{"id": 4, "name": "Vraagtype", "choices_json": '["Bereken", "Teken"]'}]
        dialog = TestDialog([], [], [], properties)
        visible_fields = [dialog.properties.item(index).text() for index in range(dialog.properties.count())]
        self.assertIn("Vraagtype (keuzelijst)", visible_fields)
        self.assertEqual(["Bereken", "Teken"], [dialog.question_types.item(index).text() for index in range(2)])
        dialog.close()

    def test_classification_page_can_delete_unused_classification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO property_definitions(name, field_type) VALUES(?, ?)",
                    ("Contextniveau", "tekst"),
                )
                page = ClassificationPage(database, None)
                matches = page.table.findItems("Contextniveau", Qt.MatchFlag.MatchExactly)
                self.assertTrue(matches)
                page.table.selectRow(matches[0].row())

                with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                    page.delete_classification()

                self.assertEqual(
                    0,
                    database.scalar(
                        "SELECT is_active FROM property_definitions WHERE name=?", ("Contextniveau",)
                    ),
                )
                page.close()
            finally:
                database.close()

    def test_classification_page_blocks_delete_when_classification_is_used(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO property_definitions(name, field_type) VALUES(?, ?)",
                    ("Contextniveau", "tekst"),
                )
                property_id = database.scalar("SELECT id FROM property_definitions WHERE name='Contextniveau'")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
                    (year_id, "SO1", "Periode 1", "SO"),
                )
                test_id = database.scalar("SELECT id FROM tests WHERE name='SO1'")
                database.execute(
                    "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
                    (test_id, "1", 1),
                )
                question_id = database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,))
                database.execute(
                    "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
                    (question_id, property_id, "Hoog"),
                )
                page = ClassificationPage(database, None)
                matches = page.table.findItems("Contextniveau", Qt.MatchFlag.MatchExactly)
                self.assertTrue(matches)
                page.table.selectRow(matches[0].row())

                with patch.object(QMessageBox, "warning") as warning:
                    page.delete_classification()

                self.assertEqual(
                    1,
                    database.scalar(
                        "SELECT is_active FROM property_definitions WHERE name=?", ("Contextniveau",)
                    ),
                )
                warning.assert_called_once()
                self.assertIn("Classificatie niet verwijderd", warning.call_args.args[1])
                page.close()
            finally:
                database.close()

    def test_students_page_can_delete_student_attribute_with_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO student_attributes(name, field_type) VALUES(?, ?)", ("Mentor", "tekst")
                )
                attribute_id = database.scalar("SELECT id FROM student_attributes WHERE name='Mentor'")
                database.execute("INSERT INTO students(display_name) VALUES(?)", ("Lina",))
                student_id = database.scalar("SELECT id FROM students WHERE display_name='Lina'")
                database.execute(
                    "INSERT INTO student_attribute_values(student_id, attribute_id, value) VALUES(?, ?, ?)",
                    (student_id, attribute_id, "J. de Vries"),
                )

                page = StudentsPage(database, None)
                buttons = [button.text() for button in page.findChildren(QPushButton)]
                self.assertIn("Eigenschap verwijderen", buttons)

                with (
                    patch("toetsanalyse.app.QInputDialog.getItem", return_value=("Mentor", True)),
                    patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes),
                ):
                    page.delete_attribute()

                self.assertEqual(
                    0,
                    database.scalar("SELECT COUNT(*) FROM student_attributes WHERE name='Mentor'"),
                )
                self.assertEqual(0, database.scalar("SELECT COUNT(*) FROM student_attribute_values"))
                page.close()
            finally:
                database.close()

    def test_help_wizard_navigates_steps_and_contains_screen_preview(self) -> None:
        preview = QPixmap(120, 80)
        preview.fill(Qt.GlobalColor.white)
        dialog = HelpWizardDialog(
            "Leerlingen",
            "Hier beheert u leerlingen.",
            [
                {
                    "title": "Een leerling toevoegen",
                    "text": "Voeg de leerling toe.",
                    "action": "Klik op toevoegen.",
                    "tip": "Controleer de groep.",
                }
            ],
            screen_preview=preview,
        )
        self.assertEqual(2, dialog.step_stack.count())
        self.assertEqual("Stap 1 van 2", dialog.progress.text())
        self.assertTrue(dialog.findChildren(type(dialog.progress), "helpImage"))
        available = QApplication.primaryScreen().availableGeometry()
        self.assertLessEqual(dialog.width(), max(420, available.width() - 64))
        self.assertLessEqual(dialog.height(), max(380, available.height() - 64))
        dialog.next_button.click()
        self.assertEqual(1, dialog.step_stack.currentIndex())
        self.assertEqual("Stap 2 van 2", dialog.progress.text())
        self.assertFalse(dialog.next_button.isVisible())
        dialog.close()

    def test_enabling_question_type_selects_all_options_by_default(self) -> None:
        properties = [{"id": 4, "name": "Vraagtype", "choices_json": '["Bereken", "Teken"]'}]
        dialog = TestDialog([], [], [], properties)
        self.assertTrue(dialog.question_types.isHidden())
        dialog.properties.item(0).setCheckState(Qt.CheckState.Checked)
        self.assertEqual(["Bereken", "Teken"], dialog.checked_question_types())
        self.assertFalse(dialog.question_types.isHidden())
        dialog.close()

    def test_test_groups_use_checkboxes_for_multiple_links(self) -> None:
        classes = [{"id": 1, "name": "ha4.na1"}, {"id": 2, "name": "ha4.na2"}]
        dialog = TestDialog(classes, [], [], [])
        dialog.classes.item(0).setCheckState(Qt.CheckState.Checked)
        dialog.classes.item(1).setCheckState(Qt.CheckState.Checked)
        self.assertEqual([1, 2], dialog.checked_class_ids())
        dialog.close()

    def test_question_overview_requires_explicit_test_selection_each_time_it_opens(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
                    (year_id, "SE1", "Toetsweek 1", "SE"),
                )
                page = MatrixPage(database, year_id)
                self.assertEqual("Kies toets...", page.test.currentText())
                self.assertIsNone(page.test.currentData())
                page.test.setCurrentIndex(1)
                self.assertEqual("SE1", page.test.currentText())
                page.on_activated()
                self.assertEqual("Kies toets...", page.test.currentText())
                self.assertIsNone(page.test.currentData())
                page.close()
            finally:
                database.close()

    def test_question_overview_filters_tests_by_level_and_grade(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year) "
                    "VALUES(?, ?, ?, ?, ?, ?)",
                    (year_id, "SE1 H4", "Toetsweek 1", "SE", "havo", "4"),
                )
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year) "
                    "VALUES(?, ?, ?, ?, ?, ?)",
                    (year_id, "SE1 V5", "Toetsweek 1", "SE", "vwo", "5"),
                )
                page = MatrixPage(database, year_id)
                page.level_filter.setCurrentText("havo")
                page.grade_filter.setCurrentText("4")
                test_names = [page.test.itemText(index) for index in range(page.test.count())]
                self.assertIn("Kies toets...", test_names)
                self.assertIn("SE1 H4", test_names)
                self.assertNotIn("SE1 V5", test_names)
                page.close()
            finally:
                database.close()

    def test_results_entry_keeps_student_names_visible_as_fixed_row_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute("INSERT INTO classes(school_year_id, name) VALUES(?, ?)", (year_id, "Cluster A"))
                class_id = database.scalar("SELECT id FROM classes WHERE name='Cluster A'")
                database.execute("INSERT INTO students(display_name) VALUES(?)", ("Mila de Vries",))
                student_id = database.scalar("SELECT id FROM students WHERE display_name='Mila de Vries'")
                database.execute(
                    "INSERT INTO enrollments(student_id, class_id, school_year_id) VALUES(?, ?, ?)",
                    (student_id, class_id, year_id),
                )
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
                    (year_id, "SE1", "Toetsweek 1", "SE"),
                )
                test_id = database.scalar("SELECT id FROM tests WHERE name='SE1'")
                database.execute("INSERT INTO test_classes(test_id, class_id) VALUES(?, ?)", (test_id, class_id))
                database.execute(
                    "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
                    (test_id, "1", 3),
                )
                page = ResultsPage(database, year_id)
                page.test.setCurrentIndex(1)
                self.assertTrue(page.table.isColumnHidden(0))
                self.assertFalse(page.table.verticalHeader().isHidden())
                self.assertTrue(page.table.verticalHeader().isVisibleTo(page.table))
                header_item = page.table.verticalHeaderItem(0)
                self.assertIsNotNone(header_item)
                self.assertEqual("Mila de Vries", header_item.text())
                page.close()
            finally:
                database.close()

    def test_report_page_marker_becomes_qt_page_break(self) -> None:
        document = formatted_report_document(
            "<p>Eerste</p><p>[[PAGE_BREAK]]</p><p>Tweede</p>"
            "<p>[[PAGE_BREAK]]</p><p>Derde kaart</p>"
        )
        block = document.begin()
        second_policy = None
        third_policy = None
        while block.isValid():
            if block.text().strip() == "Tweede":
                second_policy = block.blockFormat().pageBreakPolicy()
            if block.text().strip() == "Derde kaart":
                third_policy = block.blockFormat().pageBreakPolicy()
            block = block.next()
        self.assertTrue(second_policy & QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
        self.assertTrue(third_policy & QTextFormat.PageBreakFlag.PageBreak_AlwaysBefore)
        self.assertNotIn("[[PAGE_BREAK]]", document.toPlainText())

    def test_single_student_report_wizard_reveals_optional_feedback_field(self) -> None:
        dialog = StudentReportWizardDialog(
            {
                "student_dimensions": [],
                "group_dimensions": [],
                "participants": [{"student_id": 12, "name": "Mila de Vries"}],
            },
            False,
        )
        self.assertIsNotNone(dialog.feedback)
        self.assertEqual(12, dialog.selected_student_id())
        self.assertTrue(dialog.feedback_text.isHidden())
        dialog.feedback.setChecked(True)
        dialog.feedback_text.setPlainText("Persoonlijke opmerking")
        self.assertFalse(dialog.feedback_text.isHidden())
        self.assertEqual("Persoonlijke opmerking", dialog.selected_options()["feedback_text"])
        dialog.close()

    def test_batch_report_wizard_has_no_personal_feedback_option(self) -> None:
        dialog = StudentReportWizardDialog({"student_dimensions": [], "group_dimensions": []}, True)
        self.assertIsNone(dialog.feedback)
        self.assertIsNone(dialog.selected_student_id())
        self.assertFalse(dialog.selected_options()["include_feedback"])
        dialog.close()

    def question_database_payload(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "title": "Arbeid berekenen",
            "question_text": "Bereken de arbeid bij een kracht van 20 N over 3 m.",
            "short_description": "Arbeid bij constante kracht",
            "status": "Actief",
            "maximum_score": 3.0,
            "expected_time_minutes": 4.0,
            "is_multiple_choice": 0,
            "multiple_choice_answer": "",
            "taxonomy_values": {},
            "property_values": {},
            "subquestions": [],
        }
        payload.update(overrides)
        return payload

    def test_question_database_dialog_requires_one_explicit_question_structure(self) -> None:
        dialog = QuestionDatabaseDialog([], [])

        self.assertTrue(dialog.single_question.isChecked())
        self.assertFalse(dialog.question_with_subquestions.isChecked())
        self.assertFalse(dialog.maximum_score.isHidden())
        self.assertTrue(dialog.subquestion_table.isHidden())

        dialog.question_with_subquestions.setChecked(True)
        QApplication.processEvents()

        self.assertFalse(dialog.single_question.isChecked())
        self.assertTrue(dialog.maximum_score.isHidden())
        self.assertTrue(dialog.is_multiple_choice.isHidden())
        self.assertFalse(dialog.subquestion_table.isHidden())
        self.assertGreaterEqual(dialog.subquestion_count.minimum(), 2)
        self.assertIn("geen score", dialog.structure_explanation.text())
        dialog.close()

    def test_question_database_subquestion_payload_has_no_separate_scored_main_question(self) -> None:
        dialog = QuestionDatabaseDialog([], [])
        dialog.title.setText("Hoofdvraag kracht")
        dialog.question_with_subquestions.setChecked(True)
        dialog.subquestion_count.setValue(2)
        QApplication.processEvents()
        dialog.subquestion_rows[0]["maximum_score"].setValue(2)
        dialog.subquestion_rows[1]["maximum_score"].setValue(3)

        payload = dialog.payload()

        self.assertEqual(5.0, payload["maximum_score"])
        self.assertEqual(0, payload["is_multiple_choice"])
        self.assertEqual(["a", "b"], [row["subquestion"] for row in payload["subquestions"]])
        self.assertEqual([2, 3], [row["maximum_score"] for row in payload["subquestions"]])
        dialog.close()

    def test_existing_database_question_with_subquestions_opens_in_subquestion_mode(self) -> None:
        dialog = QuestionDatabaseDialog(
            [],
            [],
            version={"title": "Vraaggroep", "question_text": "Beantwoord a en b."},
            subquestions=[
                {"subquestion": "a", "maximum_score": 1},
                {"subquestion": "b", "maximum_score": 2},
            ],
        )

        self.assertTrue(dialog.question_with_subquestions.isChecked())
        self.assertEqual(2, dialog.subquestion_count.value())
        self.assertTrue(dialog.maximum_score.isHidden())
        self.assertFalse(dialog.subquestion_table.isHidden())
        dialog.close()

    def test_question_database_title_change_keeps_same_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                page = QuestionDatabasePage(database, year_id)
                item_id = page.save_new_question(self.question_database_payload())
                version_id = database.scalar(
                    "SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)
                )
                version, subquestions, taxonomy_values, property_values = page.load_version(version_id)
                changed_payload = self.question_database_payload(
                    title="Arbeid berekenen met formule",
                    short_description="Alleen de omschrijving is aangescherpt",
                )

                self.assertFalse(
                    page.is_significant_version_change(
                        version, subquestions, taxonomy_values, property_values, changed_payload
                    )
                )
                page.update_existing_version(version_id, item_id, changed_payload)
                database.connection.commit()

                self.assertEqual(
                    1,
                    database.scalar("SELECT COUNT(*) FROM question_bank_versions WHERE item_id=?", (item_id,)),
                )
                self.assertEqual(
                    "Arbeid berekenen met formule",
                    database.scalar("SELECT title FROM question_bank_items WHERE id=?", (item_id,)),
                )
                page.close()
            finally:
                database.close()

    def test_question_database_metadata_and_status_change_keeps_same_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    ("Analyseveld", "keuzelijst", '["A", "B"]'),
                )
                property_id = int(database.scalar("SELECT id FROM property_definitions WHERE name='Analyseveld'"))
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                page = QuestionDatabasePage(database, year_id)
                item_id = page.save_new_question(
                    self.question_database_payload(property_values={property_id: "A"})
                )
                version_id = database.scalar(
                    "SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)
                )
                version, subquestions, taxonomy_values, property_values = page.load_version(version_id)
                changed_payload = self.question_database_payload(
                    status="Gearchiveerd",
                    property_values={property_id: "B"},
                )

                self.assertFalse(
                    page.is_significant_version_change(
                        version, subquestions, taxonomy_values, property_values, changed_payload
                    )
                )
                page.update_existing_version(version_id, item_id, changed_payload)
                database.connection.commit()

                self.assertEqual(
                    1,
                    database.scalar("SELECT COUNT(*) FROM question_bank_versions WHERE item_id=?", (item_id,)),
                )
                self.assertEqual(
                    "Gearchiveerd",
                    database.scalar("SELECT status FROM question_bank_items WHERE id=?", (item_id,)),
                )
                page.close()
            finally:
                database.close()

    def test_question_database_content_change_creates_new_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                page = QuestionDatabasePage(database, year_id)
                item_id = page.save_new_question(self.question_database_payload())
                version_id = database.scalar(
                    "SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)
                )
                version, subquestions, taxonomy_values, property_values = page.load_version(version_id)
                changed_payload = self.question_database_payload(
                    question_text="Bereken de arbeid bij een kracht van 25 N over 3 m."
                )

                self.assertTrue(
                    page.is_significant_version_change(
                        version, subquestions, taxonomy_values, property_values, changed_payload
                    )
                )
                page.save_new_version(item_id, changed_payload)
                database.connection.commit()

                self.assertEqual(
                    2,
                    database.scalar("SELECT COUNT(*) FROM question_bank_versions WHERE item_id=?", (item_id,)),
                )
                self.assertEqual(
                    2,
                    database.scalar("SELECT MAX(version_number) FROM question_bank_versions WHERE item_id=?", (item_id,)),
                )
                page.close()
            finally:
                database.close()

    def test_question_database_points_change_creates_new_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                page = QuestionDatabasePage(database, year_id)
                item_id = page.save_new_question(self.question_database_payload())
                version_id = database.scalar(
                    "SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)
                )
                version, subquestions, taxonomy_values, property_values = page.load_version(version_id)
                changed_payload = self.question_database_payload(maximum_score=4.0)

                self.assertTrue(
                    page.is_significant_version_change(
                        version, subquestions, taxonomy_values, property_values, changed_payload
                    )
                )
                page.close()
            finally:
                database.close()

    def test_question_database_page_filters_by_classification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    ("Testdomein", "keuzelijst", '["Mechanica", "Elektriciteit"]'),
                )
                property_id = database.scalar("SELECT id FROM property_definitions WHERE name='Testdomein'")
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                page = QuestionDatabasePage(database, year_id)
                page.save_new_question(
                    self.question_database_payload(
                        title="Kracht berekenen",
                        property_values={property_id: "Mechanica"},
                    )
                )
                page.save_new_question(
                    self.question_database_payload(
                        title="Spanning berekenen",
                        property_values={property_id: "Elektriciteit"},
                    )
                )
                page.refresh()

                page.filters.property_filters[property_id].setCurrentText("Mechanica")

                self.assertEqual(1, page.table.rowCount())
                self.assertEqual("Kracht berekenen", page.table.item(0, 0).text())
                self.assertIn("1 van 2", page.count_label.text())
                page.close()
            finally:
                database.close()

    def test_question_database_selection_dialog_filters_by_taxonomy_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                rtti_id = database.scalar("SELECT id FROM taxonomy_definitions WHERE name='RTTI'")
                r_value_id = database.scalar(
                    "SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name='R'",
                    (rtti_id,),
                )
                t1_value_id = database.scalar(
                    "SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name='T1'",
                    (rtti_id,),
                )
                page = QuestionDatabasePage(database, database.scalar("SELECT id FROM school_years LIMIT 1"))
                page.save_new_question(
                    self.question_database_payload(
                        title="Definitie arbeid",
                        taxonomy_values={rtti_id: r_value_id},
                    )
                )
                page.save_new_question(
                    self.question_database_payload(
                        title="Kracht berekenen",
                        taxonomy_values={rtti_id: t1_value_id},
                    )
                )
                rows = page.latest_versions()
                dialog = QuestionDatabaseSelectionDialog(rows, database)

                dialog.filters.taxonomy_filters[rtti_id].setCurrentText("T1")
                self.assertEqual(1, dialog.table.rowCount())
                self.assertEqual("Kracht berekenen", dialog.table.item(0, 0).text())

                dialog.filters.search.setText("definitie")
                self.assertEqual(0, dialog.table.rowCount())
                dialog.filters.taxonomy_filters[rtti_id].setCurrentIndex(0)
                self.assertEqual(1, dialog.table.rowCount())
                self.assertEqual("Definitie arbeid", dialog.table.item(0, 0).text())
                dialog.close()
                page.close()
            finally:
                database.close()

    def test_database_description_and_test_description_remain_separate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
                    (year_id, "SE1", "Toetsweek 1", "SE"),
                )
                test_id = database.scalar("SELECT id FROM tests WHERE name='SE1'")
                database_page = QuestionDatabasePage(database, year_id)
                item_id = database_page.save_new_question(
                    self.question_database_payload(short_description="Algemene databaseomschrijving")
                )
                version_id = database.scalar(
                    "SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)
                )
                version, subquestions, taxonomy_values, property_values = database_page.load_version(version_id)

                question_ids = MatrixPage.insert_database_question_rows(
                    database,
                    test_id,
                    "1",
                    item_id,
                    version_id,
                    version,
                    subquestions,
                    taxonomy_values,
                    property_values,
                )
                question_id = question_ids[0]
                self.assertEqual(
                    "",
                    database.scalar("SELECT short_description FROM matrix_questions WHERE id=?", (question_id,)),
                )
                database.execute(
                    "UPDATE matrix_questions SET short_description=? WHERE id=?",
                    ("Omschrijving voor deze toets", question_id),
                )

                changed_source = dict(version)
                changed_source["short_description"] = "Gewijzigde databaseomschrijving"
                database_page.update_linked_matrix_question(
                    question_id,
                    "1",
                    None,
                    changed_source,
                    item_id,
                    version_id,
                    None,
                    taxonomy_values,
                    property_values,
                )
                database.connection.commit()

                self.assertEqual(
                    "Omschrijving voor deze toets",
                    database.scalar("SELECT short_description FROM matrix_questions WHERE id=?", (question_id,)),
                )
                database_page.refresh()
                database_page.filters.search.setText("Omschrijving voor deze toets")
                self.assertEqual(1, database_page.table.rowCount())
                database_page.table.selectRow(0)
                database_page.update_usage()
                self.assertIn("Omschrijving voor deze toets", database_page.usage.text())
                database_page.close()
            finally:
                database.close()

    def test_database_question_only_copies_metadata_enabled_for_the_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    ("Domein HAVO", "keuzelijst", '["B1: Informatieverdracht"]'),
                )
                database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    ("Domein VWO", "keuzelijst", '["C1: Dynamica"]'),
                )
                havo_property_id = int(
                    database.scalar("SELECT id FROM property_definitions WHERE name='Domein HAVO'")
                )
                vwo_property_id = int(
                    database.scalar("SELECT id FROM property_definitions WHERE name='Domein VWO'")
                )
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type, level) VALUES(?, ?, ?, ?, ?)",
                    (year_id, "Havo toets", "Toetsweek 1", "SE", "havo"),
                )
                test_id = int(database.scalar("SELECT id FROM tests WHERE name='Havo toets'"))
                database.execute(
                    "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)",
                    (test_id, havo_property_id),
                )
                database.execute(
                    "INSERT INTO test_property_option_selections(test_id, property_id, value) VALUES(?, ?, ?)",
                    (test_id, havo_property_id, "B1: Informatieverdracht"),
                )
                database_page = QuestionDatabasePage(database, year_id)
                item_id = database_page.save_new_question(
                    self.question_database_payload(
                        property_values={
                            havo_property_id: "B1: Informatieverdracht",
                            vwo_property_id: "C1: Dynamica",
                        }
                    )
                )
                version_id = int(
                    database.scalar("SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,))
                )
                version, subquestions, taxonomy_values, property_values = database_page.load_version(version_id)

                question_id = MatrixPage.insert_database_question_rows(
                    database,
                    test_id,
                    "1",
                    item_id,
                    version_id,
                    version,
                    subquestions,
                    taxonomy_values,
                    property_values,
                )[0]

                self.assertEqual(
                    "B1: Informatieverdracht",
                    database.scalar(
                        "SELECT value FROM question_property_values WHERE question_id=? AND property_id=?",
                        (question_id, havo_property_id),
                    ),
                )
                self.assertIsNone(
                    database.scalar(
                        "SELECT value FROM question_property_values WHERE question_id=? AND property_id=?",
                        (question_id, vwo_property_id),
                    )
                )
                self.assertEqual(
                    0,
                    database.scalar(
                        "SELECT COUNT(*) FROM test_property_selections WHERE test_id=? AND property_id=?",
                        (test_id, vwo_property_id),
                    ),
                )
                database_page.close()
            finally:
                database.close()

    def test_database_question_skips_property_options_not_enabled_for_the_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    ("Niveaudomein", "keuzelijst", '["HAVO", "VWO"]'),
                )
                property_id = int(database.scalar("SELECT id FROM property_definitions WHERE name='Niveaudomein'"))
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
                    (year_id, "Havo toets", "Toetsweek 1", "SE"),
                )
                test_id = int(database.scalar("SELECT id FROM tests WHERE name='Havo toets'"))
                database.execute(
                    "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)",
                    (test_id, property_id),
                )
                database.execute(
                    "INSERT INTO test_property_option_selections(test_id, property_id, value) VALUES(?, ?, ?)",
                    (test_id, property_id, "HAVO"),
                )
                database_page = QuestionDatabasePage(database, year_id)
                item_id = database_page.save_new_question(
                    self.question_database_payload(property_values={property_id: "VWO"})
                )
                version_id = int(
                    database.scalar("SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,))
                )
                version, subquestions, taxonomy_values, property_values = database_page.load_version(version_id)

                question_id = MatrixPage.insert_database_question_rows(
                    database,
                    test_id,
                    "1",
                    item_id,
                    version_id,
                    version,
                    subquestions,
                    taxonomy_values,
                    property_values,
                )[0]

                self.assertIsNone(
                    database.scalar(
                        "SELECT value FROM question_property_values WHERE question_id=? AND property_id=?",
                        (question_id, property_id),
                    )
                )
                database_page.close()
            finally:
                database.close()

    def test_database_subquestion_metadata_is_copied_per_subquestion(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    ("Subonderdeel", "keuzelijst", '["Hoofdvraag", "Subvraag A"]'),
                )
                property_id = int(database.scalar("SELECT id FROM property_definitions WHERE name='Subonderdeel'"))
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
                    (year_id, "SE1", "Toetsweek 1", "SE"),
                )
                test_id = int(database.scalar("SELECT id FROM tests WHERE name='SE1'"))
                database.execute(
                    "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)",
                    (test_id, property_id),
                )
                for value in ("Hoofdvraag", "Subvraag A"):
                    database.execute(
                        "INSERT INTO test_property_option_selections(test_id, property_id, value) VALUES(?, ?, ?)",
                        (test_id, property_id, value),
                    )
                database_page = QuestionDatabasePage(database, year_id)
                item_id = database_page.save_new_question(
                    self.question_database_payload(
                        maximum_score=3.0,
                        property_values={property_id: "Hoofdvraag"},
                        subquestions=[
                            {
                                "subquestion": "a",
                                "question_text": "Subvraag a",
                                "short_description": "",
                                "maximum_score": 1,
                                "expected_time_minutes": None,
                                "is_multiple_choice": 0,
                                "multiple_choice_answer": None,
                                "sort_order": 0,
                                "property_values": {property_id: "Subvraag A"},
                                "taxonomy_values": {},
                            },
                            {
                                "subquestion": "b",
                                "question_text": "Subvraag b",
                                "short_description": "",
                                "maximum_score": 2,
                                "expected_time_minutes": None,
                                "is_multiple_choice": 0,
                                "multiple_choice_answer": None,
                                "sort_order": 1,
                                "property_values": {},
                                "taxonomy_values": {},
                            },
                        ],
                    )
                )
                version_id = int(
                    database.scalar("SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,))
                )
                version, subquestions, taxonomy_values, property_values = database_page.load_version(version_id)
                question_ids = MatrixPage.insert_database_question_rows(
                    database,
                    test_id,
                    "3",
                    item_id,
                    version_id,
                    version,
                    subquestions,
                    taxonomy_values,
                    property_values,
                )
                value_by_question = {
                    int(row["question_id"]): row["value"]
                    for row in database.rows(
                        "SELECT question_id, value FROM question_property_values WHERE property_id=?",
                        (property_id,),
                    )
                }

                self.assertEqual("Subvraag A", value_by_question.get(question_ids[0]))
                self.assertNotIn(question_ids[1], value_by_question)
                database_page.close()
            finally:
                database.close()

    def test_question_overview_database_import_can_store_extra_metadata_not_on_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    ("Niveaudomein", "keuzelijst", '["HAVO", "VWO"]'),
                )
                property_id = int(database.scalar("SELECT id FROM property_definitions WHERE name='Niveaudomein'"))
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type, level) VALUES(?, ?, ?, ?, ?)",
                    (year_id, "Havo toets", "Toetsweek 1", "SE", "havo"),
                )
                test_id = int(database.scalar("SELECT id FROM tests WHERE name='Havo toets'"))
                database.execute(
                    "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
                    (test_id, "1", 3),
                )
                question_id = int(database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,)))
                rows = [dict(row) for row in database.rows("SELECT * FROM matrix_questions WHERE id=?", (question_id,))]
                page = MatrixPage(database, year_id)
                dialog = QuestionDatabaseImportDialog(
                    "Vraag 1",
                    [],
                    [{"id": property_id, "name": "Niveaudomein", "field_type": "keuzelijst", "choices_json": '["HAVO", "VWO"]'}],
                    rows,
                    {},
                    {},
                )
                dialog.property_widgets[property_id].setCurrentText("VWO")
                dialog.question_text.setPlainText("Volledige databasevraag bij deze toetsvraag.")
                payload = dialog.payload()

                item_id = page.create_question_database_item_from_rows(
                    str(payload["title"]),
                    str(payload["short_description"]),
                    rows,
                    str(payload["status"]),
                    dict(payload["taxonomy_values"]),
                    dict(payload["property_values"]),
                    dict(payload["subquestion_metadata"]),
                    question_text=str(payload["question_text"]),
                )
                database.connection.commit()
                version_id = int(database.scalar("SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)))

                self.assertEqual(
                    "Volledige databasevraag bij deze toetsvraag.",
                    database.scalar("SELECT question_text FROM question_bank_versions WHERE id=?", (version_id,)),
                )
                self.assertEqual(
                    "VWO",
                    database.scalar(
                        "SELECT value FROM question_bank_version_property_values WHERE version_id=? AND property_id=?",
                        (version_id, property_id),
                    ),
                )
                self.assertIsNone(
                    database.scalar(
                        "SELECT value FROM question_property_values WHERE question_id=? AND property_id=?",
                        (question_id, property_id),
                    )
                )
                self.assertEqual(
                    item_id,
                    database.scalar("SELECT question_bank_id FROM matrix_questions WHERE id=?", (question_id,)),
                )
                dialog.close()
                page.close()
            finally:
                database.close()

    def test_question_overview_database_import_saves_subquestion_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                database.execute(
                    "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
                    ("DatabaseSubmeta", "keuzelijst", '["A", "B"]'),
                )
                property_id = int(database.scalar("SELECT id FROM property_definitions WHERE name='DatabaseSubmeta'"))
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
                    (year_id, "SE1", "Toetsweek 1", "SE"),
                )
                test_id = int(database.scalar("SELECT id FROM tests WHERE name='SE1'"))
                for subquestion, maximum in (("a", 1), ("b", 2)):
                    database.execute(
                        "INSERT INTO matrix_questions(test_id, question_number, subquestion, maximum_score) VALUES(?, ?, ?, ?)",
                        (test_id, "3", subquestion, maximum),
                    )
                rows = [
                    dict(row)
                    for row in database.rows(
                        "SELECT * FROM matrix_questions WHERE test_id=? ORDER BY subquestion",
                        (test_id,),
                    )
                ]
                page = MatrixPage(database, year_id)
                item_id = page.create_question_database_item_from_rows(
                    "Vraag 3",
                    "Vraaggroep",
                    rows,
                    "Actief",
                    {},
                    {},
                    {
                        int(rows[0]["id"]): {
                            "question_text": "Tekst voor database-subvraag a",
                            "short_description": "Databaseomschrijving subvraag a",
                            "taxonomy_values": {},
                            "property_values": {property_id: "A"},
                        }
                    },
                    question_text="Hoofdvraagtekst voor vraag 3",
                )
                database.connection.commit()
                version_id = int(database.scalar("SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)))
                subquestion_id = int(
                    database.scalar(
                        "SELECT id FROM question_bank_subquestions WHERE version_id=? AND subquestion='a'",
                        (version_id,),
                    )
                )

                self.assertEqual(
                    "Hoofdvraagtekst voor vraag 3",
                    database.scalar("SELECT question_text FROM question_bank_versions WHERE id=?", (version_id,)),
                )
                self.assertEqual(
                    "Tekst voor database-subvraag a",
                    database.scalar("SELECT question_text FROM question_bank_subquestions WHERE id=?", (subquestion_id,)),
                )
                self.assertEqual(
                    "Databaseomschrijving subvraag a",
                    database.scalar("SELECT short_description FROM question_bank_subquestions WHERE id=?", (subquestion_id,)),
                )
                self.assertEqual(
                    "A",
                    database.scalar(
                        "SELECT value FROM question_bank_subquestion_property_values WHERE subquestion_id=? AND property_id=?",
                        (subquestion_id, property_id),
                    ),
                )
                page.close()
            finally:
                database.close()

    def test_question_database_analysis_breaks_down_by_group_level_and_year(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO classes(school_year_id, name, level, grade_year) VALUES(?, ?, ?, ?)",
                    (year_id, "H4A", "havo", "4"),
                )
                class_id = int(database.scalar("SELECT id FROM classes WHERE name='H4A'"))
                student_ids = []
                for display_name in ("Sven Leijten", "Jordi van Roij"):
                    database.execute("INSERT INTO students(display_name) VALUES(?)", (display_name,))
                    student_id = int(database.scalar("SELECT id FROM students WHERE display_name=?", (display_name,)))
                    student_ids.append(student_id)
                    database.execute(
                        "INSERT INTO enrollments(student_id, class_id, school_year_id) VALUES(?, ?, ?)",
                        (student_id, class_id, year_id),
                    )
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year) VALUES(?, ?, ?, ?, ?, ?)",
                    (year_id, "SE1", "Toetsweek 1", "SE", "havo", "4"),
                )
                test_id = int(database.scalar("SELECT id FROM tests WHERE name='SE1'"))
                database.execute(
                    "INSERT INTO question_bank_items(title, short_description, status, maximum_score) VALUES(?, ?, ?, ?)",
                    ("Vraag kracht", "", "Actief", 4),
                )
                item_id = int(database.scalar("SELECT id FROM question_bank_items WHERE title='Vraag kracht'"))
                database.execute(
                    "INSERT INTO question_bank_versions(item_id, version_number, title, maximum_score) VALUES(?, ?, ?, ?)",
                    (item_id, 1, "Vraag kracht", 4),
                )
                version_id = int(database.scalar("SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)))
                database.execute(
                    "INSERT INTO matrix_questions(test_id, question_number, maximum_score, question_bank_id, question_bank_version_id) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (test_id, "1", 4, item_id, version_id),
                )
                database.execute(
                    "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
                    (test_id, "2", 2),
                )
                question_id = int(
                    database.scalar(
                        "SELECT id FROM matrix_questions WHERE test_id=? AND question_bank_id=?",
                        (test_id, item_id),
                    )
                )
                extra_question_id = int(
                    database.scalar(
                        "SELECT id FROM matrix_questions WHERE test_id=? AND question_bank_id IS NULL",
                        (test_id,),
                    )
                )
                attempt_data = [
                    (student_ids[0], 5, 3, 2),
                    (student_ids[1], 1, 1, 0),
                ]
                for student_id, total_score, bank_score, extra_score in attempt_data:
                    database.execute(
                        "INSERT INTO test_attempts(test_id, student_id, status, total_score) VALUES(?, ?, ?, ?)",
                        (test_id, student_id, "gemaakt", total_score),
                    )
                    attempt_id = int(
                        database.scalar(
                            "SELECT id FROM test_attempts WHERE test_id=? AND student_id=?",
                            (test_id, student_id),
                        )
                    )
                    database.execute(
                        "INSERT INTO scores(attempt_id, question_id, score) VALUES(?, ?, ?)",
                        (attempt_id, question_id, bank_score),
                    )
                    database.execute(
                        "INSERT INTO scores(attempt_id, question_id, score) VALUES(?, ?, ?)",
                        (attempt_id, extra_question_id, extra_score),
                    )
                dialog = QuestionDatabaseAnalysisDialog(database, item_id, version_id)
                entries = dialog.breakdown_entries(dialog._linked_rows())
                by_dimension = {(entry["dimension"], entry["category"]): entry for entry in entries}

                self.assertEqual(50, round(float(by_dimension[("Niveau", "havo")]["percentage"])))
                self.assertEqual(50, round(float(by_dimension[("Groep", "H4A")]["percentage"])))
                self.assertAlmostEqual(0.5, float(by_dimension[("Niveau", "havo")]["p_value"]))
                self.assertIsNotNone(by_dimension[("Niveau", "havo")]["rit"])
                self.assertIsNotNone(by_dimension[("Niveau", "havo")]["rir"])
                self.assertIn(("Schooljaar", "2025-2026"), by_dimension)
                self.assertIn(("Leerjaar", "4"), by_dimension)
                dialog.close()
            finally:
                database.close()

    def test_question_overview_delete_button_removes_question_without_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = SubjectDatabase.create(Path(directory) / "vak.db", "Natuurkunde", "2025-2026")
            try:
                year_id = database.scalar("SELECT id FROM school_years LIMIT 1")
                database.execute(
                    "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
                    (year_id, "SE1", "Toetsweek 1", "SE"),
                )
                test_id = database.scalar("SELECT id FROM tests WHERE name='SE1'")
                database.execute(
                    "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
                    (test_id, "1", 3),
                )
                page = MatrixPage(database, year_id)
                page.test.setCurrentIndex(page.test.findData(test_id))
                page.table.selectRow(0)

                delete_buttons = [
                    button for button in page.findChildren(QPushButton) if button.text() == "Vraag verwijderen"
                ]
                self.assertTrue(delete_buttons)
                with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
                    page.delete_question()

                self.assertEqual(
                    0,
                    database.scalar("SELECT COUNT(*) FROM matrix_questions WHERE test_id=?", (test_id,)),
                )
                page.close()
            finally:
                database.close()


if __name__ == "__main__":
    unittest.main()
