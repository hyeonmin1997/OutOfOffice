"""evaluate.py --kind runs only the chosen kind of case and records it."""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluate


class KindFilterTests(unittest.TestCase):
    def run_main(self, *argv):
        with tempfile.TemporaryDirectory() as out:
            args = ["evaluate.py", "--mode", "fixture", "--split", "dev", "--out", out, *argv]
            with patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()):
                evaluate.main()
            files = list(Path(out).glob("*.json"))
            self.assertEqual(len(files), 1)
            return files[0].name, json.loads(files[0].read_text(encoding="utf-8"))

    def test_attack_only(self):
        name, record = self.run_main("--kind", "attack")
        self.assertIn("-attack_", name)
        self.assertEqual(record["meta"]["kind"], "attack")
        self.assertTrue(record["trials"])
        self.assertEqual({t["kind"] for t in record["trials"]}, {"attack"})
        self.assertIsNone(record["summary"]["on"]["benign_task_success"]["pct"])

    def test_default_runs_both(self):
        name, record = self.run_main()
        self.assertNotIn("-attack_", name)
        self.assertEqual(record["meta"]["kind"], "all")
        self.assertEqual({t["kind"] for t in record["trials"]}, {"attack", "benign"})


if __name__ == "__main__":
    unittest.main()
