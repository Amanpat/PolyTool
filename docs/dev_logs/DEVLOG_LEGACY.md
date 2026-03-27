## 2026-03-11

Built:
- Added `tools/gates/mm_sweep.py` to discover `prepare-gate2` / sports / NHL tapes, run a five-scenario `market_maker_v1` spread sweep, summarize best per-tape PnL, and write `artifacts/gates/mm_sweep_gate/gate_passed.json` or `gate_failed.json`.
- Added `tools/gates/close_mm_sweep_gate.py` as the new Gate 2 market-maker closure wrapper.
- Added `python -m polytool simtrader sweep-mm --tapes-dir ... --out ...` to run the same market-maker sweep path from the CLI and print a summary table.
- Updated `tools/gates/gate_status.py` to report `mm_sweep_gate` as an optional fifth gate that shows `NOT_RUN` when missing and does not change the existing required-gate exit code semantics.
- Added focused regression tests for mm sweep discovery/aggregation/CLI wiring and optional gate status reporting.

First sweep run:
- Command: `python -m polytool simtrader sweep-mm --tapes-dir artifacts/simtrader/tapes/ --out artifacts/gates/mm_sweep_gate/`
- Result: `FAIL` with `0/3` positive tapes (`pass_rate=0.0%`, threshold `70%`).
- Best per-tape net PnL: Toronto `-0.75000011952048000`, Vancouver `-0.65000010358441600`, Calgary `-0.29000004621458560`.
- Artifact written: `artifacts/gates/mm_sweep_gate/gate_failed.json`.

## 2026-03-12

Built:
- Fixed `sweep-mm` / `close_mm_sweep_gate.py` so Gate 2 market-maker sweeps accept `--spread-multipliers` (default: `0.5 1.0 1.5 2.0 3.0`) and pass the multiplier through `market_maker_v1` as `spread_multiplier`, producing the five required scenarios: `spread-x050`, `spread-x100`, `spread-x150`, `spread-x200`, `spread-x300`.
- Added `--min-events` (default: `50`) to the market-maker sweep flow. Tapes below the threshold are reported as `SKIPPED_TOO_SHORT`, stale `mm_sweep_gate` artifacts are cleared, and the gate is left as `NOT_RUN` when no eligible tapes remain.
- Added spread-multiplier coverage to `market_maker_v0` / `market_maker_v1` tests so widening the A-S spread is explicitly regression-tested.

Tape guidance:
- Valid MM sweep tapes should be materially longer than the current NHL captures: target at least `>=50` effective events after per-asset normalization, which in practice means recording longer multi-asset tapes rather than 30-93 raw-event sports snippets.
- Prefer politics or newly listed (`<48h`) markets with active BBO/depth instead of thin NHL outrights; the sweep needs sustained quote updates to produce meaningful market-maker PnL.
- Recommended recording command: `python -m polytool simtrader quickrun --strategy market_maker_v1 --duration 1800 --market <slug>`.

First fixed sweep run:
- Command: `python -m polytool simtrader sweep-mm --tapes-dir artifacts/simtrader/tapes/ --out artifacts/gates/mm_sweep_gate/`
- Result: `NOT_RUN`. All three current NHL tapes were `SKIPPED_TOO_SHORT` (`40`, `33`, and `15` effective events versus `--min-events 50`), so no `mm_sweep_gate` pass/fail artifact was written.
