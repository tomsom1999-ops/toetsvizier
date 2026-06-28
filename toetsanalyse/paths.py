from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Mapping


def _app_root() -> Path:
    override = os.environ.get("TOETSVIZIER_APP_ROOT", "").strip()
    if override:
        return Path(override).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _env_bool(value: str) -> bool:
    return value.strip().casefold() in {"1", "true", "yes", "ja", "aan"}


def _user_data_root(
    app_root: Path,
    *,
    frozen: bool | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    override = str(env.get("TOETSVIZIER_DATA_ROOT", "")).strip()
    if override:
        return Path(override).resolve()
    if _env_bool(str(env.get("TOETSVIZIER_PORTABLE_MODE", ""))):
        return app_root
    is_frozen = getattr(sys, "frozen", False) if frozen is None else frozen
    if not is_frozen:
        return app_root
    local_appdata = str(env.get("LOCALAPPDATA", "")).strip()
    if local_appdata:
        return Path(local_appdata).resolve() / "ToetsVizier"
    return app_root


APP_ROOT = _app_root()
USER_DATA_ROOT = _user_data_root(APP_ROOT)
DATA_DIR = USER_DATA_ROOT / "data"
BACKUP_DIR = USER_DATA_ROOT / "backups"
EXPORT_DIR = USER_DATA_ROOT / "exports"
PDF_EXPORT_DIR = EXPORT_DIR / "pdf"
EXCEL_EXPORT_DIR = EXPORT_DIR / "excel"
LOG_DIR = USER_DATA_ROOT / "logs"
CONFIG_DIR = USER_DATA_ROOT / "config"


def ensure_app_directories() -> None:
    for directory in (
        DATA_DIR,
        BACKUP_DIR,
        PDF_EXPORT_DIR,
        EXCEL_EXPORT_DIR,
        LOG_DIR,
        CONFIG_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)
