import json
import os
import unittest
from unittest.mock import patch

from aira import host_memory


class HostMemoryTest(unittest.TestCase):
    def test_current_host_id_can_come_from_env(self):
        with patch.dict(os.environ, {"AIRA_HOST_ID": "railway-host"}):
            self.assertEqual(host_memory.get_current_host_id(), "railway-host")

    def test_default_host_memory_can_come_from_env_json(self):
        env = {
            "HOST_PROFILE_JSON": json.dumps({"trash_notes": "Behind the garage."}),
            "HOST_PREFERENCES_JSON": json.dumps({"tone": "warm"}),
            "HOST_PLAYBOOKS_JSON": json.dumps({"trash": {"enabled": True}}),
        }

        with patch.dict(os.environ, env):
            memory = host_memory.get_default_host_memory("david")

        self.assertEqual(memory["host_id"], "david")
        self.assertEqual(memory["profile"]["trash_notes"], "Behind the garage.")
        self.assertEqual(memory["preferences"]["tone"], "warm")
        self.assertTrue(memory["playbooks"]["trash"]["enabled"])


if __name__ == "__main__":
    unittest.main()
