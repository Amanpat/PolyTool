# Feature: close_ts ladder and explainability

## Summary
CLV now records explicit close-timestamp ladder diagnostics per position:
- `close_ts_attempted_sources`
- `close_ts_failure_reason`

This makes `NO_CLOSE_TS` rows auditable instead of opaque.

## Ladder behavior
Priority order:
1. `resolved_at` (on-chain resolution timestamp)
2. gamma closed-time fields (for example `gamma_closedTime`, `closedTime`, `close_date_iso`)
3. gamma end-date fields (for example `gamma_endDate`, `endDate`, `end_date_iso`)
4. gamma UMA end-date aliases

If no usable timestamp is found:
- `close_ts = null`
- `close_ts_source = null`
- explainability fields are populated.

## Export changes
Position export now carries fallback market-close fields when available, so CLV can consume them:
- `gamma_close_date_iso` / `close_date_iso`
- `gamma_end_date_iso` / `end_date_iso`
- `gamma_uma_end_date` / `uma_end_date` (nullable path)

## Verification
1. Run scan with CLV enabled.
2. Open `dossier.json` and inspect any row where `clv_missing_reason = "NO_CLOSE_TS"`.
3. Confirm:
   - `close_ts_attempted_sources` is present
   - `close_ts_failure_reason` is present and stable
4. For rows with fallback timestamps present, confirm:
   - `close_ts` and `close_ts_source` are populated from the ladder.

