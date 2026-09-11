"""Resolves and applies the app's Light/Dark/System theme.

Previously the stylesheet was only ever loaded once at startup — changing
the Settings page's Theme dropdown updated AppSettings but nothing re-applied
a stylesheet, so the UI never visibly changed. apply_theme() is now called
both at startup and whenever the setting changes.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_effective_theme(theme: str) -> str:
    """Turn 'System' into a concrete 'Light' or 'Dark' choice."""
    if theme in ("Light", "Dark"):
        return theme
    # "System": Qt 6.5+ exposes the OS color scheme via styleHints().
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        # Qt.ColorScheme.Dark == 2, Light == 1, Unknown == 0
        if scheme is not None and scheme.name == "Dark":
            return "Dark"
        if scheme is not None and scheme.name == "Light":
            return "Light"
    except AttributeError:
        pass
    # Fall back to Dark if the OS scheme can't be determined — matches the
    # app's original default look rather than guessing wrong either way.
    return "Dark"


def apply_theme(app: QApplication, theme: str) -> None:
    effective = _resolve_effective_theme(theme)
    filename = "style_light.qss" if effective == "Light" else "style_dark.qss"
    style_path = _PROJECT_ROOT / "assets" / filename
    if style_path.exists():
        app.setStyleSheet(style_path.read_text(encoding="utf-8"))
