import unittest
from unittest.mock import patch

from toetsanalyse.pdf_export import PdfExportError, browser_report_html, export_html_to_pdf


class BrowserPdfExportTests(unittest.TestCase):
    def test_qt_page_markers_become_browser_print_breaks(self) -> None:
        html = "<html><head></head><body><p class=\"pdf-break\">[[PAGE_BREAK]]</p><div>Matrijs</div></body></html>"

        printable = browser_report_html(html)

        self.assertNotIn("[[PAGE_BREAK]]", printable)
        self.assertIn("browser-page-break", printable)
        self.assertIn("break-before: page", printable)

    def test_print_html_preserves_background_colors_and_card_integrity_rules(self) -> None:
        printable = browser_report_html("<html><head></head><body></body></html>")

        self.assertIn("-webkit-print-color-adjust: exact", printable)
        self.assertIn(".distribution-card", printable)
        self.assertIn("break-inside: avoid-page !important", printable)

    def test_missing_playwright_mentions_chromium_install_command(self) -> None:
        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            with self.assertRaises(PdfExportError) as context:
                export_html_to_pdf("<html></html>", "rapport.pdf")

        self.assertIn("python -m pip install -r requirements.txt", str(context.exception))


if __name__ == "__main__":
    unittest.main()
