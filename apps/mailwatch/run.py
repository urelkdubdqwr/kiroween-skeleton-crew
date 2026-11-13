"""
apps/mailwatch/run.py – Scan a maildir-style folder for keyword matches.

Reads .eml files from mail_dir (default: apps/mailwatch/data/), scores each
message against weighted keywords defined in config.toml, and prints a ranked
summary card for the highest-scoring messages.

Outputs JSON to stdout so the skeleton-crew script runner captures it,
or run directly:  python apps/mailwatch/run.py
"""

from __future__ import annotations

import email
import email.header
import email.message
import json
import os
import sys
import tomllib
from pathlib import Path

# ── config ────────────────────────────────────────────────────────────────────

_HERE = Path(__file__).parent
_DEFAULT_CONFIG = _HERE / "config.toml"
_DEFAULT_DATA   = _HERE / "data"


def load_config(config_path: Path = _DEFAULT_CONFIG) -> dict:
    if not config_path.exists():
        return {"mail_dir": str(_DEFAULT_DATA), "keywords": []}
    with open(config_path, "rb") as fh:
        return tomllib.load(fh)


# ── email parsing ──────────────────────────────────────────────────────────────

def _decode_header(raw: str | None) -> str:
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            # Normalize bad/unknown charsets to latin-1 for safe decoding
            enc = charset if charset and charset.lower() not in ("unknown-8bit", "unknown") else "latin-1"
            try:
                decoded.append(part.decode(enc, errors="replace"))
            except (LookupError, UnicodeDecodeError):
                decoded.append(part.decode("latin-1", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def parse_eml(path: Path) -> dict:
    """Parse an .eml file and return a dict with subject, sender, body."""
    raw = path.read_bytes()
    msg = email.message_from_bytes(raw)
    subject = _decode_header(msg.get("Subject"))
    sender  = _decode_header(msg.get("From"))
    date    = msg.get("Date", "")

    body_parts: list[str] = []

    def _part_text(part: email.message.Message) -> str:
        charset = part.get_content_charset()
        # get_payload(decode=True) always returns bytes; decode=False returns str
        # when there is no transfer-encoding.  Handle both.
        payload_bytes = part.get_payload(decode=True)
        if payload_bytes is not None:
            # We have raw bytes; decode safely.
            enc = charset if charset and charset.lower() not in ("unknown-8bit",) else "latin-1"
            return payload_bytes.decode(enc, errors="replace")
        # Fallback: get_payload returned a string directly
        raw = part.get_payload(decode=False)
        return raw if isinstance(raw, str) else ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                body_parts.append(_part_text(part))
    else:
        body_parts.append(_part_text(msg))

    return {
        "path":    str(path),
        "subject": subject,
        "sender":  sender,
        "date":    date,
        "body":    "\n".join(body_parts),
    }


# ── scoring ───────────────────────────────────────────────────────────────────

def score_message(msg: dict, keywords: list[dict]) -> tuple[int, list[str]]:
    """Return (score, hit_words) for a message against the keyword list."""
    text = (msg["subject"] + " " + msg["body"]).lower()
    total = 0
    hits: list[str] = []
    for kw in keywords:
        word = kw["word"].lower()
        if word in text:
            total += kw.get("weight", 1)
            hits.append(kw["word"])
    return total, hits


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    cfg = load_config()
    keywords: list[dict] = cfg.get("keywords", [])

    # resolve mail_dir relative to repo root (cwd) or absolute
    raw_dir = cfg.get("mail_dir", str(_DEFAULT_DATA))
    mail_dir = Path(raw_dir)
    if not mail_dir.is_absolute():
        # try relative to repo root first, then relative to this file
        cwd_rel = Path(raw_dir)
        if cwd_rel.exists():
            mail_dir = cwd_rel
        else:
            mail_dir = _DEFAULT_DATA

    if not mail_dir.is_dir():
        result = {
            "status": "error",
            "error":  f"mail_dir not found: {mail_dir}",
        }
        print(json.dumps(result))
        return 1

    eml_files = sorted(mail_dir.glob("*.eml"))
    if not eml_files:
        result = {
            "status":  "ok",
            "scanned": 0,
            "matches": 0,
            "summary": "No .eml files found.",
        }
        print(json.dumps(result))
        return 0

    scored: list[tuple[int, list[str], dict]] = []
    for path in eml_files:
        try:
            msg  = parse_eml(path)
            sc, hits = score_message(msg, keywords)
            if sc > 0:
                scored.append((sc, hits, msg))
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"[warn] could not parse {path}: {exc}\n")

    scored.sort(key=lambda t: t[0], reverse=True)

    top = scored[:5]
    result: dict = {
        "status":    "ok",
        "scanned":   len(eml_files),
        "matches":   len(scored),
        "top_match": top[0][2]["subject"] if top else None,
        "keywords":  ", ".join(top[0][1]) if top else None,
        "ranked":    [
            {
                "score":   sc,
                "subject": msg["subject"],
                "from":    msg["sender"],
                "hits":    hits,
            }
            for sc, hits, msg in top
        ],
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
