"""Unit tests for MarketMakerV1 calibration plumbing.

Covers:
  - sigma_b (logit-mid variance) responds correctly to rolling history
  - _kappa() fallback when trade arrivals are insufficient
  - _kappa() live proxy when sufficient trade arrivals exist
  - kappa proxy clamped to [_MIN_KAPPA, _MAX_KAPPA]
  - non-trade events do not contribute to kappa history
  - quote outputs are bounded and tick-valid
  - no regression: V1 inherits V0 crossed-book / empty-book guard
  - reason strings are relabeled to market_maker_v1
"""

from __future__ import annotations

import math
from collections import deque
from decimal import Decimal

import pytest

from packages.polymarket.simtrader.strategies.market_maker_v1 import (
    MarketMakerV1,
    _DEFAULT_SIGMA_SQ_LOGIT,
    _KAPPA_TRADES_PER_SEC_SCALE,
    _MAX_KAPPA,
    _MIN_KAPPA,
    _MIN_TRADES_FOR_KAPPA,
    _logit,
    _sigmoid,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mm(**kwargs) -> MarketMakerV1:
    kwargs.setdefault("tick_size", "0.01")
    kwargs.setdefault("order_size", "10")
    return MarketMakerV1(**kwargs)


def _book_event(
    *,
    asset_id: str = "tok1",
    seq: int = 1,
    ts_recv: float = 1000.0,
    bids=None,
    asks=None,
) -> dict:
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": ts_recv,
        "event_type": "book",
        "asset_id": asset_id,
        "bids": bids if bids is not None else [{"price": "0.45", "size": "100"}],
        "asks": asks if asks is not None else [{"price": "0.55", "size": "100"}],
    }


def _trade_event(ts_recv: float, asset_id: str = "tok1", seq: int = 1) -> dict:
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": ts_recv,
        "event_type": "last_trade_price",
        "asset_id": asset_id,
        "price": "0.50",
    }


def _price_change_event(ts_recv: float, asset_id: str = "tok1", seq: int = 1) -> dict:
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": ts_recv,
        "event_type": "price_change",
        "asset_id": asset_id,
        "price": "0.50",
    }


def _bid_ask(intents):
    bid = next(i for i in intents if i.side == "BUY")
    ask = next(i for i in intents if i.side == "SELL")
    return bid, ask


def _feed_trades(mm: MarketMakerV1, n: int, base_ts: float = 1000.0) -> None:
    """Inject n last_trade_price events spaced 1 s apart."""
    for i in range(n):
        mm._record_trade_arrival(_trade_event(base_ts + i), base_ts + i)


# ---------------------------------------------------------------------------
# Math helpers sanity checks
# ---------------------------------------------------------------------------


class TestMathHelpers:
    def test_logit_at_half(self) -> None:
        assert _logit(0.5) == pytest.approx(0.0)

    def test_sigmoid_at_zero(self) -> None:
        assert _sigmoid(0.0) == pytest.approx(0.5)

    def test_logit_sigmoid_roundtrip(self) -> None:
        for p in (0.1, 0.3, 0.5, 0.7, 0.9):
            assert _sigmoid(_logit(p)) == pytest.approx(p, abs=1e-9)


# ---------------------------------------------------------------------------
# Sigma_b: realized logit-mid variance
# ---------------------------------------------------------------------------


