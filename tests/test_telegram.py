import io
import json
import unittest
import urllib.error
from contextlib import redirect_stdout

from nixkeeper_status import issues, telegram
from nixkeeper_status.check import GREEN, RED

from .fakes import NOW, FakeGitHub, at


class Opener:
    def __init__(self, answer):
        self.answer = answer
        self.asked = []

    def __call__(self, req, timeout):
        self.asked.append(req)
        if isinstance(self.answer, int):
            body = io.BytesIO(
                b'{"ok": false, "description": "Bad Request: chat not found"}'
            )
            raise urllib.error.HTTPError(req.full_url, self.answer, "no", {}, body)
        return io.BytesIO(json.dumps(self.answer).encode())


class Bot:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return True


def row(state):
    return {
        "id": "digest-prs",
        "group": "runs",
        "name": "digest-prs",
        "every": "every hour",
        "link": "https://github.com/x",
        "state": state,
        "parts": [
            {
                "what": "runs",
                "state": state,
                "text": "last run {ago}, but one is expected within 2 h",
                "at": at(5),
            }
        ],
    }


class Sending(unittest.TestCase):
    def test_from_env(self):
        self.assertIsNone(telegram.Telegram.from_env({}))
        self.assertIsNone(telegram.Telegram.from_env({"TELEGRAM_BOT_TOKEN": "t"}))
        bot = telegram.Telegram.from_env(
            {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "42"}
        )
        self.assertEqual((bot.token, bot.chat), ("t", "42"))

    def test_send(self):
        opener = Opener({"ok": True})
        self.assertTrue(telegram.Telegram("secret", "42", opener).send("<b>hi</b>"))
        req = opener.asked[0]
        self.assertEqual(req.full_url, "https://api.telegram.org/botsecret/sendMessage")
        body = json.loads(req.data)
        self.assertEqual(body["chat_id"], "42")
        self.assertEqual(body["parse_mode"], "HTML")
        self.assertTrue(body["link_preview_options"]["is_disabled"])

    def test_refused_without_the_token(self):
        out = io.StringIO()
        with redirect_stdout(out):
            sent = telegram.Telegram("secret", "42", Opener(400)).send("hi")
        self.assertFalse(sent)
        self.assertIn("chat not found", out.getvalue())
        self.assertNotIn("secret", out.getvalue())


class Messages(unittest.TestCase):
    def test_opened(self):
        text = telegram.opened(
            row(RED),
            "digest-prs: last run 5.0 h ago, but <one> is expected within 2 h",
            "https://github.com/nixkeeper/status/issues/12",
            "https://status.nixkeeper.com/",
        )
        self.assertTrue(
            text.startswith("\N{LARGE RED CIRCLE} <b>digest-prs</b>: last run")
        )
        self.assertIn("&lt;one&gt;", text)
        self.assertIn(
            '<a href="https://github.com/nixkeeper/status/issues/12">the issue</a>',
            text,
        )

    def test_closed_and_failed(self):
        self.assertIn("is on time again", telegram.closed(row(GREEN), "https://i"))
        self.assertIn(
            '<a href="https://run">the run</a>', telegram.check_failed("https://run")
        )


class WithIssues(unittest.TestCase):
    def test_told_of_each(self):
        bot = Bot()
        gh = FakeGitHub(
            issues=[
                {
                    "number": 7,
                    "html_url": "https://github.com/nixkeeper/status/issues/7",
                    "body": issues.MARKER.format("other"),
                }
            ]
        )
        green = dict(row(GREEN), id="other", name="other")
        status = {"rows": [row(RED), green]}
        issues.apply(
            gh, "nixkeeper/status", status, NOW, log=lambda _: None, telegram=bot
        )
        self.assertEqual(len(bot.sent), 2)
        self.assertIn("issues/12", bot.sent[0])
        self.assertIn("issues/7", bot.sent[1])

    def test_dry_run_sends_nothing(self):
        bot = Bot()
        issues.apply(
            FakeGitHub(),
            "r",
            {"rows": [row(RED)]},
            NOW,
            dry_run=True,
            log=lambda _: None,
            telegram=bot,
        )
        self.assertEqual(bot.sent, [])
