"""Точка входа. Только запуск приложения, без бизнес-логики."""

from __future__ import annotations

import sys
from datetime import date, datetime

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from config import APP_VERSION, load_config
from images import ImageManager
from logger import get_logger, setup_logging
from mainwindow import MainWindow
from quotes import QuoteManager
from settings import Settings


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    verbose = "--verbose" in argv

    config = load_config()
    setup_logging(config.paths.log_file, verbose=verbose)
    log = get_logger("main")
    log.info("Запуск %s %s", config.name, APP_VERSION)

    app = QApplication(argv)
    app.setApplicationName(config.name)
    app.setApplicationVersion(APP_VERSION)
    if config.paths.icon_file.exists():
        app.setWindowIcon(QIcon(str(config.paths.icon_file)))

    settings = Settings.load(config.paths.settings_file)
    quotes = QuoteManager(config.paths.quotes_file)
    images = ImageManager(settings.photos_path(config.paths.photos_dir))

    window = MainWindow(config, settings, quotes, images)
    window.show_date(_initial_date(settings.last_date))
    window.reveal()

    # Сначала показать окно, затем декодировать первую фотографию.
    QTimer.singleShot(0, lambda: window.next_photo(animate=False))

    if images.is_empty():
        window.warn_no_photos()

    return app.exec()


def _initial_date(stored: str) -> date:
    """Последняя выбранная дата или текущая системная дата."""
    if stored:
        try:
            return datetime.strptime(stored, "%Y-%m-%d").date()
        except ValueError:
            pass
    return date.today()


if __name__ == "__main__":
    raise SystemExit(main())
