import tempfile
import unittest
from pathlib import Path

from toetsanalyse.analysis import _metric_status, _rank_context, analysis_data
from toetsanalyse.analysis_dashboard import build_analysis_dashboard_html
from toetsanalyse.database import SubjectDatabase
from toetsanalyse.results import save_score
from toetsanalyse.student_attribute_analysis import (
    GROUP_ATTRIBUTE_KEY,
    analyzable_student_attributes,
    student_attribute_dimension_summary,
    student_attribute_grade_distribution,
    student_attribute_summary,
    student_attribute_year_comparison,
)


class SingleTestAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = SubjectDatabase.create(
            Path(self.temporary_directory.name) / "analyse.db", "Wiskunde", "2025-2026"
        )
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year) VALUES(?, ?, ?, ?, ?, ?)",
            (year_id, "Toetsweek 1", "Toetsweek 1", "Proefwerk", "havo", "4"),
        )
        self.test_id = self.database.scalar("SELECT id FROM tests LIMIT 1")
        for label, points in (("1", 4), ("2", 6)):
            self.database.execute(
                "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
                (self.test_id, label, points),
            )
        self.questions = [
            row["id"] for row in self.database.rows("SELECT id FROM matrix_questions WHERE test_id=? ORDER BY id", (self.test_id,))
        ]
        rtti = self.database.scalar("SELECT id FROM taxonomy_definitions WHERE name='RTTI'")
        t1 = self.database.scalar("SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name='T1'", (rtti,))
        r_value = self.database.scalar("SELECT id FROM taxonomy_values WHERE taxonomy_id=? AND name='R'", (rtti,))
        self.database.execute(
            "INSERT INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
            (self.questions[0], rtti, t1),
        )
        self.database.execute(
            "INSERT INTO question_taxonomy_values(question_id, taxonomy_id, taxonomy_value_id) VALUES(?, ?, ?)",
            (self.questions[1], rtti, r_value),
        )
        domain = self.database.scalar("SELECT id FROM property_definitions WHERE name='Domein'")
        question_type = self.database.scalar("SELECT id FROM property_definitions WHERE name='Vraagtype'")
        for question, domain_value, type_value in (
            (self.questions[0], "Getallen", "Bereken"),
            (self.questions[1], "Verhoudingen", "Leg uit"),
        ):
            self.database.execute(
                "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
                (question, domain, domain_value),
            )
            self.database.execute(
                "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
                (question, question_type, type_value),
            )
        for name, scores in (("Emma", (4, 6)), ("Liam", (2, 3)), ("Noah", (0, 0))):
            self.database.execute("INSERT INTO students(display_name) VALUES(?)", (name,))
            student_id = self.database.scalar("SELECT id FROM students WHERE display_name=?", (name,))
            for question, score in zip(self.questions, scores):
                save_score(self.database, self.test_id, student_id, question, str(score))

    def tearDown(self) -> None:
        self.database.close()
        self.temporary_directory.cleanup()

    def test_analysis_calculates_quality_item_and_group_values_for_one_test(self) -> None:
        data = analysis_data(self.database, self.test_id)

        self.assertEqual(3, data["participant_count"])
        self.assertTrue(data["sample"]["is_small_group"])
        self.assertIn("Voorzichtig interpreteren", data["sample"]["message"])
        self.assertFalse(data["normalization_finalized"])
        self.assertIsNone(data["summary"]["mean_grade"])
        self.assertIsNone(data["summary"]["sufficient_percentage"])
        self.assertTrue(all(participant["grade"] is None for participant in data["participants"]))
        self.assertAlmostEqual(0.5, data["quality"]["p_value"]["value"])
        self.assertAlmostEqual(0.96, data["quality"]["alpha"]["value"], places=2)
        self.assertAlmostEqual(10.0, data["quality"]["sem"]["value"], places=5)
        self.assertAlmostEqual(5.0, data["summary"]["median_score"], places=5)
        self.assertIsNone(data["summary"]["mode_score"])
        self.assertEqual(0, data["summary"]["mode_count"])
        self.assertAlmostEqual(1.0, data["item_analysis"][0]["rir"], places=5)
        self.assertIn("advieswaarden", data["item_analysis"][0]["status"]["reason"])
        self.assertNotIn("alpha_without", data["item_analysis"][0])
        self.assertEqual(["R", "T1"], [entry["name"] for entry in data["groups"]["rtti"]["entries"]])
        self.assertEqual(["Getallen", "Verhoudingen"], [entry["name"] for entry in data["groups"]["domains"]["entries"]])
        self.assertEqual(2, len(data["participants"][0]["items"]))
        self.assertEqual(1, data["participants"][0]["rank"])
        self.assertEqual(67, data["participants"][0]["percentile"])
        self.assertEqual("T1", data["participants"][0]["items"][0]["rtti"])
        self.assertEqual("Getallen", data["participants"][0]["items"][0]["component"])
        self.assertEqual(34, data["participants"][0]["profiles"]["taxonomy_rtti"][0]["top_percentage"])
        self.assertEqual(
            {"RTTI", "Domein", "Vraagtype"},
            {dimension["title"] for dimension in data["student_dimensions"]},
        )
        self.assertIn("Kleine groep", build_analysis_dashboard_html(data, "plotly.js"))

    def test_analysis_can_focus_on_named_analysis_part(self) -> None:
        self.database.execute(
            "INSERT INTO test_analysis_parts(test_id, name, sort_order) VALUES(?, ?, ?)",
            (self.test_id, "Rekenen", 0),
        )
        part_id = int(self.database.scalar("SELECT id FROM test_analysis_parts WHERE test_id=?", (self.test_id,)))
        self.database.execute(
            "INSERT INTO question_analysis_parts(question_id, part_id) VALUES(?, ?)",
            (self.questions[0], part_id),
        )

        data = analysis_data(self.database, self.test_id, analysis_part_id=part_id)

        self.assertEqual("Rekenen", data["subtest_context"]["name"])
        self.assertEqual(1, data["question_count"])
        self.assertEqual(4, data["maximum_score"])
        self.assertEqual(10, data["full_maximum_score"])
        self.assertAlmostEqual(50.0, data["summary"]["mean_score"] / data["maximum_score"] * 100)
        self.assertAlmostEqual(50.0, data["subtest_context"]["mean_percentage"])
        self.assertAlmostEqual(50.0, data["subtest_context"]["total_mean_percentage"])
        self.assertEqual(["T1"], [entry["name"] for entry in data["groups"]["rtti"]["entries"]])
        self.assertIn("subtestInsight", build_analysis_dashboard_html(data, "plotly.js"))

    def test_quality_indicators_use_advice_value_ranges(self) -> None:
        self.assertEqual("bad", _metric_status("p", 0.19)["level"])
        self.assertEqual("good", _metric_status("p", 0.50)["level"])
        self.assertEqual("bad", _metric_status("rit", 0.10)["level"])
        self.assertEqual("excellent", _metric_status("rir", 0.60)["level"])
        self.assertEqual("overlap", _metric_status("alpha", 0.97)["level"])
        self.assertEqual("good", _metric_status("sem", 4.9)["level"])
        self.assertEqual("attention", _metric_status("sem", 7.0)["level"])
        self.assertEqual("bad", _metric_status("sem", 10.1)["level"])

    def test_rank_context_reports_shared_positions_for_equal_scores(self) -> None:
        context = _rank_context(8.0, [10.0, 8.0, 8.0, 5.0])

        self.assertEqual(2, context["rank"])
        self.assertEqual(3, context["rank_end"])
        self.assertEqual(2, context["tied_count"])
        self.assertEqual(25, context["percentile"])
        self.assertEqual(50, context["top_percentage"])

    def test_analysis_contains_multiple_choice_overview_with_response_distribution(self) -> None:
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score, is_multiple_choice, multiple_choice_answer) "
            "VALUES(?, ?, ?, 1, ?)",
            (self.test_id, "3", 2, "A"),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE question_number='3'")
        for name, response in (("Emma", "A"), ("Liam", "B"), ("Noah", "A")):
            student_id = self.database.scalar("SELECT id FROM students WHERE display_name=?", (name,))
            save_score(self.database, self.test_id, student_id, question_id, response)

        data = analysis_data(self.database, self.test_id)
        multiple_choice = data["multiple_choice"]
        item = multiple_choice["items"][0]

        self.assertEqual(1, multiple_choice["summary"]["question_count"])
        self.assertEqual("3", item["label"])
        self.assertEqual(["A"], item["accepted_answers"])
        self.assertEqual(2, item["correct_count"])
        self.assertEqual(
            {"A": (2, True), "B": (1, False)},
            {entry["option"]: (entry["count"], entry["accepted"]) for entry in item["responses"]},
        )
        self.assertIn("Conclusie", build_analysis_dashboard_html(data, "plotly.js"))
        self.assertIn("Meerkeuzeanalyse", build_analysis_dashboard_html(data, "plotly.js"))

    def test_multiple_choice_n_response_is_not_listed_as_answer_option(self) -> None:
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score, is_multiple_choice, multiple_choice_answer) "
            "VALUES(?, ?, ?, 1, ?)",
            (self.test_id, "3", 2, "A"),
        )
        question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE question_number='3'")
        for name, response in (("Emma", "A"), ("Liam", "B"), ("Noah", "N")):
            student_id = self.database.scalar("SELECT id FROM students WHERE display_name=?", (name,))
            save_score(self.database, self.test_id, student_id, question_id, response)

        item = analysis_data(self.database, self.test_id)["multiple_choice"]["items"][0]

        self.assertEqual(1, item["not_made_count"])
        self.assertNotIn("N", {entry["option"] for entry in item["responses"]})
        self.assertEqual(
            {"A": (1, True), "B": (1, False)},
            {entry["option"]: (entry["count"], entry["accepted"]) for entry in item["responses"]},
        )

    def test_student_attribute_analysis_groups_by_choice_attribute_with_privacy_limit(self) -> None:
        self.database.execute(
            "INSERT INTO student_attributes(name, field_type, options_json) VALUES(?, ?, ?)",
            ("Profiel", "keuzelijst", '["N&T"]'),
        )
        self.database.execute(
            "INSERT INTO student_attributes(name, field_type) VALUES(?, ?)",
            ("Opmerking", "tekst"),
        )
        attribute_id = self.database.scalar("SELECT id FROM student_attributes WHERE name='Profiel'")
        grades = {"Emma": 8.0, "Liam": 5.5, "Noah": 3.5}
        for name, grade in grades.items():
            student_id = self.database.scalar("SELECT id FROM students WHERE display_name=?", (name,))
            self.database.execute(
                "INSERT INTO student_attribute_values(student_id, attribute_id, value) VALUES(?, ?, ?)",
                (student_id, attribute_id, "N&T"),
            )
            self.database.execute(
                "UPDATE test_attempts SET grade=? WHERE test_id=? AND student_id=?",
                (grade, self.test_id, student_id),
            )

        attributes = {row["name"] for row in analyzable_student_attributes(self.database)}
        self.assertIn("Profiel", attributes)
        self.assertNotIn("Opmerking", attributes)

        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        summary = student_attribute_summary(self.database, attribute_id=attribute_id, year_id=year_id)
        self.assertEqual(3, summary["total_students"])
        self.assertEqual(1, len(summary["rows"]))
        self.assertEqual("N&T", summary["rows"][0]["value"])
        self.assertAlmostEqual(50.0, summary["rows"][0]["mean_percentage"])

        rtti_id = self.database.scalar("SELECT id FROM taxonomy_definitions WHERE name='RTTI'")
        dimension = student_attribute_dimension_summary(
            self.database,
            attribute_id=attribute_id,
            dimension_kind="taxonomy",
            dimension_id=rtti_id,
            year_id=year_id,
        )
        self.assertEqual(["N&T", "N&T"], [row["value"] for row in dimension["rows"]])
        self.assertEqual(["R", "T1"], [row["dimension"] for row in dimension["rows"]])

        distribution = student_attribute_grade_distribution(
            self.database,
            attribute_id=attribute_id,
            year_id=year_id,
        )
        self.assertEqual(["< 4,0", "4,0 - 5,4", "5,5 - 6,9", "7,0 - 8,4", "8,5 - 10"], distribution["bins"])
        self.assertEqual([1, 0, 1, 1, 0], distribution["rows"][0]["bins"])

    def test_student_attribute_analysis_can_group_by_class_group(self) -> None:
        year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.execute(
            "INSERT INTO classes(school_year_id, name, level, grade_year) VALUES(?, ?, ?, ?)",
            (year_id, "H4A", "havo", "4"),
        )
        class_id = self.database.scalar("SELECT id FROM classes WHERE name='H4A'")
        for student in self.database.rows("SELECT id FROM students"):
            self.database.execute(
                "INSERT OR IGNORE INTO enrollments(student_id, class_id, school_year_id) VALUES(?, ?, ?)",
                (student["id"], class_id, year_id),
            )

        summary = student_attribute_summary(
            self.database,
            attribute_id=GROUP_ATTRIBUTE_KEY,
            year_id=year_id,
        )
        self.assertEqual(3, summary["total_students"])
        self.assertEqual(1, len(summary["rows"]))
        self.assertEqual("H4A", summary["rows"][0]["value"])
        self.assertAlmostEqual(50.0, summary["rows"][0]["mean_percentage"])

    def test_student_attribute_year_comparison_compares_same_attribute_value_between_years(self) -> None:
        self.database.execute(
            "INSERT INTO student_attributes(name, field_type, options_json) VALUES(?, ?, ?)",
            ("Profiel", "keuzelijst", '["N&T"]'),
        )
        attribute_id = self.database.scalar("SELECT id FROM student_attributes WHERE name='Profiel'")
        for student in self.database.rows("SELECT id FROM students"):
            self.database.execute(
                "INSERT INTO student_attribute_values(student_id, attribute_id, value) VALUES(?, ?, ?)",
                (student["id"], attribute_id, "N&T"),
            )
        base_year_id = self.database.scalar("SELECT id FROM school_years LIMIT 1")
        self.database.add_school_year("2026-2027")
        comparison_year_id = self.database.scalar("SELECT id FROM school_years WHERE name='2026-2027'")
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year) VALUES(?, ?, ?, ?, ?, ?)",
            (comparison_year_id, "Toetsweek 1 jaar 2", "Toetsweek 1", "Proefwerk", "havo", "4"),
        )
        next_test_id = self.database.scalar("SELECT id FROM tests WHERE name='Toetsweek 1 jaar 2'")
        self.database.execute(
            "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
            (next_test_id, "1", 10),
        )
        next_question_id = self.database.scalar("SELECT id FROM matrix_questions WHERE test_id=?", (next_test_id,))
        for name, score in (("Emma", 8), ("Liam", 6), ("Noah", 4)):
            student_id = self.database.scalar("SELECT id FROM students WHERE display_name=?", (name,))
            save_score(self.database, next_test_id, student_id, next_question_id, str(score))

        comparison = student_attribute_year_comparison(
            self.database,
            attribute_id=attribute_id,
            base_year_id=base_year_id,
            comparison_year_id=comparison_year_id,
            level="havo",
            grade_year="4",
        )

        self.assertEqual(1, len(comparison["rows"]))
        row = comparison["rows"][0]
        self.assertEqual("N&T", row["value"])
        self.assertAlmostEqual(50.0, row["base_mean_percentage"])
        self.assertAlmostEqual(60.0, row["comparison_mean_percentage"])
        self.assertAlmostEqual(10.0, row["difference"])

    def test_subquestions_get_main_question_statistics_and_hierarchical_rows(self) -> None:
        for subquestion, maximum in (("a", 2), ("b", 3)):
            self.database.execute(
                "INSERT INTO matrix_questions(test_id, question_number, subquestion, maximum_score) VALUES(?, ?, ?, ?)",
                (self.test_id, "3", subquestion, maximum),
            )
        subquestions = list(
            self.database.rows(
                "SELECT id, subquestion FROM matrix_questions WHERE test_id=? AND question_number='3' ORDER BY subquestion",
                (self.test_id,),
            )
        )
        score_rows = {
            "Emma": {"a": 2, "b": 3},
            "Liam": {"a": 1, "b": 2},
            "Noah": {"a": 0, "b": 0},
        }
        for name, scores in score_rows.items():
            student_id = self.database.scalar("SELECT id FROM students WHERE display_name=?", (name,))
            for question in subquestions:
                save_score(self.database, self.test_id, student_id, question["id"], str(scores[question["subquestion"]]))

        data = analysis_data(self.database, self.test_id)
        group = next(item for item in data["question_group_analysis"] if item["question_number"] == "3")

        self.assertEqual("group", group["row_type"])
        self.assertEqual("Vraag 3", group["display_label"])
        self.assertEqual(5.0, group["maximum_score"])
        self.assertAlmostEqual(8 / 15, group["p_value"], places=5)
        self.assertEqual(["a", "b"], [child["label"] for child in group["children"]])
        self.assertIsNotNone(group["rit"])
        self.assertIsNotNone(group["rir"])

        html = build_analysis_dashboard_html(data, "plotly.js")
        self.assertIn("Itemanalyse - hoofdvragen en subvragen", html)
        self.assertIn("item-label-sub", html)
        self.assertIn("question_group_analysis", html)

    def test_dashboard_has_three_single_test_views_without_trend_language(self) -> None:
        html = build_analysis_dashboard_html(analysis_data(self.database, self.test_id), "plotly.js")

        self.assertIn('data-tab="general"', html)
        self.assertIn('data-tab="group"', html)
        self.assertIn('data-tab="student"', html)
        self.assertIn("Toetsanalyse - ", html)
        self.assertIn("Cronbach's alpha", html)
        self.assertIn("SEM", html)
        self.assertIn("Itemanalyse", html)
        self.assertIn("Status en onderbouwing", html)
        self.assertNotIn("Alpha zonder vraag", html)
        self.assertIn("Scorebereik", html)
        self.assertIn("Verdeling van scores", html)
        self.assertNotIn("studentRadarChart", html)
        self.assertIn("renderGroupDimensionCards", html)
        self.assertIn("groupDimensionCards", html)
        self.assertIn("studentProfileCards", html)
        self.assertIn("studentBarProfileChart", html)
        self.assertIn("const gradesVisible = Boolean(data.normalization_finalized);", html)
        self.assertIn('id="groupGradesCard"', html)
        self.assertIn('id="groupCumulativeCard"', html)
        self.assertIn('id="groupGradesPendingCard"', html)
        self.assertIn("Er moet nog een normering worden vastgesteld", html)
        self.assertIn("gradesCard.style.display = gradesVisible ? \"\" : \"none\";", html)
        self.assertIn("pendingCard.style.display = gradesVisible ? \"none\" : \"\";", html)
        self.assertIn("Geanonimiseerde heatmap", html)
        self.assertIn("Heatmap per leerling", html)
        self.assertIn("studentHeatmapSelect", html)
        self.assertIn("groupHeatmapSelect", html)
        self.assertIn("selectedCells", html)
        self.assertIn("rankedColumns", html)
        self.assertIn('line:{color:"#f04491", width:4}', html)
        self.assertIn("Algemene score", html)
        self.assertIn("% van de punten gescoord", html)
        self.assertNotIn("(% goed)", html)
        self.assertIn("Groepsniveau", html)
        self.assertIn("beter dan ", html)
        self.assertIn("Vraaganalyse - overzicht", html)
        self.assertIn("Meerkeuzeanalyse", html)
        self.assertIn('<th>Vraag</th><th>Onderdeel</th><th>Score</th><th>Max.</th><th>Resultaat</th>', html)
        self.assertIn('level === "attention" ? "Deels goed" : "Fout"', html)
        self.assertIn("PDF genereren voor deze leerling", html)
        self.assertIn("PDF genereren voor alle leerlingen", html)
        self.assertIn("analysisBridge", html)
        self.assertIn("exportStudentReports", html)
        self.assertNotIn("vorige toets", html.lower())
        self.assertNotIn("ontwikkeling", html.lower())

    def test_resit_analysis_compares_original_and_resit_results(self) -> None:
        self.database.execute(
            "INSERT INTO tests(school_year_id, name, period, test_type, level, grade_year, is_resit, original_test_id) "
            "SELECT school_year_id, ?, ?, ?, level, grade_year, 1, id FROM tests WHERE id=?",
            ("Toetsweek 1 herkansing", "Toetsweek 2", "Herkansing", self.test_id),
        )
        resit_id = self.database.scalar("SELECT id FROM tests WHERE name='Toetsweek 1 herkansing'")
        resit_questions = []
        for label, points, question_type in (("1", 4, "Bereken"), ("2", 6, "Leg uit")):
            self.database.execute(
                "INSERT INTO matrix_questions(test_id, question_number, maximum_score) VALUES(?, ?, ?)",
                (resit_id, label, points),
            )
            question_id = self.database.scalar(
                "SELECT id FROM matrix_questions WHERE test_id=? AND question_number=?",
                (resit_id, label),
            )
            resit_questions.append(question_id)
            question_type_id = self.database.scalar("SELECT id FROM property_definitions WHERE name='Vraagtype'")
            self.database.execute(
                "INSERT INTO question_property_values(question_id, property_id, value) VALUES(?, ?, ?)",
                (question_id, question_type_id, question_type),
            )
        scores_by_student = {
            "Emma": (4, 6),
            "Liam": (4, 4),
            "Noah": (1, 1),
        }
        for name, scores in scores_by_student.items():
            student_id = self.database.scalar("SELECT id FROM students WHERE display_name=?", (name,))
            for question_id, score in zip(resit_questions, scores):
                save_score(self.database, resit_id, student_id, question_id, str(score))

        data = analysis_data(self.database, self.test_id)
        resit = data["resit_analysis"]
        html = build_analysis_dashboard_html(data, "plotly.js")

        self.assertIsNotNone(resit)
        self.assertEqual("Toetsweek 1", resit["original_test"]["name"])
        self.assertEqual("Toetsweek 1 herkansing", resit["resit_test"]["name"])
        self.assertEqual(3, resit["comparison_count"])
        self.assertEqual(2, resit["improved_count"])
        self.assertGreater(resit["mean_delta_percentage"], 0)
        self.assertTrue(resit["categories"])
        self.assertIn("Herkansingsanalyse", html)


if __name__ == "__main__":
    unittest.main()
