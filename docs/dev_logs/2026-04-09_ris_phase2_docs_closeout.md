# Dev Log: RIS Phase 2 Docs Closeout

**Date:** 2026-04-09
**Task:** quick-260409-jfi -- Reconcile operator-facing docs for shipped Phase 2 RIS behavior
**Status:** Complete

## Purpose

Four Phase 2 code ships landed on 2026-04-08 but the operator docs still contained
stale v1-era claims. This log covers the docs-only reconciliation that brought
README.md, docs/README.md, docs/RIS_OPERATOR_GUIDE.md, and docs/CURRENT_STATE.md
into alignment with shipped behavior.

## Files Changed and Why

| File | Why |
|------|-----|
| `docs/RIS_OPERATOR_GUIDE.md` | Remove stale "v2 deliverable / raises ValueError" cloud provider claim; rewrite troubleshooting entry; update env vars table; add Evaluation Gate section; add Review Queue section; add Retrieval Benchmark section; update last-verified date to 2026-04-09 |
| `README.md` | Update RIS row in "What Is Shipped Today" table; add `research-review` to CLI command reference table |
| `docs/README.md` | Add `RIS_OPERATOR_GUIDE.md` link to "Start here" list (item 14) and to Workflows section |
| `docs/CURRENT_STATE.md` | Append 4 Phase 2 shipped-truth entries (cloud routing, ingest/review integration, monitoring truth, retrieval benchmark truth) |

## Specific Edits Made

### docs/RIS_OPERATOR_GUIDE.md

1. **Last verified date** updated from 2026-04-08 to 2026-04-09.

2. **Quick Reference table** -- added `research-review list`, `research-review accept`,
   `research-review reject` rows.

3. **New "Evaluation Gate" section** added before "Health Monitoring":
   - Weighted composite formula (relevance*0.30 + novelty*0.25 + actionability*0.25 + credibility*0.20)
   - Per-dimension floors (relevance >= 2, credibility >= 2; waived for priority_1)
   - Priority tier thresholds (P1=2.5, P2=3.0, P3=3.2, P4=3.5)
   - Provider routing: gemini -> deepseek -> ollama
   - Fail-closed behavior documented
   - `research-eval eval` CLI example with `--enable-cloud` flag
   - Cloud provider env var requirements

4. **New "Review Queue" section** added before "Health Monitoring":
   - 4 dispositions (accepted, queued_for_review, rejected, blocked) with table
   - All 5 subcommands: list, inspect, accept, reject, defer
   - `--db` flag noted
   - pending_review_history audit trail noted

5. **New "Retrieval Benchmark" section** added before "Calibration":
   - `rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl` command
   - `--suite-hash-only` flag for corpus verification
   - 3 query classes: factual, analytical, exploratory
   - 8 required metrics table
   - Artifact paths: `kb/rag/eval/reports/<timestamp>/report.json` and `summary.md`

6. **"What Does NOT Work Yet" section** -- cloud provider bullet updated from
   "Gemini, DeepSeek, OpenAI, Anthropic all raise ValueError (RIS v2 deliverables)"
   to accurate partial status: Gemini and DeepSeek implemented; OpenAI and Anthropic
   remain deferred.

7. **Troubleshooting section** -- "Provider gemini is a RIS v2 deliverable" entry
   replaced with "Provider unavailable / timeout" entry documenting real routing
   fallback behavior and required env vars.

8. **Environment variables table** -- `RIS_ENABLE_CLOUD_PROVIDERS` row updated from
   "No effect" to real description. Added 7 new rows: `GEMINI_API_KEY`,
   `DEEPSEEK_API_KEY`, `RIS_EVAL_PRIMARY_PROVIDER`, `RIS_EVAL_ESCALATION_PROVIDER`,
   `RIS_EVAL_FALLBACK_PROVIDER`, `RIS_EVAL_ESCALATE_REVIEW_DECISIONS`,
   `RIS_EVAL_FALLBACK_ON_PROVIDER_UNAVAILABLE`.

### README.md

1. **"What Is Shipped Today" RIS row** updated to: "Evaluation (weighted gate, cloud
   routing, fail-closed), ingestion, review queue, prechecking, claims extraction,
   scheduling, reporting, health/monitoring, retrieval benchmarks".

