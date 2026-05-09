# Fix: Marker IPC Revised Gate — All-Docs Consistency

Date: 2026-05-08
Type: docs-only fix
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1
Verdict: **COMPLETE** — all active docs now show ≤10s/paper gate as rejected/superseded; CURRENT_STATE.md shows warm-worker as Active Feature 3

---

## Codex Blockers Addressed

Codex FAIL (`docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-doc-consistency.md`)
identified three blocking issues after the prior fix session:

1. **Active ≤10s/paper language remaining in 5 locations across 4 docs** not yet fixed by the
   previous `fix-marker-ipc-revised-gate-doc-consistency` session:
   - `docs/features/ris-marker-structural-parser-scaffold.md:7` — status header still said gate failed by 8.6×
   - `docs/features/ris-marker-structural-parser-scaffold.md:14` — resume trigger still said `≤10s/paper`
   - `docs/obsidian-vault/…/Work-Packet - Marker Structural Parser Integration.md:96` — acceptance gate 2 still required ≤10 seconds
   - `docs/obsidian-vault/…/Work-Packet - Marker Canonical Academic Parse Queue.md:60` — Goal item 2 still said `≤10s/paper post-load`
   - `docs/obsidian-vault/…/Work-Packet - Marker Canonical Academic Parse Queue.md:101` — Acceptance gate 3 still required `≤10s/paper`
   - `docs/obsidian-vault/…/Work-Packet - Prefetch Label Discovery Mode.md:154,157` — deferred warning block still required `≤10s/paper`

2. **`docs/CURRENT_STATE.md` still said warm-worker v1 is deferred** from Queue v0, conflicting
   with `CURRENT_DEVELOPMENT.md` where it is Active Feature 3.

3. **Repo-level implementation path evidence** clarification: implementation file changes
   (Dockerfile.ris, packages/research/ingestion/\*, tests/test_ris_marker_queue.py,
   tools/cli/research_marker_queue.py) are pre-existing Feature 3 implementation changes from
   prior sessions — not introduced by this docs fix session.

All three blockers addressed by this session.

---

## Files Changed and Why

### `docs/features/ris-marker-structural-parser-scaffold.md`

**Why:** Feature doc for the completed Marker scaffold. Two callout-block lines still described
the ≤10s/paper gate as the active acceptance criterion for L1 rollout. Status header said "blocked
awaiting async queue implementation" rather than the current truth (blocked on Feature 3 closeout).

**Changes:**
- **Line 3 (status header):** Updated from "awaiting async queue implementation, 2026-05-05" to
  "pending Marker Docker IPC Warm-Worker v1 Feature 3 closeout, 2026-05-07".
- **Line 7 (gate failure callout):** Reworded from "fails the ≤10s/paper production gate by ~8.6×"
  to say the cold-start time is honest and that the original aspirational ≤10s/paper gate was
  **rejected as unrealistic (Director 2026-05-08)** with pointer to Active Feature 3.
- **Lines 13–14 (resume trigger):** Updated from `≤10s/paper` to "Marker Docker IPC Warm-Worker v1
  Feature 3 closeout verification passes (≤10s/paper gate superseded 2026-05-08)".

### `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md`

**Why:** Acceptance gate 2 still required Marker to parse a typical arXiv paper in ≤10 seconds —
an active, non-historical gate requirement.

**Changes:**
- **Acceptance gate 2:** Original ≤10 second requirement struck through with strikethrough and
  **Superseded (Director 2026-05-08)** note. Replaced with revised gate: ≥3 papers in one warm
  Docker IPC session; papers 2+ delta ≤5s; `body_source=marker`; `ipc_warm_worker_used=true`;
  no pdfplumber fallback. Pointer to Active Feature 3 and warm-worker work packet.

### `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md`

**Why:** Three locations with active ≤10s/paper gate requirements — the v1 deferred block, Goal
item 2, and Acceptance gate 3.

**Changes:**
- **v1 implementation status block (line ~47–53):** Changed from "v1 Deferred" to
  "v1 Active Feature 3 (activated 2026-05-07; revised gates PASS 2026-05-08)". Updated
  `parse_seconds ≤10s` to the revised gate (papers 2+ delta ≤5s). Added explicit rejection
  sentence for the original timing gate.
- **Goal item 2 (line 60):** Updated from `≤10s/paper post-load` to note the original target
  and show **revised gate 2026-05-08** (papers 2+ delta ≤5s, cold-load eliminated).
