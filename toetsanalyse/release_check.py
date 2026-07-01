from __future__ import annotations

from pathlib import Path

from .paths import APP_ROOT


SENSITIVE_PATTERNS = (
    "data/**/*",
    "backups/**/*",
    "exports/**/*",
    "logs/**/*",
    "config/**/*",
    "**/__pycache__/*.pyc",
    "*.pyc",
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
)


def find_release_privacy_risks(root: Path | str | None = None) -> list[Path]:
    base = Path(root) if root is not None else APP_ROOT
    risks: set[Path] = set()
    for pattern in SENSITIVE_PATTERNS:
        for path in base.glob(pattern):
            if path.is_file():
                risks.add(path)
    return sorted(risks, key=lambda path: str(path).casefold())


def main() -> int:
    risks = find_release_privacy_risks()
    if not risks:
        print("Releasecheck OK: geen lokale data, exports, logs of bytecode gevonden.")
        return 0
    print("Releasecheck gestopt: deze bestanden horen niet in een uitrolpakket:")
    for path in risks[:50]:
        print(f"- {path.relative_to(APP_ROOT)}")
    if len(risks) > 50:
        print(f"... en {len(risks) - 50} meer.")
    print("Maak een schone distributiemap of sluit deze bestanden uit bij het bouwen.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
