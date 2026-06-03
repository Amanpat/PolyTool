---
title: L2 1 Deliverable B Closeout Hygiene
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-25_l2-1-deliverable-b-closeout-hygiene.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# L2.1 Deliverable B Closeout Hygiene

**Date:** 2026-05-25
**Author:** Claude Code (Sonnet 4.6)
**Commit:** b921857
**Status:** CLOSEOUT-CLEAN — 3-paper category sample is safe to start

---

## Objective

Isolate and commit the L2.1 one-paper acceptance repair files from the dirty working
tree so that the Codex PASS WITH CONCERNS finding (dirty tree) is resolved and the
L2.1 Deliverable B story is represented by two clean, auditable commits.

---

## Commits in the L2.1 Deliverable B Story

| SHA | Message |
|-----|---------|
| `7fc6bf2` | `fix(ris): L2.1 Deliverable B — offline-safe semantic fallback, resolves Codex BLOCK` |
| `b921857` | `fix(ris): L2.1 one-paper acceptance repair — Chroma embed, span strip, NTFS fallback` |

---

## Files Staged and Committed (b921857)

| Status | Path | Rationale |
|--------|------|-----------|
| M | `packages/research/ingestion/marker_queue.py` | NTFS U+F03A colon fallback + `_embed_body_into_chroma()` + `embed_chroma` flag |
| M | `packages/research/synthesis/academic_query.py` | `span` added to `_KNOWN_MARKER_TAGS`; `min_similarity` 0.30 → 0.18 |
| M | `tests/test_ris_marker_queue.py` | 695 lines of Chroma embedding tests (fake infra, offline-safe) |
| M | `tools/cli/research_marker_queue.py` | `--reindex-chroma`, `--chroma-path`, `check-chroma-links` subcommand |
| M | `tools/cli/research_query.py` | Exposes `retrieval_mode` + `semantic_unavailable_reason` in JSON output |
| M | `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Step 4c Chroma embedding documentation |
| A | `docs/dev_logs/2026-05-25_l2-1-one-paper-acceptance-repair.md` | Primary repair dev log |
| A | `docs/dev_logs/2026-05-25_codex-review-l2-1-one-paper-acceptance-repair.md` | Codex PASS WITH CONCERNS review |

---

## Files Intentionally Left Dirty

### Root-doc modifications — require Director review
| Path | Reason left dirty |
|------|-------------------|
| `AGENTS.md` | Unrelated root-doc edit; Director review required before committing |
| `claude.md` | Unrelated root-doc edit; Director review required before committing |

### Orphaned dev logs from prior L2.1 sessions (2026-05-23)
These six logs were created during earlier L2.1 work packets (chroma linkage fix,
semantic fallback block fix) that were committed as code but whose dev logs were
never staged. They should be committed in a separate dev-log cleanup commit.

| Path |
|------|
| `docs/dev_logs/2026-05-23_codex-review-l2-1-chroma-linkage.md` |
| `docs/dev_logs/2026-05-23_codex-review-l2-1-semantic-fallback-block-fix.md` |
| `docs/dev_logs/2026-05-23_codex-review-l2-1-semantic-fallback.md` |
| `docs/dev_logs/2026-05-23_l2-1-chroma-linkage-command-contract-fix.md` |
| `docs/dev_logs/2026-05-23_l2-1-chroma-linkage.md` |
| `docs/dev_logs/2026-05-23_l2-1-semantic-fallback-block-fix.md` |

### Orphaned dev logs from today — prior sub-features (2026-05-25)
The offline-safe fix code was committed in `7fc6bf2` but the corresponding Codex
reviews and the fast-fail dev log were not staged alongside it. These belong to
the prior L2.1 Deliverable B sub-features. Recommend committing them in a
dev-log cleanup commit alongside the 2026-05-23 set.

| Path | Notes |
|------|-------|
| `docs/dev_logs/2026-05-25_codex-review-l2-1-semantic-fallback-block-fix.md` | Codex review for block fix (committed in earlier SHA) |
| `docs/dev_logs/2026-05-25_codex-review-l2-1-semantic-fallback-fast-fail.md` | Codex review for fast-fail (committed in earlier SHA) |
| `docs/dev_logs/2026-05-25_codex-review-l2-1-semantic-fallback-offline-safe-fix.md` | Codex review for offline-safe fix (feature in 7fc6bf2) |
| `docs/dev_logs/2026-05-25_l2-1-semantic-fallback-fast-fail.md` | Dev log for fast-fail sub-feature |

### Hygiene dev log
| Path | Notes |
|------|-------|
| `docs/dev_logs/2026-05-25_repo-hygiene-after-4788871.md` | Documents the soft-reset that split commit 4788871; safe to commit standalone as `chore(docs): L2.1 commit hygiene — split vault/code in 4788871` |

### Other unrelated untracked
| Path | Notes |
|------|-------|
| `docs/scripts/` | Unrelated directory; Director review |
| `docs/specs/vault-redesign-spec-v1.md` | Vault spec; Director review |
| `docs/obsidian-vault/` | All vault churn (plugins, config, legacy/); Director review |

---

## Commands Run + Output

```
$ python -m pytest tests/test_research_query.py tests/test_ris_marker_queue.py -q --tb=short
299 passed, 1 skipped in 6.03s

