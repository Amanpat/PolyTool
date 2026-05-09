# Codex Verify: Marker Final L1-Blocked Status

Date: 2026-05-08
Type: docs-only closeout verification
Scope: final stale-status verification for Marker Docker IPC Warm-Worker v1 closeout
Verdict: FAIL

---

## Summary

FAIL. The three target stale references from the prior Codex failure are fixed:

- `docs/features/ris-marker-structural-parser-scaffold.md` no longer says L1 is blocked pending warm-worker Feature 3 closeout.
- `docs/INDEX.md` current feature row no longer says L1 is blocked awaiting Docker IPC warm-worker v1.
- `docs/CURRENT_DEVELOPMENT.md` queue v0 row no longer says L1 rollout is blocked on IPC warm-worker.

However, the required repo-wide stale-status grep still found current-facing Obsidian notes that contradict the post-closeout state. Most matches are historical dev logs or dated session history, but these current docs remain stale:

- `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:102` still says "See Active Feature 3 in CURRENT_DEVELOPMENT.md."
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:47` still says "v1 Active Feature 3."
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:96` and `:126` still say "See Active Feature 3 in CURRENT_DEVELOPMENT.md."
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:147-158` still says the warm-worker is "Now Active Feature 3" and "L1 Marker production rollout remains blocked until Feature 3 closeout verification passes."

Feature 3 closeout is therefore not accepted yet.

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
- `docs/dev_logs/2026-05-08_codex-verify-marker-closeout-stale-status-references.md`
- `docs/dev_logs/2026-05-08_fix-marker-final-l1-blocked-status.md`
- Additional current docs surfaced by grep:
  - `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md`
  - `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`
  - `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`
  - `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md`

---

## Verification Matrix

| Check | Result | Notes |
|---|---|---|
| `ris-marker-structural-parser-scaffold.md` no longer says L1 is blocked pending warm-worker Feature 3 closeout | PASS | Top status now says warm-worker v1 closed 2026-05-08 and L1 can proceed to next explicit rollout step. |
| `INDEX.md` no longer says L1 is blocked awaiting Docker IPC warm-worker v1 | PASS with caveat | Current feature row is fixed. Historical recent-dev-log rows still contain old state summaries. |
| `CURRENT_DEVELOPMENT.md` queue v0 row no longer says L1 rollout is blocked on IPC warm-worker | PASS | Queue v0 row now says IPC warm-worker v1 closed 2026-05-08. |
| Docs accurately say Marker Docker IPC Warm-Worker v1 is Recently Completed / closed under revised functional gate | FAIL | Core docs do, but current Obsidian notes still point to "Active Feature 3"; one still says L1 remains blocked until closeout verification passes. |
| Docs do not claim full academic/RIS pipeline complete | PASS | Targeted negative grep found no such claim in reviewed closeout docs. |
| Docs do not claim L2/PaperQA2 or L4 are unblocked | PASS | Targeted negative grep found no L2/L4 unblocked claim in reviewed closeout docs. |
| Completion protocol remains complete | PASS | Feature doc exists, INDEX has feature row, CURRENT_DEVELOPMENT moved warm-worker to Recently Completed. |
| Revised gate remains honest | PASS | 45.55s, 69.73s, and 48.31s are preserved; no reviewed closeout doc claims `<=10s` / `<=10s` was achieved. |
| No implementation/test/Docker/artifact/SVM/trading/L2/L4 changes were added by final stale-status fix | PASS with caveat | Fix dev log reports docs-only scope. Current working tree still has pre-existing Docker/package/tool/test diffs from the warm-worker feature stream, so this cannot be proven from `git diff` alone. |

---

## Completion Protocol Status

Required protocol from `docs/CURRENT_DEVELOPMENT.md`:

1. Feature doc created: PASS (`docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` exists).
2. `docs/INDEX.md` updated: PASS (feature row present).
3. Feature moved to Recently Completed: PASS (`docs/CURRENT_DEVELOPMENT.md` Recently Completed row present).

Completion protocol is complete, but closeout acceptance still FAILS due to stale current-facing Obsidian status notes.

---

## Commands Run

### Session awareness

Command:

```powershell
git status --short
```

Result: exit 0. Working tree was dirty before this review. Relevant output included:

```text
 M Dockerfile.ris
 M docs/CURRENT_DEVELOPMENT.md
 M docs/CURRENT_STATE.md
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/features/ris-marker-structural-parser-scaffold.md
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md"
 M "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? docs/dev_logs/2026-05-08_fix-marker-final-l1-blocked-status.md
?? docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

Command:

