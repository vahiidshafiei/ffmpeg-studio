"""Merge page: select multiple videos, reorder them, concatenate."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QComboBox, QGroupBox, QFormLayout, QMessageBox, QFileDialog,
)

from app.operations.merge import MergeOperation
from app.i18n.translator import t
from app.ui.dialogs.overwrite_dialog import resolve_output_path
from app.ui.widgets.run_panel import RunPanel
from app.ui.widgets.output_name_field import OutputNameField
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name


class MergePage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager=None, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._operation = MergeOperation()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.merge"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        list_row = QHBoxLayout()
        self._list = QListWidget()
        list_row.addWidget(self._list, stretch=1)

        buttons_col = QVBoxLayout()
        add_button = QPushButton("Add…")
        add_button.clicked.connect(self._add_files)
        up_button = QPushButton("Move Up")
        up_button.clicked.connect(self._move_up)
        down_button = QPushButton("Move Down")
        down_button.clicked.connect(self._move_down)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._remove_selected)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear)
        for b in (add_button, up_button, down_button, remove_button, clear_button):
            buttons_col.addWidget(b)
        buttons_col.addStretch()
        list_row.addLayout(buttons_col)
        layout.addLayout(list_row)

        options_group = QGroupBox(t("common.options_group"))
        form = QFormLayout(options_group)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["fast", "compatibility"])
        self._mode_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow("Mode:", self._mode_combo)

        mode_note = QLabel(
            "Fast mode concatenates without re-encoding, but only works reliably when all "
            "videos share the same codec/resolution/frame rate. Compatibility mode re-encodes "
            "everything to a common format first — use it if fast mode fails or your clips differ."
        )
        mode_note.setObjectName("mutedLabel")
        mode_note.setWordWrap(True)
        form.addRow("", mode_note)

        self._output_name_field = OutputNameField()
        self._output_name_field.changed.connect(self._refresh_preview)
        form.addRow(t("common.output_name_label"), self._output_name_field)

        layout.addWidget(options_group)

        self._run_panel = RunPanel()
        self._run_panel.run_button.clicked.connect(self._run)
        self._run_panel.job_succeeded.connect(self._on_job_succeeded)
        self._run_panel.job_failed.connect(self._on_job_failed)
        layout.addWidget(self._run_panel)
        layout.addStretch()

    def _on_job_succeeded(self, output_path: Path) -> None:
        if self._history_manager:
            self._history_manager.add(
                operation="merge", input_summary=f"{self._list.count()} videos",
                output_path=str(output_path), status="Success",
            )
        maybe_open_output_folder(self._settings_manager, output_path)

    def _on_job_failed(self, _message: str) -> None:
        if self._history_manager:
            self._history_manager.add(
                operation="merge", input_summary=f"{self._list.count()} videos",
                output_path="", status="Failed",
            )

    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select videos", filter="Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*)"
        )
        for path in paths:
            self._list.addItem(path)
        self._refresh_preview()

    def _move_up(self) -> None:
        row = self._list.currentRow()
        if row > 0:
            item = self._list.takeItem(row)
            self._list.insertItem(row - 1, item)
            self._list.setCurrentRow(row - 1)
        self._refresh_preview()

    def _move_down(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < self._list.count() - 1:
            item = self._list.takeItem(row)
            self._list.insertItem(row + 1, item)
            self._list.setCurrentRow(row + 1)
        self._refresh_preview()

    def _remove_selected(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
        self._refresh_preview()

    def _clear(self) -> None:
        self._list.clear()
        self._refresh_preview()

    def _inputs(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _build_params(self) -> Optional[dict]:
        inputs = self._inputs()
        if len(inputs) < 2:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        first = Path(inputs[0])
        output_path = first.with_name(f"{first.stem}_merged{first.suffix}")
        output_path = resolve_custom_output_name(output_path, self._output_name_field.value())
        list_file_path = Path(tempfile.gettempdir()) / "ffmpeg_studio_merge_list.txt"
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "inputs": inputs,
            "output": str(output_path),
            "mode": self._mode_combo.currentText(),
            "list_file_path": str(list_file_path),
            "overwrite": False,
        }

    def _refresh_preview(self, *_args) -> None:
        params = self._build_params()
        if not params:
            self._run_panel.set_preview_command(None)
            return
        try:
            self._run_panel.set_preview_command(self._operation.build_command(params))
        except ValueError as exc:
            self._run_panel.set_preview_command([f"# Invalid configuration: {exc}"])

    def _run(self) -> None:
        params = self._build_params()
        if not params:
            QMessageBox.warning(self, "Merge", "Add at least two videos and make sure FFmpeg is configured.")
            return

        resolved = resolve_output_path(
            self, Path(params["output"]), self._settings_manager.settings.overwrite_policy
        )
        if resolved is None:
            return
        params["output"] = str(resolved)
        params["overwrite"] = True

        try:
            command = self._operation.build_command(params)
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid settings", str(exc))
            return

        self._run_panel.run(command, resolved)
