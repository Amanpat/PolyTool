"""Normalized event schema for SimTrader tape files.

All events written to events.jsonl carry this envelope:
  - parser_version  int   Schema version; increment when event shape changes
  - seq             int   Monotonic arrival counter (per event, not per WS frame)
  - ts_recv         float Unix timestamp (seconds) when the frame was received
  - event_type      str   One of the EVENT_TYPE_* constants below
  - ...             dict  All original fields from the WS message

The parser_version field lets future readers handle schema migrations.
"""

from __future__ import annotations

# Increment this whenever the shape of a normalized event changes.
PARSER_VERSION: int = 1

# Event types emitted by the Polymarket Market Channel.
EVENT_TYPE_BOOK = "book"
EVENT_TYPE_PRICE_CHANGE = "price_change"
EVENT_TYPE_LAST_TRADE_PRICE = "last_trade_price"
EVENT_TYPE_TICK_SIZE_CHANGE = "tick_size_change"

KNOWN_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EVENT_TYPE_BOOK,
        EVENT_TYPE_PRICE_CHANGE,
        EVENT_TYPE_LAST_TRADE_PRICE,
        EVENT_TYPE_TICK_SIZE_CHANGE,
    }
)
