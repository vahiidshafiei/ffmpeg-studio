"""Natural/numeric sorting for filenames.

Ensures 1.mp3, 2.mp3, 10.mp3 sort in the expected numeric order rather than
lexicographic order (which would put 10.mp3 before 2.mp3).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List

_CHUNK_RE = re.compile(r"(\d+)")


def natural_sort_key(value: str):
    """Split a string into text/number chunks so digit runs compare numerically."""
    parts = _CHUNK_RE.split(value)
    key = []
    for part in parts:
        if part.isdigit():
            key.append((1, int(part)))
        else:
            key.append((0, part.lower()))
    return key


def natural_sorted_paths(paths: Iterable[Path]) -> List[Path]:
    """Sort paths by their filename using natural sort order."""
    return sorted(paths, key=lambda p: natural_sort_key(p.name))


def natural_sorted_strings(values: Iterable[str]) -> List[str]:
    return sorted(values, key=natural_sort_key)
