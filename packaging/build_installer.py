from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from toetsanalyse.installer_builder import build_installer
from toetsanalyse.version import APP_VERSION


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bouw een Windows-installer voor ToetsVizier.")
    parser.add_argument("--version", default=APP_VERSION, help="Versie voor de installernaam.")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "releases"),
        help="Map waar de installer terechtkomt.",
    )
    parser.add_argument(
        "--build-dir",
        default="",
        help="Korte tijdelijke buildmap. Laat leeg voor de standaard korte buildmap.",
    )
    args = parser.parse_args(argv)
    installer_path, sha256 = build_installer(
        ROOT,
        version=str(args.version),
        output_dir=Path(args.output_dir),
        build_dir=Path(args.build_dir) if str(args.build_dir).strip() else None,
    )
    print(f"Installer gebouwd: {installer_path}")
    print(f"SHA256: {sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
