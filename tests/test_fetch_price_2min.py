"""Offline tests for fetch-price-2min CLI and FetchAndIngestEngine.

All tests are fully offline: no real HTTP requests, no ClickHouse connection.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from packages.polymarket.price_2min_fetcher import (
    FetchAndIngestEngine,
    FetchConfig,
    FetchResult,
    normalize_rows,
)
from tools.cli.fetch_price_2min import main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SAMPLE_HISTORY = [
    {"t": 1700000000, "p": 0.55},
    {"t": 1700000120, "p": 0.57},
    {"t": 1700000240, "p": 0.58},
]

_TOKEN_A = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_TOKEN_B = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def _make_fetch_fn(responses: Dict[str, List[Dict[str, Any]]]):
    """Return a fake fetch function that returns canned responses per token_id."""
    def _fetch(token_id: str) -> List[Dict[str, Any]]:
        return responses.get(token_id, [])
    return _fetch


def _make_ch_client():
    """Return a mock CH client that records calls."""
    client = MagicMock()
    client.insert_rows.return_value = 0  # will be overridden per call
    return client


# ---------------------------------------------------------------------------
# normalize_rows: shape and type contracts
# ---------------------------------------------------------------------------


class TestNormalizeRows:
    def test_basic_shape(self):
        rows = normalize_rows(_TOKEN_A, _SAMPLE_HISTORY, "run-001")
        assert len(rows) == 3
        # Each row: [token_id, ts, price, source, import_run_id]
        assert rows[0][0] == _TOKEN_A
        assert isinstance(rows[0][1], datetime)
        assert rows[0][1].tzinfo is not None  # timezone-aware
        assert isinstance(rows[0][2], float)
        assert rows[0][3] == "clob_api"
        assert rows[0][4] == "run-001"

    def test_epoch_timestamp_converts_to_utc(self):
        rows = normalize_rows(_TOKEN_A, [{"t": 0, "p": 0.5}], "r")
        assert rows[0][1] == datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    def test_price_as_string(self):
        rows = normalize_rows(_TOKEN_A, [{"t": 1700000000, "p": "0.72"}], "r")
        assert rows[0][2] == pytest.approx(0.72)

    def test_skips_null_timestamp(self):
        records = [
            {"t": None, "p": 0.5},
            {"t": 1700000000, "p": 0.6},
        ]
        rows = normalize_rows(_TOKEN_A, records, "r")
        assert len(rows) == 1
        assert rows[0][2] == pytest.approx(0.6)

    def test_skips_missing_timestamp(self):
        rows = normalize_rows(_TOKEN_A, [{"p": 0.5}], "r")
        assert rows == []

    def test_skips_non_dict_records(self):
        rows = normalize_rows(_TOKEN_A, [None, "bad", 42, {"t": 1700000000, "p": 0.5}], "r")
        assert len(rows) == 1

    def test_empty_history(self):
        assert normalize_rows(_TOKEN_A, [], "r") == []

    def test_iso_timestamp(self):
        rows = normalize_rows(_TOKEN_A, [{"t": "2024-01-01T00:00:00Z", "p": 0.3}], "r")
        assert len(rows) == 1
        assert rows[0][1].year == 2024

    def test_preserves_run_id(self):
        rows = normalize_rows(_TOKEN_A, _SAMPLE_HISTORY, "my-run-xyz")
        assert all(r[4] == "my-run-xyz" for r in rows)


# ---------------------------------------------------------------------------
# FetchAndIngestEngine: dry-run mode
# ---------------------------------------------------------------------------


class TestEngineWithDryRun:
    def _engine(self, responses=None):
        fetch_fn = _make_fetch_fn(responses or {_TOKEN_A: _SAMPLE_HISTORY})
        return FetchAndIngestEngine(_fetch_fn=fetch_fn)

    def test_dry_run_returns_result(self):
        engine = self._engine()
        result = engine.run([_TOKEN_A], dry_run=True)
        assert isinstance(result, FetchResult)
        assert result.import_mode == "dry-run"

    def test_dry_run_counts_fetched_rows(self):
        engine = self._engine()
        result = engine.run([_TOKEN_A], dry_run=True)
        assert result.total_rows_fetched == 3
        assert result.tokens[0].rows_fetched == 3

    def test_dry_run_does_not_insert(self):
        ch = _make_ch_client()
        fetch_fn = _make_fetch_fn({_TOKEN_A: _SAMPLE_HISTORY})
        engine = FetchAndIngestEngine(_fetch_fn=fetch_fn, _ch_client=ch)
        engine.run([_TOKEN_A], dry_run=True)
        ch.insert_rows.assert_not_called()

    def test_dry_run_inserted_count_is_zero(self):
        engine = self._engine()
        result = engine.run([_TOKEN_A], dry_run=True)
        assert result.total_rows_inserted == 0
        assert result.tokens[0].rows_inserted == 0

    def test_multiple_tokens_dry_run(self):
        fetch_fn = _make_fetch_fn({
            _TOKEN_A: _SAMPLE_HISTORY,
            _TOKEN_B: [{"t": 1700001000, "p": 0.4}],
        })
        engine = FetchAndIngestEngine(_fetch_fn=fetch_fn)
        result = engine.run([_TOKEN_A, _TOKEN_B], dry_run=True)
        assert result.total_rows_fetched == 4
        assert len(result.tokens) == 2

    def test_empty_history_token(self):
        fetch_fn = _make_fetch_fn({_TOKEN_A: []})
        engine = FetchAndIngestEngine(_fetch_fn=fetch_fn)
        result = engine.run([_TOKEN_A], dry_run=True)
        assert result.total_rows_fetched == 0
        assert not result.errors


# ---------------------------------------------------------------------------
# FetchAndIngestEngine: live mode
# ---------------------------------------------------------------------------


class TestEngineWithLive:
    def _engine_with_ch(self, responses=None, ch_return=None):
        fetch_fn = _make_fetch_fn(responses or {_TOKEN_A: _SAMPLE_HISTORY})
        ch = _make_ch_client()
        if ch_return is not None:
            ch.insert_rows.return_value = ch_return
        else:
            ch.insert_rows.side_effect = lambda table, cols, rows: len(rows)
        return FetchAndIngestEngine(_fetch_fn=fetch_fn, _ch_client=ch), ch

    def test_live_calls_insert_rows(self):
        engine, ch = self._engine_with_ch()
        engine.run([_TOKEN_A], dry_run=False)
        ch.insert_rows.assert_called_once()

    def test_live_inserts_correct_table(self):
        engine, ch = self._engine_with_ch()
        engine.run([_TOKEN_A], dry_run=False)
        call_args = ch.insert_rows.call_args
        assert call_args[0][0] == "polytool.price_2min"

    def test_live_inserts_correct_columns(self):
        engine, ch = self._engine_with_ch()
        engine.run([_TOKEN_A], dry_run=False)
        call_args = ch.insert_rows.call_args
        assert call_args[0][1] == ["token_id", "ts", "price", "source", "import_run_id"]

    def test_live_inserts_correct_row_count(self):
        engine, ch = self._engine_with_ch()
        engine.run([_TOKEN_A], dry_run=False)
        call_args = ch.insert_rows.call_args
        inserted_rows = call_args[0][2]
        assert len(inserted_rows) == 3

    def test_live_result_has_run_id(self):
        engine, ch = self._engine_with_ch()
        result = engine.run([_TOKEN_A], dry_run=False, run_id="fixed-id")
        assert result.run_id == "fixed-id"

    def test_fetch_error_is_captured(self):
        def _bad_fetch(token_id):
            raise RuntimeError("network error")

        ch = _make_ch_client()
        engine = FetchAndIngestEngine(_fetch_fn=_bad_fetch, _ch_client=ch)
        result = engine.run([_TOKEN_A], dry_run=False)
        assert len(result.errors) == 1
        assert "network error" in result.errors[0]
        ch.insert_rows.assert_not_called()

    def test_to_dict_serializable(self):
        engine, _ = self._engine_with_ch()
        result = engine.run([_TOKEN_A], dry_run=False)
        d = result.to_dict()
        json.dumps(d, default=str)  # must not raise


# ---------------------------------------------------------------------------
# CLI: behavior tests (offline)
# ---------------------------------------------------------------------------


class TestFetchPrice2MinCLI:
    def _make_engine_patch(self, mocker=None, rows_fetched=3, insert_count=3):
        """Build a FetchAndIngestEngine patch that returns a canned result."""
        from packages.polymarket.price_2min_fetcher import FetchResult, TokenFetchResult

        mock_result = FetchResult(
            run_id="test-run-id",
            import_mode="dry-run",
            started_at="2026-03-16T00:00:00+00:00",
            completed_at="2026-03-16T00:00:01+00:00",
            total_rows_fetched=rows_fetched,
            total_rows_inserted=insert_count,
        )
        mock_result.tokens = [
            TokenFetchResult(
                token_id=_TOKEN_A,
                rows_fetched=rows_fetched,
                rows_inserted=insert_count,
            )
        ]
        return mock_result

    def test_help_exits_0(self):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_no_tokens_returns_1(self, capsys):
        rc = main([])
        assert rc == 1
        captured = capsys.readouterr()
        assert "no token IDs" in captured.err

    def test_dry_run_with_injected_engine(self, tmp_path):
        """Dry-run CLI with a fully mocked engine — no network, no CH."""
        fetch_fn = _make_fetch_fn({_TOKEN_A: _SAMPLE_HISTORY})
        # Patch FetchAndIngestEngine to use our fake fetch_fn
        from unittest.mock import patch

        with patch(
            "tools.cli.fetch_price_2min.FetchAndIngestEngine",
            side_effect=lambda config: FetchAndIngestEngine(_fetch_fn=fetch_fn),
        ):
            rc = main(["--token-id", _TOKEN_A, "--dry-run"])
        assert rc == 0

    def test_token_file_is_read(self, tmp_path):
        token_file = tmp_path / "tokens.txt"
        token_file.write_text(f"# comment\n{_TOKEN_A}\n{_TOKEN_B}\n", encoding="utf-8")

        fetch_fn = _make_fetch_fn({
            _TOKEN_A: _SAMPLE_HISTORY,
            _TOKEN_B: [{"t": 1700001000, "p": 0.4}],
        })
        from unittest.mock import patch

        with patch(
            "tools.cli.fetch_price_2min.FetchAndIngestEngine",
            side_effect=lambda config: FetchAndIngestEngine(_fetch_fn=fetch_fn),
        ):
            rc = main(["--token-file", str(token_file), "--dry-run"])
        assert rc == 0

    def test_bad_token_file_returns_1(self, capsys):
        rc = main(["--token-file", "/nonexistent/tokens.txt"])
        assert rc == 1
        assert "cannot read token file" in capsys.readouterr().err

    def test_out_writes_artifact(self, tmp_path):
        out_file = tmp_path / "run_record.json"
        fetch_fn = _make_fetch_fn({_TOKEN_A: _SAMPLE_HISTORY})
        from unittest.mock import patch

        with patch(
            "tools.cli.fetch_price_2min.FetchAndIngestEngine",
            side_effect=lambda config: FetchAndIngestEngine(_fetch_fn=fetch_fn),
        ):
            rc = main([
                "--token-id", _TOKEN_A,
                "--dry-run",
                "--out", str(out_file),
            ])
        assert rc == 0
        assert out_file.exists()
        payload = json.loads(out_file.read_text())
        assert "run_id" in payload
        assert payload["import_mode"] == "dry-run"

    def test_deduplicates_token_ids(self, tmp_path):
        """Repeated --token-id values should only be fetched once."""
        call_log = []

        def tracking_fetch(token_id):
            call_log.append(token_id)
            return _SAMPLE_HISTORY

        from unittest.mock import patch

        with patch(
            "tools.cli.fetch_price_2min.FetchAndIngestEngine",
            side_effect=lambda config: FetchAndIngestEngine(_fetch_fn=tracking_fetch),
        ):
            rc = main(["--token-id", _TOKEN_A, "--token-id", _TOKEN_A, "--dry-run"])
        assert rc == 0
        assert call_log.count(_TOKEN_A) == 1

    def test_fetch_error_returns_1(self, capsys):
        def _always_fail(token_id):
            raise RuntimeError("simulated network failure")

        from unittest.mock import patch

        with patch(
            "tools.cli.fetch_price_2min.FetchAndIngestEngine",
            side_effect=lambda config: FetchAndIngestEngine(_fetch_fn=_always_fail),
        ):
            rc = main(["--token-id", _TOKEN_A, "--dry-run"])
        assert rc == 1
