"""
cards.py – Turn a job result dict into a compact Unicode card string.

Cards are pure functions that take a result mapping and return a str.
They use box-drawing characters for a clean terminal look.

Card anatomy:
  ┌─ job-id ──────────── [STATUS] ─┐
  │  key : value                   │
  │  key : value                   │
  └─ 0.42 s ───────────────────────┘
"""

from __future__ import annotations

import textwrap
from typing import Any

# ── box-drawing glyphs ────────────────────────────────────────────────────────
_H = "─"
_TL = "┌"
_TR = "┐"
_BL = "└"
_BR = "┘"
_V = "│"

# ── status badge map ─────────────────────────────────────────────────────────
STATUS_GLYPHS: dict[str, str] = {
    "ok":      "✓ OK",
    "error":   "✗ ERROR",
    "skipped": "⊘ SKIPPED",
    "running": "⟳ RUNNING",
    "demo":    "★ DEMO",
}

DEFAULT_WIDTH = 64


def _status_badge(status: str) -> str:
    return STATUS_GLYPHS.get(status, status.upper())


def _pad_between(left: str, right: str, width: int, fill: str = _H) -> str:
    """Return a line of exactly `width` chars with left and right anchors,
    padding between them with `fill` repeated as needed."""
    gap = width - len(left) - len(right)
    if gap < 1:
        gap = 1
    return left + fill * gap + right


def render_header(job_id: str, status: str, width: int = DEFAULT_WIDTH) -> str:
    badge = _status_badge(status)
    left = f"{_TL}{_H} {job_id} "
    right = f" [{badge}] {_H}{_TR}"
    return _pad_between(left, right, width)


def render_footer(duration_s: float | None, width: int = DEFAULT_WIDTH) -> str:
    if duration_s is None:
        dur_str = "─"
    else:
        dur_str = f"{duration_s:.3f} s"
    left = f"{_BL}{_H} {dur_str} "
    right = f" {_H}{_BR}"
    return _pad_between(left, right, width)


def render_row(key: str, value: Any, width: int = DEFAULT_WIDTH) -> list[str]:
    """Render a single key/value row, wrapping long values."""
    max_val_width = width - len(key) - 7  # "│  key : " + " │"
    value_str = str(value)
    if max_val_width < 10:
        max_val_width = 10

    # wrap long values
    wrapped = textwrap.wrap(value_str, max_val_width) or [""]
    lines = []
    for i, segment in enumerate(wrapped):
        if i == 0:
            inner = f"  {key} : {segment}"
        else:
            inner = " " * (len(key) + 5) + segment
        # pad to width
        padded = inner.ljust(width - 2)
        lines.append(f"{_V}{padded}{_V}")
    return lines


def render_divider(width: int = DEFAULT_WIDTH) -> str:
    return f"{_V}{_H * (width - 2)}{_V}"


def render_card(
    job_id: str,
    status: str,
    fields: dict[str, Any],
    duration_s: float | None = None,
    width: int = DEFAULT_WIDTH,
) -> str:
    """Render a complete card string from job result data.

    Args:
        job_id:     The job identifier.
        status:     One of ok / error / skipped / running / demo.
        fields:     Ordered dict of key → value rows to display.
        duration_s: Elapsed seconds (shown in footer).
        width:      Total card width in characters.

    Returns:
        A multi-line string ready to print.
    """
    lines: list[str] = []
    lines.append(render_header(job_id, status, width))
    for key, val in fields.items():
        lines.extend(render_row(key, val, width))
    lines.append(render_footer(duration_s, width))
    return "\n".join(lines)


# ── demo cards ────────────────────────────────────────────────────────────────

DEMO_CARDS: list[tuple[str, str, dict, float | None]] = [
    (
        "mailwatch",
        "ok",
        {
            "new messages": 3,
            "top match":    "Re: Invoice #2024-11 — urgent payment request",
            "keywords hit": "invoice, urgent, payment",
            "action":       "Flag for review",
        },
        0.012,
    ),
    (
        "drainwatch",
        "error",
        {
            "event log":    "transfers_2024-11-13.json",
            "error":        "Outflow anomaly: 4 transfers exceed 3σ threshold",
            "largest":      "0xDeadBeef → 0xC0ffee  142.7 ETH",
            "alert level":  "HIGH",
        },
        0.034,
    ),
    (
        "daily-report",
        "skipped",
        {
            "reason": "already ran today",
            "last run": "2024-11-13T00:05:11Z",
        },
        None,
    ),
]


def render_demo(width: int = DEFAULT_WIDTH) -> str:
    """Return all demo cards joined by blank lines."""
    parts = []
    for job_id, status, fields, dur in DEMO_CARDS:
        parts.append(render_card(job_id, status, fields, dur, width))
    return "\n\n".join(parts)