```powershell
git log --oneline -5
```

Result: exit 0.

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### Required stale-status grep

Command:

```powershell
rg -n "blocked awaiting Docker IPC|blocked pending warm-worker|blocked on IPC warm-worker|blocked on Feature 3 closeout|Active Feature 3|NOT yet closed" docs
```

Result: exit 0. Most matches are historical dev logs or dated session context. Blocker-relevant current-doc output:

```text
docs\obsidian-vault\Claude Desktop\09-Decisions\Decision - Academic Pipeline Hosting.md:102:- [~] GPU performance baseline run: <=10 s/paper on the production host ... Measured timings: paper 1 = 45.55s, paper 2 = 69.73s, paper 3 = 48.31s. See Active Feature 3 in CURRENT_DEVELOPMENT.md.
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Canonical Academic Parse Queue.md:47:> **v1 Active Feature 3 (Docker IPC warm-worker - activated 2026-05-07; revised gates PASS 2026-05-08):**
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Structural Parser Integration.md:96:... See Active Feature 3 in `CURRENT_DEVELOPMENT.md` and `Work-Packet - Marker Docker IPC Warm-Worker v1`.
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Marker Structural Parser Integration.md:126:... See Active Feature 3 in CURRENT_DEVELOPMENT.md.
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Prefetch Label Discovery Mode.md:147:> [!SUCCESS] Marker Docker IPC Warm-Worker v1 - Now Active Feature 3 (2026-05-07)
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Prefetch Label Discovery Mode.md:157:> **L1 Marker production rollout remains blocked until Feature 3 closeout verification passes.**
docs\obsidian-vault\Claude Desktop\12-Ideas\Work-Packet - Prefetch Label Discovery Mode.md:158:> See Active Feature 3 and Paused/Deferred table in `CURRENT_DEVELOPMENT.md`.
```

Historical/non-blocking examples also appeared in `docs/dev_logs/**` and `docs/INDEX.md` recent-dev-log summaries.

### Required CURRENT_DEVELOPMENT grep

Command:

```powershell
git grep -n "Feature 3\|Marker Docker IPC" docs/CURRENT_DEVELOPMENT.md
```

Result: exit 0.

```text
docs/CURRENT_DEVELOPMENT.md:92:| Marker Docker IPC Warm-Worker v1 ... Revised gate ... Measured: 45.55s/69.73s/48.31s ... L1 Marker production rollout UNBLOCKED. L2/L4 remain stubs. ...
docs/CURRENT_DEVELOPMENT.md:96:| Marker Single-Paper Validation Control Surface ... L1 production blocked on <=10s/paper gate at time of closeout (**gate later revised/superseded 2026-05-08 - see Marker Docker IPC Warm-Worker v1 closeout above**). |
docs/CURRENT_DEVELOPMENT.md:116:| RIS L1 Marker Production Rollout - Validation ... warm-worker v1 complete (Feature 3 closed 2026-05-08) ... Resume trigger met 2026-05-08 ...
docs/CURRENT_DEVELOPMENT.md:140:- ... Docker IPC warm-worker (v1) is COMPLETE (2026-05-08) ... L1 Marker Production Rollout is UNBLOCKED ...
docs/CURRENT_DEVELOPMENT.md:145:- ... Marker Docker IPC warm-worker v1 is COMPLETE (2026-05-08) - active count is now 2 ...
```

Interpretation: CURRENT_DEVELOPMENT is internally acceptable for this check.

### Required status and diff checks

Command:

```powershell
git status --short
```

Result: exit 0. Dirty tree with docs, Obsidian vault state, Dockerfile, package/tool/test changes, and many untracked dev logs/features. Key implementation/test/Docker entries:

```text
 M Dockerfile.ris
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
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
 docs/CURRENT_DEVELOPMENT.md                        |  15 +-
 docs/CURRENT_STATE.md                              |  58 +-
 docs/INDEX.md                                      |  21 +-
 ...026-05-03_academic-pipeline-hosting-decision.md |  18 +-
 .../ris-marker-structural-parser-scaffold.md       |  13 +-
 packages/research/ingestion/fetchers.py            | 137 ++++
 packages/research/ingestion/marker_queue.py        | 111 +++-
 tests/test_ris_marker_queue.py                     | 724 +++++++++++++++++++++
 tools/cli/research_marker_queue.py                 | 133 +++-
 25 files changed, 1962 insertions(+), 249 deletions(-)
```

Command:

```powershell
git diff --name-status
```

Result: exit 0. Relevant output:

