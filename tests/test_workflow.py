import json
import os
import unittest
from unittest.mock import patch

from app import Service
from service import ATTACK, NORMAL


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.service = Service(":memory:")
        self.addCleanup(self.service.db.close)

    def test_normal_workflow_requires_two_independent_approvals(self):
        result = self.service.plan(NORMAL, "fixture")
        state = self.service.state()
        self.assertEqual(len(state["events"]), 2)
        self.assertEqual(state["grants"], [])
        self.assertEqual(state["outbox"], [])
        pending = [item for item in result["results"] if item["status"] == "pending"]
        self.assertEqual(len(pending), 2)
        self.service.approve(pending[0]["approval_id"], False)
        self.service.approve(pending[1]["approval_id"])
        self.assertEqual(self.service.state()["outbox"], [])
        self.assertEqual(
            self.service.state()["grants"],
            [{"user_id": "A", "project": "Alpha", "role": "member"}],
        )

    def test_attack_is_blocked_before_access_approval_without_editing_mail(self):
        original = self.service.state()["mails"]
        result = self.service.plan(ATTACK, "fixture", "attack1")
        self.assertEqual(result["results"][-1]["status"], "blocked")
        state = self.service.state()
        self.assertEqual(state["mails"], original)
        self.assertEqual(state["grants"], [])
        self.assertTrue(
            all(
                json.loads(row["action"])["tool"] == "send_email"
                for row in state["approvals"]
            )
        )

    def test_private_mail_cannot_be_selected(self):
        with self.assertRaises(ValueError):
            self.service.plan(NORMAL, "fixture", "private_b")
        self.assertEqual(self.service.state()["approvals"], [])

    def test_live_loop_returns_tool_results_and_blocks_forbidden_request(self):
        replies = [
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "bad",
                        "type": "function",
                        "function": {
                            "name": "grant_access",
                            "arguments": json.dumps(
                                {"user_id": "B", "project": "Finance", "role": "admin"}
                            ),
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "Forbidden access was blocked."},
        ]
        requests = []

        def fake_open(request, timeout):
            import io

            requests.append(json.loads(request.data))
            return io.BytesIO(
                json.dumps({"choices": [{"message": replies.pop(0)}]}).encode()
            )

        with patch.dict(
            os.environ,
            {
                "LLM_API_KEY": "test",
                "LLM_MODEL": "test",
                "LLM_CHAT_URL": "https://example.test/chat",
            },
        ):
            with patch("planner.urllib.request.urlopen", side_effect=fake_open):
                result = self.service.plan(ATTACK, "api")
        self.assertEqual(len(requests), 2)
        self.assertEqual(
            json.loads(requests[1]["messages"][-1]["content"])["status"], "blocked"
        )
        self.assertEqual(result["results"][-1]["status"], "blocked")
        self.assertEqual(self.service.state()["grants"], [])
        self.assertEqual(self.service.state()["approvals"], [])


if __name__ == "__main__":
    unittest.main()
