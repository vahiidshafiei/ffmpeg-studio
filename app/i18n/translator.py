"""Loads a language's string table and resolves keys to translated text.

Usage in UI code:
    from app.i18n.translator import t
    label = QLabel(t("nav.compress"))

Missing keys fall back to English, then to the key itself (so a missing
translation shows up as an obviously-wrong string like "nav.compress"
instead of crashing) — this makes gaps easy to spot without breaking the app.
If an ENTIRE locale file fails to load (e.g. it wasn't bundled into a
packaged .exe — see build/build.py's data_dirs list), every string in the
app would show as a raw key; a warning is logged in that case specifically,
since that failure mode is otherwise silent and easy to mistake for "the UI
just isn't translated" rather than "the translation files are missing".

Language changes are applied by loading a new table and take full effect on
the next app restart (see Settings page) — this app does not attempt to
retranslate already-built widgets live, since doing that correctly for every
widget in every page would require a much larger refactor than a "restart
to apply" prompt costs the user.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict

from app.i18n.languages import DEFAULT_LANGUAGE_CODE

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"
_logger = logging.getLogger("ffmpeg_studio")

_current_code = DEFAULT_LANGUAGE_CODE
_current_strings: Dict[str, str] = {}
_fallback_strings: Dict[str, str] = {}


def _load_locale_file(code: str) -> Dict[str, str]:
    path = _LOCALES_DIR / f"{code}.json"
    if not path.exists():
        _logger.warning(
            "Locale file not found: %s (translations will show as raw keys, e.g. 'nav.home'). "
            "If this is a packaged build, app/i18n/locales/ wasn't bundled — see build/build.py.",
            path,
        )
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _logger.warning("Could not read locale file %s: %s", path, exc)
        return {}


def set_language(code: str) -> None:
    """Load `code`'s string table as current. Call once at startup."""
    global _current_code, _current_strings, _fallback_strings
    _current_code = code
    _current_strings = _load_locale_file(code)
    if code != DEFAULT_LANGUAGE_CODE:
        _fallback_strings = _load_locale_file(DEFAULT_LANGUAGE_CODE)
    else:
        _fallback_strings = {}


def current_language_code() -> str:
    return _current_code


def has_loaded_strings() -> bool:
    """False means no locale file loaded at all — every t() call will return
    raw keys. Used by main.py to surface this loudly on startup instead of
    leaving the person staring at a UI full of "nav.home"-style text with no
    explanation of why.
    """
    return bool(_current_strings) or bool(_fallback_strings)


def t(key: str, **kwargs) -> str:
    """Resolve a translation key, formatting with kwargs if given."""
    text = _current_strings.get(key) or _fallback_strings.get(key) or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


# Load English by default so `t()` works even before set_language() is
# explicitly called (e.g. in unit tests that import a page module directly).
set_language(DEFAULT_LANGUAGE_CODE)
