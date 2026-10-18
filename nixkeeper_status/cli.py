"""`python3 -m nixkeeper_status check`: checks every row, writes
data/status.json (the page's), and opens or closes this repository's issues
(--issues, in the workflow)."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime

from . import check, issues
from .github import GitHub


def main(argv=None, gh=None, now=None):
    parser = argparse.ArgumentParser(prog="nixkeeper_status")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("check", help="check every row and write status.json")
    run.add_argument("--out", default="data", help="where status.json goes")
    run.add_argument(
        "--issues",
        action="store_true",
        help="open and close this repository's issues (GITHUB_REPOSITORY)",
    )
    run.add_argument(
        "--dry-run", action="store_true", help="say which issues, change none"
    )
    args = parser.parse_args(argv)

    gh = gh or GitHub(os.environ.get("GITHUB_TOKEN"))
    now = now or datetime.now(UTC)
    status = check.check(gh, now)
    server, repo, run_id = (
        os.environ.get(k)
        for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")
    )
    run_url = (
        f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else None
    )
    if run_url:
        status["run"] = run_url

    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, "status.json")
    with open(path + ".tmp", "w") as f:
        json.dump(status, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(path + ".tmp", path)

    for row in status["rows"]:
        print(f"{row['state']:>7}  {row['name']}")
        for part in row["parts"]:
            if part["state"] not in (check.GREEN, None):
                print(f"         {check.text_of(part, now)}")
    print(f"overall: {status['state']}; wrote {path}")

    if args.issues or args.dry_run:
        if not repo:
            print("No GITHUB_REPOSITORY: no issues to open or close.", file=sys.stderr)
            return 2
        issues.apply(gh, repo, status, now, run_url, dry_run=args.dry_run)
    return 0
