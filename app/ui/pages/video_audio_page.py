"""Video + Audio page: replace/add/remove the audio track of a video."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QGroupBox,
    QFormLayout, QMessageBox,
)

from app.operations.video_audio import VideoAudioOperation
from app.i18n.translator import t
from app.ui.dialogs.overwrite_dialog import resolve_output_path
from app.ui.widgets.file_drop import FileDropField
from app.ui.widgets.run_panel import RunPanel
from app.ui.widgets.output_name_field import OutputNameField
from app.utils.os_utils import maybe_open_output_folder
from app.utils.output_naming import resolve_custom_output_name


class VideoAudioPage(QWidget):
    def __init__(self, ffmpeg_manager, settings_manager, history_manager=None, parent=None):
        super().__init__(parent)
        self._ffmpeg_manager = ffmpeg_manager
        self._settings_manager = settings_manager
        self._history_manager = history_manager
        self._operation = VideoAudioOperation()
        self._video_path: Optional[Path] = None
        self._audio_path: Optional[Path] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel(t("titles.video_audio"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        video_drop = FileDropField(t("common.drop_video_here"), mode="file")
        video_drop.paths_selected.connect(self._on_video_selected)
        layout.addWidget(video_drop)

        self._audio_drop = FileDropField(
            t("common.drop_audio_here"), mode="file",
            name_filter="Audio files (*.mp3 *.wav *.aac *.flac);;All files (*)",
        )
        self._audio_drop.paths_selected.connect(self._on_audio_selected)
        layout.addWidget(self._audio_drop)

        options_group = QGroupBox(t("common.options_group"))
        form = QFormLayout(options_group)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["replace", "add", "remove"])
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        form.addRow(t("video_audio.mode_label"), self._mode_combo)

        self._policy_combo = QComboBox()
        self._policy_combo.addItems(["shortest", "loop_audio", "video_duration"])
        self._policy_combo.currentTextChanged.connect(self._refresh_preview)
        form.addRow(t("video_audio.duration_handling_label"), self._policy_combo)

        policy_note = QLabel(t("video_audio.policy_note"))
        policy_note.setObjectName("mutedLabel")
        policy_note.setWordWrap(True)
        form.addRow("", policy_note)

        self._audio_encode_combo = QComboBox()
        self._audio_encode_combo.addItem(t("common.audio_reencode_option"), "aac")
        self._audio_encode_combo.addItem(t("common.audio_copy_option"), "copy")
        self._audio_encode_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow(t("common.audio_encoding_label"), self._audio_encode_combo)

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
        if self._history_manager and self._video_path:
            self._history_manager.add(
                operation="video_audio", input_summary=str(self._video_path),
                output_path=str(output_path), status="Success",
            )
        maybe_open_output_folder(self._settings_manager, output_path)

    def _on_job_failed(self, _message: str) -> None:
        if self._history_manager and self._video_path:
            self._history_manager.add(
                operation="video_audio", input_summary=str(self._video_path),
                output_path="", status="Failed",
            )

    def _on_mode_changed(self, mode: str) -> None:
        self._audio_drop.setEnabled(mode != "remove")
        # "copy" audio is only valid for Replace — Add mixes via a filter
        # (must re-encode) and Remove has no audio at all.
        self._audio_encode_combo.setEnabled(mode == "replace")
        self._refresh_preview()

    def _on_video_selected(self, paths) -> None:
        self._video_path = paths[0]
        self._refresh_preview()

    def _on_audio_selected(self, paths) -> None:
        self._audio_path = paths[0]
        self._refresh_preview()

    def _build_params(self) -> Optional[dict]:
        if not self._video_path:
            return None
        mode = self._mode_combo.currentText()
        if mode != "remove" and not self._audio_path:
            return None
        location = self._ffmpeg_manager.location
        if not location.is_valid:
            return None
        suffix_map = {"replace": "dubbed", "add": "with_audio", "remove": "no_audio"}
        output_path = self._video_path.with_name(
            f"{self._video_path.stem}_{suffix_map[mode]}{self._video_path.suffix}"
        )
        output_path = resolve_custom_output_name(output_path, self._output_name_field.value())
        return {
            "ffmpeg_path": str(location.ffmpeg_path),
            "video_input": str(self._video_path),
            "audio_input": str(self._audio_path) if self._audio_path else None,
            "output": str(output_path),
            "mode": mode,
            "duration_policy": self._policy_combo.currentText(),
            "audio_encode": self._audio_encode_combo.currentData(),
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
            QMessageBox.warning(self, t("titles.video_audio"), t("dialogs.ffmpeg_not_configured"))
            return
        resolved = resolve_output_path(self, Path(params["output"]), self._settings_manager.settings.overwrite_policy)
        if resolved is None:
            return
        params["output"] = str(resolved)
        params["overwrite"] = True
        try:
            command = self._operation.build_command(params)
        except ValueError as exc:
            QMessageBox.critical(self, t("dialogs.invalid_settings_title"), str(exc))
            return
        self._run_panel.run(command, resolved)
