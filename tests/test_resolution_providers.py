"""Unit tests for resolution providers (OnChainCTF, Subgraph, CachedResolutionProvider)."""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Ensure project root is on sys.path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from packages.polymarket.on_chain_ctf import OnChainCTFProvider
from packages.polymarket.subgraph import SubgraphResolutionProvider
from packages.polymarket.resolution import (
    CachedResolutionProvider,
    Resolution,
    ClickHouseResolutionProvider,
    GammaResolutionProvider,
)


def mock_rpc_response(result_hex: str):
    """Helper to build a mock JSON-RPC response."""
    resp = MagicMock()
    resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": result_hex}
    resp.raise_for_status = MagicMock()
    return resp


class TestOnChainCTFProvider(unittest.TestCase):
    """Tests for OnChainCTFProvider."""

    def test_onchain_resolved_win(self):
        """Test on-chain resolution for winning outcome."""
        provider = OnChainCTFProvider()

        with patch("requests.post") as mock_post:
            # Mock responses for: denominator, numerator(0), numerator(1)
            mock_post.side_effect = [
                mock_rpc_response(hex(1000000)),  # denominator = 1000000
                mock_rpc_response(hex(1000000)),  # numerator[0] = 1000000 (winner)
                mock_rpc_response(hex(0)),        # numerator[1] = 0
            ]

            resolution = provider.get_resolution(
                condition_id="0xabc123",
                outcome_token_id="token1",
                outcome_index=0,
            )

            self.assertIsNotNone(resolution)
            self.assertEqual(resolution.settlement_price, 1.0)
            self.assertEqual(resolution.resolution_source, "on_chain_ctf")
            self.assertIn("payoutDenominator", resolution.reason)
            self.assertIn("payoutNumerator", resolution.reason)

    def test_onchain_resolved_loss(self):
        """Test on-chain resolution for losing outcome."""
        provider = OnChainCTFProvider()

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                mock_rpc_response(hex(1000000)),  # denominator = 1000000
                mock_rpc_response(hex(0)),        # numerator[1] = 0 (loser)
            ]

            resolution = provider.get_resolution(
                condition_id="0xabc123",
                outcome_token_id="token2",
                outcome_index=1,
            )

            self.assertIsNotNone(resolution)
            self.assertEqual(resolution.settlement_price, 0.0)
            self.assertEqual(resolution.resolution_source, "on_chain_ctf")

    def test_onchain_pending(self):
        """Test on-chain resolution for pending (unresolved) market."""
        provider = OnChainCTFProvider()

        with patch("requests.post") as mock_post:
            mock_post.return_value = mock_rpc_response(hex(0))  # denominator = 0

            resolution = provider.get_resolution(
                condition_id="0xabc123",
                outcome_token_id="token1",
                outcome_index=0,
            )

            self.assertIsNone(resolution)  # PENDING returns None

    def test_onchain_rpc_error(self):
        """Test graceful handling of RPC errors."""
        provider = OnChainCTFProvider()

        with patch("requests.post") as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.Timeout()

            resolution = provider.get_resolution(
                condition_id="0xabc123",
                outcome_token_id="token1",
                outcome_index=0,
            )

            self.assertIsNone(resolution)  # Timeout returns None

    def test_onchain_no_outcome_index(self):
        """Test on-chain resolution without outcome_index (queries both)."""
        provider = OnChainCTFProvider()

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                mock_rpc_response(hex(1000000)),  # denominator
                mock_rpc_response(hex(1000000)),  # numerator[0] = winner
                mock_rpc_response(hex(0)),        # numerator[1] = loser
            ]

            resolution = provider.get_resolution(
                condition_id="0xabc123",
                outcome_token_id="token1",
                # No outcome_index provided
            )

            self.assertIsNotNone(resolution)
            self.assertEqual(resolution.settlement_price, 1.0)  # index 0 won
            self.assertIn("winningIndex=0", resolution.reason)


