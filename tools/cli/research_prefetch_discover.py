"""CLI for L3.2 Prefetch Label Discovery Mode.

Search arXiv metadata (title + abstract only), score candidates with the
existing lexical relevance filter, and enqueue to the prefetch review queue
for operator labeling.

Metadata-only guarantee: no PDFs are downloaded, no Marker is called, no
ingestion or indexing occurs. Only the arXiv Atom API is used.

Usage:
  python -m polytool research-prefetch-discover \\
    --search "prediction markets microstructure" \\
    --max-results 20

  python -m polytool research-prefetch-discover \\
    --search "limit order book dynamics" \\
    --include-allow

  python -m polytool research-prefetch-discover \\
    --search "market making strategy" \\
    --decision-filter all --force
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Callable, List, Optional, Set


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_QUEUE_PATH = (
    _REPO_ROOT / "artifacts" / "research" / "prefetch_review_queue" / "review_queue.jsonl"
)
_DEFAULT_LABEL_PATH = (
    _REPO_ROOT / "artifacts" / "research" / "svm_filter_labels" / "labels.jsonl"
)

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
_ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")
_SVM_TARGET = 30
_VALID_DECISIONS = {"allow", "review", "reject"}


# ---------------------------------------------------------------------------
# Metadata-only arXiv search — no PDF download, no Marker
# ---------------------------------------------------------------------------

def _default_urlopen(url: str, timeout: int) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "PolyTool-PrefetchDiscover/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} {exc.reason} for {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"URL error: {exc.reason}") from exc
    except TimeoutError:
        raise RuntimeError(f"Timeout fetching {url}")
    except Exception as exc:
        raise RuntimeError(f"Fetch error: {exc}") from exc


def arxiv_search_metadata_only(
    query: str,
    max_results: int = 20,
    timeout: int = 15,
    _http_fn: Optional[Callable] = None,
) -> List[dict]:
    """Search arXiv for papers matching *query*, returning metadata only.

    Returns a list of dicts with keys: url, title, abstract, authors,
    published_date. No PDF is downloaded.

    Parameters
    ----------
    query:
        Topic/keyword search string.
    max_results:
        Maximum number of results to return.
    timeout:
        HTTP request timeout in seconds.
    _http_fn:
        Injectable HTTP function for offline testing.
        Signature: (url: str, timeout: int) -> bytes.

    Returns
    -------
    list[dict]
        Empty list when the API returns no entries.

    Raises
    ------
    RuntimeError
        On network failure or XML parse error.
    """
    http_fn = _http_fn if _http_fn is not None else _default_urlopen
    encoded = urllib.parse.quote_plus(query)
    api_url = (
        f"http://export.arxiv.org/api/query"
        f"?search_query=all:{encoded}&max_results={max_results}"
    )

    xml_bytes = http_fn(api_url, timeout)

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise RuntimeError(f"Failed to parse arXiv Atom response: {exc}") from exc

    results: List[dict] = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        title_el = entry.find("atom:title", _ATOM_NS)
        title = title_el.text.strip() if title_el is not None and title_el.text else ""

        summary_el = entry.find("atom:summary", _ATOM_NS)
        abstract = (
            summary_el.text.strip() if summary_el is not None and summary_el.text else ""
        )

        authors = [
            name_el.text.strip()
            for author_el in entry.findall("atom:author", _ATOM_NS)
            for name_el in [author_el.find("atom:name", _ATOM_NS)]
            if name_el is not None and name_el.text
        ]

        published_el = entry.find("atom:published", _ATOM_NS)
        published_date = None
        if published_el is not None and published_el.text:
            published_date = published_el.text[:10]  # YYYY-MM-DD

        id_el = entry.find("atom:id", _ATOM_NS)
        canonical_url = ""
        if id_el is not None and id_el.text:
            raw_id = id_el.text.strip()
            m = _ARXIV_ID_RE.search(raw_id)
            canonical_url = f"https://arxiv.org/abs/{m.group(1)}" if m else raw_id

        results.append(
            {
                "url": canonical_url,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "published_date": published_date,
            }
        )

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_decision_filter(value: str) -> Set[str]:
    """Parse --decision-filter into a set of decision strings."""
    if value.strip().lower() == "all":
        return set(_VALID_DECISIONS)
    parts = {p.strip().lower() for p in value.split(",") if p.strip()}
    unknown = parts - _VALID_DECISIONS
    if unknown:
        raise ValueError(
            f"Unknown decision(s): {', '.join(sorted(unknown))}. "
            f"Valid: allow, review, reject, all"
        )
    return parts


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(
    argv: List[str] | None = None,
    _http_fn: Optional[Callable] = None,
) -> int:
    """CLI entry point.

    Parameters
    ----------
    argv:
        Argument list (defaults to sys.argv[1:] when None).
    _http_fn:
        Injectable HTTP function for offline testing.
        Signature: (url: str, timeout: int) -> bytes.
    """
    parser = argparse.ArgumentParser(
        prog="research-prefetch-discover",
        description=(
            "L3.2 Prefetch Label Discovery: search arXiv metadata only, score candidates "
            "with the lexical relevance filter, and enqueue to the prefetch review queue. "
            "No PDFs are downloaded. No ingestion, no embeddings, no Marker."
        ),
    )
    parser.add_argument(
        "--search",
        required=True,
        metavar="QUERY",
        help="arXiv search query string.",
    )
    parser.add_argument(
        "--source-family",
        dest="source_family",
        default="academic",
        choices=["academic"],
        metavar="FAMILY",
        help="Source family to search (only 'academic'/arXiv supported in v0). Default: academic.",
    )
    parser.add_argument(
        "--max-results",
        "--limit",
        dest="max_results",
        type=int,
        default=20,
        metavar="N",
        help="Maximum number of search results to fetch. Default: 20.",
    )
    parser.add_argument(
        "--include-allow",
        dest="include_allow",
        action="store_true",
        help=(
            "Also queue ALLOW candidates (for positive label accumulation). "
            "Default: queue REVIEW candidates only."
        ),
    )
    parser.add_argument(
        "--decision-filter",
        dest="decision_filter",
        default=None,
        metavar="DECISIONS",
        help=(
            "Comma-separated decisions to queue: allow,review,reject,all. "
            "Overrides --include-allow. Default: review."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Re-queue candidates already in the queue (override idempotency). "
            "Creates a new entry for the same URL."
        ),
    )
    parser.add_argument(
        "--queue-path",
        dest="queue_path",
        metavar="PATH",
        default=None,
        help="Override review queue JSONL path.",
    )
    parser.add_argument(
        "--label-path",
        dest="label_path",
        metavar="PATH",
        default=None,
        help="Override label store JSONL path.",
    )
    parser.add_argument(
        "--filter-config",
        dest="filter_config",
        metavar="PATH",
        default=None,
        help="Override relevance filter config JSON path.",
    )
    parser.add_argument(
        "--timeout",
        dest="timeout",
        type=int,
        default=15,
        metavar="SECONDS",
        help="HTTP timeout for arXiv API call. Default: 15.",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output structured JSON summary instead of human-readable text.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Score and show what would be queued without writing anything.",
    )

    args = parser.parse_args(argv)

    # Resolve queue decision set
    if args.decision_filter is not None:
        try:
            queue_decisions = _parse_decision_filter(args.decision_filter)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
    else:
        queue_decisions = {"review"}
        if args.include_allow:
            queue_decisions.add("allow")

    # Load relevance filter config and scorer
    try:
        from packages.research.relevance_filter.scorer import (
            CandidateInput,
            RelevanceScorer,
            load_filter_config,
        )
        cfg_path = Path(args.filter_config) if args.filter_config else None
        cfg = load_filter_config(cfg_path)
        scorer = RelevanceScorer(cfg)
    except FileNotFoundError as exc:
        print(f"Error loading filter config: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error initializing relevance scorer: {exc}", file=sys.stderr)
        return 1

    # Open review queue and label store
    from packages.research.relevance_filter.queue_store import (
        LabelStore,
        ReviewQueueStore,
        candidate_id_from_url,
    )

    queue_path = Path(args.queue_path) if args.queue_path else _DEFAULT_QUEUE_PATH
    label_path = Path(args.label_path) if args.label_path else _DEFAULT_LABEL_PATH
    queue = ReviewQueueStore(queue_path)
    label_store = LabelStore(label_path)

    # Search arXiv — metadata only, no PDF downloads
    try:
        papers = arxiv_search_metadata_only(
            args.search,
            max_results=args.max_results,
            timeout=args.timeout,
            _http_fn=_http_fn,
        )
    except RuntimeError as exc:
        print(f"Error searching arXiv: {exc}", file=sys.stderr)
        return 1

    # Score and (optionally) enqueue
    discovered = len(papers)
    queued = 0
    skipped_duplicate = 0
    decision_counts = {"allow": 0, "review": 0, "reject": 0}
    queued_records: List[dict] = []

    for paper in papers:
        candidate = CandidateInput(
            title=paper["title"],
            abstract=paper["abstract"],
            source_url=paper["url"],
        )
        result = scorer.score(candidate)
        decision = result.decision
        decision_counts[decision] += 1

        if decision not in queue_decisions:
            continue

        record: dict = {
            "source_url": paper["url"],
            "title": paper["title"],
            "abstract": paper["abstract"],
            "score": result.score,
            "raw_score": result.raw_score,
            "decision": decision,
            "reason_codes": result.reason_codes,
            "matched_terms": result.matched_terms,
            "allow_threshold": result.allow_threshold,
            "review_threshold": result.review_threshold,
            "config_version": result.config_version,
            "source_family": args.source_family,
            "discovery_query": args.search,
        }
        if paper.get("published_date"):
            record["published_date"] = paper["published_date"]
        if paper.get("authors"):
            record["authors"] = paper["authors"]

        if args.dry_run:
            queued_records.append(record)
            queued += 1
            continue

        was_written = queue.enqueue(record, force=args.force)
        if was_written:
            queued += 1
            queued_records.append(record)
        else:
            skipped_duplicate += 1

    # Collect summary stats
    label_counts = label_store.counts()
    queue_stats = queue.queue_stats(label_store)
    allow_gap = max(0, _SVM_TARGET - label_counts["allow"])
    reject_gap = max(0, _SVM_TARGET - label_counts["reject"])

    if args.output_json:
        out = {
            "query": args.search,
            "source_family": args.source_family,
            "discovered": discovered,
            "queued": queued,
            "skipped_duplicate": skipped_duplicate,
            "dry_run": args.dry_run,
            "decision_filter": sorted(queue_decisions),
            "decisions": decision_counts,
            "label_counts": label_counts,
            "queue_stats": queue_stats,
            "svm_trigger": {
                "target": _SVM_TARGET,
                "allow_gap": allow_gap,
                "reject_gap": reject_gap,
            },
        }
        if args.dry_run:
            out["would_queue"] = queued_records
        print(json.dumps(out, indent=2))
        return 0

    # Human-readable output
    dry_tag = "[DRY RUN] " if args.dry_run else ""
    print(f"{dry_tag}arXiv metadata discovery: {args.search!r}")
    print(f"  source_family    : {args.source_family}")
    print(f"  discovered       : {discovered}")
    print(
        f"  filter decisions : "
        f"allow={decision_counts['allow']}  "
        f"review={decision_counts['review']}  "
        f"reject={decision_counts['reject']}"
    )
    verb = "would queue" if args.dry_run else "queued"
    print(
        f"  {verb:<15}: {queued}  "
        f"(filter: {', '.join(sorted(queue_decisions))})"
    )
    if skipped_duplicate:
        print(f"  skipped dup      : {skipped_duplicate}  (use --force to re-queue)")
    print("")

    if queued_records:
        heading = "Would queue:" if args.dry_run else "Queued:"
        print(heading)
        for r in queued_records:
            cid = candidate_id_from_url(r["source_url"])[:12]
            print(
                f"  {cid}  [{r['decision']:6s}]  score={r['score']:.4f}  {r['title']}"
            )
            if r.get("source_url"):
                print(f"             {r['source_url']}")
        print("")

    print(
        f"Label store  : {label_counts['total']} total  "
        f"allow={label_counts['allow']}  reject={label_counts['reject']}"
    )
    if allow_gap or reject_gap:
        print(
            f"SVM trigger (>={_SVM_TARGET} each) : "
            f"need {allow_gap} more allow, {reject_gap} more reject"
        )
    else:
        print(
            f"SVM trigger (>={_SVM_TARGET} each) : "
            "threshold met — ready for L3 v1 training"
        )
    return 0
