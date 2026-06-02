---
title: Marker Docker Ipc Warm Worker V1 Closeout
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker Docker IPC Warm-Worker v1 — Feature 3 Closeout

Date: 2026-05-08
Type: docs-only closeout
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1

---

## Completion Protocol Checklist

1. [x] Feature doc created: `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`
2. [x] `docs/INDEX.md` updated — feature doc row + closeout dev log row added
3. [x] `docs/CURRENT_DEVELOPMENT.md` — Feature 3 moved from Active to Recently Completed (active count: 3 → 2)
4. [x] `docs/CURRENT_STATE.md` — warm-worker blocker resolved; L1 production rollout can resume; L2/L4 remain blocked
5. [x] `docs/obsidian-vault/Claude Desktop/Current-Focus.md` — Feature 3 marked recently completed; active priorities updated
6. [x] Work Packet — status: closed; all DoD checkboxes checked; deferred items listed
7. [x] Closeout dev log created (this file)

---

## Files Changed

| File | Change | Why |
|------|--------|-----|
| `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` | Created | Completion protocol: feature doc required |
| `docs/INDEX.md` | Added feature doc row + closeout dev log row | Completion protocol: INDEX must track all feature docs |
| `docs/CURRENT_DEVELOPMENT.md` | Moved Feature 3 from Active to Recently Completed; updated Paused section; updated Architect Notes | Completion protocol: active count 3→2; Feature 3 is done |
| `docs/CURRENT_STATE.md` | Added Marker Docker IPC Warm-Worker v1 section; updated SVM Deferred block | State truth: warm-worker blocker resolved |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Updated Active Priorities, RIS status table, Key Blockers, Recent Session Context | Living doc: Feature 3 closed, L1 can resume |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md` | status: closed; all DoD [x]; final deferred items listed | Work packet truth-sync at close |
| `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md` | Created (this file) | Mandatory dev log for every meaningful work unit |

No implementation code, tests, Docker files/images, validation queues/artifacts, SVM
labels/models, trading files, L2, or L4 were touched.

---

## Validation Evidence Summary

Live session: 3 full academic PDFs in one Docker/GPU warm-worker session on RTX 2070
Super (CUDA 13.2). No container restart between papers. daemon=False fix confirmed.

| Paper | arxiv_id | parse_seconds | total_seconds | delta |
|-------|----------|--------------|--------------|-------|
| 1 (Polymarket microstructure) | 2604.24366 | 45.55s | 72.31s | 26.76s (cold-load) |
| 2 (COVID-19 sports betting) | 2109.07581 | 69.73s | 69.86s | **0.13s (warm)** |
| 3 (Sports betting inefficiencies) | 1910.08858 | 48.31s | 48.53s | **0.22s (warm)** |

All 3: `body_source=marker`, `ipc_warm_worker_used=true`, no pdfplumber fallback, no
daemon error, queue semantics intact (done=3, failed=0, pending=0), clean shutdown.

Papers 2–3 delta (0.13s, 0.22s) confirms cold-load overhead eliminated. Models remain
warm in GPU VRAM across the session.

---

## Revised Gate Summary

| Criterion | Threshold | Evidence | Result |
|-----------|-----------|----------|--------|
| ≥3 full PDFs in one warm session | all done | done=3, failed=0 | PASS |
| Papers 2+ delta ≤5s | cold-load eliminated | 0.13s, 0.22s | PASS |
| `body_source=marker` all papers | true | all 3 | PASS |
| `ipc_warm_worker_used=true` all papers | true | all 3 | PASS |
| No pdfplumber fallback | none | confirmed | PASS |
| No daemon-process error | none | confirmed | PASS |
| Clean shutdown, no orphans | exit_code=0 | confirmed | PASS |
| `ipc_warm_worker_used` persisted in `results.jsonl` | fix applied | 4 new tests pass | PASS |

**Old gate rejected:** Original ≤10s/paper timing gate for papers 2+ is superseded as
unrealistic. Marker's five-stage multi-model pipeline requires ~45–70s warm inference on
the RTX 2070 Super for full academic PDFs (15–46 pages). This is a hardware constant,
not a regression. Director decision: gate replaced with functional warm-worker gate above.

---

## Commands Run (test plan from OBJECTIVE)

### `git diff --stat -- docs`

Expected: closeout docs created/updated.

```
docs/CURRENT_DEVELOPMENT.md
docs/CURRENT_STATE.md
docs/INDEX.md
docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md
docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-v1-closeout.md
docs/obsidian-vault/Claude Desktop/Current-Focus.md
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md
```

### `git grep` verification targets

- Feature 3 in Recently Completed: PASS
- Active count 2: PASS
- No active ≤10s/paper claims in feature doc / CURRENT_DEVELOPMENT.md / CURRENT_STATE.md: PASS

---

## Remaining Blocked / Stubbed Work

| Item | Status |
|------|--------|
| L1 Marker Production Rollout — scheduling, full queue pipeline, production | Paused — now UNBLOCKED by Feature 3 closeout; next explicit Director workpacket required |
| L2 PaperQA2 RAG Control Flow | Stub — explicitly blocked until L1 production rollout completes |
| L4 Multi-source Academic Harvesters | Stub — explicitly blocked until L1 + L3 production ready |
| Automatic warm-worker startup on container boot | Deferred — v1 scope is manual trigger only |
| IPC crash recovery / reconnect | Deferred — post-v1 hardening pass |
| Bulk re-ingest of pdfplumber corpus | Deferred — separate cleanup task |

---

## Recommended Next Workpacket

L1 Marker Production Rollout is the natural next step. The warm-worker v1 closeout
removes the last stated blocker for L1. The L1 workpacket (`Work-Packet - Marker
Structural Parser Integration`) should be reviewed and activated as the new Feature 3
at Director's discretion.

Specifically: the next L1 packet should cover production scheduling integration (APScheduler
warm-worker startup, queue drain loop, retry policy), Grafana/health monitoring integration,
and an end-to-end validation run with the production queue (not the isolated validation queue).

Do NOT activate L2 or L4 until L1 production rollout is stable.

---

## Codex Review Summary

Docs-only closeout session. No implementation code, tests, Docker files, validation
queues/artifacts, SVM labels/models, trading files, L2, or L4 in scope.

Issues found: none.
Issues addressed: N/A.
