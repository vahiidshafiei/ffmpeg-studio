"""Builds FFmpegStudio.exe with PyInstaller.

Usage:
    python build\\build.py

Produces:
    dist/FFmpegStudio/FFmpegStudio.exe   (one-folder build; see notes below)

Notes:
- One-folder (not one-file) packaging is used by default: PySide6 apps have a
  large set of Qt plugin/DLL dependencies, and one-file mode's self-extraction
  to a temp directory noticeably slows startup and complicates bundling the
  ffmpeg/ subfolder next to the exe. One-folder keeps startup fast and makes
  "drop ffmpeg.exe next to the exe" (Option A bundling) trivial.
- If an `ffmpeg/` folder with ffmpeg.exe + ffprobe.exe exists in the project
  root at build time, it is copied into the dist output automatically.
- Run this from the project root or via `python build/build.py`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = PROJECT_ROOT / "dist" / "FFmpegStudio"
# PyInstaller's own defaults are ./build and ./<name>.spec in the current
# directory — which would collide with this project's own build/ folder
# (this very script lives there) and clutter the project root with a spec
# file. Pointing both explicitly at build/_pyinstaller/ keeps every
# generated artifact contained in one place that's easy to .gitignore
# without ever touching build/build.py itself.
WORK_DIR = PROJECT_ROOT / "build" / "_pyinstaller" / "work"
SPEC_DIR = PROJECT_ROOT / "build" / "_pyinstaller" / "spec"


def run_pyinstaller() -> None:
    icon_path = PROJECT_ROOT / "assets" / "logo" / "ffmpeg_studio.ico"
    sep = ";" if sys.platform == "win32" else ":"
    # Every one of these is a data folder read from disk at runtime (not
    # imported as Python code), so PyInstaller's automatic dependency
    # analysis can't see it — each needs its own --add-data entry, placed
    # at a destination path that matches its source path relative to the
    # project root. That's what lets every runtime Path(__file__)-relative
    # lookup in the app (translator.py, preset_manager.py, theme.py, etc.)
    # resolve identically whether running from source or from the frozen
    # .exe, with no frozen-vs-dev branching needed in that code at all.
    data_dirs = ["assets", "app/i18n/locales", "presets"]
    args = [
        sys.executable, "-m", "PyInstaller",
        "--name", "FFmpegStudio",
        "--windowed",
        "--noconfirm",
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(WORK_DIR),
        "--specpath", str(SPEC_DIR),
        str(PROJECT_ROOT / "app" / "main.py"),
    ]
    for data_dir in data_dirs:
        args += ["--add-data", f"{PROJECT_ROOT / data_dir}{sep}{data_dir}"]
    if icon_path.exists():
        args[3:3] = ["--icon", str(icon_path)]
    subprocess.run(args, check=True, cwd=PROJECT_ROOT)


def bundle_ffmpeg_if_present() -> None:
    source = PROJECT_ROOT / "ffmpeg"
    if not source.is_dir():
        print("No local ffmpeg/ folder found — skipping bundling (Option B/C still work at runtime).")
        return
    target = DIST_DIR / "ffmpeg"
    shutil.copytree(source, target, dirs_exist_ok=True)
    print(f"Bundled ffmpeg/ into {target}")


def main() -> None:
    run_pyinstaller()
    bundle_ffmpeg_if_present()
    print(f"\nBuild complete: {DIST_DIR / 'FFmpegStudio.exe'}")


if __name__ == "__main__":
    main()
