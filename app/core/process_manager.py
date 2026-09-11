"""Runs ffmpeg asynchronously via QProcess so the GUI never blocks.

QProcess (rather than raw subprocess + threading) is used because it
integrates natively with the Qt event loop: readyReadStandardOutput /
finished signals fire on the main thread without manual polling, which is
the simplest way to keep this both responsive and easy to reason about.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QObject, QProcess, Signal

from app.core.progress_parser import ProgressParser
from app.models.models import ProgressState


class FFmpegProcess(QObject):
    """Wraps a single ffmpeg invocation."""

    started = Signal()
    progress = Signal(ProgressState)
    log_line = Signal(str)          # raw stderr line (ffmpeg's human log)
    finished = Signal(int)          # exit code
    failed_to_start = Signal(str)

    def __init__(
        self,
        ffmpeg_path: str,
        args: List[str],
        total_duration_seconds: Optional[float] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._ffmpeg_path = ffmpeg_path
        # args here should NOT include the ffmpeg path itself (see start()).
        self._args = list(args)
        self._parser = ProgressParser(total_duration_seconds)
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.started.connect(self.started.emit)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)
        self._full_log: List[str] = []

    @property
    def full_log(self) -> List[str]:
        return self._full_log

    def start(self) -> None:
        # -progress pipe:1 writes machine-readable key=value progress to
        # stdout; -nostats suppresses ffmpeg's default human progress spam on
        # stderr so stderr is reserved for real log/error output.
        full_args = ["-nostats", "-progress", "pipe:1", *self._args]
        self._process.start(self._ffmpeg_path, full_args)

    def cancel(self) -> None:
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.terminate()
            if not self._process.waitForFinished(3000):
                self._process.kill()

    def _on_stdout(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            state = self._parser.feed(line)
            if state is not None:
                self.progress.emit(state)

    def _on_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        for line in data.splitlines():
            if line.strip():
                self._full_log.append(line)
                self.log_line.emit(line)

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        self.finished.emit(exit_code)

    def _on_error(self, _error) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            self.failed_to_start.emit(self._process.errorString())
