# FEATURE: RIS Social Ingestion Pipeline -- v1

**Status:** Partial -- v1 shipped 2026-04-02 (quick-260402-wj9)
**Branch:** feat/ws-clob-feed

## Overview

RIS_02 defines five social/practitioner source families. This doc records
what is implemented at v1, what is deferred, and why.

## Coverage Table

| Source Family | v1 Status | Adapter         | Fetcher            | CLI                        | Notes                                                                   |
|---------------|-----------|-----------------|--------------------|-----------------------------|-------------------------------------------------------------------------|
| blog/news     | SHIPPED   | BlogNewsAdapter | LiveBlogFetcher    | --source-family blog/news  | Shipped in quick-260402-rm1                                             |
| github        | SHIPPED   | GithubAdapter   | LiveGitHubFetcher  | --source-family github     | Shipped in quick-260402-rm1                                             |
| reddit        | SHIPPED   | RedditAdapter   | LiveRedditFetcher  | --source-family reddit     | Live path requires PRAW (opt-in); offline via fetch_raw()               |
| youtube       | SHIPPED   | YouTubeAdapter  | LiveYouTubeFetcher | --source-family youtube    | Live path requires yt-dlp (opt-in); offline via fetch_raw()             |
| twitter/x     | DEFERRED  | --              | --                 | --                         | See deferred note below                                                 |

## Twitter/X -- DEFERRED

Twitter/X is **not implemented** in RIS v1. The official API costs $100/month
(not justified pre-profit). Free alternatives (snscrape, nitter RSS) are
unreliable and frequently broken by Twitter's anti-scraping measures. This
source family is deferred to RIS v2, contingent on either:

- a partner project with existing Twitter collection, or
- post-profit budget for the official API.

**No Twitter/X-related code exists in this repo.** Do not infer support from
docs that mention it as a future target.

## Reddit -- Live Path Setup

Live Reddit fetching requires a free Reddit "script" app:

1. Visit reddit.com/prefs/apps
2. Create a new "script" app -- note client_id and client_secret
3. Set env vars: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
4. Install praw: `pip install praw`
5. Construct a praw.Reddit instance and pass as `praw_instance` to `LiveRedditFetcher()`

Use `fetch_raw()` with a pre-built dict for offline/fixture-backed testing.

## YouTube -- Live Path Setup

Live YouTube fetching requires yt-dlp:

1. Install yt-dlp: `pip install yt-dlp` (or `brew install yt-dlp`)
2. No API key needed -- yt-dlp uses public YouTube data

Use `fetch_raw()` with a pre-built dict for offline/fixture-backed testing.

Duration filter: videos shorter than 180s or longer than 3600s are skipped
with a `FetchError`.

## clean_transcript()

`clean_transcript(text: str) -> str` is a pure function in
`packages/research/ingestion/fetchers.py`. It strips:

- VTT timestamp range lines (`HH:MM:SS.mmm --> HH:MM:SS.mmm`)
- Inline timestamps (`<HH:MM:SS.mmm>`)
- The `WEBVTT` header line
- Align/position directive lines
- Sponsor boilerplate lines ("sponsored by", "like and subscribe", etc.)
- Consecutive duplicate lines
- Extra whitespace

It can be imported directly without loading adapter dependencies.

## CLI Usage

```bash
# Reddit fixture-backed dry run (no PRAW needed)
python -m polytool research-acquire \
  --url https://reddit.com/r/polymarket/comments/abc123/post \
  --source-family reddit \
  --dry-run --no-eval --json

# YouTube fixture-backed dry run (no yt-dlp needed in dry-run)
python -m polytool research-acquire \
  --url https://www.youtube.com/watch?v=VIDEO_ID \
  --source-family youtube \
  --dry-run --no-eval --json
```

Note: `--dry-run` exits after fetch+normalize only. For Reddit and YouTube,
the live fetch path requires PRAW / yt-dlp respectively. Use `fetch_raw()`
in code for offline-first workflows.

## Tests

All tests are offline and fixture-based. Located in:

- `tests/test_ris_social_ingestion.py` -- Reddit + YouTube adapters, fetchers, clean_transcript (30 tests)
- `tests/fixtures/ris_external_sources/reddit_sample.json`
- `tests/fixtures/ris_external_sources/youtube_sample.json`

Run targeted tests:

```bash
python -m pytest tests/test_ris_social_ingestion.py -v --tb=short -m "not live"
```
