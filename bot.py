"""
MaxMusicBot — Multi-language Music Bot (UZ, RU, EN)
Style: VKM Bot
Features: Music Search, YouTube Download, Stars Payment, Admin Panel
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
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    PreCheckoutQueryHandler, CallbackQueryHandler
)
import yt_dlp

# ─────────────────────────────────────────────────────────────
#  Logging
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
ADMIN_ID       = int(os.getenv("ADMIN_ID", "0"))  # O'zingizning ID'ingizni .env ga yozing
TEMP_DIR       = "temp_downloads"
USER_DATA_DB   = "users_data.json"
PREMIUM_PRICE  = 100   # Stars
COMMISSION     = 10    # Stars

os.makedirs(TEMP_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
#  Database Logic
# ─────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(USER_DATA_DB):
        with open(USER_DATA_DB, "r") as f:
            return json.load(f)
    return {"premium": [], "languages": {}, "users": []}

def save_data(data):
    with open(USER_DATA_DB, "w") as f:
        json.dump(data, f)

DATA = load_data()

def get_lang(user_id):
    return DATA["languages"].get(str(user_id), "ru")

def is_premium(user_id):
    return user_id in DATA["premium"]

def add_user(user):
    if user.id not in DATA["users"]:
        DATA["users"].append(user.id)
        save_data(DATA)
        return True
    return False

# ─────────────────────────────────────────────────────────────
#  Localization Strings
# ─────────────────────────────────────────────────────────────
STRINGS = {
    "uz": {
        "welcome": (
            "👋 Salom!\n"
            "Men sizga musiqa topishga yordam beraman 🎶 menga quyidagilardan birini yuboring:\n\n"
            "🎵 Qo'shiq yoki ijrochi nomi\n"
            "🔤 Qo'shiq matni\n"
            "🎙 Musiqa bilan ovozli xabar\n"
            "📹 Musiqa bilan video\n"
            "🔊 Audioyozuv\n"
            "🎥 Musiqa bilan videoxabar\n"
            "🔗 Instagram, Tik-Tok, YouTube va boshqa saytlarga video havola\n\n"
            "🕺 Rohatlaning!"
        ),
        "select_lang": "Iltimos, tilni tanlang / Пожалуйста, выберите язык / Please select a language:",
        "premium_btn": "💎 Premium sotib olish (100 ⭐️)",
        "search_status": "🔍 Qidirilmoqda: «{}»...",
        "no_results": "❌ Hech narsa topilmadi.",
        "yt_detected": "🔗 YouTube havola aniqlandi! Nima yuklaymiz?",
        "dl_audio": "🎵 Audio",
        "dl_video": "🎬 Video",
        "premium_info": "✅ Sizda Premium statusi faol! 🚀",
        "pay_desc": "Premium bilan AI funksiyalar va cheksiz tezlikka ega bo'ling!",
        "success_pay": "🎉 Tabriklaymiz! Siz endi Premium foydalanuvchisiz! 💎\n(100 Stars + 10 Stars komissiya)",
        "back": "⬅️ Orqaga"
    },
    "ru": {
        "welcome": (
            "👋 Привет!\n"
            "Я помогу найти музыку 🎶, отправь мне что-то из этого:\n\n"
            "🎵 Название песни или исполнителя\n"
            "🔤 Слова из песни\n"
            "🎙 Голосовое сообщение с музыкой\n"
            "📹 Видео с музыкой\n"
            "🔊 Аудиозапись\n"
            "🎥 Видеосообщение с музыкой\n"
            "🔗 Ссылку на видео в Instagram, Tik-Tok, YouTube и другие сайты\n\n"
            "🕺 Наслаждайся!"
        ),
        "select_lang": "Пожалуйста, выберите язык:",
        "premium_btn": "💎 Купить Premium (100 ⭐️)",
        "search_status": "🔍 Ищу: «{}»...",
        "no_results": "❌ Ничего не найдено.",
        "yt_detected": "🔗 YouTube ссылка обнаружена! Что скачать?",
        "dl_audio": "🎵 Аудио",
        "dl_video": "🎬 Видео",
        "premium_info": "✅ У вас активен Premium статус! 🚀",
        "pay_desc": "С Premium вы получите AI функции и максимальную скорость!",
        "success_pay": "🎉 Поздравляем! Вы теперь Premium пользователь! 💎\n(100 Stars + 10 Stars комиссия)",
        "back": "⬅️ Назад"
    },
    "en": {
        "welcome": (
            "👋 Hi!\n"
            "I'll help you find music 🎶 send me some of this:\n\n"
            "🎵 Song title or artist\n"
            "🔤 Lyrics from the song\n"
            "🎙 Voice message with music\n"
            "📹 Video with music\n"
            "🔊 Audio recording\n"
            "🎥 Video message with music\n"
            "🔗 Link the video to Instagram, Tik-Tok, YouTube and other sites\n\n"
            "🕺 Enjoy!"
        ),
        "select_lang": "Please select a language:",
        "premium_btn": "💎 Buy Premium (100 ⭐️)",
        "search_status": "🔍 Searching for: «{}»...",
        "no_results": "❌ No results found.",
        "yt_detected": "🔗 YouTube link detected! What to download?",
        "dl_audio": "🎵 Audio",
        "dl_video": "🎬 Video",
        "premium_info": "✅ You have active Premium status! 🚀",
        "pay_desc": "Get AI features and unlimited speed with Premium!",
        "success_pay": "🎉 Congratulations! You are now a Premium user! 💎\n(100 Stars + 10 Stars commission)",
        "back": "⬅️ Back"
    }
}

# ─────────────────────────────────────────────────────────────
#  Keyboards
# ─────────────────────────────────────────────────────────────
def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇺🇿 O'zbekcha", callback_data="setlang_uz")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="setlang_ru")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="setlang_en")]
    ])

def main_reply_keyboard(user_id):
    lang = get_lang(user_id)
    btn_text = STRINGS[lang]["premium_btn"] if not is_premium(user_id) else STRINGS[lang]["premium_info"]
    keyboard = [[KeyboardButton(btn_text)]]
    
    # Admin bo'lsa, Admin Panel tugmasini qo'shish
    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton("📊 Admin Panel")])
        
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📈 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton("📢 Reklama yuborish", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👤 Foydalanuvchilar", callback_data="admin_users_list")]
    ])

def vkm_style_keyboard(results):
    buttons = []
    row = []
    for i in range(len(results)):
        row.append(InlineKeyboardButton(str(i+1), callback_data=f"track_{i}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)

# ─────────────────────────────────────────────────────────────
#  Core Functions
# ─────────────────────────────────────────────────────────────
async def search_music(query):
    url = f"https://itunes.apple.com/search?term={quote(query)}&media=music&entity=song&limit=8"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("results", [])
    return []

# ─────────────────────────────────────────────────────────────
#  Handlers
# ─────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # Yangi user bo'lsa adminga xabar berish
    is_new = add_user(user)
    if is_new and ADMIN_ID != 0:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🆕 **Yangi foydalanuvchi!**\n👤 Ism: {user.first_name}\n🆔 ID: `{user_id}`\n🔗 Username: @{user.username or 'yoq'}",
                parse_mode="Markdown"
            )
        except: pass

    if str(user_id) not in DATA["languages"]:
        await update.message.reply_text(STRINGS["ru"]["select_lang"], reply_markup=lang_keyboard())
    else:
        lang = get_lang(user_id)
        await update.message.reply_text(
            STRINGS[lang]["welcome"],
            reply_markup=main_reply_keyboard(user_id)
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user = update.effective_user
    user_id = user.id
    lang = get_lang(user_id)
    
    # Admin Panel Check
    if text == "📊 Admin Panel" and user_id == ADMIN_ID:
        await update.message.reply_text("🛠 **Admin Panelga xush kelibsiz!**", reply_markup=admin_keyboard(), parse_mode="Markdown")
        return

    # Premium Button Check
    if "Premium" in text or "💎" in text:
        if is_premium(user_id):
            await update.message.reply_text(STRINGS[lang]["premium_info"])
        else:
            await send_premium_invoice(update, context)
        return

    # YouTube Check
    yt_pattern = r'(https?://)?(www\.)?(youtube\.com|youtu\.?be|tiktok\.com|instagram\.com)/.+'
    if re.match(yt_pattern, text):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(STRINGS[lang]["dl_audio"], callback_data=f"yt_dl_a|{text}")],
            [InlineKeyboardButton(STRINGS[lang]["dl_video"], callback_data=f"yt_dl_v|{text}")]
        ])
        await update.message.reply_text(STRINGS[lang]["yt_detected"], reply_markup=keyboard)
        return

    # Search
    status = await update.message.reply_text(STRINGS[lang]["search_status"].format(text))
    results = await search_music(text)
    
    if not results:
        await status.edit_text(STRINGS[lang]["no_results"])
        return
        
    context.user_data["last_results"] = results
    
    response_text = ""
    for i, t in enumerate(results):
        artist = t.get("artistName", "Unknown")
        title = t.get("trackName", "Unknown")
        duration_ms = t.get("trackTimeMillis", 0)
        duration = f"{duration_ms // 60000}:{(duration_ms % 60000) // 1000:02d}"
        response_text += f"{i+1}. **{artist}** — {title} ({duration})\n"
    
    await status.edit_text(
        response_text,
        parse_mode="Markdown",
        reply_markup=vkm_style_keyboard(results)
    )

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    lang = get_lang(user_id)
    
    await query.answer()
    
    if data.startswith("setlang_"):
        lang_code = data.split("_")[1]
        DATA["languages"][str(user_id)] = lang_code
        save_data(DATA)
        await query.message.delete()
        await context.bot.send_message(chat_id=user_id, text=STRINGS[lang_code]["welcome"], reply_markup=main_reply_keyboard(user_id))
    
    elif data.startswith("track_"):
        idx = int(data.split("_")[1])
        results = context.user_data.get("last_results", [])
        if idx < len(results):
            track = results[idx]
            preview = track.get("previewUrl")
            artist = track.get("artistName")
            title = track.get("trackName")
            await query.message.reply_audio(audio=preview, title=title, performer=artist, caption=f"🎵 {artist} - {title}\n\n@MaxMusicBot")
            
    # Admin Actions
    elif data == "admin_stats" and user_id == ADMIN_ID:
        total_users = len(DATA["users"])
        premium_users = len(DATA["premium"])
        await query.message.edit_text(f"📈 **Bot Statistikasi:**\n\n👥 Jami foydalanuvchilar: {total_users}\n💎 Premium foydalanuvchilar: {premium_users}", parse_mode="Markdown", reply_markup=admin_keyboard())
        
    elif data == "admin_broadcast" and user_id == ADMIN_ID:
        await query.message.reply_text("📝 **Reklama xabarini yuboring.**\nBarcha foydalanuvchilarga yuboriladi.")
        context.user_data["admin_state"] = "waiting_broadcast"

    elif data == "admin_users_list" and user_id == ADMIN_ID:
        users_text = "👤 **Oxirgi foydalanuvchilar (ID):**\n" + "\n".join([str(uid) for uid in DATA["users"][-10:]])
        await query.message.edit_text(users_text, reply_markup=admin_keyboard())

# ─────────────────────────────────────────────────────────────
#  Broadcast Logic
# ─────────────────────────────────────────────────────────────
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("admin_state") == "waiting_broadcast" and update.effective_user.id == ADMIN_ID:
        text = update.message.text
        count = 0
        for uid in DATA["users"]:
            try:
                await context.bot.send_message(chat_id=uid, text=text)
                count += 1
                await asyncio.sleep(0.05) # Flood protection
            except: pass
        await update.message.reply_text(f"✅ Reklama {count} ta foydalanuvchiga yuborildi.")
        context.user_data["admin_state"] = None

# ─────────────────────────────────────────────────────────────
#  Payments
# ─────────────────────────────────────────────────────────────
async def send_premium_invoice(update, context):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    await context.bot.send_invoice(
        chat_id=user_id,
        title="MaxMusic Premium 💎",
        description=STRINGS[lang]["pay_desc"] + "\n\nFee: 10 Stars",
        payload=f"premium_{user_id}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice("Premium", PREMIUM_PRICE)]
    )

async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def success_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = get_lang(user_id)
    if user_id not in DATA["premium"]:
        DATA["premium"].append(user_id)
        save_data(DATA)
    await update.message.reply_text(STRINGS[lang]["success_pay"], reply_markup=main_reply_keyboard(user_id))

# ─────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_query_handler))
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, success_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, handle_broadcast))
    
    logger.info("Bot started with Admin Panel!")
    app.run_polling()

if __name__ == "__main__":
    main()
