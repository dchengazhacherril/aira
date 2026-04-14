from email_reader import get_newest_unread_airbnb_email, parse_airbnb_email
from host_memory import load_host_memory
from reply_engine import generate_reply_plan
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
        "-- send {{ suggested reply }}",
        "-- edit {{ your custom reply }}",
        "-- skip",
        ]
    )

    return "\n".join(lines)


def get_final_reply_text(host_input, reply_plan):
    normalized_input = host_input.strip()

    if normalized_input.upper() == "SEND":
        return reply_plan["suggested_reply"]

    if normalized_input.upper() == "SKIP":
        return ""

    return normalized_input


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

        print(f"SMS sent. Message SID: {message_sid}")
        print()
        print("Simulate host SMS reply in the terminal.")
        print("Type SEND to use the suggested reply, SKIP to ignore, or type your edited reply.")
        host_input = input("Host reply: ")
        final_reply = get_final_reply_text(host_input, reply_plan)
        print()

        if not final_reply:
            print("Host chose to skip. No reply will be sent.")
            return

        if host_input.strip().upper() == "SEND":
            print("Host chose SEND. Using the suggested reply.")
        else:
            print("Host provided an edited reply.")

        print()
        print("Final reply to send")
        print("-------------------")
        print(final_reply)
        print()
        print("Reply sending back through Airbnb/email is not built yet.")
        print("This is a local MVP simulation of the host reply loop.")
    else:
        print("This does not look like a relevant host-side Airbnb message, so Aira should ignore it.")


if __name__ == "__main__":
    main()
