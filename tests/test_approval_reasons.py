"""An expired approval and a replayed one are logged with different reasons."""

import time
import unittest

from service import APPROVAL_EXPIRED, APPROVAL_USED, Service

GRANT = {"tool": "grant_access", "args": {"user_id": "A", "project": "Alpha", "role": "member"}}


class ApprovalReasonTests(unittest.TestCase):
    def setUp(self):
        self.s = Service(":memory:")
        self.s.begin_run()

    def last_reason(self):
        return self.s.db.execute("SELECT reason FROM logs ORDER BY id DESC LIMIT 1").fetchone()[0]

    def test_replayed_approval(self):
        token = self.s.propose(GRANT)["approval_id"]
        self.assertEqual(self.s.approve(token)["status"], "executed")
        self.assertEqual(self.s.approve(token), {"status": "blocked", "reason": APPROVAL_USED})
        self.assertEqual(self.last_reason(), APPROVAL_USED)

    def test_expired_approval(self):
        token = self.s.propose(GRANT)["approval_id"]
        with self.s.db:
            self.s.db.execute("UPDATE approvals SET expires=? WHERE id=?", (time.time() - 1, token))
        self.assertEqual(self.s.approve(token), {"status": "blocked", "reason": APPROVAL_EXPIRED})
        self.assertEqual(self.last_reason(), APPROVAL_EXPIRED)
        self.assertEqual(self.s.state()["grants"], [])


if __name__ == "__main__":
    unittest.main()
