"""Compress page: the first fully wired operation, proving the pipeline
UI -> command_builder -> command preview -> QProcess -> progress/log display.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QComboBox, QSpinBox, QSlider, QProgressBar, QPlainTextEdit, QGroupBox,
    QFormLayout, QMessageBox,
)
from PySide6.QtCore import Qt

from app.core.media_probe import probe_media, ProbeError
from app.core.process_manager import FFmpegProcess
from app.i18n.translator import t
from app.models.models import ProgressState
from app.operations.compress import CompressOperation
from app.ui.widgets.command_preview import CommandPreviewWidget
from app.ui.widgets.output_name_field import OutputNameField
from app.utils.formatting import format_duration, format_size, format_bitrate
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name


class CompressPage(QWidget):
    output_ready = Signal(Path)  # emitted with output path when a job completes successfully

    def __init__(self, ffmpeg_manager, settings_manager=None, history_manager=None, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._operation = CompressOperation()
        self._input_path: Optional[Path] = None
        self._media_duration: Optional[float] = None
        self._process: Optional[FFmpegProcess] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.compress"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # --- Input row ---
        input_row = QHBoxLayout()
        self._input_label = QLabel("No file selected")
        self._input_label.setObjectName("mutedLabel")
        select_button = QPushButton("Select Video…")
        select_button.clicked.connect(self._select_input)
        input_row.addWidget(select_button)
        input_row.addWidget(self._input_label, stretch=1)
        layout.addLayout(input_row)

        self._info_label = QLabel("")
        self._info_label.setObjectName("mutedLabel")
        layout.addWidget(self._info_label)

        # --- Options ---
        options_group = QGroupBox(t("common.options_group"))
        form = QFormLayout(options_group)

        self._codec_combo = QComboBox()
        self._codec_combo.addItems(["h264", "h265", "av1"])
        form.addRow("Codec:", self._codec_combo)

        crf_row = QHBoxLayout()
        self._crf_slider = QSlider(Qt.Orientation.Horizontal)
        self._crf_slider.setRange(0, 51)
        self._crf_slider.setValue(23)
        self._crf_spin = QSpinBox()
        self._crf_spin.setRange(0, 51)
        self._crf_spin.setValue(23)
        self._crf_slider.valueChanged.connect(self._crf_spin.setValue)
        self._crf_spin.valueChanged.connect(self._crf_slider.setValue)
        crf_row.addWidget(self._crf_slider)
        crf_row.addWidget(self._crf_spin)
        form.addRow("CRF (lower = higher quality, larger file):", crf_row)

        self._preset_combo = QComboBox()
        self._preset_combo.addItems([
            "ultrafast", "superfast", "veryfast", "faster", "fast",
            "medium", "slow", "slower", "veryslow",
        ])
        self._preset_combo.setCurrentText("medium")
        form.addRow("Preset:", self._preset_combo)

        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems(["Original", "2160p", "1440p", "1080p", "720p", "480p"])
        form.addRow("Resolution:", self._resolution_combo)

        self._audio_combo = QComboBox()
        self._audio_combo.addItems(["copy", "aac", "mp3", "opus"])
        form.addRow("Audio:", self._audio_combo)

        self._audio_bitrate_combo = QComboBox()
        self._audio_bitrate_combo.addItems(["64k", "96k", "128k", "160k", "192k", "256k", "320k"])
        self._audio_bitrate_combo.setCurrentText("192k")
        form.addRow("Audio bitrate:", self._audio_bitrate_combo)

        self._output_name_field = OutputNameField()
        self._output_name_field.changed.connect(self._refresh_preview)
        form.addRow(t("common.output_name_label"), self._output_name_field)

        layout.addWidget(options_group)

        for widget in (
            self._codec_combo, self._crf_spin, self._preset_combo,
            self._resolution_combo, self._audio_combo, self._audio_bitrate_combo,
        ):
            if hasattr(widget, "currentTextChanged"):
                widget.currentTextChanged.connect(self._refresh_preview)
            if hasattr(widget, "valueChanged"):
                widget.valueChanged.connect(self._refresh_preview)

        # --- Command preview ---
        self._preview = CommandPreviewWidget()
        layout.addWidget(self._preview)

        # --- Run controls ---
        run_row = QHBoxLayout()
        self._run_button = QPushButton(t("common.run"))
        self._run_button.clicked.connect(self._run)
        self._cancel_button = QPushButton(t("common.cancel"))
        self._cancel_button.setObjectName("secondaryButton")
        self._cancel_button.clicked.connect(self._cancel)
        self._cancel_button.setEnabled(False)
        run_row.addWidget(self._run_button)
        run_row.addWidget(self._cancel_button)
        run_row.addStretch()
        layout.addLayout(run_row)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setObjectName("mutedLabel")
        layout.addWidget(self._status_label)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumHeight(120)
        self._log_view.setPlaceholderText(t("common.log_placeholder"))
        layout.addWidget(self._log_view)

        layout.addStretch()

    # ------------------------------------------------------------------
    def _select_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select video", filter="Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*)"
        )
        if not path:
            return
        self._input_path = Path(path)
        self._input_label.setText(self._input_path.name)
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
            self._media_duration = None
            return
        self._media_duration = info.duration_seconds
        parts = [f"Duration: {format_duration(info.duration_seconds)}", f"Size: {format_size(info.size_bytes)}"]
        if info.video:
            parts.append(f"{info.video.width}×{info.video.height} · {info.video.codec} · {info.video.fps:.0f} fps")
        if info.audio:
            parts.append(f"Audio: {info.audio.codec} · {format_bitrate(info.audio.bitrate_kbps)}")
        self._info_label.setText(" | ".join(parts))

    def _build_params(self) -> Optional[dict]:
        if not self._input_path:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        resolution = self._resolution_combo.currentText()
        output_path = self._operation.default_output_name(
            self._input_path, "compressed", self._input_path.suffix
        )
        output_path = resolve_custom_output_name(output_path, self._output_name_field.value())
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "input": str(self._input_path),
            "output": str(output_path),
            "codec": self._codec_combo.currentText(),
            "crf": self._crf_spin.value(),
            "preset": self._preset_combo.currentText(),
            "resolution": None if resolution == "Original" else resolution,
            "audio_mode": self._audio_combo.currentText(),
            "audio_bitrate": self._audio_bitrate_combo.currentText(),
            "overwrite": False,
        }

    def _refresh_preview(self, *_args) -> None:
        params = self._build_params()
        if not params:
            self._preview.clear()
            return
        try:
            command = self._operation.build_command(params)
            self._preview.set_command(command)
        except ValueError as exc:
            self._preview.set_command([f"# Invalid configuration: {exc}"])

    # ------------------------------------------------------------------
    def _run(self) -> None:
        params = self._build_params()
        if not params:
            QMessageBox.warning(self, "Compress", "Select a video and make sure FFmpeg is configured first.")
            return

        output_path = Path(params["output"])
        if output_path.exists():
            reply = QMessageBox.question(
                self, "Output already exists",
                f"{output_path.name} already exists. Replace it?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            params["overwrite"] = True

        try:
            command = self._operation.build_command(params)
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid settings", str(exc))
            return

        self._run_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._progress_bar.setValue(0)
        self._log_view.clear()
        self._status_label.setText("Starting…")

        self._process = FFmpegProcess(
            ffmpeg_path=command[0],
            args=command[1:],
            total_duration_seconds=self._media_duration,
        )
        self._process.progress.connect(self._on_progress)
        self._process.log_line.connect(self._log_view.appendPlainText)
        self._process.finished.connect(lambda code: self._on_finished(code, output_path))
        self._process.failed_to_start.connect(self._on_failed_to_start)
        self._process.start()

    def _cancel(self) -> None:
        if self._process:
            self._process.cancel()
        self._status_label.setText("Cancelled.")
        self._reset_run_state()

    def _on_progress(self, state: ProgressState) -> None:
        if state.percent is not None:
            self._progress_bar.setValue(int(state.percent))
        speed = f"{state.speed:.1f}x" if state.speed else "—"
        eta = format_duration(state.eta_seconds) if state.eta_seconds else "—"
        self._status_label.setText(
            f"{t('common.time_label')}: {format_duration(state.out_time_seconds)}  "
            f"{t('common.speed_label')}: {speed}  {t('common.eta_label')}: {eta}"
        )

    def _on_finished(self, exit_code: int, output_path: Path) -> None:
        if exit_code == 0:
            self._progress_bar.setValue(100)
            self._status_label.setText(f"Done — saved to {output_path.name}")
            self.output_ready.emit(output_path)
            if self._history_manager and self._input_path:
                self._history_manager.add(
                    operation="compress", input_summary=str(self._input_path),
                    output_path=str(output_path), status="Success",
                )
            maybe_open_output_folder(self._settings_manager, output_path)
        else:
            log_tail = "\n".join((self._process.full_log if self._process else [])[-5:])
            self._status_label.setText("FFmpeg reported an error — see log below.")
            QMessageBox.critical(
                self, "Compression failed",
                f"FFmpeg exited with code {exit_code}.\n\n{log_tail or 'No log output captured.'}",
            )
            if self._history_manager and self._input_path:
                self._history_manager.add(
                    operation="compress", input_summary=str(self._input_path),
                    output_path="", status="Failed",
                )
        self._reset_run_state()

    def _on_failed_to_start(self, message: str) -> None:
        QMessageBox.critical(self, "Could not start FFmpeg", message)
        self._status_label.setText("Failed to start.")
        self._reset_run_state()

    def _reset_run_state(self) -> None:
        self._run_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
