"""FFmpeg Studio entry point."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

# Allow `python app/main.py` to work as well as `python -m app.main` by
# ensuring the project root is on sys.path.
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.config.logging_setup import setup_logging  # noqa: E402
from app.config.settings_manager import SettingsManager  # noqa: E402
from app.config.theme import apply_theme  # noqa: E402
from app.i18n.translator import set_language, has_loaded_strings  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    logger = setup_logging()
    logger.info("FFmpeg Studio starting up.")

    app = QApplication(sys.argv)
    app.setApplicationName("FFmpeg Studio")

    # Both theme and language are applied from saved settings before any
    # widget is built, so a fresh launch reflects the saved preference
    # immediately rather than needing an in-app switch first.
    startup_settings = SettingsManager().settings
    apply_theme(app, startup_settings.theme)
    set_language(startup_settings.language)

    if not has_loaded_strings():
        logger.critical("No translation files could be loaded — the UI will show raw keys like 'nav.home'.")
        QMessageBox.warning(
            None, "FFmpeg Studio",
            "The app's language files could not be found, so menus and labels will show as "
            "raw text (e.g. \"nav.home\") instead of readable words.\n\n"
            "This usually means the install is incomplete or corrupted — try reinstalling or "
            "re-downloading the app. The app will continue to work normally otherwise.",
        )

    window = MainWindow()
    window.show()

    exit_code = app.exec()
    logger.info("FFmpeg Studio exiting with code %s.", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
