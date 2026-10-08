# Architecture

Related: [CONFIGURATION](CONFIGURATION.md), [USAGE](USAGE.md),
[LIMITATIONS](LIMITATIONS.md).

## Why two extra layers

Most "AI writes your posts" tools fail the same two ways: they invent things
that never happened, and they write like a changelog. The prompt is not the
interesting part. Two layers around it are:

- **Deterministic checks** (`pipeline/checks.py`): a script, not a model.
  Length, banned phrases, jargon ceiling, invented numbers, invented
  colleagues, internal identifiers. Models count characters badly and forget a
  constraint they agreed to earlier; a regex does neither.
- **A factual verifier** (`pipeline/generate.py`, `verify_post`): a second
  model reads the draft and the source and reports any claim the source does
  not support.

Real example (from the author's own testing): a draft passed every mechanical
check, then failed verification. The verifier's output, abridged:

```
"I ran a strictly read-only audit" - the source describes a series of tests
and a bootstrap plan, not a read-only audit performed by the author
"It revealed a surprising escalation vector..." - the source states no such
vector exists
```

Every word was allowed; the meaning was invented. Only something that reads
both texts can catch that.

## Pipeline

```
conversations/           exported .md files, one per session
      |
      +- 1. ingest       no LLM: take what is NEW since last run, drop
      |                  noise, share a character budget, cap the total
      |
      +- 2. judge        a reasoning model reads only the OPENINGS and picks
      |                  the single most tellable subject
      |
      +- 3. write        a plain model drafts from the winning material
      |
      +- 4. check        a script rejects mechanically-broken drafts
      |        +- retry with the exact failures named
      |
      +- 5. verify       a reasoning model confirms every claim is grounded
      |
      +- 6. deliver      Telegram or stdout, flagged if anything is shaky
```

| Stage | Module |
|---|---|
| Entry point, configuration, orchestration | `run.py` |
| 1. Ingest | `pipeline/ingest.py` |
| 2, 3, 5, translation | `pipeline/generate.py` |
| 4. Checks | `pipeline/checks.py` |
| Model calls | `pipeline/providers.py` |
| 6. Delivery | `pipeline/deliver.py` |

Stage 1 uses no model: the cheap deterministic work happens before any token
is spent. The author measured, on one real month of exports, a busy day of
about 280,000 tokens across ten conversations and a single conversation of
about 481,000 tokens (author's measurement, not a benchmark). Stage 2 judges on
about 2,000 characters per conversation instead of the full corpus, so the
writer reads only what won.

Failure policy: if the subject judge or the verifier is unavailable, the run
continues (no forced focus / draft passed unverified). If the writer is
unavailable, the run aborts with an alert (exit code 2). If no draft passes
the checks after `candidates` attempts, it aborts with an alert (exit code 3).

## Do not select conversations by date

The first design asked for "yesterday's files". It was wrong twice, with no
error message either time.

- **A conversation file is named after the session's start.** A session left
  open across days inherits its opening date. In one real case a session
  opened on 28 July held all of the 29th's and 30th's work (877 KB) while the
  only file named for the 30th was a 9 KB aside.
- **Exports arrive by sync, at an imprecise moment.** A scheduled job can read
  the folder seconds before files land and log `0 conversations`, which looks
  like a quiet day.

So the pipeline ignores dates. It records how many characters of each file it
has consumed (`state/consumed.json`, key `manifest_path`) and takes only what
came after. A growing file yields its new material; an unchanged file yields
nothing; a file that shrank (re-exported in another format) is re-read whole.
On a first run, only files from the last 2 days are considered
(`bootstrap_days` in `load_new`), and a file needs at least 3,000 new
characters (`min_new`) to count.

The manifest is written **only after a post has been delivered**. Every abort
path leaves it untouched, so material that failed to become a post waits for
the next run. Consequence: the pipeline is incremental, not idempotent by day;
two runs in a row give a post, then nothing. `--date` rebuilds an old post
from the files named for that day and consumes nothing.

### The budget is shared smallest-first

Serving the largest conversations first and stopping at the ceiling dropped
six conversations out of nine on a busy day. The budget is now shared
smallest-first: short conversations pass whole, unspent budget flows to the
long ones, and the longest are trimmed from the front.

## Delivery design

A message meant to be copied contains only what should be copied. See
[USAGE](USAGE.md#delivery-rules) for the rules and the reason behind each.

## History: the removed free-tier cascade

Until 2026-08-07 the pipeline called free LLM tiers (Cerebras, Mistral,
OpenRouter, Gemini) in a fallback cascade. It was removed because a weaker
model would answer, nothing checked what it wrote, and the run still looked
successful: silent degradation is worse than a clean failure. The pipeline now
produces either an answer from the configured backend or an exception.

Findings from that period, kept because they are reusable (the limits below
were observed on real free accounts at the time and are **not** current
guarantees):

- A free provider behind Cloudflare answered 403 without a `User-Agent`
  header, which looks exactly like an invalid key.
- Reasoning models silently truncate output: hidden thinking tokens count
  against `max_tokens` but not `completion_tokens`, so a small ceiling yields
  a few real tokens cut mid-sentence with `finish_reason: length` as the only
  clue. Treat truncation as a provider failure.
- Do not use a reasoning model to write prose; use it to judge and verify.
- Two providers that their documentation still listed as usable were dead on a
  working key (HTTP 403 and HTTP 402).
