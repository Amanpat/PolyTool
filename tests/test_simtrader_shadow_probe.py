"""Tests for simtrader shadow activeness-probe preflight flags.

All tests are fully offline — ActivenessProbe.run() is patched so no
WebSocket connections are opened.
"""

from __future__ import annotations

from unittest.mock import patch

from packages.polymarket.simtrader.activeness_probe import (
    ActivenessProbe,
    ProbeResult,
)

YES_ID = "aaa" * 20 + "1"
NO_ID = "bbb" * 20 + "2"


# ------------------------------------------------------------------
# 1) Parser recognises the new flags
# ------------------------------------------------------------------


def test_shadow_parser_accepts_probe_flags() -> None:
    """The shadow subparser must accept the three activeness-probe flags."""
    from tools.cli.simtrader import _build_parser

    parser = _build_parser()
    args = parser.parse_args([
        "shadow",
        "--market", "demo-slug",
        "--activeness-probe-seconds", "10",
        "--min-probe-updates", "3",
        "--require-active",
    ])
    assert args.subcommand == "shadow"
    assert args.activeness_probe_seconds == 10.0
    assert args.min_probe_updates == 3
    assert args.require_active is True


def test_shadow_parser_defaults_probe_flags() -> None:
    """Probe flags default to disabled (0 / 1 / False)."""
    from tools.cli.simtrader import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["shadow", "--market", "demo-slug"])
    assert args.activeness_probe_seconds == 0.0
    assert args.min_probe_updates == 1
    assert args.require_active is False


# ------------------------------------------------------------------
# 2) Probe invoked with injected results prints stats
# ------------------------------------------------------------------


def test_shadow_probe_prints_stats(capsys) -> None:
    """ActivenessProbe.run_from_source counts events correctly and
    the CLI would see per-token stats."""
    events = [
        {"event_type": "price_change", "asset_id": YES_ID},
        {"event_type": "price_change", "asset_id": YES_ID},
        {"event_type": "price_change", "asset_id": NO_ID},
        {"event_type": "book", "asset_id": YES_ID},       # not counted
        {"event_type": "last_trade_price", "asset_id": NO_ID},
    ]
    probe = ActivenessProbe(
        asset_ids=[YES_ID, NO_ID],
        probe_seconds=5.0,
        min_updates=2,
    )
    results = probe.run_from_source(events)

    assert results[YES_ID].updates == 2
    assert results[YES_ID].active is True
    assert results[NO_ID].updates == 2
    assert results[NO_ID].active is True


# ------------------------------------------------------------------
# 3) --require-active: probe failure -> early exit
# ------------------------------------------------------------------


def test_shadow_probe_require_active_fails_on_quiet_token(capsys) -> None:
    """When --require-active is set and a token has zero qualifying events,
    _shadow() must return non-zero without proceeding to the strategy run.

    We patch ActivenessProbe.run() and the market-picker layer so no
    network calls are made.
    """
    from types import SimpleNamespace
    from tools.cli.simtrader import _shadow

    # Fake args matching what argparse would produce
    args = SimpleNamespace(
        market="demo-slug",
        duration=10.0,
        strategy="binary_complement_arb",
        strategy_config_path=None,
        strategy_config_json=None,
        strategy_preset="sane",
        starting_cash=1000.0,
        fee_rate_bps=None,
        mark_method="bid",
        cancel_latency_ticks=0,
        no_record_tape=True,
        dry_run=False,
        ws_url="wss://fake",
        max_ws_stall_seconds=5.0,
        activeness_probe_seconds=5.0,
        min_probe_updates=3,
        require_active=True,
    )

    # Fake resolved market
    resolved = SimpleNamespace(
        slug="demo-slug",
        question="Will demo pass?",
        yes_token_id=YES_ID,
        no_token_id=NO_ID,
        yes_label="Yes",
        no_label="No",
        mapping_tier="explicit",
    )
    valid_book = SimpleNamespace(valid=True, reason="ok")

    # Fake probe results: YES is active, NO is NOT active (0 updates)
    fake_probe_results = {
        YES_ID: ProbeResult(token_id=YES_ID, probe_seconds=5.0, updates=5, active=True),
        NO_ID: ProbeResult(token_id=NO_ID, probe_seconds=5.0, updates=0, active=False),
    }

    # _shadow() uses local imports, so patch at the source module level.
    with (
        patch("packages.polymarket.clob.ClobClient"),
        patch("packages.polymarket.gamma.GammaClient"),
        patch(
            "packages.polymarket.simtrader.market_picker.MarketPicker.resolve_slug",
            return_value=resolved,
        ),
        patch(
            "packages.polymarket.simtrader.market_picker.MarketPicker.validate_book",
            return_value=valid_book,
        ),
        patch.object(ActivenessProbe, "run", return_value=fake_probe_results),
    ):
        exit_code = _shadow(args)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "activeness probe failed" in captured.err
    assert "NO" in captured.err
