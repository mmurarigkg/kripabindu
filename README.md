# Krpa Bindu 1.0

Настольный виджет для Windows 10/11: цитата дня и случайная фотография.

## Структура

```
assets/          icon.ico, logo.png, fonts/
data/            quotes.json, settings.json, photos/
logs/            app.log
main.py          точка входа
mainwindow.py    интерфейс
quotes.py        база цитат
images.py        фотографии, кэш
settings.py      пользовательские настройки
config.py        пути и константы
desktop.py       интеграция с Windows
effects.py       Mica / Acrylic / скругления
animations.py    все анимации
logger.py        журналирование
build.py         сборка PyInstaller
installer.iss    установщик Inno Setup
```

## Запуск

```
python -m pip install -r requirements.txt
python main.py
```

Фотографии положите в `data/photos` (jpg, jpeg, png, webp, bmp).
Цитаты — в `data/quotes.json`, ключ даты в формате `MM-DD`.

## Управление

| Действие | Результат |
|---|---|
| Левая кнопка | перетаскивание виджета |
| Правая кнопка | контекстное меню |
| Двойной щелчок | следующая фотография |
| F5 | обновить фотографию |
| Ctrl + D | сегодня |
| Ctrl + G | выбрать дату |
| Ctrl + Q | выход |

## Сборка

```
python build.py          # dist/Krpabindu.exe
iscc installer.iss       # Setup.exe
```

## Архитектура

Интерфейс не читает JSON и не обращается к файлам: только через
`QuoteManager`, `ImageManager` и `Settings`. Модули не знают друг о друге —
связь идёт через `mainwindow.py`. Замена хранилища (SQLite, PostgreSQL)
требует правки только модулей данных.
