# Codex Review - Academic Batch A

**Date:** 2026-05-28
**Reviewer:** Codex
**Scope:** Review only plus this dev log. No implementation code, parser/retrieval behavior, benchmark baselines, GPU parsing, or Batch B/C/D execution changed or run.
**Verdict:** BLOCK

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/dev_logs/2026-05-28_academic-batch-a-preflight.md`
- `docs/dev_logs/2026-05-28_academic-scaled-validation-batch-a.md`
- `docs/dev_logs/2026-05-28_codex-review-academic-queue-reset-readiness.md`

Artifacts inspected read-only:

- `artifacts/research/scaled_validation_queue_v2/queue.jsonl`
- `artifacts/research/scaled_validation_queue_v2/results.jsonl`
- `artifacts/research/scaled_validation_queue_v2/indexed.jsonl`
- `artifacts/research/scaled_validation_queue_v2/batch_a_warmprocess.log`
- `kb/rag/index/`

---

## Commands Run

```text
git status --short
git log --oneline -5
python -m polytool --help
```

Results:

- Worktree is dirty, but visible changed paths are docs, vault, runbook, AGENTS/claude context files, and dev logs. `git diff --name-only -- . ':!docs/**' ':!AGENTS.md' ':!claude.md'` returned empty, so no implementation files were dirty.
- Recent commits: `c249ff5`, `b921857`, `7fc6bf2`, `15ef471`, `3348e79`.
- `python -m polytool --help` exited 0 and listed `research-marker-queue` and `research-query`.

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

Note: `indexed_count=25` is audit-log line count, not unique-paper count.

```text
python -m polytool research-marker-queue check-chroma-links --json
```

Result:

```json
{"total_chunks":485,"unique_papers":13,"valid_ks_doc_id":485,"missing_ks_doc_id":0,"ks_doc_id_not_in_ks":0}
```

```text
python -m polytool research-marker-queue --help
```

Result: exit 0; subcommands include `warm-process`, `index-done`, `status-report`, `jit-cache-check`, and `check-chroma-links`.

```text
Get-Content artifacts/research/scaled_validation_queue_v2/results.jsonl -Tail 8
Get-Content artifacts/research/scaled_validation_queue_v2/indexed.jsonl -Tail 8
Get-Content artifacts/research/scaled_validation_queue_v2/batch_a_warmprocess.log -Tail 120
```

Result:

- Last five Batch A results are all `queue_status=done`, `body_source=marker`, `marker_ready=true`, `ipc_warm_worker_used=true`.
- Batch A parse metrics: 2605.00864 `11.34s`, 2507.08921 `20.29s`, 2510.05533 `14.06s`, 2507.01990 `23.99s`, 2601.18815 `1319.91s`.
- Batch A indexed entries exist for all five; `2510.05533` has `claims_extracted=0`, but 34 chunks were indexed and embedded per the Batch A log.
- Warm-process log contains five `[PASS]` lines and no fetch/HTTP/live fallback warnings from the `Select-String` scan.

```text
research-query probes
```

Independent probes:

- `algorithmic arbitrage Polymarket NBA prediction markets` returned `arxiv:2605.00864` top hit, `had_fallback=false`, semantic.
- `large language model survey financial prediction 2024` returned `arxiv:2510.05533` top hit and `arxiv:2507.01990` second, `had_fallback=false`, semantic.
- `Bayesian inference prediction market price path` returned `arxiv:2601.18815` top hit, `had_fallback=false`, semantic.
- `protein folding molecular dynamics` did **not** reject. It returned `arxiv:1705.01446` with `paper_score=0.18156492710113525`, `had_fallback=false`, semantic, exit 0.

---

## Preflight Verdict

PASS WITH CONCERNS.

The preflight evidence is mostly trustworthy:

- Duplicate `indexed.jsonl` disposition is correct: duplicate lines are audit noise; candidate/doc IDs are stable and idempotent.
- Chroma refresh is real: link check now reports 485 chunks, 13 unique papers, 0 missing `ks_doc_id`, 0 orphaned `ks_doc_id`.
- JIT cache diagnostic remains unproven, but the preflight documented this honestly.
- Stale runbook text was corrected.
- Batch A paper list excluded explicit Tier-3 papers.

Concern: the preflight did not catch that the post-Batch-A FIFO order would place Tier-3 papers before the full intended Batch B set.

---

## Batch A Verdict

PASS for parse/index evidence.

Batch A itself appears trustworthy:

- Only five Batch A papers were processed in the final run.
- All five used cached `pdf_url` paths.
- Warm-process log scan found no arXiv fetch, HTTP 429, or live fallback warnings.
- All five parsed with Marker and `ipc_warm_worker_used=true`.
- No timeout, parse, sidecar, index, or Chroma link failures were observed.
- `index-done` recorded all five Batch A papers.
- `check-chroma-links` is clean after Batch A.
- No explicit Tier-3 paper is in the done set.

Non-blocking concern: `arxiv:2510.05533` extracted 0 claims, but it is still chunked, embedded, and retrievable.

---

## Chroma / Query Verdict

BLOCK for rejection-quality evidence.

Relevant query probes are acceptable: the three rerun topical probes retrieved expected Batch A papers as top hits. Snippets are mostly readable Marker text, though some are long reference-heavy chunks.

The unrelated rejection probe is not acceptable. The Batch A log claims `protein folding molecular dynamics` rejected honestly with no citations. Independent rerun returned an unrelated semantic citation (`arxiv:1705.01446`) with score just above the semantic threshold and `had_fallback=false`. That means the Batch A retrieval PASS is overstated. The parse/index evidence remains valid, but the query-probe evidence is not fully trustworthy.

---

## Batch B Scheduling Verdict

BLOCK.

Batch B should not be run from the current queue state with the logged command. Current first 10 pending FIFO items are:

```text
1. arxiv:1206.4810  ingest_tier=2
2. arxiv:2003.05958 ingest_tier=2
3. arxiv:2203.13053 ingest_tier=2
4. arxiv:1810.04383 ingest_tier=2
5. arxiv:2409.02025 ingest_tier=3
6. arxiv:1011.6402  ingest_tier=3
7. arxiv:1609.03471
8. arxiv:2508.03474 large/tier3_flag by status-report
9. arxiv:2605.11640
10. arxiv:2605.02286
```

`warm-process --max-items 10 --marker-timeout 7200` would process Tier-3 papers at positions 5 and 6, and a large outlier at position 8, before the intended Batch B medium set is complete. That violates the stated constraint that Tier-3 papers require operator approval and that Batch B/C/D must not be mixed.

---

## Final Verdict

**BLOCK: do not schedule the Batch B run yet.**

Batch A parse/index/Chroma-link evidence is trustworthy. The two blocking issues are:

1. The unrelated query rejection probe did not reproduce; semantic retrieval returned an irrelevant paper.
2. The current FIFO queue order would cause the documented Batch B command to process Tier-3/large papers.

## Exact Next Action

Run a Batch B preflight only. Reorder or otherwise constrain the queue so the next `warm-process --max-items 10` contains exactly the intended non-Tier-3 medium Batch B papers, then rerun:

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
python -m polytool research-marker-queue check-chroma-links --json
python -m polytool research-query --question "protein folding molecular dynamics" --k 3
```

Do not run Batch B until those checks show no Tier-3/large items in the next 10 FIFO pending papers and the unrelated-query behavior is either fixed or explicitly classified as an accepted retrieval-quality caveat.
