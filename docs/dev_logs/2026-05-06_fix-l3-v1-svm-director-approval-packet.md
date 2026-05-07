# Fix — L3 v1 SVM Director Approval Packet Wording

**Date:** 2026-05-06
**Track:** Research Intelligence System — L3 v1 SVM Topic Filter
**Scope:** Docs only. No code, tests, labels, artifacts, feature docs, INDEX, or L2/L4/Marker changes.
**Type:** Codex FAIL remediation — wording inaccuracies in director approval packet

---

## Why This Fix Exists

Codex reviewed `docs/dev_logs/2026-05-06_l3-v1-svm-director-approval-packet.md` and returned
FAIL with two blocking findings. The underlying evidence (156 labels, eval metrics, artifacts)
was verified correct. Only the decision/flag language was wrong.

---

## Codex Findings and Resolutions

### Finding 1 — Wrong flag name for `research-prefetch-discover`

**Codex finding:** The packet's Current State table claimed SVM is available via
`--prefetch-filter-scorer svm` on both `research-acquire` and `research-prefetch-discover`.
The actual flag on `research-prefetch-discover` is `--filter-scorer svm`, not
`--prefetch-filter-scorer svm`.

**Verification:**
```
python -m polytool research-prefetch-discover --help
  → --filter-scorer {lexical,svm}    (no --prefetch-filter-scorer flag)

python -m polytool research-acquire --help
  → --prefetch-filter-scorer {lexical,svm}
```

**Resolution:** Updated Current State table Integration row to name each command separately
with its correct flag:
- `research-acquire`: `--prefetch-filter-scorer svm`
- `research-prefetch-discover`: `--filter-scorer svm`

---

### Finding 2 — Option 1 described dry-run/hold-review as needing to be unlocked

**Codex finding:** Decision 2 / Option 1 said to "unlock `--prefetch-filter-scorer svm` with
`--prefetch-filter-mode dry-run` or `hold-review`" and listed "What changes in code: Remove
the enforce-specific rc=1 guard only for dry-run/hold-review paths." This is inaccurate.
Current code already permits SVM dry-run and hold-review with an explicit model path. Only
`enforce` is blocked at rc=1.

**Verification:** The enforce block error message from Codex's own run:
```
Error: SVM enforce is blocked until >=150 labels and Director approval.
Use --prefetch-filter-mode dry-run or hold-review for evidence collection.
```
The error message itself confirms dry-run/hold-review are the un-blocked alternatives.

**Resolution:** Rewrote Decision 2 / Option 1:
- Title changed from "Staged unlock — score-only first, enforce separate prompt" to
  "Approve continued default-off, score-only evidence collection"
- Added explicit statement: "SVM dry-run and hold-review modes are already available with
  an explicit scorer flag and model path — no code unlock is required."
- "What changes in code" changed from "Remove the enforce-specific rc=1 guard…" to
  "Nothing. Dry-run and hold-review already work with explicit flags. The enforce rc=1
  guard stays in place. The only remaining code decision is whether to remove or modify
  the enforce block — that is a separate prompt."

---

### What Happens Next table — Option 1 rows corrected

Two rows in the "What Happens Next" table reflected the same false premise:

- **A + 1** previously said "Remove dry-run/hold-review guard only" → corrected to
  "No code change — dry-run/hold-review already work"
- **B + 1** previously said "then unlock dry-run/hold-review" → corrected to
  "then write feature doc scoped to score-only (dry-run/hold-review already work)"

---

## Files Changed

| File | Change | Why |
|---|---|---|
| `docs/dev_logs/2026-05-06_l3-v1-svm-director-approval-packet.md` | 4 targeted edits | Codex FAIL remediation — flag name + Option 1 unlock language |
| `docs/dev_logs/2026-05-06_fix-l3-v1-svm-director-approval-packet.md` | Created (this file) | Mandatory dev log per session conventions |

No code, tests, labels, artifacts, feature docs, INDEX.md, CURRENT_DEVELOPMENT.md,
or L2/L4/Marker IPC files were touched.

---

## Commands Run

```
python -m polytool research-prefetch-discover --help
  → --filter-scorer {lexical,svm}  ✓ confirms correct flag for discovery command

python -m polytool research-acquire --help
  → --prefetch-filter-scorer {lexical,svm}  ✓ confirms correct flag for acquire command

git status --short docs/dev_logs/2026-05-06_l3-v1-svm-director-approval-packet.md
  → ?? (untracked — git diff shows nothing; edits verified via grep)
```

---

## Packet Readiness

The approval packet is now accurate and ready for Codex re-review:

- Flag names match CLI help output for both commands
- Option 1 no longer implies dry-run/hold-review need a code unlock
- Only enforce remains blocked at rc=1
- Evidence summary unchanged: 156 labels, 74/82, train=117, test=39,
  macro-F1=1.000, confusion matrix [[19,0],[0,20]]
- Artifact paths, caveats, Director decision options, and reply template all intact

---

## Remaining Director Decisions

The packet still requires explicit Director signoff on:

1. **Model selection** — Option A (declare bge-large production), Option B (block until
   SPECTER2 resolved), or Option C (close without enforce)
2. **Enforce scope** — Option 1 (keep blocked, accumulate score-only evidence — no code
   change), Option 2 (approve guarded enforce now), or Option 3 (do not unlock enforce)

Feature 3 remains Active. Enforce guard at rc=1 is unchanged. No feature closeout.

---

## Codex Review Summary

Tier: Skip — docs-only fix session. No implementation code, tests, labels, artifacts,
live-trading paths, risk manager, rate limiter, or kill-switch code changed.
Issues addressed: two blocking wording inaccuracies from prior Codex FAIL.
