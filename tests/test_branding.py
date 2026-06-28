import tempfile
import unittest
from pathlib import Path

from PySide6.QtWidgets import QApplication

from toetsanalyse.branding import brand_app_icon, write_windows_icon


@unittest.skipIf(QApplication is None, "PySide6 is niet beschikbaar in deze Python-omgeving.")
class BrandingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_brand_app_icon_is_available(self) -> None:
        self.assertFalse(brand_app_icon().isNull())

    def test_write_windows_icon_creates_non_empty_ico(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            icon_path = write_windows_icon(Path(temporary_directory) / "toetsvizier.ico")

            self.assertTrue(icon_path.exists())
            self.assertGreater(icon_path.stat().st_size, 0)
