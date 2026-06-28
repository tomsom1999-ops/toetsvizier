from __future__ import annotations

import unittest

from toetsanalyse.analysis_exports import build_section_analysis_report_html


class AnalysisExportReportTests(unittest.TestCase):
    def test_section_report_contains_selected_analysis_sections(self) -> None:
        data = {
            "test": {
                "name": "SE1 Mechanica",
                "school_year": "2025-2026",
                "period": "Toetsweek 1",
                "level": "havo",
                "grade_year": "4",
            },
            "participant_count": 2,
            "question_count": 1,
            "maximum_score": 4,
            "summary": {"mean_score": 2.5, "median_score": 2.5, "mode_score": 2, "mode_count": 1},
            "quality": {
                "alpha": {"value": 0.74, "status": {"label": "Goed", "level": "good", "advice": "Voldoende betrouwbaar."}},
                "p_value": {"value": 0.62, "status": {"label": "Goed", "level": "good", "advice": "Passend."}},
                "rit": {"value": 0.31, "status": {"label": "Goed", "level": "good", "advice": "Onderscheidt voldoende."}},
                "rir": {"value": 0.28, "status": {"label": "Redelijk", "level": "attention", "advice": "Bespreekbaar."}},
                "sem": {"value": 7.5, "score_value": 0.3, "status": {"label": "Redelijk", "level": "attention", "advice": "Acceptabel."}},
            },
            "question_group_analysis": [
                {
                    "label": "1",
                    "display_label": "1",
                    "description": "Krachten berekenen",
                    "maximum_score": 4,
                    "p_value": 0.62,
                    "rit": 0.31,
                    "rir": 0.28,
                    "status": {"label": "Goed", "level": "good", "reason": "De vraag past bij de toets."},
                    "children": [],
                }
            ],
            "multiple_choice": {
                "items": [
                    {
                        "label": "1",
                        "answer_key": "B",
                        "accepted_answers": ["B"],
                        "not_made_count": 1,
                        "p_value": 0.62,
                        "rit": 0.31,
                        "rir": 0.28,
                        "responses": [
                            {"option": "A", "count": 1, "accepted": False},
                            {"option": "B", "count": 1, "accepted": True},
                        ],
                        "conclusion": {"label": "Goed", "level": "good", "text": "De vraag functioneert voldoende."},
                    }
                ]
            },
            "group_dimensions": [
                {
                    "title": "Taxonomie RTTI",
                    "entries": [
                        {"name": "R", "percentage": 70},
                        {"name": "T1", "percentage": 45},
                    ],
                }
            ],
            "participants": [{"name": "Sanne Jansen", "total_score": 3, "score_percentage": 75, "grade": 7.0, "rank": 1}],
        }
        html = build_section_analysis_report_html(
            data,
            {
                "summary": True,
                "item_analysis": True,
                "multiple_choice": True,
                "group_analysis": True,
                "participants": False,
            },
        )
        self.assertIn("Sectierapport toetsanalyse", html)
        self.assertIn("SE1 Mechanica", html)
        self.assertIn("Itemanalyse", html)
        self.assertIn("Meerkeuzeanalyse", html)
        self.assertIn("N-score", html)
        self.assertIn("Taxonomie RTTI", html)
        self.assertNotIn("Sanne Jansen", html)


if __name__ == "__main__":
    unittest.main()
