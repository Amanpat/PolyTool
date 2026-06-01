---
title: "Work Packet — WI-2 Dossier Supersede + Schema"
type: work_packet
status: active
source_zone: claude_memory
last_updated: 2026-05-29
lifecycle: draft
tags: [work-packet, wallet-discovery, ingestion, rag, supersede]
target_agent: claude-code
acceptance_criteria:
  - See Definition of Done
---
# Work Packet — WI-2 Dossier Supersede + Schema

**Status: DRAFT — pending architect review.** Must land before WP-3 turns on frequent rescanning, or the RAG accumulates non-decaying duplicate dossier snapshots.

## Goal
On a material rescan of a wallet, retire the prior dossier's findings instead of accumulating them: add lifecycle fields to `source_documents`, supersede the prior wallet dossier doc + its claims on changed content, register `dossier_report` in the freshness config, keep the prior interpretive report on disk as "previous results," and compress (not delete) the prior raw scan.

## Context (audit evidence)
- Changed content accumulates: `packages/research/integration/dossier_extractor.py :: ingest_dossier_findings` (lines 481-516) skips only byte-identical content; changed content creates a new source doc + new active claims, with **no supersede branch**.
- `packages/polymarket/rag/knowledge_store.py :: _init_schema` (lines 139-149): `source_documents` has no lifecycle/superseded fields; `derived_claims` (lines 151-167) already has `lifecycle` + `superseded_by`.
- `config/freshness_decay.json` has no `dossier_report` family → dossier claims treated as timeless (never decay).
- Dossier artifacts written fresh per run: `packages/polymarket/llm_research_packets.py :: build_dossier_dir` / `export_user_dossier`.

## Scope
1. **Schema.** Add `lifecycle` (active|superseded), `superseded_by`, and supersede timestamp to `source_documents`. Provide a forward migration (existing rows default to active).
2. **Supersede logic.** In `ingest_dossier_findings`, when ingesting changed content for a wallet/source identity that already has an active dossier source doc, mark the prior source doc superseded (set `superseded_by` → new doc id) and **cascade**: mark the prior doc's `derived_claims` superseded (reuse existing claim lifecycle fields). Identity is the wallet/source, NOT the content hash.
3. **Query exclusion.** Default retrieval (`query_claims` and any source-doc lookups) excludes superseded source docs and superseded claims, consistent with how `query_claims` already excludes archived/superseded claims.
4. **Freshness.** Add a `dossier_report` family to `config/freshness_decay.json` with a finite decay window (propose 120 days; operator-tunable) so dossier claims age rather than counting as timeless.
5. **Disk retention.** On rescan: copy the prior run's interpretive report (memo) into the new run directory as `previous-results.md`; gzip the prior raw scan directory; do not hard-delete.

## Steps
1. Schema migration + defaults.
2. Supersede branch on changed-content re-ingest (wallet/source identity keyed).
3. Cascade supersede to prior claims.
4. Query-path exclusion of superseded source docs.
5. Freshness config entry for `dossier_report`.
6. Disk retention (previous-results copy + gzip prior raw).
7. Tests for the changed-content lifecycle (the audit flagged this test is missing) + dev log.

## Definition of Done
- [x] Rescan with changed content leaves exactly one active dossier source doc + active claim set per wallet. — wallet-level supersede-on-new-run model (sections are conditional, so wallet-level not (wallet,section)).
- [x] Prior source doc + claims marked superseded, linked via `superseded_by`, excluded from default retrieval. — source-doc query exclusion mirrors `query_claims`; cascade by `source_document_id` FK.
- [x] Identical-content re-ingest still skipped (unchanged behavior). — content_hash skip preserved.
- [x] `previous-results.md` present in the new run dir; prior raw scan compressed, not deleted. — success-gated `_retain_prior_runs`; prior dir located via superseded docs' `metadata_json.dossier_path`.
- [x] `dossier_report` decays per freshness config. — `dossier_report: 4` (months ≈ 120d); confirmed LIVE knob (consumed by `query_claims`→`compute_freshness_modifier`).
- [x] Changed-content lifecycle test added; dev log written. — `tests/test_ris_dossier_supersede.py` (14 tests incl. missing-section, atomicity, normalization, migration-idempotency, live-DB guard).

**COMPLETED 2026-05-31.** Commit `ef82b10` (code) + hardening commit. Touched-surface tests 94→ (now 81 in the focused guard run) pass; broader regression 971 passed / 3 PRE-EXISTING failures (verified on clean tree). Wallet normalized lowercase on write+match; single new-first transaction with rollback-on-failure; RIS mirror sync (`docs/scripts/sync-ris-mirror.py`) now excludes superseded/archived.

**⚠️ Migration gate incident (operator-acknowledged, "Accept but harden first"):** the gated `source_documents` lifecycle ALTER auto-applied to the live `knowledge.sqlite3` via a bare `KnowledgeStore()` open during an ad-hoc run (`_ensure_schema` auto-upgrades). Landed clean (additive; 151 docs / 4893 claims all `active`, 0 superseded; backup `knowledge.sqlite3.pre-wi2.2026-05-31.bak` saved). Hardening: `KnowledgeStore.__init__` now refuses the live default path under pytest (`POLYTOOL_ALLOW_LIVE_KB=1` override) + 4 guard tests.

## Acceptance Gates
1. **No data loss.** Superseded rows retained (queryable with explicit lifecycle filter); raw scans archived not deleted.
2. **Determinism.** Same inputs → same supersede outcome.
3. **Regression.** Existing dossier ingestion / knowledge-store tests pass with 0 new failures; identical-content idempotency preserved.

## Non-Goals
No change to the identical-content skip; no hard deletion of raw scans; no LLM; no changes to `claim_extractor` heuristics; no new claim types.

## Dependencies
WP-1 (consumer wires ingestion into the loop). Blocks WP-3's frequent rescanning.

## Cross-References
- [[claude-memory/work-packets/work-packet-wallet-ingestion-v1-sprint]]
- [[claude-memory/session-notes/2026-05-29-wallet-ingestion-audit-results]]

## Connections
- [[claude-memory/work-packets/_index]]
- [[index|Vault Home]]
