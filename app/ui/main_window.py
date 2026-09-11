"""Main window: sidebar + stacked pages, wired to core managers."""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from PySide6.QtCore import QUrl, QByteArray
from PySide6.QtGui import QIcon, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget, QMessageBox, QLabel

from app.config.settings_manager import SettingsManager
from app.core.ffmpeg_manager import FFmpegManager
from app.core.history_manager import HistoryManager
from app.i18n.translator import t
from app.presets.preset_manager import PresetManager
from app.version import APP_NAME, APP_VERSION

from app.ui.pages.home_page import HomePage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.about_page import AboutPage
from app.ui.pages.compress_page import CompressPage
from app.ui.pages.convert_page import ConvertPage
from app.ui.pages.trim_page import TrimPage
from app.ui.pages.merge_page import MergePage
from app.ui.pages.audio_page import AudioPage
from app.ui.pages.images_page import ImagesToVideoPage
from app.ui.pages.video_audio_page import VideoAudioPage
from app.ui.pages.storyboard_page import StoryboardPage
from app.ui.pages.shorts_page import ShortsPage
from app.ui.pages.batch_page import BatchPage
from app.ui.pages.presets_page import PresetsPage
from app.ui.pages.history_page import HistoryPage
from app.ui.widgets.sidebar import Sidebar

