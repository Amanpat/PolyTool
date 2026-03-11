## Summary

Shipped an offline-only hypothesis lifecycle layer for the post-`alpha-distill`
workflow:

- `hypothesis-register`
- `hypothesis-status`
- `experiment-init`
- `experiment-run` (generated-attempt alias over `experiment-init`)

The registry is append-only JSONL and the experiment step writes a starter
`experiment.json`. No network calls. No LLM calls.

## What shipped

- Deterministic `hypothesis_id` generation from candidate identity fields
- Append-only full-snapshot events at `artifacts/research/hypothesis_registry/registry.jsonl`
- Lifecycle statuses: `proposed`, `testing`, `validated`, `rejected`, `parked`
- `experiment-init` skeleton that copies the current registry snapshot into `experiment.json`
- `experiment-run` wrapper that creates a generated attempt directory and writes the same `experiment.json`

## Safety properties

- Offline-only: all commands operate on local JSON files.
- Auditable: older registry states remain preserved in append-only JSONL.
- Deterministic: rank suffixes do not change `hypothesis_id`.
- Research-only: this tracks ideas and tests; it does not execute trades or produce signals.

## How to run it

```bash
python -m polytool hypothesis-register \
  --candidate-file alpha_candidates.json \
  --rank 1 \
  --registry artifacts/research/hypothesis_registry/registry.jsonl

python -m polytool hypothesis-status \
  --id hyp_<id> \
  --status testing \
  --reason "manual review started" \
  --registry artifacts/research/hypothesis_registry/registry.jsonl

python -m polytool experiment-init \
  --id hyp_<id> \
  --registry artifacts/research/hypothesis_registry/registry.jsonl \
  --outdir artifacts/research/experiments/hyp_<id>/exp001

python -m polytool experiment-run \
  --id hyp_<id> \
  --registry artifacts/research/hypothesis_registry/registry.jsonl \
  --outdir artifacts/research/experiments/hyp_<id>
```

Optional register-time fields:

- `--title` to override the candidate label
- `--notes` to append an initial registration note

## Outputs

- `registry.jsonl`: append-only hypothesis events
- `experiment.json`: starter experiment record with registry snapshot and candidate provenance

## Current boundary

- `experiment-run` currently aliases the same skeleton writer as `experiment-init`; experiment execution remains manual.
- Status updates are explicit operator actions via `hypothesis-status`.

## References

- `docs/specs/SPEC-hypothesis-registry-v0.md`
- `docs/dev_logs/2026-03-05_hypothesis_registry_v0.md`
