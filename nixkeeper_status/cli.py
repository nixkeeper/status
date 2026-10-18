"""`python3 -m nixkeeper_status check`: checks every row, writes
data/status.json (the page's), and opens or closes this repository's issues
(--issues, in the workflow), telling Telegram too when it's set up.
`python3 -m nixkeeper_status telegram --test | --failed`: one message."""

import argparse
import json
import os
import sys
from datetime import UTC, datetime

from . import check, issues, telegram
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
    say = sub.add_parser(
        "telegram",
        help="send a Telegram message (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)",
    )
    what = say.add_mutually_exclusive_group(required=True)
    what.add_argument("--test", action="store_true", help="a test message")
    what.add_argument(
        "--failed", action="store_true", help="that the check itself failed"
    )
    args = parser.parse_args(argv)
    server, repo, run_id = (
        os.environ.get(k)
        for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID")
    )
    run_url = (
        f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else None
    )

    if args.command == "telegram":
        bot = telegram.Telegram.from_env()
        if not bot:
            print("No TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID: nothing sent.")
            return 0
        if args.test:
            text = (
                f"{telegram.CLOSED} nixkeeper status will send its notifications here"
            )
        else:
            text = telegram.check_failed(run_url)
        return 0 if bot.send(text) else 1

    gh = gh or GitHub(os.environ.get("GITHUB_TOKEN"))
    now = now or datetime.now(UTC)
    status = check.check(gh, now)
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
        issues.apply(
            gh,
            repo,
            status,
            now,
            run_url,
            dry_run=args.dry_run,
            telegram=None if args.dry_run else telegram.Telegram.from_env(),
        )
    return 0
