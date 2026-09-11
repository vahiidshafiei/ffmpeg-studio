"""Opens a folder in the OS file manager. Shared so every page's success
handler can honor the "automatically open output folder" setting the same
way, instead of each page reimplementing platform detection.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_folder(path: Path) -> None:
    folder = path if path.is_dir() else path.parent
    if not folder.exists():
        return
    if sys.platform == "win32":
        os.startfile(str(folder))  # noqa: S606 — local folder we just wrote to, not user input
    elif sys.platform == "darwin":
        subprocess.run(["open", str(folder)])
    else:
        subprocess.run(["xdg-open", str(folder)])


def maybe_open_output_folder(settings_manager, output_path: Path) -> None:
    """Open output_path's folder if the user has that behavior turned on."""
    if settings_manager is not None and settings_manager.settings.open_output_folder_on_complete:
        open_folder(output_path)
