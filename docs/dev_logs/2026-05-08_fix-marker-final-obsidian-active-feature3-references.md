# Fix: Marker Final Obsidian Active-Feature-3 References

**Date:** 2026-05-08
**Type:** Docs-only fix
**Scope:** Four Obsidian work-packet/decision files

---

## Codex Blockers Addressed

Codex FAILed closeout because a repo-wide stale-status grep found current Obsidian notes still
pointing to Marker Docker IPC Warm-Worker v1 as "Active Feature 3" or asserting L1 remains
blocked until Feature 3 closeout verification passes. The four flagged files and their fixes:

| File | Stale text | Resolution |
|---|---|---|
| `Decision - Academic Pipeline Hosting.md` line 15 | "L1 Marker production rollout remains blocked by Marker Docker IPC warm-worker validation — see 2026-05-07 live validation dev log." | Replaced: warm-worker v1 closed 2026-05-08 under revised functional gate; L1 can proceed to next explicit rollout/readiness workpacket or Director decision. |
| `Decision - Academic Pipeline Hosting.md` line 102 | "See Active Feature 3 in CURRENT_DEVELOPMENT.md." | Replaced: pointer to `FEATURE-marker-docker-ipc-warm-worker-v1.md` (closed 2026-05-08). |
| `Work-Packet - Marker Canonical Academic Parse Queue.md` frontmatter | "L1 STILL BLOCKED: v0 queue shipped; Docker IPC warm-worker (v1) required for throughput validation" | Replaced: "L1 warm-worker blocker resolved 2026-05-08; next L1 rollout/readiness step requires separate workpacket/Director decision." |
| `Work-Packet - Marker Canonical Academic Parse Queue.md` INFO callout | "L1 Marker production rollout remains blocked on v1." | Replaced: "IPC warm-worker v1 closed 2026-05-08 under revised functional gate. L1 warm-worker blocker resolved…" |
| `Work-Packet - Marker Canonical Academic Parse Queue.md` lines 47–51 | "v1 Active Feature 3 (Docker IPC warm-worker — activated 2026-05-07…)" / "L1 Marker production throughput claim cannot be made until Feature 3 closeout verification passes" | Replaced: "v1 Recently Completed Feature 3 (closed 2026-05-08)" / "L1 warm-worker blocker resolved; next L1 rollout/readiness step requires separate workpacket/Director decision." |
| `Work-Packet - Marker Structural Parser Integration.md` frontmatter | "CURRENT BLOCKER (2026-05-08): Feature 3 closeout — Marker Docker IPC Warm-Worker v1 pending Codex closeout verification." | Replaced: "Feature 3 closed 2026-05-08 under revised functional gate. L1 warm-worker blocker resolved…" |
| `Work-Packet - Marker Structural Parser Integration.md` DANGER callout | `[!DANGER] Status: BLOCKED — Pending Feature 3 Closeout` | Replaced: `[!INFO] Status: Feature 3 Closed — L1 Warm-Worker Blocker Resolved (2026-05-08)` |
| `Work-Packet - Marker Structural Parser Integration.md` line 46 | "Current blocker: Feature 3 closeout — Marker Docker IPC Warm-Worker v1 pending Codex closeout verification." | Replaced: "Feature 3 closed 2026-05-08. L1 warm-worker blocker resolved; next L1 rollout/readiness step requires separate workpacket/Director decision." |
| `Work-Packet - Marker Structural Parser Integration.md` line 96 | "See Active Feature 3 in `CURRENT_DEVELOPMENT.md` and `Work-Packet - Marker Docker IPC Warm-Worker v1`." | Replaced: pointer to `FEATURE-marker-docker-ipc-warm-worker-v1.md` (closed 2026-05-08). |
| `Work-Packet - Marker Structural Parser Integration.md` line 126 | "See Active Feature 3 in CURRENT_DEVELOPMENT.md." | Replaced: pointer to `FEATURE-marker-docker-ipc-warm-worker-v1.md` (closed 2026-05-08). |
| `Work-Packet - Prefetch Label Discovery Mode.md` lines 147–158 | "[!SUCCESS] Marker Docker IPC Warm-Worker v1 — Now Active Feature 3 (2026-05-07)" / "L1 Marker production rollout remains blocked until Feature 3 closeout verification passes. / See Active Feature 3 and Paused/Deferred table in CURRENT_DEVELOPMENT.md." | Replaced: "Feature 3 Closed 2026-05-08" / "L1 warm-worker blocker resolved. Next L1 rollout/readiness step requires a separate workpacket/Director decision." / pointer to feature doc. |

