# Dev Log: RIS Phase 2 Acceptance Closeout

**Date:** 2026-04-09
**Task:** 260409-jfm-01 -- Phase 2 RIS acceptance sweep and closeout
**Status:** Complete

---

## Objective

Run targeted verification commands against all 10 Phase 2 contract items (per
`docs/specs/SPEC-ris-phase2-operational-contracts.md` and
`docs/roadmaps/RIS_PHASE2_evaluation_gate_monitoring_rag_testing_v1_1.md`) and produce
a per-item disposition table backed by specific command output or grep evidence.

---

## Commands Run and Output

### 1. Full Phase 2 test suite

```
python -m pytest tests/test_ris_phase2_weighted_gate.py \
  tests/test_ris_phase2_cloud_provider_routing.py \
  tests/test_ris_evaluation.py \
  tests/test_ris_ingestion_integration.py \
  tests/test_ris_research_acquire_cli.py \
  tests/test_ris_phase5_provider_enablement.py \
  tests/test_ris_monitoring.py \
  tests/test_ris_review_queue.py \
  tests/test_ris_scheduler.py \
  tests/test_rag_eval.py -q
```

Output: **307 passed in 8.95s**

Individual file counts:
- `test_ris_phase2_weighted_gate.py`: 51 tests (items 1+2 core)
- `test_ris_evaluation.py`: 41 tests (general evaluation)
- `test_ris_ingestion_integration.py`: 18 tests (item 4 pipeline wiring)
- `test_ris_research_acquire_cli.py`: 16 tests (acquire/review path)
- `test_ris_phase5_provider_enablement.py`: 20 tests (provider enablement)
- `test_ris_phase2_cloud_provider_routing.py`: 8 tests (item 1+cloud providers)
- `test_ris_monitoring.py`: 75 tests (items 7+monitoring)
- `test_ris_review_queue.py`: 6 tests (item 4 queue storage)
- `test_ris_scheduler.py`: 37 tests (item 8 scheduling)
- `test_rag_eval.py`: 35 tests (item 7 retrieval benchmark)

### 2. research-health CLI

```
python -m polytool research-health --json
```

Output (abbreviated):
- 7 health checks reported (pipeline_failed, no_new_docs_48h, accept_rate_low,
  accept_rate_high, data_freshness, model_unavailable, review_queue_backlog)
- `overall_category: "FAILURE"` (due to blog_ingest error + reddit not configured,
  which is expected in the development environment -- reddit requires praw + env vars)
- `review_queue_backlog: GREEN` (1 item in queue, under 20 threshold)
- Phase 2 fields confirmed present: `overall_category` key in JSON output

### 3. research-stats summary CLI

```
python -m polytool research-stats summary --json
```

Output (abbreviated):
```json
{
  "provider_route_distribution": {},
  "provider_failure_counts": {},
  "review_queue": { "queue_depth": 1, "by_status": {"pending": 1}, "by_gate": {"REVIEW": 1} },
  "disposition_distribution": { "ACCEPT": 0, "REVIEW": 0, "REJECT": 0, "BLOCKED": 0 },
  "routing_summary": { "escalation_count": 0, "fallback_count": 0, "direct_count": 0, "total_routed": 0 }
}
```

Phase 2 fields confirmed: `provider_route_distribution`, `provider_failure_counts`,
`review_queue`, `disposition_distribution`, `routing_summary`.

### 4. research-review CLI

```
python -m polytool research-review --help
```

Output: showed `list`, `inspect`, `accept`, `reject`, `defer` subcommands with description
"Inspect and resolve the RIS review queue. Scores classify ingestion/research usefulness only."

### 5. research-eval CLI

```
python -m polytool research-eval --help
```

Output: showed `--provider`, `--enable-cloud`, `--priority-tier`, `--artifacts-dir` args.
Provider list includes gemini, deepseek, ollama, manual. `--priority-tier` options: priority_1..priority_4.

### 6. ris_eval_config.json validity

