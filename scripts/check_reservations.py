import argparse

from aira.app_logging import log_event
from aira.email_reader import (
    get_unread_airbnb_reservation_emails,
    mark_message_read,
)
from aira.host_memory import load_host_memory
from aira.reservations import (
    get_due_reservation_alerts,
    load_reservations,
    mark_alert_sent,
    parse_reservation_email,
    upsert_reservation,
)
from aira.sms import send_sms


def ingest_reservation_emails(max_results=10):
    print("Checking Gmail for unread Airbnb reservation emails...")
    messages = get_unread_airbnb_reservation_emails(max_results=max_results)
    parsed_count = 0
    ignored_count = 0

    for message in messages:
        reservation = parse_reservation_email(message)
        if not reservation:
            print(f"Ignoring reservation email that could not be parsed: {message['subject']}")
            mark_message_read(message["id"])
            ignored_count += 1
            continue

        reservation_id = upsert_reservation(reservation)
        mark_message_read(message["id"])
        parsed_count += 1
        print(
            "Saved reservation "
            f"{reservation_id}: {reservation['guest_name']} "
            f"{reservation['checkin_date']} -> {reservation['checkout_date']}"
        )
        log_event(
            "reservation_saved",
            reservation_id=reservation_id,
            gmail_message_id=message.get("id", ""),
        )

    if not messages:
        print("No unread Airbnb reservation emails found.")

    return parsed_count, ignored_count


def send_due_reservation_alerts(now=None):
    reservations = load_reservations()
    host_memory = load_host_memory()
    due_alerts = get_due_reservation_alerts(
        reservations,
        now=now,
        host_memory=host_memory,
    )

    if not due_alerts:
        print("No reservation alerts due.")
        return 0

    for alert in due_alerts:
        message_sid = send_sms(alert["message"])
        mark_alert_sent(alert["alert_key"], sent_at=now)
        print(f"Reservation alert sent. Message SID: {message_sid}")
        print(f"Alert key: {alert['alert_key']}")
        log_event(
            "reservation_alert_sent",
            alert_key=alert["alert_key"],
            sms_message_sid=message_sid,
        )

    return len(due_alerts)


def check_reservations_once(max_results=10, now=None):
    print("Aira reservations")
    print()
    parsed_count, ignored_count = ingest_reservation_emails(max_results=max_results)
    sent_count = send_due_reservation_alerts(now=now)
    print()
    print(
        "Reservation check complete: "
        f"{parsed_count} saved, {ignored_count} ignored, {sent_count} alerts sent."
    )
    return {
        "parsed_count": parsed_count,
        "ignored_count": ignored_count,
        "sent_count": sent_count,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Check Airbnb reservation emails and send host alerts."
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=10,
        help="Maximum unread reservation emails to process in one run.",
    )
    args = parser.parse_args()
    check_reservations_once(max_results=args.max_results)


if __name__ == "__main__":
    main()
