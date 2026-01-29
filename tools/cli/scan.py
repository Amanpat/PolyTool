#!/usr/bin/env python3
"""One-shot scan runner for PolyTool API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional

import requests

ALLOWED_BUCKETS = {"day", "hour", "week"}
DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_MAX_PAGES = 50
DEFAULT_BUCKET = "day"
DEFAULT_BACKFILL = True
DEFAULT_INGEST_MARKETS = False
DEFAULT_INGEST_ACTIVITY = False
DEFAULT_INGEST_POSITIONS = False
DEFAULT_COMPUTE_PNL = False
DEFAULT_COMPUTE_OPPORTUNITIES = False
DEFAULT_SNAPSHOT_BOOKS = False
DEFAULT_TIMEOUT_SECONDS = 120.0
MAX_BODY_SNIPPET = 800


class ApiError(Exception):
    """Raised when the API returns a non-200 response."""

    def __init__(self, method: str, url: str, status: int, body: str):
        super().__init__(f"{method} {url} -> {status}")
        self.method = method
        self.url = url
        self.status = status
        self.body = body


class NetworkError(Exception):
    """Raised when retries are exhausted for network errors."""

    def __init__(self, url: str, message: str, is_connection_error: bool = False):
        super().__init__(f"{url}: {message}")
        self.url = url
        self.message = message
        self.is_connection_error = is_connection_error


def load_env_file(path: str) -> Dict[str, str]:
    """Load key/value pairs from a .env-style file."""
    if not os.path.exists(path):
        return {}

    env: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                env[key] = value
    return env


def apply_env_defaults(env: Dict[str, str]) -> None:
    """Populate os.environ with defaults from .env without overriding existing vars."""
    for key, value in env.items():
        os.environ.setdefault(key, value)


def parse_bool(value: Optional[str], key: str) -> Optional[bool]:
    """Parse a boolean env value. Returns None if value is None."""
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "y", "on"):
        return True
    if normalized in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError(f"{key} must be a boolean (true/false), got: {value}")


def parse_int(value: Optional[str], key: str) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got: {value}") from exc


def parse_float(value: Optional[str], key: str) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number, got: {value}") from exc


def request_with_retry(
    method: str,
    url: str,
    payload: Dict[str, Any],
    timeout: float,
    retries: int,
    backoff_seconds: float,
) -> requests.Response:
    attempt = 0
    last_is_connection_error = False
    while True:
        try:
            response = requests.request(method, url, json=payload, timeout=timeout)
            return response
        except requests.exceptions.RequestException as exc:
            last_is_connection_error = isinstance(exc, requests.exceptions.ConnectionError)
            if attempt >= retries:
                raise NetworkError(url, str(exc), is_connection_error=last_is_connection_error) from exc
            delay = backoff_seconds * (2**attempt)
            print(
                f"Network error contacting {url}: {exc}. Retrying in {delay:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(delay)
            attempt += 1


def post_json(
    base_url: str,
    path: str,
    payload: Dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = 3,
    backoff_seconds: float = 1.0,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    response = request_with_retry("POST", url, payload, timeout, retries, backoff_seconds)

    if response.status_code != 200:
        body = response.text.strip()
        if len(body) > MAX_BODY_SNIPPET:
            body = body[:MAX_BODY_SNIPPET] + "..."
        raise ApiError("POST", url, response.status_code, body)

    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("POST", url, response.status_code, "Invalid JSON response") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a one-shot Polymarket scan via the PolyTool API.",
    )
    parser.add_argument("--user", help="Target Polymarket username (@name) or wallet address")
    parser.add_argument("--max-pages", type=int, help="Max pages to fetch for trade ingestion")
    parser.add_argument(
        "--bucket",
        choices=sorted(ALLOWED_BUCKETS),
        help="Bucket type for detectors (day, hour, week)",
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        default=None,
        help="Disable backfill of missing market mappings",
    )
    parser.add_argument(
        "--ingest-markets",
        action="store_true",
        default=None,
        help="Ingest active market metadata before scanning",
    )
    parser.add_argument(
        "--ingest-activity",
        action="store_true",
        default=None,
        help="Ingest user activity before running detectors",
    )
    parser.add_argument(
        "--ingest-positions",
        action="store_true",
        default=None,
        help="Ingest a user positions snapshot before running detectors",
    )
    parser.add_argument(
        "--compute-pnl",
        action="store_true",
        default=None,
        help="Compute PnL after running detectors",
    )
    parser.add_argument(
        "--compute-opportunities",
        action="store_true",
        default=None,
        help="Compute low-cost opportunity candidates after scanning",
    )
    parser.add_argument(
        "--snapshot-books",
        action="store_true",
        default=None,
        help="Snapshot orderbook metrics before computing PnL/arb",
    )
    parser.add_argument("--api-base-url", help="Base URL for the PolyTool API")
    return parser


def build_config(args: argparse.Namespace) -> Dict[str, Any]:
    env_user = os.getenv("TARGET_USER")
    env_max_pages = parse_int(os.getenv("SCAN_MAX_PAGES"), "SCAN_MAX_PAGES")
    env_bucket = os.getenv("SCAN_BUCKET")
    env_backfill = parse_bool(os.getenv("SCAN_BACKFILL"), "SCAN_BACKFILL")
    env_ingest_markets = parse_bool(os.getenv("SCAN_INGEST_MARKETS"), "SCAN_INGEST_MARKETS")
    env_ingest_activity = parse_bool(os.getenv("SCAN_INGEST_ACTIVITY"), "SCAN_INGEST_ACTIVITY")
    env_ingest_positions = parse_bool(os.getenv("SCAN_INGEST_POSITIONS"), "SCAN_INGEST_POSITIONS")
    env_compute_pnl = parse_bool(os.getenv("SCAN_COMPUTE_PNL"), "SCAN_COMPUTE_PNL")
    env_compute_opportunities = parse_bool(
        os.getenv("SCAN_COMPUTE_OPPORTUNITIES"), "SCAN_COMPUTE_OPPORTUNITIES"
    )
    env_snapshot_books = parse_bool(os.getenv("SCAN_SNAPSHOT_BOOKS"), "SCAN_SNAPSHOT_BOOKS")
    env_api_base = os.getenv("API_BASE_URL")
    env_timeout = parse_float(os.getenv("SCAN_HTTP_TIMEOUT_SECONDS"), "SCAN_HTTP_TIMEOUT_SECONDS")

    user = args.user or (env_user.strip() if env_user else "")
    max_pages = args.max_pages or env_max_pages or DEFAULT_MAX_PAGES
    bucket = (args.bucket or env_bucket or DEFAULT_BUCKET).lower()
    api_base_url = args.api_base_url or env_api_base or DEFAULT_API_BASE_URL
    timeout_seconds = env_timeout or DEFAULT_TIMEOUT_SECONDS

    if args.no_backfill is True:
        backfill = False
    elif env_backfill is not None:
        backfill = env_backfill
    else:
        backfill = DEFAULT_BACKFILL

    if args.ingest_markets is True:
        ingest_markets = True
    elif env_ingest_markets is not None:
        ingest_markets = env_ingest_markets
    else:
        ingest_markets = DEFAULT_INGEST_MARKETS

    if args.ingest_activity is True:
        ingest_activity = True
    elif env_ingest_activity is not None:
        ingest_activity = env_ingest_activity
    else:
        ingest_activity = DEFAULT_INGEST_ACTIVITY

    if args.ingest_positions is True:
        ingest_positions = True
    elif env_ingest_positions is not None:
        ingest_positions = env_ingest_positions
    else:
        ingest_positions = DEFAULT_INGEST_POSITIONS

    if args.compute_pnl is True:
        compute_pnl = True
    elif env_compute_pnl is not None:
        compute_pnl = env_compute_pnl
    else:
        compute_pnl = DEFAULT_COMPUTE_PNL

    if args.compute_opportunities is True:
        compute_opportunities = True
    elif env_compute_opportunities is not None:
        compute_opportunities = env_compute_opportunities
    else:
        compute_opportunities = DEFAULT_COMPUTE_OPPORTUNITIES

    if args.snapshot_books is True:
        snapshot_books = True
    elif env_snapshot_books is not None:
        snapshot_books = env_snapshot_books
    else:
        snapshot_books = DEFAULT_SNAPSHOT_BOOKS

    return {
        "user": user,
        "max_pages": max_pages,
        "bucket": bucket,
        "backfill": backfill,
        "ingest_markets": ingest_markets,
        "ingest_activity": ingest_activity,
        "ingest_positions": ingest_positions,
        "compute_pnl": compute_pnl,
        "compute_opportunities": compute_opportunities,
        "snapshot_books": snapshot_books,
        "api_base_url": api_base_url,
        "timeout_seconds": timeout_seconds,
    }


def validate_config(config: Dict[str, Any]) -> None:
    errors = []
    if not config["user"]:
        errors.append("TARGET_USER or --user is required.")
    if config["bucket"] not in ALLOWED_BUCKETS:
        errors.append(f"SCAN_BUCKET must be one of {sorted(ALLOWED_BUCKETS)}.")
    if not isinstance(config["max_pages"], int) or config["max_pages"] <= 0:
        errors.append("SCAN_MAX_PAGES must be a positive integer.")

    if errors:
        for err in errors:
            print(f"Config error: {err}", file=sys.stderr)
        raise SystemExit(1)

    if config["timeout_seconds"] <= 0:
        print("Config error: SCAN_HTTP_TIMEOUT_SECONDS must be positive.", file=sys.stderr)
        raise SystemExit(1)


def summarize_detector_results(results: list[dict]) -> list[dict]:
    top_by_detector: Dict[str, dict] = {}
    for item in results:
        name = item.get("detector") or "unknown"
        score = item.get("score")
        if score is None:
            continue
        current = top_by_detector.get(name)
        if current is None or score > current["score"]:
            top_by_detector[name] = {
                "detector": name,
                "score": score,
                "label": item.get("label"),
                "bucket_start": item.get("bucket_start"),
            }
    return sorted(top_by_detector.values(), key=lambda row: row["score"], reverse=True)


def print_summary(
    config: Dict[str, Any],
    resolve_response: Dict[str, Any],
    ingest_response: Dict[str, Any],
    activity_response: Optional[Dict[str, Any]],
    positions_response: Optional[Dict[str, Any]],
    snapshot_response: Optional[Dict[str, Any]],
    detectors_response: Dict[str, Any],
    pnl_response: Optional[Dict[str, Any]],
    opportunities_response: Optional[Dict[str, Any]],
) -> None:
    username = resolve_response.get("username") or config["user"]
    proxy_wallet = resolve_response.get("proxy_wallet") or "unknown"

    print("")
    print("Scan complete")
    print(f"Username: {username}")
    print(f"Proxy wallet: {proxy_wallet}")

    print(
        "Trades ingested: "
        f"pages={ingest_response.get('pages_fetched')}, "
        f"fetched={ingest_response.get('rows_fetched_total')}, "
        f"written={ingest_response.get('rows_written')}, "
        f"distinct={ingest_response.get('distinct_trade_uids_total')}"
    )

    if activity_response:
        print(
            "Activity ingested: "
            f"pages={activity_response.get('pages_fetched')}, "
            f"fetched={activity_response.get('rows_fetched_total')}, "
            f"written={activity_response.get('rows_written')}, "
            f"distinct={activity_response.get('distinct_activity_uids_total')}"
        )

    if positions_response:
        print(
            "Positions snapshot: "
            f"rows={positions_response.get('rows_written')}, "
            f"snapshot_ts={positions_response.get('snapshot_ts')}"
        )

    if snapshot_response:
        # Token selection diagnostics
        candidates = snapshot_response.get('tokens_candidates_before_filter', 0)
        with_metadata = snapshot_response.get('tokens_with_market_metadata', 0)
        after_filter = snapshot_response.get('tokens_after_active_filter', 0)
        selected = snapshot_response.get('tokens_selected_total', 0)
        # Execution results
        ok = snapshot_response.get('tokens_ok', 0)
        error = snapshot_response.get('tokens_error', 0)
        no_orderbook = snapshot_response.get('tokens_no_orderbook', 0)
        http_429 = snapshot_response.get('tokens_http_429', 0)
        http_5xx = snapshot_response.get('tokens_http_5xx', 0)
        skipped_ttl = snapshot_response.get('tokens_skipped_no_orderbook_ttl', 0)
        no_ok_reason = snapshot_response.get('no_ok_reason')

        print(
            f"Books snapshotted: candidates={candidates} -> "
            f"metadata={with_metadata} -> active={after_filter} -> selected={selected}"
        )
        print(
            f"  Results: ok={ok}, empty={snapshot_response.get('tokens_empty', 0)}, "
            f"one_sided={snapshot_response.get('tokens_one_sided', 0)}, "
            f"no_orderbook={no_orderbook}, error={error} "
            f"(429={http_429}, 5xx={http_5xx}), skipped_ttl={skipped_ttl}"
        )
        if no_ok_reason:
            print(f"  Reason: {no_ok_reason}")

    backfill_stats = detectors_response.get("backfill_stats")
    if backfill_stats:
        backfill_text = json.dumps(backfill_stats, separators=(",", ":"))
    else:
        backfill_text = "disabled" if not config["backfill"] else "none"
    print(f"Backfill: {backfill_text}")

    detector_results = summarize_detector_results(detectors_response.get("results", []))
    if detector_results:
        print("Detector scores:")
        for item in detector_results:
            bucket_start = item.get("bucket_start") or "n/a"
            print(
                f"  {item['detector']}: score={item['score']} "
                f"label={item.get('label')} bucket_start={bucket_start}"
            )
    else:
        print("Detector scores: none")

    if pnl_response:
        latest_bucket = pnl_response.get("latest_bucket") or {}
        if latest_bucket:
            print(
                "PnL latest bucket: "
                f"realized={latest_bucket.get('realized_pnl')}, "
                f"mtm={latest_bucket.get('mtm_pnl_estimate')}, "
                f"exposure={latest_bucket.get('exposure_notional_estimate')}"
            )
        else:
            print("PnL latest bucket: none")

    if opportunities_response:
        print(
            "Opportunities: "
            f"candidates={opportunities_response.get('candidates_considered')}, "
            f"returned={opportunities_response.get('returned_count')}, "
            f"bucket={opportunities_response.get('bucket_start')}"
        )

    api_base_url = config["api_base_url"].rstrip("/")
    print("")
    print("URLs")
    print("  Grafana: http://localhost:3000")
    print("  Dashboards: PolyTool - User Trades, PolyTool - Strategy Detectors, PolyTool - PnL")
    print(f"  Swagger: {api_base_url}/docs")


def run_scan(config: Dict[str, Any]) -> None:
    api_base_url = config["api_base_url"]
    timeout_seconds = config["timeout_seconds"]

    if config["ingest_markets"]:
        post_json(
            api_base_url,
            "/api/ingest/markets",
            {"active_only": True},
            timeout=timeout_seconds,
        )

    activity_response = None
    if config["ingest_activity"]:
        activity_response = post_json(
            api_base_url,
            "/api/ingest/activity",
            {"user": config["user"], "max_pages": config["max_pages"]},
            timeout=timeout_seconds,
        )

    positions_response = None
    if config["ingest_positions"]:
        positions_response = post_json(
            api_base_url,
            "/api/ingest/positions",
            {"user": config["user"]},
            timeout=timeout_seconds,
        )

    snapshot_response = None
    if config["snapshot_books"]:
        snapshot_response = post_json(
            api_base_url,
            "/api/snapshot/books",
            {"user": config["user"]},
            timeout=timeout_seconds,
        )

    resolve_response = post_json(
        api_base_url,
        "/api/resolve",
        {"input": config["user"]},
        timeout=timeout_seconds,
    )
    ingest_response = post_json(
        api_base_url,
        "/api/ingest/trades",
        {"user": config["user"], "max_pages": config["max_pages"]},
        timeout=timeout_seconds,
    )
    detectors_response = post_json(
        api_base_url,
        "/api/run/detectors",
        {
            "user": config["user"],
            "bucket": config["bucket"],
            "backfill_mappings": config["backfill"],
        },
        timeout=timeout_seconds,
    )

    pnl_response = None
    if config["compute_pnl"]:
        pnl_response = post_json(
            api_base_url,
            "/api/compute/pnl",
            {"user": config["user"], "bucket": config["bucket"]},
            timeout=timeout_seconds,
        )

    opportunities_response = None
    if config["compute_opportunities"]:
        opportunities_response = post_json(
            api_base_url,
            "/api/compute/opportunities",
            {"user": config["user"], "bucket": config["bucket"]},
            timeout=timeout_seconds,
        )

    print_summary(
        config,
        resolve_response,
        ingest_response,
        activity_response,
        positions_response,
        snapshot_response,
        detectors_response,
        pnl_response,
        opportunities_response,
    )


def main(argv: Optional[list[str]] = None) -> int:
    env_values = load_env_file(os.path.join(os.getcwd(), ".env"))
    apply_env_defaults(env_values)

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = build_config(args)
        validate_config(config)
        run_scan(config)
        return 0
    except ApiError as exc:
        print(
            f"API error: {exc.method} {exc.url} -> {exc.status}",
            file=sys.stderr,
        )
        if exc.body:
            print(f"Response body: {exc.body}", file=sys.stderr)
        if exc.status in (502, 503, 504):
            print("Start docker compose up -d --build", file=sys.stderr)
        return 1
    except NetworkError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        if exc.is_connection_error:
            print("Start docker compose up -d --build", file=sys.stderr)
        return 1
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


if __name__ == "__main__":
    raise SystemExit(main())
