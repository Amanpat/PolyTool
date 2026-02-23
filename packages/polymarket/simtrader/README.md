# SimTrader – Replay Core

Record Polymarket Market Channel WebSocket data to a local tape, then
deterministically replay it to reconstruct best bid/ask over time.

> **Full specification:** [`docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`](../../../docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md)
> — vision, architecture, realism constraints, strategy classes, and full phased roadmap.

---

## Quick start

### Record a tape

```bash
# Record for 60 seconds (Ctrl-C to stop early)
python -m polytool simtrader record \
  --asset-id <TOKEN_ID> \
  --duration 60

# Record two assets until Ctrl-C
python -m polytool simtrader record \
  --asset-id <TOKEN_ID_YES> \
  --asset-id <TOKEN_ID_NO>
```

Output lands in `artifacts/simtrader/tapes/<timestamp>_<asset_prefix>/`.

### Replay a tape

```bash
python -m polytool simtrader replay \
  --tape artifacts/simtrader/tapes/<tape_dir>/events.jsonl \
  --format jsonl        # or csv
```

Output lands in `artifacts/simtrader/runs/<run_id>/best_bid_ask.jsonl`.

---

## Tape format

Two files are written per recording session:

| File | Description |
|------|-------------|
| `raw_ws.jsonl` | Exact WS frame strings + `frame_seq` + `ts_recv`.  Future-proof archive. |
| `events.jsonl` | Normalized events.  One JSON object per line.  Includes `parser_version` and `seq`. |

### Normalized event envelope

```jsonc
{
  "parser_version": 1,   // incremented on schema changes
  "seq": 42,             // monotonic per-event arrival counter
  "ts_recv": 1708620000.123,
  "event_type": "book",  // see table below
  // ...all original WS fields...
}
```

### Event types

| `event_type` | Book effect | Description |
|---|---|---|
| `book` | Replaces entire state | Full L2 snapshot sent on subscribe |
| `price_change` | Updates levels | Delta updates to bid/ask levels |
| `last_trade_price` | None | Last traded price update |
| `tick_size_change` | None | Tick size change notification |

---

## Replay output

`best_bid_ask.jsonl` (or `.csv`) — one row per book-affecting event:

```jsonc
{"seq": 0, "ts_recv": 1708620000.1, "asset_id": "...", "event_type": "book",
 "best_bid": 0.55, "best_ask": 0.57}
{"seq": 1, "ts_recv": 1708620001.3, "asset_id": "...", "event_type": "price_change",
 "best_bid": 0.56, "best_ask": 0.57}
```

`meta.json` — run quality metadata:

```jsonc
{
  "run_quality": "ok",   // "ok" | "warnings"
  "total_events": 1234,
  "timeline_rows": 890,
  "warnings": []
}
```

---

## Requirements

Recording requires `websocket-client`:

```bash
pip install 'websocket-client>=1.6'
```

Replay has no extra dependencies beyond the standard library.

---

## Running tests

```bash
pytest -k simtrader -v
```