- **Acceptance gate 3 (line 101):** Struck through `≤10s/paper` requirement. Added **timing
  gate rejected as unrealistic (Director 2026-05-08)** with revised gate and actual evidence
  (paper 2 delta=0.13s, paper 3 delta=0.22s).

### `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Prefetch Label Discovery Mode.md`

**Why:** Deferred warning block still described the IPC warm-worker as deferred and still
required `≥3 papers at ≤10s/paper` as the resume trigger.

**Changes:**
- **Deferred warning block (lines 145–157):** Changed callout type from `[!WARNING]` to
  `[!SUCCESS]`. Updated to say the warm-worker is now **Active Feature 3 (2026-05-07)** with
  all revised functional gates PASS (2026-05-08). Added the Director gate rejection sentence.
  Updated resume trigger to "Feature 3 closeout verification passes".
  Preserved actual measured timings (paper 1 delta=26.76s, paper 2 delta=0.13s, paper 3 delta=0.22s).

### `docs/CURRENT_STATE.md`

**Why:** Line 1783 still said "Marker Docker IPC warm-worker v1 — deferred from Queue v0
(2026-05-05); NOT canceled." — directly contradicting `CURRENT_DEVELOPMENT.md` which shows
it as Active Feature 3.

**Changes:**
- **Line 1783:** Updated from "deferred from Queue v0" to "**Active Feature 3** (activated
  2026-05-07); revised functional gates PASS (2026-05-08); pending Codex closeout verification.
  L1 Marker Production Rollout blocked until Feature 3 closeout verification passes. Original
  ≤10s/paper timing gate rejected as unrealistic (Director 2026-05-08)."

---

## Revised Gate (current canonical form)

Director-approved 2026-05-08. Replaces all prior `≤10s/paper` gate language.

| Criterion | Threshold | Evidence |
|-----------|-----------|----------|
| ≥3 full academic PDFs in one warm session | done=3, failed=0 | confirmed |
| Papers 2+ delta (total_seconds − parse_seconds) ≤5s | cold-load not repeated | paper 2: 0.13s, paper 3: 0.22s |
| `body_source=marker` all papers | true | all 3 |
| `ipc_warm_worker_used=true` all papers | true | all 3 |
| No pdfplumber fallback | none | confirmed |
| No daemon-process error | none | confirmed |
| Clean shutdown / no orphans | exit_code=0 | confirmed |

Actual measured timings (preserved, not hidden):

| Paper | parse_seconds | total_seconds | delta |
|-------|--------------|--------------|-------|
| arxiv:2604.24366 (paper 1) | 45.55s | 72.31s | 26.76s (cold-load) |
| arxiv:2109.07581 (paper 2) | 69.73s | 69.86s | **0.13s** (warm) |
| arxiv:1910.08858 (paper 3) | 48.31s | 48.53s | **0.22s** (warm) |

---

## Baseline Scoped Evidence (start of session)

### `git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Pre-existing implementation changes (from prior Feature 3 sessions, NOT from this docs session):
```
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```
Untracked (also pre-existing): `packages/research/ingestion/marker_ipc_worker.py`, `tests/test_ris_marker_ipc_worker.py`

### `git grep -n "<=10s|≤10s|10s/paper" docs` (before fix)

Problem matches identified:
- `docs/features/ris-marker-structural-parser-scaffold.md:7` — gate failure description still active-framed
- `docs/features/ris-marker-structural-parser-scaffold.md:14` — resume trigger still said `≤10s/paper`
- `docs/obsidian-vault/…/Work-Packet - Marker Structural Parser Integration.md:96` — acceptance gate 2 active
- `docs/obsidian-vault/…/Work-Packet - Marker Canonical Academic Parse Queue.md:60,101` — goal + gate active
- `docs/obsidian-vault/…/Work-Packet - Prefetch Label Discovery Mode.md:154,157` — deferred block active

### `git grep -n "deferred from Queue v0" docs` (before fix)

```
docs/CURRENT_STATE.md:1783: Marker Docker IPC warm-worker v1 — deferred from Queue v0 (2026-05-05); NOT canceled.
```

---

## After-State Evidence

### `git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Unchanged from baseline — same pre-existing implementation changes only. No new implementation
files modified or created by this session.

### `git diff --stat -- docs` (this session's docs changes)

New changes introduced by this session:
- `docs/CURRENT_STATE.md` — 2 lines (1 changed)
- `docs/features/ris-marker-structural-parser-scaffold.md` — ~8 lines (status + callout updated)
- `docs/obsidian-vault/…/Work-Packet - Marker Structural Parser Integration.md` — ~2 lines (gate 2)
- `docs/obsidian-vault/…/Work-Packet - Marker Canonical Academic Parse Queue.md` — ~13 lines (v1 block + goal + gate 3)
- `docs/obsidian-vault/…/Work-Packet - Prefetch Label Discovery Mode.md` — ~19 lines (deferred → active callout)

