# 🎵 MaxMusicBot

> **Суперскоростной музыкальный Telegram-бот** с поиском треков, скачиванием аудио/видео с YouTube и Premium-подпиской на Telegram Stars.

---

## ✨ Возможности

| Функция | Описание |
|---|---|
| 🔍 Поиск музыки | Поиск по названию или исполнителю через iTunes API |
| 📥 Скачать аудио | Отправь YouTube-ссылку → получи MP3 |
| 🎬 Скачать видео | Отправь YouTube-ссылку → получи MP4 |
| 💎 Premium | 100 ⭐️ Stars — AI-функции, приоритет, без ограничений |
| 🤖 AI (скоро) | AI-рекомендации треков и плейлисты |

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

> Убедитесь, что установлен **ffmpeg**:
> ```bash
> # Ubuntu / Debian
> sudo apt install ffmpeg
> # macOS
> brew install ffmpeg
> ```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```env
BOT_TOKEN=ВАШ_ТОКЕН_ОТ_BOTFATHER
ITUNES_API_KEY=ВАШ_КЛЮЧ_ITUNES  # опционально
```

### 3. Запуск

```bash
python bot.py
```

---

## 🔧 Конфигурация

| Переменная | Описание | Обязательно |
|---|---|---|
| `BOT_TOKEN` | Токен от @BotFather | ✅ Да |
| `ITUNES_API_KEY` | Ключ iTunes API (расширенный доступ) | ❌ Нет |

---

## 💎 Premium-система

Premium активируется через **Telegram Stars** (встроенная валюта Telegram):

- **Цена:** 100 ⭐️ Stars
- **Комиссия сервиса:** 10 ⭐️ Stars
- **Что включено:**
  - 🚀 Максимальная скорость загрузки
  - 🤖 AI-функции (скоро!)
  - 🎯 Приоритетная обработка
  - 🔓 Без ограничений

---

## 📁 Структура проекта

```
Maxmusicbot/
├── bot.py              # Основной файл бота
├── requirements.txt    # Зависимости Python
├── .env.example        # Пример переменных окружения
├── .gitignore          # Git-игнор
└── README.md           # Документация
```

---

## 📦 Зависимости

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram Bot API
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Скачивание с YouTube
- [aiohttp](https://docs.aiohttp.org/) — Асинхронные HTTP-запросы
- [iTunes Search API](https://performance-partners.apple.com/search-api) — Поиск музыки

---

## 🛠 Деплой на сервер

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить в фоне (systemd или screen)
screen -S maxmusicbot
python bot.py
```

Или через `systemd`:

```ini
[Unit]
Description=MaxMusicBot
After=network.target

[Service]
WorkingDirectory=/path/to/Maxmusicbot
ExecStart=/usr/bin/python3 bot.py
Restart=always
Environment=BOT_TOKEN=ВАШ_ТОКЕН

[Install]
WantedBy=multi-user.target
```

---

## 📄 Лицензия

MIT License — используйте свободно!
