#!/usr/bin/env python3
"""Small standard-library tests for the repeated-trial summary helper."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("analyze_repeated_trials.py")
SPEC = importlib.util.spec_from_file_location("analysis", MODULE)
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)

class SummaryStatsTests(unittest.TestCase):
    def test_single_value_has_no_interval(self):
        mean, sd, low, high = analysis.stats([4.0])
        self.assertEqual(mean, 4.0)
        self.assertIsNone(sd)
        self.assertIsNone(low)
        self.assertIsNone(high)

    def test_multiple_values_have_interval_around_mean(self):
        mean, sd, low, high = analysis.stats([10.0, 12.0, 11.0])
        self.assertEqual(mean, 11.0)
        self.assertGreater(sd, 0)
        self.assertLess(low, mean)
        self.assertGreater(high, mean)

    def test_t_critical_values(self):
        self.assertAlmostEqual(analysis.T95[9], 2.262)
        self.assertAlmostEqual(analysis.T95[1], 12.706)

if __name__ == "__main__":
    unittest.main()
