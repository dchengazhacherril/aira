import unittest

from aira.reply_engine import classify_message, generate_reply_plan


class ReplyEngineTest(unittest.TestCase):
    def test_classifies_trash_messages(self):
        self.assertEqual(classify_message("Where should I put the trash?"), "trash")
        self.assertEqual(classify_message("Which bins should we use?"), "trash")

    def test_generates_trash_reply_from_profile_fact(self):
        parsed_email = {
            "guest_message_body": "Where should I put the trash?",
        }
        host_memory = {
            "profile": {
                "trash_notes": "You can put trash in the bins behind the garage.",
            },
            "preferences": {
                "sign_off": "Thanks!",
            },
            "playbooks": {
                "trash": {
                    "opening": "Happy to help.",
                    "required_profile_fields": ["trash_notes"],
                    "response_template": "{trash_notes}",
                },
            },
        }

        reply_plan = generate_reply_plan(parsed_email, host_memory)

        self.assertEqual(reply_plan["message_type"], "trash")
        self.assertEqual(reply_plan["confidence"], "high")
        self.assertFalse(reply_plan["needs_manual_review"])
        self.assertIn("bins behind the garage", reply_plan["suggested_reply"])


if __name__ == "__main__":
    unittest.main()
