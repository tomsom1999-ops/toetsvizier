import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from toetsanalyse.norming_exports import build_participant_overview_html, export_participant_overview_xlsx


class NormingExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.test = {
            "name": "Toetsweek 1",
            "school_year": "2025-2026",
            "level": "havo",
            "grade_year": "4",
            "period": "Toetsweek 1",
        }
        self.rows = [
            {"name": "Bakker, Sophie", "score": 16, "percentage": 80, "grade": 8.2},
            {"name": "Jansen, Emma", "score": 8, "percentage": 40, "grade": 4.6},
        ]

    def test_pdf_overview_identifies_concept_norming_and_participant_status(self) -> None:
        html = build_participant_overview_html(self.test, 20, self.rows, "N-term", False)

        self.assertIn("Conceptnormering", html)
        self.assertIn("Bakker, Sophie", html)
        self.assertIn("Voldoende", html)
        self.assertIn("Onvoldoende", html)

    def test_excel_overview_writes_filterable_scored_table(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "overzicht.xlsx"
            export_participant_overview_xlsx(target, self.test, 20, self.rows, "N-term", True)

            workbook = load_workbook(target)
            sheet = workbook["Deelnemersoverzicht"]

        self.assertEqual("Vastgestelde normering", sheet["B4"].value)
        self.assertEqual("Deelnemer", sheet["B6"].value)
        self.assertEqual("Bakker, Sophie", sheet["B7"].value)
        self.assertEqual("Voldoende", sheet["F7"].value)
        self.assertEqual("A7", sheet.freeze_panes)
        self.assertEqual("A6:F8", sheet.auto_filter.ref)


if __name__ == "__main__":
    unittest.main()
