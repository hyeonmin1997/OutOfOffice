import unittest
from app import Service


class PolicyTests(unittest.TestCase):

    def setUp(self):
        self.s = Service(":memory:")
        self.addCleanup(self.s.db.close)
        self.good = {
            "tool": "grant_access",
            "args": {"user_id": "A", "project": "Alpha", "role": "member"},
        }

    def test_approval_and_replay(self):
        p = self.s.propose(self.good)
        self.assertEqual(self.s.state()["grants"], [])
        self.assertEqual(self.s.approve(p["approval_id"])["status"], "executed")
        self.assertEqual(self.s.approve(p["approval_id"])["status"], "blocked")

    def test_rejection(self):
        p = self.s.propose(self.good)
        self.s.approve(p["approval_id"], False)
        self.assertEqual(self.s.state()["grants"], [])

    def test_wrong_target(self):
        self.good["args"]["user_id"] = "B"
        self.assertEqual(self.s.propose(self.good)["status"], "blocked")
        self.assertEqual(self.s.state()["approvals"], [])

    def test_exfiltration(self):
        a = {
            "tool": "send_email",
            "args": {
                "recipient": "outside@example.test",
                "subject": "x",
                "body": "secret",
            },
        }
        self.assertEqual(self.s.propose(a)["status"], "blocked")
        self.assertEqual(self.s.state()["outbox"], [])

    def test_expiry(self):
        p = self.s.propose(self.good)
        self.s.db.execute("UPDATE approvals SET expires=0")
        self.s.db.commit()
        self.assertEqual(self.s.approve(p["approval_id"])["status"], "blocked")

    def test_recheck(self):
        p = self.s.propose(self.good)
        self.s.db.execute("UPDATE tasks SET context=replace(context, 'Alpha', 'Other')")
        self.s.db.commit()
        self.assertEqual(self.s.approve(p["approval_id"])["status"], "blocked")
        self.assertEqual(self.s.state()["grants"], [])

    def test_schema(self):
        self.good["args"]["extra"] = "x"
        self.assertEqual(self.s.propose(self.good)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
