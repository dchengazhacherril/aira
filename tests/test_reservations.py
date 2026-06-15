import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from aira import reservations


def make_reservation(
    reservation_id,
    guest_name,
    listing_name,
    checkin_date,
    checkout_date,
    total_guests=2,
    adults=2,
    infants=0,
):
    return {
        "reservation_id": reservation_id,
        "guest_name": guest_name,
        "listing_name": listing_name,
        "checkin_date": checkin_date,
        "checkout_date": checkout_date,
        "nights": reservations.calculate_nights(checkin_date, checkout_date),
        "guest_counts": {
            "total_guests": total_guests,
            "adults": adults,
            "children": 0,
            "infants": infants,
            "pets": 0,
        },
    }


class ReservationsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.patches = [
            patch.dict(os.environ, {"DATABASE_URL": ""}),
            patch.object(reservations, "LOCAL_DIR", self.temp_dir.name),
            patch.object(
                reservations,
                "RESERVATIONS_PATH",
                os.path.join(self.temp_dir.name, "reservations.json"),
            ),
            patch.object(
                reservations,
                "RESERVATION_ALERTS_PATH",
                os.path.join(self.temp_dir.name, "reservation_alerts.json"),
            ),
        ]
        for active_patch in self.patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def test_parses_reservation_confirmed_email(self):
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

        reservation = reservations.parse_reservation_email(
            message,
            reference_year=2026,
        )

        self.assertEqual(reservation["guest_name"], "Taylor Ford")
        self.assertEqual(reservation["listing_name"], "2BR King Bed | BeltLine")
        self.assertEqual(reservation["checkin_date"], "2026-05-28")
        self.assertEqual(reservation["checkout_date"], "2026-05-31")
        self.assertEqual(reservation["nights"], 3)
        self.assertEqual(reservation["guest_counts"]["total_guests"], 4)
        self.assertEqual(reservation["guest_counts"]["infants"], 1)

    def test_parses_split_checkin_checkout_labels(self):
        message = {
            "id": "gmail-maggie",
            "thread_id": "thread-maggie",
            "subject": "Reservation confirmed - Maggie Banks arrives Jun 14",
            "body": """
RESERVATION DETAILS
2BR KING | WORLD CUP STAY NEAR STADIUM + BELTLINE
Home - hosted by David
Check-in
Sun, Jun 14
Checkout
Wed, Jun 17, 2026
3 adults
3 dogs
""",
        }

        reservation = reservations.parse_reservation_email(
            message,
            reference_year=2026,
        )

        self.assertEqual(reservation["guest_name"], "Maggie Banks")
        self.assertEqual(
            reservation["listing_name"],
            "2BR KING | WORLD CUP STAY NEAR STADIUM + BELTLINE",
        )
        self.assertEqual(reservation["checkin_date"], "2026-06-14")
        self.assertEqual(reservation["checkout_date"], "2026-06-17")
        self.assertEqual(reservation["nights"], 3)
        self.assertEqual(reservation["guest_counts"]["adults"], 3)
        self.assertEqual(reservation["guest_counts"]["pets"], 3)

    def test_derives_checkout_from_nights_when_checkout_label_is_missing(self):
        message = {
            "id": "gmail-maggie",
            "thread_id": "thread-maggie",
            "subject": "Reservation confirmed - Maggie Banks arrives Jun 14",
            "body": """
RESERVATION DETAILS
2BR KING | WORLD CUP STAY NEAR STADIUM + BELTLINE
Home - hosted by David
3 nights
3 adults
3 pets
""",
        }

        reservation = reservations.parse_reservation_email(
            message,
            reference_year=2026,
        )

        self.assertEqual(reservation["checkin_date"], "2026-06-14")
        self.assertEqual(reservation["checkout_date"], "2026-06-17")
        self.assertEqual(reservation["nights"], 3)

    def test_due_alerts_include_checkin_and_turnover_at_noon(self):
        checkout_guest = make_reservation(
            "RYAN",
            "Ryan",
            "BeltLine",
            "2026-05-18",
            "2026-05-21",
        )
        checkin_guest = make_reservation(
            "AMIT",
            "Amit",
            "BeltLine",
            "2026-05-21",
            "2026-05-24",
            total_guests=4,
            adults=3,
            infants=1,
        )
        now = datetime(2026, 5, 20, 12, 0, tzinfo=ZoneInfo("America/New_York"))

        alerts = reservations.get_due_reservation_alerts(
            {
                checkout_guest["reservation_id"]: checkout_guest,
                checkin_guest["reservation_id"]: checkin_guest,
            },
            now=now,
        )

        self.assertEqual(len(alerts), 1)
        self.assertIn("Turnover tomorrow", alerts[0]["message"])
        self.assertIn("Amit", alerts[0]["message"])
        self.assertIn("4 total (3 adults, 1 infant)", alerts[0]["message"])

    def test_infant_alerts_include_baby_gear_memory_when_available(self):
        checkin_guest = make_reservation(
            "WILLIAM",
            "William",
            "BeltLine",
            "2026-05-21",
            "2026-05-24",
            total_guests=3,
            adults=2,
            infants=1,
        )
        host_memory = {
            "profile": {
                "baby_gear_notes": "Travel crib and high chair are available.",
            }
        }
        now = datetime(2026, 5, 21, 12, 0, tzinfo=ZoneInfo("America/New_York"))

        alerts = reservations.get_due_reservation_alerts(
            {checkin_guest["reservation_id"]: checkin_guest},
            now=now,
            host_memory=host_memory,
        )

        self.assertEqual(len(alerts), 1)
        self.assertIn("William checks in today", alerts[0]["message"])
        self.assertIn("3 total (2 adults, 1 infant)", alerts[0]["message"])
        self.assertIn(
            "Infant prep: Travel crib and high chair are available.",
            alerts[0]["message"],
        )

    def test_checkout_alert_mentions_next_guest_within_seven_days(self):
        checkout_guest = make_reservation(
            "RYAN",
            "Ryan",
            "BeltLine",
            "2026-05-18",
            "2026-05-21",
        )
        next_guest = make_reservation(
            "AMIT",
            "Amit",
            "BeltLine",
            "2026-05-24",
            "2026-05-27",
        )
        now = datetime(2026, 5, 21, 12, 0, tzinfo=ZoneInfo("America/New_York"))

        alerts = reservations.get_due_reservation_alerts(
            {
                checkout_guest["reservation_id"]: checkout_guest,
                next_guest["reservation_id"]: next_guest,
            },
            now=now,
        )

        self.assertEqual(len(alerts), 1)
        self.assertIn("Ryan checks out today", alerts[0]["message"])
        self.assertIn("Next guest checks in in 3 days", alerts[0]["message"])

    def test_checkout_alert_ignored_when_next_guest_more_than_seven_days_out(self):
        checkout_guest = make_reservation(
            "RYAN",
            "Ryan",
            "BeltLine",
            "2026-05-18",
            "2026-05-21",
        )
        next_guest = make_reservation(
            "AMIT",
            "Amit",
            "BeltLine",
            "2026-05-29",
            "2026-06-01",
        )
        now = datetime(2026, 5, 21, 12, 0, tzinfo=ZoneInfo("America/New_York"))

        alerts = reservations.get_due_reservation_alerts(
            {
                checkout_guest["reservation_id"]: checkout_guest,
                next_guest["reservation_id"]: next_guest,
            },
            now=now,
        )

        self.assertEqual(alerts, [])

    def test_alerts_are_not_due_outside_noon_hour(self):
        checkin_guest = make_reservation(
            "AMIT",
            "Amit",
            "BeltLine",
            "2026-05-21",
            "2026-05-24",
        )
        now = datetime(2026, 5, 21, 11, 0, tzinfo=ZoneInfo("America/New_York"))

        alerts = reservations.get_due_reservation_alerts(
            {checkin_guest["reservation_id"]: checkin_guest},
            now=now,
        )

        self.assertEqual(alerts, [])

    def test_sent_alerts_are_deduped(self):
        checkin_guest = make_reservation(
            "AMIT",
            "Amit",
            "BeltLine",
            "2026-05-21",
            "2026-05-24",
        )
        now = datetime(2026, 5, 21, 12, 0, tzinfo=ZoneInfo("America/New_York"))
        alert_key = "checkin:AMIT:2026-05-21"
        reservations.mark_alert_sent(alert_key, sent_at=now)

        alerts = reservations.get_due_reservation_alerts(
            {checkin_guest["reservation_id"]: checkin_guest},
            now=now,
        )

        self.assertEqual(alerts, [])


if __name__ == "__main__":
    unittest.main()
