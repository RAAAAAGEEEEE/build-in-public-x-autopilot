#!/usr/bin/env python3
"""Turn yesterday's AI conversations into a post draft, for review.

    python3 run.py --config config.json
    python3 run.py --config config.json --date 2026-07-29 --dry-run

Runs unattended from cron. Every abort path alerts through the delivery
channel, so a broken day is visible instead of silent.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from pipeline import checks, deliver, generate, ingest, providers

DEFAULTS = {
    "conversations_dir": "",
    "timezone": "UTC",
    "publish_previous_day": True,
    "drafts_dir": "drafts",
    "persona": "",
    "language": "English",
    "translate_to": "",
    "translated_opening": "",
    "candidates": 3,
    "keys": {},
    "telegram": {"bot_token": "", "chat_id": ""},
    "rules": {},
}


def log(message: str) -> None:
    print(f"{datetime.now().isoformat(timespec='seconds')} {message}",
          file=sys.stderr)


def load_config(path: Path) -> dict:
    config = dict(DEFAULTS)
    config.update(json.loads(path.read_text(encoding="utf-8")))
    if not config["conversations_dir"]:
        raise SystemExit("config: conversations_dir is required")
    return config


def build_channel(config: dict) -> deliver.Delivery:
    telegram = config.get("telegram") or {}
    if telegram.get("bot_token") and telegram.get("chat_id"):
        return deliver.Telegram(telegram["bot_token"], telegram["chat_id"])
    return deliver.Stdout()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--date", help="the day WORKED, YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the draft, deliver nothing, store nothing")
    parser.add_argument("--no-verify", action="store_true",
                        help="skip the factual verification pass")
    args = parser.parse_args()

    config = load_config(args.config)
    channel = build_channel(config)
    tz = ZoneInfo(config["timezone"])

    if args.date:
        day = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        now = datetime.now(tz)
        day = (now - timedelta(days=1)).date() if config["publish_previous_day"] \
            else now.date()

    rules = checks.Rules(**config.get("rules", {}))
    folder = Path(config["conversations_dir"])
    if not folder.is_dir():
        deliver.alert(channel, "conversations folder not found", str(folder))
        return 1

    conversations = ingest.load_day(folder, day)
    if not conversations:
        # Not an error worth shouting about: some days you simply did not work.
        log(f"no conversations exported for {day}, nothing to do")
        return 0

    corpus = ingest.build_corpus(conversations)
    log(corpus.summary())
    if not corpus.text:
        log(f"every conversation for {day} was filtered out as noise")
        return 0

    keys = config["keys"]

    # Judge on short openings only -- roughly 80% fewer tokens than judging on
    # the full corpus, and the writer then reads only what won.
    index = ingest.build_index(conversations)
    subject = generate.judge_subject(index, keys, log=log)

    try:
        draft = generate.write_post(
            corpus.text, keys, rules,
            subject=subject, persona=config["persona"],
            max_attempts=config["candidates"], log=log)
    except providers.AllProvidersFailed as exc:
        deliver.alert(channel, "no LLM provider answered", str(exc))
        return 2

    if not draft.ok:
        deliver.alert(
            channel,
            f"no draft passed the checks for {day}",
            "Last attempt failed on:\n- " + "\n- ".join(draft.problems)
            + f"\n\nLast text ({len(draft.text)} chars):\n{draft.text}")
        return 3

    if not args.no_verify:
        passed, problems = generate.verify_post(draft.text, corpus.text, keys,
                                                log=log)
        if not passed:
            # Deliver it anyway, flagged. A post with one shaky claim is worth
            # reviewing; silently dropping it teaches you nothing.
            draft = generate.Draft(
                text=draft.text, provider=draft.provider,
                attempts=draft.attempts,
                problems=[f"unverified claim: {p}" for p in problems])

    translated = None
    if config["translate_to"]:
        translated = generate.translate_post(
            draft.text, config["translate_to"], keys, rules,
            opening=config["translated_opening"], log=log)

    header = f"draft for {day}"
    if draft.problems:
        header += "  [REVIEW: " + "; ".join(draft.problems) + "]"

    if args.dry_run:
        print(f"--- {header} ---\n{draft.text}")
        if translated:
            print(f"\n--- {config['translate_to']} ---\n{translated}")
        return 0

    drafts_dir = Path(config["drafts_dir"])
    drafts_dir.mkdir(parents=True, exist_ok=True)
    (drafts_dir / f"{day.isoformat()}.json").write_text(
        json.dumps({"day": day.isoformat(), "post": draft.text,
                    "translated": translated, "provider": draft.provider,
                    "attempts": draft.attempts, "review": draft.problems},
                   ensure_ascii=False, indent=2), encoding="utf-8")

    message_id = channel.send(f"{header}\n\n{draft.text}")
    log(f"delivered {day} (message id {message_id})")
    if translated:
        channel.send(f"{header} [{config['translate_to']}]\n\n{translated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
