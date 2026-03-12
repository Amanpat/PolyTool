#!/usr/bin/env python3
"""Cache trusted web sources for RAG indexing.

This command downloads and caches content from allowlisted URLs
so that rag-index can ingest them for retrieval.

Usage:
    polytool cache-source --url https://docs.polymarket.com/...
    polytool cache-source --url https://arxiv.org/abs/... --ttl-days 30
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None  # type: ignore

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

# Default allowlist (MVP)
DEFAULT_ALLOWLIST = [
    "docs.polymarket.com",
    "learn.polymarket.com",
    "github.com/Polymarket/",
    "docs.alchemy.com",
    "thegraph.com/docs",
    "dune.com/docs",
    "mlfinlab.readthedocs.io",
    "vectorbt.dev/docs",
    "arxiv.org",
    "papers.ssrn.com",
    "nber.org/papers",
    "the-odds-api.com/docs",
    "developer.sportradar.com/docs",
]

DEFAULT_TTL_DAYS = 14
DEFAULT_OUTPUT_DIR = "kb/sources"


def _utcnow() -> datetime:
    return datetime.utcnow()


def _format_utc(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def _content_hash(content: str) -> str:
    """Generate SHA256 hash of content for deduplication."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _url_to_filename(url: str) -> str:
    """Convert URL to safe filename."""
    parsed = urlparse(url)
    # Combine host and path, replace unsafe chars
    safe_name = f"{parsed.netloc}{parsed.path}"
    safe_name = re.sub(r"[^\w\-.]", "_", safe_name)
    safe_name = re.sub(r"_+", "_", safe_name)
    safe_name = safe_name.strip("_")[:100]  # Limit length
    return safe_name or "cached_source"


def _is_url_allowed(url: str, allowlist: List[str]) -> bool:
    """Check if URL matches any pattern in allowlist."""
    parsed = urlparse(url)
    full_url = f"{parsed.netloc}{parsed.path}"

    for pattern in allowlist:
        # Pattern can be domain or domain/path prefix
        if pattern.endswith("/"):
            # Prefix match
            if full_url.startswith(pattern) or parsed.netloc.endswith(pattern.rstrip("/")):
                return True
        else:
            # Domain match
            if parsed.netloc == pattern or parsed.netloc.endswith("." + pattern):
                return True
            # Partial path match
            if full_url.startswith(pattern):
                return True
    return False


def _check_robots_txt(url: str, timeout: float = 10.0) -> bool:
    """Check robots.txt to see if URL is allowed for fetching.

    Returns True if allowed, False if disallowed.
    """
    if requests is None:
        return True  # Skip check if requests not available

    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        response = requests.get(robots_url, timeout=timeout)
        if response.status_code != 200:
            return True  # No robots.txt = allowed

        # Simple robots.txt parsing
        # Look for Disallow rules for our path
        path = parsed.path or "/"
        lines = response.text.split("\n")

        in_user_agent_section = False
        for line in lines:
            line = line.strip().lower()
            if line.startswith("user-agent:"):
                agent = line.split(":", 1)[1].strip()
                in_user_agent_section = agent == "*" or "polytool" in agent
            elif in_user_agent_section and line.startswith("disallow:"):
                disallow_path = line.split(":", 1)[1].strip()
                if disallow_path and path.startswith(disallow_path):
                    return False
        return True
    except Exception:
        return True  # On error, assume allowed


def _fetch_url(url: str, timeout: float = 30.0) -> Optional[str]:
    """Fetch URL content."""
    if requests is None:
        print("Error: requests library not available.", file=sys.stderr)
        return None

    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={
                "User-Agent": "PolyTool/0.1 (local research tool)",
                "Accept": "text/html,text/plain,application/json",
            },
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        return None


