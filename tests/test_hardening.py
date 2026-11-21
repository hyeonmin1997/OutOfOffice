"""Approval window, token hiding, bad LLM responses, and HTTP request checks."""

import io
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from unittest.mock import patch

import app
from planner import LLMResponseError
from service import NORMAL, Service

API_ENV = {"LLM_API_KEY": "test", "LLM_MODEL": "test-model",
           "LLM_CHAT_URL": "https://example.test/chat"}


def call(cid, name, args):
    return {"id": cid, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def serve(bodies, sent):
    bodies = list(bodies)

    def fake_open(request, timeout):
        sent.append(json.loads(request.data))
        body = bodies.pop(0) if len(bodies) > 1 else bodies[0]
        return io.BytesIO(json.dumps(body).encode())

    return fake_open


class ApprovalWindowTests(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:")

    def tearDown(self):
        self.s.db.close()

    def test_window_opens_after_a_slow_run(self):
        grant = {"user_id": "A", "project": "Alpha", "role": "member"}
        replies = [{"choices": [{"message": {"content": "", "tool_calls": [
            call("c1", "grant_access", grant)]}}]},
            {"choices": [{"message": {"content": "done"}}]}]
        sent = []
        clock = [1000.0]
        with patch.dict(os.environ, API_ENV), \
                patch("planner.urllib.request.urlopen", side_effect=serve(replies, sent)), \
                patch("service.time.time", side_effect=lambda: clock[0]):
            result = self.s.plan(NORMAL, "api")
            clock[0] += 500  # the run went on long after the request was made
            self.s.open_approvals(result["run_id"])
            token = next(r["approval_id"] for r in result["results"] if r["status"] == "pending")
            self.assertEqual(self.s.approve(token)["status"], "executed")

    def test_approval_token_is_not_shown_to_the_model(self):
        grant = {"user_id": "A", "project": "Alpha", "role": "member"}
        replies = [{"choices": [{"message": {"content": "", "tool_calls": [
            call("c1", "grant_access", grant)]}}]},
            {"choices": [{"message": {"content": "done"}}]}]
        sent = []
        with patch.dict(os.environ, API_ENV), \
                patch("planner.urllib.request.urlopen", side_effect=serve(replies, sent)):
            result = self.s.plan(NORMAL, "api")
        token = next(r["approval_id"] for r in result["results"] if r["status"] == "pending")
        self.assertTrue(len(sent) >= 2)
        self.assertNotIn(token, json.dumps(sent))

    def test_bad_llm_response_raises_clear_error(self):
        sent = []
        with patch.dict(os.environ, API_ENV), \
                patch("planner.urllib.request.urlopen",
                      side_effect=serve([{"error": "model not found"}], sent)):
            with self.assertRaises(LLMResponseError):
                self.s.plan(NORMAL, "api")
        self.assertEqual(self.s.state()["model_calls"][-1]["status"], "bad_response")


class HttpTests(unittest.TestCase):
    def setUp(self):
        # SQLite connections belong to one thread: build the service in the server thread.
        ready = threading.Event()

        def run():
            self.s = Service(":memory:")
            self.server = HTTPServer(("127.0.0.1", 0), app.make_handler(self.s))
            ready.set()
            self.server.serve_forever()
            self.server.server_close()
            self.s.db.close()

        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        ready.wait(5)
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(5)

    def send(self, path, data=None, host="127.0.0.1:8000"):
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=None if data is None else json.dumps(data).encode(),
            headers={"Host": host, "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def test_foreign_host_is_denied(self):
        self.assertEqual(self.send("/state", host="attacker.test:8000")[0], 403)
        self.assertEqual(self.send("/reset", {}, host="attacker.test:8000")[0], 403)
        self.assertEqual(self.send("/state")[0], 200)

    def test_non_string_approval_id_is_a_client_error(self):
        status, body = self.send("/approve", {"id": ["x"], "accept": True})
        self.assertEqual(status, 400)
        self.assertIn("string", body["error"])


if __name__ == "__main__":
    unittest.main()
