# Feature: Crypto Pair Report v0

## Purpose

`python -m polytool crypto-pair-report --run <path>` summarizes one completed
Track 2 paper run from its local artifact bundle and writes a compact operator
packet:

- `paper_soak_summary.json`
- `paper_soak_summary.md`

The command is artifact-first. It does not require ClickHouse or Grafana.

## Inputs

Point `--run` at a completed paper-run directory, or at
`run_manifest.json` / `run_summary.json` inside that directory.

The report reads these primary artifacts:

- `run_manifest.json`
- `run_summary.json`
- `runtime_events.jsonl`

When present, it also uses:

- `observations.jsonl`
- `order_intents.jsonl`
- `fills.jsonl`
- `exposures.jsonl`
- `settlements.jsonl`

## Outputs

The report is written next to the source run artifacts.

### `paper_soak_summary.json`

Machine-readable summary with:

- run metadata
- rubric metrics
- evidence-floor checks
- per-metric pass / rerun / reject bands
- safety violation findings
- final verdict

### `paper_soak_summary.md`

Compact operator-facing Markdown with:

- key metrics table
- evidence-floor table
- rubric-band table
- decision reasons
- safety-violation list

## Rubric Metrics Covered

The v0 report computes the paper-soak metrics directly from the run artifacts:

- soak duration
- opportunities observed
- intents generated
- completed pairs (`paired_exposure_count`)
- settled pair count
- pair completion rate
- average completed pair cost
- estimated profit per completed pair
- maker fill rate floor
- partial-leg incidence
- stale count
- disconnect count
- safety violation count
- net PnL sanity

The verdict follows `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`
explicitly:

- `PROMOTE TO MICRO LIVE CANDIDATE`
- `RERUN PAPER SOAK`
- `REJECT CURRENT CONFIG / DO NOT PROMOTE`

## Safety Audit Notes

When the ClickHouse sink is disabled, the report stays file-first:

- feed-state counts come from `runtime_events.jsonl`
- frozen-window violations are audited from runtime event order
- sink-write failures are checked only when sink metadata says the sink was enabled

## Known Limitations

- The report does not query ClickHouse in v0.
- `settled_pair_count` depends on the settlement artifacts already written by the
  run; if `settlements.jsonl` is absent, the report can only use
  `run_summary.json`.
- The report does not modify run artifacts beyond adding the two summary files.
