"""Guards against the exact bug that shipped in an early build: app/i18n/locales/
and presets/ are read from disk at runtime but aren't Python source, so
PyInstaller's automatic analysis can't discover them — they must be listed
explicitly in build/build.py's data_dirs, or every translated string quietly
falls back to showing its raw key (e.g. "nav.home") with no crash and no
obvious cause.

This test doesn't run PyInstaller (too slow/heavy for a unit test, and not
available on every dev machine) — it just checks the build script's source
still declares the directories the app actually needs at runtime.
"""
from pathlib import Path

_BUILD_SCRIPT = Path(__file__).resolve().parents[1] / "build" / "build.py"

# Every directory the running app reads from disk (not imports as Python
# code) at runtime. If a future change adds a new one, add it here too —
# that's the whole point of this test catching the gap.
_REQUIRED_BUNDLED_DIRS = ["assets", "app/i18n/locales", "presets"]


def test_build_script_bundles_every_runtime_data_directory():
    content = _BUILD_SCRIPT.read_text(encoding="utf-8")
    for data_dir in _REQUIRED_BUNDLED_DIRS:
        assert data_dir in content, (
            f"build/build.py doesn't appear to bundle '{data_dir}' — "
            f"anything the app reads from that folder at runtime will be "
            f"missing from the packaged .exe."
        )
