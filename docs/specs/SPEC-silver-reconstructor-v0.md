# SPEC-silver-reconstructor-v0: Silver Tape Reconstruction Foundation

**Status:** Implemented (v0)
**Date:** 2026-03-16
**Supersedes:** None (new)

---

## Purpose

PolyTool's Gate 2 validation requires a Silver-tier tape: a deterministic, time-bounded event sequence for a single market that is sufficient for scenario sweeping. This spec defines the reconstruction contract, input sources, output format, confidence model, and known limitations for the v0 foundation.

---

## Scope

- Single market/token, bounded time window
- Offline-first: all logic is injectable; no live connections required for testing
- Foundation only: no batch generation, no full-market-library sweeps

**Not in scope for v0:**
- Multi-market batch reconstruction
- Gold tape generation (Gold requires live WS recording, not reconstruction)
- FastAPI/n8n wrappers
- Automated Gate 2 closure

---

## Database Split (v4.2 Rule)

The two databases are strictly separated:

| Source | Database | Access |
|--------|----------|--------|
| pmxt Parquet snapshots | DuckDB | Direct file reads, no import step |
| Jon-Becker trade CSV/Parquet | DuckDB | Direct file reads, no import step |
| price_2min midpoint series | ClickHouse | `polytool.price_2min` table |

DuckDB and ClickHouse never share data and never communicate.

---

## Input Sources

### Source 1: pmxt Anchor (DuckDB)

- **What it provides:** The L2 order book state nearest to / at the window start.
- **Query:** Find the pmxt snapshot row where `token_col = token_id AND ts_col <= window_start`, ORDER BY ts DESC, LIMIT 1.
- **Column detection:** Auto-detected using candidates `["token_id", "asset_id", "condition_id", "market_id"]` for token and `["snapshot_ts", "timestamp_received", "timestamp_created_at", "ts", "timestamp", "datetime"]` for timestamp.
- **Output event type:** `"book"` with `silver_source: "pmxt_anchor"`.
- **If missing:** Warning emitted, confidence degraded. The book state at window open is unknown.

### Source 2: Jon-Becker Fills (DuckDB)

- **What it provides:** Trade events within the window, applied chronologically.
- **Query:** `token_col = token_id AND ts_col >= window_start AND ts_col <= window_end`, ORDER BY ts ASC.
- **File detection:** Prefers `.parquet` files; falls back to `.csv`. Both use DuckDB auto-detection.
- **Output event type:** `"last_trade_price"` with `silver_source: "jon_fill"`.
- **Timestamp ambiguity:** If multiple fills share the same timestamp value (bucketized source), a `jon_timestamp_ambiguity` warning is emitted. Ordering within same-bucket rows is deterministic (file order) but not clock-accurate.
- **If missing:** Warning emitted, confidence degraded.

### Source 3: price_2min Guide (ClickHouse)

- **What it provides:** A 2-minute midpoint price constraint series from `polytool.price_2min`.
- **Pre-condition:** Must be populated via `fetch-price-2min --token-id <ID>` before reconstruction.
- **Output event type:** `"price_2min_guide"` (Silver-specific, not a live WS event type). Carries an explicit `note: "2-min midpoint constraint; NOT synthetic tick data"` field.
- **Usage:** This is a **constraint/guide only**. It MUST NOT be treated as synthetic tick data or used to fabricate fills at 2-minute intervals.
- **If missing:** Warning emitted, confidence degraded. Run `fetch-price-2min` to populate.

---

## Output Format

### silver_events.jsonl

One event per line, newline-delimited JSON. Each event carries the standard tape envelope plus a Silver extension:

```json
{
  "parser_version": 1,
  "seq": 0,
  "ts_recv": 1700000000.0,
  "event_type": "book",
  "asset_id": "0x...",
  "silver_source": "pmxt_anchor",
  "pmxt_raw": {"snapshot_ts": "...", "best_bid": "0.54", ...}
}
```

```json
{
  "parser_version": 1,
  "seq": 1,
  "ts_recv": 1700001800.0,
  "event_type": "last_trade_price",
  "asset_id": "0x...",
  "price": 0.55,
  "size": 10.0,
  "side": "BUY",
  "silver_source": "jon_fill"
}
```

```json
{
  "parser_version": 1,
  "seq": 2,
  "ts_recv": 1700001600.0,
  "event_type": "price_2min_guide",
  "asset_id": "0x...",
  "price": 0.55,
  "silver_source": "price_2min",
  "note": "2-min midpoint constraint; NOT synthetic tick data"
}
```

**Ordering guarantee:** Events are sorted by `ts_recv` ascending, then seq. Seq is reassigned after sort to ensure monotonic sequence numbers in the output file.

**Compatibility with ReplayRunner:** `book` and `last_trade_price` events are standard tape types and will be processed by `ReplayRunner`. `price_2min_guide` is a Silver-specific type that `ReplayRunner` will skip (it is not in `KNOWN_EVENT_TYPES`), which is correct.

### silver_meta.json

Machine-readable reconstruction metadata:

