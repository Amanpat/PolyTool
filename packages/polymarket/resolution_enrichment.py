"""Scan-stage resolution enrichment with cache writes to ClickHouse."""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from .on_chain_ctf import OnChainCTFProvider
from .resolution import (
    CachedResolutionProvider,
    ClickHouseResolutionProvider,
    GammaResolutionProvider,
    Resolution,
)
from .subgraph import SubgraphResolutionProvider

logger = logging.getLogger(__name__)

DEFAULT_MAX_CANDIDATES = 200
DEFAULT_BATCH_SIZE = 25
DEFAULT_MAX_CONCURRENCY = 4
MAX_CANDIDATES_HARD_CAP = 1000
MAX_BATCH_SIZE = 200
MAX_CONCURRENCY = 16


@dataclass(frozen=True)
class ResolutionCandidate:
    """Token-level candidate for resolution enrichment."""

    outcome_token_id: str
    condition_id: str
    outcome_index: Optional[int]
    market_slug: str = ""
    outcome_name: str = ""


@dataclass
class ResolutionEnrichmentResult:
    """Summary metrics for one enrichment run."""

    proxy_wallet: str
    max_candidates: int
    batch_size: int
    max_concurrency: int
    candidates_total: int = 0
    candidates_processed: int = 0
    cached_hits: int = 0
    resolved_written: int = 0
    unresolved_network: int = 0
    skipped_missing_identifiers: int = 0
    skipped_unsupported: int = 0
    errors: int = 0
    skipped_reasons: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def add_skip_reason(self, reason: str) -> None:
        self.skipped_reasons[reason] = self.skipped_reasons.get(reason, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "proxy_wallet": self.proxy_wallet,
            "max_candidates": self.max_candidates,
            "batch_size": self.batch_size,
            "max_concurrency": self.max_concurrency,
            "candidates_total": self.candidates_total,
            "candidates_processed": self.candidates_processed,
            "cached_hits": self.cached_hits,
            "resolved_written": self.resolved_written,
            "unresolved_network": self.unresolved_network,
            "skipped_missing_identifiers": self.skipped_missing_identifiers,
            "skipped_unsupported": self.skipped_unsupported,
            "errors": self.errors,
            "skipped_reasons": dict(self.skipped_reasons),
            "warnings": list(self.warnings),
        }


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_limit(value: int, default: int, maximum: int) -> int:
    parsed = _coerce_int(value)
    if parsed is None or parsed <= 0:
        return default
    return min(parsed, maximum)


def _iter_batches(items: Sequence[ResolutionCandidate], batch_size: int) -> list[list[ResolutionCandidate]]:
    output: list[list[ResolutionCandidate]] = []
    for idx in range(0, len(items), batch_size):
        output.append(list(items[idx : idx + batch_size]))
    return output


def build_provider_chain(
    clickhouse_client,
    gamma_client,
    rpc_timeout_seconds: float = 10.0,
    subgraph_timeout_seconds: float = 15.0,
) -> tuple[CachedResolutionProvider, list[str]]:
    """Build default ClickHouse -> OnChain -> Subgraph -> Gamma provider chain."""
    warnings: list[str] = []

    clickhouse_provider = ClickHouseResolutionProvider(clickhouse_client)
    gamma_provider = GammaResolutionProvider(gamma_client) if gamma_client is not None else None

    rpc_url = (os.getenv("POLYGON_RPC_URL") or "").strip()
    onchain_provider = None
    if rpc_url:
        onchain_provider = OnChainCTFProvider(
            rpc_url=rpc_url,
            timeout=rpc_timeout_seconds,
        )
    else:
        warnings.append(
            "POLYGON_RPC_URL is not set; skipping OnChainCTFProvider. "
            "Unresolved outcomes remain PENDING/UNKNOWN when other providers miss."
        )

    subgraph_url = (os.getenv("POLYMARKET_SUBGRAPH_URL") or "").strip()
    subgraph_provider = None
    if subgraph_url:
        subgraph_provider = SubgraphResolutionProvider(
            subgraph_url=subgraph_url,
            timeout=subgraph_timeout_seconds,
        )
    else:
        warnings.append(
            "POLYMARKET_SUBGRAPH_URL is not set; skipping SubgraphResolutionProvider."
        )

    return (
        CachedResolutionProvider(
            clickhouse_provider=clickhouse_provider,
            gamma_provider=gamma_provider,
            on_chain_ctf_provider=onchain_provider,
            subgraph_provider=subgraph_provider,
        ),
        warnings,
    )


