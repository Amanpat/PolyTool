# SimTrader

Record → replay → strategy-run Polymarket binary markets in simulation.

> **Full user guide:** [`docs/README_SIMTRADER.md`](../../../docs/README_SIMTRADER.md)
> — quickrun one-liner, common flags, manual record/run/sweep, artifact reference, troubleshooting.
>
> **Architecture spec:** [`docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`](../../../docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md)

---

## Quickstart

```bash
# Requires: pip install 'websocket-client>=1.6'

# Auto-pick a live binary market, record 15 min, run binary_complement_arb:
python -m polytool simtrader quickrun --duration 900

# Target a specific market:
python -m polytool simtrader quickrun --market some-slug --duration 900

# Validate without recording:
python -m polytool simtrader quickrun --market some-slug --dry-run
```

See [`docs/README_SIMTRADER.md`](../../../docs/README_SIMTRADER.md) for all flags, the manual
record/run/sweep workflow, artifact descriptions, and troubleshooting.

---

## Tape linkage

`simtrader run` writes `tape_path` and `tape_dir` into `run_manifest.json`.
`browse` and `report` use these fields to resolve the market slug from the
tape's `meta.json` when no `quickrun_context` or `shadow_context` is present
in the manifest directly. This makes plain `simtrader run` artifacts
identifiable in listings and HTML reports without needing quickrun.

## Running tests

```bash
pytest -k simtrader -v
```