logger = logging.getLogger("ffmpeg_studio")

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(980, 640)
        self.resize(1150, 760)

        icon_path = _PROJECT_ROOT / "assets" / "logo" / "ffmpeg_studio.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.settings_manager = SettingsManager()
        settings = self.settings_manager.settings
        self.ffmpeg_manager = FFmpegManager(settings.ffmpeg_path, settings.ffprobe_path)
        self.history_manager = HistoryManager()
        self.preset_manager = PresetManager()

        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(central)

        self.sidebar = Sidebar()
        root_layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, stretch=1)

        self._pages: dict[str, QWidget] = {}
        self._current_page_key = "home"
        self._build_pages()
        self.sidebar.page_selected.connect(self._show_page)
        self._show_page("home")

        self._build_status_bar()
        self._restore_geometry()
        self._setup_shortcuts()

        self._detect_ffmpeg()

    def _build_status_bar(self) -> None:
        bar = self.statusBar()
        bar.showMessage(t("statusbar.ready"))
        self._version_label = QLabel(f"{APP_NAME} v{APP_VERSION}")
        self._version_label.setObjectName("mutedLabel")
        self._version_label.setContentsMargins(0, 0, 10, 0)
        bar.addPermanentWidget(self._version_label)

    def _restore_geometry(self) -> None:
        saved = self.settings_manager.settings.window_geometry
        if saved:
            try:
                self.restoreGeometry(QByteArray.fromBase64(saved.encode("ascii")))
            except (ValueError, TypeError):
                pass  # corrupt/old-format value — fall back to the default size set above

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("F1"), self, activated=self._open_help)
        QShortcut(QKeySequence("Ctrl+,"), self, activated=lambda: self._show_page("settings"))
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        geometry_b64 = bytes(self.saveGeometry().toBase64()).decode("ascii")
        self.settings_manager.update(window_geometry=geometry_b64)
        super().closeEvent(event)

    def _build_pages(self) -> None:
        fm, sm, hm = self.ffmpeg_manager, self.settings_manager, self.history_manager

        self.home_page = HomePage()
        self.home_page.quick_action_selected.connect(self._show_page)
        self.home_page.open_settings_requested.connect(lambda: self._show_page("settings"))
        self._register_page("home", self.home_page)

        self.compress_page = CompressPage(fm, settings_manager=sm, history_manager=hm)
        self._register_page("compress", self.compress_page)

        self._register_page("convert", ConvertPage(fm, sm, history_manager=hm))
        self._register_page("trim", TrimPage(fm, sm, history_manager=hm))
        self._register_page("merge", MergePage(fm, sm, history_manager=hm))
        self._register_page("audio", AudioPage(fm, sm, history_manager=hm))
        self._register_page("images", ImagesToVideoPage(fm, sm, history_manager=hm))
        self._register_page("video_audio", VideoAudioPage(fm, sm, history_manager=hm))
        self._register_page("storyboard", StoryboardPage(fm, sm, hm))
        self._register_page("shorts", ShortsPage(fm, sm, history_manager=hm))
        self._register_page("batch", BatchPage(fm, sm, hm))

        self.presets_page = PresetsPage(self.preset_manager)
        self._register_page("presets", self.presets_page)

        self.history_page = HistoryPage(hm)
        self._register_page("history", self.history_page)

        self.settings_page = SettingsPage()
        self.settings_page.load_settings(sm.settings)
        self.settings_page.detect_requested.connect(self._detect_ffmpeg)
        self.settings_page.ffmpeg_paths_changed.connect(self._apply_ffmpeg_paths)
        self.settings_page.settings_changed.connect(self._apply_settings_change)
        self._register_page("settings", self.settings_page)

        self.about_page = AboutPage()
        self.about_page.help_requested.connect(self._open_help)
        self._register_page("about", self.about_page)

    def _register_page(self, key: str, widget: QWidget) -> None:
        self._pages[key] = widget
        self.stack.addWidget(widget)

    def _show_page(self, key: str) -> None:
        if key == "help":
            self._open_help()
            # Help isn't a stacked page — restore the sidebar highlight to
            # whatever was actually showing before Help was clicked.
            self.sidebar.select(self._current_page_key)
            return
        widget = self._pages.get(key)
        if widget is None:
            return
        self.stack.setCurrentWidget(widget)
        self.sidebar.select(key)
        self._current_page_key = key
        # History/Presets lists can go stale while the user works elsewhere.
        if key == "history":
            self.history_page.refresh()
        elif key == "presets":
            self.presets_page.refresh()

    def _open_help(self) -> None:
        help_path = _PROJECT_ROOT / "assets" / "help.html"
        if not help_path.exists():
            QMessageBox.information(
                self, "Help",
                "The help file hasn't been generated yet. Run docs/generate_help.py.",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(help_path)))

    def _detect_ffmpeg(self) -> None:
        location = self.ffmpeg_manager.detect()
        logger.info("FFmpeg detection: source=%s valid=%s", location.source, location.is_valid)
        self.home_page.set_ffmpeg_status(location)
        if location.ffmpeg_path:
            self.settings_page.set_ffmpeg_fields(str(location.ffmpeg_path), str(location.ffprobe_path))
        if not location.is_valid:
            logger.warning("FFmpeg not found on startup.")

    def _apply_ffmpeg_paths(self, ffmpeg_path: str, ffprobe_path: str) -> None:
        location = self.ffmpeg_manager.set_user_paths(ffmpeg_path, ffprobe_path)
        self.settings_manager.update(ffmpeg_path=ffmpeg_path or None, ffprobe_path=ffprobe_path or None)
        self.home_page.set_ffmpeg_status(location)
        if not location.is_valid:
            QMessageBox.warning(self, "FFmpeg", "Could not validate the provided FFmpeg/FFprobe paths.")
        else:
            self.statusBar().showMessage(t("statusbar.ffmpeg_updated"), 4000)

    def _apply_settings_change(self, changes: dict) -> None:
        self.settings_manager.update(**changes)
        logger.info("Settings updated: %s", list(changes.keys()))
        if "theme" in changes:
            from PySide6.QtWidgets import QApplication
            from app.config.theme import apply_theme
            app = QApplication.instance()
            if app is not None:
                apply_theme(app, changes["theme"])
            self.statusBar().showMessage(t("statusbar.theme_changed"), 3000)
        elif "language" in changes:
            self.statusBar().showMessage(t("statusbar.language_changed"), 5000)
        else:
            self.statusBar().showMessage(t("statusbar.settings_saved"), 3000)
