"""About page: version, creators, copyright, and a quick link to Help."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from app.i18n.translator import t
from app.version import APP_NAME, APP_VERSION, RELEASE_DATE, COPYRIGHT_YEAR, CREATORS

_PROJECT_ROOT = Path(__file__).resolve().parents[3]


class AboutPage(QWidget):
    help_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        card = QFrame()
        card.setObjectName("aboutCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(40, 40, 40, 36)
        card_layout.setSpacing(4)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        icon_label = QLabel()
        icon_path = _PROJECT_ROOT / "assets" / "logo" / "ffmpeg_studio.png"
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path)).scaled(
                72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            icon_label.setPixmap(pixmap)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(icon_label)
        card_layout.addSpacing(14)

        name_label = QLabel(APP_NAME)
        name_label.setObjectName("aboutAppName")
        name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(name_label)

        tagline_label = QLabel(t("about.tagline"))
        tagline_label.setObjectName("aboutTagline")
        tagline_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(tagline_label)
        card_layout.addSpacing(18)

        version_row = QHBoxLayout()
        version_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        version_badge = QLabel(t("about.version_label", version=APP_VERSION))
        version_badge.setObjectName("aboutBadge")
        released_badge = QLabel(t("about.released_label", date=RELEASE_DATE))
        released_badge.setObjectName("aboutBadge")
        version_row.addWidget(version_badge)
        version_row.addWidget(released_badge)
        card_layout.addLayout(version_row)
        card_layout.addSpacing(24)

        description_label = QLabel(t("about.description"))
        description_label.setObjectName("aboutDescription")
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        description_label.setMaximumWidth(520)
        card_layout.addWidget(description_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        card_layout.addSpacing(28)

        divider = QFrame()
        divider.setObjectName("aboutDivider")
        divider.setFixedHeight(1)
        card_layout.addWidget(divider)
        card_layout.addSpacing(20)

        creators_label = QLabel(t("about.creators_label"))
        creators_label.setObjectName("sectionLabel")
        creators_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(creators_label)

        names_label = QLabel(" · ".join(CREATORS))
        names_label.setObjectName("aboutCreators")
        names_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(names_label)
        card_layout.addSpacing(16)

        tech_label = QLabel(f"{t('about.tech_stack_label')}: {t('about.tech_stack_value')}")
        tech_label.setObjectName("mutedLabel")
        tech_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(tech_label)
        card_layout.addSpacing(14)

        shortcuts_label = QLabel(t("about.shortcuts_label"))
        shortcuts_label.setObjectName("sectionLabel")
        shortcuts_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(shortcuts_label)

        for key in ("about.shortcut_help", "about.shortcut_settings", "about.shortcut_quit"):
            shortcut_label = QLabel(t(key))
            shortcut_label.setObjectName("mutedLabel")
            shortcut_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            card_layout.addWidget(shortcut_label)
        card_layout.addSpacing(6)

        ffmpeg_credit_label = QLabel(t("about.ffmpeg_credit"))
        ffmpeg_credit_label.setObjectName("mutedLabel")
        ffmpeg_credit_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        ffmpeg_credit_label.setWordWrap(True)
        ffmpeg_credit_label.setMaximumWidth(460)
        card_layout.addWidget(ffmpeg_credit_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        card_layout.addSpacing(20)

        copyright_label = QLabel(t("about.copyright_label", year=COPYRIGHT_YEAR, creators=" & ".join(CREATORS)))
        copyright_label.setObjectName("aboutCopyright")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        card_layout.addWidget(copyright_label)
        card_layout.addSpacing(22)

        help_button = QPushButton(t("about.view_help_button"))
        help_button.clicked.connect(self.help_requested.emit)
        button_row = QHBoxLayout()
        button_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        button_row.addWidget(help_button)
        card_layout.addLayout(button_row)

        outer_row = QHBoxLayout()
        outer_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer_row.addWidget(card)
        layout.addLayout(outer_row)
        layout.addStretch()
