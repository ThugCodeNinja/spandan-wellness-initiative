import json
import sqlite3

from datetime import datetime, timezone


DB_NAME = "spandan.db"


def now():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    connection = sqlite3.connect(
        DB_NAME,
        timeout=30
    )

    connection.row_factory = sqlite3.Row

    return connection


def _ensure_column(
    connection,
    table,
    column,
    definition
):
    columns = connection.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    existing = {
        row["name"]
        for row in columns
    }

    if column not in existing:
        connection.execute(
            f"""
            ALTER TABLE {table}
            ADD COLUMN {column} {definition}
            """
        )


def init_db():

    connection = get_connection()

    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (

            telegram_id INTEGER PRIMARY KEY,

            first_name TEXT,

            username TEXT,

            current_state TEXT NOT NULL
                DEFAULT 'intake',

            current_case_id INTEGER,

            created_at TEXT NOT NULL,

            updated_at TEXT NOT NULL
        )
        """
    )

    # -----------------------------------------------------
    # MESSAGES
    # -----------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            telegram_id INTEGER NOT NULL,

            role TEXT NOT NULL,

            content TEXT NOT NULL,

            created_at TEXT NOT NULL
        )
        """
    )

    # -----------------------------------------------------
    # CASES
    # -----------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS cases (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            telegram_id INTEGER NOT NULL,

            status TEXT NOT NULL
                DEFAULT 'NEW',

            intake_data TEXT NOT NULL
                DEFAULT '{}',

            suggested_modality TEXT,

            routing_scores TEXT,

            routing_reason TEXT,

            created_at TEXT NOT NULL,

            updated_at TEXT NOT NULL,

            closed_at TEXT
        )
        """
    )

    # Migration support for databases created
    # with an earlier version.
    _ensure_column(
        connection,
        "cases",
        "user_name",
        "TEXT"
    )

    _ensure_column(
        connection,
        "cases",
        "telegram_username",
        "TEXT"
    )

    # -----------------------------------------------------
    # CASE NOTES
    # -----------------------------------------------------

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS case_notes (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            case_id INTEGER NOT NULL,

            admin_telegram_id INTEGER NOT NULL,

            note TEXT NOT NULL,

            created_at TEXT NOT NULL
        )
        """
    )

    connection.commit()

    connection.close()


# =========================================================
# USERS
# =========================================================


def ensure_user(
    telegram_id,
    first_name,
    username
):

    connection = get_connection()

    existing = connection.execute(
        """
        SELECT telegram_id
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    ).fetchone()

    if existing:

        connection.execute(
            """
            UPDATE users

            SET
                first_name = ?,
                username = ?,
                updated_at = ?

            WHERE telegram_id = ?
            """,
            (
                first_name,
                username,
                now(),
                telegram_id
            )
        )

    else:

        connection.execute(
            """
            INSERT INTO users
            (
                telegram_id,
                first_name,
                username,
                current_state,
                current_case_id,
                created_at,
                updated_at
            )

            VALUES
            (
                ?,
                ?,
                ?,
                'intake',
                NULL,
                ?,
                ?
            )
            """,
            (
                telegram_id,
                first_name,
                username,
                now(),
                now()
            )
        )

    connection.commit()

    connection.close()


def get_user(
    telegram_id
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    ).fetchone()

    connection.close()

    return row


def set_user_state(
    telegram_id,
    state
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE users

        SET
            current_state = ?,
            updated_at = ?

        WHERE telegram_id = ?
        """,
        (
            state,
            now(),
            telegram_id
        )
    )

    connection.commit()

    connection.close()


def set_current_case(
    telegram_id,
    case_id
):

    connection = get_connection()

    connection.execute(
        """
        UPDATE users

        SET
            current_case_id = ?,
            updated_at = ?

        WHERE telegram_id = ?
        """,
        (
            case_id,
            now(),
            telegram_id
        )
    )

    connection.commit()

    connection.close()


def get_current_case_id(
    telegram_id
):

    user = get_user(
        telegram_id
    )

    if not user:
        return None

    return user["current_case_id"]


# =========================================================
# MESSAGES
# =========================================================


def save_message(
    telegram_id,
    role,
    content
):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO messages
        (
            telegram_id,
            role,
            content,
            created_at
        )

        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            telegram_id,
            role,
            content,
            now()
        )
    )

    connection.commit()

    connection.close()


