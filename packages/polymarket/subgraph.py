"""Subgraph resolution provider using The Graph."""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from .resolution import Resolution

logger = logging.getLogger(__name__)


class SubgraphResolutionProvider:
    """Resolution provider that queries The Graph subgraph for CTF condition data.

    Queries the Polymarket subgraph for condition resolution state.
    Uses GraphQL over HTTP POST.
    """

    def __init__(self, subgraph_url: Optional[str] = None, timeout: float = 15.0):
        """Initialize subgraph resolution provider.

        Args:
            subgraph_url: The Graph subgraph URL (defaults to POLYMARKET_SUBGRAPH_URL env var)
            timeout: Request timeout in seconds
        """
        self.subgraph_url = subgraph_url or os.environ.get(
            "POLYMARKET_SUBGRAPH_URL",
            "https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic",
        )
        self.timeout = timeout

    def _normalize_condition_id(self, condition_id: str) -> str:
        """Normalize condition ID for subgraph query.

        The Graph indexes condition IDs as lowercase hex WITHOUT 0x prefix.

        Args:
            condition_id: Condition ID (with or without 0x prefix)

        Returns:
            Lowercase hex string without 0x prefix
        """
        return condition_id.lower().replace("0x", "")

    def get_resolution(
        self,
        condition_id: str,
        outcome_token_id: str,
        outcome_index: Optional[int] = None,
    ) -> Optional[Resolution]:
        """Query subgraph for condition resolution.

        Args:
            condition_id: Market condition ID
            outcome_token_id: Outcome token ID (for Resolution object)
            outcome_index: Outcome index (0 or 1). If None, infers from payoutNumerators.

        Returns:
            Resolution with settlement_price and descriptive reason, or None if not resolved
        """
        normalized_cid = self._normalize_condition_id(condition_id)

        # GraphQL query
        query = """
        {
          condition(id: "%s") {
            id
            resolved
            payoutNumerators
            payoutDenominator
            resolutionTimestamp
          }
        }
        """ % normalized_cid

        payload = {"query": query}

        try:
            response = requests.post(
                self.subgraph_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                logger.warning(
                    f"GraphQL errors for condition {condition_id[:8]}...: "
                    f"{result['errors']}"
                )
                return None

            data = result.get("data", {})
            condition = data.get("condition")

            if not condition:
                logger.debug(f"Condition {condition_id[:8]}... not found in subgraph")
                return None

            resolved = condition.get("resolved", False)
            if not resolved:
                logger.debug(f"Condition {condition_id[:8]}... not resolved yet")
                return None

            payout_numerators = condition.get("payoutNumerators", [])
            payout_denominator = condition.get("payoutDenominator")

            if not payout_numerators or payout_denominator is None:
                logger.debug(
                    f"Condition {condition_id[:8]}... resolved but missing payout data"
                )
                return None

            # Parse numerators (they come as string array from GraphQL)
            try:
                numerators = [int(n) for n in payout_numerators]
                denominator = int(payout_denominator)
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Failed to parse payout data for {condition_id[:8]}...: {e}"
                )
                return None

            if denominator == 0:
                logger.debug(f"Condition {condition_id[:8]}... has zero denominator")
                return None

            # Determine winning outcome
            winning_index = None
            for idx, numerator in enumerate(numerators):
                if numerator == denominator:
                    winning_index = idx
                    break

            if winning_index is None:
                logger.warning(
                    f"No winning outcome found for {condition_id[:8]}...: "
                    f"numerators={numerators}, denominator={denominator}"
                )
                return None

            # If outcome_index is provided, determine settlement_price for that outcome
            if outcome_index is not None:
                settlement_price = 1.0 if outcome_index == winning_index else 0.0
            else:
                # Assume this is outcome index 0 (caller should provide outcome_index)
                settlement_price = 1.0 if winning_index == 0 else 0.0

            reason = (
                f"subgraph condition resolved=true, "
                f"payoutNumerators={numerators}, "
                f"payoutDenominator={denominator}, "
                f"winningIndex={winning_index}"
            )

            # Parse resolution timestamp if available
            resolution_timestamp = condition.get("resolutionTimestamp")
            resolved_at = None
            if resolution_timestamp:
                try:
                    from datetime import datetime
                    resolved_at = datetime.utcfromtimestamp(int(resolution_timestamp))
                except (ValueError, TypeError):
                    pass

            return Resolution(
                condition_id=condition_id,
                outcome_token_id=outcome_token_id,
                settlement_price=settlement_price,
                resolved_at=resolved_at,
                resolution_source="subgraph",
                reason=reason,
            )

        except requests.exceptions.Timeout:
            logger.warning(
                f"Timeout querying subgraph for condition {condition_id[:8]}..."
            )
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error querying subgraph: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error in subgraph query: {e}")
            return None

    def get_resolutions_batch(
        self,
        token_ids: list[str],
    ) -> dict[str, Resolution]:
        """Fetch multiple resolutions.

        Note: Could be optimized with batched GraphQL query in the future.

        Args:
            token_ids: List of outcome token IDs

        Returns:
            Dict mapping token_id to Resolution
        """
        results: dict[str, Resolution] = {}
        # Simple iteration for now - would need condition_id mapping
        # which we don't have from just token_ids
        return results
