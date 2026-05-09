# Codex Verify - Marker Docker IPC Warm-Worker v1 Activation Fixed

Date: 2026-05-07
Type: read-only verification plus mandatory review dev log
Verdict: FAIL

## Summary

The fixed activation is mostly correct: Feature 3 is active as Marker Docker IPC
Warm-Worker v1, the active count is 3, max-3 is respected, L3 SVM remains
Recently Completed/default-off/enforce-deferred, L2/PaperQA2 and L4 remain
blocked/stubbed, and no implementation/test/artifact/trading/Docker paths are
dirty.

The verification still fails under the requested strict checklist because the
required `git grep` still finds docs that positively claim L1 is unblocked:

- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
  still says "L1 Marker production rollout is unblocked."
- `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md` still says
  "L1 is unblocked."

The fixed `docs/INDEX.md` and `Current-Focus.md` current/navigation entries now
say L1 remains blocked by IPC warm-worker v1, but the accepted hosting decision
note remains stale enough to mislead an implementation prompt designer. Under
the objective as written, implementation design should not proceed yet.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
- `docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md`
- `docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md`
- `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`

## Verification Checklist

| Check | Result | Notes |
|---|---:|---|
| Feature 3 remains active as Marker Docker IPC Warm-Worker v1 | PASS | `CURRENT_DEVELOPMENT.md` has Feature 3 active and `Current-Focus.md` says Feature 3 activated 2026-05-07. |
| Active count remains 3 and max-3 is respected | PASS | `CURRENT_DEVELOPMENT.md` and `Current-Focus.md` state Active count is 3 and max-3 reached. |
| No docs claim L1 Marker production rollout is unblocked | FAIL | `git grep` still finds positive unblocked claims in the accepted hosting decision note and the 2026-05-03 hosting dev log. |
| Docs accurately say L1 production remains blocked until warm-worker validates >=3 warm papers and <=10s/paper for papers 2+ | PASS with caveat | Current state docs and work packet say this correctly; stale hosting docs still need caveat/fix. |
| L3 SVM remains Recently Completed, default-off, enforce deferred | PASS | `CURRENT_DEVELOPMENT.md`, `INDEX.md`, and `Current-Focus.md` all agree. |
| L2/PaperQA2 and L4 remain blocked/stubbed | PASS | `Current-Focus.md` and the warm-worker work packet explicitly block L2 and leave L4 stubbed. |
| Smart-env dirty paths are cleaned or documented as accepted generated metadata | PASS | Fix dev log explicitly accepts the two remaining `.smart-env` runtime files as generated Obsidian metadata. Current status matches that. |
| No implementation code, tests, artifacts, labels, models, trading files, or Docker files changed | PASS | Scoped status check for implementation/config/test/artifact paths had no output. |
| Implementation design may proceed | FAIL | Blocked by stale "L1 unblocked" docs under the strict verification criteria. |

## Commands Run and Results

### `git status --short`

Exit 0.

```text
 M docs/CURRENT_DEVELOPMENT.md
 M docs/INDEX.md
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

### `git diff --stat`

Exit 0.

```text
 docs/CURRENT_DEVELOPMENT.md                        | 27 +++++++++++++++++++---
 docs/INDEX.md                                      |  5 +++-
 .../.smart-env/event_logs/event_logs.ajson         | 10 +++++++-
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  6 +++++
 .../obsidian-vault/Claude Desktop/Current-Focus.md | 19 +++++++--------
 5 files changed, 53 insertions(+), 14 deletions(-)
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

### `git diff --name-status`

Exit 0.

```text
M	docs/CURRENT_DEVELOPMENT.md
M	docs/INDEX.md
M	docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
warning: in the working copy of 'docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson', LF will be replaced by CRLF the next time Git touches it
```

### `git log --oneline -5`

