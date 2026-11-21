"""95% Wilson intervals on every rate."""

import unittest

from evaluate import fmt, rate, wilson


class WilsonTests(unittest.TestCase):
    def test_known_values(self):
        self.assertEqual(wilson(0, 2), [0.0, 65.8])
        self.assertEqual(wilson(0, 5), [0.0, 43.4])
        self.assertEqual(wilson(0, 20), [0.0, 16.1])
        self.assertEqual(wilson(16, 20), [58.4, 91.9])
        self.assertEqual(wilson(20, 20), [83.9, 100.0])
        self.assertIsNone(wilson(0, 0))

    def test_rate_and_format(self):
        self.assertEqual(rate(0, 2)["ci95"], [0.0, 65.8])
        self.assertEqual(fmt(rate(0, 2)), "0.0% (0/2) [0–65.8]")
        self.assertEqual(fmt(rate(0, 2), ci=False), "0.0% (0/2)")
        self.assertEqual(fmt(rate(0, 0)), "N/A")
        # results saved before intervals existed still print
        self.assertEqual(fmt({"num": 1, "den": 4, "pct": 25.0}), "25.0% (1/4)")


if __name__ == "__main__":
    unittest.main()
