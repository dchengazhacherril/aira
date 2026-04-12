from email_reader import get_newest_unread_airbnb_email, parse_airbnb_email
from sms import send_sms


def build_sms_text(parsed_email):
    sender_name = parsed_email["guest_name"]
    sender_role = parsed_email["sender_role"]
    listing_name = parsed_email["listing_name"]
    message_body = parsed_email["guest_message_body"]

    lines = [
        "Aira: Airbnb message",
        f"From: {sender_name}",
    ]

    if sender_role != "unknown":
        lines.append(f"Role: {sender_role}")

    if listing_name != "Not found":
        lines.append(f"Listing: {listing_name}")

    lines.append("")
    lines.append(message_body)

    return "\n".join(lines)


def main():
    print("Aira")
    print()
    print("Checking Gmail for the newest unread Airbnb email...")
    print()

    message = get_newest_unread_airbnb_email()

    if not message:
        print("No unread Airbnb email found in your inbox.")
        return

    parsed_email = parse_airbnb_email(
        email_body=message["body"],
        subject=message["subject"],
    )

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
        print("Sending this message to your phone with Twilio...")

        sms_text = build_sms_text(parsed_email)
        message_sid = send_sms(sms_text)

        print(f"SMS sent. Message SID: {message_sid}")
    else:
        print("This does not look like a relevant host-side Airbnb message, so Aira should ignore it.")


if __name__ == "__main__":
    main()
