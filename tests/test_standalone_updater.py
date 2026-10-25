import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('standalone_updater', Path(__file__).resolve().parents[1] / 'packaging' / 'standalone_updater.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class StandaloneUpdaterTests(unittest.TestCase):
    def package(self, folder, files, corrupt=False):
        package = folder / 'update.zip'
        manifest = {'version': '1.1.5', 'files': list(files),
                    'sha256': {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}
        with zipfile.ZipFile(package, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            for name, content in files.items():
                archive.writestr(name, b'corrupt' if corrupt else content)
        return package

    def test_checked_update_preserves_data_and_backs_up_program(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            root = folder / 'app'
            root.mkdir()
            (root / 'ToetsVizier.exe').write_bytes(b'old')
            (root / 'results.db').write_bytes(b'results')
            package = self.package(folder, {'ToetsVizier.exe': b'new', '_internal/chart.js': b'chart'})
            updater.apply_patch(package, root, folder / 'backup')
            self.assertEqual(b'new', (root / 'ToetsVizier.exe').read_bytes())
            self.assertEqual(b'old', (folder / 'backup/ToetsVizier.exe').read_bytes())
            self.assertEqual(b'results', (root / 'results.db').read_bytes())

    def test_corrupt_package_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            package = self.package(Path(directory), {'ToetsVizier.exe': b'new'}, corrupt=True)
            with self.assertRaises(ValueError):
                updater.inspect_package(package)

    def test_protected_and_escaping_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ('../outside.exe', 'C:/outside.exe', 'data/test.db', 'config/settings.json'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    updater.inspect_package(self.package(Path(directory), {name: b'bad'}))

    def test_write_failure_restores_old_program_and_removes_new_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            root = folder / 'app'
            root.mkdir()
            (root / 'ToetsVizier.exe').write_bytes(b'old')
            (root / 'blocked').write_bytes(b'not a directory')
            package = self.package(folder, {'ToetsVizier.exe': b'new', 'new.js': b'new', 'blocked/file.js': b'fail'})
            with self.assertRaises(RuntimeError):
                updater.apply_patch(package, root, folder / 'backup')
            self.assertEqual(b'old', (root / 'ToetsVizier.exe').read_bytes())
            self.assertFalse((root / 'new.js').exists())
