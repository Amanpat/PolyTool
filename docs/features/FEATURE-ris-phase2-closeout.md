# RIS Phase 2 Closeout

**Date:** 2026-04-09
**Spec:** docs/specs/SPEC-ris-phase2-operational-contracts.md
**Roadmap:** docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md

---

## Scope Completed

RIS Phase 2 delivered the weighted composite evaluation gate, fail-closed scoring,
novelty/dedup detection, review queue storage and CLI, per-priority acceptance thresholds,
cloud provider routing (Gemini + DeepSeek with offline-safe mocking), segmented retrieval
benchmark metrics by query class, Phase 2 monitoring fields in health/stats CLIs, real
implementation of the model_unavailable health check (replacing a stub), n8n unified alert
and summary paths, and all requisite tests (307 tests across 10 Phase 2 test files, all
passing). Development was conducted across 6 implementation dev logs on 2026-04-08.

---

## Acceptance Matrix

| # | Contract Item | Status | Evidence | Notes |
|---|---------------|--------|----------|-------|
| 1 | Fail-closed evaluation | PASS | `test_ris_phase2_weighted_gate.py` (51), `test_ris_phase2_cloud_provider_routing.py` (8); `2026-04-08_ris_phase2_eval_gate_core.md` | Two independent fail-closed paths: parse_scoring_response() and DocumentEvaluator try/except |
| 2 | Weighted composite gate | PASS | `test_ris_phase2_weighted_gate.py` (51); `config/ris_eval_config.json`; `2026-04-08_ris_phase2_eval_gate_core.md` | weights {rel:0.30, nov:0.25, act:0.25, cred:0.20}; floors {rel>=2, cred>=2}; thresholds {P1:2.5, P2:3.0, P3:3.2, P4:3.5} |
| 3 | Novelty/dedup detection | PASS | `test_ris_evaluation.py` (41); `packages/research/evaluation/dedup.py`; `evaluator.py` | Hard-stops (canonical ID) run before near-dup (shingle); near-dup runs before provider scoring |
| 4 | Review queue contract | PASS with caveat | `test_ris_review_queue.py` (6), `test_ris_ingestion_integration.py` (18); `2026-04-08_ris_phase2_review_queue_cli.md`; `research-review --help` | Storage + CLI: PASS. 72-hour auto-promote/auto-reject policy: NOT IMPLEMENTED |
| 5 | Per-source daily budget caps | NOT IMPLEMENTED | `grep -rn "budget_exhausted" packages/research/` returned no matches | `config/ris_eval_config.json` has budget key with cap values; no enforcement code exists |
| 6 | Per-priority acceptance gates | PASS | `test_ris_phase2_weighted_gate.py` (51); `types.py` threshold lookup; `2026-04-08_ris_phase2_eval_gate_core.md` | P1-P4 thresholds in config; floor waived for priority_1; CLI `--priority-tier` arg on all ingest/eval commands |
| 7 | Segmented benchmark metrics | PASS | `test_rag_eval.py` (35), `test_ris_monitoring.py` (75); `docs/eval/ris_retrieval_benchmark.jsonl` (9 cases, 3 classes); `2026-04-08_ris_phase2_retrieval_benchmark_truth.md` | All 8 required metrics per ModeAggregate; factual/analytical/exploratory classes; Phase 2 monitoring fields in stats CLI |
| 8 | Env-var-primary n8n config hierarchy | PASS | `test_ris_scheduler.py` (37); `packages/research/evaluation/config.py` (30+ RIS_EVAL_* overrides); `2026-04-08_unified_n8n_alerts_and_summary.md` | n8n workflow calls Python CLI via `docker exec`; Python reads env vars first; n8n Variables not used in config hierarchy |
| 9 | Dual-layer ClickHouse write idempotency | N/A | Grep: no `ris_events`, `ReplacingMergeTree.*ris` found; RIS Operator Guide confirms SQLite-only persistence | RIS uses SQLite (KnowledgeStore), not ClickHouse; SQLite uniqueness on doc_id provides storage-level idempotency |
| 10 | Research-only posture statement | PARTIAL | `tools/cli/research_review.py` lines 3-4, 228 (PASS); `research_health.py`, `research_ingest.py`, `research_eval.py`, `research_stats.py` (absent) | Posture language in review CLI and spec docs; absent from 4 of 5 research CLI module docstrings |

---

## Commands Verified

