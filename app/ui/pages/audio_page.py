"""Audio page: three tabs sharing one file, since they're all audio-focused
workflows a user reaches for from the same sidebar entry.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QComboBox,
    QFormLayout, QMessageBox, QListWidget, QPushButton, QFileDialog,
)

from app.operations.audio import ExtractAudioOperation, ConvertAudioOperation, MergeAudioOperation
from app.i18n.translator import t
from app.ui.dialogs.overwrite_dialog import resolve_output_path
from app.ui.widgets.file_drop import FileDropField
from app.ui.widgets.run_panel import RunPanel
from app.ui.widgets.output_name_field import OutputNameField
from app.utils.natural_sort import natural_sorted_paths
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name

_FORMATS = ["copy", "mp3", "aac", "wav", "flac", "opus"]
_BITRATES = ["64k", "96k", "128k", "160k", "192k", "256k", "320k"]


class AudioPage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager=None, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.audio"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_extract_tab(), "Extract from Video")
        tabs.addTab(self._build_convert_tab(), "Convert")
        tabs.addTab(self._build_merge_tab(), "Merge (Batch)")
        layout.addWidget(tabs)

    def _log_history(self, operation: str, input_summary, output_path, status: str) -> None:
        if self._history_manager:
            self._history_manager.add(
                operation=operation,
                input_summary=str(input_summary) if input_summary else "",
                output_path=str(output_path) if output_path else "",
                status=status,
            )
        if status == "Success" and output_path:
            maybe_open_output_folder(self._settings_manager, Path(output_path))

    # ------------------------------------------------------------------
    # Extract tab
    # ------------------------------------------------------------------
    def _build_extract_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self._extract_input: Optional[Path] = None
        self._extract_op = ExtractAudioOperation()

        drop = FileDropField(t("common.drop_video_here"), mode="file")
        drop.paths_selected.connect(self._on_extract_file)
        layout.addWidget(drop)

        form = QFormLayout()
        self._extract_format = QComboBox()
        self._extract_format.addItems(_FORMATS)
        self._extract_format.currentTextChanged.connect(self._on_extract_format_changed)
        form.addRow(t("audio.format_label"), self._extract_format)
        self._extract_bitrate = QComboBox()
        self._extract_bitrate.addItems(_BITRATES)
        self._extract_bitrate.setCurrentText("192k")
        self._extract_bitrate.currentTextChanged.connect(self._refresh_extract_preview)
        form.addRow(t("audio.bitrate_label"), self._extract_bitrate)
        self._extract_output_name = OutputNameField()
        self._extract_output_name.changed.connect(self._refresh_extract_preview)
        form.addRow(t("common.output_name_label"), self._extract_output_name)
        layout.addLayout(form)

        self._extract_copy_hint = QLabel(t("audio.copy_hint"))
        self._extract_copy_hint.setObjectName("mutedLabel")
        self._extract_copy_hint.setWordWrap(True)
        self._extract_copy_hint.setVisible(False)
        layout.addWidget(self._extract_copy_hint)

        self._extract_panel = RunPanel()
        self._extract_panel.run_button.clicked.connect(self._run_extract)
        self._extract_panel.job_succeeded.connect(
            lambda out: self._log_history("extract_audio", self._extract_input, out, "Success")
        )
        self._extract_panel.job_failed.connect(
            lambda _msg: self._log_history("extract_audio", self._extract_input, None, "Failed")
        )
        layout.addWidget(self._extract_panel)
        layout.addStretch()
        return widget

    def _on_extract_file(self, paths) -> None:
        self._extract_input = paths[0]
        self._refresh_extract_preview()

    def _on_extract_format_changed(self, fmt: str) -> None:
        is_copy = fmt == "copy"
        self._extract_bitrate.setEnabled(not is_copy)
        self._extract_copy_hint.setVisible(is_copy)
        self._refresh_extract_preview()

    def _build_extract_params(self) -> Optional[dict]:
        if not self._extract_input:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        fmt = self._extract_format.currentText()
        extension = ".mka" if fmt == "copy" else f".{fmt}"
        output = self._extract_input.with_suffix(extension)
        output = resolve_custom_output_name(output, self._extract_output_name.value())
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "input": str(self._extract_input),
            "output": str(output),
            "format": fmt,
            "bitrate": self._extract_bitrate.currentText(),
            "overwrite": False,
        }

    def _refresh_extract_preview(self, *_args) -> None:
        params = self._build_extract_params()
        if not params:
            self._extract_panel.set_preview_command(None)
            return
        try:
            self._extract_panel.set_preview_command(self._extract_op.build_command(params))
        except ValueError as exc:
            self._extract_panel.set_preview_command([f"# Invalid configuration: {exc}"])

    def _run_extract(self) -> None:
        params = self._build_extract_params()
        if not params:
            QMessageBox.warning(self, "Extract Audio", "Select a video and make sure FFmpeg is configured.")
            return
        resolved = resolve_output_path(self, Path(params["output"]), self._settings_manager.settings.overwrite_policy)
        if resolved is None:
            return
        params["output"] = str(resolved)
        params["overwrite"] = True
        command = self._extract_op.build_command(params)
        self._extract_panel.run(command, resolved)

    # ------------------------------------------------------------------
    # Convert tab
    # ------------------------------------------------------------------
    def _build_convert_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self._convert_input: Optional[Path] = None
        self._convert_op = ConvertAudioOperation()

        drop = FileDropField(
            t("common.drop_audio_here"), mode="file",
            name_filter="Audio files (*.mp3 *.wav *.aac *.flac *.opus *.m4a);;All files (*)",
        )
        drop.paths_selected.connect(self._on_convert_file)
        layout.addWidget(drop)

        form = QFormLayout()
        self._convert_format = QComboBox()
        self._convert_format.addItems(_FORMATS)
        self._convert_format.currentTextChanged.connect(self._on_convert_format_changed)
        form.addRow(t("audio.format_label"), self._convert_format)
        self._convert_bitrate = QComboBox()
        self._convert_bitrate.addItems(_BITRATES)
        self._convert_bitrate.setCurrentText("192k")
        self._convert_bitrate.currentTextChanged.connect(self._refresh_convert_preview)
        form.addRow(t("audio.bitrate_label"), self._convert_bitrate)
        self._convert_sample_rate = QComboBox()
        self._convert_sample_rate.addItems(["Keep original", "44100", "48000"])
        self._convert_sample_rate.currentTextChanged.connect(self._refresh_convert_preview)
        form.addRow("Sample rate:", self._convert_sample_rate)
        self._convert_output_name = OutputNameField()
        self._convert_output_name.changed.connect(self._refresh_convert_preview)
        form.addRow(t("common.output_name_label"), self._convert_output_name)
        layout.addLayout(form)

        self._convert_copy_hint = QLabel(t("audio.copy_hint"))
        self._convert_copy_hint.setObjectName("mutedLabel")
        self._convert_copy_hint.setWordWrap(True)
        self._convert_copy_hint.setVisible(False)
        layout.addWidget(self._convert_copy_hint)

        self._convert_panel = RunPanel()
        self._convert_panel.run_button.clicked.connect(self._run_convert)
        self._convert_panel.job_succeeded.connect(
            lambda out: self._log_history("convert_audio", self._convert_input, out, "Success")
        )
        self._convert_panel.job_failed.connect(
            lambda _msg: self._log_history("convert_audio", self._convert_input, None, "Failed")
        )
        layout.addWidget(self._convert_panel)
        layout.addStretch()
        return widget

    def _on_convert_file(self, paths) -> None:
        self._convert_input = paths[0]
        self._refresh_convert_preview()

    def _on_convert_format_changed(self, fmt: str) -> None:
        is_copy = fmt == "copy"
        self._convert_bitrate.setEnabled(not is_copy)
        self._convert_sample_rate.setEnabled(not is_copy)
        self._convert_copy_hint.setVisible(is_copy)
        self._refresh_convert_preview()

    def _build_convert_params(self) -> Optional[dict]:
        if not self._convert_input:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        fmt = self._convert_format.currentText()
        extension = ".mka" if fmt == "copy" else f".{fmt}"
        output = self._convert_input.with_suffix(extension)
        output = resolve_custom_output_name(output, self._convert_output_name.value())
        sample_rate = self._convert_sample_rate.currentText()
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "input": str(self._convert_input),
            "output": str(output),
            "format": fmt,
            "bitrate": self._convert_bitrate.currentText(),
            "sample_rate": None if sample_rate == "Keep original" else int(sample_rate),
            "overwrite": False,
        }

    def _refresh_convert_preview(self, *_args) -> None:
        params = self._build_convert_params()
        if not params:
            self._convert_panel.set_preview_command(None)
            return
        try:
            self._convert_panel.set_preview_command(self._convert_op.build_command(params))
        except ValueError as exc:
            self._convert_panel.set_preview_command([f"# Invalid configuration: {exc}"])

    def _run_convert(self) -> None:
        params = self._build_convert_params()
        if not params:
            QMessageBox.warning(self, "Convert Audio", "Select a file and make sure FFmpeg is configured.")
            return
        resolved = resolve_output_path(self, Path(params["output"]), self._settings_manager.settings.overwrite_policy)
        if resolved is None:
            return
        params["output"] = str(resolved)
        params["overwrite"] = True
        command = self._convert_op.build_command(params)
        self._convert_panel.run(command, resolved)

    # ------------------------------------------------------------------
    # Merge (batch) tab
    # ------------------------------------------------------------------
    def _build_merge_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self._merge_op = MergeAudioOperation()
        self._merge_output_dir: Optional[Path] = None

        folder_row = QHBoxLayout()
        select_folder_button = QPushButton("Select Folder…")
        select_folder_button.clicked.connect(self._select_merge_folder)
        self._merge_folder_label = QLabel("No folder selected")
        self._merge_folder_label.setObjectName("mutedLabel")
        folder_row.addWidget(select_folder_button)
        folder_row.addWidget(self._merge_folder_label, stretch=1)
        layout.addLayout(folder_row)

        note = QLabel(
            "Audio files in the folder are detected and sorted naturally "
            "(1.mp3, 2.mp3, … 10.mp3 — not 1, 10, 2). Reorder manually below if needed."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        list_row = QHBoxLayout()
        self._merge_list = QListWidget()
        list_row.addWidget(self._merge_list, stretch=1)
        buttons_col = QVBoxLayout()
        up_button = QPushButton("Move Up")
        up_button.clicked.connect(self._merge_move_up)
        down_button = QPushButton("Move Down")
        down_button.clicked.connect(self._merge_move_down)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._merge_remove_selected)
        for b in (up_button, down_button, remove_button):
            buttons_col.addWidget(b)
        buttons_col.addStretch()
        list_row.addLayout(buttons_col)
        layout.addLayout(list_row)

        output_name_row = QHBoxLayout()
        output_name_row.addWidget(QLabel(t("common.output_name_label")))
        self._merge_output_name = OutputNameField()
        self._merge_output_name.changed.connect(self._refresh_merge_preview)
        output_name_row.addWidget(self._merge_output_name, stretch=1)
        layout.addLayout(output_name_row)

        self._merge_panel = RunPanel()
        self._merge_panel.run_button.clicked.connect(self._run_merge)
        self._merge_panel.job_succeeded.connect(
            lambda out: self._log_history("merge_audio", f"{self._merge_list.count()} audio files", out, "Success")
        )
        self._merge_panel.job_failed.connect(
            lambda _msg: self._log_history("merge_audio", f"{self._merge_list.count()} audio files", None, "Failed")
        )
        layout.addWidget(self._merge_panel)
        layout.addStretch()
        return widget

    def _select_merge_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder with audio files")
        if not folder:
            return
        self._merge_output_dir = Path(folder)
        self._merge_folder_label.setText(folder)
        exts = {".mp3", ".wav", ".aac", ".flac", ".opus", ".m4a"}
        files = [p for p in self._merge_output_dir.iterdir() if p.is_file() and p.suffix.lower() in exts]
        files = natural_sorted_paths(files)
        self._merge_list.clear()
        for f in files:
            self._merge_list.addItem(str(f))
        self._refresh_merge_preview()

    def _merge_move_up(self) -> None:
        row = self._merge_list.currentRow()
        if row > 0:
            item = self._merge_list.takeItem(row)
            self._merge_list.insertItem(row - 1, item)
            self._merge_list.setCurrentRow(row - 1)
        self._refresh_merge_preview()

    def _merge_move_down(self) -> None:
        row = self._merge_list.currentRow()
        if 0 <= row < self._merge_list.count() - 1:
            item = self._merge_list.takeItem(row)
            self._merge_list.insertItem(row + 1, item)
            self._merge_list.setCurrentRow(row + 1)
        self._refresh_merge_preview()

    def _merge_remove_selected(self) -> None:
        row = self._merge_list.currentRow()
        if row >= 0:
            self._merge_list.takeItem(row)
        self._refresh_merge_preview()

    def _merge_inputs(self) -> list[str]:
        return [self._merge_list.item(i).text() for i in range(self._merge_list.count())]

    def _build_merge_params(self) -> Optional[dict]:
        inputs = self._merge_inputs()
        if len(inputs) < 2 or not self._merge_output_dir:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        output = self._merge_output_dir / "merged_audio.mp3"
        output = resolve_custom_output_name(output, self._merge_output_name.value())
        list_file_path = Path(tempfile.gettempdir()) / "ffmpeg_studio_audio_merge_list.txt"
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "inputs": inputs,
            "output": str(output),
            "list_file_path": str(list_file_path),
            "overwrite": False,
        }

    def _refresh_merge_preview(self, *_args) -> None:
        params = self._build_merge_params()
        if not params:
            self._merge_panel.set_preview_command(None)
            return
        try:
            self._merge_panel.set_preview_command(self._merge_op.build_command(params))
        except ValueError as exc:
            self._merge_panel.set_preview_command([f"# Invalid configuration: {exc}"])

    def _run_merge(self) -> None:
        params = self._build_merge_params()
        if not params:
            QMessageBox.warning(self, "Merge Audio", "Select a folder with at least two audio files.")
            return
        resolved = resolve_output_path(self, Path(params["output"]), self._settings_manager.settings.overwrite_policy)
        if resolved is None:
            return
        params["output"] = str(resolved)
        params["overwrite"] = True
        command = self._merge_op.build_command(params)
        self._merge_panel.run(command, resolved)
