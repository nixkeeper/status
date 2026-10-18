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
    git push -q --force origin HEAD:data
    echo "Published the status as $(git rev-parse --short HEAD), on main."
    ;;
  *)
    echo "usage: bash scripts/data-branch.sh publish MESSAGE" >&2
    exit 2
    ;;
esac
