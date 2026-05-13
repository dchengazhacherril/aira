import unittest
from unittest.mock import patch

from scripts.check_airbnb_email import build_sms_text


class SmsTextTest(unittest.TestCase):
    def test_trial_safe_sms_text_does_not_include_internal_reply_id(self):
        parsed_email = {
            "guest_name": "David",
            "sender_role": "co-host",
            "listing_name": "Not found",
            "guest_message_body": "Where should I put the trash?",
        }
        reply_plan = {
            "suggested_reply": "Please use the bins by the garage.",
            "needs_manual_review": False,
        }

        sms_text = build_sms_text(parsed_email, reply_plan)

        self.assertLessEqual(len(sms_text), 120)
        self.assertNotIn("4C35CD", sms_text)
        self.assertNotIn("🏠", sms_text)
        self.assertNotIn("✨", sms_text)
        self.assertIn("Ans: Please use the bins by the garage.", sms_text)
        self.assertIn("SEND/SKIP/type reply.", sms_text)

    def test_trial_safe_sms_uses_exact_send_reply_when_it_fits(self):
        parsed_email = {
            "guest_name": "David",
            "sender_role": "co-host",
            "listing_name": "Not found",
            "guest_message_body": "Where should I put the trash?",
        }
        suggested_reply = (
            "Hi! Happy to help. You can put it in the back by the garage. Thanks!"
        )
        reply_plan = {
            "suggested_reply": suggested_reply,
            "needs_manual_review": False,
        }

        sms_text = build_sms_text(parsed_email, reply_plan)

        self.assertLessEqual(len(sms_text), 120)
        self.assertIn(f"Ans: {suggested_reply}", sms_text)

    def test_low_confidence_sms_asks_for_plain_response(self):
        parsed_email = {
            "guest_name": "David",
            "sender_role": "co-host",
            "listing_name": "Lake House",
            "guest_message_body": "Where should I put the trash?",
        }
        reply_plan = {
            "suggested_reply": "I'm not fully confident here, please review.",
            "needs_manual_review": True,
        }

        sms_text = build_sms_text(parsed_email, reply_plan)

        self.assertLessEqual(len(sms_text), 120)
        self.assertIn("David (co-host): Where should I put the trash?", sms_text)
        self.assertIn("Reply with answer or SKIP.", sms_text)
        self.assertNotIn("EDIT", sms_text)

    def test_rich_sms_text_can_be_enabled_after_twilio_trial(self):
        parsed_email = {
            "guest_name": "David",
            "sender_role": "co-host",
            "listing_name": "Not found",
            "guest_message_body": "Where should I put the trash?",
        }
        reply_plan = {
            "suggested_reply": "Please use the bins by the garage.",
            "needs_manual_review": False,
        }

        with patch.dict("os.environ", {"AIRA_TRIAL_SMS_SAFE": "false"}):
            sms_text = build_sms_text(parsed_email, reply_plan)

        self.assertIn("🏠 Listing: n/a", sms_text)
        self.assertIn("\n\n💬 David (co-host): Where should I put the trash?", sms_text)
        self.assertIn("✨ Suggested reply: Please use the bins by the garage.", sms_text)


if __name__ == "__main__":
    unittest.main()
