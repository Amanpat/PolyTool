"""Deterministic accumulation engine for Track 2 / Phase 1A crypto pair bot.

Evaluates one pair-market state and produces an accumulation decision as a
pure data object.  No network calls, no side-effects.

Entry-rule hierarchy
====================
1. **Feed gate** (hard):   Binance feed must be usable (connected + fresh).
                           Stale or disconnected → FREEZE.
2. **Quote gate**:         Both YES and NO best-ask quotes must be present.
                           Missing quote(s) → SKIP.
3. **Target-bid gate**:    Each leg must have ask_price <= target_bid, where
                           target_bid = 0.5 - edge_buffer_per_leg (default 0.46).
                           At least one leg must meet the target; legs that do not
                           meet the target are excluded.  If no leg meets the
                           target, SKIP.
4. **Partial-pair logic**:  If one leg is already accumulated, focus on the
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
        price_history: Rolling reference-feed prices, newest-last.  Empty
            tuple means no history yet.  Used by evaluate_directional_entry().
        cooldown_brackets: Market IDs already entered in this run window.
            Used to enforce one entry per bracket.
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

    # New fields with defaults — all existing call sites stay valid.
    price_history: tuple[float, ...] = field(default_factory=tuple)
    cooldown_brackets: frozenset[str] = field(default_factory=frozenset)


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
        hard_rule_passed: ``True`` when at least one leg meets the target-bid.
            Kept for API compatibility.
        soft_rule_yes_passed: ``True`` when YES meets target_bid.
            Kept for API compatibility.
        soft_rule_no_passed: ``True`` when NO meets target_bid.
            Kept for API compatibility.
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
    # Gate 3 — Target-bid gate (per-leg)                                   #
    # Each leg meets the target when ask_price <= target_bid, where        #
    # target_bid = 0.5 - edge_buffer_per_leg (default 0.46).               #
    # At least one leg must meet the target; legs that miss are excluded.  #
    # ------------------------------------------------------------------ #
    target_bid = Decimal("0.5") - config.edge_buffer_per_leg
    yes_target_met = yes_ask <= target_bid
    no_target_met = no_ask <= target_bid

    rationale["projected_pair_cost"] = str(projected_pair_cost)
    rationale["target_bid"] = str(target_bid)
    rationale["yes_target_met"] = yes_target_met
    rationale["no_target_met"] = no_target_met
    rationale["hard_rule_passed"] = yes_target_met or no_target_met

    if not yes_target_met and not no_target_met:
        rationale["skip_reason"] = "no_leg_meets_target_bid"
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
    # Leg selection: partial-pair state awareness                          #
    # ------------------------------------------------------------------ #
    has_yes = state.yes_accumulated_size > _ZERO
    has_no = state.no_accumulated_size > _ZERO
    partial_state = _classify_partial_state(has_yes, has_no)
    rationale["partial_pair_state"] = partial_state

    legs = _select_legs(partial_state, yes_target_met, no_target_met)

    if not legs:
        rationale["skip_reason"] = "no_leg_meets_target_bid"
        return AccumulationIntent(
            action=ACTION_SKIP,
            legs=(),
            rationale=rationale,
            projected_pair_cost=projected_pair_cost,
            hard_rule_passed=False,
            soft_rule_yes_passed=yes_target_met,
            soft_rule_no_passed=no_target_met,
        )

    return AccumulationIntent(
        action=ACTION_ACCUMULATE,
        legs=legs,
        rationale=rationale,
        projected_pair_cost=projected_pair_cost,
        hard_rule_passed=True,
        soft_rule_yes_passed=yes_target_met,
        soft_rule_no_passed=no_target_met,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _feed_is_usable(snapshot: Optional[ReferencePriceSnapshot]) -> bool:
    if snapshot is None:
        return False
    return snapshot.is_usable


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
    yes_target_met: bool,
    no_target_met: bool,
) -> tuple[str, ...]:
    """Select which legs to include based on partial-pair state and target-bid.

    Priority logic:
    - ``yes_only``:  We already hold YES; complete the pair by focusing on NO.
    - ``no_only``:   We already hold NO; complete the pair by focusing on YES.
    - ``none`` / ``both_legs``: Bid whichever legs meet the target-bid.
    """
    if partial_state == "yes_only":
        return (LEG_NO,) if no_target_met else ()
    if partial_state == "no_only":
        return (LEG_YES,) if yes_target_met else ()

    legs = []
    if yes_target_met:
        legs.append(LEG_YES)
    if no_target_met:
        legs.append(LEG_NO)
    return tuple(legs)


# ---------------------------------------------------------------------------
# Momentum signal model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MomentumSignal:
    """Result of a momentum signal computation.

    Attributes:
        signal_direction: ``"UP"``, ``"DOWN"``, or ``"NONE"``.
        price_change_pct: Fractional price change from baseline to current
            (positive = price rose, negative = fell).
        reference_price: Most recent price used for signal (price_history[-1]).
        baseline_price: Oldest price in the window (price_history[0]).
    """

    signal_direction: str   # "UP" | "DOWN" | "NONE"
    price_change_pct: float
    reference_price: float
    baseline_price: float


def compute_momentum_signal(
    price_history: list[float],
    threshold: float,
) -> MomentumSignal:
    """Compute a directional momentum signal from a rolling price history.

    Args:
        price_history: List of prices in chronological order (newest-last).
        threshold: Fractional threshold above which a signal fires (e.g. 0.003).

    Returns:
        :class:`MomentumSignal` with signal_direction in ``("UP", "DOWN", "NONE")``.
    """
    if len(price_history) < 2:
        return MomentumSignal(
            signal_direction="NONE",
            price_change_pct=0.0,
            reference_price=price_history[-1] if price_history else 0.0,
            baseline_price=price_history[0] if price_history else 0.0,
        )

    baseline = price_history[0]
    current = price_history[-1]

    if baseline == 0.0:
        return MomentumSignal(
            signal_direction="NONE",
            price_change_pct=0.0,
            reference_price=current,
            baseline_price=baseline,
        )

    pct_change = (current - baseline) / baseline

    if pct_change >= threshold:
        direction = "UP"
    elif pct_change <= -threshold:
        direction = "DOWN"
    else:
        direction = "NONE"

    return MomentumSignal(
        signal_direction=direction,
        price_change_pct=pct_change,
        reference_price=current,
        baseline_price=baseline,
    )


# ---------------------------------------------------------------------------
# Directional entry engine (gabagool22-pattern)
# ---------------------------------------------------------------------------


def evaluate_directional_entry(
    state: PairMarketState,
    config: CryptoPairPaperModeConfig,
) -> AccumulationIntent:
    """Evaluate whether to enter a directional position for one pair market.

    Replaces the old pair-cost gate with a momentum-driven directional signal.
    Gabagool22's observed pattern: read BTC/ETH momentum, buy the FAVORITE leg
    as taker when momentum fires, buy the HEDGE leg as a cheap maker limit.

    Gate hierarchy:
    1. Feed gate  — feed must be usable (FREEZE if not).
    2. Quote gate — both YES/NO asks must be present (SKIP if not).
    3. Momentum gate — abs(price_change) > threshold (SKIP with reason="no_momentum_signal").
    4. Cooldown gate — bracket not already entered (SKIP with reason="bracket_cooldown").
    5. Favorite price gate — favorite_ask <= max_favorite_entry (SKIP if too expensive).
    6. Entry — return ACCUMULATE with favorite+hedge legs.

    Pure function — no network calls, no side-effects.
    """
    rationale: dict[str, Any] = {
        "symbol": state.symbol,
        "duration_min": state.duration_min,
        "market_id": state.market_id,
        "feed_usable": False,
        "hard_rule_passed": False,
        "soft_rule_yes": None,
        "soft_rule_no": None,
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
    # Gate 3 — Momentum signal                                             #
    # ------------------------------------------------------------------ #
    price_history_list = list(state.price_history)
    momentum = config.momentum
    signal = compute_momentum_signal(price_history_list, momentum.momentum_threshold)
    rationale["signal_direction"] = signal.signal_direction
    rationale["price_change_pct"] = signal.price_change_pct
    rationale["reference_price"] = signal.reference_price

    if signal.signal_direction == "NONE":
        rationale["skip_reason"] = "no_momentum_signal"
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
    # Gate 4 — Cooldown (one entry per bracket window)                     #
    # ------------------------------------------------------------------ #
    if state.market_id in state.cooldown_brackets:
        rationale["skip_reason"] = "bracket_cooldown"
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
    # Gate 5 — Favorite selection and price check                          #
    # ------------------------------------------------------------------ #
    if signal.signal_direction == "UP":
        favorite_leg = LEG_YES
        hedge_leg = LEG_NO
        favorite_ask = yes_ask
    else:  # DOWN
        favorite_leg = LEG_NO
        hedge_leg = LEG_YES
        favorite_ask = no_ask

    hedge_price = momentum.max_hedge_price

    rationale["favorite_leg"] = favorite_leg
    rationale["hedge_leg"] = hedge_leg
    rationale["favorite_price"] = float(favorite_ask)
    rationale["hedge_price"] = hedge_price
    rationale["favorite_leg_size_usdc"] = momentum.favorite_leg_size_usdc
    rationale["hedge_leg_size_usdc"] = momentum.hedge_leg_size_usdc

    if float(favorite_ask) > momentum.max_favorite_entry:
        rationale["skip_reason"] = "favorite_too_expensive"
        return AccumulationIntent(
            action=ACTION_SKIP,
            legs=(),
            rationale=rationale,
            projected_pair_cost=projected_pair_cost,
            hard_rule_passed=False,
            soft_rule_yes_passed=(favorite_leg == LEG_NO),  # hedge leg is YES
            soft_rule_no_passed=(favorite_leg == LEG_YES),  # hedge leg is NO
        )

    # ------------------------------------------------------------------ #
    # Entry                                                                #
    # ------------------------------------------------------------------ #
    rationale["hard_rule_passed"] = True
    return AccumulationIntent(
        action=ACTION_ACCUMULATE,
        legs=(favorite_leg, hedge_leg),
        rationale=rationale,
        projected_pair_cost=projected_pair_cost,
        hard_rule_passed=True,
        soft_rule_yes_passed=(favorite_leg == LEG_YES),
        soft_rule_no_passed=(favorite_leg == LEG_NO),
    )
