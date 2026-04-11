from sms import send_sms


def main():
    guest_name = "Taylor"
    guest_message = "Hi! What time is check-in tomorrow?"

    print("Aira")
    print()
    print("New Airbnb message received")
    print(f"Guest: {guest_name}")
    print(f"Message: {guest_message}")
    print()

    text_message = f"Guest {guest_name} says: {guest_message}"
    print("Sending this guest message to your phone...")
    message_sid = send_sms(text_message)
    print(f"SMS sent. Message SID: {message_sid}")


if __name__ == "__main__":
    main()