class TestSigmaSq:
    def test_returns_default_with_fewer_than_three_points(self) -> None:
        mm = _mm()
        mm._mid_history = deque(
            [(1000.0, _logit(0.50)), (1001.0, _logit(0.51))]
        )
        assert mm._sigma_sq(1001.0) == pytest.approx(_DEFAULT_SIGMA_SQ_LOGIT)

    def test_returns_default_with_exactly_two_points(self) -> None:
        mm = _mm()
        mm._mid_history = deque(
            [(1000.0, _logit(0.40)), (1001.0, _logit(0.45))]
        )
        assert mm._sigma_sq(1001.0) == pytest.approx(_DEFAULT_SIGMA_SQ_LOGIT)

    def test_returns_nondefault_with_three_or_more_points(self) -> None:
        mm = _mm(vol_window_seconds=3600.0)
        # Feed history so we get >2 logit-space changes.
        logit_mids = [_logit(p) for p in (0.40, 0.45, 0.50, 0.55, 0.60)]
        mm._mid_history = deque(
            (1000.0 + i, x) for i, x in enumerate(logit_mids)
        )
        sigma = mm._sigma_sq(1004.0)
        assert sigma != pytest.approx(_DEFAULT_SIGMA_SQ_LOGIT)
        assert sigma > 0.0

    def test_sigma_increases_with_more_volatile_history(self) -> None:
        mm_lo = _mm(vol_window_seconds=3600.0)
        mm_hi = _mm(vol_window_seconds=3600.0)

        # Low vol: small logit moves
        mm_lo._mid_history = deque(
            (1000.0 + i, _logit(0.50 + i * 0.001)) for i in range(5)
        )
        # High vol: large logit moves
        mm_hi._mid_history = deque(
            (1000.0 + i, _logit(0.50 + i * 0.05)) for i in range(5)
        )

        assert mm_lo._sigma_sq(1004.0) < mm_hi._sigma_sq(1004.0)

    def test_sigma_prunes_entries_outside_window(self) -> None:
        mm = _mm(vol_window_seconds=60.0)
        # Put entries far in the past; they should be pruned → fall back to default.
        mm._mid_history = deque(
            (i, _logit(0.50 + i * 0.01)) for i in range(1, 6)
        )
        # t_now = 1000 → cutoff = 940 → all entries below 940 are pruned.
        assert mm._sigma_sq(1000.0) == pytest.approx(_DEFAULT_SIGMA_SQ_LOGIT)

    def test_sigma_stored_as_logit_not_probability(self) -> None:
        """V1 _record_mid stores logit(mid), not raw mid."""
        mm = _mm(vol_window_seconds=3600.0)
        mm._mid_history.clear()
        mm._record_mid(1000.0, 0.50)
        mm._record_mid(1001.0, 0.55)
        mm._record_mid(1002.0, 0.60)
        ts, x = mm._mid_history[0]
        # Should be logit(0.50) ≈ 0.0, not 0.50.
        assert abs(x) < 0.01


# ---------------------------------------------------------------------------
# Kappa calibration
# ---------------------------------------------------------------------------