```text
M	Dockerfile.ris
M	docs/CURRENT_DEVELOPMENT.md
M	docs/CURRENT_STATE.md
M	docs/INDEX.md
M	docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
M	docs/features/ris-marker-structural-parser-scaffold.md
M	docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md
M	docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md
M	docs/obsidian-vault/Claude Desktop/Current-Focus.md
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

Command:

```powershell
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
```

Result: exit 0.

```text
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

Interpretation: current working tree contains non-doc changes from the warm-worker feature stream. The final stale-status fix log says it only changed docs; this review did not add code/test/Docker changes.

### Changed-doc inspection

Command:

```powershell
git diff -- docs/features/ris-marker-structural-parser-scaffold.md docs/INDEX.md docs/CURRENT_DEVELOPMENT.md
```

Result: exit 0. Confirmed the three prior blocker locations were changed from blocked/deferred wording to closed/unblocked wording.

Command:

```powershell
git diff -- "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md"
```

Result: exit 0. Confirmed stale "Active Feature 3" and "L1 remains blocked until Feature 3 closeout verification passes" text remains in current Obsidian notes.

### Full pipeline / L2 / L4 negative checks

Command:

```powershell
rg -n "full academic/RIS pipeline (is )?complete|full RIS pipeline (is )?complete|academic/RIS pipeline complete" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md docs/features/ris-marker-structural-parser-scaffold.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

Result: exit 1, no output.

Command:

```powershell
rg -n "L2[^\n]*(UNBLOCKED|unblocked)|PaperQA2[^\n]*(UNBLOCKED|unblocked)|L4[^\n]*(UNBLOCKED|unblocked)" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md docs/features/ris-marker-structural-parser-scaffold.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

Result: exit 1, no output.

### Revised gate timing check

Command:

```powershell
rg -n "45\.55s|69\.73s|48\.31s|<=10s.*achiev|<=10s.*achiev|achiev.*<=10s|achiev.*<=10s" docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md docs/features/ris-marker-structural-parser-scaffold.md "docs/obsidian-vault/Claude Desktop/Current-Focus.md" "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
```

Result: exit 0. Relevant output confirms timings preserved and no `<=10s achieved` claim:

```text
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:116:| 1 (Polymarket microstructure) | 2604.24366 | 45.55s | 72.31s | **26.76s (cold-load)** | marker | true |
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:117:| 2 (COVID-19 sports betting) | 2109.07581 | 69.73s | 69.86s | **0.13s (warm)** | marker | true |
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md:118:| 3 (Sports betting inefficiencies) | 1910.08858 | 48.31s | 48.53s | **0.22s (warm)** | marker | true |
docs/CURRENT_DEVELOPMENT.md:92:... Measured: 45.55s/69.73s/48.31s; papers 2-3 delta=0.13s/0.22s. Original <=10s/paper gate rejected as unrealistic. L1 Marker production rollout UNBLOCKED. L2/L4 remain stubs. ...
docs/CURRENT_STATE.md:1832:| arxiv:2604.24366 (paper 1) | 45.55s | 72.31s | 26.76s (cold-load) | marker | true |
docs/CURRENT_STATE.md:1833:| arxiv:2109.07581 (paper 2) | 69.73s | 69.86s | **0.13s (warm)** | marker | true |
docs/CURRENT_STATE.md:1834:| arxiv:1910.08858 (paper 3) | 48.31s | 48.53s | **0.22s (warm)** | marker | true |
```

---

## Commands Not Run

No tests, validation commands, Docker commands, queue commands, artifact mutations, SVM commands, trading commands, L2 commands, or L4 commands were run.

I did not run `python -m polytool --help` because the task explicitly said not to run validation and provided a fixed verification command list.

---

## Blockers / Fixes Needed

Blocking fixes before accepting Feature 3 closeout:

1. Update `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md:102` to point to the closed warm-worker feature doc/current closeout, not Active Feature 3.
2. Update `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md:47` so v1 is closed/complete, not Active Feature 3.
3. Update `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md:96` and `:126` so they point to the closed warm-worker closeout, not Active Feature 3.
4. Update `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md:147-158`; this is the clearest current blocker because it still says L1 remains blocked until Feature 3 closeout verification passes.

---

## Codex Review Summary

Tier: docs-only closeout verification.

Issues found:

- Blocking: current Obsidian notes still refer to Marker Docker IPC Warm-Worker v1 as Active Feature 3 after closeout.
- Blocking: one current Obsidian note still says L1 Marker production rollout remains blocked until Feature 3 closeout verification passes.

Issues addressed: none in source docs. Per instruction, this review changed only this dev log.
