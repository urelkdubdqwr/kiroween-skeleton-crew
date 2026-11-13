# Requirements — skeleton-crew

## Overview

skeleton-crew is a lean, dependency-free Python template for scheduling agent jobs and rendering their results as compact Unicode "cards" suitable for pasting into a chat, displaying in a terminal, or piping to any text sink.

---

## Functional Requirements

### FR-01 Job Scheduling
- The system MUST support defining jobs as TOML files under `jobs/`.
- Each job spec MUST declare: `id` (string), `kind` ("script" | "llm"), and optionally `schedule`, `command`, `prompt`, `timeout`, `state_key`, `model`.
- Schedule values MUST include: `"manual"`, `"daily"`, `"hourly"`, and `"HH:MM"` (UTC wall-clock).
- The runner MUST skip a job when its schedule condition is already satisfied for the current period.
- Passing `-f` / `--force` MUST override the skip check.

### FR-02 Job Execution
- The runner MUST execute `kind = "script"` jobs by running the `command` field via a subprocess.
- The runner MUST execute `kind = "llm"` jobs by calling the configured LLM provider with the `prompt` field.
- The runner MUST respect the `timeout` field (default 60 s) and kill jobs that exceed it.
- A failing or timing-out job MUST NOT crash the runner; it MUST emit an error card instead.

### FR-03 State Persistence
- After a successful job run, the runner MUST write `{ "last_run": "<ISO-8601>", "last_status": "ok" }` to a JSON state file keyed by job `id`.
- The default state directory is `.skeleton_crew_state/`.
- The state directory MUST be overridable via `--state-dir`.

### FR-04 Card Rendering
- Every job result (success, failure, skip) MUST be rendered as a Unicode card.
- A card MUST consist of: a header line (job id + status badge), zero or more key/value rows, and a footer line (duration).
- All lines in a card MUST be the same width (default 64 chars; configurable).
- Long values MUST wrap across continuation lines inside the card border.
- Status badges MUST include: `✓ OK`, `✗ ERROR`, `⊘ SKIPPED`, `⟳ RUNNING`, `★ DEMO`.

### FR-05 LLM Provider
- `providers.py` MUST implement a `chat_completion(prompt)` function using only `urllib.request`.
- Configuration priority: explicit kwargs → environment variables → `skeleton_crew.toml` → hard-coded defaults.
- Environment variables: `SKELETON_API_KEY`, `SKELETON_BASE_URL`, `SKELETON_MODEL`, `SKELETON_TIMEOUT`.
- Any OpenAI-compatible endpoint (Ollama, LiteLLM, OpenRouter, …) MUST work without code changes.

### FR-06 CLI
- `python -m skeleton_crew run --job <id>` MUST run the named job.
- `python -m skeleton_crew run --job all` MUST run all jobs in `jobs/`.
- `python -m skeleton_crew list` MUST print a table of all jobs.
- `python -m skeleton_crew render --demo` MUST print example cards to stdout.

### FR-07 Example Apps
- `apps/mailwatch/run.py` MUST scan `.eml` files for weighted-keyword matches and emit ranked JSON.
- `apps/drainwatch/run.py` MUST read JSON transfer logs, detect σ-based and hard-threshold anomalies, and emit alert JSON.
- Both apps MUST work with sample data bundled in their respective `data/` directories.
- Both apps MUST run with `python apps/<name>/run.py` from the repo root.

---

## Non-Functional Requirements

### NFR-01 Standard Library Only
- No third-party packages MAY be imported at runtime.
- `tomllib` (stdlib since 3.11), `urllib`, `email`, `json`, `subprocess`, `unittest` are all permitted.

### NFR-02 Python Version
- Minimum supported version: Python 3.11.

### NFR-03 Code Size
- Total Python source SHOULD remain between 600 and 1200 lines.

### NFR-04 Testability
- All card functions MUST be pure (no I/O, no global state).
- State functions MUST accept a `state_dir` path argument so tests can use temp dirs.
- Tests MUST use `unittest` only (no pytest).

### NFR-05 Legibility
- Functions SHOULD be short (≤ 30 lines preferred).
- Names SHOULD be clear and self-documenting.
- No "clever" tricks: no metaclasses, no dynamic import loops, no monkey-patching.