def get_recent_messages(
    telegram_id,
    limit=20
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT
            role,
            content

        FROM messages

        WHERE telegram_id = ?

        ORDER BY id DESC

        LIMIT ?
        """,
        (
            telegram_id,
            limit
        )
    ).fetchall()

    connection.close()

    return list(
        reversed(rows)
    )


def clear_messages(
    telegram_id
):

    connection = get_connection()

    connection.execute(
        """
        DELETE FROM messages
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    )

    connection.commit()

    connection.close()


# =========================================================
# CASES
# =========================================================


def create_case(
    telegram_id,
    intake,
    routing,
    user_name=None,
    telegram_username=None
):

    connection = get_connection()

    timestamp = now()

    cursor = connection.execute(
        """
        INSERT INTO cases
        (
            telegram_id,
            user_name,
            telegram_username,
            status,
            intake_data,
            suggested_modality,
            routing_scores,
            routing_reason,
            created_at,
            updated_at,
            closed_at
        )

        VALUES
        (
            ?,
            ?,
            ?,
            'NEW',
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            NULL
        )
        """,
        (
            telegram_id,

            user_name,

            telegram_username,

            json.dumps(
                intake,
                ensure_ascii=False
            ),

            routing.modality,

            json.dumps(
                routing.scores,
                ensure_ascii=False
            ),

            routing.reason,

            timestamp,

            timestamp
        )
    )

    case_id = cursor.lastrowid

    connection.commit()

    connection.close()

    return case_id


def get_case(
    case_id
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM cases
        WHERE id = ?
        """,
        (case_id,)
    ).fetchone()

    connection.close()

    return row


def get_case_for_user(
    telegram_id,
    case_id
):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM cases

        WHERE
            id = ?
            AND telegram_id = ?
        """,
        (
            case_id,
            telegram_id
        )
    ).fetchone()

    connection.close()

    return row


def list_cases(
    status=None,
    limit=10,
    offset=0
):

    connection = get_connection()

    if status:

        rows = connection.execute(
            """
            SELECT *
            FROM cases

            WHERE status = ?

            ORDER BY id DESC

            LIMIT ?
            OFFSET ?
            """,
            (
                status,
                limit,
                offset
            )
        ).fetchall()

    else:

        rows = connection.execute(
            """
            SELECT *
            FROM cases

            ORDER BY id DESC

            LIMIT ?
            OFFSET ?
            """,
            (
                limit,
                offset
            )
        ).fetchall()

    connection.close()

    return rows


def update_case_status(
    case_id,
    status
):

    connection = get_connection()

    closed_at = (
        now()
        if status == "CLOSED"
        else None
    )

    connection.execute(
        """
        UPDATE cases

        SET
            status = ?,
            updated_at = ?,
            closed_at = ?

        WHERE id = ?
        """,
        (
            status,
            now(),
            closed_at,
            case_id
        )
    )

    connection.commit()

    connection.close()


def add_case_note(
    case_id,
    admin_telegram_id,
    note
):

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO case_notes
        (
            case_id,
            admin_telegram_id,
            note,
            created_at
        )

        VALUES
        (
            ?,
            ?,
            ?,
            ?
        )
        """,
        (
            case_id,
            admin_telegram_id,
            note,
            now()
        )
    )

    connection.commit()

    connection.close()


def get_case_notes(
    case_id
):

    connection = get_connection()

    rows = connection.execute(
        """
        SELECT *
        FROM case_notes

        WHERE case_id = ?

        ORDER BY id ASC
        """,
        (case_id,)
    ).fetchall()

    connection.close()

    return rows


def get_stats():

    connection = get_connection()

    total = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM cases
        """
    ).fetchone()["count"]

    new = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM cases
        WHERE status = 'NEW'
        """
    ).fetchone()["count"]

    review = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM cases
        WHERE status = 'IN_REVIEW'
        """
    ).fetchone()["count"]

    closed = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM cases
        WHERE status = 'CLOSED'
        """
    ).fetchone()["count"]

    connection.close()

    return {
        "total": total,
        "new": new,
        "in_review": review,
        "closed": closed
    }


# =========================================================
# RESET
# =========================================================


def reset_user_intake(
    telegram_id
):

    clear_messages(
        telegram_id
    )

    set_user_state(
        telegram_id,
        "intake"
    )

    set_current_case(
        telegram_id,
        None
    )