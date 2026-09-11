"""Presets page: browse built-in presets, manage custom ones.

Applying a preset directly into an operation page's controls is a natural
next hook to add per-page as their forms stabilize; this page focuses on
preset management (browse/duplicate/delete/export/import), which stands on
its own regardless of that wiring.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QTextEdit, QFileDialog, QMessageBox, QInputDialog,
)

from app.i18n.translator import t
from app.presets.preset_manager import PresetManager


class PresetsPage(QWidget):
    def __init__(self, preset_manager: PresetManager, parent=None):
        super().__init__(parent)
        self._preset_manager = preset_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.presets"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        body_row = QHBoxLayout()
        self._list = QListWidget()
        self._list.currentItemChanged.connect(self._on_selection_changed)
        body_row.addWidget(self._list, stretch=1)

        self._detail = QTextEdit()
        self._detail.setReadOnly(True)
        body_row.addWidget(self._detail, stretch=2)
        layout.addLayout(body_row)

        button_row = QHBoxLayout()
        duplicate_button = QPushButton(t("common.duplicate"))
        duplicate_button.setObjectName("secondaryButton")
        duplicate_button.clicked.connect(self._duplicate)
        delete_button = QPushButton(t("common.delete"))
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self._delete)
        export_button = QPushButton(t("presets.export"))
        export_button.setObjectName("secondaryButton")
        export_button.clicked.connect(self._export)
        import_button = QPushButton(t("presets.import"))
        import_button.setObjectName("secondaryButton")
        import_button.clicked.connect(self._import)
        for b in (duplicate_button, delete_button, export_button, import_button):
            button_row.addWidget(b)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.refresh()

    def refresh(self) -> None:
        self._preset_manager.reload()
        self._list.clear()
        for preset in self._preset_manager.list_presets():
            label = f"{'⭐ ' if preset.built_in else ''}{preset.name}  ·  {preset.operation}"
            item = QListWidgetItem(label)
            item.setData(1000, preset.id)
            self._list.addItem(item)

    def _current_preset(self):
        item = self._list.currentItem()
        if not item:
            return None
        return self._preset_manager.get(item.data(1000))

    def _on_selection_changed(self, *_args) -> None:
        preset = self._current_preset()
        if not preset:
            self._detail.setPlainText("")
            return
        lines = [
            f"Name: {preset.name}",
            f"Operation: {preset.operation}",
            f"Built-in: {'yes' if preset.built_in else 'no'}",
            f"Description: {preset.description}",
            "",
            "Parameters:",
        ]
        for key, value in preset.params.items():
            lines.append(f"  {key}: {value}")
        self._detail.setPlainText("\n".join(lines))

    def _duplicate(self) -> None:
        preset = self._current_preset()
        if not preset:
            return
        name, ok = QInputDialog.getText(self, "Duplicate Preset", "New preset name:", text=f"{preset.name} (Copy)")
        if ok and name:
            self._preset_manager.duplicate(preset.id, name)
            self.refresh()

    def _delete(self) -> None:
        preset = self._current_preset()
        if not preset:
            return
        if preset.built_in:
            QMessageBox.information(self, "Delete Preset", "Built-in presets can't be deleted.")
            return
        if self._preset_manager.delete(preset.id):
            self.refresh()

    def _export(self) -> None:
        preset = self._current_preset()
        if not preset:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export preset", f"{preset.id}.json", "JSON (*.json)")
        if path:
            self._preset_manager.export_to(preset.id, Path(path))

    def _import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import preset", filter="JSON (*.json)")
        if not path:
            return
        try:
            self._preset_manager.import_from(Path(path))
            self.refresh()
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.critical(self, "Import Preset", f"Could not import preset: {exc}")
