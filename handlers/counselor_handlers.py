import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import config
import database
from handlers.common import (
    forward_to_seeker,
    broadcast_new_case_to_counselors
)

logger = logging.getLogger(__name__)

async def counselor_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Control panel welcome for authorized counselors.
    """
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Waiting Feed", callback_data="btn:feed"),
            InlineKeyboardButton("Active Chat", callback_data="btn:active")
        ],
        [
            InlineKeyboardButton("Statistics", callback_data="btn:stats"),
            InlineKeyboardButton("Help & Guide", callback_data="btn:help")
        ]
    ])

    text = (
        "Counselor Control Panel\n\n"
        f"Welcome to the {config.BOT_NAME} counselor portal.\n"
        "You are recognized as an authorized counselor.\n\n"
        "Commands:\n"
        "/feed or /cases - View feed of new users waiting for counsel\n"
        "/active - View the user you are currently chatting with\n"
        "/close - Conclude and close your active session\n"
        "/release - Return your active user back to the feed\n"
        "/stats - View counseling statistics\n"
        "/reload - Reload counselor list from .env\n"
        "/myid - View your numeric Telegram user ID\n"
        "/help - View full guide\n\n"
        "Choose an option below or type a command:"
    )

    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)

async def feed_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays the feed of new users waiting to be counseled.
    Counselor can select any user to begin chatting.
    """
    pending = database.get_pending_cases(limit=10)
    
    if not pending:
        text = (
            "Counselor Feed\n\n"
            "The feed is currently clear. No users are waiting right now.\n"
            "You will be notified as soon as a new user sends a message."
        )
        refresh_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Refresh Feed", callback_data="btn:feed")]
        ])
        if update.message:
            await update.message.reply_text(text, reply_markup=refresh_kb)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=refresh_kb)
        return

    text = f"Counselor Feed ({len(pending)} waiting):\n\n"
    keyboard_buttons = []

    for item in pending:
        cid = item["case_id"]
        q = item["initial_question"] or "[No preview text]"
        short_q = (q[:120] + "...") if len(q) > 120 else q
        text += f"Anonymous User #{cid}:\n\"{short_q}\"\n\n"
        keyboard_buttons.append([
            InlineKeyboardButton(f"Select User #{cid} & Chat", callback_data=f"claim:{cid}")
        ])

    keyboard_buttons.append([
        InlineKeyboardButton("Refresh Feed", callback_data="btn:feed")
    ])

    reply_markup = InlineKeyboardMarkup(keyboard_buttons)
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

async def active_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Shows details of the user the counselor is currently chatting with.
    """
    counselor_id = update.effective_user.id
    active_case = database.get_active_case_for_counselor(counselor_id)

    if not active_case:
        text = (
            "Active Session\n\n"
            "You are not currently chatting with any user.\n"
            "Use /feed to select a waiting user and begin counseling."
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("View Waiting Feed", callback_data="btn:feed")]
        ])
        if update.message:
            await update.message.reply_text(text, reply_markup=kb)
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=kb)
        return

    cid = active_case["case_id"]
    claimed_at = active_case["claimed_at"] or "Recently"
    q = active_case["initial_question"] or "[No preview]"

    text = (
        f"Active Counseling Session\n\n"
        f"User: Anonymous User #{cid}\n"
        f"Connected: {claimed_at}\n\n"
        f"Initial Message:\n\"{q}\"\n\n"
        "Live Mode Active: Any regular message, voice note, or media you send here "
        "will be delivered directly and anonymously to the user.\n\n"
        "When finished, use /close to conclude the session."
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("End Session", callback_data=f"close:{cid}"),
            InlineKeyboardButton("Release to Feed", callback_data=f"release:{cid}")
        ]
    ])

    if update.message:
        await update.message.reply_text(text, reply_markup=kb)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb)

async def close_command_counselor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Counselor concludes counseling session with their selected user.
    """
    counselor_id = update.effective_user.id
    active_case = database.get_active_case_for_counselor(counselor_id)

    if not active_case:
        await update.message.reply_text(
            "You do not have an active counseling session to close.\n"
            "Use /feed to view waiting users."
        )
        return

    cid = active_case["case_id"]
    seeker_id = active_case["seeker_id"]

    # Close in database
    database.close_case(cid, closed_by="COUNSELOR")

    # Notify counselor
    await update.message.reply_text(
        f"Session with User #{cid} concluded successfully.\n"
        "You are now free. Check /feed to select another waiting user."
    )

    # Notify seeker
    try:
        closing_note = (
            "Your counseling session has been concluded by the counselor.\n\n"
            "Thank you for reaching out to AMU-ECSF Counseling. We pray that God guides, "
            "comforts, and strengthens you on your journey.\n\n"
            "If you ever need counsel again in the future, simply send /start or type a new question anytime. "
            "You are always welcome."
        )
        await context.bot.send_message(chat_id=seeker_id, text=closing_note)
    except Exception as e:
        logger.warning(f"Could not deliver session end note to seeker {seeker_id}: {e}")