2. **CLI Command Reference -- Research Intelligence (RIS) table** -- `research-review`
   row added after `research-health`.

### docs/README.md

1. **"Start here" list** -- item 14 added: `[RIS Operator Guide](RIS_OPERATOR_GUIDE.md)`.

2. **Workflows section** -- new line added:
   `[RIS Operator Guide](RIS_OPERATOR_GUIDE.md) - Evaluation gate, review queue, ingestion, health monitoring, retrieval benchmarks`

### docs/CURRENT_STATE.md

Four new entries appended at end of file:
1. RIS Phase 2 -- Cloud Provider Routing (quick-260408-*, 2026-04-08)
2. RIS Phase 2 -- Ingest/Review Integration (quick-260408-*, 2026-04-08)
3. RIS Phase 2 -- Monitoring Truth (quick-260408-oyu, 2026-04-08)
4. RIS Phase 2 -- Retrieval Benchmark Truth (quick-260408-oz0, 2026-04-08)

## Commands Run + Output

### Git diff stat

```
 README.md                  |   3 +-
 docs/CURRENT_STATE.md      |  37 +++++++++++++
 docs/README.md             |  12 ++++
 docs/RIS_OPERATOR_GUIDE.md | 135 ++++++++++++++++++++++++++++++++++++++---
 4 files changed, 179 insertions(+), 8 deletions(-)
```

### CLI smoke

```
python -m polytool --help
# PASS: CLI loads, no import errors
```

### No code files changed

```
git diff --name-only HEAD~2 HEAD | grep -v "\.md$" | grep -v "\.planning/"
# Output: CLEAN: only markdown and planning files changed
```

### Full pytest suite

```
python -m pytest tests/ -x -q --tb=short
# 3810 passed, 3 deselected, 25 warnings in 134.78s
```

## Test Results

- **3810 passed, 3 deselected, 25 warnings** -- no regressions
- All existing tests continue to pass
- 25 warnings are pre-existing `datetime.utcnow()` deprecation warnings (out of scope)

## Remaining Active-Doc Caveats

The following items are intentionally still documented as PLANNED or deferred:

- `rejection_audit_disagreement` health check remains a stub -- requires audit runner;
  Phase 3 / RIS v2 deliverable.
- LLM-based report synthesis (DeepSeek V3 narrative generation) remains PLANNED.
- Grafana RIS panels do not exist.
- ClickHouse RIS tables do not exist (everything is SQLite / JSONL).
- Twitter/X ingestion not implemented, explicitly excluded.
- SSRN adapter not implemented (academic adapter covers arXiv only).
- `past_failures` in precheck always empty; populated in v2.
- OpenAI and Anthropic cloud providers not implemented (only Gemini + DeepSeek shipped).

## Operator Commands / Doc Paths Updated

Commands added or corrected in active docs:

| Command | Added To |
|---------|---------|
| `python -m polytool research-review list` | RIS_OPERATOR_GUIDE.md (Quick Reference + Review Queue section), README.md |
| `python -m polytool research-review inspect <doc_id>` | RIS_OPERATOR_GUIDE.md (Review Queue section) |
| `python -m polytool research-review accept <doc_id>` | RIS_OPERATOR_GUIDE.md (Quick Reference + Review Queue section) |
| `python -m polytool research-review reject <doc_id>` | RIS_OPERATOR_GUIDE.md (Quick Reference + Review Queue section) |
| `python -m polytool research-review defer <doc_id>` | RIS_OPERATOR_GUIDE.md (Review Queue section) |
| `python -m polytool research-eval eval --provider gemini --enable-cloud ...` | RIS_OPERATOR_GUIDE.md (Evaluation Gate section) |
| `python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl` | RIS_OPERATOR_GUIDE.md (Retrieval Benchmark section) |
| `python -m polytool rag-eval --suite ... --suite-hash-only` | RIS_OPERATOR_GUIDE.md (Retrieval Benchmark section) |

## Codex Review

Tier: Skip -- docs-only change, no execution or risk-sensitive paths. No review required.
