"""History page: view, repeat-reference, and clear past jobs."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QApplication, QMessageBox,
)

from app.core.history_manager import HistoryManager
from app.i18n.translator import t
from app.utils.os_utils import open_folder


class HistoryPage(QWidget):
    def __init__(self, history_manager: HistoryManager, parent=None):
        super().__init__(parent)
        self._history_manager = history_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.history"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Date", "Operation", "Input", "Output", "Status"])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        button_row = QHBoxLayout()
        open_folder_button = QPushButton(t("history.open_output_folder"))
        open_folder_button.setObjectName("secondaryButton")
        open_folder_button.clicked.connect(self._open_output_folder)
        copy_command_button = QPushButton(t("history.copy_command"))
        copy_command_button.setObjectName("secondaryButton")
        copy_command_button.clicked.connect(self._copy_command)
        delete_button = QPushButton(t("history.delete_entry"))
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self._delete_selected)
        clear_button = QPushButton(t("history.clear_all"))
        clear_button.setObjectName("dangerButton")
        clear_button.clicked.connect(self._clear_all)
        for b in (open_folder_button, copy_command_button, delete_button, clear_button):
            button_row.addWidget(b)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self) -> None:
        entries = self._history_manager.list_entries()
        self._table.setRowCount(len(entries))
        self._entries = entries
        for row, entry in enumerate(entries):
            self._table.setItem(row, 0, QTableWidgetItem(entry.date))
            self._table.setItem(row, 1, QTableWidgetItem(entry.operation))
            self._table.setItem(row, 2, QTableWidgetItem(entry.input_summary))
            self._table.setItem(row, 3, QTableWidgetItem(entry.output_path))
            self._table.setItem(row, 4, QTableWidgetItem(entry.status))

    def _selected_entry(self):
        row = self._table.currentRow()
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _open_output_folder(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        folder = Path(entry.output_path).parent
        if not folder.exists():
            QMessageBox.warning(self, "Open Folder", "That folder no longer exists.")
            return
        open_folder(folder)

    def _copy_command(self) -> None:
        entry = self._selected_entry()
        if not entry or not entry.command:
            QMessageBox.information(self, "Copy Command", "No command was recorded for this entry.")
            return
        QApplication.clipboard().setText(" ".join(shlex.quote(p) for p in entry.command))

    def _delete_selected(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        self._history_manager.delete(entry.id)
        self.refresh()

    def _clear_all(self) -> None:
        reply = QMessageBox.question(self, "Clear History", "Delete all history entries?")
        if reply == QMessageBox.StandardButton.Yes:
            self._history_manager.clear()
            self.refresh()
