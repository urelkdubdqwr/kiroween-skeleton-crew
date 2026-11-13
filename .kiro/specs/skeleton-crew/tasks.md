# Tasks — skeleton-crew

## Completed Foundation Tasks

### Phase 1 – Core scaffold

- [x] Create `src/skeleton_crew/__init__.py` with version metadata
- [x] Create `src/skeleton_crew/cards.py` — pure card renderer
  - `render_header`, `render_footer`, `render_row`, `render_card`, `render_demo`
  - Width parameter on every function; constant-width line invariant
- [x] Create `src/skeleton_crew/runner.py` — job runner + state
  - `load_state`, `save_state`, `_should_skip`
  - `load_job_spec`, `list_jobs`
  - `run_job`, `run_all`
- [x] Create `src/skeleton_crew/providers.py` — LLM client
  - `chat_completion`, `stream_chat_completion`
  - Config resolution: kwargs → env → TOML → defaults
  - `ProviderError` exception class
- [x] Create `src/skeleton_crew/__main__.py` — CLI
  - Subcommands: `run`, `list`, `render`
  - `--job`, `--force`, `--jobs-dir`, `--state-dir` flags

### Phase 2 – Job specs

- [x] `jobs/hello.toml` — manual script job (`echo`)
- [x] `jobs/mailwatch.toml` — daily script job
- [x] `jobs/drainwatch.toml` — hourly script job
- [x] `jobs/daily-report.toml` — LLM job at 08:00

### Phase 3 – Example apps

- [x] `apps/mailwatch/run.py` — keyword scoring over maildir
- [x] `apps/mailwatch/config.toml` — keyword definitions
- [x] `apps/mailwatch/data/*.eml` — 4 synthetic email samples
- [x] `apps/drainwatch/run.py` — σ-anomaly detection over JSON transfer logs
- [x] `apps/drainwatch/config.toml` — threshold config
- [x] `apps/drainwatch/data/transfers_2026-11-13.json` — 10 synthetic transfers

### Phase 4 – Tests

- [x] `tests/test_cards.py` — card renderer unit tests (width, borders, badges, wrapping)
- [x] `tests/test_runner.py` — state round-trip, skip logic, run_job lifecycle
- [x] `tests/test_apps.py` — subprocess integration + detection unit tests

### Phase 5 – Documentation

- [x] `README.md` — quickstart, app descriptions, job spec reference, card anatomy
- [x] `.kiro/specs/skeleton-crew/requirements.md`
- [x] `.kiro/specs/skeleton-crew/design.md`
- [x] `.kiro/specs/skeleton-crew/tasks.md`
- [x] `.kiro/steering/project.md`

---

## Potential Future Tasks

These are not part of the current foundation but represent natural extensions:

- [ ] Add a `watch` subcommand that polls and runs due jobs on a tick interval
- [ ] Add `--output json` flag to `run` for machine-readable card data
- [ ] Add `--width N` flag to override card width from CLI
- [ ] Support multiple job directories via `--jobs-dir` glob or list
- [ ] Add a `mailwatch` app option to mark processed messages (avoid re-scanning)
- [ ] Add a `drainwatch` app option to persist seen tx hashes (deduplicate alerts)
- [ ] Add an optional `notify` field in job specs (write card to file / pipe to command)
- [ ] Support Ollama natively by auto-detecting model names without `api_key`
- [ ] Add `python -m skeleton_crew run --job all --dry-run` to show what would run
