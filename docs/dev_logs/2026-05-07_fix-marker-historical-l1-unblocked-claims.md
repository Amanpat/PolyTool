# Fix — Marker Historical L1 Rollout-Cleared Claims

Date: 2026-05-07
Type: docs-only cleanup / stale-claim correction
Precursor: `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-fixed.md` (FAIL — stale claims in hosting decision note and 2026-05-03 dev log)

---

## Summary

Two historical docs contained standalone positive claims that L1 Marker production rollout
was cleared. These claims were accurate on 2026-05-03 with respect to the *hosting blocker*
but became stale on 2026-05-05 when the Marker Docker IPC warm-worker v1 requirement was
identified, and were formally superseded on 2026-05-07 when Feature 3 was activated.

This fix adds dated correction notes and rewords the stale phrases without erasing the
historical hosting-decision record.

No implementation code, tests, artifacts, SVM labels/models, L2/PaperQA2, L4, or trading
files were touched.

---

## Files Changed

### 1. `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`

**Stale claim (line 15):**
```
**ACCEPTED — 2026-05-02. All open questions answered. Docker GPU passthrough verified.
L1 Marker production rollout is unblocked.**
```

**Corrected to:**
```
**ACCEPTED — 2026-05-02. Hosting blocker resolved. All open questions answered. Docker GPU
passthrough verified.** *(CORRECTION 2026-05-07: Prior rollout-cleared wording in this
status line is superseded. L1 Marker production rollout remains blocked by Marker Docker
IPC warm-worker v1 — Feature 3, active as of 2026-05-07. This decision resolved only the
hosting question, not overall L1 rollout readiness. L1 ships when Feature 3 acceptance
gates pass: ≥3 warm papers in one session, ≤10s/paper for papers 2+.)*
```

**Why:** The status line read as a current positive claim to any prompt designer reading
this file. The fix preserves that the hosting decision was resolved while making clear that
overall L1 rollout remains blocked.

---

### 2. `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`

Three changes applied:

**A. Added correction block near top (before Summary):**

A blockquote correction note was inserted explaining that:
- The hosting blocker was resolved on 2026-05-03 (historical fact preserved).
- Prior rollout-cleared wording applied only to the hosting question.
- Current L1 rollout remains blocked by Feature 3 (Marker Docker IPC warm-worker v1).
- Current rollout status is superseded by 2026-05-07 activation.

**B. Summary section final sentence:**

Before: `...L1 is unblocked.`
After: `...Hosting blocker resolved; current L1 rollout status is superseded by 2026-05-07 Marker Docker IPC warm-worker v1.`

**C. Section header and content (was "Is L1 unblocked?" / YES):**

Before:
```
## Is L1 unblocked?
**YES.** The only gate was the hosting decision. That gate is now cleared:
...
[[Work-Packet - Marker Structural Parser Integration]] may proceed to implementation.
```

After:
```
## Was the hosting blocker cleared?
**YES — as of 2026-05-03, the hosting blocker was cleared.** The only gate known at this
writing was the hosting decision. That gate was cleared:
...
*(CORRECTION 2026-05-07: A later throughput/process-boundary blocker — Marker Docker IPC
warm-worker v1 — was identified 2026-05-05 and activated as Feature 3 on 2026-05-07.
[[Work-Packet - Marker Structural Parser Integration]] remains in progress; L1 ships when
Feature 3 acceptance gates pass.)*
```

---

## Current Truth Statement

- **Hosting blocker**: resolved 2026-05-03. Docker GPU passthrough verified. RTX 2070 Super,
  CUDA 13.2, Docker Desktop 29.x GPU passthrough via WSL2. Volume-mount weight strategy chosen.
- **L1 Marker production rollout**: BLOCKED. Current blocker is Marker Docker IPC warm-worker v1
  (Feature 3 — active as of 2026-05-07). Acceptance gates: ≥3 warm papers in one session;
  ≤10s/paper for papers 2+.
- **L2 / PaperQA2**: explicitly blocked until Feature 3 passes.
- **L4**: stub, gated on L1 + L3.

---

## Commands Run and Outputs

### Verification grep (after fixes)

```
git grep -n "L1 Marker production rollout unblocked\|production rollout unblocked\|L1.*unblocked" docs
```

Output:
```
docs/INDEX.md:155:| [Fix — Marker Docker IPC Warm-Worker v1 Activation Blockers](...) | ... stale "L1 unblocked" claims removed ... |
docs/INDEX.md:156:| [Codex Verify — Marker Docker IPC Warm-Worker v1 Activation (FAIL)](...) | ... stale "L1 unblocked" claims in INDEX + Current-Focus ... |
```

Both remaining hits are INDEX.md row descriptions referencing what *prior* sessions fixed —
not positive current claims. No stale rollout-cleared claims remain in source docs.

### Implementation-path status check

```
git status --short -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
```

Output: (empty — no implementation paths touched)

---

## Whether Implementation Design May Proceed

**YES.** All stale positive L1 rollout-cleared claims are corrected. Hosting-decision
history is preserved. Current L1 blocker is correctly identified as Feature 3: Marker
Docker IPC warm-worker v1. Implementation design for Feature 3 may proceed per the work
packet at `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`.

---

## Codex Review Summary

Tier: Skip. Docs-only cleanup. No mandatory or recommended review-path implementation code changed.
Issues found: none.
Issues addressed: two stale "L1 rollout cleared" claims across one accepted decision note and one historical dev log.
