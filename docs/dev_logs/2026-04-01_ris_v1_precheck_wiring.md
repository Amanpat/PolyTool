# Dev Log: RIS v1 Precheck Wiring and Ledger Enrichment

**Date:** 2026-04-01
**Plan:** quick-260401-n1s
**Depends on:** quick-260401-m8y (evaluation gate + precheck runner)

## Summary

Wired two explicit stubs from `quick-260401-m8y` to real KnowledgeStore and freshness
infrastructure, enriched the precheck ledger schema to v1, added 35 offline deterministic
tests, and wrote the operator-facing feature doc.

**Stubs wired:**
- `find_contradictions()` — was `return []` hardcoded; now queries KnowledgeStore for
  CONTRADICTS relations when a store is provided.
- `check_stale_evidence()` — was a passthrough; now applies freshness decay and sets
  `stale_warning=True` when all source documents are stale.

## What Was Wired and Why

### `find_contradictions(idea, knowledge_store=None)`

The stub existed because the KnowledgeStore schema (4-table SQLite: `source_documents`,
`derived_claims`, `claim_evidence`, `claim_relations`) was already built in quick-055 but
the precheck module was designed to be independently testable without a KS dependency.

The wired implementation:
1. Returns `[]` when `knowledge_store=None` (backward compat, all 25 existing tests unaffected).
2. When a store is provided: calls `ks.query_claims(apply_freshness=False)` to get all
   active claims, then `ks.get_relations(claim_id, relation_type="CONTRADICTS")` for each.
3. Returns `claim_text` strings for any claim that has at least one CONTRADICTS relation
   (as source or target).

**Key decision — no semantic filtering:** The idea text is NOT used to filter which
contradictions are returned. Semantic matching requires embeddings, which are out of scope
for v1. The function returns ALL claims with CONTRADICTS relations as broad candidates;
the precheck prompt explicitly asks the LLM to evaluate relevance. This keeps the function
simple, deterministic, and fully testable offline.

**Import strategy:** `KnowledgeStore` is imported under a `TYPE_CHECKING` guard to avoid
circular import risk. At runtime, the `knowledge_store` parameter is duck-typed — any object
with `query_claims()` and `get_relations()` works.

### `check_stale_evidence(result, knowledge_store=None)`

The stub existed because freshness decay requires source document metadata. The wired version:
1. Returns `result` unchanged when `knowledge_store=None` (backward compat).
2. When a store is provided: queries `source_documents` directly via `ks._conn` (no public
   API for listing all source docs yet), computes `compute_freshness_modifier(source_family,
   published_at)` for each.
3. If ALL documents have `freshness_modifier < 0.5`, returns a new `PrecheckResult` with
   `stale_warning=True`. Threshold 0.5 = one full half-life for the source family.
4. If no source documents exist, returns result unchanged (no data = no penalty).

**Internal coupling note:** The `ks._conn` access is a minor internal coupling. This is
acceptable for v1 because: (a) the KnowledgeStore is a local SQLite store we own, (b) adding
a `list_source_documents()` public API would be scope creep for this task. Tracked for future
cleanup if the KS API evolves.

### `run_precheck()` wiring

Updated to accept `knowledge_store=None` kwarg:
1. Passes `knowledge_store` to `find_contradictions()`.
2. Merges returned contradictions into `result.contradicting_evidence` with deduplication
   (set-based, order preserved).
3. Passes `knowledge_store` to `check_stale_evidence()`.

Existing callers that do not pass `knowledge_store` get identical behavior — the defaults
ensure full backward compatibility.

## Ledger Schema Enrichment (v1)

`PrecheckResult` gained four new fields (all default to `""` so existing construction sites
are unaffected):

| Field | Type | Description |
|-------|------|-------------|
| `precheck_id` | str | SHA-256[:12] of idea text — deterministic, stable across re-runs |
| `reason_code` | str | STRONG_SUPPORT / MIXED_EVIDENCE / FUNDAMENTAL_BLOCKER |
| `evidence_gap` | str | Populated when contradicting_evidence empty and rec != GO |
| `review_horizon` | str | 7d (CAUTION), 30d (STOP), empty (GO) |

