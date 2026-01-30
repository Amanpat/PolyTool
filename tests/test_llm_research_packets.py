import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.llm_research_packets import export_user_dossier


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _FakeClickhouseClient:
    def __init__(self):
        self.inserts = []
        self.now = datetime(2026, 1, 15, 12, 0, 0)
        self.snapshot_ts = datetime(2026, 1, 14, 8, 0, 0)

    def query(self, query, parameters=None):
        if "FROM user_trades_resolved" in query and "countDistinct" in query:
            return _FakeResult([[3, 2, 1, 2, 2]])
        if "FROM user_activity_resolved" in query:
            return _FakeResult([[4]])
        if "FROM user_positions_resolved" in query and "max(snapshot_ts)" in query:
            return _FakeResult([[self.snapshot_ts]])
        if "FROM user_positions_resolved" in query and "snapshot_ts = {snapshot:DateTime}" in query:
            return _FakeResult([[2]])
        if "bucket_0_25" in query:
            return _FakeResult([[1, 1, 1, 0, 0, 0]])
        if "GROUP BY category" in query:
            return _FakeResult([["Sports", 2, 150.0]])
        if "GROUP BY market_slug" in query:
            return _FakeResult([["market-a", 2, 150.0]])
        if "quantileExactIf(0.5)" in query and "first_buy" in query:
            return _FakeResult([[3600, 7200, 2]])
        if "FROM user_pnl_bucket" in query and "LIMIT 1" in query:
            return _FakeResult([[self.now, 10.0, 5.0, 100.0, 0.7, "HIGH"]])
        if "FROM user_pnl_bucket" in query and "ORDER BY bucket_start ASC" in query:
            return _FakeResult([
                [self.now - timedelta(days=2), 1.0, 0.5, 50.0],
                [self.now - timedelta(days=1), 2.0, 1.0, 60.0],
            ])
        if "FROM detector_results" in query and "GROUP BY detector_name" in query:
            return _FakeResult([["HOLDING_STYLE", 0.8, "SCALPER", self.now]])
        if "FROM detector_results" in query and "ORDER BY detector_name" in query:
            return _FakeResult([
                ["HOLDING_STYLE", self.now - timedelta(days=1), 0.7, "SCALPER"],
                ["HOLDING_STYLE", self.now, 0.8, "SCALPER"],
            ])
        if "FROM orderbook_snapshots_enriched" in query and "sumIf(1, status = 'ok')" in query:
            return _FakeResult([[5, 3, 1, 0, 1, 0, 2, 50.0, 80.0]])
        if "ORDER BY median_exec_cost DESC" in query:
            return _FakeResult([[
                "tokenA", "market-a", "Question A", "Yes", 120.0, 180.0, 4
            ]])
        if "ORDER BY median_exec_cost ASC" in query:
            return _FakeResult([[
                "tokenB", "market-b", "Question B", "No", 20.0, 40.0, 3
            ]])
        if "quantileExact(0.95)" in query:
            return _FakeResult([[120.0]])
        if "ORDER BY ts DESC" in query:
            return _FakeResult([
                ["uid3", self.now, "tokenC", "tokenC", "market-c", "Question C", "Yes", "buy", 0.2, 50.0, 10.0, "tx3"],
                ["uid2", self.now - timedelta(hours=1), "tokenB", "tokenB", "market-b", "Question B", "No", "sell", 0.6, 20.0, 12.0, "tx2"],
                ["uid1", self.now - timedelta(hours=2), "tokenA", "tokenA", "market-a", "Question A", "Yes", "buy", 0.4, 10.0, 4.0, "tx1"],
            ])
        if "ORDER BY notional DESC" in query and "min_notional" in query:
            return _FakeResult([
                ["uid2", self.now - timedelta(hours=1), "tokenB", "tokenB", "market-b", "Question B", "No", "sell", 0.6, 20.0, 12.0, "tx2"],
            ])
        if "ORDER BY notional DESC" in query:
            return _FakeResult([
                ["uid2", self.now - timedelta(hours=1), "tokenB", "tokenB", "market-b", "Question B", "No", "sell", 0.6, 20.0, 12.0, "tx2"],
                ["uid3", self.now, "tokenC", "tokenC", "market-c", "Question C", "Yes", "buy", 0.2, 50.0, 10.0, "tx3"],
            ])
        return _FakeResult([])

    def insert(self, table, rows, column_names=None):
        self.inserts.append({"table": table, "rows": rows, "column_names": column_names})


class ResearchPacketExportTests(unittest.TestCase):
    def test_export_builds_expected_artifacts(self) -> None:
        client = _FakeClickhouseClient()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = export_user_dossier(
                clickhouse_client=client,
                proxy_wallet="0xabc",
                user_input="@tester",
                window_days=30,
                max_trades=3,
                artifacts_base_path=tmpdir,
                generated_at=client.now,
            )

        self.assertIn("header", result.dossier)
        self.assertIn("coverage", result.dossier)
        self.assertIn("pnl_summary", result.dossier)
        self.assertIn("distributions", result.dossier)
        self.assertIn("liquidity_summary", result.dossier)
        self.assertIn("detectors", result.dossier)
        self.assertIn("anchors", result.dossier)
        self.assertLessEqual(len(result.anchor_trade_uids), 3)

        memo = result.memo_md
        self.assertIn("## Executive Summary", memo)
        self.assertIn("## Data Coverage & Caveats", memo)
        self.assertIn("## Key Observations", memo)
        self.assertIn("## Hypotheses", memo)
        self.assertIn("## What changed recently", memo)
        self.assertIn("## Next features to compute", memo)
        self.assertIn("## Evidence anchors", memo)

        self.assertTrue(client.inserts)
        insert = client.inserts[0]
        self.assertEqual(insert["table"], "user_dossier_exports")
        self.assertIn("export_id", insert["column_names"])
        self.assertIn("proxy_wallet", insert["column_names"])
        self.assertIn("generated_at", insert["column_names"])
        self.assertIn("dossier_json", insert["column_names"])
        dossier_index = insert["column_names"].index("dossier_json")
        self.assertTrue(insert["rows"][0][dossier_index])


if __name__ == "__main__":
    unittest.main()