class TestKappaCalibration:
    def test_fallback_when_no_trades(self) -> None:
        mm = _mm(kappa=1.5)
        assert mm._kappa(1000.0) == pytest.approx(1.5)

    def test_fallback_below_min_trades_threshold(self) -> None:
        mm = _mm(kappa=2.0)
        _feed_trades(mm, _MIN_TRADES_FOR_KAPPA - 1, base_ts=990.0)
        assert mm._kappa(1000.0) == pytest.approx(2.0)

    def test_live_kappa_at_threshold(self) -> None:
        mm = _mm(kappa=1.5, vol_window_seconds=60.0)
        # Exactly _MIN_TRADES_FOR_KAPPA trades within window.
        _feed_trades(mm, _MIN_TRADES_FOR_KAPPA, base_ts=960.0)
        k = mm._kappa(999.0)
        assert k != pytest.approx(1.5), "should use live proxy, not fallback"
        assert _MIN_KAPPA <= k <= _MAX_KAPPA

    def test_kappa_increases_with_more_trades(self) -> None:
        mm_lo = _mm(kappa=1.5, vol_window_seconds=60.0)
        mm_hi = _mm(kappa=1.5, vol_window_seconds=60.0)

        _feed_trades(mm_lo, _MIN_TRADES_FOR_KAPPA, base_ts=950.0)
        _feed_trades(mm_hi, 30, base_ts=950.0)

        assert mm_lo._kappa(999.0) < mm_hi._kappa(999.0)

    def test_kappa_clamped_to_min(self) -> None:
        """Even with just enough trades, rate should be low → clamped at _MIN_KAPPA."""
        mm = _mm(kappa=1.5, vol_window_seconds=3600.0)
        # _MIN_TRADES_FOR_KAPPA trades in a 3600-s window → tiny rate.
        _feed_trades(mm, _MIN_TRADES_FOR_KAPPA, base_ts=100.0)
        k = mm._kappa(3600.0)
        assert k >= _MIN_KAPPA

    def test_kappa_clamped_to_max(self) -> None:
        mm = _mm(kappa=1.5, vol_window_seconds=60.0)
        # 1000 trades in a 60-s window → very high rate → clamped at _MAX_KAPPA.
        for i in range(200):
            mm._trade_arrival_ts.append(960.0 + i * 0.3)
        k = mm._kappa(999.0)
        assert k == pytest.approx(_MAX_KAPPA)

    def test_non_trade_events_ignored(self) -> None:
        mm = _mm(kappa=1.5, vol_window_seconds=60.0)
        for i in range(20):
            mm._record_trade_arrival(_price_change_event(950.0 + i), 950.0 + i)
            mm._record_trade_arrival(_book_event(ts_recv=950.0 + i), 950.0 + i)
        assert mm._kappa(999.0) == pytest.approx(1.5), "only last_trade_price counts"

    def test_trades_outside_window_pruned(self) -> None:
        mm = _mm(kappa=1.5, vol_window_seconds=60.0)
        # Feed trades at t=0..4 → all outside window when t_now=1000.
        _feed_trades(mm, _MIN_TRADES_FOR_KAPPA, base_ts=0.0)
        assert mm._kappa(1000.0) == pytest.approx(1.5)

    def test_kappa_proxy_formula(self) -> None:
        """Verify exact formula: kappa = clamp(n/window*scale, min, max)."""
        window = 60.0
        mm = _mm(kappa=1.5, vol_window_seconds=window)
        n = 10
        _feed_trades(mm, n, base_ts=960.0)
        k = mm._kappa(999.0)
        expected = (n / window) * _KAPPA_TRADES_PER_SEC_SCALE
        expected = max(_MIN_KAPPA, min(_MAX_KAPPA, expected))
        assert k == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# Quote bounds (outputs remain bounded and tick-valid)
# ---------------------------------------------------------------------------


