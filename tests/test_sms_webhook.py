import os
import unittest
from unittest.mock import patch

from aira import sms_webhook


class SmsWebhookTest(unittest.TestCase):
    def test_signature_validation_can_be_disabled_for_manual_testing(self):
        with patch.dict(os.environ, {"TWILIO_VALIDATE_REQUESTS": "false"}):
            self.assertFalse(sms_webhook.should_validate_twilio_requests())

    def test_build_twiml_response_escapes_message_text(self):
        response = sms_webhook.build_twiml_response("A & B < C")

        self.assertIn("A &amp; B &lt; C", response)

    def test_success_confirmation_hides_gmail_message_id(self):
        pending_reply = {
            "reply_plan": {
                "suggested_reply": "Suggested reply.",
                "needs_manual_review": False,
            },
            "original_message": {
                "id": "gmail-source",
                "thread_id": "gmail-thread",
            },
        }

        with patch.dict(os.environ, {"MY_PHONE_NUMBER": "+15555555555"}):
            with patch("aira.sms_webhook.resolve_pending_reply") as resolve_pending:
                with patch("aira.sms_webhook.send_reply_email", return_value="gmail-sent-id"):
                    with patch("aira.sms_webhook.clear_pending_reply"):
                        resolve_pending.return_value = (pending_reply, "ABC123", "")

                        response = sms_webhook.handle_inbound_sms("+15555555555", "SEND")

        self.assertEqual(response, "Sent Airbnb reply.")
        self.assertNotIn("gmail-sent-id", response)


if __name__ == "__main__":
    unittest.main()