Exit 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers — Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation — L1 still blocked
```

### `git grep -n "L1 Marker production rollout unblocked\|production rollout unblocked\|L1.*unblocked" docs`

Exit 0.

```text
docs/INDEX.md:155:| [Fix — Marker Docker IPC Warm-Worker v1 Activation Blockers](dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md) | 2026-05-07 | Fixes Codex FAIL: 3 stale "L1 unblocked" claims removed from INDEX + Current-Focus; smart-env generated metadata reverted/removed; 2 accepted Obsidian runtime dirty files documented. Implementation may proceed. |
docs/INDEX.md:156:| [Codex Verify — Marker Docker IPC Warm-Worker v1 Activation (FAIL)](dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md) | 2026-05-07 | FAIL — stale "L1 unblocked" claims in INDEX + Current-Focus; Obsidian smart-env noise contradicts context-map read-only claim. Blockers documented; no fixes applied. |
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:14:verified by running `nvidia-smi` inside a CUDA container with `--gpus all`. L1 is unblocked.
docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md:77:## Is L1 unblocked?
docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:15:**ACCEPTED — 2026-05-02. All open questions answered. Docker GPU passthrough verified. L1 Marker production rollout is unblocked.**
```

Interpretation: the two `docs/INDEX.md` hits are references to prior stale-claim
fixes, not positive current claims. The accepted hosting decision note is a
positive current-looking claim and fails the requested negative check. The
2026-05-03 dev log is historical, but it still matches the requested "No docs"
standard.

### `git grep -n "Feature 3: Marker Docker IPC Warm-Worker v1\|Active count.*3\|max-3" -- docs/CURRENT_DEVELOPMENT.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" docs/INDEX.md`

Exit 0. Relevant output:

```text
docs/CURRENT_DEVELOPMENT.md:75:### Feature 3: Marker Docker IPC Warm-Worker v1
docs/CURRENT_DEVELOPMENT.md:164:- **RIS L3 v1 SVM Topic Filter — expanded 156-label retrain/eval COMPLETE (2026-05-06). PROCEED to Director approval review.** Default-off integration shipped (2026-05-06). Expanded corpus retrain/eval complete: 156 labels (74 allow / 82 reject, 3 pending), train=117, test=39, accuracy=1.000, macro-F1=1.000, confusion_matrix=[[19,0],[0,20]]. Test set nearly 2.5× larger than prior run (16→39); no degradation. Artifacts in `artifacts/research/svm_filter_models/expanded_156/`. 123 targeted SVM tests pass. Label gate (>=150) now met. **Enforce is hard-blocked at rc=1** pending Director approval. Remaining blockers before any enforcement: (1) Director approval, (2) model selection decision (SPECTER2 options or declare `BAAI/bge-large-en-v1.5` as production — `peft` is NOT in `pyproject.toml` ris-svm and NOT needed for the bge-large path). Remaining DoD items: feature doc, CURRENT_STATE.md update, closeout dev log. **Active count is 3 (Features 1, 2, 3) — max-3 reached.**
docs/CURRENT_DEVELOPMENT.md:166:- **Marker Docker/Linux IPC Warm-Worker (v1) is now ACTIVE as Feature 3 (2026-05-07).** Director decision: promote to Active. Queue v0 shipped 2026-05-05. v1 (persistent IPC subprocess, Unix domain socket, Marker models warm in GPU VRAM across papers on Linux/Docker) is the active implementation target. **Active count is now 3 (Features 1, 2, 3) — max-3 reached.** L1 Marker production rollout BLOCKED until Feature 3 acceptance gates pass (≥3 papers warm; ≤10s/paper for papers 2+). L2 PaperQA2 is blocked until Feature 3 passes. Work packet: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`. Do NOT design prompts for a 4th Active feature without Director decision to pause or complete an existing one. Windows thread mode is unchanged — IPC is Linux/Docker only.
docs/INDEX.md:157:| [Marker Docker IPC Warm-Worker v1 — Feature 3 Activation](dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md) | 2026-05-07 | Docs-only activation. Active count 2→3 (max-3 reached). Work packet created; 7 acceptance gates locked. CURRENT_DEVELOPMENT, Current-Focus, INDEX updated. No code, tests, or artifacts touched. |
docs/obsidian-vault/Claude Desktop/Current-Focus.md:14:1. **RIS Scientific RAG roadmap** — primary active workstream. **L3 v1 SVM CLOSED 2026-05-07.** Feature doc: `docs/features/FEATURE-ris-svm-filter-v1.md`. SVM enforce deferred; BGE-large approved. **Feature 3 ACTIVATED 2026-05-07: Marker Docker IPC warm-worker v1 is now Active.** Active count: 3 (Features 1, 2, 3 — max-3 reached). Work packet: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`. **L1 Marker production rollout remains BLOCKED** — Docker IPC warm-worker (v1) is the active implementation target; L1 unblocks when all 7 acceptance gates pass (≥3 papers warm, ≤10s/paper for papers 2+). pdfplumber is legacy/debug only. **L2 is explicitly blocked until Feature 3 passes.** L4 remains stub. Do NOT start L2 or L4.
```

