import io
import json
import os
import unittest
from unittest.mock import patch

from planner import llm_config, local_model_info
from service import ATTACK, Service

LOCAL = {"LLM_CHAT_URL": "http://localhost:11434/v1/chat/completions",
         "LLM_MODEL": "qwen2.5:3b", "LLM_API_KEY": ""}


class ConfigTests(unittest.TestCase):
    def test_local_http_needs_no_key(self):
        with patch.dict(os.environ, LOCAL):
            config = llm_config()
        self.assertTrue(config["local"])
        self.assertIsNone(config["key"])

    def test_defaults_point_to_local_ollama(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("LLM_")}
        with patch.dict(os.environ, env, clear=True):
            config = llm_config()
        self.assertTrue(config["local"])
        self.assertTrue(config["url"].startswith("http://localhost:11434/"))

    def test_remote_plain_http_is_rejected(self):
        with patch.dict(os.environ, dict(LOCAL, LLM_CHAT_URL="http://example.test/v1/chat/completions")):
            with self.assertRaises(ValueError):
                llm_config()

    def test_remote_https_needs_key(self):
        with patch.dict(os.environ, dict(LOCAL, LLM_CHAT_URL="https://example.test/v1/chat/completions")):
            with self.assertRaises(ValueError):
                llm_config()


class LocalServerTests(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:")
        self.addCleanup(self.s.db.close)

    def test_object_arguments_and_missing_ids_are_accepted(self):
        """Some local servers send arguments as an object and omit call IDs."""
        replies = [
            {"role": "assistant", "content": None, "tool_calls": [
                {"type": "function", "function": {
                    "name": "grant_access",
                    "arguments": {"user_id": "B", "project": "Finance", "role": "admin"}}},
            ]},
            {"role": "assistant", "content": "Blocked."},
        ]
        sent = []

        def fake_open(request, timeout):
            sent.append(request)
            message = replies.pop(0) if len(replies) > 1 else replies[0]
            body = {"choices": [{"message": message}]}
            return io.BytesIO(json.dumps(body).encode())

        with patch.dict(os.environ, LOCAL):
            with patch("planner.urllib.request.urlopen", side_effect=fake_open):
                result = self.s.plan(ATTACK, "api")
        self.assertEqual(result["results"][-1]["status"], "blocked")
        self.assertEqual(result["mode"], "local LLM")
        self.assertNotIn("Authorization", sent[0].headers)
        second = json.loads(sent[1].data)["messages"]
        self.assertEqual(second[-2]["tool_calls"][0]["id"], second[-1]["tool_call_id"])

    def test_model_digest_is_read_from_ollama(self):
        tags = {"models": [{"name": "qwen2.5:3b", "digest": "abc123", "size": 1900000000,
                            "details": {"format": "gguf", "parameter_size": "3.1B",
                                        "quantization_level": "Q4_K_M"}}]}
        with patch("planner.urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(tags).encode())):
            with patch.dict(os.environ, LOCAL):
                info = local_model_info(llm_config())
        self.assertEqual(info["digest"], "abc123")
        self.assertEqual(info["quantization"], "Q4_K_M")
        with patch("planner.urllib.request.urlopen",
                   return_value=io.BytesIO(json.dumps(tags).encode())):
            with patch.dict(os.environ, dict(LOCAL, LLM_MODEL="llama3.1:8b")):
                self.assertTrue(local_model_info(llm_config())["missing"])


if __name__ == "__main__":
    unittest.main()
