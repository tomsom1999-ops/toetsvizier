import json
import tempfile
import unittest
from pathlib import Path

from toetsanalyse.update_checker import update_info_from_manifest
from toetsanalyse.update_manifest import (
    UpdateManifestError,
    build_update_manifest,
    load_manifest_template,
    main as build_update_manifest_main,
)


class UpdateManifestTests(unittest.TestCase):
    def test_build_update_manifest_replaces_version_placeholders(self) -> None:
        manifest = build_update_manifest(
            {
                "release_notes": "Nieuw in {version}.",
                "download_url_template": "https://example.test/downloads/{version}.zip",
                "installer_url_template": "https://example.test/installers/{version}.exe",
                "versions": [
                    {
                        "version": "{version}",
                        "type": "kleine update/patch",
                        "title": "Versie {version}",
                        "changes": ["Verbetering voor {version}."],
                    }
                ],
            },
            version="1.2.3",
        )

        self.assertEqual("1.2.3", manifest["latest_version"])
        self.assertEqual("https://example.test/downloads/1.2.3.zip", manifest["download_url"])
        self.assertEqual("https://example.test/installers/1.2.3.exe", manifest["installer_url"])
        self.assertEqual("Nieuw in 1.2.3.", manifest["release_notes"])
        self.assertEqual("Versie 1.2.3", manifest["versions"][0]["title"])

    def test_build_update_manifest_requires_current_version_entry(self) -> None:
        with self.assertRaises(UpdateManifestError):
            build_update_manifest(
                {
                    "versions": [
                        {
                            "version": "0.9.0",
                            "changes": ["Oude release."],
                        }
                    ]
                },
                version="1.0.0",
            )

    def test_command_can_generate_update_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            template_path = temporary_path / "template.json"
            output_path = temporary_path / "update.json"
            template_path.write_text(
                json.dumps(
                    {
                        "release_notes": "Nieuwe release.",
                        "download_url_template": "https://example.test/releases/{version}",
                        "installer_url_template": "https://example.test/{version}.exe",
                        "versions": [
                            {
                                "version": "{version}",
                                "title": "Nieuwe versie",
                                "changes": ["Nieuwe functie."],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            exit_code = build_update_manifest_main(
                ["--template", str(template_path), "--output", str(output_path), "--version", "2.0.0"]
            )

            self.assertEqual(0, exit_code)
            manifest = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual("2.0.0", manifest["latest_version"])
            self.assertEqual("https://example.test/releases/2.0.0", manifest["download_url"])
            self.assertEqual("https://example.test/2.0.0.exe", manifest["installer_url"])

    def test_repository_update_json_is_a_valid_manifest(self) -> None:
        manifest = load_manifest_template(Path(__file__).resolve().parent.parent / "update.json")

        info = update_info_from_manifest(manifest, current_version="0.0.0")

        self.assertEqual(str(manifest["latest_version"]), info.latest_version)
        self.assertTrue(info.download_url.startswith("https://"))
