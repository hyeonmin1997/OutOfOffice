"""Two-person label agreement: blind sheets, no silent overwrite, kappa."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))

import agreement  # noqa: E402


def fill(path, labels):
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        row["label"] = labels[row["blind_id"]]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=agreement.FIELDS)
        w.writeheader()
        w.writerows(rows)


class AgreementTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        self.key = agreement.sample(["p1", "p2"], n=10, out=self.out)
        cases = {c["id"]: c for c in json.loads(agreement.CASES.read_text(encoding="utf-8"))}
        self.truth = {b: cases[cid]["kind"] for b, cid in self.key.items()}

    def tearDown(self):
        self.tmp.cleanup()

    def test_sheets_are_blind(self):
        text = (self.out / "sheet_p1.csv").read_text(encoding="utf-8-sig")
        for case_id in self.key.values():
            self.assertNotIn(case_id, text)
        with (self.out / "sheet_p1.csv").open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["blind_id"] for r in rows], sorted(self.key))
        self.assertTrue(all(r["label"] == "" for r in rows))
        self.assertTrue((self.out / "INSTRUCTIONS.md").exists())

    def test_same_seed_same_sample(self):
        with tempfile.TemporaryDirectory() as other:
            self.assertEqual(agreement.sample(["p1", "p2"], n=10, out=other), self.key)

    def test_no_silent_overwrite(self):
        with self.assertRaises(FileExistsError):
            agreement.sample(["p1", "p2"], n=10, out=self.out)

    def test_score(self):
        fill(self.out / "sheet_p1.csv", self.truth)
        flipped = dict(self.truth)
        first = sorted(flipped)[0]
        flipped[first] = "benign" if flipped[first] == "attack" else "공격"
        fill(self.out / "sheet_p2.csv", flipped)
        r = agreement.score(out=self.out)
        self.assertEqual(r["agreement"], {"num": 9, "den": 10, "pct": 90.0})
        self.assertEqual(r["vs_generator_label"], {"p1": 10, "p2": 9})
        self.assertEqual([d["blind_id"] for d in r["disagreements"]], [first])
        a = [self.truth[i] for i in sorted(self.truth)]
        b = [agreement.LABELS[flipped[i].lower()] for i in sorted(flipped)]
        self.assertAlmostEqual(r["cohen_kappa"], round(agreement.cohen_kappa(a, b), 3))
        self.assertTrue((self.out / "agreement.json").exists())

    def test_blank_label_is_an_error(self):
        fill(self.out / "sheet_p1.csv", self.truth)
        with self.assertRaises(ValueError):
            agreement.score(out=self.out)          # p2 is still blank

    def test_kappa(self):
        self.assertAlmostEqual(agreement.cohen_kappa(["attack", "benign"] * 5, ["attack", "benign"] * 5), 1.0)
        self.assertIsNone(agreement.cohen_kappa(["attack"] * 4, ["attack"] * 4))


if __name__ == "__main__":
    unittest.main()
