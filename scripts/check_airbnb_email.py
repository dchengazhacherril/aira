import argparse
import os

from aira.airbnb_parser import parse_airbnb_email
from aira.app_logging import log_event
from aira.email_reader import get_newest_unread_airbnb_email, mark_message_read
from aira.host_memory import load_host_memory
from aira.reply_engine import generate_reply_plan
from aira.reply_server import ReplyServer
from aira.reply_state import build_reply_id, save_pending_reply
from aira.sms import send_sms


TRIAL_SMS_MAX_LENGTH = 120


def should_use_trial_safe_sms():
    value = os.getenv("AIRA_TRIAL_SMS_SAFE", "true").strip().lower()
    return value not in {"0", "false", "no"}


def make_sms_safe(text):
    replacements = {
        "\u2019": "'",
        "\u2018": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
        "\u2009": " ",
    }

    for old_value, new_value in replacements.items():
        text = text.replace(old_value, new_value)

    return " ".join(text.split())


def fit_sms_text(prefix, text, suffix, max_length):
    available_length = max_length - len(prefix) - len(suffix)

    if available_length <= 0:
        return f"{prefix}{suffix}"[:max_length]

    return f"{prefix}{truncate_text(text, available_length)}{suffix}"


def truncate_text(text, max_length):
    text = make_sms_safe(text)

    if len(text) <= max_length:
        return text

    return f"{text[: max_length - 3].rstrip()}..."


def format_listing_name(parsed_email):
    listing_name = parsed_email.get("listing_name", "")

    if not listing_name or listing_name == "Not found":
        return "n/a"

    return listing_name


def format_sender_line(parsed_email):
    sender_name = parsed_email["guest_name"]
    sender_role = parsed_email["sender_role"]

    if sender_role == "unknown":
        return sender_name

    return f"{sender_name} ({sender_role})"


def build_trial_safe_sms_text(parsed_email, reply_plan):
    sender_name = truncate_text(parsed_email["guest_name"], 14)
    sender_line = truncate_text(format_sender_line(parsed_email), 22)
    message_body = parsed_email["guest_message_body"]
    suggested_reply = make_sms_safe(reply_plan["suggested_reply"])

    heading = f"{sender_line}: {truncate_text(message_body, 36)}"

    if reply_plan["needs_manual_review"]:
        prefix = f"{heading}\n"
        suffix = "\nReply with answer or SKIP."
        return fit_sms_text(prefix, "", suffix, TRIAL_SMS_MAX_LENGTH)

    prefix = f"{sender_name}\nAns: "
    suffix = "\nSEND/SKIP/type reply."
    return fit_sms_text(
        prefix,
        suggested_reply,
        suffix,
        TRIAL_SMS_MAX_LENGTH,
    )


def build_sms_text(parsed_email, reply_plan):
    if should_use_trial_safe_sms():
        return build_trial_safe_sms_text(parsed_email, reply_plan)

    message_body = parsed_email["guest_message_body"]
    suggested_reply = reply_plan["suggested_reply"]

    sections = [
        f"🏠 Listing: {truncate_text(format_listing_name(parsed_email), 56)}",
        f"💬 {truncate_text(format_sender_line(parsed_email), 34)}: {truncate_text(message_body, 140)}",
    ]

    if reply_plan["needs_manual_review"]:
        sections.append(
            "🤔 I don't know this one yet.\n"
            "Reply with the message you want to send, or SKIP."
        )
    else:
        sections.append(f"✨ Suggested reply: {truncate_text(suggested_reply, 260)}")
        sections.append(
            "Reply SEND/SKIP, or respond with the message you want to send."
        )

    return "\n\n".join(sections)


def check_airbnb_email_once():
    print("Aira")
    print()
    print("Checking Gmail for the newest unread Airbnb email...")
    print()

    message = get_newest_unread_airbnb_email()

    if not message:
        print("No unread Airbnb email found in your inbox.")
        log_event("email_not_found")
        return False

    parsed_email = parse_airbnb_email(
        email_body=message["body"],
        subject=message["subject"],
    )
    host_memory = load_host_memory()

    print("Newest unread Airbnb email")
    print("-------------------------")
    print(f"Subject: {message['subject']}")
    print(f"From: {message['from']}")
    print(f"Date: {message['date']}")
    print(f"Snippet: {message['snippet']}")
    print()
    print("Plain text body:")
    print(message["body"] or "No plain text body found.")
    print()
    print("Parsed Airbnb fields")
    print("--------------------")
    print(f"Guest name: {parsed_email['guest_name']}")
    print(f"Host name: {parsed_email['host_name']}")
    print(f"Sender role: {parsed_email['sender_role']}")
    print(f"Listing name: {parsed_email['listing_name']}")
    print()

    if parsed_email["is_relevant_message"]:
        print("This looks like a relevant host-side Airbnb message.")
        print()
        print("Message body:")
        print(parsed_email["guest_message_body"])
        print()
        reply_plan = generate_reply_plan(parsed_email, host_memory)
        print("Reply plan")
        print("----------")
        print(f"Type: {reply_plan['message_type']}")
        print(f"Confidence: {reply_plan['confidence']}")
        print(f"Suggested reply: {reply_plan['suggested_reply']}")
        print()
        print("Sending this message to your phone with Twilio...")

        reply_id = build_reply_id(message)
        sms_text = build_sms_text(parsed_email, reply_plan)
        message_sid = send_sms(sms_text)
        save_pending_reply(message, parsed_email, reply_plan, message_sid, reply_id)
        mark_message_read(message["id"])

        print(f"SMS sent. Message SID: {message_sid}")
        print(f"Reply ID: {reply_id}")
        print()
        print("Saved pending reply context for the inbound SMS webhook.")
        print(
            "Reply to the text with SEND, SKIP, EDIT followed by your reply, "
            "or any edited reply text."
        )
        log_event(
            "sms_sent",
            gmail_message_id=message["id"],
            gmail_thread_id=message["thread_id"],
            reply_id=reply_id,
            sms_message_sid=message_sid,
            needs_manual_review=reply_plan["needs_manual_review"],
        )
        return True
    else:
        print("This does not look like a relevant host-side Airbnb message, so Aira should ignore it.")
        mark_message_read(message["id"])
        log_event(
            "email_ignored",
            gmail_message_id=message["id"],
            gmail_thread_id=message["thread_id"],
            sender_role=parsed_email["sender_role"],
        )
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Check Gmail for Airbnb messages and keep the SMS reply flow alive."
    )
    parser.add_argument(
        "--no-reply-server",
        action="store_true",
        help="Only check/send outbound SMS; do not start the inbound reply server.",
    )
    args = parser.parse_args()

    reply_server = None

    try:
        if not args.no_reply_server:
            reply_server = ReplyServer()
            reply_server.start()
            print()

        sms_sent = check_airbnb_email_once()

        if reply_server and sms_sent:
            print()
            print("Waiting for your SMS reply. Press Ctrl-C to stop.", flush=True)
            reply_server.monitor()
    except KeyboardInterrupt:
        print("Stopping Aira reply flow...", flush=True)
    finally:
        if reply_server:
            reply_server.stop()


if __name__ == "__main__":
    main()
