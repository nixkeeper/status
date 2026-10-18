import io
import json
import unittest
import urllib.error

from nixkeeper_status.github import GitHub, Unavailable


class Opener:
    """Answers each request from a list, keeping what was asked."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.asked = []

    def __call__(self, req, timeout):
        self.asked.append(req)
        answer = self.answers.pop(0)
        if isinstance(answer, int):
            raise urllib.error.HTTPError(req.full_url, answer, "no", {}, None)
        return io.BytesIO(json.dumps(answer).encode())


class Requests(unittest.TestCase):
    def test_token_only_for_the_api(self):
        opener = Opener({"workflow_runs": []}, {"fetchedAt": "x"})
        gh = GitHub("secret", opener)
        gh.runs("nixkeeper/digest-prs", "digest.yml", branch="main", event="push")
        gh.get(
            "https://raw.githubusercontent.com/nixkeeper/digest-prs/data/data/meta.json"
        )
        api, raw = opener.asked
        self.assertEqual(api.get_header("Authorization"), "Bearer secret")
        self.assertIn("branch=main", api.full_url)
        self.assertIn("event=push", api.full_url)
        self.assertIsNone(raw.get_header("Authorization"))

    def test_runs_asked_once(self):
        opener = Opener({"workflow_runs": [{"n": 1}]})
        gh = GitHub(None, opener)
        gh.runs("a/b", "c.yml")
        self.assertEqual(gh.runs("a/b", "c.yml"), [{"n": 1}])
        self.assertEqual(len(opener.asked), 1)

    def test_errors(self):
        gh = GitHub(None, Opener(502))
        with self.assertRaises(Unavailable) as e:
            gh.get("https://api.github.com/x")
        self.assertEqual(str(e.exception), "api.github.com: 502")
        self.assertEqual(e.exception.code, 502)

    def test_label_made_when_missing(self):
        opener = Opener(404, {})
        GitHub("t", opener).ensure_label("nixkeeper/status", "status", "d73a4a", "d")
        self.assertEqual([r.get_method() for r in opener.asked], ["GET", "POST"])
        opener = Opener({})
        GitHub("t", opener).ensure_label("nixkeeper/status", "status", "d73a4a", "d")
        self.assertEqual(len(opener.asked), 1)

    def test_pull_requests_are_not_issues(self):
        gh = GitHub("t", Opener([{"number": 1}, {"number": 2, "pull_request": {}}]))
        self.assertEqual(gh.open_issues("nixkeeper/status", "status"), [{"number": 1}])
