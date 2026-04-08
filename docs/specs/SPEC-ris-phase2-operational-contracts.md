# SPEC: RIS Phase 2 Operational Contracts

**Status:** Accepted
**Date:** 2026-04-07

## Purpose and non-goals

Purpose:

- Freeze the RIS Phase 2 operational contract so the next code prompts can implement one behavior at a time without reopening policy.
- Keep Phase 2 limited to ingestion evaluation, review handling, budget enforcement, retrieval benchmark reporting, and monitoring/idempotency.
- Evaluation scores classify ingestion quality and research usefulness only, not strategy recommendations, market edge, trade selection, or execution decisions.

Non-goals:

- No implementation code, tests, SQL migrations, workflow edits, Docker changes, or config-file creation in this spec.
- No new product scope beyond the Director-approved Phase 2 decisions.
- No change to RIS research-only posture.

## Existing repo capabilities to reuse

- `packages/research/evaluation/providers.py` already supports only `manual` and `ollama`; cloud providers are recognized but not implemented. Phase 2 should extend around that truth, not assume additional providers exist.
- `packages/research/evaluation/dedup.py` and `packages/research/evaluation/evaluator.py` already perform near-duplicate detection. Phase 2 should reuse that path instead of introducing a second dedup system.
- `tools/cli/research_health.py` and `tools/cli/research_stats.py` already exist for operator monitoring surfaces.
- `packages/research/scheduling/scheduler.py` is the APScheduler-backed default scheduler surface. Per `docs/adr/0013-ris-n8n-pilot-scoped.md`, n8n remains an opt-in pilot and not the default runtime assumption.
- `ris_eval_config.json` does not exist yet. This spec defines what that file must own if added later; this prompt does not create it.

## Fail-closed evaluation contract

- Every evaluation attempt must end with one normalized decision record containing at least `doc_id`, `source_url`, `source_type`, `priority_tier`, `eval_provider`, `eval_model`, `relevance_score`, `novelty_score`, `actionability_score`, `credibility_score`, `composite_score`, `simple_sum_score`, and `gate_decision`.
- A document may ingest only after a valid parsed evaluation result is produced for the current attempt.
- Any timeout, provider error, parse failure, missing required score field, or schema violation resolves to `gate_decision = "REJECT"` with `reject_reason = "scorer_failure"`.
- Fail-closed rejects do not auto-ingest and do not enter `pending_review`.
- Fallback or escalation scoring may run inside the same evaluation flow, but only a valid parsed result may replace the default reject.

## Canonical gate formula

Phase 2 uses weighted composite + per-dimension floor as the only acceptance gate.

```text
weighted composite =
  relevance_score * 0.30 +
  novelty_score * 0.25 +
  actionability_score * 0.25 +
  credibility_score * 0.20
```

- Score range for each dimension is `1-5`.
- Standard per-dimension floor is `relevance_score >= 2` and `credibility_score >= 2`.
- Priority 1 is the only tier allowed to waive the standard floor.
- `simple_sum_score = relevance_score + novelty_score + actionability_score + credibility_score` is retained as diagnostic only.
- Simple sum must never be the accept/reject gate, review-queue gate, or retrieval benchmark acceptance gate.

## Novelty dedup rule before nearest-neighbor injection

- Canonical duplicate checks on `doc_id` and `source_url` run first.
- If a canonical duplicate is found, evaluation stops before any nearest-neighbor lookup or novelty-context injection.
- Existing near-duplicate detection remains in scope and should run only for canonically unique candidates.
- Nearest-neighbor novelty injection may run only after duplicate and near-duplicate rejection checks complete.
- Nearest-neighbor injection is capped at the implementation-defined top neighbors for novelty context only; it informs scoring and never overrides duplicate rejection on its own.

## Review queue contract

`pending_review` storage intent:

- `pending_review` is the durable human review queue in KnowledgeStore SQLite.
- It holds borderline documents that are not auto-accepted and not hard-rejected.
- `pending_review` is not used for `scorer_failure` rejects or canonical duplicates.

Minimum fields:

- `doc_id`
- `source_url`
- `source_type`
- `title`
- `priority_tier`
- `scores_json`
- `composite_score`
- `simple_sum_score`
- `queue_reason`
- `eval_provider`
- `eval_model`
- `execution_id`
- `queued_at`
- `review_status`
- `reviewed_at`
- `reviewed_by`
- `review_notes`
- `defer_until`

Accept/reject/defer actions:

- `accept`: ingest the document and record `validation_status = "human_accepted"`.
- `reject`: do not ingest and record `reject_reason = "human_rejected"`.
- `defer`: keep the item in `pending_review`, set `review_status = "deferred"`, and require notes or `defer_until`.

