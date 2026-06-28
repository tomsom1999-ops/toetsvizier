import unittest
from pathlib import Path

from toetsanalyse.self_update import (
    SelfUpdateError,
    build_installer_launch_command,
    installer_extension_from_url,
)


class SelfUpdateTests(unittest.TestCase):
    def test_installer_extension_from_url_accepts_query_string(self) -> None:
        self.assertEqual(".exe", installer_extension_from_url("https://example.test/update.exe?token=abc"))
        self.assertEqual(".msi", installer_extension_from_url("https://example.test/update.msi"))

    def test_installer_extension_from_url_rejects_unsupported_file(self) -> None:
        with self.assertRaises(SelfUpdateError):
            installer_extension_from_url("https://example.test/update.zip")

    def test_build_installer_launch_command_for_exe_returns_direct_path(self) -> None:
        command = build_installer_launch_command(Path("C:\\Temp\\ToetsVizier-1.2.3.exe"))

        self.assertEqual(["C:\\Temp\\ToetsVizier-1.2.3.exe"], command)

    def test_build_installer_launch_command_for_msi_uses_msiexec(self) -> None:
        command = build_installer_launch_command(Path("C:\\Temp\\ToetsVizier-1.2.3.msi"))

        self.assertEqual(["msiexec.exe", "/i", "C:\\Temp\\ToetsVizier-1.2.3.msi"], command)
