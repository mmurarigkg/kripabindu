"""Все анимации проекта сосредоточены в этом модуле."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QSequentialAnimationGroup,
)
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

DEFAULT_DURATION = 400


def _opacity_effect(widget: QWidget) -> QGraphicsOpacityEffect:
    effect = widget.graphicsEffect()
    if isinstance(effect, QGraphicsOpacityEffect):
        return effect
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(1.0)
    widget.setGraphicsEffect(effect)
    return effect


def fade_in(widget: QWidget, duration: int = DEFAULT_DURATION) -> QPropertyAnimation:
    """Плавное появление виджета."""
    effect = _opacity_effect(widget)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(effect.opacity())
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def fade_out(widget: QWidget, duration: int = DEFAULT_DURATION) -> QPropertyAnimation:
    """Плавное исчезновение виджета."""
    effect = _opacity_effect(widget)
    animation = QPropertyAnimation(effect, b"opacity", widget)
    animation.setDuration(duration)
    animation.setStartValue(effect.opacity())
    animation.setEndValue(0.0)
    animation.setEasingCurve(QEasingCurve.Type.InCubic)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def cross_fade(
    widget: QWidget,
    update: Callable[[], None],
    duration: int = DEFAULT_DURATION,
) -> QSequentialAnimationGroup:
    """Исчезновение → обновление содержимого → появление.

    Используется и для смены фотографии, и для смены текста цитаты.
    """
    effect = _opacity_effect(widget)
    half = max(80, duration // 2)

    out_animation = QPropertyAnimation(effect, b"opacity")
    out_animation.setDuration(half)
    out_animation.setStartValue(effect.opacity())
    out_animation.setEndValue(0.0)
    out_animation.setEasingCurve(QEasingCurve.Type.InCubic)

    in_animation = QPropertyAnimation(effect, b"opacity")
    in_animation.setDuration(half)
    in_animation.setStartValue(0.0)
    in_animation.setEndValue(1.0)
    in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    group = QSequentialAnimationGroup(widget)
    group.addAnimation(out_animation)
    group.addAnimation(in_animation)

    applied = False

    def on_state(state: QPropertyAnimation.State) -> None:
        nonlocal applied
        if state == QPropertyAnimation.State.Running and not applied:
            applied = True
            update()

    in_animation.stateChanged.connect(lambda new, _old: on_state(new))
    group.start(QSequentialAnimationGroup.DeletionPolicy.DeleteWhenStopped)
    return group


def show_window(window: QWidget, duration: int = DEFAULT_DURATION) -> QPropertyAnimation:
    """Анимация появления окна (без graphics effect — через windowOpacity)."""
    window.setWindowOpacity(0.0)
    window.show()
    animation = QPropertyAnimation(window, b"windowOpacity", window)
    animation.setDuration(duration)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    animation.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return animation


def keep_alive(owner: QObject, animation: QObject) -> None:
    """Привязать анимацию к владельцу, чтобы её не удалил сборщик мусора."""
    animation.setParent(owner)
