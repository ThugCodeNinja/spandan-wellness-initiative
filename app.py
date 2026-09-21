import logging

from telegram import Update

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from groq import (
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    EMERGENCY_MESSAGE,
    validate_config,
)

from database import (
    init_db,
    ensure_user,
    set_user_state,
    get_current_case_id,
    set_current_case,
    save_message,
    get_recent_messages,
    get_case_for_user,
    create_case,
    get_case,
    add_case_note,
    reset_user_intake,
)

from llm import (
    conversational_reply,
    extract_intake,
)

from models import (
    merge_intake,
)

from routing import (
    route_intake,
)

from admin import (
    admin_help,
    cases_command,
    case_command,
    close_command,
    reopen_command,
    note_command,
    stats_command,
    admin_callback,
    notify_new_case,
    is_admin,
)


logging.basicConfig(
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
    level=logging.INFO,
)

logger = logging.getLogger(
    "spandan"
)


WELCOME_MESSAGE = """
🌿 Welcome to Spandan.

Spandan connects people with human practitioners who
offer different holistic wellness modalities.

I'd like to understand what you're currently
experiencing so that the Spandan team can review
which type of session may be relevant for you.

This chatbot is for information gathering only.
It does not provide medical diagnosis, emergency
support, or treatment.

What brings you to Spandan today?
"""


COMPLETION_MESSAGE = """
Thank you for sharing that. 🌿

I've recorded your information and sent the intake
to the Spandan team.

A human practitioner will review your responses
and follow up with you regarding the next steps.

The chatbot's intake is not a medical diagnosis
or treatment recommendation.
"""


def intake_is_complete(
    intake
):

    if not intake.get(
        "primary_concern"
    ):
        return False

    supporting_fields = [
        "duration",
        "impact",
        "goals",
        "previous_attempts",
        "relevant_context",
    ]

    supporting_count = sum(
        bool(
            intake.get(field)
        )
        for field in supporting_fields
    )

    return supporting_count >= 2


def build_history(
    telegram_id
):

    rows = get_recent_messages(
        telegram_id,
        limit=20
    )

    return [
        {
            "role": row["role"],
            "content": row["content"],
        }
        for row in rows
    ]


def build_user_summary(
    case_id,
    intake,
    user_name
):

    def list_or_none(values):

        if not values:
            return "Not provided"

        return ", ".join(
            str(value)
            for value in values
        )

    return f"""
🌿 Your Spandan Intake Summary

Case: SP-{case_id:04d}

Thank you for sharing your information.

Here is a summary of what I've captured:

👤 Name
{user_name or "Not provided"}

🧩 Main concern
{intake.get("primary_concern") or "Not provided"}

📌 Details
{intake.get("concern_details") or "Not provided"}

⏳ Duration
{intake.get("duration") or "Not provided"}

💭 Impact
{list_or_none(intake.get("impact"))}

🎯 What you'd like help with
{list_or_none(intake.get("goals"))}

🔄 Previous approaches
{list_or_none(intake.get("previous_attempts"))}

📝 Relevant context
{intake.get("relevant_context") or "Not provided"}

✨ Modality preference
{intake.get("preferred_modality") or "Not provided"}

You can review this summary and let the Spandan
team know if any important information is missing
or incorrect.

Your information has been sent to a human Spandan
practitioner for review.

The automated intake does not determine or communicate
a final modality selection.
"""


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    ensure_user(
        user.id,
        user.full_name,
        user.username
    )

    reset_user_intake(
        user.id
    )

    context.user_data.pop(
        "intake",
        None
    )

    save_message(
        user.id,
        "assistant",
        WELCOME_MESSAGE
    )

    await update.message.reply_text(
        WELCOME_MESSAGE
    )


