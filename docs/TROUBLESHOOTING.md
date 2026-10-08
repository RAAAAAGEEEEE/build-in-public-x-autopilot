# Troubleshooting

Related: [CONFIGURATION](CONFIGURATION.md), [USAGE](USAGE.md),
[ARCHITECTURE](ARCHITECTURE.md).

| Symptom | Cause | Fix |
|---|---|---|
| `no LLM provider answered`, exit code 2, log line says the wrapper was not found | The external generation wrapper is missing at the path in `CLAUDE_CALL` | See [Text generation backend](CONFIGURATION.md#text-generation-backend) |
| `no new material ... nothing to do`, exit 0 | Nothing was added since the last real run, or the new text is under 3,000 characters per file | Expected. To rebuild an old day: `--date YYYY-MM-DD` |
| `no new material`, first run | On a first run only files from the last 2 days are read | Export recent sessions, or use `--date` |
| `conversations folder not found`, exit 1 | `conversations_dir` wrong, or the sync has not arrived | Check the path; the alert names it |
| `config: conversations_dir is required` | Key missing or empty | Edit `config.json` |
| `every conversation ... was filtered out as noise` | Content judged as noise by ingestion | Check the exports are real conversations |
| `no draft passed the checks`, exit 3 | The model broke a rule on every attempt | Read the alert (it lists failures and the last text); adjust `persona` or `rules`, raise `candidates` |
| Draft flagged `[REVIEW: unverified claim: ...]` | The verifier found a claim the source does not support | Edit or drop that claim; it is delivered flagged on purpose |
| Posted text contained a header or link | Copied from the wrong message | The post is sent alone; copy only the message that is the post |
| Second run produced nothing | Incremental by design | See [ARCHITECTURE](ARCHITECTURE.md#do-not-select-conversations-by-date) |
| Want to start over | | Delete the file at `manifest_path` |
| `ZoneInfoNotFoundError` | Missing timezone database (common on Windows) | `pip install tzdata`, or use a valid IANA `timezone` |
| "Open in X" button asks for login on iOS | Telegram's in-app browser | See [USAGE](USAGE.md#delivery-rules) |
