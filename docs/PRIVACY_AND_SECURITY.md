# Privacy and security

Related: [SECURITY](../SECURITY.md), [CONFIGURATION](CONFIGURATION.md),
[LIMITATIONS](LIMITATIONS.md).

## What data goes where

| Data | Goes to | When |
|---|---|---|
| New material from your conversation exports (up to 40,000 characters per run) | The text-generation backend configured in `pipeline/providers.py` | Every run that finds new material, including `--dry-run` |
| The draft (and its translation) | Telegram, if `telegram.*` is set; otherwise stdout | Real runs; `--dry-run` prints to stdout only |
| Failure alerts, which can include the last rejected draft | The same channel as drafts | On aborts |
| Draft JSON files | Local disk, `drafts/` | Real runs |
| Consumption manifest (file names and character counts) | Local disk, `state/consumed.json` | Real runs |

Nothing is published to X by this code. The "Open in X" button is a link that
you open yourself.

## Secrets

- `config.json` can hold a Telegram bot token and chat id. It is listed in
  `.gitignore`; never commit it. `config.example.json` holds no value.
- The `keys` entries are obsolete and ignored; leave them empty.
- Conversation exports often contain paths, file names and sometimes
  credentials. They are sent to the backend as input. Strip or exclude
  sensitive sessions from `conversations_dir`.
- The checks remove internal identifiers from drafts (paths, file names, hashes,
  names you list in `internal_names`), but the filter is not exhaustive: read
  every draft before posting.
- `drafts/`, `state/` and `run.log` are gitignored; they hold your own work.

## Network

The only outbound calls made by the Python code are to the Telegram Bot API
(when configured). Model calls leave through the external wrapper, whose
network behaviour is not defined by this repository.

To report a vulnerability, see [SECURITY](../SECURITY.md).