async def reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    ensure_user(
        user.id,
        user.full_name,
        user.username
    )

    reset_user_intake(
        user.id
    )

    context.user_data.pop(
        "intake",
        None
    )

    message = """
Sure — let's start a new intake. 🌿

What brings you to Spandan today? Please provide a brief description of your main concern 
or reason for seeking support.
"""

    save_message(
        user.id,
        "assistant",
        message
    )

    await update.message.reply_text(
        message
    )


async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    ensure_user(
        user.id,
        user.full_name,
        user.username
    )

    case_id = get_current_case_id(
        user.id
    )

    if not case_id:

        await update.message.reply_text(
            """
You don't currently have an active case.

Use /start to begin a new intake.
"""
        )

        return

    case = get_case(
        case_id
    )

    if not case:

        await update.message.reply_text(
            "No active case found."
        )

        return

    await update.message.reply_text(
        f"""
🌿 Your Spandan intake

Case: SP-{case_id:04d}

Status: {case["status"]}

Your information has been recorded
for practitioner review.
"""
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if is_admin(
        update.effective_user.id
    ):

        await admin_help(
            update,
            context
        )

        return

    await update.message.reply_text(
        """
🌿 Spandan Intake Bot

/start
Start a new intake.

/reset
Start the intake again.

/status
Check your current intake.

/help
Show this help.
"""
    )


async def handle_admin_note_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):
        return False

    case_id = context.user_data.get(
        "awaiting_note_for"
    )

    if not case_id:
        return False

    note = (
        update.message.text
        or ""
    ).strip()

    if not note:

        await update.message.reply_text(
            "Please send a non-empty note."
        )

        return True

    case = get_case(
        case_id
    )

    if not case:

        context.user_data.pop(
            "awaiting_note_for",
            None
        )

        await update.message.reply_text(
            "Case no longer exists."
        )

        return True

    add_case_note(
        case_id,
        update.effective_user.id,
        note
    )

    context.user_data.pop(
        "awaiting_note_for",
        None
    )

    await update.message.reply_text(
        f"📝 Note added to SP-{case_id:04d}."
    )

    return True


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if (
        not update.message
        or not update.message.text
    ):
        return

    # -----------------------------------------------------
    # ADMIN NOTE MODE
    # -----------------------------------------------------

    if await handle_admin_note_message(
        update,
        context
    ):
        return

    # -----------------------------------------------------
    # USER
    # -----------------------------------------------------

    user = update.effective_user

    telegram_id = user.id

    user_message = (
        update.message.text.strip()
    )

    ensure_user(
        telegram_id,
        user.full_name,
        user.username
    )

    # Admins don't participate in normal intake.
    if is_admin(
        telegram_id
    ):

        await update.message.reply_text(
            "Use /admin for the Spandan admin console."
        )

        return

    # -----------------------------------------------------
    # CHECK EXISTING CASE
    # -----------------------------------------------------

    current_case_id = get_current_case_id(
        telegram_id
    )

    if current_case_id:

        case = get_case_for_user(
            telegram_id,
            current_case_id
        )

        if (
            case
            and case["status"] != "CLOSED"
        ):

            await update.message.reply_text(
                """
Your current Spandan intake has already been
submitted for practitioner review.

Use /reset if you want to start a new case.
"""
            )

            return

    save_message(
        telegram_id,
        "user",
        user_message
    )

    try:

        # -------------------------------------------------
        # HISTORY
        # -------------------------------------------------

        history = build_history(
            telegram_id
        )

        # -------------------------------------------------
        # EXTRACT
        # -------------------------------------------------

        extracted = extract_intake(
            history
        )

        previous_intake = (
            context.user_data.get(
                "intake",
                {}
            )
        )

        intake = merge_intake(
            previous_intake,
            extracted
        )

        # -------------------------------------------------
        # ALWAYS CAPTURE TELEGRAM NAME
        # -------------------------------------------------

        if not intake.get(
            "name"
        ):

            intake["name"] = (
                user.full_name
            )

        context.user_data[
            "intake"
        ] = intake

        # -------------------------------------------------
        # SAFETY
        # -------------------------------------------------

        if intake.get(
            "emergency_flag"
        ):

            set_user_state(
                telegram_id,
                "safety"
            )

            safety_message = (
                "I'm sorry you're going through this.\n\n"
                + EMERGENCY_MESSAGE
            )

            save_message(
                telegram_id,
                "assistant",
                safety_message
            )

            await update.message.reply_text(
                safety_message
            )

            return

        # -------------------------------------------------
        # COMPLETE
        # -------------------------------------------------

        if intake_is_complete(
            intake
        ):

            routing = route_intake(
                intake
            )

            case_id = create_case(
                telegram_id,
                intake,
                routing,
                user_name=user.full_name,
                telegram_username=(
                    f"@{user.username}"
                    if user.username
                    else None
                )
            )

            set_current_case(
                telegram_id,
                case_id
            )

            set_user_state(
                telegram_id,
                "completed"
            )

            # ---------------------------------------------
            # ADMIN NOTIFICATION
            # ---------------------------------------------

            await notify_new_case(
                context.application,
                case_id
            )

            # ---------------------------------------------
            # USER SUMMARY
            # ---------------------------------------------

            summary = build_user_summary(
                case_id,
                intake,
                user.full_name
            )

            save_message(
                telegram_id,
                "assistant",
                summary
            )

            await update.message.reply_text(
                summary
            )

            context.user_data.pop(
                "intake",
                None
            )

            return

        # -------------------------------------------------
        # CONTINUE INTAKE
        # -------------------------------------------------

        reply = conversational_reply(
            history
        )

        save_message(
            telegram_id,
            "assistant",
            reply
        )

        await update.message.reply_text(
            reply
        )

    except RateLimitError:

        logger.exception(
            "Groq rate limit"
        )

        await update.message.reply_text(
            """
I'm temporarily receiving too many requests.

Please wait a little and try again.
Your previous information has been retained.
"""
        )

    except (
        APIConnectionError,
        APITimeoutError
    ):

        logger.exception(
            "Groq connection error"
        )

        await update.message.reply_text(
            """
I'm having trouble connecting to the
intake service right now.

Please try again in a moment.
"""
        )

    except Exception:

        logger.exception(
            "Error handling user %s",
            telegram_id
        )

        await update.message.reply_text(
            """
I'm having a temporary problem processing
that.

Please try again in a moment.

Your conversation has been retained.
"""
        )


