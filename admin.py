import json

from datetime import datetime

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)

from telegram.ext import (
    ContextTypes,
)

from config import (
    ADMIN_TELEGRAM_ID,
)

from database import (
    add_case_note,
    get_case,
    get_case_notes,
    get_stats,
    list_cases,
    update_case_status,
)


# =========================================================
# AUTH
# =========================================================


def is_admin(
    user_id
):

    return (
        user_id is not None
        and int(user_id) == int(
            ADMIN_TELEGRAM_ID
        )
    )


# =========================================================
# HELPERS
# =========================================================


def format_case_id(
    case_id
):

    return f"SP-{int(case_id):04d}"


def parse_case_id(
    value
):

    value = value.strip().upper()

    if value.startswith("SP-"):
        value = value[3:]

    try:
        return int(value)

    except ValueError:
        return None


def format_date(
    value
):

    if not value:
        return "Unknown"

    try:

        dt = datetime.fromisoformat(
            value
        )

        return dt.strftime(
            "%d %b %Y, %H:%M UTC"
        )

    except Exception:

        return value


def _load_intake(
    case
):

    try:

        return json.loads(
            case["intake_data"]
            or "{}"
        )

    except Exception:

        return {}


def format_list(
    values
):

    if not values:
        return "Not provided"

    return "\n".join(
        f"• {value}"
        for value in values
    )


# =========================================================
# KEYBOARD
# =========================================================


def admin_keyboard(
    case_id,
    status
):

    case_id = int(case_id)

    buttons = [
        [
            InlineKeyboardButton(
                "👁 View Case",
                callback_data=f"view:{case_id}"
            ),
            InlineKeyboardButton(
                "📝 Add Note",
                callback_data=f"note:{case_id}"
            ),
        ]
    ]

    if status == "CLOSED":

        buttons.append(
            [
                InlineKeyboardButton(
                    "🔄 Reopen Case",
                    callback_data=f"reopen:{case_id}"
                )
            ]
        )

    elif status == "NEW":

        buttons.append(
            [
                InlineKeyboardButton(
                    "👨‍💼 Start Review",
                    callback_data=f"review:{case_id}"
                ),
                InlineKeyboardButton(
                    "✅ Close",
                    callback_data=f"close:{case_id}"
                ),
            ]
        )

    else:

        buttons.append(
            [
                InlineKeyboardButton(
                    "✅ Close Case",
                    callback_data=f"close:{case_id}"
                )
            ]
        )

    return InlineKeyboardMarkup(
        buttons
    )


# =========================================================
# CASE FORMAT
# =========================================================


def build_case_text(
    case,
    include_notes=True
):

    intake = _load_intake(
        case
    )

    try:

        scores = json.loads(
            case["routing_scores"]
            or "{}"
        )

    except Exception:

        scores = {}

    user_name = (
        case["user_name"]
        or intake.get("name")
        or "Not provided"
    )

    telegram_username = (
        case["telegram_username"]
        or "Not available"
    )

    text = f"""
🌿 SPANDAN CASE

Case: {format_case_id(case["id"])}
Status: {case["status"]}

Created:
{format_date(case["created_at"])}

Updated:
{format_date(case["updated_at"])}


👤 USER

Name:
{user_name}

Telegram username:
{telegram_username}

Telegram ID:
{case["telegram_id"]}


🧩 INTAKE

Primary concern:
{intake.get("primary_concern") or "Not provided"}


Concern details:
{intake.get("concern_details") or "Not provided"}


Duration:
{intake.get("duration") or "Not provided"}


Impact:
{format_list(intake.get("impact"))}


Goals:
{format_list(intake.get("goals"))}


Previous attempts:
{format_list(intake.get("previous_attempts"))}


Relevant context:
{intake.get("relevant_context") or "Not provided"}


Preferred modality:
{intake.get("preferred_modality") or "Not provided"}


Modality interests:
{format_list(intake.get("modality_interest"))}


Additional notes:
{intake.get("additional_notes") or "Not provided"}


⚠️ SAFETY FLAG

{bool(intake.get("emergency_flag", False))}


✨ AUTOMATED INTERNAL ROUTING

Suggested modality:
{case["suggested_modality"] or "Human practitioner review"}


Scores:
"""

    for modality, score in scores.items():

        text += (
            f"\n• {modality}: {score}"
        )

    text += f"""


Routing reason:

{case["routing_reason"] or "Not available"}


This is an automated internal triage signal.
Human practitioner review is required.
"""

    if include_notes:

        notes = get_case_notes(
            case["id"]
        )

        text += "\n\n📝 INTERNAL NOTES\n"

        if not notes:

            text += "\nNo notes yet."

        else:

            for note in notes:

                text += (
                    f"\n\n"
                    f"{format_date(note['created_at'])}\n"
                    f"{note['note']}"
                )

    return text


