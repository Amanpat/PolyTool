# Marker IPC — Revised Gate and Result Evidence Persistence

Date: 2026-05-08
Type: code fix + docs update
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1
Verdict: **COMPLETE** — persistence fix applied, revised gates recorded, 158 tests pass

---

## Director Decision

The original ≤10s/paper acceptance gate for papers 2+ is **rejected as unrealistic** for full
academic PDFs on the RTX 2070 Super and replaced with a functional warm-worker gate.

Basis for rejection:

- Marker runs a five-stage multi-model pipeline per paper (layout detection, OCR error
  detection, bounding box detection, text recognition, table recognition).
- Full academic PDFs (15–46 pages) require ~45–70s warm inference on the RTX 2070 Super.
- The ≤10s target was aspirational; no measured evidence ever existed for this hardware +
  paper complexity combination.

Revised functional gate (Director-approved):

| Criterion | Result |
|-----------|--------|
| ≥3 full academic PDFs in one warm session | PASS (done=3, failed=0) |
| Papers 2+ delta (total_seconds − parse_seconds) ≤5s | PASS (0.13s, 0.22s) |
| `body_source=marker` all papers | PASS |
| `ipc_warm_worker_used=true` all papers | PASS |
| No pdfplumber fallback | PASS |
| No daemon-process error | PASS |
| Clean shutdown / no orphans | PASS |
| `ipc_warm_worker_used` persisted in `results.jsonl` | PASS (fix applied) |

Measured timings (from 2026-05-08 live validation, not rerun):

| Paper | parse_seconds | total_seconds | delta |
|-------|--------------|--------------|-------|
| arxiv:2604.24366 (paper 1) | 45.55 | 72.31 | 26.76s (cold-load) |
| arxiv:2109.07581 (paper 2) | 69.73 | 69.86 | **0.13s** (warm) |
| arxiv:1910.08858 (paper 3) | 48.31 | 48.53 | **0.22s** (warm) |

Papers 2–3 delta ≈ 0.13–0.22s confirms cold-load overhead is eliminated. The warm-worker
delivers its intended value: models load once, papers 2+ pay only inference + queue overhead.

---

## Files Changed

### `packages/research/ingestion/marker_queue.py`

**Problem:** `process_next_ipc()` tagged `ipc_warm_worker_used` onto in-memory result dicts
AFTER `_append_result()` had already written to `results.jsonl`. The field was present in the
live command JSON output but absent from the persisted artifact.

**Fix:**

1. Added `_extra_result_fields: Optional[dict] = None` parameter to `process_next()`.
2. Merged the extra fields into `result_record` before `_append_result()` is called.
3. Updated both code paths in `process_next_ipc()` to pass
   `_extra_result_fields={"ipc_warm_worker_used": ipc_flag/ipc_used}` — eliminating the
   post-hoc in-memory tagging loop that ran after persistence.

The fix is backward-compatible: `process_next()` callers that do not pass
`_extra_result_fields` get no change in `results.jsonl` schema.

### `tests/test_ris_marker_queue.py`

Added `TestIPCResultPersistence` class (4 new tests):

- `test_ipc_flag_true_persisted_when_worker_provided` — `_ipc_worker` provided →
  `results.jsonl` has `ipc_warm_worker_used=true`.
- `test_ipc_flag_false_persisted_when_no_worker` — `_fetcher` only, no `_ipc_worker` →
  `results.jsonl` has `ipc_warm_worker_used=false`.
- `test_process_next_does_not_persist_ipc_flag` — non-IPC `process_next()` path does not
  inject `ipc_warm_worker_used` into `results.jsonl` (backward-compatible schema).
- `test_multiple_ipc_items_all_have_flag_persisted` — 2 papers, both get
  `ipc_warm_worker_used=true` persisted.

### `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`

- Status callout updated: records live validation result, gate revision decision, and
  persistence fix.
- Gate 2 revised: ≤10s requirement struck through, replaced with delta ≤5s functional gate.
  Evidence: paper 1 delta=26.76s (cold-load), papers 2–3 delta=0.13–0.22s (warm). PASS.
- Gate 3 revised: `parse_seconds ≤10s` requirement struck through. All 3 measured timings
  preserved. PASS.
- Added `Director Gate Revision (2026-05-08)` section explaining the decision, why ≤10s was
  rejected, what the warm-worker actually delivers, revised functional gate table, and
  persistence fix summary.

---

## Tests Run

```
python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q --tb=short
```

Result: **158 passed, 1 skipped in 2.96s**

The 1 skip is the Linux-only `test_warm_thread_worker_raises_on_subprocess_platform` test,
which is correct on Windows.

```
python -m polytool research-marker-queue warm-process --help
```

Result: exit 0, `--max-items` and `--marker-timeout` present. CLI intact.

---

## No Live Validation Rerun

Live Docker/GPU validation was NOT rerun. All evidence is from the 2026-05-08 live session
documented in `docs/dev_logs/2026-05-08_marker-ipc-daemon-fix-direct-pdf-live-validation.md`
and the Codex verification in
`docs/dev_logs/2026-05-08_codex-verify-marker-ipc-daemon-fix-direct-pdf-live-validation.md`.

No Docker rebuild, prune, or queue mutation was performed.

---

## Feature 3 Status

Feature 3 is **NOT yet closed.** All revised functional gates PASS. L1 Marker production
rollout and L2 PaperQA2 RAG Control Flow remain blocked until:

1. Codex verifies this session's changes (code fix + test + docs).
2. Feature 3 closeout is explicitly approved by the operator.

The closeout prompt may proceed after Codex verification passes.

---

## Codex Review Summary

Tier: research ingestion / queue consumer. Mandatory trading, execution, kill-switch,
risk-manager, rate-limiter, SVM, L2, L4 code not in scope.

Issues found: `ipc_warm_worker_used` not persisted in `results.jsonl` (Codex artifact caveat
from prior review). Addressed: `_extra_result_fields` fix applied, 4 new tests cover
persistence for IPC and non-IPC paths.

Issues addressed: persistence fix complete, revised gate recorded.
