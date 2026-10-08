# Usage

Related: [INSTALLATION](INSTALLATION.md), [CONFIGURATION](CONFIGURATION.md),
[OPTIONAL_IMAGE_WORKFLOW](OPTIONAL_IMAGE_WORKFLOW.md),
[TROUBLESHOOTING](TROUBLESHOOTING.md).

## Command line

```bash
# See what it would produce: delivers nothing, stores nothing, consumes nothing
python3 run.py --config config.json --dry-run

# Real run: store the draft, deliver it, then record what it consumed
python3 run.py --config config.json
```

| Option | Effect |
|---|---|
| `--config PATH` | Required. Path to the JSON configuration. |
| `--dry-run` | Print the draft; deliver nothing, store nothing. |
| `--date YYYY-MM-DD` | Rebuild from the files **named** for that day; consumes nothing. |
| `--no-verify` | Skip the factual verification pass. |
| `--image PATH` | Send an illustration with the draft (Telegram sends it with the text; stdout only prints its path). |

Exit codes: `0` success or nothing new, `1` conversations folder missing,
`2` no model answered, `3` no draft passed the checks.

A real run stores `drafts/<day>.json` (post, translation, review flags) and
updates `state/consumed.json`. Running twice in a row gives a post, then
nothing: see [ARCHITECTURE](ARCHITECTURE.md#do-not-select-conversations-by-date).

## Output example

Illustrative format of `--dry-run` (the text is made up; the layout is real):

```
--- draft for 2026-10-04 ---
<post text>
```

If verification found an unsupported claim, the header carries
`[REVIEW: unverified claim: ...]`. The draft is still delivered, flagged.

## Delivery rules

Without Telegram settings, drafts print to stdout. With them, drafts go to your
Telegram chat. One rule, learned twice: **a message meant to be copied
contains nothing but what should be copied.**

- A draft sent as `"draft for <date>\n\n<post>"` got pasted into X with the
  header. The post therefore travels alone; the date and review flags go in a
  separate message before it.
- An image prompt sent with a label got the label drawn into the picture.
- The "Open in X" button is an inline keyboard button, deliberately not a link
  in the text, so the link is not copied along with the post.
- X's compose link carries **text only**; no image can be attached that way.
  With `--image`, the picture arrives in the same Telegram message, ready to
  attach by hand.
- On iOS the button opens Telegram's in-app browser, which is not logged in to
  X: long-press and choose "Open in Safari", or set your browser under
  Telegram, Settings, Data and Storage. On desktop it works directly.

## Posting in two languages

Set `translate_to` (and optionally `translated_opening`). The approved post is
**translated**, not regenerated, so both audiences read the same story. If you
serve two audiences, pick each time slot for its own audience.

## Illustration

Attaching an illustration is a manual workflow:
[OPTIONAL_IMAGE_WORKFLOW](OPTIONAL_IMAGE_WORKFLOW.md).
