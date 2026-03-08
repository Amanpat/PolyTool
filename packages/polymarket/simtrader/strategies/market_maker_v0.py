"""MarketMakerV0 market making strategy using an Avellaneda-Stoikov quote model.

Legacy constructor arguments are retained for compatibility with existing
SimTrader configs and CLI entry points. Quote generation now centers on a
reservation price derived from inventory, volatility, and time horizon rather
than quoting directly at the best bid / ask.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, InvalidOperation
from statistics import pvariance
from typing import Any, Optional

from packages.polymarket.simtrader.orderbook.l2book import L2Book
from packages.polymarket.simtrader.strategy.base import OrderIntent, Strategy

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_ONE = Decimal("1")
_MIN_TICK = Decimal("0.0001")
_DEFAULT_SIGMA_SQ = 0.0002
_MIN_BID_PRICE = 0.01
_MAX_BID_PRICE = 0.98
_MIN_ASK_PRICE = 0.02
_MAX_ASK_PRICE = 0.99
_MIN_REMAINING_HOURS = 0.01


def _to_decimal(value: Any, name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"market_maker_v0: invalid {name}={value!r}: {exc}") from exc


def _to_float(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"market_maker_v0: invalid {name}={value!r}: {exc}") from exc
    if not math.isfinite(number):
        raise ValueError(f"market_maker_v0: invalid {name}={value!r}: expected finite float")
    return number


def _tick_floor(price: Decimal, tick: Decimal) -> Decimal:
    """Round price down to the nearest multiple of tick."""
    return (price / tick).to_integral_value(rounding=ROUND_FLOOR) * tick


def _tick_ceil(price: Decimal, tick: Decimal) -> Decimal:
    """Round price up to the nearest multiple of tick."""
    return (price / tick).to_integral_value(rounding=ROUND_CEILING) * tick


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


@dataclass(frozen=True)
class MMConfig:
    gamma: float = 0.10
    kappa: float = 1.50
    vol_window_seconds: float = 60.0
    session_hours: float = 24.0
    min_spread: float = 0.020
    max_spread: float = 0.120
    reprice_threshold: float = 0.005
    resolution_guard: float = 0.10


class MarketMakerV0(Strategy):
    """Two-sided market maker with an Avellaneda-Stoikov reservation price."""

    def __init__(
        self,
        tick_size: Any = "0.01",
        order_size: Any = "10",
        quote_ticks_from_bbo: int = 0,
        inventory_skew_factor: Any = "0.5",
        max_skew_ticks: int = 5,
        min_order_size: Any = "1",
        gamma: float = 0.10,
        kappa: float = 1.50,
        vol_window_seconds: float = 60.0,
        session_hours: float = 24.0,
        min_spread: float = 0.020,
        max_spread: float = 0.120,
        reprice_threshold: float = 0.005,
        resolution_guard: float = 0.10,
        hours_to_resolution: float = 24.0,
    ) -> None:
        self.tick_size = _to_decimal(tick_size, "tick_size")
        if self.tick_size < _MIN_TICK:
            raise ValueError(
                f"market_maker_v0: tick_size must be >= {_MIN_TICK}, got {self.tick_size}"
            )

        self.order_size = _to_decimal(order_size, "order_size")
        if self.order_size <= _ZERO:
            raise ValueError(f"market_maker_v0: order_size must be > 0, got {self.order_size}")

        if not isinstance(quote_ticks_from_bbo, int):
            raise ValueError("market_maker_v0: quote_ticks_from_bbo must be an int")
        self.quote_ticks_from_bbo = quote_ticks_from_bbo

        self.inventory_skew_factor = _to_decimal(inventory_skew_factor, "inventory_skew_factor")
        if self.inventory_skew_factor < _ZERO:
            raise ValueError(
                f"market_maker_v0: inventory_skew_factor must be >= 0, "
                f"got {self.inventory_skew_factor}"
            )

        if not isinstance(max_skew_ticks, int) or max_skew_ticks < 0:
            raise ValueError(
                f"market_maker_v0: max_skew_ticks must be a non-negative int, "
                f"got {max_skew_ticks}"
            )
        self.max_skew_ticks = max_skew_ticks

        self.min_order_size = _to_decimal(min_order_size, "min_order_size")
        self.mm_config = MMConfig(
            gamma=_to_float(gamma, "gamma"),
            kappa=_to_float(kappa, "kappa"),
            vol_window_seconds=_to_float(vol_window_seconds, "vol_window_seconds"),
            session_hours=_to_float(session_hours, "session_hours"),
            min_spread=_to_float(min_spread, "min_spread"),
            max_spread=_to_float(max_spread, "max_spread"),
            reprice_threshold=_to_float(reprice_threshold, "reprice_threshold"),
            resolution_guard=_to_float(resolution_guard, "resolution_guard"),
        )
        self._validate_mm_config(self.mm_config)

        self.default_hours_to_resolution = _to_float(hours_to_resolution, "hours_to_resolution")
        if self.default_hours_to_resolution <= 0:
            raise ValueError("market_maker_v0: hours_to_resolution must be > 0")

        # Runtime state.
        self._asset_id: Optional[str] = None
        self._inventory: Decimal = _ZERO
        self._book: Optional[L2Book] = None
        self._mid_history: deque[tuple[float, float]] = deque()
        self._session_start_ts: Optional[float] = None
        self._last_ts_recv: Optional[float] = None
        self._hours_to_resolution = self.default_hours_to_resolution
        self.hours_to_resolution = self.default_hours_to_resolution
        self._last_quotes: Optional[tuple[Decimal, Decimal]] = None

    @staticmethod
    def _validate_mm_config(config: MMConfig) -> None:
        if config.gamma <= 0:
            raise ValueError("market_maker_v0: gamma must be > 0")
        if config.kappa <= 0:
            raise ValueError("market_maker_v0: kappa must be > 0")
        if config.vol_window_seconds <= 0:
            raise ValueError("market_maker_v0: vol_window_seconds must be > 0")
        if config.session_hours <= 0:
            raise ValueError("market_maker_v0: session_hours must be > 0")
        if config.min_spread <= 0:
            raise ValueError("market_maker_v0: min_spread must be > 0")
        if config.max_spread < config.min_spread:
            raise ValueError("market_maker_v0: max_spread must be >= min_spread")
        if config.reprice_threshold < 0:
            raise ValueError("market_maker_v0: reprice_threshold must be >= 0")
        if not 0 <= config.resolution_guard < 0.5:
            raise ValueError("market_maker_v0: resolution_guard must be in [0, 0.5)")

    # ------------------------------------------------------------------
    # Strategy lifecycle
    # ------------------------------------------------------------------

    def on_start(self, asset_id: str, starting_cash: Decimal) -> None:
        self._asset_id = asset_id
        self._inventory = _ZERO
        self._book = L2Book(asset_id)
        self._mid_history.clear()
        self._session_start_ts = None
        self._last_ts_recv = None
        self._hours_to_resolution = self.default_hours_to_resolution
        self.hours_to_resolution = self.default_hours_to_resolution
        self._last_quotes = None

    def on_event(
        self,
        event: dict,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        self._update_book_state(event)
        return self.compute_quotes(
            best_bid=best_bid,
            best_ask=best_ask,
            asset_id=self._asset_id,
            book=self._book,
            event=event,
            ts_recv=ts_recv,
            open_orders=open_orders,
        )

    def on_fill(
        self,
        order_id: str,
        asset_id: str,
        side: str,
        fill_price: Decimal,
        fill_size: Decimal,
        fill_status: str,
        seq: int,
        ts_recv: float,
    ) -> None:
        if side.upper() == "BUY":
            self._inventory += fill_size
        else:
            self._inventory -= fill_size

    # ------------------------------------------------------------------
    # Quote model primitives
    # ------------------------------------------------------------------

    def _update_book_state(self, event: dict[str, Any]) -> None:
        if self._book is None or self._asset_id is None:
            return

        event_type = str(event.get("event_type") or "")
        event_asset = str(event.get("asset_id") or "")

        if event_type == "price_change" and "price_changes" in event:
            for entry in event.get("price_changes", []):
                if str(entry.get("asset_id") or "") == self._asset_id:
                    self._book.apply_single_delta(entry)
            return

        if event_asset == self._asset_id:
            self._book.apply(event)

    def _microprice(self, book: Any) -> Optional[float]:
        bids, asks = self._top_levels(book, depth=3)
        if not bids or not asks:
            return None

        weighted_sum = 0.0
        total_size = 0.0
        for level in bids + asks:
            price = _to_float(level.get("price"), "price")
            size = _to_float(level.get("size"), "size")
            if size <= 0:
                continue
            weighted_sum += price * size
            total_size += size

        if total_size <= 0:
            return None
        return weighted_sum / total_size

    def _top_levels(self, book: Any, depth: int) -> tuple[list[dict[str, float]], list[dict[str, float]]]:
        if isinstance(book, L2Book):
            return book.top_bids(depth), book.top_asks(depth)
        if hasattr(book, "top_bids") and hasattr(book, "top_asks"):
            return list(book.top_bids(depth)), list(book.top_asks(depth))
        if not isinstance(book, dict):
            return [], []

        bids = self._normalized_levels(book.get("bids") or [], reverse=True, depth=depth)
        asks = self._normalized_levels(book.get("asks") or [], reverse=False, depth=depth)
        return bids, asks

    def _normalized_levels(
        self,
        levels: list[Any],
        *,
        reverse: bool,
        depth: int,
    ) -> list[dict[str, float]]:
        normalized: list[dict[str, float]] = []
        for level in levels:
            if not isinstance(level, dict):
                continue
            try:
                price = _to_float(level.get("price"), "price")
                size = _to_float(level.get("size"), "size")
            except ValueError:
                continue
            if size <= 0:
                continue
            normalized.append({"price": price, "size": size})

        normalized.sort(key=lambda row: row["price"], reverse=reverse)
        return normalized[:depth]

    def _record_mid(self, t_now: float, mid: float) -> None:
        self._mid_history.append((t_now, mid))
        cutoff = t_now - self.mm_config.vol_window_seconds
        while self._mid_history and self._mid_history[0][0] < cutoff:
            self._mid_history.popleft()

    def _sigma_sq(self, t_now: float) -> float:
        cutoff = t_now - self.mm_config.vol_window_seconds
        while self._mid_history and self._mid_history[0][0] < cutoff:
            self._mid_history.popleft()

        if len(self._mid_history) < 3:
            return _DEFAULT_SIGMA_SQ

        changes = [
            current_mid - previous_mid
            for (_, previous_mid), (_, current_mid) in zip(self._mid_history, list(self._mid_history)[1:])
        ]
        if len(changes) < 2:
            return _DEFAULT_SIGMA_SQ
        return float(pvariance(changes))

    def _compute_quotes(self, mid: float, t_elapsed_hours: float, sigma_sq: float) -> tuple[float, float]:
        remaining_hours = max(self.mm_config.session_hours - t_elapsed_hours, _MIN_REMAINING_HOURS)
        inventory_units = float(self._inventory)
        order_size = float(self.order_size)
        q = inventory_units / (order_size + 1e-9)

        reservation_price = mid - (q * self.mm_config.gamma * sigma_sq * remaining_hours)
        spread = (
            self.mm_config.gamma * sigma_sq * remaining_hours
            + (2.0 / self.mm_config.gamma) * math.log(1.0 + (self.mm_config.gamma / self.mm_config.kappa))
        )

        if mid < self.mm_config.resolution_guard or mid > (1.0 - self.mm_config.resolution_guard):
            spread *= 2.5

        spread = _clamp(spread, self.mm_config.min_spread, self.mm_config.max_spread)
        bid = _clamp(reservation_price - (spread / 2.0), _MIN_BID_PRICE, _MAX_BID_PRICE)
        ask = _clamp(reservation_price + (spread / 2.0), _MIN_ASK_PRICE, _MAX_ASK_PRICE)
        return round(bid, 3), round(ask, 3)

    # ------------------------------------------------------------------
    # Quote generation
    # ------------------------------------------------------------------

    def compute_quotes(
        self,
        best_bid: Optional[float],
        best_ask: Optional[float],
        asset_id: Optional[str] = None,
        *,
        book: Optional[Any] = None,
        event: Optional[dict[str, Any]] = None,
        ts_recv: Optional[float] = None,
        open_orders: Optional[dict[str, Any]] = None,
        hours_to_resolution: Optional[float] = None,
    ) -> list[OrderIntent]:
        """Compute desired bid / ask quotes as OrderIntents.

        When ``event`` and ``ts_recv`` are provided, the strategy updates its
        internal volatility window and time horizon. The plain best bid / ask
        path remains available for the live CLI bridge.
        """

        used_asset_id = asset_id or self._asset_id or "unknown"

        if best_bid is None or best_ask is None:
            return []

        bb = Decimal(str(best_bid))
        ba = Decimal(str(best_ask))
        if bb >= ba:
            logger.debug("market_maker_v0: crossed book bid=%s ask=%s, no quotes", bb, ba)
            return []

        if self.order_size < self.min_order_size:
            return []

        book_view = book if book is not None else event
        mid = self._microprice(book_view)
        if mid is None:
            mid = (float(best_bid) + float(best_ask)) / 2.0

        if ts_recv is not None:
            t_elapsed_hours = self._t_elapsed_hours(ts_recv, event=event, hours_to_resolution=hours_to_resolution)
            self._record_mid(ts_recv, mid)
            sigma_sq = self._sigma_sq(ts_recv)
        else:
            sigma_sq = self._sigma_sq(self._history_now())
            t_elapsed_hours = self._default_t_elapsed_hours(hours_to_resolution=hours_to_resolution)

        bid_raw, ask_raw = self._compute_quotes(mid, t_elapsed_hours, sigma_sq)

        # Legacy outward offset remains supported for config compatibility.
        outward_offset = float(self.quote_ticks_from_bbo) * float(self.tick_size)
        bid_raw = _clamp(bid_raw - outward_offset, _MIN_BID_PRICE, _MAX_BID_PRICE)
        ask_raw = _clamp(ask_raw + outward_offset, _MIN_ASK_PRICE, _MAX_ASK_PRICE)

        bid_price = _tick_floor(_to_decimal(f"{bid_raw:.3f}", "bid_price"), self.tick_size)
        ask_price = _tick_ceil(_to_decimal(f"{ask_raw:.3f}", "ask_price"), self.tick_size)

        if bid_price <= _ZERO or ask_price >= _ONE:
            logger.debug(
                "market_maker_v0: prices out of range bid=%s ask=%s, no quotes",
                bid_price,
                ask_price,
            )
            return []

        if bid_price >= ask_price:
            logger.debug(
                "market_maker_v0: computed quotes cross bid=%s >= ask=%s, no quotes",
                bid_price,
                ask_price,
            )
            return []

        if self._should_skip_reprice(bid_price, ask_price, open_orders):
            return []

        self._last_quotes = (bid_price, ask_price)
        return [
            OrderIntent(
                action="submit",
                asset_id=used_asset_id,
                side="BUY",
                limit_price=bid_price,
                size=self.order_size,
                reason="market_maker_v0_bid",
            ),
            OrderIntent(
                action="submit",
                asset_id=used_asset_id,
                side="SELL",
                limit_price=ask_price,
                size=self.order_size,
                reason="market_maker_v0_ask",
            ),
        ]

    def _should_skip_reprice(
        self,
        bid_price: Decimal,
        ask_price: Decimal,
        open_orders: Optional[dict[str, Any]],
    ) -> bool:
        if self._last_quotes is None or not open_orders:
            return False

        sides = {
            str(order.get("side") or "").upper()
            for order in open_orders.values()
            if isinstance(order, dict)
        }
        if not {"BUY", "SELL"}.issubset(sides):
            return False

        last_bid, last_ask = self._last_quotes
        return (
            abs(float(bid_price - last_bid)) < self.mm_config.reprice_threshold
            and abs(float(ask_price - last_ask)) < self.mm_config.reprice_threshold
        )

    def _history_now(self) -> float:
        if self._last_ts_recv is not None:
            return self._last_ts_recv
        if self._mid_history:
            return self._mid_history[-1][0]
        return 0.0

    def _default_t_elapsed_hours(self, *, hours_to_resolution: Optional[float]) -> float:
        remaining = self._hours_to_resolution
        if hours_to_resolution is not None:
            remaining = max(_to_float(hours_to_resolution, "hours_to_resolution"), _MIN_REMAINING_HOURS)
        effective_remaining = min(self.mm_config.session_hours, remaining)
        return max(self.mm_config.session_hours - effective_remaining, 0.0)

    def _t_elapsed_hours(
        self,
        ts_recv: float,
        *,
        event: Optional[dict[str, Any]],
        hours_to_resolution: Optional[float],
    ) -> float:
        if self._session_start_ts is None:
            self._session_start_ts = ts_recv

        elapsed_hours = max((ts_recv - self._session_start_ts) / 3600.0, 0.0)
        remaining_session = max(self.mm_config.session_hours - elapsed_hours, _MIN_REMAINING_HOURS)
        remaining_resolution = self._update_hours_to_resolution(
            ts_recv,
            event=event,
            explicit_hours=hours_to_resolution,
        )
        effective_remaining = min(remaining_session, remaining_resolution)
        return max(self.mm_config.session_hours - effective_remaining, 0.0)

    def _update_hours_to_resolution(
        self,
        ts_recv: float,
        *,
        event: Optional[dict[str, Any]],
        explicit_hours: Optional[float],
    ) -> float:
        resolved_hours: Optional[float] = None
        if explicit_hours is not None:
            resolved_hours = max(_to_float(explicit_hours, "hours_to_resolution"), _MIN_REMAINING_HOURS)
        elif event is not None:
            resolved_hours = self._extract_hours_to_resolution(event, ts_recv)

        if resolved_hours is None:
            resolved_hours = self._hours_to_resolution
            if self._last_ts_recv is not None and ts_recv >= self._last_ts_recv:
                resolved_hours = max(
                    resolved_hours - ((ts_recv - self._last_ts_recv) / 3600.0),
                    _MIN_REMAINING_HOURS,
                )

        self._hours_to_resolution = resolved_hours
        self.hours_to_resolution = resolved_hours
        self._last_ts_recv = ts_recv
        return resolved_hours

    def _extract_hours_to_resolution(
        self,
        event: dict[str, Any],
        ts_recv: float,
    ) -> Optional[float]:
        containers = [event]
        for key in ("market_metadata", "metadata", "market", "market_context"):
            nested = event.get(key)
            if isinstance(nested, dict):
                containers.append(nested)

        for container in containers:
            for key in ("hours_to_resolution", "hoursToResolution"):
                if key not in container:
                    continue
                try:
                    return max(_to_float(container.get(key), key), _MIN_REMAINING_HOURS)
                except ValueError:
                    logger.debug("market_maker_v0: could not parse %s=%r", key, container.get(key))

            for key in (
                "end_date_iso",
                "endDate",
                "end_date",
                "close_time",
                "closeTime",
                "closedTime",
                "resolution_time",
                "resolutionTime",
                "resolutionTimestamp",
            ):
                if key not in container:
                    continue
                target_ts = self._parse_timestamp(container.get(key))
                if target_ts is None:
                    continue
                return max((target_ts - ts_recv) / 3600.0, _MIN_REMAINING_HOURS)

        return None

    def _parse_timestamp(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None

        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 1_000_000_000_000:
                timestamp /= 1000.0
            return timestamp

        text = str(value).strip()
        if not text:
            return None

        try:
            numeric = float(text)
        except ValueError:
            numeric = None
        if numeric is not None:
            if numeric > 1_000_000_000_000:
                numeric /= 1000.0
            return numeric

        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()

    # ------------------------------------------------------------------
    # Convenience: compute as OrderRequests (for live execution layer)
    # ------------------------------------------------------------------

    def compute_order_requests(
        self,
        best_bid: Optional[float],
        best_ask: Optional[float],
        asset_id: str,
    ) -> list:
        """Same as compute_quotes but returns OrderRequest objects."""
        from packages.polymarket.simtrader.execution.live_executor import OrderRequest

        intents = self.compute_quotes(best_bid=best_bid, best_ask=best_ask, asset_id=asset_id)
        requests = []
        for intent in intents:
            if intent.action != "submit":
                continue
            requests.append(
                OrderRequest(
                    asset_id=intent.asset_id or asset_id,
                    side=intent.side,  # type: ignore[arg-type]
                    price=intent.limit_price,  # type: ignore[arg-type]
                    size=intent.size,  # type: ignore[arg-type]
                    post_only=True,
                    meta={"reason": intent.reason or ""},
                )
            )
        return requests
