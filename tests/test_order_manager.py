"""Offline unit tests for OrderManager.

All tests inject a fake clock and use explicit ``now`` values to avoid any
real time dependency.  No network, no files.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from packages.polymarket.simtrader.execution.order_manager import (
    ActionPlan,
    DesiredOrder,
    OpenOrder,
    OrderManager,
    OrderManagerConfig,
    _is_old_enough,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _cfg(**kwargs) -> OrderManagerConfig:
    defaults = dict(max_cancels_per_minute=10, max_places_per_minute=10, min_order_lifetime_seconds=5.0)
    defaults.update(kwargs)
    return OrderManagerConfig(**defaults)


def _open(
    order_id: str,
    asset_id: str = "tok1",
    side: str = "BUY",
    price: str = "0.45",
    size: str = "10",
    submitted_at: float = 0.0,
) -> OpenOrder:
    return OpenOrder(
        order_id=order_id,
        asset_id=asset_id,
        side=side,
        price=Decimal(price),
        size=Decimal(size),
        submitted_at=submitted_at,
    )


def _desired(
    asset_id: str = "tok1",
    side: str = "BUY",
    price: str = "0.45",
    size: str = "10",
) -> DesiredOrder:
    return DesiredOrder(
        asset_id=asset_id,
        side=side,
        price=Decimal(price),
        size=Decimal(size),
    )


def _mgr(config: OrderManagerConfig | None = None, start_time: float = 1000.0) -> OrderManager:
    t = [start_time]
    return OrderManager(config=config, _clock=lambda: t[0]), t


# ===========================================================================
# _is_old_enough helper
# ===========================================================================


class TestIsOldEnough:
    def test_just_old_enough(self) -> None:
        o = _open("o1", submitted_at=100.0)
        assert _is_old_enough(o, now=105.0, min_lifetime=5.0) is True

    def test_too_young(self) -> None:
        o = _open("o1", submitted_at=100.0)
        assert _is_old_enough(o, now=104.9, min_lifetime=5.0) is False

    def test_zero_min_lifetime_always_old_enough(self) -> None:
        o = _open("o1", submitted_at=100.0)
        assert _is_old_enough(o, now=100.0, min_lifetime=0.0) is True


# ===========================================================================
# Basic reconciliation
# ===========================================================================


class TestBasicReconcile:
    def test_empty_desired_and_no_open_is_noop(self) -> None:
        mgr, _ = _mgr()
        plan = mgr.reconcile_once(desired_orders=[], open_orders={}, now=1010.0)
        assert plan.to_cancel == []
        assert plan.to_place == []
        assert plan.skipped_cancels == 0
        assert plan.skipped_places == 0

    def test_place_when_desired_and_no_open(self) -> None:
        mgr, _ = _mgr()
        desired = [_desired("tok1", "BUY", "0.45")]
        plan = mgr.reconcile_once(desired, {}, now=1010.0)
        assert len(plan.to_place) == 1
        assert plan.to_place[0].side == "BUY"
        assert plan.to_place[0].price == Decimal("0.45")

    def test_no_action_when_prices_match(self) -> None:
        mgr, _ = _mgr()
        open_order = _open("o1", "tok1", "BUY", "0.45", submitted_at=1000.0)
        desired = [_desired("tok1", "BUY", "0.45")]
        plan = mgr.reconcile_once(desired, {"o1": open_order}, now=1010.0)
        assert plan.to_cancel == []
        assert plan.to_place == []

    def test_cancel_stale_when_no_desired(self) -> None:
        mgr, _ = _mgr()
        open_order = _open("o1", "tok1", "BUY", "0.45", submitted_at=1000.0)
        plan = mgr.reconcile_once([], {"o1": open_order}, now=1010.0)
        assert "o1" in plan.to_cancel

    def test_replace_when_price_changes(self) -> None:
        mgr, _ = _mgr()
        open_order = _open("o1", "tok1", "BUY", "0.45", submitted_at=1000.0)
        desired = [_desired("tok1", "BUY", "0.46")]  # different price
        plan = mgr.reconcile_once(desired, {"o1": open_order}, now=1010.0)
        assert "o1" in plan.to_cancel
        assert len(plan.to_place) == 1
        assert plan.to_place[0].price == Decimal("0.46")

    def test_both_sides_managed_independently(self) -> None:
        mgr, _ = _mgr()
        # BUY open at correct price, SELL open at wrong price
        buy_order = _open("ob", "tok1", "BUY", "0.45", submitted_at=1000.0)
        sell_order = _open("os", "tok1", "SELL", "0.55", submitted_at=1000.0)
        desired = [
            _desired("tok1", "BUY", "0.45"),    # matches → no action
            _desired("tok1", "SELL", "0.56"),   # different → cancel + place
        ]
        plan = mgr.reconcile_once(desired, {"ob": buy_order, "os": sell_order}, now=1010.0)
        assert "ob" not in plan.to_cancel
        assert "os" in plan.to_cancel
        assert len(plan.to_place) == 1
        assert plan.to_place[0].side == "SELL"
        assert plan.to_place[0].price == Decimal("0.56")


# ===========================================================================
# Min-lifetime guard (churn protection)
# ===========================================================================


class TestMinLifetime:
    def test_too_young_order_not_cancelled(self) -> None:
        mgr, _ = _mgr(_cfg(min_order_lifetime_seconds=10.0))
        # Order submitted at t=1000, now=1005 → age=5 < min=10
        open_order = _open("o1", submitted_at=1000.0)
        plan = mgr.reconcile_once([], {"o1": open_order}, now=1005.0)
        assert "o1" not in plan.to_cancel
        assert plan.skipped_cancels == 1

    def test_old_enough_order_is_cancelled(self) -> None:
        mgr, _ = _mgr(_cfg(min_order_lifetime_seconds=5.0))
        open_order = _open("o1", submitted_at=1000.0)
        plan = mgr.reconcile_once([], {"o1": open_order}, now=1006.0)
        assert "o1" in plan.to_cancel

    def test_too_young_replace_not_cancelled(self) -> None:
        mgr, _ = _mgr(_cfg(min_order_lifetime_seconds=10.0))
        open_order = _open("o1", submitted_at=1000.0)
        # Price changed but order is too young
        desired = [_desired("tok1", "BUY", "0.46")]
        plan = mgr.reconcile_once(desired, {"o1": open_order}, now=1005.0)
        assert "o1" not in plan.to_cancel
        assert plan.skipped_cancels == 1
        # Should still place if not blocked by rate cap
        assert len(plan.to_place) == 1

    def test_zero_min_lifetime_always_cancellable(self) -> None:
        mgr, _ = _mgr(_cfg(min_order_lifetime_seconds=0.0))
        open_order = _open("o1", submitted_at=1000.0)
        plan = mgr.reconcile_once([], {"o1": open_order}, now=1000.0)
        assert "o1" in plan.to_cancel


# ===========================================================================
# Rate caps
# ===========================================================================


class TestRateCaps:
    def test_cancel_rate_cap_blocks_excess(self) -> None:
        mgr, _ = _mgr(_cfg(max_cancels_per_minute=2))
        # 3 old open orders, cap=2
        open_orders = {
            "o1": _open("o1", submitted_at=900.0),
            "o2": _open("o2", submitted_at=900.0),
            "o3": _open("o3", submitted_at=900.0),
        }
        plan = mgr.reconcile_once([], open_orders, now=1010.0)
        assert len(plan.to_cancel) == 2
        assert plan.skipped_cancels == 1

    def test_place_rate_cap_blocks_excess(self) -> None:
        mgr, _ = _mgr(_cfg(max_places_per_minute=2))
        # 3 desired orders, no open orders, cap=2
        desired = [
            _desired("tok1", "BUY", "0.45"),
            _desired("tok2", "BUY", "0.46"),
            _desired("tok3", "BUY", "0.47"),
        ]
        plan = mgr.reconcile_once(desired, {}, now=1010.0)
        assert len(plan.to_place) == 2
        assert plan.skipped_places == 1

    def test_rate_cap_sliding_window_resets_after_minute(self) -> None:
        t = [1000.0]
        mgr = OrderManager(config=_cfg(max_cancels_per_minute=1), _clock=lambda: t[0])

        # First reconcile: 1 old order → cancel (uses up cap)
        o1 = _open("o1", submitted_at=900.0)
        plan1 = mgr.reconcile_once([], {"o1": o1}, now=t[0])
        assert len(plan1.to_cancel) == 1

        # Second reconcile at same time: cap exceeded
        o2 = _open("o2", submitted_at=900.0)
        plan2 = mgr.reconcile_once([], {"o2": o2}, now=t[0])
        assert len(plan2.to_cancel) == 0
        assert plan2.skipped_cancels == 1

        # Advance 61 seconds: window resets
        t[0] = 1061.0
        o3 = _open("o3", submitted_at=900.0)
        plan3 = mgr.reconcile_once([], {"o3": o3}, now=t[0])
        assert len(plan3.to_cancel) == 1

    def test_cancel_and_place_caps_are_independent(self) -> None:
        mgr, _ = _mgr(_cfg(max_cancels_per_minute=1, max_places_per_minute=1))
        open_orders = {
            "o1": _open("o1", "tok1", "BUY", "0.45", submitted_at=900.0),
            "o2": _open("o2", "tok2", "BUY", "0.45", submitted_at=900.0),
        }
        desired = [
            _desired("tok3", "BUY", "0.45"),
            _desired("tok4", "BUY", "0.45"),
        ]
        plan = mgr.reconcile_once(desired, open_orders, now=1010.0)
        # Cancel cap=1: 2 open orders, only 1 cancelled
        assert len(plan.to_cancel) == 1
        assert plan.skipped_cancels == 1
        # Place cap=1: 2 desired, only 1 placed
        assert len(plan.to_place) == 1
        assert plan.skipped_places == 1


# ===========================================================================
# Stable action plan (determinism)
# ===========================================================================


class TestActionPlanStability:
    def test_same_inputs_same_plan(self) -> None:
        """Given the same inputs at the same time, reconcile_once is deterministic."""
        mgr, _ = _mgr()
        open_orders = {
            "o1": _open("o1", "tok1", "BUY", "0.44", submitted_at=1000.0),
        }
        desired = [
            _desired("tok1", "BUY", "0.45"),
            _desired("tok1", "SELL", "0.55"),
        ]
        plan_a = mgr.reconcile_once(desired, open_orders, now=1010.0)

        # Fresh manager, same inputs
        mgr2, _ = _mgr()
        plan_b = mgr2.reconcile_once(desired, open_orders, now=1010.0)

        assert plan_a.to_cancel == plan_b.to_cancel
        assert [(d.side, d.price) for d in plan_a.to_place] == [
            (d.side, d.price) for d in plan_b.to_place
        ]

    def test_no_open_desired_is_stable(self) -> None:
        mgr, _ = _mgr()
        plan = mgr.reconcile_once([], {}, now=1010.0)
        assert plan.to_cancel == []
        assert plan.to_place == []
        assert plan.skipped_cancels == 0
        assert plan.skipped_places == 0


# ===========================================================================
# ActionPlan dataclass
# ===========================================================================


class TestActionPlanDefaults:
    def test_default_plan_is_empty(self) -> None:
        plan = ActionPlan()
        assert plan.to_cancel == []
        assert plan.to_place == []
        assert plan.skipped_cancels == 0
        assert plan.skipped_places == 0
        assert plan.reasons == []

    def test_reasons_populated_on_skip(self) -> None:
        mgr, _ = _mgr(_cfg(min_order_lifetime_seconds=100.0))
        open_order = _open("o1", submitted_at=1000.0)
        plan = mgr.reconcile_once([], {"o1": open_order}, now=1005.0)
        assert len(plan.reasons) >= 1
        assert any("too young" in r for r in plan.reasons)


# ===========================================================================
# Multi-asset support
# ===========================================================================


class TestMultiAsset:
    def test_different_assets_managed_independently(self) -> None:
        mgr, _ = _mgr()
        open_orders = {
            "oa": _open("oa", "tok_a", "BUY", "0.45", submitted_at=1000.0),
        }
        # tok_a buy: keep (price matches). tok_b buy: place new.
        desired = [
            _desired("tok_a", "BUY", "0.45"),
            _desired("tok_b", "BUY", "0.46"),
        ]
        plan = mgr.reconcile_once(desired, open_orders, now=1010.0)
        assert "oa" not in plan.to_cancel
        assert len(plan.to_place) == 1
        assert plan.to_place[0].asset_id == "tok_b"

    def test_cancel_only_for_orphaned_open_asset(self) -> None:
        mgr, _ = _mgr()
        # tok_a open but not desired
        open_orders = {
            "oa": _open("oa", "tok_a", "BUY", "0.45", submitted_at=1000.0),
        }
        desired = [_desired("tok_b", "BUY", "0.46")]
        plan = mgr.reconcile_once(desired, open_orders, now=1010.0)
        assert "oa" in plan.to_cancel
        assert len(plan.to_place) == 1
        assert plan.to_place[0].asset_id == "tok_b"
