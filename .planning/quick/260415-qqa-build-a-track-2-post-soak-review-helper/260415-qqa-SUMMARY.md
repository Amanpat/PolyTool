---
phase: quick-260415-qqa
plan: "01"
subsystem: crypto-pairs
tags: [track2, paper-soak, review, cli, reporting]
dependency_graph:
  requires: []
  provides: [crypto-pair-review CLI, format_post_soak_review, load_or_generate_report]
  affects: [packages/polymarket/crypto_pairs/reporting.py, polytool/__main__.py]
tech_stack:
  added: []
  patterns: [argparse CLI entrypoint, lazy _command_entrypoint registration]
key_files:
  created:
    - tools/cli/crypto_pair_review.py
    - tests/test_crypto_pair_review.py
    - docs/dev_logs/2026-04-15_track2_post_soak_review_helper.md
  modified:
    - packages/polymarket/crypto_pairs/reporting.py
    - polytool/__main__.py
decisions:
  - "load_or_generate_report checks for existing paper_soak_summary.json first to avoid re-computation on repeated review calls"
  - "format_post_soak_review uses plain ASCII only (no Unicode) per CLAUDE.md Windows-safe output rule"
  - "feed_state_transitions value shown as stale=N, disconnect=N string (composite metric has no single float)"
metrics:
  duration_minutes: 4
  completed_date: "2026-04-15"
  tasks_completed: 3
  files_changed: 5
---

# Phase quick-260415-qqa Plan 01: Track 2 Post-Soak Review Helper Summary

**One-liner:** One-screen ASCII review command that reads paper soak artifacts and renders verdict, PnL, risk controls, and promote-band fit without opening JSON files.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Add format_post_soak_review and crypto-pair-review CLI | 783c7c9 | reporting.py, crypto_pair_review.py, __main__.py |
| 2 | Add deterministic tests for post-soak review helper | ab5f513 | tests/test_crypto_pair_review.py |
| 3 | Regression check and dev log | 8c04feb | docs/dev_logs/2026-04-15_track2_post_soak_review_helper.md |

## What Was Built

### `format_post_soak_review(report)` in reporting.py

Takes the paper-soak summary report dict and returns a plain-ASCII terminal string structured as 7 sections:

1. Header — run ID, duration, generated timestamp
2. Verdict — full verdict string, decision, decision reasons
3. Key Metrics — Net PnL, opportunities, intents, pairs, settled, symbols, cycles
4. Promote-Band Fit table — all 8 rubric metrics with band classifications
5. Risk Controls — triggered safety violations with codes and first detail
6. Evidence Floor — MET/NOT MET with FAIL lines for failing checks
7. Notes — operator notes if present

### `load_or_generate_report(run_path)` in reporting.py

Idempotent loader: reads `paper_soak_summary.json` if it already exists (fast path for re-running review on already-reported runs), otherwise calls `generate_crypto_pair_paper_report()` to produce the full report.

### `crypto-pair-review` CLI command

```
python -m polytool crypto-pair-review --run <path>          # formatted review
python -m polytool crypto-pair-review --run <path> --json   # JSON to stdout
```

Registered in `polytool/__main__.py` with a help line in the Track 2 block.

## Test Results

- `tests/test_crypto_pair_review.py`: 8 new tests, all passing
- `tests/test_crypto_pair_report.py`: 13 existing tests, all still passing
- Full suite: 2546 passed, 1 pre-existing failure (`test_gemini_provider_success` — known, unrelated)
- Zero new failures introduced

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. All sections of the review output are wired to live report dict fields.

## Threat Flags

None. This is a read-only local display tool. No network endpoints, no auth paths, no schema changes at trust boundaries.

## Self-Check

### Created files exist

- `packages/polymarket/crypto_pairs/reporting.py` — modified (format_post_soak_review and load_or_generate_report added)
- `tools/cli/crypto_pair_review.py` — created
- `polytool/__main__.py` — modified (crypto_pair_review_main registered)
- `tests/test_crypto_pair_review.py` — created
- `docs/dev_logs/2026-04-15_track2_post_soak_review_helper.md` — created

### Commits exist

- 783c7c9: feat(quick-260415-qqa): add format_post_soak_review, load_or_generate_report, and crypto-pair-review CLI
- ab5f513: test(quick-260415-qqa): add 8 deterministic tests for post-soak review helper
- 8c04feb: docs(quick-260415-qqa): add dev log for Track 2 post-soak review helper

## Self-Check: PASSED
