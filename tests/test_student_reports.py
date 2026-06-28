import unittest

from toetsanalyse.student_reports import (
    build_student_report_html,
    default_report_options,
    report_dimensions,
)


class StudentReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.student = {
            "student_id": 1,
            "name": "Noor Oberndorff",
            "total_score": 16,
            "score_percentage": 80,
            "grade": 7.8,
            "sufficient": True,
            "profiles": {
                "taxonomy_rtti": [
                    {"name": "R", "percentage": 75, "group_percentage": 62},
                    {"name": "T1", "percentage": 65, "group_percentage": 58},
                ],
                "property_taxonomie": [
                    {"name": "RTTI: R", "percentage": 75, "group_percentage": 62, "percentile": 90},
                    {"name": "RTTI: T1", "percentage": 65, "group_percentage": 58, "percentile": 70},
                ],
                "property_domein": [
                    {"name": "Mechanica", "percentage": 75, "group_percentage": 55},
                ],
            },
            "items": [
                {"label": "1", "component": "Mechanica", "score": 2, "maximum_score": 2},
                {"label": "2", "component": "Mechanica", "score": 0, "maximum_score": 3},
            ],
        }
        peer = {
            "student_id": 2,
            "name": "Andere Leerling",
            "total_score": 10,
            "score_percentage": 50,
            "profiles": {
                "property_taxonomie": [
                    {"name": "RTTI: R", "percentage": 50, "group_percentage": 62},
                    {"name": "RTTI: T1", "percentage": 42, "group_percentage": 58},
                ],
                "property_domein": [
                    {"name": "Mechanica", "percentage": 40, "group_percentage": 55},
                ],
            },
        }
        self.data = {
            "test": {"name": "SE1", "school_year": "2025-2026", "level": "havo", "grade_year": "4"},
            "maximum_score": 20,
            "normalization_finalized": True,
            "participants": [self.student, peer],
            "student_dimensions": [
                {"key": "taxonomy_rtti", "title": "RTTI", "kind": "taxonomy"},
                {"key": "property_taxonomie", "title": "Taxonomie", "kind": "property"},
                {"key": "property_domein", "title": "Domein", "kind": "property"},
            ],
            "group_dimensions": [
                {"key": "taxonomy_rtti", "title": "RTTI", "kind": "taxonomy", "entries": [{"name": "R"}, {"name": "T1"}]},
                {"key": "property_taxonomie", "title": "Taxonomie", "kind": "property", "entries": [{"name": "RTTI: R"}, {"name": "RTTI: T1"}]},
                {"key": "property_domein", "title": "Domein", "kind": "property", "entries": [{"name": "Mechanica"}]},
            ],
        }

    def test_dimensions_collapse_duplicate_rtti_taxonomy_and_clean_labels(self) -> None:
        dimensions = report_dimensions(self.data)

        self.assertEqual(1, sum(dimension["title"] == "Taxonomie: RTTI" for dimension in dimensions))
        rtti = next(dimension for dimension in dimensions if dimension["title"] == "Taxonomie: RTTI")
        self.assertEqual(["R", "T1"], [entry["label"] for entry in rtti["entries"]])
        self.assertEqual("property_taxonomie", rtti["key"])

    def test_report_is_student_friendly_with_taxonomy_explanation_and_anonymous_heatmap(self) -> None:
        options = default_report_options(self.data)
        options["heatmap_key"] = "property_taxonomie"

        report = build_student_report_html(self.data, self.student, options)

        self.assertIn("Leerlingrapport - SE1", report)
        self.assertIn("% van de punten gescoord", report)
        self.assertIn("Taxonomie: RTTI", report)
        self.assertIn("RTTI beschrijft het type denkwerk", report)
        self.assertIn("beter dan 90% van de leerlingen", report)
        self.assertIn("Geanonimiseerde positiekaart", report)
        self.assertIn("Noor Oberndorff", report)
        self.assertNotIn("Andere Leerling", report)
        self.assertIn("Fout", report)
        self.assertIn("window.__chartsReady = true", report)
        self.assertIn("fitReportCards", report)
        self.assertIn("break-inside:avoid-page !important", report)

    def test_optional_sections_can_be_excluded(self) -> None:
        report = build_student_report_html(
            self.data,
            self.student,
            {
                "profile_keys": [],
                "include_question_analysis": False,
                "include_strengths": False,
                "include_heatmap": False,
            },
        )

        self.assertIn("Algemene gegevens", report)
        self.assertNotIn("Vraaganalyse", report)
        self.assertNotIn("Geanonimiseerde positiekaart", report)
        self.assertNotIn("RTTI beschrijft", report)

    def test_second_heatmap_is_optional_and_can_be_added(self) -> None:
        defaults = default_report_options(self.data)
        first_only = build_student_report_html(self.data, self.student, defaults)
        second = build_student_report_html(
            self.data,
            self.student,
            {
                **defaults,
                "include_second_heatmap": True,
                "second_heatmap_key": "overall",
            },
        )

        self.assertEqual(1, first_only.count("Geanonimiseerde positiekaart -"))
        self.assertEqual(2, second.count("Geanonimiseerde positiekaart -"))

    def test_personal_feedback_creates_an_extra_report_card_only_when_selected(self) -> None:
        report_without_feedback = build_student_report_html(self.data, self.student)
        report_with_feedback = build_student_report_html(
            self.data,
            self.student,
            {
                "include_feedback": True,
                "feedback_text": "Mooi gewerkt.\nLet volgende keer op je eenheden.",
            },
        )

        self.assertNotIn("Feedback van de docent", report_without_feedback)
        self.assertIn("Feedback van de docent", report_with_feedback)
        self.assertIn("Mooi gewerkt.<br>Let volgende keer op je eenheden.", report_with_feedback)

    def test_standard_taxonomy_explanations_include_obit_and_bloom(self) -> None:
        student = {
            **self.student,
            "profiles": {
                "taxonomy_obit": [{"name": "Begrijpen", "percentage": 70, "group_percentage": 60}],
                "taxonomy_bloom": [{"name": "Analyseren", "percentage": 55, "group_percentage": 50}],
            },
        }
        data = {
            **self.data,
            "participants": [student],
            "student_dimensions": [
                {"key": "taxonomy_obit", "title": "OBIT", "kind": "taxonomy"},
                {"key": "taxonomy_bloom", "title": "Bloom", "kind": "taxonomy"},
            ],
            "group_dimensions": [
                {"key": "taxonomy_obit", "title": "OBIT", "kind": "taxonomy", "entries": [{"name": "Begrijpen"}]},
                {"key": "taxonomy_bloom", "title": "Bloom", "kind": "taxonomy", "entries": [{"name": "Analyseren"}]},
            ],
        }

        report = build_student_report_html(data, student, {"include_heatmap": False})

        self.assertIn("OBIT beschrijft het leerproces", report)
        self.assertIn("Bloom ordent denkvaardigheden", report)

    def test_report_hides_grade_kpis_when_normalization_is_not_finalized(self) -> None:
        report = build_student_report_html(
            {**self.data, "normalization_finalized": False},
            self.student,
        )

        self.assertIn("Normering", report)
        self.assertIn("Nog niet vastgesteld", report)
        self.assertIn("Resultaat", report)
        self.assertIn("Nog niet beschikbaar", report)
        self.assertNotIn('<div class="label">Cijfer</div>', report)

    def test_report_theme_changes_title_and_audience_note(self) -> None:
        teacher_report = build_student_report_html(
            self.data,
            self.student,
            {"report_theme": "teacher", "include_heatmap": False},
        )
        section_report = build_student_report_html(
            self.data,
            self.student,
            {"report_theme": "section", "include_heatmap": False},
        )

        self.assertIn("Intern docentrapport - SE1", teacher_report)
        self.assertIn("Interne variant", teacher_report)
        self.assertIn("Sectierapport - SE1", section_report)
        self.assertIn("Sectievariant", section_report)


if __name__ == "__main__":
    unittest.main()
