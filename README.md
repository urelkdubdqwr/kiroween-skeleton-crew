# skeleton-crew

A lean, dependency-free Python template for scheduling agent jobs and rendering their results as chat-ready cards.

**Zero pip installs required at runtime.** Everything is Python 3.11+ standard library.

```
┌─ mailwatch ──────────────────────── [✓ OK] ─┐
│  new messages : 3                            │
│  top match    : Re: Invoice #2024-11 — urgent│
│  keywords hit : invoice, urgent, payment     │
│  action       : Flag for review              │
└─ 0.012 s ───────────────────────────────────┘
```

---

## What it is

skeleton-crew gives you a minimal, hackable scaffold for running small agent jobs on a schedule and surfacing their outputs as compact Unicode cards — suitable for pasting into a chat, displaying in a terminal dashboard, or piping to any text sink.

It is deliberately **not a framework**. It is a starting point: copy it, gut it, adapt it.

---

## Project layout

```
skeleton-crew/
├── src/skeleton_crew/
│   ├── __init__.py        – package metadata
│   ├── __main__.py        – CLI entry point
│   ├── cards.py           – card renderer (pure functions)
│   ├── runner.py          – job executor + state persistence
│   └── providers.py       – OpenAI-compatible LLM client (urllib only)
├── jobs/
│   ├── hello.toml         – simplest possible script job
│   ├── mailwatch.toml     – daily mail-scan job
│   ├── drainwatch.toml    – hourly on-chain outflow monitor
│   └── daily-report.toml  – LLM-powered daily digest (needs API key)
├── apps/
│   ├── mailwatch/         – scans a maildir for keyword matches
│   └── drainwatch/        – flags abnormal on-chain outflows
└── tests/                 – unittest suite (stdlib only)
```

---

## Quickstart

No install step needed.

```bash
# Render demo cards
python -m skeleton_crew render --demo

# List all jobs
python -m skeleton_crew list

# Run a specific job (force, ignore schedule)
python -m skeleton_crew run --job hello -f

# Run all jobs
python -m skeleton_crew run --job all -f

# Run the test suite
python3 -m unittest discover -s tests -v
```

For LLM jobs set your API key:

```bash
export SKELETON_API_KEY=sk-...
python -m skeleton_crew run --job daily-report -f
```

Or create `skeleton_crew.toml` in the repo root:

```toml
[provider]
base_url = "https://api.openai.com/v1"
model    = "gpt-4o-mini"
api_key  = "sk-..."
```

---

## The two example apps

### mailwatch

`apps/mailwatch/` — Scans a maildir-style folder of `.eml` files for messages matching weighted keywords (invoice, urgent, payment, overdue, …). Emits a JSON summary of ranked matches, highest-scoring first.

**Sample data:** `apps/mailwatch/data/` contains four synthetic `.eml` files:
- `msg001.eml` — routine invoice (payment due in 7 days)
- `msg002.eml` — escalation notice, overdue invoice (high score)
- `msg003.eml` — weekly tech newsletter (no keyword match)
- `msg004.eml` — urgency-phrased payment confirmation request

```bash
python apps/mailwatch/run.py
```

Configuration: `apps/mailwatch/config.toml` — set `mail_dir` and add/remove `[[keywords]]` entries.

---

### drainwatch

`apps/drainwatch/` — Reads JSON event logs of on-chain ETH transfers, computes per-vault mean and standard deviation, and flags transfers that exceed either a hard ETH threshold or a configurable σ-multiple of the mean.

**Sample data:** `apps/drainwatch/data/transfers_2026-11-13.json` — 10 synthetic transfers from `0xVault01`, two of which are obvious anomalies (48.5 ETH and 142.7 ETH while the rest are ~1 ETH).

```bash
python apps/drainwatch/run.py
```

Configuration: `apps/drainwatch/config.toml` — `hard_threshold_eth`, `sigma_multiplier`, `[alert_levels]`.

---

## Job spec reference

Job specs are TOML files under `jobs/`.

| Field       | Type   | Required | Description |
|-------------|--------|----------|-------------|
| `id`        | string | ✓        | Unique identifier. Used in state file and card header. |
| `kind`      | string | ✓        | `"script"` or `"llm"`. |
| `schedule`  | string |          | `"manual"` (default), `"daily"`, `"hourly"`, or `"HH:MM"` (UTC). |
| `command`   | string | script   | Shell command to run. Supports `{state_dir}` substitution. |
| `prompt`    | string | llm      | Prompt to send to the LLM. |
| `timeout`   | int    |          | Seconds before the job is killed. Default `60`. |
| `state_key` | string |          | Custom label for the state entry (informational). |
| `model`     | string | llm      | Override the default model for this job only. |

### Schedule semantics

- `manual` — only runs when explicitly requested (`run --job <id>`).
- `daily` — skips if the job already ran today (UTC date).
- `hourly` — skips if the job already ran during the current UTC hour.
- `HH:MM` — skips if the job already ran during this UTC minute today.

Pass `-f` / `--force` to override the schedule.

---

## Card anatomy

```
┌─ job-id ──────────────────── [✓ OK] ─┐
│  key     : value                      │
│  another : longer value that wraps    │
│            across two lines           │
└─ 0.042 s ────────────────────────────┘
```

Cards are pure functions in `cards.py` — easy to unit test, easy to pipe.  Width defaults to 64 characters; pass `width=N` to `render_card()` to change it.

---

## State file

Stored at `.skeleton_crew_state/state.json` (override with `--state-dir`).

```json
{
  "mailwatch": {
    "last_run": "2026-11-13T08:05:11+00:00",
    "last_status": "ok"
  }
}
```

---

## LLM provider

`providers.py` speaks the OpenAI Chat Completions API over plain HTTPS with `urllib.request`.  Any OpenAI-compatible endpoint works (Ollama, LiteLLM, OpenRouter, Anthropic proxy, …).

Config priority: explicit kwargs → env vars → `skeleton_crew.toml` → defaults.

| Env var             | Default                             |
|---------------------|-------------------------------------|
| `SKELETON_API_KEY`  | (empty — required for real calls)   |
| `SKELETON_BASE_URL` | `https://api.openai.com/v1`         |
| `SKELETON_MODEL`    | `gpt-4o-mini`                       |
| `SKELETON_TIMEOUT`  | `30`                                |

---

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```

The test suite is stdlib-only (no pytest).  It covers:
- card renderer (width, borders, wrapping, all status badges)
- state load/save round-trip and schedule skip logic
- job execution (success, failure, timeout, skip, force)
- mailwatch and drainwatch integration against sample data

---

## Design principles

- **Standard library only** — no `pip install`, no `requirements.txt` to maintain.
- **Cards are the output format** — every job result becomes a card; failures too.
- **Lean and legible** — short functions, clear names, no magic.
- **Fail safe** — a crashing job emits an error card; it never takes the runner down.

---

## License

MIT
