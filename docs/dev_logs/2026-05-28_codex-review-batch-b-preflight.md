# Codex Review - Batch B Preflight

**Date:** 2026-05-28
**Reviewer:** Codex
**Scope:** Review only plus this dev log. No implementation code, parser behavior, queue artifacts, benchmark baselines, GPU parsing, or Batch B/C/D execution changed or run.
**Verdict:** PASS WITH CONCERNS - Batch B may be scheduled with the command constraints below.

---

## Files Reviewed

- `CLAUDE.md`
- `claude.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-28_l2-1-semantic-rejection-guard.md`
- `docs/dev_logs/2026-05-28_academic-batch-b-preflight.md`
- `docs/dev_logs/2026-05-28_codex-review-academic-batch-a.md`

Artifacts inspected read-only:

- `artifacts/research/scaled_validation_queue_v2/queue.jsonl`
- `artifacts/research/scaled_validation_queue_v2/results.jsonl`
- `artifacts/research/scaled_validation_queue_v2/indexed.jsonl`
- `artifacts/research/scaled_validation_queue_v2/pdf_cache/`
- `artifacts/research/scaled_validation_queue_v2/*.log`

Implementation diff reviewed:

- `packages/research/synthesis/academic_query.py`
- `tests/test_research_query.py`

---

## Commands Run

```text
git status --short
git log --oneline -5
python -m polytool --help
```

Results:

- Worktree is very dirty, mostly docs/vault churn.
- Implementation changes visible under `packages/`, `tools/`, `polytool/`, `tests/` are limited to:
  - `packages/research/synthesis/academic_query.py`
  - `tests/test_research_query.py`
- Recent commits: `c249ff5`, `b921857`, `7fc6bf2`, `15ef471`, `3348e79`.
- `python -m polytool --help` exited 0 and listed `research-marker-queue` and `research-query`.

```text
git diff -- packages/research/synthesis/academic_query.py tests/test_research_query.py
git diff --name-only -- packages tools polytool tests
git diff --name-only -- artifacts config kb
```

Results:

- The semantic guard diff is scoped to `_query_chroma_semantic()` plus targeted tests.
- No tracked `artifacts/`, `config/`, or `kb/` diffs are present.

```text
pytest -q tests/test_research_query.py
```

Result:

```text
98 passed in 5.17s
```

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Result summary:

```text
pending=19
processing=0
done=10
failed=0
total=29
prefetch_stats.cached=24
prefetch_stats.failed=0
sidecar_count=10
indexed_count=25
```

```text
python -m polytool research-marker-queue check-chroma-links --json
```

Result:

```json
{"total_chunks":485,"unique_papers":13,"valid_ks_doc_id":485,"missing_ks_doc_id":0,"ks_doc_id_not_in_ks":0}
```

```text
python -m polytool research-query --question "protein folding molecular dynamics" --k 3
python -m polytool research-query --question "weather forecast" --k 3
```

First attempt with a 120s command timeout timed out for both probes. Re-run with a 300s timeout succeeded:

```text
protein folding molecular dynamics: citations=[], had_fallback=true, retrieval_mode=lexical
weather forecast: citations=[], had_fallback=true, retrieval_mode=lexical
```

```text
python -m polytool research-query --question "algorithmic arbitrage Polymarket NBA prediction markets" --k 3
python -m polytool research-query --question "large language model survey financial prediction 2024" --k 3
python -m polytool research-query --question "Bayesian inference prediction market price path" --k 3
```

Results:

- `algorithmic arbitrage Polymarket NBA prediction markets`: top hit `arxiv:2605.00864`, `had_fallback=false`, `retrieval_mode=semantic`.
- `large language model survey financial prediction 2024`: top hit `arxiv:2510.05533`, second hit `arxiv:2507.01990`, `had_fallback=false`, `retrieval_mode=semantic`.
- `Bayesian inference prediction market price path`: top hit `arxiv:2601.18815`, `had_fallback=false`, `retrieval_mode=semantic`.

```text
PowerShell JSONL inspection of queue.jsonl, pdf_cache, results tail, indexed tail, and log mtimes.
```

Results:

- `done=10`, `processing=0`, `failed=0`.
- Last five done IDs are Batch A only: `arxiv:2605.00864`, `arxiv:2507.08921`, `arxiv:2510.05533`, `arxiv:2507.01990`, `arxiv:2601.18815`.
- `batch_a_warmprocess.log` last modified 2026-05-28 09:05:44; stale `warm_process_batch2.log` is from 2026-05-18.
- No evidence Batch B was run.

---

## Semantic Rejection Verdict

PASS.

The previous unrelated-query blocker is resolved in the live corpus:

- `protein folding molecular dynamics` now rejects honestly: no citations, `had_fallback=true`.
- `weather forecast` still rejects honestly: no citations, `had_fallback=true`.
- Relevant L2.1 queries still pass through semantic retrieval and return expected papers.

Non-blocking concern: the guard has a thin calibration margin (`confident_threshold=0.19`; logged hallucination score `0.197`). This is acceptable for Batch B scheduling, but future corpus updates should keep unrelated-query controls in the smoke set.

---

## Queue FIFO Verdict

PASS.

The next 10 pending FIFO items are:

```text
1. arxiv:1206.4810
2. arxiv:2003.05958
3. arxiv:2203.13053
4. arxiv:1810.04383
5. arxiv:1609.03471
6. arxiv:2605.11640
7. arxiv:2605.02286
8. arxiv:2605.00493
9. arxiv:2208.13564
10. arxiv:2605.10400
```

`status-report` classifies all ten as:

- `size_bucket=medium (601-1500KB)`
- `is_known_timeout_risk=false`
- `recommended_timeout_seconds=7200.0`
- `tier3_flag=false`
- `ingest_tier=2`

Tier-3 / excluded items are outside the Batch B window:

- `arxiv:2409.02025` at position 11: `ingest_tier=3`, `tier3_flag=true`
- `arxiv:1011.6402` at position 12: `ingest_tier=3`, `tier3_flag=true`
- Large/tier3-flag items at positions 13-19.

---

## PDF Cache Verdict

PASS.

All 10 Batch B PDFs exist under `artifacts/research/scaled_validation_queue_v2/pdf_cache/`:

```text
arxiv-1206.4810.pdf
arxiv-2003.05958.pdf
arxiv-2203.13053.pdf
arxiv-1810.04383.pdf
arxiv-1609.03471.pdf
arxiv-2605.11640.pdf
arxiv-2605.02286.pdf
arxiv-2605.00493.pdf
arxiv-2208.13564.pdf
arxiv-2605.10400.pdf
```

No live arXiv fetch should be needed during Batch B warm-process.

---

## Chroma / Status Verdict

PASS.

- Queue: `pending=19`, `processing=0`, `done=10`, `failed=0`.
- Chroma links: `485` chunks, `13` unique papers, `0` missing `ks_doc_id`, `0` orphaned `ks_doc_id`.
- Batch B was not run: done set remains at 10 papers, and results tail contains only prior Batch A completions after the old 2026-05-18 failed/partial run records.

---

## Concerns

1. The worktree is heavily dirty outside this review scope, mostly docs/vault churn. This does not block Batch B, but commit hygiene should be handled separately.
2. Live `research-query` cold-start latency exceeded 120s for unrelated probes when run in parallel. A 300s timeout succeeded. This is operational latency, not a correctness failure.
3. Some raw queue rows do not persist all derived risk fields; `status-report` computes the full tier/size/timeout classification. Operators should rely on `status-report` before batch execution.

---

## Final Verdict

PASS WITH CONCERNS.

The two Batch A blockers are resolved:

1. Unrelated-query rejection now behaves honestly for both `protein folding molecular dynamics` and `weather forecast`.
2. Batch B FIFO now excludes Tier-3 and large/tier3-flag papers from the next 10 pending items.

## Exact Next Action

Run Batch B next, with these constraints:

- Do not change queue order before running.
- Do not include Tier-3 papers.
- Do not run Batch C/D.
- Use `--max-items 10`.
- Use `--marker-timeout 7200`.
- Run in Docker/GPU, not on the Windows host.

Command:

```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 10 --marker-timeout 7200
```