### `git grep -n "L1 Marker production rollout remains blocked\|L1 production rollout remains blocked\|warm-worker validates\|papers 2+\|<=10s\|parse_seconds" -- docs/CURRENT_DEVELOPMENT.md docs/INDEX.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"`

Exit 0. Relevant output:

```text
docs/CURRENT_DEVELOPMENT.md:135:| RIS Marker Queue — Docker IPC Warm-Worker (v1)         | ACTIVATED      | Promoted to Active as Feature 3 (2026-05-07) per Director decision. Queue v0 shipped 2026-05-05; v1 IPC warm-worker work packet created. L1 Marker production rollout remains blocked until Feature 3 acceptance gates pass. | N/A — now Active Feature 3 |
docs/CURRENT_DEVELOPMENT.md:136:| RIS L1 Marker Production Rollout — Validation          | 2026-05-05     | Operator chose Option A 2026-05-05: async parse queue. Queue v0 complete (Codex re-review PASS). Blocked on Docker IPC warm-worker (v1). pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. | Docker IPC warm-worker (v1) ships; warm worker validates ≥3 papers with `parse_seconds ≤10s` for papers 2+ |
docs/CURRENT_DEVELOPMENT.md:166:- **Marker Docker/Linux IPC Warm-Worker (v1) is now ACTIVE as Feature 3 (2026-05-07).** Director decision: promote to Active. Queue v0 shipped 2026-05-05. v1 (persistent IPC subprocess, Unix domain socket, Marker models warm in GPU VRAM across papers on Linux/Docker) is the active implementation target. **Active count is now 3 (Features 1, 2, 3) — max-3 reached.** L1 Marker production rollout BLOCKED until Feature 3 acceptance gates pass (≥3 papers warm; ≤10s/paper for papers 2+). L2 PaperQA2 is blocked until Feature 3 passes. Work packet: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`. Do NOT design prompts for a 4th Active feature without Director decision to pause or complete an existing one. Windows thread mode is unchanged — IPC is Linux/Docker only.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:20:- ~~**Academic pipeline hosting**~~ — **RESOLVED 2026-05-02.** Docker with GPU passthrough on dev machine. RTX 2070 Super, CUDA 13.2. Docker GPU passthrough verified via `docker run --gpus all`. Model weights volume-mounted from `~/.cache/datalab/`. See [[Decision - Academic Pipeline Hosting]] (status: accepted). Hosting blocker resolved; **L1 Marker production rollout remains blocked by IPC warm-worker v1 (Feature 3 — active, see Active Priorities above).**
docs/obsidian-vault/Claude Desktop/Current-Focus.md:29:| L1 | [[Work-Packet - Marker Structural Parser Integration]] + [[Work-Packet - Marker Docker IPC Warm-Worker v1]] | **ACTIVE (Feature 3) — IPC warm-worker v1 is the current implementation target.** Queue v0 shipped 2026-05-05. v1 work packet created 2026-05-07. L1 production rollout remains blocked until all 7 acceptance gates pass: IPC worker exists, models warm across papers, ≥3 papers in one session, papers 2+ ≤10s, queue semantics intact, no pdfplumber fallback, Windows behavior honest. pdfplumber is legacy/debug only. RAG-ready requires `body_source=marker`. |
docs/obsidian-vault/Claude Desktop/Current-Focus.md:73:| Docker IPC warm-worker v1 | L1 Marker production rollout | **ACTIVE as Feature 3 (2026-05-07)** — Work packet created; 7 acceptance gates locked. Implementation not yet started. L1 unblocks when all gates pass (≥3 papers warm, ≤10s/paper for papers 2+). L2 explicitly blocked until Feature 3 passes. |
```

### `git grep -n "RIS L3 v1 SVM Topic Filter\|default-off\|enforce deferred\|enforce remains\|Recently Completed" -- docs/CURRENT_DEVELOPMENT.md docs/INDEX.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md"`

