import unittest

from nixkeeper_status import check, checks
from nixkeeper_status.github import Unavailable

from .fakes import NOW, FakeGitHub, at, run

R = ("nixkeeper/digest-prs", "digest.yml")
META = checks.digest_meta("digest-prs")


def one(part, gh):
    row = {
        "id": "x",
        "group": "runs",
        "name": "x",
        "every": "",
        "link": "",
        "parts": [part],
    }
    return check.check_row(row, gh, NOW, {})


class Helpers(unittest.TestCase):
    def test_by_age(self):
        self.assertEqual(check.by_age(1, 2, 4), check.GREEN)
        self.assertEqual(check.by_age(3, 2, 4), check.YELLOW)
        self.assertEqual(check.by_age(5, 2, 4), check.RED)
        self.assertEqual(check.by_age(500, 2, None), check.YELLOW)

    def test_ago(self):
        self.assertEqual(check.ago(check.parse_time(at(0.5)), NOW), "30 min ago")
        self.assertEqual(check.ago(check.parse_time(at(3)), NOW), "3.0 h ago")
        self.assertEqual(check.ago(check.parse_time(at(72)), NOW), "3 days ago")

    def test_field(self):
        self.assertEqual(check.field({"a": {"b": 1}}, "a.b"), 1)
        self.assertIsNone(check.field({"a": 1}, "a.b"))

    def test_worst(self):
        self.assertEqual(check.worst([check.GREEN, None, check.YELLOW]), check.YELLOW)
        self.assertEqual(check.worst([check.UNKNOWN, check.GREEN]), check.UNKNOWN)


class Runs(unittest.TestCase):
    part = checks.run(*R, 2, 4)

    def test_on_time(self):
        row = one(self.part, FakeGitHub({R: [run(0.5)]}))
        self.assertEqual(row["state"], check.GREEN)
        self.assertEqual(row["parts"][0]["text"], "last run {ago}: success")

    def test_late_then_an_issue(self):
        self.assertEqual(
            one(self.part, FakeGitHub({R: [run(3)]}))["state"], check.YELLOW
        )
        row = one(self.part, FakeGitHub({R: [run(5)]}))
        self.assertEqual(row["state"], check.RED)
        self.assertEqual(
            row["parts"][0]["text"], "last run {ago}, but one is expected within 2 h"
        )

    def test_failures(self):
        failed = FakeGitHub({R: [run(0.5, "failure", n=2), run(1.5)]})
        row = one(self.part, failed)
        self.assertEqual(row["state"], check.YELLOW)
        self.assertEqual(row["parts"][0]["link"], "https://github.com/runs/2")
        twice = FakeGitHub(
            {R: [run(0.5, "failure"), run(1.5, "cancelled"), run(2.5, "failure")]}
        )
        row = one(self.part, twice)
        self.assertEqual(row["state"], check.RED)
        self.assertIn("the last 2 runs failed", row["parts"][0]["text"])

    def test_running(self):
        row = one(
            self.part, FakeGitHub({R: [run(0.2, status="in_progress"), run(1.2)]})
        )
        self.assertEqual(row["state"], check.GREEN)
        self.assertIn("in progress", row["parts"][0]["text"])

    def test_unreadable(self):
        row = one(self.part, FakeGitHub({R: Unavailable("GET x: 502")}))
        self.assertEqual(row["state"], check.UNKNOWN)

    def test_no_runs(self):
        self.assertEqual(one(self.part, FakeGitHub())["state"], check.UNKNOWN)


