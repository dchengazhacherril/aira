import base64
import json
import os.path
import re

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from aira.airbnb_parser import clean_text, parse_airbnb_email


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]
AIRBNB_SENDER = "express@airbnb.com"
AIRBNB_AUTOMATED_SENDER = "automated@airbnb.com"
LOCAL_DIR = ".local"
CREDENTIALS_PATH = os.path.join(LOCAL_DIR, "credentials.json")
load_dotenv(os.path.join(LOCAL_DIR, ".env"))

DEFAULT_GMAIL_ACCOUNT_EMAIL = "david@getaira.host"
DEFAULT_GMAIL_SEND_AS_EMAIL = "aira.cohost@gmail.com"


def get_configured_email(name, default):
    return os.getenv(name, default).strip().lower()


def get_token_path(account_email):
    configured_token_path = os.getenv("GMAIL_TOKEN_PATH")
    if configured_token_path:
        return configured_token_path

    token_account = re.sub(r"[^a-zA-Z0-9_.-]+", "_", account_email)
    return os.path.join(LOCAL_DIR, f"token-{token_account}.json")


def load_json_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        return None

    return json.loads(value)


GMAIL_ACCOUNT_EMAIL = get_configured_email(
    "GMAIL_ACCOUNT_EMAIL",
    DEFAULT_GMAIL_ACCOUNT_EMAIL,
)

GMAIL_SEND_AS_EMAIL = get_configured_email(
    "GMAIL_SEND_AS_EMAIL",
    DEFAULT_GMAIL_SEND_AS_EMAIL,
)

TOKEN_PATH = get_token_path(GMAIL_ACCOUNT_EMAIL)


def token_has_required_scopes(token_data):
    saved_scopes = token_data.get("scopes") or token_data.get("scope") or []

    if isinstance(saved_scopes, str):
        saved_scopes = saved_scopes.split()

    return all(scope in saved_scopes for scope in SCOPES)


def load_token_data():
    env_token_data = load_json_env("GMAIL_TOKEN_JSON")
    if env_token_data:
        return env_token_data

    if not os.path.exists(TOKEN_PATH):
        return None

    with open(TOKEN_PATH) as token_file:
        return json.load(token_file)


def token_file_has_required_scopes():
    token_data = load_token_data()
    if not token_data:
        return False

    return token_has_required_scopes(token_data)


def build_installed_app_flow():
    credentials_data = load_json_env("GMAIL_CREDENTIALS_JSON")
    if credentials_data:
        return InstalledAppFlow.from_client_config(credentials_data, SCOPES)

    return InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_PATH,
        SCOPES,
    )


def can_write_gmail_token_file():
    return not load_json_env("GMAIL_TOKEN_JSON")


def get_gmail_service():
    creds = None
    token_data = load_token_data()

    if token_data and token_has_required_scopes(token_data):
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = build_installed_app_flow()
            creds = flow.run_local_server(port=0)

        if can_write_gmail_token_file():
            os.makedirs(LOCAL_DIR, exist_ok=True)

            with open(TOKEN_PATH, "w") as token_file:
                token_file.write(creds.to_json())

    service = build("gmail", "v1", credentials=creds)
    validate_gmail_account(service)
    return service


def validate_gmail_account(service):
    profile = service.users().getProfile(userId="me").execute()
    authenticated_email = profile.get("emailAddress", "").lower()

    if authenticated_email == GMAIL_ACCOUNT_EMAIL:
        return

    raise RuntimeError(
        "Authenticated Gmail account mismatch. "
        f"Expected {GMAIL_ACCOUNT_EMAIL}, but token is for "
        f"{authenticated_email or 'unknown account'}. "
        f"Delete {TOKEN_PATH} and sign in as {GMAIL_ACCOUNT_EMAIL}."
    )


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


def html_to_text(html_text):
    if not html_text:
        return ""

    text = re.sub(r"(?i)<br\s*/?>", "\n", html_text)
    text = re.sub(r"(?i)</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return clean_text(text)


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


def read_message(message_id):
    service = get_gmail_service()
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


def mark_message_read(message_id):
    try:
        service = get_gmail_service()
        service.users().messages().modify(
            userId="me",
            id=message_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
        return True
    except HttpError as error:
        print(f"Gmail mark-read error: {error}")
        return False


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

        return read_message(messages[0]["id"])
    except HttpError as error:
        print(f"Gmail API error: {error}")
        return None


def get_messages_by_query(query, max_results=10):
    try:
        service = get_gmail_service()

        results = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            q=query,
            maxResults=max_results,
        ).execute()

        return [
            read_message(message["id"])
            for message in results.get("messages", [])
        ]
    except HttpError as error:
        print(f"Gmail API error: {error}")
        return []


def get_newest_unread_airbnb_email():
    return get_newest_message_by_query(f"from:{AIRBNB_SENDER} is:unread")


def get_unread_airbnb_reservation_emails(max_results=10):
    query = (
        f"{{from:{AIRBNB_AUTOMATED_SENDER} from:{AIRBNB_SENDER}}} "
        'is:unread ("Reservation confirmed" OR "Reservation reminder" OR arrives)'
    )
    return get_messages_by_query(query, max_results=max_results)
