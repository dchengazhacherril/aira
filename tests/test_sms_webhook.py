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

    def test_edited_reply_learns_fact_and_mentions_memory(self):
        pending_reply = {
            "reply_plan": {
                "suggested_reply": "Please review.",
                "needs_manual_review": True,
                "message_type": "trash",
            },
            "parsed_email": {
                "guest_message_body": "Where should I put the trash?",
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
                        with patch("aira.sms_webhook.learn_from_edited_reply") as learn:
                            resolve_pending.return_value = (pending_reply, "ABC123", "")
                            learn.return_value = {
                                "message_type": "trash",
                                "profile_field": "trash_notes",
                            }

                            response = sms_webhook.handle_inbound_sms(
                                "+15555555555",
                                "Put trash in the bins behind the garage.",
                            )

        self.assertEqual(
            response,
            "Sent Airbnb reply. I’ll remember that for next time.",
        )


if __name__ == "__main__":
    unittest.main()