async def release_command_counselor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Counselor releases active user back to the feed.
    """
    counselor_id = update.effective_user.id
    active_case = database.get_active_case_for_counselor(counselor_id)

    if not active_case:
        await update.message.reply_text(
            "You do not have an active session to release."
        )
        return

    cid = active_case["case_id"]
    seeker_id = active_case["seeker_id"]
    initial_q = active_case["initial_question"] or ""

    success = database.release_case(cid, counselor_id)
    if not success:
        await update.message.reply_text("Could not release this user.")
        return

    await update.message.reply_text(
        f"User #{cid} has been returned to the feed for other counselors to take."
    )

    # Notify seeker
    try:
        await context.bot.send_message(
            chat_id=seeker_id,
            text=(
                "Your counselor had to step away. Your request has been returned to the queue, "
                "and another counselor from our team will join you shortly. "
                "Thank you for your patience."
            )
        )
    except Exception as e:
        logger.warning(f"Could not notify seeker {seeker_id} of release: {e}")

    # Re-post to counselors' feed
    await broadcast_new_case_to_counselors(context, cid, initial_q)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays counseling statistics.
    """
    stats = database.get_statistics()
    text = (
        "Counseling Bot Statistics\n\n"
        f"Total Users Counseled: {stats['total']}\n"
        f"Waiting in Feed: {stats['pending']}\n"
        f"Active Sessions: {stats['active']}\n"
        f"Completed Sessions: {stats['closed']}\n"
    )
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text, 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="btn:start")]])
        )