```
python -m json.tool config/ris_eval_config.json > /dev/null && echo "VALID JSON"
```

Output: `VALID JSON`

Top-level keys: `_comment`, `scoring`, `acceptance_gates`, `budget`, `defaults`, `routing`, `provider_configs`

Config loaded and verified:
```python
cfg = get_eval_config()
# weights: {'relevance': 0.3, 'novelty': 0.25, 'actionability': 0.25, 'credibility': 0.2}
# floors: {'relevance': 2, 'credibility': 2}
# floor_waive_tiers: ('priority_1',)
# thresholds: {'priority_1': 2.5, 'priority_2': 3.0, 'priority_3': 3.2, 'priority_4': 3.5}
```

### 7. Retrieval benchmark JSONL

```
python -c "import json; [json.loads(l) for l in open('docs/eval/ris_retrieval_benchmark.jsonl')]; print('VALID JSONL')"
```

Output: `VALID JSONL`

Inspection: 9 cases, 3 classes (factual: 3, analytical: 3, exploratory: 3). All required
query_class values present.

### 8. Budget cap implementation check

```
grep -rn "budget\|daily_cap\|per_source.*cap\|budget_exhausted" packages/research/ingestion/ packages/research/evaluation/ packages/research/scheduling/ --include="*.py"
```

Output: **No matches found** in RIS packages.

Broader search in all packages + tools also found nothing relevant in the RIS ingestion
or evaluation area. The only `budget` hits were in `packages/polymarket/simtrader/batch/runner.py`
(time_budget_seconds, unrelated to RIS daily caps).

**Finding: Budget caps (Item 5) are NOT IMPLEMENTED in code.** The config file has a
`budget` key (confirmed), but there is no enforcement code in ingestion/evaluation/scheduling.

### 9. Posture statement check

```
grep -rn "research context\|not trading signals\|research-only\|posture" tools/cli/research_*.py packages/research/evaluation/scoring.py --include="*.py"
```

Relevant findings:
- `tools/cli/research_review.py` line 3-4: "Scores in this queue classify ingestion/research usefulness only. / They are not trading recommendations."
- `tools/cli/research_review.py` line 228: "Scores classify ingestion/research usefulness only."
- `tools/cli/llm_bundle.py` line 241: "## Go/No-Go (research-only)" (unrelated)

**Finding:** Posture language is present in `research-review` CLI (the operator-facing review
surface). It is NOT explicitly present in the module docstrings of `research-health`,
`research-ingest`, `research-eval`, or `research-stats`. The spec says ALL output surfaces
must carry or reference the posture statement.

The posture statement IS in `docs/RIS_OPERATOR_GUIDE.md` and the spec documents. The gap is
that the ingest/eval/health CLI module-level docstrings do not carry it.

### 10. ClickHouse RIS idempotency check

```
grep -rn "ris_events\|ReplacingMergeTree.*ris\|execution_id.*INSERT" packages/ tools/ --include="*.py"
```

Output: **No matches found.**

The RIS Operator Guide confirms: "RIS data is stored in SQLite via KnowledgeStore. There is
no ClickHouse table for RIS events." This is consistent with the architectural decision
noted in dev logs -- RIS uses SQLite, not ClickHouse for its knowledge store.

**Finding: ClickHouse RIS idempotency (Item 9) is NOT APPLICABLE.** The RIS system does not
write to ClickHouse. SQLite (KnowledgeStore) is the persistence layer. The idempotency
contract is partially addressed at the SQLite layer (pending_review table uses doc_id as
primary key), but the spec describes a ClickHouse-specific contract that does not apply.

---

## Phase 2 Contract Item Evidence

### Item 1: Fail-closed evaluation

- Tests: 51 tests in `test_ris_phase2_weighted_gate.py` + 8 in
  `test_ris_phase2_cloud_provider_routing.py` covering fail-closed behavior
