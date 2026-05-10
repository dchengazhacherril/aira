import json
import os
from datetime import datetime, timezone


LOCAL_DIR = ".local"
PENDING_REPLY_PATH = os.path.join(LOCAL_DIR, "pending_reply.json")


def save_pending_reply(original_message, parsed_email, reply_plan, sms_message_sid):
    os.makedirs(LOCAL_DIR, exist_ok=True)

    pending_reply = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sms_message_sid": sms_message_sid,
        "original_message": original_message,
        "parsed_email": parsed_email,
        "reply_plan": reply_plan,
    }

    with open(PENDING_REPLY_PATH, "w") as pending_file:
        json.dump(pending_reply, pending_file, indent=2)


def load_pending_reply():
    if not os.path.exists(PENDING_REPLY_PATH):
        return None

    with open(PENDING_REPLY_PATH) as pending_file:
        return json.load(pending_file)


def clear_pending_reply():
    if os.path.exists(PENDING_REPLY_PATH):
        os.remove(PENDING_REPLY_PATH)
