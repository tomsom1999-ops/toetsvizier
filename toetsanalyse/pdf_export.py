from __future__ import annotations

import os
import logging
from pathlib import Path

from .paths import APP_ROOT


class PdfExportError(RuntimeError):
    pass


LOGGER = logging.getLogger("toetsvizier")
LOGGER.propagate = False


def _log_exception(message: str) -> None:
    if LOGGER.handlers:
        LOGGER.exception(message)


def _configure_bundled_playwright() -> None:
    bundled = APP_ROOT / "ms-playwright"
    if bundled.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(bundled))


def _missing_browser_message() -> str:
    return (
        "De browser voor moderne PDF-export ontbreekt of kan niet worden gestart. "
        "Voor de portable versie moet de map 'ms-playwright' met Chromium naast ToetsVizier.exe "
        "worden meegeleverd. Bij een installer hoort deze map automatisch in de installatie te zitten. "
        "In de ontwikkelomgeving kun je dit herstellen met: "
        "python -m playwright install chromium"
    )


def browser_report_html(html: str) -> str:
    html = html.replace(
        '<p class="pdf-break">[[PAGE_BREAK]]</p>',
        '<div class="browser-page-break" aria-hidden="true"></div>',
    )
    print_css = """
<style>
html, body { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
.browser-page-break { break-before: page; page-break-before: always; height: 0; margin: 0; padding: 0; }
.card, .report-card, .fit-page-card, .matrix-section, .chart-grid, .chart-grid tr, .chart-cell,
.distribution-card-shell, .distribution-card, .dim-section, .signal-card, .trend-card {
  break-inside: avoid-page !important;
  page-break-inside: avoid !important;
}
.fit-page-card { overflow: hidden !important; }
@media print {
  .card, .report-card, .fit-page-card { box-shadow: none !important; }
}
</style>
"""
    return html.replace("</head>", print_css + "</head>", 1)


def export_html_to_pdf(html: str, output_path: str | Path) -> None:
    _configure_bundled_playwright()
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as error:
        raise PdfExportError(
            "De moderne PDF-export vereist Playwright. Installeer de bijgewerkte onderdelen "
            "eenmalig met: python -m pip install -r requirements.txt"
        ) from error

    output_path = Path(output_path)
    printable_html = browser_report_html(html)

    try:
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
            except PlaywrightError as error:
                raise PdfExportError(_missing_browser_message()) from error

            try:
                page = browser.new_page(viewport={"width": 1400, "height": 1000}, color_scheme="light")
                page.emulate_media(media="print")
                try:
                    page.set_content(printable_html, wait_until="domcontentloaded", timeout=10000)
                except PlaywrightTimeoutError:
                    # De statische SVG-grafieken staan al in de HTML; een trage CDN-chart
                    # mag een geldige PDF-export niet blokkeren.
                    pass
                try:
                    page.wait_for_function("window.__chartsReady === true", timeout=5000)
                except PlaywrightTimeoutError:
                    pass
                page.pdf(
                    path=str(output_path),
                    format="A4",
                    landscape=True,
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"},
                )
            finally:
                browser.close()
    except PdfExportError:
        raise
    except PermissionError as error:
        _log_exception("PDF-export heeft geen toegang tot de browserbestanden.")
        raise PdfExportError(_missing_browser_message()) from error
    except Exception as error:
        _log_exception("PDF-export is mislukt.")
        raise PdfExportError(f"De PDF kon niet worden gemaakt: {error}") from error
