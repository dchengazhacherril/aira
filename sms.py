import os

from dotenv import load_dotenv
from twilio.rest import Client


load_dotenv()


def send_sms(message_text):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")
    to_phone = os.getenv("MY_PHONE_NUMBER")
    messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

    if not account_sid or not auth_token or not to_phone:
        raise ValueError(
            "Missing Twilio settings. Add them to your .env file before sending an SMS."
        )

    if not messaging_service_sid and not from_phone:
        raise ValueError(
            "Add either TWILIO_MESSAGING_SERVICE_SID or TWILIO_PHONE_NUMBER to your .env file."
        )

    client = Client(account_sid, auth_token)

    if messaging_service_sid:
        message = client.messages.create(
            messaging_service_sid=messaging_service_sid,
            body=message_text,
            to=to_phone,
        )
    else:
        message = client.messages.create(
            body=message_text,
            from_=from_phone,
            to=to_phone,
        )

    return message.sid
