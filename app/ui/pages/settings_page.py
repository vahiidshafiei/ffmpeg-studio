"""Settings page: FFmpeg paths, output folder, appearance, language, behavior."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QHBoxLayout,
    QComboBox, QCheckBox, QLabel, QFileDialog, QGroupBox, QMessageBox,
)

from app.i18n.languages import SUPPORTED_LANGUAGES, get_language
from app.i18n.translator import t
from app.models.models import AppSettings


class SettingsPage(QWidget):
    ffmpeg_paths_changed = Signal(str, str)  # ffmpeg_path, ffprobe_path
    detect_requested = Signal()
    settings_changed = Signal(dict)  # partial AppSettings fields

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(t("settings.title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # --- FFmpeg group ---
        ffmpeg_group = QGroupBox(t("settings.group_ffmpeg"))
        ffmpeg_form = QFormLayout(ffmpeg_group)

        self._ffmpeg_edit = QLineEdit()
        ffmpeg_row = self._path_row(self._ffmpeg_edit, self._browse_ffmpeg)
        ffmpeg_form.addRow(t("settings.ffmpeg_executable"), ffmpeg_row)

        self._ffprobe_edit = QLineEdit()
        ffprobe_row = self._path_row(self._ffprobe_edit, self._browse_ffprobe)
        ffmpeg_form.addRow(t("settings.ffprobe_executable"), ffprobe_row)

        detect_button = QPushButton(t("settings.detect_automatically"))
        detect_button.clicked.connect(self.detect_requested.emit)
        ffmpeg_form.addRow("", detect_button)

        apply_button = QPushButton(t("settings.apply_ffmpeg_paths"))
        apply_button.clicked.connect(
            lambda: self.ffmpeg_paths_changed.emit(self._ffmpeg_edit.text(), self._ffprobe_edit.text())
        )
        ffmpeg_form.addRow("", apply_button)

        layout.addWidget(ffmpeg_group)

        # --- Output group ---
        output_group = QGroupBox(t("settings.group_output"))
        output_form = QFormLayout(output_group)
        self._output_folder_edit = QLineEdit()
        output_row = self._path_row(self._output_folder_edit, self._browse_output_folder)
        output_form.addRow(t("settings.default_output_folder"), output_row)
        layout.addWidget(output_group)

        # --- Appearance group ---
        appearance_group = QGroupBox(t("settings.group_appearance"))
        appearance_form = QFormLayout(appearance_group)
        self._theme_combo = QComboBox()
        self._theme_items = [
            (t("settings.theme_light"), "Light"),
            (t("settings.theme_dark"), "Dark"),
            (t("settings.theme_system"), "System"),
        ]
        self._theme_combo.addItems([label for label, _ in self._theme_items])
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        appearance_form.addRow(t("settings.theme"), self._theme_combo)
        layout.addWidget(appearance_group)

        # --- Language group ---
        # Flags are shown directly in each combo item's text (emoji flag +
        # native name) since QComboBox has no first-class icon-plus-rich-text
        # slot that's simpler than just putting the emoji in the string.
        language_group = QGroupBox(t("settings.group_language"))
        language_form = QFormLayout(language_group)
        self._language_combo = QComboBox()
        for lang in SUPPORTED_LANGUAGES:
            self._language_combo.addItem(f"{lang.flag}  {lang.native_name}", userData=lang.code)
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_form.addRow(t("settings.language"), self._language_combo)
        layout.addWidget(language_group)

        # --- Behavior group ---
        behavior_group = QGroupBox(t("settings.group_behavior"))
        behavior_form = QFormLayout(behavior_group)

        self._overwrite_combo = QComboBox()
        self._overwrite_items = [
            (t("settings.overwrite_ask"), "Ask every time"),
            (t("settings.overwrite_always"), "Always overwrite"),
            (t("settings.overwrite_never"), "Never overwrite"),
        ]
        self._overwrite_combo.addItems([label for label, _ in self._overwrite_items])
        self._overwrite_combo.currentIndexChanged.connect(self._on_overwrite_changed)
        behavior_form.addRow(t("settings.overwrite_policy"), self._overwrite_combo)

        self._open_output_check = QCheckBox(t("settings.open_output_folder_checkbox"))
        self._open_output_check.toggled.connect(
            lambda v: self.settings_changed.emit({"open_output_folder_on_complete": v})
        )
        behavior_form.addRow("", self._open_output_check)

        self._remember_dir_check = QCheckBox(t("settings.remember_last_directory_checkbox"))
        self._remember_dir_check.toggled.connect(
            lambda v: self.settings_changed.emit({"remember_last_directory": v})
        )
        behavior_form.addRow("", self._remember_dir_check)

        self._notifications_check = QCheckBox(t("settings.notifications_checkbox"))
        self._notifications_check.toggled.connect(
            lambda v: self.settings_changed.emit({"notifications_enabled": v})
        )
        behavior_form.addRow("", self._notifications_check)

        layout.addWidget(behavior_group)
        layout.addStretch()

    def _path_row(self, line_edit: QLineEdit, browse_slot) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(line_edit)
        browse_button = QPushButton(t("common.browse"))
        browse_button.clicked.connect(browse_slot)
        row.addWidget(browse_button)
        return container

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select ffmpeg.exe", filter="ffmpeg.exe;;All files (*)")
        if path:
            self._ffmpeg_edit.setText(path)

    def _browse_ffprobe(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select ffprobe.exe", filter="ffprobe.exe;;All files (*)")
        if path:
            self._ffprobe_edit.setText(path)

    def _browse_output_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select default output folder")
        if path:
            self._output_folder_edit.setText(path)
            self.settings_changed.emit({"default_output_folder": path})

    def _on_theme_changed(self, index: int) -> None:
        if 0 <= index < len(self._theme_items):
            self.settings_changed.emit({"theme": self._theme_items[index][1]})

    def _on_overwrite_changed(self, index: int) -> None:
        if 0 <= index < len(self._overwrite_items):
            self.settings_changed.emit({"overwrite_policy": self._overwrite_items[index][1]})

    def _on_language_changed(self, index: int) -> None:
        code = self._language_combo.itemData(index)
        if not code:
            return
        self.settings_changed.emit({"language": code})
        QMessageBox.information(self, t("settings.group_language"), t("settings.language_restart_notice"))

    def load_settings(self, settings: AppSettings) -> None:
        self._ffmpeg_edit.setText(settings.ffmpeg_path or "")
        self._ffprobe_edit.setText(settings.ffprobe_path or "")
        self._output_folder_edit.setText(settings.default_output_folder or "")

        for i, (_, value) in enumerate(self._theme_items):
            if value == settings.theme:
                self._theme_combo.setCurrentIndex(i)
                break

        for i in range(self._language_combo.count()):
            if self._language_combo.itemData(i) == settings.language:
                self._language_combo.setCurrentIndex(i)
                break

        for i, (_, value) in enumerate(self._overwrite_items):
            if value == settings.overwrite_policy:
                self._overwrite_combo.setCurrentIndex(i)
                break

        self._open_output_check.setChecked(settings.open_output_folder_on_complete)
        self._remember_dir_check.setChecked(settings.remember_last_directory)
        self._notifications_check.setChecked(settings.notifications_enabled)

    def set_ffmpeg_fields(self, ffmpeg_path: str, ffprobe_path: str) -> None:
        self._ffmpeg_edit.setText(ffmpeg_path)
        self._ffprobe_edit.setText(ffprobe_path)
