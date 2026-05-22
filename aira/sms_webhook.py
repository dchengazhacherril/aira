import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from dotenv import load_dotenv
from twilio.request_validator import RequestValidator

from aira.app_logging import log_event as log_json_event
from aira.email_sender import send_reply_email
from aira.memory_learning import learn_from_edited_reply
from aira.reply_flow import parse_host_reply
from aira.reply_state import (
    clear_pending_reply,
    clear_recent_reply_context,
    clear_reply_clarification,
    find_reply_id_in_text,
    get_active_pending_replies,
    get_pending_reply_candidates,
    load_all_pending_replies,
    load_recent_reply_context,
    load_reply_clarification,
    is_clarification_expired,
    parse_clarification_selection,
    resolve_pending_reply,
    save_recent_reply_context,
    save_reply_clarification,
)


LOCAL_ENV_PATH = os.path.join(".local", ".env")


load_dotenv(LOCAL_ENV_PATH)


def log_message(message):
    print(message, flush=True)


def normalize_phone_number(phone_number):
    return "".join(character for character in phone_number if character.isdigit())


def build_twiml_response(message_text):
    escaped_message = (
        message_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{escaped_message}</Message></Response>"
    )


def should_validate_twilio_requests():
    value = os.getenv("TWILIO_VALIDATE_REQUESTS", "true").strip().lower()
    return value not in {"0", "false", "no"}


def flatten_form_data(form_data):
    return {key: values[0] if values else "" for key, values in form_data.items()}


def get_public_request_url(handler):
    configured_webhook_url = os.getenv("AIRA_PUBLIC_WEBHOOK_URL", "").strip()
    if configured_webhook_url:
        return configured_webhook_url

    proto = handler.headers.get("X-Forwarded-Proto", "https")
    host = handler.headers.get("X-Forwarded-Host") or handler.headers.get("Host", "")
    return f"{proto}://{host}{handler.path}"


def validate_twilio_request(handler, form_data):
    if not should_validate_twilio_requests():
        return True

    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    signature = handler.headers.get("X-Twilio-Signature", "")

    if not auth_token or not signature:
        return False

    validator = RequestValidator(auth_token)
    return validator.validate(
        get_public_request_url(handler),
        flatten_form_data(form_data),
        signature,
    )


def truncate_text(text, max_length):
    text = " ".join((text or "").split())
    if len(text) <= max_length:
        return text

    return f"{text[: max_length - 3].rstrip()}..."


def get_pending_reply_guest_name(pending_reply):
    return pending_reply.get("parsed_email", {}).get("guest_name", "Guest")


def get_pending_reply_snippet(pending_reply):
    return pending_reply.get("parsed_email", {}).get("guest_message_body", "")


def build_clarification_prompt(candidates):
    lines = ["Which guest should I send this to?"]
    for index, pending_reply in enumerate(candidates, start=1):
        guest_name = truncate_text(get_pending_reply_guest_name(pending_reply), 16)
        snippet = truncate_text(get_pending_reply_snippet(pending_reply), 42)
        lines.append(f"{index}. {guest_name}: {snippet}")

    lines.append("Reply 1, 2, 3, guest name, or CANCEL.")
    return "\n".join(lines)


def needs_reply_clarification(host_reply_text, pending_replies):
    if len(pending_replies) <= 1:
        return False

    return not find_reply_id_in_text(host_reply_text, pending_replies)


def maybe_start_reply_clarification(host_reply_text):
    pending_replies = get_active_pending_replies(load_all_pending_replies())
    if not needs_reply_clarification(host_reply_text, pending_replies):
        return ""

    candidates = get_pending_reply_candidates(pending_replies)
    save_reply_clarification(
        host_reply_text,
        [candidate["reply_id"] for candidate in candidates],
    )
    log_json_event(
        "reply_clarification_requested",
        candidate_count=len(candidates),
    )
    return build_clarification_prompt(candidates)


def is_plain_follow_up_text(host_reply_text):
    normalized_text = host_reply_text.strip().lower()
    if not normalized_text:
        return False

    if normalized_text in {"send", "skip", "cancel"}:
        return False

    if normalized_text.isdigit():
        return False

    if normalized_text.startswith("edit "):
        return False

    return True


def resolve_recent_reply_follow_up(host_reply_text):
    if not is_plain_follow_up_text(host_reply_text):
        return None, ""

    recent_context = load_recent_reply_context()
    if not recent_context:
        return None, ""

    pending_reply = recent_context.get("pending_reply")
    reply_id = recent_context.get("reply_id", "")
    if not pending_reply or not reply_id:
        clear_recent_reply_context()
        return None, ""

    recent_thread_id = pending_reply.get("original_message", {}).get("thread_id", "")
    if recent_thread_id:
        same_thread_replies = [
            (candidate_reply_id, candidate)
            for candidate_reply_id, candidate in get_active_pending_replies(
                load_all_pending_replies()
            ).items()
            if candidate.get("original_message", {}).get("thread_id", "")
            == recent_thread_id
        ]
        if same_thread_replies:
            return max(
                same_thread_replies,
                key=lambda item: item[1].get("created_at", ""),
            )

    return pending_reply, reply_id


def resolve_clarified_reply(host_reply_text):
    clarification = load_reply_clarification(include_expired=True)
    if not clarification:
        return None, "", host_reply_text, ""

    if is_clarification_expired(clarification):
        clear_reply_clarification()
        return (
            None,
            "",
            "",
            "That clarification expired. Reply to the guest message again so I know what to send.",
        )

    pending_replies = get_active_pending_replies(load_all_pending_replies())
    pending_reply, reply_id, selection_error = parse_clarification_selection(
        host_reply_text,
        clarification,
        pending_replies,
    )

    if reply_id == "cancel":
        clear_reply_clarification()
        return None, "", "", "Canceled. No Airbnb reply was sent."

    if not pending_reply:
        return None, "", "", selection_error

    clear_reply_clarification()
    return pending_reply, reply_id, clarification["host_reply_text"], ""


