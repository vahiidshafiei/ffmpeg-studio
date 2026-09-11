"""A labeled 'Output name (optional)' field, reused across pages.

Just a QLineEdit with a placeholder explaining the default-naming fallback —
kept as its own widget so every page wires it up identically.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLineEdit

from app.i18n.translator import t


class OutputNameField(QLineEdit):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(t("common.output_name_placeholder"))
        self.textChanged.connect(self.changed.emit)

    def value(self) -> str:
        return self.text().strip()
