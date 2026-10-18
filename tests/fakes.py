"""A GitHub of the tests' making."""

from datetime import UTC, datetime, timedelta

from nixkeeper_status.github import Unavailable

NOW = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)


def at(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")


def run(hours_ago, conclusion="success", status="completed", event="schedule", n=1):
    return {
        "created_at": at(hours_ago),
        "status": status,
        "conclusion": conclusion if status == "completed" else None,
        "event": event,
        "html_url": f"https://github.com/runs/{n}",
    }


class FakeGitHub:
    def __init__(self, runs=None, files=None, issues=None):
        self.runs_by = runs or {}  # (repo, workflow): [runs, newest first]
        self.files = files or {}  # url: JSON, or an Unavailable
        self.issues = issues or []
        self.done = []

    def runs(self, repo, workflow, branch=None, event=None):
        found = self.runs_by.get((repo, workflow))
        if isinstance(found, Unavailable):
            raise found
        found = found or []
        if event:
            found = [r for r in found if r["event"] == event]
        return found

    def get(self, url):
        found = self.files.get(url)
        if found is None:
            raise Unavailable("raw.githubusercontent.com: 404", 404)
        if isinstance(found, Unavailable):
            raise found
        return found

    def open_issues(self, repo, label):
        return self.issues

    def ensure_label(self, repo, name, color, description):
        self.done.append(("label", name))

    def create_issue(self, repo, title, body, labels):
        self.done.append(("create", title, body, labels))

    def comment(self, repo, number, body):
        self.done.append(("comment", number, body))

    def close(self, repo, number):
        self.done.append(("close", number))