# =========================================================
# ADMIN NOTIFICATION
# =========================================================


async def notify_new_case(
    application,
    case_id
):

    case = get_case(
        case_id
    )

    if not case:
        return

    text = (
        "🔔 NEW SPANDAN CASE\n\n"
        + build_case_text(
            case,
            include_notes=False
        )
    )

    await application.bot.send_message(

        chat_id=ADMIN_TELEGRAM_ID,

        text=text,

        reply_markup=admin_keyboard(
            case_id,
            case["status"]
        )
    )


# =========================================================
# ADMIN HELP
# =========================================================


async def admin_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):

        await update.message.reply_text(
            "You are not authorized to use the admin console."
        )

        return

    await update.message.reply_text(
        """
🌿 SPANDAN ADMIN CONSOLE

CASE LISTS

/cases
All recent cases.

/cases new
New cases.

/cases review
Cases currently in review.

/cases closed
Closed cases.


CASE MANAGEMENT

/case SP-0001
View a case.

/close SP-0001
Close a case.

/reopen SP-0001
Reopen a case.

/note SP-0001 your note
Add an internal note.


REPORTING

/stats
View case statistics.


You can also manage cases directly using
the buttons attached to case notifications.
"""
    )


# =========================================================
# LIST CASES
# =========================================================


async def cases_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):
        return

    status = None

    if context.args:

        value = context.args[0].lower()

        mapping = {
            "new": "NEW",
            "review": "IN_REVIEW",
            "closed": "CLOSED",
        }

        if value not in mapping:

            await update.message.reply_text(
                "Usage: /cases, /cases new, /cases review, /cases closed"
            )

            return

        status = mapping[value]

    cases = list_cases(
        status=status,
        limit=15
    )

    if not cases:

        await update.message.reply_text(
            "No cases found."
        )

        return

    lines = [
        "🌿 SPANDAN CASES",
        ""
    ]

    for case in cases:

        name = (
            case["user_name"]
            or "Anonymous"
        )

        intake = _load_intake(
            case
        )

        concern = (
            intake.get(
                "primary_concern"
            )
            or "No concern"
        )

        if len(concern) > 50:

            concern = (
                concern[:47]
                + "..."
            )

        lines.append(
            f"{format_case_id(case['id'])} | "
            f"{case['status']}"
        )

        lines.append(
            f"👤 {name}"
        )

        lines.append(
            f"🧩 {concern}"
        )

        lines.append(
            f"🕒 {format_date(case['created_at'])}"
        )

        lines.append("")

    lines.append(
        "Use /case SP-XXXX to open a case."
    )

    await update.message.reply_text(
        "\n".join(lines)
    )


# =========================================================
# VIEW CASE
# =========================================================


async def case_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):
        return

    if not context.args:

        await update.message.reply_text(
            "Usage: /case SP-0001"
        )

        return

    case_id = parse_case_id(
        context.args[0]
    )

    if not case_id:

        await update.message.reply_text(
            "Invalid case ID."
        )

        return

    case = get_case(
        case_id
    )

    if not case:

        await update.message.reply_text(
            "Case not found."
        )

        return

    await update.message.reply_text(

        build_case_text(
            case
        ),

        reply_markup=admin_keyboard(
            case_id,
            case["status"]
        )
    )


# =========================================================
# CLOSE
# =========================================================


async def close_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):
        return

    if not context.args:

        await update.message.reply_text(
            "Usage: /close SP-0001"
        )

        return

    case_id = parse_case_id(
        context.args[0]
    )

    if not case_id:

        await update.message.reply_text(
            "Invalid case ID."
        )

        return

    case = get_case(
        case_id
    )

    if not case:

        await update.message.reply_text(
            "Case not found."
        )

        return

    update_case_status(
        case_id,
        "CLOSED"
    )

    await update.message.reply_text(
        f"✅ {format_case_id(case_id)} is now CLOSED."
    )


# =========================================================
# REOPEN
# =========================================================


async def reopen_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):
        return

    if not context.args:

        await update.message.reply_text(
            "Usage: /reopen SP-0001"
        )

        return

    case_id = parse_case_id(
        context.args[0]
    )

    if not case_id:

        await update.message.reply_text(
            "Invalid case ID."
        )

        return

    case = get_case(
        case_id
    )

    if not case:

        await update.message.reply_text(
            "Case not found."
        )

        return

    update_case_status(
        case_id,
        "IN_REVIEW"
    )

    await update.message.reply_text(
        f"🔄 {format_case_id(case_id)} reopened and moved to IN REVIEW."
    )


