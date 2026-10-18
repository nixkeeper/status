import json
import os
import tempfile
import unittest
from unittest import mock

from nixkeeper_status import check, cli, issues

from .fakes import NOW, FakeGitHub, at


def row(id_, state, text="last run {ago}: success"):
    return {
        "id": id_,
        "group": "runs",
        "name": id_,
        "every": "every hour",
        "link": f"https://github.com/{id_}",
        "state": state,
        "parts": [{"what": "runs", "state": state, "text": text, "at": at(5)}],
    }


def status(*rows):
    return {"rows": list(rows)}


def issue(number, id_):
    return {"number": number, "body": f"{issues.MARKER.format(id_)}\nsomething"}


class Plan(unittest.TestCase):
    def test_opens_once(self):
        found = issues.plan(status(row("a", check.RED), row("b", check.GREEN)), [])
        self.assertEqual([(a[0], a[1]["id"]) for a in found], [("open", "a")])
        self.assertEqual(issues.plan(status(row("a", check.RED)), [issue(7, "a")]), [])

    def test_closes_when_on_time(self):
        found = issues.plan(status(row("a", check.GREEN)), [issue(7, "a")])
        self.assertEqual([(a[0], a[2]["number"]) for a in found], [("close", 7)])

    def test_late_keeps_it_open(self):
        self.assertEqual(
            issues.plan(status(row("a", check.YELLOW)), [issue(7, "a")]), []
        )
        self.assertEqual(
            issues.plan(status(row("a", check.UNKNOWN)), [issue(7, "a")]), []
        )

    def test_github_down(self):
        rows = [row("a", check.RED), row("b", check.UNKNOWN), row("c", check.UNKNOWN)]
        self.assertEqual(issues.plan(status(*rows), []), [])

    def test_other_issues_left_alone(self):
        others = [{"number": 3, "body": "a person's"}, issue(4, "gone")]
        self.assertEqual(issues.plan(status(row("a", check.GREEN)), others), [])


class Apply(unittest.TestCase):
    def test_open_and_close(self):
        red = row("a", check.RED, "last run {ago}, but one is expected within 2 h")
        gh = FakeGitHub(issues=[issue(7, "b")])
        issues.apply(
            gh,
            "nixkeeper/status",
            status(red, row("b", check.GREEN)),
            NOW,
            "https://run",
            log=lambda _: None,
        )
        kinds = [d[0] for d in gh.done]
        self.assertEqual(kinds, ["label", "create", "comment", "close"])
        _, title, body, labels = gh.done[1]
        self.assertEqual(title, "a: last run 5.0 h ago, but one is expected within 2 h")
        self.assertIn(issues.MARKER.format("a"), body)
        self.assertIn("[this check](https://run)", body)
        self.assertEqual(labels, ["status"])
        self.assertEqual(issues.row_of({"body": body}), "a")
        self.assertIn("On time again", gh.done[2][2])

    def test_dry_run(self):
        gh = FakeGitHub()
        said = []
        found = issues.apply(
            gh, "r", status(row("a", check.RED)), NOW, dry_run=True, log=said.append
        )
        self.assertEqual(len(found), 1)
        self.assertEqual(gh.done, [])
        self.assertTrue(said[0].startswith("opening an issue: a:"))


class Cli(unittest.TestCase):
    def test_writes_status(self):
        with (
            tempfile.TemporaryDirectory() as out,
            mock.patch.dict(
                os.environ,
                {
                    "GITHUB_SERVER_URL": "https://github.com",
                    "GITHUB_REPOSITORY": "nixkeeper/status",
                    "GITHUB_RUN_ID": "9",
                },
            ),
            mock.patch("builtins.print"),
        ):
            gh = FakeGitHub()
            self.assertEqual(
                cli.main(["check", "--out", out, "--issues"], gh=gh, now=NOW), 0
            )
            with open(os.path.join(out, "status.json")) as f:
                written = json.load(f)
        self.assertEqual(
            written["run"], "https://github.com/nixkeeper/status/actions/runs/9"
        )
        self.assertEqual(written["checkedAt"], NOW.isoformat())
        # Nothing readable: no issue opened.
        self.assertEqual(gh.done, [])
