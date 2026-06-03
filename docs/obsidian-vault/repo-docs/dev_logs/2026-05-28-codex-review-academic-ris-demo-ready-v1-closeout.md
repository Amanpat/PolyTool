---
title: Codex Review Academic Ris Demo Ready V1 Closeout
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-28_codex-review-academic-ris-demo-ready-v1-closeout.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - Academic RIS Demo-Ready v1 Closeout Docs

**Date:** 2026-05-28
**Reviewer:** Codex
**Scope:** Review only plus this dev log. No implementation code, runtime artifacts, Batch C/D, benchmark baselines, or unrelated docs changed.
**Verdict:** BLOCK - fix stale `CURRENT_DEVELOPMENT.md` Chroma-deferred language before marking Academic RIS v1 closed.

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/features/FEATURE-ris-academic-demo-ready-v1.md`
- `docs/dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md`
- `docs/dev_logs/2026-05-28_codex-review-academic-batch-b-closeout.md`

## Commands / Searches Run

```text
git status --short
git log --oneline -5
python -m polytool --help
```

Results:

- Worktree was dirty before this review.
- Closeout-relevant tracked doc diffs are limited to:
  - `docs/CURRENT_DEVELOPMENT.md`
  - `docs/CURRENT_STATE.md`
  - `docs/INDEX.md`
- The feature doc and closeout dev logs are untracked docs:
  - `docs/features/FEATURE-ris-academic-demo-ready-v1.md`
  - `docs/dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md`
  - `docs/dev_logs/2026-05-28_codex-review-academic-batch-b-closeout.md`
- Pre-existing unrelated implementation/test diffs remain in:
  - `packages/research/synthesis/academic_query.py`
  - `tests/test_research_query.py`
- `python -m polytool --help` exited 0 and listed `research-marker-queue` and `research-query`.

```text
rg -n -i "Chroma deferred|ChromaDB academic path deferred|not semantic|not vector retrieval|29-paper complete|29 paper complete|29-paper validation|full 29-paper|production-ready|production ready" docs\CURRENT_STATE.md docs\CURRENT_DEVELOPMENT.md docs\INDEX.md docs\features\FEATURE-ris-academic-demo-ready-v1.md docs\dev_logs\2026-05-28_academic-ris-demo-ready-v1-closeout.md docs\dev_logs\2026-05-28_codex-review-academic-batch-b-closeout.md
```

Key results:

- `docs/features/FEATURE-ris-academic-demo-ready-v1.md` correctly says developer/operator demo-ready and `NOT production-ready`.
- `docs/CURRENT_STATE.md` correctly says Batch 2 was not a valid 29-paper measurement, Batch C/D are deferred, and the feature is not production-ready.
- `docs/CURRENT_DEVELOPMENT.md:92` correctly records the new Recently Completed row with Chroma 917 chunks / 21 papers, PASS WITH CONCERNS, weather lexical false positive, Docker Chroma gap, JIT unresolved, Batch C/D deferred, and not production-ready.
- `docs/CURRENT_DEVELOPMENT.md:93` still says the older 3-paper validation left "ChromaDB academic retrieval (L2.1) remain deferred."
- `docs/CURRENT_DEVELOPMENT.md:155` still says "SSRN/NBER and ChromaDB academic retrieval (L2.1) remain deferred."
- The closeout dev log claims those stale notes were fixed, but the two `CURRENT_DEVELOPMENT.md` hits remain.

```text
rg -n -i "perfect|correctly rejected|unrelated.*reject|reject.*unrelated|weather forecast|protein folding|full 29|29-paper|29 paper|validation passed|passed validation" docs\CURRENT_STATE.md docs\CURRENT_DEVELOPMENT.md docs\INDEX.md docs\features\FEATURE-ris-academic-demo-ready-v1.md docs\dev_logs\2026-05-28_academic-ris-demo-ready-v1-closeout.md docs\dev_logs\2026-05-28_codex-review-academic-batch-b-closeout.md
```

Key results:

- No reviewed closeout doc claims full 29-paper validation passed.
- No reviewed closeout doc claims unrelated-query rejection is perfect.
- The weather lexical false positive remains visible in the feature doc, `CURRENT_STATE.md`, `INDEX.md`, and the two 2026-05-28 closeout/review dev logs.

```text
Select-String -Path docs\CURRENT_STATE.md -Pattern "Developer/Operator Demo-Ready v1|Not production-ready|Batch C/D deferred|weather forecast|full 29-paper|not a valid 29-paper|ChromaDB academic retrieval" -Context 1,2
Select-String -Path docs\CURRENT_DEVELOPMENT.md -Pattern "RIS Academic Pipeline.*Demo-Ready|weather lexical false positive|Batch C/D deferred|Not production-ready|ChromaDB academic retrieval|not semantic|ChromaDB academic path deferred" -Context 0,1
Select-String -Path docs\INDEX.md -Pattern "RIS Academic Pipeline.*Demo-Ready|Academic RIS.*Demo-Ready|weather lexical|Batch C/D|PASS WITH CONCERNS" -Context 0,1
Select-String -Path docs\features\FEATURE-ris-academic-demo-ready-v1.md -Pattern "NOT production-ready|not a production service|weather forecast|Batch C/D deferred|Tier-3 approval|20 papers|29-paper|perfect|full" -Context 1,1
```

Results:

- `CURRENT_STATE.md`, `INDEX.md`, and the feature doc align on demo-ready v1, not production-ready, Batch C/D deferred, and caveats visible.
- `CURRENT_DEVELOPMENT.md` has the new correct closeout row, but still has stale current-facing Chroma-deferred language in the older 3-paper row and Notes section.

## Closeout Protocol Verdict

BLOCK.

Protocol pieces exist:

- Feature doc exists: `docs/features/FEATURE-ris-academic-demo-ready-v1.md`
- `docs/INDEX.md` links the feature doc and related dev logs.
- `docs/CURRENT_DEVELOPMENT.md` moved Academic RIS demo-ready v1 to Recently Completed.

But the protocol is not clean because `CURRENT_DEVELOPMENT.md` still contains contradictory stale L2.1/Chroma deferred language after the new completion row.

## Consistency Verdict

BLOCK.

The feature doc, `INDEX.md`, and `CURRENT_STATE.md` are consistent:

- Academic RIS is developer/operator demo-ready v1.
- It is not production-ready.
- Batch C/D are deferred to post-v1 hardening / Tier-3 approval.
- The weather lexical false positive is visible.
- No full 29-paper validation pass is claimed.
- Unrelated-query rejection is explicitly not perfect.

`CURRENT_DEVELOPMENT.md` is not fully consistent:

- Line 93 says ChromaDB academic retrieval remains deferred in the older 3-paper validation row.
- Line 155 repeats the same stale deferred language in the Architect notes.

## Caveats Preserved

Preserved and visible:

- Weather lexical false positive from `arxiv:2605.00493`.
- Docker Chroma gap / Windows-host Chroma embedding fallback.
- JIT cache persistence unresolved.
- Batch C/D deferred; Tier-3 approval required for named papers.
- Not production-ready.

## Final Verdict

BLOCK.

Fix `docs/CURRENT_DEVELOPMENT.md` before marking Academic RIS v1 closed. The exact fix should update the two stale L2.1/Chroma deferred statements so they read as historical-at-the-time or explicitly note that L2.1 semantic retrieval was completed on 2026-05-25.

## Exact Next Action

Edit only `docs/CURRENT_DEVELOPMENT.md` to remove or qualify the two stale "ChromaDB academic retrieval (L2.1) remain deferred" statements, then re-run the stale-language search above. Do not run Batch C/D.
