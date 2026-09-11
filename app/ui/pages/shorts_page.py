"""YouTube Shorts / vertical video page."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox,
    QGroupBox, QFormLayout, QMessageBox,
)

from app.core.media_probe import probe_media, ProbeError
from app.i18n.translator import t
from app.operations.shorts import ShortsOperation
from app.ui.dialogs.overwrite_dialog import resolve_output_path
from app.ui.widgets.file_drop import FileDropField
from app.ui.widgets.run_panel import RunPanel
from app.ui.widgets.output_name_field import OutputNameField
from app.utils.formatting import format_duration, format_size
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name


class ShortsPage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager=None, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._operation = ShortsOperation()
        self._input_path: Optional[Path] = None
        self._duration: Optional[float] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.shorts"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        drop = FileDropField(t("common.drop_landscape_video_here"), mode="file")
        drop.paths_selected.connect(self._on_file_selected)
        layout.addWidget(drop)

        self._info_label = QLabel("")
        self._info_label.setObjectName("mutedLabel")
        layout.addWidget(self._info_label)

        options_group = QGroupBox(t("common.options_group"))
        form = QFormLayout(options_group)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["crop", "fit", "blur", "custom"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        form.addRow("Mode:", self._mode_combo)

        mode_note = QLabel(
            "Crop fills the vertical frame by cropping the sides. Fit keeps the whole frame "
            "with black bars. Blur fills the background with a blurred, enlarged copy of the "
            "video behind the full frame."
        )
        mode_note.setObjectName("mutedLabel")
        mode_note.setWordWrap(True)
        form.addRow("", mode_note)

        self._width_spin = QSpinBox()
        self._width_spin.setRange(16, 7680)
        self._width_spin.setValue(1080)
        self._width_spin.valueChanged.connect(self._refresh_preview)
        self._height_spin = QSpinBox()
        self._height_spin.setRange(16, 7680)
        self._height_spin.setValue(1920)
        self._height_spin.valueChanged.connect(self._refresh_preview)
        custom_row = QHBoxLayout()
        custom_row.addWidget(self._width_spin)
        custom_row.addWidget(QLabel("×"))
        custom_row.addWidget(self._height_spin)
        form.addRow("Custom size:", custom_row)

        self._fps_combo = QComboBox()
        self._fps_combo.addItems(["24", "30", "60"])
        self._fps_combo.setCurrentText("30")
        self._fps_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow("FPS:", self._fps_combo)

        self._codec_combo = QComboBox()
        self._codec_combo.addItems(["h264", "h265"])
        self._codec_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow("Codec:", self._codec_combo)

        self._crf_spin = QSpinBox()
        self._crf_spin.setRange(0, 51)
        self._crf_spin.setValue(23)
        self._crf_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("CRF:", self._crf_spin)

        self._audio_codec_combo = QComboBox()
        self._audio_codec_combo.addItem(t("common.audio_reencode_option"), "aac")
        self._audio_codec_combo.addItem(t("common.audio_copy_option"), "copy")
        self._audio_codec_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow(t("common.audio_encoding_label"), self._audio_codec_combo)

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

        self._on_mode_changed(self._mode_combo.currentText())

    def _on_job_succeeded(self, output_path: Path) -> None:
        if self._history_manager and self._input_path:
            self._history_manager.add(
                operation="shorts", input_summary=str(self._input_path),
                output_path=str(output_path), status="Success",
            )
        maybe_open_output_folder(self._settings_manager, output_path)

    def _on_job_failed(self, _message: str) -> None:
        if self._history_manager and self._input_path:
            self._history_manager.add(
                operation="shorts", input_summary=str(self._input_path),
                output_path="", status="Failed",
            )

    def _on_mode_changed(self, mode: str) -> None:
        is_custom = mode == "custom"
        self._width_spin.setEnabled(is_custom)
        self._height_spin.setEnabled(is_custom)
        self._refresh_preview()

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
        output_path = self._input_path.with_name(f"{self._input_path.stem}_shorts{self._input_path.suffix}")
        output_path = resolve_custom_output_name(output_path, self._output_name_field.value())
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "input": str(self._input_path),
            "output": str(output_path),
            "mode": self._mode_combo.currentText(),
            "width": self._width_spin.value(),
            "height": self._height_spin.value(),
            "fps": int(self._fps_combo.currentText()),
            "codec": self._codec_combo.currentText(),
            "crf": self._crf_spin.value(),
            "audio_codec": self._audio_codec_combo.currentData(),
            "audio_bitrate": "192k",
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
            QMessageBox.warning(self, "Shorts", "Select a video and make sure FFmpeg is configured.")
            return
        resolved = resolve_output_path(self, Path(params["output"]), self._settings_manager.settings.overwrite_policy)
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
