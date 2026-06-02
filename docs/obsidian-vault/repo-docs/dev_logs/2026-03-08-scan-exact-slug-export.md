---
title: Scan Exact Slug Export
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-03-08_scan_exact_slug_export.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log: Scan Exact Slug Export

## Date

2026-03-08

## Summary

Added a small operator-UX patch to `scan-gate2-candidates`:

- new `--watchlist-out PATH` flag
- writes one exact market slug per line for the shown ranked candidates
- keeps the terminal ranking table and ranking logic unchanged

## Why

The scan table intentionally truncates long slugs for readability. Operators
needed a copy-safe path to move top candidates into `watch-arb-candidates`
without retyping or guessing the missing tail of a slug.

## Validation

- added CLI tests covering exact untruncated export
- added CLI test confirming default output still works unchanged
- `pytest -q tests/test_gate2_candidate_ranking.py`
