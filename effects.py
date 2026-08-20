"""Визуальные эффекты Windows: Mica, Acrylic, скругление, прозрачность.

При отсутствии поддержки автоматически применяется резервный стиль.
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from enum import IntEnum

from config import Theme
from logger import get_logger

log = get_logger("effects")

IS_WINDOWS = sys.platform == "win32"


class _DwmAttribute(IntEnum):
    BORDER_COLOR = 34
    CORNER_PREFERENCE = 33
    SYSTEMBACKDROP_TYPE = 38
    MICA_EFFECT = 1029


class _CornerPreference(IntEnum):
    DEFAULT = 0
    DO_NOT_ROUND = 1
    ROUND = 2
    ROUND_SMALL = 3


class _Backdrop(IntEnum):
    AUTO = 0
    NONE = 1
    MICA = 2
    ACRYLIC = 3
    MICA_ALT = 4


def apply_theme(window, theme: Theme) -> bool:
    """Применить системный эффект к окну. False — использован резервный стиль."""
    if not IS_WINDOWS:
        log.info("Системные эффекты недоступны вне Windows — резервный стиль")
        return False

    handle = _hwnd(window)
    if handle is None:
        return False

    round_corners(window)

    backdrop = {
        Theme.MICA: _Backdrop.MICA,
        Theme.ACRYLIC: _Backdrop.ACRYLIC,
        Theme.PLAIN: _Backdrop.NONE,
    }.get(theme, _Backdrop.MICA)

    if theme is Theme.PLAIN:
        return False

    if _set_attribute(handle, _DwmAttribute.SYSTEMBACKDROP_TYPE, int(backdrop)):
        log.info("Применён эффект %s", theme.value)
        return True

    # Windows 10 / ранние сборки Windows 11
    if _set_attribute(handle, _DwmAttribute.MICA_EFFECT, 1):
        log.info("Применён Mica (устаревший атрибут)")
        return True

    log.warning("Системные эффекты не поддерживаются — резервный стиль")
    return False


def round_corners(window, small: bool = False) -> bool:
    """Включить скругление углов окна (Windows 11)."""
    handle = _hwnd(window)
    if handle is None:
        return False
    preference = _CornerPreference.ROUND_SMALL if small else _CornerPreference.ROUND
    return _set_attribute(handle, _DwmAttribute.CORNER_PREFERENCE, int(preference))


def set_opacity(window, value: float) -> None:
    """Прозрачность окна (0.0 – 1.0)."""
    window.setWindowOpacity(max(0.1, min(1.0, value)))


def _hwnd(window) -> int | None:
    try:
        return int(window.winId())
    except (AttributeError, TypeError, ValueError) as error:
        log.warning("Не удалось получить дескриптор окна: %s", error)
        return None


def _set_attribute(handle: int, attribute: int, value: int) -> bool:
    try:
        data = ctypes.c_int(value)
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(handle),
            wintypes.DWORD(attribute),
            ctypes.byref(data),
            ctypes.sizeof(data),
        )
        return result == 0
    except (AttributeError, OSError) as error:
        log.debug("DwmSetWindowAttribute(%s) недоступен: %s", attribute, error)
        return False
