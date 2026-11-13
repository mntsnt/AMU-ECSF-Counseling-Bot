import logging
from telegram import Update
from telegram.ext import ContextTypes
import config
import database
from handlers.common import (
    extract_message_content,
    broadcast_new_case_to_counselors,
    broadcast_pending_update_to_counselors,
    forward_to_counselor
)

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /start for seekers (non-counselors).
    """
    user_id = update.effective_user.id
    
    # Check if user already has an open case
    open_case = database.get_open_case_for_seeker(user_id)
    if open_case:
        status = open_case["status"]
        case_id = open_case["case_id"]
        if status == "ACTIVE":
            await update.message.reply_text(
                f"Welcome back.\n\n"
                f"You have an active confidential session (Case #{case_id}).\n"
                f"Any message you send here is delivered directly to your counselor.\n\n"
                f"To conclude this session, send /close."
            )
            return
        elif status == "PENDING":
            await update.message.reply_text(
                f"Welcome back.\n\n"
                f"Your counseling request (Case #{case_id}) is waiting for an available counselor.\n"
                f"Please wait patiently. Any additional messages you send will be delivered to the counselor upon joining.\n\n"
                f"To cancel your request, send /close."
            )
            return

    # New seeker welcome message
    await update.message.reply_text(config.WELCOME_MESSAGE)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles /help for seekers.
    """
    await update.message.reply_text(config.HELP_MESSAGE_USER)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Checks the status of the seeker's counseling request.
    """
    user_id = update.effective_user.id
    open_case = database.get_open_case_for_seeker(user_id)
    
    if not open_case:
        await update.message.reply_text(
            "You do not have any open counseling requests.\n"
            "Send your question or concern anytime to begin."
        )
        return

    case_id = open_case["case_id"]
    status = open_case["status"]

    if status == "PENDING":
        await update.message.reply_text(
            f"Status: Waiting for Counselor\n"
            f"Case: #{case_id}\n\n"
            "Your question has been received. Our team will connect with you as soon as an available counselor accepts your case.\n"
            "Thank you for your patience."
        )
    elif status == "ACTIVE":
        await update.message.reply_text(
            f"Status: Live Session Active\n"
            f"Case: #{case_id}\n\n"
            "You are connected with a counselor. You can send your messages, voice notes, or questions here.\n"
            "To end the session, use /close."
        )

async def close_command_seeker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Allows a seeker to conclude or cancel their open case.
    """
    user_id = update.effective_user.id
    open_case = database.get_open_case_for_seeker(user_id)

    if not open_case:
        await update.message.reply_text(
            "You do not have an active counseling request to close."
        )
        return

    case_id = open_case["case_id"]
    counselor_id = open_case["counselor_id"]
    was_active = open_case["status"] == "ACTIVE"

    # Close case in database
    database.close_case(case_id, closed_by="SEEKER")

    await update.message.reply_text(
        "Your counseling session has been closed.\n\n"
        "Thank you for reaching out to AMU-ECSF Counseling. "
        "If you ever need support or guidance again, simply send /start or type a new question anytime. You are always welcome."
    )

    # If it was active with a counselor, inform the counselor
    if was_active and counselor_id:
        try:
            await context.bot.send_message(
                chat_id=counselor_id,
                text=f"[Case #{case_id}] was closed by the user.\nYou are now free to take another case."
            )
        except Exception as e:
            logger.warning(f"Could not notify counselor {counselor_id} of user closure: {e}")

async def handle_seeker_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles all incoming messages (text, photo, voice, document, etc.) from seekers.
    """
    user_id = update.effective_user.id
    message = update.message
    if not message:
        return

    content_preview, msg_type = extract_message_content(message)
    open_case = database.get_open_case_for_seeker(user_id)

    # 1. No open case: Create a new counseling case
    if not open_case:
        case_id = database.create_case(seeker_id=user_id, initial_question=content_preview)
        database.log_message(case_id, "SEEKER", msg_type, content_preview)

        # Confirm to seeker
        confirmation_text = (
            "#SENT\n\n"
            "Request received\n\n"
            "Please Wait for the Response Patiently\n\n"
            f"Your Question:\n{content_preview}"
        )
        await message.reply_text(confirmation_text)

        # Notify all counselors
        await broadcast_new_case_to_counselors(context, case_id, content_preview)
        return

    # 2. Case is PENDING (waiting for counselor to claim)
    case_id = open_case["case_id"]
    status = open_case["status"]

    if status == "PENDING":
        database.log_message(case_id, "SEEKER", msg_type, content_preview)
        await message.reply_text(
            "#QUESTION\n\n"
            "Your message has been added to your request. Please wait patiently for a counselor."
        )
        # Notify counselors of update
        await broadcast_pending_update_to_counselors(context, case_id, message)
        return

    # 3. Case is ACTIVE (live counseling session)
    if status == "ACTIVE":
        counselor_id = open_case["counselor_id"]
        if not counselor_id:
            await message.reply_text(
                "A counselor is being assigned. Please wait a moment."
            )
            return

        success = await forward_to_counselor(context, counselor_id, message, case_id)
        if not success:
            await message.reply_text(
                "We had trouble delivering your message. Please try sending it again in a moment."
            )
