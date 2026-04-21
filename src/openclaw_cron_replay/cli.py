from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .core import compare_jobs, diff_prompt_replay, render_markdown, render_terminal, replay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openclaw-cron-replay",
        description="Replay OpenClaw cron job formatting and delivery decisions locally.",
    )
    parser.add_argument("--job", help="Job id from jobs.json.")
    parser.add_argument("--jobs", default="jobs.json", help="Path to jobs JSON. Defaults to jobs.json.")
    parser.add_argument("--result", help="Saved result JSON file.")
    parser.add_argument("--prompt", help="Saved prompt text file.")
    parser.add_argument("--payload", help="Saved payload text file.")
    parser.add_argument("--metadata", help="Optional prior run metadata JSON file.")
    parser.add_argument("--from-run", help="Prior run id. manual:<job-id> resolves the job id.")
    parser.add_argument("--json", action="store_true", help="Render replay report as JSON.")
    parser.add_argument("--markdown", action="store_true", help="Render replay report as Markdown.")
    parser.add_argument(
        "--compare",
        nargs=2,
        metavar=("BEFORE_JOBS_JSON", "AFTER_JOBS_JSON"),
        help="Diff two job config JSON files and exit.",
    )
    parser.add_argument(
        "--diff-prompt",
        help="Diff replay output against the same replay with a replacement prompt file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.compare:
            print(compare_jobs(Path(args.compare[0]), Path(args.compare[1])))
            return 0

        report = replay(
            job_id=args.job,
            jobs_path=Path(args.jobs),
            result_path=Path(args.result) if args.result else None,
            prompt_path=Path(args.prompt) if args.prompt else None,
            payload_path=Path(args.payload) if args.payload else None,
            metadata_path=Path(args.metadata) if args.metadata else None,
            from_run=args.from_run,
        )

        if args.diff_prompt:
            print(diff_prompt_replay(report, Path(args.diff_prompt)))
        elif args.json:
            print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
        elif args.markdown:
            print(render_markdown(report))
        else:
            print(render_terminal(report))
        return 0
    except Exception as exc:
        print(f"openclaw-cron-replay: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