class Data(unittest.TestCase):
    def test_age(self):
        part = checks.data(META, "generatedAt", 2, 5)
        gh = FakeGitHub(files={META: {"generatedAt": at(1)}})
        self.assertEqual(one(part, gh)["state"], check.GREEN)
        gh = FakeGitHub(files={META: {"generatedAt": at(6)}})
        row = one(part, gh)
        self.assertEqual(row["state"], check.RED)
        self.assertEqual(
            row["parts"][0]["text"], "data from {ago}, but it's expected within 2 h"
        )

    def test_named(self):
        part = checks.data(META, "at", 2, 4, "x", lambda m: f"evaluation {m['eval']}")
        row = one(part, FakeGitHub(files={META: {"at": at(1), "eval": 5}}))
        self.assertEqual(row["parts"][0]["text"], "evaluation 5, as of {ago}")
        row = one(part, FakeGitHub(files={META: {"at": at(1)}}))
        self.assertEqual(row["parts"][0]["text"], "x from {ago}")

    def test_never_red(self):
        part = checks.data(META, "fetchedAt", 24, None)
        gh = FakeGitHub(files={META: {"fetchedAt": at(200)}})
        self.assertEqual(one(part, gh)["state"], check.YELLOW)

    def test_missing(self):
        part = checks.data(META, "generatedAt", 2, 5)
        self.assertEqual(one(part, FakeGitHub(files={META: {}}))["state"], check.YELLOW)
        self.assertEqual(one(part, FakeGitHub())["state"], check.UNKNOWN)

    def test_note(self):
        part = checks.note(META, "diffs.pending", "{n} PRs' diffs still to read")
        row = one(part, FakeGitHub(files={META: {"diffs": {"pending": 1500}}}))
        self.assertEqual(row["parts"][0]["text"], "1,500 PRs' diffs still to read")
        self.assertEqual(row["parts"][0]["state"], None)
        row = one(part, FakeGitHub(files={META: {"diffs": {"pending": 0}}}))
        self.assertEqual(row["parts"], [])
        self.assertEqual(row["state"], check.UNKNOWN)


class Source(unittest.TestCase):
    index = checks.DASHBOARD + "index.json"
    part = checks.source("osv", "OSV", lambda s: f"{s['advisories']} advisories")

    def sources(self, **found):
        return FakeGitHub(files={self.index: {"sources": found}})

    def test_read(self):
        row = one(
            self.part, self.sources(osv={"used": True, "at": at(2), "advisories": 7})
        )
        self.assertEqual(row["parts"][0]["text"], "OSV: 7 advisories, as of {ago}")
        self.assertEqual(row["parts"][0]["state"], None)

    def test_not_used(self):
        row = one(self.part, self.sources(osv={"used": False, "why": "it's old"}))
        self.assertEqual(row["parts"][0]["text"], "OSV: not used, it's old")

    def test_changed_shape(self):
        row = one(self.part, self.sources(osv={"used": True}))
        self.assertEqual(row["parts"][0]["text"], "OSV: read")

    def test_missing_or_unreadable(self):
        self.assertEqual(one(self.part, self.sources())["parts"], [])
        self.assertEqual(one(self.part, FakeGitHub())["parts"], [])


class Problems(unittest.TestCase):
    """The package lists' problems, 2026-10-20: a list naming a package
    nixpkgs had removed."""

    URL = checks.DASHBOARD + "index.json"
    part = checks.problems(URL, "listProblems", "the package lists")

    def test_none(self):
        row = one(self.part, FakeGitHub(files={self.URL: {"checkedAt": at(1)}}))
        self.assertEqual(row["state"], check.GREEN)
        self.assertEqual(row["parts"][0]["text"], "the package lists: no problems")

    def test_any_is_an_issue(self):
        found = [
            "extraPackages.gaming: pokemmo-installer is neither a nixpkgs attribute"
        ]
        row = one(self.part, FakeGitHub(files={self.URL: {"listProblems": found}}))
        self.assertEqual(row["state"], check.RED)
        self.assertEqual(
            row["parts"][0]["text"],
            "the package lists: 1 problem, extraPackages.gaming: pokemmo-installer "
            "is neither a nixpkgs attribute",
        )
        many = [f"p{i}" for i in range(5)]
        row = one(self.part, FakeGitHub(files={self.URL: {"listProblems": many}}))
        self.assertEqual(
            row["parts"][0]["text"],
            "the package lists: 5 problems, p0; p1; p2; and 2 more",
        )

    def test_unreadable(self):
        self.assertEqual(one(self.part, FakeGitHub())["state"], check.UNKNOWN)


