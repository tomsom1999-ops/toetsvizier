from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_EXCLUDES = (
    ".git/**",
    ".agents/**",
    ".codex_tmp/**",
    ".codex_pdf_review/**",
    "__pycache__/**",
    "**/__pycache__/**",
    "*.pyc",
    "data/**",
    "backups/**",
    "exports/**",
    "logs/**",
    "config/**",
    "build/**",
    "dist/**",
    "b/**",
    "b20/**",
    "releases/**",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.xlsx",
    "*.xls",
    "*.xlsm",
    "*.csv",
    "*.tsv",
    "*.pdf",
    "*.log",
    "*.tmp",
    "update.json",
)

DIST_EXCLUDES = (
    ".git/**",
    ".agents/**",
    ".codex_tmp/**",
    ".codex_pdf_review/**",
    "__pycache__/**",
    "**/__pycache__/**",
    "*.pyc",
    "data/**",
    "backups/**",
    "exports/**",
    "logs/**",
    "config/**",
    "releases/**",
    "update.json",
    "*.log",
    "*.tmp",
)

DEFAULT_INCLUDE_ROOTS = (
    "main.py",
    "requirements.txt",
    "ToetsVizier.spec",
    "toetsanalyse",
    "dashboard",
    "packaging",
)


def normalized(path: Path) -> str:
    return path.as_posix()


def is_excluded(relative_path: Path, patterns: Sequence[str]) -> bool:
    value = normalized(relative_path)
    return any(fnmatch.fnmatch(value, pattern) for pattern in patterns)


def iter_package_files(root: Path, include_roots: Sequence[str], exclude_patterns: Sequence[str]) -> list[Path]:
    files: list[Path] = []
    for include in include_roots:
        path = root / include
        if not path.exists():
            continue
        if path.is_file():
            relative = path.relative_to(root)
            if not is_excluded(relative, exclude_patterns):
                files.append(relative)
            continue
        for child in path.rglob("*"):
            if not child.is_file():
                continue
            relative = child.relative_to(root)
            if not is_excluded(relative, exclude_patterns):
                files.append(relative)
    return sorted(set(files), key=lambda item: item.as_posix().casefold())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def build_update_package(
    *,
    version: str,
    output_dir: Path,
    root: Path = ROOT,
    include_roots: Sequence[str] = DEFAULT_INCLUDE_ROOTS,
    exclude_patterns: Sequence[str] = DEFAULT_EXCLUDES,
) -> tuple[Path, str]:
    version = version.strip()
    if not version:
        raise ValueError("Geef een versienummer op.")
    files = iter_package_files(root, include_roots, exclude_patterns)
    if not files:
        raise ValueError("Geen bestanden gevonden voor het updatepakket.")
    output_dir.mkdir(parents=True, exist_ok=True)
    package_path = output_dir / f"ToetsVizier-update-{version}.zip"
    manifest = {
        "name": "ToetsVizier updatepakket",
        "version": version,
        "files": [file.as_posix() for file in files],
    }
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        for relative in files:
            archive.write(root / relative, relative.as_posix())
    return package_path, sha256_file(package_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bouw een licht ToetsVizier-updatepakket.")
    parser.add_argument("--version", required=True, help="Versie voor het pakket, bijvoorbeeld 0.3.1.")
    parser.add_argument("--output-dir", default="releases", help="Map waarin het ZIP-pakket wordt geschreven.")
    parser.add_argument(
        "--dist-dir",
        default="",
        help="Optioneel: maak het pakket vanuit een PyInstaller-map, bijvoorbeeld dist\\ToetsVizier.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if str(args.dist_dir).strip():
        root = Path(args.dist_dir).resolve()
        include_roots = tuple(path.name for path in root.iterdir())
        exclude_patterns = DIST_EXCLUDES
    else:
        root = ROOT
        include_roots = DEFAULT_INCLUDE_ROOTS
        exclude_patterns = DEFAULT_EXCLUDES
    package_path, digest = build_update_package(
        version=args.version,
        output_dir=Path(args.output_dir),
        root=root,
        include_roots=include_roots,
        exclude_patterns=exclude_patterns,
    )
    print(f"Updatepakket geschreven: {package_path}")
    print(f"SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
