import tempfile
import unittest
from pathlib import Path

from toetsanalyse.database import SubjectDatabase
from toetsanalyse.question_bank import (
    load_active_question_properties,
    load_all_taxonomies,
    question_database_distinct_property_values,
    question_database_enabled,
    question_database_latest_rows,
)


class QuestionBankServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = SubjectDatabase.create(
            Path(self.temporary_directory.name) / "vak.db", "Natuurkunde", "2025-2026"
        )

    def tearDown(self) -> None:
        self.database.close()
        self.temporary_directory.cleanup()

    def test_question_database_enabled_reads_subject_setting(self) -> None:
        self.assertFalse(question_database_enabled(self.database))

        self.database.set_meta("question_database_enabled", "1")
        self.database.connection.commit()

        self.assertTrue(question_database_enabled(self.database))

    def test_taxonomies_and_active_properties_are_loaded_for_question_database_filters(self) -> None:
        self.database.execute(
            "INSERT INTO property_definitions(name, field_type, choices_json, is_active) VALUES(?, ?, ?, ?)",
            ("Hoofdstuk", "keuzelijst", '["H1", "H2"]', 1),
        )
        self.database.execute(
            "INSERT INTO property_definitions(name, field_type, choices_json, is_active) VALUES(?, ?, ?, ?)",
            ("Oud veld", "tekst", None, 0),
        )

        taxonomies = load_all_taxonomies(self.database)
        properties = load_active_question_properties(self.database)

        self.assertGreaterEqual(len(taxonomies), 3)
        self.assertIn("RTTI", {taxonomy["name"] for taxonomy in taxonomies})
        property_names = {property_definition["name"] for property_definition in properties}
        self.assertIn("Hoofdstuk", property_names)
        self.assertNotIn("Oud veld", property_names)

    def test_latest_rows_include_usage_and_filter_metadata(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "SE1", "Toetsweek 1", "SE"),
        )
        test_id = int(self.database.scalar("SELECT id FROM tests WHERE name='SE1'"))
        rtti_id = int(self.database.scalar("SELECT id FROM taxonomy_definitions WHERE name='RTTI'"))
        rtti_value_id = int(
            self.database.scalar("SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name='T1'", (rtti_id,))
        )
        self.database.execute(
            "INSERT INTO property_definitions(name, field_type, choices_json) VALUES(?, ?, ?)",
            ("Hoofdstuk", "keuzelijst", '["H1", "H2"]'),
        )
        property_id = int(self.database.scalar("SELECT id FROM property_definitions WHERE name='Hoofdstuk'"))
        self.database.execute(
            "INSERT INTO question_bank_items(title, short_description, status, maximum_score) VALUES(?, ?, ?, ?)",
            ("Kracht berekenen", "Databaseomschrijving", "Actief", 3),
        )
        item_id = int(self.database.scalar("SELECT id FROM question_bank_items WHERE title='Kracht berekenen'"))
        self.database.execute(
            "INSERT INTO question_bank_versions(item_id, version_number, title, question_text, short_description, maximum_score) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (item_id, 1, "Kracht berekenen", "Bereken F.", "Databaseomschrijving", 3),
        )
        version_id = int(self.database.scalar("SELECT id FROM question_bank_versions WHERE item_id=?", (item_id,)))
        self.database.execute(
            "INSERT INTO question_bank_version_taxonomy_values(version_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
            (version_id, rtti_id, rtti_value_id),
        )
        self.database.execute(
            "INSERT INTO question_bank_version_property_values(version_id, property_id, value) VALUES(?, ?, ?)",
            (version_id, property_id, "H1"),
        )
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score, short_description, question_bank_id, question_bank_version_id) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (test_id, "1", 3, "Toetsomschrijving", item_id, version_id),
        )

        rows = question_database_latest_rows(self.database)

        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual("Kracht berekenen", row["title"])
        self.assertEqual(1, row["usage_count"])
        self.assertIn("Toetsomschrijving", row["usage_description_summary"])
        self.assertIn("RTTI: T1", row["taxonomy_summary"])
        self.assertIn("Hoofdstuk: H1", row["property_summary"])
        self.assertIn(f"{rtti_id}={rtti_value_id}", row["taxonomy_filters"])
        self.assertIn(f"{property_id}=h1", row["property_filters"])
        self.assertEqual(["H1"], question_database_distinct_property_values(self.database, property_id))


if __name__ == "__main__":
    unittest.main()
