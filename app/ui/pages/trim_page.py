"""Trim page: cut a clip by start/end time, fast (stream copy) or accurate (re-encode)."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QGroupBox,
    QFormLayout, QMessageBox,
)

from app.core.media_probe import probe_media, ProbeError
from app.i18n.translator import t
from app.operations.trim import TrimOperation
from app.ui.dialogs.overwrite_dialog import resolve_output_path
from app.ui.widgets.file_drop import FileDropField
from app.ui.widgets.run_panel import RunPanel
from app.ui.widgets.output_name_field import OutputNameField
from app.utils.formatting import format_duration, format_size, parse_timecode
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name


class TrimPage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager=None, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._operation = TrimOperation()
        self._input_path: Optional[Path] = None
        self._duration: Optional[float] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.trim"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self._drop = FileDropField(t("common.drop_video_here"), mode="file")
        self._drop.paths_selected.connect(self._on_file_selected)
        layout.addWidget(self._drop)

        self._info_label = QLabel("")
        self._info_label.setObjectName("mutedLabel")
        layout.addWidget(self._info_label)

        options_group = QGroupBox("Trim range")
        form = QFormLayout(options_group)

        self._start_edit = QLineEdit("00:00:00")
        form.addRow("Start (HH:MM:SS):", self._start_edit)
        self._end_edit = QLineEdit("")
        self._end_edit.setPlaceholderText("HH:MM:SS (leave blank to use duration below)")
        form.addRow("End:", self._end_edit)
        self._duration_edit = QLineEdit("")
        self._duration_edit.setPlaceholderText("HH:MM:SS (used if End is blank)")
        form.addRow("Duration:", self._duration_edit)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["fast", "accurate"])
        form.addRow("Mode:", self._mode_combo)

        mode_note = QLabel(
            "Fast mode copies streams without re-encoding — very quick, but the cut can only "
            "land on a keyframe. Accurate mode re-encodes so the cut lands exactly on your "
            "chosen time, at the cost of encoding time."
        )
        mode_note.setObjectName("mutedLabel")
        mode_note.setWordWrap(True)
        form.addRow("", mode_note)

        self._output_name_field = OutputNameField()
        self._output_name_field.changed.connect(self._refresh_preview)
        form.addRow(t("common.output_name_label"), self._output_name_field)

        layout.addWidget(options_group)

        for widget in (self._start_edit, self._end_edit, self._duration_edit):
            widget.textChanged.connect(self._refresh_preview)
        self._mode_combo.currentTextChanged.connect(self._refresh_preview)

        self._run_panel = RunPanel()
        self._run_panel.run_button.clicked.connect(self._run)
        self._run_panel.job_succeeded.connect(self._on_job_succeeded)
        self._run_panel.job_failed.connect(self._on_job_failed)
        layout.addWidget(self._run_panel)
        layout.addStretch()

    def _on_job_succeeded(self, output_path: Path) -> None:
        if self._history_manager and self._input_path:
            self._history_manager.add(
                operation="trim", input_summary=str(self._input_path),
                output_path=str(output_path), status="Success",
            )
        maybe_open_output_folder(self._settings_manager, output_path)

    def _on_job_failed(self, _message: str) -> None:
        if self._history_manager and self._input_path:
            self._history_manager.add(
                operation="trim", input_summary=str(self._input_path),
                output_path="", status="Failed",
            )

    def _on_file_selected(self, paths) -> None:
        self._input_path = paths[0]
        self._probe_input()
        self._refresh_preview()

    def _probe_input(self) -> None:
        location = self._ffmpeg_manager.location
        if not location.is_valid or not self._input_path:
            return
        try:
            info = probe_media(location.ffprobe_path, self._input_path)
        except ProbeError as exc:
            self._info_label.setText(f"Could not read media info: {exc}")
            self._duration = None
            return
        self._duration = info.duration_seconds
        self._info_label.setText(
            f"Duration: {format_duration(info.duration_seconds)} | Size: {format_size(info.size_bytes)}"
        )

    def _build_params(self) -> Optional[dict]:
        if not self._input_path:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        output_path = self._operation.default_output_name(
            self._input_path, "trimmed", self._input_path.suffix
        )
        output_path = resolve_custom_output_name(output_path, self._output_name_field.value())
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "input": str(self._input_path),
            "output": str(output_path),
            "start": self._start_edit.text().strip(),
            "end": self._end_edit.text().strip() or None,
            "duration": self._duration_edit.text().strip() or None,
            "mode": self._mode_combo.currentText(),
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
            QMessageBox.warning(self, "Trim", "Select a video and make sure FFmpeg is configured first.")
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

        # Progress percent for a trim should be measured against the clip's
        # own length, not the source video's — estimate it from start/end/duration.
        clip_duration = self._estimate_clip_duration(params)
        self._run_panel.run(command, resolved, total_duration_seconds=clip_duration)

    def _estimate_clip_duration(self, params: dict) -> Optional[float]:
        try:
            if params["duration"]:
                return parse_timecode(params["duration"])
            if params["end"]:
                return parse_timecode(params["end"]) - parse_timecode(params["start"])
        except ValueError:
            return None
        return None
