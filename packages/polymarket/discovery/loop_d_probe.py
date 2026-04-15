"""Loop D feasibility probe helpers.

This module provides minimal, offline-testable helper functions that produce
evidence for the Loop D managed CLOB subscription feasibility assessment.

IMPORTANT: This is a FEASIBILITY-ONLY module.
- It does NOT implement Loop D.
- It does NOT modify ClobStreamClient, Loop A, Loop B/C, or any v1 code.
- It is standalone — the only optional external import is GammaClient for the
  live convenience wrapper ``bootstrap_token_inventory``.

See docs/dev_logs/2026-04-15_wallet_discovery_loop_d_pof.md for the full
feasibility verdict and evidence.
"""

from __future__ import annotations

from typing import Any, Optional


# ---------------------------------------------------------------------------
# 1. Gamma bootstrap token counter
# ---------------------------------------------------------------------------

def count_subscribable_tokens(markets: list[Any]) -> dict:
    """Summarize token subscription capacity from a list of Market-like objects.

    Accepts a list of either:
    - ``Market`` dataclass instances (from ``packages.polymarket.gamma``)
    - Plain ``dict`` objects with keys ``clob_token_ids``, ``accepting_orders``,
      and optionally ``category``.

    Returns:
        dict with keys:
          - ``total_markets`` (int): number of markets in the input.
          - ``total_tokens`` (int): total clob_token_ids across all markets.
          - ``accepting_orders_tokens`` (int): token count where the market's
            ``accepting_orders`` flag is True.
          - ``category_breakdown`` (dict[str, int]): token count per category.
    """
    total_markets = len(markets)
    total_tokens = 0
    accepting_orders_tokens = 0
    category_breakdown: dict[str, int] = {}

    for market in markets:
        # Support both dataclass and dict
        if isinstance(market, dict):
            token_ids: list = market.get("clob_token_ids") or []
            accepting: Optional[bool] = market.get("accepting_orders")
            category: str = market.get("category") or "unknown"
        else:
            token_ids = getattr(market, "clob_token_ids", None) or []
            accepting = getattr(market, "accepting_orders", None)
            category = getattr(market, "category", None) or "unknown"

        n = len(token_ids)
        total_tokens += n

        if accepting is True:
            accepting_orders_tokens += n

        category_breakdown[category] = category_breakdown.get(category, 0) + n

    return {
        "total_markets": total_markets,
        "total_tokens": total_tokens,
        "accepting_orders_tokens": accepting_orders_tokens,
        "category_breakdown": category_breakdown,
    }


def bootstrap_token_inventory(gamma_client: Any) -> dict:
    """Live convenience wrapper: fetch all active markets then count tokens.

    NOT tested offline. Requires a network connection to the Gamma API.

    Args:
        gamma_client: A ``GammaClient`` instance.

    Returns:
        Same dict shape as ``count_subscribable_tokens``.
    """
    result = gamma_client.fetch_all_markets(active_only=True)
    return count_subscribable_tokens(result.markets)


# ---------------------------------------------------------------------------
# 2. ClobStreamClient gap audit
# ---------------------------------------------------------------------------

