"""Leaderboard fetcher for Wallet Discovery v1 — Loop A.

Paginates through the Polymarket leaderboard API and returns typed row objects.
Threat T-qeu-04 (DoS): max_pages cap prevents unbounded pagination.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md section "Loop A"
API: GET https://data-api.polymarket.com/v1/leaderboard
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from packages.polymarket.discovery.models import LeaderboardSnapshotRow

logger = logging.getLogger(__name__)

_LEADERBOARD_BASE_URL = "https://data-api.polymarket.com"
_LEADERBOARD_PATH = "/v1/leaderboard"


def fetch_leaderboard(
    order_by: str = "PNL",
    time_period: str = "DAY",
    category: str = "OVERALL",
    max_pages: int = 5,
    page_size: int = 50,
    http_client=None,
) -> list[dict]:
    """Fetch paginated leaderboard entries from the Polymarket data API.

    Args:
        order_by: Sort field — 'PNL' or 'VOL'
        time_period: Time window — 'DAY', 'WEEK', 'MONTH', 'ALL'
        category: Market category — 'OVERALL', 'POLITICS', 'SPORTS', 'CRYPTO'
        max_pages: Maximum pages to fetch (DoS guard, T-qeu-04)
        page_size: Entries per page (default 50 matching API default)
        http_client: Optional injectable HttpClient for testing. If None,
            creates a real HttpClient against the data API.

    Returns:
        List of raw dict entries from the API, ordered by rank (ascending).
    """
    if http_client is None:
        from packages.polymarket.http_client import HttpClient
        http_client = HttpClient(
            base_url=_LEADERBOARD_BASE_URL,
            timeout=20.0,
            max_retries=3,
            backoff_factor=1.0,
        )

    all_entries: list[dict] = []

    for page_num in range(max_pages):
        offset = page_num * page_size
        params = {
            "order_by": order_by,
            "time_period": time_period,
            "limit": page_size,
            "offset": offset,
        }
        if category and category.upper() != "OVERALL":
            params["category"] = category

        try:
            resp = http_client.get(_LEADERBOARD_PATH, params=params)
            if resp.status_code != 200:
                logger.warning(
                    "Leaderboard API returned status %d on page %d — stopping.",
                    resp.status_code,
                    page_num + 1,
                )
                break

            page_data = resp.json()
            if not page_data:
                logger.debug("Empty page at offset %d — stopping pagination.", offset)
                break

            all_entries.extend(page_data)
            logger.debug("Fetched page %d: %d entries (total so far: %d)", page_num + 1, len(page_data), len(all_entries))

        except Exception as exc:
            logger.error("Leaderboard fetch error on page %d: %s", page_num + 1, exc)
            break

    # Sort by rank ascending (spec AT-01 requires ordered rank 1-N, no duplicates)
    all_entries.sort(key=lambda e: e.get("rank", 0))
    return all_entries


def to_snapshot_rows(
    raw_entries: list[dict],
    fetch_run_id: str,
    snapshot_ts: datetime,
    order_by: str,
    time_period: str,
    category: str,
    prior_wallets: Optional[set[str]] = None,
) -> list[LeaderboardSnapshotRow]:
    """Convert raw API dict entries to typed LeaderboardSnapshotRow objects.

    Args:
        raw_entries: Raw dict entries from fetch_leaderboard().
        fetch_run_id: UUID for this fetch run.
        snapshot_ts: Timestamp for this snapshot batch.
        order_by: Sort field used for this fetch.
        time_period: Time period used for this fetch.
        category: Category used for this fetch.
        prior_wallets: Set of proxy_wallet values from the previous snapshot
            at the same (order_by, time_period, category) key. If None or
            empty, all wallets are treated as new (first-ever snapshot).

    Returns:
        List of LeaderboardSnapshotRow objects with is_new flags set.
    """
    prior = prior_wallets or set()
    rows: list[LeaderboardSnapshotRow] = []

    for entry in raw_entries:
        proxy_wallet = entry.get("proxy_wallet", "")
        is_new = 0 if (proxy_wallet and proxy_wallet in prior) else 1

        raw_payload_json = json.dumps(entry)

        rows.append(
            LeaderboardSnapshotRow(
                snapshot_ts=snapshot_ts,
                fetch_run_id=fetch_run_id,
                order_by=order_by,
                time_period=time_period,
                category=category,
                rank=int(entry.get("rank", 0)),
                proxy_wallet=proxy_wallet,
                username=entry.get("name", entry.get("username", "")),
                pnl=float(entry.get("pnl", 0.0)),
                volume=float(entry.get("volume", 0.0)),
                is_new=is_new,
                raw_payload_json=raw_payload_json,
            )
        )

    return rows