$ python -m polytool research-marker-queue check-chroma-links --json
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

$ git diff --cached --name-status   # before commit
A  docs/dev_logs/2026-05-25_codex-review-l2-1-one-paper-acceptance-repair.md
A  docs/dev_logs/2026-05-25_l2-1-one-paper-acceptance-repair.md
M  docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md
M  packages/research/ingestion/marker_queue.py
M  packages/research/synthesis/academic_query.py
M  tests/test_ris_marker_queue.py
M  tools/cli/research_marker_queue.py
M  tools/cli/research_query.py

$ git commit -m "fix(ris): L2.1 one-paper acceptance repair..."
[main b921857] ... 8 files changed, 1588 insertions(+), 26 deletions(-)
```

---

## Chroma Link-Check Result

PASS. 162 chunks, 5 papers, `missing_ks_doc_id=0`, `ks_doc_id_not_in_ks=0`.

---

## Is L2.1 Deliverable B Closeout-Clean?

**YES.** Both the Deliverable B offline-safe semantic fallback (`7fc6bf2`) and the
one-paper acceptance repair (`b921857`) are committed as isolated, auditable units.
The Codex PASS WITH CONCERNS finding was dirty-tree only; it is now resolved for
the L2.1 acceptance repair scope.

---

## Is 3-Paper Category Sample Safe to Start?

**YES.** Prerequisites met:

1. `academic_papers` Chroma collection contains `arxiv:2510.05533` with 162 chunks.
2. Chroma linkage is clean (0 orphaned chunks).
3. Semantic acceptance queries return `2510.05533` for LLM-topic questions.
4. `weather forecast` is correctly rejected (`had_fallback=true`, 0 citations).
5. All 4 acceptance query tiers pass per Codex review.
6. L2.1 code is in a clean commit; working tree no longer contains L2.1 repair changes.

**Recommended next step:** 3-paper category sample — one paper from a distinct academic
category (e.g., sports analytics or macro economics) plus `arxiv:2510.05533`. Confirm:
(a) both papers land in `academic_papers`, (b) a category-specific query returns the
right paper and not the other, (c) `check-chroma-links` remains clean after second
ingestion.

---

## Open Questions for Director

1. Commit the 2026-05-23 and orphaned 2026-05-25 dev logs in a standalone
   `docs(ris): commit orphaned L2.1 dev logs from 2026-05-23 and 2026-05-25`?
2. Commit `docs/dev_logs/2026-05-25_repo-hygiene-after-4788871.md` alone as
   `chore(docs): commit hygiene log for 4788871 soft-reset`?
3. Stage and commit `AGENTS.md` and `claude.md` modifications?
