import os
import tempfile
import unittest
from unittest.mock import patch

from aira import reply_state


class ReplyStateTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.pending_path = os.path.join(self.temp_dir.name, "pending_replies.json")
        self.legacy_path = os.path.join(self.temp_dir.name, "pending_reply.json")
        self.patches = [
            patch.dict(os.environ, {"DATABASE_URL": ""}),
            patch.object(reply_state, "LOCAL_DIR", self.temp_dir.name),
            patch.object(reply_state, "PENDING_REPLIES_PATH", self.pending_path),
            patch.object(reply_state, "LEGACY_PENDING_REPLY_PATH", self.legacy_path),
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


if __name__ == "__main__":
    unittest.main()
