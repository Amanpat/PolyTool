# Codex Verify - Marker Docker IPC Warm-Worker v1 Activation

Date: 2026-05-07
Type: read-only verification plus mandatory review dev log
Verdict: FAIL

## Summary

Feature 3 is correctly activated as Marker Docker IPC Warm-Worker v1. Active count is
3 and the max-3 rule is explicitly called out. L3 v1 SVM is Recently Completed,
default-off, and enforce-deferred. The warm-worker acceptance gates include >=3
warm papers and <=10s/paper for papers 2+. L2/PaperQA2 and L4 remain blocked or
stubbed. No implementation code, tests, trading files, tracked artifacts, labels,
or model files are dirty.

FAIL is due to two review blockers:

1. Current docs still contain stale "L1 Marker production rollout unblocked"
   claims in `docs/obsidian-vault/Claude Desktop/Current-Focus.md` and
   `docs/INDEX.md`.
2. The context-map session claims "dev log only", but current git state includes
   dirty tracked Obsidian workspace/smart-env metadata and an untracked smart-env
   index for the new Marker work packet. These are not implementation files, but
   they contradict a strict "read-only except its dev log" claim.

Implementation prompt design should not proceed until those doc/metadata blockers
are either fixed or explicitly accepted by the operator.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md`
- `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md`
- Dirty Obsidian metadata diffs under `docs/obsidian-vault/.obsidian/` and `docs/obsidian-vault/.smart-env/`

## Verification Checklist

| Check | Result | Notes |
|---|---|---|
| Feature 3 active as Marker Docker IPC warm-worker v1 | PASS | `CURRENT_DEVELOPMENT.md` has Feature 3 active with status "Docs-only activation". |
| Active count 3 and max-3 respected | PASS | `CURRENT_DEVELOPMENT.md`, `Current-Focus.md`, and activation log all state active count is 3 and max-3 reached. |
| L3 v1 SVM Recently Completed, default-off, enforce deferred | PASS | `CURRENT_DEVELOPMENT.md` Recently Completed row and `CURRENT_STATE.md` SVM section say default-off and enforce blocked/deferred. |
| Acceptance gates include >=3 warm papers and <=10s/paper for papers 2+ | PASS | Work packet gates 2-3 and activation log gates 3-4 include these criteria. |
| Docs do not claim L1 production is already unblocked | FAIL | Stale current/navigation lines still say "L1 Marker production rollout unblocked"; see command output below. |
| L2/PaperQA2 and L4 remain deferred/stub | PASS | `Current-Focus.md` and work packet explicitly block L2 and keep L4 stub. |
| Activation was docs-only | PASS with caveat | No code/tests/artifacts/trading paths are dirty. Obsidian metadata is dirty, so the activation log's files-changed list is incomplete if metadata is considered in scope. |
| Context map read-only except its dev log | FAIL | Context-map dev log claims dev-log-only, but current status includes dirty tracked Obsidian metadata and an untracked Marker work-packet smart-env index. |
| No implementation code, tests, labels, model artifacts, or trading files modified | PASS | Targeted status for `packages`, `tools`, `tests`, `polytool`, `config`, `infra`, Docker files, and `artifacts` was empty. |
| Implementation prompts can be designed next | FAIL | Blocked by stale unblocked claims and context-map read-only mismatch. |

## Commands Run and Results

### `git status --short`

Exit 0.

```text
 M docs/CURRENT_DEVELOPMENT.md
 M docs/INDEX.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_Marker_Docker_IPC_Warm-Worker_v1_md.ajson
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

### `git log --oneline -5`

Exit 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### `python -m polytool --help`

Exit 0. CLI loaded successfully. Relevant command families present:
`research-marker-queue`, `research-prefetch-svm-train`, `research-prefetch-discover`.

### `git diff --stat`

Exit 0.

```text
 docs/CURRENT_DEVELOPMENT.md                        |  27 ++++-
 docs/INDEX.md                                      |   1 +
 docs/obsidian-vault/.obsidian/workspace.json       |  16 +--
 .../.smart-env/event_logs/event_logs.ajson         |  60 ++++++++++-
 ...cket_-_L3_v1_SVM_Topic_Filter_Training_md.ajson | 118 +++++++++++++++++++++
 .../multi/Claude_Desktop_Current-Focus_md.ajson    |  20 ++++
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  15 +--
 7 files changed, 238 insertions(+), 19 deletions(-)
```

Note: untracked activation/context-map dev logs, the new work packet, and the
new Marker smart-env index are not included in `git diff --stat`.

### `git diff --name-status`

Exit 0.

```text
M	docs/CURRENT_DEVELOPMENT.md
M	docs/INDEX.md
M	docs/obsidian-vault/.obsidian/workspace.json
M	docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_12-Ideas_Work-Packet_-_L3_v1_SVM_Topic_Filter_Training_md.ajson
M	docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
```

### Dirty implementation-path check

Command:

```powershell
git status --short -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
```

Exit 0, no output. No tracked implementation, tests, config, infra, Docker,
artifact, or trading paths are dirty.

### `rg` attempts

Requested `rg` searches could not execute because the bundled `rg.exe` returned
Access denied, including after an escalation request.

`rg --version` output:

