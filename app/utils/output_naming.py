"""Turns an optional user-typed filename into a real output Path.

If the user leaves the field blank, the operation's own default name (e.g.
"input_compressed.mp4") is used unchanged. If they type something, it's
placed in the same folder as the default, with the default's extension
added automatically if they didn't type one.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def resolve_custom_output_name(default_path: Path, custom_name: Optional[str]) -> Path:
    if not custom_name or not custom_name.strip():
        return default_path
    name = custom_name.strip()
    candidate = Path(name)
    if not candidate.suffix:
        candidate = candidate.with_suffix(default_path.suffix)
    if not candidate.is_absolute():
        candidate = default_path.parent / candidate
    return candidate
