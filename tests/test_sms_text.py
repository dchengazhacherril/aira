import unittest

from scripts.check_airbnb_email import build_sms_text


class SmsTextTest(unittest.TestCase):
    def test_sms_text_does_not_include_internal_reply_id(self):
        parsed_email = {
            "guest_name": "David",
            "sender_role": "co-host",
            "guest_message_body": "Where should I put the trash?",
        }
        reply_plan = {
            "suggested_reply": "Please use the bins by the garage.",
            "needs_manual_review": False,
        }

        sms_text = build_sms_text(parsed_email, reply_plan)

        self.assertNotIn("4C35CD", sms_text)
        self.assertIn("Aira Airbnb", sms_text)
        self.assertIn("Reply SEND/SKIP/EDIT <text>.", sms_text)


if __name__ == "__main__":
    unittest.main()
