import re
from html import unescape


def clean_text(text):
    if not text:
        return ""

    text = text.replace("\r", "")
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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

    inquiry_name = find_first_match(
        clean_body,
        [
            r"RESPOND TO\s+(.+?)[’']S INQUIRY",
        ],
    )
    if inquiry_name:
        return inquiry_name.title()

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

        if line.lower().startswith("inquiry for "):
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
            r"Inquiry for (.+?) for [A-Z][a-z]{2,9} \d{1,2}",
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

    if re.search(r"RESPOND TO\s+.+?[’']S INQUIRY", clean_body, re.IGNORECASE):
        return "guest"

    for index, line in enumerate(lines):
        if line.upper() in {"YOU’VE GOT A NEW MESSAGE"} or line.upper().startswith("RESERVATION FOR"):
            for next_line in lines[index + 1:index + 4]:
                lower_line = next_line.lower()
                if lower_line in role_labels:
                    return clean_text(next_line)

    return ""


def is_reservation_reminder(subject, clean_body):
    if subject.lower().startswith("reservation reminder:"):
        return True

    return bool(
        re.search(r"^[A-Z][A-Z\s]+ ARRIVES .+", clean_body)
        and "if you haven’t already, reach out" in clean_body.lower()
    )


def extract_guest_message_body(email_body):
    clean_body = remove_noise_lines(email_body)

    patterns = [
        r"(?s)RESPOND TO .+?[’']S INQUIRY\s+[^\n]+\s+(?:Identity verified[^\n]*\n\s*)?(?:[^\n]*,\s*[A-Z]{2}\n\s*)?(.+?)\s*(?:Pre-approve|Decline|YOU HAVE 24|FREQUENTLY ASKED|CUSTOMER SUPPORT|Airbnb, Inc\.|$)",
        r"(?s)Inquiry for[^\n]*\n\s*[^\n]+\n\s*(?:Booker|Co-host|Cohost|Guest|Host)\s+(.+?)\s*(?:Reply|You can also respond|RESERVATION DETAILS|Home -|$)",
        r"(?s)RESERVATION FOR[^\n]*\n\s*[^\n]+\n\s*(?:Booker|Co-host|Cohost|Guest|Host)\s+(.+?)\s*(?:Reply|You can also respond|RESERVATION DETAILS|$)",
        r"(?s)YOU’VE GOT A NEW MESSAGE\s+[^\n]+\s+(?:Booker|Co-host|Cohost|Guest|Host)\s+(.+?)\s*(?:Reply|You can also respond|RESERVATION DETAILS|$)",
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
        if lower_line.startswith("inquiry for"):
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
    is_reminder = is_reservation_reminder(subject, clean_body)

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

    if subject.lower().startswith("inquiry for "):
        is_relevant_message = True

    if is_reminder:
        is_relevant_message = False

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
