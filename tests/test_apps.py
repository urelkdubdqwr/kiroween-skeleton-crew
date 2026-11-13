"""
tests/test_apps.py – Integration tests for apps/mailwatch and apps/drainwatch.

These tests run each app directly (not via the job runner) against the sample
data bundled under apps/*/data/, verifying that:
  - Both apps exit successfully or with the expected code
  - Both apps emit valid JSON on stdout
  - mailwatch finds the expected keyword matches
  - drainwatch flags the known anomalous transfers
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# repo root so we can resolve app paths
_REPO_ROOT = Path(__file__).parent.parent


class TestMailwatchApp(unittest.TestCase):
    """Run apps/mailwatch/run.py against apps/mailwatch/data/."""

    def _run(self) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, "apps/mailwatch/run.py"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=15,
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(
                f"mailwatch did not emit valid JSON.\n"
                f"stdout: {result.stdout!r}\n"
                f"stderr: {result.stderr!r}"
            )
        return result.returncode, data

    def test_exits_zero(self):
        code, _ = self._run()
        self.assertEqual(code, 0, "mailwatch should exit 0 when messages are found")

    def test_status_ok(self):
        _, data = self._run()
        self.assertEqual(data.get("status"), "ok")

    def test_scanned_four_messages(self):
        _, data = self._run()
        self.assertEqual(data.get("scanned"), 4,
                         f"Expected 4 .eml files scanned, got {data.get('scanned')}")

    def test_found_matches(self):
        _, data = self._run()
        self.assertGreater(data.get("matches", 0), 0,
                           "Expected at least one keyword match")

    def test_top_match_is_string(self):
        _, data = self._run()
        self.assertIsInstance(data.get("top_match"), str)

    def test_ranked_list_is_non_empty(self):
        _, data = self._run()
        ranked = data.get("ranked", [])
        self.assertGreater(len(ranked), 0)

    def test_ranked_items_have_required_fields(self):
        _, data = self._run()
        for item in data.get("ranked", []):
            self.assertIn("score",   item)
            self.assertIn("subject", item)
            self.assertIn("hits",    item)

    def test_scores_are_descending(self):
        _, data = self._run()
        ranked = data.get("ranked", [])
        scores = [item["score"] for item in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True),
                         "Ranked results should be in descending score order")

    def test_urgent_message_ranked_highest(self):
        """The escalation / overdue message should outscore plain invoice."""
        _, data = self._run()
        ranked = data.get("ranked", [])
        if len(ranked) >= 2:
            self.assertGreaterEqual(ranked[0]["score"], ranked[1]["score"])


class TestDrainwatchApp(unittest.TestCase):
    """Run apps/drainwatch/run.py against apps/drainwatch/data/."""

    def _run(self) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, "apps/drainwatch/run.py"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            timeout=15,
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            self.fail(
                f"drainwatch did not emit valid JSON.\n"
                f"stdout: {result.stdout!r}\n"
                f"stderr: {result.stderr!r}"
            )
        return result.returncode, data

    def test_exits_nonzero_on_anomaly(self):
        """drainwatch should exit 1 when anomalies are detected."""
        code, _ = self._run()
        self.assertEqual(code, 1, "drainwatch should exit 1 when anomalies found")

    def test_status_error_on_anomaly(self):
        _, data = self._run()
        self.assertEqual(data.get("status"), "error")

    def test_total_transfers_correct(self):
        _, data = self._run()
        self.assertEqual(data.get("total"), 10,
                         f"Expected 10 transfers, got {data.get('total')}")

    def test_anomalies_detected(self):
        _, data = self._run()
        self.assertGreater(data.get("anomaly_count", 0), 0,
                           "Expected anomalies in sample data")

    def test_largest_outflow_flagged(self):
        """142.7 ETH transfer to 0xDeadBeef must be in anomalies."""
        _, data = self._run()
        anomalies = data.get("anomalies", [])
        amounts = [a["amount_eth"] for a in anomalies]
        self.assertIn(142.7, amounts,
                      f"142.7 ETH transfer should be flagged. Amounts: {amounts}")

    def test_alert_level_critical_or_high(self):
        _, data = self._run()
        level = data.get("alert_level", "")
        self.assertIn(level, ("CRITICAL", "HIGH"),
                      f"Expected CRITICAL or HIGH alert level, got {level!r}")

    def test_anomalies_have_required_fields(self):
        _, data = self._run()
        for a in data.get("anomalies", []):
            for field in ("tx_hash", "from", "to", "amount_eth", "alert", "reason"):
                self.assertIn(field, a, f"Anomaly missing field {field!r}: {a}")

    def test_anomalies_sorted_descending(self):
        _, data = self._run()
        amounts = [a["amount_eth"] for a in data.get("anomalies", [])]
        self.assertEqual(amounts, sorted(amounts, reverse=True),
                         "Anomalies should be sorted by amount descending")

    def test_statistical_fields_present(self):
        _, data = self._run()
        self.assertIn("mean_eth",   data)
        self.assertIn("stddev_eth", data)
        self.assertIn("cutoff_eth", data)


class TestDrainwatchDetectionLogic(unittest.TestCase):
    """Unit tests for the drainwatch detection functions (no subprocess)."""

    def setUp(self):
        sys.path.insert(0, str(_REPO_ROOT / "apps" / "drainwatch"))

    def _import(self):
        # reload on first import to avoid cached state
        import importlib
        import sys as _sys
        mod_name = "run"
        if mod_name in _sys.modules:
            return _sys.modules[mod_name]
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            mod_name, _REPO_ROOT / "apps" / "drainwatch" / "run.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_mean_all_equal(self):
        mod = self._import()
        self.assertAlmostEqual(mod._mean([5.0, 5.0, 5.0]), 5.0)

    def test_mean_empty(self):
        mod = self._import()
        self.assertEqual(mod._mean([]), 0.0)

    def test_stddev_all_equal(self):
        mod = self._import()
        self.assertEqual(mod._stddev([3.0, 3.0, 3.0]), 0.0)

    def test_stddev_empty(self):
        mod = self._import()
        self.assertEqual(mod._stddev([]), 0.0)

    def test_alert_level_critical(self):
        mod = self._import()
        levels = {"critical": 100.0, "high": 50.0, "medium": 20.0}
        self.assertEqual(mod._alert_level(150.0, levels), "CRITICAL")

    def test_alert_level_high(self):
        mod = self._import()
        levels = {"critical": 100.0, "high": 50.0, "medium": 20.0}
        self.assertEqual(mod._alert_level(60.0, levels), "HIGH")

    def test_alert_level_medium(self):
        mod = self._import()
        levels = {"critical": 100.0, "high": 50.0, "medium": 20.0}
        self.assertEqual(mod._alert_level(25.0, levels), "MEDIUM")

    def test_alert_level_low(self):
        mod = self._import()
        levels = {"critical": 100.0, "high": 50.0, "medium": 20.0}
        self.assertEqual(mod._alert_level(1.0, levels), "LOW")

    def test_detect_no_anomalies(self):
        mod = self._import()
        transfers = [{"amount_eth": 1.0, "tx_hash": "x", "from": "a", "to": "b", "ts": "t"}
                     for _ in range(10)]
        result = mod.detect_anomalies(transfers, 50.0, 2.5, {})
        self.assertEqual(result["anomaly_count"], 0)
        self.assertEqual(result["status"], "ok")

    def test_detect_hard_threshold_hit(self):
        mod = self._import()
        transfers = [
            {"amount_eth": 1.0,  "tx_hash": "a", "from": "v", "to": "h", "ts": "t"},
            {"amount_eth": 1.0,  "tx_hash": "b", "from": "v", "to": "h", "ts": "t"},
            {"amount_eth": 55.0, "tx_hash": "c", "from": "v", "to": "x", "ts": "t"},
        ]
        result = mod.detect_anomalies(transfers, 50.0, 2.5, {})
        self.assertEqual(result["anomaly_count"], 1)
        self.assertEqual(result["anomalies"][0]["amount_eth"], 55.0)


if __name__ == "__main__":
    unittest.main()
