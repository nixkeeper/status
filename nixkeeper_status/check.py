"""Each row's state, from its parts (checks.py): on time (green), late
(yellow), an issue (red), or unknown (grey: GitHub or a file couldn't be
read, which says nothing of the thing itself).

A part's text says what was found, with "{ago}" where its time goes: the
page writes it as it's read ("38 min ago"), an issue as it's opened."""

from datetime import UTC, date, datetime

from . import checks
from .github import Unavailable

GREEN, YELLOW, RED, UNKNOWN = "green", "yellow", "red", "unknown"
# Worst last; a note's None counts for nothing.
ORDER = {None: -1, GREEN: 0, UNKNOWN: 1, YELLOW: 2, RED: 3}
FAILED = {"failure", "timed_out", "startup_failure"}
# Neither passed nor failed: a newer run took its place, or it had nothing
# to do.
NEUTRAL = {"cancelled", "skipped", "neutral", "stale"}


def worst(states):
    return max(states, key=ORDER.__getitem__, default=None)


def parse_time(text):
    found = datetime.fromisoformat(text)
    return found if found.tzinfo else found.replace(tzinfo=UTC)


def hours_since(at, now):
    return (now - at).total_seconds() / 3600


def by_age(hours, green, red):
    if hours <= green:
        return GREEN
    if red is None or hours <= red:
        return YELLOW
    return RED


def ago(at, now):
    """ "38 min ago", "2.5 h ago", "3 days ago"."""
    minutes = max(0, (now - at).total_seconds() / 60)
    if minutes < 90:
        return f"{minutes:.0f} min ago"
    if minutes < 48 * 60:
        return f"{minutes / 60:.1f} h ago"
    return f"{minutes / 1440:.0f} days ago"


def expected(hours):
    if hours < 48:
        return f"{hours:g} h"
    return f"{hours / 24:g} days"


def field(data, path):
    """A dotted path's value in a JSON object ("tracker.readAt"), or None."""
    for key in path.split("."):
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _part(what, state, text, at=None, link=None):
    found = {"what": what, "state": state, "text": text}
    if at:
        found["at"] = at.isoformat()
    if link:
        found["link"] = link
    return found


def _run(part, gh, now):
    runs = gh.runs(part["repo"], part["workflow"])
    if not runs:
        return _part("runs", UNKNOWN, "no runs yet")
    newest = runs[0]
    at = parse_time(newest["created_at"])
    state = by_age(hours_since(at, now), part["green"], part["red"])
    if newest["status"] != "completed":
        text = f"last run started {{ago}}, {newest['status'].replace('_', ' ')}"
    else:
        text = f"last run {{ago}}: {newest['conclusion']}"
    if state != GREEN:
        text = f"last run {{ago}}, but one is expected within {expected(part['green'])}"
    # The results of the last runs that passed or failed, newest first.
    done = [
        r for r in runs if r["status"] == "completed" and r["conclusion"] not in NEUTRAL
    ]
    failed = 0
    for r in done:
        if r["conclusion"] not in FAILED:
            break
        failed += 1
    link = newest["html_url"]
    if failed:
        state = worst([state, RED if failed >= 2 else YELLOW])
        link = done[0]["html_url"]
        text += (
            f"; the last {failed} runs failed"
            if failed >= 2
            else "; the last run failed"
        )
    return _part("runs", state, text, at, link)


def _read(gh, cache, url):
    if url not in cache:
        try:
            cache[url] = gh.get(url)
        except Unavailable as e:
            cache[url] = e
    if isinstance(cache[url], Unavailable):
        raise cache[url]
    return cache[url]


def _data(part, gh, now, cache):
    what = part["what"]
    value = field(_read(gh, cache, part["url"]), part["field"])
    if not value:
        return _part(what, YELLOW, f"{what}: no {part['field']} in its meta.json")
    at = parse_time(value)
    state = by_age(hours_since(at, now), part["green"], part["red"])
    late = f", but it's expected within {expected(part['green'])}"
    text = f"{what} from {{ago}}" + (late if state != GREEN else "")
    return _part(what, state, text, at)


def _note(part, gh, cache):
    n = field(_read(gh, cache, part["url"]), part["field"])
    if not n:
        return None
    return _part("note", None, part["text"].format(n=f"{n:,}"))


def _source(part, gh, cache):
    """A note on what nixkeeper's last sync read from a source (index.json's
    "sources"): None when it doesn't name the source, or index.json can't be
    read (the sync's own row says so; a note never turns a digest's row grey)."""
    try:
        index = _read(gh, cache, checks.DASHBOARD + "index.json")
    except Unavailable:
        return None
    found = (index.get("sources") or {}).get(part["key"])
    if not found:
        return None
    label = part["label"]
    if not found.get("used"):
        return _part(
            "source", None, f"{label}: not used, {found.get('why') or 'unknown'}"
        )
    try:
        said = part["say"](found)
    except (KeyError, TypeError):
        said = "read"
    at = parse_time(found["at"]) if found.get("at") else None
    return _part(
        "source", None, f"{label}: {said}" + (", as of {ago}" if at else ""), at
    )


