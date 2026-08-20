"""Интеграция с Windows: позиционирование виджета, поведение окна, WinAPI."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QGuiApplication

from logger import get_logger

log = get_logger("desktop")

IS_WINDOWS = sys.platform == "win32"

_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_APPWINDOW = 0x00040000


def configure_widget_window(window) -> None:
    """Настроить окно как виджет рабочего стола."""
    window.setWindowFlags(
        Qt.WindowType.Window
        | Qt.WindowType.WindowSystemMenuHint
        | Qt.WindowType.WindowMinimizeButtonHint
        | Qt.WindowType.WindowCloseButtonHint
        | Qt.WindowType.NoDropShadowWindowHint
    )
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)


def hide_from_taskbar(window) -> bool:
    """Убрать окно из панели задач (WS_EX_TOOLWINDOW)."""
    if not IS_WINDOWS:
        return False
    try:
        handle = wintypes.HWND(int(window.winId()))
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(handle, _GWL_EXSTYLE)
        style = (style | _WS_EX_TOOLWINDOW) & ~_WS_EX_APPWINDOW
        user32.SetWindowLongW(handle, _GWL_EXSTYLE, style)
        return True
    except (AttributeError, OSError, TypeError) as error:
        log.warning("Не удалось скрыть окно из панели задач: %s", error)
        return False


def available_area() -> QRect:
    """Рабочая область экрана без панели задач."""
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1920, 1080)
    return screen.availableGeometry()


def default_position(size: QSize) -> QPoint:
    """Положение по умолчанию — правый нижний угол с отступом."""
    area = available_area()
    margin = 48
    return QPoint(
        area.right() - size.width() - margin,
        area.bottom() - size.height() - margin,
    )


def clamp_position(position: QPoint, size: QSize) -> QPoint:
    """Не позволить окну уйти за пределы экрана."""
    area = available_area()
    x = min(max(position.x(), area.left()), max(area.right() - size.width(), area.left()))
    y = min(max(position.y(), area.top()), max(area.bottom() - size.height(), area.top()))
    return QPoint(x, y)


def restore_geometry(window, position: list[int], size: list[int]) -> None:
    """Восстановить сохранённые размер и положение окна."""
    window_size = QSize(size[0], size[1])
    window.resize(window_size)

    if position[0] < 0 and position[1] < 0:
        point = default_position(window_size)
    else:
        point = clamp_position(QPoint(position[0], position[1]), window_size)

    window.move(point)


def store_geometry(window) -> tuple[list[int], list[int]]:
    """Вернуть текущие положение и размер окна для сохранения в настройках."""
    return (
        [window.x(), window.y()],
        [window.width(), window.height()],
    )
