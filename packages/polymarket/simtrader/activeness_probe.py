"""Activeness probe: subscribe to WS market channel for N seconds and count updates.

Used by :class:`~packages.polymarket.simtrader.market_picker.MarketPicker` to
filter out quiet markets before committing to a full recording session.

Only ``price_change`` and ``last_trade_price`` events are counted — the
``book`` event type is deliberately excluded because it represents an initial
snapshot sent on subscribe, not genuine real-time activity.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Iterable, Optional

logger = logging.getLogger(__name__)

# Event types that indicate genuine market activity (order-book changes, trades).
# ``book`` (initial snapshot) and ``tick_size_change`` are intentionally excluded.
_ACTIVE_EVENT_TYPES: frozenset[str] = frozenset({"price_change", "last_trade_price"})

WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
_DEFAULT_RECV_TIMEOUT = 5.0


@dataclass
class ProbeResult:
    """Activeness probe result for one token / asset."""

    token_id: str
    #: Wall-clock seconds the probe actually ran.
    probe_seconds: float
    #: Number of qualifying WS events counted for this asset.
    updates: int
    #: True when ``updates >= min_updates``.
    active: bool


class ActivenessProbe:
    """Subscribe to the Market Channel for a fixed window and count updates.

    Args:
        asset_ids:    Token IDs to subscribe to (typically YES + NO of a market).
        probe_seconds: How long to listen (wall-clock seconds).
        min_updates:  Minimum qualifying event count per token to be considered
                      active (default: 1).
        ws_url:       WebSocket endpoint (default: production Market Channel).
    """

    def __init__(
        self,
        asset_ids: list[str],
        probe_seconds: float,
        min_updates: int = 1,
        ws_url: str = WS_MARKET_URL,
    ) -> None:
        self._asset_ids = list(asset_ids)
        self._probe_seconds = probe_seconds
        self._min_updates = max(1, int(min_updates))
        self._ws_url = ws_url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict[str, ProbeResult]:
        """Subscribe via live WebSocket and return per-asset probe results.

        Exits early if every tracked asset has already met ``min_updates``
        before the window elapses.

        Raises:
            ImportError: if ``websocket-client`` is not installed.
        """
        try:
            import websocket  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "websocket-client is required for the activeness probe. "
                "Run: pip install 'websocket-client>=1.6'"
            ) from exc

        timeout_exc = getattr(websocket, "WebSocketTimeoutException", TimeoutError)
        closed_exc = getattr(
            websocket, "WebSocketConnectionClosedException", OSError
        )

        counts: dict[str, int] = {aid: 0 for aid in self._asset_ids}
        start = time.monotonic()
        deadline = time.time() + self._probe_seconds

        subscribe_msg = json.dumps(
            {
                "assets_ids": self._asset_ids,
                "type": "market",
                "custom_feature_enabled": True,
                "initial_dump": True,
            }
        )

        ws = None
        try:
            ws = websocket.WebSocket()
            ws.connect(self._ws_url)
            ws.settimeout(_DEFAULT_RECV_TIMEOUT)
            ws.send(subscribe_msg)
            logger.debug(
                "Probe: subscribed to %d asset(s) for %.1fs",
                len(self._asset_ids),
                self._probe_seconds,
            )

            while time.time() < deadline:
                # Early exit: all assets have met the threshold.
                if self._all_met(counts):
                    logger.debug("Probe: all assets met min_updates=%d early", self._min_updates)
                    break

                try:
                    raw = ws.recv()
                except timeout_exc:
                    continue  # keep waiting until deadline
                except (closed_exc, OSError) as exc:
                    logger.debug("Probe: WS disconnected: %s", exc)
                    break

                try:
                    frames = json.loads(raw)
                    if not isinstance(frames, list):
                        frames = [frames]
                    for evt in frames:
                        self._count_event(evt, counts)
                except Exception:  # noqa: BLE001
                    pass

        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:  # noqa: BLE001
                    pass

        elapsed = time.monotonic() - start
        results = self._build_results(counts, elapsed)
        logger.debug(
            "Probe done in %.2fs: %s",
            elapsed,
            {tid[:8]: r.updates for tid, r in results.items()},
        )
        return results

    def run_from_source(self, source: Iterable[dict]) -> dict[str, ProbeResult]:
        """Offline probe using injected event dicts — for testing.

        Args:
            source: Iterable of event dicts that have an ``event_type`` field
                    (same format as ``events.jsonl`` rows produced by the tape
                    recorder or shadow runner).

        Returns:
            Per-asset :class:`ProbeResult` mapping (same structure as
            :meth:`run`).
        """
        counts: dict[str, int] = {aid: 0 for aid in self._asset_ids}
        start = time.monotonic()

        for evt in source:
            self._count_event(evt, counts)
            # Early exit when all assets have met the threshold.
            if self._all_met(counts):
                break

        elapsed = time.monotonic() - start
        return self._build_results(counts, elapsed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _all_met(self, counts: dict[str, int]) -> bool:
        return all(counts[aid] >= self._min_updates for aid in self._asset_ids)

    def _count_event(self, event: object, counts: dict[str, int]) -> None:
        """Increment per-asset counters for qualifying event types."""
        if not isinstance(event, dict):
            return

        etype = event.get("event_type") or event.get("type")
        if etype not in _ACTIVE_EVENT_TYPES:
            return

        # Modern batched format: price_changes is a list, each entry has asset_id.
        if etype == "price_change" and isinstance(event.get("price_changes"), list):
            for entry in event["price_changes"]:
                if not isinstance(entry, dict):
                    continue
                aid = entry.get("asset_id")
                if aid and aid in counts:
                    counts[aid] += 1
        else:
            aid = event.get("asset_id")
            if aid and aid in counts:
                counts[aid] += 1

    def _build_results(
        self, counts: dict[str, int], elapsed: float
    ) -> dict[str, ProbeResult]:
        return {
            aid: ProbeResult(
                token_id=aid,
                probe_seconds=elapsed,
                updates=counts[aid],
                active=counts[aid] >= self._min_updates,
            )
            for aid in self._asset_ids
        }
