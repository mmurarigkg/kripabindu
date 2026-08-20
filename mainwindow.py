"""Главное окно — только отображение и обработка действий пользователя.

Модуль не читает JSON и не обращается к файлам напрямую: все данные приходят
через QuoteManager, ImageManager и Settings.
"""

from __future__ import annotations

import random
from pathlib import Path

from datetime import date, timedelta

from PySide6.QtCore import QDate, QPoint, QRectF, QSize, Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QColor,
    QDesktopServices,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import animations
import desktop
import effects
from config import AppConfig, Language
from images import ImageManager
from logger import get_logger
from quotes import Quote, QuoteManager
from settings import Settings

log = get_logger("mainwindow")

_WEEKDAYS = (
    "Mon (Пн)",
    "Tue (Вт)",
    "Wed (Ср)",
    "Thu (Чт)",
    "Fri (Пт)",
    "Sat (Суб)",
    "Sun (Вскр)",
)
_MONTHS = (
    "Jan (Янв)",
    "Feb (Фев)",
    "Mar (Мар)",
    "Apr (Апр)",
    "May (Май)",
    "Jun (Июн)",
    "Jul (Июл)",
    "Aug (Авг)",
    "Sep (Сен)",
    "Oct (Окт)",
    "Nov (Ноя)",
    "Dec (Дек)",
)


class PhotoView(QWidget):
    """Фотография со скруглёнными углами, без искажения пропорций."""

    def __init__(self, radius: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._radius = radius
        self._pixmap: QPixmap | None = None
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt API)
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), self._radius, self._radius)
        painter.setClipPath(path)

        if self._pixmap is None or self._pixmap.isNull():
            painter.fillPath(path, QColor(0, 0, 0, 40))
            painter.setPen(QColor(120, 120, 120))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "Нет фотографий" if self._settings.language == Language.RU
                else "No photos",
            )
            return

        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        offset = QPoint(
            (self.width() - scaled.width()) // 2,
            (self.height() - scaled.height()) // 2,
        )
        painter.drawPixmap(offset, scaled)


