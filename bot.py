"""
MaxMusicBot — Быстрый музыкальный Telegram-бот
Автор: @MaxMusicBot
Язык: Русский
"""

import os
import logging
import asyncio
import re
import json
import aiohttp
from urllib.parse import quote
from telegram import (
    Update, LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaAudio
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    PreCheckoutQueryHandler, CallbackQueryHandler
)
import yt_dlp

# ─────────────────────────────────────────────────────────────
#  Логирование
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Конфигурация
# ─────────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ITUNES_API_KEY = os.getenv("ITUNES_API_KEY", "")   # Опционально — для расширенного доступа
TEMP_DIR       = "temp_downloads"
PREMIUM_DB     = "premium_users.json"
PREMIUM_PRICE  = 100   # Stars
COMMISSION     = 10    # Stars

os.makedirs(TEMP_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
#  Хранилище Premium-пользователей (JSON-файл)
# ─────────────────────────────────────────────────────────────
def load_premium_users() -> set:
    if os.path.exists(PREMIUM_DB):
        with open(PREMIUM_DB, "r") as f:
            return set(json.load(f))
    return set()

def save_premium_users(users: set):
    with open(PREMIUM_DB, "w") as f:
        json.dump(list(users), f)

PREMIUM_USERS = load_premium_users()

def is_premium(user_id: int) -> bool:
    return user_id in PREMIUM_USERS

# ─────────────────────────────────────────────────────────────
#  iTunes Search API
# ─────────────────────────────────────────────────────────────
async def search_itunes(query: str, limit: int = 5) -> list:
    """Поиск треков через iTunes API"""
    url = (
        f"https://itunes.apple.com/search"
        f"?term={quote(query)}&media=music&entity=song&limit={limit}&lang=ru_ru"
    )
    headers = {}
    if ITUNES_API_KEY:
        headers["Authorization"] = f"Bearer {ITUNES_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    return data.get("results", [])
    except Exception as e:
        logger.error(f"iTunes search error: {e}")
    return []

# ─────────────────────────────────────────────────────────────
#  YouTube / yt-dlp
# ─────────────────────────────────────────────────────────────
async def download_youtube_audio(url: str, user_id: int) -> tuple[str, dict]:
    """Скачивает аудио с YouTube. Возвращает (путь_к_файлу, info_dict)"""
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{TEMP_DIR}/{user_id}_%(id)s.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 15,
    }
    loop = asyncio.get_event_loop()

    def _dl():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = f"{TEMP_DIR}/{user_id}_{info['id']}.mp3"
            return path, info

    return await loop.run_in_executor(None, _dl)

async def download_youtube_video(url: str, user_id: int) -> tuple[str, dict]:
    """Скачивает видео с YouTube (до 50 МБ). Возвращает (путь_к_файлу, info_dict)"""
    ydl_opts = {
        "format": "bestvideo[ext=mp4][filesize<50M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<50M]/best",
        "outtmpl": f"{TEMP_DIR}/{user_id}_video_%(id)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 15,
    }
    loop = asyncio.get_event_loop()

    def _dl():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = f"{TEMP_DIR}/{user_id}_video_{info['id']}.mp4"
            return path, info

    return await loop.run_in_executor(None, _dl)

# ─────────────────────────────────────────────────────────────
#  Клавиатуры
# ─────────────────────────────────────────────────────────────
def main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🔍 Поиск музыки", switch_inline_query_current_chat="")],
    ]
    if not is_premium(user_id):
        buttons.append([InlineKeyboardButton(
            "💎 PREMIUM — 100 ⭐️", callback_data="buy_premium"
        )])
    else:
        buttons.append([InlineKeyboardButton("✅ У вас Premium 💎", callback_data="premium_info")])
    return InlineKeyboardMarkup(buttons)

