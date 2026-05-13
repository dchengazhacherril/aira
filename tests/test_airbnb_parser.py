import unittest

from aira.airbnb_parser import parse_airbnb_email


class AirbnbParserTest(unittest.TestCase):
    def test_parses_guest_message_as_relevant(self):
        email_body = """
YOU’VE GOT A NEW MESSAGE
Jordan
Guest
Hi, what is the wifi password?
Reply
RESERVATION DETAILS
Lake House
Home - hosted by David
https://www.airbnb.com/hosting/thread/123
"""

        parsed = parse_airbnb_email(email_body, "Message from Jordan about Lake House")

        self.assertEqual(parsed["guest_name"], "Jordan")
        self.assertEqual(parsed["sender_role"], "guest")
        self.assertTrue(parsed["is_relevant_message"])
        self.assertEqual(parsed["guest_message_body"], "Hi, what is the wifi password?")

    def test_ignores_host_originated_message(self):
        email_body = """
YOU’VE GOT A NEW MESSAGE
David
Host
Thanks, I sent the details.
Reply
Home - hosted by David
"""

        parsed = parse_airbnb_email(email_body, "Message from David")

        self.assertEqual(parsed["sender_role"], "host")
        self.assertFalse(parsed["is_relevant_message"])


if __name__ == "__main__":
    unittest.main()
