"""Deliver a draft for human review, and shout when the pipeline breaks.

There is deliberately no code here that publishes to X. A generated post goes
to you first, and you decide. Automated publishing is the one failure mode you
cannot take back, and the cost of being wrong is public.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class Delivery:
    """Base: implement send() and you can plug in any channel."""

    def send(self, text: str) -> str | None:
        raise NotImplementedError


class Stdout(Delivery):
    """Default. Works with no credentials, pipes into anything."""

    def send(self, text: str) -> str | None:
        print(text)
        return None


class Telegram(Delivery):
    """A private channel is a good inbox: it reaches your phone, keeps a
    history, and nothing is public until you copy it out yourself."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, text: str) -> str | None:
        payload = json.dumps({"chat_id": self.chat_id, "text": text}).encode("utf-8")
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data=payload, headers={"Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read())
        return str((data.get("result") or {}).get("message_id") or "")


def alert(channel: Delivery, subject: str, detail: str) -> None:
    """Report a failure through the same channel as the drafts.

    An unattended pipeline that fails silently into a log file is a pipeline
    you stop trusting: you cannot tell "nothing happened today" from "it has
    been broken for a week". Every abort path should end up here.
    """
    body = f"[pipeline failed] {subject}\n\n{detail}"
    try:
        channel.send(body[:3500])
    except Exception as exc:  # noqa: BLE001 - never let alerting mask the error
        print(f"could not deliver the alert ({type(exc).__name__}: {exc}):\n{body}")
