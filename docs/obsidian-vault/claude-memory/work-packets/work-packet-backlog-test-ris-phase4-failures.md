---
title: "Backlog — 3 pre-existing test_ris_phase4_source_acquisition failures"
type: work_packet
status: draft
source_zone: claude_memory
last_updated: 2026-06-01
lifecycle: draft
tags: [work-packet, backlog, ris, academic, tests, tech-debt]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Backlog — 3 pre-existing `test_ris_phase4_source_acquisition` failures

**Status: BACKLOG (deferred).** Logged during Wallet-Ingestion v1 (2026-06-01) per operator instruction.
NOT to be fixed in that sprint — unrelated to wallet ingestion.

## The failing tests
`tests/test_ris_phase4_source_acquisition.py::TestEndToEnd`:
- `test_ingest_external_arxiv_fixture`
- `test_ingest_external_with_cache`
- `test_ingest_external_metadata_canonical_ids_preserved`

## Evidence they are pre-existing
- Present on the clean tree at `c249ff5` (before the Wallet-Ingestion sprint) — verified via `git stash`.
- They are the ONLY failures in the full suite as of 2026-06-01: **5355 passed, 1 skipped, 3 failed**.
- Domain is the academic external-source-acquisition / arXiv-fixture / Marker gate path — no overlap with
  wallet discovery, scan queue, dossier supersede, scheduler, watchlist, or MVF.

## Scope (when picked up)
1. Reproduce + capture the failure mode (assertion at `test_ris_phase4_source_acquisition.py:557` etc.).
2. Determine whether it is a stale fixture, a Marker/academic-gate behavior change, or a real regression in
   the academic acquisition path.
3. Fix or re-baseline the tests; confirm full suite green.

## Definition of Done
- [ ] Root cause identified (fixture vs gate vs code).
- [ ] Tests pass or are correctly re-baselined; full suite green.

## Cross-References
- Dev log: `docs/dev_logs/2026-06-01_wi-validation-fix.md`
- Sprint STATUS: `docs/dev_logs/2026-05-31_wallet-ingestion-sprint-STATUS.md`

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
