# nixkeeper status

Whether each part of [nixkeeper](https://github.com/nixkeeper/nixkeeper) is
on time: its sync and hourly updates, the five digests, start-runs, the
tests on main of every repository, and the tokens that expire. One page,
[nixkeeper.github.io/status](https://nixkeeper.github.io/status/), and an
issue here for anything that needs attention.

## What it checks

Every hour, [`check.yml`](.github/workflows/check.yml) looks at each row of
[`nixkeeper_status/checks.py`](nixkeeper_status/checks.py):

- **runs**: when a workflow last ran, and whether its last runs passed;
- **data**: when a digest's data (or the page's) was made, from its
  `meta.json`, as a run can pass and still publish nothing new;
- **start-runs**: when it last started a run (it starts them from outside
  GitHub, whose own schedules come hours late when it's busy);
- **tests on main** in every repository;
- **tokens**: the security tracker's (it renews itself) and start-runs'
  (renewed by hand), before they expire;
- and backlogs worth seeing (logs or diffs still to read), never late.

Each part says when it's late, from a week of real runs: green is on time,
yellow is late, red needs attention; grey couldn't be read (GitHub's
trouble, not the part's). A row is as bad as its worst part.

## Notifications

A row that turns red opens an issue here, labelled `status`, with what's
wrong and links to its runs. It stays open while the row is late, and
closes itself with a comment once it's on time again. Watching this
repository is all it takes to be told: GitHub sends issues by mail and to
its mobile app. When GitHub can't be read for most rows, no issue opens or
closes.

The check is started by GitHub's schedule and by start-runs, so it keeps
running when either stops. If both stop, the page says its results are old.

## The page

[`index.html`](index.html) on GitHub Pages (from main, served as it is:
`.nojekyll`), reading `data/status.json` from the `data` branch, which each
check replaces (main plus one commit: the issues are the record of what
went wrong). `?data=URL` reads another status.json.

## Running it

`python3 -m nixkeeper_status check --out data` checks every row and writes
`data/status.json` (Python 3.11 or later, standard library only; with
`GITHUB_TOKEN` set, GitHub allows more than 60 requests an hour).
`--issues` opens and closes the issues (with `GITHUB_REPOSITORY`),
`--dry-run` says which it would. `nix run . -- check` does the same;
`nix flake check` runs the tests (which never ask GitHub), lint and the
formatting check; `nix fmt` formats.

To check something new, add a row to `checks.py`.

## AI & automation disclosure

This repository's code and documentation are written with the assistance of
an AI (Claude, by Anthropic), with a person in the loop: nixkeeper's
maintainer decides what to build, and reviews and tests every change before
it's merged. The check itself is automation: a scheduled workflow that reads
nixkeeper's public runs and data, and opens and closes issues in this
repository only. It never comments on, closes or merges anything in nixpkgs.

## License

MIT
