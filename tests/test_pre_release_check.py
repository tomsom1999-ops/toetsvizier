import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parent.parent / "packaging" / "pre_release_check.py"
SPEC = importlib.util.spec_from_file_location("pre_release_check_script", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
pre_release_check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pre_release_check)


class PreReleaseCheckTests(unittest.TestCase):
    def test_update_package_exclusion_check_accepts_current_file_selection(self) -> None:
        pre_release_check.check_update_package_exclusions()

    def test_release_manifest_can_be_validated_without_network(self) -> None:
        pre_release_check.check_update_manifest()


if __name__ == "__main__":
    unittest.main()
