import tempfile
import unittest
from pathlib import Path

from toetsanalyse.release_check import find_release_privacy_risks


class ReleaseCheckTests(unittest.TestCase):
    def test_empty_release_folder_has_no_privacy_risks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.assertEqual([], find_release_privacy_risks(Path(temporary_directory)))

    def test_release_check_finds_local_data_exports_logs_and_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for relative_path in (
                "data/natuurkunde.db",
                "backups/natuurkunde-2025.db",
                "exports/pdf/rapport.pdf",
                "logs/toetsvizier.log",
                "config/settings.ini",
                "toetsanalyse/__pycache__/app.cpython-311.pyc",
            ):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("niet in release", encoding="utf-8")

            risks = {str(path.relative_to(root)).replace("\\", "/") for path in find_release_privacy_risks(root)}

        self.assertEqual(
            {
                "data/natuurkunde.db",
                "backups/natuurkunde-2025.db",
                "exports/pdf/rapport.pdf",
                "logs/toetsvizier.log",
                "config/settings.ini",
                "toetsanalyse/__pycache__/app.cpython-311.pyc",
            },
            risks,
        )


if __name__ == "__main__":
    unittest.main()
