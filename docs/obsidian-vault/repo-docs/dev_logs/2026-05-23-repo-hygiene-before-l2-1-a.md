---
title: Repo Hygiene Before L2 1 A
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-23_repo-hygiene-before-l2-1-a.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Repo Hygiene Before L2.1 Deliverable A

**Date:** 2026-05-23
**Status:** COMPLETE — L2.1 Deliverable A is safe to start

## Objective

Land or isolate all completed work groups before Chroma linkage (L2.1 Deliverable A) starts.
No implementation code was changed in this hygiene pass. All changes are git operations and
this dev log only.

## Branch and Commit Policy

- Branch: `main`
- Policy (CLAUDE.md): "Single branch: `main`. Commit and push directly to `main`."
- Commits executed: yes, two commits directly to `main`.

## File Groups

### WP-2 speed/observability + WP-2 review-concern fix (merged — shared files)

The two WP-2 sub-groups share `tools/cli/research_marker_queue.py` and
`tests/test_ris_marker_queue.py`. Splitting them requires hunk-level staging (`git add -p`),
which is complex on Windows PowerShell. Decision: land as one combined WP-2 commit.

**Files included:**
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_queue.py`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/CURRENT_STATE.md`
- `docs/dev_logs/2026-05-23_academic-wp2-speed-observability.md`
- `docs/dev_logs/2026-05-23_academic-processing-speed-diagnosis.md`
- `docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_codex-review-academic-speed-and-retrieval-plan.md`
- `docs/dev_logs/2026-05-23_l2-1-academic-retrieval-quality-packet.md`
- `docs/dev_logs/2026-05-23_codex-review-academic-wp2-and-l2-1-packet.md`
- `docs/dev_logs/2026-05-23_academic-wp2-review-concerns-fix.md`

**Commit:** `310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes`

### L2.1 Deliverable C snippet sanitation

**Files included:**
- `packages/research/synthesis/academic_query.py`
- `tests/test_research_query.py`
- `docs/specs/SPEC-ris-l2-1-academic-retrieval-quality.md`
- `docs/dev_logs/2026-05-23_l2-1-snippet-sanitation.md`
- `docs/dev_logs/2026-05-23_codex-review-l2-1-snippet-sanitation.md`
- `docs/dev_logs/2026-05-23_l2-1-deliverable-c-closeout-hygiene.md`

**Commit:** `3348e79 feat(ris): L2.1 Deliverable C — display-only snippet sanitation`

### Intentionally left dirty — Obsidian/vault/runtime/unrelated files

All paths under `docs/obsidian-vault/**` (modified, deleted, untracked), `docs/scripts/`,
and `docs/specs/vault-redesign-spec-v1.md` are intentionally not committed. These are
Obsidian plugin data, Smart Connections runtime `.ajson` embeddings, vault redesign content,
and local script scaffolding — unrelated to the RIS academic pipeline. They should be landed
as a separate operator-directed packet when ready.

## Commands Run and Results

### `git branch --show-current`
```
main
```

### `git status --short` (before staging)
Showed four groups: WP-2 Marker queue files, L2.1 Deliverable C files, unrelated Obsidian
files, and `docs/scripts/` / `docs/specs/vault-redesign-spec-v1.md`.

### `python -m pytest tests/test_research_query.py tests/test_ris_marker_queue.py -q --tb=short`
```
260 passed, 1 skipped in 3.55s
```
Run BEFORE staging to confirm baseline. All focused tests pass.

### Staging and commits
```
git add [WP-2 files]
git commit -m "feat(ris): WP-2 Marker queue speed observability and review-concern fixes"
# → 310e184, 12 files changed, 2652 insertions(+), 18 deletions(-)

git add [L2.1 Deliverable C files]
git commit -m "feat(ris): L2.1 Deliverable C — display-only snippet sanitation"
# → 3348e79, 6 files changed, 1154 insertions(+), 2 deletions(-)
```

### `git log --oneline -5` (final state)
```
3348e79 feat(ris): L2.1 Deliverable C — display-only snippet sanitation
310e184 feat(ris): WP-2 Marker queue speed observability and review-concern fixes
76db8a1 docs(ris): WP-1 cached PDF E2E closeout — PASS
22f9201 fix(ris): POSIX path separator in prefetch_pdfs for Docker/Linux compatibility
50775d1 feat(ris): WP-1 academic PDF prefetch separation
```

### `git status --short` (after commits)
Only `docs/obsidian-vault/**`, `docs/scripts/`, and `docs/specs/vault-redesign-spec-v1.md`
remain dirty — all intentionally excluded as described above.

## L2.1 Deliverable A Start Readiness

**SAFE TO START.**

All RIS academic pipeline work groups are landed:
- WP-2 speed/observability: committed (`310e184`)
- WP-2 review-concern fix: committed (`310e184`)
- L2.1 Deliverable C snippet sanitation: committed (`3348e79`)

The remaining dirty tree contains only Obsidian/vault/runtime files and an unrelated vault
spec — zero ambiguity about what belongs to L2.1 Deliverable A vs. what is already landed.

L2.1 Deliverable A (ChromaDB academic collection linkage) may begin immediately. Do not
commit Obsidian/vault files alongside Deliverable A code without an explicit operator
decision to do so.

## No L2.1 Deliverable A Work Started

Confirmed. No ChromaDB linkage, semantic retrieval, embedding, or `_query_chroma` code
was introduced in either commit above. The existing closeout hygiene doc
(`docs/dev_logs/2026-05-23_l2-1-deliverable-c-closeout-hygiene.md`) verified this
with a negative-scope grep before it was committed.
