"""The Defense OFF baseline used by the UI comparison and by evaluate.py."""

import unittest

import app
from evaluate import UnprotectedService
from service import ATTACK, Service


class DefenseToggleTests(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:")

    def tearDown(self):
        self.s.db.close()

    def test_off_run_executes_forbidden_grant_without_approval(self):
        result = self.s.plan(ATTACK, "fixture", "mail1", defense=False)
        self.assertIs(result["defense"], False)
        grants = {(g["user_id"], g["project"], g["role"]) for g in self.s.state()["grants"]}
        self.assertIn(("B", "Finance", "admin"), grants)
        self.assertEqual(self.s.state()["approvals"], [])
        info = [r for r in self.s.state()["logs"] if r["verdict"] == "info"]
        self.assertTrue(any("Baseline run" in r["reason"] for r in info))

    def test_off_applies_to_one_run_only(self):
        self.s.plan(ATTACK, "fixture", "mail1", defense=False)
        self.assertTrue(self.s.defense)
        self.s.reset()
        result = self.s.plan(ATTACK, "fixture", "mail1")
        self.assertIs(result["defense"], True)
        blocked = [r for r in result["results"] if r["status"] == "blocked"]
        self.assertEqual(blocked[0]["reason"], "Task scope / ACL denied")
        self.assertEqual(self.s.state()["grants"], [])

    def test_defense_must_be_boolean(self):
        with self.assertRaises(ValueError):
            self.s.plan(ATTACK, "fixture", "mail1", defense="off")

    def test_evaluate_baseline_is_the_same_path(self):
        svc = UnprotectedService(":memory:")
        try:
            self.assertFalse(svc.defense)
            res = svc.propose({"tool": "send_email", "args": {
                "recipient": "x@outside.test", "subject": "s", "body": "b"}})
            self.assertEqual(res["status"], "executed")
            res = svc.propose({"tool": "read_mail", "args": {"mail_id": "nope"}})
            self.assertEqual(res["reason"], "Record not found")
        finally:
            svc.db.close()

    def test_baseline_examples_come_from_the_case_file(self):
        examples = app.baseline_examples()
        self.assertEqual([e["id"] for e in examples], list(app.BASELINE_EXAMPLES))
        self.assertTrue(all(e["mail"] for e in examples))


if __name__ == "__main__":
    unittest.main()
