# Codex Review - Academic WP-2 and L2.1 Packet

**Date:** 2026-05-23
**Reviewer:** Codex
**Scope:** Read-only review plus this dev log
**Verdict:** PASS WITH CONCERNS

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/dev_logs/2026-05-23_academic-wp2-speed-observability.md`
- `docs/dev_logs/2026-05-23_l2-1-academic-retrieval-quality-packet.md`
- `docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_codex-review-academic-speed-and-retrieval-plan.md`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_queue.py`

Relevant dirty state noted but not reviewed in detail: large unrelated
`docs/obsidian-vault/**` modifications and generated `.smart-env/**` files.

---

## Commands Run

```powershell
git status --short
```

Result: dirty tree. Relevant files included `docs/CURRENT_STATE.md`,
`docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`,
`packages/research/ingestion/marker_queue.py`,
`tools/cli/research_marker_queue.py`, `tests/test_ris_marker_queue.py`,
new WP-2/L2.1 dev logs, and new `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`.
There were also many unrelated Obsidian-vault changes.

```powershell
git log --oneline -5
```

Output:

```text
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
50775d1 feat(ris): WP-1 academic PDF prefetch separation
1fb000d Academic Pipeline Improvements/Testing
de72208 docs(ris): academic pipeline scaled validation - Batch 1 execution record
```

```powershell
python -m polytool --help
```

Result: exit 0. CLI loads and lists `research-marker-queue` and `research-query`.

```powershell
python -m pytest tests/test_ris_marker_queue.py -q --tb=short
```

Result:

```text
170 passed, 1 skipped in 3.34s
```

```powershell
python -m polytool research-marker-queue --help
python -m polytool research-marker-queue enqueue --help
python -m polytool research-marker-queue warm-process --help
python -m polytool research-marker-queue status-report --help
python -m polytool research-marker-queue jit-cache-check --json
python -m polytool research-marker-queue status-report --json
```

Results: all exit 0. Help exposes `--tier {2,3}`, `--auto-timeout`,
`status-report`, and `jit-cache-check`. `jit-cache-check --json` returns
`torchinductor_cache_dir`, `triton_cache_dir`, and diagnostic instructions.
`status-report --json` includes `sidecar_count`, `indexed_count`, and
`timeout_risk_items`.

---

## Review Findings

### Parser quality / Marker gate

PASS. The WP-2 code does not reduce parser quality thresholds. The canonical
guard remains:

```python
return body_source == "marker" and body_length >= MIN_MARKER_BODY_LENGTH
```

`_process_item()` still rejects non-marker output and short Marker bodies before
setting `marker_ready`. `index_done_items()` still indexes only latest results
with `queue_status=done` and `marker_ready=True`, then calls the existing
`IngestPipeline.ingest_external(..., "academic")` gate.

### Tier 0 / Tier 1 acceptance path

PASS. No Tier 0 or Tier 1 academic RAG acceptance path was introduced. New
enqueue metadata accepts only `{2, 3}` and rejects other values with `ValueError`;
the CLI also constrains `--tier` to `{2,3}`. Tier 3 is metadata/classification
for timeout-risk handling, not a lower-quality parser path.

### Stale "29-paper rerun safe now" language

PASS. The stale `CURRENT_STATE.md` text saying the 29-paper rerun was safe to
proceed was replaced with "NOT YET READY" plus blockers: unresolved JIT cache
persistence, three timeout-risk papers requiring Tier-3/operator approval, and
`jit-cache-check` before full-batch execution. The runbook also now states the
29-paper corpus remains paused and updates dense math timing from "~60-70s" to
observed 33-55 minute timings plus JIT cold-start risk.

### Status/progress fields

PASS WITH CONCERNS. The new JSON fields are testable and operator-readable:
`sidecar_count`, `indexed_count`, and per-pending `timeout_risk_items` with
file size bucket, known-risk flag, recommended timeout, tier flag, and ingest
tier. Tests cover their presence and core behavior.

Concern: `warm-process --auto-timeout` silently assigns the 14400s default to
items missing cached prefetch size data. That is conservative for timeout, but
it can hide a missing prefetch step and still let `warm-process` fall back to
live arXiv fetch during parse. Before a full 29-paper run, this should become
at least a clear warning, preferably a fail-fast unless the operator explicitly
allows uncached items.

Concern: `jit-cache-check` Step 3 uses `find ~/.triton -newer /tmp/before_marker`
but the printed procedure never tells the operator to create `/tmp/before_marker`.
The diagnostic is still useful, but that step is not copy/paste reliable.

### L2.1 packet scope

PASS. The L2.1 packet is scoped correctly:

- semantic retrieval fallback only, not hybrid RRF;
- a dedicated `academic_papers` Chroma collection;
- explicit `ks_doc_id` linkage back to KnowledgeStore source documents;
- `body_source=marker` filtering on semantic hits;
- snippet cleanup at render time only;
- no LLM synthesis, page-level citation promise, SVM enforce, broad ingestion
  rewrite, benchmark work, or gate-language change.

The packet correctly flags open questions around snippet regex false positives
and `had_fallback` semantics. Recommended implementation should add a distinct
`used_semantic_fallback` field or equivalent, so `had_fallback` does not become
ambiguous after semantic fallback exists.

---

## Contradictions Found

1. `docs/dev_logs/2026-05-23_academic-wp2-speed-observability.md` says
   **Status: SHIPPED** but later says **WP-2 Not Closed**. Interpreted as:
   implementation shipped, operational blockers remain for the full 29-paper
   rerun. This should be clarified in closeout language before handoff.

2. `jit-cache-check` printed instructions reference `/tmp/before_marker`
   without a prior `touch /tmp/before_marker` or equivalent marker creation
   step.

3. The L2.1 packet's acceptance table expects `had_fallback=False` after
   semantic fallback succeeds. That is workable, but the packet itself notes
   the semantics are ambiguous. Add a separate fallback-used field during
   implementation rather than relying only on overloaded `had_fallback`.

No contradiction found with the Marker-only RAG gate, pdfplumber legacy/debug
status, or "29-paper rerun is not ready" documentation.

---

## Verdict

PASS WITH CONCERNS.

WP-2 is safe as an observability/status packet and does not weaken parser quality
or academic RAG acceptance. It should not be treated as authorization to run the
full 29-paper validation yet. The docs now correctly soften readiness language.

L2.1 is scoped correctly and ready as a narrow implementation packet, with one
recommended addition: preserve clear result semantics by adding an explicit
semantic-fallback-used indicator.

---

## Recommended Next Action

Before the 29-paper run: make `--auto-timeout` warn or fail when pending items
lack cached prefetch manifest entries, and fix the `jit-cache-check` timestamp
marker instruction. Then run the JIT cache diagnostic and only proceed after
Tier-3 papers are explicitly approved or excluded.

For L2.1: proceed with the packet in order C, A, B, keeping fallback-only
semantic retrieval and render-time snippet sanitation.

---

## Codex Review Summary

Tier: recommended operational/code review for RIS marker queue changes.

Issues found:
- No parser-quality downgrade.
- No Tier 0/Tier 1 acceptance path.
- Readiness docs now say 29-paper rerun is not ready.
- Two non-blocking operational concerns: missing prefetch-data warning in
  `--auto-timeout`, and incomplete `jit-cache-check` timestamp-marker step.

Issues addressed:
- No implementation changes made per scope. This dev log records the review.
