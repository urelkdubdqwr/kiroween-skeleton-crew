"""
tests/test_runner.py – Tests for skeleton_crew.runner

Tests:
  - load_state returns empty dict when no state file exists
  - save_state/load_state round-trips correctly
  - _should_skip returns False for "manual" schedule
  - _should_skip returns True for "daily" when already ran today
  - _should_skip returns False for "daily" when last ran yesterday
  - _should_skip returns True for "hourly" when already ran this hour
  - _should_skip returns False for "hourly" when last ran previous hour
  - _should_skip handles HH:MM schedule
  - run_job with a simple script job: returns a card string
  - run_job captures script failure as an error card
  - run_job marks state after success
  - run_all with a tmp jobs dir returns one card per job
"""

import json
import os
import sys
import tempfile
import tomllib
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ensure src/ is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from skeleton_crew.runner import (
    load_state,
    save_state,
    _should_skip,
    _now_utc,
    run_job,
    run_all,
    load_job_spec,
)


def _write_toml(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


class TestState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_load_state_missing_file(self):
        state = load_state(self.state_dir)
        self.assertEqual(state, {})

    def test_save_and_load_roundtrip(self):
        data = {"my-job": {"last_run": "2024-01-01T00:00:00+00:00", "last_status": "ok"}}
        save_state(data, self.state_dir)
        loaded = load_state(self.state_dir)
        self.assertEqual(loaded, data)

    def test_save_creates_directory(self):
        nested = self.state_dir / "deep" / "nested"
        save_state({"x": 1}, nested)
        self.assertTrue((nested / "state.json").exists())

    def test_load_corrupted_file_returns_empty(self):
        state_file = self.state_dir / "state.json"
        state_file.write_text("NOT JSON {{{", encoding="utf-8")
        result = load_state(self.state_dir)
        self.assertEqual(result, {})


class TestShouldSkip(unittest.TestCase):
    def _job(self, schedule: str) -> dict:
        return {"id": "j", "schedule": schedule, "kind": "script"}

    def _state_today(self) -> dict:
        return {"last_run": _now_utc().isoformat()}

    def _state_yesterday(self) -> dict:
        return {"last_run": (_now_utc() - timedelta(days=1)).isoformat()}

    def _state_last_hour(self) -> dict:
        return {"last_run": (_now_utc() - timedelta(hours=1)).isoformat()}

    def test_manual_never_skipped(self):
        self.assertFalse(_should_skip(self._job("manual"), self._state_today()))

    def test_manual_no_state(self):
        self.assertFalse(_should_skip(self._job("manual"), {}))

    def test_daily_skipped_if_ran_today(self):
        self.assertTrue(_should_skip(self._job("daily"), self._state_today()))

    def test_daily_not_skipped_if_ran_yesterday(self):
        self.assertFalse(_should_skip(self._job("daily"), self._state_yesterday()))

    def test_daily_not_skipped_with_no_state(self):
        self.assertFalse(_should_skip(self._job("daily"), {}))

    def test_hourly_skipped_if_ran_this_hour(self):
        self.assertTrue(_should_skip(self._job("hourly"), self._state_today()))

    def test_hourly_not_skipped_if_ran_last_hour(self):
        self.assertFalse(_should_skip(self._job("hourly"), self._state_last_hour()))

    def test_hhmm_skipped_if_ran_at_same_minute_today(self):
        now = _now_utc()
        hhmm = now.strftime("%H:%M")
        state = {"last_run": now.isoformat()}
        self.assertTrue(_should_skip(self._job(hhmm), state))

    def test_hhmm_not_skipped_if_ran_yesterday_same_time(self):
        now = _now_utc()
        hhmm = now.strftime("%H:%M")
        yesterday = now - timedelta(days=1)
        state = {"last_run": yesterday.isoformat()}
        self.assertFalse(_should_skip(self._job(hhmm), state))

    def test_no_state_never_skipped(self):
        for schedule in ("daily", "hourly", "08:00"):
            with self.subTest(schedule=schedule):
                self.assertFalse(_should_skip(self._job(schedule), {}))


class TestRunJob(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name) / "state"

    def tearDown(self):
        self.tmp.cleanup()

    def _script_job(self, command: str, schedule: str = "manual") -> dict:
        return {
            "id":       "test-script",
            "kind":     "script",
            "schedule": schedule,
            "command":  command,
            "timeout":  10,
        }

    def test_success_returns_card_string(self):
        job = self._script_job("echo hello")
        card = run_job(job, self.state_dir)
        self.assertIsInstance(card, str)
        self.assertGreater(len(card), 10)

    def test_success_card_contains_ok(self):
        job = self._script_job("echo hello")
        card = run_job(job, self.state_dir)
        self.assertIn("OK", card)

    def test_success_card_contains_job_id(self):
        job = self._script_job("echo hello")
        card = run_job(job, self.state_dir)
        self.assertIn("test-script", card)

    def test_success_persists_state(self):
        job = self._script_job("echo hi")
        run_job(job, self.state_dir)
        state = load_state(self.state_dir)
        self.assertIn("test-script", state)
        self.assertEqual(state["test-script"]["last_status"], "ok")

    def test_failure_returns_error_card(self):
        job = self._script_job("exit 1")
        card = run_job(job, self.state_dir)
        self.assertIn("ERROR", card)

    def test_failure_does_not_persist_state(self):
        job = self._script_job("exit 1")
        run_job(job, self.state_dir)
        state = load_state(self.state_dir)
        self.assertNotIn("test-script", state)

    def test_skip_returns_skipped_card(self):
        job = self._script_job("echo hi", schedule="daily")
        # Pre-populate state so job thinks it already ran today
        state = {"test-script": {"last_run": _now_utc().isoformat(), "last_status": "ok"}}
        save_state(state, self.state_dir)
        card = run_job(job, self.state_dir)
        self.assertIn("SKIPPED", card)

    def test_force_ignores_skip(self):
        job = self._script_job("echo hi", schedule="daily")
        state = {"test-script": {"last_run": _now_utc().isoformat(), "last_status": "ok"}}
        save_state(state, self.state_dir)
        card = run_job(job, self.state_dir, force=True)
        self.assertIn("OK", card)

    def test_missing_command_returns_error(self):
        job = {"id": "no-cmd", "kind": "script", "schedule": "manual"}
        card = run_job(job, self.state_dir)
        self.assertIn("ERROR", card)

    def test_timeout_returns_error_card(self):
        job = {
            "id":       "slow-job",
            "kind":     "script",
            "schedule": "manual",
            "command":  "sleep 10",
            "timeout":  1,
        }
        card = run_job(job, self.state_dir)
        self.assertIn("ERROR", card)
        self.assertIn("timed out", card.lower())


class TestRunAll(unittest.TestCase):
    def setUp(self):
        self.tmp  = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.jobs_dir  = self.root / "jobs"
        self.state_dir = self.root / "state"
        self.jobs_dir.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _write_job(self, name: str, command: str = "echo ok") -> None:
        content = (
            f'id       = "{name}"\n'
            f'kind     = "script"\n'
            f'schedule = "manual"\n'
            f'command  = "{command}"\n'
            f'timeout  = 10\n'
        )
        (self.jobs_dir / f"{name}.toml").write_text(content, encoding="utf-8")

    def test_run_all_returns_one_card_per_job(self):
        self._write_job("job-a")
        self._write_job("job-b")
        cards = run_all(self.jobs_dir, self.state_dir)
        self.assertEqual(len(cards), 2)

    def test_run_all_empty_dir_returns_error_card(self):
        cards = run_all(self.jobs_dir, self.state_dir)
        self.assertEqual(len(cards), 1)
        self.assertIn("ERROR", cards[0])

    def test_run_all_cards_are_strings(self):
        self._write_job("j1")
        cards = run_all(self.jobs_dir, self.state_dir)
        for card in cards:
            self.assertIsInstance(card, str)


class TestLoadJobSpec(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, content: str) -> Path:
        path = Path(self.tmp.name) / "job.toml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_valid_script_job(self):
        p = self._write('id = "x"\nkind = "script"\ncommand = "ls"\n')
        spec = load_job_spec(p)
        self.assertEqual(spec["id"], "x")

    def test_valid_llm_job(self):
        p = self._write('id = "y"\nkind = "llm"\nprompt = "hello"\n')
        spec = load_job_spec(p)
        self.assertEqual(spec["kind"], "llm")

    def test_missing_id_raises(self):
        p = self._write('kind = "script"\n')
        with self.assertRaises(ValueError):
            load_job_spec(p)

    def test_unknown_kind_raises(self):
        p = self._write('id = "z"\nkind = "magic"\n')
        with self.assertRaises(ValueError):
            load_job_spec(p)


if __name__ == "__main__":
    unittest.main()