def audit_clob_stream_gaps() -> list[dict]:
    """Return a static catalog of ClobStreamClient gaps relevant to Loop D.

    Each entry is a dict with keys:
      - ``gap_id`` (str): short identifier.
      - ``description`` (str): what the gap is.
      - ``severity`` (str): ``"blocker"`` | ``"constraint"`` | ``"enhancement"``.
      - ``code_ref`` (str): location in the codebase where the gap is visible.
      - ``remediation`` (str): how to address the gap.

    This function is PURE (no I/O, no imports from clob_stream.py) and returns
    a deterministic list derived from manual code inspection of:
      packages/polymarket/crypto_pairs/clob_stream.py

    Audit findings as of 2026-04-15:
    - ``_ws_loop`` uses ``ws_conn.recv()`` with a 5 s timeout but sends no PING
      frames. The Polymarket CLOB WS server requires a PING every 10 s or the
      server closes the connection (~30 s grace period typical for WS servers).
    - ``subscribe()`` adds to ``self._subscribed`` (set) but the subscription
      message is only sent at (re)connect time in ``_ws_loop``. There is no
      runtime ``send()`` of a new subscribe message to an open connection.
    - ``_apply_message`` handles ``"book"`` and ``"price_change"`` event types.
      It does NOT handle ``"new_market"`` or ``"market_resolved"`` lifecycle
      events that Loop D would need to maintain the active-market set.
    - The constructor-time token set assumption: ``subscribe()`` populates
      ``self._subscribed`` before ``start()`` is called. Dynamic add/remove
      after start does not send a subscribe/unsubscribe message immediately.
    - On reconnect, ``_ws_loop`` re-subscribes using the current
      ``self._subscribed`` set but does NOT perform a REST backfill for events
      missed during the disconnection window.
    """
    return [
        {
            "gap_id": "G-01",
            "description": (
                "No PING keepalive: _ws_loop sends no WebSocket PING frames. "
                "The CLOB WS server requires a PING every 10 s; without it the "
                "server will close the connection after ~30 s silence."
            ),
            "severity": "blocker",
            "code_ref": (
                "packages/polymarket/crypto_pairs/clob_stream.py:_ws_loop — "
                "recv() loop has no threading.Timer or periodic ws_conn.ping() call"
            ),
            "remediation": (
                "Add a threading.Timer(10, ping_fn) that calls ws_conn.ping() "
                "every 10 s while the connection is open. Reset the timer on "
                "each recv() iteration or use a select-based approach."
            ),
        },
        {
            "gap_id": "G-02",
            "description": (
                "No dynamic subscribe/unsubscribe at runtime: ClobStreamClient.subscribe() "
                "adds to self._subscribed (set) but only takes effect on the NEXT "
                "(re)connect. Loop D needs to add/remove thousands of tokens at runtime "
                "as markets open and close without full reconnection."
            ),
            "severity": "blocker",
            "code_ref": (
                "packages/polymarket/crypto_pairs/clob_stream.py:subscribe() L95-103 — "
                "only updates set; _ws_loop L225-226 sends subscribe msg only at connect"
            ),
            "remediation": (
                "Add a send_subscribe(asset_ids) helper that sends a subscribe "
                "message to the open ws_conn immediately when the thread is running. "
                "Alternatively build a new ManagedSubscriptionClient that wraps "
                "ClobStreamClient with runtime subscription management."
            ),
        },
        {
            "gap_id": "G-03",
            "description": (
                "No new_market / market_resolved event parsing: _apply_message "
                "only dispatches 'book' and 'price_change' event types. Loop D "
                "requires lifecycle events to maintain the active-market set "
                "without constant re-bootstrapping from Gamma."
            ),
            "severity": "constraint",
            "code_ref": (
                "packages/polymarket/crypto_pairs/clob_stream.py:_apply_message L276-294 — "
                "event_type branch handles 'book' and 'price_change' only"
            ),
            "remediation": (
                "Extend _apply_message (or a subclass) to parse 'new_market' "
                "and 'market_resolved' event types, calling registered lifecycle "
                "callbacks. This is a well-defined JSON parsing addition."
            ),
        },
        {
            "gap_id": "G-04",
            "description": (
                "Fixed token set at construction: the design assumes tokens are "
                "subscribed before start() and remain stable for the session. "
                "Loop D manages 800-1600+ tokens that change over time as markets "
                "open/close, requiring a truly dynamic subscription set."
            ),
            "severity": "constraint",
            "code_ref": (
                "packages/polymarket/crypto_pairs/clob_stream.py:__init__ L66-89 — "
                "self._subscribed initialized as empty set; subscribe() called "
                "pre-start() in usage pattern"
            ),
            "remediation": (
                "Decouple token set management from connection lifecycle. "
                "A higher-level subscription manager (bootstrapped from Gamma, "
                "updated via lifecycle events) should call subscribe/unsubscribe "
                "on the underlying client at runtime."
            ),
        },
        {
            "gap_id": "G-05",
            "description": (
                "No reconnect backfill: _ws_loop reconnects and re-subscribes "
                "but does not fetch missed events via REST GET /trades for the "
                "disconnection window. This creates gaps in trade history that "
                "can affect anomaly detectors relying on continuous streams."
            ),
            "severity": "enhancement",
            "code_ref": (
                "packages/polymarket/crypto_pairs/clob_stream.py:_ws_loop L219-271 — "
                "reconnect path re-subscribes only; no REST /trades backfill"
            ),
            "remediation": (
                "On reconnect, record disconnect_time and reconnect_time; "
                "call REST GET /trades with startTs=disconnect_time for each "
                "subscribed asset_id to fill the gap. Paginate if window > 60 s. "
                "This is medium complexity but not a hard blocker for Phase 0."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# 3. Trade event data sufficiency assessment
# ---------------------------------------------------------------------------

#: Canonical detector definitions with their required event fields.
_DETECTOR_REQUIREMENTS: dict[str, list[str]] = {
    "volume_spike": ["asset_id", "size", "timestamp"],
    "price_anomaly": ["asset_id", "price", "timestamp"],
    "trade_burst": ["asset_id", "timestamp", "side"],
    "spread_divergence": ["asset_id", "price", "side", "timestamp"],
    # wallet_attribution requires fields NOT present in CLOB last_trade_price events
    "wallet_attribution": ["maker_address", "taker_address"],
}

_WALLET_ATTRIBUTION_NOTE = (
    "CLOB last_trade_price events do NOT contain wallet addresses. "
    "The 'maker_address' and 'taker_address' fields are absent by design: "
    "the CLOB WS feed exposes market-level trade data only. "
    "Wallet attribution requires a second feed: Alchemy eth_getLogs on the "
    "CTFExchange contract (Polygon), which emits OrderFilled events containing "
    "maker and taker addresses. This is a known two-feed architecture: CLOB "
    "detects WHAT is anomalous (which market, when, at what price/size); "
    "Alchemy tells WHO did it. See Decision - Loop D Managed CLOB Subscription.md."
)


def assess_trade_event_sufficiency(sample_events: list[dict]) -> dict:
    """Assess whether last_trade_price event fields satisfy anomaly detector needs.

    Args:
        sample_events: List of last_trade_price event dicts (can be empty or
            partial). Fixtures are used for offline testing.

    Returns:
        dict with keys:
          - ``fields_present`` (set[str]): all field names found across events.
          - ``fields_needed_for_detectors`` (dict[str, list[str]]): the canonical
            required-fields map per detector.
          - ``detector_readiness`` (dict[str, dict]): per detector:
              ``{"ready": bool, "missing_fields": list[str]}``.
          - ``wallet_attribution_note`` (str): explanation of the two-feed constraint.
    """
    # Collect all field names present across sample events
    fields_present: set[str] = set()
    for event in sample_events:
        if isinstance(event, dict):
            fields_present.update(event.keys())

    # Evaluate each detector
    detector_readiness: dict[str, dict] = {}
    for detector, required in _DETECTOR_REQUIREMENTS.items():
        missing = [f for f in required if f not in fields_present]
        detector_readiness[detector] = {
            "ready": len(missing) == 0,
            "missing_fields": missing,
        }

    return {
        "fields_present": fields_present,
        "fields_needed_for_detectors": dict(_DETECTOR_REQUIREMENTS),
        "detector_readiness": detector_readiness,
        "wallet_attribution_note": _WALLET_ATTRIBUTION_NOTE,
    }


# ---------------------------------------------------------------------------
# 4. Feasibility verdict formatter
# ---------------------------------------------------------------------------

def format_feasibility_verdict(
    token_inventory: dict,
    gaps: list[dict],
    sufficiency: dict,
) -> dict:
    """Combine all three assessments into a structured feasibility verdict.

    Verdict logic:
    - BLOCKED if any gap has severity "blocker" AND all blockers have no
      remediation path (remediation field is empty or None).
    - READY_WITH_CONSTRAINTS if any blocker gaps exist but ALL have a
      non-empty remediation.
    - READY if no gaps have severity "blocker".

    Args:
        token_inventory: Output of ``count_subscribable_tokens``.
        gaps: Output of ``audit_clob_stream_gaps``.
        sufficiency: Output of ``assess_trade_event_sufficiency``.

    Returns:
        dict with keys:
          - ``verdict`` (str): "READY" | "READY_WITH_CONSTRAINTS" | "BLOCKED".
          - ``constraints`` (list[str]): human-readable constraint statements.
          - ``blockers`` (list[str]): blocker statements (empty if not BLOCKED).
          - ``scale_assessment`` (dict): token count summary and throughput note.
          - ``next_steps`` (list[str]): recommended actions.
    """
    blocker_gaps = [g for g in gaps if g.get("severity") == "blocker"]
    constraint_gaps = [g for g in gaps if g.get("severity") == "constraint"]

    # Determine verdict
    if not blocker_gaps:
        verdict = "READY"
    else:
        all_have_remediation = all(
            g.get("remediation", "").strip() for g in blocker_gaps
        )
        if all_have_remediation:
            verdict = "READY_WITH_CONSTRAINTS"
        else:
            verdict = "BLOCKED"

    # Build constraint list
    constraints: list[str] = []
    for g in blocker_gaps:
        constraints.append(
            f"[{g['gap_id']} blocker] {g['description'][:120].rstrip()}"
        )
    for g in constraint_gaps:
        constraints.append(
            f"[{g['gap_id']} constraint] {g['description'][:120].rstrip()}"
        )

    # Wallet attribution is a data constraint derived from sufficiency
    dr = sufficiency.get("detector_readiness", {})
    wallet_info = dr.get("wallet_attribution", {})
    if not wallet_info.get("ready", True):
        constraints.append(
            "[data constraint] CLOB events lack wallet addresses — "
            "Alchemy eth_getLogs required for wallet attribution."
        )

    # Blockers list (only populated if verdict == BLOCKED)
    blockers: list[str] = []
    if verdict == "BLOCKED":
        for g in blocker_gaps:
            if not g.get("remediation", "").strip():
                blockers.append(g["description"])

    # Scale assessment
    total_tokens = token_inventory.get("total_tokens", 0)
    total_markets = token_inventory.get("total_markets", 0)
    accepting = token_inventory.get("accepting_orders_tokens", 0)
    scale_assessment = {
        "total_markets": total_markets,
        "total_tokens": total_tokens,
        "accepting_orders_tokens": accepting,
        "throughput_avg_per_sec": "2-3 (150k-300k trades/day)",
        "throughput_peak_per_sec": "~50",
        "python_process_capacity_per_sec": "10000+",
        "throughput_bottleneck": False,
        "note": (
            "Single Python process can handle 10k+ msg/s; "
            "peak CLOB throughput ~50 msg/s is well within capacity."
        ),
    }

    # Next steps
    next_steps: list[str] = [
        "Implement PING keepalive in ClobStreamClient or new ManagedSubscriptionClient (G-01).",
        "Add runtime subscribe/unsubscribe message sending to open WS connection (G-02).",
        "Parse new_market / market_resolved lifecycle events (G-03).",
        "Build platform-wide subscription manager: bootstrap from Gamma, maintain via lifecycle events.",
        "Live probe: subscribe all active tokens on a single connection, measure stability over 1h.",
        "Estimate Alchemy eth_getLogs CU cost for wallet attribution feed.",
        "Design anomaly detector algorithms (binomial win-rate first per research doc).",
        "Design ClickHouse schema for anomaly events.",
    ]

    return {
        "verdict": verdict,
        "constraints": constraints,
        "blockers": blockers,
        "scale_assessment": scale_assessment,
        "next_steps": next_steps,
    }
