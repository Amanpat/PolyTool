# 2026-04-10 — Wallet Discovery v1 Integration (Packets A and B)

**Task:** quick-260410-ge0 — Integrate Wallet Discovery v1 Packets A and B into coherent combined state on main.

**Status:** COMPLETE — 106 touched-area tests pass, regression baseline 3896 maintained.

---

## Objective

Packets A (Loop A storage + plumbing, commit `83832e1`) and B (MVF + scan --quick,
commit `724a23c`) were implemented by parallel agents and pushed sequentially to main.
Both commits were already reachable from HEAD before this integration pass. This task
performed the cleanup: resolving the redundant ImportError guard in `__init__.py`,
updating package exports to cover both packets, updating the feature doc to reflect
implemented status, running the combined test suite, and writing this mandatory dev log.

---

## Git State Before

HEAD was at `e4cf989` (the ge0 plan creation commit). Both prior commits were already
linear on main:

- `83832e1` — `docs(quick-260409-qeu): Wallet Discovery v1 Loop A — STATE.md updated`
- `724a23c` — `docs(quick-260409-qez): finalize wallet discovery v1 scan-side artifacts and STATE.md table row`

No merge, rebase, or cherry-pick was needed. The integration concern was purely in
`packages/polymarket/discovery/__init__.py` — Packet B had added a `try/except ImportError`
guard as a defensive measure during parallel development (documented as "Auto-fix [Rule 1]"
in its dev log). Once both packets landed on main, the guard became dead code.

---

## What Was Changed

### 1. `packages/polymarket/discovery/__init__.py`

**Why:** The `try/except ImportError` guard around the models import was dead code.
`models.py` (shipped in Packet A) now exists on main. The guard was originally added
by Packet B to allow the MVF module to load before `models.py` was present — a
parallel-development defensive measure. Retaining it silently swallows future import
errors, which is strictly worse than fail-fast behavior.

**Changes:**
- Updated module docstring to reflect both Packet A (Loop A plumbing) and Packet B (MVF scan-side).
- Removed `try/except ImportError` guard around models imports. Replaced with direct import block.
- Added MVF exports: `compute_mvf`, `MvfResult`, `mvf_to_dict` from `packages.polymarket.discovery.mvf`.
- Single `__all__` list now covers all 11 symbols: 8 Loop A models + 3 MVF.

### 2. `docs/features/wallet-discovery-v1.md`

**Why:** The feature doc still read "Spec frozen (2026-04-09). Implementation pending."
Both packets had fully shipped.

**Changes:**
- Status line updated to: "Implemented (2026-04-09). Integrated (2026-04-10)."
- Added "Implementation" section listing both packets with commit hashes and test counts.
- CLI Surface section: removed "(pending implementation)" parenthetical from both commands.

---

## Commands Run + Output

### Step 1: Pre-flight import checks

```
python -c "from packages.polymarket.discovery.mvf import compute_mvf, MvfResult, mvf_to_dict; print('MVF imports OK')"
# MVF imports OK

python -c "from packages.polymarket.discovery.models import LifecycleState, ...; print('Models imports OK')"
# Models imports OK
```

### Step 2: Post-edit unified import check

```
python -c "from packages.polymarket.discovery import compute_mvf, MvfResult, mvf_to_dict, LifecycleState, validate_transition; print('All 11 exports OK')"
# All 11 exports OK

python -c "from packages.polymarket.discovery import __all__; assert len(__all__) == 11; print('__all__ has 11 entries')"
# __all__ has 11 entries: ['LifecycleState', 'ReviewStatus', 'QueueState', 'InvalidTransitionError', 'validate_transition', 'WatchlistRow', 'LeaderboardSnapshotRow', 'ScanQueueRow', 'compute_mvf', 'MvfResult', 'mvf_to_dict']
```

### Step 3: CLI smoke checks

```
python -m polytool discovery --help
# Shows: run-loop-a subcommand — PASS

python -m polytool scan --help | grep quick
# Shows: --quick flag with "Fast discovery scan: no LLM calls" description — PASS
```

### Step 4: Touched-area test suite

```
python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py -v --tb=short
```

Result: **106 passed in 2.53s**

### Step 5: Full regression suite

```
python -m pytest tests/ -q --tb=short -x --deselect tests/test_ris_phase2_cloud_provider_routing.py
```

Result: **3896 passed, 11 deselected, 25 warnings in 118.23s**

---

## Test Results

| Suite | Count | Result |
|-------|-------|--------|
| `test_wallet_discovery.py` (Packet A, AT-01 to AT-05) | 54 | PASS |
| `test_mvf.py` (Packet B, AT-07) | 37 | PASS |
| `test_scan_quick_mode.py` (Packet B, AT-06) | 15 | PASS |
| **Touched-area total** | **106** | **PASS** |
| Full regression (deselecting pre-existing failure) | 3896 | PASS |

---

## Merge / Conflict Decisions

None needed. Both packets were already linear on main before this integration pass.
The only "integration decision" was removing the try/except ImportError guard, which
was explicitly documented as a temporary defensive measure in Packet B's dev log.

---

## Remaining Risks

1. **`test_ris_phase2_cloud_provider_routing.py` pre-existing failure** — 8 tests fail
   with `AttributeError: module has no attribute '_post_json'`. Confirmed pre-existing
   before either packet's changes. Deferred to whoever owns the RIS Phase 2 cloud
   provider routing feature.

2. **`late_entry_rate` MVF dimension returns null** — This dimension requires
   `market_open_ts` and `close_timestamp` fields on wallet positions. These fields are
   absent from the current dossier export schema (documented as "Gap E" in the spec).
   Returning null is correct behavior per the spec. No action required until Gap E is
   addressed.

---

## Codex Review

Skip — no execution layer touched, no live-capital paths, no mandatory-tier files.
This integration pass modified only package exports (`__init__.py`) and documentation.
No codex review required per CLAUDE.md policy.