- Dev log: `2026-04-08_ris_phase2_eval_gate_core.md`, `2026-04-08_ris_phase2_cloud_provider_routing.md`
- Code evidence: `packages/research/evaluation/evaluator.py` try/except block constructs
  fail-closed ScoringResult; `packages/research/evaluation/scoring.py` parse_scoring_response()
  returns reject_reason="scorer_failure" on malformed output
- Status: **PASS**

### Item 2: Weighted composite gate

- Tests: 51 tests in `test_ris_phase2_weighted_gate.py`
- Dev log: `2026-04-08_ris_phase2_eval_gate_core.md`
- Config evidence: weights {relevance:0.30, novelty:0.25, actionability:0.25, credibility:0.20},
  floors {relevance:2, credibility:2}, thresholds {P1:2.5, P2:3.0, P3:3.2, P4:3.5}
- Status: **PASS**

### Item 3: Novelty/dedup detection

- Tests: covered in `test_ris_phase2_weighted_gate.py` and `test_ris_evaluation.py`
- Dev log: `2026-04-08_ris_phase2_eval_gate_core.md`
- Code evidence: `packages/research/evaluation/dedup.py` EXISTS with check_near_duplicate();
  `evaluator.py` calls it as a pre-scoring step before provider invocation;
  canonical ID check via hard_stops runs before near-dup check
- Status: **PASS** (caveat: canonical doc_id/source_url dedup runs in hard_stops;
  near-dup shingle check runs when existing_hashes provided; spec requires both)

### Item 4: Review queue contract

- Tests: 6 tests in `test_ris_review_queue.py`, 18 in `test_ris_ingestion_integration.py`,
  16 in `test_ris_research_acquire_cli.py`
- Dev logs: `2026-04-08_ris_phase2_review_queue_cli.md`, `2026-04-08_ris_phase2_ingest_review_integration.md`
- CLI evidence: `research-review --help` shows list/inspect/accept/reject/defer subcommands
- Code evidence: `packages/polymarket/rag/knowledge_store.py` has `pending_review` and
  `pending_review_history` tables; `packages/research/ingestion/pipeline.py` routes REVIEW
  outcomes to pending_review
- Caveat: 72-hour auto-promote/auto-reject policy is NOT implemented. The spec says
  "72-hour auto-promote or auto-reject policy applies if operator does not respond" -- no
  code enforces this expiry
- Status: **PASS with caveat** (queue storage + CLI = PASS; auto-expiry = NOT IMPLEMENTED)

### Item 5: Per-source daily budget caps

- Tests: none found for budget caps
- Grep: no matches in packages/research/ingestion/, packages/research/evaluation/,
  packages/research/scheduling/
- config/ris_eval_config.json has a `budget` key (present), but there is no enforcement code
- Status: **NOT IMPLEMENTED** -- budget schema defined in config, but enforcement absent

### Item 6: Per-priority acceptance gates

- Tests: 51 tests in `test_ris_phase2_weighted_gate.py` include priority threshold tests
- Dev log: `2026-04-08_ris_phase2_eval_gate_core.md`
- Code evidence: `packages/research/evaluation/types.py` gate property applies
  `cfg.thresholds.get(self.priority_tier)` with tier-specific values;
  floor_waive_tiers=('priority_1',) for floor waiver
- CLI evidence: `research-eval --priority-tier TIER` arg present, `research-ingest --priority-tier` present
- Status: **PASS**

### Item 7: Segmented benchmark metrics

- Tests: 35 tests in `test_rag_eval.py` including QueryClassSegmentationTests
- Dev log: `2026-04-08_ris_phase2_retrieval_benchmark_truth.md`
- Artifact evidence: `docs/eval/ris_retrieval_benchmark.jsonl` (9 cases, 3 classes: factual,
  analytical, exploratory) -- VALID JSONL confirmed
- Code evidence: `packages/polymarket/rag/eval.py` extended with query_class segmentation;
  all 8 required metrics per ModeAggregate (query_count, mean_recall_at_k, mean_mrr_at_k,
  total_scope_violations, queries_with_violations, mean_latency_ms, p50_latency_ms, p95_latency_ms)
