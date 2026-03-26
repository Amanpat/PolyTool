# Dev Log: Phase 1B — Gate 2 Benchmark Sweep + Gate 3 Shadow Packet

**Date:** 2026-03-26
**Branch:** phase-1B
**Objective:** Close the Gate 2 tooling gaps so the benchmark sweep can run
against `config/benchmark_v1.tape_manifest`, and deliver the Gate 3 operator
runbook.

---

## Context

`benchmark_v1` was closed on 2026-03-21 with 50 tapes across 5 buckets:
`politics=10, sports=15, crypto=10, near_resolution=10, new_market=5`.

Gate 2 sweep tooling existed (`mm_sweep.py`, `close_mm_sweep_gate.py`) but
had two gaps:

1. `_build_tape_candidate` could not extract the YES asset ID from Gold
   new_market tapes (`watch_meta.json`) or Silver tapes
   (`market_meta.json`, `silver_meta.json`). Only `prep_meta.json` and
   `meta.json` context dicts were read. This would cause `ValueError` for a
   significant fraction of the 50 tapes when running against
   `benchmark_v1.tape_manifest`.

2. `close_mm_sweep_gate.py` had no `--benchmark-manifest` flag. The only way
   to target all 50 tapes was via `simtrader sweep-mm --benchmark-manifest`.
   The standalone gate closure script needed parity.

Additionally, the gate output lacked bucket-level diagnostics (no
`bucket_breakdown` in the JSON payload, no Markdown summary artifact), making
post-run triage harder.

Gate 3 had no operator runbook beyond a legacy checklist in
`tools/gates/shadow_gate_checklist.md`.

---

## Changes

### `tools/gates/mm_sweep.py`

**YES asset ID fallback chain** extended from 2 sources to 5:

| Priority | Source | Field |
|----------|--------|-------|
| 1 | `prep_meta.json` | `yes_asset_id` or `yes_token_id` |
| 2 | `meta.json` | context dicts (`quickrun_context`, `shadow_context`) |
| 3 | `watch_meta.json` | `yes_asset_id` or `yes_token_id` |
| 4 | `market_meta.json` | `token_id` |
| 5 | `silver_meta.json` | `token_id` |

**Bucket derivation** added:

- `watch_meta.json` → `bucket` (direct field, e.g. `"new_market"`)
- `market_meta.json` → `benchmark_bucket` (e.g. `"crypto"`, `"politics"`)
- `manifest_entry` → `bucket` (fallback if manifest carries it)

**`TapeCandidate` dataclass** extended with `bucket: str | None = None`.

**`discover_mm_sweep_tapes`** now reads `watch_meta.json`, `market_meta.json`,
and `silver_meta.json` per tape directory and passes them to
`_build_tape_candidate`.

**`_load_benchmark_manifest_tapes`** passes the new metadata files.

**`_build_gate_payload`** adds:
- `bucket` field per scenario in `best_scenarios`
- `bucket_breakdown` dict (only present when any tape has bucket metadata):
  ```json
  {
    "politics": {"total": 10, "positive": 7, "pass_rate": 0.7},
    "sports":   {"total": 15, "positive": 12, "pass_rate": 0.8},
    ...
  }
  ```

**`_write_gate_result`** now calls `_write_gate_markdown_summary`.

**`_write_gate_markdown_summary`** (new function): writes `gate_summary.md`
alongside the JSON gate artifact. Contains:
- One-line verdict with pass rate
- Per-bucket breakdown table (if bucket metadata present)
- Per-tape verdict table (tape name, events, best multiplier, best net profit,
  result, bucket)

### `tools/gates/close_mm_sweep_gate.py`

Added `--benchmark-manifest` argument:

```
--benchmark-manifest PATH
    Path to config/benchmark_v1.tape_manifest.
    When provided, overrides --tapes-dir and --manifest and runs
    the sweep against all 50 benchmark tapes.
```

Passes `benchmark_manifest_path` to `run_mm_sweep()`.

### `tests/test_mm_sweep_gate.py`

7 new test functions added (12 total, all passing):

