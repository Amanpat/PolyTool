---
title: Wi Validation Fix
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-06-01_wi-validation-fix.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# 2026-06-01 — WI Validation Fix: dossier ingest persistence + no-silent-success

**Sprint:** Wallet-Ingestion v1 (post-WI-4 live validation)
**Status:** COMPLETE. Fix committed (`ae4947d`); live two-pass supersede re-validation PASS.

## What this addresses

The live two-pass supersede validation (the v1 proof) was blocked: the
scan → dossier → RIS ingest step **silently persisted nothing for realistic
(memo-bearing) wallets**, while the worker reported `completed`. Root cause was
two interacting defects (full diagnosis in the sprint STATUS log).

## Root cause

1. **DEFECT 1 — pre-existing extractor heuristic.** `PlainTextExtractor.extract`
   (`packages/research/ingestion/extractors.py`) treats any raw-text string
   containing `/` or `\` as a (missing) file path and raises `FileNotFoundError`.
   Dossier **memo** bodies contain `/` → throw. (`extractors.py` is untouched by
   this sprint.)
2. **DEFECT 2 — WI-2 silent total-rollback.** `ingest_dossier_findings` wraps a
   wallet's findings in ONE transaction with a broad `except: rollback-all` that
   swallowed the error non-fatally. The memo's exception rolled back the WHOLE
   wallet (incl. good Detectors/Candidates), and the worker reported success with
   zero persisted. The WI-1 "smoke PASS" was a false positive (its wallet had no
   substantive memo → only 2 slash-free findings ingested).

## Fix (per operator decision)

- **DEFECT 1 — Option A (explicit flag, not temp-file):** added a `raw_text: bool`
  kwarg to `PlainTextExtractor.extract`. When `True`, the file-probe AND the
  content-sniffing heuristic are skipped and `source` is treated as a literal
  body. `ingest_dossier_findings`'s `pipeline.ingest(...)` now passes
  `raw_text=True`. The shared `/`→path heuristic is **unchanged** for every
  other caller.
- **DEFECT 2 — mandatory no-silent-success:**
  - `ingest_dossier_findings` logs the rollback loudly (`logger.error(..., exc_info=True)`).
  - `_make_dossier_extractor._extract_and_ingest` (wallet_scan.py) now inspects
    results and **raises** when 0 of N findings persisted (all rejected/rolled back).
  - `ScanWorker.run` no longer swallows post-scan extractor errors: an ingest
    failure propagates to the failure path → the queue item is marked **failed**
    (requeue within attempt limits) and the **watchlist is NOT advanced** to
    `scanned`. The outer handler logs loudly (`exc_info`).
  - Ingest stays **all-or-nothing per wallet** (preserves WI-2's "one complete
    active set per wallet" supersede invariant) — failures are loud, NOT
    best-effort-per-section.

## Tests

- `tests/test_ris_dossier_supersede.py::TestSlashBodyIngestRegression` — a dossier
  whose memo body contains `/` ingests all 3 findings (the exact bug).
- `tests/test_scan_worker.py::...test_ingest_failure_fails_item_and_skips_watchlist_advance`
  — ingest failure marks the item failed + does NOT advance the watchlist
  (rewrote the prior `..._does_not_fail_the_queue_row` test, which encoded the
  now-reversed contract — a directed contract change, not a weakening).
- Affected suites: 105 passed (dossier + worker + wallet_scan). Broad
  ingestion/extractor slice: 1202 passed, only the 3 pre-existing
  `test_ris_phase4_source_acquisition` academic failures remain.

## Live re-validation (real wallet 0xcf609d3256f0f37f0595e5dc64012fa3a8fea6f5)

Two-pass on the live stack — all four invariants PASS (see STATUS log for the
recorded counts/ids): (a) one active set, (b) prior superseded+linked + claim
cascade, (c) mirror shows only active (superseded removed), (d) `previous-results.md`
+ gzipped prior raw on disk.

## Backlog items logged (NOT done in this sprint)

1. **Option B — remove the content-sniffing `/`→path heuristic across ALL callers**
   (with a full caller audit). The `raw_text=True` flag is the correct first step;
   the heuristic itself remains for legacy callers. Tracked as a backlog
   work-packet: `docs/obsidian-vault/claude-memory/work-packets/work-packet-backlog-extractor-slash-heuristic.md`.
2. **3 pre-existing `test_ris_phase4_source_acquisition::TestEndToEnd` failures**
   (academic arXiv-fixture ingest / marker gate). Present before this sprint
   (verified on clean tree `c249ff5`); unrelated to wallet ingestion. Logged for
   later triage — NOT to be fixed in this sprint.

## Files changed

- `packages/research/ingestion/extractors.py` — `raw_text=True` bypass.
- `packages/research/integration/dossier_extractor.py` — pass `raw_text=True`; loud rollback log.
- `tools/cli/wallet_scan.py` — `_extract_and_ingest` raises on zero-persisted.
- `packages/polymarket/discovery/scan_worker.py` — ingest failure is fatal to the item; no advance.
- `tests/test_ris_dossier_supersede.py`, `tests/test_scan_worker.py` — regression tests.

## Codex

Research-side files; not in the mandatory adversarial-review denylist → Recommended tier; not run.

## Connections

- Sprint STATUS: `docs/dev_logs/2026-05-31_wallet-ingestion-sprint-STATUS.md`
- WI-2 dossier supersede: `docs/dev_logs/2026-05-31_wi-2-dossier-supersede.md`
