import unittest
from unittest.mock import patch

from aira.reply_server import ReplyServer


class FakeProcess:
    def __init__(self, poll_result=None):
        self.poll_result = poll_result

    def poll(self):
        return self.poll_result


class ReplyServerTest(unittest.TestCase):
    def make_reply_server(self):
        reply_server = ReplyServer()
        reply_server.webhook_process = FakeProcess()
        reply_server.tunnel_process = FakeProcess()
        return reply_server

    def test_monitor_pending_reply_stops_when_reply_is_cleared(self):
        reply_server = self.make_reply_server()

        with patch("aira.reply_server.load_pending_reply", return_value=None):
            resolved = reply_server.monitor_pending_reply(
                "ABC123",
                timeout_seconds=30,
            )

        self.assertTrue(resolved)

    def test_monitor_pending_reply_times_out_when_reply_remains(self):
        reply_server = self.make_reply_server()

        with patch("aira.reply_server.load_pending_reply", return_value={"reply_id": "ABC123"}):
            resolved = reply_server.monitor_pending_reply(
                "ABC123",
                timeout_seconds=0,
            )

        self.assertFalse(resolved)


if __name__ == "__main__":
    unittest.main()