Exit 0. Relevant output:

```text
docs/CURRENT_DEVELOPMENT.md:109:## Recently Completed (rolling 30 days)
docs/CURRENT_DEVELOPMENT.md:113:| RIS L3 v1 SVM Topic Filter                                   | 2026-05-07 | RIS      | `docs/features/FEATURE-ris-svm-filter-v1.md` — default-off integrated; dry-run + hold-review ready; enforce deferred. **Director decision 2026-05-07: `BAAI/bge-large-en-v1.5` approved as production model; enforce deferred pending future approval.** 156 labels (74/82), train=117, test=39, macro-F1=1.000, confusion=[[19,0],[0,20]]. `research-prefetch-svm-train` CLI; SVM flags on both acquisition CLIs; enforce blocked at rc=1. 123 targeted SVM tests pass. Dev log: `docs/dev_logs/2026-05-07_l3-v1-svm-feature-closeout.md`. |
docs/CURRENT_DEVELOPMENT.md:165:- **RIS L3 v1 SVM Topic Filter is COMPLETE (2026-05-07).** Default-off integrated; dry-run + hold-review ready; enforce deferred. Director decision: `BAAI/bge-large-en-v1.5` approved as production model. Feature doc at `docs/features/FEATURE-ris-svm-filter-v1.md`. SVM enforce remains hard-blocked at rc=1 pending future Director approval. SPECTER2 path remains unresolved; BGE-large is the declared production model. Marker Docker IPC warm-worker activated as Feature 3 (2026-05-07 — see below).
docs/INDEX.md:120:| [RIS L3 v1 SVM Topic Filter](features/FEATURE-ris-svm-filter-v1.md) | **Default-off integrated. Dry-run + hold-review ready. Enforce deferred.** `BAAI/bge-large-en-v1.5` approved as production model (Director 2026-05-07). 156 labels (74/82), train=117, test=39, macro-F1=1.000. `research-prefetch-svm-train` CLI; `--prefetch-filter-scorer svm` on `research-acquire`; `--filter-scorer svm` on `research-prefetch-discover`. SVM enforce returns rc=1 — blocked pending future Director approval. Lexical remains default. |
docs/obsidian-vault/Claude Desktop/Current-Focus.md:14:1. **RIS Scientific RAG roadmap** — primary active workstream. **L3 v1 SVM CLOSED 2026-05-07.** Feature doc: `docs/features/FEATURE-ris-svm-filter-v1.md`. SVM enforce deferred; BGE-large approved. **Feature 3 ACTIVATED 2026-05-07: Marker Docker IPC warm-worker v1 is now Active.** Active count: 3 (Features 1, 2, 3 — max-3 reached). Work packet: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`. **L1 Marker production rollout remains BLOCKED** — Docker IPC warm-worker (v1) is the active implementation target; L1 unblocks when all 7 acceptance gates pass (≥3 papers warm, ≤10s/paper for papers 2+). pdfplumber is legacy/debug only. **L2 is explicitly blocked until Feature 3 passes.** L4 remains stub. Do NOT start L2 or L4.
```

### `git grep -n "L2.*blocked\|PaperQA2.*blocked\|PaperQA2.*BLOCKED\|L4.*Stub\|L4 remains stub\|No L4 work" -- docs/CURRENT_DEVELOPMENT.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"`

Exit 0. Relevant output:

