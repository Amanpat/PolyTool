# Feature: Gate 2 Eligible Tape Acquisition

**Spec**: `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md`
**Status**: Shipped
**Date**: 2026-03-08
**Branch**: simtrader

---

## What this feature does

Extends the existing Gate 2 candidate discovery and tape capture workflow to:

1. **Regime labeling during capture**: `watch-arb-candidates` and `prepare-gate2`
   now accept `--regime` (politics | sports | new_market | unknown), which is
   written into tape metadata (`watch_meta.json` / `prep_meta.json`).

2. **Tape acquisition manifest**: new `tape-manifest` CLI command scans the
   tape corpus, runs eligibility checks on every tape, reads regime metadata,
   and emits `artifacts/gates/gate2_tape_manifest.json` with per-tape evidence
   signals and a corpus coverage summary.

3. **Eligibility invariant**: the manifest enforces that `eligible=true`
   appears ONLY when `executable_ticks > 0`. Non-executable tapes are never
   mislabeled eligible.

---

## New CLI surface

```bash
# Scan tape corpus, check eligibility, emit manifest
python -m polytool tape-manifest [--tapes-dir DIR] [--out PATH]

# Watch + auto-record with regime labeling
python -m polytool watch-arb-candidates --markets <slugs> --regime sports

# Orchestrated scan → record → check with regime labeling
python -m polytool prepare-gate2 --top 3 --regime politics
```

---

## New files

| File | Purpose |
|------|---------|
| `tools/cli/tape_manifest.py` | `tape-manifest` CLI: scans tapes, emits manifest |
| `tests/test_gate2_eligible_tape_acquisition.py` | Tests for manifest, regime reading, eligibility invariant |
| `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md` | Full specification |
| `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` | Operator step-by-step runbook |

## Modified files

| File | Change |
|------|--------|
| `tools/cli/watch_arb_candidates.py` | `ResolvedWatch.regime` field; `--regime` CLI arg; regime written to `watch_meta.json` |
| `tools/cli/prepare_gate2.py` | `--regime` CLI arg; regime written to `prep_meta.json` via `prepare_candidates` |
| `polytool/__main__.py` | `tape-manifest` command registered |

---

## Manifest schema

`artifacts/gates/gate2_tape_manifest.json` (schema version `gate2_tape_manifest_v1`):

```json
{
  "corpus_summary": {
    "total_tapes": 14,
    "eligible_count": 1,
    "by_regime": {
      "politics": {"total": 0, "eligible": 0},
      "sports": {"total": 8, "eligible": 1},
      "new_market": {"total": 0, "eligible": 0},
      "unknown": {"total": 6, "eligible": 0}
    },
    "mixed_regime_eligible": false,
    "gate2_eligible_tapes": ["artifacts/simtrader/tapes/..."],
    "corpus_note": "PARTIAL: ..."
  }
}
```

---

## What this unblocks

- Operator can run `tape-manifest` at any time to see the current corpus state
- Regime coverage gaps are visible before starting Gate 3 shadow runs
- Eligible tapes are identified with their evidence stats for Gate 2 sweep

## What this does NOT do

- Does not close Gate 2 (that requires `close_sweep_gate.py` with an eligible tape)
- Does not replace the eligibility check in `sweeps/eligibility.py`
- Does not implement Opportunity Radar (still deferred)
- Does not change gate pass criteria
