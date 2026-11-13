"""
__main__.py – CLI entry point for skeleton-crew.

Usage
─────
  python -m skeleton_crew run --job <id>      Run a specific job by id.
  python -m skeleton_crew run --job all       Run all jobs in jobs/.
  python -m skeleton_crew run --job <id> -f   Force run (ignore schedule).
  python -m skeleton_crew list                List all job specs.
  python -m skeleton_crew render --demo       Print demo cards to stdout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def cmd_run(args: argparse.Namespace) -> int:
    from skeleton_crew.runner import (
        JOBS_DIR, DEFAULT_STATE_DIR,
        list_jobs, load_job_spec, run_job, run_all,
    )

    jobs_dir = Path(args.jobs_dir) if args.jobs_dir else JOBS_DIR
    state_dir = Path(args.state_dir) if args.state_dir else DEFAULT_STATE_DIR
    force = args.force

    job_id: str = args.job

    if job_id.lower() == "all":
        cards = run_all(jobs_dir=jobs_dir, state_dir=state_dir, force=force)
        for card in cards:
            print(card)
            print()
        return 0

    # find the specific job
    specs = list_jobs(jobs_dir)
    matched = [s for s in specs if s["id"] == job_id]
    if not matched:
        # try loading directly by filename
        direct = jobs_dir / f"{job_id}.toml"
        if direct.exists():
            try:
                matched = [load_job_spec(direct)]
            except Exception as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
        else:
            print(f"error: no job with id '{job_id}' found in {jobs_dir}", file=sys.stderr)
            return 1

    card = run_job(matched[0], state_dir=state_dir, force=force)
    print(card)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from skeleton_crew.runner import JOBS_DIR, list_jobs

    jobs_dir = Path(args.jobs_dir) if args.jobs_dir else JOBS_DIR
    specs = list_jobs(jobs_dir)

    if not specs:
        print(f"No jobs found in {jobs_dir}")
        return 0

    # table header
    col_id  = max(len(s["id"]) for s in specs)
    col_id  = max(col_id, 4)
    fmt = f"  {{:<{col_id}}}  {{:<8}}  {{:<8}}  {{}}"
    print(fmt.format("ID", "KIND", "SCHEDULE", "COMMAND / PROMPT"))
    print("  " + "─" * (col_id + 2 + 8 + 2 + 8 + 2 + 40))
    for s in specs:
        detail = s.get("command") or s.get("prompt") or "—"
        detail = detail[:60]
        print(fmt.format(
            s["id"],
            s.get("kind", "?"),
            s.get("schedule", "manual"),
            detail,
        ))
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    if args.demo:
        from skeleton_crew.cards import render_demo
        print(render_demo())
        return 0
    print("error: use --demo to render example cards", file=sys.stderr)
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m skeleton_crew",
        description="skeleton-crew: schedule agent jobs, render cards.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- run --
    p_run = sub.add_parser("run", help="Execute one job or all jobs.")
    p_run.add_argument("--job", required=True, metavar="ID|all",
                       help="Job id to run, or 'all'.")
    p_run.add_argument("-f", "--force", action="store_true",
                       help="Run even if schedule says skip.")
    p_run.add_argument("--jobs-dir", default=None, metavar="PATH",
                       help="Override jobs/ directory.")
    p_run.add_argument("--state-dir", default=None, metavar="PATH",
                       help="Override state directory.")

    # -- list --
    p_list = sub.add_parser("list", help="List all job specs.")
    p_list.add_argument("--jobs-dir", default=None, metavar="PATH",
                        help="Override jobs/ directory.")

    # -- render --
    p_render = sub.add_parser("render", help="Render cards to stdout.")
    p_render.add_argument("--demo", action="store_true",
                          help="Print demo cards.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        "run":    cmd_run,
        "list":   cmd_list,
        "render": cmd_render,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
