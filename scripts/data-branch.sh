# shellcheck shell=bash
# The data branch, for the check workflow (.github/workflows/check.yml): main
# with one commit on top, holding data/status.json, the last check's
# results (the page reads it from there). Each run replaces the branch with
# main plus one new commit, so no history piles up: the issues are the
# record of what went wrong. Adapted from the digests'.
#
#   bash scripts/data-branch.sh publish MESSAGE
#       commit data/ on main and replace the data branch with it
#
# For the workflow's checkout: it makes nixkeeper-bot the committer there.

# A failed push is tried again, 4 attempts in all, NIXKEEPER_PUSH_PAUSE seconds
# apart (30 by default): GitHub sometimes answers a push with a 500, and the
# whole run's work would wait for the next run.

set -euo pipefail

git config user.name "nixkeeper-bot"
git config user.email "nixkeeper-bot@users.noreply.github.com"

case "${1:-}" in
  publish)
    message="${2:?publish needs a commit message}"
    if [ ! -f data/status.json ]; then
      echo "::error::No data/status.json: nothing to publish."
      exit 1
    fi
    git checkout -q -B data
    git add -f data
    git commit -q -m "$message"
    # Each check stands on its own: the newest replaces whatever is there
    # (the workflow's concurrency group runs one at a time).
    pause=${NIXKEEPER_PUSH_PAUSE:-30}
    attempts=4
    for attempt in $(seq "$attempts"); do
      if git push -q --force origin HEAD:data; then
        break
      fi
      if [ "$attempt" -eq "$attempts" ]; then
        echo "::error::Pushing the status failed $attempts times."
        exit 1
      fi
      echo "::warning::Pushing the status failed (attempt $attempt of $attempts), trying again in $pause s."
      sleep "$pause"
    done
    echo "Published the status as $(git rev-parse --short HEAD), on main."
    ;;
  *)
    echo "usage: bash scripts/data-branch.sh publish MESSAGE" >&2
    exit 2
    ;;
esac
