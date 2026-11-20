import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

from build_cases import build, render  # noqa: E402


class CaseFileTests(unittest.TestCase):
    def setUp(self):
        self.cases = build()

    def test_committed_file_matches_generator(self):
        text = (ROOT / "eval" / "cases.json").read_text(encoding="utf-8")
        self.assertEqual(text, render(self.cases), "run python3 eval/build_cases.py")

    def test_grid_size_and_splits(self):
        count = {}
        for c in self.cases:
            count[(c["split"], c["kind"])] = count.get((c["split"], c["kind"]), 0) + 1
        self.assertEqual(count[("dev", "attack")], 20)
        self.assertEqual(count[("test", "attack")], 20)
        self.assertEqual(count[("dev", "benign")], 20)
        self.assertEqual(count[("test", "benign")], 20)

    def test_every_attack_has_a_twin_in_the_same_split(self):
        by_id = {c["id"]: c for c in self.cases}
        self.assertEqual(len(by_id), len(self.cases))
        for c in self.cases:
            twin = by_id[c["twin_of"]]
            self.assertEqual(twin["twin_of"], c["id"])
            self.assertEqual(twin["split"], c["split"])
            self.assertNotEqual(twin["kind"], c["kind"])

    def test_no_mail_appears_in_two_splits(self):
        seen = {}
        for c in self.cases:
            self.assertEqual(seen.setdefault(c["mail"], c["split"]), c["split"])

    def test_cases_are_valid_for_the_service(self):
        for c in self.cases:
            self.assertLessEqual(len(c["mail"]), 8000)
            self.assertIn(c["kind"], ("attack", "benign"))
            self.assertTrue(c["expect"]["event_time_prefix"].startswith("2026-11-"))
            json.dumps(c)


if __name__ == "__main__":
    unittest.main()
