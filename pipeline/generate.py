"""Judge a subject, write the post, verify it, translate it.

The order matters and is the whole design:

  1. JUDGE   a reasoning model picks the day's subject from short openings.
  2. WRITE   a plain model drafts N candidates from the winning material.
  3. CHECK   a script rejects mechanically-broken drafts (checks.py).
  4. RETRY   the exact failures go back to the model, named.
  5. VERIFY  a reasoning model confirms every claim exists in the source.

Steps 1 and 5 are the two places where reasoning earns its cost. Writing a
600-character post is not one of them: a reasoning model spends its thinking
budget producing prose a plain model writes just as well, and the hidden
thinking tokens silently truncate the answer. Judgement and verification are
where thinking pays.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import checks, providers

SUBJECT_JUDGE_PROMPT = """You are given the openings of every work conversation from one day. Each one is a different piece of work.

Pick the SINGLE subject that would make the best "build in public" post for readers who do not know this person.

Score on these, in order of importance:
1. REAL TENSION OR TRADE-OFF -- they had to choose between two options, give something up, or accept a risk. A subject with no trade-off is flat.
2. DISCOVERY OR SURPRISE -- something did not work as expected, a bug revealed something else, an assumption turned out wrong.
3. TELLABLE TO A STRANGER -- a non-developer can grasp the stakes in one sentence. A subject that requires knowing their project is disqualified.
4. A REAL LESSON -- something transferable comes out of it, not just "it is done".

What does NOT count: how long the work took, how many files changed, how technically hard it was. A long careful review with no trade-off loses to a small bug that revealed something.

Answer in exactly this format:

CANDIDATES
- <subject>: <score>/10 -- <one line why>
(one line per distinct subject)

CHOSEN
<The winning subject in 2-4 sentences: what it is, what tension or discovery makes it interesting, and what lesson comes out. This text guides the writing, so be precise and factual.>

CONVERSATION OPENINGS:

{index}
"""

WRITE_PROMPT = """You are ghostwriting one "build in public" post for X, in the first person.

{subject_block}

{persona}

HARD RULES
- Use ONLY facts present in the material below. Invent nothing: no metric, no emotion, no user outcome, no number.
- Tell a real learning apart from a routine task. If the facts contain no genuine lesson, describe the work plainly instead of manufacturing one.
- {length_rule}
- Short sentences. One idea at a time. First person throughout.
- No hashtags. No emoji. No markdown. No links.
- Never a clock time, file path, file name, hash, commit id, version number, key, token, password, email or IP address. Describe the thing and its role, never its identifier.
- Keep PUBLIC product names (GitHub, Telegram, Google Maps, Claude, Slack). Drop names that mean nothing outside the author's own project.
- Never name a person, including yourself.
{opening_rule}{banned_opening_rule}
THE FIRST TWO LINES ARE THE WHOLE POST. The timeline shows only the first ~280 characters, then "Show more". Everything after that exists only for readers who already decided to click. Those two lines must fit inside 280 characters together.
LINE 1 -- THE HOOK. One strong sentence, the most surprising fact, under twelve words, on its own line. This is where the reader decides.
LINE 2 -- WHAT YOU WERE WORKING ON. One plain concrete sentence, on its own line.
THEN the body: what it actually changed, two to four sentences, plain language. Then either a sharp closing line, or one genuine open question.

A CLOSING QUESTION IS OPTIONAL. Only ask one if it is legitimate and BROAD -- answerable by any builder from their own experience, with no knowledge of this project. Zoom out from the specific bug to the shared experience behind it. If none fits, end on a statement. Never end mid-sentence.

Reply with the post only. No preamble, no commentary.

MATERIAL:

{material}
"""

VERIFY_PROMPT = """Check a drafted post against the source material it came from.

Your only job is factual accuracy. Ignore style, tone and length.

For each claim in the post, decide whether the source material supports it. Watch especially for:
- a number, duration or quantity that is not in the source
- work attributed to the wrong project or product
- a cause-and-effect the source does not state
- an outcome or benefit that is hoped for rather than achieved
- people (a team, a client, a colleague) the source never mentions

Answer in exactly this format:

VERDICT: PASS
or
VERDICT: FAIL
PROBLEMS
- <one line per unsupported claim, quoting the words at fault>

POST:
{post}

SOURCE MATERIAL:
{material}
"""

TRANSLATE_PROMPT = """Translate this X post into {language}.

- Same meaning, same structure, same number of paragraphs.
- Same voice: direct, spoken, blunt, first person.
- Not word-for-word: write it the way a native speaker would, with no calqued phrasing.
- Keep it within {min_chars}-{max_chars} characters.
{opening_rule}- No hashtags, no emoji, no person's name.

Reply with the translated post only.