def send_or_skip_pending_reply(pending_reply, reply_id, host_reply_text):
    reply_plan = pending_reply["reply_plan"]
    original_message = pending_reply["original_message"]
    parsed_reply = parse_host_reply(
        host_reply_text,
        reply_plan["suggested_reply"],
        needs_manual_review=reply_plan["needs_manual_review"],
        reply_id=reply_id,
    )
    log_message(
        "Parsed host reply "
        f"action={parsed_reply['action']} "
        f"reply_id={reply_id} "
        f"gmail_thread={original_message.get('thread_id', '')} "
        f"source_message={original_message.get('id', '')}"
    )
    log_json_event(
        "reply_parsed",
        action=parsed_reply["action"],
        reply_id=reply_id,
        gmail_message_id=original_message.get("id", ""),
        gmail_thread_id=original_message.get("thread_id", ""),
    )

    if parsed_reply["action"] == "error":
        log_message(f"Reply command error: {parsed_reply['message']}")
        return parsed_reply["message"]

    if parsed_reply["action"] == "skip":
        clear_pending_reply(reply_id)
        clear_recent_reply_context()
        log_message("Pending reply skipped and cleared.")
        log_json_event("reply_skipped", reply_id=reply_id)
        return parsed_reply["message"]

    sent_reply_id = send_reply_email(
        original_message,
        parsed_reply["reply_text"],
    )

    if not sent_reply_id:
        log_message("Gmail reply failed. Pending reply was left in place.")
        log_json_event("reply_send_failed", reply_id=reply_id)
        return (
            "Aira could not send the Airbnb reply through Gmail. "
            "Check the webhook terminal logs."
        )

    learned_fact = {}
    if parsed_reply["action"] == "edit":
        learned_fact = learn_from_edited_reply(
            pending_reply,
            parsed_reply["reply_text"],
        )
        if learned_fact:
            log_message(
                "Learned host fact "
                f"message_type={learned_fact['message_type']} "
                f"profile_field={learned_fact['profile_field']}"
            )
            log_json_event(
                "host_fact_learned",
                reply_id=reply_id,
                message_type=learned_fact["message_type"],
                profile_field=learned_fact["profile_field"],
            )

    clear_pending_reply(reply_id)
    save_recent_reply_context(pending_reply, reply_id)
    log_message(
        "Gmail reply sent "
        f"sent_message_id={sent_reply_id} "
        f"reply_id={reply_id} "
        f"gmail_thread={original_message.get('thread_id', '')}. "
        "Pending reply cleared."
    )
    log_json_event(
        "reply_sent",
        reply_id=reply_id,
        sent_message_id=sent_reply_id,
        gmail_thread_id=original_message.get("thread_id", ""),
    )
    if learned_fact:
        return "Sent Airbnb reply. I’ll remember that for next time."

    return "Sent Airbnb reply."


def handle_inbound_sms(from_phone, body_text):
    host_phone = os.getenv("MY_PHONE_NUMBER", "")
    normalized_body = body_text.strip()

    log_message(f"SMS received from {from_phone}: {normalized_body}")
    log_json_event("sms_received", from_phone=from_phone)

    if host_phone and normalize_phone_number(from_phone) != normalize_phone_number(
        host_phone
    ):
        log_message("Rejected SMS because it was not from the configured host phone.")
        log_json_event("sms_rejected", reason="unexpected_sender")
        return "This Aira number is only configured for the host phone."

    clarified_reply, clarified_reply_id, clarified_text, clarification_response = (
        resolve_clarified_reply(body_text)
    )
    if clarification_response:
        return clarification_response

    if clarified_reply:
        return send_or_skip_pending_reply(
            clarified_reply,
            clarified_reply_id,
            clarified_text,
        )

    recent_reply, recent_reply_id = resolve_recent_reply_follow_up(body_text)
    if recent_reply:
        return send_or_skip_pending_reply(
            recent_reply,
            recent_reply_id,
            body_text,
        )

    clarification_prompt = maybe_start_reply_clarification(body_text)
    if clarification_prompt:
        return clarification_prompt

    pending_reply, reply_id, resolve_error = resolve_pending_reply(body_text)
    if not pending_reply:
        log_message("No pending reply context found.")
        log_json_event("sms_rejected", reason="no_pending_reply")
        return resolve_error

    return send_or_skip_pending_reply(
        pending_reply,
        reply_id,
        body_text,
    )


class SmsWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length).decode("utf-8")
        form_data = parse_qs(request_body)

        if not validate_twilio_request(self, form_data):
            log_json_event("sms_rejected", reason="invalid_twilio_signature")
            response_body = build_twiml_response(
                "Invalid Twilio request signature."
            ).encode("utf-8")
            self.send_response(403)
            self.send_header("Content-Type", "text/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)
            return

        from_phone = form_data.get("From", [""])[0]
        body_text = form_data.get("Body", [""])[0]

        response_message = handle_inbound_sms(from_phone, body_text)
        response_body = build_twiml_response(response_message).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)

    def do_GET(self):
        response_body = b"Aira SMS webhook is running."

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)


def get_listen_port():
    return int(os.getenv("PORT", os.getenv("SMS_WEBHOOK_PORT", "8000")))


def main():
    port = get_listen_port()
    server = HTTPServer(("0.0.0.0", port), SmsWebhookHandler)

    log_message(f"Aira SMS webhook listening on http://localhost:{port}")
    log_message("Configure Twilio incoming messages to POST to this service URL.")
    server.serve_forever()


if __name__ == "__main__":
    main()