async def error_handler(
    update,
    context
):

    logger.error(
        "Unhandled Telegram error",
        exc_info=context.error
    )


def main():

    validate_config()

    init_db()

    application = (
        Application
        .builder()
        .token(
            TELEGRAM_BOT_TOKEN
        )
        .build()
    )

    # -----------------------------------------------------
    # USER COMMANDS
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "reset",
            reset
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    # -----------------------------------------------------
    # ADMIN COMMANDS
    # -----------------------------------------------------

    application.add_handler(
        CommandHandler(
            "admin",
            admin_help
        )
    )

    application.add_handler(
        CommandHandler(
            "cases",
            cases_command
        )
    )

    application.add_handler(
        CommandHandler(
            "case",
            case_command
        )
    )

    application.add_handler(
        CommandHandler(
            "close",
            close_command
        )
    )

    application.add_handler(
        CommandHandler(
            "reopen",
            reopen_command
        )
    )

    application.add_handler(
        CommandHandler(
            "note",
            note_command
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats_command
        )
    )

    # -----------------------------------------------------
    # INLINE ADMIN BUTTONS
    # IMPORTANT: registered before normal text handler
    # -----------------------------------------------------

    application.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern=r"^(view|note|review|close|reopen):\d+$"
        )
    )

    # -----------------------------------------------------
    # NORMAL TEXT
    # -----------------------------------------------------

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "Starting Spandan V2..."
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()