- `python -m pytest tests/test_ris_phase2_weighted_gate.py tests/test_ris_phase2_cloud_provider_routing.py tests/test_ris_evaluation.py tests/test_ris_ingestion_integration.py tests/test_ris_research_acquire_cli.py tests/test_ris_phase5_provider_enablement.py tests/test_ris_monitoring.py tests/test_ris_review_queue.py tests/test_ris_scheduler.py tests/test_rag_eval.py -q` -- **307 passed**
- `python -m polytool research-health --json` -- runs, returns `overall_category`, 7 health checks, Phase 2 fields present
- `python -m polytool research-stats summary --json` -- runs, returns Phase 2 fields: `provider_route_distribution`, `provider_failure_counts`, `review_queue`, `disposition_distribution`, `routing_summary`
- `python -m polytool research-review --help` -- shows list/inspect/accept/reject/defer subcommands
- `python -m polytool research-eval --help` -- shows `--provider`, `--enable-cloud`, `--priority-tier` args
- `python -m json.tool config/ris_eval_config.json > /dev/null && echo "VALID JSON"` -- **VALID JSON**
- `python -c "import json; [json.loads(l) for l in open('docs/eval/ris_retrieval_benchmark.jsonl')]; print('VALID JSONL')"` -- **VALID JSONL**, 9 cases, 3 query classes

---

## Artifact Paths

- `config/ris_eval_config.json` -- gate weights, floors, thresholds, budget schema, routing defaults, provider configs
- `packages/research/evaluation/config.py` -- EvalConfig dataclass with env-var override loading
- `packages/research/evaluation/providers.py` -- Gemini + DeepSeek HTTP clients + cloud guard (RIS_ENABLE_CLOUD_PROVIDERS)
- `packages/research/evaluation/evaluator.py` -- fail-closed DocumentEvaluator with routed provider chain
- `packages/research/evaluation/types.py` -- ScoringResult with composite_score, priority_tier, reject_reason; gate property
- `packages/research/evaluation/scoring.py` -- scoring_v2 prompt template, _compute_composite(), strict parse
- `packages/research/evaluation/dedup.py` -- near-duplicate detection with shingle-based Jaccard similarity
- `packages/research/evaluation/artifacts.py` -- replay-grade provider attempt traces and routing metadata
- `packages/research/ingestion/pipeline.py` -- ACCEPT/REVIEW/REJECT/blocked disposition routing
- `packages/research/ingestion/review_integration.py` -- disposition classification helper
- `packages/polymarket/rag/knowledge_store.py` -- pending_review + pending_review_history SQLite tables
- `tools/cli/research_review.py` -- review queue CLI (list/inspect/accept/reject/defer)
- `tools/cli/research_health.py` -- 7-check health CLI with overall_category
- `tools/cli/research_stats.py` -- stats CLI with Phase 2 monitoring fields
- `docs/eval/ris_retrieval_benchmark.jsonl` -- 9-case Phase 2 retrieval benchmark suite
- `packages/polymarket/rag/eval.py` -- query_class segmentation, 8-metric ModeAggregate
- `workflows/n8n/ris-unified-dev.json` -- unified n8n pilot workflow with health/summary alerts

---

## Test Evidence

All Phase 2 test files (10 files, 307 tests total):

| Test File | Count | Covers |
|-----------|-------|--------|
| `tests/test_ris_phase2_weighted_gate.py` | 51 | Items 1, 2, 6 (composite gate, fail-closed, priority thresholds) |
| `tests/test_ris_evaluation.py` | 41 | Items 1, 2, 3 (general evaluation + dedup) |
| `tests/test_ris_ingestion_integration.py` | 18 | Item 4 (pipeline ingest disposition routing) |
| `tests/test_ris_research_acquire_cli.py` | 16 | Item 4 (acquire-path review queue) |
| `tests/test_ris_phase5_provider_enablement.py` | 20 | Items 1, 8 (cloud guard, provider enablement) |
| `tests/test_ris_phase2_cloud_provider_routing.py` | 8 | Items 1, 8 (cloud routing fail-closed) |
| `tests/test_ris_monitoring.py` | 75 | Items 7, monitoring (Phase 2 health check fields) |
| `tests/test_ris_review_queue.py` | 6 | Item 4 (queue schema, enqueue, resolve) |
| `tests/test_ris_scheduler.py` | 37 | Item 8 (scheduler + n8n job dispatching) |
| `tests/test_rag_eval.py` | 35 | Item 7 (retrieval benchmark segmentation) |
| **Total** | **307** | |

---

## Manual Validations Already Performed

The following dev logs from 2026-04-08 document manual CLI smoke tests and end-to-end
validation:

1. `docs/dev_logs/2026-04-08_ris_phase2_eval_gate_core.md` -- weighted gate + config loading;
   `pytest tests/` 3750 passed
2. `docs/dev_logs/2026-04-08_ris_phase2_cloud_provider_routing.md` -- Gemini/DeepSeek routing;
   manual smoke with `gate=ACCEPT`, `eval_provider=gemini`; mocked cloud CLI smoke passed
3. `docs/dev_logs/2026-04-08_ris_phase2_ingest_review_integration.md` -- pipeline disposition
   routing; manual `gate=ACCEPT` and `gate=REVIEW->queued_for_review` smoke; 3779 passed
4. `docs/dev_logs/2026-04-08_ris_phase2_review_queue_cli.md` -- review queue CLI smoke;
   list returns pending item with weighted_score and simple_sum_score
5. `docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md` -- health checks smoke; 75 tests
   in test_ris_monitoring.py
6. `docs/dev_logs/2026-04-08_ris_phase2_retrieval_benchmark_truth.md` -- benchmark suite
   validation; 35 tests in test_rag_eval.py

---

## Remaining Caveats / Deferred Items

### Item 5 (Per-source daily budget caps) -- NOT IMPLEMENTED

- `config/ris_eval_config.json` has `budget` key with global cap (200), per-source limits,
  and manual reserve (10).
- No enforcement code exists in `packages/research/ingestion/`, `packages/research/evaluation/`,
  or `packages/research/scheduling/`.
- Documents are NOT gated by daily budget caps during automated ingestion runs.
- Impact: automated ingestion can exceed the 200/day global cap; manual reserve is not
  protected.
- Deferred to Phase 3.

### Item 4 -- 72-hour auto-promote/auto-reject policy -- NOT IMPLEMENTED

- `pending_review` table stores queue items with `defer_until` field available.
- No scheduled job or expiry check implements auto-promotion or auto-rejection after 72 hours.
- Impact: pending items stay in the queue indefinitely without operator action.
- Deferred to Phase 3.

### Item 9 (ClickHouse idempotency) -- N/A to current architecture

- Spec anticipated ClickHouse writes for RIS events. Implemented architecture uses SQLite.
- The N/A determination is based on the architecture decision: `CLAUDE.md` specifies
  "ClickHouse handles all live streaming writes" but RIS knowledge data is operator-facing
  research context, not live streaming writes. SQLite idempotency is in place via doc_id
  uniqueness in KnowledgeStore.

### Item 10 (Posture statement) -- Partial

- Posture language appears in `research-review` CLI description (operator-facing queue inspection).
- Missing from module-level docstrings of: `research-health`, `research-ingest`,
  `research-eval`, `research-stats`, `research-acquire`.
- Deferred: adding a one-line posture note to remaining CLIs is a low-effort follow-up.
  Recommend addressing before Phase 3 begins.

### rejection_audit_disagreement health check -- Deferred stub

- Still returns stub. Requires an audit runner that samples rejected documents and re-scores
  for disagreement detection. Phase 3 / RIS v2 deliverable.

### Cloud provider live integration

- Gemini and DeepSeek clients are implemented with real HTTP logic.
- Live evaluation requires: `RIS_ENABLE_CLOUD_PROVIDERS=1`, `GEMINI_API_KEY` or
  `GOOGLE_API_KEY`, `DEEPSEEK_API_KEY`.
- Offline/manual path (ManualProvider) works without these keys.

---

## Recommendation

**CONDITIONAL CLOSE**

Core contract items (1, 2, 3, 4-storage, 6, 7, 8) pass with 307 tests and documented
manual validation. Item 9 is documented as N/A with architectural rationale.

The following gaps prevent full closure per the original spec:

1. **Item 5 (budget caps):** Config schema present, enforcement absent. Daily and per-source
   caps are not enforced during automated runs.
2. **Item 4 (72-hour auto-expiry):** Queue storage and CLI are complete, but the automatic
   time-based promotion/rejection policy is not implemented.
3. **Item 10 (posture statement):** Missing from 4 of 5 research CLI module docstrings.

**Operator decision required:** If items 5, the Item 4 auto-expiry, and Item 10 gap are
acceptable deferrals to Phase 3, Phase 2 can be declared closed on the 7 core contract items
(1, 2, 3, 4-storage, 6, 7, 8) plus the N/A Item 9. If not, address them before closure.

The **CONDITIONAL CLOSE** reflects: the substantive engineering work is complete and the
system operates correctly; the remaining gaps are policy enforcement (budget caps, auto-expiry)
and a documentation sweep (posture statement) rather than functional defects.
