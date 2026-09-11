"""Home dashboard: FFmpeg status + quick actions."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QGridLayout,
)

from app.i18n.translator import t
from app.models.models import FFmpegLocation, FFmpegSource

_QUICK_ACTIONS = [
    ("convert", "🎬", "nav.convert"),
    ("compress", "🗜", "nav.compress"),
    ("trim", "✂", "nav.trim"),
    ("merge", "🔗", "nav.merge"),
    ("audio", "🎵", "nav.audio"),
    ("images", "🖼", "home.quick_images_to_video"),
]


class HomePage(QWidget):
    quick_action_selected = Signal(str)
    open_settings_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel(t("home.title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # FFmpeg status card
        self._status_frame = QFrame()
        self._status_frame.setObjectName("card")
        status_layout = QVBoxLayout(self._status_frame)
        self._status_label = QLabel(t("home.checking_ffmpeg"))
        self._status_label.setObjectName("statusLabel")
        self._version_label = QLabel("")
        status_layout.addWidget(self._status_label)
        status_layout.addWidget(self._version_label)

        settings_button = QPushButton(t("home.configure_button"))
        settings_button.clicked.connect(self.open_settings_requested.emit)
        status_row = QHBoxLayout()
        status_row.addWidget(self._status_frame, stretch=1)
        status_col = QVBoxLayout()
        status_col.addWidget(settings_button)
        status_col.addStretch()
        status_row.addLayout(status_col)
        layout.addLayout(status_row)

        # Quick actions
        actions_label = QLabel(t("home.quick_actions"))
        actions_label.setObjectName("sectionLabel")
        layout.addWidget(actions_label)

        grid = QGridLayout()
        grid.setSpacing(10)
        for i, (key, icon, label_key) in enumerate(_QUICK_ACTIONS):
            button = QPushButton(f"{icon}  {t(label_key)}")
            button.setObjectName("quickActionButton")
            button.setMinimumHeight(56)
            button.clicked.connect(lambda checked, k=key: self.quick_action_selected.emit(k))
            grid.addWidget(button, i // 3, i % 3)
        layout.addLayout(grid)

        # Recent jobs (placeholder until job history is wired up in Phase 4)
        recent_label = QLabel(t("home.recent_jobs"))
        recent_label.setObjectName("sectionLabel")
        layout.addWidget(recent_label)
        self._recent_placeholder = QLabel(t("home.no_recent_jobs"))
        self._recent_placeholder.setObjectName("mutedLabel")
        layout.addWidget(self._recent_placeholder)

        layout.addStretch()

    def set_ffmpeg_status(self, location: FFmpegLocation) -> None:
        if location.source == FFmpegSource.NOT_FOUND:
            self._status_label.setText(t("home.ffmpeg_not_detected"))
            self._status_label.setObjectName("statusLabelError")
            self._version_label.setText(t("home.configure_ffmpeg_hint"))
        else:
            source_label = {
                FFmpegSource.BUNDLED: t("home.source_bundled"),
                FFmpegSource.SYSTEM_PATH: t("home.source_system_path"),
                FFmpegSource.USER_SELECTED: t("home.source_user_selected"),
            }.get(location.source, "unknown")
            self._status_label.setText(t("home.ffmpeg_detected", source=source_label))
            version_text = t("home.version_label", version=location.version) if location.version else ""
            self._version_label.setText(version_text)
