# Roadmap 3 Completion (Resolution Coverage)

Roadmap 3 is complete.

## Completion criteria
- `UNKNOWN_RESOLUTION` for objectively resolved markets reduced to < 5%
- Resolution records include explicit `resolution_source` and `reason`
- Scan trust artifacts show stable resolved outcome coverage
- **No-knob parity**: `--enrich-resolutions` (without explicit `--resolution-*` knobs) must
  achieve comparable resolved coverage to a knobbed run, OR the scan must detect and
  explicitly report a dataset mismatch via `resolution_parity_debug.json`.

## Command used (evidence run)
```bash
python -m polytool scan --user "@DrPufferfish" --api-base-url "http://127.0.0.1:8000" --ingest-positions --compute-pnl --enrich-resolutions --resolution-max-candidates 300 --resolution-batch-size 25 --resolution-max-concurrency 4 --debug-export
```

## Evidence
- Run ID: `dd32ff26-b751-41a3-9aae-e9f59645040f`
- `unknown_resolution_rate = 0.0`
- `resolved_total = 48`
- `WIN+LOSS covered rate = 100%`

## Enrichment parity fix (2026-02-12)

The enrichment payload now always includes explicit `max_candidates`, `batch_size`,
and `max_concurrency` values (from config defaults when no CLI knobs are passed).
Each scan run emits a `resolution_parity_debug.json` artifact containing:
- `positions_identity_hash` — stable SHA-256 over sorted position identifiers
- `enrichment_request_payload` — the exact knobs sent to `/api/enrich/resolutions`
- `enrichment_response_summary` — candidates_total, candidates_selected, truncated, etc.

When comparing two runs, differing `positions_identity_hash` values indicate the
underlying position datasets changed between runs (common with sequential runs on
different DB states). The `enrichment_request_payload` field confirms both runs
used identical enrichment parameters.

## Remaining issues (not Roadmap 3)
- Deterministic `trade_uid` coverage is still `0%`
- `fees_source` is still `unknown` for this run

Next milestone focus: Roadmap 4 (Hypothesis Validation Loop), including fee/PnL completeness and hypothesis workflow hardening.
