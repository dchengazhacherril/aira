import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from aira import reply_state


class ReplyStateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.pending_path = os.path.join(self.temp_dir.name, "pending_replies.json")
        self.legacy_path = os.path.join(self.temp_dir.name, "pending_reply.json")
        self.clarification_path = os.path.join(
            self.temp_dir.name,
            "reply_clarification.json",
        )
        self.patches = [
            patch.dict(os.environ, {"DATABASE_URL": ""}),
            patch.object(reply_state, "LOCAL_DIR", self.temp_dir.name),
            patch.object(reply_state, "PENDING_REPLIES_PATH", self.pending_path),
            patch.object(reply_state, "LEGACY_PENDING_REPLY_PATH", self.legacy_path),
            patch.object(
                reply_state,
                "REPLY_CLARIFICATION_PATH",
                self.clarification_path,
            ),
        ]
        for active_patch in self.patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def test_saves_more_than_one_pending_reply(self):
        first_id = reply_state.save_pending_reply(
            {"id": "gmail-1", "thread_id": "thread-1"},
            {"guest_name": "One"},
            {"suggested_reply": "First"},
            "sms-1",
        )
        second_id = reply_state.save_pending_reply(
            {"id": "gmail-2", "thread_id": "thread-2"},
            {"guest_name": "Two"},
            {"suggested_reply": "Second"},
            "sms-2",
        )

        pending_replies = reply_state.load_all_pending_replies()

        self.assertEqual(set(pending_replies), {first_id, second_id})

    def test_resolves_reply_id_from_sms_text(self):
        reply_id = reply_state.save_pending_reply(
            {"id": "gmail-1", "thread_id": "thread-1"},
            {"guest_name": "One"},
            {"suggested_reply": "First"},
            "sms-1",
        )

        pending_reply, resolved_reply_id, error = reply_state.resolve_pending_reply(
            f"SEND {reply_id}"
        )

        self.assertEqual(error, "")
        self.assertEqual(resolved_reply_id, reply_id)
        self.assertEqual(pending_reply["sms_message_sid"], "sms-1")

    def test_database_storage_is_enabled_by_database_url(self):
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://example"}):
            self.assertTrue(reply_state.should_use_database_storage())

    def test_saves_and_clears_reply_clarification(self):
        saved = reply_state.save_reply_clarification(
            "Yes, that works.",
            ["FIRST", "SECOND"],
        )

        loaded = reply_state.load_reply_clarification()

        self.assertEqual(loaded["host_reply_text"], "Yes, that works.")
        self.assertEqual(loaded["candidate_reply_ids"], ["FIRST", "SECOND"])
        self.assertEqual(saved["candidate_reply_ids"], ["FIRST", "SECOND"])

        reply_state.clear_reply_clarification()

        self.assertIsNone(reply_state.load_reply_clarification())

    def test_clarification_expires_after_six_hours(self):
        clarification = {
            "created_at": (
                datetime.now(timezone.utc) - timedelta(hours=6, minutes=1)
            ).isoformat(),
            "host_reply_text": "Yes.",
            "candidate_reply_ids": ["FIRST"],
        }

        self.assertTrue(reply_state.is_clarification_expired(clarification))

    def test_clarification_selection_uses_number(self):
        pending_replies = {
            "FIRST": {"reply_id": "FIRST"},
            "SECOND": {"reply_id": "SECOND"},
        }
        clarification = {
            "candidate_reply_ids": ["FIRST", "SECOND"],
        }

        pending_reply, reply_id, error = reply_state.parse_clarification_selection(
            "2",
            clarification,
            pending_replies,
        )

        self.assertEqual(error, "")
        self.assertEqual(reply_id, "SECOND")
        self.assertEqual(pending_reply["reply_id"], "SECOND")

    def test_clarification_selection_uses_unambiguous_guest_name(self):
        pending_replies = {
            "FIRST": {
                "reply_id": "FIRST",
                "parsed_email": {"guest_name": "Amit"},
            },
            "SECOND": {
                "reply_id": "SECOND",
                "parsed_email": {"guest_name": "Ryan"},
            },
        }
        clarification = {
            "candidate_reply_ids": ["FIRST", "SECOND"],
        }

        pending_reply, reply_id, error = reply_state.parse_clarification_selection(
            "Amit",
            clarification,
            pending_replies,
        )

        self.assertEqual(error, "")
        self.assertEqual(reply_id, "FIRST")
        self.assertEqual(pending_reply["parsed_email"]["guest_name"], "Amit")


if __name__ == "__main__":
    unittest.main()
