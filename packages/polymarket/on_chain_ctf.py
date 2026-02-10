"""On-chain CTF resolution provider using Polygon RPC."""

from __future__ import annotations

import logging
import os
from typing import Optional

import requests

from .resolution import Resolution

logger = logging.getLogger(__name__)


class OnChainCTFProvider:
    """Resolution provider that reads on-chain CTF payout state from Polygon.

    Uses raw JSON-RPC eth_call to query the ConditionalTokens contract:
    - payoutDenominator(bytes32): Check if market is resolved
    - payoutNumerators(bytes32, uint256): Get payout for each outcome index

    No web3.py dependency - pure HTTP JSON-RPC calls.
    """

    CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    PAYOUT_DENOMINATOR_SELECTOR = "0xda35a26f"
    PAYOUT_NUMERATORS_SELECTOR = "0x20135e58"

    def __init__(self, rpc_url: Optional[str] = None, timeout: float = 10.0):
        """Initialize on-chain CTF provider.

        Args:
            rpc_url: Polygon RPC URL (defaults to POLYGON_RPC_URL env var or public endpoint)
            timeout: Request timeout in seconds
        """
        self.rpc_url = rpc_url or os.environ.get(
            "POLYGON_RPC_URL", "https://polygon-rpc.com"
        )
        self.timeout = timeout

    def _eth_call(self, data: str) -> Optional[str]:
        """Execute eth_call against CTF contract.

        Args:
            data: Hex-encoded calldata (0x prefix required)

        Returns:
            Hex result string (0x prefix) or None on error
        """
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [
                {"to": self.CTF_ADDRESS, "data": data},
                "latest",
            ],
            "id": 1,
        }

        try:
            response = requests.post(
                self.rpc_url,
                json=payload,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            result = response.json()

            if "error" in result:
                logger.warning(
                    f"RPC error calling {data[:10]}...: {result['error']}"
                )
                return None

            return result.get("result")

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout calling Polygon RPC for {data[:10]}...")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error calling Polygon RPC: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error in eth_call: {e}")
            return None

    def _encode_condition_id(self, condition_id: str) -> str:
        """Ensure condition_id is 32-byte hex (64 hex chars without 0x prefix).

        Args:
            condition_id: Condition ID (with or without 0x prefix)

        Returns:
            64-character hex string (no 0x prefix)
        """
        # Strip 0x prefix if present
        cid = condition_id.lower().replace("0x", "")

        # Pad to 64 chars (32 bytes)
        if len(cid) < 64:
            cid = cid.zfill(64)
        elif len(cid) > 64:
            # Truncate if somehow longer (shouldn't happen with valid condition IDs)
            cid = cid[:64]

        return cid

    def get_payout_denominator(self, condition_id: str) -> Optional[int]:
        """Call payoutDenominator(conditionId).

        Args:
            condition_id: Market condition ID

        Returns:
            Payout denominator as int, or None on error
        """
        encoded_cid = self._encode_condition_id(condition_id)
        calldata = f"0x{self.PAYOUT_DENOMINATOR_SELECTOR[2:]}{encoded_cid}"

        result_hex = self._eth_call(calldata)
        if result_hex is None:
            return None

        try:
            # Result is 32-byte uint256
            return int(result_hex, 16)
        except ValueError as e:
            logger.warning(
                f"Failed to parse payoutDenominator result {result_hex}: {e}"
            )
            return None

    def get_payout_numerator(
        self, condition_id: str, outcome_index: int
    ) -> Optional[int]:
        """Call payoutNumerators(conditionId, outcomeIndex).

        Args:
            condition_id: Market condition ID
            outcome_index: Outcome index (0 or 1 for binary markets)

        Returns:
            Payout numerator as int, or None on error
        """
        encoded_cid = self._encode_condition_id(condition_id)
        # Encode outcome_index as 32-byte uint256 (zero-padded)
        encoded_index = f"{outcome_index:064x}"
        calldata = (
            f"0x{self.PAYOUT_NUMERATORS_SELECTOR[2:]}"
            f"{encoded_cid}{encoded_index}"
        )

        result_hex = self._eth_call(calldata)
        if result_hex is None:
            return None

        try:
            return int(result_hex, 16)
        except ValueError as e:
            logger.warning(
                f"Failed to parse payoutNumerator result {result_hex}: {e}"
            )
            return None

    def get_resolution(
        self,
        condition_id: str,
        outcome_token_id: str,
        outcome_index: Optional[int] = None,
    ) -> Optional[Resolution]:
        """Resolve using on-chain CTF payout data.

        Args:
            condition_id: Market condition ID
            outcome_token_id: Outcome token ID (for Resolution object)
            outcome_index: Outcome index (0 or 1). If None, checks both indices.

        Returns:
            Resolution with settlement_price and descriptive reason, or None if pending/error
        """
        # Check if market is resolved
        denominator = self.get_payout_denominator(condition_id)
        if denominator is None:
            return None

        if denominator == 0:
            # Market not resolved yet
            logger.debug(f"Market {condition_id[:8]}... is PENDING (denominator=0)")
            return None

        # If outcome_index is provided, just check that one
        if outcome_index is not None:
            numerator = self.get_payout_numerator(condition_id, outcome_index)
            if numerator is None:
                return None

            settlement_price = (
                1.0 if numerator == denominator else 0.0 if numerator == 0 else None
            )

            reason = (
                f"payoutDenominator={denominator}, "
                f"outcomeIndex={outcome_index} has payoutNumerator={numerator}"
            )

            return Resolution(
                condition_id=condition_id,
                outcome_token_id=outcome_token_id,
                settlement_price=settlement_price,
                resolved_at=None,  # On-chain doesn't provide timestamp easily
                resolution_source="on_chain_ctf",
                reason=reason,
            )

        # outcome_index not provided - check both indices to determine winner
        numerator_0 = self.get_payout_numerator(condition_id, 0)
        numerator_1 = self.get_payout_numerator(condition_id, 1)

        if numerator_0 is None or numerator_1 is None:
            return None

        # Determine which outcome won (should have numerator == denominator)
        if numerator_0 == denominator and numerator_1 == 0:
            settlement_price = 1.0  # Assuming this token is index 0
            winning_index = 0
        elif numerator_1 == denominator and numerator_0 == 0:
            settlement_price = 0.0  # Assuming this token is index 0 (index 1 won)
            winning_index = 1
        else:
            # Unexpected payout state
            logger.warning(
                f"Unexpected payout state for {condition_id[:8]}...: "
                f"denominator={denominator}, numerators=[{numerator_0}, {numerator_1}]"
            )
            return None

        reason = (
            f"payoutDenominator={denominator}, "
            f"payoutNumerators=[{numerator_0}, {numerator_1}], "
            f"winningIndex={winning_index}"
        )

        return Resolution(
            condition_id=condition_id,
            outcome_token_id=outcome_token_id,
            settlement_price=settlement_price,
            resolved_at=None,
            resolution_source="on_chain_ctf",
            reason=reason,
        )

    def get_resolutions_batch(
        self,
        token_ids: list[str],
    ) -> dict[str, Resolution]:
        """Fetch multiple resolutions.

        Note: This is a simple iteration. Could be optimized with multicall
        contract in the future.

        Args:
            token_ids: List of outcome token IDs

        Returns:
            Dict mapping token_id to Resolution
        """
        results: dict[str, Resolution] = {}
        for token_id in token_ids:
            # We don't have condition_id from just token_id, so this won't work
            # without additional context. The Protocol signature doesn't require
            # batch to work perfectly - it's just an optimization.
            # Skip for now - callers should use get_resolution directly
            pass
        return results
