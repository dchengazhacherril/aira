def main():
    guest_name = "Taylor"
    guest_message = "Hi! What time is check-in tomorrow?"

    print("Aira")
    print()
    print("New Airbnb message received")
    print(f"Guest: {guest_name}")
    print(f"Message: {guest_message}")
    print()

    reply = input("Type your reply: ")
    print()
    print(f"Reply sent to {guest_name}: {reply}")


if __name__ == "__main__":
    main()