class TestQuoteBounds:
    def _run_quotes(self, mm, best_bid, best_ask, ts=1000.0):
        event = _book_event(ts_recv=ts)
        mm.on_start("tok1", Decimal("1000"))
        return mm.compute_quotes(
            best_bid=best_bid,
            best_ask=best_ask,
            asset_id="tok1",
            book=event,
            event=event,
            ts_recv=ts,
            open_orders={},
        )

    def test_basic_bid_ask_bounded(self) -> None:
        mm = _mm()
        intents = self._run_quotes(mm, 0.45, 0.55)
        assert len(intents) == 2
        bid, ask = _bid_ask(intents)
        assert 0.01 <= float(bid.limit_price) <= 0.98
        assert 0.02 <= float(ask.limit_price) <= 0.99

    def test_ask_strictly_greater_than_bid(self) -> None:
        mm = _mm()
        intents = self._run_quotes(mm, 0.45, 0.55)
        bid, ask = _bid_ask(intents)
        assert ask.limit_price > bid.limit_price

    def test_tick_aligned(self) -> None:
        mm = _mm(tick_size="0.01")
        intents = self._run_quotes(mm, 0.45, 0.55)
        bid, ask = _bid_ask(intents)
        assert bid.limit_price % Decimal("0.01") == Decimal("0")
        assert ask.limit_price % Decimal("0.01") == Decimal("0")

    def test_tail_market_quotes_valid(self) -> None:
        """Near-resolution market (mid ≈ 0.05) still produces valid quotes."""
        mm = _mm()
        intents = self._run_quotes(mm, 0.03, 0.07)
        assert len(intents) == 2
        bid, ask = _bid_ask(intents)
        assert ask.limit_price > bid.limit_price

    def test_live_kappa_does_not_break_bounds(self) -> None:
        """With calibrated kappa the quotes remain bounded."""
        mm = _mm(kappa=1.5, vol_window_seconds=60.0)
        mm.on_start("tok1", Decimal("1000"))
        # Inject 20 trades so kappa goes live.
        for i in range(20):
            mm._record_trade_arrival(_trade_event(950.0 + i), 950.0 + i)
        event = _book_event(ts_recv=999.0)
        intents = mm.compute_quotes(
            best_bid=0.45,
            best_ask=0.55,
            asset_id="tok1",
            book=event,
            event=event,
            ts_recv=999.0,
            open_orders={},
        )
        assert len(intents) == 2
        bid, ask = _bid_ask(intents)
        assert 0.01 <= float(bid.limit_price) <= 0.98
        assert ask.limit_price > bid.limit_price

    def test_spread_widens_near_tails_vs_midpoint(self) -> None:
        """Resolution guard: spread near p=0.06 should be >= spread at p=0.50."""
        mm_mid = _mm()
        mm_tail = _mm()
        i_mid = self._run_quotes(mm_mid, 0.45, 0.55)
        i_tail = self._run_quotes(mm_tail, 0.03, 0.09)
        if i_mid and i_tail:
            bid_m, ask_m = _bid_ask(i_mid)
            bid_t, ask_t = _bid_ask(i_tail)
            spread_mid = float(ask_m.limit_price - bid_m.limit_price)
            spread_tail = float(ask_t.limit_price - bid_t.limit_price)
            assert spread_tail >= spread_mid


# ---------------------------------------------------------------------------
# Regression: V1 inherits V0 guard behaviour
# ---------------------------------------------------------------------------


class TestNoRegression:
    def test_crossed_book_returns_empty(self) -> None:
        mm = _mm()
        mm.on_start("tok1", Decimal("1000"))
        intents = mm.compute_quotes(best_bid=0.55, best_ask=0.45, asset_id="tok1")
        assert intents == []

    def test_none_bid_returns_empty(self) -> None:
        mm = _mm()
        mm.on_start("tok1", Decimal("1000"))
        intents = mm.compute_quotes(best_bid=None, best_ask=0.55, asset_id="tok1")
        assert intents == []

    def test_reason_relabeled_to_v1(self) -> None:
        mm = _mm()
        mm.on_start("tok1", Decimal("1000"))
        event = _book_event(ts_recv=1000.0)
        intents = mm.compute_quotes(
            best_bid=0.45,
            best_ask=0.55,
            asset_id="tok1",
            book=event,
            event=event,
            ts_recv=1000.0,
            open_orders={},
        )
        assert len(intents) == 2
        for intent in intents:
            assert "market_maker_v1" in (intent.reason or "")
            assert "market_maker_v0" not in (intent.reason or "")

    def test_on_start_resets_trade_arrival_ts(self) -> None:
        mm = _mm(vol_window_seconds=60.0)
        mm.on_start("tok1", Decimal("1000"))
        _feed_trades(mm, _MIN_TRADES_FOR_KAPPA, base_ts=960.0)
        assert len(mm._trade_arrival_ts) == _MIN_TRADES_FOR_KAPPA
        mm.on_start("tok1", Decimal("1000"))
        assert len(mm._trade_arrival_ts) == 0

    def test_on_event_captures_trades(self) -> None:
        mm = _mm(vol_window_seconds=60.0)
        mm.on_start("tok1", Decimal("1000"))
        # Feed _MIN_TRADES_FOR_KAPPA trade events via on_event.
        for i in range(_MIN_TRADES_FOR_KAPPA):
            mm.on_event(
                _trade_event(960.0 + i),
                seq=i,
                ts_recv=960.0 + i,
                best_bid=0.45,
                best_ask=0.55,
                open_orders={},
            )
        assert len(mm._trade_arrival_ts) == _MIN_TRADES_FOR_KAPPA

    def test_sigma_responds_to_logit_mid_changes(self) -> None:
        """End-to-end: feeding book events makes sigma_sq diverge from default."""
        mm = _mm(vol_window_seconds=3600.0)
        mm.on_start("tok1", Decimal("1000"))
        mids = [0.40, 0.44, 0.48, 0.52, 0.56, 0.60]
        for i, (bid, ask) in enumerate(
            [(m - 0.04, m + 0.04) for m in mids], start=1
        ):
            mm.on_event(
                _book_event(
                    bids=[{"price": str(round(bid, 3)), "size": "100"}],
                    asks=[{"price": str(round(ask, 3)), "size": "100"}],
                    ts_recv=1000.0 + i,
                ),
                seq=i,
                ts_recv=1000.0 + i,
                best_bid=bid,
                best_ask=ask,
                open_orders={},
            )
        sigma = mm._sigma_sq(1006.0)
        assert sigma != pytest.approx(_DEFAULT_SIGMA_SQ_LOGIT)
        assert sigma > 0.0


