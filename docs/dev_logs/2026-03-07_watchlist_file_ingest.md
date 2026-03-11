# Watchlist File Ingest for `watch-arb-candidates` (2026-03-07)

## Summary

Added a small input-layer convenience to `watch-arb-candidates` so a
report-derived watchlist JSON can seed the watcher directly via
`--watchlist-file`.

Scope stayed intentionally narrow:

- no strategy logic changes
- no threshold changes
- no token-ID requirement added to the input file
- no report schema redesign
- no automation pipeline added

The watcher still resolves YES/NO token IDs internally from `market_slug`.

## Files Changed

- `tools/cli/watch_arb_candidates.py`
- `tests/test_watch_arb_candidates.py`
- `docs/dev_logs/2026-03-07_watchlist_file_ingest.md`

## CLI Option Added

New option:

```text
--watchlist-file PATH
```

This can be used:

- by itself
- together with `--markets`

If both are supplied:

- slugs from both inputs are combined
- duplicate `market_slug` values are deduped
- first-seen slug order is preserved
- watchlist metadata is kept for logging only

## Sample Usage

Watch only from a report-derived watchlist:

```bash
python -m polytool watch-arb-candidates \
  --watchlist-file artifacts/watchlists/report_watchlist.json
```

Combine direct CLI slugs with a watchlist file:

```bash
python -m polytool watch-arb-candidates \
  --markets slug-a,slug-b \
  --watchlist-file artifacts/watchlists/report_watchlist.json \
  --dry-run
```

## Final Supported Input Contract

Expected file shape:

```json
{
  "schema_version": "report_to_watchlist_v1",
  "watchlist": [
    {
      "market_slug": "example-market-slug",
      "reason": "optional short explanation",
      "priority": 1,
      "provenance": {
        "source_type": "report",
        "source_path": "path/to/source.md",
        "source_id": "abc123"
      },
      "timestamp_utc": "2026-03-07T12:00:00Z",
      "expiry_utc": "2026-03-07T18:00:00Z"
    }
  ]
}
```

Rules implemented:

- top-level JSON object must contain a `watchlist` array
- each `watchlist[]` item must be an object
- each item must include a non-empty `market_slug`
- token IDs are not required
- optional metadata fields are accepted and preserved for logging only
- if `expiry_utc` is present and is already in the past, that entry is skipped
- repeated `market_slug` values are deduped
- the watcher resolves market/token details internally from `market_slug`

## Tests Run

```bash
pytest -q tests/test_watch_arb_candidates.py
python -m polytool watch-arb-candidates --help
```

Focused coverage added for:

- valid watchlist-file ingest
- missing `market_slug` rejection
- duplicate slug dedupe
- expired entry skipping
- coexistence with direct `--markets`
