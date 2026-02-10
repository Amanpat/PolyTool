"""Resolution provider for fetching market settlement data.

Implements best-effort resolution fetching from Gamma API and ClickHouse cache.
If resolution cannot be determined, returns UNKNOWN_RESOLUTION.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol

logger = logging.getLogger(__name__)


class ResolutionOutcome(str, Enum):
    """Resolution outcome taxonomy."""
    WIN = "WIN"
    LOSS = "LOSS"
    PROFIT_EXIT = "PROFIT_EXIT"
    LOSS_EXIT = "LOSS_EXIT"
    PENDING = "PENDING"
    UNKNOWN_RESOLUTION = "UNKNOWN_RESOLUTION"


@dataclass
class Resolution:
    """Market resolution data for a single outcome token."""
    condition_id: str
    outcome_token_id: str
    settlement_price: Optional[float]  # 1.0 for winner, 0.0 for loser, None if pending
    resolved_at: Optional[datetime]
    resolution_source: str
    reason: str = ""


class ResolutionProvider(Protocol):
    """Protocol for resolution data providers."""

    def get_resolution(
        self,
        condition_id: str,
        outcome_token_id: str,
        outcome_index: Optional[int] = None,
        skip_clickhouse_cache: bool = False,
    ) -> Optional[Resolution]:
        """Fetch resolution for an outcome token."""
        ...

    def get_resolutions_batch(
        self,
        token_ids: list[str],
    ) -> dict[str, Resolution]:
        """Fetch resolutions for multiple tokens."""
        ...


def generate_trade_uid(tx_hash: str, log_index: int) -> str:
    """Generate deterministic trade UID from transaction hash and log index.

    trade_uid = sha256(f"{tx_hash}:{log_index}").hexdigest()
    """
    if not tx_hash:
        return ""
    data = f"{tx_hash}:{log_index}"
    return hashlib.sha256(data.encode()).hexdigest()


def determine_resolution_outcome(
    settlement_price: Optional[float],
    side: str,
    position_remaining: float,
    gross_pnl: float,
) -> ResolutionOutcome:
    """Determine resolution outcome based on settlement and position state.

    Args:
        settlement_price: 1.0 for winner, 0.0 for loser, None if pending
        side: Trade side ('buy' or 'sell')
        position_remaining: Remaining position size
        gross_pnl: Gross profit/loss

    Returns:
        ResolutionOutcome enum value
    """
    side_lower = side.lower() if side else ""

    # Pending if no settlement price
    if settlement_price is None:
        return ResolutionOutcome.PENDING

    # If still holding position, outcome depends on settlement
    if position_remaining > 0:
        if settlement_price == 1.0:
            return ResolutionOutcome.WIN
        elif settlement_price == 0.0:
            return ResolutionOutcome.LOSS
        else:
            return ResolutionOutcome.UNKNOWN_RESOLUTION

    # If fully exited, outcome depends on PnL
    if position_remaining <= 0:
        if gross_pnl > 0:
            return ResolutionOutcome.PROFIT_EXIT
        else:
            return ResolutionOutcome.LOSS_EXIT

    return ResolutionOutcome.UNKNOWN_RESOLUTION


class ClickHouseResolutionProvider:
    """Resolution provider that reads from ClickHouse cache."""

    def __init__(self, client):
        self.client = client

    def get_resolution(
        self,
        condition_id: str,
        outcome_token_id: str,
        outcome_index: Optional[int] = None,
        skip_clickhouse_cache: bool = False,
    ) -> Optional[Resolution]:
        """Fetch resolution from ClickHouse cache."""
        query = """
            SELECT
                condition_id,
                outcome_token_id,
                settlement_price,
                resolved_at,
                resolution_source
            FROM market_resolutions
            WHERE outcome_token_id = {token_id:String}
            ORDER BY fetched_at DESC
            LIMIT 1
        """
        try:
            result = self.client.query(query, parameters={"token_id": outcome_token_id})
            if result.result_rows:
                row = result.result_rows[0]
                return Resolution(
                    condition_id=row[0] or condition_id,
                    outcome_token_id=row[1] or outcome_token_id,
                    settlement_price=float(row[2]) if row[2] is not None else None,
                    resolved_at=row[3] if row[3] else None,
                    resolution_source=row[4] or "clickhouse_cache",
                    reason="cached from ClickHouse",
                )
        except Exception as e:
            logger.warning(f"Error fetching resolution from ClickHouse: {e}")
        return None

    def get_resolutions_batch(
        self,
        token_ids: list[str],
    ) -> dict[str, Resolution]:
        """Fetch multiple resolutions from ClickHouse cache."""
        if not token_ids:
            return {}

        query = """
            SELECT
                condition_id,
                outcome_token_id,
                settlement_price,
                resolved_at,
                resolution_source
            FROM market_resolutions
            WHERE outcome_token_id IN {token_ids:Array(String)}
        """
        results: dict[str, Resolution] = {}
        try:
            result = self.client.query(query, parameters={"token_ids": token_ids})
            for row in result.result_rows:
                token_id = row[1]
                results[token_id] = Resolution(
                    condition_id=row[0] or "",
                    outcome_token_id=token_id,
                    settlement_price=float(row[2]) if row[2] is not None else None,
                    resolved_at=row[3] if row[3] else None,
                    resolution_source=row[4] or "clickhouse_cache",
                    reason="cached from ClickHouse",
                )
        except Exception as e:
            logger.warning(f"Error fetching batch resolutions from ClickHouse: {e}")
        return results


class GammaResolutionProvider:
    """Resolution provider that fetches from Gamma API (closed markets)."""

    def __init__(self, gamma_client):
        self.gamma_client = gamma_client

    @staticmethod
    def _normalize_condition_id(condition_id: str) -> str:
        text = str(condition_id or "").strip().lower()
        if not text:
            return ""
        if text.startswith("0x"):
            return "0x" + text[2:]
        return "0x" + text

    @staticmethod
    def _infer_winning_outcome_from_prices(raw: dict) -> Optional[int]:
        prices_raw = raw.get("outcomePrices", raw.get("outcome_prices"))
        if prices_raw is None:
            return None
        if isinstance(prices_raw, str):
            try:
                prices_raw = json.loads(prices_raw)
            except (TypeError, ValueError, json.JSONDecodeError):
                return None
        if not isinstance(prices_raw, list) or not prices_raw:
            return None

        prices: list[float] = []
        for value in prices_raw:
            try:
                prices.append(float(value))
            except (TypeError, ValueError):
                return None

        max_idx = max(range(len(prices)), key=lambda idx: prices[idx])
        max_price = prices[max_idx]
        # Require a clear winner near settlement price 1.0.
        if max_price < 0.99:
            return None
        for idx, price in enumerate(prices):
            if idx == max_idx:
                continue
            if price > 0.01:
                return None
        return max_idx

    def get_resolution(
        self,
        condition_id: str,
        outcome_token_id: str,
        outcome_index: Optional[int] = None,
        skip_clickhouse_cache: bool = False,
    ) -> Optional[Resolution]:
        """Fetch resolution from Gamma API for closed markets."""
        try:
            market = None
            normalized_requested_cid = self._normalize_condition_id(condition_id)
            if condition_id:
                candidate_market = self.gamma_client.get_market_by_condition_id(condition_id)
                if candidate_market:
                    normalized_candidate_cid = self._normalize_condition_id(candidate_market.condition_id)
                    if normalized_candidate_cid == normalized_requested_cid:
                        market = candidate_market

            markets = [market] if market else self.gamma_client.fetch_markets_filtered(
                clob_token_ids=[outcome_token_id],
                closed=True,
            )
            if not market and normalized_requested_cid:
                for fetched_market in markets:
                    if self._normalize_condition_id(fetched_market.condition_id) == normalized_requested_cid:
                        market = fetched_market
                        break
                if market is None and markets:
                    market = markets[0]

            if markets:
                market = market or markets[0]
                # Determine outcome index for this token.
                if outcome_index is not None:
                    idx = outcome_index
                else:
                    try:
                        idx = market.clob_token_ids.index(outcome_token_id)
                    except ValueError:
                        idx = -1

                # Check if market is resolved (closed)
                if market.close_date_iso:
                    # Gamma doesn't directly expose settlement_price, but we can infer
                    # from the raw JSON if available
                    raw = market.raw_json or {}
                    winning_outcome = raw.get("winningOutcome", raw.get("winner", None))
                    if isinstance(winning_outcome, str):
                        winning_outcome_str = winning_outcome.strip()
                        if winning_outcome_str.isdigit():
                            winning_outcome = int(winning_outcome_str)
                        else:
                            normalized = winning_outcome_str.lower()
                            outcomes = [str(o).strip().lower() for o in (market.outcomes or [])]
                            try:
                                winning_outcome = outcomes.index(normalized)
                            except ValueError:
                                winning_outcome = None
                    if winning_outcome is None:
                        winning_outcome = self._infer_winning_outcome_from_prices(raw)
                    if isinstance(winning_outcome, int) and idx >= 0:
                        # Determine settlement price based on winning outcome
                        settlement_price = 1.0 if idx == winning_outcome else 0.0
                        reason = f"gamma winningOutcome={winning_outcome}, outcome_index={idx}"
                        return Resolution(
                            condition_id=condition_id,
                            outcome_token_id=outcome_token_id,
                            settlement_price=settlement_price,
                            resolved_at=market.close_date_iso,
                            resolution_source="gamma",
                            reason=reason,
                        )
        except Exception as e:
            logger.warning(f"Error fetching resolution from Gamma: {e}")
        return None

    def get_resolutions_batch(
        self,
        token_ids: list[str],
    ) -> dict[str, Resolution]:
        """Fetch multiple resolutions from Gamma API."""
        results: dict[str, Resolution] = {}
        for token_id in token_ids:
            resolution = self.get_resolution("", token_id)
            if resolution:
                results[token_id] = resolution
        return results


class CachedResolutionProvider:
    """Resolution provider that caches results and falls back to multiple sources.

    Chain: ClickHouse -> OnChainCTF -> Subgraph -> Gamma -> None
    """

    def __init__(
        self,
        clickhouse_provider: Optional[ClickHouseResolutionProvider] = None,
        gamma_provider: Optional[GammaResolutionProvider] = None,
        on_chain_ctf_provider: Optional["OnChainCTFProvider"] = None,
        subgraph_provider: Optional["SubgraphResolutionProvider"] = None,
    ):
        self.clickhouse_provider = clickhouse_provider
        self.gamma_provider = gamma_provider
        self.on_chain_ctf_provider = on_chain_ctf_provider
        self.subgraph_provider = subgraph_provider
        self._cache: dict[str, Resolution] = {}

    def get_resolution(
        self,
        condition_id: str,
        outcome_token_id: str,
        outcome_index: Optional[int] = None,
        skip_clickhouse_cache: bool = False,
    ) -> Optional[Resolution]:
        """Fetch resolution with caching and fallback.

        Chain: ClickHouse -> OnChainCTF -> Subgraph -> Gamma -> None
        """
        # Check cache first
        if outcome_token_id in self._cache:
            return self._cache[outcome_token_id]

        resolution = None

        # Try ClickHouse cache first (fastest)
        if self.clickhouse_provider and not skip_clickhouse_cache:
            resolution = self.clickhouse_provider.get_resolution(
                condition_id, outcome_token_id, outcome_index=outcome_index
            )

        # Fall back to on-chain CTF
        if not resolution and self.on_chain_ctf_provider:
            resolution = self.on_chain_ctf_provider.get_resolution(
                condition_id,
                outcome_token_id,
                outcome_index=outcome_index,
            )

        # Fall back to subgraph
        if not resolution and self.subgraph_provider:
            resolution = self.subgraph_provider.get_resolution(
                condition_id,
                outcome_token_id,
                outcome_index=outcome_index,
            )

        # Fall back to Gamma API
        if not resolution and self.gamma_provider:
            resolution = self.gamma_provider.get_resolution(
                condition_id,
                outcome_token_id,
                outcome_index=outcome_index,
            )

        # Cache result
        if resolution:
            self._cache[outcome_token_id] = resolution

        return resolution

    def get_resolutions_batch(
        self,
        token_ids: list[str],
    ) -> dict[str, Resolution]:
        """Fetch multiple resolutions with caching.

        Chain: ClickHouse -> OnChainCTF -> Subgraph -> Gamma -> None
        """
        results: dict[str, Resolution] = {}
        missing: list[str] = []

        # Check cache first
        for token_id in token_ids:
            if token_id in self._cache:
                results[token_id] = self._cache[token_id]
            else:
                missing.append(token_id)

        # Batch fetch missing from ClickHouse
        if missing and self.clickhouse_provider:
            ch_results = self.clickhouse_provider.get_resolutions_batch(missing)
            results.update(ch_results)
            self._cache.update(ch_results)
            missing = [t for t in missing if t not in ch_results]

        # Fetch remaining from on-chain CTF (note: batch not optimized yet)
        if missing and self.on_chain_ctf_provider:
            onchain_results = self.on_chain_ctf_provider.get_resolutions_batch(missing)
            results.update(onchain_results)
            self._cache.update(onchain_results)
            missing = [t for t in missing if t not in onchain_results]

        # Fetch remaining from subgraph (note: batch not optimized yet)
        if missing and self.subgraph_provider:
            subgraph_results = self.subgraph_provider.get_resolutions_batch(missing)
            results.update(subgraph_results)
            self._cache.update(subgraph_results)
            missing = [t for t in missing if t not in subgraph_results]

        # Fetch remaining from Gamma
        if missing and self.gamma_provider:
            gamma_results = self.gamma_provider.get_resolutions_batch(missing)
            results.update(gamma_results)
            self._cache.update(gamma_results)

        return results
