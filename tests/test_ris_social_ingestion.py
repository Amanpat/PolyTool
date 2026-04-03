"""RIS Social Ingestion — offline tests for Reddit and YouTube adapters, fetchers,
and clean_transcript.

All tests are deterministic and offline.  No PRAW, no yt-dlp, no network calls.
Mark a test with @pytest.mark.live if it requires real network access (none here).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "ris_external_sources"
REDDIT_FIXTURE = FIXTURES_DIR / "reddit_sample.json"
YOUTUBE_FIXTURE = FIXTURES_DIR / "youtube_sample.json"


def _load_fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# TestCleanTranscript
# ===========================================================================


class TestCleanTranscript:
    def test_strips_vtt_timestamps(self):
        from packages.research.ingestion.fetchers import clean_transcript

        text = "00:00:01.000 --> 00:00:03.000\nHello world."
        result = clean_transcript(text)
        assert "-->" not in result
        assert "Hello world." in result

    def test_strips_inline_timestamps(self):
        from packages.research.ingestion.fetchers import clean_transcript

        text = "<00:00:05.000>Hello there."
        result = clean_transcript(text)
        assert "<0" not in result
        assert "Hello there." in result

    def test_deduplicates_consecutive_lines(self):
        from packages.research.ingestion.fetchers import clean_transcript

        text = "Today we cover market making.\nToday we cover market making.\nSomething else."
        result = clean_transcript(text)
        # Should appear only once, not twice
        assert result.count("Today we cover market making.") == 1
        assert "Something else." in result

    def test_strips_like_and_subscribe(self):
        from packages.research.ingestion.fetchers import clean_transcript

        text = "Great content here.\nLike and subscribe for more content.\nEnd."
        result = clean_transcript(text)
        assert "like and subscribe" not in result.lower()

    def test_strips_sponsor_segment(self):
        from packages.research.ingestion.fetchers import clean_transcript

        text = "This video is sponsored by VPN service provider check the link in description.\nReal content here."
        result = clean_transcript(text)
        assert "sponsored by" not in result.lower()
        assert "Real content here." in result

    def test_collapses_whitespace(self):
        from packages.research.ingestion.fetchers import clean_transcript

        text = "Hello   world.  This  has  extra   spaces."
        result = clean_transcript(text)
        assert "  " not in result

    def test_empty_input(self):
        from packages.research.ingestion.fetchers import clean_transcript

        result = clean_transcript("")
        assert result == ""

    def test_pure_content_preserved(self):
        from packages.research.ingestion.fetchers import clean_transcript

        sentence = "The key insight is that binary markets compress spreads near resolution."
        result = clean_transcript(sentence)
        assert "binary markets compress spreads" in result


# ===========================================================================
# TestRedditAdapter
# ===========================================================================


class TestRedditAdapter:
    def test_adapt_basic(self):
        from packages.research.ingestion.adapters import RedditAdapter

        fixture = _load_fixture(REDDIT_FIXTURE)
        adapter = RedditAdapter()
        doc = adapter.adapt(fixture)
        assert doc.source_family == "reddit"
        assert "How are you playing the election markets?" in doc.body
        assert "spreads on the 2026 midterm markets" in doc.body

    def test_adapt_includes_top_comments(self):
        from packages.research.ingestion.adapters import RedditAdapter

        fixture = _load_fixture(REDDIT_FIXTURE)
        adapter = RedditAdapter()
        doc = adapter.adapt(fixture)
        assert "Top Comments" in doc.body
        assert "binary resolution markets" in doc.body

    def test_adapt_no_comments(self):
        from packages.research.ingestion.adapters import RedditAdapter

        raw = {
            "url": "https://reddit.com/r/test/comments/xyz/post",
            "title": "A post with no comments",
            "body_text": "Post body here.",
            "author": "user1",
            "published_date": "2026-03-01",
            "subreddit": "test",
            "score": 5,
            "num_comments": 0,
            "top_comments": [],
        }
        adapter = RedditAdapter()
        doc = adapter.adapt(raw)
        assert "Top Comments" not in doc.body

    def test_adapt_caches_raw(self, tmp_path):
        from packages.research.ingestion.adapters import RedditAdapter
        from packages.research.ingestion.source_cache import RawSourceCache

        fixture = _load_fixture(REDDIT_FIXTURE)
        cache = RawSourceCache(tmp_path / "cache")
        adapter = RedditAdapter()
        adapter.adapt(fixture, cache=cache)

        from packages.research.ingestion.source_cache import make_source_id
        source_id = make_source_id(fixture["url"])
        assert cache.has_raw(source_id, "reddit")

    def test_adapt_metadata_fields(self):
        from packages.research.ingestion.adapters import RedditAdapter

        fixture = _load_fixture(REDDIT_FIXTURE)
        adapter = RedditAdapter()
        doc = adapter.adapt(fixture)
        assert doc.metadata["subreddit"] == "polymarket"
        assert doc.metadata["score"] == 47
        assert doc.metadata["num_comments"] == 12

    def test_source_url_preserved(self):
        from packages.research.ingestion.adapters import RedditAdapter

        fixture = _load_fixture(REDDIT_FIXTURE)
        adapter = RedditAdapter()
        doc = adapter.adapt(fixture)
        assert doc.source_url == fixture["url"]


# ===========================================================================
# TestYouTubeAdapter
# ===========================================================================


class TestYouTubeAdapter:
    def test_adapt_basic(self):
        from packages.research.ingestion.adapters import YouTubeAdapter

        fixture = _load_fixture(YOUTUBE_FIXTURE)
        adapter = YouTubeAdapter()
        doc = adapter.adapt(fixture)
        assert doc.source_family == "youtube"
        assert doc.author == "AlgoTradingPro"

    def test_adapt_body_is_cleaned(self):
        from packages.research.ingestion.adapters import YouTubeAdapter

        fixture = _load_fixture(YOUTUBE_FIXTURE)
        adapter = YouTubeAdapter()
        doc = adapter.adapt(fixture)
        # clean_transcript should have removed VTT markers and WEBVTT header
        assert "WEBVTT" not in doc.body
        assert "-->" not in doc.body

    def test_adapt_metadata_fields(self):
        from packages.research.ingestion.adapters import YouTubeAdapter

        fixture = _load_fixture(YOUTUBE_FIXTURE)
        adapter = YouTubeAdapter()
        doc = adapter.adapt(fixture)
        assert doc.metadata["duration_seconds"] == 420
        assert doc.metadata["view_count"] == 15200
        assert doc.metadata["channel"] == "AlgoTradingPro"

    def test_adapt_publish_date(self):
        from packages.research.ingestion.adapters import YouTubeAdapter

        fixture = _load_fixture(YOUTUBE_FIXTURE)
        adapter = YouTubeAdapter()
        doc = adapter.adapt(fixture)
        assert doc.publish_date == "2026-02-20"


# ===========================================================================
# TestLiveRedditFetcher
# ===========================================================================


class TestLiveRedditFetcher:
    def test_fetch_raw_returns_immediately(self):
        from packages.research.ingestion.fetchers import LiveRedditFetcher

        raw = {"url": "https://reddit.com/r/test/comments/abc/post", "title": "Test"}
        fetcher = LiveRedditFetcher()
        result = fetcher.fetch_raw(raw)
        assert result is raw

    def test_fetch_without_praw_raises_fetcherror(self):
        from packages.research.ingestion.fetchers import FetchError, LiveRedditFetcher

        fetcher = LiveRedditFetcher()
        with pytest.raises(FetchError):
            fetcher.fetch("https://reddit.com/r/polymarket/comments/abc/post")

    def test_fetch_raw_fixture_round_trip(self):
        from packages.research.ingestion.adapters import RedditAdapter
        from packages.research.ingestion.fetchers import LiveRedditFetcher

        fixture = _load_fixture(REDDIT_FIXTURE)
        fetcher = LiveRedditFetcher()
        raw = fetcher.fetch_raw(fixture)
        adapter = RedditAdapter()
        doc = adapter.adapt(raw)
        assert doc.source_family == "reddit"
        assert doc.title == fixture["title"]


# ===========================================================================
# TestLiveYouTubeFetcher
# ===========================================================================


class TestLiveYouTubeFetcher:
    def test_fetch_raw_returns_immediately(self):
        from packages.research.ingestion.fetchers import LiveYouTubeFetcher

        raw = {"url": "https://www.youtube.com/watch?v=abc", "title": "Test Video"}
        fetcher = LiveYouTubeFetcher()
        result = fetcher.fetch_raw(raw)
        assert result is raw

    def test_fetch_without_ytdlp_raises_fetcherror(self):
        from packages.research.ingestion.fetchers import FetchError, LiveYouTubeFetcher

        def failing_subprocess(*args, **kwargs):
            # Simulate yt-dlp returning nonzero
            raise OSError("yt-dlp not found")

        fetcher = LiveYouTubeFetcher(_subprocess_fn=failing_subprocess)
        with pytest.raises(FetchError):
            fetcher.fetch("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    def test_fetch_raw_fixture_round_trip(self):
        from packages.research.ingestion.adapters import YouTubeAdapter
        from packages.research.ingestion.fetchers import LiveYouTubeFetcher

        fixture = _load_fixture(YOUTUBE_FIXTURE)
        fetcher = LiveYouTubeFetcher()
        raw = fetcher.fetch_raw(fixture)
        adapter = YouTubeAdapter()
        doc = adapter.adapt(raw)
        assert doc.source_family == "youtube"
        assert doc.title == fixture["title"]


# ===========================================================================
# TestRegistries
# ===========================================================================


class TestRegistries:
    def test_adapter_registry_has_reddit(self):
        from packages.research.ingestion.adapters import ADAPTER_REGISTRY, RedditAdapter

        assert ADAPTER_REGISTRY["reddit"] is RedditAdapter

    def test_adapter_registry_has_youtube(self):
        from packages.research.ingestion.adapters import ADAPTER_REGISTRY, YouTubeAdapter

        assert ADAPTER_REGISTRY["youtube"] is YouTubeAdapter

    def test_fetcher_registry_has_reddit(self):
        from packages.research.ingestion.fetchers import FETCHER_REGISTRY, LiveRedditFetcher

        assert FETCHER_REGISTRY["reddit"] is LiveRedditFetcher

    def test_fetcher_registry_has_youtube(self):
        from packages.research.ingestion.fetchers import FETCHER_REGISTRY, LiveYouTubeFetcher

        assert FETCHER_REGISTRY["youtube"] is LiveYouTubeFetcher

    def test_get_adapter_reddit(self):
        from packages.research.ingestion.adapters import RedditAdapter, get_adapter

        adapter = get_adapter("reddit")
        assert isinstance(adapter, RedditAdapter)

    def test_get_adapter_youtube(self):
        from packages.research.ingestion.adapters import YouTubeAdapter, get_adapter

        adapter = get_adapter("youtube")
        assert isinstance(adapter, YouTubeAdapter)