class TestSubgraphResolutionProvider(unittest.TestCase):
    """Tests for SubgraphResolutionProvider."""

    def test_subgraph_resolved(self):
        """Test subgraph resolution for resolved market."""
        provider = SubgraphResolutionProvider()

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": {
                    "condition": {
                        "id": "abc123",
                        "resolved": True,
                        "payoutNumerators": ["1000000", "0"],
                        "payoutDenominator": "1000000",
                        "resolutionTimestamp": "1700000000",
                    }
                }
            }
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            resolution = provider.get_resolution(
                condition_id="0xabc123",
                outcome_token_id="token1",
                outcome_index=0,
            )

            self.assertIsNotNone(resolution)
            self.assertEqual(resolution.settlement_price, 1.0)
            self.assertEqual(resolution.resolution_source, "subgraph")
            self.assertIn("winningIndex", resolution.reason)

    def test_subgraph_not_resolved(self):
        """Test subgraph when market not resolved."""
        provider = SubgraphResolutionProvider()

        with patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "data": {
                    "condition": {
                        "id": "abc123",
                        "resolved": False,
                        "payoutNumerators": [],
                        "payoutDenominator": "0",
                    }
                }
            }
            mock_resp.raise_for_status = MagicMock()
            mock_post.return_value = mock_resp

            resolution = provider.get_resolution(
                condition_id="0xabc123",
                outcome_token_id="token1",
                outcome_index=0,
            )

            self.assertIsNone(resolution)

    def test_subgraph_error(self):
        """Test graceful handling of connection errors."""
        provider = SubgraphResolutionProvider()

        with patch("requests.post") as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.ConnectionError()

            resolution = provider.get_resolution(
                condition_id="0xabc123",
                outcome_token_id="token1",
                outcome_index=0,
            )

            self.assertIsNone(resolution)


