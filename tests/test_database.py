import os
import tempfile
import time
import unittest
import sqlite3
from pathlib import Path
from unittest.mock import patch

from toetsanalyse.database import SCHEMA_VERSION, SubjectDatabase


class SubjectDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "natuurkunde.db"
        self.database = SubjectDatabase.create(self.database_path, "Natuurkunde", "2025-2026")

    def tearDown(self) -> None:
        self.database.close()
        self.temporary_directory.cleanup()

    def test_new_database_has_subject_year_and_taxonomies(self) -> None:
        self.assertEqual("Natuurkunde", self.database.meta("subject_name"))
        self.assertEqual(1, self.database.scalar("SELECT COUNT(*) FROM school_years"))
        self.assertEqual(3, self.database.scalar("SELECT COUNT(*) FROM taxonomy_definitions"))

    def test_question_database_setting_is_saved_in_subject_database(self) -> None:
        self.assertEqual("0", self.database.meta("question_database_enabled", "0"))
        self.database.set_meta("question_database_enabled", "1")
        self.database.connection.commit()
        self.assertEqual("1", self.database.meta("question_database_enabled", "0"))

    def test_opening_older_schema_makes_pre_update_backup(self) -> None:
        backup_directory = Path(self.temporary_directory.name) / "schema_backups"
        self.database.set_meta("schema_version", str(SCHEMA_VERSION - 1))
        self.database.connection.commit()
        self.database.close()
        with patch("toetsanalyse.database.BACKUP_DIR", backup_directory):
            reopened = SubjectDatabase.open(self.database_path)
            try:
                self.assertEqual(str(SCHEMA_VERSION), reopened.meta("schema_version"))
            finally:
                reopened.close()
        backups = list(backup_directory.glob("natuurkunde-voor-update-v*.db"))
        self.assertEqual(1, len(backups))
        self.database = SubjectDatabase.open(self.database_path)

    def test_development_analysis_setting_is_saved_in_subject_database(self) -> None:
        self.assertEqual("0", self.database.meta("development_analysis_enabled", "0"))
        self.database.set_meta("development_analysis_enabled", "1")
        self.database.connection.commit()
        self.assertEqual("1", self.database.meta("development_analysis_enabled", "0"))

    def test_student_attribute_analysis_setting_is_saved_in_subject_database(self) -> None:
        self.assertEqual("0", self.database.meta("student_attribute_analysis_enabled", "0"))
        self.database.set_meta("student_attribute_analysis_enabled", "1")
        self.database.connection.commit()
        self.assertEqual("1", self.database.meta("student_attribute_analysis_enabled", "0"))

    def test_backups_are_labeled_and_old_automatic_backups_are_cleaned(self) -> None:
        backup_directory = Path(self.temporary_directory.name) / "backups"
        backup_directory.mkdir()
        old_timestamp = time.time() - 30 * 24 * 60 * 60
        with patch("toetsanalyse.database.BACKUP_DIR", backup_directory):
            manual = self.database.backup(automatic=False)
            self.assertIn("-handmatig-", manual.name)

            for index in range(35):
                old_backup = backup_directory / f"natuurkunde-auto-20240101-120000-{index:06d}.db"
                old_backup.write_text("oude automatische back-up")
                os.utime(old_backup, (old_timestamp + index, old_timestamp + index))
            legacy = backup_directory / "natuurkunde-20240101-120000.db"
            legacy.write_text("oude onherkenbare back-up")
            os.utime(legacy, (old_timestamp, old_timestamp))

            automatic = self.database.backup(automatic=True)
            self.assertIn("-auto-", automatic.name)
            self.assertLessEqual(len(list(backup_directory.glob("natuurkunde-auto-*.db"))), 30)
            self.assertTrue(manual.exists())
            self.assertTrue(legacy.exists())

    def test_question_database_status_column_exists_with_default(self) -> None:
        columns = {
            row["name"]
            for row in self.database.connection.execute("PRAGMA table_info(question_bank_items)").fetchall()
        }
        self.assertIn("status", columns)
        self.database.execute(
            "INSERT INTO question_bank_items(title, short_description, maximum_score) VALUES(?, ?, ?)",
            ("Vraag zonder status", "", 1),
        )
        self.assertEqual(
            "Actief",
            self.database.scalar("SELECT status FROM question_bank_items WHERE title='Vraag zonder status'"),
        )

    def test_matrix_question_can_link_to_question_database_version(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "SE1 Mechanica", "Periode 1", "SE"),
        )
        test_id = self.database.scalar("SELECT id FROM tests LIMIT 1")
        self.database.execute(
            "INSERT INTO question_bank_items(title, short_description, maximum_score) VALUES(?, ?, ?)",
            ("Arbeid berekenen", "Arbeid bij constante kracht", 3),
        )
        item_id = self.database.scalar("SELECT id FROM question_bank_items WHERE title='Arbeid berekenen'")
        self.database.execute(
            "INSERT INTO question_bank_versions(item_id, version_number, title, question_text, short_description, maximum_score) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (item_id, 1, "Arbeid berekenen", "Bereken de arbeid.", "Arbeid bij constante kracht", 3),
        )
        version_id = self.database.scalar("SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,))
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score, question_bank_id, question_bank_version_id) "
            "VALUES(?, ?, ?, ?, ?)",
            (test_id, "1", 3, item_id, version_id),
        )
        linked = self.database.rows(
            "SELECT q.question_number, i.title, v.version_number FROM matrix_questions q "
            "JOIN question_bank_items i ON i.id=q.question_bank_id "
            "JOIN question_bank_versions v ON v.id=q.question_bank_version_id "
            "WHERE q.test_id=?",
            (test_id,),
        )[0]
        self.assertEqual(("1", "Arbeid berekenen", 1), tuple(linked))

    def test_core_associations_and_question_total(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO classes(school_year_id, name, level, grade_year) VALUES(?, ?, ?, ?)",
            (year_id, "H4A", "havo", "4"),
        )
        class_id = self.database.scalar("SELECT id FROM classes WHERE name='H4A'")
        self.database.execute("INSERT INTO students(display_name) VALUES(?)", ("Sam Jansen",))
        student_id = self.database.scalar("SELECT id FROM students WHERE display_name='Sam Jansen'")
        self.database.execute(
            "INSERT INTO enrollments(student_id, class_id, school_year_id) VALUES(?, ?, ?)",
            (student_id, class_id, year_id),
        )
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "SE1 Mechanica", "Periode 1", "SE"),
        )
        test_id = self.database.scalar("SELECT id FROM tests LIMIT 1")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 4),
        )
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "2", 6),
        )
        total = self.database.scalar(
            "SELECT SUM(maximum_score) FROM matrix_questions WHERE test_id=?", (test_id,)
        )
        self.assertEqual(10, total)

    def test_class_and_student_details_can_be_changed(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO classes(school_year_id, name, level, grade_year) VALUES(?, ?, ?, ?)",
            (year_id, "H4A", "havo", "4"),
        )
        self.database.execute(
            "INSERT INTO classes(school_year_id, name, level, grade_year) VALUES(?, ?, ?, ?)",
            (year_id, "H4B", "havo", "4"),
        )
        first_class_id = self.database.scalar("SELECT id FROM classes WHERE name='H4A'")
        second_class_id = self.database.scalar("SELECT id FROM classes WHERE name='H4B'")
        self.database.execute(
            "UPDATE classes SET name=?, level=?, grade_year=? WHERE id=?",
            ("H5A", "havo", "5", first_class_id),
        )
        self.database.execute("INSERT INTO students(display_name, student_number) VALUES(?, ?)", ("Mila", "10"))
        student_id = self.database.scalar("SELECT id FROM students WHERE display_name='Mila'")
        self.database.execute(
            "INSERT INTO enrollments(student_id, class_id, school_year_id) VALUES(?, ?, ?)",
            (student_id, first_class_id, year_id),
        )
        self.database.execute(
            "UPDATE students SET display_name=?, student_number=? WHERE id=?",
            ("Mila de Vries", "11", student_id),
        )
        self.database.execute("UPDATE enrollments SET class_id=? WHERE student_id=?", (second_class_id, student_id))
        changed = self.database.rows(
            "SELECT s.display_name, s.student_number, c.name FROM students s "
            "JOIN enrollments e ON e.student_id=s.id JOIN classes c ON c.id=e.class_id WHERE s.id=?",
            (student_id,),
        )[0]
        self.assertEqual(("Mila de Vries", "11", "H4B"), tuple(changed))

    def test_student_extra_attribute_values_are_removed_with_student(self) -> None:
        self.database.execute(
            "INSERT INTO student_attributes(name, field_type) VALUES(?, ?)", ("Profiel", "tekst")
        )
        attribute_id = self.database.scalar("SELECT id FROM student_attributes WHERE name='Profiel'")
        self.database.execute("INSERT INTO students(display_name) VALUES(?)", ("Mila",))
        student_id = self.database.scalar("SELECT id FROM students WHERE display_name='Mila'")
        self.database.execute(
            "INSERT INTO student_attribute_values(student_id, attribute_id, value) VALUES(?, ?, ?)",
            (student_id, attribute_id, "Natuur en Techniek"),
        )
        self.assertEqual(
            "Natuur en Techniek",
            self.database.scalar("SELECT value FROM student_attribute_values WHERE student_id=?", (student_id,)),
        )
        self.database.execute("DELETE FROM students WHERE id=?", (student_id,))
        self.assertEqual(0, self.database.scalar("SELECT COUNT(*) FROM student_attribute_values"))

    def test_student_extra_attribute_values_are_removed_with_attribute(self) -> None:
        self.database.execute(
            "INSERT INTO student_attributes(name, field_type) VALUES(?, ?)", ("Mentor", "tekst")
        )
        attribute_id = self.database.scalar("SELECT id FROM student_attributes WHERE name='Mentor'")
        self.database.execute("INSERT INTO students(display_name) VALUES(?)", ("Lina",))
        student_id = self.database.scalar("SELECT id FROM students WHERE display_name='Lina'")
        self.database.execute(
            "INSERT INTO student_attribute_values(student_id, attribute_id, value) VALUES(?, ?, ?)",
            (student_id, attribute_id, "J. de Vries"),
        )
        self.database.execute("DELETE FROM student_attributes WHERE id=?", (attribute_id,))
        self.assertEqual(0, self.database.scalar("SELECT COUNT(*) FROM student_attribute_values"))

    def test_student_attribute_can_store_choice_options(self) -> None:
        self.database.execute(
            "INSERT INTO student_attributes(name, field_type, options_json) VALUES(?, ?, ?)",
            ("Profiel", "keuzelijst", '["N&T", "N&G"]'),
        )
        self.assertEqual(
            '["N&T", "N&G"]',
            self.database.scalar("SELECT options_json FROM student_attributes WHERE name='Profiel'"),
        )

    def test_test_can_be_renamed_and_delete_removes_matrix_questions(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "Oude naam", "Periode 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='Oude naam'")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 2),
        )
        self.database.execute("UPDATE tests SET name=?, period=? WHERE id=?", ("Nieuwe naam", "Toetsweek 1", test_id))
        self.assertEqual(
            ("Nieuwe naam", "Toetsweek 1"),
            tuple(self.database.rows("SELECT name, period FROM tests WHERE id=?", (test_id,))[0]),
        )
        self.database.execute("DELETE FROM tests WHERE id=?", (test_id,))
        self.assertEqual(0, self.database.scalar("SELECT COUNT(*) FROM matrix_questions WHERE test_id=?", (test_id,)))

    def test_test_weight_defaults_to_one_and_can_be_changed(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "Toets met weging", "Periode 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='Toets met weging'")
        self.assertEqual(1, self.database.scalar("SELECT weight FROM tests WHERE id=?", (test_id,)))
        self.database.execute("UPDATE tests SET weight=? WHERE id=?", (2.5, test_id))
        self.assertEqual(2.5, self.database.scalar("SELECT weight FROM tests WHERE id=?", (test_id,)))

    def test_existing_database_receives_weight_column_when_opened(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "bestaand.db"
        connection = sqlite3.connect(legacy_path)
        connection.executescript(
            """
            CREATE TABLE school_years (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                start_date TEXT,
                end_date TEXT,
                is_active INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_year_id INTEGER NOT NULL REFERENCES school_years(id),
                name TEXT NOT NULL,
                period TEXT NOT NULL,
                test_type TEXT NOT NULL
            );
            INSERT INTO school_years(name, is_active) VALUES('2024-2025', 1);
            INSERT INTO tests(school_year_id, name, period, test_type)
                VALUES(1, 'Bestaande toets', 'Periode 1', 'SO');
            """
        )
        connection.commit()
        connection.close()
        existing_database = SubjectDatabase.open(legacy_path)
        try:
            self.assertEqual(1, existing_database.scalar("SELECT weight FROM tests WHERE name='Bestaande toets'"))
        finally:
            existing_database.close()

    def test_existing_database_receives_question_database_columns_before_indexes(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "oude_vraagdatabase.db"
        connection = sqlite3.connect(legacy_path)
        connection.executescript(
            """
            CREATE TABLE matrix_questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id INTEGER NOT NULL,
                question_number TEXT NOT NULL,
                subquestion TEXT,
                maximum_score REAL NOT NULL,
                question_bank_id INTEGER
            );
            """
        )
        connection.commit()
        connection.close()

        existing_database = SubjectDatabase.open(legacy_path)
        try:
            columns = {
                row["name"]
                for row in existing_database.connection.execute("PRAGMA table_info(matrix_questions)").fetchall()
            }
            indexes = {
                row["name"]
                for row in existing_database.connection.execute("PRAGMA index_list(matrix_questions)").fetchall()
            }
            self.assertIn("question_bank_id", columns)
            self.assertIn("question_bank_version_id", columns)
            self.assertIn("question_bank_subquestion_id", columns)
            self.assertIn("idx_matrix_questions_bank", indexes)
            self.assertIn("idx_matrix_questions_bank_version", indexes)
        finally:
            existing_database.close()

    def test_student_number_key_is_unique_but_existing_duplicates_do_not_block_opening(self) -> None:
        legacy_path = Path(self.temporary_directory.name) / "dubbele_leerlingen.db"
        connection = sqlite3.connect(legacy_path)
        connection.executescript(
            """
            CREATE TABLE students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                student_number TEXT
            );
            INSERT INTO students(display_name, student_number) VALUES('Mila', '100');
            INSERT INTO students(display_name, student_number) VALUES('Mila dubbel', '100');
            """
        )
        connection.commit()
        connection.close()

        existing_database = SubjectDatabase.open(legacy_path)
        try:
            rows = existing_database.rows(
                "SELECT display_name, student_number_key FROM students ORDER BY id"
            )
            self.assertEqual("100", rows[0]["student_number_key"])
            self.assertIsNone(rows[1]["student_number_key"])
            with self.assertRaises(sqlite3.IntegrityError):
                existing_database.execute(
                    "INSERT INTO students(display_name, student_number) VALUES(?, ?)",
                    ("Nieuwe dubbel", "100"),
                )
        finally:
            existing_database.close()

    def test_resit_is_linked_to_original_test(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "SE1", "Toetsweek 1", "SE"),
        )
        original_id = self.database.scalar("SELECT id FROM tests WHERE name='SE1'")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type, is_resit, original_test_id) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (year_id, "SE1 herkansing", "Toetsweek 2", "Herkansing", 1, original_id),
        )
        relation = self.database.rows(
            "SELECT h.name, o.name FROM tests h JOIN tests o ON o.id=h.original_test_id WHERE h.is_resit=1"
        )[0]
        self.assertEqual(("SE1 herkansing", "SE1"), tuple(relation))

    def test_matrix_question_can_store_taxonomy_and_custom_property(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "SE1", "Toetsweek 1", "SE"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='SE1'")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 3),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,))
        rtti_id = self.database.scalar("SELECT id FROM taxonomy_definitions WHERE name='RTTI'")
        rtti_value_id = self.database.scalar(
            "SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name='T1'", (rtti_id,)
        )
        self.database.execute(
            "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
            ("Contextniveau", "keuzelijst", '["Laag", "Hoog"]'),
        )
        context_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Contextniveau'")
        self.database.execute(
            "INSERT INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
            (question_id, rtti_id, rtti_value_id),
        )
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_id, context_id, "Hoog"),
        )
        property_values = self.database.rows(
            "SELECT p.name, v.value FROM question_property_values v "
            "JOIN property_definitions p ON p.id=v.property_id WHERE v.question_id=?",
            (question_id,),
        )
        taxonomy_values = self.database.rows(
            "SELECT d.name, v.name FROM question_taxonomy_values q "
            "JOIN taxonomy_definitions d ON d.id=q.taxonomy_id "
            "JOIN taxonomy_values v ON v.id=q.taxonomy_value_id WHERE q.question_id=?",
            (question_id,),
        )
        self.assertEqual([("Contextniveau", "Hoog")], [tuple(row) for row in property_values])
        self.assertEqual([("RTTI", "T1")], [tuple(row) for row in taxonomy_values])

    def test_custom_taxonomy_values_can_be_added(self) -> None:
        cursor = self.database.connection.execute(
            "INSERT INTO taxonomy_definitions(name, is_standard) VALUES(?, 0)", ("Eigen denkniveau",)
        )
        for order, value in enumerate(["Basis", "Verdieping", "Transfer"]):
            self.database.connection.execute(
                "INSERT INTO taxonomy_values(taxonomy_id, name, sort_order) VALUES(?, ?, ?)",
                (cursor.lastrowid, value, order),
            )
        self.database.connection.commit()
        values = self.database.rows(
            "SELECT d.name, v.name FROM taxonomy_definitions d "
            "JOIN taxonomy_values v ON v.taxonomy_id=d.id WHERE d.name=? ORDER BY v.sort_order",
            ("Eigen denkniveau",),
        )
        self.assertEqual(
            [("Eigen denkniveau", "Basis"), ("Eigen denkniveau", "Verdieping"), ("Eigen denkniveau", "Transfer")],
            [tuple(row) for row in values],
        )

    def test_question_type_choices_can_be_configured_by_teacher(self) -> None:
        question_type_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Vraagtype'")
        self.database.execute(
            "UPDATE property_definitions SET choices_json=? WHERE id=?",
            ('["Leg uit", "Bereken", "Bepaal", "Teken"]', question_type_id),
        )
        stored = self.database.scalar(
            "SELECT choices_json FROM property_definitions WHERE id=?", (question_type_id,)
        )
        self.assertEqual('["Leg uit", "Bereken", "Bepaal", "Teken"]', stored)

    def test_question_type_option_can_be_added_renamed_and_removed(self) -> None:
        property_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Vraagtype'")
        self.database.execute(
            "UPDATE property_definitions SET choices_json=? WHERE id=?",
            ('["Leg uit", "Bereken"]', property_id),
        )
        self.database.execute(
            "UPDATE property_definitions SET choices_json=? WHERE id=?",
            ('["Leg uit", "Bereken", "Teken"]', property_id),
        )
        self.database.execute(
            "UPDATE property_definitions SET choices_json=? WHERE id=?",
            ('["Leg uit", "Bereken", "Schets"]', property_id),
        )
        self.database.execute(
            "UPDATE property_definitions SET choices_json=? WHERE id=?",
            ('["Leg uit", "Schets"]', property_id),
        )
        self.assertEqual(
            '["Leg uit", "Schets"]',
            self.database.scalar("SELECT choices_json FROM property_definitions WHERE id=?", (property_id,)),
        )

    def test_renamed_question_type_option_updates_used_question_value(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "SO1", "Periode 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='SO1'")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 1),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,))
        property_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Vraagtype'")
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_id, property_id, "Bepaal"),
        )
        self.database.execute(
            "UPDATE question_property_values SET value=? WHERE property_id=? AND value=?",
            ("Leid af", property_id, "Bepaal"),
        )
        self.assertEqual(
            "Leid af",
            self.database.scalar("SELECT value FROM question_property_values WHERE question_id=?", (question_id,)),
        )

    def test_optional_question_classification_value_can_be_removed(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "SO1", "Periode 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='SO1'")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 1),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,))
        question_type_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Vraagtype'")
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_id, question_type_id, "Bereken"),
        )
        self.database.execute(
            "DELETE FROM question_property_values WHERE question_id=? AND property_id=?",
            (question_id, question_type_id),
        )
        self.assertEqual(
            0,
            self.database.scalar("SELECT COUNT(*) FROM question_property_values WHERE question_id=?", (question_id,)),
        )

    def test_test_can_select_multiple_taxonomies_and_question_fields(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "SE meerdere taxonomieen", "Toetsweek 1", "SE"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='SE meerdere taxonomieen'")
        rtti_id = self.database.scalar("SELECT id FROM taxonomy_definitions WHERE name='RTTI'")
        bloom_id = self.database.scalar("SELECT id FROM taxonomy_definitions WHERE name='Bloom'")
        vraagtype_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Vraagtype'")
        self.database.execute(
            "INSERT INTO test_taxonomy_selections(test_id, taxonomy_id) VALUES(?, ?)", (test_id, rtti_id)
        )
        self.database.execute(
            "INSERT INTO test_taxonomy_selections(test_id, taxonomy_id) VALUES(?, ?)", (test_id, bloom_id)
        )
        self.database.execute(
            "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)", (test_id, vraagtype_id)
        )
        self.database.execute(
            "INSERT INTO test_property_option_selections(test_id, property_id, value) VALUES(?, ?, ?)",
            (test_id, vraagtype_id, "Bereken"),
        )
        self.assertEqual(
            2, self.database.scalar("SELECT COUNT(*) FROM test_taxonomy_selections WHERE test_id=?", (test_id,))
        )
        self.assertEqual(
            1, self.database.scalar("SELECT COUNT(*) FROM test_property_selections WHERE test_id=?", (test_id,))
        )
        self.assertEqual(
            "Bereken",
            self.database.scalar("SELECT value FROM test_property_option_selections WHERE test_id=?", (test_id,)),
        )
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 2),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,))
        rtti_value_id = self.database.scalar(
            "SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name='T2'", (rtti_id,)
        )
        bloom_value_id = self.database.scalar(
            "SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name='Analyseren'", (bloom_id,)
        )
        self.database.execute(
            "INSERT INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
            (question_id, rtti_id, rtti_value_id),
        )
        self.database.execute(
            "INSERT INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
            (question_id, bloom_id, bloom_value_id),
        )
        self.assertEqual(
            2, self.database.scalar("SELECT COUNT(*) FROM question_taxonomy_values WHERE question_id=?", (question_id,))
        )

    def test_existing_test_can_receive_classification_added_later(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "Bestaande toets", "Toetsweek 1", "SE"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='Bestaande toets'")
        self.database.execute(
            "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
            ("Werkwijze", "keuzelijst", '["Exact", "Schatting"]'),
        )
        property_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Werkwijze'")

        self.database.execute(
            "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)",
            (test_id, property_id),
        )

        selected = self.database.rows(
            "SELECT p.name, p.choices_json FROM test_property_selections s "
            "JOIN property_definitions p ON p.id=s.property_id WHERE s.test_id=?",
            (test_id,),
        )[0]
        self.assertEqual(("Werkwijze", '["Exact", "Schatting"]'), tuple(selected))

    def test_legacy_single_taxonomy_value_is_converted_when_database_reopens(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "Oude toets", "Periode 1", "SO"),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name='Oude toets'")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (test_id, "1", 1),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (test_id,))
        self.database.execute(
            "INSERT INTO property_definitions(name, field_type) VALUES(?, ?)", ("Taxonomie", "keuzelijst")
        )
        legacy_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Taxonomie'")
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_id, legacy_id, "RTTI: R"),
        )
        self.database.close()
        self.database = SubjectDatabase.open(self.database_path)
        self.assertEqual(
            1, self.database.scalar("SELECT COUNT(*) FROM question_taxonomy_values WHERE question_id=?", (question_id,))
        )
        self.assertEqual(
            1, self.database.scalar("SELECT COUNT(*) FROM test_taxonomy_selections WHERE test_id=?", (test_id,))
        )
        self.assertEqual(
            0, self.database.scalar("SELECT is_active FROM property_definitions WHERE name='Taxonomie'")
        )

    def test_class_link_count_is_available_before_user_confirms_deletion(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO classes(school_year_id, name) VALUES(?, ?)", (year_id, "Cluster A")
        )
        class_id = self.database.scalar("SELECT id FROM classes WHERE name='Cluster A'")
        self.database.execute("INSERT INTO students(display_name) VALUES(?)", ("Mila",))
        student_id = self.database.scalar("SELECT id FROM students WHERE display_name='Mila'")
        self.database.execute(
            "INSERT INTO enrollments(student_id, class_id, school_year_id) VALUES(?, ?, ?)",
            (student_id, class_id, year_id),
        )
        self.assertEqual(1, self.database.scalar("SELECT COUNT(*) FROM enrollments WHERE class_id=?", (class_id,)))


if __name__ == "__main__":
    unittest.main()