`LEDGER_SCHEMA_VERSION` bumped from `precheck_ledger_v0` to `precheck_ledger_v1`.
`append_precheck()` now serializes all four fields. `list_prechecks()` is unchanged —
returns raw dicts, so v0 entries naturally lack the new fields (callers use `.get()` with
defaults).

## Deferred: Lifecycle Fields

The original task spec mentioned four lifecycle fields:
- `was_overridden` — operator marked this precheck as overridden
- `override_reason` — why the precheck was overridden
- `outcome_label` — what actually happened after development completed
- `outcome_date` — when the outcome was recorded

These are NOT included in v1 for the following reasons:
1. They require an operator workflow for marking prechecks as resolved (a "precheck review"
   CLI command or similar).
2. Building outcome tracking before any prechecks have generated real outcomes is premature
   — there's nothing to track yet.
3. The ledger's append-only design means adding these fields later (as a separate update
   event type) is straightforward without a schema migration.

Deferred to a future "precheck lifecycle" task. The dev log and feature doc both document
this explicitly.

## Files Changed

| File | Change |
|------|--------|
| `packages/research/synthesis/precheck.py` | Wired stubs; added TYPE_CHECKING import; added 4 new PrecheckResult fields; run_precheck() merges KS contradictions + checks staleness + populates enriched fields |
| `packages/research/synthesis/precheck_ledger.py` | LEDGER_SCHEMA_VERSION bumped to v1; append_precheck() serializes 4 new fields |
| `tools/cli/research_precheck.py` | --json output updated to include 4 enriched fields |
| `tests/test_ris_precheck_wiring.py` | 35 new offline deterministic tests (new file) |
| `docs/features/FEATURE-ris-v1-evaluation-gate.md` | Operator-facing feature doc (new file) |

## Test Results

```
tests/test_ris_precheck_wiring.py  35 passed
tests/test_ris_precheck.py         25 passed
tests/test_ris_evaluation.py       37 passed
Total: 97 passed, 0 failed, 0 skipped
```

All tests are fully offline — no network, no LLM calls, no Chroma. KnowledgeStore uses
`:memory:` SQLite throughout. Freshness config is passed inline to avoid file I/O
dependencies in tests.

Test coverage categories:
- `TestFindContradictions` (8 tests): backward compat, KS with/without CONTRADICTS relations, deduplication, only CONTRADICTS not other relation types
- `TestCheckStaleEvidence` (7 tests): backward compat, all-stale scenario, one-fresh scenario, no source docs
- `TestRunPrecheckWiring` (3 tests): KS contradictions merged into result, stale warning flows through, no-KS backward compat
- `TestEnrichedPrecheckResult` (2 tests): dataclass construction with new fields
- `TestRunPrecheckPopulatesEnrichedFields` (9 tests): precheck_id deterministic, reason_code mapping, evidence_gap when no contradictions, review_horizon per recommendation
- `TestEnrichedPrecheckLedger` (5 tests): schema version, JSONL contains new fields, list_prechecks reads v0 entries
- `TestResearchPrecheckCLIEnriched` (1 test): --json includes all 4 enriched fields

## Codex Review

Tier: Skip (no execution, risk manager, or order-placement code touched).

## Open Questions / Follow-up

1. **KS public API for source docs:** `check_stale_evidence()` currently accesses `ks._conn`
   directly. If `KnowledgeStore` adds a `list_source_documents()` method in a future task,
   update `check_stale_evidence()` to use it.

2. **Semantic contradiction filtering:** Currently returns ALL claims with CONTRADICTS
   relations. When the knowledge base has sufficient content to make semantic filtering
   meaningful, add embeddings-based relevance filtering to `find_contradictions()`.

3. **Precheck lifecycle fields:** `was_overridden`, `override_reason`, `outcome_label`,
   `outcome_date` — deferred as documented above.