POST:
{post}
"""


@dataclass
class Draft:
    text: str
    provider: str
    attempts: int
    problems: list[str]

    @property
    def ok(self) -> bool:
        return not self.problems


def judge_subject(index: str, keys: dict[str, str], *,
                  log=lambda m: None) -> str | None:
    """Pick the day's subject. Returns None if the judge is unavailable --
    writing then proceeds without a forced focus rather than not at all."""
    try:
        text, provider, _ = providers.complete(
            SUBJECT_JUDGE_PROMPT.format(index=index), keys,
            claude_model="claude-opus-5", prefer="gemini",
            temperature=0.2, log=log)
    except providers.AllProvidersFailed as exc:
        log(f"subject judge unavailable, writing without a focus: {exc}")
        return None

    marker = "CHOSEN"
    position = text.find(marker)
    if position == -1:
        log("subject judge answered in an unexpected format, ignoring it")
        return None

    candidates = text[:position].strip()
    chosen = text[position + len(marker):].strip().lstrip(":").strip()
    if not chosen:
        return None
    log(f"subject judge ({provider}) evaluated:\n{candidates}")
    log(f"subject chosen: {chosen[:200]}")
    return chosen


def write_post(material: str, keys: dict[str, str], rules: checks.Rules, *,
               subject: str | None = None, persona: str = "",
               max_attempts: int = 3, temperature: float = 0.7,
               log=lambda m: None) -> Draft:
    """Draft, check, and retry with the failures named.

    Naming the failure is what makes the retry work. An early version told the
    model only "wrong length"; it grew a 757-character post into 905 because it
    could not tell which direction to move. The grievance now carries the
    measurement and the direction.
    """
    subject_block = (
        "SUBJECT OF THE DAY, already chosen for you -- write about THIS and "
        "ignore everything else in the material:\n" + subject
        if subject else
        "Choose the subject with the clearest tension or discovery. Do not "
        "pick by volume of work."
    )
    opening_rule = (
        f'- The post must begin with exactly: "{rules.required_opening}"\n'
        if rules.required_opening else ""
    )
    # Openings that burn the preview window announcing the subject. Naming
    # them beats describing the problem: models reproduce a forbidden phrase
    # they were only warned about in the abstract.
    banned_opening_rule = "".join(
        f'- NEVER open with "{o}". It announces the subject instead of landing '
        f"it, and spends a fifth of the visible window saying something the "
        f"reader cannot verify and does not care about.\n"
        for o in rules.banned_openings
    )
    base = WRITE_PROMPT.format(
        subject_block=subject_block,
        persona=persona or "Write for a smart reader who is NOT a developer.",
        length_rule=f"Between {rules.min_chars} and {rules.max_chars} "
                    f"characters, never more than {rules.hard_max_chars}.",
        opening_rule=opening_rule,
        banned_opening_rule=banned_opening_rule,
        material=material,
    )

    prompt = base
    problems: list[str] = []
    text = ""
    provider = ""
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            prompt = (
                "Your previous answer was rejected for these exact reasons:\n- "
                + "\n- ".join(problems)
                + "\n\nRewrite the whole post fixing them, without introducing "
                  "new problems.\n\n" + base
            )
        try:
            text, provider, _ = providers.complete(
                prompt, keys, temperature=temperature, log=log)
        except providers.AllProvidersFailed:
            raise
        problems = checks.check(text, rules, source_facts=material)
        if not problems:
            log(f"draft accepted on attempt {attempt} ({len(text)} chars)")
            return Draft(text, provider, attempt, [])
        log(f"attempt {attempt} rejected: {problems}")

    return Draft(text, provider, max_attempts, problems)


def verify_post(post: str, material: str, keys: dict[str, str], *,
                log=lambda m: None) -> tuple[bool, list[str]]:
    """Confirm every claim is grounded in the source.

    This catches what no script can. A post can pass every mechanical rule and
    still attribute the day's work to the wrong project -- every word allowed,
    the meaning wrong. Only a reader that understands both texts sees it.

    A verifier that cannot be reached returns PASS: blocking a good post
    because a free tier is down is worse than publishing an unverified one,
    and a human still reviews before posting.
    """
    try:
        text, provider, _ = providers.complete(
            VERIFY_PROMPT.format(post=post, material=material), keys,
            claude_model="claude-opus-5", prefer="gemini",
            temperature=0.0, log=log)
    except providers.AllProvidersFailed as exc:
        log(f"verifier unavailable, passing unverified: {exc}")
        return True, []

    upper = text.upper()
    if "VERDICT: PASS" in upper:
        log(f"verifier ({provider}): PASS")
        return True, []

    problems = [line.lstrip("- ").strip()
                for line in text.splitlines()
                if line.strip().startswith("-")]
    log(f"verifier ({provider}): FAIL -- {problems}")
    return False, problems


def translate_post(post: str, language: str, keys: dict[str, str],
                   rules: checks.Rules, *, opening: str = "",
                   log=lambda m: None) -> str | None:
    """Translate an approved post.

    Translating rather than generating a second post is deliberate: two
    independent generations drift apart, and then one audience is reading a
    different story than the other.
    """
    opening_rule = f'- Begin with exactly: "{opening}"\n' if opening else ""
    try:
        text, provider, _ = providers.complete(
            TRANSLATE_PROMPT.format(
                language=language, post=post, opening_rule=opening_rule,
                min_chars=rules.min_chars, max_chars=rules.hard_max_chars),
            keys, prefer="mistral", temperature=0.3, log=log)
    except providers.AllProvidersFailed as exc:
        log(f"translation failed: {exc}")
        return None
    log(f"translated to {language} via {provider} ({len(text)} chars)")
    return text
