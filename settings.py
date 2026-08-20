"""Пользовательские настройки: чтение, запись, валидация, значения по умолчанию."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from config import ENCODING, Language, Theme
from logger import get_logger

log = get_logger("settings")


@dataclass(slots=True)
class Settings:
    """Настройки пользователя. Хранятся в пользовательском каталоге %LOCALAPPDATA%\\KrpaBindu."""

    website: str = "https://www.youtube.com/@GopalKrishnaGoswamiOfficial"
    photos_folder: str = ""
    theme: Theme = Theme.MICA
    language: Language = Language.RU
    window_color: str = "24,24,28,0.72"
    window_position: list[int] = field(default_factory=lambda: [-1, -1])
    window_size: list[int] = field(default_factory=lambda: [960, 520])
    animation_duration: int = 400
    photo_interval: int = 0
    show_today: bool = True
    last_date: str = ""

    _file: Path | None = field(default=None, repr=False, compare=False)

    # ---------------------------------------------------------------- загрузка
    @classmethod
    def load(cls, file: Path) -> "Settings":
        """Прочитать настройки; при любой проблеме вернуть корректный объект."""
        settings = cls()
        settings._file = file

        if not file.exists():
            log.info("Файл настроек отсутствует, создаётся по умолчанию: %s", file)
            settings.save()
            return settings

        try:
            raw = json.loads(file.read_text(encoding=ENCODING))
            if not isinstance(raw, dict):
                raise ValueError("Ожидался JSON-объект")
        except (OSError, ValueError) as error:
            log.warning("Настройки повреждены (%s), создаётся резервная копия", error)
            settings._backup(file)
            settings.save()
            return settings

        settings._apply(raw)
        if settings.validate():
            settings.save()
        return settings

    def _apply(self, raw: dict) -> None:
        """Заполнить поля из словаря, игнорируя неизвестные ключи."""
        self.website = _as_str(raw.get("website"), self.website)
        self.photos_folder = _as_str(raw.get("photos_folder"), self.photos_folder)
        self.theme = Theme.parse(raw.get("theme"), self.theme)
        self.language = Language.parse(raw.get("language"), self.language)
        self.window_color = _as_color(raw.get("window_color"), self.window_color)
        self.window_position = _as_pair(raw.get("window_position"), self.window_position)
        self.window_size = _as_pair(raw.get("window_size"), self.window_size)
        self.animation_duration = _as_int(
            raw.get("animation_duration"), self.animation_duration, 100, 2000
        )
        self.photo_interval = _as_int(raw.get("photo_interval"), self.photo_interval, 0, 86_400)
        self.show_today = bool(raw.get("show_today", self.show_today))
        self.last_date = _as_date(raw.get("last_date"), self.last_date)

    # -------------------------------------------------------------- валидация
    def validate(self) -> bool:
        """Проверить типы и диапазоны. True — если что-то было исправлено."""
        fixed = False
        defaults = Settings()

        if not self.website.startswith(("http://", "https://")):
            self.website = defaults.website
            fixed = True

        width, height = self.window_size
        if width < 720 or height < 420:
            self.window_size = [max(width, 720), max(height, 420)]
            fixed = True

        if self.animation_duration <= 0:
            self.animation_duration = defaults.animation_duration
            fixed = True

        if fixed:
            log.info("Настройки исправлены до корректных значений")
        return fixed

    # ----------------------------------------------------------------- запись
    def save(self) -> None:
        """Сохранить настройки на диск (атомарно)."""
        if self._file is None:
            return
        try:
            self._file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self.as_dict(), ensure_ascii=False, indent=2),
                encoding=ENCODING,
            )
            tmp.replace(self._file)
        except OSError as error:
            log.error("Не удалось сохранить настройки: %s", error)

    def reset(self) -> None:
        """Вернуть значения по умолчанию и сохранить."""
        file = self._file
        defaults = Settings()
        for name in _FIELDS:
            setattr(self, name, getattr(defaults, name))
        self._file = file
        self.save()

    def as_dict(self) -> dict:
        data = {name: getattr(self, name) for name in _FIELDS}
        data["theme"] = self.theme.value
        data["language"] = self.language.value
        return data

    # ------------------------------------------------------------ вспомогательное
    def photos_path(self, default_dir: Path) -> Path:
        """Каталог фотографий: пользовательский или стандартный."""
        if self.photos_folder:
            candidate = Path(self.photos_folder).expanduser()
            if candidate.is_dir():
                return candidate
            log.warning("Каталог фотографий недоступен: %s", candidate)
        return default_dir

    @staticmethod
    def _backup(file: Path) -> None:
        try:
            shutil.copy2(file, file.with_suffix(".bak"))
        except OSError as error:
            log.error("Резервная копия настроек не создана: %s", error)


_FIELDS: tuple[str, ...] = tuple(
    name for name in asdict(Settings()).keys() if not name.startswith("_")
)


def _as_str(value: object, default: str) -> str:
    return value if isinstance(value, str) else default


def _as_color(value: object, default: str) -> str:
    """Проверить строку цвета в формате R,G,B,A."""
    if isinstance(value, str):
        parts = value.split(",")
        if len(parts) == 4:
            try:
                r, g, b = (int(parts[i]) for i in range(3))
                a = float(parts[3])
                if all(0 <= x <= 255 for x in (r, g, b)) and 0.0 <= a <= 1.0:
                    return f"{r},{g},{b},{a:g}"
            except (TypeError, ValueError):
                pass
    return default


def _as_int(value: object, default: int, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return int(min(max(int(value), low), high))


def _as_pair(value: object, default: list[int]) -> list[int]:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
    ):
        return [int(value[0]), int(value[1])]
    return list(default)


def _as_date(value: object, default: str) -> str:
    if isinstance(value, str) and value:
        try:
            datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError:
            return default
    return default
