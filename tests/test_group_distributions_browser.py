"""Render the group distributions with and without a functioning Plotly renderer."""
from pathlib import Path
import unittest

from toetsanalyse.analysis import analysis_data
from toetsanalyse.analysis_dashboard import build_analysis_dashboard_html
from tests import test_analysis as fixtures


class GroupDistributionBrowserTests(unittest.TestCase):
    def test_long_version_names_do_not_overlap_answer_bars_or_counts(self):
        from playwright.sync_api import sync_playwright
        from tests import test_test_versions as version_fixtures
        from toetsanalyse.test_versions import save_question_mapping
        fixture = version_fixtures.TestVersions()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        names = ['Technische Automatisering', 'Menselijk Lichaam', 'Optica']
        for form, name in zip((fixture.a, fixture.b, fixture.c), names):
            fixture.db.execute('UPDATE test_versions SET name=? WHERE id=?', (name, form))
        identity = {'A': 'A', 'B': 'B', 'C': 'C', 'D': 'D'}
        shuffled = {'A': 'B', 'B': 'D', 'C': 'A', 'D': 'C'}
        save_question_mapping(fixture.db, fixture.test_id, fixture.mapping, {
            (fixture.a, fixture.shared): identity, (fixture.b, fixture.shared): shuffled,
            (fixture.c, fixture.shared): identity,
        })
        fixture.fill()
        data = analysis_data(fixture.db, fixture.test_id)
        html = build_analysis_dashboard_html(data, 'unused.js').replace('<script src="unused.js"></script>', '').replace('<script src="qrc:///qtwebchannel/qwebchannel.js"></script>', '')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            for width in (1280, 640):
                page = browser.new_page(viewport={'width': width, 'height': 1000})
                page.set_content(html, wait_until='domcontentloaded')
                self.assertEqual(12, page.locator('.mc-version-link').count())
                self.assertTrue(page.locator('.mc-option').evaluate_all('''elements => elements.every(el => {
                    const row = el.querySelector('.mc-option-row').getBoundingClientRect();
                    const links = el.querySelector('.mc-version-links').getBoundingClientRect();
                    return links.top >= row.bottom && el.scrollWidth <= el.clientWidth + 1;
                })'''))
                self.assertTrue(page.locator('.mc-version-link').evaluate_all('''elements => elements.every(el => {
                    const name = el.querySelector('.mc-version-name').getBoundingClientRect();
                    const letter = el.querySelector('.mc-version-letter').getBoundingClientRect();
                    return name.right <= letter.left;
                })'''))
                if width == 1280:
                    output = Path(__file__).resolve().parents[3] / 'outputs' / 'analyse-meerkeuze-versies-controle.png'
                    output.parent.mkdir(parents=True, exist_ok=True)
                    page.locator('.mc-question').first.screenshot(path=str(output))
                page.close()
            browser.close()

    def test_group_bars_remain_visible_when_plotly_renders_nothing(self):
        from playwright.sync_api import sync_playwright
        fixture = fixtures.SingleTestAnalysisTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        data = analysis_data(fixture.database, fixture.test_id)
        plotly_path = Path(__file__).resolve().parents[1] / 'toetsanalyse/assets/plotly-2.35.2.min.js'
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            errors = []
            source = 'https://test.local/plotly.js'
            for real_plotly in (False, True):
                page = browser.new_page(viewport={'width': 1280, 'height': 900})
                page.on('pageerror', lambda error: errors.append(str(error)))
                body = plotly_path.read_text(encoding='utf-8') if real_plotly else 'window.Plotly={react:()=>Promise.resolve(),Plots:{resize:()=>{}}};'
                html = build_analysis_dashboard_html(data, source).replace(f'<script src="{source}"></script>', '').replace('<script src="qrc:///qtwebchannel/qwebchannel.js"></script>', '')
                page.set_content(html, wait_until='domcontentloaded')
                page.add_script_tag(content=body)
                page.locator('[data-tab="group"]').click()
                page.wait_for_function("document.querySelectorAll('#groupDimensionCards .fallback-fill').length > 0")
                self.assertGreaterEqual(page.locator('#groupDimensionCards .fallback-fill').count(), 6)
                positive_widths = page.locator('#groupDimensionCards .fallback-fill').evaluate_all('(elements)=>elements.filter(el=>el.getBoundingClientRect().width>0).length')
                self.assertGreater(positive_widths, 0)
                if real_plotly:
                    page.wait_for_function("document.querySelector('#groupHeatmap .heatmaplayer') !== null")
                    output = Path(__file__).resolve().parents[3] / 'outputs' / 'analyse-groepsverdelingen-controle.png'
                    output.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(output), full_page=True)
                page.close()
            self.assertEqual([], errors)
            browser.close()
