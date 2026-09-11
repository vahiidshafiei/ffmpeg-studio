"""Left-hand navigation sidebar. Emits page_selected(page_key) on click."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QFrame

from app.i18n.translator import t
from app.version import APP_NAME, APP_VERSION

# (page_key, icon glyph, translation key)
NAV_ITEMS = [
    ("home", "🏠", "nav.home"),
    ("convert", "🎬", "nav.convert"),
    ("compress", "🗜", "nav.compress"),
    ("trim", "✂", "nav.trim"),
    ("merge", "🔗", "nav.merge"),
    ("audio", "🎵", "nav.audio"),
    ("images", "🖼", "nav.images"),
    ("video_audio", "🎚", "nav.video_audio"),
    ("storyboard", "🎞", "nav.storyboard"),
    ("shorts", "📱", "nav.shorts"),
    ("batch", "📦", "nav.batch"),
    (None, None, None),  # separator
    ("presets", "⭐", "nav.presets"),
    ("history", "📜", "nav.history"),
    (None, None, None),  # separator
    ("settings", "⚙", "nav.settings"),
    ("help", "❓", "nav.help"),
    ("about", "ℹ", "nav.about"),
]


class Sidebar(QWidget):
    page_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(212)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(2)

        brand = QWidget()
        brand.setObjectName("sidebarBrand")
        brand_layout = QHBoxLayout(brand)
        brand_layout.setContentsMargins(18, 20, 14, 18)
        brand_layout.setSpacing(10)
        icon_label = QLabel("🎬")
        icon_label.setObjectName("sidebarBrandIcon")
        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        title_label = QLabel(APP_NAME)
        title_label.setObjectName("sidebarBrandTitle")
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setObjectName("sidebarBrandVersion")
        text_col.addWidget(title_label)
        text_col.addWidget(version_label)
        brand_layout.addWidget(icon_label)
        brand_layout.addLayout(text_col)
        brand_layout.addStretch()
        layout.addWidget(brand)

        divider = QFrame()
        divider.setObjectName("sidebarDivider")
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        nav_container = QWidget()
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(8, 14, 8, 0)
        nav_layout.setSpacing(2)
        layout.addWidget(nav_container)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)

        for key, icon, label_key in NAV_ITEMS:
            if key is None:
                spacer = QWidget()
                spacer.setFixedHeight(12)
                nav_layout.addWidget(spacer)
                continue

            button = QPushButton(f"{icon}   {t(label_key)}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setProperty("pageKey", key)
            button.clicked.connect(lambda checked, k=key: self.page_selected.emit(k))
            self._group.addButton(button)
            nav_layout.addWidget(button)

            if key == "home":
                button.setChecked(True)

        layout.addStretch()

    def select(self, page_key: str) -> None:
        for button in self._group.buttons():
            if button.property("pageKey") == page_key:
                button.setChecked(True)
                break
