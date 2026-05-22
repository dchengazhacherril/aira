import json
import os
import tempfile
import unittest
from unittest.mock import patch

from aira import reply_state
from aira import sms_webhook


class SmsWebhookTest(unittest.TestCase):
    def use_temp_reply_state(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        patches = [
            patch.dict(os.environ, {"DATABASE_URL": ""}),
            patch.object(reply_state, "LOCAL_DIR", temp_dir.name),
            patch.object(
                reply_state,
                "PENDING_REPLIES_PATH",
                os.path.join(temp_dir.name, "pending_replies.json"),
            ),
            patch.object(
                reply_state,
                "LEGACY_PENDING_REPLY_PATH",
                os.path.join(temp_dir.name, "pending_reply.json"),
            ),
            patch.object(
                reply_state,
                "REPLY_CLARIFICATION_PATH",
                os.path.join(temp_dir.name, "reply_clarification.json"),
            ),
            patch.object(
                reply_state,
                "RECENT_REPLY_CONTEXT_PATH",
                os.path.join(temp_dir.name, "recent_reply_context.json"),
            ),
        ]
        for active_patch in patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def save_pending_reply(self, reply_id, guest_name, body):
        return reply_state.save_pending_reply(
            {
                "id": f"gmail-{reply_id}",
                "thread_id": f"thread-{reply_id}",
            },
            {
                "guest_name": guest_name,
                "guest_message_body": body,
            },
            {
                "suggested_reply": "Suggested reply.",
                "needs_manual_review": False,
                "message_type": "other",
            },
            f"sms-{reply_id}",
            reply_id=reply_id,
        )

    def test_signature_validation_can_be_disabled_for_manual_testing(self):
        with patch.dict(os.environ, {"TWILIO_VALIDATE_REQUESTS": "false"}):
            self.assertFalse(sms_webhook.should_validate_twilio_requests())

    def test_build_twiml_response_escapes_message_text(self):
        response = sms_webhook.build_twiml_response("A & B < C")

        self.assertIn("A &amp; B &lt; C", response)

    def test_listen_port_prefers_platform_port(self):
        with patch.dict(
            os.environ,
            {"PORT": "12345", "SMS_WEBHOOK_PORT": "8000"},
        ):
            self.assertEqual(sms_webhook.get_listen_port(), 12345)

    def test_success_confirmation_hides_gmail_message_id(self):
        pending_reply = {
            "reply_plan": {
                "suggested_reply": "Suggested reply.",
                "needs_manual_review": False,
            },
            "original_message": {
                "id": "gmail-source",
                "thread_id": "gmail-thread",
            },
        }

        with patch.dict(os.environ, {"MY_PHONE_NUMBER": "+15555555555"}):
            with patch("aira.sms_webhook.resolve_pending_reply") as resolve_pending:
                with patch("aira.sms_webhook.send_reply_email", return_value="gmail-sent-id"):
                    with patch("aira.sms_webhook.clear_pending_reply"):
                        resolve_pending.return_value = (pending_reply, "ABC123", "")

                        response = sms_webhook.handle_inbound_sms("+15555555555", "SEND")

        self.assertEqual(response, "Sent Airbnb reply.")
        self.assertNotIn("gmail-sent-id", response)

    def test_edited_reply_learns_fact_and_mentions_memory(self):
        pending_reply = {
            "reply_plan": {
                "suggested_reply": "Please review.",
                "needs_manual_review": True,
                "message_type": "trash",
            },
            "parsed_email": {
                "guest_message_body": "Where should I put the trash?",
            },
            "original_message": {
                "id": "gmail-source",
                "thread_id": "gmail-thread",
            },
        }

        with patch.dict(os.environ, {"MY_PHONE_NUMBER": "+15555555555"}):
            with patch("aira.sms_webhook.resolve_pending_reply") as resolve_pending:
                with patch("aira.sms_webhook.send_reply_email", return_value="gmail-sent-id"):
                    with patch("aira.sms_webhook.clear_pending_reply"):
                        with patch("aira.sms_webhook.learn_from_edited_reply") as learn:
                            resolve_pending.return_value = (pending_reply, "ABC123", "")
                            learn.return_value = {
                                "message_type": "trash",
                                "profile_field": "trash_notes",
                            }

                            response = sms_webhook.handle_inbound_sms(
                                "+15555555555",
                                "Put trash in the bins behind the garage.",
                            )

        self.assertEqual(
            response,
            "Sent Airbnb reply. I’ll remember that for next time.",
        )

    def test_multiple_pending_plain_reply_asks_which_guest(self):
        self.use_temp_reply_state()
        self.save_pending_reply("FIRST1", "Amit", "Can I refill it instead?")
        self.save_pending_reply("SECOND", "Ryan", "Thanks, checking in later.")

        with patch.dict(os.environ, {"MY_PHONE_NUMBER": "+15555555555"}):
            with patch("aira.sms_webhook.send_reply_email") as send_email:
                response = sms_webhook.handle_inbound_sms(
                    "+15555555555",
                    "Yes, that works.",
                )

        send_email.assert_not_called()
        self.assertIn("Which guest should I send this to?", response)
        self.assertIn("1. Amit", response)
        self.assertIn("2. Ryan", response)

    def test_clarified_number_sends_saved_reply_to_selected_pending_message(self):
        self.use_temp_reply_state()
        self.save_pending_reply("FIRST1", "Amit", "Can I refill it instead?")
        self.save_pending_reply("SECOND", "Ryan", "Thanks, checking in later.")

        with patch.dict(os.environ, {"MY_PHONE_NUMBER": "+15555555555"}):
            sms_webhook.handle_inbound_sms("+15555555555", "Yes, that works.")
            with patch(
                "aira.sms_webhook.send_reply_email",
                return_value="gmail-sent-id",
            ) as send_email:
                response = sms_webhook.handle_inbound_sms("+15555555555", "1")

        send_email.assert_called_once()
        original_message, reply_text = send_email.call_args.args
        self.assertEqual(original_message["id"], "gmail-FIRST1")
        self.assertEqual(reply_text, "Yes, that works.")
        self.assertEqual(response, "Sent Airbnb reply.")
        self.assertIsNone(reply_state.load_pending_reply("FIRST1"))

    def test_cancel_clears_clarification_without_sending(self):
        self.use_temp_reply_state()
        self.save_pending_reply("FIRST1", "Amit", "Can I refill it instead?")
        self.save_pending_reply("SECOND", "Ryan", "Thanks, checking in later.")

        with patch.dict(os.environ, {"MY_PHONE_NUMBER": "+15555555555"}):
            sms_webhook.handle_inbound_sms("+15555555555", "Yes, that works.")
            with patch("aira.sms_webhook.send_reply_email") as send_email:
                response = sms_webhook.handle_inbound_sms("+15555555555", "CANCEL")

        send_email.assert_not_called()
        self.assertEqual(response, "Canceled. No Airbnb reply was sent.")
        self.assertIsNone(reply_state.load_reply_clarification())
        self.assertIsNotNone(reply_state.load_pending_reply("FIRST1"))

    def test_expired_clarification_does_not_send_to_anyone(self):
        self.use_temp_reply_state()
        self.save_pending_reply("FIRST1", "Amit", "Can I refill it instead?")
        reply_state.save_reply_clarification("Yes, that works.", ["FIRST1"])
        clarification = reply_state.load_reply_clarification()
        clarification["created_at"] = "2000-01-01T00:00:00+00:00"
        with open(reply_state.REPLY_CLARIFICATION_PATH, "w") as clarification_file:
            json.dump(clarification, clarification_file)

        with patch.dict(os.environ, {"MY_PHONE_NUMBER": "+15555555555"}):
            with patch("aira.sms_webhook.send_reply_email") as send_email:
                response = sms_webhook.handle_inbound_sms("+15555555555", "1")

        send_email.assert_not_called()
        self.assertIn("clarification expired", response)
        self.assertIsNotNone(reply_state.load_pending_reply("FIRST1"))

    def test_plain_follow_up_continues_recently_selected_thread(self):
        self.use_temp_reply_state()
        self.save_pending_reply("NIYATI", "Niyati", "Do you have umbrellas?")
        self.save_pending_reply("WILLIA", "William", "The code will not work.")

        with patch.dict(os.environ, {"MY_PHONE_NUMBER": "+15555555555"}):
            sms_webhook.handle_inbound_sms(
                "+15555555555",
                "Unfortunately we do not have any umbrellas.",
            )
            with patch(
                "aira.sms_webhook.send_reply_email",
                return_value="gmail-sent-id",
            ) as send_email:
                sms_webhook.handle_inbound_sms("+15555555555", "1")
                response = sms_webhook.handle_inbound_sms(
                    "+15555555555",
                    "That said, I will order one that arrives tomorrow.",
                )

        self.assertEqual(response, "Sent Airbnb reply.")
        self.assertEqual(send_email.call_count, 2)
        first_original_message, first_reply_text = send_email.call_args_list[0].args
        second_original_message, second_reply_text = send_email.call_args_list[1].args
        self.assertEqual(first_original_message["id"], "gmail-NIYATI")
        self.assertEqual(first_reply_text, "Unfortunately we do not have any umbrellas.")
        self.assertEqual(second_original_message["id"], "gmail-NIYATI")
        self.assertEqual(
            second_reply_text,
            "That said, I will order one that arrives tomorrow.",
        )
        self.assertIsNotNone(reply_state.load_pending_reply("WILLIA"))


if __name__ == "__main__":
    unittest.main()