- Monitoring side: `test_ris_monitoring.py` 75 tests include Phase 2 fields
  (provider_route_distribution, provider_failure_counts, review_queue, disposition_distribution)
- Status: **PASS**

### Item 8: Env-var-primary n8n config hierarchy

- Tests: 37 tests in `test_ris_scheduler.py` for scheduler behavior
- Dev log: `2026-04-08_unified_n8n_alerts_and_summary.md`
- Code evidence: n8n workflow executes `docker exec polytool-ris-scheduler python -m polytool
  research-scheduler run-job academic_ingest` -- Python CLI reads env vars from container
  environment, not from n8n Variables
- Config evidence: `packages/research/evaluation/config.py` documents 30+ `RIS_EVAL_*` env
  var overrides; env vars take priority over file values
- n8n Variables confirmed optional: workflows run correctly without n8n Variables set;
  `DISCORD_WEBHOOK_URL` for alerts is the only n8n-injected value (optional, not required)
- Status: **PASS** (n8n workflow drives Python CLI which reads env vars first; n8n Variables
  are not used in the config hierarchy at all, satisfying "optional convenience overrides only")

### Item 9: Dual-layer ClickHouse write idempotency

- Grep: no `ris_events`, `ReplacingMergeTree.*ris`, or `execution_id.*INSERT` found
- Operator Guide confirms: RIS data stored in SQLite via KnowledgeStore; no ClickHouse table
  for RIS events
- ADR context: CLAUDE.md specifies ClickHouse handles live streaming writes; RIS uses SQLite
  for knowledge store data
- Status: **N/A -- architecture does not include ClickHouse for RIS events**

Rationale: The spec item was written when the architecture anticipated ClickHouse for
monitoring/idempotency. The implemented architecture uses SQLite (KnowledgeStore) exclusively
for RIS persistence. SQLite uniqueness constraints on doc_id provide storage-level
idempotency; there is no dual-layer ClickHouse requirement to satisfy.

### Item 10: Research-only posture statement

- Grep findings:
  - `tools/cli/research_review.py` lines 3-4, 228: posture statement present
  - `tools/cli/research_eval.py` line 19: mentions RIS_ENABLE_CLOUD_PROVIDERS but no posture
  - `tools/cli/research_health.py`, `research_stats.py`, `research_ingest.py`: no posture
- Spec says: "All RIS output surfaces (reports, precheck verdicts, knowledge-base entries)
  must carry or reference the posture statement"
- Status: **PARTIAL** -- posture language in research-review (the human-facing queue CLI);
  not present in health/stats/ingest/acquire module docstrings or help text

Caveat precision: The posture statement IS in `docs/RIS_OPERATOR_GUIDE.md` and spec docs.
It is NOT in the CLI module docstrings for health, stats, ingest, eval, acquire. The
review CLI has it but other surfaces do not.

---

## Final Recommendation

**CONDITIONAL CLOSE**

Core contract items (1, 2, 3, 4, 6, 7, 8) PASS with full test coverage (307 tests).
Item 9 is N/A with documented rationale (RIS uses SQLite, not ClickHouse).

Remaining items with gaps:
- Item 5 (budget caps): NOT IMPLEMENTED -- config schema exists, no enforcement code
- Item 4 (72-hour expiry): queue storage PASS, auto-expiry policy NOT IMPLEMENTED
- Item 10 (posture statement): partial -- present in review CLI, absent from health/ingest/eval/acquire

Blockers for full closure:
1. Item 5: budget enforcement is a genuine gap (daily cap, per-source caps, manual reserve)
2. Item 10: posture statement gap in 4 of 5 research CLI module docstrings
3. Item 4: 72-hour auto-promote/reject policy is unimplemented (operational policy gap)

Items 5, 10, and the Item 4 auto-expiry are scoped as deferred for Phase 3 or a follow-on
Phase 2.5 if the operator decides to close Phase 2 on the 7 completed core items.
