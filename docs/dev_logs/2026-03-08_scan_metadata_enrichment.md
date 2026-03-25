# Dev Log: Scan Metadata Enrichment

**Date:** 2026-03-08
**Branch:** simtrader
**Author:** PolyTool Contributors

---

## What was built

Added an opt-in `--enrich` path for `scan-gate2-candidates` so live candidate
discovery can surface reward, volume, age, competition, and stronger
regime-context data when the repo can fetch it cheaply.

### Problem

The new Gate 2 ranking already supported reward, volume, competition, age, and
regime factors, but the default live scan only passed slug/question context into
scoring. That left too many live rows with `UNKNOWN` market-quality fields even
when the required data was fetchable at scan time.

### Solution

- Added `--enrich` to the CLI as an optional, live-only mode.
- Reused existing repo sources for enrichment:
  - `GammaClient.get_markets_by_slugs(...)` for market metadata
  - `market_selection.api_client.fetch_reward_config(...)` for reward configs
  - already-fetched live orderbooks for competition scoring
- Kept the path conservative:
  - only explicit 24h-volume fields populate `volume_24h`
  - missing/failing fetches stay non-fatal
  - affected factors remain `UNKNOWN`

---

## Files changed

| File | What changed |
|------|-------------|
| `tools/cli/scan_gate2_candidates.py` | Added `--enrich`, live metadata normalization, non-fatal enrichment helper, and opt-in combined live orderbooks for competition scoring |
| `tests/test_gate2_candidate_ranking.py` | Added enrichment success, enrichment failure, and honest-`UNKNOWN` tests |
| `docs/specs/SPEC-0017-phase1-gate2-candidate-ranking.md` | Synced CLI examples and fallback expectations for shipped `--enrich` behavior |
| `docs/features/FEATURE-scan-metadata-enrichment.md` | Feature note |
| `docs/dev_logs/2026-03-08_scan_metadata_enrichment.md` | This file |
| `docs/INDEX.md` | Added feature/dev-log index entries |

---

## Test results

```bash
pytest -q tests/test_gate2_candidate_ranking.py
pytest -q tests/test_market_selection.py
```

Result: 31 passed.
