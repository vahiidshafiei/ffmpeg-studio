"""Batch page: apply Compress to many files at once via JobQueue.

Scoped to Compress for now since it's the most common batch workflow (the
spec's own example is batch-compressing a folder of lecture videos). The
same JobQueue/pattern extends to other operations later — nothing here is
Compress-specific except the params dict each Job's command is built from.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QComboBox, QSpinBox, QGroupBox, QFormLayout, QFileDialog,
    QMessageBox, QProgressBar,
)

from app.i18n.translator import t
from app.models.models import Job, JobStatus
from app.operations.compress import CompressOperation
from app.core.job_queue import JobQueue
from app.core.history_manager import HistoryManager
from app.utils.os_utils import maybe_open_output_folder


class BatchPage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager: HistoryManager, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._operation = CompressOperation()
        self._queue = JobQueue(self)
        self._output_dir: Optional[Path] = None
        self._files: List[Path] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.batch"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        input_row = QHBoxLayout()
        add_files_button = QPushButton("Add Files…")
        add_files_button.clicked.connect(self._add_files)
        add_folder_button = QPushButton("Add Folder…")
        add_folder_button.clicked.connect(self._add_folder)
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self._clear_files)
        input_row.addWidget(add_files_button)
        input_row.addWidget(add_folder_button)
        input_row.addWidget(clear_button)
        input_row.addStretch()
        layout.addLayout(input_row)

        self._file_list = QListWidget()
        layout.addWidget(self._file_list)

        options_group = QGroupBox("Compression settings (applied to every file)")
        form = QFormLayout(options_group)

        self._codec_combo = QComboBox()
        self._codec_combo.addItems(["h264", "h265", "av1"])
        form.addRow("Codec:", self._codec_combo)

        self._crf_spin = QSpinBox()
        self._crf_spin.setRange(0, 51)
        self._crf_spin.setValue(23)
        form.addRow("CRF:", self._crf_spin)

        self._preset_combo = QComboBox()
        self._preset_combo.addItems(["fast", "medium", "slow"])
        self._preset_combo.setCurrentText("medium")
        form.addRow("Preset:", self._preset_combo)

        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems(["Original", "1080p", "720p", "480p"])
        form.addRow("Resolution:", self._resolution_combo)

        self._audio_mode_combo = QComboBox()
        self._audio_mode_combo.addItem(t("common.audio_copy_option"), "copy")
        self._audio_mode_combo.addItem(t("common.audio_reencode_option"), "aac")
        form.addRow(t("batch.audio_label"), self._audio_mode_combo)

        output_row = QHBoxLayout()
        self._output_label = QLabel("No output folder selected — will create '<input folder>_Compressed'")
        self._output_label.setObjectName("mutedLabel")
        output_button = QPushButton("Select Output Folder…")
        output_button.clicked.connect(self._select_output_folder)
        output_row.addWidget(self._output_label, stretch=1)
        output_row.addWidget(output_button)
        form.addRow("Output folder:", output_row)

        layout.addWidget(options_group)

        run_row = QHBoxLayout()
        self._start_button = QPushButton("Start Batch")
        self._start_button.clicked.connect(self._start_batch)
        self._cancel_button = QPushButton(t("common.cancel"))
        self._cancel_button.setObjectName("secondaryButton")
        self._cancel_button.setEnabled(False)
        self._cancel_button.clicked.connect(self._queue.cancel)
        run_row.addWidget(self._start_button)
        run_row.addWidget(self._cancel_button)
        run_row.addStretch()
        layout.addLayout(run_row)

        self._overall_progress = QProgressBar()
        self._overall_progress.setFormat("Overall: %p%")
        layout.addWidget(self._overall_progress)

        self._current_label = QLabel("")
        self._current_label.setObjectName("mutedLabel")
        layout.addWidget(self._current_label)

        self._queue.job_started.connect(self._on_job_started)
        self._queue.job_progress.connect(self._on_job_progress)
        self._queue.job_finished.connect(self._on_job_finished)
        self._queue.queue_finished.connect(self._on_queue_finished)

        layout.addStretch()

    # ------------------------------------------------------------------
    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select videos", filter="Video files (*.mp4 *.mkv *.mov *.avi *.webm);;All files (*)"
        )
        for p in paths:
            self._add_file(Path(p))

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder")
        if not folder:
            return
        exts = {".mp4", ".mkv", ".mov", ".avi", ".webm"}
        for p in sorted(Path(folder).iterdir()):
            if p.is_file() and p.suffix.lower() in exts:
                self._add_file(p)

    def _add_file(self, path: Path) -> None:
        if path in self._files:
            return
        self._files.append(path)
        item = QListWidgetItem(f"⏳ {path.name}")
        item.setData(1000, str(path))
        self._file_list.addItem(item)

    def _clear_files(self) -> None:
        self._files = []
        self._file_list.clear()

    def _select_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select output folder")
        if folder:
            self._output_dir = Path(folder)
            self._output_label.setText(folder)

    # ------------------------------------------------------------------
    def _start_batch(self) -> None:
        if not self._files:
            QMessageBox.warning(self, "Batch", "Add at least one file.")
            return
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            QMessageBox.warning(self, "Batch", "FFmpeg is not configured.")
            return

        output_dir = self._output_dir or (self._files[0].parent / f"{self._files[0].parent.name}_Compressed")
        output_dir.mkdir(parents=True, exist_ok=True)

        jobs: List[Job] = []
        resolution = self._resolution_combo.currentText()
        for path in self._files:
            output_path = output_dir / f"{path.stem}_compressed{path.suffix}"
            params = {
                "ffmpeg_path": str(location.ffmpeg_path),
                "input": str(path),
                "output": str(output_path),
                "codec": self._codec_combo.currentText(),
                "crf": self._crf_spin.value(),
                "preset": self._preset_combo.currentText(),
                "resolution": None if resolution == "Original" else resolution,
                "audio_mode": self._audio_mode_combo.currentData(),
                "overwrite": True,
            }
            try:
                command = self._operation.build_command(params)
            except ValueError as exc:
                QMessageBox.critical(self, "Invalid settings", str(exc))
                return
            jobs.append(Job(
                id=path.stem, operation_name="compress",
                input_paths=[path], output_path=output_path, command=command,
            ))

        self._queue.set_jobs(jobs)
        self._current_output_dir = output_dir
        self._overall_progress.setValue(0)
        self._start_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._queue.start()

    def _on_job_started(self, index: int) -> None:
        item = self._file_list.item(index)
        item.setText(f"▶ {self._files[index].name}")
        self._current_label.setText(f"Current: {self._files[index].name}")

    def _on_job_progress(self, index: int, state) -> None:
        if state.percent is not None:
            overall = int(((index + state.percent / 100) / len(self._files)) * 100)
            self._overall_progress.setValue(overall)

    def _on_job_finished(self, index: int, status: JobStatus) -> None:
        job = self._queue.jobs[index]
        icon = {"Success": "✓", "Failed": "✗", "Skipped": "⏭"}.get(status.value, "•")
        item = self._file_list.item(index)
        item.setText(f"{icon} {self._files[index].name} — {status.value}")
        self._history_manager.add(
            operation="compress (batch)",
            input_summary=str(self._files[index]),
            output_path=str(job.output_path),
            status=status.value,
            command=job.command,
        )

    def _on_queue_finished(self) -> None:
        self._start_button.setEnabled(True)
        self._cancel_button.setEnabled(False)
        self._overall_progress.setValue(100)
        self._current_label.setText("Batch complete.")
        if getattr(self, "_current_output_dir", None):
            maybe_open_output_folder(self._settings_manager, self._current_output_dir)
