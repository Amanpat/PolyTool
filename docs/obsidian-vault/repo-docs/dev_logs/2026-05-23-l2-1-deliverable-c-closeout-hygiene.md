---
title: L2 1 Deliverable C Closeout Hygiene
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-23_l2-1-deliverable-c-closeout-hygiene.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L2.1 Deliverable C Closeout Hygiene

**Date:** 2026-05-23
**Status:** CLOSED - hygiene audit complete

## Objective

Close the L2.1 Deliverable C worktree-hygiene concern by separating the dirty tree into
work packets, verifying the snippet-sanitation patch stayed in scope, and documenting the
safe next landing order before L2.1 Deliverable A starts.

No implementation code, tests, parser settings, ChromaDB linkage, semantic retrieval,
benchmark baselines, GPU parsing, or 29-paper artifacts were changed in this closeout.

## Worktree Groups

### WP-2 speed / observability

Files:
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_queue.py`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/CURRENT_STATE.md`
- `docs/dev_logs/2026-05-23_academic-wp2-speed-observability.md`
- Supporting diagnostics/planning logs:
  - `docs/dev_logs/2026-05-23_academic-processing-speed-diagnosis.md`
  - `docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md`
  - `docs/dev_logs/2026-05-23_codex-review-academic-speed-and-retrieval-plan.md`
  - `docs/dev_logs/2026-05-23_l2-1-academic-retrieval-quality-packet.md`
  - `docs/dev_logs/2026-05-23_codex-review-academic-wp2-and-l2-1-packet.md`

Scope verified:
- Adds queue observability fields (`sidecar_count`, `indexed_count`,
  `timeout_risk_items`).
- Adds ingest tier metadata and tier validation for Marker queue items.
- Adds file-size-based timeout recommendation and `warm-process --auto-timeout`.
- Adds `jit-cache-check` diagnostic text/JSON.
- Updates runbook and CURRENT_STATE to say the full 29-paper rerun is not ready.

Dev log exists: `docs/dev_logs/2026-05-23_academic-wp2-speed-observability.md`.

### WP-2 review-concern fix

Files:
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_queue.py`
- `docs/dev_logs/2026-05-23_academic-wp2-review-concerns-fix.md`

Scope verified:
- `--auto-timeout` now fails fast when pending items lack cached prefetch manifest
  data unless `--allow-uncached` is explicitly passed.
- `jit-cache-check` instructions now include `touch /tmp/before_marker` before the
  later `find ... -newer /tmp/before_marker` step.

Dev log exists: `docs/dev_logs/2026-05-23_academic-wp2-review-concerns-fix.md`.

Note: these changes share files with WP-2 speed / observability. If landing as separate
commits, split the relevant hunks in `tools/cli/research_marker_queue.py` and
`tests/test_ris_marker_queue.py`.

### L2.1 Deliverable C snippet sanitation

Files:
- `packages/research/synthesis/academic_query.py`
- `tests/test_research_query.py`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_l2-1-snippet-sanitation.md`
- `docs/dev_logs/2026-05-23_codex-review-l2-1-snippet-sanitation.md`

Scope verified:
- `academic_query.py` only adds `re`, display-only snippet sanitizer regexes,
  `_sanitize_snippet()`, and applies the sanitizer to `AcademicCitation.best_snippet`.
- Raw KnowledgeStore `claim_text` is not mutated.
- `tests/test_research_query.py` only adds sanitizer unit/integration coverage.
- No ChromaDB linkage, semantic retrieval fallback, parser quality change, SVM enforce
  change, or benchmark baseline change is present in the L2.1 code diff.

Dev logs exist:
- `docs/dev_logs/2026-05-23_l2-1-snippet-sanitation.md`
- `docs/dev_logs/2026-05-23_codex-review-l2-1-snippet-sanitation.md`

### Unrelated / local / Obsidian / runtime files

Files:
- Modified/deleted/untracked paths under `docs/obsidian-vault/**`, including `.obsidian`,
  `.smart-env`, `claude-memory`, `repo-docs`, templates, session notes, and plugin files.
- `docs/scripts/`
- `docs/specs/vault-redesign-spec-v1.md`

These are unrelated to WP-2 Marker queue work and L2.1 snippet sanitation. Do not include
them in the WP-2 or L2.1 Deliverable C commits unless the operator explicitly lands the
Obsidian/vault work as its own packet.

## Negative-Scope Verification

Checked changed RIS files for:

```
academic_papers|semantic_fallback|_query_chroma|chromadb|ChromaDB|sentence_transformer|embedding|SVM|enforce
```

