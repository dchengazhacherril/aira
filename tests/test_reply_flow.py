import unittest

from aira.reply_flow import parse_host_reply


class ReplyFlowTest(unittest.TestCase):
    def test_send_with_reply_id_uses_suggestion(self):
        parsed = parse_host_reply("SEND A1B2C3", "Suggested reply.", reply_id="A1B2C3")

        self.assertEqual(parsed["action"], "send")
        self.assertEqual(parsed["reply_text"], "Suggested reply.")

    def test_send_is_blocked_when_manual_review_needed(self):
        parsed = parse_host_reply(
            "SEND A1B2C3",
            "Please review.",
            needs_manual_review=True,
            reply_id="A1B2C3",
        )

        self.assertEqual(parsed["action"], "error")
        self.assertIn("Review needed", parsed["message"])

    def test_edit_with_reply_id_sends_custom_text(self):
        parsed = parse_host_reply(
            "EDIT A1B2C3 Thanks, I will send that now.",
            "Suggested reply.",
            reply_id="A1B2C3",
        )

        self.assertEqual(parsed["action"], "edit")
        self.assertEqual(parsed["reply_text"], "Thanks, I will send that now.")


if __name__ == "__main__":
    unittest.main()
