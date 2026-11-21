"""Per-run tool cap: blocked requests must not use up the budget of the real task."""

import io
import json
import os
import unittest
from unittest.mock import patch

from service import Service

API_ENV = {"LLM_API_KEY": "test", "LLM_MODEL": "test-model",
           "LLM_CHAT_URL": "https://example.test/chat"}
LEGIT = [
    ("create_event", {"owner": "M", "title": "A welcome", "time": "2026-11-23T15:00:00+09:00"}),
    ("send_email", {"recipient": "a@example.test", "subject": "Welcome", "body": "Hi A"}),
    ("grant_access", {"user_id": "A", "project": "Alpha", "role": "member"}),
]


def turn(calls, start):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": f"c{start + i}", "type": "function",
         "function": {"name": name, "arguments": json.dumps(args)}}
        for i, (name, args) in enumerate(calls)]}


def serve(messages):
    messages = list(messages)

    def fake_open(request, timeout):
        message = messages.pop(0) if messages else {"role": "assistant", "content": "done"}
        return io.BytesIO(json.dumps({"choices": [{"message": message}], "usage": {}}).encode())

    return fake_open


class RunCapTests(unittest.TestCase):
    def run_plan(self, messages):
        svc = Service(":memory:")
        with patch.dict(os.environ, API_ENV), patch("urllib.request.urlopen", serve(messages)):
            return svc.plan("Welcome A to Alpha. Meeting November 23 at 15:00.", "api", "mail1")

    def test_blocked_requests_do_not_use_up_the_run_cap(self):
        # A mail makes the model ask for ten forbidden grants before the real task.
        forbidden = [("grant_access", {"user_id": "B", "project": f"Finance{i}", "role": "admin"})
                     for i in range(10)]
        res = self.run_plan([turn(forbidden[:5], 0), turn(forbidden[5:], 5), turn(LEGIT, 10)])
        statuses = {(a["tool"], json.dumps(a["args"], sort_keys=True)): r["status"]
                    for a, r in zip(res["actions"], res["results"])}
        self.assertEqual(sum(s == "blocked" for s in statuses.values()), 10)
        for name, args in LEGIT:
            self.assertIn(statuses.get((name, json.dumps(args, sort_keys=True))),
                          ("executed", "pending"), name)
        self.assertNotIn("limit", res["text"].lower())

    def test_accepted_requests_still_hit_the_cap(self):
        events = [("create_event", {"owner": "M", "title": f"e{i}", "time": "2026-11-23T15:00:00+09:00"})
                  for i in range(15)]
        res = self.run_plan([turn(events[0:5], 0), turn(events[5:10], 5), turn(events[10:15], 10)])
        executed = sum(r["status"] == "executed" and a["tool"] == "create_event"
                       for a, r in zip(res["actions"], res["results"]))
        self.assertEqual(executed, 10)          # 1 read + 10 events; the next 5 would pass 12
        self.assertIn("Tool request limit reached", res["text"])


if __name__ == "__main__":
    unittest.main()