Result:
- No new Chroma linkage or semantic fallback appears in implementation files.
- `academic_query.py` still contains only the existing docstring note that this version
  does not query ChromaDB.
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` and `docs/CURRENT_STATE.md` mention
  ChromaDB/SVM only as existing/deferred status text.
- No parser quality setting, SVM enforce, benchmark manifest, or Gate 2 baseline file was
  changed.

## CURRENT_STATE.md

No additional edit was needed in this closeout. The existing dirty diff already corrects
the overstatement from "29-paper rerun safe to proceed" to "NOT YET READY" and lists the
remaining WP-2 blockers:
- JIT cache persistence unconfirmed.
- Three timeout-risk papers require Tier-3 classification and operator approval.
- Use `--auto-timeout` or explicit longer timeouts after `jit-cache-check`.

The file does not overstate L2.1 readiness: ChromaDB academic retrieval remains deferred,
and L2.1 Deliverables A/B are not described as complete.

## Commands Run

### `git status --short`

Result: dirty tree with four groups:
- WP-2 Marker queue/runbook/current-state files:
  - `docs/CURRENT_STATE.md`
  - `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
  - `packages/research/ingestion/marker_queue.py`
  - `tests/test_ris_marker_queue.py`
  - `tools/cli/research_marker_queue.py`
  - WP-2 dev logs listed above
- L2.1 Deliverable C files:
  - `packages/research/synthesis/academic_query.py`
  - `tests/test_research_query.py`
  - L2.1 spec/review/dev logs listed above
- Unrelated local/Obsidian/runtime files:
  - many modified/deleted/untracked paths under `docs/obsidian-vault/**`
  - `docs/scripts/`
  - `docs/specs/vault-redesign-spec-v1.md`
- No benchmark, Chroma academic collection, semantic retrieval, parser setting, or
  full 29-paper artifact paths were present in the relevant code groups.

### `git log --oneline -5`

```text
76db8a1 docs(ris): WP-1 cached PDF E2E closeout - PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
50775d1 feat(ris): WP-1 academic PDF prefetch separation
1fb000d Academic Pipeline Improvements/Testing
de72208 docs(ris): academic pipeline scaled validation - Batch 1 execution record
```

### `python -m polytool --help`

Result: exit 0. CLI loaded and listed both `research-query` and
`research-marker-queue`.

### `python -m pytest tests/test_research_query.py tests/test_ris_marker_queue.py -q --tb=short`

```text
collected 261 items
260 passed, 1 skipped in 3.32s
```

### `python -m pytest tests/ -x -q --tb=short`

```text
collected 5207 items / 3 deselected / 5204 selected
command timed out after 180329 milliseconds
```

The full stop-at-first-failure run did not reach the known Phase 4 failure before the
timeout. It reached `tests/test_ris_fetchers.py` after passing the earlier files shown in
the console output.

### `python -m pytest tests/test_ris_phase4_source_acquisition.py::TestEndToEnd -q --tb=short`

```text
collected 7 items
3 failed, 4 passed in 1.13s
```

Failures:
- `test_ingest_external_arxiv_fixture`
- `test_ingest_external_with_cache`
- `test_ingest_external_metadata_canonical_ids_preserved`

Root cause is unchanged and unrelated to L2.1 Deliverable C: the Phase 4 fixture expects
abstract-only academic ingestion to pass, but the current academic Marker gate rejects
`body_source='abstract'` with `body_length=0`. This same pre-existing TestEndToEnd failure
set is documented in prior dev logs, including
`docs/dev_logs/2026-05-13_academic-scaled-validation-packet.md` and
`docs/dev_logs/2026-05-13_l5-v0-1-current-marker-rerun.md`.

## Recommended Landing Order

1. **WP-2 speed / observability**
   - Land queue status/timeout/tier diagnostics, runbook updates, CURRENT_STATE correction,
     and `docs/dev_logs/2026-05-23_academic-wp2-speed-observability.md`.
2. **WP-2 review-concern fix**
   - Land `--auto-timeout` uncached fail-fast / `--allow-uncached` and
     `jit-cache-check` `/tmp/before_marker` instruction fix with
     `docs/dev_logs/2026-05-23_academic-wp2-review-concerns-fix.md`.
3. **L2.1 Deliverable C**
   - Land `academic_query.py`, `tests/test_research_query.py`, L2.1 spec packet/log,
     snippet-sanitation dev log, and Codex review log.
4. **Codex review / test cleanup**
   - Land any remaining review-only documentation or test-only cleanup after the three
     functional packets are isolated.
5. **Unrelated Obsidian/vault/runtime files**
   - Keep separate from RIS academic pipeline commits.

## Safe Next Action

L2.1 Deliverable A is safe to start after the above groups are landed or otherwise isolated
from the working tree. Do not start Deliverable A from the current mixed dirty tree because
it would combine Chroma linkage work with unrelated WP-2 and Obsidian/runtime changes.

