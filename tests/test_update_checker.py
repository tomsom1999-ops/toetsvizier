import json
import tempfile
import unittest
from pathlib import Path

from toetsanalyse.update_checker import (
    DEFAULT_UPDATE_MANIFEST_URL,
    UpdateCheckError,
    check_for_update,
    semantic_version_explanation,
    update_info_from_manifest,
    version_tuple,
)


class UpdateCheckerTests(unittest.TestCase):
    def test_version_tuple_compares_numeric_versions(self) -> None:
        self.assertGreater(version_tuple("1.10.0"), version_tuple("1.2.9"))
        self.assertEqual(version_tuple("v2.0"), (2, 0, 0, 0))
        self.assertIn("grote update", semantic_version_explanation("1.2.3"))
        self.assertIn("tomsom1999-ops/toetsvizier", DEFAULT_UPDATE_MANIFEST_URL)

    def test_manifest_marks_newer_version(self) -> None:
        info = update_info_from_manifest(
            {
                "latest_version": "0.2.0",
                "download_url": "https://example.test/releases/0.2.0",
                "installer_url": "https://example.test/toetsvizier-0.2.0.exe",
                "release_notes": "Kleine verbeteringen.",
                "versions": [
                    {
                        "version": "0.2.0",
                        "type": "middelgrote update",
                        "title": "Resultatenanalyse",
                        "changes": ["Nieuwe analysekaart toegevoegd."],
                    }
                ],
            },
            current_version="0.1.0",
        )
        self.assertTrue(info.is_newer)
        self.assertEqual("0.2.0", info.latest_version)
        self.assertEqual("https://example.test/toetsvizier-0.2.0.exe", info.installer_url)
        self.assertEqual("Resultatenanalyse", info.version_changes[0].title)
        self.assertEqual(("Nieuwe analysekaart toegevoegd.",), info.version_changes[0].changes)

    def test_manifest_requires_version_and_download_url(self) -> None:
        with self.assertRaises(UpdateCheckError):
            update_info_from_manifest({"latest_version": "0.2.0"}, current_version="0.1.0")
        with self.assertRaises(UpdateCheckError):
            update_info_from_manifest({"download_url": "https://example.test"}, current_version="0.1.0")

    def test_manifest_can_fall_back_to_download_url_as_installer_url(self) -> None:
        info = update_info_from_manifest(
            {
                "latest_version": "1.0.0",
                "download_url": "https://example.test/toetsvizier-1.0.0.exe",
            },
            current_version="0.9.0",
        )

        self.assertEqual(info.download_url, info.installer_url)

    def test_manifest_accepts_update_package_without_installer(self) -> None:
        info = update_info_from_manifest(
            {
                "latest_version": "1.1.0",
                "download_url": "https://example.test/releases/1.1.0",
                "package_url": "https://example.test/ToetsVizier-update-1.1.0.zip",
                "package_sha256": "ABC",
                "update_type": "package",
            },
            current_version="1.0.0",
        )

        self.assertTrue(info.is_newer)
        self.assertEqual("", info.installer_url)
        self.assertEqual("https://example.test/ToetsVizier-update-1.1.0.zip", info.package_url)
        self.assertEqual("ABC", info.package_sha256)
        self.assertEqual("package", info.update_type)

    def test_check_for_update_reads_json_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "update.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "latest_version": "1.0.0",
                        "download_url": "https://example.test/releases/1.0.0",
                        "installer_url": "https://example.test/ToetsVizier-1.0.0.exe",
                    }
                ),
                encoding="utf-8",
            )
            info = check_for_update(manifest_path.as_uri(), current_version="0.9.0")
        self.assertTrue(info.is_newer)
        self.assertEqual("https://example.test/ToetsVizier-1.0.0.exe", info.installer_url)


if __name__ == "__main__":
    unittest.main()
