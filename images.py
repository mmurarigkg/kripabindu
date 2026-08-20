"""Работа с фотографиями: поиск, случайный выбор, масштабирование, кэш."""

from __future__ import annotations

import random
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap

from config import IMAGE_EXTENSIONS
from logger import get_logger

log = get_logger("images")

_CACHE_LIMIT = 12


@dataclass(slots=True)
class ImageInfo:
    """Описание одной фотографии."""

    path: Path
    _pixmap: QPixmap | None = field(default=None, repr=False)

    @property
    def filename(self) -> str:
        return self.path.name

    @property
    def extension(self) -> str:
        return self.path.suffix.lower()

    @property
    def size(self) -> int:
        try:
            return self.path.stat().st_size
        except OSError:
            return 0

    @property
    def width(self) -> int:
        pixmap = self.load()
        return pixmap.width() if pixmap else 0

    @property
    def height(self) -> int:
        pixmap = self.load()
        return pixmap.height() if pixmap else 0

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> QPixmap | None:
        """Загрузить изображение (один раз на объект)."""
        if self._pixmap is not None:
            return self._pixmap
        if not self.exists():
            log.warning("Файл недоступен: %s", self.path)
            return None
        pixmap = QPixmap(str(self.path))
        if pixmap.isNull():
            log.warning("Изображение не читается: %s", self.path)
            return None
        self._pixmap = pixmap
        return pixmap

    def scaled(self, target: QSize) -> QPixmap | None:
        """Масштабировать с сохранением пропорций, заполняя область."""
        pixmap = self.load()
        if pixmap is None or target.isEmpty():
            return None
        return pixmap.scaled(
            target,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

    def thumbnail(self, edge: int = 160) -> QPixmap | None:
        return self.scaled(QSize(edge, edge))


class ImageManager:
    """Каталог фотографий и кэш загруженных изображений."""

    def __init__(self, folder: Path) -> None:
        self._folder = folder
        self._files: list[Path] = []
        self._cache: "OrderedDict[Path, ImageInfo]" = OrderedDict()
        self._last: Path | None = None
        self.scan()

    # ---------------------------------------------------------------- каталог
    def scan(self) -> int:
        """Просканировать каталог и собрать список поддерживаемых файлов."""
        self._files = []
        if not self._folder.is_dir():
            log.warning("Каталог фотографий отсутствует: %s", self._folder)
            return 0

        try:
            for entry in sorted(self._folder.iterdir()):
                if entry.is_file() and entry.suffix.lower() in IMAGE_EXTENSIONS:
                    self._files.append(entry)
        except OSError as error:
            log.error("Ошибка чтения каталога фотографий: %s", error)

        log.info("Найдено фотографий: %d", len(self._files))
        return len(self._files)

    def set_folder(self, folder: Path) -> None:
        if folder == self._folder:
            return
        self._folder = folder
        self._cache.clear()
        self._last = None
        self.scan()

    @property
    def folder(self) -> Path:
        return self._folder

    def count(self) -> int:
        return len(self._files)

    def is_empty(self) -> bool:
        return not self._files

    # ----------------------------------------------------------------- выборка
    def random_image(self) -> ImageInfo | None:
        """Случайная фотография; не повторяется два раза подряд."""
        if not self._files:
            return None

        candidates = [path for path in self._files if path != self._last] or self._files
        chosen = random.choice(candidates)
        self._last = chosen
        return self._from_cache(chosen)

    def current(self) -> ImageInfo | None:
        if self._last is None:
            return None
        return self._from_cache(self._last)

    # -------------------------------------------------------------------- кэш
    def _from_cache(self, path: Path) -> ImageInfo:
        info = self._cache.get(path)
        if info is not None:
            self._cache.move_to_end(path)
            return info

        info = ImageInfo(path=path)
        self._cache[path] = info
        while len(self._cache) > _CACHE_LIMIT:
            self._cache.popitem(last=False)
        return info

    def clear_cache(self) -> None:
        self._cache.clear()