async def reload_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Reloads configurations from .env at runtime.
    """
    config.reload_config()
    await update.message.reply_text(
        f"Configuration reloaded from .env.\n"
        f"Active counselors count: {len(config.COUNSELOR_IDS)}\n"
        f"Counselor Group ID: {config.COUNSELOR_GROUP_ID or 'Not set'}"
    )

async def handle_counselor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles all counselor inline button presses from feed and controls.
    """
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if not config.is_counselor(user_id):
        await query.answer("Access restricted to authorized counselors.", show_alert=True)
        return

    # Button shortcuts
    if data in ("btn:feed", "btn:cases"):
        await feed_command(update, context)
        return
    elif data == "btn:active":
        await active_command(update, context)
        return
    elif data == "btn:stats":
        await stats_command(update, context)
        return
    elif data == "btn:help":
        await query.edit_message_text(
            config.HELP_MESSAGE_COUNSELOR,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="btn:start")]])
        )
        return
    elif data == "btn:start":
        await counselor_start(update, context)
        return

    # Action: Claim / Select User (claim:<case_id>)
    if data.startswith("claim:"):
        case_id_str = data.split(":", 1)[1]
        if not case_id_str.isdigit():
            return
        case_id = int(case_id_str)

        success, msg, case_data = database.claim_case(case_id, user_id)
        if not success:
            await query.answer(msg, show_alert=True)
            try:
                await query.edit_message_text(
                    f"Notice regarding User #{case_id}:\n{msg}",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("View Waiting Feed", callback_data="btn:feed")]])
                )
            except Exception:
                pass
            return

        seeker_id = case_data["seeker_id"]
        q_text = case_data["initial_question"] or ""

        # Update the clicked message in feed
        await query.edit_message_text(
            f"User #{case_id} Selected\n\n"
            f"Initial Message:\n\"{q_text}\"\n\n"
            "You are now chatting anonymously with this user. "
            "Every message, voice note, or photo you send in this bot chat will be delivered directly to the user.\n\n"
            "When finished, use /close to conclude the session.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("End Session", callback_data=f"close:{case_id}")]
            ])
        )

        # Notify seeker
        try:
            seeker_notify_text = (
                "A counselor has connected to your session.\n\n"
                "You are now in a private, confidential counseling chat. "
                "Feel free to share your thoughts openly and safely."
            )
            await context.bot.send_message(chat_id=seeker_id, text=seeker_notify_text)
        except Exception as e:
            logger.error(f"Failed to notify seeker {seeker_id} on select: {e}")
        return

    # Action: Close a session from inline button (close:<case_id>)
    if data.startswith("close:"):
        case_id_str = data.split(":", 1)[1]
        if not case_id_str.isdigit():
            return
        case_id = int(case_id_str)
        case_row = database.get_case(case_id)
        if not case_row or case_row["counselor_id"] != user_id or case_row["status"] != "ACTIVE":
            await query.answer("This session is no longer active with you.", show_alert=True)
            return

        seeker_id = case_row["seeker_id"]
        database.close_case(case_id, closed_by="COUNSELOR")

        await query.edit_message_text(
            f"Session with User #{case_id} has been concluded and closed.\n"
            "You are now free to select another user.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("View Waiting Feed", callback_data="btn:feed")]])
        )

        try:
            closing_note = (
                "Your counseling session has been concluded by the counselor.\n\n"
                "Thank you for reaching out to AMU-ECSF Counseling. We pray that God guides, "
                "comforts, and strengthens you on your journey.\n\n"
                "If you ever need counsel again in the future, simply send /start or type a new question anytime. "
                "You are always welcome."
            )
            await context.bot.send_message(chat_id=seeker_id, text=closing_note)
        except Exception as e:
            logger.warning(f"Could not deliver closing note to seeker {seeker_id}: {e}")
        return

    # Action: Release a session from inline button (release:<case_id>)
    if data.startswith("release:"):
        case_id_str = data.split(":", 1)[1]
        if not case_id_str.isdigit():
            return
        case_id = int(case_id_str)
        case_row = database.get_case(case_id)
        if not case_row or case_row["counselor_id"] != user_id or case_row["status"] != "ACTIVE":
            await query.answer("This session is no longer active with you.", show_alert=True)
            return

        seeker_id = case_row["seeker_id"]
        initial_q = case_row["initial_question"] or ""
        database.release_case(case_id, user_id)

        await query.edit_message_text(
            f"User #{case_id} has been returned to the feed for other counselors to take.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("View Waiting Feed", callback_data="btn:feed")]])
        )

        try:
            await context.bot.send_message(
                chat_id=seeker_id,
                text=(
                    "Your counselor had to step away. Your request has been returned to the queue, "
                    "and another counselor from our team will join you shortly. "
                    "Thank you for your patience."
                )
            )
        except Exception as e:
            logger.warning(f"Could not notify seeker {seeker_id}: {e}")

        await broadcast_new_case_to_counselors(context, case_id, initial_q)
        return

async def handle_counselor_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles regular messages (text, photos, voice notes, etc.) sent by a counselor.
    Delivers them anonymously to the currently selected user.
    """
    counselor_id = update.effective_user.id
    message = update.message
    if not message:
        return

    active_case = database.get_active_case_for_counselor(counselor_id)

    if not active_case:
        await message.reply_text(
            "You have not selected a user to chat with right now.\n\n"
            "Use /feed to view waiting users and select one to begin counseling."
        )
        return

    cid = active_case["case_id"]
    seeker_id = active_case["seeker_id"]

    success = await forward_to_seeker(context, seeker_id, message, cid)
    if not success:
        await message.reply_text(
            f"Could not deliver your message to User #{cid}. "
            "They may have blocked or stopped the bot."
        )
