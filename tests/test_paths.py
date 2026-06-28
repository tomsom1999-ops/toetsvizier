import unittest
from pathlib import Path

from toetsanalyse.paths import _user_data_root


class PathsTests(unittest.TestCase):
    def test_development_build_keeps_data_next_to_source_tree(self) -> None:
        root = _user_data_root(Path(r"C:\project\ToetsVizier"), frozen=False, environ={})

        self.assertEqual(Path(r"C:\project\ToetsVizier"), root)

    def test_frozen_build_uses_local_appdata_by_default(self) -> None:
        root = _user_data_root(
            Path(r"C:\Program Files\ToetsVizier"),
            frozen=True,
            environ={"LOCALAPPDATA": r"C:\Users\Test\AppData\Local"},
        )

        self.assertEqual(Path(r"C:\Users\Test\AppData\Local\ToetsVizier"), root)

    def test_portable_mode_keeps_data_next_to_executable(self) -> None:
        root = _user_data_root(
            Path(r"D:\ToetsVizier"),
            frozen=True,
            environ={
                "LOCALAPPDATA": r"C:\Users\Test\AppData\Local",
                "TOETSVIZIER_PORTABLE_MODE": "1",
            },
        )

        self.assertEqual(Path(r"D:\ToetsVizier"), root)
