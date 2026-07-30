# bip-autopilot

Turn your AI coding conversations into a daily "build in public" post — using
only free LLM tiers, with a human approving every post before it goes out.

You already explain your work to an AI all day. That transcript is the raw
material for a build-in-public post. This reads yesterday's conversations,
picks the one subject worth telling, drafts a post, checks it mechanically,
verifies every claim against the source, and sends it to you for review.

**It never publishes anything.** Drafts land in Telegram or on stdout. You copy
what you like. There is no posting code in this repository, on purpose.

---

## Why this exists

Most "AI writes your social posts" tools have the same two failure modes:
they invent things that never happened, and they write like a changelog. Both
are fatal for build-in-public, where the whole value is that it is true and
readable.

So the interesting part of this project is not the prompt. It is the two layers
that sit around it:

- **Deterministic checks** (`pipeline/checks.py`) — a script, not a model.
  Length, banned phrases, jargon ceiling, invented numbers, invented
  colleagues, internal identifiers. Models count characters badly and forget a
  constraint they agreed to two paragraphs earlier. A regex does neither.
- **A factual verifier** (`pipeline/generate.py`) — a second model reads the
  draft *and* the source, and reports any claim the source does not support.

That second layer earns its place. Here is a real run: a draft that passed
**every** mechanical check, then failed verification on four counts.

> Yesterday I worked on a security audit of AI autonomy. […] I ran a strictly
> read-only audit. It revealed a surprising escalation vector where the agent
> could potentially gain root access via cron or systemd.

The verifier's response:

```
"I ran a strictly read-only audit" — the source describes a series of tests
and a bootstrap plan, not a read-only audit performed by the author
"It revealed a surprising escalation vector…" — the source states no such
vector exists and that no cron or service file is touched
"Read-only audits are the most powerful tool…" — an opinion, not in the source
```

Every word was allowed. The meaning was invented. No pattern-matching rule can
catch that; only something that reads both texts can.

---

## Free tiers, as actually measured

Every limit below came from a real free-tier account and the API's own
response headers — not from a pricing page. Two providers that documentation
still lists as usable were dead on a working key.

| Provider | Measured free limits | Role here |
|---|---|---|
| **Cerebras** | 1,000,000 tokens/day · 2,400 req/day · **5 req/min** · 30k tokens/min | Largest daily budget by far. The per-minute cap is the real constraint, so the pipeline paces itself. |
| **Mistral** | 50,000 tokens/min · 50 req/min | Strong writer, notably in French. Absorbs bursts well. |
| **OpenRouter** | 17 free models, incl. a 550B with a 1M context window | Widest safety net. Individual free models return 429 when their shared pool is busy. |
| **Gemini** | 250 req/day · 250k tokens/min · 10 req/min | Reasoning model. The daily request count binds, so it judges and verifies rather than writes. |
| ~~Groq~~ | HTTP 403 on a previously working key | Excluded |
| ~~DeepSeek~~ | HTTP 402 Payment Required | Excluded |

Three findings that will save you an afternoon:

**Cerebras answers 403 without a `User-Agent` header.** It sits behind
Cloudflare (error 1010), and the failure looks exactly like an invalid key.

**Reasoning models silently truncate your output.** Their hidden thinking
tokens count against `max_tokens` but never appear in `completion_tokens`. Ask
one for a 600-character post with a 220-token ceiling and you get 46 tokens of
real text, cut mid-sentence, with `finish_reason: length` as the only clue.
This pipeline defaults to a high ceiling and treats truncation as a provider
failure.

**Do not use a reasoning model to write prose.** It spends its budget thinking
about a task that needs no thinking. Use it to judge and to verify — that is
where the reasoning pays for itself.

---

## How it works

