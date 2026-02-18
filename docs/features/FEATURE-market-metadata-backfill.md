# Feature: Market Metadata Backfill

When PolyTool exports your position history, individual records sometimes
arrive without `market_slug`, `question`, or `outcome_name` — the three fields
that tell you which market a bet was placed on, what the question was, and
which outcome you backed.  This feature fills those gaps automatically using
information that is already available locally, before coverage statistics are
computed.  It never makes network calls and never guesses: if a mapping isn't
found, the field is left blank and counted as unmappable so you can see exactly
where the gaps are.

---

## How it works

1. **Map construction** — when `scan` loads your dossier positions, it indexes
   every record that already carries market metadata (any non-empty value in
   `market_slug`, `question`, or `outcome_name`) by its token ID or condition
   ID.

2. **Backfill** — each position that is missing metadata is looked up in this
   map.  If a match is found, the empty fields are filled.  Fields that already
   have a value are never overwritten.

3. **Coverage reporting** — after backfill, the coverage report gains a new
   `market_metadata_coverage` section that breaks down:
   - How many positions have market metadata (`present_count`)
   - How many are still missing it (`missing_count`)
   - Where the present data came from (`source_counts`: ingested vs backfilled)
   - The top token IDs that could not be mapped (`top_unmappable`)

4. **Warning** — if more than 20 % of positions are unmappable, a warning
   appears in both the JSON and Markdown reports.

---

## Coverage report additions

New top-level key in `coverage_reconciliation_report.json`:

```json
"market_metadata_coverage": {
    "present_count": 42,
    "missing_count": 8,
    "coverage_rate": 0.84,
    "source_counts": {
        "ingested": 30,
        "backfilled": 12,
        "unknown": 8
    },
    "top_unmappable": [
        {
            "token_id": "0xabc...",
            "count": 3,
            "example": { ... }
        }
    ]
}
```

New section in `coverage_reconciliation_report.md`:

```
## Market Metadata Coverage

- Coverage: 84.00% (42/50 positions have market metadata)
- Sources: ingested=30, backfilled=12, unknown=8
```

---

## Configuration

Backfill is enabled by default.  Use `--no-backfill` to disable it:

```powershell
python -m polytool scan --user "@example" --no-backfill
```

---

## Spec / ADR references

- [SPEC-0005 — Market Metadata Backfill](../specs/SPEC-0005-market-metadata-backfill.md)
- [ADR-0008 — Token-ID → Market Mapping for Local Backfill](../adr/0008-tokenid-market-mapping.md)
