"""
runner.py – Execute jobs defined by TOML specs.

Job spec fields
───────────────
id          str         Unique identifier, used for state key & card header.
schedule    str         "manual" | "daily" | "hourly" | cron-like "HH:MM"
kind        str         "script" | "llm"
command     str         Shell command (kind=script). Supports {state_dir}.
prompt      str         Prompt template (kind=llm).
timeout     int         Seconds before the job is killed (default 60).
state_key   str         Key written to state file when job succeeds.

State file
──────────
A single JSON file at <state_dir>/state.json  (default .skeleton_crew_state/).
Schema: { "<job_id>": { "last_run": "<ISO-8601>", "last_status": "ok"|... } }

A job is skipped when:
  - schedule == "daily"  and last_run is today (UTC)
  - schedule == "hourly" and last_run is within the current UTC hour
  - schedule == "HH:MM"  and last_run matches the current HH:MM (UTC)
  - schedule == "manual" → never auto-skipped (always runs when asked)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skeleton_crew.cards import render_card

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_STATE_DIR = Path(".skeleton_crew_state")
DEFAULT_TIMEOUT = 60
JOBS_DIR = Path("jobs")

# ── state helpers ─────────────────────────────────────────────────────────────

def _state_path(state_dir: Path) -> Path:
    return state_dir / "state.json"


def load_state(state_dir: Path = DEFAULT_STATE_DIR) -> dict[str, Any]:
    path = _state_path(state_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict[str, Any], state_dir: Path = DEFAULT_STATE_DIR) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(state_dir)
    path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _should_skip(job: dict[str, Any], job_state: dict[str, Any]) -> bool:
    """Return True if the job should be skipped given its schedule and last run."""
    schedule: str = job.get("schedule", "manual").lower()
    last_run_str: str | None = job_state.get("last_run")
    if not last_run_str:
        return False  # never ran → run it

    try:
        last_run = datetime.fromisoformat(last_run_str)
    except ValueError:
        return False

    now = _now_utc()

    if schedule == "manual":
        return False
    if schedule == "daily":
        return last_run.date() == now.date()
    if schedule == "hourly":
        return (
            last_run.date() == now.date()
            and last_run.hour == now.hour
        )
    # HH:MM schedule
    if len(schedule) == 5 and schedule[2] == ":":
        return (
            last_run.date() == now.date()
            and last_run.strftime("%H:%M") == schedule
        )
    return False


# ── job loader ────────────────────────────────────────────────────────────────

def load_job_spec(path: Path) -> dict[str, Any]:
    """Load and validate a TOML job spec."""
    with open(path, "rb") as fh:
        spec = tomllib.load(fh)
    required = {"id", "kind"}
    missing = required - spec.keys()
    if missing:
        raise ValueError(f"Job spec {path} missing required fields: {missing}")
    if spec["kind"] not in ("script", "llm"):
        raise ValueError(f"Job spec {path}: unknown kind '{spec['kind']}'")
    return spec


def list_jobs(jobs_dir: Path = JOBS_DIR) -> list[dict[str, Any]]:
    """Return all job specs found in jobs_dir, sorted by id."""
    specs = []
    for toml_path in sorted(jobs_dir.glob("*.toml")):
        try:
            specs.append(load_job_spec(toml_path))
        except Exception as exc:
            print(f"[warn] could not load {toml_path}: {exc}", file=sys.stderr)
    return specs


# ── job execution ─────────────────────────────────────────────────────────────

def _run_script_job(
    job: dict[str, Any],
    state_dir: Path,
) -> tuple[str, dict[str, Any]]:
    """Run a script-kind job. Returns (status, fields)."""
    command: str = job.get("command", "")
    if not command:
        return "error", {"error": "no command specified"}

    timeout: int = int(job.get("timeout", DEFAULT_TIMEOUT))
    # allow {state_dir} substitution in commands
    command = command.format(state_dir=str(state_dir))

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "error", {"error": f"timed out after {timeout}s"}
    except OSError as exc:
        return "error", {"error": str(exc)}

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode == 0:
        fields: dict[str, Any] = {"exit code": result.returncode}
        if stdout:
            fields["output"] = stdout[:300]
        return "ok", fields
    else:
        fields = {"exit code": result.returncode}
        if stderr:
            fields["stderr"] = stderr[:300]
        elif stdout:
            fields["stdout"] = stdout[:300]
        return "error", fields


def _run_llm_job(
    job: dict[str, Any],
    state_dir: Path,
) -> tuple[str, dict[str, Any]]:
    """Run an llm-kind job via providers.chat_completion."""
    # Import lazily so runner.py doesn't require providers to be configured
    try:
        from skeleton_crew.providers import chat_completion, ProviderError
    except ImportError as exc:
        return "error", {"error": f"providers import failed: {exc}"}

    prompt: str = job.get("prompt", "")
    if not prompt:
        return "error", {"error": "no prompt specified"}

    model: str = job.get("model", "")
    try:
        reply = chat_completion(prompt, model=model or None)
    except ProviderError as exc:
        return "error", {"error": str(exc)}

    return "ok", {"reply": reply[:500]}


# ── single-job runner ─────────────────────────────────────────────────────────

def run_job(
    job: dict[str, Any],
    state_dir: Path = DEFAULT_STATE_DIR,
    *,
    force: bool = False,
) -> str:
    """Execute one job and return its rendered card string."""
    job_id: str = job["id"]
    state = load_state(state_dir)
    job_state = state.get(job_id, {})

    if not force and _should_skip(job, job_state):
        card = render_card(
            job_id,
            "skipped",
            {
                "reason":   "already ran this period",
                "schedule": job.get("schedule", "manual"),
                "last run": job_state.get("last_run", "unknown"),
            },
        )
        return card

    t0 = time.monotonic()
    kind: str = job["kind"]

    try:
        if kind == "script":
            status, fields = _run_script_job(job, state_dir)
        elif kind == "llm":
            status, fields = _run_llm_job(job, state_dir)
        else:
            status, fields = "error", {"error": f"unknown kind: {kind}"}
    except Exception as exc:  # noqa: BLE001 – catch-all intentional
        status, fields = "error", {"error": f"unexpected: {exc}"}

    duration = time.monotonic() - t0

    # update state on success
    if status == "ok":
        state[job_id] = {
            "last_run":    _now_utc().isoformat(),
            "last_status": status,
        }
        save_state(state, state_dir)

    fields["job id"] = job_id
    fields["kind"] = kind
    return render_card(job_id, status, fields, duration_s=duration)


# ── batch runner ──────────────────────────────────────────────────────────────

def run_all(
    jobs_dir: Path = JOBS_DIR,
    state_dir: Path = DEFAULT_STATE_DIR,
    *,
    force: bool = False,
) -> list[str]:
    """Run all jobs and return a list of card strings."""
    jobs = list_jobs(jobs_dir)
    if not jobs:
        return [render_card("skeleton-crew", "error", {"error": f"no jobs found in {jobs_dir}"})]
    return [run_job(job, state_dir, force=force) for job in jobs]
