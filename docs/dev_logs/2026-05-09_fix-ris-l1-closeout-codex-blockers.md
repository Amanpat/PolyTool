# Fix: RIS L1 Closeout — Codex FAIL Blockers

**Date:** 2026-05-09
**Track:** Research Intelligence System — L1
**Context:** Codex FAIL on commit d2c0c27. Two blocking findings; fixed in this session.

---

## Codex Blockers Addressed

### Blocker 1 — Feature 3 duplicated in Active Features

**Finding:** `docs/CURRENT_DEVELOPMENT.md` had `### Feature 3: RIS L1 Marker Production
Readiness Rollout` under Active Features *and* in Recently Completed simultaneously.
Completion protocol (rule line 18) requires moving the entry to Recently Completed, not
copying it. The Architect Note already said "Active count: 2 (Features 1, 2)" which
contradicted the visible Active Features section.

**Fix:** Removed the `### Feature 3` block (lines 38–61 in the pre-fix file) from Active
Features entirely. Recently Completed row and Architect Note remain unchanged.

**Verified:**
```
rg -n "### Feature 3" docs/CURRENT_DEVELOPMENT.md
# (no output — header is gone)
```
RIS L1 Rollout now appears only at:
- Recently Completed table (line 92)
- Architect Notes (line 148)

### Blocker 2 — Stale L1-blocked / ≤10s comments in source files

**Finding (Codex):**
- `packages/research/ingestion/marker_queue.py:353` — docstring said
  "NOTE: L1 production is NOT unblocked. Live validation required before
  production deployment of this path."
- `packages/research/ingestion/marker_queue.py:269` — inline comment said
  "warm IPC worker is deferred to v1."
- `packages/research/ingestion/marker_ipc_worker.py:8` — module docstring said
  "failing the ≤10s/paper gate for papers 2+"
- `packages/research/ingestion/marker_ipc_worker.py:17` — integration contract example
  said "# warm parse, ≤10s for papers 2+"
- `packages/research/ingestion/marker_ipc_worker.py:158` — class docstring said
  "# papers 2+: warm, ≤10s on RTX 2070 Super"
- `packages/research/ingestion/marker_ipc_worker.py:270` — `start()` docstring said
  "Subsequent parse() calls return from warm VRAM (target: ≤10s/paper)."

**Fixes:**

| File | Location | Old | New |
|------|----------|-----|-----|
| `marker_queue.py` | `process_next_ipc` docstring | "L1 production is NOT unblocked. Live validation required…" | "L1 production readiness rollout COMPLETE 2026-05-09. IPC warm-worker validated 2026-05-08." |
| `marker_queue.py` | `process_next` inline comment | "warm IPC worker is deferred to v1." | "For warm IPC reuse, call process_next_ipc()." |
| `marker_ipc_worker.py` | Module docstring | "failing the ≤10s/paper gate for papers 2+" | Factual: cold-load overhead eliminated; per-paper inference ~45-70s; original ≤10s target rejected as unrealistic |
| `marker_ipc_worker.py` | Integration contract | "# warm parse, ≤10s for papers 2+" | "# warm parse, ~45-70s inference (delta ≤1s papers 2+)" |
| `marker_ipc_worker.py` | Class docstring lifecycle | "# papers 2+: warm, ≤10s on RTX 2070 Super" | "# papers 2+: warm inference ~45-70s, cold-load delta ≤1s" |
| `marker_ipc_worker.py` | `start()` docstring | "target: ≤10s/paper" | Measured: paper 2 delta=0.13s, paper 3 delta=0.22s; original target rejected |

No runtime behavior changed. Comments and docstrings only.

---

## Files Changed

| File | Change |
|------|--------|
| `docs/CURRENT_DEVELOPMENT.md` | Removed `### Feature 3` block from Active Features |
| `packages/research/ingestion/marker_queue.py` | Fixed `process_next_ipc` docstring (L1 status); fixed `process_next` inline comment (IPC v1 deferred → available) |
| `packages/research/ingestion/marker_ipc_worker.py` | Fixed module docstring, integration contract comment, class docstring lifecycle, `start()` docstring — all ≤10s references now historical/rejected |

---

## Searches Run and Outputs

### Feature 3 in Active Features

```
rg -n "### Feature 3" docs/CURRENT_DEVELOPMENT.md
# (no output)
```

### RIS L1 in CURRENT_DEVELOPMENT.md

```
rg -n "### Feature 3|RIS L1 Marker Production Readiness Rollout|Recently Completed|Active Features" docs/CURRENT_DEVELOPMENT.md
18:   - Move entry to Recently Completed
36:## Active Features (max 3)
88:## Recently Completed (rolling 30 days)
92:| RIS L1 Marker Production Readiness Rollout ...
148:- **RIS L1 Marker Production Readiness Rollout is COMPLETE (2026-05-09).**
```

Active Features section (line 36) contains only Feature 1 and Feature 2 headers. RIS L1
Rollout appears only in Recently Completed (line 92) and Architect Notes (line 148).

### Stale L1/≤10s pattern in source files

```
rg -n "L1.*blocked|blocked.*L1|<=10s|<=10 s|10s/paper|production gate|NOT unblocked|Live validation required|deferred to v1" packages/research/ingestion/marker_queue.py packages/research/ingestion/marker_ipc_worker.py
marker_ipc_worker.py:13:delta=0.22s. Original ≤10s/paper target was rejected as unrealistic.
marker_ipc_worker.py:274:        overhead eliminated for papers 2+). Original ≤10s/paper target was rejected
```

Only two matches remain, both in the context "Original ≤10s/paper target was rejected as
unrealistic" — historical/factual notes, not active gates.

---

## Test Results

```
python -m pytest tests/test_ris_marker_queue.py tests/test_ris_marker_ipc_worker.py tests/test_ris_academic_pdf.py -x -q --tb=short
197 passed, 1 skipped
```

No regressions. 1 skipped = Linux-only platform skip (correct on Windows).

---

## Active Feature Count

Active count: **2** — Feature 1 (Track 2 Paper Soak) and Feature 2 (RIS Phase 2A).
Feature 3 slot is empty. RIS L1 Rollout is in Recently Completed only.

---

## Codex Re-review

May run. All documented blockers resolved:
- ✅ Feature 3 removed from Active Features
- ✅ Stale "L1 production is NOT unblocked" docstring corrected
- ✅ Stale "deferred to v1" inline comment corrected
- ✅ All active-looking ≤10s targets updated to historical/rejected language
- ✅ 197 tests pass, 1 skipped
