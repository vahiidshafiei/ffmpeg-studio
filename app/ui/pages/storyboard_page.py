"""Storyboard page — the "combine audios and images with explicit per-image
timing" workflow:

1. Add audios (in the order they'll eventually be merged).
2. Select an audio on the left, add images to it on the right, and set each
   image's Start/End time directly in the table. Different audios can have
   different numbers of images (1, 2, however many) — nothing here assumes
   a fixed ratio.
3. "Generate Videos" renders one video per audio (image sequence + that
   audio's track) via a JobQueue, so one bad audio doesn't stop the rest.
4. Once videos exist, reorder them in the "Final merge order" list (independent
   from the audio list order, in case the merge order should differ) and
   "Merge into Final Video" concatenates them.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox, QSpinBox,
    QGroupBox, QFormLayout, QMessageBox, QFileDialog, QProgressBar, QSplitter,
)

from app.core.media_probe import probe_media, ProbeError
from app.i18n.translator import t
from app.core.job_queue import JobQueue
from app.core.history_manager import HistoryManager
from app.models.models import Job, JobStatus
from app.operations.storyboard import StoryboardVideoOperation
from app.operations.merge import MergeOperation
from app.ui.widgets.output_name_field import OutputNameField
from app.ui.widgets.run_panel import RunPanel
from app.ui.dialogs.overwrite_dialog import resolve_output_path
from app.utils.formatting import format_duration
from app.utils.natural_sort import natural_sorted_paths
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name

_RESOLUTIONS = {
    "1920×1080 (landscape)": (1920, 1080),
    "1080×1920 (portrait)": (1080, 1920),
    "1280×720": (1280, 720),
}

_START_COL, _END_COL, _DURATION_COL = 1, 2, 3


class StoryboardPage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager: HistoryManager, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._storyboard_op = StoryboardVideoOperation()
        self._merge_op = MergeOperation()
        self._queue = JobQueue(self)

        self._audios: List[Path] = []
        self._audio_durations: Dict[str, Optional[float]] = {}
        # audio path (str) -> list of {"image": str, "start": float, "end": float}
        self._assignments: Dict[str, List[dict]] = {}
        self._generated_videos: Dict[str, Path] = {}  # audio path (str) -> output video path
        self._output_dir: Optional[Path] = None
        self._current_audio: Optional[str] = None
        self._updating_table = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.storyboard"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Add audios, then for each audio add images and set exactly when each one "
            "appears. Different audios can have different numbers of images."
        )
        subtitle.setObjectName("mutedLabel")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_audio_column())
        splitter.addWidget(self._build_image_column())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        layout.addWidget(self._build_generation_section())
        layout.addWidget(self._build_merge_section())

    # ------------------------------------------------------------------
    # Left column: audios
    # ------------------------------------------------------------------
    def _build_audio_column(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(QLabel("Audios (merge order by default)"))

        self._audio_list = QListWidget()
        self._audio_list.currentRowChanged.connect(self._on_audio_selected)
        layout.addWidget(self._audio_list)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("Add…")
        add_button.clicked.connect(self._add_audios)
        sort_button = QPushButton("Natural Sort")
        sort_button.clicked.connect(self._natural_sort_audios)
        up_button = QPushButton("↑")
        up_button.clicked.connect(lambda: self._move_audio(-1))
        down_button = QPushButton("↓")
        down_button.clicked.connect(lambda: self._move_audio(1))
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._remove_audio)
        for b in (add_button, sort_button, up_button, down_button, remove_button):
            buttons_row.addWidget(b)
        layout.addLayout(buttons_row)

        return widget

    def _add_audios(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select audio files", filter="Audio files (*.mp3 *.wav *.aac *.flac *.opus *.m4a);;All files (*)"
        )
        if not paths:
            return
        location = self._ffmpeg_manager.location
        for p in paths:
            path = Path(p)
            if str(path) in self._assignments:
                continue
            self._audios.append(path)
            self._assignments[str(path)] = []
            duration = None
            if location.is_valid:
                try:
                    duration = probe_media(location.ffprobe_path, path).duration_seconds
                except ProbeError:
                    duration = None
            self._audio_durations[str(path)] = duration
        self._refresh_audio_list()

    def _natural_sort_audios(self) -> None:
        self._audios = natural_sorted_paths(self._audios)
        self._refresh_audio_list()

    def _move_audio(self, delta: int) -> None:
        row = self._audio_list.currentRow()
        new_row = row + delta
        if row < 0 or not (0 <= new_row < len(self._audios)):
            return
        self._audios[row], self._audios[new_row] = self._audios[new_row], self._audios[row]
        self._refresh_audio_list()
        self._audio_list.setCurrentRow(new_row)

    def _remove_audio(self) -> None:
        row = self._audio_list.currentRow()
        if row < 0:
            return
        path = self._audios.pop(row)
        self._assignments.pop(str(path), None)
        self._audio_durations.pop(str(path), None)
        self._generated_videos.pop(str(path), None)
        self._refresh_audio_list()
        self._refresh_merge_list()

    def _refresh_audio_list(self) -> None:
        self._audio_list.clear()
        for path in self._audios:
            duration = self._audio_durations.get(str(path))
            n_images = len(self._assignments.get(str(path), []))
            duration_text = format_duration(duration) if duration else "unknown"
            has_video = "✓ " if str(path) in self._generated_videos else ""
            self._audio_list.addItem(f"{has_video}{path.name}  ({duration_text}, {n_images} image(s))")

    def _on_audio_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._audios):
            self._current_audio = None
            self._image_group.setEnabled(False)
            self._table.setRowCount(0)
            return
        self._image_group.setEnabled(True)
        self._current_audio = str(self._audios[row])
        duration = self._audio_durations.get(self._current_audio)
        self._selected_audio_label.setText(
            f"Editing: {self._audios[row].name} — duration {format_duration(duration) if duration else 'unknown'}"
        )
        self._reload_table()

    # ------------------------------------------------------------------
    # Right column: images + timing table for the selected audio
    # ------------------------------------------------------------------
    def _build_image_column(self) -> QWidget:
        self._image_group = QWidget()
        self._image_group.setEnabled(False)
        layout = QVBoxLayout(self._image_group)
        layout.setContentsMargins(0, 0, 0, 0)

        self._selected_audio_label = QLabel("Select an audio on the left to assign images.")
        self._selected_audio_label.setObjectName("sectionLabel")
        self._selected_audio_label.setWordWrap(True)
        layout.addWidget(self._selected_audio_label)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Image", "Start (s)", "End (s)", "Duration (s)"])
        self._table.itemChanged.connect(self._on_table_item_changed)
        layout.addWidget(self._table)

        table_buttons = QHBoxLayout()
        add_image_button = QPushButton("Add Image(s)…")
        add_image_button.clicked.connect(self._add_images_to_current_audio)
        autofill_button = QPushButton("Auto-Fill to Audio End")
        autofill_button.clicked.connect(self._autofill_last_end)
        up_button = QPushButton("↑")
        up_button.clicked.connect(lambda: self._move_table_row(-1))
        down_button = QPushButton("↓")
        down_button.clicked.connect(lambda: self._move_table_row(1))
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._remove_table_row)
        for b in (add_image_button, autofill_button, up_button, down_button, remove_button):
            table_buttons.addWidget(b)
        layout.addLayout(table_buttons)

        return self._image_group

    def _add_images_to_current_audio(self) -> None:
        if not self._current_audio:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select images", filter="Images (*.jpg *.jpeg *.png *.webp);;All files (*)"
        )
        if not paths:
            return
        rows = self._assignments[self._current_audio]
        cursor = rows[-1]["end"] if rows else 0.0
        for p in paths:
            start = cursor
            end = cursor + 5.0  # default 5s per new image; user edits as needed
            rows.append({"image": p, "start": start, "end": end})
            cursor = end
        self._reload_table()
        self._refresh_audio_list()

    def _reload_table(self) -> None:
        self._updating_table = True
        self._table.setRowCount(0)
        if self._current_audio:
            for row in self._assignments[self._current_audio]:
                self._append_table_row(row)
        self._updating_table = False

    def _append_table_row(self, row: dict) -> None:
        r = self._table.rowCount()
        self._table.insertRow(r)
        name_item = QTableWidgetItem(Path(row["image"]).name)
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(r, 0, name_item)
        self._table.setItem(r, _START_COL, QTableWidgetItem(f"{row['start']:.2f}"))
        self._table.setItem(r, _END_COL, QTableWidgetItem(f"{row['end']:.2f}"))
        duration_item = QTableWidgetItem(f"{row['end'] - row['start']:.2f}")
        duration_item.setFlags(duration_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self._table.setItem(r, _DURATION_COL, duration_item)

    def _on_table_item_changed(self, item: QTableWidgetItem) -> None:
        if self._updating_table or not self._current_audio:
            return
        row_index = item.row()
        col = item.column()
        if col not in (_START_COL, _END_COL):
            return
        rows = self._assignments[self._current_audio]
        if row_index >= len(rows):
            return
        try:
            value = float(item.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid value", "Start/End must be numbers (seconds).")
            self._reload_table()
            return
        key = "start" if col == _START_COL else "end"
        rows[row_index][key] = value
        self._updating_table = True
        duration_item = self._table.item(row_index, _DURATION_COL)
        duration_item.setText(f"{rows[row_index]['end'] - rows[row_index]['start']:.2f}")
        self._updating_table = False

    def _move_table_row(self, delta: int) -> None:
        if not self._current_audio:
            return
        rows = self._assignments[self._current_audio]
        row = self._table.currentRow()
        new_row = row + delta
        if row < 0 or not (0 <= new_row < len(rows)):
            return
        rows[row], rows[new_row] = rows[new_row], rows[row]
        self._reload_table()
        self._table.setCurrentCell(new_row, 0)

    def _remove_table_row(self) -> None:
        if not self._current_audio:
            return
        row = self._table.currentRow()
        rows = self._assignments[self._current_audio]
        if 0 <= row < len(rows):
            rows.pop(row)
            self._reload_table()
            self._refresh_audio_list()

    def _autofill_last_end(self) -> None:
        if not self._current_audio:
            return
        rows = self._assignments[self._current_audio]
        duration = self._audio_durations.get(self._current_audio)
        if not rows or not duration:
            QMessageBox.information(
                self, "Auto-Fill",
                "Add at least one image and make sure the audio's duration was detected."
            )
            return
        rows[-1]["end"] = duration
        self._reload_table()

    # ------------------------------------------------------------------
    # Generation section: shared render settings + Generate Videos
    # ------------------------------------------------------------------
    def _build_generation_section(self) -> QWidget:
        group = QGroupBox("Video settings (applied to every generated video)")
        outer = QVBoxLayout(group)
        form = QFormLayout()

        self._fps_combo = QComboBox()
        self._fps_combo.addItems(["24", "25", "30", "50", "60"])
        self._fps_combo.setCurrentText("30")
        form.addRow("FPS:", self._fps_combo)

        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems(list(_RESOLUTIONS))
        form.addRow("Resolution:", self._resolution_combo)

        self._fit_combo = QComboBox()
        self._fit_combo.addItems(["fit", "crop", "stretch", "pad"])
        form.addRow("Fit mode:", self._fit_combo)

        self._audio_codec_combo = QComboBox()
        self._audio_codec_combo.addItem(t("common.audio_reencode_option"), "aac")
        self._audio_codec_combo.addItem(t("common.audio_copy_option"), "copy")
        form.addRow(t("common.audio_encoding_label"), self._audio_codec_combo)

        output_row = QHBoxLayout()
        self._output_dir_label = QLabel("Will create 'Storyboard_Videos' next to the first audio")
        self._output_dir_label.setObjectName("mutedLabel")
        select_output_button = QPushButton("Select Output Folder…")
        select_output_button.clicked.connect(self._select_output_folder)
        output_row.addWidget(self._output_dir_label, stretch=1)
        output_row.addWidget(select_output_button)
        form.addRow("Output folder:", output_row)

        outer.addLayout(form)

        run_row = QHBoxLayout()
        self._generate_button = QPushButton("Generate Videos")
        self._generate_button.clicked.connect(self._generate_videos)
        self._cancel_generate_button = QPushButton(t("common.cancel"))
        self._cancel_generate_button.setObjectName("secondaryButton")
        self._cancel_generate_button.setEnabled(False)
        self._cancel_generate_button.clicked.connect(self._queue.cancel)
        run_row.addWidget(self._generate_button)
        run_row.addWidget(self._cancel_generate_button)
        run_row.addStretch()
        outer.addLayout(run_row)

        self._generate_progress = QProgressBar()
        self._generate_progress.setFormat("Overall: %p%")
        outer.addWidget(self._generate_progress)

        self._generate_status = QLabel("")
        self._generate_status.setObjectName("mutedLabel")
        outer.addWidget(self._generate_status)

        self._queue.job_started.connect(self._on_generate_job_started)
        self._queue.job_progress.connect(self._on_generate_job_progress)
        self._queue.job_finished.connect(self._on_generate_job_finished)
        self._queue.queue_finished.connect(self._on_generate_queue_finished)

        return group

    def _select_output_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select output folder")
        if folder:
            self._output_dir = Path(folder)
            self._output_dir_label.setText(folder)

    def _generate_videos(self) -> None:
        if not self._audios:
            QMessageBox.warning(self, "Storyboard", "Add at least one audio.")
            return
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            QMessageBox.warning(self, "Storyboard", "FFmpeg is not configured.")
            return

        output_dir = self._output_dir or (self._audios[0].parent / "Storyboard_Videos")
        output_dir.mkdir(parents=True, exist_ok=True)
        resolution = _RESOLUTIONS[self._resolution_combo.currentText()]
        fps = int(self._fps_combo.currentText())
        fit_mode = self._fit_combo.currentText()
        audio_codec = self._audio_codec_combo.currentData()

        jobs: List[Job] = []
        self._job_audio_keys: List[str] = []
        skipped = []
        for audio_path in self._audios:
            key = str(audio_path)
            rows = sorted(self._assignments.get(key, []), key=lambda r: r["start"])
            if not rows:
                skipped.append(audio_path.name)
                continue
            entries = [(r["image"], round(r["end"] - r["start"], 3)) for r in rows]
            if any(d <= 0 for _, d in entries):
                QMessageBox.critical(
                    self, "Invalid timing",
                    f"'{audio_path.name}' has an image whose End is not after its Start. Fix it before generating."
                )
                return
            output_path = output_dir / f"{audio_path.stem}_video.mp4"
            list_file_path = Path(tempfile.gettempdir()) / f"ffmpeg_studio_storyboard_{audio_path.stem}.txt"
            params = {
                "ffmpeg_path": str(location.ffmpeg_path),
                "entries": entries,
                "audio_path": key,
                "output": str(output_path),
                "list_file_path": str(list_file_path),
                "fps": fps, "resolution": resolution, "fit_mode": fit_mode,
                "audio_codec": audio_codec,
                "overwrite": True,
            }
            try:
                command = self._storyboard_op.build_command(params)
            except ValueError as exc:
                QMessageBox.critical(self, "Invalid settings", f"{audio_path.name}: {exc}")
                return
            jobs.append(Job(
                id=audio_path.stem, operation_name="storyboard_video",
                input_paths=[audio_path], output_path=output_path, command=command,
            ))
            self._job_audio_keys.append(key)

        if not jobs:
            QMessageBox.warning(self, "Storyboard", "No audio has any images assigned yet.")
            return
        if skipped:
            reply = QMessageBox.question(
                self, "Some audios have no images",
                f"{len(skipped)} audio(s) have no images assigned and will be skipped:\n"
                + ", ".join(skipped) + "\n\nContinue with the rest?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._queue.set_jobs(jobs)
        self._current_output_dir = output_dir
        self._generate_progress.setValue(0)
        self._generate_button.setEnabled(False)
        self._cancel_generate_button.setEnabled(True)
        self._queue.start()

    def _on_generate_job_started(self, index: int) -> None:
        key = self._job_audio_keys[index]
        self._generate_status.setText(f"Rendering: {Path(key).name}")

    def _on_generate_job_progress(self, index: int, state) -> None:
        if state.percent is not None:
            overall = int(((index + state.percent / 100) / len(self._job_audio_keys)) * 100)
            self._generate_progress.setValue(overall)

    def _on_generate_job_finished(self, index: int, status: JobStatus) -> None:
        key = self._job_audio_keys[index]
        job = self._queue.jobs[index]
        if status == JobStatus.SUCCESS:
            self._generated_videos[key] = job.output_path
        self._history_manager.add(
            operation="storyboard_video", input_summary=Path(key).name,
            output_path=str(job.output_path) if status == JobStatus.SUCCESS else "",
            status=status.value, command=job.command,
        )
        self._refresh_audio_list()

    def _on_generate_queue_finished(self) -> None:
        self._generate_button.setEnabled(True)
        self._cancel_generate_button.setEnabled(False)
        self._generate_progress.setValue(100)
        self._generate_status.setText("Video generation complete.")
        self._refresh_merge_list()
        output_dir = getattr(self, "_current_output_dir", None)
        if output_dir:
            maybe_open_output_folder(self._settings_manager, output_dir)

    # ------------------------------------------------------------------
    # Final merge section
    # ------------------------------------------------------------------
    def _build_merge_section(self) -> QWidget:
        group = QGroupBox("Final merge order")
        layout = QVBoxLayout(group)

        note = QLabel(
            "Defaults to the audio list order above once videos are generated. Reorder here if the "
            "final video should play them in a different order."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        list_row = QHBoxLayout()
        self._merge_list = QListWidget()
        list_row.addWidget(self._merge_list, stretch=1)
        buttons_col = QVBoxLayout()
        up_button = QPushButton("Move Up")
        up_button.clicked.connect(lambda: self._move_merge_row(-1))
        down_button = QPushButton("Move Down")
        down_button.clicked.connect(lambda: self._move_merge_row(1))
        for b in (up_button, down_button):
            buttons_col.addWidget(b)
        buttons_col.addStretch()
        list_row.addLayout(buttons_col)
        layout.addLayout(list_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(t("common.output_name_label")))
        self._final_output_name = OutputNameField()
        name_row.addWidget(self._final_output_name, stretch=1)
        layout.addLayout(name_row)

        self._merge_panel = RunPanel()
        self._merge_panel.run_button.setText("Merge into Final Video")
        self._merge_panel.run_button.clicked.connect(self._run_final_merge)
        self._merge_panel.job_succeeded.connect(self._on_final_merge_succeeded)
        layout.addWidget(self._merge_panel)

        return group

    def _refresh_merge_list(self) -> None:
        self._merge_list.clear()
        for audio_path in self._audios:
            video = self._generated_videos.get(str(audio_path))
            if video:
                item = QListWidgetItem(video.name)
                item.setData(1000, str(video))
                self._merge_list.addItem(item)

    def _move_merge_row(self, delta: int) -> None:
        row = self._merge_list.currentRow()
        new_row = row + delta
        if row < 0 or not (0 <= new_row < self._merge_list.count()):
            return
        item = self._merge_list.takeItem(row)
        self._merge_list.insertItem(new_row, item)
        self._merge_list.setCurrentRow(new_row)

    def _merge_video_paths(self) -> List[str]:
        return [self._merge_list.item(i).data(1000) for i in range(self._merge_list.count())]

    def _run_final_merge(self) -> None:
        videos = self._merge_video_paths()
        if len(videos) < 2:
            QMessageBox.warning(self, "Merge", "Generate at least two videos first (one per audio).")
            return
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            QMessageBox.warning(self, "Merge", "FFmpeg is not configured.")
            return

        output_dir = self._output_dir or Path(videos[0]).parent
        default_output = output_dir / "storyboard_final.mp4"
        output_path = resolve_custom_output_name(default_output, self._final_output_name.value())
        resolved = resolve_output_path(self, output_path, self._settings_manager.settings.overwrite_policy)
        if resolved is None:
            return

        list_file_path = Path(tempfile.gettempdir()) / "ffmpeg_studio_storyboard_final_merge.txt"
        params = {
            "ffmpeg_path": str(location.ffmpeg_path),
            "inputs": videos,
            "output": str(resolved),
            "mode": "fast",
            "list_file_path": str(list_file_path),
            "overwrite": True,
        }
        try:
            command = self._merge_op.build_command(params)
        except ValueError as exc:
            QMessageBox.critical(self, "Invalid settings", str(exc))
            return
        self._merge_panel.run(command, resolved)

    def _on_final_merge_succeeded(self, output_path: Path) -> None:
        self._history_manager.add(
            operation="storyboard_final_merge", input_summary=f"{self._merge_list.count()} videos",
            output_path=str(output_path), status="Success",
        )
        maybe_open_output_folder(self._settings_manager, output_path)
