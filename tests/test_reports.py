import tempfile
import unittest
from pathlib import Path

from toetsanalyse.database import SubjectDatabase
from toetsanalyse.reports import build_matrix_report_html


class MatrixReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = SubjectDatabase.create(
            Path(self.temporary_directory.name) / "natuurkunde.db", "Natuurkunde", "2025-2026"
        )
        self.year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.rtti_id = self.database.scalar("SELECT id FROM taxonomy_definitions WHERE name='RTTI'")
        self.question_type_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Vraagtype'")
        self.domain_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Domein'")

    def tearDown(self) -> None:
        self.database.close()
        self.temporary_directory.cleanup()

    def add_test(self, name: str, original_id: int | None = None) -> int:
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year, "
            "available_time_minutes, is_resit, original_test_id) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                self.year_id,
                name,
                "Toetsweek 1",
                "Herkansing" if original_id else "SE",
                "havo",
                "4",
                50,
                int(original_id is not None),
                original_id,
            ),
        )
        test_id = self.database.scalar("SELECT id FROM tests WHERE name=?", (name,))
        self.database.execute(
            "INSERT INTO test_taxonomy_selections(test_id, taxonomy_id) VALUES(?, ?)",
            (test_id, self.rtti_id),
        )
        for property_id in (self.question_type_id, self.domain_id):
            self.database.execute(
                "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)",
                (test_id, property_id),
            )
        return test_id

    def add_question(self, test_id: int, number: str, points: float, taxonomy: str, question_type: str) -> None:
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score, expected_time_minutes) "
            "VALUES(?, ?, ?, ?)",
            (test_id, number, points, points * 2),
        )
        question_id = self.database.scalar(
            "SELECT id FROM matrix_questions WHERE test_id=? AND question_number=?", (test_id, number)
        )
        taxonomy_value_id = self.database.scalar(
            "SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name=?", (self.rtti_id, taxonomy)
        )
        self.database.execute(
            "INSERT INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
            (question_id, self.rtti_id, taxonomy_value_id),
        )
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_id, self.question_type_id, question_type),
        )
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_id, self.domain_id, "Mechanica"),
        )

    def test_matrix_report_contains_general_information_and_distributions(self) -> None:
        test_id = self.add_test("SE1 Mechanica")
        self.database.execute(
            "INSERT INTO classes(school_year_id, name) VALUES(?, ?)", (self.year_id, "ha4.na1")
        )
        self.database.execute(
            "INSERT INTO classes(school_year_id, name) VALUES(?, ?)", (self.year_id, "ha4.na2")
        )
        for name in ("ha4.na1", "ha4.na2"):
            class_id = self.database.scalar("SELECT id FROM classes WHERE name=?", (name,))
            self.database.execute(
                "INSERT INTO test_classes(test_id, class_id) VALUES(?, ?)", (test_id, class_id)
            )
        self.add_question(test_id, "1", 4, "R", "Bereken")
        self.add_question(test_id, "2", 6, "T1", "Leg uit")

        html = build_matrix_report_html(self.database, test_id)

        self.assertIn("1. Algemene gegevens over de toets", html)
        self.assertIn("2. Toetsmatrijs", html)
        self.assertIn("3. Verdeling op basis van onderdelen", html)
        self.assertIn("info-grid", html)
        self.assertIn("matrix-table", html)
        self.assertIn("chart-grid", html)
        self.assertIn("SE1 Mechanica", html)
        self.assertIn("Toetsweek 1", html)
        self.assertIn("ha4.na1, ha4.na2", html)
        self.assertIn("Vraagtype", html)
        self.assertIn("Bereken", html)
        self.assertIn("Domein", html)
        self.assertIn("Mechanica", html)
        self.assertIn("RTTI-niveaus", html)
        self.assertIn("Domeinen", html)
        self.assertIn("Vraagtypes", html)
        self.assertIn("Tijdsverdeling", html)
        self.assertIn("Totaal:", html)
        self.assertIn("cdn.jsdelivr.net/npm/apexcharts", html)
        self.assertIn("distribution-chart", html)
        self.assertIn("window.__chartsReady = true", html)
        self.assertNotIn("Kwaliteitsstatus", html)
        self.assertNotIn("Grootste aandeel", html)
        self.assertIn("[[PAGE_BREAK]]", html)
        self.assertEqual(3, html.count("[[PAGE_BREAK]]"))
        self.assertNotIn("Vergelijking met originele toets", html)

    def test_resit_report_names_original_test_without_separate_analysis_page(self) -> None:
        original_id = self.add_test("SE1 origineel")
        self.add_question(original_id, "1", 10, "R", "Bereken")
        resit_id = self.add_test("SE1 herkansing", original_id)
        self.add_question(resit_id, "1", 5, "T1", "Leg uit")
        self.add_question(resit_id, "2", 5, "T1", "Leg uit")

        html = build_matrix_report_html(self.database, resit_id)

        self.assertIn("Herkansing van", html)
        self.assertIn("SE1 origineel", html)
        self.assertIn("4. Vergelijking met originele toets", html)
        self.assertIn("Originele toets - SE1 origineel", html)
        self.assertIn("Herkansing - SE1 herkansing", html)
        self.assertIn("comparison-grid", html)

    def test_report_omits_time_distribution_without_time_values(self) -> None:
        test_id = self.add_test("SE zonder tijd")
        self.add_question(test_id, "1", 5, "R", "Bereken")
        self.database.execute(
            "UPDATE matrix_questions SET expected_time_minutes=NULL WHERE test_id=?", (test_id,)
        )

        html = build_matrix_report_html(self.database, test_id)

        self.assertNotIn("<h3>Tijdsverdeling</h3>", html)

    def test_report_shows_distribution_for_extra_property(self) -> None:
        test_id = self.add_test("SE met extra eigenschap")
        self.database.execute(
            "INSERT INTO property_definitions(name, field_type, is_active) VALUES(?, ?, 1)",
            ("Context", "text"),
        )
        context_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Context'")
        self.database.execute(
            "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)",
            (test_id, context_id),
        )
        self.add_question(test_id, "1", 4, "R", "Bereken")
        self.add_question(test_id, "2", 6, "T1", "Leg uit")
        question_ids = self.database.rows(
            "SELECT id FROM matrix_questions WHERE test_id=? ORDER BY id",
            (test_id,),
        )
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_ids[0]["id"], context_id, "Praktijk"),
        )
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_ids[1]["id"], context_id, "Theorie"),
        )

        html = build_matrix_report_html(self.database, test_id)

        self.assertIn("<h3>Context</h3>", html)

    def test_distribution_prefers_filled_property_value_over_empty_duplicate(self) -> None:
        test_id = self.add_test("SE hoofdstuk")
        self.database.execute(
            "INSERT INTO property_definitions(name, field_type, is_active) VALUES(?, ?, 1)",
            ("Hoofdstuk", "text"),
        )
        chapter_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Hoofdstuk'")
        self.database.execute(
            "INSERT INTO test_property_selections(test_id, property_id) VALUES(?, ?)",
            (test_id, chapter_id),
        )
        self.add_question(test_id, "1", 4, "R", "Bereken")
        question_id = self.database.scalar(
            "SELECT id FROM matrix_questions WHERE test_id=? AND question_number='1'",
            (test_id,),
        )
        self.database.execute(
            "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
            (question_id, chapter_id, ""),
        )
        self.database.execute(
            "UPDATE question_property_values SET value=? WHERE question_id=? AND property_id=?",
            ("H1", question_id, chapter_id),
        )

        html = build_matrix_report_html(self.database, test_id)

        self.assertIn("<h3>Hoofdstuk</h3>", html)
        self.assertIn("H1", html)


if __name__ == "__main__":
    unittest.main()
