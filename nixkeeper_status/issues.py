"""The notifications: an issue in this repository for each row that's red,
which GitHub tells its watchers of (the maintainer: by mail and the mobile
app). Opened once when a row turns red, left open while it's late (yellow,
so it doesn't open and close as a row wavers), closed with a comment once
it's on time again (green). Each issue says which row it's for in a hidden
marker, so its title can be anything.

When GitHub couldn't be read for most rows, nothing is opened or closed:
that's GitHub's trouble, not the rows'."""

import re

from .check import GREEN, RED, UNKNOWN, text_of

LABEL = "status"
LABEL_COLOR = "d73a4a"
LABEL_DESCRIPTION = "Opened and closed by the status check"
MARKER = "<!-- nixkeeper-status: {} -->"
MARKER_RE = re.compile(r"<!-- nixkeeper-status: ([\w.-]+) -->")
PAGE = "https://nixkeeper.github.io/status/"


def row_of(issue):
    m = MARKER_RE.search(issue.get("body") or "")
    return m.group(1) if m else None


def _lines(row, now, states):
    return [f"- {text_of(p, now)}" for p in row["parts"] if p["state"] in states]


def title(row, now):
    reds = [text_of(p, now) for p in row["parts"] if p["state"] == RED]
    return f"{row['name']}: {reds[0] if reds else 'needs attention'}"


def body(row, now, run_url=None):
    lines = [
        MARKER.format(row["id"]),
        f"**{row['name']}** ({row['every']}) needs attention:",
        "",
        *_lines(row, now, {RED}),
    ]
    others = _lines(row, now, {"yellow", GREEN, UNKNOWN})
    if others:
        lines += ["", "Also:", "", *others]
    lines += [
        "",
        f"[Its runs]({row['link']}) · [the status page]({PAGE})"
        + (f" · [this check]({run_url})" if run_url else ""),
        "",
        "This issue closes itself once it's on time again.",
    ]
    return "\n".join(lines)


def recovered(row, now, run_url=None):
    lines = [
        "On time again:",
        "",
        *_lines(row, now, {GREEN, "yellow", UNKNOWN}),
    ]
    if run_url:
        lines += ["", f"[This check]({run_url})"]
    return "\n".join(lines)


def plan(status, open_issues):
    """What to do: [("open", row) | ("close", row, issue)]. Issues for rows
    no longer checked are left for a person."""
    rows = status["rows"]
    unknown = sum(r["state"] == UNKNOWN for r in rows)
    if unknown * 2 > len(rows):
        return []
    by_row = {}
    for issue in open_issues:
        found = row_of(issue)
        if found:
            by_row.setdefault(found, issue)
    actions = []
    for row in rows:
        issue = by_row.get(row["id"])
        if row["state"] == RED and not issue:
            actions.append(("open", row))
        elif row["state"] == GREEN and issue:
            actions.append(("close", row, issue))
    return actions


def apply(gh, repo, status, now, run_url=None, dry_run=False, log=print):
    """Opens and closes this repository's issues as plan says."""
    actions = plan(status, gh.open_issues(repo, LABEL))
    if not actions:
        return actions
    if not dry_run:
        gh.ensure_label(repo, LABEL, LABEL_COLOR, LABEL_DESCRIPTION)
    for action in actions:
        row = action[1]
        if action[0] == "open":
            log(f"opening an issue: {title(row, now)}")
            if not dry_run:
                gh.create_issue(repo, title(row, now), body(row, now, run_url), [LABEL])
        else:
            issue = action[2]
            log(f"closing #{issue['number']}: {row['name']} is on time again")
            if not dry_run:
                gh.comment(repo, issue["number"], recovered(row, now, run_url))
                gh.close(repo, issue["number"])
    return actions