### `git grep -n "<=10s|≤10s|10s/paper" docs` (after fix, active docs only)

Remaining matches — all correctly classified:
- `CURRENT_DEVELOPMENT.md:85` — "Original ≤10s/paper timing gate **rejected**..." (gate rejection statement)
- `CURRENT_DEVELOPMENT.md:118` — "L1 blocked on ≤10s/paper gate at time of closeout (**gate later revised 2026-05-08**)" (historical closeout note, labeled)
- `CURRENT_STATE.md:1783` — "Original ≤10s/paper timing gate **rejected**..." (part of updated rejection statement)
- `ris-marker-structural-parser-scaffold.md:7` — "Original aspirational ≤10s/paper timing gate **rejected as unrealistic**" (now correctly labeled)
- `ris-marker-structural-parser-scaffold.md:14` — "≤10s/paper gate superseded 2026-05-08" (labeled superseded)
- `Work-Packet - Marker Canonical Academic Parse Queue.md:23` — historical context in SUCCESS callout about why Option A was needed (describes the gate failing, not stating a current requirement)
- `Work-Packet - Marker Canonical Academic Parse Queue.md:50` — "Original...timing gate **rejected as unrealistic (Director 2026-05-08)**" (rejection statement)
- `Work-Packet - Marker Canonical Academic Parse Queue.md:61` — "original ≤10s/paper timing target; **revised gate 2026-05-08**" (labeled revised)
- `Work-Packet - Marker Canonical Academic Parse Queue.md:102` — `~~≤10s/paper~~` strikethrough + "timing gate rejected" (labeled)
- `Work-Packet - Marker Structural Parser Integration.md:5` — frontmatter `blocked-reason` historical description (frontmatter, not acceptance gate; acceptance gate 2 is fixed)
- `Work-Packet - Marker Structural Parser Integration.md:31,34,43,56` — inside DANGER/IMPORTANT callout blocks describing 2026-05-05 state, not current acceptance criteria; gate 2 (line 96) is fixed
- `Work-Packet - Marker Structural Parser Integration.md:96` — "~~≤10 seconds~~ **Superseded (Director 2026-05-08)**" (labeled superseded)
- `Work-Packet - Marker Structural Parser Integration.md:126` — open question from 2026-05-05 historical context
- `Work-Packet - Marker Single-Paper Validation Control Surface.md:14,21,29,149` — completed work packet; historical descriptions of what the gate result was at validation time (not current acceptance criteria)
- `Work-Packet - Prefetch Label Discovery Mode.md:152` — "Original ≤10s/paper timing gate rejected as unrealistic (Director 2026-05-08)" (rejection statement in updated block)
- `Current-Focus.md:4,81` — header/footer noting the gate was removed (contextual, correct)
- Dev logs (various) — immutable historical records

No active current acceptance gate anywhere in active docs still requires ≤10s/paper.

### `git grep -n "deferred from Queue v0" docs` (after fix)

No matches — CURRENT_STATE.md line 1783 updated.

---

## Remaining Blocker

Feature 3 is **NOT closed by this session.** All revised functional gates PASS and docs are now
consistent across all active documents. The sole remaining blocker before Feature 3 can move to
Recently Completed is:

- **Codex closeout verification** — a fresh Codex review of the full Feature 3 state (code +
  tests + docs) must return PASS before the completion protocol runs (feature doc creation,
  CURRENT_STATE.md update, move to Recently Completed).

---

## Confirmation: No Code / Tests / Artifacts Touched

- No changes to `packages/`, `tools/`, `tests/`, `infra/`, `config/`, or `artifacts/`.
- No Docker rebuild, prune, or container modification.
- No queue mutations, no SVM labels/models touched.
- No trading files touched.
- No L2 (PaperQA2) or L4 (multi-source harvesters) work started.
- Feature 3 NOT moved to Recently Completed.
- No feature closeout doc created (deferred to post-Codex-verification).

---

## Codex Review Summary

Tier: docs-only session. No implementation code in scope.

Issues found: five active ≤10s/paper gate locations in 4 docs; CURRENT_STATE.md showing deferred
instead of Active Feature 3.

Issues addressed: all resolved. Active ≤10s/paper acceptance gate language removed from all
active docs. CURRENT_STATE.md updated to Active Feature 3 pending closeout.