# How many of a part's problems its text names; the rest are counted.
PROBLEMS_SHOWN = 3


def _problems(part, gh, cache):
    found = field(_read(gh, cache, part["url"]), part["field"]) or []
    what = part["what"]
    if not found:
        return _part(what, GREEN, f"{what}: no problems")
    named = "; ".join(found[:PROBLEMS_SHOWN])
    more = len(found) - PROBLEMS_SHOWN
    n = f"{len(found)} problem{'s' if len(found) > 1 else ''}"
    text = f"{what}: {n}, {named}" + (f"; and {more} more" if more > 0 else "")
    return _part(what, RED, text)


def _ci(part, gh):
    runs = gh.runs(part["repo"], part["workflow"], branch="main", event="push")
    done = [
        r for r in runs if r["status"] == "completed" and r["conclusion"] not in NEUTRAL
    ]
    if not done:
        return _part("tests", UNKNOWN, "no tests on main yet")
    newest = done[0]
    at = parse_time(newest["created_at"])
    if newest["conclusion"] in FAILED:
        return _part(
            "tests", RED, "failing on main, since {ago}", at, newest["html_url"]
        )
    return _part(
        "tests", GREEN, f"{newest['conclusion']} {{ago}}", at, newest["html_url"]
    )


def _started(part, gh, now):
    """The newest run started through the API (workflow_dispatch) of the
    workflows start-runs starts: by hand counts too, but that's rare."""
    newest = None
    for repo, workflow in part["workflows"]:
        for r in gh.runs(repo, workflow):
            if r["event"] == "workflow_dispatch":
                at = parse_time(r["created_at"])
                if not newest or at > newest[0]:
                    newest = (at, repo.split("/")[-1])
                break
    if not newest:
        return _part("starts", RED, "no run started through the API lately")
    at, repo = newest
    state = by_age(hours_since(at, now), part["green"], part["red"])
    late = "; GitHub's own schedules run instead" if state != GREEN else ""
    return _part("starts", state, f"last start {{ago}} ({repo}){late}", at)


def _expiry(part, gh, now, cache):
    meta = None
    if "date" in part:
        day = part["date"]
    else:
        meta = _read(gh, cache, part["url"])
        day = field(meta, part["field"])
    if part.get("state") == "tracker":
        tracker = (meta or {}).get("tracker") or {}
        if tracker.get("token") == "refused":
            return _part(
                "expiry",
                RED,
                "refused: expired, revoked or replaced; the digest "
                "goes on at the tracker's slower pace without it",
            )
        if tracker.get("tokenRenewal") == "failed":
            return _part("expiry", RED, f"couldn't be renewed: it expires on {day}")
        if not tracker.get("token"):
            return _part(
                "expiry", YELLOW, "not set: the digest reads the tracker slowly"
            )
    if not day:
        return _part("expiry", UNKNOWN, "expiry unknown")
    left = (date.fromisoformat(day) - now.date()).days
    if left > part["green"]:
        state = GREEN
    elif left > part["red"]:
        state = YELLOW
    else:
        state = RED
    text = f"expires on {day}, in {left} days" if left >= 0 else f"expired on {day}"
    return _part("expiry", state, text)


def check_row(row, gh, now, cache):
    parts = []
    for part in row["parts"]:
        kind = part["kind"]
        try:
            if kind == "run":
                found = _run(part, gh, now)
            elif kind == "data":
                found = _data(part, gh, now, cache)
            elif kind == "note":
                found = _note(part, gh, cache)
            elif kind == "problems":
                found = _problems(part, gh, cache)
            elif kind == "source":
                found = _source(part, gh, cache)
            elif kind == "ci":
                found = _ci(part, gh)
            elif kind == "started":
                found = _started(part, gh, now)
            elif kind == "expiry":
                found = _expiry(part, gh, now, cache)
            else:
                raise ValueError(f"no such kind of part: {kind}")
        except Unavailable as e:
            found = _part(kind, UNKNOWN, f"couldn't be read ({e})")
        if found:
            parts.append(found)
    return {
        "id": row["id"],
        "group": row["group"],
        "name": row["name"],
        "every": row["every"],
        "link": row["link"],
        "state": worst(p["state"] for p in parts) or UNKNOWN,
        "parts": parts,
    }


def check(gh, now=None, rows=None):
    """Every row, checked: status.json's content."""
    now = now or datetime.now(UTC)
    cache = {}
    found = [check_row(row, gh, now, cache) for row in rows or checks.ROWS]
    return {
        "format": 1,
        "checkedAt": now.isoformat(),
        "state": worst(r["state"] for r in found) or UNKNOWN,
        "groups": checks.GROUPS,
        "rows": found,
    }


def text_of(part, now):
    """A part's text with its time written in."""
    at = part.get("at")
    return part["text"].replace("{ago}", ago(parse_time(at), now) if at else "")
