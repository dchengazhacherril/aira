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

    def test_parses_listing_inquiry_as_relevant(self):
        email_body = """
Inquiry for 2BR King Bed | BeltLine, MLK Park, Mercedes-Benz for Jun 24 – 28, 2026
Elena
Guest
Hi, is the backyard fully fenced for my dog?
Reply
https://www.airbnb.com/hosting/thread/2505708035?inbox_type=host
Home - Entire home/apt hosted by David
"""

        parsed = parse_airbnb_email(
            email_body,
            "Inquiry for 2BR King Bed | BeltLine, MLK Park, Mercedes-Benz for Jun 24 – 28, 2026",
        )

        self.assertEqual(parsed["guest_name"], "Elena")
        self.assertEqual(
            parsed["listing_name"],
            "2BR King Bed | BeltLine, MLK Park, Mercedes-Benz",
        )
        self.assertEqual(parsed["sender_role"], "guest")
        self.assertTrue(parsed["is_relevant_message"])
        self.assertEqual(
            parsed["guest_message_body"],
            "Hi, is the backyard fully fenced for my dog?",
        )

    def test_parses_automated_airbnb_inquiry_format(self):
        email_body = """
RESPOND TO NATHAN’S INQUIRY

Nathan

Identity verified · 9 reviews

Atlanta, GA

Hi! Does there happen to be a grill out back? And walkable
coffee shop? Thanks !

Pre-approve / DeclinePre-approve / Decline

2BR KING BED | BELTLINE, MLK PARK, MERCEDES-BENZ

Entire home/apt

YOU HAVE 24 HOURS TO RESPOND
"""

        parsed = parse_airbnb_email(
            email_body,
            "Inquiry for 2BR King Bed | BeltLine, MLK Park, Mercedes-Benz for Jun 24 – 28, 2026",
        )

        self.assertEqual(parsed["guest_name"], "Nathan")
        self.assertEqual(parsed["sender_role"], "guest")
        self.assertTrue(parsed["is_relevant_message"])
        self.assertEqual(
            parsed["guest_message_body"],
            "Hi! Does there happen to be a grill out back? And walkable\ncoffee shop? Thanks !",
        )

    def test_ignores_automated_reservation_reminder(self):
        email_body = """
ELENA ARRIVES THURSDAY, MAY 14.

If you haven’t already, reach out to Elena to send
directions and coordinate check-in time.

Elena Volk

Identity verified · 1 review

Send Elena a MessageSend Elena a Message

2BR KING BED | BELTLINE, MLK PARK, MERCEDES-BENZ

Entire home/apt
"""

        parsed = parse_airbnb_email(
            email_body,
            "Reservation reminder: Elena is coming soon!",
        )

        self.assertFalse(parsed["is_relevant_message"])


if __name__ == "__main__":
    unittest.main()
