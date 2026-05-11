import base64
import json
import os.path
import re
from html import unescape

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]
AIRBNB_SENDER = "express@airbnb.com"
LOCAL_DIR = ".local"
CREDENTIALS_PATH = os.path.join(LOCAL_DIR, "credentials.json")
TOKEN_PATH = os.path.join(LOCAL_DIR, "token.json")


def token_file_has_required_scopes():
    if not os.path.exists(TOKEN_PATH):
        return False

    with open(TOKEN_PATH) as token_file:
        token_data = json.load(token_file)

    saved_scopes = token_data.get("scopes") or token_data.get("scope") or []

    if isinstance(saved_scopes, str):
        saved_scopes = saved_scopes.split()

    return all(scope in saved_scopes for scope in SCOPES)


def get_gmail_service():
    creds = None

    if token_file_has_required_scopes():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH,
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        os.makedirs(LOCAL_DIR, exist_ok=True)

        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_header_value(headers, name):
    for header in headers:
        if header["name"].lower() == name.lower():
            return header["value"]
    return ""


def decode_base64_text(data):
    if not data:
        return ""

    decoded_bytes = base64.urlsafe_b64decode(data)
    return decoded_bytes.decode("utf-8", errors="replace")


def clean_text(text):
    if not text:
        return ""

    text = text.replace("\r", "")
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_text(html_text):
    if not html_text:
        return ""

    text = re.sub(r"(?i)<br\s*/?>", "\n", html_text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return clean_text(unescape(text))


def find_body_text(payload):
    if payload.get("mimeType") == "text/plain":
        return clean_text(decode_base64_text(payload.get("body", {}).get("data")))

    if payload.get("mimeType") == "text/html":
        return html_to_text(decode_base64_text(payload.get("body", {}).get("data")))

    for part in payload.get("parts", []):
        body_text = find_body_text(part)
        if body_text:
            return body_text

    return ""


def find_first_match(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def remove_noise_lines(email_body):
    cleaned_lines = []

    for line in email_body.splitlines():
        stripped_line = line.strip()
        lower_line = stripped_line.lower()

        if not stripped_line:
            cleaned_lines.append("")
            continue

        if stripped_line.startswith("http"):
            continue

        if stripped_line.startswith("[http"):
            continue

        if lower_line in {
            "%opentrack%",
            "reply",
            "reservation details",
            "guests",
            "airbnb, inc.",
            "get the airbnb app",
        }:
            continue

        if "always communicate through airbnb" in lower_line:
            continue

        if "update your email preferences" in lower_line:
            continue

        if "unsubscribe" in lower_line:
            continue

        cleaned_lines.append(stripped_line)

    return clean_text("\n".join(cleaned_lines))


def extract_message_sender(clean_body, subject):
    subject_name = find_first_match(
        subject,
        [
            r"RE:\s*(.+?)\s*sent you a message",
            r"Message from\s+(.+?)(?:\s+about|$)",
        ],
    )
    if subject_name:
        return subject_name

    lines = [line for line in clean_body.splitlines() if line.strip()]
    if not lines:
        return ""

    for index, line in enumerate(lines):
        if line.upper() == "YOU’VE GOT A NEW MESSAGE" and index + 1 < len(lines):
            possible_name = lines[index + 1]
            if len(possible_name) < 60:
                return clean_text(possible_name)

        if line.upper().startswith("RESERVATION FOR"):
            if index + 1 < len(lines):
                possible_name = lines[index + 1]
                if len(possible_name) < 60:
                    return clean_text(possible_name)

        if line.lower().startswith("hi ") and index > 0:
            possible_name = lines[index - 1]
            if len(possible_name) < 60 and not possible_name.lower().startswith("re:"):
                return clean_text(possible_name)

    first_line = lines[0]
    if len(first_line) < 60 and not first_line.lower().startswith("re:"):
        return clean_text(first_line)

    return ""


def extract_listing_name(clean_body, subject):
    listing_name = find_first_match(
        subject,
        [
            r"Reservation at (.+?) for [A-Z][a-z]{2,9} \d{1,2}",
        ],
    )
    if listing_name:
        return listing_name

    listing_name = find_first_match(
        clean_body,
        [
            r"RESERVATION DETAILS\s+(.+?)\s+Home -",
        ],
    )
    if listing_name:
        return listing_name

    return ""


def extract_host_name(clean_body):
    return find_first_match(
        clean_body,
        [
            r"hosted by\s+([^\n]+)",
        ],
    )


def extract_sender_role(clean_body):
    lines = [line for line in clean_body.splitlines() if line.strip()]
    role_labels = {"booker", "co-host", "cohost", "guest", "host"}

    for index, line in enumerate(lines):
        if line.upper() in {"YOU’VE GOT A NEW MESSAGE"} or line.upper().startswith("RESERVATION FOR"):
            for next_line in lines[index + 1:index + 4]:
                lower_line = next_line.lower()
                if lower_line in role_labels:
                    return clean_text(next_line)

    return ""


def extract_guest_message_body(email_body):
    clean_body = remove_noise_lines(email_body)

    patterns = [
        r"(?s)RESERVATION FOR[^\n]*\n\s*[^\n]+\n\s*(?:Booker|Co-host|Cohost|Guest|Host)\s+(.+?)\s*(?:Reply|You can also respond|$)",
        r"(?s)YOU’VE GOT A NEW MESSAGE\s+[^\n]+\s+(?:Booker|Co-host|Cohost|Guest|Host)\s+(.+?)\s*(?:Reply|You can also respond|$)",
        r"(?s)^\s*(?:RE:.*?\n+)?[^\n]+\n\s*Hi [^\n,]+,\s*(.+?)\s*(?:Respond to|RESERVATION DETAILS|$)",
        r"(?s)Message from .*?:\s*(.+?)\s*(?:Reply|RESERVATION DETAILS|$)",
        r"(?s)Guest message:\s*(.+?)\s*(?:Reply|RESERVATION DETAILS|$)",
        r"(?s)says:\s*[\"“]?(.+?)[\"”]?\s*(?:Reply|RESERVATION DETAILS|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, clean_body, re.IGNORECASE)
        if match:
            return clean_text(match.group(1))

    lines = [line.strip() for line in clean_body.splitlines() if line.strip()]
    filtered_lines = []

    for line in lines:
        lower_line = line.lower()
        if lower_line.startswith("re:"):
            continue
        if lower_line.startswith("reservation for"):
            continue
        if lower_line in {"booker", "host", "guest", "co-host", "cohost"}:
            continue
        if "reservation details" in lower_line or "check-in" in lower_line or "check-out" in lower_line:
            continue
        if "you can also respond by replying directly to this email" in lower_line:
            continue
        filtered_lines.append(line)

    if filtered_lines and len(filtered_lines) > 1:
        return clean_text("\n".join(filtered_lines[1:8]))

    return clean_text("\n".join(filtered_lines[:6]))


def parse_airbnb_email(email_body, subject=""):
    clean_body = remove_noise_lines(email_body)
    message_sender = extract_message_sender(clean_body, subject)
    listing_name = extract_listing_name(clean_body, subject)
    host_name = extract_host_name(clean_body)
    extracted_sender_role = extract_sender_role(clean_body)
    guest_message_body = extract_guest_message_body(email_body)
    sender_role = "unknown"
    is_relevant_message = False

    if extracted_sender_role:
        sender_role = extracted_sender_role.lower()

    if message_sender and host_name and sender_role == "unknown":
        if message_sender.lower() == host_name.lower():
            sender_role = "host"
        else:
            sender_role = "guest"

    if sender_role in {"guest", "co-host", "cohost"}:
        is_relevant_message = True

    if "inbox_type=host" in email_body or "/hosting/thread/" in email_body:
        is_relevant_message = True

    if sender_role == "host":
        is_relevant_message = False

    return {
        "guest_name": message_sender or "Not found",
        "listing_name": listing_name or "Not found",
        "host_name": host_name or "Not found",
        "sender_role": sender_role,
        "is_guest_message": sender_role == "guest",
        "is_relevant_message": is_relevant_message,
        "guest_message_body": guest_message_body or "Not found",
    }


def get_newest_message_by_query(query):
    try:
        service = get_gmail_service()

        results = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            q=query,
            maxResults=1,
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return None

        message_id = messages[0]["id"]
        message = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()

        headers = message.get("payload", {}).get("headers", [])

        return {
            "id": message.get("id", ""),
            "thread_id": message.get("threadId", ""),
            "subject": get_header_value(headers, "Subject"),
            "from": get_header_value(headers, "From"),
            "reply_to": get_header_value(headers, "Reply-To"),
            "message_id_header": get_header_value(headers, "Message-ID"),
            "references": get_header_value(headers, "References"),
            "date": get_header_value(headers, "Date"),
            "snippet": clean_text(message.get("snippet", "")),
            "body": find_body_text(message.get("payload", {})),
        }
    except HttpError as error:
        print(f"Gmail API error: {error}")
        return None


def get_newest_unread_airbnb_email():
    return get_newest_message_by_query(f"from:{AIRBNB_SENDER} is:unread")
