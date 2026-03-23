# Phase 1 Docs Closeout

**Date**: 2026-03-21
**Branch**: `phase-1`
**Type**: Docs-only — no source code, no tests, no config changes.

---

## Purpose

Authority and current-state docs were updated to explicitly record Phase 1
benchmark closure as complete and to leave a clean handoff note for the next
chat, which should start Phase 2 (Gate 2 scenario sweep).

---

## Proof of Phase 1 Completion

The following artifacts exist and are validated:

| Artifact | Path | Status |
|---|---|---|
| Tape manifest | `config/benchmark_v1.tape_manifest` | 50 paths |
| Lock file | `config/benchmark_v1.lock.json` | sha256 verified |
| Audit file | `config/benchmark_v1.audit.json` | selected tapes logged |

**Validation output** (from `benchmark-manifest validate`):

```
[benchmark-manifest] valid: config\benchmark_v1.tape_manifest
[benchmark-manifest] bucket counts: politics=10, sports=15, crypto=10, near_resolution=10, new_market=5
[benchmark-manifest] manifest sha256: d27369a22c526b5824fc127b0f4c9ebdab8db1544a234f49535d317921633827
[benchmark-manifest] lock verified: config\benchmark_v1.lock.json
```

**Five `new_market` tapes selected** (from `config/benchmark_v1.audit.json`):

- `xrp-updown-5m-1774209300`
- `sol-updown-5m-1774209300`
- `btc-updown-5m-1774209300`
- `bnb-updown-5m-1774209300`
- `hype-updown-5m-1774209300`

See `docs/dev_logs/2026-03-21_phase1_finalization_check.md` for the full
command log including the tape-dir inspection, process termination, and the
exact finalization commands.

---

## Inventory-Root Nuance (critical for future operators)

Default `benchmark-manifest` inventory roots are:

```
artifacts/simtrader/tapes
artifacts/silver
```

These roots do **not** include `artifacts/tapes/new_market`. Running plain
`python -m polytool benchmark-manifest` after the live new-market capture
still reported `new_market=5` shortage because the Gold tapes under
`artifacts/tapes/new_market/` were invisible to the scanner.

**Correct finalization command** (must use all three roots):

```powershell
python -m polytool benchmark-manifest \
  --root artifacts/simtrader/tapes \
  --root artifacts/silver \
  --root artifacts/tapes/new_market
```

This is the command that wrote `config/benchmark_v1.tape_manifest` and closed
Phase 1. Future benchmark refreshes and any new `benchmark_v1` closure attempt
**must** include `--root artifacts/tapes/new_market` or the new-market tapes
will be missed.

This nuance is also captured in `docs/CURRENT_STATE.md` (benchmark-manifest
Pending section and the Phase 2 starting-point subsection).

---

## Files Changed and Why

| File | Change | Reason |
|---|---|---|
| `docs/CURRENT_STATE.md` | Updated status date to 2026-03-21; updated section header to "Phase 1 benchmark complete"; replaced stale "Benchmark_v1 inventory still blocked" bullet with "CLOSED" bullet including inventory-root nuance; updated Gate 2 sweep bullet; added Phase 2 starting-point subsection. | Primary authority doc for repo truth — must explicitly state Phase 1 is done. |
| `docs/ROADMAP.md` | Updated Track A status section date (2026-03-07 → 2026-03-21); replaced "DuckDB setup and integration is next step" with Phase 2 sweep note; updated scenario sweep gate checkbox with benchmark manifest note. | Implementation ledger showed stale pending state; needed to reflect benchmark closure. |
| `docs/PLAN_OF_RECORD.md` | Updated Gate 2 primary path row to note manifest exists; added Phase 1 complete bullet in Track alignment section. | Policy companion doc had benchmark sweep still described as pending. |
| `docs/TODO.md` | Updated Gate 2 Blocker section to note `benchmark_v1.tape_manifest` now exists; reframed blocker as edge scarcity only, not missing tapes. | Stale entry would mislead next operator into thinking tape capture was still needed. |
| `docs/dev_logs/2026-03-21_phase1_docs_closeout.md` | Created (this file). | Mandatory closeout dev log per repo conventions. |

**No source code, tests, config artifacts, specs, or branches were touched.**

---

## What the Next Chat Should Start With

1. **Branch**: stay on `phase-1` until Phase 1 PR is merged, then create `phase-2`.
2. **Goal**: Gate 2 scenario sweep against `config/benchmark_v1.tape_manifest`.
3. **Command to run first**:
   ```powershell
   python -m polytool --help
   python tools/gates/gate_status.py
   python -m polytool close-benchmark-v1 --status
   ```
4. **Gate 2 acceptance**: ≥ 70% of benchmark tapes show positive net PnL after
   fees and realistic fill assumptions (`close_sweep_gate.py` writes the
   artifact).
5. **Do not reopen Phase 1** tasks. The manifest, lock, and audit are finalized.

Phase 2 is the Gate 2 scenario sweep. Nothing else.
