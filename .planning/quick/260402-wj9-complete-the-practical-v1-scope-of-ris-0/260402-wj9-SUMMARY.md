---
phase: quick-260402-wj9
plan: 01
subsystem: research-ingestion
tags: [ris, social-ingestion, reddit, youtube, adapters, fetchers, clean_transcript, vtt]

requires: []
provides:
  - RedditAdapter with top_comments body assembly and metadata (subreddit, score, num_comments)
  - YouTubeAdapter with clean_transcript body and metadata (duration_seconds, view_count, channel)
  - clean_transcript() pure function for VTT noise stripping and sponsor boilerplate removal
  - LiveRedditFetcher with fetch_raw() offline mode and PRAW-optional live path
  - LiveYouTubeFetcher with fetch_raw() offline mode and yt-dlp-optional live path
  - ADAPTER_REGISTRY["reddit"] and ADAPTER_REGISTRY["youtube"]
  - FETCHER_REGISTRY["reddit"] and FETCHER_REGISTRY["youtube"]
  - research-acquire CLI --source-family reddit/youtube choices
  - 30 offline fixture-backed tests in test_ris_social_ingestion.py
  - Twitter/X explicitly documented as DEFERRED with reason
affects: [ris-ingestion, research-acquire-cli, ris-social-sources]

tech-stack:
  added: []
  patterns:
    - fetch_raw() offline mode pattern for fetchers without live network dependencies
    - clean_transcript() as pure function in fetchers.py (importable without adapter deps)
    - Injectable _subprocess_fn on LiveYouTubeFetcher for deterministic testing

key-files:
  created:
    - packages/research/ingestion/fetchers.py (extended with clean_transcript, LiveRedditFetcher, LiveYouTubeFetcher)
    - tests/fixtures/ris_external_sources/reddit_sample.json
    - tests/fixtures/ris_external_sources/youtube_sample.json
    - tests/test_ris_social_ingestion.py
    - docs/features/FEATURE-ris-social-ingestion-v1.md
    - docs/dev_logs/2026-04-02_ris_r2_social_ingestion_completion.md
  modified:
    - packages/research/ingestion/adapters.py (added RedditAdapter, YouTubeAdapter)
    - packages/research/ingestion/__init__.py (new exports)
    - tools/cli/research_acquire.py (extended --source-family choices)
    - docs/CURRENT_STATE.md (appended RIS Social Ingestion v1 section)

key-decisions:
  - "clean_transcript() lives in fetchers.py (not adapters.py) so it is importable without loading adapter dependencies"
  - "PRAW and yt-dlp are never imported at module level -- only inside live fetch() behind try/except ImportError"
  - "fetch_raw() method on both fetchers provides the offline/fixture-backed path for tests and CI"
  - "Twitter/X deferred to RIS v2 -- $100/month API not justified pre-profit; free scraping alternatives unreliable"
  - "Duration filter on LiveYouTubeFetcher: skip videos < 180s or > 3600s (too short/long for signal value)"

patterns-established:
  - "fetch_raw(raw_dict) -> offline mode returning dict immediately; fetch(url) -> live mode with optional dep"
  - "Sponsor boilerplate detection via regex patterns in _SPONSOR_PATTERNS list (extensible)"

requirements-completed: [RIS-02]

duration: 30min
completed: 2026-04-02
---

# Quick Task 260402-wj9: RIS Social Ingestion v1 Summary

**Reddit and YouTube adapters, fetchers, and clean_transcript() added to RIS ingestion pipeline with 30 offline tests and Twitter/X explicitly deferred**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-04-02T00:00:00Z
- **Completed:** 2026-04-02T00:30:00Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments

- Added `RedditAdapter` and `YouTubeAdapter` to `ADAPTER_REGISTRY` with full ExtractedDocument production
- Added `clean_transcript()` pure function that strips VTT timestamps, inline timestamps, sponsor boilerplate, and deduplicates consecutive lines
- Added `LiveRedditFetcher` and `LiveYouTubeFetcher` with injectable offline mode (`fetch_raw()`) and optional-dep live paths
- Extended `research-acquire` CLI `--source-family` choices to include reddit and youtube
- 30 offline fixture-backed tests passing in `test_ris_social_ingestion.py`
- Full regression suite: 3405 passed, 0 failed, 3 deselected
- Twitter/X documented as DEFERRED in `FEATURE-ris-social-ingestion-v1.md` with explicit reason