def fetch_resolution_candidates(
    clickhouse_client,
    proxy_wallet: str,
    max_candidates: int,
) -> list[ResolutionCandidate]:
    """Collect unique token/condition/outcome candidates for one wallet."""
    query = """
        SELECT
            resolved_token_id AS token_id,
            argMax(resolved_condition_id, ts) AS condition_id,
            argMax(resolved_outcome_index, ts) AS outcome_index,
            argMax(market_slug, ts) AS market_slug,
            argMax(resolved_outcome_name, ts) AS outcome_name,
            max(ts) AS latest_ts
        FROM user_trades_resolved
        WHERE proxy_wallet = {wallet:String}
          AND resolved_token_id != ''
        GROUP BY resolved_token_id
        ORDER BY latest_ts DESC
        LIMIT {limit:Int32}
    """
    result = clickhouse_client.query(
        query,
        parameters={"wallet": proxy_wallet, "limit": int(max_candidates)},
    )

    candidates: list[ResolutionCandidate] = []
    for row in result.result_rows:
        token_id = str(row[0] or "").strip()
        condition_id = str(row[1] or "").strip()
        outcome_index = _coerce_int(row[2])
        market_slug = str(row[3] or "").strip()
        outcome_name = str(row[4] or "").strip()
        candidates.append(
            ResolutionCandidate(
                outcome_token_id=token_id,
                condition_id=condition_id,
                outcome_index=outcome_index,
                market_slug=market_slug,
                outcome_name=outcome_name,
            )
        )
    return candidates


def _write_resolutions(
    clickhouse_client,
    proxy_wallet: str,
    rows_to_write: list[tuple[ResolutionCandidate, Resolution]],
) -> int:
    if not rows_to_write:
        return 0

    fetched_at = datetime.now(timezone.utc).replace(microsecond=0)
    rows = []
    for candidate, resolution in rows_to_write:
        raw_payload = {
            "proxy_wallet": proxy_wallet,
            "reason": resolution.reason,
            "outcome_index": candidate.outcome_index,
        }
        rows.append(
            [
                resolution.condition_id or candidate.condition_id,
                candidate.outcome_token_id,
                candidate.market_slug,
                candidate.outcome_name,
                float(resolution.settlement_price),
                resolution.resolved_at,
                resolution.resolution_source,
                fetched_at,
                json.dumps(raw_payload, sort_keys=True),
            ]
        )

    clickhouse_client.insert(
        "market_resolutions",
        rows,
        column_names=[
            "condition_id",
            "outcome_token_id",
            "market_slug",
            "outcome_name",
            "settlement_price",
            "resolved_at",
            "resolution_source",
            "fetched_at",
            "raw_json",
        ],
    )
    return len(rows)


def _ensure_market_resolutions_table(clickhouse_client) -> None:
    clickhouse_client.command(
        """
        CREATE TABLE IF NOT EXISTS market_resolutions (
            condition_id String,
            outcome_token_id String,
            market_slug String,
            outcome_name String,
            settlement_price Nullable(Float64),
            resolved_at DateTime64(3) NULL,
            resolution_source LowCardinality(String) DEFAULT 'unknown',
            fetched_at DateTime64(3) DEFAULT now64(3),
            raw_json String DEFAULT ''
        ) ENGINE = ReplacingMergeTree(fetched_at)
        ORDER BY (condition_id, outcome_token_id)
        SETTINGS index_granularity = 8192
        """
    )


