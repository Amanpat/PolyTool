# Report -> Watchlist Handoff (2026-03-07)

## Purpose

This note defines the smallest handoff contract for seeding selected
report/dossier markets into a dislocation watcher watchlist.

Scope is intentionally narrow:

- docs/spec only
- no report or dossier schema redesign
- no watcher redesign
- no token-ID requirement when the watcher resolves them internally

## Contract

One payload can seed one or more markets into a watchlist consumer.

### Minimum required field

| Field | Type | Why it is required |
|---|---|---|
| `market_slug` | string | Canonical market key. The watcher can resolve market metadata and token IDs from this slug internally. |

### Optional but helpful fields

| Field | Type | Why it helps |
|---|---|---|
| `reason` | string | Short explanation for why this market was surfaced for watch. |
| `priority` | integer | Ordering hint when multiple markets are seeded at once. Lower number means higher priority. |
| `provenance` | object | Traceback to the source artifact. Recommended keys: `source_type`, `source_path`, `source_id`. |
| `timestamp_utc` | string | When the market was surfaced or added to the watchlist. |
| `expiry_utc` | string | Optional freshness limit. After this time, the consumer should ignore the entry unless refreshed. |

## Interpretation Rules

- Each `watchlist[]` row is one market-level watch instruction.
- `market_slug` is the dedupe key.
- No token IDs are required in this contract.
- If the watcher needs YES/NO token IDs, it resolves them from `market_slug`.
- If `expiry_utc` is present and already in the past, the consumer should skip the row.

## Concrete JSON Example

`schema_version` is optional but recommended for future compatibility.

```json
{
  "schema_version": "report_to_watchlist_v1",
  "watchlist": [
    {
      "market_slug": "will-there-be-between-10-and-13-us-strikes-on-somalia-in-february-2026",
      "reason": "surfaced in report as a market to monitor for dislocation",
      "priority": 1,
      "provenance": {
        "source_type": "report",
        "source_path": "kb/users/drpufferfish/reports/2026-03-05/890dc539_report.md",
        "source_id": "890dc539"
      },
      "timestamp_utc": "2026-03-05T18:10:00Z",
      "expiry_utc": "2026-03-06T18:10:00Z"
    }
  ]
}
```

This is the full handoff:

- a market identifier
- an optional watch reason
- an optional ordering hint
- lightweight provenance
- a timestamp
- an optional expiry

That is enough for a report or dossier consumer to seed a watchlist for the
dislocation recorder without broadening into a larger automation design.
