---
title: Fix L3 V1 Svm Smoke Doc Caveats
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-06_fix-l3-v1-svm-smoke-doc-caveats.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix — L3 v1 SVM Smoke Doc Caveats (Codex Cleanup)

**Date:** 2026-05-06
**Author:** Claude Code (docs-only session)
**Scope:** Documentation corrections per Codex PASS-with-cleanup verdict. No implementation code, tests, labels, artifacts, or feature docs modified.

---

## Objective

Resolve the three docs-cleanup items Codex flagged before allowing Feature 3 closeout:
1. `peft` contradiction between Blockers, Architect note, and Work Packet.
2. Work Packet DoD checkboxes not aligned with evidence already recorded in CURRENT_DEVELOPMENT.md.
3. Wording implying live hold-review real-artifact smoke completed when it was blocked by arXiv HTTP 429.

---

## Files Changed

### `docs/CURRENT_DEVELOPMENT.md`

**A. Feature 3 Blockers section** — removed stale separate `` `peft` `` bullet; consolidated into SPECTER2 bullet with explicit clarification that `peft` is NOT in `pyproject.toml` ris-svm extras and NOT needed for the current BAAI/bge-large-en-v1.5 validated path.

**B. Feature 3 Current step** — replaced "Dry-run and hold-review paths execute against real model artifact" with language that is specific about what was and was not tested:
- Dry-run paths: PASS (acquire: arXiv 1802.06101; discover: 5-paper query)
- Live hold-review real-artifact smoke: NOT COMPLETED — arXiv HTTP 429 after prior API calls; hold-review queue behavior covered by 52 passing discovery tests

**C. Architect note (Feature 3 bullet)** — two fixes:
- Removed "Dry-run and hold-review paths execute against real model artifact" wording; replaced with same dry-run/hold-review distinction as Current step.
- Replaced "(2) `` `peft` `` added to `pyproject.toml` ris-svm extras (done in integration commit)" (false claim) with accurate statement: `` `peft` `` is NOT in `pyproject.toml` ris-svm and NOT needed for bge-large path; only needed if SPECTER2 AdapterHub path is chosen. Reduced to two enforcement blockers (was three).

### `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md`

**A. DoD checkboxes** — checked off 6 items whose evidence was already in CURRENT_DEVELOPMENT.md but left unchecked in the Work Packet:

| Item | Before | After |
|---|---|---|
| Train/eval CLI exists and runs end-to-end on real labels | `[ ]` | `[x]` |
| Uses existing `labels.jsonl` without format changes | `[ ]` | `[x]` |
| Embedding path is cacheable; cached embeddings re-used | `[ ]` | `[x]` |
| Evaluation report: precision, recall, F1, confusion matrix, baseline comparison | `[ ]` | `[x]` |
| Exported model artifact includes metadata/ledger | `[ ]` | `[x]` |
| Graceful failure if `sentence-transformers` or `scikit-learn` not installed | `[ ]` | `[x]` |

Remaining unchecked (correctly): feature doc, CURRENT_STATE.md update, closeout dev log.

**B. Open environment issues item 2** — replaced false claim "added to `ris-svm` extras in the integration commit" with accurate statement: `peft` is NOT in `pyproject.toml` ris-svm extras and NOT needed for the current BAAI/bge-large-en-v1.5 path; only relevant if SPECTER2 AdapterHub path is chosen.

**C. Smoke test table** — added explicit NOT COMPLETED row for live hold-review real-artifact smoke (arXiv HTTP 429; covered by 52 passing discovery tests).

### `docs/obsidian-vault/Claude Desktop/Current-Focus.md`

**A. Frontmatter** — updated `updated:` field to reflect this session.

**B. Recent Session Context** — prepended new entry documenting all three Codex cleanup items resolved, with reference to this dev log. Historical entries (including the "readiness decision" entry that mentioned adding `peft`) left intact as-is; they record intent at the time, and the correction is captured in the new entry.

---

## Codex Cleanup Item Resolution

| Item | Resolution |
|---|---|
| `peft` contradiction (Architect note false claim) | Fixed: "(done in integration commit)" removed; accurate statement that `peft` is NOT in pyproject.toml and NOT needed for bge-large path |
| `peft` stale separate Blocker bullet | Fixed: removed; content consolidated into SPECTER2 bullet |
| `peft` false "added" claim in Work Packet | Fixed: replaced with accurate NOT-in-extras statement |
| Work Packet DoD checkboxes misaligned | Fixed: 6 items checked off (train/eval, labels, cache, eval-report, metadata-ledger, graceful-fail) |
| Hold-review smoke wording overstates evidence | Fixed: "NOT COMPLETED — arXiv HTTP 429" row added to smoke table; current-step and Architect note now distinguish dry-run PASS from hold-review NOT COMPLETED |

---

## Remaining Blockers (unchanged — no new unblocks)

| Item | Status |
|---|---|
| Operator model selection decision | PENDING — SPECTER2 options (adapters lib / specter2_base download) or declare bge-large-en-v1.5 production |
| Label corpus expansion to >=150 | PENDING — current: 61 labels (30 allow / 31 reject) |
| Director approval to unlock enforce | PENDING — explicit gate, cannot be bypassed |
| `docs/features/FEATURE-ris-svm-filter-v1.md` | NOT CREATED — requires Director closeout approval first |
| `docs/CURRENT_STATE.md` RIS L3 v1 section | NOT UPDATED — same |

Feature 3 remains **Active — integrated but enforce-blocked**. Not moved to Recently Completed.

---

## Closeout Status

**Closeout remains blocked.** Codex PASS covered the narrow "default-off integrated; enforce-blocked" status. Closeout requires:
- Label corpus >=150 (currently 61)
- Director approval to unlock enforce OR explicit Director decision to close at dry-run/hold-review capability only
- Feature doc creation
- CURRENT_STATE.md update

---

## Next Recommended Prompt

**Label expansion session** — run `research-prefetch-discover --decision-filter all --include-allow` queries to push label count from 61 toward 150. Each session adds candidates to the review queue; label via `research-prefetch-review label`. Track progress with `research-prefetch-review counts --json`.

Alternatively, **model selection decision**: operator picks one of (a) `pip install adapters` for SPECTER2 AdapterHub, (b) download `allenai/specter2_base`, or (c) declare `BAAI/bge-large-en-v1.5` as production. This does not unlock enforce but resolves the SPECTER2 blocker and clarifies the `peft` question permanently.

---

## Codex Review Summary

Tier: Skip — no implementation code changed. Docs-only corrections per Codex cleanup requirement.
