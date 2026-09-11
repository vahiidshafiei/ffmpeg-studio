"""Locates a usable ffmpeg/ffprobe pair.

Resolution order:
  1. User-configured path (from AppSettings), if valid.
  2. Bundled ffmpeg/ next to the running executable/script (Option A).
  3. ffmpeg/ffprobe found on the system PATH (Option B).

This module has no Qt dependency so it can be unit tested and reused
from a CLI/build script if needed.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

from app.models.models import FFmpegLocation, FFmpegSource


def _app_root() -> Path:
    """Directory containing the running app (exe dir when frozen by PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    # app/core/ffmpeg_manager.py -> project root is two levels up
    return Path(__file__).resolve().parents[2]


def _bundled_dir() -> Path:
    return _app_root() / "ffmpeg"


def _validate_pair(ffmpeg: Optional[Path], ffprobe: Optional[Path]) -> bool:
    return bool(ffmpeg and ffprobe and ffmpeg.is_file() and ffprobe.is_file())


def _get_version(ffmpeg_path: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            [str(ffmpeg_path), "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        # e.g. "ffmpeg version 7.0.1-full_build-www.gyan.dev ..."
        parts = first_line.split()
        if len(parts) >= 3:
            return parts[2]
        return first_line or None
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


class FFmpegManager:
    def __init__(self, user_ffmpeg: Optional[str] = None, user_ffprobe: Optional[str] = None):
        self._user_ffmpeg = Path(user_ffmpeg) if user_ffmpeg else None
        self._user_ffprobe = Path(user_ffprobe) if user_ffprobe else None
        self._location: Optional[FFmpegLocation] = None

    def detect(self) -> FFmpegLocation:
        """Re-run detection and cache the result. Call again after settings change."""
        # 1. User-selected
        if _validate_pair(self._user_ffmpeg, self._user_ffprobe):
            self._location = FFmpegLocation(
                source=FFmpegSource.USER_SELECTED,
                ffmpeg_path=self._user_ffmpeg,
                ffprobe_path=self._user_ffprobe,
                version=_get_version(self._user_ffmpeg),
            )
            return self._location

        # 2. Bundled
        bundled = _bundled_dir()
        bundled_ffmpeg = bundled / "ffmpeg.exe"
        bundled_ffprobe = bundled / "ffprobe.exe"
        if _validate_pair(bundled_ffmpeg, bundled_ffprobe):
            self._location = FFmpegLocation(
                source=FFmpegSource.BUNDLED,
                ffmpeg_path=bundled_ffmpeg,
                ffprobe_path=bundled_ffprobe,
                version=_get_version(bundled_ffmpeg),
            )
            return self._location

        # 3. System PATH
        system_ffmpeg = shutil.which("ffmpeg")
        system_ffprobe = shutil.which("ffprobe")
        if system_ffmpeg and system_ffprobe:
            ffmpeg_path = Path(system_ffmpeg)
            self._location = FFmpegLocation(
                source=FFmpegSource.SYSTEM_PATH,
                ffmpeg_path=ffmpeg_path,
                ffprobe_path=Path(system_ffprobe),
                version=_get_version(ffmpeg_path),
            )
            return self._location

        self._location = FFmpegLocation(source=FFmpegSource.NOT_FOUND)
        return self._location

    @property
    def location(self) -> FFmpegLocation:
        if self._location is None:
            return self.detect()
        return self._location

    def set_user_paths(self, ffmpeg_path: Optional[str], ffprobe_path: Optional[str]) -> FFmpegLocation:
        self._user_ffmpeg = Path(ffmpeg_path) if ffmpeg_path else None
        self._user_ffprobe = Path(ffprobe_path) if ffprobe_path else None
        return self.detect()
