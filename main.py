import sys
import json
import asyncio
import logging
from urllib.parse import parse_qs
from typing import Optional
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    Application,
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

async def counselor_only_guard(update: Update, context: ContextTypes.DEFAULT_TYPE, handler_func):
    """Guards counselor commands from unauthorized users."""
    user_id = update.effective_user.id
    if not config.is_counselor(user_id):
        await update.message.reply_text(
            "🔒 This command is restricted to authorized counselors."
        )
        return
    await handler_func(update, context)

async def dispatch_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dispatches inline button callbacks for both seekers and counselors."""
    query = update.callback_query
    data = query.data

    if data == "seeker:close":
        await query.answer()
        await close_command_seeker(update, context)
        return

    await handle_counselor_callback(update, context)

async def dispatch_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Routes incoming non-command messages (text, photos, voice notes, files, etc.)."""
    user_id = update.effective_user.id
    if config.is_counselor(user_id):
        await handle_counselor_message(update, context)
    else:
        await handle_seeker_message(update, context)

async def post_init(application: Application) -> None:
    """Sets standard menu commands on startup."""
    try:
        commands = [
            BotCommand("start", "Start or restart the bot"),
            BotCommand("feed", "View waiting seekers (Counselors)"),
            BotCommand("status", "Check counseling status"),
            BotCommand("close", "Conclude counseling session"),
            BotCommand("help", "Help and information"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("Bot commands registered successfully.")
    except Exception as e:
        logger.warning(f"Could not register bot commands menu: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Logs unexpected exceptions."""
    logger.error("Exception while handling an update:", exc_info=context.error)

def build_application(token: Optional[str] = None) -> Application:
    """Builds and configures the python-telegram-bot Application instance."""
    bot_token = token or config.BOT_TOKEN
    database.init_db()

    app_builder = ApplicationBuilder().token(bot_token)
    application = app_builder.post_init(post_init).build()

    # Commands
    application.add_handler(CommandHandler("start", dispatch_start))
    application.add_handler(CommandHandler("help", dispatch_help))
    application.add_handler(CommandHandler("status", dispatch_status))
    application.add_handler(CommandHandler("close", dispatch_close))
    application.add_handler(CommandHandler("cancel", dispatch_close))

    # Counselor-specific commands
    application.add_handler(CommandHandler("feed", lambda u, c: counselor_only_guard(u, c, feed_command)))
    application.add_handler(CommandHandler("cases", lambda u, c: counselor_only_guard(u, c, feed_command)))
    application.add_handler(CommandHandler("pending", lambda u, c: counselor_only_guard(u, c, feed_command)))
    application.add_handler(CommandHandler("active", lambda u, c: counselor_only_guard(u, c, active_command)))
    application.add_handler(CommandHandler("release", lambda u, c: counselor_only_guard(u, c, release_command_counselor)))
    application.add_handler(CommandHandler("stats", lambda u, c: counselor_only_guard(u, c, stats_command)))
    application.add_handler(CommandHandler("reload", lambda u, c: counselor_only_guard(u, c, reload_command)))

    # Callbacks
    application.add_handler(CallbackQueryHandler(dispatch_callback))

    # Messages
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, dispatch_message))

    # Error handling
    application.add_error_handler(error_handler)

    return application

# Lazy singleton for serverless / webhook mode
_serverless_application: Optional[Application] = None

def get_serverless_application() -> Application:
    global _serverless_application
    if _serverless_application is None:
        _serverless_application = build_application()
    return _serverless_application

# ==============================================================================
# WSGI Entrypoint for Serverless Platforms (Vercel, Render, AWS Lambda, WSGI)
# ==============================================================================
def wsgi_app(environ, start_response):
    """
    Standard WSGI entrypoint that satisfies Vercel, Gunicorn, uWSGI, and Render.
    Handles GET health checks, webhook setup, and incoming POST Telegram updates.
    """
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "/")

    # GET Endpoints
    if method == "GET":
        query_string = environ.get("QUERY_STRING", "")
        params = parse_qs(query_string)

        # Webhook setup helper: /set_webhook?url=https://...
        if path.startswith("/set_webhook"):
            target_url = params.get("url", [None])[0]
            if not target_url:
                host = environ.get("HTTP_HOST", "")
                if host:
                    target_url = f"https://{host}/"

            if target_url:
                try:
                    bot_app = get_serverless_application()
                    async def _set_wh():
                        await bot_app.bot.set_webhook(url=target_url)
                    asyncio.run(_set_wh())
                    resp = json.dumps({
                        "ok": True,
                        "message": f"Webhook registered successfully to: {target_url}"
                    }).encode("utf-8")
                    start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(resp)))])
                    return [resp]
                except Exception as e:
                    resp = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
                    start_response("500 Internal Server Error", [("Content-Type", "application/json"), ("Content-Length", str(len(resp)))])
                    return [resp]
            else:
                resp = json.dumps({
                    "ok": False,
                    "error": "Missing 'url' parameter. Usage: /set_webhook?url=https://your-domain.vercel.app/"
                }).encode("utf-8")
                start_response("400 Bad Request", [("Content-Type", "application/json"), ("Content-Length", str(len(resp)))])
                return [resp]

        # Standard Health Check
        status_data = {
            "status": "online",
            "bot": config.BOT_NAME,
            "mode": "serverless_webhook",
            "message": "AMU-ECSF Counseling Bot is online and operational."
        }
        body = json.dumps(status_data, indent=2).encode("utf-8")
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]

    # POST Webhook Updates from Telegram
    if method == "POST":
        try:
            content_length = int(environ.get("CONTENT_LENGTH", 0))
        except (ValueError, TypeError):
            content_length = 0

        request_body = environ["wsgi.input"].read(content_length)
        if request_body:
            try:
                update_dict = json.loads(request_body.decode("utf-8"))
                
                async def _process():
                    bot_app = get_serverless_application()
                    if not bot_app._initialized:
                        await bot_app.initialize()
                    update = Update.de_json(update_dict, bot_app.bot)
                    await bot_app.process_update(update)

                asyncio.run(_process())
            except Exception as e:
                logger.error(f"Error processing webhook update: {e}", exc_info=True)

        body = b'{"ok": true}'
        start_response("200 OK", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
        return [body]

    body = b'{"error": "Method not allowed"}'
    start_response("405 Method Not Allowed", [("Content-Type", "application/json"), ("Content-Length", str(len(body)))])
    return [body]

# Top-level variables exported specifically for Vercel and WSGI servers
app = wsgi_app
application = wsgi_app
handler = wsgi_app

# ==============================================================================
# Local / Long Polling Runner
# ==============================================================================
def main() -> None:
    """Entry point for local execution or persistent background workers."""
    print("=" * 60)
    print(f"Starting {config.BOT_NAME}...")
    print("=" * 60)

    try:
        database.init_db()
        print(f"[OK] Database initialized at: {config.DATABASE_PATH}")
    except Exception as e:
        print(f"[ERROR] Could not initialize database: {e}")
        sys.exit(1)

    token = config.BOT_TOKEN
    if not token or token == "your_bot_token_here":
        print("\n" + "!" * 60)
        print("[SETUP REQUIRED] Telegram Bot Token is missing in .env!")
        print("Please open .env in this folder:")
        print(f"  {config.BASE_DIR / '.env'}")
        print("and set BOT_TOKEN to your token from @BotFather.")
        print("!" * 60 + "\n")
        sys.exit(1)

    counselor_count = len(config.COUNSELOR_IDS)
    if counselor_count == 0:
        print("[NOTICE] No counselor IDs configured yet in .env.")
        print("Counselors will not receive notifications until their Telegram User IDs")
        print("are added to COUNSELOR_IDS in .env.")
    else:
        print(f"[OK] Loaded {counselor_count} authorized counselor ID(s): {config.COUNSELOR_IDS}")

    if config.COUNSELOR_GROUP_ID:
        print(f"[OK] Counselor Team Group ID configured: {config.COUNSELOR_GROUP_ID}")

    # Build bot application
    bot_app = build_application(token)

    print(f"\n[OK] {config.BOT_NAME} is online and listening for updates (Polling mode)...")
    print("Press Ctrl+C to stop.\n")

    bot_app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
