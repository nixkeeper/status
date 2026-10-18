"""Telegram messages, beside the issues: one when an issue opens (a row
turned red), one when it closes (on time again), and one when the check
itself fails. From a bot (its token in TELEGRAM_BOT_TOKEN) to one chat
(TELEGRAM_CHAT_ID: a person's chat with the bot, or a group's); without
both, nothing is sent.

A message that can't be sent is said in the log, never fails the check:
the issue is what counts, the message only tells of it."""

import html
import json
import os
import urllib.error
import urllib.request

API = "https://api.telegram.org"
TIMEOUT = 30

OPENED = "\N{LARGE RED CIRCLE}"
CLOSED = "\N{WHITE HEAVY CHECK MARK}"
FAILED = "\N{WARNING SIGN}\N{VARIATION SELECTOR-16}"


class Telegram:
    def __init__(self, token, chat, opener=urllib.request.urlopen):
        self.token = token
        self.chat = chat
        self.opener = opener

    @classmethod
    def from_env(cls, env=None):
        """The bot from TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or None."""
        env = os.environ if env is None else env
        token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
        return cls(token, chat) if token and chat else None

    def send(self, text):
        """Sends text (Telegram's HTML); True if Telegram took it."""
        body = json.dumps(
            {
                "chat_id": self.chat,
                "text": text,
                "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": True},
            }
        ).encode()
        req = urllib.request.Request(
            f"{API}/bot{self.token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.opener(req, timeout=TIMEOUT) as resp:
                ok = json.loads(resp.read()).get("ok")
        except urllib.error.HTTPError as e:
            # Telegram says why (a wrong chat, a bot not started): never the
            # URL, which holds the token.
            try:
                why = json.loads(e.read()).get("description")
            except (ValueError, OSError):
                why = None
            print(f"::warning::Telegram: {e.code} {why or ''}".rstrip())
            return False
        except (urllib.error.URLError, OSError, ValueError) as e:
            print(f"::warning::Telegram: {getattr(e, 'reason', type(e).__name__)}")
            return False
        if not ok:
            print("::warning::Telegram didn't take the message")
        return bool(ok)


def _link(url, text):
    return f'<a href="{html.escape(url)}">{html.escape(text)}</a>'


def opened(row, title, issue_url=None, page=None):
    """A row turned red: what's wrong (the issue's title), and links."""
    name = html.escape(row["name"])
    what = html.escape(
        title[len(row["name"]) + 2 :] if title.startswith(row["name"] + ": ") else title
    )
    links = [
        link
        for link in (
            issue_url and _link(issue_url, "the issue"),
            page and _link(page, "status page"),
        )
        if link
    ]
    text = f"{OPENED} <b>{name}</b>: {what}"
    return text + ("\n" + " · ".join(links) if links else "")


def closed(row, issue_url=None):
    text = f"{CLOSED} <b>{html.escape(row['name'])}</b> is on time again"
    return text + (f" ({_link(issue_url, 'the issue')})" if issue_url else "")


def check_failed(run_url=None):
    text = (
        f"{FAILED} <b>The status check failed</b>: its results and issues may "
        "be out of date"
    )
    return text + (f"\n{_link(run_url, 'the run')}" if run_url else "")
