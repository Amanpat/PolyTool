---
title: Codex Review Academic 3Paper And Operator Tests
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-25_codex-review-academic-3paper-and-operator-tests.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - Academic 3-Paper Category Sample and Operator Path

**Date:** 2026-05-25
**Reviewer:** Codex
**Scope:** Review only. No implementation, retrieval, parser, benchmark, or 29-paper artifact changes.
**Verdict:** PASS WITH CONCERNS

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/dev_logs/2026-05-25_academic-3paper-category-sample.md`
- `docs/dev_logs/2026-05-25_academic-operator-path-test.md`
- Artifact evidence under:
  - `artifacts/research/smoke_test_queue/`
  - `artifacts/research/wp1_closeout_queue/`
  - `artifacts/research/scaled_validation_queue_v2/`
  - `kb/rag/index` via Chroma `academic_papers`

---

## Commands Run

Session start / scope checks:

```text
git status --short
```

Output: dirty tree existed before this review, mostly vault churn plus untracked RIS dev logs. Relevant requested new sample log was untracked:

```text
?? docs/dev_logs/2026-05-25_academic-3paper-category-sample.md
```

```text
git log --oneline -5
```

Output:

```text
c249ff5 docs(ris): operator-path simplicity test - 9 runbook corrections, readiness verdict
b921857 fix(ris): L2.1 one-paper acceptance repair - Chroma embed, span strip, NTFS fallback
7fc6bf2 fix(ris): L2.1 Deliverable B - offline-safe semantic fallback, resolves Codex BLOCK
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
```

```text
python -m polytool --help
```

Output: CLI loaded successfully and listed `research-marker-queue` and `research-query`.

Operator CLI checks:

```text
python -m polytool research-marker-queue --help
python -m polytool research-marker-queue prefetch --help
python -m polytool research-marker-queue index-done --help
python -m polytool research-query --help
```

Relevant outputs:

```text
usage: polytool research-marker-queue [-h] [--queue-dir PATH] {enqueue,list,process,warm-process,index-done,counts,prefetch,status-report,jit-cache-check,check-chroma-links} ...
--delay-seconds SECONDS  Seconds to sleep between successive PDF downloads (default: 10.0).
--reindex-chroma         After indexing into KnowledgeStore, also embed each paper body into the 'academic_papers' ChromaDB collection...
```

Chroma link check:

```text
python -m polytool research-marker-queue check-chroma-links --json
```

Output:

```json
{
  "collection": "academic_papers",
  "chroma_path": "kb\\rag\\index",
  "total_chunks": 162,
  "unique_papers": 5,
  "valid_ks_doc_id": 162,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0,
  "not_in_ks_doc_ids": []
}
```

Queue status checks:

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/smoke_test_queue counts
```

Output:

```text
pending: 0
processing: 0
done: 4
failed: 0
total: 4
```

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 counts
```

Output:

```text
pending: 18
processing: 1
done: 5
failed: 5
total: 29
```

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/wp1_closeout_queue status-report --json
```

Output summary: one done item, one sidecar, one indexed item, one cached PDF for `arxiv:2510.05533`.

Focused query rerun:

```text
python -m polytool research-query --question "<probe>"
```

Summary output:

```json
{"label":"1a","top_arxiv_id":"2510.05533","citation_count":1,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"1b","top_arxiv_id":"2510.05533","citation_count":1,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"1c","top_arxiv_id":"2510.05533","citation_count":1,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"2a","top_arxiv_id":"1106.5040","citation_count":3,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"2b","top_arxiv_id":"1106.5040","citation_count":3,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"2c","top_arxiv_id":"1810.04383","citation_count":3,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"3a","top_arxiv_id":"1609.03471","citation_count":5,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"3b","top_arxiv_id":"1609.03471","citation_count":4,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"3c","top_arxiv_id":"1810.04383","citation_count":5,"had_fallback":false,"retrieval_mode":"semantic"}
{"label":"REJ","top_arxiv_id":null,"citation_count":0,"had_fallback":true,"retrieval_mode":"lexical"}
```

Snippet cleanliness spot check:

