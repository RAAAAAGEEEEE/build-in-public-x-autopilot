"""Deterministic checks on a generated post.

Every rule here was added because a model broke it in practice, not because it
sounded sensible. The comments name the failure -- keep them, they are the
reason each rule exists.

Why a script and not a model: an LLM counts characters badly and forgets a
constraint it agreed to two paragraphs earlier. A regex does neither, costs
nothing, and gives the same answer every time. Send the *failures* back to the
model as a named grievance and it fixes them on the next try.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass
class Rules:
    """Everything a post must satisfy. Tune per account and language."""

    # Length barely matters, and getting this wrong cost two rewrites. The
    # real limits on X are 280 characters on the free tier, 25,000 with
    # Premium, 100,000 in an Article. What actually constrains the writing is
    # something else entirely -- see preview_chars below.
    min_chars: int = 400
    max_chars: int = 1500
    hard_max_chars: int = 25_000

    # THE ONE THAT MATTERS. The timeline shows only the first ~280 characters
    # of a long post, then "Show more". Everything past that exists only for
    # readers who already decided to click. So the first two lines -- the hook,
    # and what you were working on -- must fit inside this window, or the feed
    # cuts mid-sentence.
    preview_chars: int = 280

    # An opening line the model must reproduce verbatim. Leave empty to skip.
    required_opening: str = ""

    # Openings that waste the preview window announcing the subject instead of
    # landing it. "Yesterday I worked on ..." was MANDATORY here until it was
    # measured against a real post: it spent a fifth of the visible window
    # saying something no reader can verify and none of them care about.
    banned_openings: tuple[str, ...] = ("yesterday i worked on",)

    # Phrases that mark a post as generic. Extend freely.
    banned_phrases: tuple[str, ...] = (
        "small win", "excited to announce", "proud to share",
        "proud to announce", "game changer", "game-changer",
        "revolutionary", "the future of", "made progress on",
    )

    # Words with no plain-language equivalent in a short post. The reader is
    # assumed to be smart but not a developer, so these must be rephrased,
    # not cited. Two distinct ones are tolerated: jargon is seasoning.
    jargon: tuple[str, ...] = (
        "acl", "posix", "root", "non-root", "commit", "commits", "repo",
        "repos", "sha", "diff", "staging", "sandbox", "sudo", "chmod",
        "regex", "stdout", "stderr", "cron", "crontab", "api", "json",
        "sqlite", "venv", "backend", "frontend", "middleware", "runtime",
        "parser", "parsing",
    )
    max_jargon: int = 2

    # A solo builder writing "the team decided" or "our client" has invented a
    # colleague. Observed repeatedly: models add social context that is not in
    # the facts. Only flagged when the word is ABSENT from the source, so a
    # genuine client project can still be written about.
    solo: bool = True
    collective_words: tuple[str, ...] = (
        "we", "our", "us", "team", "client", "colleague", "coworker",
        "the company",
    )

    # Internal names that mean nothing outside your own repository. A reader
    # scrolls past "LOT 9B" and "sys.modules". Add your own codenames.
    internal_names: tuple[str, ...] = ()

    require_first_person: bool = True
    allow_hashtags: bool = False
    allow_emoji: bool = False
    # Clock times read like an operations log and nobody cares what hour a job
    # runs. Banning them also removes a whole class of invented numbers.
    allow_clock_times: bool = False
    # Numbers not present in the source are hallucinations. "100%" and "0%" are
    # exempt: they are figures of speech, not measurements.
    check_numbers_against_source: bool = True


_IDIOMATIC_PERCENT = re.compile(r"\b(?:100|0)%")
_CLOCK_TIME = re.compile(r"\b\d{1,2}\s*[:h]\s*\d{2}\b|\b\d{1,2}\s*(?:am|pm)\b",
                         re.IGNORECASE)
_VERSION = re.compile(r"\b\d+\.\d+\.\d+\b")
_HASH = re.compile(r"\b[0-9a-f]{12,}\b", re.IGNORECASE)
_FILENAME = re.compile(r"\b[\w.-]+\.(?:py|md|json|txt|jsonl|env|sh|ya?ml)\b",
                       re.IGNORECASE)
_PATH = re.compile(r"(?<![\w/])/(?:root|home|etc|var|opt|usr|srv)(?:/[\w.\-]+)+")


def _fold(text: str) -> str:
    """Lowercase, strip accents, normalise curly apostrophes.

    The apostrophe step is not cosmetic: models write "j'ai" and "I've" with
    U+2019, so a naive regex for "i'" never matches and correct posts get
    rejected as impersonal.
    """
    folded = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                     if unicodedata.category(c) != "Mn")
    return folded.replace("’", "'").replace("‘", "'")


def _present(needle: str, haystack: str) -> bool:
    """Word-boundary match. Substring matching is a trap: "api" hides inside
    "rapid", and "prive" inside "privé" -- both produced false rejections
    before the boundaries were added."""
    return re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack) is not None


def check(post: str, rules: Rules, *, source_facts: str = "") -> list[str]:
    """Return a list of human-readable failures. Empty means the post passes."""
    problems: list[str] = []
    folded = _fold(post)
    folded_source = _fold(source_facts)
    length = len(post)

    if not (rules.min_chars <= length <= rules.max_chars):
        problems.append(
            f"length is {length}, outside {rules.min_chars}-{rules.max_chars}"
        )
    if length > rules.hard_max_chars:
        problems.append(f"length {length} exceeds the hard maximum "
                        f"{rules.hard_max_chars}")

    # The preview window: the first two non-empty lines are the hook and the
    # subject, and they are all most readers will ever see.
    visible = [ln for ln in post.split("\n") if ln.strip()][:2]
    head = "\n".join(visible)
    if len(head) > rules.preview_chars:
        problems.append(
            f"the first two lines are {len(head)} characters, past the "
            f"{rules.preview_chars}-character timeline preview: the feed will "
            f"cut them mid-sentence"
        )

    for opening in rules.banned_openings:
        if folded.startswith(_fold(opening)):
            problems.append(
                f'opens with "{opening}", which announces the subject instead '
                f"of landing it -- open on the most surprising fact instead"
            )

    if rules.required_opening and not folded.startswith(_fold(rules.required_opening)):
        problems.append(f'must start with "{rules.required_opening}"')

    for phrase in rules.banned_phrases:
        if _fold(phrase) in folded:
            problems.append(f"contains the banned phrase {phrase!r}")

    if not rules.allow_hashtags and "#" in post:
        problems.append("contains a hashtag")
    if not rules.allow_emoji and any(unicodedata.category(c) == "So" for c in post):
        problems.append("contains an emoji")

    if not rules.allow_clock_times:
        match = _CLOCK_TIME.search(post)
        if match:
            problems.append(f"contains a clock time ({match.group()!r}) -- say "
                            f'"every evening" or "once a day" instead')

    jargon_found = sorted({w for w in rules.jargon if _present(w, folded)})
    if len(jargon_found) > rules.max_jargon:
        problems.append(
            f"too much jargon ({len(jargon_found)} terms: {jargon_found}); "
            f"say what the thing DOES, not what it is called"
        )

    internal = sorted({n for n in rules.internal_names if _present(_fold(n), folded)})
    for pattern, label in ((_PATH, "a file path"), (_FILENAME, "a file name"),
                           (_HASH, "a hash or commit id"),
                           (_VERSION, "a precise version number")):
        found = pattern.search(post)
        if found:
            internal.append(f"{label} ({found.group()!r})")
    if internal:
        problems.append(f"contains internal identifiers: {internal}")

    if rules.require_first_person and not re.search(
            r"(?<!\w)(?:i|i'|my|me|mine)(?!\w)", folded):
        problems.append("not written in the first person")

    if rules.solo:
        invented = sorted({
            w for w in rules.collective_words
            if _present(w, folded) and not _present(w, folded_source)
        })
        if invented:
            problems.append(
                f"invents people who are not in the facts: {invented}; "
                f"write only 'I' and 'my'"
            )

    if rules.check_numbers_against_source and source_facts:
        # Digits inside a version number in the source do not license reusing
        # them elsewhere: a source containing "2.96.0" was letting a model
        # write an invented "2 hours" and pass.
        allowed = set(re.findall(r"\d+", _VERSION.sub("", source_facts)))
        idiomatic = {m.group()[:-1] for m in _IDIOMATIC_PERCENT.finditer(post)}
        for number in re.findall(r"\d+", post):
            if number in idiomatic or number in allowed:
                continue
            problems.append(f"the number {number!r} is not in the source facts")

    return problems