| Test | What it covers |
|------|---------------|
| `test_watch_meta_yes_asset_id_fallback` | watch_meta → yes_asset_id extraction |
| `test_market_meta_token_id_fallback` | market_meta → token_id extraction |
| `test_silver_meta_token_id_fallback` | silver_meta → token_id extraction |
| `test_bucket_breakdown_present_when_buckets_known` | bucket_breakdown appears when tapes have bucket field |
| `test_bucket_breakdown_absent_when_no_buckets` | bucket_breakdown omitted when no bucket metadata |
| `test_close_mm_sweep_gate_cli_accepts_benchmark_manifest_flag` | --benchmark-manifest CLI flag wiring |
| `test_gate_summary_md_written` | gate_summary.md written alongside gate JSON |

**Notable fix during test implementation:** The test for
`test_close_mm_sweep_gate_cli_accepts_benchmark_manifest_flag` initially
failed with `AssertionError: assert None == WindowsPath(...)` because
`monkeypatch.setattr(mm_sweep, "run_mm_sweep", ...)` targeted the source
module, but `close_mm_sweep_gate.py` imports `run_mm_sweep` via
`from tools.gates.mm_sweep import ...` at load time, binding the name into
`close_mm_sweep_gate`'s own namespace. The fix was to patch
`close_gate.run_mm_sweep` and `close_gate.format_mm_sweep_summary` directly.

### `docs/specs/SPEC-phase1b-gate2-shadow-packet.md` (new)

Full Phase 1B spec covering:
- Gate 2 acceptance criteria: `tapes_positive / tapes_total >= 0.70`
- Gate 2 artifact contract (JSON payload schema with `bucket_breakdown`)
- Tape metadata fallback chain (all 5 levels)
- Gate 3 acceptance criteria and artifact contract
- Promotion path diagram
- Blockers table (Gate 2 verdict = NOT YET RUN; Gate 3 = not yet run;
  Track 2 = blocked by market availability)

### `docs/runbooks/GATE3_SHADOW_RUNBOOK.md` (new)

Full Gate 3 operator runbook replacing the legacy shadow_gate_checklist.md.
Sections:
- Prerequisites (Gate 2 must PASS)
- Safety invariants table (no real orders, cancel-all on disconnect, etc.)
- Step 1: pick a market (list-candidates command)
- Step 2: run shadow session (`simtrader shadow --strategy market_maker_v1 --duration 300`)
- Step 3: review artifacts (run_manifest.json checks, Python one-liner validator)
- Step 4: write gate_passed.json (schema + git hash command)
- Step 5: verify gate status (`gate_status.py`)
- Abort criteria
- Artifact schema reference
- Troubleshooting table

---

## Commands run

```bash
# Targeted test run after implementation
python -m pytest tests/test_mm_sweep_gate.py -v --tb=short
# Result: 12 passed, 0 failed in 0.43s
```

---

## Commits

- `d26e163` — `feat(phase-1B): fix benchmark sweep gaps — metadata fallbacks, --benchmark-manifest CLI flag, bucket diagnostics`
- `caee34f` — `docs(phase-1B): add Phase 1B spec and Gate 3 shadow runbook`
- `1a68950` — `docs(phase-1B): update CURRENT_STATE.md — Phase 1B gate tooling complete`

---

## Gate 2 — Operator Actions Needed

Gate 2 is **NOT YET RUN**. The tooling is complete. To run:

```bash
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/benchmark_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
python tools/gates/gate_status.py
```

Acceptance threshold: `>= 0.70` (at least 35 of 50 eligible tapes positive
after 200 bps fees, mark method = bid). The threshold must not be weakened.

Artifacts written to `artifacts/gates/mm_sweep_gate/`:
- `gate_passed.json` or `gate_failed.json`
- `gate_summary.md`

Discord notification fires automatically on gate result if `DISCORD_WEBHOOK_URL`
is set.

---

## Gate 3 — Operator Actions Needed

Gate 3 is **NOT YET RUN**. Requires Gate 2 PASS first.

See `docs/runbooks/GATE3_SHADOW_RUNBOOK.md` for the full procedure.

After Gate 2 passes and Gate 3 is signed off:

```bash
python tools/gates/gate_status.py
# Expected: ALL REQUIRED GATES PASSED - Track A promotion criteria met.
```

Then proceed to Stage 0 (72h paper-live dry-run).

---

## Open Issues / Deferred

- Track 2 (crypto pair) market availability: No active BTC/ETH/SOL 5m/15m
  markets as of 2026-03-25. Deferred per SPEC-phase1b-gate2-shadow-packet.md.
- Gate 2 verdict is NOT YET RUN — actual sweep result unknown until operator
  runs the command against live artifacts.
