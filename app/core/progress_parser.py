"""Parses ffmpeg's machine-readable progress output.

Run ffmpeg with `-progress pipe:1 -nostats` and feed each stdout line to
`ProgressParser.feed()`. ffmpeg emits a block of key=value lines terminated
by a line "progress=continue" or "progress=end" — feed() accumulates keys
and returns a ProgressState once a terminator line completes a block.
"""
from __future__ import annotations

from typing import Optional

from app.models.models import ProgressState


class ProgressParser:
    def __init__(self, total_duration_seconds: Optional[float] = None):
        self.total_duration_seconds = total_duration_seconds
        self._pending: dict[str, str] = {}

    def feed(self, line: str) -> Optional[ProgressState]:
        line = line.strip()
        if not line or "=" not in line:
            return None
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        self._pending[key] = value

        if key != "progress":
            return None

        state = self._build_state(value)
        self._pending = {}
        return state

    def _build_state(self, progress_value: str) -> ProgressState:
        out_time_us = self._pending.get("out_time_us") or self._pending.get("out_time_ms")
        out_time_seconds = 0.0
        if out_time_us is not None:
            try:
                # out_time_us is microseconds in modern ffmpeg; out_time_ms (legacy)
                # is actually also microseconds in some builds, so we normalize
                # to seconds the same way — divide by 1_000_000. If a build truly
                # emits milliseconds, the "out_time" HH:MM:SS.ms field below is
                # used as a more reliable fallback.
                out_time_seconds = int(out_time_us) / 1_000_000
            except ValueError:
                out_time_seconds = 0.0
        elif "out_time" in self._pending:
            out_time_seconds = _parse_hms(self._pending["out_time"])

        speed_raw = self._pending.get("speed", "").rstrip("x")
        speed = None
        if speed_raw and speed_raw != "N/A":
            try:
                speed = float(speed_raw)
            except ValueError:
                speed = None

        fps_raw = self._pending.get("fps")
        fps = None
        if fps_raw and fps_raw != "N/A":
            try:
                fps = float(fps_raw)
            except ValueError:
                fps = None

        size_raw = self._pending.get("total_size")
        total_size_bytes = None
        if size_raw and size_raw.isdigit():
            total_size_bytes = int(size_raw)

        percent = None
        eta_seconds = None
        if self.total_duration_seconds and self.total_duration_seconds > 0:
            percent = min(100.0, max(0.0, out_time_seconds / self.total_duration_seconds * 100))
            if speed and speed > 0:
                remaining = max(0.0, self.total_duration_seconds - out_time_seconds)
                eta_seconds = remaining / speed

        return ProgressState(
            out_time_seconds=out_time_seconds,
            speed=speed,
            fps=fps,
            total_size_bytes=total_size_bytes,
            percent=percent,
            eta_seconds=eta_seconds,
            raw_status=progress_value,
        )


def _parse_hms(value: str) -> float:
    try:
        h, m, s = value.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return 0.0
