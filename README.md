# bip-autopilot

Turn your AI coding conversations into a daily "build in public" post — using
only free LLM tiers, with a human approving every post before it goes out.

You already explain your work to an AI all day. That transcript is the raw
material for a build-in-public post. This reads whatever you have said since
its last run, picks the one subject worth telling, drafts a post, checks it
mechanically, verifies every claim against the source, and sends it to you for
review.

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
      ├─ 1. ingest       no LLM: take what is NEW since last run, drop
      │                  noise, share a character budget, cap the total
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

## Do not select conversations by date

This is the mistake worth reading before you write your own version. The first
build of this pipeline asked for "yesterday's files". That is wrong twice over,
and neither failure produces an error message.

**A conversation file is named after the session's start.** Leave a session
open across days and its entire content inherits the opening date. In one real
case a session opened on 28 July held every bit of the 29th's and the 30th's
work — 877 KB of it — while the only file named for the 30th was a 9 KB aside.
Asking for "yesterday" returned the aside and missed the actual day.

**Exports arrive by sync, at an imprecise moment.** A job reading the folder on
a schedule will sometimes read it seconds before the files land, and find
nothing. The log says `0 conversations` and looks like a quiet day.

So the pipeline ignores dates entirely. It records how many characters of each
file it has already consumed (`state/consumed.json`) and takes only what came
after. A file that grows yields its new material whatever its name says; an
unchanged file yields nothing; a file that shrank — re-exported in another
format — is simply re-read whole.

The manifest is written **only after a post has been delivered**. Every abort
path leaves it untouched, so material that failed to become a post is still
waiting for the next run instead of being silently burned.

One consequence worth stating: this pipeline is not idempotent by day, it is
incremental. Running it twice in a row gives you a post and then nothing. That
is the intended behaviour — the second run genuinely has nothing new to say.
Use `--date` to rebuild an old post from the files named for that day.

### The budget must be shared fairly

A related trap, in the same stage. The obvious way to enforce a character
ceiling is to serve the largest conversations first and stop when the budget
runs out. On a busy day that dropped six conversations out of nine: one
talkative session ate everything, and the post could not mention the day's real
subject.

The budget is now shared smallest-first. Short conversations pass whole,
whatever they leave unspent flows to the long ones, and nothing disappears —
the longest are merely trimmed, from the front, where the least is decided.

---

## Setup

Requires Python 3.9+ and nothing else. No dependencies.

```bash
git clone <this repo>
cd bip-autopilot
cp config.example.json config.json
```

Edit `config.json`:

