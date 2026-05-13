import base64
from email.message import EmailMessage

from googleapiclient.errors import HttpError

from aira.email_reader import GMAIL_SEND_AS_EMAIL, get_gmail_service


def build_reply_headers(original_message):
    reply_to = original_message.get("reply_to") or original_message.get("from", "")
    subject = original_message.get("subject", "")
    message_id_header = original_message.get("message_id_header", "")
    references = original_message.get("references", "")

    if references and message_id_header:
        references = f"{references} {message_id_header}".strip()
    elif message_id_header:
        references = message_id_header

    return {
        "to": reply_to,
        "subject": subject,
        "in_reply_to": message_id_header,
        "references": references,
    }


def send_reply_email(original_message, reply_text):
    try:
        service = get_gmail_service()
        reply_headers = build_reply_headers(original_message)

        email_message = EmailMessage()
        email_message["From"] = GMAIL_SEND_AS_EMAIL
        email_message["To"] = reply_headers["to"]
        email_message["Subject"] = reply_headers["subject"]

        if reply_headers["in_reply_to"]:
            email_message["In-Reply-To"] = reply_headers["in_reply_to"]

        if reply_headers["references"]:
            email_message["References"] = reply_headers["references"]

        email_message.set_content(reply_text)

        encoded_message = base64.urlsafe_b64encode(
            email_message.as_bytes()
        ).decode()

        send_body = {
            "raw": encoded_message,
            "threadId": original_message.get("thread_id", ""),
        }

        sent_message = (
            service.users()
            .messages()
            .send(userId="me", body=send_body)
            .execute()
        )

        return sent_message.get("id", "")
    except (HttpError, RuntimeError) as error:
        print(f"Gmail send error: {error}")
        return ""
