# RIS_02 — Social Ingestion Pipeline (Pipeline B)
**System:** PolyTool Research Intelligence System  
**Covers:** Reddit, Twitter/X, YouTube transcripts, blog RSS, GitHub READMEs

---

## Purpose

Pipeline B ingests community and practitioner knowledge: strategy discussions, market
commentary, bot analyses, and real-world trading experiences. These sources are noisier
than academic papers but often contain actionable insights that haven't been formalized
in published research (e.g., gabagool22's CoinsBench analysis).

---

## Sources

### Reddit (PRAW)

**API:** PRAW (Python Reddit API Wrapper). Requires a free Reddit "app" — 2 minutes to
create at `reddit.com/prefs/apps`. Creates `client_id` and `client_secret`.

**Rate limit:** 60 requests/minute (PRAW handles this automatically).

**Subreddits to monitor:**

| Subreddit | Schedule | What to Look For |
|-----------|----------|-----------------|
| r/polymarket | Every 6 hours | Strategy discussions, market anomalies, platform changes |
| r/algotrading | Daily | Algorithmic trading strategies, backtesting approaches |
| r/quantfinance | Daily | Quantitative methods, market microstructure |
| r/sportsbook | Daily | Sports modeling approaches (Phase 1C relevant) |
| r/sportsbetting | Weekly | Community strategies, model comparisons |
| r/options | Weekly | Market making concepts (transferable to binary markets) |

**Content extraction per post:**
- Post title + body text
- Top 5 comments by score (collapsed into one document with the post)
- Filter: skip posts with <5 upvotes (noise floor)
- Filter: skip posts that are pure memes/images with no text body

**Implementation sketch:**
```python
# packages/research/ingestion/reddit_ingest.py

import praw
from datetime import datetime, timedelta

def fetch_subreddit_posts(
    reddit: praw.Reddit,
    subreddit_name: str,
    days_back: int = 7,
    min_score: int = 5,
    max_posts: int = 50,
) -> list[dict]:
    """Fetch recent posts from a subreddit with top comments."""
    subreddit = reddit.subreddit(subreddit_name)
    cutoff = datetime.utcnow() - timedelta(days=days_back)
    posts = []
    
    for submission in subreddit.new(limit=max_posts * 3):  # overfetch, then filter
        post_time = datetime.utcfromtimestamp(submission.created_utc)
        if post_time < cutoff:
            break
        if submission.score < min_score:
            continue
        if not submission.selftext and not submission.title:
            continue
        
        # Get top comments
        submission.comment_sort = "best"
        submission.comments.replace_more(limit=0)
        top_comments = [
            c.body for c in submission.comments[:5]
            if hasattr(c, 'body') and len(c.body) > 20
        ]
        
        # Combine post + comments into one document
        full_text = f"Title: {submission.title}\n\n"
        full_text += f"{submission.selftext}\n\n"
        if top_comments:
            full_text += "--- Top Comments ---\n\n"
            full_text += "\n\n".join(top_comments)
        
        posts.append({
            "text": full_text,
            "title": submission.title,
            "source_type": "reddit",
            "source_url": f"https://reddit.com{submission.permalink}",
            "author": str(submission.author),
            "source_publish_date": post_time.isoformat(),
            "raw_metadata": {
                "subreddit": subreddit_name,
                "score": submission.score,
                "num_comments": submission.num_comments,
                "comment_count_included": len(top_comments),
            },
        })
    
    return posts[:max_posts]
```

### Twitter/X

**Challenge:** Official Twitter API is $100/month for basic access.

**Approach (ordered by preference):**

1. **Partner's existing scraper** — if the partner's news ingest project already handles
   Twitter collection, repurpose it. Swap stock ticker entity resolution for prediction
   market topic detection. This is the cheapest path if the code is available.

2. **`snscrape`** — free, no API key needed. Less reliable (Twitter frequently blocks
   scraping), but sufficient for research ingestion where missing some tweets is acceptable.

3. **Nitter RSS feeds** — Nitter instances provide RSS feeds for public accounts. Free,
   no API, but Nitter instances frequently go offline.

4. **Official API** — $100/month. Only justified post-profit. Not for v1.

**Accounts to monitor (curated list in `config/twitter_watchlist.json`):**
- Known Polymarket traders and analysts
- Quantitative trading commentators
- Market microstructure researchers
- Prediction market platform accounts

**Content:** Tweet text + thread context (if part of a thread, collect the full thread).
Media attachments (images, links) → extract linked article text if URL present.

**Schedule:** Every 6 hours.

### YouTube Transcripts

**Method:** `yt-dlp` for transcript extraction (free, no API key needed).

**Search queries:**
- `"polymarket strategy"`, `"polymarket analysis"`
- `"prediction market trading"`, `"prediction market bot"`
- `"sports betting model"`, `"sports prediction algorithm"`
- `"market making explained"`, `"algorithmic trading tutorial"`

**Content extraction:** Video title, channel name, upload date, auto-generated transcript.

**Filters:**
- Skip videos < 3 minutes (usually promotional/clickbait)
- Skip videos > 60 minutes (too broad — likely full lectures, better as manual ingestion)
- Skip channels with < 1,000 subscribers (quality floor)

**Transcript cleaning is critical.** See the Transcript Cleaner section below.

**Schedule:** Weekly (YouTube content is less time-sensitive than social media).

**Implementation sketch:**
```python
# packages/research/ingestion/youtube_ingest.py

import subprocess
import json
from pathlib import Path

def fetch_video_transcript(video_url: str) -> dict | None:
    """Extract transcript from a YouTube video using yt-dlp."""
    try:
        # Get metadata
        meta_result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", video_url],
            capture_output=True, text=True, timeout=30,
        )
        if meta_result.returncode != 0:
            return None
        
        meta = json.loads(meta_result.stdout)
        
        # Filter by length
        duration = meta.get("duration", 0)
        if duration < 180 or duration > 3600:
            return None
        
        # Get transcript
        transcript_result = subprocess.run(
            ["yt-dlp", "--write-auto-sub", "--sub-lang", "en",
             "--skip-download", "--sub-format", "vtt",
             "-o", "/tmp/yt_transcript", video_url],
            capture_output=True, text=True, timeout=60,
        )
        
        vtt_path = Path("/tmp/yt_transcript.en.vtt")
        if not vtt_path.exists():
            return None
        
        raw_transcript = vtt_path.read_text()
        cleaned = clean_transcript(raw_transcript)
        
        return {
            "text": cleaned,
            "title": meta.get("title", ""),
            "source_type": "youtube",
            "source_url": video_url,
            "author": meta.get("channel", ""),
            "source_publish_date": meta.get("upload_date", ""),
            "raw_metadata": {
                "channel": meta.get("channel", ""),
                "duration_seconds": duration,
                "view_count": meta.get("view_count", 0),
                "subscriber_count": meta.get("channel_follower_count", 0),
            },
        }
    except Exception:
        return None
```

### Blog/RSS Feeds

**Method:** `feedparser` for RSS + `requests` + `BeautifulSoup` for article text extraction.

**Sources (curated in `config/blog_feeds.json`):**

| Source | Feed Type | Content |
|--------|----------|---------|
| CoinsBench | Blog | Polymarket deep-dive analyses |
| Medium (tag: polymarket) | RSS | Community strategy posts |
| Medium (tag: prediction-markets) | RSS | Market analysis, platform comparisons |
| Substack newsletters (curated list) | RSS | Quantitative trading, market structure |
| Polymarket blog | RSS | Platform updates, market mechanics |

**Schedule:** Every 4 hours for RSS check. New articles → evaluate and ingest.

### GitHub READMEs

**Method:** GitHub API (60 req/hr unauthenticated, 5,000/hr with free personal token).

**Search queries:** `"polymarket bot"`, `"prediction market"`, `"market maker bot"`,
`"sports betting model"`.

**Content extraction:** README.md content, repo description, star count, last commit date.

**Star count informs credibility:** >100 stars → `PRACTITIONER`, <100 → `COMMUNITY`.

**Schedule:** Weekly (repos don't change frequently).

**One-time seed:** Ingest READMEs from all repos identified in the master roadmap v5.1
(lorine93s, dylanpersonguy, warproxxx, realfishsam, etc.).

---

## Transcript Cleaner

YouTube transcripts contain significant noise that degrades evaluation scores and
embedding quality. The cleaner strips common patterns before evaluation.

```python
# packages/research/extraction/transcript_cleaner.py

import re

# Patterns to strip from YouTube transcripts
SPONSOR_PATTERNS = [
    r"(?i)this video is sponsored by.*?(?=\n\n|\.\s[A-Z])",
    r"(?i)today'?s sponsor.*?(?=\n\n|\.\s[A-Z])",
    r"(?i)use code \w+ for \d+%? off.*?(?=\n\n|\.\s[A-Z])",
    r"(?i)thanks to \w+ for sponsoring.*?(?=\n\n|\.\s[A-Z])",
    r"(?i)check out the link in the description.*?(?=\n\n|\.\s[A-Z])",
]

CTA_PATTERNS = [
    r"(?i)like and subscribe.*?(?=\n|\.\s)",
    r"(?i)hit the bell icon.*?(?=\n|\.\s)",
    r"(?i)don'?t forget to subscribe.*?(?=\n|\.\s)",
    r"(?i)leave a comment below.*?(?=\n|\.\s)",
    r"(?i)check out my other video.*?(?=\n|\.\s)",
    r"(?i)follow me on (twitter|instagram|tiktok).*?(?=\n|\.\s)",
]

VTT_NOISE_PATTERNS = [
    r"\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}",  # timestamps
    r"<\d{2}:\d{2}:\d{2}\.\d{3}>",  # inline timestamps
    r"align:start position:\d+%",    # VTT positioning
    r"WEBVTT\n",                      # VTT header
]

def clean_transcript(raw_text: str) -> str:
    """Remove noise from YouTube auto-generated transcript."""
    text = raw_text
    
    # Strip VTT formatting
    for pattern in VTT_NOISE_PATTERNS:
        text = re.sub(pattern, "", text)
    
    # Remove duplicate lines (common in auto-captions)
    lines = text.split('\n')
    seen = set()
    deduped = []
    for line in lines:
        stripped = line.strip()
        if stripped and stripped not in seen:
            seen.add(stripped)
            deduped.append(stripped)
    text = ' '.join(deduped)
    
    # Strip sponsor segments
    for pattern in SPONSOR_PATTERNS:
        text = re.sub(pattern, "[sponsor segment removed]", text)
    
    # Strip calls to action
    for pattern in CTA_PATTERNS:
        text = re.sub(pattern, "", text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
```

**Important note on transcript cleaning:** This is an area that requires testing with real
transcripts to ensure good content isn't being cut. The patterns above are conservative —
they target common noise phrases but may miss creative sponsor integrations. The v1
approach is:
1. Clean with the above patterns
2. Log what was removed (for manual review)
3. Evaluate the cleaned text through the gate
4. If a video has >50% of its content removed, flag it for human review

---

## Content Normalizer

All Pipeline B sources produce the same standard document format as Pipeline A:

```python
# Standard document format
{
    "text": str,                 # Main content (cleaned)
    "title": str,                # Post title, video title, article title
    "source_type": str,          # "reddit" | "twitter" | "youtube" | "blog" | "github"
    "source_url": str,           # Permalink
    "author": str,               # Username, channel name
    "source_publish_date": str,  # ISO 8601
    "raw_metadata": dict,        # Source-specific (score, views, stars, etc.)
}
```

### Human Language Handling

Social sources use informal language: typos, slang, abbreviations, incomplete sentences.
The evaluation gate prompt explicitly accounts for this:

> "Evaluate substance, not grammar. Typos, informal language, casual phrasing, and
> non-standard English do not reduce the score. Focus on whether the content contains
> actionable information about prediction market strategies, market mechanics, or
> trading approaches."

This is implemented in the evaluation prompt (`config/research_eval_prompt.md`) and
applies equally to all social sources.

---

## CLI Commands

```bash
# Reddit ingestion
polytool research ingest-reddit --subreddits polymarket,algotrading --days 7
polytool research ingest-reddit --subreddits polymarket --days 1  # daily r/polymarket

# Twitter/X ingestion
polytool research ingest-twitter --days 7

# YouTube ingestion
polytool research ingest-youtube --query "polymarket strategy" --max-videos 20

# Blog/RSS ingestion
polytool research ingest-blogs

# GitHub ingestion
polytool research ingest-github --query "polymarket bot" --max-repos 20

# Run all social pipelines
polytool research ingest-social
```

---

## v1 vs v2 Features

| Feature | v1 | v2 |
|---------|----|----|
| Reddit | PRAW keyword scraping | Subreddit-specific quality models (e.g., r/polymarket gets different scoring than r/algotrading) |
| Twitter/X | snscrape or partner project | Official API (post-profit) or fine-tuned relevance model |
| YouTube | yt-dlp transcripts | SponsorBlock dataset integration for precise ad removal |
| Blog/RSS | feedparser + BeautifulSoup | Author reputation scoring (repeat high-quality authors get auto-elevated) |
| GitHub | README scraping | Code analysis (extract strategy logic from bot implementations, not just README text) |
| Partner project | Not yet integrated | Full integration: Discord + Reddit + Twitter from existing codebase |
| Noise handling | Regex-based transcript cleaning | LLM-based content segmentation (identify sponsor vs content sections) |

---

## Scheduling Summary

| Source | Schedule | Rationale |
|--------|----------|-----------|
| Reddit r/polymarket | Every 6 hours | Most time-sensitive social source |
| Reddit others | Daily | Lower urgency, higher volume |
| Twitter/X | Every 6 hours | Time-sensitive market commentary |
| YouTube | Weekly | Content not time-sensitive |
| Blog/RSS | Every 4 hours | New articles checked via RSS |
| GitHub | Weekly | Repos don't change frequently |

---

## Reference Projects (from Research Report 4)

- **Media Agent** — Scrapes Twitter (Tweepy) and Reddit (PRAW), embeds into ChromaDB.
  Good building block for social ingestion.
- **Reddit QA Analyzer** — Reddit threads (asyncpraw) → Chroma → RAG with Gemini.
  Clean Reddit→Chroma pattern.
- **reply_gAI** — Twitter user tweets → LangGraph memory store. Pattern for X→RAG.

---

*End of RIS_02 — Social Ingestion Pipeline*
