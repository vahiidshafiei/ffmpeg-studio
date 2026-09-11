"""Common interface every operation implements.

UI pages collect params into a dict and hand them to `build_command` /
`validate`. Nothing here touches Qt or subprocess — these are pure functions
of (params) -> list[str], which is what makes them unit-testable without
launching the GUI (rule from spec section 35).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class Operation(ABC):
    name: str = "operation"
    description: str = ""

    @abstractmethod
    def validate(self, params: dict) -> List[str]:
        """Return a list of human-readable validation errors (empty = valid)."""
        raise NotImplementedError

    @abstractmethod
    def build_command(self, params: dict) -> List[str]:
        """Build the full ffmpeg argument list, starting with the ffmpeg path."""
        raise NotImplementedError

    def default_output_name(self, input_path: Path, suffix: str, extension: str) -> Path:
        return input_path.with_name(f"{input_path.stem}_{suffix}{extension}")
