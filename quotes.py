"""Работа с базой цитат. Модуль не знает об интерфейсе и о фотографиях."""

from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from config import ENCODING
from logger import get_logger

log = get_logger("quotes")


@dataclass(frozen=True, slots=True)
class Quote:
    """Одна цитата. Дополнительные поля базы сохраняются в extra."""

    text: str = ""
    source: str = ""
    extra: dict | None = None

    def is_empty(self) -> bool:
        return not self.text.strip()

    def has_source(self) -> bool:
        return bool(self.source.strip())

    def formatted(self) -> str:
        """Текст цитаты вместе с источником."""
        if self.has_source():
            return f"{self.text.strip()}\n— {self.source.strip()}"
        return self.text.strip()

    def get(self, name: str, default: object = None) -> object:
        """Доступ к будущим полям (author, category, language, audio, ...)."""
        if self.extra:
            return self.extra.get(name, default)
        return default


class QuoteManager:
    """Единственная точка доступа к quotes.json."""

    def __init__(self, file: Path) -> None:
        self._file = file
        self._quotes: dict[str, Quote] = {}
        self.load()

    # ---------------------------------------------------------------- загрузка
    def load(self) -> None:
        """Загрузить и проверить базу. При ошибке база восстанавливается."""
        if not self._file.exists():
            log.warning("База цитат отсутствует, создаётся пустая: %s", self._file)
            self._create_empty()
            return

        try:
            raw = json.loads(self._file.read_text(encoding=ENCODING))
            if not isinstance(raw, dict):
                raise ValueError("Ожидался JSON-объект вида {\"MM-DD\": {...}}")
        except (OSError, ValueError) as error:
            log.error("База цитат повреждена или недоступна (%s): %s", error, self._file)
            self._create_empty()
            return

        self._quotes = self._validate(raw)
        log.info("Загружено цитат: %d", len(self._quotes))

    @staticmethod
    def _validate(raw: dict) -> dict[str, Quote]:
        """Отобрать корректные записи, пропустив повреждённые."""
        result: dict[str, Quote] = {}
        for key, value in raw.items():
            if not _is_key(key) or not isinstance(value, dict):
                log.warning("Пропущена некорректная запись: %r", key)
                continue
            text = value.get("text")
            if not isinstance(text, str) or not text.strip():
                log.warning("Запись %s без текста — пропущена", key)
                continue
            source = value.get("source")
            extra = {
                name: item
                for name, item in value.items()
                if name not in {"text", "source"}
            }
            result[key] = Quote(
                text=text.strip(),
                source=source.strip() if isinstance(source, str) else "",
                extra=extra or None,
            )
        return result

    # ----------------------------------------------------------------- выборка
    def for_date(self, day: date) -> Quote:
        """Цитата на указанную дату. 29 февраля подменяется на 28 февраля."""
        key = self.key_for(day)
        quote = self._quotes.get(key)

        if quote is None and key == "02-29":
            quote = self._quotes.get("02-28")

        if quote is None:
            log.info("Цитата на %s не найдена", key)
            return Quote()
        return quote

    def for_today(self) -> Quote:
        return self.for_date(date.today())

    @staticmethod
    def key_for(day: date) -> str:
        """Ключ базы в формате MM-DD."""
        return f"{day.month:02d}-{day.day:02d}"

    @staticmethod
    def is_leap(year: int) -> bool:
        return calendar.isleap(year)

    def has(self, day: date) -> bool:
        return not self.for_date(day).is_empty()

    def count(self) -> int:
        return len(self._quotes)

    def is_empty(self) -> bool:
        return not self._quotes

    # ------------------------------------------------------------ обслуживание
    def _create_empty(self) -> None:
        """Вернуть пустую базу только в памяти. Установленные ресурсы не изменяются."""
        self._quotes = {}


def _is_key(key: object) -> bool:
    if not isinstance(key, str) or len(key) != 5 or key[2] != "-":
        return False
    month, day = key[:2], key[3:]
    if not (month.isdigit() and day.isdigit()):
        return False
    month_num, day_num = int(month), int(day)
    return 1 <= month_num <= 12 and 1 <= day_num <= 31
