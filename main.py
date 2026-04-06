"""
===========================================
  TELEGRAM MUSIC BOT — main.py
  Token: BOT_TOKEN (Replit Secret)
  Admin ID: ADMIN_ID (Replit Secret)
  Qo'shimcha adminlar: EXTRA_ADMIN_IDS
===========================================
"""
import os
import sys
import logging
import asyncio

from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

sys.path.insert(0, os.path.dirname(__file__))

from database import init_db, register_user, is_banned, get_language, log_error
from utils.rate_limit import check_rate_limit
from utils.downloader import is_url, cleanup_old_files
from utils.lang import t
from handlers.user import (
    cmd_start, cmd_help, cmd_favorites, cmd_history,
    cmd_lang, cmd_profile, cmd_cancel,
    handle_delfav_callback, handle_setlang_callback,
)
from handlers.admin import (
    cmd_admin, cmd_ban, cmd_unban, cmd_stats, cmd_addadmin,
    handle_admin_callback, handle_broadcast, is_admin,
)
from handlers.music import (
    cmd_trending, handle_search_query, handle_link, handle_dl_callback,
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "bot.log"),
                            encoding="utf-8"),
    ],
)
for noisy in ("httpx", "httpcore", "telegram.ext.Updater",
              "telegram.ext.Application", "aiohttp"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def _set_commands(app: Application):
    commands = [
        BotCommand("start",     "Botni boshlash"),
        BotCommand("help",      "Yordam"),
        BotCommand("favorites", "❤️ Sevimlilar"),
        BotCommand("history",   "📜 Qidiruv tarixi"),
        BotCommand("profile",   "👤 Profilim"),
        BotCommand("trending",  "🔥 Trend qo'shiqlar"),
        BotCommand("lang",      "🌍 Til tanlash"),
        BotCommand("cancel",    "❌ Bekor qilish"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Bot commands set.")


async def post_init(app: Application):
    await init_db()
    logger.info("✅ Database initialized.")
    cleanup_old_files()
    await _set_commands(app)
    logger.info("🤖 Bot ready.")


async def post_shutdown(app: Application):
    logger.info("Bot stopped.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user = update.effective_user
    text = update.message.text.strip()
    await register_user(user.id, user.username or "", user.first_name or "")
    if await is_banned(user.id):
        lang = await get_language(user.id)
        await update.message.reply_text(t(lang, "banned"))
        return
    if is_admin(user.id) and context.user_data.get("awaiting_broadcast"):
        handled = await handle_broadcast(update, context)
        if handled:
            return
    allowed, wait = check_rate_limit(user.id)
    if not allowed:
        lang = await get_language(user.id)
        await update.message.reply_text(t(lang, "rate_limited", wait=wait))
        return
    if is_url(text):
        await handle_link(update, context, text)
    else:
        await handle_search_query(update, context, text)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    data = query.data or ""
    user = query.from_user
    await register_user(user.id, user.username or "", user.first_name or "")
    if await is_banned(user.id):
        await query.answer("🚫 Bloklangansiz")
        return
    if   data.startswith("delfav_"):  await handle_delfav_callback(update, context)
    elif data.startswith("setlang_"): await handle_setlang_callback(update, context)
    elif data.startswith("admin"):    await handle_admin_callback(update, context)
    else:                             await handle_dl_callback(update, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    err = str(context.error)
    if "Conflict" in err:
        return
    logger.error("Exception:", exc_info=context.error)
    if hasattr(update, "effective_user") and update.effective_user:
        try:
            await log_error(update.effective_user.id, err[:300])
        except Exception:
            pass


def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN topilmadi! Replit Secrets ga qo'shing.")
        sys.exit(1)
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )
    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("favorites", cmd_favorites))
    app.add_handler(CommandHandler("history",   cmd_history))
    app.add_handler(CommandHandler("profile",   cmd_profile))
    app.add_handler(CommandHandler("lang",      cmd_lang))
    app.add_handler(CommandHandler("trending",  cmd_trending))
    app.add_handler(CommandHandler("cancel",    cmd_cancel))
    app.add_handler(CommandHandler("admin",     cmd_admin))
    app.add_handler(CommandHandler("ban",       cmd_ban))
    app.add_handler(CommandHandler("unban",     cmd_unban))
    app.add_handler(CommandHandler("stats",     cmd_stats))
    app.add_handler(CommandHandler("addadmin",  cmd_addadmin))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_error_handler(error_handler)
    app.job_queue.run_repeating(
        lambda ctx: cleanup_old_files(1800), interval=1800, first=1800,
    )
    logger.info("🚀 Bot polling started!")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        close_loop=False,
    )


if __name__ == "__main__":
    main()
