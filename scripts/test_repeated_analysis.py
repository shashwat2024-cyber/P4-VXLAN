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


import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from campaign_validation import validate_campaign_rows


class CampaignValidationTests(unittest.TestCase):
    campaign = "campaign-A"
    configurations = ["P4_VXLAN"]
    tenants = ["A"]
    mss_values = [500]
    trials = 2

    def make_rows(self):
        return [
            {
                "campaign_id": self.campaign,
                "configuration": "P4_VXLAN",
                "tenant": "A",
                "mss_bytes": "500",
                "trial_number": str(number),
                "status": "success",
            }
            for number in (1, 2)
        ]

    def validate(self, rows):
        return validate_campaign_rows(
            rows,
            self.campaign,
            self.configurations,
            self.tenants,
            self.mss_values,
            self.trials,
        )

    def test_complete_campaign_passes(self):
        self.assertEqual(self.validate(self.make_rows()), [])

    def test_row_with_missing_csv_field_is_rejected(self):
        rows = self.make_rows()
        rows[0]["transport"] = None

        errors = self.validate(rows)

        self.assertTrue(
            any("missing fields in CSV row" in error for error in errors),
            errors,
        )

    def test_missing_trial_is_rejected(self):
        errors = self.validate(self.make_rows()[:1])
        self.assertTrue(any("Missing trial 2" in error for error in errors))

    def test_duplicate_trial_is_rejected(self):
        rows = self.make_rows()
        rows.append(dict(rows[0]))
        errors = self.validate(rows)
        self.assertTrue(any("Duplicate trial" in error for error in errors))

    def test_failed_trial_is_rejected(self):
        rows = self.make_rows()
        rows[1]["status"] = "failed"
        errors = self.validate(rows)
        self.assertTrue(any("not 'success'" in error for error in errors))

    def test_unexpected_condition_is_rejected(self):
        rows = self.make_rows()
        rows[0]["tenant"] = "C"
        errors = self.validate(rows)
        self.assertTrue(any("unexpected condition" in error for error in errors))

    def test_other_campaign_rows_do_not_count(self):
        rows = self.make_rows()
        rows[0]["campaign_id"] = "campaign-B"
        errors = self.validate(rows)
        self.assertTrue(
            any("Missing trial 1" in error for error in errors),
            errors,
        )
        self.assertFalse(
            any("Duplicate trial" in error for error in errors),
            errors,
        )



if __name__ == "__main__":
    unittest.main()
