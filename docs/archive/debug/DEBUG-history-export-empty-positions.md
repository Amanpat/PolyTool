# DEBUG: History Export Reports Empty Positions While Dossier Declares Positions

Date: 2026-02-18

## Symptom

- `coverage_reconciliation_report.json` shows `totals.positions_total = 0`
- Warning appears: `dossier_declares_positions_count=... but exported positions rows=0`
- `/api/export/user_dossier` reports `stats.positions_count > 0`
- `/api/export/user_dossier/history` top row can show `positions_count = 0` or a count-only payload with no position rows

## Reproduce Quickly

```bash
curl "http://127.0.0.1:8000/api/export/user_dossier?user=@DrPufferfish"
curl "http://127.0.0.1:8000/api/export/user_dossier/history?user=@DrPufferfish&limit=5&include_body=true"
```

Check:

- export stats count from `/api/export/user_dossier`
- history row `positions_count`
- history `dossier_json.positions.positions` length

## Root Cause

Two issues combined:

1. `packages/polymarket/llm_research_packets.py` lifecycle queries joined `polymarket_tokens`, but the active schema uses `market_tokens` in many deployments. When that join target was missing, both lifecycle queries could fail and dossier position rows became empty.
2. Lifecycle row parsing relied on fixed indices inside a broad exception block. A single malformed row/shape mismatch could effectively drop all rows.

Secondary scan behavior amplified this:

- history hydration selection prioritized `positions_count > 0` over actual row presence, so count-only history payloads could be chosen ahead of payloads with real rows.

## Fix

- Export lifecycle now resolves category table defensively: `polymarket_tokens` first, then `market_tokens` (equivalent source), else category defaults to `""`.
- Lifecycle parsing now enforces expected column counts per query shape and skips malformed rows per-row (without dropping valid rows).
- Scan history hydration now prefers rows with actual `positions_len > 0` before count-only rows.
- Added defensive fallback warning path:
  - when history says `positions_count=0` but dossier payload declares positions and contains rows, scan uses dossier rows and emits a warning that includes both endpoints and counts.

## Verify

1. Run tests:

```bash
pytest -q
```

2. Re-run scan:

```bash
python -m polytool scan --user "@DrPufferfish" --api-base-url "http://127.0.0.1:8000"
```

3. Confirm:

- `coverage_reconciliation_report.json` has `totals.positions_total > 0` when dossier rows exist
- warning `history_positions_fallback_used` appears only when fallback conditions are met
- category labels remain raw Polymarket labels (no custom remapping); missing category remains `Unknown` downstream
