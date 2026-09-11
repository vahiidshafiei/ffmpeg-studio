"""Shows the exact FFmpeg command that will run, with a copy button.

Every operation page embeds one of these — the core principle "GUI
convenience + full FFmpeg transparency" means the user must always be able
to see this before clicking Run.
"""
from __future__ import annotations

import shlex
from typing import List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QApplication,
)

from app.i18n.translator import t


class CommandPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(t("common.generated_command"))
        header.setObjectName("sectionLabel")
        layout.addWidget(header)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setObjectName("commandPreview")
        self._text.setMaximumHeight(90)
        layout.addWidget(self._text)

        button_row = QHBoxLayout()
        self._copy_button = QPushButton(t("common.copy_command"))
        self._copy_button.clicked.connect(self._copy_to_clipboard)
        button_row.addWidget(self._copy_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._current_command: List[str] = []

    def set_command(self, command: List[str]) -> None:
        self._current_command = command
        self._text.setPlainText(self._format(command))

    def clear(self) -> None:
        self._current_command = []
        self._text.setPlainText("")

    @staticmethod
    def _format(command: List[str]) -> str:
        if not command:
            return ""
        # shlex.quote keeps paths-with-spaces readable and copy-pasteable
        # into a real shell, without affecting the argument list actually
        # passed to QProcess (which never goes through a shell).
        return " ".join(shlex.quote(part) for part in command)

    def _copy_to_clipboard(self) -> None:
        QApplication.clipboard().setText(self._format(self._current_command))
