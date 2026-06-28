import tempfile
import unittest
from pathlib import Path

from toetsanalyse.database import SubjectDatabase
from toetsanalyse.norming import (
    calculate_grade,
    dashboard_data,
    default_settings,
    has_active_normalization,
    load_normalization,
    remove_normalization,
    round_grade,
    save_normalization,
    sufficient_score,
)
from toetsanalyse.norming_dashboard import build_norming_dashboard_html
from toetsanalyse.results import save_score


class NormingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = SubjectDatabase.create(
            Path(self.temporary_directory.name) / "wiskunde.db", "Wiskunde", "2025-2026"
        )
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year) VALUES(?, ?, ?, ?, ?, ?)",
            (year_id, "Toetsweek 1", "Toetsweek 1", "Proefwerk", "havo", "4"),
        )
        self.test_id = self.database.scalar("SELECT id FROM tests LIMIT 1")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (self.test_id, "1", 4),
        )
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (self.test_id, "2", 6),
        )
        self.question_ids = [
            row["id"] for row in self.database.rows("SELECT id FROM matrix_questions WHERE test_id=? ORDER BY id", (self.test_id,))
        ]
        self.database.execute("INSERT INTO students(display_name) VALUES(?)", ("Emma Janssen",))
        self.student_id = self.database.scalar("SELECT id FROM students LIMIT 1")
        save_score(self.database, self.test_id, self.student_id, self.question_ids[0], "2")
        save_score(self.database, self.test_id, self.student_id, self.question_ids[1], "3")

    def tearDown(self) -> None:
        self.database.close()
        self.temporary_directory.cleanup()

    def test_n_term_calculates_a_linear_grade(self) -> None:
        settings = default_settings(10)
        settings["method"] = "n_term"
        settings["n_term"] = 1.0

        self.assertEqual(5.5, calculate_grade(5, 10, settings))
        self.assertEqual(5.0, sufficient_score(10, settings))

    def test_n_term_uses_official_boundary_relations_at_extreme_scores(self) -> None:
        settings = default_settings(57)
        settings["method"] = "n_term"
        settings["n_term"] = 1.9

        self.assertEqual(1.3, calculate_grade(1, 57, settings))
        self.assertEqual(5.5, calculate_grade(23, 57, settings))
        self.assertEqual(9.9, calculate_grade(56, 57, settings))
        self.assertEqual(10.0, calculate_grade(57, 57, settings))

    def test_low_n_term_uses_official_boundary_relations_at_extreme_scores(self) -> None:
        settings = default_settings(48)
        settings["method"] = "n_term"
        settings["n_term"] = 0.7

        self.assertEqual(1.0, calculate_grade(0, 48, settings))
        self.assertEqual(9.6, calculate_grade(47, 48, settings))
        self.assertEqual(10.0, calculate_grade(48, 48, settings))

    def test_cesuur_with_kink_maps_pass_score_to_five_point_five(self) -> None:
        settings = default_settings(10)
        settings["method"] = "cesuur_knik"
        settings["pass_score"] = 6.0

        self.assertEqual(5.5, calculate_grade(6, 10, settings))
        self.assertEqual(6.0, sufficient_score(10, settings))

    def test_cito_linear_method_reaches_five_point_five_and_ten_at_defined_points(self) -> None:
        settings = default_settings(20)
        settings.update({"method": "cesuur", "pass_score": 12.0})

        self.assertEqual(1.0, calculate_grade(0, 20, settings))
        self.assertEqual(5.5, calculate_grade(12, 20, settings))
        self.assertEqual(10.0, calculate_grade(20, 20, settings))

    def test_cito_cvte_method_accepts_grensscore_and_applies_official_rounding(self) -> None:
        settings = default_settings(20)
        settings.update({"method": "cvte_cesuur", "pass_score": 12.0})

        save_normalization(self.database, self.test_id, {**settings, "pass_score": 6.0})

        self.assertEqual(5.5, calculate_grade(12, 20, settings))
        self.assertEqual(10.0, calculate_grade(20, 20, settings))
        stored = load_normalization(self.database, self.test_id)
        self.assertEqual("cvte_cesuur", stored["method"])
        self.assertEqual("standaard", stored["rounding_method"])
        self.assertEqual(1, stored["decimal_places"])

    def test_cito_cvte_method_rejects_grensscore_outside_quarter_to_three_quarters(self) -> None:
        settings = default_settings(10)
        settings.update({"method": "cvte_cesuur", "pass_score": 2.0})

        with self.assertRaises(ValueError):
            save_normalization(self.database, self.test_id, settings)

    def test_percentage_method_uses_percentage_for_five_point_five(self) -> None:
        settings = default_settings(20)
        settings.update({"method": "percentage_voldoende", "pass_percentage": 60.0})

        self.assertEqual(1.0, calculate_grade(0, 20, settings))
        self.assertEqual(5.5, calculate_grade(12, 20, settings))
        self.assertEqual(10.0, calculate_grade(20, 20, settings))
        self.assertEqual(12.0, sufficient_score(20, settings))

    def test_rounding_is_configurable_for_teacher_methods(self) -> None:
        self.assertEqual(5.5, round_grade(5.26, method="halve cijfers"))
        self.assertEqual(5.3, round_grade(5.21, method="naar boven"))

    def test_percentage_method_rejects_invalid_boundary(self) -> None:
        settings = default_settings(10)
        settings.update({"method": "percentage_voldoende", "pass_percentage": 100.0})

        with self.assertRaises(ValueError):
            save_normalization(self.database, self.test_id, settings)

    def test_saving_normalization_sets_active_config_and_student_grade(self) -> None:
        settings = default_settings(10)
        settings["method"] = "n_term"
        settings["n_term"] = 1.0

        save_normalization(self.database, self.test_id, settings)
        stored = load_normalization(self.database, self.test_id)
        grade = self.database.scalar("SELECT grade FROM test_attempts WHERE test_id=?", (self.test_id,))

        self.assertEqual("n_term", stored["method"])
        self.assertEqual(1.0, stored["n_term"])
        self.assertEqual(5.5, grade)
        self.assertEqual(1, self.database.scalar("SELECT COUNT(*) FROM normalizations WHERE is_active=1"))
        self.assertTrue(has_active_normalization(self.database, self.test_id))

    def test_saving_normalization_requires_questions_with_points(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type) VALUES(?, ?, ?, ?)",
            (year_id, "Lege toets", "Toetsweek 1", "SO"),
        )
        empty_test_id = self.database.scalar("SELECT id FROM tests WHERE name='Lege toets'")

        with self.assertRaisesRegex(ValueError, "toetsmatrijs"):
            save_normalization(self.database, empty_test_id, default_settings(0))

    def test_removing_established_normalization_clears_saved_values_and_grades(self) -> None:
        save_normalization(self.database, self.test_id, default_settings(10))

        remove_normalization(self.database, self.test_id)

        self.assertFalse(has_active_normalization(self.database, self.test_id))
        self.assertEqual(0, self.database.scalar("SELECT COUNT(*) FROM normalizations WHERE test_id=?", (self.test_id,)))
        self.assertIsNone(self.database.scalar("SELECT grade FROM test_attempts WHERE test_id=?", (self.test_id,)))

    def test_official_n_term_forces_official_rounding_and_rejects_two_decimal_n_term(self) -> None:
        settings = default_settings(10)
        settings.update({"method": "n_term", "n_term": 1.0, "rounding_method": "hele cijfers", "decimal_places": 0})

        save_normalization(self.database, self.test_id, settings)
        stored = load_normalization(self.database, self.test_id)

        self.assertEqual("standaard", stored["rounding_method"])
        self.assertEqual(1, stored["decimal_places"])
        settings["n_term"] = 1.05
        with self.assertRaises(ValueError):
            save_normalization(self.database, self.test_id, settings)

    def test_exceptional_n_term_above_two_is_supported(self) -> None:
        settings = default_settings(10)
        settings.update({"method": "n_term", "n_term": 2.5})

        save_normalization(self.database, self.test_id, settings)

        self.assertEqual(2.5, load_normalization(self.database, self.test_id)["n_term"])

    def test_dashboard_contains_scored_participants_and_modern_charts(self) -> None:
        data = dashboard_data(self.database, self.test_id)
        html = build_norming_dashboard_html(data, default_settings(10), "plotly.js")

        self.assertEqual("Emma Janssen", data["participants"][0]["name"])
        self.assertIn('id="scatter"', html)
        self.assertIn('id="histogram"', html)
        self.assertIn('id="participantRows"', html)
        self.assertIn('class="analytics-grid"', html)
        self.assertIn("compactStripPositions", html)
        self.assertIn("histogramBinSize", html)
        self.assertIn('<option value="4" selected>4 punten</option>', html)
        self.assertIn("let histogramBinSize = 4", html)
        self.assertIn("participantSort", html)
        self.assertIn("Excel exporteren", html)
        self.assertIn("PDF exporteren", html)
        self.assertIn("fixedrange:true", html)
        self.assertIn('data-expand="curve"', html)
        self.assertIn('data-expand="scatter"', html)
        self.assertIn('data-expand="histogram"', html)
        self.assertIn('id="chartModal"', html)
        self.assertIn("openExpandedChart", html)
        self.assertIn('aria-hidden="true" inert', html)
        self.assertIn('modal.setAttribute("inert", "")', html)
        self.assertIn("restoreFocus.focus()", html)
        self.assertIn("% van de punten gescoord voor 5,5", html)
        self.assertIn("Normering vaststellen", html)
        self.assertIn("Vastgestelde normering opheffen", html)
        self.assertNotIn("Omzettingstabel", html)

    def test_legacy_conversion_table_opens_as_percentage_method(self) -> None:
        self.database.execute(
            "INSERT INTO normalizations(test_id, method, configuration_json, is_active) VALUES(?, ?, ?, 1)",
            (self.test_id, "omzettingstabel", '{"pass_score": 6}'),
        )

        settings = load_normalization(self.database, self.test_id)

        self.assertEqual("percentage_voldoende", settings["method"])
        self.assertEqual(60.0, settings["pass_percentage"])

    def test_incomplete_result_is_excluded_from_norming_and_does_not_get_grade(self) -> None:
        self.database.execute("INSERT INTO students(display_name) VALUES(?)", ("Onvolledig",))
        partial_id = self.database.scalar("SELECT id FROM students WHERE display_name='Onvolledig'")
        save_score(self.database, self.test_id, partial_id, self.question_ids[0], "3")

        data = dashboard_data(self.database, self.test_id)
        save_normalization(self.database, self.test_id, default_settings(10))
        partial_grade = self.database.scalar(
            "SELECT grade FROM test_attempts WHERE test_id=? AND student_id=?",
            (self.test_id, partial_id),
        )

        self.assertEqual(1, data["incomplete_count"])
        self.assertEqual(["Emma Janssen"], [participant["name"] for participant in data["participants"]])
        self.assertIsNone(partial_grade)


if __name__ == "__main__":
    unittest.main()