# =========================================================
# NOTE
# =========================================================


async def note_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):
        return

    if len(context.args) < 2:

        await update.message.reply_text(
            """
Usage:

/note SP-0001 spoke with the user today
"""
        )

        return

    case_id = parse_case_id(
        context.args[0]
    )

    if not case_id:

        await update.message.reply_text(
            "Invalid case ID."
        )

        return

    note = " ".join(
        context.args[1:]
    ).strip()

    case = get_case(
        case_id
    )

    if not case:

        await update.message.reply_text(
            "Case not found."
        )

        return

    add_case_note(
        case_id,
        update.effective_user.id,
        note
    )

    await update.message.reply_text(
        f"📝 Note added to {format_case_id(case_id)}."
    )


# =========================================================
# STATS
# =========================================================


async def stats_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not is_admin(
        update.effective_user.id
    ):
        return

    stats = get_stats()

    await update.message.reply_text(
        f"""
🌿 SPANDAN STATS

Total cases:
{stats["total"]}

🆕 New:
{stats["new"]}

🔄 In review:
{stats["in_review"]}

✅ Closed:
{stats["closed"]}
"""
    )


# =========================================================
# CALLBACK BUTTONS
# =========================================================


async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    # ALWAYS answer the callback once.
    # This removes Telegram's loading spinner.
    try:
        await query.answer()
    except Exception:
        pass

    # -----------------------------------------------------
    # SECURITY
    # -----------------------------------------------------

    if not is_admin(
        query.from_user.id
    ):

        try:

            await query.answer(
                "Not authorized.",
                show_alert=True
            )

        except Exception:
            pass

        return

    # -----------------------------------------------------
    # PARSE
    # -----------------------------------------------------

    try:

        action, raw_case_id = (
            query.data.split(
                ":",
                1
            )
        )

        case_id = int(
            raw_case_id
        )

    except Exception:

        await query.message.reply_text(
            "Invalid admin action."
        )

        return

    case = get_case(
        case_id
    )

    if not case:

        await query.message.reply_text(
            "This case no longer exists."
        )

        return

    # -----------------------------------------------------
    # VIEW
    # -----------------------------------------------------

    if action == "view":

        await query.message.reply_text(

            build_case_text(
                case
            ),

            reply_markup=admin_keyboard(
                case_id,
                case["status"]
            )
        )

        return

    # -----------------------------------------------------
    # START REVIEW
    # -----------------------------------------------------

    if action == "review":

        update_case_status(
            case_id,
            "IN_REVIEW"
        )

        case = get_case(
            case_id
        )

        try:

            await query.edit_message_reply_markup(
                reply_markup=admin_keyboard(
                    case_id,
                    case["status"]
                )
            )

        except Exception:
            pass

        await query.message.reply_text(
            f"👨‍💼 {format_case_id(case_id)} moved to IN REVIEW."
        )

        return

    # -----------------------------------------------------
    # CLOSE
    # -----------------------------------------------------

    if action == "close":

        update_case_status(
            case_id,
            "CLOSED"
        )

        case = get_case(
            case_id
        )

        try:

            await query.edit_message_reply_markup(
                reply_markup=admin_keyboard(
                    case_id,
                    case["status"]
                )
            )

        except Exception:
            pass

        await query.message.reply_text(
            f"✅ {format_case_id(case_id)} is now CLOSED."
        )

        return

    # -----------------------------------------------------
    # REOPEN
    # -----------------------------------------------------

    if action == "reopen":

        update_case_status(
            case_id,
            "IN_REVIEW"
        )

        case = get_case(
            case_id
        )

        try:

            await query.edit_message_reply_markup(
                reply_markup=admin_keyboard(
                    case_id,
                    case["status"]
                )
            )

        except Exception:
            pass

        await query.message.reply_text(
            f"🔄 {format_case_id(case_id)} reopened."
        )

        return

    # -----------------------------------------------------
    # NOTE
    # -----------------------------------------------------

    if action == "note":

        context.user_data[
            "awaiting_note_for"
        ] = case_id

        await query.message.reply_text(
            f"""
📝 Add note to {format_case_id(case_id)}.

Send your next message as the note.

Example:

Spoke with user. Practitioner appointment
scheduled for Friday.
"""
        )

        return

    await query.message.reply_text(
        "Unknown admin action."
    )