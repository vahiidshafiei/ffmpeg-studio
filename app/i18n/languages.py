"""Metadata for every language the app can display in. Adding a language
means: add an entry here, and add app/i18n/locales/<code>.json with the same
keys as en.json (English is the fallback for any missing key).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Language:
    code: str          # ISO 639-1, matches the locales/<code>.json filename
    native_name: str    # shown in the language's own script, e.g. "Türkçe"
    english_name: str  # shown for reference/search, e.g. "Turkish"
    flag: str          # emoji flag shown next to the name in the selector


SUPPORTED_LANGUAGES: List[Language] = [
    Language(code="en", native_name="English", english_name="English", flag="🇬🇧"),
    Language(code="tr", native_name="Türkçe", english_name="Turkish", flag="🇹🇷"),
]

DEFAULT_LANGUAGE_CODE = "en"


def get_language(code: str) -> Language:
    for lang in SUPPORTED_LANGUAGES:
        if lang.code == code:
            return lang
    return SUPPORTED_LANGUAGES[0]
