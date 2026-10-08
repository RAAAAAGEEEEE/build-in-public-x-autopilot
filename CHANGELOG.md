# Changelog

Dated entries (the project has no version tags). Newest first.

## 2026-10-05

### Documentation
- README shortened; technical detail moved to `docs/`.
- Added CHANGELOG, CONTRIBUTING, SECURITY and the `docs/` set.
- Documented that the free-tier cascade is gone and that text generation
  depends on an external wrapper not included in the repository.

## 2026-08-07

### Changed (breaking)
- Free-tier provider cascade removed: all model calls go through one external
  subscription wrapper, or fail cleanly. The `keys` setting is now ignored.
- The subscription model is used first, ahead of the free tiers (intermediate
  step, same day).

## 2026-07-31

- README uses the repository's actual name.
- Documented the optional Claude Code image and compose workflow.

## 2026-07-30

- The preview window, not the length, is the constraint (`preview_chars`).
- Read new material since the last run instead of yesterday's files
  (`manifest_path`).
- Initial commit: build-in-public post drafts from AI conversations.
