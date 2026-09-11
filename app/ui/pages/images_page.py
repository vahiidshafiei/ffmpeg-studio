"""Images -> Video page."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QComboBox, QDoubleSpinBox, QGroupBox, QFormLayout, QMessageBox, QFileDialog,
)

from app.operations.image_video import ImagesToVideoOperation
from app.i18n.translator import t
from app.ui.dialogs.overwrite_dialog import resolve_output_path
from app.ui.widgets.run_panel import RunPanel
from app.ui.widgets.output_name_field import OutputNameField
from app.utils.natural_sort import natural_sorted_paths
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name

_RESOLUTIONS = {
    "1920×1080 (landscape)": (1920, 1080),
    "1080×1920 (portrait)": (1080, 1920),
    "1280×720": (1280, 720),
}


class ImagesToVideoPage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager=None, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._operation = ImagesToVideoOperation()
        self._audio_path: Optional[Path] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.images"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        list_row = QHBoxLayout()
        self._list = QListWidget()
        list_row.addWidget(self._list, stretch=1)
        buttons_col = QVBoxLayout()
        add_button = QPushButton("Add Images…")
        add_button.clicked.connect(self._add_images)
        sort_button = QPushButton("Natural Sort")
        sort_button.clicked.connect(self._natural_sort)
        up_button = QPushButton("Move Up")
        up_button.clicked.connect(self._move_up)
        down_button = QPushButton("Move Down")
        down_button.clicked.connect(self._move_down)
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(self._remove_selected)
        for b in (add_button, sort_button, up_button, down_button, remove_button):
            buttons_col.addWidget(b)
        buttons_col.addStretch()
        list_row.addLayout(buttons_col)
        layout.addLayout(list_row)

        options_group = QGroupBox(t("common.options_group"))
        form = QFormLayout(options_group)

        self._duration_spin = QDoubleSpinBox()
        self._duration_spin.setRange(0.1, 3600)
        self._duration_spin.setValue(5.0)
        self._duration_spin.setSuffix(" s per image")
        self._duration_spin.valueChanged.connect(self._refresh_preview)
        form.addRow("Duration:", self._duration_spin)

        self._fps_combo = QComboBox()
        self._fps_combo.addItems(["24", "25", "30", "50", "60"])
        self._fps_combo.setCurrentText("30")
        self._fps_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow("FPS:", self._fps_combo)

        self._resolution_combo = QComboBox()
        self._resolution_combo.addItems(list(_RESOLUTIONS))
        self._resolution_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow("Resolution:", self._resolution_combo)

        self._fit_combo = QComboBox()
        self._fit_combo.addItems(["fit", "crop", "stretch", "pad"])
        self._fit_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow("Fit mode:", self._fit_combo)

        audio_row = QHBoxLayout()
        self._audio_label = QLabel("No audio")
        self._audio_label.setObjectName("mutedLabel")
        audio_button = QPushButton("Select Audio…")
        audio_button.clicked.connect(self._select_audio)
        clear_audio_button = QPushButton("Clear")
        clear_audio_button.clicked.connect(self._clear_audio)
        audio_row.addWidget(self._audio_label, stretch=1)
        audio_row.addWidget(audio_button)
        audio_row.addWidget(clear_audio_button)
        form.addRow("Audio (optional):", audio_row)

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

    def _on_job_succeeded(self, output_path: Path) -> None:
        if self._history_manager:
            self._history_manager.add(
                operation="images_to_video", input_summary=f"{self._list.count()} images",
                output_path=str(output_path), status="Success",
            )
        maybe_open_output_folder(self._settings_manager, output_path)

    def _on_job_failed(self, _message: str) -> None:
        if self._history_manager:
            self._history_manager.add(
                operation="images_to_video", input_summary=f"{self._list.count()} images",
                output_path="", status="Failed",
            )

    def _add_images(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select images", filter="Images (*.jpg *.jpeg *.png *.webp);;All files (*)"
        )
        for path in paths:
            self._list.addItem(path)
        self._refresh_preview()

    def _natural_sort(self) -> None:
        items = [Path(self._list.item(i).text()) for i in range(self._list.count())]
        sorted_items = natural_sorted_paths(items)
        self._list.clear()
        for p in sorted_items:
            self._list.addItem(str(p))
        self._refresh_preview()

    def _move_up(self) -> None:
        row = self._list.currentRow()
        if row > 0:
            item = self._list.takeItem(row)
            self._list.insertItem(row - 1, item)
            self._list.setCurrentRow(row - 1)
        self._refresh_preview()

    def _move_down(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < self._list.count() - 1:
            item = self._list.takeItem(row)
            self._list.insertItem(row + 1, item)
            self._list.setCurrentRow(row + 1)
        self._refresh_preview()

    def _remove_selected(self) -> None:
        row = self._list.currentRow()
        if row >= 0:
            self._list.takeItem(row)
        self._refresh_preview()

    def _select_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select audio", filter="Audio files (*.mp3 *.wav *.aac *.flac);;All files (*)")
        if path:
            self._audio_path = Path(path)
            self._audio_label.setText(self._audio_path.name)
            self._refresh_preview()

    def _clear_audio(self) -> None:
        self._audio_path = None
        self._audio_label.setText("No audio")
        self._refresh_preview()

    def _images(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _build_params(self) -> Optional[dict]:
        images = self._images()
        if not images:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        first_dir = Path(images[0]).parent
        output_path = first_dir / "images_video.mp4"
        output_path = resolve_custom_output_name(output_path, self._output_name_field.value())
        list_file_path = Path(tempfile.gettempdir()) / "ffmpeg_studio_image_list.txt"
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "images": images,
            "output": str(output_path),
            "list_file_path": str(list_file_path),
            "seconds_per_image": self._duration_spin.value(),
            "fps": int(self._fps_combo.currentText()),
            "resolution": _RESOLUTIONS[self._resolution_combo.currentText()],
            "fit_mode": self._fit_combo.currentText(),
            "audio_path": str(self._audio_path) if self._audio_path else None,
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
            QMessageBox.warning(self, "Images → Video", "Add at least one image and make sure FFmpeg is configured.")
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
        total_duration = len(params["images"]) * params["seconds_per_image"]
        self._run_panel.run(command, resolved, total_duration_seconds=total_duration)
