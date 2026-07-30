"""Deliver a draft for human review, and shout when the pipeline breaks.

There is deliberately no code here that publishes to X. A generated post goes
to you first, and you decide. Automated publishing is the one failure mode you
cannot take back, and the cost of being wrong is public.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


# X's own composer, pre-filled. It accepts TEXT ONLY -- no image can be
# attached this way, and that restriction is deliberate on their side: a third
# party page must not be able to attach a file to a message you are about to
# publish. The picture stays a manual gesture.
INTENT_URL = "https://x.com/intent/post?text="

# Telegram caption limit. Past it the API rejects the whole message, so the
# post is sent as its own message instead of being silently truncated.
CAPTION_MAX = 1024
# A button carries a URL, not unlimited text. A very long post would exceed
# what Telegram accepts and the entire message would be refused.
BUTTON_URL_MAX = 1900


def compose_url(text: str) -> str:
    return INTENT_URL + urllib.parse.quote(text, safe="")


class Delivery:
    """Base: implement send() and you can plug in any channel."""

    def send(self, text: str, *, image: str | None = None,
             compose_link: bool = False) -> str | None:
        raise NotImplementedError


class Stdout(Delivery):
    """Default. Works with no credentials, pipes into anything."""

    def send(self, text: str, *, image: str | None = None,
             compose_link: bool = False) -> str | None:
        print(text)
        if image:
            print(f"[image: {image}]")
        if compose_link:
            print(f"[compose: {compose_url(text)}]")
        return None


class Telegram(Delivery):
    """A private channel is a good inbox: it reaches your phone, keeps a
    history, and nothing is public until you copy it out yourself."""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id

    def send(self, text: str, *, image: str | None = None,
             compose_link: bool = False) -> str | None:
        """Send the draft, optionally as the caption of an image, optionally
        with a button that opens X's composer already filled in.

        The button lives OUTSIDE the message text on purpose. A link written
        into the caption gets copied along with the post and ends up published.
        The same mistake, in the same week, put a message heading inside an
        image-generation prompt and the model drew the heading into the picture.
        Anything a human will copy wholesale must contain nothing but what they
        meant to copy.
        """
        markup = None
        if compose_link:
            url = compose_url(text)
            if len(url) <= BUTTON_URL_MAX:
                markup = {"inline_keyboard": [[{"text": "Open in X", "url": url}]]}

        if image and len(text) <= CAPTION_MAX:
            return self._photo(image, caption=text, markup=markup)
        if image:
            self._photo(image, caption="", markup=None)
        return self._message(text, markup)

    def _api(self, method: str, payload: dict) -> dict:
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.bot_token}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read())

    def _message(self, text: str, markup: dict | None) -> str | None:
        payload = {"chat_id": self.chat_id, "text": text}
        if markup:
            payload["reply_markup"] = markup
        data = self._api("sendMessage", payload)
        return str((data.get("result") or {}).get("message_id") or "")

    def _photo(self, image: str, caption: str, markup: dict | None) -> str | None:
        """multipart/form-data by hand: this project has no dependencies, and a
        correct multipart body is fifteen lines."""
        import uuid
        from pathlib import Path

        boundary = "----bip" + uuid.uuid4().hex
        fields = {"chat_id": self.chat_id}
        if caption:
            fields["caption"] = caption
        if markup:
            fields["reply_markup"] = json.dumps(markup)

        body = bytearray()
        for name, value in fields.items():
            body += (f"--{boundary}\r\n"
                     f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                     f"{value}\r\n").encode("utf-8")
        path = Path(image)
        body += (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="photo"; '
                 f'filename="{path.name}"\r\n'
                 f"Content-Type: application/octet-stream\r\n\r\n").encode("utf-8")
        body += path.read_bytes()
        body += f"\r\n--{boundary}--\r\n".encode("utf-8")

        request = urllib.request.Request(
            f"https://api.telegram.org/bot{self.bot_token}/sendPhoto",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST")
        with urllib.request.urlopen(request, timeout=120) as response:
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