```json
{
  "schema_version": "silver_tape_v0",
  "run_id": "<uuid>",
  "token_id": "0x...",
  "window_start": "2023-11-14T22:13:20+00:00",
  "window_end": "2023-11-15T00:13:20+00:00",
  "reconstruction_confidence": "high",
  "warnings": [],
  "event_count": 5,
  "fill_count": 2,
  "price_2min_count": 2,
  "source_inputs": {
    "pmxt_anchor_found": true,
    "pmxt_anchor_ts": "2023-11-14T22:00:00+00:00",
    "pmxt_columns_found": ["token_id", "snapshot_ts", "best_bid", "best_ask"],
    "jon_fill_count": 2,
    "jon_columns_found": ["asset_id", "timestamp", "price", "size", "side"],
    "price_2min_count": 2
  },
  "out_dir": "artifacts/silver/0xaaaaaa/2023-11-14T221320Z",
  "events_path": "artifacts/silver/0xaaaaaa/2023-11-14T221320Z/silver_events.jsonl",
  "meta_path": "artifacts/silver/0xaaaaaa/2023-11-14T221320Z/silver_meta.json",
  "error": null
}
```

---

## Confidence Model

Confidence is derived from which sources contributed data:

| Confidence | Condition |
|-----------|-----------|
| `high` | All three sources present (pmxt anchor + Jon fills + price_2min) |
| `medium` | pmxt anchor present + at least one of (Jon fills OR price_2min) |
| `low` | Exactly one source contributed data |
| `none` | No data from any source |

**Confidence is not a binary gate.** The operator decides what confidence level is acceptable for a given reconstruction purpose. Gate 2 sweep suitability requires operator judgment.

---

## Warning Contract

Warnings are emitted as strings in `silver_meta.json["warnings"]`. They never raise exceptions (degrade gracefully). Warning key prefixes:

| Prefix | Cause |
|--------|-------|
| `pmxt_anchor_missing` | No pmxt snapshot found at or before window_start for the token |
| `pmxt_root_not_configured` | `pmxt_root` was not set in config |
| `jon_fills_missing` | No Jon-Becker fills found in window for the token |
| `jon_root_not_configured` | `jon_root` was not set in config |
| `jon_timestamp_ambiguity` | Multiple fills with identical timestamps (bucketized source) |
| `price_2min_missing` | No price_2min rows found; run `fetch-price-2min` to populate |
| `price_2min_skipped` | `skip_price_2min=True` was set |

---

## Determinism Guarantee

Given the same input sources (same Parquet/CSV files, same ClickHouse rows), two calls to `SilverReconstructor.reconstruct()` with the same token ID and window will produce:
- The same event sequence (same event types, same fields, same ordering)
- The same `reconstruction_confidence`
- The same `warnings` list

`run_id` is unique per call (UUID). All other fields in `silver_meta.json` are deterministic.

---

## CLI

```bash
# Full reconstruction (all three sources):
python -m polytool reconstruct-silver \
    --token-id 0x... \
    --window-start "2024-01-01T00:00:00Z" \
    --window-end   "2024-01-01T02:00:00Z" \
    --pmxt-root    /data/raw/pmxt_archive \
    --jon-root     /data/raw/jon_becker

# Offline mode (skip ClickHouse):
python -m polytool reconstruct-silver \
    --token-id 0x... \
    --window-start 1700000000 \
    --window-end   1700007200 \
    --pmxt-root /data/raw/pmxt_archive \
    --jon-root  /data/raw/jon_becker \
    --skip-price-2min

# Dry run (no files written):
python -m polytool reconstruct-silver \
    --token-id 0x... \
    --window-start "2024-01-01T00:00:00Z" \
    --window-end   "2024-01-01T02:00:00Z" \
    --pmxt-root /data/raw/pmxt_archive \
    --dry-run
```

Default output directory: `artifacts/silver/<token_first8>/<window_start_iso>/`

---

## Known Limitations (v0)

1. **pmxt column schema is not guaranteed.** Column detection uses a heuristic candidate list. If the actual pmxt column names differ, the anchor query will fail gracefully with a warning. Log `pmxt_columns_found` in `source_inputs` to diagnose.

2. **Jon timestamp resolution.** Jon-Becker timestamps may be bucketized to the minute or second. Fill ordering within equal-timestamp buckets is deterministic (file order) but not clock-accurate. The `jon_timestamp_ambiguity` warning surfaces this condition.

3. **price_2min must be pre-populated.** Run `fetch-price-2min --token-id <ID>` before reconstruction if midpoint constraints are needed. price_2min rows from ClickHouse are NOT backfilled automatically.

4. **pmxt anchor is the nearest snapshot before window_start, not at window_start.** The actual book state at window_start may differ due to market activity between the anchor and the window. This is a known approximation, not a bug.

5. **No intra-window book state reconstruction.** The v0 reconstructor does not reconstruct intermediate book state between fills. It emits one anchor event (book snapshot) and then individual fill events. A future Gold-tier reconstructor could bridge these gaps from live WS recordings.

6. **Single market/token only.** No batch generation across multiple markets. For Gate 2, reconstruct each market individually.

---

## Files

| File | Purpose |
|------|---------|
| `packages/polymarket/silver_reconstructor.py` | Core module: `SilverReconstructor`, `ReconstructConfig`, result types |
| `tools/cli/reconstruct_silver.py` | CLI: `python -m polytool reconstruct-silver` |
| `tests/test_silver_reconstructor.py` | 58 offline tests (all sources, confidence model, warnings, output files, CLI) |
| `polytool/__main__.py` | `reconstruct-silver` command registered |
| `docs/specs/SPEC-silver-reconstructor-v0.md` | This document |
| `docs/dev_logs/2026-03-16_silver_reconstructor_foundation_v0.md` | Dev log |
