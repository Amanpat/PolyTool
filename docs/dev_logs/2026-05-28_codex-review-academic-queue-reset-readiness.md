# Codex Review - Academic Queue Reset Readiness

**Date:** 2026-05-28
**Reviewer:** Codex
**Scope:** Review only plus this dev log. No implementation code, parser behavior, retrieval behavior, tests, benchmark baselines, GPU parsing, or 29-paper validation were changed or run.
**Verdict:** PASS WITH CONCERNS

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/dev_logs/2026-05-28_academic-scaled-validation-queue-reset-readiness.md`
- `docs/dev_logs/2026-05-26_codex-review-academic-demo-ready-docs-queue-triage.md`

Artifacts inspected read-only:

- `artifacts/research/scaled_validation_queue_v2/queue.jsonl`
- `artifacts/research/scaled_validation_queue_v2/results.jsonl`
- `artifacts/research/scaled_validation_queue_v2/indexed.jsonl`
- `artifacts/research/scaled_validation_queue_v2/bodies/`
- `artifacts/research/scaled_validation_queue_v2/pdf_cache/`
- `kb/rag/index/chroma.sqlite3`

---

## Commands Run

```text
git status --short
```

Result: dirty worktree, but changes shown are docs/vault/dev-log/runbook/current-state related. No implementation code changes were shown in the status output. Existing dirty files were not reverted or edited.

```text
git log --oneline -5
```

Result:

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

Result: exit 0. CLI loaded and listed `research-marker-queue` and `research-query`.

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Result summary:

```text
pending=24
processing=0
done=5
failed=0
total=29
stuck_warning=false
prefetch_stats.cached=24
prefetch_stats.failed=0
sidecar_count=5
indexed_count=10
```

Important caveat: `indexed_count=10` is not 10 unique papers. `indexed.jsonl` contains two entries for each of the same 5 done candidates. Unique indexed papers are 5.

```text
python -m polytool research-marker-queue check-chroma-links --json
```

Result:

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

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 jit-cache-check
```

Result: diagnostic printed. Current host environment:

```text
TORCHINDUCTOR_CACHE_DIR = (not set)
TRITON_CACHE_DIR        = (not set)
```

The command repeats that persistence proof requires an inside-Docker before/after parse check. No GPU parse was run.

Additional read-only inspections:

- `pdf_cache` contains 24 nonzero PDFs plus `manifest.jsonl`.
- `bodies` contains body and meta sidecars for the 5 done papers.
- `results.jsonl` still preserves prior fetch failures and the `arxiv:1011.6402` timeout.
- Chroma metadata currently contains candidate IDs `arxiv:1106.5040`, `arxiv:1609.03471`, `arxiv:1810.04383`, `arxiv:2510.05533`, and `arxiv:2604.24366`.

---

## Queue State Verdict

PASS WITH CONCERNS.

The queue was safely reset for cached parsing:

- Current queue state is clean: `pending=24`, `processing=0`, `done=5`, `failed=0`.
- The previous stuck item, `arxiv:1011.6402`, is now pending with `attempts=0`, `ingest_tier=3`, and a cached PDF.
- The previous failed fetch items are now pending with `attempts=0` and cached PDFs.
- Prior failure history was not hidden: `results.jsonl` still records HTTP 429/timeouts for `1206.4810`, `2003.05958`, `2203.13053`, `1810.04383`, and `2409.02025`, plus the 3600s timeout for `1011.6402`.
- The 5 done sidecars exist and are indexed in the KnowledgeStore: unique indexed candidates are `1105.3115`, `1106.5040`, `1605.01862`, `1705.01446`, and `2307.14129`, totaling 227 chunks and 1106 claims per `indexed.jsonl`.

Concern:

- `indexed.jsonl` has duplicate entries for the 5 indexed papers, so live `status-report` reports `indexed_count=10` while the unique indexed set is 5. Do not use raw `indexed_count` as the unique-paper validation count without deduping by `candidate_id`.

---

## Chroma Verdict

PASS for link integrity; PARTIAL for this queue's semantic completeness.

`check-chroma-links` is clean: 162 chunks, 5 unique Chroma papers, 0 missing `ks_doc_id`, 0 orphaned `ks_doc_id`.

Chroma is not complete for the reset queue. Of the 5 done sidecars, only `arxiv:1106.5040` is currently present in Chroma. The other newly indexed done papers are KS-indexed but not semantically embedded. Chroma also contains prior embeddings for `arxiv:1609.03471` and `arxiv:1810.04383`, which are pending in this queue.

This does not block cached Marker parsing, but it does block calling the final validation Chroma-complete until the embedding gap is remediated.

---

## JIT Cache Verdict

UNPROVEN, documented honestly.

The reset log accurately states that the host-side diagnostic only prints instructions and environment state. The actual persistence proof was not run inside the GPU container. Runtime planning should assume cold-start risk remains until the inside-Docker before/after parse diagnostic proves otherwise.

---

## Tier-3 Timeout Verdict

PASS WITH CONCERNS.

Risky papers are identified:

- `arxiv:1011.6402`: confirmed 3600s Marker timeout; currently `ingest_tier=3`.
- `arxiv:2409.02025`: repeated fetch/HTTP 429 history; currently `ingest_tier=3`.
- Seven large PDFs are flagged by size with 14400s recommended timeout, including `arxiv:2508.03474` at 9.7 MB.
- `arxiv:2307.14129` is a historical timeout-risk paper by runtime (`parse_seconds=2947s`) but is already one of the 5 done/indexed papers, so it is not part of the pending warm-process set.

The timeout policy is explicit and conservative:

- Small: 3600s.
- Medium: 7200s.
- Large: 14400s, starting with one large paper before continuing.
- Confirmed Tier-3: separate Batch D and no inclusion without explicit operator approval.
- Stop if more than one paper in Batch A/B fails with `marker_timeout`.
- Escalate if the 9.7 MB outlier exceeds 14400s.
- Do not treat partial completion as a valid 29-paper measurement.

Concern:

- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` still has a stale "Corpus Status (as of 2026-05-18)" section saying the 29-paper corpus is paused and showing pre-reset counts. The newer reset log and `docs/CURRENT_STATE.md` reflect the current reset-ready state, but the runbook section should be updated before relying on it as the sole operator guide.

---

## Final Verdict

**PASS WITH CONCERNS: schedule only with named caveats.**

The cached validation can be scheduled as a staged cached run, not as a blind monolithic run.

Caveats:

1. Treat `indexed_count=10` as duplicate-log noise; unique indexed done papers are 5.
2. Run the inside-Docker JIT cache preflight before the first GPU parse session and budget runtime as if cache persistence is unproven.
3. Do not include Tier-3 Batch D (`1011.6402`, `2409.02025`) without explicit operator approval.
4. Do not claim Chroma-complete validation until the Chroma embedding gap is remediated.
5. Update the stale runbook corpus-status section before handing this to an operator who will rely only on the runbook.

## Exact Next Action

Schedule the staged cached validation preflight and Batch A:

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
python -m polytool research-marker-queue check-chroma-links --json
docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi
```

Then run Batch A only:

```text
docker compose --profile ris-gpu run --rm ris-scheduler-gpu python -m polytool research-marker-queue --queue-dir /app/artifacts/research/scaled_validation_queue_v2 warm-process --max-items 5 --marker-timeout 3600
```

After Batch A, run `index-done` inside Docker, inspect failures, and proceed to Batch B only if the stop conditions are not triggered.