def enrich_market_resolutions(
    clickhouse_client,
    proxy_wallet: str,
    provider: CachedResolutionProvider,
    max_candidates: int = DEFAULT_MAX_CANDIDATES,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
) -> ResolutionEnrichmentResult:
    """Enrich and cache market resolutions for a wallet."""
    normalized_max = _normalize_limit(
        max_candidates,
        default=DEFAULT_MAX_CANDIDATES,
        maximum=MAX_CANDIDATES_HARD_CAP,
    )
    normalized_batch = _normalize_limit(
        batch_size,
        default=DEFAULT_BATCH_SIZE,
        maximum=MAX_BATCH_SIZE,
    )
    normalized_workers = _normalize_limit(
        max_concurrency,
        default=DEFAULT_MAX_CONCURRENCY,
        maximum=MAX_CONCURRENCY,
    )

    summary = ResolutionEnrichmentResult(
        proxy_wallet=proxy_wallet,
        max_candidates=normalized_max,
        batch_size=normalized_batch,
        max_concurrency=normalized_workers,
    )
    try:
        _ensure_market_resolutions_table(clickhouse_client)
    except Exception as exc:
        summary.warnings.append(f"Failed ensuring market_resolutions table exists: {exc}")
        return summary

    candidates = fetch_resolution_candidates(
        clickhouse_client=clickhouse_client,
        proxy_wallet=proxy_wallet,
        max_candidates=normalized_max,
    )
    summary.candidates_total = len(candidates)

    if not candidates:
        summary.warnings.append(
            f"No resolution candidates found for wallet {proxy_wallet}."
        )
        return summary

    filtered: list[ResolutionCandidate] = []
    seen_tokens: set[str] = set()
    for candidate in candidates:
        if not candidate.outcome_token_id:
            summary.skipped_missing_identifiers += 1
            summary.add_skip_reason("missing_outcome_token_id")
            continue
        if candidate.outcome_token_id in seen_tokens:
            continue
        seen_tokens.add(candidate.outcome_token_id)

        if not candidate.condition_id:
            summary.skipped_missing_identifiers += 1
            summary.add_skip_reason("missing_condition_id")
            logger.info(
                "Skipping token %s: missing condition_id",
                candidate.outcome_token_id,
            )
            continue
        if candidate.outcome_index is None:
            summary.skipped_missing_identifiers += 1
            summary.add_skip_reason("missing_outcome_index")
            logger.info(
                "Skipping token %s (condition %s): missing outcome_index",
                candidate.outcome_token_id,
                candidate.condition_id,
            )
            continue
        if candidate.outcome_index < 0:
            summary.skipped_missing_identifiers += 1
            summary.add_skip_reason("invalid_outcome_index")
            logger.info(
                "Skipping token %s (condition %s): invalid outcome_index=%s",
                candidate.outcome_token_id,
                candidate.condition_id,
                candidate.outcome_index,
            )
            continue
        filtered.append(candidate)

    summary.candidates_processed = len(filtered)
    if not filtered:
        return summary

    cache_hits: dict[str, Resolution] = {}
    if provider.clickhouse_provider is not None:
        cache_hits = provider.clickhouse_provider.get_resolutions_batch(
            [candidate.outcome_token_id for candidate in filtered]
        )
    summary.cached_hits = len(cache_hits)

    pending_candidates = [
        candidate
        for candidate in filtered
        if candidate.outcome_token_id not in cache_hits
    ]

    resolved_to_write: list[tuple[ResolutionCandidate, Resolution]] = []
    for batch in _iter_batches(pending_candidates, normalized_batch):
        with ThreadPoolExecutor(max_workers=normalized_workers) as executor:
            futures = {
                executor.submit(
                    provider.get_resolution,
                    candidate.condition_id,
                    candidate.outcome_token_id,
                    candidate.outcome_index,
                    True,  # skip ClickHouse during concurrent network resolution
                ): candidate
                for candidate in batch
            }
            for future in as_completed(futures):
                candidate = futures[future]
                try:
                    resolution = future.result()
                except Exception as exc:
                    summary.errors += 1
                    summary.add_skip_reason("provider_error")
                    logger.warning(
                        "Resolution provider error for token %s: %s",
                        candidate.outcome_token_id,
                        exc,
                    )
                    continue

                if resolution is None:
                    summary.unresolved_network += 1
                    continue

                settlement_price = resolution.settlement_price
                if settlement_price is None:
                    summary.unresolved_network += 1
                    continue

                if settlement_price not in (0.0, 1.0):
                    summary.skipped_unsupported += 1
                    summary.add_skip_reason("unsupported_settlement_price")
                    logger.info(
                        "Skipping token %s: unsupported settlement_price=%s",
                        candidate.outcome_token_id,
                        settlement_price,
                    )
                    continue

                if resolution.resolution_source == "clickhouse_cache":
                    summary.cached_hits += 1
                    continue

                resolved_to_write.append((candidate, resolution))

    summary.resolved_written = _write_resolutions(
        clickhouse_client=clickhouse_client,
        proxy_wallet=proxy_wallet,
        rows_to_write=resolved_to_write,
    )
    return summary
