"""Deterministic accumulation engine for Track 2 / Phase 1A crypto pair bot.

Evaluates one pair-market state and produces an accumulation decision as a
pure data object.  No network calls, no side-effects.

Entry-rule hierarchy
====================
1. **Feed gate** (hard):   Binance feed must be usable (connected + fresh).
                           Stale or disconnected → FREEZE.
2. **Quote gate**:         Both YES and NO best-ask quotes must be present.
                           Missing quote(s) → SKIP.
3. **Hard pair-cost rule**: YES_ask + NO_ask ≤ config.target_pair_cost_threshold.
                           Pair too expensive → SKIP.
4. **Soft fair-value rule**: Each leg is only included when its ask price is
                             strictly below its fair-value estimate (leg is
                             underpriced vs model).  No fair-value estimate
                             available → soft rule passes (no filter applied).
5. **Partial-pair logic**:  If one leg is already accumulated, focus on the
                            missing leg rather than both.

All monetary values use Python ``Decimal`` for precision consistency with the
paper ledger.  Never import from the live-execution layer here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from .config_models import CryptoPairPaperModeConfig
from .reference_feed import FeedConnectionState, ReferencePriceSnapshot

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEG_YES = "YES"
LEG_NO = "NO"

ACTION_ACCUMULATE = "accumulate"
ACTION_SKIP = "skip"
ACTION_FREEZE = "freeze"

_ZERO = Decimal("0")


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BestQuote:
    """Best ask price for one token leg."""

    leg: str        # "YES" | "NO"
    token_id: str
    ask_price: Decimal


@dataclass(frozen=True)
class PairMarketState:
    """Complete observed state for one pair market evaluation cycle.

    Attributes:
        symbol: "BTC", "ETH", or "SOL".
        duration_min: 5 or 15.
        market_id: Unique market identifier (slug or condition_id).
        yes_quote: Best ask for YES leg; ``None`` if unavailable.
        no_quote: Best ask for NO leg; ``None`` if unavailable.
        yes_accumulated_size: YES contracts already accumulated this cycle.
        no_accumulated_size: NO contracts already accumulated this cycle.
        fair_value_yes: Fair probability for YES from fair_value.py; ``None``
            if not computed (soft rule skipped).
        fair_value_no: Fair probability for NO; ``None`` if not computed.
        feed_snapshot: Binance reference snapshot for freeze-gate check.
            ``None`` is treated as unusable (triggers FREEZE).
    """

    symbol: str
    duration_min: int
    market_id: str

    yes_quote: Optional[BestQuote]
    no_quote: Optional[BestQuote]

    yes_accumulated_size: Decimal = _ZERO
    no_accumulated_size: Decimal = _ZERO

    fair_value_yes: Optional[float] = None
    fair_value_no: Optional[float] = None

    feed_snapshot: Optional[ReferencePriceSnapshot] = None


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccumulationIntent:
    """Decision output from the accumulation engine for one evaluation cycle.

    Attributes:
        action: ``"accumulate"`` | ``"skip"`` | ``"freeze"``.
        legs: Which legs to bid for.  Empty tuple on skip/freeze.
        rationale: Diagnostic flags; always populated regardless of action.
        projected_pair_cost: YES_ask + NO_ask at evaluation time.
            ``None`` when quotes are unavailable or feed is frozen.
        hard_rule_passed: ``True`` when projected pair cost ≤ threshold.
        soft_rule_yes_passed: ``True`` when YES ask < fair_value_yes, or when
            no fair-value estimate is available (rule vacuously passes).
        soft_rule_no_passed: Same as above for NO leg.
    """

    action: str
    legs: tuple[str, ...]

    rationale: dict[str, Any]

    projected_pair_cost: Optional[Decimal]
    hard_rule_passed: bool
    soft_rule_yes_passed: bool
    soft_rule_no_passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "legs": list(self.legs),
            "rationale": self.rationale,
            "projected_pair_cost": (
                str(self.projected_pair_cost)
                if self.projected_pair_cost is not None
                else None
            ),
            "hard_rule_passed": self.hard_rule_passed,
            "soft_rule_yes_passed": self.soft_rule_yes_passed,
            "soft_rule_no_passed": self.soft_rule_no_passed,
        }


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------


def evaluate_accumulation(
    state: PairMarketState,
    config: CryptoPairPaperModeConfig,
) -> AccumulationIntent:
    """Evaluate whether to accumulate positions for one pair market.

    Pure function — no network calls, no side-effects.

    Args:
        state: Current market state including quotes, accumulated sizes, fair
            values, and the reference-feed snapshot.
        config: Paper-mode configuration (thresholds, filters, safety knobs).

    Returns:
        :class:`AccumulationIntent` — never raises; all failure paths produce
        an ``ACTION_SKIP`` or ``ACTION_FREEZE`` result with populated rationale.
    """
    rationale: dict[str, Any] = {
        "symbol": state.symbol,
        "duration_min": state.duration_min,
        "market_id": state.market_id,
        "feed_usable": False,
        "hard_rule_passed": False,
        "soft_rule_yes": None,
        "soft_rule_no": None,
        "partial_pair_state": None,
    }

    # ------------------------------------------------------------------ #
    # Gate 1 — Feed gate (FREEZE on stale or disconnected)                #
    # ------------------------------------------------------------------ #
    feed_usable = _feed_is_usable(state.feed_snapshot)
    rationale["feed_usable"] = feed_usable

    if not feed_usable:
        conn_state = (
            state.feed_snapshot.connection_state.value
            if state.feed_snapshot is not None
            else "no_snapshot"
        )
        rationale["freeze_reason"] = f"feed_not_usable:{conn_state}"
        return AccumulationIntent(
            action=ACTION_FREEZE,
            legs=(),
            rationale=rationale,
            projected_pair_cost=None,
            hard_rule_passed=False,
            soft_rule_yes_passed=False,
            soft_rule_no_passed=False,
        )

    # ------------------------------------------------------------------ #
    # Gate 2 — Quote availability                                          #
    # ------------------------------------------------------------------ #
    if state.yes_quote is None or state.no_quote is None:
        missing = []
        if state.yes_quote is None:
            missing.append(LEG_YES)
        if state.no_quote is None:
            missing.append(LEG_NO)
        rationale["skip_reason"] = f"missing_quotes:{','.join(missing)}"
        return AccumulationIntent(
            action=ACTION_SKIP,
            legs=(),
            rationale=rationale,
            projected_pair_cost=None,
            hard_rule_passed=False,
            soft_rule_yes_passed=False,
            soft_rule_no_passed=False,
        )

    yes_ask = state.yes_quote.ask_price
    no_ask = state.no_quote.ask_price
    projected_pair_cost = yes_ask + no_ask

    # ------------------------------------------------------------------ #
    # Gate 3 — Hard pair-cost rule                                         #
    # ------------------------------------------------------------------ #
    threshold = config.target_pair_cost_threshold
    hard_rule_passed = projected_pair_cost <= threshold
    rationale["hard_rule_passed"] = hard_rule_passed
    rationale["projected_pair_cost"] = str(projected_pair_cost)
    rationale["threshold"] = str(threshold)

    if not hard_rule_passed:
        rationale["skip_reason"] = "hard_rule_failed"
        return AccumulationIntent(
            action=ACTION_SKIP,
            legs=(),
            rationale=rationale,
            projected_pair_cost=projected_pair_cost,
            hard_rule_passed=False,
            soft_rule_yes_passed=False,
            soft_rule_no_passed=False,
        )

    # ------------------------------------------------------------------ #
    # Gate 4 — Soft fair-value rules (per leg)                             #
    # ------------------------------------------------------------------ #
    soft_yes = _soft_rule_passes(yes_ask, state.fair_value_yes, LEG_YES, rationale)
    soft_no = _soft_rule_passes(no_ask, state.fair_value_no, LEG_NO, rationale)

    # ------------------------------------------------------------------ #
    # Leg selection: partial-pair state awareness                          #
    # ------------------------------------------------------------------ #
    has_yes = state.yes_accumulated_size > _ZERO
    has_no = state.no_accumulated_size > _ZERO
    partial_state = _classify_partial_state(has_yes, has_no)
    rationale["partial_pair_state"] = partial_state

    legs = _select_legs(partial_state, soft_yes, soft_no)

    if not legs:
        rationale["skip_reason"] = "soft_rule_blocked_all_legs"
        return AccumulationIntent(
            action=ACTION_SKIP,
            legs=(),
            rationale=rationale,
            projected_pair_cost=projected_pair_cost,
            hard_rule_passed=True,
            soft_rule_yes_passed=soft_yes,
            soft_rule_no_passed=soft_no,
        )

    return AccumulationIntent(
        action=ACTION_ACCUMULATE,
        legs=legs,
        rationale=rationale,
        projected_pair_cost=projected_pair_cost,
        hard_rule_passed=True,
        soft_rule_yes_passed=soft_yes,
        soft_rule_no_passed=soft_no,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _feed_is_usable(snapshot: Optional[ReferencePriceSnapshot]) -> bool:
    if snapshot is None:
        return False
    return snapshot.is_usable


def _soft_rule_passes(
    ask_price: Decimal,
    fair_prob: Optional[float],
    leg: str,
    rationale: dict[str, Any],
) -> bool:
    """Evaluate the soft fair-value rule for one leg.

    Returns ``True`` (passes) when the ask price is strictly below the fair-
    probability estimate.  If no fair-value estimate is available the rule
    vacuously passes — the hard pair-cost rule is the only active gate.
    """
    key = f"soft_rule_{leg.lower()}"
    if fair_prob is None:
        rationale[key] = {"passed": True, "reason": "no_fair_value_estimate"}
        return True

    ask_float = float(ask_price)
    passed = ask_float < fair_prob
    rationale[key] = {
        "passed": passed,
        "ask": ask_float,
        "fair_prob": fair_prob,
        "reason": "underpriced" if passed else "overpriced",
    }
    return passed


def _classify_partial_state(has_yes: bool, has_no: bool) -> str:
    if has_yes and has_no:
        return "both_legs"
    if has_yes:
        return "yes_only"
    if has_no:
        return "no_only"
    return "none"


def _select_legs(
    partial_state: str,
    soft_yes: bool,
    soft_no: bool,
) -> tuple[str, ...]:
    """Select which legs to include based on partial-pair state and soft rules.

    Priority logic:
    - ``yes_only``:  We already hold YES; complete the pair by focusing on NO.
    - ``no_only``:   We already hold NO; complete the pair by focusing on YES.
    - ``none`` / ``both_legs``: Bid whichever legs pass the soft rule.
    """
    if partial_state == "yes_only":
        return (LEG_NO,) if soft_no else ()
    if partial_state == "no_only":
        return (LEG_YES,) if soft_yes else ()

    legs = []
    if soft_yes:
        legs.append(LEG_YES)
    if soft_no:
        legs.append(LEG_NO)
    return tuple(legs)
