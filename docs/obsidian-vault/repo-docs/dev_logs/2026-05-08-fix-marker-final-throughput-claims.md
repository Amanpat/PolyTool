---
title: Fix Marker Final Throughput Claims
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_fix-marker-final-throughput-claims.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: Marker Final Throughput Claims — Feature 3 Closeout Blocker

Date: 2026-05-08
Type: docs-only fix
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1 closeout readiness
Verdict: **PASS — all Codex FAIL blockers addressed**

---

## Summary

Four Codex FAIL blockers from the previous docs-consistency review
(`2026-05-08_codex-verify-marker-ipc-revised-gate-all-docs-consistency.md`) were
fixed. No implementation code, tests, Docker files, queues, artifacts, SVM,
trading files, L2, or L4 were touched.

Director decision: original ≤10s/paper / 5-10s/paper full-PDF throughput target
**rejected as unrealistic for RTX 2070 Super**. Revised gate: ≥3 full academic
PDFs complete in one Docker/GPU IPC warm-worker session; papers 2+ delta ≤5s;
body_source=marker; ipc_warm_worker_used=true; no pdfplumber fallback; no daemon
error; queue semantics intact; clean shutdown/no orphans.

Measured validated timings: 45.55s, 69.73s, 48.31s.

---

## Scoped Implementation Baseline (before and after)

`git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts`

Before fix: identical output.
After fix: identical output.

```
M	Dockerfile.ris
M	packages/research/ingestion/fetchers.py
M	packages/research/ingestion/marker_queue.py
M	tests/test_ris_marker_queue.py
M	tools/cli/research_marker_queue.py
```

No implementation paths changed in this session.

---

## Codex Blockers Addressed

### Blocker 1 — Decision - Academic Pipeline Hosting.md line 19

**Was:** Context section stated "on a modest GPU (NVIDIA 2070 Super or better) it
runs in 5-10 seconds" without any supersession note — read as a current production
claim.

**Fix:** Changed to "it was surveyed at 5-10 seconds (historical architecture
survey estimate — **rejected as unrealistic for full academic PDFs on RTX 2070
Super, Director 2026-05-08; revised gate: ≥3 papers in one IPC warm-worker
session, papers 2+ delta ≤5s; measured timings: 45.55s, 69.73s, 48.31s**)".

### Blocker 2 — Decision - Academic Pipeline Hosting.md line 102

**Was:** Unchecked prerequisite checklist item `- [ ] GPU performance baseline
run: ≤10 s/paper on the production host` — presented as an outstanding gate to
satisfy.

**Fix:** Changed to `- [~]` (crossed/superseded) with inline label:
"**SUPERSEDED 2026-05-08.** Original ≤10s/paper timing gate rejected as
unrealistic for full academic PDFs on RTX 2070 Super. Revised gate: ≥3 full
academic PDFs complete in one Docker/GPU IPC warm-worker session; papers 2+ delta
(total_seconds − parse_seconds) ≤5s; body_source=marker; ipc_warm_worker_used=true;
no pdfplumber fallback; clean shutdown/no orphans. Measured timings: paper 1 =
45.55s, paper 2 = 69.73s, paper 3 = 48.31s. See Active Feature 3 in
CURRENT_DEVELOPMENT.md."

### Blocker 3 — ris-marker-structural-parser-scaffold.md Installation section

**Was:** "GPU required for production throughput (~5–10 s/paper on RTX 2070
Super; 300 s timeout on CPU)" — presented as the current production throughput
figure.

**Fix:** "GPU required for production throughput (historical survey estimate:
~5–10 s/paper on RTX 2070 Super — **rejected as unrealistic for full academic
PDFs, Director 2026-05-08**; measured warm-worker timings: 45.55s, 69.73s, 48.31s;
300 s timeout on CPU for cold single-paper invocation)."

### Blocker 4a — Work-Packet - Marker Structural Parser Integration.md line 43

**Was:** Inside the DANGER callout's "Operator decision — Option A: Async Parse
Queue" block: "papers 2+ expected ≤10s on warm RTX 2070 Super VRAM" — still
stated as the expected behavior.

**Fix:** "papers 2+ cold-load delta expected ≤5s (revised gate 2026-05-08;
original "≤10s/paper" per-paper target **rejected as unrealistic** — measured
warm-worker timings: 45.55s, 69.73s, 48.31s; papers 2–3 deltas: 0.13s, 0.22s)"

### Blocker 4b — Work-Packet - Marker Structural Parser Integration.md line 56

**Was:** Inside the IMPORTANT callout: "Marker on this hardware is ~5-10s/paper
per the survey's evidence — fast enough for production." — stated as a current
architectural justification.

**Fix:** Struck through with `~~...~~` and appended "**Historical note, superseded
2026-05-08:** architecture survey estimate of ~5-10s/paper rejected as unrealistic
for full academic PDFs on RTX 2070 Super. Measured warm IPC worker timings:
45.55s, 69.73s, 48.31s. Revised gate is functional warm-worker throughput (≥3
papers in one IPC session, papers 2+ delta ≤5s), not per-paper timing."

### Blocker 4c — Work-Packet - Marker Structural Parser Integration.md line 126

**Was:** Open question 6 still asked "Does acceptance gate 2 ('≤10s warm') assume
warm scheduler mode only?" — an unresolved open question referencing old gate
language.

**Fix:** Marked "**NEW (2026-05-05) — RESOLVED 2026-05-08**", struck through the
question with `~~...~~`, and appended "**Resolved:** acceptance gate 2 revised
(Director 2026-05-08) — original ≤10s/paper per-paper target rejected as
unrealistic; revised gate is functional warm-worker throughput (≥3 papers in one
Docker IPC session, papers 2+ delta ≤5s, body_source=marker,
ipc_warm_worker_used=true). See Active Feature 3 in CURRENT_DEVELOPMENT.md."