def search_result_keyboard(tracks: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, track in enumerate(tracks):
        artist = track.get("artistName", "Неизвестно")
        title  = track.get("trackName", "Неизвестно")
        label  = f"{i+1}. {artist} — {title}"[:60]
        buttons.append([InlineKeyboardButton(label, callback_data=f"track_{i}")])
    return InlineKeyboardMarkup(buttons)

def track_action_keyboard(track_idx: int, preview_url: str = None) -> InlineKeyboardMarkup:
    buttons = []
    if preview_url:
        buttons.append([InlineKeyboardButton("▶️ Слушать превью", url=preview_url)])
    buttons.append([InlineKeyboardButton("⬅️ Назад к результатам", callback_data=f"back_search")])
    return InlineKeyboardMarkup(buttons)

# ─────────────────────────────────────────────────────────────
#  Команда /start
# ─────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    premium = is_premium(user.id)
    
    badge = "💎 Premium" if premium else "🆓 Бесплатный"
    
    text = (
        f"👋 Привет, **{user.first_name}**!\n\n"
        f"🎵 Я **MaxMusicBot** — твой суперскоростной музыкальный помощник!\n\n"
        f"**Что умею:**\n"
        f"🔍 Искать треки по названию или исполнителю\n"
        f"📥 Скачивать аудио по YouTube-ссылке\n"
        f"🎬 Скачивать видео по YouTube-ссылке\n"
        f"🎵 Отправлять аудио из видео\n\n"
        f"**Как пользоваться:**\n"
        f"• Напиши название песни → получи список треков\n"
        f"• Отправь YouTube-ссылку → скачаю аудио или видео\n\n"
        f"📊 Ваш статус: {badge}\n"
    )
    
    premium_block = (
        "\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💎✨🌟 **PREMIUM** 🌟✨💎\n"
        "🚀 Максимальная скорость\n"
        "🤖 AI-функции (скоро!)\n"
        "🎯 Приоритетная обработка\n"
        "🔓 Без ограничений\n"
        "💬 Поддержка 24/7\n"
        "━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    await update.message.reply_text(
        text + (premium_block if not premium else ""),
        parse_mode="Markdown",
        reply_markup=main_keyboard(user.id)
    )

# ─────────────────────────────────────────────────────────────
#  Обработка текстовых сообщений
# ─────────────────────────────────────────────────────────────
YT_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w\-]+'
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    if YT_REGEX.search(text):
        await handle_youtube_link(update, context, text)
    else:
        await handle_music_search(update, context, text)

# ─────────────────────────────────────────────────────────────
#  Обработка YouTube-ссылки
# ─────────────────────────────────────────────────────────────
async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE, url: str):
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎵 Скачать аудио", callback_data=f"yt_audio|{url}"),
            InlineKeyboardButton("🎬 Скачать видео", callback_data=f"yt_video|{url}"),
        ]
    ])
    await update.message.reply_text(
        "🔗 **YouTube-ссылка обнаружена!**\n\nЧто скачать?",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

# ─────────────────────────────────────────────────────────────
#  Поиск музыки
# ─────────────────────────────────────────────────────────────
async def handle_music_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    status = await update.message.reply_text(f"🔍 Ищу «{query}»...")
    
    results = await search_itunes(query, limit=5)
    
    if not results:
        await status.edit_text(
            "❌ Ничего не найдено. Попробуйте другой запрос.\n\n"
            "_Пример: Eminem Lose Yourself_",
            parse_mode="Markdown"
        )
        return
    
    # Сохраняем результаты в контекст
    context.user_data["search_results"] = results
    context.user_data["search_query"]   = query
    
    lines = [f"🎵 **Результаты для «{query}»:**\n"]
    for i, t in enumerate(results):
        artist  = t.get("artistName", "—")
        title   = t.get("trackName", "—")
        album   = t.get("collectionName", "—")
        year    = t.get("releaseDate", "")[:4]
        lines.append(f"{i+1}. **{artist}** — {title} ({year})\n   💿 {album}")
    
    lines.append("\n👇 Выберите трек:")
    
    await status.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=search_result_keyboard(results)
    )

