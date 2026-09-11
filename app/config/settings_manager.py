"""Persists AppSettings as JSON under the OS-appropriate user config directory
(e.g. %APPDATA%\\FFmpegStudio on Windows), via platformdirs so behaviour is
correct across platforms during development too.
"""
from __future__ import annotations

import json
import dataclasses
from pathlib import Path

from platformdirs import user_config_dir, user_log_dir

from app.models.models import AppSettings

APP_NAME = "FFmpegStudio"
APP_AUTHOR = "FFmpegStudio"


def config_dir() -> Path:
    path = Path(user_config_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = Path(user_log_dir(APP_NAME, APP_AUTHOR))
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return config_dir() / "settings.json"


class SettingsManager:
    def __init__(self):
        self._settings = self.load()

    @property
    def settings(self) -> AppSettings:
        return self._settings

    def load(self) -> AppSettings:
        path = settings_file()
        if not path.exists():
            return AppSettings()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known_fields = {f.name for f in dataclasses.fields(AppSettings)}
            filtered = {k: v for k, v in data.items() if k in known_fields}
            return AppSettings(**filtered)
        except (json.JSONDecodeError, OSError, TypeError):
            # Corrupt or unreadable settings should never crash startup.
            return AppSettings()

    def save(self) -> None:
        path = settings_file()
        path.write_text(
            json.dumps(dataclasses.asdict(self._settings), indent=2),
            encoding="utf-8",
        )

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self.save()
