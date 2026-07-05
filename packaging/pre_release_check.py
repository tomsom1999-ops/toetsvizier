from __future__ import annotations

import argparse
import importlib.util
import py_compile
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from toetsanalyse.update_checker import update_info_from_manifest
from toetsanalyse.update_manifest import load_manifest_template

_UPDATE_PACKAGE_SCRIPT = ROOT / "packaging" / "build_update_package.py"
_UPDATE_PACKAGE_SPEC = importlib.util.spec_from_file_location("toetsvizier_build_update_package", _UPDATE_PACKAGE_SCRIPT)
if _UPDATE_PACKAGE_SPEC is None or _UPDATE_PACKAGE_SPEC.loader is None:
    raise RuntimeError("Kan build_update_package.py niet laden.")
_UPDATE_PACKAGE = importlib.util.module_from_spec(_UPDATE_PACKAGE_SPEC)
_UPDATE_PACKAGE_SPEC.loader.exec_module(_UPDATE_PACKAGE)
DEFAULT_EXCLUDES = _UPDATE_PACKAGE.DEFAULT_EXCLUDES
DEFAULT_INCLUDE_ROOTS = _UPDATE_PACKAGE.DEFAULT_INCLUDE_ROOTS
iter_package_files = _UPDATE_PACKAGE.iter_package_files


PROTECTED_PACKAGE_PREFIXES = ("data/", "backups/", "exports/", "logs/", "config/")
PROTECTED_PACKAGE_SUFFIXES = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".xlsx",
    ".xls",
    ".xlsm",
    ".csv",
    ".tsv",
    ".pdf",
    ".log",
    ".tmp",
    ".pyc",
)


def python_files() -> list[Path]:
    roots = [ROOT / "main.py", ROOT / "toetsanalyse", ROOT / "tests", ROOT / "packaging"]
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            files.append(root)
        elif root.is_dir():
            files.extend(
                path
                for path in root.rglob("*.py")
                if "__pycache__" not in path.parts
            )
    return sorted(set(files), key=lambda path: str(path).casefold())


def check_python_syntax() -> None:
    errors: list[str] = []
    for path in python_files():
        compiled_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pyc", delete=False) as handle:
                compiled_path = Path(handle.name)
            py_compile.compile(str(path), cfile=str(compiled_path), doraise=True)
        except py_compile.PyCompileError as error:
            errors.append(f"{path.relative_to(ROOT)}: {error.msg}")
        finally:
            if compiled_path is not None:
                try:
                    compiled_path.unlink(missing_ok=True)
                except OSError:
                    pass
    if errors:
        raise RuntimeError("Syntaxcheck mislukt:\n" + "\n".join(errors))


def run_unittests() -> None:
    command = [sys.executable, "-m", "unittest", "discover", "tests"]
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode:
        raise RuntimeError("Unittest-suite is niet geslaagd.")


def check_update_package_exclusions() -> None:
    files = iter_package_files(ROOT, DEFAULT_INCLUDE_ROOTS, DEFAULT_EXCLUDES)
    risky = []
    for relative in files:
        value = relative.as_posix()
        lower_value = value.casefold()
        if lower_value.startswith(PROTECTED_PACKAGE_PREFIXES) or lower_value.endswith(PROTECTED_PACKAGE_SUFFIXES):
            risky.append(value)
    if risky:
        preview = "\n".join(f"- {path}" for path in risky[:40])
        if len(risky) > 40:
            preview += f"\n... en {len(risky) - 40} meer."
        raise RuntimeError("Updatepakket zou privacygevoelige of lokale data bevatten:\n" + preview)


def check_update_manifest() -> None:
    manifest_path = ROOT / "update.json"
    if not manifest_path.exists():
        raise RuntimeError("update.json ontbreekt.")
    manifest = load_manifest_template(manifest_path)
    info = update_info_from_manifest(manifest, current_version="0.0.0")
    if not info.latest_version:
        raise RuntimeError("update.json bevat geen bruikbaar versienummer.")
    if not (info.download_url or info.package_url):
        raise RuntimeError("update.json bevat geen download- of pakketlink.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Voer de lokale ToetsVizier pre-release kwaliteitscheck uit.")
    parser.add_argument("--skip-tests", action="store_true", help="Sla de unittest-suite over.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    checks: list[tuple[str, object]] = [
        ("Python-syntax", check_python_syntax),
        ("Updatepakket-uitsluitingen", check_update_package_exclusions),
        ("Update-manifest", check_update_manifest),
    ]
    if not args.skip_tests:
        checks.insert(1, ("Unit tests", run_unittests))

    try:
        for label, check in checks:
            print(f"[pre-release] {label}...")
            check()  # type: ignore[operator]
        print("[pre-release] Alles akkoord.")
        return 0
    except Exception as error:
        print(f"[pre-release] Gestopt: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
