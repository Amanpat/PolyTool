---
title: L3 V1 Svm Feature Closeout
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_l3-v1-svm-feature-closeout.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L3 v1 SVM Topic Filter — Feature Closeout

Date: 2026-05-07
Track: Research Intelligence System — L3 v1
Scope: Docs-only closeout. No code, tests, labels, model artifacts, or enforce behavior changed.

---

## Director Decision

**Approved:** `BAAI/bge-large-en-v1.5` as the L3 v1 SVM production model for default-off use.

**Enforce deferred:** SVM enforce remains hard-blocked at rc=1. Requires explicit future
Director approval before autonomous rejection is enabled. This closeout does NOT unblock enforce.

**Scope of closeout:** Feature 3 closed as default-off integrated / dry-run + hold-review ready,
with enforce explicitly deferred.

---

## Completion Protocol Checklist

1. [x] **Feature doc created** — `docs/features/FEATURE-ris-svm-filter-v1.md`
2. [x] **INDEX updated** — feature row added under Features table; 5 dev log entries added under Recent Dev Logs
3. [x] **CURRENT_DEVELOPMENT moved to Recently Completed** — Feature 3 removed from Active; row added to Recently Completed table; Architect note added; last_verified bumped to 2026-05-07
4. [x] **CURRENT_STATE.md updated** — new section "RIS L3 v1 SVM Topic Filter — Default-Off Integrated (2026-05-07)" appended
5. [x] **Obsidian Current-Focus.md updated** — frontmatter date, Active Priorities blurb, L3 table row, Recent Session Context entry, footer date
6. [x] **Work Packet updated** — frontmatter status=closed, Current Step updated, all DoD checkboxes checked, Blockers resolved, Director decision recorded

---

## Files Changed

| File | Change |
|---|---|
| `docs/features/FEATURE-ris-svm-filter-v1.md` | Created — full feature doc |
| `docs/INDEX.md` | Feature row + 5 dev log entries added |
| `docs/CURRENT_STATE.md` | L3 v1 SVM section appended |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 moved to Recently Completed; Architect note; last_verified updated |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Frontmatter, priorities, L3 table row, session context, footer |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - L3 v1 SVM Topic Filter Training.md` | Status closed; DoD all checked; blockers resolved |
| `docs/dev_logs/2026-05-07_l3-v1-svm-feature-closeout.md` | This file |

**Not touched:** implementation code, tests, labels, model artifacts, L2/L4 docs, Marker IPC warm-worker code.

---

## Evidence Summary

| Metric | Value |
|---|---|
| label_count | 156 |
| allow_count | 74 |
| reject_count | 82 |
| train_size | 117 |
| test_size | 39 |
| seed | 42 |
| embedding_model | BAAI/bge-large-en-v1.5 |
| model_type | LinearSVC |
| accuracy | 1.000 |
| macro F1 | 1.000 |
| confusion_matrix | [[19, 0], [0, 20]] |
| lexical baseline (Scenario B) | 5.88% off-topic |
| targeted SVM tests | 123 pass |
| labels SHA256 | 56CEBCC2210BA7FF1A47BA1CB6A64DE649472833D23FB9D3EB4E38BEC387767E |

Expanded artifact path: `artifacts/research/svm_filter_models/expanded_156/`

Prior 61-label artifacts in `artifacts/research/svm_filter_models/` — untouched.

---

## Safety Posture

- Lexical scorer v1.1 remains the default on both `research-acquire` and `research-prefetch-discover`.
- SVM activates only with `--prefetch-filter-scorer svm` + `--prefetch-svm-model PATH` (acquire)
  or `--filter-scorer svm` + `--svm-model PATH` (discover).
- SVM enforce returns `rc=1` with message: "SVM enforce is blocked until >=150 labels and
  Director approval." The label gate is now met; the enforce block requires a new explicit
  Director approval to lift — this closeout does NOT lift it.
- Dry-run and hold-review are safe: no ingestion is blocked or silently lost.
- No behavior changes in default paths. No silent scope creep.

---

## Commands Run (verification)

### git diff -- docs/features/FEATURE-ris-svm-filter-v1.md docs/INDEX.md docs/CURRENT_STATE.md docs/CURRENT_DEVELOPMENT.md

Confirms: feature doc created (new file); INDEX, CURRENT_STATE.md, CURRENT_DEVELOPMENT.md
all have diff content matching closeout edits.

### python -m polytool research-prefetch-review counts --json

Expected (from prior Codex verify session, unchanged):
```json
{
  "total_queued": 159,
  "pending_unlabeled": 3,
  "labeled_total": 156,
  "labeled_allow": 74,
  "labeled_reject": 82
}
```

No label counts changed by this docs-only session.

### python -m polytool research-acquire --help (enforce guard)

SVM enforce flag still present and blocked. Expected output includes:
```
--prefetch-filter-scorer {lexical,svm}
    ...enforce mode is blocked for SVM until >=150 labels and Director approval.
```

### python -m polytool research-prefetch-discover --help

SVM scorer flag present. Expected output includes:
```
--filter-scorer {lexical,svm}
    ...svm: use trained SVM model - requires --svm-model.
```

---

## Remaining Deferred Work

| Item | Status |
|---|---|
| SVM enforce | Deferred. Requires future Director approval. Label gate (>=150) met; enforce block is a policy gate, not a technical gate. |
| SPECTER2 integration | Deferred indefinitely. Director chose BGE-large (Option C). |
| Marker Docker IPC warm-worker (v1) | Deferred from Queue v0 (2026-05-05). **NOT canceled.** Must be revisited now that L3/SVM stream is complete, or before L2 production launch (whichever comes first). See Paused/Deferred row in CURRENT_DEVELOPMENT.md. |
| L2 PaperQA2 activation | Stub. Gated on L1 Marker Docker IPC warm-worker v1. Do NOT start L2 yet. |
| L4 multi-source harvesters | Stub. Gated on L1 + L3. |

---

## Codex Review Summary

Tier: Skip — docs-only changes. No implementation code, tests, live-trading paths,
risk manager, rate limiter, or kill-switch code was changed.

Issues found: none.
Issues addressed: none.
