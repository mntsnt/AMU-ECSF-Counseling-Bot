import sys
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

import config
import database
from handlers.user_handlers import (
    start_command as seeker_start,
    help_command as seeker_help,
    status_command as seeker_status,
    close_command_seeker,
    handle_seeker_message
)
from handlers.counselor_handlers import (
    counselor_start,
    feed_command,
    active_command,
    close_command_counselor,
    release_command_counselor,
    stats_command,
    reload_command,
    handle_counselor_callback,
    handle_counselor_message
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("CounselingBot")

# Quiet down noisy HTTP loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

async def dispatch_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes /start depending on whether sender is an authorized counselor or seeker."""
    user_id = update.effective_user.id
    if config.is_counselor(user_id):
        await counselor_start(update, context)
    else:
        await seeker_start(update, context)

async def dispatch_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes /help depending on role."""
    user_id = update.effective_user.id
    if config.is_counselor(user_id):
        await update.message.reply_text(config.HELP_MESSAGE_COUNSELOR)
    else:
        await seeker_help(update, context)

async def dispatch_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes /status depending on role."""
    user_id = update.effective_user.id
    if config.is_counselor(user_id):
        await active_command(update, context)
    else:
        await seeker_status(update, context)

async def dispatch_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes /close depending on role."""
    user_id = update.effective_user.id
    if config.is_counselor(user_id):
        await close_command_counselor(update, context)
    else:
        await close_command_seeker(update, context)

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Replies with the user's numeric Telegram ID for easy setup in .env."""
    user_id = update.effective_user.id
    is_counselor = config.is_counselor(user_id)
    role_text = "Authorized Counselor" if is_counselor else "Seeker / User"

    text = (
        f"Your Telegram User ID is: {user_id}\n"
        f"Role: {role_text}\n\n"
        "If you are a counselor or administrator, paste this ID into "
        "COUNSELOR_IDS in the bot's .env file."
    )
    await update.message.reply_text(text)

async def counselor_only_guard(update: Update, context: ContextTypes.DEFAULT_TYPE, handler_func):
    """Guards counselor commands from unauthorized users."""
    user_id = update.effective_user.id
    if not config.is_counselor(user_id):
        await update.message.reply_text(
            "This command is restricted to authorized counselors."
        )
        return
    await handler_func(update, context)

async def dispatch_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes incoming non-command messages (text, photos, voice notes, files, etc.)."""
    user_id = update.effective_user.id
    if config.is_counselor(user_id):
        await handle_counselor_message(update, context)
    else:
        await handle_seeker_message(update, context)

async def post_init(application) -> None:
    """Sets standard menu commands on startup."""
    try:
        commands = [
            BotCommand("start", "Start or restart the bot"),
            BotCommand("feed", "View waiting users (Counselors)"),
            BotCommand("status", "Check counseling status"),
            BotCommand("close", "Conclude counseling session"),
            BotCommand("myid", "View your Telegram User ID"),
            BotCommand("help", "Help and information"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands registered successfully.")
    except Exception as e:
        logger.warning(f"Could not register bot commands menu: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs unexpected exceptions."""
    logger.error("Exception while handling an update:", exc_info=context.error)

def main() -> None:
    """Entry point to launch the bot."""
    print("=" * 60)
    print(f"Starting {config.BOT_NAME}...")
    print("=" * 60)

    # 1. Initialize Database
    try:
        database.init_db()
        print(f"[OK] Database initialized at: {config.DATABASE_PATH.name}")
    except Exception as e:
        print(f"[ERROR] Could not initialize database: {e}")
        sys.exit(1)

    # 2. Check Bot Token
    token = config.BOT_TOKEN
    if not token or token == "your_bot_token_here":
        print("\n" + "!" * 60)
        print("[SETUP REQUIRED] Telegram Bot Token is missing in .env!")
        print("Please open .env in this folder:")
        print(f"  {config.BASE_DIR / '.env'}")
        print("and set BOT_TOKEN to your token from @BotFather.")
        print("!" * 60 + "\n")
        sys.exit(1)

    # 3. Inform about counselors
    counselor_count = len(config.COUNSELOR_IDS)
    if counselor_count == 0:
        print("[NOTICE] No counselor IDs configured yet in .env.")
        print("Counselors will not receive notifications until their Telegram User IDs")
        print("are added to COUNSELOR_IDS in .env.")
        print("Send /myid to the bot to get your Telegram User ID.")
    else:
        print(f"[OK] Loaded {counselor_count} authorized counselor ID(s): {config.COUNSELOR_IDS}")

    if config.COUNSELOR_GROUP_ID:
        print(f"[OK] Counselor Team Group ID configured: {config.COUNSELOR_GROUP_ID}")

    # 4. Build application
    application = (
        ApplicationBuilder()
        .token(token)
        .post_init(post_init)
        .build()
    )

    # 5. Register Command Handlers
    application.add_handler(CommandHandler("start", dispatch_start))
    application.add_handler(CommandHandler("help", dispatch_help))
    application.add_handler(CommandHandler("status", dispatch_status))
    application.add_handler(CommandHandler("close", dispatch_close))
    application.add_handler(CommandHandler("cancel", dispatch_close))
    application.add_handler(CommandHandler("myid", myid_command))

    # Counselor-specific commands
    application.add_handler(CommandHandler("feed", lambda u, c: counselor_only_guard(u, c, feed_command)))
    application.add_handler(CommandHandler("cases", lambda u, c: counselor_only_guard(u, c, feed_command)))
    application.add_handler(CommandHandler("pending", lambda u, c: counselor_only_guard(u, c, feed_command)))
    application.add_handler(CommandHandler("active", lambda u, c: counselor_only_guard(u, c, active_command)))
    application.add_handler(CommandHandler("release", lambda u, c: counselor_only_guard(u, c, release_command_counselor)))
    application.add_handler(CommandHandler("stats", lambda u, c: counselor_only_guard(u, c, stats_command)))
    application.add_handler(CommandHandler("reload", lambda u, c: counselor_only_guard(u, c, reload_command)))

    # Inline Keyboard Callbacks
    application.add_handler(CallbackQueryHandler(handle_counselor_callback))

    # General Messages (Text, Photos, Voice notes, Audio, Documents, Video, Stickers)
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, dispatch_message))

    # Error handler
    application.add_error_handler(error_handler)

    print(f"\n[OK] {config.BOT_NAME} is online and listening for updates...")
    print("Press Ctrl+C to stop.\n")

    # 6. Run Polling
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