---

## Files Changed

| File | Why |
|---|---|
| `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md` | Lines 19 (Context claim) and 102 (unchecked prerequisite item) were the two clearest active-looking blockers per Codex FAIL |
| `docs/features/ris-marker-structural-parser-scaffold.md` | Installation section still presented ~5–10 s/paper as current production throughput |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md` | Three spots: line 43 (papers 2+ ≤10s claim), line 56 (~5-10s/paper active justification), line 126 (open question with old gate language) |

---

## Remaining Timing Mentions — Safety Analysis

All remaining mentions in the six primary files are safe. Evidence:

| File | Line | Mention | Why safe |
|---|---|---|---|
| CURRENT_DEVELOPMENT.md | 85 | "Original ≤10s/paper timing gate **rejected**" | Explicit rejection statement |
| CURRENT_DEVELOPMENT.md | 118 | "blocked on ≤10s/paper gate at closeout (**gate later revised 2026-05-08**)" | Historical with explicit revision note |
| INDEX.md | 155 | "≤10s/paper gate language superseded in 5 locations" | Meta description of prior fix |
| INDEX.md | 159 | "≤10s/paper rejected as unrealistic; revised to ≥3 papers warm" | Historical summary |
| INDEX.md | 180 | "≤10s/paper gate fails 8.6×" | Historical validation measurement |
| Decision - Academic Pipeline Hosting.md | 19 | "surveyed at 5-10 seconds (historical... **rejected as unrealistic**)" | Now explicitly historical/rejected ✓ |
| Decision - Academic Pipeline Hosting.md | 102 | "[~] ≤10 s/paper — **SUPERSEDED 2026-05-08**" | Now explicitly superseded ✓ |
| ris-marker-structural-parser-scaffold.md | 7 | "≤10s/paper timing gate **rejected as unrealistic**" | Explicit rejection |
| ris-marker-structural-parser-scaffold.md | 14 | "≤10s/paper gate superseded 2026-05-08" | Explicit supersession |
| ris-marker-structural-parser-scaffold.md | 23 | "~5–10 s/paper GPU performance claim **was not validated**" | Explicit non-validation statement |
| ris-marker-structural-parser-scaffold.md | 89 | "historical survey estimate... **rejected as unrealistic**" | Now explicitly historical/rejected ✓ |
| CURRENT_STATE.md | 1783 | "≤10s/paper timing gate rejected as unrealistic (Director 2026-05-08)" | Explicit rejection |
| Work-Packet Structural Parser | 5 | YAML frontmatter: "85.95s >> ≤10s/paper gate" | Historical blocked-reason metadata |
| Work-Packet Structural Parser | 31 | "fails ≤10s/paper production gate by ~8.6×" | Historical measurement result |
| Work-Packet Structural Parser | 34 | "~5–10s/paper estimate... was from a warm-model benchmark not replicated here" | Explicit non-replication note |
| Work-Packet Structural Parser | 43 | "revised gate 2026-05-08; original '≤10s/paper'... **rejected as unrealistic**" | Now explicitly revised ✓ |
| Work-Packet Structural Parser | 56 | "~~...~5-10s/paper...~~ **Historical note, superseded 2026-05-08**" | Now struck through + superseded ✓ |
| Work-Packet Structural Parser | 96 | "~~≤10 seconds.~~ **Superseded (Director 2026-05-08)**" | Previously fixed, remains safe |
| Work-Packet Structural Parser | 126 | "~~'≤10s warm'?~~ **Resolved 2026-05-08**" | Now struck through + resolved ✓ |

---

## Commands Run

```
# Scoped implementation baseline
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
# Result: same 5 pre-existing implementation files; no change from this session

# Targeted timing-claim grep across 6 primary files
rg -n "5.?10|<=10s|<=10 s|10s/paper|10 seconds" \
  "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md" \
  "docs/features/ris-marker-structural-parser-scaffold.md" \
  "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md" \
  docs/CURRENT_DEVELOPMENT.md docs/CURRENT_STATE.md docs/INDEX.md
# Result: 19 matches reviewed; all are historical/rejected/superseded (see table above)

# Doc diff stat
git diff --stat -- docs
# Result: 18 files changed, 537 insertions(+), 231 deletions(-)
# Note: Obsidian .smart-env cache JSON files inflate the count; primary doc changes
#       are the 4 files listed in Files Changed above.
```

---

## What Is Explicitly NOT Done

- Feature 3 not moved to Recently Completed.
- No feature closeout doc created.
- No implementation code, tests, Docker files, queues, or artifacts touched.
- No L2, L4, PaperQA2, SVM, or trading files touched.
- No validation rerun.
- No Docker rebuild or prune.

---

## Whether Codex Closeout Verification May Rerun

Yes. All four FAIL blockers from the previous Codex review are addressed. The
active `<=10s` and `5-10s/paper` production-throughput claims that were either
unchecked checklist items or unqualified current assertions have been replaced
with clearly superseded/rejected/historical language with the measured validated
timings (45.55s, 69.73s, 48.31s) preserved. Codex closeout verification for
Feature 3 may proceed.

---

## Codex Review Summary

Tier: docs-only blocker fix. No code, tests, Docker, queues, artifacts, SVM,
trading, L2, L4, or validation runs were touched.

Issues found: 6 active-looking timing claims across 3 files (Codex FAIL
blockers 1–4).

Issues addressed: all 6 fixed with explicit supersession/rejection language and
measured timings.
