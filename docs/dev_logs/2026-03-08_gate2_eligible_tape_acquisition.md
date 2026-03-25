# Dev Log: Gate 2 Eligible Tape Acquisition

**Date**: 2026-03-08
**Branch**: simtrader
**Spec**: SPEC-0014

---

## Context

SPEC-0013 identified Gate 2 as the primary blocker to Stage 1 capital. The
`bitboy-convicted` tape failed with `executable_ticks=0` — insufficient depth
on both legs. The existing scan/watch/prepare tooling was operational but
lacked:

1. **Regime metadata** on recorded tapes (no way to track politics/sports/new_market coverage)
2. **Corpus visibility** (no command to check how many tapes are eligible and which regimes are covered)
3. **Eligibility invariant enforcement** in tooling (the `prepare-gate2` output showed ELIGIBLE/INELIGIBLE per run but produced no durable manifest for cross-tape audit)

---

## What was built

### `tools/cli/tape_manifest.py` (new)

New `tape-manifest` CLI command. Scans a tape directory, runs
`check_binary_arb_tape_eligibility` on every tape, reads regime metadata,
and emits `artifacts/gates/gate2_tape_manifest.json`.

Key design decisions:
- Eligibility invariant is explicit: `eligible = result.eligible and executable_ticks > 0`
  — even if the eligibility check returns `eligible=True`, we verify `executable_ticks > 0`
  to guard against any future drift in the eligibility check
- `reject_reason` is always non-empty for ineligible tapes
- `corpus_note` gives the operator a single-line verdict: BLOCKED / PARTIAL / OK

### `--regime` flag on `watch-arb-candidates` and `prepare-gate2`

Both tools now accept `--regime` (choices: politics, sports, new_market, unknown).
The label is written to `watch_meta.json` or `prep_meta.json` and read back by
`tape-manifest` for corpus coverage tracking.

`ResolvedWatch` dataclass gained `regime: str = "unknown"` — backward compatible.

### Tests (`tests/test_gate2_eligible_tape_acquisition.py`)

34 new tests covering:
- Shallow-book tape → `eligible=False` (regression guard)
- No-edge tape → `eligible=False` (regression guard)
- Empty tape → `eligible=False`
- Missing events.jsonl → `eligible=False`
- Good tape (depth + edge) → `eligible=True`, `executable_ticks > 0`
- Regime reading from watch_meta, prep_meta, meta.json shadow_context
- Regime fallback to "unknown"
- Corpus summary counts (all ineligible, partial, fully covered)
- `mixed_regime_eligible` logic (requires ≥ 2 named regimes, not "unknown")
- Manifest schema fields
- Ineligible tape always has reject_reason
- `ResolvedWatch.regime` field defaults and mutations
- `prepare_candidates` writes regime to prep_meta.json

---

## Operator impact

No workflow changes required. Existing `watch-arb-candidates` and
`prepare-gate2` runs without `--regime` continue to work; tapes default
to `regime=unknown`.

New recommended workflow step after any tape capture session:

```bash
python -m polytool tape-manifest
```

This replaces the manual "count eligible tapes" mental model with a
machine-readable manifest that makes later gate decisions easier.

---

## Remaining blockers to Gate 2

This work makes the corpus state visible but does not produce eligible tapes.
The actual blockers remain operational:

1. **No eligible tape exists**: the live market must dislocate with
   `sum_ask < 0.99` AND `min(yes_size, no_size) >= 50` simultaneously
2. **No politics tapes**: zero tapes labeled `politics` in the current corpus
3. **No new_market tapes**: zero tapes from markets < 48h old

**Next operator action**: run `watch-arb-candidates` during a catalyst event
(game start, election night, new market launch) targeting markets with
sufficient depth from `scan-gate2-candidates`.

Gate 2 is not passed. Gate 3 remains blocked behind Gate 2.
