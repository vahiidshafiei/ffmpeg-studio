"""Configures rotating file logging under the user log directory."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config.settings_manager import log_dir

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("ffmpeg_studio")
    if logger.handlers:
        return logger  # already configured (e.g. re-imported)

    logger.setLevel(level)

    log_path = log_dir() / "ffmpeg_studio.log"
    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    logger.addHandler(console_handler)

    logger.info("Logging initialized. Log file: %s", log_path)
    return logger