class Tests(unittest.TestCase):
    part = {"kind": "ci", "repo": "nixkeeper/status", "workflow": "ci.yml"}
    key = ("nixkeeper/status", "ci.yml")

    def test_failing(self):
        gh = FakeGitHub(
            {self.key: [run(2, "failure", event="push"), run(5, event="push")]}
        )
        row = one(self.part, gh)
        self.assertEqual(row["state"], check.RED)
        self.assertEqual(row["parts"][0]["text"], "failing on main, since {ago}")

    def test_passing(self):
        gh = FakeGitHub(
            {self.key: [run(2, "cancelled", event="push"), run(5, event="push")]}
        )
        self.assertEqual(one(self.part, gh)["state"], check.GREEN)


class Started(unittest.TestCase):
    part = {
        "kind": "started",
        "workflows": [R, ("nixkeeper/digest-builds", "digest.yml")],
        "green": 1.5,
        "red": 3,
    }

    def test_newest_of_all(self):
        gh = FakeGitHub(
            {
                R: [run(0.2), run(4, event="workflow_dispatch")],
                ("nixkeeper/digest-builds", "digest.yml"): [
                    run(0.7, event="workflow_dispatch")
                ],
            }
        )
        row = one(self.part, gh)
        self.assertEqual(row["state"], check.GREEN)
        self.assertIn("(digest-builds)", row["parts"][0]["text"])

    def test_stopped(self):
        gh = FakeGitHub({R: [run(0.2), run(5, event="workflow_dispatch")]})
        row = one(self.part, gh)
        self.assertEqual(row["state"], check.RED)
        self.assertIn("GitHub's own schedules run instead", row["parts"][0]["text"])


class Expiry(unittest.TestCase):
    def test_days(self):
        self.assertEqual(
            one(
                {"kind": "expiry", "date": "2026-12-01", "green": 21, "red": 7},
                FakeGitHub(),
            )["state"],
            check.GREEN,
        )
        self.assertEqual(
            one(
                {"kind": "expiry", "date": "2026-10-28", "green": 21, "red": 7},
                FakeGitHub(),
            )["state"],
            check.YELLOW,
        )
        row = one(
            {"kind": "expiry", "date": "2026-10-10", "green": 21, "red": 7},
            FakeGitHub(),
        )
        self.assertEqual(row["state"], check.RED)
        self.assertEqual(row["parts"][0]["text"], "expired on 2026-10-10")

    def test_tracker(self):
        meta = checks.digest_meta("digest-vulnerabilities")
        part = {
            "kind": "expiry",
            "url": meta,
            "field": "tracker.tokenExpiry",
            "state": "tracker",
            "green": 10,
            "red": 3,
        }
        good = {"tracker": {"token": "used", "tokenExpiry": "2026-11-07"}}
        self.assertEqual(
            one(part, FakeGitHub(files={meta: good}))["state"], check.GREEN
        )
        refused = {"tracker": {"token": "refused"}}
        self.assertEqual(
            one(part, FakeGitHub(files={meta: refused}))["state"], check.RED
        )
        failed = {
            "tracker": {
                "token": "used",
                "tokenExpiry": "2026-11-07",
                "tokenRenewal": "failed",
            }
        }
        row = one(part, FakeGitHub(files={meta: failed}))
        self.assertEqual(row["state"], check.RED)
        self.assertIn("couldn't be renewed", row["parts"][0]["text"])


class Rows(unittest.TestCase):
    def test_well_formed(self):
        ids = [r["id"] for r in checks.ROWS]
        self.assertEqual(len(ids), len(set(ids)))
        kinds = {"run", "data", "note", "ci", "started", "expiry", "problems", "source"}
        for row in checks.ROWS:
            self.assertIn(row["group"], checks.GROUPS)
            for part in row["parts"]:
                self.assertIn(part["kind"], kinds)
                if (
                    "green" in part
                    and part.get("red") is not None
                    and part["kind"] != "expiry"
                ):
                    self.assertLess(part["green"], part["red"])

    def test_check_all(self):
        # Nothing readable: every row unknown, and still written.
        status = check.check(FakeGitHub(), NOW)
        self.assertEqual(status["format"], 1)
        self.assertEqual(len(status["rows"]), len(checks.ROWS))
        self.assertEqual(status["checkedAt"], NOW.isoformat())

    def test_text_of(self):
        part = {"text": "last run {ago}, success", "at": at(0.5)}
        self.assertEqual(check.text_of(part, NOW), "last run 30 min ago, success")
