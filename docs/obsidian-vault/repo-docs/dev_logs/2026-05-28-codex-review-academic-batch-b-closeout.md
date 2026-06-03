---
title: Codex Review Academic Batch B Closeout
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-28_codex-review-academic-batch-b-closeout.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - Academic Batch B Closeout

**Date:** 2026-05-28
**Reviewer:** Codex
**Scope:** Review only plus this dev log. No implementation code, parser/retrieval behavior, benchmark baselines, Batch C/D execution, GPU parsing, or full 29-paper artifact mutation.
**Verdict:** PASS WITH CONCERNS - Academic RIS can close as developer/operator demo-ready v1 with named caveats.

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/dev_logs/2026-05-28_academic-scaled-validation-batch-b.md`
- `docs/dev_logs/2026-05-28_codex-review-batch-b-preflight.md`
- `artifacts/research/scaled_validation_queue_v2/queue.jsonl`
- `artifacts/research/scaled_validation_queue_v2/results.jsonl`
- `artifacts/research/scaled_validation_queue_v2/indexed.jsonl`
- `artifacts/research/scaled_validation_queue_v2/bodies/`

## Commands Run

```text
git status --short
git log --oneline -5
python -m polytool --help
```

Results:

- Worktree is dirty before this review. Tracked implementation/test diffs are limited to `packages/research/synthesis/academic_query.py` and `tests/test_research_query.py`.
- Recent commits: `c249ff5`, `b921857`, `7fc6bf2`, `15ef471`, `3348e79`.
- `python -m polytool --help` exited 0 and listed `research-marker-queue` and `research-query`.

```text
git diff --name-only -- packages tools polytool tests
git diff --stat -- packages/research/synthesis/academic_query.py tests/test_research_query.py
```

Results:

- Only implementation/test files currently dirty under code/test roots:
  - `packages/research/synthesis/academic_query.py`
  - `tests/test_research_query.py`
- Stat: 2 files changed, 111 insertions, 1 deletion.
- This matches the pre-existing L2.1 semantic rejection guard/test diff documented in preflight; I did not make or modify implementation code.

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Result summary:

```text
pending=9
processing=0
done=20
failed=0
total=29
prefetch_stats.cached=24
prefetch_stats.failed=0
sidecar_count=20
indexed_count=55
```

Pending IDs are all Batch C/D or tier/large items:

```text
arxiv:2409.02025
arxiv:1011.6402
arxiv:2508.03474
arxiv:2604.10005
arxiv:2403.09267
arxiv:2212.12717
arxiv:2308.04947
arxiv:2604.20050
arxiv:2602.21091
```

```text
python -m polytool research-marker-queue check-chroma-links --json
```

Result:

```json
{"collection":"academic_papers","chroma_path":"kb\\rag\\index","total_chunks":917,"unique_papers":21,"valid_ks_doc_id":917,"missing_ks_doc_id":0,"ks_doc_id_not_in_ks":0,"not_in_ks_doc_ids":[]}
```

```text
PowerShell JSONL/body-sidecar inspection for Batch B IDs
```

Result:

- All 10 Batch B queue rows are `status=done`, `attempts=1`.
- All 10 final successful result rows have `body_source=marker`, `marker_ready=True`, `ipc_warm_worker_used=True`, and `queue_status=done`.
- All 10 Batch B body and metadata sidecars are present under `bodies/` using NTFS-safe `arxiv...` filenames.

```text
python -m polytool research-query --question "multi-asset market making closed-form spread model" --k 3
python -m polytool research-query --question "Polymarket non-retail trading behavioral tiers microstructure" --k 3
python -m polytool research-query --question "binary prediction markets belief convergence empirical" --k 3
python -m polytool research-query --question "weather forecast" --k 3
python -m polytool research-query --question "protein folding molecular dynamics" --k 3
```

Result summaries:

- `multi-asset market making closed-form spread model`: `had_fallback=false`, `retrieval_mode=semantic`; expected Batch B paper `1810.04383` appears at rank 2.
- `Polymarket non-retail trading behavioral tiers microstructure`: `had_fallback=false`, `retrieval_mode=semantic`; expected Batch B paper `2605.11640` appears at rank 1.
- `binary prediction markets belief convergence empirical`: `had_fallback=false`, `retrieval_mode=semantic`; expected Batch B paper `1609.03471` appears at rank 1.
- `weather forecast`: returns one lexical citation from `2605.00493`; `had_fallback=false`, `retrieval_mode=lexical`. This is a lexical false positive for an unrelated-probe smoke because that paper explicitly mentions weather forecasts as a control category.
- `protein folding molecular dynamics`: rejects honestly with `citations=[]`, `had_fallback=true`, `retrieval_mode=lexical`.

## Parse / Index Verdict

PASS.

Batch B parse evidence independently checks out:

| arXiv ID | body_length | parse_seconds | marker_ready | ipc_warm |
|----------|-------------|---------------|--------------|----------|
| 1206.4810 | 89163 | 1245.29 | True | True |
| 2003.05958 | 130920 | 3248.93 | True | True |
| 2203.13053 | 97745 | 3055.95 | True | True |
| 1810.04383 | 116221 | 2269.74 | True | True |
| 1609.03471 | 61281 | 58.51 | True | True |
| 2605.11640 | 181670 | 73.02 | True | True |
| 2605.02286 | 42701 | 30.99 | True | True |
| 2605.00493 | 138768 | 33.39 | True | True |
| 2208.13564 | 42256 | 53.87 | True | True |
| 2605.10400 | 313516 | 2132.41 | True | True |

Index evidence checks out:

- Docker `index-done` after Batch B indexed 10 new papers and extracted 2490 claims per Batch B log.
- Windows host `index-done --reindex-chroma --force` ran after that and reprocessed all 20 done papers for Chroma embedding.
- Current queue status reports `indexed_count=55`, which is raw append-line count after repeated force reindexing, not unique-paper count. This is harmless audit noise.

## Chroma Verdict

PASS.

Current `check-chroma-links --json` is clean:

- `total_chunks=917`
- `unique_papers=21`
- `valid_ks_doc_id=917`
- `missing_ks_doc_id=0`
- `ks_doc_id_not_in_ks=0`

Named caveat: the Docker GPU image still lacks the Chroma dependencies, so Batch B Chroma embedding required the Windows-host fallback path. This is operational friction, not a corpus correctness blocker.

## Query Verdict

PASS WITH CONCERNS.

Relevant Batch B probes retrieve expected papers with `retrieval_mode=semantic` and `had_fallback=false`. Metadata includes `retrieval_mode` in live output.

Snippets are acceptable for developer/operator v1: they are Marker body text, cite the expected papers, and are readable enough for operator validation. Caveat: snippets can still be long and occasionally reference-heavy; this is not a blocker for v1.

Unrelated rejection is not perfect:

- `protein folding molecular dynamics` rejects honestly.
- `weather forecast` returns one lexical citation from `2605.00493`, because the paper explicitly mentions weather forecasts as a control category. This means the Batch B log's broad "weather correctly rejected" conclusion is not correct in the current corpus.

Classification: non-blocking for demo-ready v1 if documented honestly. The semantic guard is doing its job; the false positive is in lexical fallback over real paper text.

## Performance Verdict

PASS WITH CONCERNS.

Batch B parsed 10/10 within the 7200s timeout. Five papers were fast (<100s); five were slow (>1000s), with the slowest at 3248.93s. This is consistent with the documented RTX 2070 Super / Marker JIT behavior for equation-heavy or new format groups.

Performance is acceptable for developer/operator demo-ready v1 because:

- All Batch B papers completed successfully.
- Slow papers stayed within the selected timeout.
- Batch C/D are not required for v1 closeout.

Caveats:

- JIT cache persistence remains unresolved for future large-batch planning.
- Query probes can be slow; the unrelated probes each took close to the 300s timeout in this review.

## Final Verdict

PASS WITH CONCERNS.

Academic RIS can close as developer/operator demo-ready v1, provided the closeout states these caveats explicitly:

1. Worktree is dirty before review; implementation diffs are limited to the pre-existing L2.1 query guard/test files.
2. Chroma links are clean, but embedding required Windows-host fallback because the Docker GPU image lacks Chroma dependencies.
3. Unrelated-query rejection is not perfect: `weather forecast` returns one lexical citation from a Batch B paper that mentions weather forecasts as controls.
4. Slow parse/query behavior is acceptable for v1 but remains an operational planning concern for Batch C/D.

## Exact Next Action

Closeout docs.

Do not run Batch C/D for demo-ready v1 closure. Record the caveats above in the feature closeout/current-state update. Treat a lexical fallback false-positive guard as a targeted post-v1 hardening item, not a blocker to developer/operator demo-ready v1.
