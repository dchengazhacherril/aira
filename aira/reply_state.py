import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone


LOCAL_DIR = ".local"
LEGACY_PENDING_REPLY_PATH = os.path.join(LOCAL_DIR, "pending_reply.json")
PENDING_REPLIES_PATH = os.path.join(LOCAL_DIR, "pending_replies.json")
REPLY_CLARIFICATION_PATH = os.path.join(LOCAL_DIR, "reply_clarification.json")
CLARIFICATION_TIMEOUT_MINUTES = 6 * 60


def should_use_database_storage():
    return bool(os.getenv("DATABASE_URL", "").strip())


def build_reply_id(original_message):
    source = "|".join(
        [
            original_message.get("id", ""),
            original_message.get("thread_id", ""),
            original_message.get("message_id_header", ""),
        ]
    )
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:6].upper()


def get_database_connection():
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "DATABASE_URL is set, but psycopg is not installed. "
            "Run pip install -r requirements.txt."
        ) from error

    return psycopg.connect(os.environ["DATABASE_URL"])


def ensure_pending_replies_table(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_replies (
                reply_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                sms_message_sid TEXT NOT NULL,
                original_message JSONB NOT NULL,
                parsed_email JSONB NOT NULL,
                reply_plan JSONB NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reply_clarifications (
                clarification_key TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                host_reply_text TEXT NOT NULL,
                candidate_reply_ids JSONB NOT NULL
            )
            """
        )
    connection.commit()


def parse_database_json(value):
    if isinstance(value, str):
        return json.loads(value)

    return value


def load_all_pending_replies_from_database():
    with get_database_connection() as connection:
        ensure_pending_replies_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    reply_id,
                    created_at,
                    sms_message_sid,
                    original_message,
                    parsed_email,
                    reply_plan
                FROM pending_replies
                """
            )
            rows = cursor.fetchall()

    pending_replies = {}
    for (
        reply_id,
        created_at,
        sms_message_sid,
        original_message,
        parsed_email,
        reply_plan,
    ) in rows:
        pending_replies[reply_id] = {
            "reply_id": reply_id,
            "created_at": created_at,
            "sms_message_sid": sms_message_sid,
            "original_message": parse_database_json(original_message),
            "parsed_email": parse_database_json(parsed_email),
            "reply_plan": parse_database_json(reply_plan),
        }

    return pending_replies


def save_all_pending_replies_to_database(pending_replies):
    from psycopg.types.json import Jsonb

    with get_database_connection() as connection:
        ensure_pending_replies_table(connection)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM pending_replies")
            for reply_id, pending_reply in pending_replies.items():
                cursor.execute(
                    """
                    INSERT INTO pending_replies (
                        reply_id,
                        created_at,
                        sms_message_sid,
                        original_message,
                        parsed_email,
                        reply_plan
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        reply_id,
                        pending_reply["created_at"],
                        pending_reply["sms_message_sid"],
                        Jsonb(pending_reply["original_message"]),
                        Jsonb(pending_reply["parsed_email"]),
                        Jsonb(pending_reply["reply_plan"]),
                    ),
                )
        connection.commit()


def load_all_pending_replies():
    if should_use_database_storage():
        return load_all_pending_replies_from_database()

    pending_replies = {}
    has_current_file = os.path.exists(PENDING_REPLIES_PATH)

    if has_current_file:
        with open(PENDING_REPLIES_PATH) as pending_file:
            pending_replies = json.load(pending_file)

    if not has_current_file and os.path.exists(LEGACY_PENDING_REPLY_PATH):
        with open(LEGACY_PENDING_REPLY_PATH) as pending_file:
            pending_reply = json.load(pending_file)
        reply_id = pending_reply.get("reply_id") or build_reply_id(
            pending_reply.get("original_message", {})
        )
        pending_reply["reply_id"] = reply_id
        pending_replies[reply_id] = pending_reply

    return pending_replies


def save_all_pending_replies(pending_replies):
    if should_use_database_storage():
        save_all_pending_replies_to_database(pending_replies)
        return

    os.makedirs(LOCAL_DIR, exist_ok=True)

    with open(PENDING_REPLIES_PATH, "w") as pending_file:
        json.dump(pending_replies, pending_file, indent=2)
        pending_file.write("\n")

    if os.path.exists(LEGACY_PENDING_REPLY_PATH):
        os.remove(LEGACY_PENDING_REPLY_PATH)


def get_newest_pending_reply(pending_replies):
    if not pending_replies:
        return None

    return max(
        pending_replies.values(),
        key=lambda pending_reply: pending_reply.get("created_at", ""),
    )


def get_pending_reply_candidates(pending_replies, limit=3):
    return sorted(
        pending_replies.values(),
        key=lambda pending_reply: pending_reply.get("created_at", ""),
        reverse=True,
    )[:limit]


def save_pending_reply(
    original_message,
    parsed_email,
    reply_plan,
    sms_message_sid,
    reply_id=None,
):
    pending_replies = load_all_pending_replies()
    reply_id = reply_id or build_reply_id(original_message)

    pending_replies[reply_id] = {
        "reply_id": reply_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sms_message_sid": sms_message_sid,
        "original_message": original_message,
        "parsed_email": parsed_email,
        "reply_plan": reply_plan,
    }

    save_all_pending_replies(pending_replies)
    return reply_id


def load_pending_reply(reply_id=None):
    pending_replies = load_all_pending_replies()

    if reply_id:
        return pending_replies.get(reply_id.upper())

    return get_newest_pending_reply(pending_replies)


def clear_pending_reply(reply_id=None):
    if reply_id:
        pending_replies = load_all_pending_replies()
        pending_replies.pop(reply_id.upper(), None)
        save_all_pending_replies(pending_replies)
        return

    if os.path.exists(LEGACY_PENDING_REPLY_PATH):
        os.remove(LEGACY_PENDING_REPLY_PATH)

    if os.path.exists(PENDING_REPLIES_PATH):
        os.remove(PENDING_REPLIES_PATH)


def is_clarification_expired(clarification):
    created_at = clarification.get("created_at", "")
    if not created_at:
        return True

    try:
        created = datetime.fromisoformat(created_at)
    except ValueError:
        return True

    return datetime.now(timezone.utc) - created > timedelta(
        minutes=CLARIFICATION_TIMEOUT_MINUTES
    )


def load_reply_clarification_from_database(clarification_key="default"):
    with get_database_connection() as connection:
        ensure_pending_replies_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT created_at, host_reply_text, candidate_reply_ids
                FROM reply_clarifications
                WHERE clarification_key = %s
                """,
                (clarification_key,),
            )
            row = cursor.fetchone()

    if not row:
        return None

    created_at, host_reply_text, candidate_reply_ids = row
    return {
        "created_at": created_at,
        "host_reply_text": host_reply_text,
        "candidate_reply_ids": parse_database_json(candidate_reply_ids),
    }


def save_reply_clarification_to_database(clarification, clarification_key="default"):
    from psycopg.types.json import Jsonb

    with get_database_connection() as connection:
        ensure_pending_replies_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO reply_clarifications (
                    clarification_key,
                    created_at,
                    host_reply_text,
                    candidate_reply_ids
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (clarification_key)
                DO UPDATE SET
                    created_at = EXCLUDED.created_at,
                    host_reply_text = EXCLUDED.host_reply_text,
                    candidate_reply_ids = EXCLUDED.candidate_reply_ids
                """,
                (
                    clarification_key,
                    clarification["created_at"],
                    clarification["host_reply_text"],
                    Jsonb(clarification["candidate_reply_ids"]),
                ),
            )
        connection.commit()


def clear_reply_clarification_from_database(clarification_key="default"):
    with get_database_connection() as connection:
        ensure_pending_replies_table(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM reply_clarifications WHERE clarification_key = %s",
                (clarification_key,),
            )
        connection.commit()


def load_reply_clarification(include_expired=False):
    if should_use_database_storage():
        clarification = load_reply_clarification_from_database()
    elif os.path.exists(REPLY_CLARIFICATION_PATH):
        with open(REPLY_CLARIFICATION_PATH) as clarification_file:
            clarification = json.load(clarification_file)
    else:
        clarification = None

    if clarification and is_clarification_expired(clarification):
        if include_expired:
            return clarification

        clear_reply_clarification()
        return None

    return clarification


def save_reply_clarification(host_reply_text, candidate_reply_ids):
    clarification = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "host_reply_text": host_reply_text,
        "candidate_reply_ids": candidate_reply_ids,
    }

    if should_use_database_storage():
        save_reply_clarification_to_database(clarification)
        return clarification

    os.makedirs(LOCAL_DIR, exist_ok=True)
    with open(REPLY_CLARIFICATION_PATH, "w") as clarification_file:
        json.dump(clarification, clarification_file, indent=2)
        clarification_file.write("\n")

    return clarification


def clear_reply_clarification():
    if should_use_database_storage():
        clear_reply_clarification_from_database()
        return

    if os.path.exists(REPLY_CLARIFICATION_PATH):
        os.remove(REPLY_CLARIFICATION_PATH)


def parse_clarification_selection(text, clarification, pending_replies):
    normalized_text = text.strip().lower()

    if normalized_text == "cancel":
        return None, "cancel", ""

    candidate_reply_ids = clarification.get("candidate_reply_ids", [])

    if normalized_text.isdigit():
        selected_index = int(normalized_text) - 1
        if 0 <= selected_index < len(candidate_reply_ids):
            reply_id = candidate_reply_ids[selected_index]
            if reply_id in pending_replies:
                return pending_replies[reply_id], reply_id, ""
            return None, "", "That pending Airbnb message is no longer available."

    guest_matches = []
    for reply_id in candidate_reply_ids:
        pending_reply = pending_replies.get(reply_id)
        if not pending_reply:
            continue

        guest_name = (
            pending_reply.get("parsed_email", {}).get("guest_name", "").strip().lower()
        )
        if guest_name and guest_name in normalized_text:
            guest_matches.append((reply_id, pending_reply))

    if len(guest_matches) == 1:
        reply_id, pending_reply = guest_matches[0]
        return pending_reply, reply_id, ""

    if len(guest_matches) > 1:
        return None, "", "I found more than one pending message for that guest. Reply with the number next to the right message."

    return None, "", "Reply with the number or guest name, or CANCEL."


def find_reply_id_in_text(text, pending_replies=None):
    pending_replies = pending_replies or load_all_pending_replies()
    upper_text = text.upper()

    for reply_id in pending_replies:
        if re.search(rf"\b{re.escape(reply_id.upper())}\b", upper_text):
            return reply_id.upper()

    return ""


def resolve_pending_reply(host_reply_text):
    pending_replies = load_all_pending_replies()
    reply_id = find_reply_id_in_text(host_reply_text, pending_replies)

    if reply_id:
        return pending_replies.get(reply_id), reply_id, ""

    newest_pending_reply = get_newest_pending_reply(pending_replies)
    if newest_pending_reply:
        return newest_pending_reply, newest_pending_reply["reply_id"], ""

    return None, "", "No pending Airbnb reply found. Run Aira first so it can text you a message to review."
