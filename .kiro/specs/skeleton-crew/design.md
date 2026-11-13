# Design — skeleton-crew

## Architecture

skeleton-crew is a small Python package (`src/skeleton_crew/`) plus two standalone example apps (`apps/`).  There is no framework, no event loop, and no daemon process.  The whole system is stateless except for a single JSON state file.

```
┌──────────────────────────────────────────────┐
│  python -m skeleton_crew <command>           │
│            __main__.py                       │
└──────────────┬───────────────────────────────┘
               │
       ┌───────┴────────┐
       │                │
  runner.py         cards.py
  job loading        render_card()
  state I/O          render_demo()
  subprocess         (pure functions)
  skip logic
       │
  providers.py
  chat_completion()
  urllib only
```

---

## Module responsibilities

### `cards.py`
Pure functions only.  No I/O.  Takes structured data, returns strings.

Key functions:
- `render_header(job_id, status, width)` → str
- `render_footer(duration_s, width)` → str
- `render_row(key, value, width)` → list[str]
- `render_card(job_id, status, fields, duration_s, width)` → str
- `render_demo()` → str

The card width is a parameter, not a global.  Every line is padded to exactly `width` characters so cards look uniform when printed or pasted.

---

### `runner.py`
All side-effectful logic lives here: file I/O, subprocess, state.

Key functions:
- `load_state(state_dir)` → dict  — reads `state.json`, returns `{}` on error
- `save_state(state, state_dir)` — writes `state.json`, creates dir if needed
- `_should_skip(job, job_state)` → bool — pure logic based on schedule + last_run
- `load_job_spec(path)` → dict — parses TOML, validates required fields
- `list_jobs(jobs_dir)` → list[dict]
- `run_job(job, state_dir, *, force)` → str (card)
- `run_all(jobs_dir, state_dir, *, force)` → list[str] (cards)

`run_job` wraps execution in a broad try/except so a crashing job never propagates.

---

### `providers.py`
Minimal HTTP client for OpenAI-compatible endpoints.

Key functions:
- `chat_completion(prompt, *, system, model, base_url, api_key, timeout, ...)` → str
- `stream_chat_completion(prompt, ...)` — streams tokens to stdout
- `_resolve_config(...)` — merges kwargs / env / TOML / defaults
- `_load_toml_provider_config(path)` → dict

Raises `ProviderError` (a `RuntimeError` subclass) on any failure so callers can handle it uniformly.

---

### `__main__.py`
Thin arg-parsing layer.  Each CLI subcommand maps to a `cmd_*` function that delegates to `runner` or `cards`.

Subcommands: `run`, `list`, `render`.

---

## State file schema

```json
{
  "<job_id>": {
    "last_run":    "<ISO-8601 with timezone>",
    "last_status": "ok"
  }
}
```

Written only on success.  On failure the previous state entry is preserved (or absent if the job never succeeded), so the next run will retry rather than skip.

---

## Schedule semantics

| Schedule  | Skip condition                              |
|-----------|---------------------------------------------|
| `manual`  | Never skip                                  |
| `daily`   | `last_run.date() == today (UTC)`            |
| `hourly`  | `last_run.date == today` and `hour == now`  |
| `HH:MM`   | `last_run.date == today` and `HH:MM == now` |

---

## Example apps

### mailwatch

```
apps/mailwatch/
├── config.toml    – mail_dir, [[keywords]] with word + weight
├── data/          – .eml sample files
└── run.py         – parse_eml(), score_message(), main()
```

Scoring: for each message, sum the weights of all keywords found in `subject + body`.  Sort descending.  Emit JSON with `status`, `scanned`, `matches`, `top_match`, `ranked[]`.

### drainwatch

```
apps/drainwatch/
├── config.toml    – data_dir, hard_threshold_eth, sigma_multiplier, [alert_levels]
├── data/          – JSON transfer logs
└── run.py         – load_transfers(), detect_anomalies(), main()
```

Detection: compute mean and sample stddev of `amount_eth` per batch.  Flag if `amount >= hard_threshold` OR `amount > mean + sigma_mult * stddev`.  Assign CRITICAL / HIGH / MEDIUM / LOW alert levels.  Exit 1 if anomalies found.

---

## Testing strategy

| Test file        | What it covers                                      |
|------------------|-----------------------------------------------------|
| `test_cards.py`  | All card functions; width invariant; badge text     |
| `test_runner.py` | State round-trip; skip logic; script job lifecycle  |
| `test_apps.py`   | Subprocess integration; detection unit tests        |

Tests use only `unittest` and `tempfile`.  No mocking framework needed: I/O is isolated by injecting `state_dir` paths into temp directories.
