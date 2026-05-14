import unittest
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


if __name__ == "__main__":
    unittest.main()
