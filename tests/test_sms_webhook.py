import os
import unittest
from unittest.mock import patch

from aira import sms_webhook


class SmsWebhookTest(unittest.TestCase):
    def test_signature_validation_can_be_disabled_for_manual_testing(self):
        with patch.dict(os.environ, {"TWILIO_VALIDATE_REQUESTS": "false"}):
            self.assertFalse(sms_webhook.should_validate_twilio_requests())

    def test_build_twiml_response_escapes_message_text(self):
        response = sms_webhook.build_twiml_response("A & B < C")

        self.assertIn("A &amp; B &lt; C", response)


if __name__ == "__main__":
    unittest.main()
