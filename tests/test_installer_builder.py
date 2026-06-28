import tempfile
import unittest
from pathlib import Path

from toetsanalyse.installer_builder import (
    compute_sha256,
    installer_output_name,
    installer_output_path,
    playwright_bundle_candidates,
)


class InstallerBuilderTests(unittest.TestCase):
    def test_installer_output_name_uses_expected_pattern(self) -> None:
        self.assertEqual(
            "ToetsVizier-1.2.3-windows-installer.exe",
            installer_output_name("1.2.3"),
        )

    def test_installer_output_path_uses_target_directory(self) -> None:
        self.assertEqual(
            Path("C:/releases/ToetsVizier-1.2.3-windows-installer.exe"),
            installer_output_path(Path("C:/releases"), "1.2.3"),
        )

    def test_playwright_bundle_candidates_include_explicit_env_first(self) -> None:
        candidates = playwright_bundle_candidates(
            {
                "PLAYWRIGHT_BROWSERS_PATH": r"D:\pw",
                "LOCALAPPDATA": r"C:\Users\Test\AppData\Local",
                "USERPROFILE": r"C:\Users\Test",
            }
        )

        self.assertEqual(Path(r"D:\pw"), candidates[0])

    def test_compute_sha256_hashes_file_content(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "sample.bin"
            path.write_bytes(b"toetsvizier")

            digest = compute_sha256(path)

        self.assertEqual(
            "12ad7d105c7e3645f16ff1f54a233e498c91525dc727adae4b0b02b9e9142489",
            digest,
        )
