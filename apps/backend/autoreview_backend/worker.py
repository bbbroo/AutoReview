from __future__ import annotations

import argparse
from pathlib import Path

from ng_drawing_qa.services.review import run_project_review


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AutoReview isolated review worker")
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--project-db", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--config")
    args = parser.parse_args(argv)

    if args.command == "run":
        run_project_review(
            project_db_path=Path(args.project_db),
            project_id=args.project_id,
            run_id=args.run_id,
            profile=args.profile,
            config_path=Path(args.config) if args.config else None,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
