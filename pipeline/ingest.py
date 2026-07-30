"""Turn a folder of exported AI conversations into a bounded corpus.

This stage uses no LLM at all. That is the point: every token you spend on a
model is a token you paid for, so the cheap deterministic work -- finding the
new material, dropping noise, trimming to what matters -- happens here first.

Two numbers justify the trimming. Measured on one real month of exports:
a busy day totalled ~280,000 tokens across ten conversations, and a single
conversation reached ~481,000 tokens. Feeding that raw would blow past both
the context window and the per-minute token cap of every free tier.

DO NOT SELECT CONVERSATIONS BY DATE. That was this project's first design and
it was wrong twice over, in ways that produced no error message at all:

1.  A conversation file is named after the session's START. Leave a session
    open across days and its whole content inherits the opening date. One
    real session opened on 28 July held every bit of the 29th's and 30th's
    work, 877 KB of it, while the only file named for the 30th was a 9 KB
    aside. "Yesterday's files" therefore missed almost all of yesterday.

2.  Exports arrive by sync, at an imprecise moment. A job that reads the
    folder on a schedule sometimes reads it just before the files land, and
    finds nothing.

`load_new` fixes both by ignoring dates entirely: it remembers how many
characters of each file it has already consumed and returns only what came
after. A file that grows yields its new material whatever its name says, and
a file that has not changed yields nothing.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
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


@dataclass
class Manifest:
    """How much of each conversation has already been turned into a post.

    Deliberately a plain character count per filename, not a hash or an
    mtime. Exporters rewrite every file on every run, so mtimes all collapse
    to the moment of export; a length, by contrast, only moves when you
    actually said something new.
    """

    path: Path
    seen: dict[str, int] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "Manifest":
        try:
            return cls(path=path, seen=json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            return cls(path=path, seen={})

    @property
    def is_empty(self) -> bool:
        return not self.seen

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.seen, indent=2, sort_keys=True),
                             encoding="utf-8")


def load_new(folder: Path, manifest: Manifest, *, glob: str = "*.md",
             min_new: int = 3_000,
             bootstrap_days: int = 2) -> tuple[list[Conversation], list[tuple[str, str]]]:
    """Only the material added since the last successful run.

    Returns the new conversations and the list of what was skipped and why.
    Each returned Conversation's `.text` is the NEW part alone, so everything
    downstream -- trimming, budget, the judge -- works unchanged.

    `manifest` is updated in memory but NOT written. Save it only once a post
    has actually been produced: if generation fails, the material must stay
    unconsumed so tomorrow's run picks it up again.

    On the very first run the manifest is empty and every file looks new,
    which would dump months of archives into one post. `bootstrap_days` limits
    that first run to recent files while still recording the size of all the
    others, so they never come back.
    """
    fresh: list[Conversation] = []
    skipped: list[tuple[str, str]] = []
    bootstrapping = manifest.is_empty
    cutoff = date.today() - timedelta(days=bootstrap_days)

    for path in sorted(folder.glob(glob)):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        seen = manifest.seen.get(path.name, 0)
        manifest.seen[path.name] = len(text)

        if bootstrapping:
            day = _day_from_name(path.name)
            if day is None or day < cutoff:
                skipped.append((path.name, "first run, older than bootstrap window"))
                continue
            new_text = text
        elif len(text) < seen:
            # The file shrank: re-exported in another format, or pruned. A
            # delta would be meaningless, so re-read the whole thing.
            new_text = text
        else:
            new_text = text[seen:]

        if len(new_text) < min_new:
            if new_text:
                skipped.append((path.name, f"only {len(new_text)} new chars"))
            continue

        match = HEADER_TIME_RE.search(text[:2000])
        fresh.append(Conversation(path=path,
                                  day=_day_from_name(path.name) or date.today(),
                                  started_at=match.group(1) if match else None,
                                  text=new_text))

    fresh.sort(key=lambda c: (c.started_at or "", c.name))
    return fresh, skipped


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
                 max_total_chars: int = 40_000,
                 min_slice: int = 2_000) -> Corpus:
    """Filter and trim, deterministically.

    min_chars   -- below this a conversation is noise: a quick question, an
                   aborted attempt. It has nothing worth writing about.
    tail_chars  -- never keep more than this from any one conversation, and
                   keep the END of it. Conclusions, decisions and final state
                   live there; the opening is usually exploration that went
                   nowhere.
    max_total   -- hard ceiling on what reaches the model, shared FAIRLY.
    min_slice   -- a share smaller than this teaches the model nothing, so
                   rather than give everyone a useless sliver, fewer
                   conversations are included and the omission is reported.

    The budget is shared smallest-first, not largest-first. Serving the big
    conversations first looks sensible and is not: on a busy day one talkative
    session ate the whole budget and six other conversations were dropped
    entirely, so the post could not even mention the day's real subject.
    Going smallest-first, short conversations pass whole, whatever they leave
    unspent flows to the long ones, and the longest are merely trimmed, from
    the front, where the least is decided.

    `max_total` is a real ceiling, not a target. An earlier version guaranteed
    every conversation at least `min_chars`, which quietly overshot the budget
    by 35% on a nine-conversation day -- exactly the kind of overrun that
    turns into a 429 from a free tier at the worst moment.
    """
    eligible: list[tuple[str, str]] = []
    dropped: list[tuple[str, str]] = []
    trimmed: list[str] = []

    for conversation in conversations:
        if len(conversation.text) < min_chars:
            dropped.append((conversation.name,
                            f"too short ({len(conversation.text)} chars)"))
            continue
        eligible.append((conversation.name, conversation.text))

    eligible.sort(key=lambda item: len(item[1]))

    # If the budget cannot give everyone a usable share, include fewer
    # conversations rather than everyone a sliver -- and name the ones left
    # out, so a thin post is explainable instead of mysterious.
    room_for = max(1, max_total_chars // min_slice)
    if len(eligible) > room_for:
        for name, text in eligible[:len(eligible) - room_for]:
            dropped.append((name, "budget too small to include every conversation"))
        eligible = eligible[len(eligible) - room_for:]

    parts: list[str] = []
    used: list[str] = []
    total = 0
    budget = max_total_chars
    for index, (name, text) in enumerate(eligible):
        remaining_files = len(eligible) - index
        quota = min(tail_chars, budget // remaining_files)
        if len(text) > quota:
            text = text[-quota:]
            trimmed.append(name)
        parts.append(f"--- conversation: {name} ---\n{text}")
        total += len(text)
        used.append(name)
        budget = max(budget - len(text), 0)

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
