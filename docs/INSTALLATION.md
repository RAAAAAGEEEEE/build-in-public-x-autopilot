# Installation

Related: [CONFIGURATION](CONFIGURATION.md), [USAGE](USAGE.md),
[TROUBLESHOOTING](TROUBLESHOOTING.md).

## Requirements

- Python 3.9 or newer (the code uses `zoneinfo`). No dependencies to install.
  Verified with Python 3.11.
- On Windows, the `zoneinfo` module may need the `tzdata` package if your
  timezone name is not found.
- A text-generation backend: see
  [CONFIGURATION](CONFIGURATION.md#text-generation-backend).

## Install

```bash
git clone https://github.com/RAAAAAGEEEEE/build-in-public-x-autopilot
cd build-in-public-x-autopilot
cp config.example.json config.json
```

Edit `config.json` (see [CONFIGURATION](CONFIGURATION.md)). Check the install:

```bash
python3 run.py --help
```

## Getting your conversations there

The pipeline needs one Markdown file per session in a folder it can read.

**Exporting.** Any exporter works if it writes one file per session and keeps a
stable name per session, so a growing session stays the same file and the
incremental reading keeps working. A session re-exported under a new name each
time is re-read from scratch (correct, but wasteful). The reference setup
produces `claude-conversation-YYYY-MM-DD-<session id>.md` with a
`Date: YYYY-MM-DD HH:MM` header line inside. File names containing
`YYYY-MM-DD` or `YYYYMMDD` are recognised for `--date`.

**Getting them to the machine that runs this.** If you code on a laptop and run
this on a server, files must travel:

- a sync tool (Syncthing, Dropbox, `rsync` on a timer);
- a `git` repository of your exports, pulled before the run;
- nothing, if you code on the same machine: point `conversations_dir` at the
  export folder.

Do not order or select files by modification time. Sync tools rewrite files in
bulk, so every modification time collapses to the moment of the sync.

## Schedule (optional)

Run once a day. With `publish_previous_day: true` the draft is labelled with
the previous day. Example crontab line (Linux/macOS):

```cron
0 12 * * * cd /path/to/build-in-public-x-autopilot && /usr/bin/python3 run.py --config config.json >> run.log 2>&1
```

The exact minute does not matter: the run reads new material, not a schedule.