class TestCachedResolutionProviderChain(unittest.TestCase):
    """Tests for CachedResolutionProvider chain."""

    def test_chain_clickhouse_hit(self):
        """Test chain stops at ClickHouse when it returns a result."""
        mock_ch = MagicMock(spec=ClickHouseResolutionProvider)
        mock_ch.get_resolution.return_value = Resolution(
            condition_id="cid",
            outcome_token_id="tid",
            settlement_price=1.0,
            resolved_at=None,
            resolution_source="clickhouse_cache",
            reason="cached",
        )

        mock_onchain = MagicMock(spec=OnChainCTFProvider)
        mock_subgraph = MagicMock(spec=SubgraphResolutionProvider)
        mock_gamma = MagicMock(spec=GammaResolutionProvider)

        provider = CachedResolutionProvider(
            clickhouse_provider=mock_ch,
            on_chain_ctf_provider=mock_onchain,
            subgraph_provider=mock_subgraph,
            gamma_provider=mock_gamma,
        )

        resolution = provider.get_resolution("cid", "tid")

        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.resolution_source, "clickhouse_cache")
        mock_ch.get_resolution.assert_called_once()
        mock_onchain.get_resolution.assert_not_called()
        mock_subgraph.get_resolution.assert_not_called()
        mock_gamma.get_resolution.assert_not_called()

    def test_chain_falls_through_to_onchain(self):
        """Test chain falls through to OnChainCTF when ClickHouse returns None."""
        mock_ch = MagicMock(spec=ClickHouseResolutionProvider)
        mock_ch.get_resolution.return_value = None

        mock_onchain = MagicMock(spec=OnChainCTFProvider)
        mock_onchain.get_resolution.return_value = Resolution(
            condition_id="cid",
            outcome_token_id="tid",
            settlement_price=1.0,
            resolved_at=None,
            resolution_source="on_chain_ctf",
            reason="onchain",
        )

        mock_subgraph = MagicMock(spec=SubgraphResolutionProvider)
        mock_gamma = MagicMock(spec=GammaResolutionProvider)

        provider = CachedResolutionProvider(
            clickhouse_provider=mock_ch,
            on_chain_ctf_provider=mock_onchain,
            subgraph_provider=mock_subgraph,
            gamma_provider=mock_gamma,
        )

        resolution = provider.get_resolution("cid", "tid")

        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.resolution_source, "on_chain_ctf")
        mock_ch.get_resolution.assert_called_once()
        mock_onchain.get_resolution.assert_called_once()
        mock_subgraph.get_resolution.assert_not_called()
        mock_gamma.get_resolution.assert_not_called()

    def test_chain_falls_through_to_subgraph(self):
        """Test chain falls through to Subgraph when ClickHouse and OnChainCTF return None."""
        mock_ch = MagicMock(spec=ClickHouseResolutionProvider)
        mock_ch.get_resolution.return_value = None

        mock_onchain = MagicMock(spec=OnChainCTFProvider)
        mock_onchain.get_resolution.return_value = None

        mock_subgraph = MagicMock(spec=SubgraphResolutionProvider)
        mock_subgraph.get_resolution.return_value = Resolution(
            condition_id="cid",
            outcome_token_id="tid",
            settlement_price=1.0,
            resolved_at=None,
            resolution_source="subgraph",
            reason="subgraph",
        )

        mock_gamma = MagicMock(spec=GammaResolutionProvider)

        provider = CachedResolutionProvider(
            clickhouse_provider=mock_ch,
            on_chain_ctf_provider=mock_onchain,
            subgraph_provider=mock_subgraph,
            gamma_provider=mock_gamma,
        )

        resolution = provider.get_resolution("cid", "tid")

        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.resolution_source, "subgraph")
        mock_ch.get_resolution.assert_called_once()
        mock_onchain.get_resolution.assert_called_once()
        mock_subgraph.get_resolution.assert_called_once()
        mock_gamma.get_resolution.assert_not_called()

    def test_chain_falls_through_to_gamma(self):
        """Test chain falls through to Gamma when all prior providers return None."""
        mock_ch = MagicMock(spec=ClickHouseResolutionProvider)
        mock_ch.get_resolution.return_value = None

        mock_onchain = MagicMock(spec=OnChainCTFProvider)
        mock_onchain.get_resolution.return_value = None

        mock_subgraph = MagicMock(spec=SubgraphResolutionProvider)
        mock_subgraph.get_resolution.return_value = None

        mock_gamma = MagicMock(spec=GammaResolutionProvider)
        mock_gamma.get_resolution.return_value = Resolution(
            condition_id="cid",
            outcome_token_id="tid",
            settlement_price=1.0,
            resolved_at=None,
            resolution_source="gamma",
            reason="gamma",
        )

        provider = CachedResolutionProvider(
            clickhouse_provider=mock_ch,
            on_chain_ctf_provider=mock_onchain,
            subgraph_provider=mock_subgraph,
            gamma_provider=mock_gamma,
        )

        resolution = provider.get_resolution("cid", "tid")

        self.assertIsNotNone(resolution)
        self.assertEqual(resolution.resolution_source, "gamma")
        mock_ch.get_resolution.assert_called_once()
        mock_onchain.get_resolution.assert_called_once()
        mock_subgraph.get_resolution.assert_called_once()
        mock_gamma.get_resolution.assert_called_once()

    def test_chain_all_none(self):
        """Test chain returns None when all providers return None."""
        mock_ch = MagicMock(spec=ClickHouseResolutionProvider)
        mock_ch.get_resolution.return_value = None

        mock_onchain = MagicMock(spec=OnChainCTFProvider)
        mock_onchain.get_resolution.return_value = None

        mock_subgraph = MagicMock(spec=SubgraphResolutionProvider)
        mock_subgraph.get_resolution.return_value = None

        mock_gamma = MagicMock(spec=GammaResolutionProvider)
        mock_gamma.get_resolution.return_value = None

        provider = CachedResolutionProvider(
            clickhouse_provider=mock_ch,
            on_chain_ctf_provider=mock_onchain,
            subgraph_provider=mock_subgraph,
            gamma_provider=mock_gamma,
        )

        resolution = provider.get_resolution("cid", "tid")

        self.assertIsNone(resolution)
        mock_ch.get_resolution.assert_called_once()
        mock_onchain.get_resolution.assert_called_once()
        mock_subgraph.get_resolution.assert_called_once()
        mock_gamma.get_resolution.assert_called_once()


if __name__ == "__main__":
    unittest.main()