```json
{"label":"1a","top_arxiv_id":"2510.05533","has_raw_span":false}
{"label":"2a","top_arxiv_id":"1106.5040","has_raw_span":false}
{"label":"3a","top_arxiv_id":"1609.03471","has_raw_span":false}
```

Category evidence spot checks from Marker sidecars:

```json
{"arxiv_id":"2510.05533","chars":93754,"table_mentions":6,"equation_markers":0,"survey_mentions":32}
{"arxiv_id":"1106.5040","chars":67585,"table_mentions":6,"equation_markers":128,"survey_mentions":5}
{"arxiv_id":"1609.03471","chars":61415,"table_mentions":3,"equation_markers":40,"survey_mentions":6}
```

Per-paper Chroma chunk check:

```text
2510.05533: 34
1106.5040: 30
1609.03471: 29
1810.04383: 44
2604.24366: 25
```

Scope-creep check:

```text
git diff --name-only b921857..HEAD
```

Output:

```text
docs/dev_logs/2026-05-25_academic-operator-path-test.md
docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md
```

This confirms the operator-path follow-up after the L2.1 repair touched docs/runbook only, not retrieval implementation, parser settings, benchmarks, or 29-paper artifacts.

---

## Evidence Checked

### 1. Category Coverage

PASS with one caveat.

- `2510.05533` is a clear prose/survey paper: title and body explicitly identify it as a survey; sidecar has 32 survey/review/literature hits and no equation markers.
- `1106.5040` is a clear equation-heavy paper: HJB/QVI, stochastic control, dynamic programming, and many displayed equations are present; sidecar spot check found 128 equation/control markers.
- `1609.03471` is a valid empirical/table-oriented prediction-market LOB paper: the body contains PredictIt market data, summary statistics, profits, figures, and tables. Caveat: extracted structural counts do not prove it is uniquely "table-heavy" compared with the other two papers. The label is acceptable for a category smoke sample, but the 29-paper validation should not overfit the "table-heavy" conclusion from this one paper.

### 2. Paper State

PASS for retrieval readiness.

| Paper | Parsed | Sidecar | KS indexed | Chroma indexed | Link-check |
|---|---:|---:|---:|---:|---:|
| `2510.05533` | yes | yes | yes, 34 chunks | yes, 34 Chroma chunks | clean |
| `1106.5040` | yes | yes | yes, 30 chunks | yes, 30 Chroma chunks | clean |
| `1609.03471` | yes | yes | yes, 29 chunks | yes, 29 Chroma chunks | clean |

PDF cache caveat: I found explicit WP-1 `pdf_cache` evidence for `2510.05533`. I did not find PDF cache files for `1106.5040` or `1609.03471`; they are still retrieval-ready because body sidecars, KS rows, and Chroma chunks exist. If "cached" means "prefetched PDF cache exists," the 3-paper log overstates that detail for two papers. If "cached" means "body sidecar available for reuse," it is true.

### 3. Query Support / Overstatement

PASS.

The focused rerun reproduced the dev log's main retrieval claims:

- Prose/survey: 3/3 target top-1, semantic, no fallback.
- Equation-heavy: 2/3 target top-1; the miss goes to another mathematical finance / optimal execution paper, with semantic retrieval and no fallback.
- Table/empirical: 2/3 target top-1; the miss goes to the same adjacent mathematical finance paper, with semantic retrieval and no fallback.
- Rejection probe: zero citations, `had_fallback=true`, `retrieval_mode=lexical`.

The dev log's "subdomain ambiguity" explanation is supported.

### 4. Unrelated Query Rejection

PASS.

`weather forecasting rainfall prediction model` returned:

```json
{"top_arxiv_id":null,"citation_count":0,"had_fallback":true,"retrieval_mode":"lexical"}
```

That is honest behavior for an out-of-domain query.

### 5. Snippet Cleanliness

PASS for demo v1, with a known cosmetic caveat.

