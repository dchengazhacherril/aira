import unittest
from unittest.mock import patch

from aira.memory_learning import learn_from_edited_reply


class MemoryLearningTest(unittest.TestCase):
    def test_learns_trash_notes_from_edited_reply(self):
        pending_reply = {
            "reply_plan": {
                "message_type": "trash",
            },
            "parsed_email": {
                "guest_message_body": "Where should I put the trash?",
            },
        }

        with patch("aira.memory_learning.update_host_profile") as update_profile:
            update_profile.return_value = {
                "trash_notes": "Put trash in the bins behind the garage.",
            }

            learned_fact = learn_from_edited_reply(
                pending_reply,
                "Put trash in the bins behind the garage.",
            )

        update_profile.assert_called_once_with(
            {"trash_notes": "Put trash in the bins behind the garage."}
        )
        self.assertEqual(learned_fact["message_type"], "trash")
        self.assertEqual(learned_fact["profile_field"], "trash_notes")

    def test_reclassifies_old_other_reply_before_learning(self):
        pending_reply = {
            "reply_plan": {
                "message_type": "other",
            },
            "parsed_email": {
                "guest_message_body": "Where should I put the trash?",
            },
        }

        with patch("aira.memory_learning.update_host_profile") as update_profile:
            update_profile.return_value = {
                "trash_notes": "Put trash in the bins behind the garage.",
            }

            learned_fact = learn_from_edited_reply(
                pending_reply,
                "Put trash in the bins behind the garage.",
            )

        self.assertEqual(learned_fact["profile_field"], "trash_notes")

    def test_learns_baby_gear_notes_from_edited_reply(self):
        pending_reply = {
            "reply_plan": {
                "message_type": "other",
            },
            "parsed_email": {
                "guest_message_body": "Just confirming you have a travel crib?",
            },
        }

        with patch("aira.memory_learning.update_host_profile") as update_profile:
            update_profile.return_value = {
                "baby_gear_notes": "Travel crib and high chair are available.",
            }

            learned_fact = learn_from_edited_reply(
                pending_reply,
                "Yes definitely! The travel crib and a high chair will be available!",
            )

        update_profile.assert_called_once_with(
            {"baby_gear_notes": "Travel crib and high chair are available."}
        )
        self.assertEqual(learned_fact["message_type"], "baby_gear")
        self.assertEqual(learned_fact["profile_field"], "baby_gear_notes")


if __name__ == "__main__":
    unittest.main()
