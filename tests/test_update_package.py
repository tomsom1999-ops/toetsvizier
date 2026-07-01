import tempfile
import unittest
import zipfile
import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "packaging" / "build_update_package.py"
SPEC = importlib.util.spec_from_file_location("build_update_package_script", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
build_update_package_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_update_package_script)
build_update_package = build_update_package_script.build_update_package
DIST_EXCLUDES = build_update_package_script.DIST_EXCLUDES


class UpdatePackageBuilderTests(unittest.TestCase):
    def test_build_update_package_excludes_sensitive_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app_file = root / "toetsanalyse" / "version.py"
            app_file.parent.mkdir()
            app_file.write_text("APP_VERSION = '1.0.1'\n", encoding="utf-8")
            data_file = root / "data" / "natuurkunde.db"
            data_file.parent.mkdir()
            data_file.write_text("privacy", encoding="utf-8")

            package_path, digest = build_update_package(
                version="1.0.1",
                output_dir=root / "releases",
                root=root,
                include_roots=("toetsanalyse", "data"),
            )

            self.assertTrue(package_path.exists())
            self.assertEqual(64, len(digest))
            with zipfile.ZipFile(package_path) as archive:
                names = set(archive.namelist())
            self.assertIn("toetsanalyse/version.py", names)
            self.assertIn("manifest.json", names)
            self.assertNotIn("data/natuurkunde.db", names)

    def test_dist_package_keeps_internal_runtime_files_but_excludes_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime_file = root / "_internal" / "some_library" / "data.csv"
            runtime_file.parent.mkdir(parents=True)
            runtime_file.write_text("runtime,data", encoding="utf-8")
            user_data = root / "data" / "natuurkunde.db"
            user_data.parent.mkdir()
            user_data.write_text("privacy", encoding="utf-8")

            package_path, _digest = build_update_package(
                version="1.0.2",
                output_dir=root / "releases",
                root=root,
                include_roots=("_internal", "data"),
                exclude_patterns=DIST_EXCLUDES,
            )

            with zipfile.ZipFile(package_path) as archive:
                names = set(archive.namelist())
            self.assertIn("_internal/some_library/data.csv", names)
            self.assertNotIn("data/natuurkunde.db", names)


if __name__ == "__main__":
    unittest.main()