Audit expectations:

- Every enqueue and every review action must create an append-only audit event keyed by `doc_id`.
- Each audit event must capture `acted_at`, `acted_by`, `previous_status`, `new_status`, and `reason_or_notes`.
- The queue row is current state only; the audit trail is the review history of record.

## Budget contract

Global cap:

- Default daily global evaluation cap is `200`.

Per-source caps:

- `academic = 50`
- `reddit = 40`
- `twitter = 30`
- `blog = 30`
- `youtube = 20`
- `github = 20`
- `manual = 10`

Escalation budget:

- Escalation scoring consumes the same daily and per-source budgets as the original document.
- Escalation usage should be tracked separately for reporting, but it is not extra budget.

Manual reserve:

- A `manual reserve` of `10` evaluations is held back for operator-submitted URLs.
- Automated jobs must not consume manual reserve.

Exhaustion behavior:

- When a source cap is exhausted, that source stops evaluating for the current daily window.
- When the non-reserved global cap is exhausted, automated evaluation stops for the current daily window.
- Manual submissions may continue only while manual reserve remains.
- Budget exhaustion must be recorded as `budget_exhausted`; the system must not silently bypass caps.

## Retrieval benchmark reporting contract

Required query classes:

- `factual`
- `analytical`
- `exploratory`

Required metrics:

- `query_count`
- `mean_recall_at_k`
- `mean_mrr_at_k`
- `total_scope_violations`
- `queries_with_violations`
- `mean_latency_ms`
- `p50_latency_ms`
- `p95_latency_ms`

Corpus and baseline expectations:

- Benchmark suites remain stable JSONL corpora with per-case `query_class`.
- Reports must publish overall results and per-`query_class` results for each retrieval mode.
- Baseline artifacts remain the current `report.json` and `summary.md` layout under `kb/rag/eval/reports/<timestamp>/`.
- Tuning and regression checks compare against a frozen baseline artifact, not ad hoc console output.

## Monitoring and idempotency contract

Execution dedup intent:

- `execution_id` identifies one logical ingestion or evaluation run.
- Retries of the same logical run must reuse the same `execution_id`.
- A new scheduled run or new operator-triggered run must mint a new `execution_id`.

Storage-level and code-level dedup:

- Storage-level dedup is the ClickHouse write-layer contract, using `execution_id + doc_id` as the intended identity.
- Code-level dedup must pre-check for rows already written for the current `execution_id` before insert.
- Storage-level merge cleanup is eventual; code-level dedup is the immediate barrier.

ClickHouse/Grafana scope for Phase 2:

- Phase 2 monitoring scope is operational only: run visibility, evaluation visibility, idempotency visibility, and budget visibility.
- Existing `research-health` and `research-stats` remain the default operator surfaces.
- ClickHouse and Grafana may support Phase 2 monitoring, but they do not own gate decisions, review decisions, or strategy logic.

## Config contract

`ris_eval_config.json` responsibilities:

- Own non-secret evaluation defaults when the file is introduced later.
- Hold default score weights, floor rules, priority thresholds, budget defaults, and retrieval reporting defaults.
- Avoid secrets and provider credentials; those remain env-var concerns.

Env-var-first runtime behavior:

- Runtime resolution is env-var-first.
- If both env vars and `ris_eval_config.json` are present, env vars win.
- If env vars are absent, runtime may fall back to `ris_eval_config.json`, then hardcoded defaults.

n8n Variables optional only:

- n8n Variables may mirror runtime settings for the pilot workflows, but they are optional only.
- Correct runtime behavior must not depend on n8n Variables existing.

## Acceptance gates for Priority 1-4

If a document has no explicit tier, default to `priority_3`.

| Priority | Typical use | Threshold | Floor rule |
|---|---|---:|---|
| `priority_1` | operator-submitted or critical manual review targets | `weighted composite >= 2.5` | floor waived |
| `priority_2` | academic and curated sources | `weighted composite >= 3.0` | standard floor applies |
| `priority_3` | default social and RSS sources | `weighted composite >= 3.2` | standard floor applies |
| `priority_4` | low-confidence auto-discovered sources | `weighted composite >= 3.5` | standard floor applies |

Decision rules:

- Above threshold and compliant with its floor rule: accept.
- Below threshold without floor failure: send to `pending_review`.
- Floor failure: reject.
- `scorer_failure`: reject.

## Locked statement

Evaluation scores classify ingestion quality and research usefulness only, not strategy recommendations.
