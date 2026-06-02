---
title: Academic Wp2 Speed Observability
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-23_academic-wp2-speed-observability.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic RIS WP-2: Speed / Observability Hardening

**Date:** 2026-05-23
**Status:** SHIPPED

## Objective

Operators can see prefetch/parse/index/query progress, timeout-risk papers are classified
clearly, JIT cache persistence is measured, and docs no longer imply the 29-paper rerun is
ready.

## Changes Shipped

### `packages/research/ingestion/marker_queue.py`

- Added constants after `_ARXIV_ID_RE`:
  - `_TIMEOUT_RISK_ARXIV_IDS` — frozenset of three known timeout-risk arXiv IDs
  - `_FILE_SIZE_TIMEOUT_BUCKETS` — `(≤600KB → 3600s, ≤1500KB → 7200s)`
  - `_FILE_SIZE_TIMEOUT_DEFAULT` = 14400.0 (>1500 KB)
  - `_VALID_INGEST_TIERS` = `{2, 3}`
- Added `auto_timeout_from_file_size(file_size_bytes: int) -> float`
- `enqueue()` now accepts `ingest_tier: int = 2`; raises `ValueError` for tiers not in `{2, 3}`
- `get_status_report()` gains three new fields:
  - `sidecar_count` — count of `.body.txt` files in `bodies/`
  - `indexed_count` — count of entries in `indexed.jsonl`
  - `timeout_risk_items` — per-pending-paper timeout/tier risk profile

### `tools/cli/research_marker_queue.py`

- `--tier {2,3}` argument wired to enqueue subparser
- `--auto-timeout` flag on warm-process: computes MAX timeout across all pending papers using
  their prefetch manifest file sizes (conservative: one IPC worker processes the whole batch)
- `jit-cache-check` subcommand: step-by-step operator diagnostics for TRITON_CACHE_DIR / 
  TORCHINDUCTOR_CACHE_DIR persistence; optionally outputs JSON; lists known risk papers
- Fixed f-string SyntaxError in `_cmd_jit_cache_check` (`!r or` is invalid; replaced with
  `repr(...) if ... else`)

### `docs/CURRENT_STATE.md`

- Section "29-paper rerun" updated: was "Safe to proceed." Now states NOT YET READY with
  explicit blockers (JIT persistence unconfirmed, three timeout-risk papers need Tier-3
  handling)

### `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`

- Corpus status section: removed "full 29-paper rerun can proceed" language; replaced with
  WP-2 blockers and checklist
- Performance table: dense math/ML paper row now shows 33–55 min (observed 1975s–3279s)
  plus JIT cold-start note (27–50 min for new format groups)
- Failure classes table: added `cache_missing`, `parse_error`, and sidecar/indexed gap rows
- New section: "JIT Cache Persistence (WP-2 — UNRESOLVED)" — background, diagnostic commands,
  timeout-risk papers table

### `tests/test_ris_marker_queue.py`

New test classes (26 tests total):

- `TestAutoTimeoutFromFileSize` (6 tests): boundary values for all three file-size buckets
- `TestEnqueueIngestTier` (7 tests): default tier=2, tier=3 accepted, tier=0/1 raise
  ValueError, CLI `--tier 3` accepted, CLI invalid tier exits nonzero
- `TestStatusReportWP2` (8 tests): sidecar_count, indexed_count, timeout_risk_items fields
- `TestCLIJitCacheCheck` (5 tests): `--help` presence, exit code 0, TRITON mention, risk
  paper list, JSON output keys

## Test Results

```
tests/test_ris_marker_queue.py: 170 passed, 1 skipped
Full suite: 3324 passed, 1 skipped (pre-existing failure in test_ris_phase4_source_acquisition)
```

The pre-existing failure (`test_ingest_external_arxiv_fixture`) is unrelated to WP-2:
a Phase 4 fixture uses `body_source='abstract'` which the academic_marker_gate rejects.
Confirmed pre-existing by running on stash (same failure without WP-2 code).

## Bug Fixes During Development

1. `test_zero_bytes_returns_default`: 0 bytes falls in the ≤600KB bucket (returns 3600s, not
   default 14400s). Callers guard `file_size > 0` separately. Test corrected.
2. F-string SyntaxError: `f"... {val!r or '(not set)'}"` is invalid Python. Fixed to
   `f"... {repr(val) if val else '(not set)'}"`.
3. `test_cli_invalid_tier_exits_nonzero`: argparse exits with code 2 for invalid `choices`,
   not 1. Changed assertion to `assert code != 0`.
4. Windows NTFS colon restriction: `arxiv:2604.24366.body.txt` cannot be created as a regular
   file on NTFS (colons denote alternate data streams). Test helper uses
   `arxiv_2604.24366.body.txt` instead (glob counts any `*.body.txt`).
5. `_make_queue_with_done_item` wrote only to `results.jsonl`; `get_status_report` reads
   `queue.jsonl` for status. Fixed helper to update `queue.jsonl` via `_write_queue`.

## Open Blockers (WP-2 Not Closed)

- **JIT cache persistence UNRESOLVED**: `TORCHINDUCTOR_CACHE_DIR` confirmed empty after batch
  runs. `TRITON_CACHE_DIR` not yet tested. Run `jit-cache-check` before starting the 29-paper
  batch and follow diagnostic steps in the runbook.
- **Three timeout-risk papers require Tier-3 and operator approval** before batch inclusion:
  - `arxiv:1011.6402` — timeout confirmed at 3600s
  - `arxiv:2307.14129` — 2947s observed
  - `arxiv:2409.02025` — HTTP 429 / fetch failures

## Codex Review

Tier: Skip (docs, tests, CLI formatting, no execution-path code changes). No adversarial
review required.