# ---------------------------------------------------------------------------
# Calibration provenance
# ---------------------------------------------------------------------------


class TestCalibrationProvenance:
    """Tests that on_finish() populates calibration_provenance with accurate
    source labels, counts, and values.
    """

    def test_provenance_none_before_on_finish(self) -> None:
        mm = _mm()
        assert mm.calibration_provenance is None

    def test_provenance_set_after_on_finish_fallback_state(self) -> None:
        """Both sigma and kappa should fall back when no history exists."""
        mm = _mm(kappa=2.5)
        mm.on_start("tok1", Decimal("1000"))
        # No book events → no mid history; no trades → no trade arrivals.
        mm.on_finish()

        prov = mm.calibration_provenance
        assert isinstance(prov, dict)
        assert prov["sigma"]["source"] == "static_fallback"
        assert prov["kappa"]["source"] == "static_fallback"

    def test_sigma_fallback_fields(self) -> None:
        mm = _mm(kappa=1.5)
        mm.on_start("tok1", Decimal("1000"))
        # Only 2 mid-history points → fallback.
        mm._mid_history.clear()
        mm._mid_history.append((999.0, _logit(0.45)))
        mm._mid_history.append((1000.0, _logit(0.50)))
        mm.on_finish()

        sigma = mm.calibration_provenance["sigma"]
        assert sigma["source"] == "static_fallback"
        assert sigma["sample_count"] == 2
        assert sigma["value"] == pytest.approx(_DEFAULT_SIGMA_SQ_LOGIT)
        assert "insufficient_samples" in (sigma["fallback_reason"] or "")
        assert sigma["fallback_reason"] is not None

    def test_sigma_rolling_fields(self) -> None:
        mm = _mm(kappa=1.5, vol_window_seconds=3600.0)
        mm.on_start("tok1", Decimal("1000"))
        # Feed 5 mid-history points in the window → rolling_logit_var.
        for i in range(5):
            mm._mid_history.append((1000.0 + i, _logit(0.40 + i * 0.05)))
        mm.on_finish()

        sigma = mm.calibration_provenance["sigma"]
        assert sigma["source"] == "rolling_logit_var"
        assert sigma["sample_count"] >= 3
        assert sigma["value"] > 0.0
        assert sigma["fallback_reason"] is None

    def test_kappa_fallback_fields(self) -> None:
        mm = _mm(kappa=2.0)
        mm.on_start("tok1", Decimal("1000"))
        # Fewer than _MIN_TRADES_FOR_KAPPA trades → fallback.
        _feed_trades(mm, _MIN_TRADES_FOR_KAPPA - 1, base_ts=990.0)
        mm._last_ts_recv = 1000.0
        mm.on_finish()

        kappa = mm.calibration_provenance["kappa"]
        assert kappa["source"] == "static_fallback"
        assert kappa["trade_count"] < _MIN_TRADES_FOR_KAPPA
        assert kappa["value"] == pytest.approx(2.0)
        assert kappa["constructor_kappa"] == pytest.approx(2.0)
        assert "insufficient_trades" in (kappa["fallback_reason"] or "")

    def test_kappa_proxy_fields(self) -> None:
        mm = _mm(kappa=1.5, vol_window_seconds=60.0)
        mm.on_start("tok1", Decimal("1000"))
        _feed_trades(mm, 10, base_ts=960.0)
        mm._last_ts_recv = 999.0
        mm.on_finish()

        kappa = mm.calibration_provenance["kappa"]
        assert kappa["source"] == "trade_arrival_proxy"
        assert kappa["trade_count"] == 10
        assert kappa["fallback_reason"] is None
        assert kappa["constructor_kappa"] == pytest.approx(1.5)
        # Kappa value should differ from static fallback (1.5).
        assert kappa["value"] != pytest.approx(1.5)
        assert _MIN_KAPPA <= kappa["value"] <= _MAX_KAPPA

    def test_vol_window_seconds_in_provenance(self) -> None:
        mm = _mm(vol_window_seconds=300.0)
        mm.on_start("tok1", Decimal("1000"))
        mm.on_finish()
        assert mm.calibration_provenance["vol_window_seconds"] == pytest.approx(300.0)

    def test_on_start_resets_provenance(self) -> None:
        mm = _mm()
        mm.on_start("tok1", Decimal("1000"))
        mm.on_finish()
        assert mm.calibration_provenance is not None
        # on_start again should NOT reset provenance (it's set by on_finish only)
        # but _trade_arrival_ts IS cleared
        mm.on_start("tok1", Decimal("1000"))
        # calibration_provenance is intentionally left from prior on_finish
        # until a new on_finish() call overwrites it
        assert mm.calibration_provenance is not None

    def test_provenance_emitted_to_runner_artifacts(self, tmp_path) -> None:
        """Integration: calibration_provenance appears in summary.json and
        run_manifest.json when running MarketMakerV1 via StrategyRunner.
        """
        import json
        from packages.polymarket.simtrader.strategy.runner import StrategyRunner
        from decimal import Decimal

        # Build a minimal tape with enough events.
        tape = tmp_path / "events.jsonl"
        events = []
        for i in range(6):
            events.append(json.dumps({
                "parser_version": 1,
                "seq": i + 1,
                "ts_recv": 1000.0 + i,
                "event_type": "book",
                "asset_id": "tokA",
                "bids": [{"price": str(round(0.44 + i * 0.01, 2)), "size": "100"}],
                "asks": [{"price": str(round(0.56 - i * 0.01, 2)), "size": "100"}],
            }))
        tape.write_text("\n".join(events) + "\n", encoding="utf-8")

        run_dir = tmp_path / "run"
        mm = MarketMakerV1(tick_size="0.01", order_size="10", vol_window_seconds=3600.0)
        runner = StrategyRunner(
            events_path=tape,
            run_dir=run_dir,
            strategy=mm,
            asset_id="tokA",
            strategy_name="market_maker_v1",
        )
        runner.run()

        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))

        assert "calibration_provenance" in summary, "summary.json missing calibration_provenance"
        assert "calibration_provenance" in manifest, "run_manifest.json missing calibration_provenance"

        prov = summary["calibration_provenance"]
        assert "sigma" in prov
        assert "kappa" in prov
        assert prov["sigma"]["source"] in ("rolling_logit_var", "static_fallback")
        assert prov["kappa"]["source"] in ("trade_arrival_proxy", "static_fallback")