def _html_to_markdown(html: str) -> str:
    """Convert HTML to markdown (basic conversion)."""
    # Try using html2text if available
    try:
        import html2text
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        return h.handle(html)
    except ImportError:
        pass

    # Fallback: basic tag stripping
    import re
    # Remove script and style
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Convert headers
    text = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", text, flags=re.IGNORECASE)
    # Convert paragraphs and breaks
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "", text, flags=re.IGNORECASE)
    # Remove remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _load_config(config_path: Optional[str]) -> Dict[str, Any]:
    """Load config from polytool.yaml."""
    config: Dict[str, Any] = {}

    # Try default location
    paths_to_try = []
    if config_path:
        paths_to_try.append(Path(config_path))
    paths_to_try.append(Path("polytool.yaml"))
    paths_to_try.append(Path("polytool.yml"))

    for path in paths_to_try:
        if path.exists():
            try:
                if yaml:
                    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                else:
                    # Try JSON fallback
                    config = json.loads(path.read_text(encoding="utf-8"))
                break
            except Exception:
                continue

    return config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cache a trusted web source for RAG indexing.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL to fetch and cache",
    )
    parser.add_argument(
        "--ttl-days",
        type=int,
        help=f"Time-to-live in days (default: {DEFAULT_TTL_DAYS})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch even if cached and not expired",
    )
    parser.add_argument(
        "--output-dir",
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--config",
        help="Path to polytool.yaml config file",
    )
    parser.add_argument(
        "--skip-robots",
        action="store_true",
        help="Skip robots.txt check (not recommended)",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Load config
    config = _load_config(args.config)
    cache_config = config.get("kb_sources_caching", {})

    # Get allowlist
    allowlist = cache_config.get("allowlist", DEFAULT_ALLOWLIST)

    # Get TTL
    ttl_config = cache_config.get("ttl_days", {})
    default_ttl = ttl_config.get("default", DEFAULT_TTL_DAYS)
    ttl_days = args.ttl_days or default_ttl

    # Get output directory
    output_dir = Path(args.output_dir or cache_config.get("output_dir", DEFAULT_OUTPUT_DIR))

    # Validate URL against allowlist
    url = args.url.strip()
    if not _is_url_allowed(url, allowlist):
        print(f"Error: URL not in allowlist: {url}", file=sys.stderr)
        print("Allowed domains:", file=sys.stderr)
        for domain in allowlist[:5]:
            print(f"  - {domain}", file=sys.stderr)
        print(f"  ... and {len(allowlist) - 5} more", file=sys.stderr)
        return 1

    # Check robots.txt
    if not args.skip_robots:
        if not _check_robots_txt(url):
            print(f"Error: URL disallowed by robots.txt: {url}", file=sys.stderr)
            return 1

    # Generate output filename
    filename = _url_to_filename(url)
    content_path = output_dir / f"{filename}.md"
    metadata_path = output_dir / f"{filename}.meta.json"

    # Check if cached and not expired
    if not args.force and metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(metadata.get("fetched_at", "").replace("Z", "+00:00"))
            expires_at = fetched_at + timedelta(days=metadata.get("ttl_days", ttl_days))
            if _utcnow() < expires_at.replace(tzinfo=None):
                print(f"Using cached version (expires: {expires_at.isoformat()})")
                print(f"Content: {content_path}")
                return 0
        except Exception:
            pass  # Proceed to fetch

    # Fetch URL
    print(f"Fetching: {url}")
    content = _fetch_url(url)
    if content is None:
        return 1

    # Convert HTML to markdown if needed
    if "<html" in content.lower() or "<body" in content.lower():
        content = _html_to_markdown(content)

    # Calculate content hash for deduplication
    content_hash = _content_hash(content)

    # Check for duplicate content
    if not args.force and content_path.exists():
        try:
            existing_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            if existing_meta.get("content_hash") == content_hash:
                print("Content unchanged, updating metadata only")
                existing_meta["fetched_at"] = _format_utc(_utcnow())
                metadata_path.write_text(json.dumps(existing_meta, indent=2), encoding="utf-8")
                return 0
        except Exception:
            pass

    # Write content
    output_dir.mkdir(parents=True, exist_ok=True)
    content_path.write_text(content, encoding="utf-8")

    # Write metadata
    metadata = {
        "source_url": url,
        "fetched_at": _format_utc(_utcnow()),
        "content_hash": content_hash,
        "ttl_days": ttl_days,
        "filename": f"{filename}.md",
        "size_bytes": len(content.encode("utf-8")),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    print("Cached successfully")
    print(f"Content: {content_path}")
    print(f"Metadata: {metadata_path}")
    print(f"Size: {metadata['size_bytes']} bytes")
    print(f"Hash: {content_hash[:16]}...")
    print(f"TTL: {ttl_days} days")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
