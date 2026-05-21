import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from aira.airbnb_parser import clean_text, remove_noise_lines


LOCAL_DIR = ".local"
RESERVATIONS_PATH = os.path.join(LOCAL_DIR, "reservations.json")
RESERVATION_ALERTS_PATH = os.path.join(LOCAL_DIR, "reservation_alerts.json")
DEFAULT_TIMEZONE = "America/New_York"
NEXT_GUEST_WINDOW_DAYS = 7
ALERT_HOUR = 12


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def should_use_database_storage():
    return bool(os.getenv("DATABASE_URL", "").strip())


def get_database_connection():
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError(
            "DATABASE_URL is set, but psycopg is not installed. "
            "Run pip install -r requirements.txt."
        ) from error

    return psycopg.connect(os.environ["DATABASE_URL"])


def ensure_reservation_tables(connection):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reservations (
                reservation_id TEXT PRIMARY KEY,
                reservation JSONB NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS reservation_alerts (
                alert_key TEXT PRIMARY KEY,
                sent_at TEXT NOT NULL
            )
            """
        )
    connection.commit()


def parse_database_json(value):
    if isinstance(value, str):
        return json.loads(value)

    return value


def parse_date_text(text, reference_year=None):
    if not text:
        return ""

    reference_year = reference_year or datetime.now().year
    match = re.search(
        r"\b("
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
        r")\s+(\d{1,2})(?:,\s*(\d{4}))?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""

    month = MONTHS[match.group(1).lower()]
    day = int(match.group(2))
    year = int(match.group(3) or reference_year)
    return date(year, month, day).isoformat()


def parse_date_range(text, reference_year=None):
    if not text:
        return "", ""

    reference_year = reference_year or datetime.now().year
    match = re.search(
        r"\b("
        r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
        r")\s+(\d{1,2})\s*[–-]\s*(?:(\w+)\s+)?(\d{1,2})(?:,\s*(\d{4}))?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return "", ""

    start_month_name = match.group(1)
    start_day = int(match.group(2))
    end_month_name = match.group(3) or start_month_name
    end_day = int(match.group(4))
    year = int(match.group(5) or reference_year)

    checkin = date(year, MONTHS[start_month_name.lower()], start_day)
    checkout = date(year, MONTHS[end_month_name.lower()], end_day)
    if checkout < checkin:
        checkout = date(year + 1, checkout.month, checkout.day)

    return checkin.isoformat(), checkout.isoformat()


def extract_first(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return clean_text(match.group(1))
    return ""


def parse_guest_name(subject, body):
    return extract_first(
        [
            r"Reservation confirmed\s*[-:]\s*(.+?)\s+arrives\b",
            r"Reservation reminder:\s*(.+?)\s+is coming soon",
            r"\b([A-Z][A-Z\s'.-]+)\s+ARRIVES\b",
            r"\bGuest\s+(.+)",
        ],
        f"{subject}\n{body}",
    ).title()


def parse_listing_name(subject, body):
    return extract_first(
        [
            r"Reservation at (.+?) for ",
            r"Reservation for (.+?) for ",
            r"RESERVATION DETAILS\s+(.+?)\s+Home -",
            r"\n([^\n]+)\n\s*Entire home/apt",
        ],
        f"{subject}\n{body}",
    )


def parse_guest_counts(text):
    counts = {
        "total_guests": 0,
        "adults": 0,
        "children": 0,
        "infants": 0,
        "pets": 0,
    }
    normalized = text.lower()

    for field, labels in {
        "adults": ["adult", "adults"],
        "children": ["child", "children"],
        "infants": ["infant", "infants"],
        "pets": ["pet", "pets", "dog", "dogs"],
    }.items():
        for label in labels:
            match = re.search(rf"\b(\d+)\s+{label}\b", normalized)
            if match:
                counts[field] = int(match.group(1))
                break

    total_match = re.search(r"\b(\d+)\s+(?:guest|guests)\b", normalized)
    if total_match:
        counts["total_guests"] = int(total_match.group(1))
    else:
        counts["total_guests"] = counts["adults"] + counts["children"] + counts["infants"]

    return counts


def calculate_nights(checkin_date, checkout_date):
    if not checkin_date or not checkout_date:
        return 0

    return (date.fromisoformat(checkout_date) - date.fromisoformat(checkin_date)).days


def build_reservation_id(reservation):
    source = "|".join(
        [
            reservation.get("guest_name", ""),
            reservation.get("listing_name", ""),
            reservation.get("checkin_date", ""),
            reservation.get("checkout_date", ""),
        ]
    )
    return hashlib.sha1(source.encode("utf-8")).hexdigest()[:12].upper()


def parse_reservation_email(message, reference_year=None):
    subject = message.get("subject", "")
    body = remove_noise_lines(message.get("body", ""))
    text = f"{subject}\n{body}"
    reference_year = reference_year or datetime.now().year

    checkin_date, checkout_date = parse_date_range(text, reference_year)
    if not checkin_date:
        checkin_date = parse_date_text(subject, reference_year)
    if not checkout_date:
        checkout_date = extract_first(
            [
                r"Check(?:-| )?out(?: date)?:?\s*([A-Z][a-z]+ \d{1,2}(?:,\s*\d{4})?)",
                r"Checkout:?\s*([A-Z][a-z]+ \d{1,2}(?:,\s*\d{4})?)",
            ],
            text,
        )
        checkout_date = parse_date_text(checkout_date, reference_year)

    guest_name = parse_guest_name(subject, body)
    listing_name = parse_listing_name(subject, body)

    if not guest_name or not checkin_date:
        return None

    guest_counts = parse_guest_counts(text)
    reservation = {
        "reservation_id": "",
        "guest_name": guest_name,
        "listing_name": listing_name or "n/a",
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "nights": calculate_nights(checkin_date, checkout_date),
        "guest_counts": guest_counts,
        "source_message_id": message.get("id", ""),
        "source_thread_id": message.get("thread_id", ""),
        "source_subject": subject,
        "updated_at": datetime.now().isoformat(),
    }
    reservation["reservation_id"] = build_reservation_id(reservation)
    return reservation


def load_reservations_from_database():
    with get_database_connection() as connection:
        ensure_reservation_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT reservation_id, reservation FROM reservations")
            rows = cursor.fetchall()

    return {
        reservation_id: parse_database_json(reservation)
        for reservation_id, reservation in rows
    }


def save_reservations_to_database(reservations):
    from psycopg.types.json import Jsonb

    with get_database_connection() as connection:
        ensure_reservation_tables(connection)
        with connection.cursor() as cursor:
            for reservation_id, reservation in reservations.items():
                cursor.execute(
                    """
                    INSERT INTO reservations (reservation_id, reservation)
                    VALUES (%s, %s)
                    ON CONFLICT (reservation_id)
                    DO UPDATE SET reservation = EXCLUDED.reservation
                    """,
                    (reservation_id, Jsonb(reservation)),
                )
        connection.commit()


def load_reservations():
    if should_use_database_storage():
        return load_reservations_from_database()

    if not os.path.exists(RESERVATIONS_PATH):
        return {}

    with open(RESERVATIONS_PATH) as reservations_file:
        return json.load(reservations_file)


def save_reservations(reservations):
    if should_use_database_storage():
        save_reservations_to_database(reservations)
        return

    os.makedirs(LOCAL_DIR, exist_ok=True)
    with open(RESERVATIONS_PATH, "w") as reservations_file:
        json.dump(reservations, reservations_file, indent=2)
        reservations_file.write("\n")


def upsert_reservation(reservation):
    reservations = load_reservations()
    reservations[reservation["reservation_id"]] = reservation
    save_reservations(reservations)
    return reservation["reservation_id"]


def load_sent_alerts_from_database():
    with get_database_connection() as connection:
        ensure_reservation_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute("SELECT alert_key, sent_at FROM reservation_alerts")
            rows = cursor.fetchall()

    return {alert_key: sent_at for alert_key, sent_at in rows}


def save_sent_alerts_to_database(sent_alerts):
    with get_database_connection() as connection:
        ensure_reservation_tables(connection)
        with connection.cursor() as cursor:
            for alert_key, sent_at in sent_alerts.items():
                cursor.execute(
                    """
                    INSERT INTO reservation_alerts (alert_key, sent_at)
                    VALUES (%s, %s)
                    ON CONFLICT (alert_key)
                    DO UPDATE SET sent_at = EXCLUDED.sent_at
                    """,
                    (alert_key, sent_at),
                )
        connection.commit()


def load_sent_alerts():
    if should_use_database_storage():
        return load_sent_alerts_from_database()

    if not os.path.exists(RESERVATION_ALERTS_PATH):
        return {}

    with open(RESERVATION_ALERTS_PATH) as alerts_file:
        return json.load(alerts_file)


def save_sent_alerts(sent_alerts):
    if should_use_database_storage():
        save_sent_alerts_to_database(sent_alerts)
        return

    os.makedirs(LOCAL_DIR, exist_ok=True)
    with open(RESERVATION_ALERTS_PATH, "w") as alerts_file:
        json.dump(sent_alerts, alerts_file, indent=2)
        alerts_file.write("\n")


def mark_alert_sent(alert_key, sent_at=None):
    sent_alerts = load_sent_alerts()
    sent_alerts[alert_key] = (sent_at or datetime.now()).isoformat()
    save_sent_alerts(sent_alerts)


def is_alert_sent(alert_key):
    return alert_key in load_sent_alerts()


def get_local_now(timezone_name=None):
    timezone_name = timezone_name or os.getenv("AIRA_TIMEZONE", DEFAULT_TIMEZONE)
    return datetime.now(ZoneInfo(timezone_name))


def is_alert_time(now):
    return now.hour == ALERT_HOUR


def get_reservations_by_listing(reservations):
    grouped = {}
    for reservation in reservations.values():
        grouped.setdefault(reservation.get("listing_name", "n/a"), []).append(
            reservation
        )

    for listing_reservations in grouped.values():
        listing_reservations.sort(key=lambda item: item.get("checkin_date", ""))

    return grouped


def find_next_reservation(reservation, listing_reservations):
    checkout_date = reservation.get("checkout_date", "")
    if not checkout_date:
        return None

    checkout = date.fromisoformat(checkout_date)
    candidates = []
    for candidate in listing_reservations:
        if candidate["reservation_id"] == reservation["reservation_id"]:
            continue
        checkin = date.fromisoformat(candidate["checkin_date"])
        if checkin >= checkout:
            candidates.append(candidate)

    if not candidates:
        return None

    return sorted(candidates, key=lambda item: item["checkin_date"])[0]


def format_guest_counts(guest_counts):
    total = guest_counts.get("total_guests", 0)
    parts = []
    for field, label in [
        ("adults", "adult"),
        ("children", "child"),
        ("infants", "infant"),
        ("pets", "pet"),
    ]:
        count = guest_counts.get(field, 0)
        if count:
            suffix = label if count == 1 else f"{label}s"
            parts.append(f"{count} {suffix}")

    if parts:
        return f"{total} total ({', '.join(parts)})" if total else ", ".join(parts)

    return f"{total} total" if total else "n/a"


def format_date(date_text):
    if not date_text:
        return "n/a"

    value = date.fromisoformat(date_text)
    return value.strftime("%b %-d")


def build_checkin_alert(reservation):
    return (
        f"{reservation['guest_name']} checks in today at {reservation['listing_name']}.\n"
        f"Stay: {reservation['nights']} nights, checks out {format_date(reservation['checkout_date'])}.\n"
        f"Guests: {format_guest_counts(reservation['guest_counts'])}."
    )


def build_turnover_alert(checkout_reservation, checkin_reservation):
    return (
        f"Turnover tomorrow: {checkout_reservation['guest_name']} checks out and "
        f"{checkin_reservation['guest_name']} checks in at {checkin_reservation['listing_name']}.\n"
        f"{checkin_reservation['guest_name']}: "
        f"{format_guest_counts(checkin_reservation['guest_counts'])}, "
        f"{checkin_reservation['nights']} nights, "
        f"checks out {format_date(checkin_reservation['checkout_date'])}."
    )


def build_checkout_alert(reservation, next_reservation, days_until_next):
    day_text = "today" if days_until_next == 0 else f"in {days_until_next} days"
    return (
        f"{reservation['guest_name']} checks out today at {reservation['listing_name']}.\n"
        f"Next guest checks in {day_text}."
    )


def get_due_reservation_alerts(reservations, now=None):
    now = now or get_local_now()
    if not is_alert_time(now):
        return []

    today = now.date()
    tomorrow = today + timedelta(days=1)
    sent_alerts = load_sent_alerts()
    due_alerts = []
    grouped = get_reservations_by_listing(reservations)

    for listing_reservations in grouped.values():
        for reservation in listing_reservations:
            checkin = date.fromisoformat(reservation["checkin_date"])
            checkout_text = reservation.get("checkout_date", "")
            checkout = date.fromisoformat(checkout_text) if checkout_text else None

            if checkin == today:
                alert_key = f"checkin:{reservation['reservation_id']}:{today.isoformat()}"
                if alert_key not in sent_alerts:
                    due_alerts.append(
                        {
                            "alert_key": alert_key,
                            "message": build_checkin_alert(reservation),
                        }
                    )

            if checkout == today:
                next_reservation = find_next_reservation(
                    reservation,
                    listing_reservations,
                )
                if next_reservation:
                    days_until_next = (
                        date.fromisoformat(next_reservation["checkin_date"]) - today
                    ).days
                    if 0 <= days_until_next <= NEXT_GUEST_WINDOW_DAYS:
                        alert_key = (
                            f"checkout:{reservation['reservation_id']}:"
                            f"{today.isoformat()}"
                        )
                        if alert_key not in sent_alerts:
                            due_alerts.append(
                                {
                                    "alert_key": alert_key,
                                    "message": build_checkout_alert(
                                        reservation,
                                        next_reservation,
                                        days_until_next,
                                    ),
                                }
                            )

            if checkout == tomorrow:
                for checkin_reservation in listing_reservations:
                    if date.fromisoformat(checkin_reservation["checkin_date"]) == tomorrow:
                        alert_key = (
                            f"turnover:{reservation['listing_name']}:"
                            f"{tomorrow.isoformat()}"
                        )
                        if alert_key not in sent_alerts:
                            due_alerts.append(
                                {
                                    "alert_key": alert_key,
                                    "message": build_turnover_alert(
                                        reservation,
                                        checkin_reservation,
                                    ),
                                }
                            )
                        break

    return due_alerts