Top snippets for the three primary probes had no raw `<span>` tags. The 3a rerun returned a clean abstract/introduction snippet for `1609.03471`. Some non-top results still include reference-list-style text and long citation-heavy spans. This is acceptable for a developer demo, but snippet-quality filtering should remain a tracked follow-up before claiming polished operator output.

### 6. Runbook / Operator Path

PASS WITH CONCERNS.

The operator-path fixes in commit `c249ff5` are real and useful:

- `--queue-dir` is now correctly documented before the `research-marker-queue` subcommand.
- `--delay-seconds` default is corrected to 10.
- Quick Start no longer mixes `docker compose run --rm` with a following `docker exec` that would require a still-running container.

Remaining runbook issues:

1. The runbook still has two competing paths (Quick Start prefetch path and Operator Path pre-WP-1 path). The operator-path test correctly flags this as confusing for a non-coder.
2. The Known-Good 3-Paper section still says ChromaDB academic retrieval is deferred, which is stale after L2.1.
3. The Querying section still says retrieval is "not semantic or vector retrieval," which is now inaccurate because focused query output shows `retrieval_mode="semantic"`.
4. The Known-Good section can still mislead a Windows operator because it reflects a pre-WP-1/pre-NTFS-discovery flow while the current runbook says `index-done` must run inside Docker for colon-bearing arXiv body filenames.

These are documentation accuracy issues, not retrieval implementation blockers.

### 7. Scope Creep

PASS.

No evidence of a full 29-paper rerun during this review. Current `scaled_validation_queue_v2` remains partial:

```text
pending: 18
processing: 1
done: 5
failed: 5
total: 29
```

Post-`b921857` committed changes are docs-only:

```text
docs/dev_logs/2026-05-25_academic-operator-path-test.md
docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md
```

No retrieval implementation, parser setting, benchmark baseline, or corpus validation artifact was changed by this review.

---

## Demo-Readiness Status

Academic RIS is demo-ready v1 for a developer/operator demo of:

1. Marker-ready papers already indexed,
2. Chroma link health,
3. semantic `research-query`,
4. honest unrelated-query rejection,
5. citations with mostly clean snippets.

It is not yet non-coder-ready without runbook cleanup. The path is usable by a developer who can read CLI errors and understand Docker lifecycle basics.

---

## Is 29-Paper Validation Safe Next?

Not as an immediate blind run.

The 3-paper sample justifies moving toward 29-paper validation from a retrieval-quality perspective, but the next run should first resolve the known operator/runbook and batch-readiness issues:

- fix stale L2.1 runbook text that still describes retrieval as non-semantic and Chroma as deferred;
- add a top routing note for 1-3 paper demo path vs 5+ prefetch batch path;
- add a caveat to the Known-Good section that the 2026-05-09 flow predates the Windows `index-done`/NTFS colon discovery;
- handle the existing `scaled_validation_queue_v2` state (`18 pending`, `1 processing`, `5 done`, `5 failed`) before treating it as a clean 29-paper validation;
- keep the already-documented timeout-risk/JIT-cache concerns visible before a long GPU batch.

After those fixes, full 29-paper validation is a reasonable next validation step.

---

## Required Fixes

Required before claiming non-coder operator readiness:

1. Update the runbook Querying section for L2.1 semantic/Chroma retrieval.
2. Update the Known-Good 3-Paper section so it no longer says ChromaDB academic retrieval is deferred.
3. Add the routing note recommended in the operator-path test: first run / 1-3 papers vs 5+ paper prefetch batch.
4. Add an explicit caveat that the 2026-05-09 Known-Good run predates the Windows `index-done` Docker requirement.

Required before starting full 29-paper validation:

1. Decide whether to resume/reset/rebuild `scaled_validation_queue_v2`, since it is currently partial.
2. Confirm handling for the known timeout-risk papers and JIT-cache persistence concern, or explicitly accept those as measured risks for the run.

---

## Exact Next Action

Make one narrow docs-only runbook correction pass for the four required operator-readiness fixes above, then run:

```text
python -m polytool research-marker-queue check-chroma-links --json
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Use that status report to decide whether `scaled_validation_queue_v2` should be resumed, reset, or rebuilt before the 29-paper validation.
