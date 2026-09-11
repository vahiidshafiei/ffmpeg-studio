"""Wraps ffprobe to build MediaInfo objects. Never guesses from file extensions."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

from app.models.models import AudioStreamInfo, MediaInfo, VideoStreamInfo


class ProbeError(Exception):
    pass


def probe_media(ffprobe_path: Path, media_path: Path, timeout: float = 15.0) -> MediaInfo:
    """Run ffprobe -print_format json and parse the result into MediaInfo."""
    if not media_path.is_file():
        raise ProbeError(f"File not found: {media_path}")

    cmd = [
        str(ffprobe_path),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(media_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(f"Failed to run ffprobe: {exc}") from exc

    if result.returncode != 0:
        raise ProbeError(result.stderr.strip() or "ffprobe failed with no error output")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"Could not parse ffprobe output: {exc}") from exc

    fmt = data.get("format", {})
    streams = data.get("streams", [])

    video_info: Optional[VideoStreamInfo] = None
    audio_info: Optional[AudioStreamInfo] = None

    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video" and video_info is None:
            video_info = VideoStreamInfo(
                codec=stream.get("codec_name", "unknown"),
                width=int(stream.get("width", 0) or 0),
                height=int(stream.get("height", 0) or 0),
                fps=_parse_frame_rate(stream.get("r_frame_rate")),
                bitrate_kbps=_to_kbps(stream.get("bit_rate")),
                pixel_format=stream.get("pix_fmt"),
                profile=stream.get("profile"),
            )
        elif codec_type == "audio" and audio_info is None:
            audio_info = AudioStreamInfo(
                codec=stream.get("codec_name", "unknown"),
                sample_rate=int(stream.get("sample_rate", 0) or 0),
                channels=int(stream.get("channels", 0) or 0),
                bitrate_kbps=_to_kbps(stream.get("bit_rate")),
                language=(stream.get("tags") or {}).get("language"),
            )

    duration = 0.0
    try:
        duration = float(fmt.get("duration", 0.0) or 0.0)
    except (TypeError, ValueError):
        pass

    size_bytes = 0
    try:
        size_bytes = int(fmt.get("size") or media_path.stat().st_size)
    except (TypeError, ValueError):
        size_bytes = media_path.stat().st_size

    return MediaInfo(
        path=media_path,
        container=fmt.get("format_name", "unknown"),
        duration_seconds=duration,
        size_bytes=size_bytes,
        video=video_info,
        audio=audio_info,
    )


def _parse_frame_rate(value: Optional[str]) -> float:
    if not value:
        return 0.0
    if "/" in value:
        num, _, den = value.partition("/")
        try:
            num_f, den_f = float(num), float(den)
            return round(num_f / den_f, 3) if den_f else 0.0
        except ValueError:
            return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _to_kbps(bit_rate: Optional[str]) -> Optional[int]:
    if not bit_rate:
        return None
    try:
        return int(int(bit_rate) / 1000)
    except (TypeError, ValueError):
        return None
