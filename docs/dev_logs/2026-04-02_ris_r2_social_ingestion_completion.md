# Dev Log: RIS Social Ingestion v1 -- Reddit + YouTube

**Date:** 2026-04-02
**Branch:** feat/ws-clob-feed
**Quick task:** 260402-wj9
**Objective:** Complete RIS_02 practical v1 social ingestion scope

## Summary

Added Reddit and YouTube as first-class source families in the RIS ingestion
pipeline. Both have full adapter + fetcher + CLI + offline test coverage.
Twitter/X is explicitly marked deferred with documented reason.

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/fetchers.py` | Added `clean_transcript()`, `LiveRedditFetcher`, `LiveYouTubeFetcher`, updated FETCHER_REGISTRY |
| `packages/research/ingestion/adapters.py` | Added `RedditAdapter`, `YouTubeAdapter`, updated ADAPTER_REGISTRY |
| `packages/research/ingestion/__init__.py` | Exported new symbols |
| `tools/cli/research_acquire.py` | Extended `--source-family` choices to include reddit, youtube |
| `tests/fixtures/ris_external_sources/reddit_sample.json` | New fixture |
| `tests/fixtures/ris_external_sources/youtube_sample.json` | New fixture |
| `tests/test_ris_social_ingestion.py` | 30 new offline tests |
| `docs/features/FEATURE-ris-social-ingestion-v1.md` | New feature doc |
| `docs/dev_logs/2026-04-02_ris_r2_social_ingestion_completion.md` | This file |
| `docs/CURRENT_STATE.md` | New RIS Social Ingestion v1 section appended |

## What Was Implemented

### clean_transcript() (fetchers.py)

Pure function that strips VTT noise from YouTube transcripts:
- Removes VTT timestamp range lines (`HH:MM:SS.mmm --> HH:MM:SS.mmm`)
- Removes inline timestamps (`<HH:MM:SS.mmm>`)
- Removes the WEBVTT header line and align/position directives
- Removes sponsor boilerplate lines (sponsored by, like and subscribe, etc.)
- Deduplicates consecutive identical lines
- Collapses whitespace

Defined in `fetchers.py` so it is importable by tests without loading adapter deps.

### RedditAdapter (adapters.py)

Converts Reddit post raw_source dict to `ExtractedDocument`:
- Body assembled as: `{title}\n\n{body_text}\n\n--- Top Comments ---\n\n{comments}`
- Comment block omitted when `top_comments` is empty
- Metadata: subreddit, score, num_comments
- Registered as `ADAPTER_REGISTRY["reddit"]`

### YouTubeAdapter (adapters.py)

Converts YouTube video raw_source dict to `ExtractedDocument`:
- Body is `clean_transcript(transcript_text)` -- all VTT noise removed
- Author is the channel name
- Metadata: duration_seconds, view_count, channel
- Registered as `ADAPTER_REGISTRY["youtube"]`

### LiveRedditFetcher (fetchers.py)

Dual-mode fetcher:
- `fetch_raw(raw_post_dict)` -- offline mode, returns dict immediately
- `fetch(url)` -- live PRAW mode; raises `FetchError` if praw not installed or no praw_instance
- PRAW never imported at module level (no ImportError at startup)
- Registered as `FETCHER_REGISTRY["reddit"]`

### LiveYouTubeFetcher (fetchers.py)

Dual-mode fetcher:
- `fetch_raw(raw_dict)` -- offline mode, returns dict immediately
- `fetch(url)` -- live yt-dlp subprocess mode; raises `FetchError` if yt-dlp not found
- Duration filter: skip videos shorter than 180s or longer than 3600s
- Injectable `_subprocess_fn` for offline testing
- Registered as `FETCHER_REGISTRY["youtube"]`

### CLI (tools/cli/research_acquire.py)

Extended `--source-family` argument choices from
`["academic", "github", "blog", "news", "book"]` to
`["academic", "github", "blog", "news", "book", "reddit", "youtube"]`.

No restructuring of pipeline logic -- the existing 7-step pipeline works for
any registered family.

## What Was Explicitly Deferred

### Twitter/X

Twitter/X is **not implemented** and **will not be implemented** in RIS v1.

Reasons:
- Official Twitter API costs $100/month (not justified pre-profit)
- Free alternatives (snscrape, nitter RSS) are frequently broken by anti-scraping

Documented as DEFERRED in `docs/features/FEATURE-ris-social-ingestion-v1.md`.
No Twitter/X code exists in the repo. Do not infer support from roadmap mentions.

## Commands Run and Output

### TDD RED (before implementation):
```
python -m pytest tests/test_ris_social_ingestion.py -x -q --tb=short -m "not live"
1 failed -- ImportError: cannot import name 'clean_transcript' from fetchers
```

### TDD GREEN (after implementation):
```
python -m pytest tests/test_ris_social_ingestion.py -v --tb=short -m "not live"
30 passed in 0.48s
```

### Full regression suite:
```
python -m pytest tests/ -x -q --tb=short -m "not live"
3405 passed, 3 deselected, 25 warnings in 91.74s
```

### CLI verification:
```
python -m polytool research-acquire --source-family reddit --url https://reddit.com/r/polymarket/comments/x --dry-run --no-eval
Error: fetch failed: praw is required for live Reddit fetching -- install praw or use fetch_raw()
```
(Accepted by argparse; error is from live fetch path as expected)

```
python -m polytool research-acquire --source-family youtube --url https://www.youtube.com/watch?v=abc --dry-run --no-eval
Error: fetch failed: yt-dlp not found: [WinError 2] The system cannot find the file specified
```
(Accepted by argparse; error is from live fetch path as expected)

## Codex Review Summary

Skip -- docs, tests, config adapters (no mandatory review files touched)
