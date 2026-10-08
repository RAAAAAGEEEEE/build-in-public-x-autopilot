# build-in-public-x-autopilot

Turn your AI coding conversations into a daily "build in public" post draft,
checked by a script and fact-checked against its source, then sent to you for
review. **It never publishes anything**: there is no posting code in this
repository, on purpose.

- **Problem solved:** you already explain your work to an AI all day; that
  transcript is the raw material of a post, but models invent facts and write
  like a changelog.
- **For:** solo builders who post about their work on X and want a reviewed
  draft each day, not an autopilot.
- **Value:** deterministic checks (`pipeline/checks.py`) plus a second model
  that verifies every claim against the source.
- **Status: alpha.** A personal tool, published as-is. Text generation depends
  on an external wrapper script that is **not** in this repository (see
  [Limitations](#limits) and [docs/LIMITATIONS.md](docs/LIMITATIONS.md)).

## How it works (Comment ça marche)

For a beginner, in three steps:

1. **Get the code.** `git clone https://github.com/RAAAAAGEEEEE/build-in-public-x-autopilot`,
   then `cd build-in-public-x-autopilot`.
2. **Create your config.** Copy `config.example.json` to `config.json` and set
   `conversations_dir` (the folder holding your exported conversations, one
   `.md` file per session) and `persona` (who reads you, what you build).
3. **Run it.** `python3 run.py --config config.json`. Add `--dry-run` to see the
   draft without delivering or recording anything.

The draft arrives on stdout or in Telegram. You read it, copy what you like,
and post it yourself.

## Prerequisites

- Python 3.9 or newer, no third-party packages.
- A folder of exported conversations in Markdown (see
  [docs/INSTALLATION.md](docs/INSTALLATION.md)).
- The external LLM wrapper script described in
  [docs/CONFIGURATION.md](docs/CONFIGURATION.md#text-generation-backend).

## Quickstart

```bash
git clone https://github.com/RAAAAAGEEEEE/build-in-public-x-autopilot
cd build-in-public-x-autopilot
cp config.example.json config.json   # edit conversations_dir and persona
python3 run.py --config config.json --dry-run
```

Expected output when the generation backend is missing (verified on
2026-10-05, exit code 2): a corpus line, then an alert.

```
corpus: 8664 chars from 1 conversation(s)
[pipeline failed] no LLM provider answered
```

With a working backend, `--dry-run` prints `--- draft for <date> ---` followed
by the post text. Details: [docs/USAGE.md](docs/USAGE.md).

## Architecture in brief

Six stages: ingest (no model, takes only material added since the last run),
judge the subject, write, mechanical checks with retry, factual verification,
deliver. Details and design rationale:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Configuration

One JSON file (`config.example.json`): conversations folder, persona,
language, optional Telegram, rule thresholds. Full reference:
[docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Security and privacy

Your conversation exports may contain paths and credentials; their content is
sent to the model backend. `config.json` may hold a Telegram bot token and is
gitignored. See [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md)
and [SECURITY.md](SECURITY.md).

## Limits

- It will not publish for you, and will not make a boring day interesting.
- Generation requires an external wrapper that is not included.
- The checks reduce, but do not remove, the need to read the draft.

Full list: [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

## Roadmap (non-binding)

- Make the generation backend configurable instead of a fixed path.
- Add tests for the checks and the ingestion stage.

## Documentation

| Document | Content |
|---|---|
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Install, getting conversations to the machine, scheduling |
| [docs/USAGE.md](docs/USAGE.md) | Command line, delivery rules, two languages |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Every config key, the checks, the generation backend |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Pipeline, design decisions, history |
| [docs/OPTIONAL_IMAGE_WORKFLOW.md](docs/OPTIONAL_IMAGE_WORKFLOW.md) | Manual workflow to attach an illustration |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | Symptoms and fixes |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | What it does not do |
| [docs/PRIVACY_AND_SECURITY.md](docs/PRIVACY_AND_SECURITY.md) | Data flows, secrets |
| [CHANGELOG.md](CHANGELOG.md) | History by date |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
