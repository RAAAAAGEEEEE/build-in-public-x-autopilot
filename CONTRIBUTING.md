# Contributing

Thanks for considering a contribution. This is a small personal tool; issues
and focused pull requests are welcome.

## Principles

- **The tool never publishes.** Pull requests adding automatic posting to X or
  anywhere else will not be accepted.
- **Deterministic first.** Prefer a script check over another model call.
- **Every rule has a story.** A new check should name the real failure that
  motivated it, as the existing ones do in `pipeline/checks.py`.
- No dependencies beyond the Python standard library.

## Checks before a pull request

There is no automated test suite. Run these and report the output:

```bash
python -m py_compile run.py pipeline/__init__.py pipeline/checks.py pipeline/deliver.py pipeline/generate.py pipeline/ingest.py pipeline/providers.py
python run.py --help
```

For a behaviour change, also run `python run.py --config <your config> --dry-run`
on a small folder of exports (this needs a working generation backend, see
[docs/CONFIGURATION.md](docs/CONFIGURATION.md#text-generation-backend)).

## Documentation

Update the relevant document in the same commit as the change. A new
configuration key updates `config.example.json` and
[docs/CONFIGURATION.md](docs/CONFIGURATION.md). Only document commands you
have actually run. Add an entry to [CHANGELOG.md](CHANGELOG.md).

## Never commit

`config.json`, `drafts/`, `state/`, conversation exports, tokens, personal
paths or names of private projects.
