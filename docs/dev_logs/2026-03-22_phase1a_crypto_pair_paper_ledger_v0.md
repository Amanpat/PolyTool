# Dev Log: Phase 1A Crypto Pair Paper Ledger v0

**Date:** 2026-03-22
**Track:** Track 2
**Status:** COMPLETE WITH OUT-OF-SCOPE FULL-SUITE BLOCKER

---

## Objective

Build the Phase 1A paper-mode foundation around the crypto pair bot:
- deterministic config models
- explicit ledger records
- pure settlement / exposure / rollup helpers
- offline tests
- spec and feature docs

No CLI wiring, no live execution, and no Gate 2 work.

---

## Files changed and why

- `packages/polymarket/crypto_pairs/config_models.py`
  - Added nested paper-mode config models for filters, fees/rebates, safety knobs, and top-level caps/thresholds.
- `packages/polymarket/crypto_pairs/paper_ledger.py`
  - Added explicit ledger dataclasses plus pure helpers for intent gating, fill aggregation, partial exposure, settlement, and rollups.
- `tests/test_crypto_pair_paper_ledger.py`
  - Added offline coverage for paired fills, threshold miss, partial exposure, settlement accounting, and config validation.
- `docs/specs/SPEC-crypto-pair-paper-ledger-v0.md`
  - Added the contract-level spec for config, records, pure functions, and scanner handoff.
- `docs/features/FEATURE-crypto-pair-paper-ledger-v0.md`
  - Added the shipped-feature summary and boundaries.
- `docs/dev_logs/2026-03-22_phase1a_crypto_pair_paper_ledger_v0.md`
  - Added this implementation log.

---

## Commands run + output

### 1. Targeted paper-ledger tests

Command:

```bash
python -m pytest tests/test_crypto_pair_paper_ledger.py -q
```

Output:

```text
collected 8 items
8 passed in 0.36s
```

### 2. Crypto-pair slice validation

Command:

```bash
python -m pytest tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_scan.py -q
```

Output:

```text
collected 70 items
70 passed in 0.45s
```

### 3. Full regression command from packet test plan

Command:

```bash
python -m pytest tests/ -x -q --tb=short
```

Output:

```text
collected 2365 items
...
FAILED tests/test_gate2_eligible_tape_acquisition.py::TestResolvedWatchRegime::test_default_regime_is_unknown
AttributeError: 'ResolvedWatch' object has no attribute 'regime'
1 failed, 713 passed, 1 warning in 28.44s
```

Notes:
- The failing test is in the out-of-scope Gate 2 area.
- This packet did not touch Gate 2 files.
- The failure was recorded rather than fixed because the prompt explicitly says not to do Gate 2 work.

---

## Test results

- `tests/test_crypto_pair_paper_ledger.py`: **8 passed / 0 failed**
- `tests/test_crypto_pair_paper_ledger.py + tests/test_crypto_pair_scan.py`: **70 passed / 0 failed**
- `tests/ -x -q --tb=short`: **713 passed / 1 failed before stop**

---

## Ledger / schema decisions

1. **Use `Decimal` in memory, strings in JSON**
   - Accounting values stay deterministic in Python.
   - `to_dict()` emits JSON-safe string values for money and prices.

2. **Keep config nested and explicit**
   - Filters, fee assumptions, and safety knobs are separate dataclasses.
   - The top-level config serializes with `schema_version: crypto_pair_paper_mode_v0`.

3. **Record types are explicit**
   - Opportunity observed
   - Order intent generated
   - Leg fill recorded
   - Exposure state
   - Pair settlement
   - Market rollup
   - Run summary

4. **Fee handling uses signed adjustment**
   - `fee_adjustment_usdc > 0` means rebate.
   - `fee_adjustment_usdc < 0` means fee.
   - This keeps net cash math simple and explicit.

5. **Settlement only applies to the paired portion**
   - `paired_size = min(yes_filled_size, no_filled_size)`
   - Unpaired inventory remains visible in `PaperExposureState` and is carried through settlement records for audit clarity.

6. **Phase 1A exposure accounting is buy-side only**
   - `summarize_leg_fills()` rejects sell-side fills.
   - Sell/unwind accounting is intentionally deferred to a later packet.

7. **Rollups assume final exposure snapshots**
   - `build_market_rollups()` expects one terminal exposure record per intent for the run.
   - It does not try to reconcile multiple intrarun exposure snapshots.

8. **Intent gating reasons are deterministic strings**
   - `filter_miss`
   - `threshold_miss`
   - `stale_quote`
   - `open_unpaired_exposure`
   - `market_cap_exceeded`
   - `run_cap_exceeded`

---

## Open questions for next prompt

1. Should partial-leg unwind modeling use `taker_fee_bps` directly, or should exit-fee assumptions be split into a separate field?
2. Does the next packet want skipped decisions persisted as explicit records, or is `PaperOpportunityObservation` + block reason sufficient?
3. Should future scanner/output plumbing emit one final `PaperExposureState` per intent, or a time series of exposure snapshots?
4. Is the full-pair `$1.00` settlement model sufficient for Phase 1A, or should a later packet carry explicit resolution provenance alongside the paper settlement record?
