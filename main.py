from email_reader import get_newest_unread_airbnb_email, parse_airbnb_email
from host_memory import load_host_memory
from reply_engine import generate_reply_plan
from reply_state import save_pending_reply
from sms import send_sms


def build_sms_text(parsed_email, reply_plan):
    sender_name = parsed_email["guest_name"]
    sender_role = parsed_email["sender_role"]
    listing_name = parsed_email["listing_name"]
    message_body = parsed_email["guest_message_body"]
    sender_label = sender_name

    if sender_role != "unknown":
        sender_label = f"{sender_name} - {sender_role.title()}"

    if listing_name == "Not found":
        listing_name = "n/a"

    lines = [
        "New Airbnb Message!",
        f"Sender: {sender_label}",
        f"Listing: {listing_name}",
        f"Type: {reply_plan['message_type']}",
        "Message:",
        f"\"{message_body}\"",
        "",
        "Suggested Reply:",
        f"\"{reply_plan['suggested_reply']}\"",
        "",
    ]

    if reply_plan["needs_manual_review"]:
        lines.extend(
            [
                "Confidence: low",
                "I’m not fully confident here, please review.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "Confidence: high",
                "",
            ]
        )

    lines.extend(
        [
            "Reply With:",
            "-- SEND to send the suggested reply",
            "-- EDIT followed by your custom reply",
            "-- SKIP to do nothing",
        ]
    )

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

        sms_text = build_sms_text(parsed_email, reply_plan)
        message_sid = send_sms(sms_text)
        save_pending_reply(message, parsed_email, reply_plan, message_sid)

        print(f"SMS sent. Message SID: {message_sid}")
        print()
        print("Saved pending reply context for the inbound SMS webhook.")
        print(
            "Reply to the text with SEND, SKIP, EDIT followed by your reply, "
            "or any edited reply text."
        )
    else:
        print("This does not look like a relevant host-side Airbnb message, so Aira should ignore it.")


if __name__ == "__main__":
    main()
