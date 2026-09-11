"""The run/cancel/progress/log block shared by every operation page.

Each page builds its own input + options UI, then embeds one of these to get
command preview, async execution, progress display, and error handling for
free — this is what keeps process/progress wiring in one place instead of
copy-pasted across compress/convert/trim/merge/etc.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QProgressBar, QLabel,
    QPlainTextEdit, QMessageBox,
)

from app.core.process_manager import FFmpegProcess
from app.i18n.translator import t
from app.models.models import ProgressState
from app.ui.widgets.command_preview import CommandPreviewWidget
from app.utils.formatting import format_duration


class RunPanel(QWidget):
    """command preview + Run/Cancel + progress bar + status + log."""

    job_succeeded = Signal(Path)   # emitted with the output path on success
    job_failed = Signal(str)       # emitted with an error summary on failure

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[FFmpegProcess] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.preview = CommandPreviewWidget()
        layout.addWidget(self.preview)

        run_row = QHBoxLayout()
        self.run_button = QPushButton(t("common.run"))
        self.cancel_button = QPushButton(t("common.cancel"))
        self.cancel_button.setObjectName("secondaryButton")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        run_row.addWidget(self.run_button)
        run_row.addWidget(self.cancel_button)
        run_row.addStretch()
        layout.addLayout(run_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedLabel")
        layout.addWidget(self.status_label)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(110)
        self.log_view.setPlaceholderText(t("common.log_placeholder"))
        layout.addWidget(self.log_view)

    def set_preview_command(self, command: Optional[List[str]]) -> None:
        if not command:
            self.preview.clear()
        else:
            self.preview.set_command(command)

    def run(
        self,
        command: List[str],
        output_path: Path,
        total_duration_seconds: Optional[float] = None,
    ) -> None:
        """Start executing `command`. output_path is only used for the success message."""
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_view.clear()
        self.status_label.setText("Starting…")

        self._process = FFmpegProcess(
            ffmpeg_path=command[0],
            args=command[1:],
            total_duration_seconds=total_duration_seconds,
        )
        self._process.progress.connect(self._on_progress)
        self._process.log_line.connect(self.log_view.appendPlainText)
        self._process.finished.connect(lambda code: self._on_finished(code, output_path))
        self._process.failed_to_start.connect(self._on_failed_to_start)
        self._process.start()

    def _cancel(self) -> None:
        if self._process:
            self._process.cancel()
        self.status_label.setText("Cancelled.")
        self._reset()

    def _on_progress(self, state: ProgressState) -> None:
        if state.percent is not None:
            self.progress_bar.setValue(int(state.percent))
        speed = f"{state.speed:.1f}x" if state.speed else "—"
        eta = format_duration(state.eta_seconds) if state.eta_seconds else "—"
        self.status_label.setText(
            f"{t('common.time_label')}: {format_duration(state.out_time_seconds)}  "
            f"{t('common.speed_label')}: {speed}  {t('common.eta_label')}: {eta}"
        )

    def _on_finished(self, exit_code: int, output_path: Path) -> None:
        if exit_code == 0:
            self.progress_bar.setValue(100)
            self.status_label.setText(f"Done — saved to {output_path.name}")
            self.job_succeeded.emit(output_path)
        else:
            log_tail = "\n".join((self._process.full_log if self._process else [])[-6:])
            self.status_label.setText("FFmpeg reported an error — see log below.")
            message = f"FFmpeg exited with code {exit_code}.\n\n{log_tail or 'No log output captured.'}"
            QMessageBox.critical(self, "Operation failed", message)
            self.job_failed.emit(message)
        self._reset()

    def _on_failed_to_start(self, message: str) -> None:
        QMessageBox.critical(self, "Could not start FFmpeg", message)
        self.status_label.setText("Failed to start.")
        self.job_failed.emit(message)
        self._reset()

    def _reset(self) -> None:
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
