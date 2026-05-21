import os
import unittest
from unittest.mock import patch

from scripts import railway_entrypoint


class RailwayEntrypointTest(unittest.TestCase):
    def test_checker_role_comes_from_service_name(self):
        with patch.dict(os.environ, {"RAILWAY_SERVICE_NAME": "aira-checker"}):
            self.assertEqual(railway_entrypoint.get_service_role(), "checker")

    def test_reservations_role_comes_from_service_name(self):
        with patch.dict(os.environ, {"RAILWAY_SERVICE_NAME": "aira-reservations"}):
            self.assertEqual(railway_entrypoint.get_service_role(), "reservations")

    def test_webhook_is_default_role(self):
        with patch.dict(os.environ, {"RAILWAY_SERVICE_NAME": "aira-webhook"}):
            self.assertEqual(railway_entrypoint.get_service_role(), "webhook")

    def test_explicit_role_overrides_service_name(self):
        with patch.dict(
            os.environ,
            {
                "AIRA_RAILWAY_ROLE": "checker",
                "RAILWAY_SERVICE_NAME": "anything",
            },
        ):
            self.assertEqual(railway_entrypoint.get_service_role(), "checker")


if __name__ == "__main__":
    unittest.main()
