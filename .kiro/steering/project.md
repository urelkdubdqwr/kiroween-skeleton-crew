# Project Conventions — skeleton-crew

This document is the single source of truth for coding and design conventions in skeleton-crew.  Any agent or contributor working in this repository MUST follow these rules.

---

## 1. Standard Library Only

**No third-party packages.**

- Do not add a `requirements.txt`, `pyproject.toml` with dependencies, `setup.cfg`, or any other file that installs packages.
- Do not `import` anything outside the Python 3.11+ standard library.
- Permitted stdlib modules include (but are not limited to): `tomllib`, `urllib`, `email`, `json`, `subprocess`, `unittest`, `tempfile`, `pathlib`, `datetime`, `textwrap`, `math`, `sys`, `os`.
- If a task seems to require a third-party library, find the stdlib equivalent or implement the needed functionality inline.

---

## 2. Cards Are the Output Format

Every job result — success, failure, skip, or timeout — MUST become a card.

- Use `skeleton_crew.cards.render_card(job_id, status, fields, duration_s)`.
- Do not print raw dicts, tracebacks, or unformatted text as the final output of a job.
- Status MUST be one of: `"ok"`, `"error"`, `"skipped"`, `"running"`, `"demo"`.
- Card width defaults to 64; pass `width=N` if you need a different size.
- All lines in a card MUST be the same character width (the renderer enforces this).

---

## 3. Lean and Legible Code

- Functions SHOULD be ≤ 30 lines.  Split longer functions rather than keeping them.
- Names MUST be clear and self-documenting.  Avoid abbreviations unless universally understood (`cfg`, `tmp`, `std`).
- No clever tricks: no metaclasses, no dynamic `__getattr__`, no monkey-patching, no `eval`.
- Prefer explicit over implicit.  `if x is None:` not `if not x:` when None is the meaningful value.
- Comments explain *why*, not *what*.  Code should be readable enough that *what* is obvious.
- Total Python source SHOULD stay between 600 and 1200 lines across `src/skeleton_crew/`.

---

## 4. Pure Functions Where Possible

- `cards.py` MUST contain only pure functions (no I/O, no global mutable state).
- `runner.py` isolates all side-effectful code; it accepts `state_dir: Path` so tests can inject a temp dir.
- `providers.py` raises `ProviderError` on any failure; callers handle it uniformly.
- Tests MUST NOT rely on the filesystem outside of `tempfile.TemporaryDirectory()`.

---

## 5. Test With `unittest` Only

- No pytest, no hypothesis, no mock frameworks beyond `unittest.mock` if truly needed.
- Tests live in `tests/` and are discovered with `python3 -m unittest discover -s tests -v`.
- Each test file covers one module or one app.
- Use `subTest` for parametric cases rather than duplicating test methods.
- Tests MUST pass on a clean checkout with `python3 -m unittest discover -s tests -v` from the repo root.

---

## 6. File Layout

```
src/skeleton_crew/   – package source (pure Python, stdlib only)
jobs/                – TOML job specs
apps/<name>/         – self-contained app (run.py + config.toml + data/)
tests/               – unittest test files
.kiro/               – Kiro specs and steering (not shipped to users)
README.md            – user-facing documentation
```

Do not create files outside this layout without a good reason documented here.

---

## 7. App Conventions

Each app under `apps/` MUST:
- Run standalone: `python apps/<name>/run.py` from the repo root.
- Read its own config from `apps/<name>/config.toml` (resolved relative to the script file, with a cwd fallback).
- Emit valid JSON to stdout as its result.
- Exit 0 on success, 1 on detected anomalies or errors.
- Use only the standard library.
- Include sample data in `apps/<name>/data/` so the app works without any setup.

---

## 8. TOML Job Specs

Required fields: `id`, `kind`.  Optional: `schedule`, `command`, `prompt`, `timeout`, `state_key`, `model`.

- `id` values MUST be lowercase, hyphenated, and unique across `jobs/`.
- `command` fields MAY use `{state_dir}` as a substitution placeholder.
- Comments at the top of each TOML file MUST describe what the job does.

---

## 9. Versioning

The package version lives in `src/skeleton_crew/__init__.py` as `__version__ = "X.Y.Z"`.  Bump it when making breaking changes to the card format, state schema, or CLI flags.
