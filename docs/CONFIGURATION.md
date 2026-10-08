# Configuration

Related: [INSTALLATION](INSTALLATION.md), [USAGE](USAGE.md),
[PRIVACY_AND_SECURITY](PRIVACY_AND_SECURITY.md).

The configuration is one JSON file, passed with `--config`. The template is
`config.example.json` (the equivalent of an `.env.example` for this project;
there are no environment variables). Copy it to `config.json`, which is
gitignored.

## Keys

| Key | Default | Meaning |
|---|---|---|
| `conversations_dir` | none, **required** | Folder of exported `.md` conversations. |
| `timezone` | `UTC` | IANA name, used to compute "yesterday". |
| `publish_previous_day` | `true` | Label the draft with the previous day. |
| `drafts_dir` | `drafts` | Where `<day>.json` is stored on a real run. |
| `manifest_path` | `state/consumed.json` | Remembers how much of each file was consumed. Delete it to start over; keep it out of git. |
| `candidates` | `3` | Maximum writing attempts before giving up (exit code 3). |
| `persona` | empty | **The most important setting.** Who reads you and what you build, in plain words. Without it, drafts drift into engineering changelogs. |
| `language` | `English` | Language of the post. |
| `translate_to` | empty | Second language; see [USAGE](USAGE.md#posting-in-two-languages). |
| `translated_opening` | empty | Opening line to impose on the translation. |
| `telegram.bot_token`, `telegram.chat_id` | empty | Optional. Both set: drafts go to Telegram. Otherwise stdout. |
| `rules` | `{}` | Overrides for the checks below. |
| `keys` | `{}` | **Obsolete.** Provider API keys of the removed free-tier cascade. Accepted and ignored; leave empty. |

`persona` tip: say what a thing meant, not what it was called, and name your
project in one or two sentences so the post can attribute work accurately.

## Text generation backend

All model calls go through `pipeline/providers.py`, function `complete`. It runs
one external executable, whose absolute path is the constant `CLAUDE_CALL` in
that file, with three arguments: a temporary file holding the prompt, a model
identifier, and a timeout in seconds. It must print the answer on stdout and
exit with code 0. That script is **not part of this repository**.

- Writing uses `claude-sonnet-5`; judging and verifying use `claude-opus-5`
  (a text checked by the model that wrote it gets rubber-stamped, so the
  reviewer is a different, stronger model).
- If the executable is missing, the run reports `no LLM provider answered` and
  exits with code 2 (verified 2026-10-05).
- To use another backend, provide an executable honouring that contract at the
  path in `CLAUDE_CALL`, or change that constant for your machine. This is the
  one place to adapt.

## The checks

`rules` maps to `pipeline/checks.Rules`. Every default exists because a model
broke it during testing.

| Rule | What it caught |
|---|---|
| `min_chars` (400) / `max_chars` (1500) | Drafts at 35 and 280 characters, cut mid-sentence |
| `hard_max_chars` (25000) | Upper bound matching X Premium posts |
| `preview_chars` (280) | A hook and subject spilling past the timeline preview |
| `required_opening` | An opening line the model must reproduce verbatim (empty = off) |
| `banned_openings` | "Yesterday I worked on ...", which burns a fifth of the visible window |
| `banned_phrases` | Generic phrases ("game changer", "excited to announce", ...) |
| `jargon` / `max_jargon` (2) | Posts readable only by the author |
| `solo` (true) / `collective_words` | "the team decided", "my client's site": people who do not exist. Only flagged when absent from the source |
| `internal_names` | Project codenames meaningless outside your repository; add yours |
| `require_first_person` (true) | Posts not written as "I" |
| `allow_hashtags`, `allow_emoji` (false) | Hashtags and emoji |
| `allow_clock_times` (false) | "runs at 5:30 PM": reads like an ops log, and a source of invented numbers |
| `check_numbers_against_source` (true) | An invented "2 hours" that borrowed its digit from a version string |

Set `solo: false` if you genuinely work with a team.

### Length is not the constraint; the preview is

The real limits on X are 280 characters on the free tier, 25,000 with Premium
and 100,000 in an Article (as the author understood them when writing this;
check X's current rules). Two earlier versions enforced 400-700 then 180-280,
numbers nobody had checked: the first produced posts too long to publish, the
second cut posts that had room. What actually constrains the writing is that
**the timeline shows only the first ~280 characters, then "Show more"**:

```
LINE 1   the hook       one strong sentence, under twelve words
LINE 2   the subject    what you were working on, plainly
---------------------- these two must fit in 280 characters together
THEN     the body       what it changed, then the close
```

`preview_chars` enforces exactly that; keep it if you keep only one rule. Do
not open with "Yesterday I worked on ...": it announces the subject instead of
landing it, which is why `banned_openings` rejects it.
