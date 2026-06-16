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

        with patch("aira.memory_learning.load_host_memory") as load_memory:
            load_memory.return_value = {"profile": {}}
            with patch("aira.memory_learning.update_host_profile") as update_profile:
                update_profile.return_value = {
                    "reply_correction_notes": (
                        "Guest asked: Where should I put the trash?\n"
                        "Host replied: Put trash in the bins behind the garage."
                    ),
                    "trash_notes": "Put trash in the bins behind the garage.",
                }

                learned_fact = learn_from_edited_reply(
                    pending_reply,
                    "Put trash in the bins behind the garage.",
                )

        update_profile.assert_called_once_with(
            {
                "reply_correction_notes": (
                    "Guest asked: Where should I put the trash?\n"
                    "Host replied: Put trash in the bins behind the garage."
                ),
                "trash_notes": "Put trash in the bins behind the garage.",
            }
        )
        self.assertEqual(learned_fact["message_type"], "trash")
        self.assertEqual(learned_fact["profile_field"], "trash_notes")
        self.assertEqual(
            learned_fact["profile_fields"],
            ["reply_correction_notes", "trash_notes"],
        )

    def test_reclassifies_old_other_reply_before_learning(self):
        pending_reply = {
            "reply_plan": {
                "message_type": "other",
            },
            "parsed_email": {
                "guest_message_body": "Where should I put the trash?",
            },
        }

        with patch("aira.memory_learning.load_host_memory") as load_memory:
            load_memory.return_value = {"profile": {}}
            with patch("aira.memory_learning.update_host_profile") as update_profile:
                update_profile.return_value = {
                    "reply_correction_notes": (
                        "Guest asked: Where should I put the trash?\n"
                        "Host replied: Put trash in the bins behind the garage."
                    ),
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

        with patch("aira.memory_learning.load_host_memory") as load_memory:
            load_memory.return_value = {"profile": {}}
            with patch("aira.memory_learning.update_host_profile") as update_profile:
                update_profile.return_value = {
                    "reply_correction_notes": (
                        "Guest asked: Just confirming you have a travel crib?\n"
                        "Host replied: Yes definitely! The travel crib and a high chair "
                        "will be available!"
                    ),
                    "baby_gear_notes": "Travel crib and high chair are available.",
                }

                learned_fact = learn_from_edited_reply(
                    pending_reply,
                    "Yes definitely! The travel crib and a high chair will be available!",
                )

        update_profile.assert_called_once_with(
            {
                "reply_correction_notes": (
                    "Guest asked: Just confirming you have a travel crib?\n"
                    "Host replied: Yes definitely! The travel crib and a high chair "
                    "will be available!"
                ),
                "baby_gear_notes": "Travel crib and high chair are available.",
            }
        )
        self.assertEqual(learned_fact["message_type"], "baby_gear")
        self.assertEqual(learned_fact["profile_field"], "baby_gear_notes")

    def test_learns_amenity_notes_from_edited_reply(self):
        pending_reply = {
            "reply_plan": {
                "message_type": "amenity_unknown",
            },
            "parsed_email": {
                "guest_message_body": "Do you have any umbrellas?",
            },
        }

        with patch("aira.memory_learning.load_host_memory") as load_memory:
            load_memory.return_value = {
                "profile": {
                    "amenity_notes": "We provide shampoo and body wash.",
                    "reply_correction_notes": "Existing correction.",
                }
            }
            with patch("aira.memory_learning.update_host_profile") as update_profile:
                update_profile.return_value = {
                    "reply_correction_notes": (
                        "Existing correction.\n"
                        "Guest asked: Do you have any umbrellas?\n"
                        "Host replied: Unfortunately we do not have umbrellas."
                    ),
                    "amenity_notes": (
                        "We provide shampoo and body wash.\n"
                        "Unfortunately we do not have umbrellas."
                    ),
                }

                learned_fact = learn_from_edited_reply(
                    pending_reply,
                    "Unfortunately we do not have umbrellas.",
                )

        update_profile.assert_called_once_with(
            {
                "reply_correction_notes": (
                    "Existing correction.\n"
                    "Guest asked: Do you have any umbrellas?\n"
                    "Host replied: Unfortunately we do not have umbrellas."
                ),
                "amenity_notes": (
                    "We provide shampoo and body wash.\n"
                    "Unfortunately we do not have umbrellas."
                )
            }
        )
        self.assertEqual(learned_fact["message_type"], "amenity_unknown")
        self.assertEqual(learned_fact["profile_field"], "amenity_notes")

    def test_learns_generic_correction_from_any_edited_reply(self):
        pending_reply = {
            "reply_plan": {
                "message_type": "other",
            },
            "parsed_email": {
                "guest_message_body": "Can we leave bags at the house?",
            },
        }

        with patch("aira.memory_learning.load_host_memory") as load_memory:
            load_memory.return_value = {"profile": {}}
            with patch("aira.memory_learning.update_host_profile") as update_profile:
                update_profile.return_value = {
                    "reply_correction_notes": (
                        "Guest asked: Can we leave bags at the house?\n"
                        "Host replied: Yes, 1pm works today."
                    ),
                }

                learned_fact = learn_from_edited_reply(
                    pending_reply,
                    "Yes, 1pm works today.",
                )

        update_profile.assert_called_once_with(
            {
                "reply_correction_notes": (
                    "Guest asked: Can we leave bags at the house?\n"
                    "Host replied: Yes, 1pm works today."
                ),
            }
        )
        self.assertEqual(learned_fact["message_type"], "other")
        self.assertEqual(learned_fact["profile_field"], "reply_correction_notes")


if __name__ == "__main__":
    unittest.main()