```text
Program 'rg.exe' failed to run: Access is denied
```

Fallback command:

```powershell
git grep -n -E "Marker Docker IPC|warm-worker|warm worker|marker_ipc|run-warm-worker|run-marker-worker|warm-process|Unix domain socket|named pipe" -- . ":(exclude)docs/**" ":(exclude)artifacts/**"
```

Exit 0.

```text
tests/test_ris_marker_queue.py:648:    """Verify warm-worker implementation is honest about platform limits."""
```

This is an existing tracked v0 test reference; `git status --short -- tests`
was empty.

### Stale L1-unblocked claim search

Command:

```powershell
Select-String -Path docs/CURRENT_DEVELOPMENT.md,docs/CURRENT_STATE.md,docs/INDEX.md,"docs/obsidian-vault/Claude Desktop/Current-Focus.md","docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md",docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md,docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md -Pattern "L1.*unblocked|production.*unblocked|L1 Marker production rollout.*unblocked|L1 production.*unblocked|already unblocked"
```

Exit 0.

```text
docs\INDEX.md:182:| [Academic Pipeline Hosting Decision](dev_logs/2026-05-03_academic-pipeline-hosting-decision.md) | 2026-05-03 | Hosting decision accepted: Docker+GPU dev machine, passthrough verified (RTX 2070 Super, CUDA 13.2), volume-mount weights, hard-cutover rollout; L1 Marker production rollout unblocked |
docs\obsidian-vault\Claude Desktop\Current-Focus.md:20:- ~~**Academic pipeline hosting**~~ - **RESOLVED 2026-05-02.** Docker with GPU passthrough on dev machine. RTX 2070 Super, CUDA 13.2. Docker GPU passthrough verified via `docker run --gpus all`. Model weights volume-mounted from `~/.cache/datalab/`. See [[Decision - Academic Pipeline Hosting]] (status: accepted). L1 Marker production rollout is now unblocked.
docs\obsidian-vault\Claude Desktop\Current-Focus.md:57:- **2026-05-03**: Academic pipeline hosting decision accepted. Docker GPU passthrough verified (RTX 2070 Super, CUDA 13.2, `docker run --gpus all` succeeds). Q1->B (Docker+GPU dev machine), Q2->confirmed, Q3->moot, Q4->academic on dev / others on partner, Q5->volume-mount host cache. L1 Marker production rollout unblocked. Next packet: [[Work-Packet - Marker Structural Parser Integration]]. Dev log: `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md`.
docs\dev_logs\2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md:54:- Do not claim L1 production is unblocked - it remains blocked.
```

### L2/L4 blocked or stub search

Exit 0. Relevant hits:

```text
docs\obsidian-vault\Claude Desktop\Current-Focus.md:30:| L2 | [[Work-Packet - PaperQA2 RAG Control Flow]] | Stub. **Explicitly blocked until Feature 3 (warm-worker) passes all acceptance gates.** Do NOT activate. |
docs\obsidian-vault\Claude Desktop\Current-Focus.md:32:| L4 | [[Work-Packet - Multi-source Academic Harvesters]] | Stub. Activation gated on L1 + L3. Updated 2026-04-29 to add backfill-vs-monitoring distinction. |
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Docker IPC Warm-Worker v1.md:76:**L2 gate:** L2 PaperQA2 RAG Control Flow remains stub and does NOT activate until gates 1-7 above are all satisfied and the acceptance dev log is written.
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Docker IPC Warm-Worker v1.md:82:- **No L2 work.** `Work-Packet - PaperQA2 RAG Control Flow` remains stub. L2 activation gates on warm-worker passing.
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Docker IPC Warm-Worker v1.md:83:- **No L4 work.** Multi-source academic harvesters remain stub and are not touched.
```

### Context-map scope check

`docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md`
states:

```text
Scope: Read-only context map. No code, tests, or state-doc changes.
Status: COMPLETE - dev log only
```

But current status includes dirty tracked Obsidian workspace/smart-env metadata
and an untracked smart-env file for the Marker work packet. The smart-env diffs
are embedding/index updates, not implementation changes, but they violate a
strict "dev log only" interpretation.

## Decisions Made

- Overall verdict is FAIL because the verification packet includes explicit
  negative checks that did not pass.
- No code, tests, Marker jobs, artifacts, or implementation files were touched.
- No fixes were applied because the objective allowed changing only this review
  dev log.

## Blockers / Required Fixes

1. Update current/navigation docs so they no longer say "L1 Marker production
   rollout unblocked" without the current warm-worker blocker caveat. Minimum:
   `Current-Focus.md` line 20 and line 57, plus `docs/INDEX.md` line 182.
2. Decide whether tracked Obsidian `.smart-env` and `.obsidian/workspace.json`
   changes are acceptable local metadata for this activation/context-map work.
   If not, remove/revert those metadata changes in a separate cleanup task.
3. After fixes, rerun the read-only verification and create a new PASS dev log.

## Codex Review Summary

Tier: Skip. This verification reviewed docs/state and dirty path scope only; no
mandatory or recommended review-path implementation code changed.
Issues found: stale L1-unblocked claims; context-map read-only mismatch via
Obsidian metadata.
Issues addressed: none, by instruction.
