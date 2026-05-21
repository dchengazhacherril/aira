import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from scripts import check_reservations


class CheckReservationsTest(unittest.TestCase):
    def test_check_reservations_ingests_and_sends_due_alerts(self):
        message = {
            "id": "gmail-1",
            "thread_id": "thread-1",
            "subject": "Reservation confirmed - Taylor Ford arrives May 28",
            "body": """
RESERVATION DETAILS
2BR King Bed | BeltLine
Home - hosted by David
May 28 – May 31, 2026
4 guests
3 adults
1 infant
""",
        }
        now = datetime(2026, 5, 28, 12, 0, tzinfo=ZoneInfo("America/New_York"))

        with patch(
            "scripts.check_reservations.get_unread_airbnb_reservation_emails",
            return_value=[message],
        ):
            with patch("scripts.check_reservations.upsert_reservation") as upsert:
                upsert.return_value = "TAYLOR"
                with patch("scripts.check_reservations.mark_message_read") as mark_read:
                    with patch(
                        "scripts.check_reservations.load_reservations",
                        return_value={
                            "TAYLOR": {
                                "reservation_id": "TAYLOR",
                                "guest_name": "Taylor Ford",
                                "listing_name": "2BR King Bed | BeltLine",
                                "checkin_date": "2026-05-28",
                                "checkout_date": "2026-05-31",
                                "nights": 3,
                                "guest_counts": {
                                    "total_guests": 4,
                                    "adults": 3,
                                    "children": 0,
                                    "infants": 1,
                                    "pets": 0,
                                },
                            }
                        },
                    ):
                        with patch(
                            "scripts.check_reservations.send_sms",
                            return_value="SM123",
                        ) as send_sms:
                            with patch("scripts.check_reservations.mark_alert_sent") as mark_alert:
                                result = check_reservations.check_reservations_once(
                                    now=now,
                                )

        self.assertEqual(result["parsed_count"], 1)
        self.assertEqual(result["sent_count"], 1)
        upsert.assert_called_once()
        mark_read.assert_called_once_with("gmail-1")
        send_sms.assert_called_once()
        mark_alert.assert_called_once()


if __name__ == "__main__":
    unittest.main()