```text
docs/CURRENT_DEVELOPMENT.md:96:  - [ ] L2 blocked notation updated (L2 stays blocked until all gates above pass)
docs/CURRENT_DEVELOPMENT.md:166:- **Marker Docker/Linux IPC Warm-Worker (v1) is now ACTIVE as Feature 3 (2026-05-07).** Director decision: promote to Active. Queue v0 shipped 2026-05-05. v1 (persistent IPC subprocess, Unix domain socket, Marker models warm in GPU VRAM across papers on Linux/Docker) is the active implementation target. **Active count is now 3 (Features 1, 2, 3) — max-3 reached.** L1 Marker production rollout BLOCKED until Feature 3 acceptance gates pass (≥3 papers warm; ≤10s/paper for papers 2+). L2 PaperQA2 is blocked until Feature 3 passes. Work packet: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`. Do NOT design prompts for a 4th Active feature without Director decision to pause or complete an existing one. Windows thread mode is unchanged — IPC is Linux/Docker only.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:14:1. **RIS Scientific RAG roadmap** — primary active workstream. **L3 v1 SVM CLOSED 2026-05-07.** Feature doc: `docs/features/FEATURE-ris-svm-filter-v1.md`. SVM enforce deferred; BGE-large approved. **Feature 3 ACTIVATED 2026-05-07: Marker Docker IPC warm-worker v1 is now Active.** Active count: 3 (Features 1, 2, 3 — max-3 reached). Work packet: `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`. **L1 Marker production rollout remains BLOCKED** — Docker IPC warm-worker (v1) is the active implementation target; L1 unblocks when all 7 acceptance gates pass (≥3 papers warm, ≤10s/paper for papers 2+). pdfplumber is legacy/debug only. **L2 is explicitly blocked until Feature 3 passes.** L4 remains stub. Do NOT start L2 or L4.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:30:| L2 | [[Work-Packet - PaperQA2 RAG Control Flow]] | Stub. **Explicitly blocked until Feature 3 (warm-worker) passes all acceptance gates.** Do NOT activate. |
docs/obsidian-vault/Claude Desktop/Current-Focus.md:32:| L4 | [[Work-Packet - Multi-source Academic Harvesters]] | Stub. Activation gated on L1 + L3. Updated 2026-04-29 to add backfill-vs-monitoring distinction. |
docs/obsidian-vault/Claude Desktop/Current-Focus.md:73:| Docker IPC warm-worker v1 | L1 Marker production rollout | **ACTIVE as Feature 3 (2026-05-07)** — Work packet created; 7 acceptance gates locked. Implementation not yet started. L1 unblocks when all gates pass (≥3 papers warm, ≤10s/paper for papers 2+). L2 explicitly blocked until Feature 3 passes. |
```

### `git status --short -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Exit 0, no output.

```text
```

### `git status --short -- docs/obsidian-vault/.obsidian docs/obsidian-vault/.smart-env`

Exit 0.

```text
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
```

This matches the fix dev log's accepted generated metadata classification.

### Final `git status --short` after creating this dev log

Exit 0.

```text
 M docs/CURRENT_DEVELOPMENT.md
 M docs/INDEX.md
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

## Decisions Made

- Overall verdict is FAIL because the requested "No docs claim L1 Marker
  production rollout is unblocked" check still fails.
- Implementation design may not proceed under the strict checklist.
- No fixes were applied because this task allowed only the review dev log to
  change.

## Remaining Blockers / Fixes

1. Update `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
   so its status distinguishes "hosting blocker resolved" from the current L1
   production rollout status, which remains blocked by IPC warm-worker v1.
2. Either update `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`
   with a dated correction note, or explicitly document that historical "L1 is
   unblocked" language is accepted and excluded from the verification grep.
3. Rerun this verification. If the same grep returns only stale-claim discussion
   lines, implementation design can proceed.

## Codex Review Summary

Tier: Skip. This verification reviewed docs/state and dirty path scope only; no
mandatory or recommended review-path implementation code changed.
Issues found: stale L1-unblocked claims remain in an accepted decision note and
one historical dev log.
Issues addressed: none, by instruction.
