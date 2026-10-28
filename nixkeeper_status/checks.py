"""What's checked: each row of the page, and the parts it's made of.

A part is one thing to look at, with when it's late (in hours, or days for
expiries): up to `green` it's on time, after `red` it's an issue (opened in
this repository), in between it's late (yellow, on the page only). The
times come from a week of real runs (2026-10-11 to 18): the hourly digests
ran at most 1 h apart (2 h for nixkeeper's hourly updates, which start-runs
skips when the sync starts), the 3-hourly ones at most 3 h, digest-versions
12 h; the only longer gaps were the move to the organisation, 2026-10-13
(4 to 7.5 h).

Kinds of parts:

- run: a workflow's newest run (when it was started) and the last ones'
  results: one failed is late, two in a row an issue. A cancelled run
  counts as failed when its job ran 15 minutes or more (it ran out of
  time); one replaced while it waited, or stopped soon, counts for nothing.
- data: when a digest's (or the dashboard's) data was made, a field of its
  meta.json: a run can pass and still publish nothing new.
- ci: the tests on main (the newest push's CI run): failing is an issue.
- started: the newest run any of the workflows had started through the API
  (start-runs, from the Oracle server): if it stops, every schedule falls
  back to GitHub's own, hours late when it's busy.
- expiry: a token's expiry, from a meta.json field or a date written here.
- note: a number worth seeing (a backlog), shown only when it's not zero;
  never late.
- source: what nixkeeper's last sync read from a source, from its
  index.json's "sources" (the counts and evaluations its page's "Where the
  data is from" listed, until it grew too long for a phone): a note, never
  late; "not used" with why, when the sync didn't use it.
- problems: a list of mistakes in a JSON field (the package lists'
  listProblems, which the sync writes when a list names something that's
  gone): any at all is an issue, none is on time.
"""

DASHBOARD = "https://nixkeeper.com/data/"


def digest_meta(repo):
    return f"https://raw.githubusercontent.com/nixkeeper/{repo}/data/data/meta.json"


def run(repo, workflow, green, red):
    return {
        "kind": "run",
        "repo": repo,
        "workflow": workflow,
        "green": green,
        "red": red,
    }


def data(url, field, green, red, what="data", say=None):
    """When a meta.json's field says its data is from: "{what} from {ago}",
    or "{say(meta)}, as of {ago}" to name what it is."""
    return {
        "kind": "data",
        "url": url,
        "field": field,
        "green": green,
        "red": red,
        "what": what,
        "say": say,
    }


def note(url, field, text):
    return {"kind": "note", "url": url, "field": field, "text": text}


def source(key, label, say):
    """A note on what nixkeeper's last sync read from a source: label, then
    say(its entry in index.json's "sources"), and when it was read."""
    return {"kind": "source", "key": key, "label": label, "say": say}


def _n(x):
    return f"{x:,}" if isinstance(x, int) else str(x)


def problems(url, field, what):
    return {"kind": "problems", "url": url, "field": field, "what": what}


HOURLY_DIGESTS = [
    ("nixkeeper/digest-builds", "digest.yml"),
    ("nixkeeper/digest-vulnerabilities", "digest.yml"),
    ("nixkeeper/digest-prs", "digest.yml"),
    ("nixkeeper/digest-update-bot", "digest.yml"),
    ("nixkeeper/nixkeeper", "data-hourly.yml"),
    ("nixkeeper/nixkeeper", "data-daily.yml"),
]

# start-runs' token (a fine-grained one, Actions: read and write) expires on
# this day: written here, as nothing publishes it. Update it with the token.
START_RUNS_TOKEN_EXPIRES = "2027-01-04"
# digest-versions' GitLab token (read_api, for gitlab.com) expires on this
# day, also written here. Update it with the token.
GITLAB_TOKEN_EXPIRES = "2027-10-27"

