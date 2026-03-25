"""Tests for Track 2 / Phase 1A — market availability watcher.

All tests are offline; no network calls are made.  GammaClient is stubbed with
MagicMock.  Injectable _sleep_fn and _check_fn are used throughout to avoid
real time.sleep in watch-mode tests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from packages.polymarket.crypto_pairs.market_watch import (
    AvailabilitySummary,
    run_availability_check,
    run_watch_loop,
)
from tools.cli.crypto_pair_watch import build_parser, main, run_crypto_pair_watch


# ---------------------------------------------------------------------------
# Test helpers (mirror pattern from test_crypto_pair_scan.py)
# ---------------------------------------------------------------------------

def _make_mock_market(
    slug: str,
    question: str,
    clob_token_ids: list,
    outcomes: list,
    active: bool = True,
    accepting_orders: Optional[bool] = True,
) -> MagicMock:
    m = MagicMock()
    m.market_slug = slug
    m.question = question
    m.clob_token_ids = clob_token_ids
    m.outcomes = outcomes
    m.active = active
    m.accepting_orders = accepting_orders
    m.condition_id = f"cond_{slug}"
    m.end_date_iso = None
    return m


def _make_gamma_client(markets: list) -> MagicMock:
    result = MagicMock()
    result.markets = markets
    client = MagicMock()
    client.fetch_all_markets.return_value = result
    return client


def _make_btc_5m_market(slug: str = "btc-5m-up") -> MagicMock:
    return _make_mock_market(
        slug,
        "Will BTC be higher in 5 minutes?",
        ["yes_btc", "no_btc"],
        ["Yes", "No"],
    )


def _make_eth_15m_market(slug: str = "eth-15m-higher") -> MagicMock:
    return _make_mock_market(
        slug,
        "Will ETH go up in 15 minutes?",
        ["yes_eth", "no_eth"],
        ["Yes", "No"],
    )


def _make_irrelevant_market(slug: str = "doge-moon") -> MagicMock:
    """Market that does NOT match symbol or duration filter."""
    return _make_mock_market(
        slug,
        "Will DOGE reach the moon?",
        ["yes_doge", "no_doge"],
        ["Yes", "No"],
    )


def _not_eligible_summary() -> AvailabilitySummary:
    return AvailabilitySummary(
        eligible_now=False,
        total_eligible=0,
        by_symbol={"BTC": 0, "ETH": 0, "SOL": 0},
        by_duration={"5m": 0, "15m": 0},
        first_eligible_slugs=[],
        rejection_reason="No active BTC/ETH/SOL 5m/15m binary pair markets found",
        checked_at="2026-03-25T22:00:00+00:00",
    )


def _eligible_summary(slugs: Optional[list] = None) -> AvailabilitySummary:
    slugs = slugs or ["btc-5m-up"]
    return AvailabilitySummary(
        eligible_now=True,
        total_eligible=len(slugs),
        by_symbol={"BTC": len(slugs), "ETH": 0, "SOL": 0},
        by_duration={"5m": len(slugs), "15m": 0},
        first_eligible_slugs=slugs[:5],
        rejection_reason=None,
        checked_at="2026-03-25T22:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Test 1: No eligible markets
# ---------------------------------------------------------------------------

class TestNoEligibleMarkets:
    def test_no_eligible_markets(self):
        """Gamma returns markets but none match BTC/ETH/SOL 5m/15m."""
        gc = _make_gamma_client([_make_irrelevant_market()])
        summary = run_availability_check(gamma_client=gc)
        assert summary.eligible_now is False
        assert summary.total_eligible == 0
        assert summary.first_eligible_slugs == []
        assert summary.rejection_reason is not None
        assert "No active" in summary.rejection_reason

    def test_empty_gamma_response(self):
        """Gamma returns no markets at all."""
        gc = _make_gamma_client([])
        summary = run_availability_check(gamma_client=gc)
        assert summary.eligible_now is False
        assert summary.total_eligible == 0


# ---------------------------------------------------------------------------
# Test 2: Eligible markets present
# ---------------------------------------------------------------------------

class TestEligibleMarketsPresent:
    def test_eligible_markets_present(self):
        """Gamma returns 2 valid BTC 5m markets."""
        gc = _make_gamma_client([
            _make_btc_5m_market("btc-5m-up-1"),
            _make_btc_5m_market("btc-5m-up-2"),
        ])
        summary = run_availability_check(gamma_client=gc)
        assert summary.eligible_now is True
        assert summary.total_eligible == 2
        assert summary.by_symbol["BTC"] == 2
        assert summary.by_symbol["ETH"] == 0
        assert summary.by_symbol["SOL"] == 0
        assert summary.rejection_reason is None

    def test_eligible_markets_slugs_populated(self):
        gc = _make_gamma_client([_make_btc_5m_market("btc-5m-up")])
        summary = run_availability_check(gamma_client=gc)
        assert "btc-5m-up" in summary.first_eligible_slugs

    def test_first_eligible_slugs_capped_at_5(self):
        """At most 5 slugs returned even when more exist."""
        markets = [_make_btc_5m_market(f"btc-5m-{i}") for i in range(8)]
        gc = _make_gamma_client(markets)
        summary = run_availability_check(gamma_client=gc)
        assert len(summary.first_eligible_slugs) == 5


# ---------------------------------------------------------------------------
# Test 3: Mixed markets — irrelevant filtered
# ---------------------------------------------------------------------------

class TestMixedMarketsIrrelevantFiltered:
    def test_mixed_markets_irrelevant_filtered(self):
        """Mix of eligible (BTC 5m) and non-eligible (DOGE); counts only eligible."""
        gc = _make_gamma_client([
            _make_btc_5m_market("btc-5m-up"),
            _make_irrelevant_market("doge-moon"),
            _make_eth_15m_market("eth-15m-higher"),
        ])
        summary = run_availability_check(gamma_client=gc)
        assert summary.eligible_now is True
        assert summary.total_eligible == 2
        assert summary.by_symbol["BTC"] == 1
        assert summary.by_symbol["ETH"] == 1
        assert summary.by_duration["5m"] == 1
        assert summary.by_duration["15m"] == 1


# ---------------------------------------------------------------------------
# Test 4: AvailabilitySummary fields populated
# ---------------------------------------------------------------------------

class TestAvailabilitySummaryFieldsPopulated:
    def test_availability_summary_fields_populated(self):
        """All AvailabilitySummary fields are non-None/correct types."""
        gc = _make_gamma_client([_make_btc_5m_market()])
        summary = run_availability_check(gamma_client=gc)
        assert isinstance(summary.eligible_now, bool)
        assert isinstance(summary.total_eligible, int)
        assert isinstance(summary.by_symbol, dict)
        assert isinstance(summary.by_duration, dict)
        assert isinstance(summary.first_eligible_slugs, list)
        # eligible_now=True, so rejection_reason should be None
        assert summary.rejection_reason is None
        assert isinstance(summary.checked_at, str)
        assert "T" in summary.checked_at  # ISO format sanity check

    def test_all_symbols_in_by_symbol(self):
        gc = _make_gamma_client([])
        summary = run_availability_check(gamma_client=gc)
        assert "BTC" in summary.by_symbol
        assert "ETH" in summary.by_symbol
        assert "SOL" in summary.by_symbol

    def test_all_durations_in_by_duration(self):
        gc = _make_gamma_client([])
        summary = run_availability_check(gamma_client=gc)
        assert "5m" in summary.by_duration
        assert "15m" in summary.by_duration


# ---------------------------------------------------------------------------
# Test 5: Watch mode — finds markets immediately
# ---------------------------------------------------------------------------

class TestWatchModeFindsMarketsImmediately:
    def test_watch_mode_finds_markets_immediately(self):
        """_check_fn returns eligible on first call; returns (True, summary)."""
        eligible = _eligible_summary(["btc-5m-up"])
        calls = [0]

        def check_fn() -> AvailabilitySummary:
            calls[0] += 1
            return eligible

        found, summary = run_watch_loop(
            poll_interval_seconds=60,
            timeout_seconds=3600,
            _sleep_fn=lambda n: None,
            _check_fn=check_fn,
        )
        assert found is True
        assert summary.eligible_now is True
        assert calls[0] == 1  # Only one poll needed


# ---------------------------------------------------------------------------
# Test 6: Watch mode — timeout
# ---------------------------------------------------------------------------

class TestWatchModeTimeout:
    def test_watch_mode_timeout(self):
        """_check_fn always returns not-eligible; returns (False, summary) after timeout."""
        not_eligible = _not_eligible_summary()
        sleep_calls = [0]

        def check_fn() -> AvailabilitySummary:
            return not_eligible

        def sleep_fn(n: float) -> None:
            sleep_calls[0] += 1

        # timeout_seconds=1, poll_interval_seconds=1 so loop exits quickly
        found, summary = run_watch_loop(
            poll_interval_seconds=1,
            timeout_seconds=1,
            _sleep_fn=sleep_fn,
            _check_fn=check_fn,
        )
        assert found is False
        assert summary.eligible_now is False


# ---------------------------------------------------------------------------
# Test 7: Artifacts written
# ---------------------------------------------------------------------------

class TestArtifactsWritten:
    def test_artifacts_written(self, tmp_path):
        """run_crypto_pair_watch writes watch_manifest.json, availability_summary.json,
        availability_summary.md in the run_dir."""
        not_eligible = _not_eligible_summary()

        manifest = run_crypto_pair_watch(
            watch_mode=False,
            output_base=tmp_path,
            _check_fn=lambda: not_eligible,
        )

        artifact_dir = Path(manifest["artifact_dir"])
        assert (artifact_dir / "watch_manifest.json").exists()
        assert (artifact_dir / "availability_summary.json").exists()
        assert (artifact_dir / "availability_summary.md").exists()

    def test_artifact_json_schema(self, tmp_path):
        """availability_summary.json contains all AvailabilitySummary fields."""
        eligible = _eligible_summary(["btc-5m-up"])

        manifest = run_crypto_pair_watch(
            watch_mode=False,
            output_base=tmp_path,
            _check_fn=lambda: eligible,
        )

        artifact_dir = Path(manifest["artifact_dir"])
        data = json.loads(
            (artifact_dir / "availability_summary.json").read_text(encoding="utf-8")
        )
        for field in (
            "eligible_now", "total_eligible", "by_symbol", "by_duration",
            "first_eligible_slugs", "rejection_reason", "checked_at",
        ):
            assert field in data, f"Missing field in availability_summary.json: {field}"

    def test_watch_manifest_schema(self, tmp_path):
        """watch_manifest.json contains required keys."""
        not_eligible = _not_eligible_summary()

        manifest = run_crypto_pair_watch(
            watch_mode=False,
            output_base=tmp_path,
            _check_fn=lambda: not_eligible,
        )

        artifact_dir = Path(manifest["artifact_dir"])
        data = json.loads(
            (artifact_dir / "watch_manifest.json").read_text(encoding="utf-8")
        )
        for key in ("run_id", "generated_at", "mode", "summary_ref", "artifact_dir"):
            assert key in data, f"Missing key in watch_manifest.json: {key}"

    def test_artifacts_written_watch_mode(self, tmp_path):
        """Watch mode also writes artifacts."""
        eligible = _eligible_summary(["btc-5m-up"])

        manifest = run_crypto_pair_watch(
            watch_mode=True,
            poll_interval_seconds=1,
            timeout_seconds=10,
            output_base=tmp_path,
            _check_fn=lambda: eligible,
            _sleep_fn=lambda n: None,
        )

        artifact_dir = Path(manifest["artifact_dir"])
        assert (artifact_dir / "watch_manifest.json").exists()
        assert (artifact_dir / "availability_summary.json").exists()
        assert (artifact_dir / "availability_summary.md").exists()


# ---------------------------------------------------------------------------
# Test 8: CLI help
# ---------------------------------------------------------------------------

class TestCliOneshotHelp:
    def test_cli_oneshot_help(self):
        """build_parser().parse_args(['--help']) raises SystemExit(0)."""
        with pytest.raises(SystemExit) as exc_info:
            build_parser().parse_args(["--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Test 9: CLI one-shot no-markets exits 0
# ---------------------------------------------------------------------------

class TestCliOneshotNoMarketsExits0:
    def test_cli_oneshot_no_markets_exits_0(self, tmp_path, monkeypatch):
        """main returns 0 even when no eligible markets are found (informational)."""
        not_eligible = _not_eligible_summary()

        # Monkeypatch run_crypto_pair_watch so no network call occurs
        import tools.cli.crypto_pair_watch as watch_mod

        original = watch_mod.run_crypto_pair_watch

        def fake_run(**kwargs):
            kwargs["_check_fn"] = lambda: not_eligible
            return original(**kwargs)

        monkeypatch.setattr(watch_mod, "run_crypto_pair_watch", fake_run)

        rc = main(["--output", str(tmp_path)])
        assert rc == 0


# ---------------------------------------------------------------------------
# Test 10: CLI watch timeout exits 1
# ---------------------------------------------------------------------------

class TestCliWatchTimeoutExits1:
    def test_cli_watch_timeout_exits_1(self, tmp_path, monkeypatch):
        """main returns 1 on watch-mode timeout with no eligible markets."""
        not_eligible = _not_eligible_summary()

        import tools.cli.crypto_pair_watch as watch_mod

        original = watch_mod.run_crypto_pair_watch

        def fake_run(**kwargs):
            kwargs["_check_fn"] = lambda: not_eligible
            kwargs["_sleep_fn"] = lambda n: None
            return original(**kwargs)

        monkeypatch.setattr(watch_mod, "run_crypto_pair_watch", fake_run)

        rc = main(["--watch", "--timeout", "1", "--output", str(tmp_path)])
        assert rc == 1
