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


def _coerce_float(value) -> float:
    """Best-effort float coercion. The data API may return numeric fields as
    strings (e.g. ``vol``/``pnl``); missing/empty/non-numeric ⇒ 0.0."""
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def fetch_leaderboard(
    order_by: str = "PNL",
    time_period: str = "DAY",
    category: str = "OVERALL",
    max_pages: int = 5,
    page_size: int = 50,
    http_client=None,
    pacer=None,
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
        pacer: Optional ``BulkPacer`` (DR-2). When provided AND enabled, a small
            inter-page delay is applied before each page fetch after the first,
            so a bulk top-N export stays polite. Default None ⇒ no pacing (the
            existing zero-sleep behaviour Loop A and other callers rely on).

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
        # DR-2 bulk pacing: space out successive page fetches when enabled.
        # No-op (and zero sleep calls) when pacer is None or disabled — Loop A
        # and the gentle scheduler path pass no pacer, so behaviour is unchanged.
        if pacer is not None and page_num > 0:
            pacer.pace()

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

    # Sort by rank ascending (spec AT-01 requires ordered rank 1-N, no duplicates).
    # The data API returns `rank` as a STRING ("1".."50"), so a naive sort orders
    # lexicographically (1, 10, 11, ..., 2) and "top N" returns the wrong N. Coerce
    # to int before comparing. `or 0` guards missing/empty rank.
    all_entries.sort(key=lambda e: int(e.get("rank") or 0))
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
        # The live /v1/leaderboard response is camelCase
        # (proxyWallet/userName/vol/pnl, rank as a STRING). Older code/fixtures
        # used snake_case (proxy_wallet/name/volume). Read camelCase first and
        # fall back to snake_case so both the live API and existing fixtures
        # work (additive — mirrors the DR-2a export-path fix). Fixing only the
        # wallet would still write zero vol/pnl and empty usernames.
        proxy_wallet = str(
            entry.get("proxyWallet") or entry.get("proxy_wallet", "") or ""
        )
        username = str(
            entry.get("userName")
            or entry.get("name")
            or entry.get("username", "")
            or ""
        )
        # rank is a string ("1".."250") in the live API; `or 0` guards
        # missing/empty so int() never raises on an empty string.
        rank = int(entry.get("rank") or 0)
        pnl = _coerce_float(entry.get("pnl"))
        volume = _coerce_float(
            entry.get("vol") if entry.get("vol") is not None else entry.get("volume")
        )

        is_new = 0 if (proxy_wallet and proxy_wallet in prior) else 1

        raw_payload_json = json.dumps(entry)

        rows.append(
            LeaderboardSnapshotRow(
                snapshot_ts=snapshot_ts,
                fetch_run_id=fetch_run_id,
                order_by=order_by,
                time_period=time_period,
                category=category,
                rank=rank,
                proxy_wallet=proxy_wallet,
                username=username,
                pnl=pnl,
                volume=volume,
                is_new=is_new,
                raw_payload_json=raw_payload_json,
            )
        )

    return rows
