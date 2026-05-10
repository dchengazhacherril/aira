import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs

from dotenv import load_dotenv

from email_sender import send_reply_email
from reply_flow import parse_host_reply
from reply_state import clear_pending_reply, load_pending_reply


LOCAL_ENV_PATH = os.path.join(".local", ".env")


load_dotenv(LOCAL_ENV_PATH)


def log_event(message):
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


def handle_inbound_sms(from_phone, body_text):
    host_phone = os.getenv("MY_PHONE_NUMBER", "")
    normalized_body = body_text.strip()

    log_event(f"SMS received from {from_phone}: {normalized_body}")

    if host_phone and normalize_phone_number(from_phone) != normalize_phone_number(
        host_phone
    ):
        log_event("Rejected SMS because it was not from the configured host phone.")
        return "This Aira number is only configured for the host phone."

    pending_reply = load_pending_reply()
    if not pending_reply:
        log_event("No pending reply context found.")
        return "No pending Airbnb reply found. Run Aira first so it can text you a message to review."

    reply_plan = pending_reply["reply_plan"]
    original_message = pending_reply["original_message"]
    parsed_reply = parse_host_reply(body_text, reply_plan["suggested_reply"])
    log_event(
        "Parsed host reply "
        f"action={parsed_reply['action']} "
        f"gmail_thread={original_message.get('thread_id', '')} "
        f"source_message={original_message.get('id', '')}"
    )

    if parsed_reply["action"] == "error":
        log_event(f"Reply command error: {parsed_reply['message']}")
        return parsed_reply["message"]

    if parsed_reply["action"] == "skip":
        clear_pending_reply()
        log_event("Pending reply skipped and cleared.")
        return parsed_reply["message"]

    sent_reply_id = send_reply_email(
        original_message,
        parsed_reply["reply_text"],
    )

    if not sent_reply_id:
        log_event("Gmail reply failed. Pending reply was left in place.")
        return "Aira could not send the Airbnb reply through Gmail. Check the webhook terminal logs."

    clear_pending_reply()
    log_event(
        "Gmail reply sent "
        f"sent_message_id={sent_reply_id} "
        f"gmail_thread={original_message.get('thread_id', '')}. "
        "Pending reply cleared."
    )
    return f"Sent Airbnb reply. Gmail message id: {sent_reply_id}"


class SmsWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length).decode("utf-8")
        form_data = parse_qs(request_body)

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


def main():
    port = int(os.getenv("SMS_WEBHOOK_PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), SmsWebhookHandler)

    log_event(f"Aira SMS webhook listening on http://localhost:{port}")
    log_event("Configure Twilio incoming messages to POST to your public tunnel URL.")
    server.serve_forever()


if __name__ == "__main__":
    main()
