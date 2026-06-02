---
title: Codex Verify Marker Closeout Stale Status References
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_codex-verify-marker-closeout-stale-status-references.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify: Marker Closeout Stale Status References

Date: 2026-05-08
Type: docs-only closeout verification
Scope: Marker Docker IPC Warm-Worker v1 stale-status closeout fix
Verdict: **FAIL**

---

## Summary

FAIL. The two stale references called out by the prior Codex verification were fixed in
the target closeout context:

- The warm-worker work packet now says Feature 3 is CLOSED.
- Current-Focus current-state sections now say Marker Docker IPC warm-worker v1 is CLOSED /
  COMPLETE and L1 Marker production rollout is UNBLOCKED.

However, inspection of the changed docs found active-looking stale status references
outside those two exact locations:

- `docs/features/ris-marker-structural-parser-scaffold.md:3` still says
  `L1 PRODUCTION BLOCKED (pending Marker Docker IPC Warm-Worker v1 Feature 3 closeout,
  2026-05-07)`.
- `docs/INDEX.md:118` still says the structural parser feature is
  `L1 PRODUCTION BLOCKED (awaiting Docker IPC warm-worker v1)` and that Docker IPC
  warm-worker is deferred to v1.
- `docs/CURRENT_DEVELOPMENT.md:95` still says Marker Canonical Academic Parse Queue v0 has
  Docker IPC warm-worker deferred to v1 and L1 production rollout still blocked on IPC
  warm-worker.

Those lines conflict with the accepted current-state docs that say warm-worker v1 is
complete and L1 production rollout is unblocked. Closeout should not be accepted until
those stale current-facing status lines are corrected or explicitly marked historical.

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
- `docs/features/ris-marker-structural-parser-scaffold.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-docker-ipc-warm-worker-v1-closeout.md`
- `docs/dev_logs/2026-05-08_fix-marker-closeout-stale-status-references.md`

---

## Verification Matrix

| Check | Result | Notes |
| --- | --- | --- |
| Work packet no longer says Feature 3 is "NOT yet closed" | PASS | Current work packet line 113 says Feature 3 is CLOSED (2026-05-08). |
| Current-Focus current state no longer blocks L1 on Feature 3 closeout | PASS | Active priorities, Open Decisions, RIS table, and Key Blockers now say CLOSED/COMPLETE/UNBLOCKED. |
| Current-Focus reflects Marker Docker IPC warm-worker v1 as recently closed/completed | PASS | Current-Focus active priority and recent-session entries record CLOSED/COMPLETE 2026-05-08 and L1 UNBLOCKED. |
| Completion protocol remains complete | PASS | Feature doc exists, INDEX has warm-worker feature row, CURRENT_DEVELOPMENT moved warm-worker to Recently Completed. |
| Revised gate remains honest | PASS | 45.55s, 69.73s, 48.31s preserved; old <=10s/paper gate is rejected/superseded, not claimed achieved. |
| L2/PaperQA2 and L4 remain blocked/stubbed | PASS | Reviewed docs keep L2/PaperQA2 and L4 stubbed/gated. |
| No implementation/test/Docker/artifact/SVM/trading/L2/L4 changes added by this stale-status fix | PASS with caveat | The working tree still contains pre-existing warm-worker implementation/test/Docker diffs, but the stale-status fix log reports docs-only changes and no evidence showed new implementation changes from that fix. |
| Broader stale closeout status in changed docs | FAIL | Structural parser feature doc, INDEX structural feature row, and one CURRENT_DEVELOPMENT recently-completed row still say L1 is blocked/pending/deferred on the warm-worker closeout. |

---

## Completion Protocol Status

Required by `docs/CURRENT_DEVELOPMENT.md`:

1. Feature doc created: PASS (`docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`).
2. `docs/INDEX.md` updated: PASS (warm-worker feature row and dev-log rows present).
3. Feature moved to Recently Completed: PASS (`docs/CURRENT_DEVELOPMENT.md:92`).

Completion protocol is complete, but closeout acceptance still FAILS because other
current-facing changed docs retain stale blocked/pending wording.

---

## Revised Gate Status

PASS. The revised functional gate remains honest:

- Timings preserved: 45.55s, 69.73s, 48.31s.
- Papers 2+ delta preserved: 0.13s and 0.22s.
- Docs claim cold-load overhead was eliminated, not that <=10s/paper was achieved.
- Old <=10s/paper gate is described as rejected/superseded/unrealistic.
- `body_source=marker`, `ipc_warm_worker_used=true`, no pdfplumber fallback, no daemon
  error, and clean shutdown remain documented.

---

## Blockers / Fixes Needed

Blocking fixes before accepting Feature 3 closeout:

1. Update `docs/features/ris-marker-structural-parser-scaffold.md:3` and its top callout
   from "L1 PRODUCTION BLOCKED / pending Marker Docker IPC Warm-Worker v1 Feature 3
   closeout" to the current state: warm-worker v1 complete, L1 production rollout
   unblocked, L2 still gated on L1 production rollout completion.
2. Update `docs/INDEX.md:118` structural parser feature row so it no longer says
   "L1 PRODUCTION BLOCKED (awaiting Docker IPC warm-worker v1)" or "Docker IPC
   warm-worker deferred to v1" as current state.
3. Update `docs/CURRENT_DEVELOPMENT.md:95` Marker Canonical Academic Parse Queue v0 row
   so the "L1 Marker production rollout still blocked on IPC warm-worker" sentence is
   either marked historical at time of v0 closeout or points to the later warm-worker
   closeout row.

Non-blocking context:

- `Current-Focus.md` still contains historical/session-context mentions of old "Active
  Feature 3" and "Feature 3 closeout" language. The current-state sections are correct,
  so I did not treat those historical entries as blockers.
- `docs/INDEX.md` recent-dev-log rows also contain historical stale-state summaries from
  earlier dated logs. Those are less severe than current feature/status rows, but they may
  still be confusing if the index is used as an operator dashboard.

---

## Commands Run

### Read-first files

Read with `Get-Content -Raw`:

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/INDEX.md`
- `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-08_codex-verify-marker-docker-ipc-warm-worker-v1-closeout.md`
- `docs/dev_logs/2026-05-08_fix-marker-closeout-stale-status-references.md`

### Requested stale-status grep

Command:

```powershell
rg -n "NOT yet closed|Active Feature 3|blocked on Feature 3 closeout|Feature 3 closeout" "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

Result: exit 0. Relevant output:

```text
docs/obsidian-vault/Claude Desktop/Current-Focus.md:4:updated: 2026-05-08 (Marker Docker IPC warm-worker v1 - Feature 3 closeout complete)
docs/obsidian-vault/Claude Desktop/Current-Focus.md:42:- ... "Feature 3 is NOT yet closed" replaced with "Feature 3 is CLOSED (2026-05-08)" ... stale "... see Active Feature 3 ..." removed ...
docs/obsidian-vault/Claude Desktop/Current-Focus.md:43:- ... Feature 3 moved to Recently Completed ... L1 Marker production rollout UNBLOCKED. L2/L4 remain stubs.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:44:- ... prior session context ... Active Feature 3 ... Feature 3 NOT marked complete - closeout verification still pending.
docs/obsidian-vault/Claude Desktop/Current-Focus.md:59:- ... stale ... L1 blocked pending Marker IPC warm-worker Feature 3 closeout ...
```

Interpretation: the current-state sections are fixed, but historical/session-context matches
remain.

### Requested CURRENT_DEVELOPMENT grep

Command:

```powershell
git grep -n "Feature 3\|Marker Docker IPC" docs/CURRENT_DEVELOPMENT.md
```

Result: exit 0. Relevant output:

```text
docs/CURRENT_DEVELOPMENT.md:92:| Marker Docker IPC Warm-Worker v1 | 2026-05-08 | RIS | ... Revised gate ... Measured: 45.55s/69.73s/48.31s ... L1 Marker production rollout UNBLOCKED. L2/L4 remain stubs. ...
docs/CURRENT_DEVELOPMENT.md:116:| RIS L1 Marker Production Rollout - Validation | ... warm-worker v1 complete (Feature 3 closed 2026-05-08) ... Resume trigger met 2026-05-08 ...
docs/CURRENT_DEVELOPMENT.md:140:- ... Docker IPC warm-worker (v1) is COMPLETE (2026-05-08) ... L1 Marker Production Rollout is UNBLOCKED ...
docs/CURRENT_DEVELOPMENT.md:145:- ... Marker Docker IPC warm-worker v1 is COMPLETE (2026-05-08) - active count is now 2 ...
```

Additional changed-doc stale-status output:

```text
docs/CURRENT_DEVELOPMENT.md:95:| Marker Canonical Academic Parse Queue v0 ... Docker IPC warm-worker deferred to v1. L1 Marker production rollout still blocked on IPC warm-worker. |
```

### Requested status and diff commands

Command:

```powershell
git status --short
```

Result: exit 0. The tree is dirty. Relevant output includes:

```text
 M Dockerfile.ris
 M docs/CURRENT_DEVELOPMENT.md
 M docs/CURRENT_STATE.md
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/features/ris-marker-structural-parser-scaffold.md
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-08_codex-verify-marker-docker-ipc-warm-worker-v1-closeout.md
?? docs/dev_logs/2026-05-08_fix-marker-closeout-stale-status-references.md
?? docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

Command:

```powershell
git diff --stat
```

Result: exit 0. Relevant output:

```text
 Dockerfile.ris                                     |   1 +
 docs/CURRENT_DEVELOPMENT.md                        |  13 +-
 docs/CURRENT_STATE.md                              |  58 +-
 docs/INDEX.md                                      |  18 +-
 .../ris-marker-structural-parser-scaffold.md       |  13 +-
 .../obsidian-vault/Claude Desktop/Current-Focus.md |  17 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 25 files changed, 1959 insertions(+), 247 deletions(-)
```

Command:

```powershell
git diff --name-status
```

Result: exit 0. Relevant output:

```text
M       Dockerfile.ris
M       docs/CURRENT_DEVELOPMENT.md
M       docs/CURRENT_STATE.md
M       docs/INDEX.md
M       docs/features/ris-marker-structural-parser-scaffold.md
M       docs/obsidian-vault/Claude Desktop/Current-Focus.md
M       packages/research/ingestion/fetchers.py
M       packages/research/ingestion/marker_queue.py
M       tests/test_ris_marker_queue.py
M       tools/cli/research_marker_queue.py
```

Command:

```powershell
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
```

Result: exit 0. Output:

```text
M       Dockerfile.ris
M       packages/research/ingestion/fetchers.py
M       packages/research/ingestion/marker_queue.py
M       tests/test_ris_marker_queue.py
M       tools/cli/research_marker_queue.py
```

Interpretation: implementation/test/Docker diffs are present in the working tree from the
warm-worker feature stream. The stale-status fix log says it touched only docs, and the
targeted stale-status review did not find evidence that the stale-status fix added new
implementation/test/Docker/artifact/SVM/trading/L2/L4 changes.

### Additional stale-status grep over changed docs

Command:

```powershell
rg -n "L1 PRODUCTION BLOCKED|L1 production blocked|awaiting Docker IPC warm-worker|L1 remains blocked|blocked pending Marker Docker IPC|warm-worker v1.*deferred|Docker IPC warm-worker.*deferred" docs/INDEX.md docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md docs/features/ris-marker-structural-parser-scaffold.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

Result: exit 0. Blocking output:

```text
docs/features/ris-marker-structural-parser-scaffold.md:3:**Status: CODE COMPLETE - L1 PRODUCTION BLOCKED (pending Marker Docker IPC Warm-Worker v1 Feature 3 closeout, 2026-05-07)**
docs/INDEX.md:118:| [RIS Marker Structural Parser - Production Default (Layer 1)](...) | **CODE COMPLETE - L1 PRODUCTION BLOCKED (awaiting Docker IPC warm-worker v1).** ... Docker IPC warm-worker deferred to v1. ...
docs/CURRENT_DEVELOPMENT.md:95:| Marker Canonical Academic Parse Queue v0 ... Docker IPC warm-worker deferred to v1. L1 Marker production rollout still blocked on IPC warm-worker. |
```

### Revised gate / L2 / L4 checks

Command:

```powershell
rg -n "45\.55s|69\.73s|48\.31s|<=10s/paper.*achieved|achieved.*<=10s|L2 PaperQA2|L4 Multi-source" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

Result: exit 0. Relevant output confirms timings and stub gates:

```text
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:116:... 45.55s ...
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:117:... 69.73s ...
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:118:... 48.31s ...
docs/CURRENT_DEVELOPMENT.md:92:... Measured: 45.55s/69.73s/48.31s ... L2/L4 remain stubs.
docs/CURRENT_STATE.md:1845:- L2 PaperQA2 RAG Control Flow - stub; gated on L1 production rollout completion.
docs/CURRENT_STATE.md:1846:- L4 Multi-source Academic Harvesters - stub; gated on L1 + L3.
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:26:> **L2 PaperQA2 RAG Control Flow remains STUB** - gated on L1 production rollout completion. Do NOT activate.
```

No `<=10s/paper achieved` claim was found.

---

## Commands Not Run

No tests, validation commands, Docker commands, queue commands, artifact mutations, SVM
commands, trading commands, L2 commands, or L4 commands were run.

I did not run `python -m polytool --help` because the requested scope explicitly said not
to run validation and listed the verification commands to run.

---

## Codex Review Summary

Tier: docs-only closeout verification.

Issues found:

- Blocking: Structural parser feature doc top status still says L1 production is blocked
  pending Marker Docker IPC Warm-Worker v1 Feature 3 closeout.
- Blocking: INDEX structural parser feature row still says L1 production is blocked awaiting
  Docker IPC warm-worker v1.
- Blocking: CURRENT_DEVELOPMENT recently-completed queue v0 row still says L1 production
  rollout is blocked on IPC warm-worker.

Issues addressed: none in source docs. Per instruction, this review changed only this dev
log.
