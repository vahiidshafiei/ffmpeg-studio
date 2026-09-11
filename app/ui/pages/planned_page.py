"""Placeholder shown for pages not yet implemented.

Per spec rule "Do not fake features": until an operation's real page ships,
the sidebar entry still navigates somewhere, but it clearly says the feature
is planned rather than presenting a non-functional form.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class PlannedFeaturePage(QWidget):
    def __init__(self, title: str, phase_note: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        layout.addWidget(title_label)

        note_label = QLabel(f"🚧 Not implemented yet. {phase_note}")
        note_label.setObjectName("mutedLabel")
        note_label.setWordWrap(True)
        layout.addWidget(note_label)

        layout.addStretch()