# ─────────────────────────────────────────────────────────────
#  Callback-обработчики
# ─────────────────────────────────────────────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    
    await query.answer()
    
    # ── Покупка Premium ──────────────────────────────────────
    if data == "buy_premium":
        await context.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title="💎 MaxMusicBot Premium",
            description=(
                "🚀 Максимальная скорость загрузки\n"
                "🤖 AI-функции (скоро будут добавлены!)\n"
                "🎯 Приоритетная обработка запросов\n"
                "🔓 Без ограничений на скачивание\n\n"
                f"💰 Стоимость: {PREMIUM_PRICE} ⭐️ Stars\n"
                f"📊 Комиссия сервиса: {COMMISSION} ⭐️ Stars"
            ),
            payload=f"premium_{update.effective_user.id}",
            provider_token="",   # XTR не требует токена
            currency="XTR",
            prices=[LabeledPrice("Premium подписка", PREMIUM_PRICE)]
        )
        return
    
    # ── Информация о Premium ─────────────────────────────────
    if data == "premium_info":
        await query.message.reply_text(
            "✅ **У вас уже есть Premium!**\n\n"
            "🤖 AI-функции скоро будут добавлены — следите за обновлениями!\n"
            "🚀 Вы пользуетесь максимальной скоростью.",
            parse_mode="Markdown"
        )
        return
    
    # ── YouTube аудио ────────────────────────────────────────
    if data.startswith("yt_audio|"):
        url = data.split("|", 1)[1]
        await _send_yt_audio(query, context, url)
        return
    
    # ── YouTube видео ────────────────────────────────────────
    if data.startswith("yt_video|"):
        url = data.split("|", 1)[1]
        await _send_yt_video(query, context, url)
        return
    
    # ── Выбор трека из поиска ────────────────────────────────
    if data.startswith("track_"):
        idx     = int(data.split("_")[1])
        results = context.user_data.get("search_results", [])
        if idx < len(results):
            track = results[idx]
            await _show_track_detail(query, context, track)
        return
    
    # ── Назад к поиску ───────────────────────────────────────
    if data == "back_search":
        results = context.user_data.get("search_results", [])
        query_str = context.user_data.get("search_query", "")
        if results:
            lines = [f"🎵 **Результаты для «{query_str}»:**\n"]
            for i, t in enumerate(results):
                artist = t.get("artistName", "—")
                title  = t.get("trackName", "—")
                year   = t.get("releaseDate", "")[:4]
                lines.append(f"{i+1}. **{artist}** — {title} ({year})")
            lines.append("\n👇 Выберите трек:")
            await query.message.edit_text(
                "\n".join(lines),
                parse_mode="Markdown",
                reply_markup=search_result_keyboard(results)
            )
        return