```
conversations/           exported .md files, one per session
      │
      ├─ 1. ingest       no LLM: pick the day, drop noise, keep each
      │                  conversation's tail, cap the total
      │
      ├─ 2. judge        a reasoning model reads only the OPENINGS and picks
      │                  the single most tellable subject
      │
      ├─ 3. write        a plain model drafts from the winning material
      │
      ├─ 4. check        a script rejects mechanically-broken drafts
      │        └─ retry with the exact failures named
      │
      ├─ 5. verify       a reasoning model confirms every claim is grounded
      │
      └─ 6. deliver      Telegram or stdout, flagged if anything is shaky
```

Stage 1 uses no model at all, and that is deliberate: the cheap deterministic
work happens before you spend a single token. It matters more than it sounds.
Measured on one real month of exports, a busy day totalled ~280,000 tokens
across ten conversations, and one single conversation reached ~481,000. Feeding
that raw exceeds both the context window and the per-minute token cap of every
free tier listed above.

Stage 2 judges on ~2,000 characters per conversation instead of the full
corpus. That is roughly 80% fewer tokens spent on selection, and the writer
then reads only what won.

---

## Setup

Requires Python 3.9+ and nothing else. No dependencies.

```bash
git clone <this repo>
cd bip-autopilot
cp config.example.json config.json
```

Edit `config.json`:

1. **`conversations_dir`** — where your exported conversations live. Any tool
   that writes one Markdown file per session works, as long as the filename or
   the header carries the date. Patterns live in `pipeline/ingest.py`; add
   yours there if it differs.
2. **`keys`** — fill in the providers you have. Missing ones are skipped and
   the cascade uses what is left. All four have a free tier; none needs a card.
3. **`persona`** — the single most important setting. Describe who reads you
   and what you are building, in plain words. Without it, drafts drift into
   engineering changelogs.

Then:

```bash
# See what it would produce, deliver nothing
python3 run.py --config config.json --date 2026-07-29 --dry-run

# Real run: store the draft and deliver it
python3 run.py --config config.json
```

Daily, from cron. It publishes the previous day by default, which means the
whole day is complete when it is processed:

```cron
0 12 * * * cd /path/to/bip-autopilot && /usr/bin/python3 run.py --config config.json >> run.log 2>&1
```

Nobody can tell a post was written about yesterday. You can, and it buys you a
complete day of material plus a free choice of publishing hour.

---

## Configuring the checks

`rules` in `config.json` maps to `pipeline/checks.Rules`. Every default is
there because a model broke it during testing:

| Rule | What it caught |
|---|---|
| `min_chars` / `max_chars` | Drafts at 35 and 280 characters, cut mid-sentence |
| `required_opening` | The model dropping the opening line it was given |
| `max_jargon` | Posts readable only by the author |
| `solo` | "the team decided", "my client's site" — people who do not exist |
| `internal_names` | Project codenames meaningless outside the repo |
| number checking | An invented "2 hours" that borrowed its digit from a version string in the source |
| clock times | "runs at 5:30 PM" — nobody cares, and it reads like an ops log |

Set `solo: false` if you genuinely work with a team. Collective words are only
flagged when they are **absent from the source**, so a real client project is
still writable.

---

## Posting in two languages

Set `translate_to` and the approved post is translated, not regenerated. Two
independent generations drift apart, and then one audience is reading a
different story than the other. Translating keeps both honest.

A note on timing, if you serve two audiences: pick each slot for its own
audience rather than spacing them evenly. French lunch and US lunch are six
hours apart, so both can hit a peak from one day's material.

---

## What this will not do

- **It will not publish for you.** By design. Automated publishing is the one
  mistake you cannot take back, and the cost of being wrong is public.
- **It will not make a boring day interesting.** The judge scores subjects on
  tension, discovery and whether a stranger could follow them. Some days score
  low on all three, and the honest output is a flat post.
- **It will not keep your secrets for you.** Conversation exports contain paths,
  file names, sometimes credentials. The checks strip identifiers from the
  *draft*, but read what you are about to post. That is what the review step
  is for.
- **It is not free of limits, only free of cost.** Free tiers go down. The
  cascade routes around one provider failing; it cannot route around all of
  them, and it will tell you when that happens.

---

## License

MIT. See [LICENSE](LICENSE).