class DatePickerDialog(QDialog):
    """Календарь выбора даты: одна дата, подтверждение или отмена."""

    def __init__(
        self,
        current: date,
        language: Language = Language.RU,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._language = language
        ru = language == Language.RU
        self.setWindowTitle("Выбрать дату" if ru else "Select date")
        self.setMinimumWidth(340)

        self._calendar = QCalendarWidget(self)
        self._calendar.setGridVisible(False)
        self._calendar.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        self._calendar.setSelectedDate(QDate(current.year, current.month, current.day))
        self._calendar.activated.connect(self._on_calendar_activated)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(
            "Показать" if ru else "Show"
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            "Отмена" if ru else "Cancel"
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        layout.addWidget(self._calendar)
        layout.addWidget(buttons)

    def _on_calendar_activated(self, _qdate: QDate) -> None:
        """Подтвердить выбранную дату при активации в календаре."""
        self.accept()

    def selected_date(self) -> date:
        value = self._calendar.selectedDate()
        return date(value.year(), value.month(), value.day())


class MainWindow(QWidget):
    """Виджет рабочего стола: фотография слева, цитата справа."""

    def __init__(
        self,
        config: AppConfig,
        settings: Settings,
        quotes: QuoteManager,
        images: ImageManager,
    ) -> None:
        super().__init__()
        self._config = config
        self._settings = settings
        self._quotes = quotes
        self._images = images
        self._date = date.today()
        self._drag_offset: QPoint | None = None
        self._font_adjustment = 0

        self._audio_output = QAudioOutput(self)
        self._audio_output.setVolume(0.75)
        self._audio_player = QMediaPlayer(self)
        self._audio_player.setAudioOutput(self._audio_output)
        self._audio_tracks: list[Path] = []
        self._audio_index = -1
        self._volume_value = 75

        self.setObjectName("krishnaWidget")
        self.setWindowTitle(config.name)
        self.setMinimumSize(QSize(config.ui.min_width, config.ui.min_height))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        desktop.configure_widget_window(self)
        self._build_ui()
        self._setup_context_menu()
        self._build_actions()
        self._retranslate_ui()
        self._apply_style()

        desktop.restore_geometry(
            self, settings.window_position, settings.window_size
        )

    # ------------------------------------------------------------------ разметка
    def _build_ui(self) -> None:
        ui = self._config.ui

        self._surface = QFrame(self)
        self._surface.setObjectName("surface")


        self._photo = PhotoView(ui.corner_radius, self._surface)

        self._quote_label = QLabel(self._surface)
        self._quote_label.setObjectName("quote")
        self._quote_label.setWordWrap(True)
        self._quote_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        self._source_label = QLabel(self._surface)
        self._source_label.setObjectName("source")
        self._source_label.setWordWrap(True)

        self._date_caption = QLabel(self._surface)
        self._date_caption.setObjectName("dateCaption")

        self._date_label = QLabel(self._surface)
        self._date_label.setObjectName("dateValue")

        self._prev_date_button = QPushButton("←", self._surface)
        self._prev_date_button.setToolTip("Предыдущий день")
        self._prev_date_button.clicked.connect(self._previous_date)

        self._next_date_button = QPushButton("→", self._surface)
        self._next_date_button.setToolTip("Следующий день")
        self._next_date_button.clicked.connect(self._next_date)

        self._menu_button = QPushButton("Меню", self._surface)
        self._menu_button.setObjectName("menuButton")
        self._menu_button.clicked.connect(self._show_main_menu)

        self._audio_prev_button = QPushButton("◀", self._surface)
        self._audio_prev_button.setToolTip("Предыдущий бхаджан")
        self._audio_prev_button.clicked.connect(self._previous_audio)

        self._audio_play_button = QPushButton("▶", self._surface)
        self._audio_play_button.setToolTip("Воспроизвести / пауза")
        self._audio_play_button.clicked.connect(self._toggle_audio)

        self._audio_next_button = QPushButton("▶|", self._surface)
        self._audio_next_button.setToolTip("Следующий бхаджан")
        self._audio_next_button.clicked.connect(self._next_audio)

        self._audio_title_label = QLabel("Бхаджаны не найдены", self._surface)
        self._audio_title_label.setObjectName("audioTitle")
        self._audio_title_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._audio_time_label = QLabel("0:00 / 0:00", self._surface)
        self._audio_time_label.setObjectName("audioTime")

        self._audio_slider = QSlider(Qt.Orientation.Horizontal, self._surface)
        self._audio_slider.setRange(0, 0)
        self._audio_slider.sliderMoved.connect(self._seek_audio)

        self._volume_label = QLabel(self._tr("Громкость", "Volume"), self._surface)
        self._volume_label.setObjectName("volumeLabel")

        self._volume_slider = QSlider(Qt.Orientation.Horizontal, self._surface)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(75)
        self._volume_slider.setToolTip("Громкость: 0–100%")
        self._volume_slider.valueChanged.connect(self._set_volume)

        self._volume_scale = QLabel("0%                         50%                         100%", self._surface)
        self._volume_scale.setObjectName("volumeScale")

        self._scan_audio_tracks()
        self._audio_player.positionChanged.connect(self._update_audio_position)
        self._audio_player.durationChanged.connect(self._update_audio_duration)
        self._audio_player.mediaStatusChanged.connect(self._audio_status_changed)

        self._last_will_button = QPushButton(self._tr("Завещание (англ.)", "Last will (ENG)"), self._surface)
        self._last_will_button.setToolTip(self._tr("Открыть lastwilleng.pdf", "Open lastwilleng.pdf"))
        self._last_will_button.clicked.connect(
            lambda: self._open_data_pdf("lastwilleng.pdf")
        )

        self._will_button = QPushButton(self._tr("Завещание (рус.)", "Last will (RUS)"), self._surface)
        self._will_button.setToolTip(self._tr("Открыть lastwillrus.pdf", "Open lastwillrus.pdf"))
        self._will_button.clicked.connect(
            lambda: self._open_data_pdf("lastwillrus.pdf")
        )

        self._language_button = QPushButton("ENG/РУС", self._surface)
        self._language_button.setToolTip("")
        self._language_button.clicked.connect(self._toggle_language)

        self._font_minus_button = QPushButton("A−", self._surface)
        self._font_minus_button.setToolTip("Уменьшить размер шрифта")
        self._font_minus_button.clicked.connect(self._decrease_font)

        self._font_plus_button = QPushButton("A+", self._surface)
        self._font_plus_button.setToolTip("Увеличить размер шрифта")
        self._font_plus_button.clicked.connect(self._increase_font)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(10)
        text_column.addStretch(1)
        text_column.addWidget(self._quote_label)
        text_column.addWidget(self._source_label)
        text_column.addStretch(1)
        text_column.addWidget(self._date_caption)

        date_row = QHBoxLayout()
        date_row.setContentsMargins(0, 0, 0, 0)
        date_row.setSpacing(6)
        date_row.addWidget(self._date_label)
        date_row.addStretch(1)
        date_row.addWidget(self._prev_date_button)
        date_row.addWidget(self._next_date_button)
        text_column.addLayout(date_row)

        text_column.addSpacing(8)

        link_row = QHBoxLayout()
        link_row.setContentsMargins(0, 0, 0, 0)
        link_row.setSpacing(6)
        link_row.addWidget(self._menu_button)
        link_row.addStretch(1)
        link_row.addWidget(self._language_button)
        link_row.addWidget(self._font_minus_button)
        link_row.addWidget(self._font_plus_button)
        text_column.addLayout(link_row)

        audio_row = QHBoxLayout()
        audio_row.setContentsMargins(0, 0, 0, 0)
        audio_row.setSpacing(5)
        audio_row.addWidget(self._audio_prev_button)
        audio_row.addWidget(self._audio_play_button)
        audio_row.addWidget(self._audio_next_button)
        audio_row.addWidget(self._audio_title_label, 1)
        audio_row.addWidget(self._audio_time_label)
        text_column.addLayout(audio_row)

        audio_seek_row = QHBoxLayout()
        audio_seek_row.setContentsMargins(0, 0, 0, 0)
        audio_seek_row.setSpacing(6)
        self._play_label = QLabel(self._tr("Воспроизведение", "Play"), self._surface)
        self._play_label.setObjectName("playLabel")
        audio_seek_row.addWidget(self._play_label)
        audio_seek_row.addWidget(self._audio_slider, 1)
        text_column.addLayout(audio_seek_row)

        volume_row = QHBoxLayout()
        volume_row.setContentsMargins(0, 0, 0, 0)
        volume_row.setSpacing(6)
        volume_row.addWidget(self._volume_label)

        volume_control = QVBoxLayout()
        volume_control.setContentsMargins(0, 0, 0, 0)
        volume_control.setSpacing(0)
        volume_control.addWidget(self._volume_slider)
        volume_control.addWidget(self._volume_scale)
        volume_row.addLayout(volume_control)

        # Регулятор громкости занимает примерно половину ширины
        # основной полосы воспроизведения.
        volume_row.addStretch(1)
        text_column.addLayout(volume_row)

        pdf_row = QHBoxLayout()
        pdf_row.setContentsMargins(0, 0, 0, 0)
        pdf_row.setSpacing(6)
        pdf_row.addStretch(1)
        pdf_row.addWidget(self._last_will_button)
        pdf_row.addWidget(self._will_button)
        text_column.addLayout(pdf_row)

        self._text_panel = QWidget(self._surface)
        self._text_panel.setLayout(text_column)

        content = QHBoxLayout(self._surface)
        content.setContentsMargins(
            ui.content_margin, ui.content_margin, ui.content_margin, ui.content_margin
        )
        content.setSpacing(ui.content_margin)
        content.addWidget(self._photo, 1)
        content.addWidget(self._text_panel, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._surface)

    def _setup_context_menu(self) -> None:
        """Разрешить контекстное меню на окне и его дочерних элементах."""
        widgets = (
            self,
            self._surface,
            self._photo,
            self._text_panel,
            self._quote_label,
            self._source_label,
            self._date_label,
            self._menu_button,
            self._prev_date_button,
            self._next_date_button,
            self._language_button,
            self._font_minus_button,
            self._font_plus_button,
            self._last_will_button,
            self._will_button,
            self._audio_prev_button,
            self._audio_play_button,
            self._audio_next_button,
            self._audio_title_label,
            self._audio_time_label,
            self._audio_slider,
            self._volume_label,
            self._volume_slider,
        )
        for widget in widgets:
            widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            widget.customContextMenuRequested.connect(
                lambda pos, w=widget: self._show_context_menu(w, pos)
            )

    def _show_context_menu(self, widget: QWidget, pos: QPoint) -> None:
        """Показать контекстное меню в глобальной позиции."""
        self._build_context_menu().exec(widget.mapToGlobal(pos))

    def _show_main_menu(self) -> None:
        """Показать основное меню приложения под кнопкой «Меню»."""
        menu = self._build_context_menu()
        menu.exec(self._menu_button.mapToGlobal(
            QPoint(0, self._menu_button.height())
        ))

    def _build_context_menu(self) -> QMenu:
        """Создать контекстное меню приложения."""
        menu = QMenu(self)
        menu.addAction(self._action_today)
        menu.addAction(self._action_pick)
        menu.addSeparator()
        menu.addAction(self._action_photo)
        menu.addSeparator()
        menu.addAction(self._action_random_color)
        menu.addSeparator()
        menu.addAction(self._action_quit)
        return menu

    def _build_actions(self) -> None:
        self._action_today = QAction(self._tr("Сегодня", "Today"), self)
        self._action_today.setShortcut(QKeySequence("Ctrl+D"))
        self._action_today.triggered.connect(self.show_today)

        self._action_pick = QAction(self._tr("Выбрать дату...", "Select date..."), self)
        self._action_pick.setShortcut(QKeySequence("Ctrl+G"))
        self._action_pick.triggered.connect(self.pick_date)

        self._action_photo = QAction(self._tr("Следующее фото", "Next photo"), self)
        self._action_photo.setShortcut(QKeySequence("F5"))
        self._action_photo.triggered.connect(self.next_photo)

        self._action_settings = QAction(self._tr("Настройки", "Settings"), self)
        self._action_settings.setShortcut(QKeySequence("Ctrl+,"))
        self._action_settings.triggered.connect(self._show_settings)

        self._action_random_color = QAction(
            self._tr("Случайный цвет", "Random color"), self
        )
        self._action_random_color.triggered.connect(self._random_window_color)

        self._action_quit = QAction(self._tr("Выход", "Exit"), self)
        self._action_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self._action_quit.triggered.connect(self.close)

        for action in (
            self._action_today,
            self._action_pick,
            self._action_photo,
            self._action_settings,
            self._action_random_color,
            self._action_quit,
        ):
            self.addAction(action)

    def _tr(self, ru: str, en: str) -> str:
        """Вернуть строку интерфейса на текущем языке."""
        return en if self._settings.language == Language.EN else ru

    def _apply_style(self) -> None:
        stylesheet = """
            #surface {
                background-color: rgba(__WINDOW_COLOR__);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
            #quote {
                color: #f6f4ef;
                font-family: "Segoe UI", "Georgia", serif;
                line-height: 150%;
            }
            #source {
                color: #cbbf9f;
                font-family: "Segoe UI", sans-serif;
                font-size: 14px;
                font-style: italic;
            }
            #dateCaption {
                color: rgba(246, 244, 239, 0.55);
                font-family: "Segoe UI", sans-serif;
                font-size: 12px;
                letter-spacing: 1px;
                text-transform: uppercase;
            }
            #dateValue {
                color: rgba(246, 244, 239, 0.85);
                font-family: "Segoe UI", sans-serif;
                font-size: 15px;
            }

            QPushButton {
                color: rgba(246, 244, 239, 0.85);
                background-color: rgba(255, 255, 255, 0.06);
                border: 1px solid rgba(255, 255, 255, 0.10);
                border-radius: 6px;
                padding: 2px 7px;
                min-width: 24px;
                min-height: 22px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.12);
            }
            QPushButton:checked {
                background-color: rgba(203, 191, 159, 0.28);
                color: #f6f4ef;
            }

            #audioTitle {
                font-size: 12px;
                color: rgba(246, 244, 239, 0.82);
            }
            #audioTime {
                font-size: 11px;
                color: rgba(246, 244, 239, 0.60);
            }

            #volumeLabel {
                font-size: 11px;
                color: rgba(246, 244, 239, 0.65);
            }

            #playLabel {
                font-size: 11px;
                color: rgba(246, 244, 239, 0.65);
                min-width: 68px;
            }
            #volumeScale {
                font-size: 9px;
                color: rgba(246, 244, 239, 0.50);
            }

            #link {
                font-family: "Segoe UI", sans-serif;
                font-size: 13px;
            }
            #link a {
                color: rgba(203, 191, 159, 0.75);
                text-decoration: none;
            }
            #link a:hover {
                color: #f6f4ef;
            }
            """
        stylesheet = stylesheet.replace("__WINDOW_COLOR__", self._settings.window_color)
        self.setStyleSheet(stylesheet)

    # ------------------------------------------------------------- отображение
    def refresh_all(self, animate: bool = False) -> None:
        """Обновить и цитату, и фотографию."""
        self._update_quote(animate=animate)
        self.next_photo(animate=animate)

    def show_today(self) -> None:
        self._date = date.today()
        self._settings.last_date = ""
        self._update_quote(animate=True)

    def show_date(self, value: date) -> None:
        """Показать цитату выбранной даты. Фотография не меняется."""
        self._date = value
        self._settings.last_date = value.isoformat()
        self._update_quote(animate=True)

    def pick_date(self) -> None:
        """Открыть календарь и показать выбранную дату."""
        dialog = DatePickerDialog(self._date, self._settings.language, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.show_date(dialog.selected_date())


    def next_photo(self, animate: bool = True) -> None:
        """Показать следующую случайную фотографию."""
        image = self._images.random_image()
        if image is None:
            self._photo.set_pixmap(None)
            return

        def apply() -> None:
            self._photo.set_pixmap(image.load())

        if animate:
            animations.cross_fade(
                self._photo, apply, self._settings.animation_duration
            )
        else:
            apply()

    def _update_quote(self, animate: bool = False) -> None:
        quote = self._quotes.for_date(self._date)

        def apply() -> None:
            self._render_quote(quote)
            self._render_date()

        if animate:
            animations.cross_fade(
                self._text_panel, apply, self._settings.animation_duration
            )
        else:
            apply()

    def _render_quote(self, quote: Quote) -> None:
        if quote.is_empty():
            text = (
                "Цитата на этот день не найдена."
                if self._settings.language == Language.RU
                else "No quote found for this date."
            )
        elif self._settings.language == Language.EN:
            text = quote.source
        else:
            text = quote.text

        self._quote_label.setText(text)
        self._source_label.clear()
        self._source_label.setVisible(False)
        self._fit_quote_font(text)

    def _fit_quote_font(self, text: str) -> None:
        """Длинный текст отображается меньшим кеглем."""
        ui = self._config.ui
        length = len(text)
        if length <= 120:
            size = ui.quote_font_max
        elif length >= 480:
            size = ui.quote_font_min
        else:
            span = ui.quote_font_max - ui.quote_font_min
            size = ui.quote_font_max - int(span * (length - 120) / 360)

        size += self._font_adjustment
        font = self._quote_label.font()
        font.setPointSize(max(8, size))
        self._quote_label.setFont(font)



    def _decrease_font(self) -> None:
        """Уменьшить размер шрифта цитаты."""
        self._font_adjustment = max(-8, self._font_adjustment - 1)
        self._update_quote_font()

    def _increase_font(self) -> None:
        """Увеличить размер шрифта цитаты."""
        self._font_adjustment = min(8, self._font_adjustment + 1)
        self._update_quote_font()

    def _update_quote_font(self) -> None:
        """Пересчитать размер шрифта текущей цитаты."""
        self._fit_quote_font(self._quote_label.text())

    def _previous_date(self) -> None:
        """Показать цитату за предыдущий день."""
        self._date -= timedelta(days=1)
        self._settings.last_date = self._date.isoformat()
        self._update_quote(animate=True)

    def _next_date(self) -> None:
        """Показать цитату за следующий день."""
        self._date += timedelta(days=1)
        self._settings.last_date = self._date.isoformat()
        self._update_quote(animate=True)

    def _toggle_language(self) -> None:
        """Переключить язык цитаты и всего интерфейса."""
        language = (
            Language.RU
            if self._settings.language == Language.EN
            else Language.EN
        )
        self._set_language(language)

    def _set_language(self, language: Language) -> None:
        """Установить язык цитаты и всего интерфейса."""
        self._settings.language = language
        self._settings.save()
        self._retranslate_ui()
        self._update_quote(animate=True)

    def _retranslate_ui(self) -> None:
        """Обновить все видимые строки интерфейса."""
        ru = self._settings.language == Language.RU

        self._menu_button.setText("Меню" if ru else "Menu")
        self._language_button.setText("ENG/РУС")
        self._language_button.setToolTip(
            "Переключить язык интерфейса и цитаты"
            if ru else
            "Switch interface and quote language"
        )

        self._prev_date_button.setToolTip("Предыдущий день" if ru else "Previous day")
        self._next_date_button.setToolTip("Следующий день" if ru else "Next day")
        self._font_minus_button.setToolTip(
            "Уменьшить размер шрифта" if ru else "Decrease font size"
        )
        self._font_plus_button.setToolTip(
            "Увеличить размер шрифта" if ru else "Increase font size"
        )
        self._audio_prev_button.setToolTip(
            "Предыдущий бхаджан" if ru else "Previous bhajan"
        )
        self._audio_play_button.setToolTip(
            "Воспроизвести / пауза" if ru else "Play / pause"
        )
        self._audio_next_button.setToolTip(
            "Следующий бхаджан" if ru else "Next bhajan"
        )
        self._volume_label.setText("Громкость" if ru else "Volume")
        self._volume_slider.setToolTip(
            f"Громкость: {self._volume_value}%"
            if ru else f"Volume: {self._volume_value}%"
        )
        self._play_label.setText("Воспроизведение" if ru else "Play")
        self._last_will_button.setText("Завещание (англ.)" if ru else "Last will (ENG)")
        self._last_will_button.setToolTip(
            "Открыть lastwilleng.pdf" if ru else "Open lastwilleng.pdf"
        )
        self._will_button.setText("Завещание (рус.)" if ru else "Last will (RUS)")
        self._will_button.setToolTip(
            "Открыть lastwillrus.pdf" if ru else "Open lastwillrus.pdf"
        )
        if not self._audio_tracks:
            self._audio_title_label.setText(
                "Бхаджаны не найдены" if ru else "No bhajans found"
            )

        self._action_today.setText("Сегодня" if ru else "Today")
        self._action_pick.setText("Выбрать дату..." if ru else "Select date...")
        self._action_photo.setText("Следующее фото" if ru else "Next photo")
        self._action_settings.setText("Настройки" if ru else "Settings")
        self._action_random_color.setText(
            "Случайный цвет" if ru else "Random color"
        )
        self._action_quit.setText("Выход" if ru else "Exit")

        self._render_date()

    def _random_window_color(self) -> None:
        """Выбрать случайный приглушённый цвет поверхности окна."""
        palettes = (
            (24, 24, 28), (24, 38, 32), (24, 34, 48),
            (38, 28, 42), (48, 34, 28), (30, 42, 44),
            (42, 32, 28), (32, 28, 44), (28, 42, 36),
            (44, 28, 32),
        )
        r, g, b = random.choice(palettes)
        self._settings.window_color = f"{r},{g},{b},0.72"
        self._settings.save()
        self._apply_style()

    def _render_date(self) -> None:
        today = self._date == date.today()
        if self._settings.language == Language.EN:
            self._date_caption.setText(
                "Today" if today else "Selected date"
            )
            weekdays = (
                "Monday", "Tuesday", "Wednesday", "Thursday",
                "Friday", "Saturday", "Sunday",
            )
            months = (
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December",
            )
        else:
            self._date_caption.setText(
                "Сегодня" if today else "Выбрана дата"
            )
            weekdays = (
                "Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс",
            )
            months = (
                "Января", "Февраля", "Марта", "Апреля", "Мая", "Июня",
                "Июля", "Августа", "Сентября", "Октября", "Ноября", "Декабря",
            )

        self._date_caption.setVisible(self._settings.show_today or not today)
        self._date_label.setText(
            f"{weekdays[self._date.weekday()]}, "
            f"{self._date.day} {months[self._date.month - 1]} {self._date.year}"
        )

    # ------------------------------------------------------------------ эффекты
    def apply_effects(self) -> None:
        """Применить системные эффекты оформления окна."""
        if not effects.apply_theme(self, self._settings.theme):
            log.info("Используется резервный стиль оформления")

    def reveal(self) -> None:
        """Плавно показать виджет."""
        animations.show_window(self, self._settings.animation_duration)
        self.apply_effects()

    # -------------------------------------------------------- действия мышью
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_offset = None
        event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.next_photo()
            event.accept()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self._build_context_menu().exec(event.globalPos())

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------ прочие окна
    def _set_volume(self, value: int) -> None:
        """Установить громкость аудиоплеера в диапазоне 0–100%."""
        self._volume_value = max(0, min(100, value))
        self._audio_output.setVolume(self._volume_value / 100.0)
        self._volume_slider.setToolTip(
            f"Громкость: {self._volume_value}%"
        )

    def _apply_audio_output_level(self) -> None:
        """Применить текущую громкость к аудиовыходу."""
        value = max(0, min(100, getattr(self, "_volume_value", 75)))
        self._audio_output.setVolume(value / 100.0)


    def _scan_audio_tracks(self) -> None:
        """Найти MP3-файлы в каталоге data, не загружая их целиком в память."""
        data_dir = Path(self._config.paths.data_dir)
        self._audio_tracks = sorted(
            (p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() == ".mp3"),
            key=lambda p: p.name.lower(),
        )
        if self._audio_tracks:
            self._audio_index = 0
            self._audio_title_label.setText(self._audio_tracks[0].stem)
            self._audio_play_button.setEnabled(True)
        else:
            self._audio_index = -1
            self._audio_play_button.setEnabled(False)
            self._audio_prev_button.setEnabled(False)
            self._audio_next_button.setEnabled(False)

    def _load_audio_track(self, index: int, autoplay: bool = False) -> None:
        if not self._audio_tracks:
            return

        self._audio_index = index % len(self._audio_tracks)
        path = self._audio_tracks[self._audio_index]

        self._audio_player.stop()
        self._audio_player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self._audio_title_label.setText(path.stem)
        self._audio_slider.setValue(0)
        self._audio_time_label.setText("0:00 / 0:00")
        self._apply_audio_output_level()

        if autoplay:
            self._audio_player.play()
            self._audio_play_button.setText("❚❚")
        else:
            self._audio_play_button.setText("▶")


    def _toggle_audio(self) -> None:
        if not self._audio_tracks:
            return
        if not self._audio_player.source().isValid():
            self._load_audio_track(self._audio_index if self._audio_index >= 0 else 0)
        if self._audio_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._audio_player.pause()
            self._audio_play_button.setText("▶")
        else:
            self._apply_audio_output_level()
            self._audio_player.play()
            self._audio_play_button.setText("❚❚")

    def _previous_audio(self) -> None:
        if self._audio_tracks:
            self._load_audio_track(self._audio_index - 1, autoplay=True)

    def _next_audio(self) -> None:
        if self._audio_tracks:
            self._load_audio_track(self._audio_index + 1, autoplay=True)

    def _seek_audio(self, position: int) -> None:
        self._audio_player.setPosition(position)

    def _update_audio_position(self, position: int) -> None:
        self._audio_slider.setValue(position)
        self._audio_time_label.setText(
            f"{self._format_audio_time(position)} / "
            f"{self._format_audio_time(self._audio_player.duration())}"
        )

    def _update_audio_duration(self, duration: int) -> None:
        self._audio_slider.setRange(0, max(0, duration))
        self._audio_time_label.setText(
            f"{self._format_audio_time(self._audio_player.position())} / "
            f"{self._format_audio_time(duration)}"
        )

    def _audio_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._next_audio()

    @staticmethod
    def _format_audio_time(milliseconds: int) -> str:
        total_seconds = max(0, milliseconds) // 1000
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _open_data_pdf(self, filename: str) -> None:
        """Открыть PDF-файл из каталога data."""
        path = self._config.paths.data_dir / filename
        if not path.exists():
            QMessageBox.warning(
                self,
                self._config.name,
                f"Файл не найден:\n{path}",
            )
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _show_settings(self) -> None:
        message = QMessageBox(self)
        ru = self._settings.language == Language.RU
        message.setWindowTitle("Настройки" if ru else "Settings")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(
            (
                "Настройки хранятся в файле data/settings.json.\n\n"
                f"Тема: {self._settings.theme.value}\n"
                f"Язык: {self._settings.language.value}\n"
                f"Цвет окна: {self._settings.window_color}\n"
                f"Каталог фотографий: {self._images.folder}\n"
                f"Фотографий: {self._images.count()}\n"
                f"Цитат в базе: {self._quotes.count()}"
            )
            if ru else
            (
                "Settings are stored in data/settings.json.\n\n"
                f"Theme: {self._settings.theme.value}\n"
                f"Language: {self._settings.language.value}\n"
                f"Window color: {self._settings.window_color}\n"
                f"Photo folder: {self._images.folder}\n"
                f"Photos: {self._images.count()}\n"
                f"Quotes in database: {self._quotes.count()}"
            )
        )
        message.exec()

    def warn_no_photos(self) -> None:
        ru = self._settings.language == Language.RU
        QMessageBox.information(
            self,
            self._config.name,
            (
                "Каталог фотографий пуст.\n"
                f"Добавьте изображения в {self._images.folder} и нажмите F5."
            )
            if ru else
            (
                "The photo folder is empty.\n"
                f"Add images to {self._images.folder} and press F5."
            ),
        )

    # ------------------------------------------------------------- завершение
    def closeEvent(self, event) -> None:  # noqa: N802
        """Сохранить положение и настройки, освободить ресурсы."""
        position, size = desktop.store_geometry(self)
        self._settings.window_position = position
        self._settings.window_size = size
        self._settings.save()
        self._images.clear_cache()
        log.info("Приложение завершает работу")
        event.accept()
