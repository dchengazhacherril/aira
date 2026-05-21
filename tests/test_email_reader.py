import unittest
import json
import os
from unittest.mock import patch

from aira import email_reader


class EmailReaderTest(unittest.TestCase):
    def test_newest_airbnb_email_query_only_includes_reply_capable_sender(self):
        with patch("aira.email_reader.get_newest_message_by_query") as get_message:
            get_message.return_value = None

            email_reader.get_newest_unread_airbnb_email()

        query = get_message.call_args.args[0]
        self.assertIn("from:express@airbnb.com", query)
        self.assertNotIn("from:automated@airbnb.com", query)
        self.assertIn("is:unread", query)

    def test_reservation_email_query_includes_automated_sender(self):
        with patch("aira.email_reader.get_messages_by_query") as get_messages:
            get_messages.return_value = []

            email_reader.get_unread_airbnb_reservation_emails()

        query = get_messages.call_args.args[0]
        self.assertIn("from:automated@airbnb.com", query)
        self.assertIn("from:express@airbnb.com", query)
        self.assertIn("is:unread", query)

    def test_token_json_env_can_replace_local_token_file(self):
        token_data = {
            "token": "access-token",
            "refresh_token": "refresh-token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "scopes": email_reader.SCOPES,
        }

        with patch.dict(os.environ, {"GMAIL_TOKEN_JSON": json.dumps(token_data)}):
            with patch("aira.email_reader.os.path.exists", return_value=False):
                self.assertTrue(email_reader.token_file_has_required_scopes())


if __name__ == "__main__":
    unittest.main()
