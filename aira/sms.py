import os

from dotenv import load_dotenv
from twilio.rest import Client


LOCAL_ENV_PATH = os.path.join(".local", ".env")


load_dotenv(LOCAL_ENV_PATH)


def send_sms(message_text):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_phone = os.getenv("TWILIO_PHONE_NUMBER")
    to_phone = os.getenv("MY_PHONE_NUMBER")
    messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

    if not account_sid or not auth_token or not to_phone:
        raise ValueError(
            "Missing Twilio settings. Add them to .local/.env before sending an SMS."
        )

    if not messaging_service_sid and not from_phone:
        raise ValueError(
            "Add either TWILIO_MESSAGING_SERVICE_SID or TWILIO_PHONE_NUMBER to .local/.env."
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


def configure_inbound_sms_webhook(webhook_url):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

    if not account_sid or not auth_token or not messaging_service_sid:
        raise ValueError(
            "Missing Twilio Messaging Service settings. Add TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, and TWILIO_MESSAGING_SERVICE_SID to .local/.env."
        )

    client = Client(account_sid, auth_token)
    service = client.messaging.v1.services(messaging_service_sid).update(
        inbound_request_url=webhook_url,
        inbound_method="POST",
    )

    return {
        "messaging_service_sid": service.sid,
        "inbound_request_url": service.inbound_request_url,
        "inbound_method": service.inbound_method,
    }
