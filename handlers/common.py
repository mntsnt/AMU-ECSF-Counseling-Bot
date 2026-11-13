import logging
from typing import Optional
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Message
from telegram.ext import ContextTypes
import config
import database

logger = logging.getLogger(__name__)

def extract_message_content(message: Message) -> tuple[str, str]:
    """
    Extracts text snippet and message type from any incoming Telegram message.
    """
    if message.text:
        return message.text, "text"
    elif message.caption:
        msg_type = "photo" if message.photo else "document" if message.document else "media"
        return message.caption, msg_type
    elif message.photo:
        return "[Photo message]", "photo"
    elif message.voice:
        return "[Voice note]", "voice"
    elif message.audio:
        return "[Audio file]", "audio"
    elif message.document:
        doc_name = message.document.file_name or "document"
        return f"[File: {doc_name}]", "document"
    elif message.video:
        return "[Video message]", "video"
    elif message.sticker:
        return "[Sticker]", "sticker"
    else:
        return "[Media]", "other"

async def broadcast_new_case_to_counselors(
    context: ContextTypes.DEFAULT_TYPE, 
    case_id: int, 
    initial_question: str
) -> None:
    """
    Posts the new seeker into the counselors' feed (private chats and/or group feed).
    """
    preview = (initial_question[:400] + "...") if len(initial_question) > 400 else initial_question
    feed_text = (
        f"🔔 [New Seeker in Feed]\n"
        f"👤 User: Anonymous Seeker #{case_id}\n"
        f"⏳ Status: Waiting for Counselor\n\n"
        f"💬 Question:\n\"{preview}\"\n\n"
        "Click below to claim this case and begin counseling:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💬 Chat with User #{case_id}", callback_data=f"claim:{case_id}")]
    ])

    for cid in config.COUNSELOR_IDS:
        try:
            await context.bot.send_message(
                chat_id=cid,
                text=feed_text,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Could not send feed alert to counselor {cid}: {e}")

    if config.COUNSELOR_GROUP_ID:
        try:
            await context.bot.send_message(
                chat_id=config.COUNSELOR_GROUP_ID,
                text=feed_text,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Could not post to counselor group {config.COUNSELOR_GROUP_ID}: {e}")

async def broadcast_pending_update_to_counselors(
    context: ContextTypes.DEFAULT_TYPE, 
    case_id: int, 
    message: Message
) -> None:
    """
    Notifies counselors when a seeker adds more messages before being claimed.
    """
    content_text, _ = extract_message_content(message)
    preview = (content_text[:300] + "...") if len(content_text) > 300 else content_text

    alert_text = (
        f"📩 [Feed Update - User #{case_id}]\n"
        f"Seeker added:\n\"{preview}\""
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"💬 Chat with User #{case_id}", callback_data=f"claim:{case_id}")]
    ])

    for cid in config.COUNSELOR_IDS:
        try:
            await context.bot.send_message(
                chat_id=cid,
                text=alert_text,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Could not deliver feed update to counselor {cid}: {e}")

    if config.COUNSELOR_GROUP_ID:
        try:
            await context.bot.send_message(
                chat_id=config.COUNSELOR_GROUP_ID,
                text=alert_text,
                reply_markup=keyboard
            )
        except Exception as e:
            logger.warning(f"Could not deliver feed update to group {config.COUNSELOR_GROUP_ID}: {e}")

async def forward_to_seeker(
    context: ContextTypes.DEFAULT_TYPE,
    seeker_id: int,
    source_message: Message,
    case_id: int
) -> bool:
    """
    Delivers a message from counselor to seeker completely anonymously.
    Prefixes with 'Counselor:'.
    """
    try:
        if source_message.text:
            text = f"Counselor:\n{source_message.text}"
            await context.bot.send_message(chat_id=seeker_id, text=text)
            database.log_message(case_id, "COUNSELOR", "text", source_message.text)
            return True

        if source_message.photo or source_message.video or source_message.document or source_message.audio or source_message.voice:
            caption = f"Counselor:\n{source_message.caption}" if source_message.caption else "Counselor"
            await context.bot.copy_message(
                chat_id=seeker_id,
                from_chat_id=source_message.chat_id,
                message_id=source_message.message_id,
                caption=caption
            )
            _, msg_type = extract_message_content(source_message)
            database.log_message(case_id, "COUNSELOR", msg_type, source_message.caption or "")
            return True

        if source_message.sticker:
            await context.bot.send_message(chat_id=seeker_id, text="Counselor sent a sticker:")
            await context.bot.copy_message(
                chat_id=seeker_id,
                from_chat_id=source_message.chat_id,
                message_id=source_message.message_id
            )
            database.log_message(case_id, "COUNSELOR", "sticker", "")
            return True

        await context.bot.copy_message(
            chat_id=seeker_id,
            from_chat_id=source_message.chat_id,
            message_id=source_message.message_id
        )
        database.log_message(case_id, "COUNSELOR", "other", "")
        return True

    except Exception as e:
        logger.error(f"Error forwarding message to seeker {seeker_id}: {e}")
        return False

async def forward_to_counselor(
    context: ContextTypes.DEFAULT_TYPE,
    counselor_id: int,
    source_message: Message,
    case_id: int
) -> bool:
    """
    Delivers a message from seeker to assigned counselor anonymously.
    Prefixes with '[User #1001]:'.
    """
    try:
        if source_message.text:
            text = f"[User #{case_id}]:\n{source_message.text}"
            await context.bot.send_message(chat_id=counselor_id, text=text)
            database.log_message(case_id, "SEEKER", "text", source_message.text)
            return True

        if source_message.photo or source_message.video or source_message.document or source_message.audio or source_message.voice:
            caption = f"[User #{case_id}]:\n{source_message.caption}" if source_message.caption else f"[User #{case_id}]"
            await context.bot.copy_message(
                chat_id=counselor_id,
                from_chat_id=source_message.chat_id,
                message_id=source_message.message_id,
                caption=caption
            )
            _, msg_type = extract_message_content(source_message)
            database.log_message(case_id, "SEEKER", msg_type, source_message.caption or "")
            return True

        if source_message.sticker:
            await context.bot.send_message(chat_id=counselor_id, text=f"[User #{case_id}] sent a sticker:")
            await context.bot.copy_message(
                chat_id=counselor_id,
                from_chat_id=source_message.chat_id,
                message_id=source_message.message_id
            )
            database.log_message(case_id, "SEEKER", "sticker", "")
            return True

        await context.bot.copy_message(
            chat_id=counselor_id,
            from_chat_id=source_message.chat_id,
            message_id=source_message.message_id
        )
        database.log_message(case_id, "SEEKER", "other", "")
        return True

    except Exception as e:
        logger.error(f"Error forwarding message to counselor {counselor_id}: {e}")
        return False
