"""Convert page: container/codec conversion."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox, QFormLayout,
    QMessageBox,
)

from app.core.media_probe import probe_media, ProbeError
from app.i18n.translator import t
from app.operations.convert import ConvertOperation
from app.ui.dialogs.overwrite_dialog import resolve_output_path
from app.ui.widgets.file_drop import FileDropField
from app.ui.widgets.run_panel import RunPanel
from app.ui.widgets.output_name_field import OutputNameField
from app.utils.formatting import format_duration, format_size
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name

_FORMATS = {"MP4": ".mp4", "MKV": ".mkv", "MOV": ".mov", "AVI": ".avi", "WebM": ".webm"}


class ConvertPage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager=None, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._operation = ConvertOperation()
        self._input_path: Optional[Path] = None
        self._duration: Optional[float] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.convert"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        self._drop = FileDropField(
            "Drop a video file here",
            mode="file",
            name_filter="Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*)",
        )
        self._drop.paths_selected.connect(self._on_file_selected)
        layout.addWidget(self._drop)

        self._info_label = QLabel("")
        self._info_label.setObjectName("mutedLabel")
        layout.addWidget(self._info_label)

        options_group = QGroupBox(t("common.options_group"))
        form = QFormLayout(options_group)

        self._format_combo = QComboBox()
        self._format_combo.addItems(list(_FORMATS))
        form.addRow("Output format:", self._format_combo)

        self._video_codec_combo = QComboBox()
        self._video_codec_combo.addItems(["h264", "h265", "vp9", "av1", "copy"])
        form.addRow("Video codec:", self._video_codec_combo)

        self._audio_codec_combo = QComboBox()
        self._audio_codec_combo.addItems(["aac", "mp3", "opus", "flac", "copy"])
        form.addRow("Audio codec:", self._audio_codec_combo)

        self._quality_combo = QComboBox()
        self._quality_combo.addItems(["Very High", "High", "Medium", "Low"])
        self._quality_combo.setCurrentText("Medium")
        form.addRow("Quality:", self._quality_combo)

        self._preset_combo = QComboBox()
        self._preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow",
        ])
        self._preset_combo.setCurrentText("medium")
        form.addRow("Encoding preset:", self._preset_combo)

        self._output_name_field = OutputNameField()
        self._output_name_field.changed.connect(self._refresh_preview)
        form.addRow(t("common.output_name_label"), self._output_name_field)

        layout.addWidget(options_group)

        for widget in (
            self._format_combo, self._video_codec_combo, self._audio_codec_combo,
            self._quality_combo, self._preset_combo,
        ):
            widget.currentTextChanged.connect(self._refresh_preview)

        self._run_panel = RunPanel()
        self._run_panel.run_button.clicked.connect(self._run)
        self._run_panel.job_succeeded.connect(self._on_job_succeeded)
        self._run_panel.job_failed.connect(self._on_job_failed)
        layout.addWidget(self._run_panel)
        layout.addStretch()

    def _on_job_succeeded(self, output_path: Path) -> None:
        if self._history_manager and self._input_path:
            self._history_manager.add(
                operation="convert", input_summary=str(self._input_path),
                output_path=str(output_path), status="Success",
            )
        maybe_open_output_folder(self._settings_manager, output_path)

    def _on_job_failed(self, _message: str) -> None:
        if self._history_manager and self._input_path:
            self._history_manager.add(
                operation="convert", input_summary=str(self._input_path),
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
        parts = [f"Duration: {format_duration(info.duration_seconds)}", f"Size: {format_size(info.size_bytes)}"]
        if info.video:
            parts.append(f"{info.video.width}×{info.video.height} · {info.video.codec}")
        self._info_label.setText(" | ".join(parts))

    def _build_params(self) -> Optional[dict]:
        if not self._input_path:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        extension = _FORMATS[self._format_combo.currentText()]
        output_path = self._input_path.with_name(f"{self._input_path.stem}_converted{extension}")
        output_path = resolve_custom_output_name(output_path, self._output_name_field.value())
        quality_map = {"Very High": "very_high", "High": "high", "Medium": "medium", "Low": "low"}
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "input": str(self._input_path),
            "output": str(output_path),
            "video_codec": self._video_codec_combo.currentText(),
            "audio_codec": self._audio_codec_combo.currentText(),
            "quality": quality_map[self._quality_combo.currentText()],
            "preset": self._preset_combo.currentText(),
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
            QMessageBox.warning(self, "Convert", "Select a video and make sure FFmpeg is configured first.")
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

        self._run_panel.run(command, resolved, total_duration_seconds=self._duration)