# ─────────────────────────────────────────────────────────────
#  Детальная информация о треке
# ─────────────────────────────────────────────────────────────
async def _show_track_detail(query, context: ContextTypes.DEFAULT_TYPE, track: dict):
    artist      = track.get("artistName", "—")
    title       = track.get("trackName", "—")
    album       = track.get("collectionName", "—")
    year        = track.get("releaseDate", "")[:4]
    genre       = track.get("primaryGenreName", "—")
    duration_ms = track.get("trackTimeMillis", 0)
    duration    = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}" if duration_ms else "—"
    preview_url = track.get("previewUrl")
    artwork_url = track.get("artworkUrl100", "").replace("100x100", "600x600")
    yt_url      = f"https://www.youtube.com/results?search_query={quote(artist + ' ' + title)}"
    
    text = (
        f"🎵 **{artist} — {title}**\n\n"
        f"💿 Альбом: {album}\n"
        f"📅 Год: {year}\n"
        f"🎸 Жанр: {genre}\n"
        f"⏱ Длительность: {duration}\n\n"
        f"🔗 [Найти на YouTube]({yt_url})"
    )
    
    buttons = []
    if preview_url:
        buttons.append([InlineKeyboardButton("▶️ Слушать превью (30 сек)", url=preview_url)])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_search")])
    
    if artwork_url:
        try:
            await query.message.reply_photo(
                photo=artwork_url,
                caption=text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return
        except Exception:
            pass
    
    await query.message.edit_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ─────────────────────────────────────────────────────────────
#  Скачивание аудио с YouTube
# ─────────────────────────────────────────────────────────────
async def _send_yt_audio(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    user_id = query.from_user.id
    msg = await query.message.reply_text("⏳ Скачиваю аудио... Пожалуйста, подождите.")
    
    try:
        audio_path, info = await download_youtube_audio(url, user_id)
        title    = info.get("title", "Аудио")
        uploader = info.get("uploader", "Неизвестно")
        duration = info.get("duration", 0)
        
        await query.message.reply_chat_action("upload_voice")
        
        with open(audio_path, "rb") as f:
            await query.message.reply_audio(
                audio=f,
                title=title,
                performer=uploader,
                duration=duration,
                caption=(
                    f"🎵 **{title}**\n"
                    f"👤 {uploader}\n\n"
                    f"📥 Скачано через @MaxMusicBot"
                ),
                parse_mode="Markdown"
            )
        
        os.remove(audio_path)
        await msg.delete()
        
    except Exception as e:
        logger.error(f"Audio download error: {e}")
        await msg.edit_text("❌ Ошибка при скачивании аудио. Проверьте ссылку или попробуйте позже.")

# ─────────────────────────────────────────────────────────────
#  Скачивание видео с YouTube
# ─────────────────────────────────────────────────────────────
async def _send_yt_video(query, context: ContextTypes.DEFAULT_TYPE, url: str):
    user_id = query.from_user.id
    msg = await query.message.reply_text("⏳ Скачиваю видео... Это может занять немного времени.")
    
    try:
        video_path, info = await download_youtube_video(url, user_id)
        title    = info.get("title", "Видео")
        uploader = info.get("uploader", "Неизвестно")
        duration = info.get("duration", 0)
        
        await query.message.reply_chat_action("upload_video")
        
        with open(video_path, "rb") as f:
            await query.message.reply_video(
                video=f,
                duration=duration,
                caption=(
                    f"🎬 **{title}**\n"
                    f"👤 {uploader}\n\n"
                    f"📥 Скачано через @MaxMusicBot"
                ),
                parse_mode="Markdown"
            )
        
        os.remove(video_path)
        await msg.delete()
        
    except Exception as e:
        logger.error(f"Video download error: {e}")
        await msg.edit_text(
            "❌ Ошибка при скачивании видео.\n"
            "Возможно, видео слишком большое (>50 МБ) или недоступно.\n"
            "Попробуйте скачать только аудио 🎵"
        )

# ─────────────────────────────────────────────────────────────
#  Платёжная система (Telegram Stars)
# ─────────────────────────────────────────────────────────────
async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.pre_checkout_query
    if q.invoice_payload.startswith("premium_"):
        await q.answer(ok=True)
    else:
        await q.answer(ok=False, error_message="Неизвестный платёж.")

async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    PREMIUM_USERS.add(user.id)
    save_premium_users(PREMIUM_USERS)
    
    await update.message.reply_text(
        "🎉 **Поздравляем! Оплата прошла успешно!**\n\n"
        f"💎 Вы теперь Premium-пользователь!\n\n"
        f"✅ Списано: {PREMIUM_PRICE} ⭐️ Stars\n"
        f"📊 Комиссия сервиса: {COMMISSION} ⭐️ Stars\n\n"
        "🤖 **AI-функции скоро будут добавлены!**\n"
        "🚀 Максимальная скорость загрузки активирована!\n"
        "🎯 Приоритетная обработка запросов включена!\n\n"
        "Спасибо за поддержку! ❤️",
        parse_mode="Markdown",
        reply_markup=main_keyboard(user.id)
    )

# ─────────────────────────────────────────────────────────────
#  Запуск
# ─────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    
    # Callback-кнопки
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    # Платежи
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))
    
    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("🚀 MaxMusicBot запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
