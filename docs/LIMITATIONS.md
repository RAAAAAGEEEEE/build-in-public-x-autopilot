# Limitations

Related: [README](../README.md), [PRIVACY_AND_SECURITY](PRIVACY_AND_SECURITY.md),
[CONFIGURATION](CONFIGURATION.md).

## What this will not do

- **It will not publish for you.** By design: automated publishing is the one
  mistake you cannot take back, and the cost of being wrong is public. No
  posting code exists in the repository.
- **It will not make a boring day interesting.** The judge scores subjects on
  tension, discovery and whether a stranger could follow them. Some days score
  low on all three; the honest output is a flat post.
- **It will not keep your secrets for you.** Conversation exports contain
  paths, file names, sometimes credentials. The checks strip identifiers from
  the draft, but you must read what you are about to post.
- **It is not a guarantee of truth.** The verifier is a model: it lowers the
  risk of invented claims, it does not remove it. If the verifier is
  unavailable, the draft passes unverified (the log says so).

## Technical limits

- **Generation backend not included.** Model calls need an external wrapper
  script at a path fixed in `pipeline/providers.py`. Without it the tool cannot
  produce a draft (exit code 2). See
  [CONFIGURATION](CONFIGURATION.md#text-generation-backend).
- **The free-tier cascade is gone.** Older notes about free providers are
  historical; see [ARCHITECTURE](ARCHITECTURE.md#history-the-removed-free-tier-cascade).
- **Incremental, not idempotent by day.** Two runs in a row: a post, then
  nothing.
- **Markdown exports only** (`*.md`), one file per session.
- **Truncation of long input.** At most 14,000 characters per conversation and
  40,000 in total reach the writer; the longest are trimmed from the front.
- **No automated tests** are shipped. Only the manual checks listed in
  [CONTRIBUTING](../CONTRIBUTING.md).
- **X only** as a target; Telegram or stdout as delivery.
- **Image attachment is manual**: [OPTIONAL_IMAGE_WORKFLOW](OPTIONAL_IMAGE_WORKFLOW.md).