---

## Remaining Stale-Status Grep Hits — Classification

After all edits, repo-wide grep for `Active Feature 3|blocked on Feature 3 closeout|blocked until closeout verification|closeout verification passes|NOT yet closed|L1 remains blocked.*Feature 3` returned hits only in:

| Location | Why safe |
|---|---|
| `docs/INDEX.md` lines 156, 157, 165, 167, 168 | Historical dev log title rows — past-tense descriptions of what each fix session addressed. Immutable historical record. |
| `docs/INDEX.md` line 198 | Historical dev log entry dated 2026-05-03 — records the state at that date. |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` lines 42, 44 | Historical session context entries dated 2026-05-08 — record what was done/state in prior sessions. Not current status claims. |
| All `docs/dev_logs/2026-05-07_codex-verify-*.md` | Historical Codex verification logs. Record what was found on 2026-05-07. |
| All `docs/dev_logs/2026-05-08_codex-verify-*.md` and `fix-*.md` | Historical verification and fix logs. Record what was found/fixed in prior 2026-05-08 sessions. |

No remaining hit is a current status claim. All are clearly dated historical records.

---

## Completion Protocol Status

- **Feature doc:** `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` — exists ✅
- **INDEX:** Feature doc linked in features table (line 121) ✅
- **CURRENT_DEVELOPMENT:** Marker Docker IPC Warm-Worker v1 in Recently Completed row (line 92) ✅
- **Completion protocol was already present** before this fix session — this session only removed stale "Active Feature 3 / closeout pending" language that contradicted the already-accepted closeout.

---

## Scoped Dirty-Path Evidence

```
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
```

Output (identical before and after this fix session):
```
M  Dockerfile.ris
M  packages/research/ingestion/fetchers.py
M  packages/research/ingestion/marker_queue.py
M  tests/test_ris_marker_queue.py
M  tools/cli/research_marker_queue.py
```

All five are pre-existing modifications from prior sessions. No implementation-path files were
touched by this fix.

---

## What Was NOT Changed

- No implementation code, tests, Docker files, queues, artifacts, SVM labels/models, or trading files.
- `docs/CURRENT_DEVELOPMENT.md` not touched (no direct contradiction found in scope).
- `docs/CURRENT_STATE.md` not touched (not in scope and no contradiction found).
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md` not touched (lines 42/44 are historical session context entries, not current status claims — safe to leave).
- The full academic/RIS pipeline is not claimed complete anywhere.
- L2/PaperQA2 and L4 are not declared unblocked anywhere.

---

## Commands Run

```
# Baseline implementation diff
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
# → 5 pre-existing modified files; no new dirty paths

# Post-edit repo-wide stale-status search
rg -n "Active Feature 3|blocked on Feature 3 closeout|blocked until closeout verification|closeout verification passes|NOT yet closed|L1 remains blocked.*Feature 3" docs
# → All remaining hits: historical dev logs and dated session context entries — no current status claims

# Final implementation diff (unchanged from baseline)
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
# → Same 5 pre-existing modified files
```

---

## Codex Closeout Verification

Codex closeout verification may rerun. All current-looking "Active Feature 3" and
"L1 remains blocked until Feature 3 closeout verification passes" references in the four
flagged Obsidian files have been resolved. No implementation paths were changed.