1. **`conversations_dir`** — where your exported conversations live. See
   [Getting your conversations there](#getting-your-conversations-there) below.
2. **`manifest_path`** — where to remember what has already been turned into a
   post. Defaults to `state/consumed.json`. Delete it to start over; it is
   local state, keep it out of git.
3. **`keys`** — fill in the providers you have. Missing ones are skipped and
   the cascade uses what is left. All four have a free tier; none needs a card.
4. **`persona`** — the single most important setting. Describe who reads you
   and what you are building, in plain words. Without it, drafts drift into
   engineering changelogs.

Then:

```bash
# See what it would produce, deliver nothing, consume nothing
python3 run.py --config config.json --dry-run

# Real run: store the draft, deliver it, then record what it consumed
python3 run.py --config config.json
```

Daily, from cron. It labels the post with the previous day, which means the
whole day is complete when it is processed:

```cron
0 12 * * * cd /path/to/bip-autopilot && /usr/bin/python3 run.py --config config.json >> run.log 2>&1
```

Nobody can tell a post was written about yesterday. You can, and it buys you a
complete day of material plus a free choice of publishing hour. The exact
minute does not matter, because the run reads new material rather than a
schedule — that is the whole point of the previous section.

---

## Getting your conversations there

The pipeline needs one Markdown file per session in a folder it can read. How
they get there is up to you; two decisions matter.

**Exporting.** Any exporter works as long as it writes one file per session
and keeps a stable name per session, so a growing session stays the same file
and the delta keeps working. A session that is re-exported under a new name
every time will be re-read from scratch each run — correct, but wasteful. The
reference setup produces `claude-conversation-YYYY-MM-DD-<session id>.md`,
with a `Date: ...` header line inside.

**Getting them to the machine that runs this.** If you code on a laptop and run
this on a server, you need the files to travel. Any of these is fine:

- **A sync tool** (Syncthing, Dropbox, `rsync` on a timer). This is the
  reference setup, with Syncthing pointed at the export folder on one side and
  `conversations_dir` on the other.
- **A `git` repo** of your exports, pulled before the run.
- **Nothing at all**, if you code on the same machine that runs this. Point
  `conversations_dir` at the export folder directly.

One warning that applies to every one of them: **do not order or select files
by modification time.** Sync tools rewrite files in bulk, so every mtime
collapses to the moment of the sync. On the reference machine all fifty-odd
exports share a single mtime, to the second. The filename and the header are
the only timestamps that mean anything — and per the previous section, even
those should not decide what gets read.

---

## Length is not the constraint. The preview is.

This section exists because getting it wrong cost two rewrites, and the mistake
is easy to repeat.

The real limits on X are **280 characters** on the free tier, **25,000** with
Premium, and **100,000** in an Article. Two earlier versions of this pipeline
enforced 400-700, then 180-280, both of them numbers nobody had checked. The
first produced posts too long to publish at all; the second amputated posts
that had plenty of room.

What actually constrains the writing is different: **the timeline shows only
the first ~280 characters, then "Show more"**. Everything past that exists only
for readers who already decided to click. So the total length barely matters
and the opening carries everything:

```
LINE 1   the hook       one strong sentence, under twelve words
LINE 2   the subject    what you were working on, plainly
---------------------- these two must fit in 280 characters together
THEN     the body       what it changed, then the close
```

`preview_chars` in `Rules` enforces exactly that, and it is the check worth
keeping if you keep only one.

**Do not open with "Yesterday I worked on ..."** — or any phrase that announces
the subject rather than landing it. It was a *mandatory* opening here until it
was measured against a real post: it spent a fifth of the visible window saying
something no reader can verify and none of them care about. `banned_openings`
now rejects it.

---

## What goes in a message a human will copy

One rule, learned twice in one week, in two different places:

**A message meant to be copied contains nothing but what should be copied.**

- A draft sent as `"draft for 2026-07-29\n\n<post>"` got pasted into X *with
  the header*.
- An image prompt sent as `"IMAGE PROMPT (paste as is)\n\n<prompt>"` got
  pasted into an image model, which obligingly **drew the words "IMAGE PROMPT"
  onto a noticeboard in the picture**.

So the post travels alone. Anything else — the date, a review flag, a prompt
label — goes in its own message. The "Open in X" button is an *inline keyboard
button*, deliberately not a link inside the text, for the same reason: a URL in
the caption would be copied along with the post and published.

X's compose link carries **text only**. No image can be attached that way, and
that restriction is deliberate on their side: a third-party page must not be
able to attach a file to a message you are about to publish. Pass `--image` and
the picture arrives in the same Telegram message as the text, ready to attach
by hand.

On **iOS**, the button opens Telegram's in-app browser, which is not logged
into X. Either long-press the button and choose *Open in Safari*, or set your
browser once under *Telegram → Settings → Data and Storage*. On desktop it just
works.

---

## Configuring the checks

`rules` in `config.json` maps to `pipeline/checks.Rules`. Every default is
there because a model broke it during testing:

| Rule | What it caught |
|---|---|
| `min_chars` / `max_chars` | Drafts at 35 and 280 characters, cut mid-sentence |
| `preview_chars` | A hook and subject spilling past the timeline preview, cut mid-sentence in the feed |
| `banned_openings` | "Yesterday I worked on ...", which burns a fifth of the visible window announcing the subject |
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
