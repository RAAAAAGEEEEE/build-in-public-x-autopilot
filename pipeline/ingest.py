"""Turn a folder of exported AI conversations into a bounded corpus.

This stage uses no LLM at all. That is the point: every token you spend on a
model is a token you paid for, so the cheap deterministic work -- picking the
right day, dropping noise, trimming to what matters -- happens here first.

Two numbers justify the trimming. Measured on one real month of exports:
a busy day totalled ~280,000 tokens across ten conversations, and a single
conversation reached ~481,000 tokens. Feeding that raw would blow past both
the context window and the per-minute token cap of every free tier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

# Exports whose name carries the date. Add your own pattern here if your
# tool names files differently; the date is what matters.
FILENAME_DATE_PATTERNS = (
    re.compile(r"(\d{4}-\d{2}-\d{2})"),   # claude-conversation-2026-07-29-<id>.md
    re.compile(r"(\d{4})(\d{2})(\d{2})"),  # Export_20260729_title.md
)

# Many exporters put the session start time in the first few lines. It is the
# only timestamp available in most formats -- there is usually none per
# message -- but it is enough to order a day's sessions.
HEADER_TIME_RE = re.compile(
    r"^\s*(?:Date|Started|Timestamp)\s*[:=]\s*"
    r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class Conversation:
    path: Path
    day: date
    started_at: str | None
    text: str

    @property
    def name(self) -> str:
        return self.path.name


@dataclass
class Corpus:
    """What actually goes to the model, plus why it looks like that."""

    text: str
    kept: list[str]
    dropped: list[tuple[str, str]]
    trimmed: list[str]
    total_chars: int

    def summary(self) -> str:
        lines = [f"corpus: {self.total_chars} chars from {len(self.kept)} conversation(s)"]
        for name, why in self.dropped:
            lines.append(f"  dropped {name}: {why}")
        for name in self.trimmed:
            lines.append(f"  trimmed {name} to its tail")
        return "\n".join(lines)


def _day_from_name(name: str) -> date | None:
    for pattern in FILENAME_DATE_PATTERNS:
        match = pattern.search(name)
        if not match:
            continue
        try:
            if len(match.groups()) == 3:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            return date.fromisoformat(match.group(1))
        except ValueError:
            continue
    return None


def load_day(folder: Path, day: date, *, glob: str = "*.md") -> list[Conversation]:
    """Every conversation exported for `day`, oldest session first.

    Ordering uses the session start time from the file header when present and
    falls back to the filename. It deliberately does NOT use the file's
    modification time: exporters rewrite every file in one pass, so all mtimes
    collapse to the moment of export and say nothing about when you worked.
    """
    found: list[Conversation] = []
    for path in sorted(folder.glob(glob)):
        if _day_from_name(path.name) != day:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        match = HEADER_TIME_RE.search(text[:2000])
        found.append(Conversation(path=path, day=day,
                                  started_at=match.group(1) if match else None,
                                  text=text))
    found.sort(key=lambda c: (c.started_at or "", c.name))
    return found


def build_corpus(conversations: list[Conversation], *,
                 min_chars: int = 6_000,
                 tail_chars: int = 14_000,
                 max_total_chars: int = 40_000) -> Corpus:
    """Filter and trim, deterministically.

    min_chars   -- below this a conversation is noise: a quick question, an
                   aborted attempt. It has nothing worth writing about.
    tail_chars  -- keep the END of each conversation. Conclusions, decisions
                   and final state live there; the opening is usually
                   exploration that went nowhere.
    max_total   -- hard ceiling on what reaches the model. The largest
                   conversations are kept first, then the budget closes.
    """
    kept: list[tuple[str, str]] = []
    dropped: list[tuple[str, str]] = []
    trimmed: list[str] = []

    for conversation in conversations:
        text = conversation.text
        if len(text) < min_chars:
            dropped.append((conversation.name, f"too short ({len(text)} chars)"))
            continue
        if len(text) > tail_chars:
            text = text[-tail_chars:]
            trimmed.append(conversation.name)
        kept.append((conversation.name, text))

    kept.sort(key=lambda item: len(item[1]), reverse=True)

    parts: list[str] = []
    total = 0
    used: list[str] = []
    for name, text in kept:
        if total + len(text) > max_total_chars:
            dropped.append((name, "total budget reached"))
            continue
        parts.append(f"--- conversation: {name} ---\n{text}")
        total += len(text)
        used.append(name)

    return Corpus(text="\n\n".join(parts), kept=used, dropped=dropped,
                  trimmed=trimmed, total_chars=total)


def build_index(conversations: list[Conversation], *,
                head_chars: int = 2_000) -> str:
    """A cheap catalogue of the day: each conversation's opening only.

    Used to let a judge pick the subject before the writer reads anything.
    Judging on 2,000 characters per conversation instead of the full corpus
    cuts the tokens spent on selection by roughly 80%, and the writer then
    only reads the winner.
    """
    parts = []
    for conversation in conversations:
        opening = conversation.text[:head_chars].strip()
        started = conversation.started_at or "unknown time"
        parts.append(f"--- {conversation.name} (started {started}) ---\n{opening}")
    return "\n\n".join(parts)
