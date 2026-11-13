"""
tests/test_cards.py – Unit tests for skeleton_crew.cards

Tests:
  - render_header produces correct borders and badge
  - render_footer shows duration or dash
  - render_row wraps long values and aligns columns
  - render_card produces the expected line count and contains expected text
  - render_demo returns non-empty string with all 3 demo card headers
"""

import sys
import os
import unittest

# ensure src/ is importable when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from skeleton_crew.cards import (
    render_header,
    render_footer,
    render_row,
    render_card,
    render_demo,
    render_divider,
    DEFAULT_WIDTH,
    _H,
    _TL,
    _TR,
    _BL,
    _BR,
)


class TestRenderHeader(unittest.TestCase):
    def test_starts_with_top_left_corner(self):
        h = render_header("my-job", "ok")
        self.assertTrue(h.startswith(_TL), f"Expected {_TL!r} at start, got: {h!r}")

    def test_ends_with_top_right_corner(self):
        h = render_header("my-job", "ok")
        self.assertTrue(h.endswith(_TR), f"Expected {_TR!r} at end, got: {h!r}")

    def test_contains_job_id(self):
        h = render_header("my-job", "ok")
        self.assertIn("my-job", h)

    def test_contains_status_badge_ok(self):
        h = render_header("x", "ok")
        self.assertIn("OK", h)

    def test_contains_status_badge_error(self):
        h = render_header("x", "error")
        self.assertIn("ERROR", h)

    def test_contains_status_badge_skipped(self):
        h = render_header("x", "skipped")
        self.assertIn("SKIPPED", h)

    def test_total_width_matches(self):
        h = render_header("abc", "ok", width=50)
        self.assertEqual(len(h), 50, f"Header width mismatch: {len(h)} != 50  → {h!r}")

    def test_custom_width(self):
        h = render_header("j", "ok", width=80)
        self.assertEqual(len(h), 80)


class TestRenderFooter(unittest.TestCase):
    def test_starts_with_bottom_left(self):
        f = render_footer(1.23)
        self.assertTrue(f.startswith(_BL))

    def test_ends_with_bottom_right(self):
        f = render_footer(1.23)
        self.assertTrue(f.endswith(_BR))

    def test_shows_duration(self):
        f = render_footer(0.456)
        self.assertIn("0.456", f)

    def test_none_duration_shows_dash(self):
        f = render_footer(None)
        self.assertIn(_H, f)
        # should not raise

    def test_total_width_matches(self):
        f = render_footer(0.1, width=50)
        self.assertEqual(len(f), 50)


class TestRenderRow(unittest.TestCase):
    def test_returns_list(self):
        rows = render_row("key", "value")
        self.assertIsInstance(rows, list)
        self.assertGreater(len(rows), 0)

    def test_first_line_contains_key_and_value(self):
        rows = render_row("status", "all good")
        self.assertIn("status", rows[0])
        self.assertIn("all good", rows[0])

    def test_line_width_matches(self):
        rows = render_row("k", "v", width=50)
        for row in rows:
            self.assertEqual(len(row), 50, f"Row width mismatch: {len(row)!r}")

    def test_long_value_wraps(self):
        long_val = "x" * 200
        rows = render_row("key", long_val, width=DEFAULT_WIDTH)
        self.assertGreater(len(rows), 1, "Long value should wrap to multiple lines")

    def test_starts_and_ends_with_vertical_bar(self):
        from skeleton_crew.cards import _V
        rows = render_row("k", "v")
        for row in rows:
            self.assertTrue(row.startswith(_V), f"Row should start with │: {row!r}")
            self.assertTrue(row.endswith(_V), f"Row should end with │: {row!r}")


class TestRenderCard(unittest.TestCase):
    def _make_card(self, **kwargs):
        defaults = dict(
            job_id="test-job",
            status="ok",
            fields={"result": "passed", "count": 42},
            duration_s=0.007,
        )
        defaults.update(kwargs)
        return render_card(**defaults)

    def test_returns_string(self):
        self.assertIsInstance(self._make_card(), str)

    def test_contains_job_id(self):
        card = self._make_card(job_id="my-job")
        self.assertIn("my-job", card)

    def test_contains_status(self):
        card = self._make_card(status="ok")
        self.assertIn("OK", card)

    def test_contains_field_key(self):
        card = self._make_card(fields={"answer": "42"})
        self.assertIn("answer", card)

    def test_contains_field_value(self):
        card = self._make_card(fields={"answer": "42"})
        self.assertIn("42", card)

    def test_contains_duration(self):
        card = self._make_card(duration_s=1.234)
        self.assertIn("1.234", card)

    def test_line_count_minimum(self):
        # at least header + 1 field row + footer = 3 lines
        card = self._make_card(fields={"x": "y"})
        self.assertGreaterEqual(len(card.splitlines()), 3)

    def test_all_lines_same_width(self):
        card = self._make_card()
        lines = card.splitlines()
        widths = {len(line) for line in lines}
        self.assertEqual(len(widths), 1,
                         f"Lines should all be the same width: {widths}")

    def test_error_status_badge(self):
        card = render_card("j", "error", {"err": "boom"})
        self.assertIn("ERROR", card)

    def test_skipped_status_badge(self):
        card = render_card("j", "skipped", {"reason": "already ran"})
        self.assertIn("SKIPPED", card)

    def test_empty_fields(self):
        card = render_card("j", "ok", {})
        self.assertIn("j", card)


class TestRenderDemo(unittest.TestCase):
    def test_returns_non_empty_string(self):
        demo = render_demo()
        self.assertIsInstance(demo, str)
        self.assertGreater(len(demo), 50)

    def test_contains_all_demo_job_ids(self):
        demo = render_demo()
        self.assertIn("mailwatch", demo)
        self.assertIn("drainwatch", demo)
        self.assertIn("daily-report", demo)

    def test_contains_ok_and_error_and_skipped(self):
        demo = render_demo()
        self.assertIn("OK", demo)
        self.assertIn("ERROR", demo)
        self.assertIn("SKIPPED", demo)


if __name__ == "__main__":
    unittest.main()
