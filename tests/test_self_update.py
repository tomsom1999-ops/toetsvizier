import unittest
import tempfile
import zipfile
from pathlib import Path

from toetsanalyse.self_update import (
    SelfUpdateError,
    apply_update_package,
    build_installer_launch_command,
    installer_extension_from_url,
    stage_update_package_for_restart,
    update_package_extension_from_url,
    validate_update_package,
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

    def test_update_package_extension_accepts_only_zip(self) -> None:
        self.assertEqual(".zip", update_package_extension_from_url("https://example.test/update.zip?token=abc"))
        with self.assertRaises(SelfUpdateError):
            update_package_extension_from_url("https://example.test/update.exe")

    def test_validate_update_package_rejects_sensitive_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "update.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("data/natuurkunde.db", "privacy")

            with self.assertRaises(SelfUpdateError):
                validate_update_package(package)

    def test_apply_update_package_overwrites_app_file_and_keeps_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "app"
            root.mkdir()
            target = root / "toetsanalyse" / "version.py"
            target.parent.mkdir()
            target.write_text("APP_VERSION = '1.0.0'\n", encoding="utf-8")
            package = Path(directory) / "update.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("manifest.json", "{}")
                archive.writestr("toetsanalyse/version.py", "APP_VERSION = '1.0.1'\n")

            backup_dir = apply_update_package(package, app_root=root, backup_root=Path(directory) / "backups")

            self.assertEqual("APP_VERSION = '1.0.1'\n", target.read_text(encoding="utf-8"))
            backup_file = backup_dir / "files" / "toetsanalyse" / "version.py"
            self.assertEqual("APP_VERSION = '1.0.0'\n", backup_file.read_text(encoding="utf-8"))

    def test_nested_manifest_file_is_treated_as_app_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "app"
            root.mkdir()
            package = Path(directory) / "update.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("manifest.json", "{}")
                archive.writestr("_internal/some_library/manifest.json", '{"runtime": true}')

            paths = validate_update_package(package)
            backup_dir = apply_update_package(package, app_root=root, backup_root=Path(directory) / "backups")

            self.assertIn(Path("_internal/some_library/manifest.json"), paths)
            self.assertEqual(
                '{"runtime": true}',
                (root / "_internal" / "some_library" / "manifest.json").read_text(encoding="utf-8"),
            )
            self.assertTrue(backup_dir.exists())

    def test_failed_apply_removes_new_files_after_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "app"
            root.mkdir()
            blocked_parent = root / "blocked"
            blocked_parent.write_text("not a directory", encoding="utf-8")
            new_file = root / "toetsanalyse" / "new_feature.py"
            package = Path(directory) / "update.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("manifest.json", "{}")
                archive.writestr("toetsanalyse/new_feature.py", "created before failure")
                archive.writestr("blocked/file.py", "this cannot be written")

            with self.assertRaises(Exception):
                apply_update_package(package, app_root=root, backup_root=Path(directory) / "backups")

            self.assertFalse(new_file.exists())

    def test_stage_update_package_creates_script_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "app"
            root.mkdir()
            executable = root / "ToetsVizier.exe"
            executable.write_text("old", encoding="utf-8")
            package = Path(directory) / "update.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("manifest.json", "{}")
                archive.writestr("ToetsVizier.exe", "new")

            script_path, backup_dir = stage_update_package_for_restart(
                package,
                app_root=root,
                backup_root=Path(directory) / "backups",
                staging_root=Path(directory) / "stage",
            )

            self.assertTrue(script_path.exists())
            self.assertTrue((backup_dir / "files" / "ToetsVizier.exe").exists())
            script = script_path.read_text(encoding="utf-8")
            self.assertIn("Copy-Tree", script)
            self.assertIn("Wait-Process", script)
            self.assertTrue((script_path.parent / "new-files.txt").exists())
