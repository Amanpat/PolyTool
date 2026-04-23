---
date: 2026-04-22
work_packet: WP1-D
phase: RIS Phase 2A
slug: ris_wp1d_foundational_seed
---

# WP1-D: RIS Phase R0 Foundational Seed

## Scope

Execute the RIS Phase R0 foundational seed against the default local KnowledgeStore,
verify `docs_by_family.book_foundational >= 11`, and write this dev log.

Allowed write surface: default local KnowledgeStore via CLI + `docs/dev_logs/`.
No application code, scoring config, providers, external knowledge reseed, or
n8n/monitoring/infra was touched.

## Prerequisites Confirmed

- WP1-A (scoring weights): complete
- WP1-B (per-dim floors + prompt drift fix): complete (verified in
  `docs/dev_logs/2026-04-22_ris_wp1b_prompt_drift_codex_verification.md`)
- WP1-C (provider_events contract): complete
- CLI smoke: `research-seed`, `research-stats`, `research-eval`, `research-acquire` all
  visible in `python -m polytool --help`

## Pre-Seed Baseline

Command:
```
python -m polytool research-stats summary --json
```

Result:
```json
{
  "generated_at": "2026-04-22T23:41:58+00:00",
  "total_docs": 48,
  "total_claims": 146,
  "docs_by_family": {
    "academic": 16,
    "blog": 16,
    "book": 1,
    "external_knowledge": 7,
    "github": 5,
    "manual": 3
  }
}
```

Key observation: no `book_foundational` family present. `external_knowledge: 7` already
existed (WP1-E content was previously ingested in earlier sessions).

## Dry Run

Command:
```
python -m polytool research-seed --dry-run --json
```

Result:
```json
{
  "total": 11,
  "ingested": 0,
  "skipped": 0,
  "failed": 0,
  "dry_run": true,
  "reseed": false
}
```

Resolved 11 docs cleanly. Manifest used: `config/seed_manifest.json` (default).

Full doc list from dry-run detail:
1. `docs/reference/RAGfiles/RIS_OVERVIEW.md`
2. `docs/reference/RAGfiles/RIS_01_INGESTION_ACADEMIC.md`
3. `docs/reference/RAGfiles/RIS_02_INGESTION_SOCIAL.md`
4. `docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md`
5. `docs/reference/RAGfiles/RIS_04_KNOWLEDGE_STORE.md`
6. `docs/reference/RAGfiles/RIS_05_SYNTHESIS_ENGINE.md`
7. `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md`
8. `docs/reference/RAGfiles/RIS_07_INTEGRATION.md`
9. `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`
10. `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v5.md`
11. `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md`

## Seed Execution

Command:
```
python -m polytool research-seed --no-eval --json
```

Rationale for `--no-eval`:
- These are internal PolyTool reference docs (RIS RAGfiles + roadmap docs), not
  external research candidates. They do not require LLM quality scoring — the content
  is operator-authored and self-verified.
- `--no-eval` skips the evaluation gate, preventing unnecessary LLM API calls and
  ensuring the seed completes offline.
- WP1-D context fetch (`docs/dev_logs/2026-04-22_ris_wp1_context_fetch.md`) confirmed
  this is the safest current operator command: plain `research-seed` does NOT default
  to no-eval in current code despite help-text implication.

Result:
```json
{
  "total": 11,
  "ingested": 11,
  "skipped": 0,
  "failed": 0,
  "dry_run": false,
  "reseed": false
}
```

All 11 docs ingested. Extractor: `structured_markdown` for all entries.
No skips, no failures, no anomalies.

Individual doc IDs (for audit trail):

| Title | doc_id |
|---|---|
| RIS Overview | f9d5765722a6b405e1ebd77eaec5e7d6... |
| RIS Ingestion: Academic Sources | 57815260087ae0f06b07e4a277f41599... |
| RIS Ingestion: Social Sources | 869db8127e0a6322747c88daed1b2f2e... |
| RIS Evaluation Gate | 67391e2f707486053892150d48d21790... |
| RIS Knowledge Store | df4007ecb92d8c87609c3ce6337277943... |
| RIS Synthesis Engine | 108ba3338e31263aa9e1ec354e2d8f68... |
| RIS Infrastructure | 8e8e8be55c6684cca5c2d72d985888c2... |
| RIS Integration | 151c08455db548c6236e9b8e5eacacfbbb... |
| PolyTool Master Roadmap v4.2 | a0e21db31c30057cfe0dacef9b8ec748... |
| PolyTool Master Roadmap v5 | 5553a5c98753cde399d7064f8c2d71f3... |
| PolyTool Master Roadmap v5.1 | 02fd363a49c9bf3b9301c377243bdb62... |

## Post-Seed Verification

Command:
```
python -m polytool research-stats summary --json
```

Result:
```json
{
  "generated_at": "2026-04-22T23:42:14+00:00",
  "total_docs": 59,
  "total_claims": 146,
  "docs_by_family": {
    "academic": 16,
    "blog": 16,
    "book": 1,
    "book_foundational": 11,
    "external_knowledge": 7,
    "github": 5,
    "manual": 3
  }
}
```

## Success Criteria Check

| Criterion | Target | Actual | Result |
|---|---|---|---|
| `docs_by_family.book_foundational` | >= 11 | 11 | PASS |
| seed failures | 0 | 0 | PASS |
| seed skips | 0 | 0 | PASS |
| total_docs delta | +11 | 59 - 48 = +11 | PASS |

**WP1-D: COMPLETE.**

## Anomalies / Observations

None. The seed ran cleanly on the first attempt. All 11 docs resolved, all used the
`structured_markdown` extractor (appropriate for structured Markdown reference docs),
and the post-seed family count matched exactly.

One pre-existing observation (not a blocker): `total_claims` did not change (146 → 146).
This is expected: `--no-eval` skips the evaluation pipeline, so no claims are extracted.
Claims are only created via the eval gate when a document passes quality scoring. The
foundational docs are in the store and retrievable; their absence from `total_claims` is
by design for `--no-eval` seeds.

## WP1-E Status

Current store already has `external_knowledge: 7`, which covers the five WP1-E target
docs plus two extras (Kalshi Fee Structure, Cross-Platform Market Matching). WP1-E was
previously seeded in an earlier session. No action required.

**Recommendation:** WP1-E is already satisfied. It does not need a reseed pass. If
reproducibility verification is desired in a future session, use:
```
python -m polytool research-seed --manifest config/seed_manifest_external_knowledge.json --no-eval --reseed --json
```
But this is optional — the acceptance criterion (5+ external docs in store) is already met.

## Codex Review

Tier: Skip. No application code was modified. CLI-only operator execution.
No review required per CLAUDE.md policy.

## Next Steps

- WP1: Foundation fixes — all items now complete:
  - [x] WP1-A: scoring weights
  - [x] WP1-B: per-dim floors + prompt drift fix
  - [x] WP1-C: provider_events contract
  - [x] WP1-D: R0 seed 11+ docs (this work packet)
  - [x] WP1-E: 5 open-source docs seeded (already satisfied in store)
- WP2 (cloud LLM providers: Gemini, DeepSeek, OpenRouter, Groq) is now unblocked.
