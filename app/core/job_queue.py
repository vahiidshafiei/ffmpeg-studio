"""Runs a list of Jobs sequentially, one FFmpegProcess at a time.

Used by the Batch page: one operation applied to many files becomes one Job
per file, and JobQueue runs them in order, emitting signals the page uses to
update an overall progress bar and a per-file status list. A failure on one
job does not stop the rest of the queue (per spec: "do not crash the whole
batch because one file fails").
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QObject, Signal

from app.core.process_manager import FFmpegProcess
from app.models.models import Job, JobStatus, ProgressState


class JobQueue(QObject):
    job_started = Signal(int)              # index into jobs
    job_progress = Signal(int, ProgressState)
    job_finished = Signal(int, JobStatus)
    queue_finished = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.jobs: List[Job] = []
        self._current_index = -1
        self._current_process: Optional[FFmpegProcess] = None
        self._cancelled = False

    def set_jobs(self, jobs: List[Job]) -> None:
        self.jobs = jobs
        self._current_index = -1
        self._cancelled = False

    def start(self) -> None:
        self._cancelled = False
        self._run_next()

    def cancel(self) -> None:
        self._cancelled = True
        if self._current_process:
            self._current_process.cancel()

    def retry(self, index: int) -> None:
        if 0 <= index < len(self.jobs):
            self.jobs[index].status = JobStatus.QUEUED
            self.jobs[index].error_message = None
            if self._current_index == -1 or self._current_index >= len(self.jobs):
                self._run_next()

    def _run_next(self) -> None:
        self._current_index += 1
        if self._cancelled or self._current_index >= len(self.jobs):
            self.queue_finished.emit()
            return

        job = self.jobs[self._current_index]
        if job.status == JobStatus.SKIPPED:
            self._run_next()
            return

        job.status = JobStatus.RUNNING
        self.job_started.emit(self._current_index)

        self._current_process = FFmpegProcess(
            ffmpeg_path=job.command[0],
            args=job.command[1:],
            total_duration_seconds=job.duration_hint_seconds,
        )
        index = self._current_index
        self._current_process.progress.connect(lambda state: self.job_progress.emit(index, state))
        self._current_process.log_line.connect(lambda line: job.log.append(line))
        self._current_process.finished.connect(lambda code: self._on_job_finished(index, code))
        self._current_process.failed_to_start.connect(lambda msg: self._on_job_failed(index, msg))
        self._current_process.start()

    def _on_job_finished(self, index: int, exit_code: int) -> None:
        job = self.jobs[index]
        if exit_code == 0:
            job.status = JobStatus.SUCCESS
        else:
            job.status = JobStatus.FAILED
            job.error_message = "\n".join(job.log[-5:]) or f"FFmpeg exited with code {exit_code}"
        self.job_finished.emit(index, job.status)
        self._run_next()

    def _on_job_failed(self, index: int, message: str) -> None:
        job = self.jobs[index]
        job.status = JobStatus.FAILED
        job.error_message = message
        self.job_finished.emit(index, job.status)
        self._run_next()