## Task Commits

1. **Task 1: Add RedditAdapter + YouTubeAdapter with clean_transcript and fetchers** - `71bdfb4` (feat)
2. **Task 2: Wire CLI, mark Twitter/X deferred, write feature doc and dev log** - `a332abf` (feat)

## Files Created/Modified

- `packages/research/ingestion/fetchers.py` - Added clean_transcript(), LiveRedditFetcher, LiveYouTubeFetcher, updated FETCHER_REGISTRY
- `packages/research/ingestion/adapters.py` - Added RedditAdapter, YouTubeAdapter, updated ADAPTER_REGISTRY
- `packages/research/ingestion/__init__.py` - Exported new symbols
- `tools/cli/research_acquire.py` - Extended --source-family choices to include reddit, youtube
- `tests/fixtures/ris_external_sources/reddit_sample.json` - Created
- `tests/fixtures/ris_external_sources/youtube_sample.json` - Created
- `tests/test_ris_social_ingestion.py` - 30 offline tests (TestCleanTranscript x8, TestRedditAdapter x6, TestYouTubeAdapter x4, TestLiveRedditFetcher x3, TestLiveYouTubeFetcher x3, TestRegistries x6)
- `docs/features/FEATURE-ris-social-ingestion-v1.md` - Coverage table, Twitter/X DEFERRED note, setup instructions
- `docs/dev_logs/2026-04-02_ris_r2_social_ingestion_completion.md` - Dev log
- `docs/CURRENT_STATE.md` - Appended RIS Social Ingestion v1 section

## Decisions Made

1. `clean_transcript()` placed in `fetchers.py` (not `adapters.py`) so it can be imported by tests without loading adapter dependencies.
2. PRAW and yt-dlp are never imported at module level -- both fetchers use `try/except ImportError` inside `fetch()`, ensuring clean import at startup even without optional deps installed.
3. `fetch_raw()` method on both fetchers provides an offline/fixture path that returns the input dict unchanged -- no network, no subprocess, no dep requirements.
4. Twitter/X deferred: $100/month official API is not justified pre-profit; snscrape/nitter RSS are unreliable. No Twitter/X code added.
5. Duration filter on `LiveYouTubeFetcher`: skip videos < 180s or > 3600s with `FetchError` to filter out short clips and very long streams.

## Deviations from Plan

None -- plan executed exactly as written.

The `research_acquire.py` file had been extended by another agent (added `--search`, `--extract-claims`, and `--max-results` flags) but the `--source-family` choices were not yet updated. Extending the choices to include reddit/youtube was the only required change, applied atomically without restructuring the pipeline logic.

## Issues Encountered

None.

## Known Stubs

None. Both adapters produce fully wired ExtractedDocuments from fixture data. The live fetch paths (PRAW and yt-dlp) are documented as optional with clear offline alternatives.

## Next Steps

- RIS v2: Twitter/X (contingent on partner data or post-profit API budget)
- Live Reddit path: set up PRAW credentials (see FEATURE-ris-social-ingestion-v1.md)
- Live YouTube path: install yt-dlp (see FEATURE-ris-social-ingestion-v1.md)

---
*Phase: quick-260402-wj9*
*Completed: 2026-04-02*

## Self-Check: PASSED

- FOUND: tests/fixtures/ris_external_sources/reddit_sample.json
- FOUND: tests/fixtures/ris_external_sources/youtube_sample.json
- FOUND: tests/test_ris_social_ingestion.py
- FOUND: docs/features/FEATURE-ris-social-ingestion-v1.md
- FOUND: docs/dev_logs/2026-04-02_ris_r2_social_ingestion_completion.md
- FOUND: .planning/quick/260402-wj9-complete-the-practical-v1-scope-of-ris-0/260402-wj9-SUMMARY.md
- FOUND commit 71bdfb4: feat(quick-260402-wj9-01) add RedditAdapter + YouTubeAdapter with clean_transcript and fetchers
- FOUND commit a332abf: feat(quick-260402-wj9-02) wire CLI, add feature doc, dev log, update CURRENT_STATE
