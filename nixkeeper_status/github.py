"""Asking GitHub (its API, and raw files): the runs of each workflow, and
this repository's issues. All the repositories are public: the workflow's
own token (GITHUB_TOKEN) reads them, and writes only this repository's
issues."""

import json
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.github.com"
USER_AGENT = "nixkeeper-status (+https://github.com/nixkeeper/status)"
TIMEOUT = 30
# Runs asked of each workflow: enough to find the last completed ones past a
# few cancelled or still running.
RUNS = 20


class Unavailable(Exception):
    """GitHub (or a file on it) couldn't be read; code: the HTTP status,
    when it answered."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class GitHub:
    def __init__(self, token=None, opener=urllib.request.urlopen):
        self.token = token
        self.opener = opener
        self._runs = {}
        self._jobs = {}

    def _request(self, method, url, body=None):
        headers = {"User-Agent": USER_AGENT}
        if url.startswith(API):
            headers["Accept"] = "application/vnd.github+json"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        # Said by host only (api.github.com: 502): the page shows it.
        host = urllib.parse.urlsplit(url).netloc
        try:
            with self.opener(req, timeout=TIMEOUT) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise Unavailable(f"{host}: {e.code}", e.code) from e
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise Unavailable(f"{host}: {getattr(e, 'reason', e)}") from e
        try:
            return json.loads(raw) if raw else None
        except ValueError as e:
            raise Unavailable(f"{host}: not JSON") from e

    def get(self, url):
        return self._request("GET", url)

    def runs(self, repo, workflow, branch=None, event=None):
        """A workflow's newest runs, newest first (each asked once a check)."""
        key = (repo, workflow, branch, event)
        if key not in self._runs:
            query = {"per_page": RUNS}
            if branch:
                query["branch"] = branch
            if event:
                query["event"] = event
            url = (
                f"{API}/repos/{repo}/actions/workflows/{workflow}/runs?"
                + urllib.parse.urlencode(query)
            )
            self._runs[key] = self.get(url)["workflow_runs"]
        return self._runs[key]

    def jobs(self, repo, run_id):
        """A run's jobs (each asked once a check)."""
        if (repo, run_id) not in self._jobs:
            url = f"{API}/repos/{repo}/actions/runs/{run_id}/jobs"
            self._jobs[(repo, run_id)] = self.get(url)["jobs"]
        return self._jobs[(repo, run_id)]

    # This repository's issues.

    def open_issues(self, repo, label):
        url = f"{API}/repos/{repo}/issues?" + urllib.parse.urlencode(
            {"state": "open", "labels": label, "per_page": 100}
        )
        return [i for i in self.get(url) if "pull_request" not in i]

    def ensure_label(self, repo, name, color, description):
        try:
            self.get(f"{API}/repos/{repo}/labels/{urllib.parse.quote(name)}")
        except Unavailable as e:
            if e.code != 404:
                raise
            self._request(
                "POST",
                f"{API}/repos/{repo}/labels",
                {"name": name, "color": color, "description": description},
            )

    def create_issue(self, repo, title, body, labels):
        return self._request(
            "POST",
            f"{API}/repos/{repo}/issues",
            {"title": title, "body": body, "labels": labels},
        )

    def comment(self, repo, number, body):
        self._request(
            "POST", f"{API}/repos/{repo}/issues/{number}/comments", {"body": body}
        )

    def close(self, repo, number):
        self._request(
            "PATCH",
            f"{API}/repos/{repo}/issues/{number}",
            {"state": "closed", "state_reason": "completed"},
        )
