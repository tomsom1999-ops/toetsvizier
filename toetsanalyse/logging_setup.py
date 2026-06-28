from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from .paths import LOG_DIR


LOGGER_NAME = "toetsvizier"


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        handler = RotatingFileHandler(
            LOG_DIR / "toetsvizier.log",
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        logger.addHandler(handler)
    logger.propagate = False
    return logger


def install_exception_hook() -> None:
    logger = configure_logging()
    previous_hook = sys.excepthook
    if getattr(previous_hook, "_toetsvizier_installed", False):
        return

    def exception_hook(exc_type, exc_value, traceback) -> None:
        logger.error(
            "Onverwachte fout buiten normale foutafhandeling.",
            exc_info=(exc_type, exc_value, traceback),
        )
        previous_hook(exc_type, exc_value, traceback)

    exception_hook._toetsvizier_installed = True  # type: ignore[attr-defined]
    sys.excepthook = exception_hook


def log_exception(context: str) -> None:
    configure_logging().exception(context)
