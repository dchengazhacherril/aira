import json
import os
import unittest
from unittest.mock import patch

from aira import response_agent
from aira.reply_engine import generate_reply_plan


class ResponseAgentTest(unittest.TestCase):
    def test_response_agent_is_disabled_without_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            self.assertFalse(response_agent.should_use_response_agent())

    def test_parse_agent_json_output_normalizes_plan(self):
        plan = response_agent.parse_agent_json_output(
            json.dumps(
                {
                    "suggested_reply": "Hi! Street parking is free nearby.",
                    "confidence": "HIGH",
                    "message_type": "parking",
                    "reason": "Used parking memory.",
                    "memory_candidates": [{"field": "parking_notes"}],
                }
            )
        )

        self.assertEqual(plan["suggested_reply"], "Hi! Street parking is free nearby.")
        self.assertEqual(plan["confidence"], "high")
        self.assertFalse(plan["needs_manual_review"])
        self.assertEqual(plan["message_type"], "parking")
        self.assertEqual(plan["source"], "response_agent")

    def test_generate_reply_plan_uses_agent_when_configured(self):
        parsed_email = {
            "guest_name": "Niyati",
            "sender_role": "guest",
            "listing_name": "BeltLine",
            "guest_message_body": "Do you have umbrellas?",
        }
        host_memory = {
            "profile": {"parking_notes": "Street parking is free."},
            "preferences": {"sign_off": "Thanks!"},
            "playbooks": {},
        }

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("aira.response_agent.run_response_agent") as run_agent:
                run_agent.return_value = json.dumps(
                    {
                        "suggested_reply": (
                            "Hi! I do not have umbrellas at the property, "
                            "but I can look into adding one."
                        ),
                        "confidence": "medium",
                        "message_type": "amenity_unknown",
                        "reason": "No umbrella memory found.",
                        "memory_candidates": [],
                    }
                )

                plan = generate_reply_plan(parsed_email, host_memory)

        self.assertEqual(plan["source"], "response_agent")
        self.assertEqual(plan["confidence"], "medium")
        self.assertFalse(plan["needs_manual_review"])
        self.assertIn("do not have umbrellas", plan["suggested_reply"])

    def test_generate_reply_plan_falls_back_when_agent_fails(self):
        parsed_email = {
            "guest_message_body": "Where should I put the trash?",
        }
        host_memory = {
            "profile": {
                "trash_notes": "Trash goes in the bins behind the garage.",
            },
            "preferences": {},
            "playbooks": {
                "trash": {
                    "required_profile_fields": ["trash_notes"],
                    "response_template": "{trash_notes}",
                },
            },
        }

        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("aira.response_agent.run_response_agent", side_effect=RuntimeError):
                plan = generate_reply_plan(parsed_email, host_memory)

        self.assertEqual(plan["source"], "rules")
        self.assertEqual(plan["confidence"], "high")
        self.assertIn("behind the garage", plan["suggested_reply"])


if __name__ == "__main__":
    unittest.main()
