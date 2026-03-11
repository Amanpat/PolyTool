from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import polytool.__main__ as polytool_main
from packages.polymarket.market_selection import filters, scorer
from packages.polymarket.market_selection.filters import passes_filters
from packages.polymarket.market_selection.scorer import score_market
from tools.cli import market_scan


FIXED_NOW = datetime(2026, 3, 5, 22, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _base_market() -> dict:
    return {
        "slug": "alpha-market",
        "best_bid": 0.48,
        "best_ask": 0.51,
        "volume_24h": 15000.0,
        "end_date_iso": _iso(FIXED_NOW + timedelta(days=7)),
        "created_at": _iso(FIXED_NOW - timedelta(hours=12)),
        "resolved_at": None,
        "token_id": "tok-alpha",
    }


def test_score_market_computes_expected_composite(monkeypatch):
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)

    market = _base_market()
    orderbook = {
        "bids": [[0.48, 20], [0.47, 80], [0.46, 200]],
        "asks": [[0.51, 30], [0.52, 40]],
    }
    reward_config = {"reward_rate": 0.005, "min_size_cutoff": 100.0}

    result = score_market(market, orderbook, reward_config)

    assert result.market_slug == "alpha-market"
    assert result.reward_apr_est == pytest.approx(1.825)
    assert result.spread_score == pytest.approx(2.0)
    assert result.fill_score == pytest.approx(1.5)
    assert result.competition_score == pytest.approx(1.0 / 3.0)
    assert result.age_hours == pytest.approx(12.0)
    assert result.composite == pytest.approx(1.52625)


@pytest.mark.parametrize(
    ("market_patch", "reward_config", "expected_reason"),
    [
        ({"best_bid": 0.02, "best_ask": 0.06}, {"reward_rate": 0.01}, "mid_price_out_of_range"),
        (
            {"end_date_iso": _iso(FIXED_NOW + timedelta(days=2))},
            {"reward_rate": 0.01},
            "resolution_too_close",
        ),
        ({"volume_24h": 4000.0}, {"reward_rate": 0.01}, "volume_too_low"),
        ({}, {}, "missing_reward_config"),
        (
            {"resolved_at": _iso(FIXED_NOW - timedelta(hours=1))},
            {"reward_rate": 0.01},
            "recently_resolved",
        ),
    ],
)
def test_passes_filters_rejects_each_condition(monkeypatch, market_patch, reward_config, expected_reason):
    monkeypatch.setattr(filters, "_utcnow", lambda: FIXED_NOW)
    market = _base_market()
    market.update(market_patch)

    passed, reason = passes_filters(market, reward_config)

    assert passed is False
    assert reason == expected_reason


def test_passes_filters_accepts_valid_market(monkeypatch):
    monkeypatch.setattr(filters, "_utcnow", lambda: FIXED_NOW)
    passed, reason = passes_filters(_base_market(), {"reward_rate": 0.01, "min_size_cutoff": 100})
    assert passed is True
    assert reason == ""


def test_market_scan_end_to_end_flow(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setattr(market_scan, "_utcnow", lambda: FIXED_NOW)
    monkeypatch.setattr(scorer, "_utcnow", lambda: FIXED_NOW)
    monkeypatch.setattr(filters, "_utcnow", lambda: FIXED_NOW)

    alpha = _base_market()
    beta = {
        **_base_market(),
        "slug": "beta-market",
        "best_bid": 0.03,
        "best_ask": 0.07,
        "token_id": "tok-beta",
    }

    def fake_fetch_active_markets(min_volume=5000, limit=50):
        assert min_volume == 5000.0
        assert limit == 50
        return [alpha, beta]

    def fake_fetch_reward_config(market_slug: str):
        return {"reward_rate": 0.005, "min_size_cutoff": 100.0, "market_slug": market_slug}

    def fake_fetch_orderbook(token_id: str):
        assert token_id == "tok-alpha"
        return {
            "bids": [[0.48, 20], [0.47, 80], [0.46, 200]],
            "asks": [[0.51, 30], [0.52, 40]],
        }

    monkeypatch.setattr(market_scan, "fetch_active_markets", fake_fetch_active_markets)
    monkeypatch.setattr(market_scan, "fetch_reward_config", fake_fetch_reward_config)
    monkeypatch.setattr(market_scan, "fetch_orderbook", fake_fetch_orderbook)

    output_path = tmp_path / "market-selection.json"
    exit_code = market_scan.main(
        [
            "--min-volume",
            "5000",
            "--top",
            "5",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["results"][0]["market_slug"] == "alpha-market"
    assert len(payload["results"]) == 1
    assert payload["filtered_out"] == [{"market_slug": "beta-market", "reason": "mid_price_out_of_range"}]

    stdout = capsys.readouterr().out
    assert "alpha-market" in stdout
    assert "Wrote market scan" in stdout


def test_polytool_main_routes_market_scan(monkeypatch):
    captured: dict[str, list[str]] = {}

    def fake_market_scan_main(argv: list[str]) -> int:
        captured["argv"] = argv
        return 7

    monkeypatch.setattr(polytool_main, "market_scan_main", fake_market_scan_main)

    assert polytool_main.main(["market-scan", "--top", "3"]) == 7
    assert captured["argv"] == ["--top", "3"]
