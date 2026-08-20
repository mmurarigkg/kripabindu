"""Конфигурация приложения.

Единственный модуль, который знает физическое расположение каталогов и файлов.
Абсолютные пути нигде не «зашиты»: всё вычисляется от расположения программы.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

APP_NAME: str = "Krpa Bindu"
APP_VERSION: str = "1.0"
ENCODING: str = "utf-8"


class Theme(str, Enum):
    """Поддерживаемые темы оформления."""

    MICA = "mica"
    ACRYLIC = "acrylic"
    PLAIN = "plain"

    @classmethod
    def parse(cls, value: object, default: "Theme" = None) -> "Theme":
        default = default or cls.MICA
        try:
            return cls(str(value).lower())
        except (ValueError, AttributeError):
            return default


class Language(str, Enum):
    """Поддерживаемые языки интерфейса."""

    RU = "ru"
    EN = "en"

    @classmethod
    def parse(cls, value: object, default: "Language" = None) -> "Language":
        default = default or cls.RU
        try:
            return cls(str(value).lower())
        except (ValueError, AttributeError):
            return default


IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
)


def base_dir() -> Path:
    """Каталог приложения (работает и из исходников, и из сборки PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


@dataclass(frozen=True, slots=True)
class Paths:
    """Пути приложения и пользовательских данных.

    Устанавливаемые ресурсы находятся рядом с EXE и используются только для чтения.
    Изменяемые данные пользователя хранятся в LOCALAPPDATA, чтобы приложение
    нормально работало без прав администратора при установке в Program Files.
    """

    root: Path = field(default_factory=base_dir)

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def fonts_dir(self) -> Path:
        return self.assets_dir / "fonts"

    @property
    def icon_file(self) -> Path:
        return self.assets_dir / "icon.ico"

    @property
    def logo_file(self) -> Path:
        return self.assets_dir / "logo.png"

    # Устанавливаемые данные: только чтение.
    @property
    def data_dir(self) -> Path:
        return self.root / "data"

    @property
    def quotes_file(self) -> Path:
        return self.data_dir / "quotes.json"

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    # Пользовательские данные: запись разрешена без прав администратора.
    @property
    def user_data_dir(self) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "KrpaBindu"
        return Path.home() / "AppData" / "Local" / "KrpaBindu"

    @property
    def settings_file(self) -> Path:
        return self.user_data_dir / "settings.json"

    @property
    def logs_dir(self) -> Path:
        return self.user_data_dir / "logs"

    @property
    def log_file(self) -> Path:
        return self.logs_dir / "app.log"

    def ensure(self) -> None:
        """Создать только пользовательские каталоги."""
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class UiConfig:
    """Константы интерфейса (см. часть 3 ТЗ)."""

    default_width: int = 960
    default_height: int = 520
    min_width: int = 720
    min_height: int = 420
    corner_radius: int = 18
    content_margin: int = 24
    photo_ratio: float = 0.5
    quote_font_max: int = 14
    quote_font_min: int = 14
    fade_duration: int = 400


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Совокупная конфигурация приложения."""

    paths: Paths = field(default_factory=Paths)
    ui: UiConfig = field(default_factory=UiConfig)
    name: str = APP_NAME
    version: str = APP_VERSION


def load_config() -> AppConfig:
    """Создать конфигурацию и подготовить структуру каталогов."""
    config = AppConfig()
    config.paths.ensure()
    return config
