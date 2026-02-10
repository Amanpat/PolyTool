import json
import os
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.llm_research_packets import export_user_dossier


def _reject_json_constant(value: str):
    raise ValueError(f"Non-standard JSON constant encountered: {value}")


def _strict_json_loads(payload: str):
    return json.loads(payload, parse_constant=_reject_json_constant)


def _latest_drpufferfish_dossier_path() -> Path:
    root = Path(__file__).resolve().parents[1] / "artifacts" / "dossiers" / "users" / "drpufferfish"
    candidates = sorted(root.rglob("dossier.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise AssertionError(f"No dossier artifacts found under {root}")
    return candidates[0]


def _load_real_fixture_positions():
    dossier_path = _latest_drpufferfish_dossier_path()
    dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    positions = dossier.get("positions", {}).get("positions", [])

    pending = next(
        (
            pos
            for pos in positions
            if pos.get("resolution_outcome") == "PENDING" and int(pos.get("sell_count") or 0) == 0
        ),
        None,
    )
    win = next((pos for pos in positions if pos.get("resolution_outcome") == "WIN"), None)
    loss = next((pos for pos in positions if pos.get("resolution_outcome") == "LOSS"), None)

    if pending is None:
        raise AssertionError(f"No pending sell_count==0 position found in {dossier_path}")
    if win is None or loss is None:
        raise AssertionError(f"Expected WIN and LOSS fixtures in {dossier_path}")
    return dict(pending), dict(win), dict(loss)


def _load_known_pending_suns_position() -> dict:
    dossier_path = _latest_drpufferfish_dossier_path()
    dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    positions = dossier.get("positions", {}).get("positions", [])
    known_slug = "will-the-phoenix-suns-win-the-2026-nba-finals"
    known = next(
        (
            pos
            for pos in positions
            if pos.get("market_slug") == known_slug
            and pos.get("resolution_outcome") == "PENDING"
            and int(pos.get("sell_count") or 0) == 0
        ),
        None,
    )
    if known is None:
        raise AssertionError(f"No known Suns pending position found in {dossier_path}")
    return dict(known)


def _parse_iso8601(ts: str | None):
    if not ts:
        return None
    text = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


@contextmanager
def _workspace_tempdir():
    root = Path("artifacts") / "_tmp_pytest_workspace" / uuid.uuid4().hex
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    try:
        yield str(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _position_to_lifecycle_row(position: dict):
    return [
        position.get("resolved_token_id", ""),
        position.get("market_slug", ""),
        position.get("question", ""),
        position.get("outcome_name", ""),
        _parse_iso8601(position.get("entry_ts")),
        position.get("entry_price"),
        position.get("total_bought"),
        position.get("total_cost"),
        _parse_iso8601(position.get("exit_ts")),
        position.get("exit_price"),
        position.get("total_sold"),
        position.get("total_proceeds"),
        position.get("hold_duration_seconds"),
        position.get("position_remaining"),
        position.get("trade_count"),
        position.get("buy_count"),
        position.get("sell_count"),
        position.get("settlement_price"),
        _parse_iso8601(position.get("resolved_at")),
        position.get("resolution_source", ""),
        position.get("resolution_outcome", "UNKNOWN_RESOLUTION"),
        position.get("gross_pnl"),
        position.get("realized_pnl_net"),
        position.get("fees_actual", 0.0),
        position.get("fees_estimated", 0.0),
        position.get("fees_source", "unknown"),
    ]


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _FakeClickhouseClient:
    def __init__(self, lifecycle_rows=None):
        self.inserts = []
        self.now = datetime(2026, 1, 15, 12, 0, 0)
        self.snapshot_ts = datetime(2026, 1, 14, 8, 0, 0)
        self.lifecycle_rows = lifecycle_rows or []

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
        if "FROM user_trade_lifecycle_enriched" in query:
            return _FakeResult(self.lifecycle_rows)
        return _FakeResult([])

    def insert(self, table, rows, column_names=None):
        self.inserts.append({"table": table, "rows": rows, "column_names": column_names})


class ResearchPacketExportTests(unittest.TestCase):
    def test_export_builds_expected_artifacts(self) -> None:
        client = _FakeClickhouseClient()
        with _workspace_tempdir() as tmpdir:
            result = export_user_dossier(
                clickhouse_client=client,
                proxy_wallet="0xabc",
                user_input="@tester",
                username="@Tester",
                window_days=30,
                max_trades=3,
                artifacts_base_path=tmpdir,
                generated_at=client.now,
            )
            date_label = client.now.strftime("%Y-%m-%d")
            expected_prefix = os.path.join(
                tmpdir,
                "dossiers",
                "users",
                "tester",
                "0xabc",
                date_label,
                result.export_id,
            )
            self.assertTrue(os.path.normpath(result.artifact_path).endswith(os.path.normpath(expected_prefix)))
            self.assertIn(os.path.join("dossiers", "users", "tester", "0xabc"), result.path_json)

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
        self.assertIn("username", insert["column_names"])
        self.assertIn("username_slug", insert["column_names"])
        self.assertIn("artifact_path", insert["column_names"])
        self.assertIn("generated_at", insert["column_names"])
        self.assertIn("dossier_json", insert["column_names"])
        dossier_index = insert["column_names"].index("dossier_json")
        self.assertTrue(insert["rows"][0][dossier_index])

    def test_pending_position_no_sells_realized_zero(self) -> None:
        pending = _load_known_pending_suns_position()
        client = _FakeClickhouseClient(lifecycle_rows=[_position_to_lifecycle_row(pending)])

        with _workspace_tempdir() as tmpdir:
            result = export_user_dossier(
                clickhouse_client=client,
                proxy_wallet="0xabc",
                user_input="@tester",
                username="@Tester",
                window_days=30,
                max_trades=3,
                artifacts_base_path=tmpdir,
                generated_at=client.now,
            )

        positions = result.dossier.get("positions", {}).get("positions", [])
        pending_row = next((row for row in positions if row.get("resolution_outcome") == "PENDING"), None)
        self.assertIsNotNone(pending_row)
        self.assertEqual(
            pending_row["market_slug"],
            "will-the-phoenix-suns-win-the-2026-nba-finals",
        )
        self.assertEqual(pending_row["sell_count"], 0)
        self.assertIsNone(pending_row["settlement_price"])
        self.assertIsNone(pending_row["exit_ts"])
        self.assertIsNone(pending_row["exit_price"])
        self.assertIsNone(pending_row["resolved_at"])
        self.assertEqual(pending_row["gross_pnl"], 0.0)
        self.assertEqual(pending_row["realized_pnl_net"], 0.0)
        self.assertGreaterEqual(pending_row["hold_duration_seconds"], 0)

    def test_dossier_json_no_nan(self) -> None:
        pending, win, loss = _load_real_fixture_positions()
        lifecycle_rows = [
            _position_to_lifecycle_row(pending),
            _position_to_lifecycle_row(win),
            _position_to_lifecycle_row(loss),
        ]
        client = _FakeClickhouseClient(lifecycle_rows=lifecycle_rows)

        with _workspace_tempdir() as tmpdir:
            result = export_user_dossier(
                clickhouse_client=client,
                proxy_wallet="0xabc",
                user_input="@tester",
                username="@Tester",
                window_days=30,
                max_trades=3,
                artifacts_base_path=tmpdir,
                generated_at=client.now,
            )
            dossier_text = Path(result.path_json).read_text(encoding="utf-8")

        self.assertNotIn("NaN", dossier_text)
        self.assertNotIn("1970-01-01T00:00:00Z", dossier_text)
        parsed = _strict_json_loads(dossier_text)
        parsed_positions = parsed.get("positions", {}).get("positions", [])
        for row in parsed_positions:
            if row.get("sell_count") == 0:
                self.assertIsNone(row.get("exit_price"))

    def test_hold_duration_non_negative(self) -> None:
        _, win, loss = _load_real_fixture_positions()
        lifecycle_rows = [
            _position_to_lifecycle_row(win),
            _position_to_lifecycle_row(loss),
        ]
        client = _FakeClickhouseClient(lifecycle_rows=lifecycle_rows)

        with _workspace_tempdir() as tmpdir:
            result = export_user_dossier(
                clickhouse_client=client,
                proxy_wallet="0xabc",
                user_input="@tester",
                username="@Tester",
                window_days=30,
                max_trades=3,
                artifacts_base_path=tmpdir,
                generated_at=client.now,
            )

        by_outcome = {
            row["resolution_outcome"]: row
            for row in result.dossier.get("positions", {}).get("positions", [])
        }
        self.assertIn("WIN", by_outcome)
        self.assertIn("LOSS", by_outcome)

        for fixture in (win, loss):
            outcome = fixture["resolution_outcome"]
            row = by_outcome[outcome]
            self.assertGreaterEqual(row["hold_duration_seconds"], 0)

            entry_ts = _parse_iso8601(fixture.get("entry_ts"))
            resolved_at = _parse_iso8601(fixture.get("resolved_at"))
            self.assertIsNotNone(entry_ts)
            self.assertIsNotNone(resolved_at)
            expected = max(0, int((resolved_at - entry_ts).total_seconds()))
            self.assertEqual(row["hold_duration_seconds"], expected)


if __name__ == "__main__":
    unittest.main()
