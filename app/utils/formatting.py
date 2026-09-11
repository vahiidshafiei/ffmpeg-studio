"""Small formatting helpers shared across UI pages."""
from __future__ import annotations


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS (or HH:MM:SS.ms if sub-second precision matters)."""
    if seconds is None or seconds < 0:
        return "00:00:00"
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    if ms:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_timecode(text: str) -> float:
    """Parse HH:MM:SS[.ms] or plain seconds into a float number of seconds.

    Raises ValueError on malformed input rather than silently returning 0,
    so the UI can surface a validation error instead of building a bad command.
    """
    text = text.strip()
    if not text:
        raise ValueError("Empty timecode")
    if ":" not in text:
        return float(text)
    parts = text.split(":")
    if len(parts) not in (2, 3):
        raise ValueError(f"Invalid timecode: {text}")
    parts = [float(p) for p in parts]
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0.0
    else:
        hours, minutes, seconds = parts
    if minutes >= 60 or seconds >= 60 or minutes < 0 or seconds < 0:
        raise ValueError(f"Invalid timecode: {text}")
    return hours * 3600 + minutes * 60 + seconds


def format_size(num_bytes: float) -> str:
    """Human readable file size, e.g. 1.42 GB."""
    if num_bytes is None:
        return "—"
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < step:
            return f"{num_bytes:.2f} {unit}" if unit != "B" else f"{int(num_bytes)} {unit}"
        num_bytes /= step
    return f"{num_bytes:.2f} PB"


def format_bitrate(kbps: float) -> str:
    if kbps is None:
        return "—"
    if kbps >= 1000:
        return f"{kbps / 1000:.1f} Mbps"
    return f"{kbps:.0f} kbps"
