# PMXT Deliverable C - Re-review After Retrieval Fix

Date: 2026-04-22
Reviewer: Codex
Scope: Re-review Deliverable C after the retrieval-fix pass to determine whether it now meets the original acceptance bar.

## Files read

- `packages/research/ingestion/claim_extractor.py`
- `packages/research/ingestion/retriever.py`
- `tests/test_research_extract_claims_cli.py`
- `tests/test_knowledge_store.py`
- `tests/test_ris_query_spine.py`
- `docs/external_knowledge/*.md`
- `docs/dev_logs/2026-04-22_deliverable-c_impl.md`
- `docs/dev_logs/2026-04-22_deliverable-c_retrieval-fix.md`
- `docs/CURRENT_DEVELOPMENT.md`

## Commands run

1. `git status --short`
   - Result: dirty worktree present before review, including `docs/CURRENT_DEVELOPMENT.md`, `docs/external_knowledge/`, deliverable C dev logs, and large unrelated `docs/obsidian-vault` churn.

2. `git log --oneline -5`
   - Result:
     - `2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)`
     - `5962d46 docs(simtrader): PMXT Deliverable B docs close-out`
     - `efb6f01 feat(simtrader): PMXT Deliverable B -- merge-ready sports strategies`
     - `504e7b7 Fee Model Overhaul`
     - `42d9985 docs: add AGENTS.md and CURRENT_DEVELOPMENT.md for workflow refresh`

3. `python -m polytool --help`
   - Result: CLI loaded successfully.

4. Official retrieval rerun:
   - `python -m polytool rag-query --question "Polymarket maker rebate formula" --hybrid --knowledge-store default`
   - `python -m polytool rag-query --question "sports VWAP prediction market" --hybrid --knowledge-store default`
   - `python -m polytool rag-query --question "SimTrader queue position" --hybrid --knowledge-store default`
   - `python -m polytool rag-query --question "Jaccard Levenshtein market matching" --hybrid --knowledge-store default`
   - `python -m polytool rag-query --question "cross-platform price divergence" --hybrid --knowledge-store default`
   - Result:
     - Q1: 0 top-5 `external_knowledge` hits
     - Q2: 0 top-5 `external_knowledge` hits
     - Q3: 0 top-5 `external_knowledge` hits
     - Q4: 0 top-5 `external_knowledge` hits
     - Q5: 1 `external_knowledge` hit at rank 2, but it is the old frontmatter-derived v1 claim

5. SQLite inspection of the live KnowledgeStore:
   - `select actor, count(*) from derived_claims group by actor order by actor`
   - Result: `[('heuristic_v1', 74), ('heuristic_v2_nofrontmatter', 72)]`

6. SQLite substring checks:
   - Query for `%simtrader queue position%` and `%jaccard levenshtein%`
   - Result:
     - `abca38edab90`, `heuristic_v2_nofrontmatter`, body claim for SimTrader queue position
     - `f262eab60821`, `heuristic_v2_nofrontmatter`, body claim for Jaccard Levenshtein market matching
   - Query for `%cross-platform price divergence%`
   - Result:
     - only `f87b13e18efa`, `heuristic_v1`, frontmatter-derived claim
   - Query for `%polymarket maker rebate formula%` or `%sports vwap prediction market%`
   - Result: no matches

7. Targeted test run:
   - `pytest -q tests/test_research_extract_claims_cli.py tests/test_knowledge_store.py tests/test_ris_query_spine.py -x --tb=short`
   - Result: `78 passed in 0.95s`

## Decisions made

- Treat the retrieval-fix pass as successful for frontmatter stripping and claim regeneration.
- Do not treat Deliverable C as complete because the live acceptance rerun still fails the original bar.
- Do not modify `docs/CURRENT_DEVELOPMENT.md` in this review-only session; record the mismatch instead.

## Review findings

1. Blocking: Deliverable C still fails the live acceptance bar.
   - The five official `rag-query` checks still do not produce 2/5 top-5 hits from real body-derived `external_knowledge` claims.
   - Live rerun result: 0/5 body-driven hits, 1/5 total hit, and that lone hit is still the frontmatter-derived v1 claim for Q5.

2. Blocking: `docs/CURRENT_DEVELOPMENT.md` is no longer truthful about Deliverable C.
   - The file still marks Deliverable C as `COMPLETE` and cites the superseded completion-pass framing, while the retrieval-fix log and the live rerun both support `NOT COMPLETE`.

3. Non-blocking documentation accuracy issue:
   - `docs/dev_logs/2026-04-22_deliverable-c_retrieval-fix.md` understates the provisional status of the seeded corpus and incorrectly describes `cross_platform_price_divergence_empirics.md` as `confidence_tier: COMMUNITY`; the current file frontmatter is `confidence_tier: PRACTITIONER`.

## Open blockers

- `packages/research/ingestion/retriever.py` still truncates enrichment to `top_k * 4` before applying `text_query`, so matching v2 claims can be excluded before substring filtering.
- Q1 and Q2 still have no body claims containing the official query strings.
- Q5 still only matches a frontmatter-derived v1 claim.

## Provisional docs status

Broadly, all seven `docs/external_knowledge/*.md` documents remain provisional in the corpus sense because they all carry `validation_status: UNTESTED` and a `source_quality_caution` block.

The two docs that remain especially caution-heavy for deliverable-C retrieval discussion are:

- `docs/external_knowledge/cross_platform_market_matching.md`
- `docs/external_knowledge/cross_platform_price_divergence_empirics.md`

## Final verdict

Deliverable C is NOT COMPLETE under the original acceptance bar.