ROWS = [
    # Runs and data.
    {
        "id": "nixkeeper-sync",
        "group": "runs",
        "name": "nixkeeper: sync",
        "every": "every 3 hours",
        "link": "https://github.com/nixkeeper/nixkeeper/actions/workflows/data-daily.yml",
        "parts": [
            run("nixkeeper/nixkeeper", "data-daily.yml", 4, 7),
            data(DASHBOARD + "index.json", "checkedAt", 4, 8, "the page's data"),
            source("nixpkgs", "nixpkgs", lambda s: f"channel at {s['revision'][:7]}"),
        ],
    },
    {
        "id": "package-lists",
        "group": "runs",
        "name": "nixkeeper: package lists",
        "every": "checked by every sync",
        "link": "https://nixkeeper.com/",
        "parts": [
            # A list naming a package nixpkgs no longer has
            # (extraPackages.gaming: pokemmo-installer, 2026-10-20): the page
            # says so at its top, here it's an issue.
            problems(DASHBOARD + "index.json", "listProblems", "the package lists"),
        ],
    },
    {
        "id": "nixkeeper-hourly",
        "group": "runs",
        "name": "nixkeeper: hourly updates",
        "every": "every hour, but the sync's",
        "link": "https://github.com/nixkeeper/nixkeeper/actions/workflows/data-hourly.yml",
        "parts": [run("nixkeeper/nixkeeper", "data-hourly.yml", 2.5, 5)],
    },
    {
        "id": "start-runs",
        "group": "runs",
        "name": "start-runs",
        "every": "every hour at :15",
        "link": "https://github.com/nixkeeper/nixkeeper/blob/main/scripts/start-runs.sh",
        "parts": [
            {"kind": "started", "workflows": HOURLY_DIGESTS, "green": 1.5, "red": 3},
        ],
    },
    {
        "id": "digest-builds",
        "group": "runs",
        "name": "digest-builds",
        "every": "every hour",
        "link": "https://github.com/nixkeeper/digest-builds/actions/workflows/digest.yml",
        "parts": [
            run("nixkeeper/digest-builds", "digest.yml", 2, 4),
            # Only new with a new evaluation of master: Hydra's pace, not
            # the digest's, so never an issue here.
            data(
                digest_meta("digest-builds"),
                "fetchedAt",
                24,
                None,
                "master's evaluation read",
                lambda m: f"master: evaluation {m['eval']}",
            ),
            note(
                digest_meta("digest-builds"),
                "reasons.pending",
                "{n} failed builds' logs still to read",
            ),
            note(
                digest_meta("digest-builds"),
                "blocked.pending",
                "{n} blocked builds still to look up",
            ),
            source(
                "branch:staging-next",
                "staging-next",
                lambda s: f"evaluation {s['eval']}",
            ),
            source(
                "branch:haskell-updates",
                "haskell-updates",
                lambda s: f"evaluation {s['eval']}, {_n(s.get('jobs', '?'))} jobs",
            ),
        ],
    },
    {
        "id": "digest-versions",
        "group": "runs",
        "name": "digest-versions",
        "every": "every 12 hours",
        "link": "https://github.com/nixkeeper/digest-versions/actions/workflows/digest.yml",
        "parts": [
            run("nixkeeper/digest-versions", "digest.yml", 14, 26),
            data(digest_meta("digest-versions"), "outdatedAt", 14, 26),
            source("versions", "Repology", lambda s: f"{_n(s['projects'])} projects"),
            source(
                "releases", "GitHub releases", lambda s: f"{_n(s['packages'])} packages"
            ),
            source(
                "typst", "Typst Universe", lambda s: f"{_n(s['packages'])} packages"
            ),
            source(
                "emacs",
                "Emacs archives",
                lambda s: (
                    f"MELPA {_n(s['melpa'])}, MELPA Stable {_n(s['melpaStable'])}, "
                    f"NonGNU {_n(s['nongnu'])}, GNU {_n(s['gnu'])} packages"
                ),
            ),
            source(
                "stackage",
                "Stackage LTS",
                lambda s: (
                    f"nixpkgs follows {s['nixpkgs']}, {s['snapshot']} is the newest "
                    f"({_n(s['packages'])} packages)"
                ),
            ),
            source(
                "cran",
                "CRAN, Bioconductor",
                lambda s: (
                    f"CRAN {_n(s['cran'])}, Bioconductor {s['biocVersion']}: "
                    f"{_n(s['bioc'] + s['annotation'] + s['experiment'])} packages"
                ),
            ),
        ],
    },
    {
        "id": "digest-update-bot",
        "group": "runs",
        "name": "digest-update-bot",
        "every": "every 3 hours",
        "link": "https://github.com/nixkeeper/digest-update-bot/actions/workflows/digest.yml",
        "parts": [
            run("nixkeeper/digest-update-bot", "digest.yml", 4, 8),
            data(digest_meta("digest-update-bot"), "fetchedAt", 4, 8),
            note(
                digest_meta("digest-update-bot"),
                "pending",
                "{n} attempts' logs still to read",
            ),
            source(
                "queue",
                "the bot's queue",
                lambda s: f"going round every {s['cycleDays']} days",
            ),
        ],
    },
    {
        "id": "digest-vulnerabilities",
        "group": "runs",
        "name": "digest-vulnerabilities",
        "every": "every hour",
        "link": "https://github.com/nixkeeper/digest-vulnerabilities/actions/workflows/digest.yml",
        "parts": [
            run("nixkeeper/digest-vulnerabilities", "digest.yml", 2, 4),
            data(
                digest_meta("digest-vulnerabilities"),
                "tracker.readAt",
                2,
                5,
                "the tracker read",
            ),
            data(digest_meta("digest-vulnerabilities"), "osv.readAt", 2, 5, "OSV read"),
            source(
                "tracker",
                "the security tracker",
                lambda s: (
                    f"{_n(s['suggestions'])} CVEs on {_n(s['packages'])} packages "
                    f"(release {s['release']})"
                ),
            ),
            source(
                "osv",
                "OSV",
                lambda s: (
                    f"{_n(s['advisories'])} advisories on {_n(s['packages'])} packages"
                ),
            ),
        ],
    },
    {
        "id": "digest-prs",
        "group": "runs",
        "name": "digest-prs",
        "every": "every hour",
        "link": "https://github.com/nixkeeper/digest-prs/actions/workflows/digest.yml",
        "parts": [
            run("nixkeeper/digest-prs", "digest.yml", 2, 4),
            data(digest_meta("digest-prs"), "generatedAt", 2, 5),
            data(digest_meta("digest-prs"), "fullSweepAt", 26, 50, "the full sweep"),
            note(
                digest_meta("digest-prs"),
                "diffs.pending",
                "{n} PRs' diffs still to read",
            ),
            source(
                "prs",
                "nixpkgs' PRs",
                lambda s: (
                    f"{_n(s['prs'])} open PRs, {_n(s['issues'])} issues, "
                    f"{_n(s['merged'])} merged since the channel, "
                    f"{_n(s['staging'])} on staging"
                ),
            ),
        ],
    },
    {
        "id": "community-checks",
        "group": "runs",
        "name": "nixkeeper: community checks",
        "every": "every week",
        "link": "https://github.com/nixkeeper/nixkeeper/actions/workflows/community-checks.yml",
        "parts": [run("nixkeeper/nixkeeper", "community-checks.yml", 8 * 24, 15 * 24)],
    },
    # Tokens.
    {
        "id": "tracker-token",
        "group": "tokens",
        "name": "the security tracker's token",
        "every": "renews itself before it expires",
        "link": "https://github.com/nixkeeper/digest-vulnerabilities",
        "parts": [
            {
                "kind": "expiry",
                "url": digest_meta("digest-vulnerabilities"),
                "field": "tracker.tokenExpiry",
                "state": "tracker",
                "green": 10,
                "red": 3,
            },
        ],
    },
    {
        "id": "start-runs-token",
        "group": "tokens",
        "name": "start-runs' token",
        "every": "renewed by hand",
        "link": "https://github.com/settings/personal-access-tokens",
        "parts": [
            {"kind": "expiry", "date": START_RUNS_TOKEN_EXPIRES, "green": 21, "red": 7},
        ],
    },
    {
        "id": "gitlab-token",
        "group": "tokens",
        "name": "digest-versions' GitLab token",
        "every": "renewed by hand",
        "link": "https://gitlab.com/-/user_settings/personal_access_tokens",
        "parts": [
            {"kind": "expiry", "date": GITLAB_TOKEN_EXPIRES, "green": 21, "red": 7},
        ],
    },
]

# The tests on main, one row each.
CI_REPOS = [
    "nixkeeper",
    "digest-builds",
    "digest-versions",
    "digest-update-bot",
    "digest-vulnerabilities",
    "digest-prs",
    "nixkeeper-mcp",
    "status",
]
ROWS += [
    {
        "id": f"ci-{repo}",
        "group": "ci",
        "name": repo,
        "every": "on every push to main",
        "link": f"https://github.com/nixkeeper/{repo}/actions/workflows/ci.yml?query=branch%3Amain",
        "parts": [{"kind": "ci", "repo": f"nixkeeper/{repo}", "workflow": "ci.yml"}],
    }
    for repo in CI_REPOS
]

GROUPS = {
    "runs": "Runs and data",
    "ci": "Tests on main",
    "tokens": "Tokens",
}
