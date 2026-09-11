"""Shared dataclasses used across UI, core and operations.

Keeping these separate from both the UI and the FFmpeg-specific logic means
any layer can import them without pulling in Qt or subprocess dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Media info (from ffprobe)
# ---------------------------------------------------------------------------

@dataclass
class VideoStreamInfo:
    codec: str
    width: int
    height: int
    fps: float
    bitrate_kbps: Optional[int] = None
    pixel_format: Optional[str] = None
    profile: Optional[str] = None


@dataclass
class AudioStreamInfo:
    codec: str
    sample_rate: int
    channels: int
    bitrate_kbps: Optional[int] = None
    language: Optional[str] = None


@dataclass
class MediaInfo:
    path: Path
    container: str
    duration_seconds: float
    size_bytes: int
    video: Optional[VideoStreamInfo] = None
    audio: Optional[AudioStreamInfo] = None

    @property
    def has_video(self) -> bool:
        return self.video is not None

    @property
    def has_audio(self) -> bool:
        return self.audio is not None


# ---------------------------------------------------------------------------
# FFmpeg location
# ---------------------------------------------------------------------------

class FFmpegSource(Enum):
    BUNDLED = auto()
    SYSTEM_PATH = auto()
    USER_SELECTED = auto()
    NOT_FOUND = auto()


@dataclass
class FFmpegLocation:
    source: FFmpegSource
    ffmpeg_path: Optional[Path] = None
    ffprobe_path: Optional[Path] = None
    version: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.source != FFmpegSource.NOT_FOUND and self.ffmpeg_path is not None


# ---------------------------------------------------------------------------
# Jobs / progress
# ---------------------------------------------------------------------------

class JobStatus(Enum):
    QUEUED = "Queued"
    RUNNING = "Running"
    SUCCESS = "Success"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    SKIPPED = "Skipped"


@dataclass
class ProgressState:
    """Snapshot parsed from ffmpeg's `-progress pipe:1` output."""
    out_time_seconds: float = 0.0
    speed: Optional[float] = None  # e.g. 2.1 for "2.1x"
    fps: Optional[float] = None
    total_size_bytes: Optional[int] = None
    percent: Optional[float] = None  # 0-100, None if total duration unknown
    eta_seconds: Optional[float] = None
    raw_status: Optional[str] = None  # ffmpeg's own "progress=..." value


@dataclass
class Job:
    id: str
    operation_name: str
    input_paths: list[Path]
    output_path: Path
    command: list[str]
    status: JobStatus = JobStatus.QUEUED
    error_message: Optional[str] = None
    log: list[str] = field(default_factory=list)
    duration_hint_seconds: Optional[float] = None  # for percent calculation


# ---------------------------------------------------------------------------
# Presets
# ---------------------------------------------------------------------------

@dataclass
class Preset:
    id: str
    name: str
    operation: str  # matches Operation.name, e.g. "compress"
    description: str = ""
    params: dict = field(default_factory=dict)
    built_in: bool = False


@dataclass
class HistoryEntry:
    id: str
    date: str  # ISO 8601
    operation: str
    input_summary: str
    output_path: str
    status: str  # JobStatus value as string
    duration_seconds: Optional[float] = None
    command: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# App settings
# ---------------------------------------------------------------------------

@dataclass
class AppSettings:
    ffmpeg_path: Optional[str] = None
    ffprobe_path: Optional[str] = None
    default_output_folder: Optional[str] = None
    theme: str = "System"  # "Light" | "Dark" | "System"
    language: str = "en"  # ISO code, matches app/i18n/locales/<code>.json
    overwrite_policy: str = "Ask every time"  # "Always overwrite" | "Never overwrite" | "Ask every time"
    open_output_folder_on_complete: bool = False
    remember_last_directory: bool = True
    last_directory: Optional[str] = None
    notifications_enabled: bool = True
    window_geometry: Optional[str] = None  # base64-encoded QMainWindow.saveGeometry()
