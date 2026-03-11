"""Pre-sweep tape eligibility check — fast-fail before a full scenario sweep.

This module scans a recorded tape to determine whether it is actionable for a
given strategy configuration.  Running 24 scenarios on a tape that can never
produce a single order wastes time and produces a misleading FAILED gate
artifact whose rejection counts are the only diagnostic signal.

The check is purely diagnostic: it does not soften gate thresholds, strategy
entry logic, or profitability criteria.  Its sole purpose is to surface the
root cause before the sweep starts so that the operator can fix the input
(choose a different market / tape) rather than wait for all 24 scenarios to
finish and then read the rejection counts.

Eligibility rules for ``binary_complement_arb``
------------------------------------------------
A tape is eligible if it contains at least one tick where **both** of the
following hold simultaneously:

1. **Sufficient depth**: the YES best-ask size >= ``max_size`` AND the NO
   best-ask size >= ``max_size`` (the same depth gate the strategy uses before
   attempting an entry).

2. **Positive edge**: ``yes_best_ask + no_best_ask < 1 - buffer`` (the same
   complement-edge condition the strategy checks after the depth gate).

If neither condition is ever met, the tape is non-actionable for the strategy
at the configured parameters and the sweep is rejected with a clear reason
before any scenario is run.

Other strategies
----------------
Strategies not in the check registry are treated as always-eligible (no-op
check).  Only ``binary_complement_arb`` is checked at this time.

Public API
----------
- ``SweepEligibilityError`` — raised by ``run_sweep`` when a tape is ineligible.
- ``EligibilityResult``     — returned by the check functions for inspection /
                             testing.
- ``check_sweep_eligibility(events_path, strategy_name, strategy_config)``
  — dispatch point called by ``run_sweep``; raises ``SweepEligibilityError``
    when ineligible.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from ..orderbook.l2book import L2Book
from ..tape.schema import EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE
from .runner import SweepConfigError

logger = logging.getLogger(__name__)

_ONE = Decimal("1")
_ZERO = Decimal("0")

# Name of the only strategy that currently has an eligibility check.
_BINARY_ARB_STRATEGY = "binary_complement_arb"


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class SweepEligibilityError(SweepConfigError):
    """Raised when a tape is non-actionable for the configured strategy.

    Subclasses ``SweepConfigError`` so the CLI's existing except-clause
    catches it cleanly and returns exit code 1.
    """


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class EligibilityResult:
    """Outcome of a pre-sweep eligibility check.

    Attributes:
        eligible:  True iff the tape passes all eligibility rules.
        reason:    Human-readable summary.  Empty string when eligible.
        stats:     Diagnostic counters from the scan.
    """

    eligible: bool
    reason: str = ""
    stats: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


def check_sweep_eligibility(
    events_path: Path,
    strategy_name: str,
    strategy_config: dict[str, Any],
) -> None:
    """Run the pre-sweep eligibility check for *strategy_name*.

    Raises:
        SweepEligibilityError: If the tape is non-actionable.

    If the strategy has no registered check, this is a no-op (returns None).
    """
    if strategy_name != _BINARY_ARB_STRATEGY:
        return  # No check registered for this strategy.

    result = check_binary_arb_tape_eligibility(events_path, strategy_config)
    if not result.eligible:
        raise SweepEligibilityError(
            f"[pre-sweep eligibility] Tape is non-actionable — {result.reason}. "
            f"Skipping 24-scenario sweep.  Diagnostic stats: {result.stats}"
        )
    logger.info(
        "[pre-sweep eligibility] Tape eligible for %s.  Stats: %s",
        strategy_name,
        result.stats,
    )


# ---------------------------------------------------------------------------
# binary_complement_arb eligibility check
# ---------------------------------------------------------------------------


def check_binary_arb_tape_eligibility(
    events_path: Path,
    strategy_config: dict[str, Any],
) -> EligibilityResult:
    """Scan a tape and check whether it is actionable for binary_complement_arb.

    Args:
        events_path:     Path to an ``events.jsonl`` tape file.
        strategy_config: Strategy config dict (must include ``yes_asset_id``,
                         ``no_asset_id``, ``max_size``, ``buffer``).

    Returns:
        ``EligibilityResult`` with ``eligible=True`` if the tape contains at
        least one tick satisfying the depth + edge preconditions, or
        ``eligible=False`` with a clear reason string otherwise.
    """
    yes_id = str(strategy_config.get("yes_asset_id", ""))
    no_id = str(strategy_config.get("no_asset_id", ""))

    try:
        max_size = Decimal(str(strategy_config.get("max_size", "50")))
    except (InvalidOperation, TypeError, ValueError):
        max_size = Decimal("50")

    try:
        buffer = Decimal(str(strategy_config.get("buffer", "0.01")))
    except (InvalidOperation, TypeError, ValueError):
        buffer = Decimal("0.01")

    threshold = _ONE - buffer  # sum_ask must be strictly below this to enter

    yes_book = L2Book(yes_id, strict=False)
    no_book = L2Book(no_id, strict=False)

    stats: dict[str, Any] = {
        "events_scanned": 0,
        "ticks_with_both_bbo": 0,
        "ticks_with_depth_ok": 0,
        "ticks_with_edge_ok": 0,
        "ticks_with_depth_and_edge": 0,
        "min_yes_ask_size_seen": None,
        "min_no_ask_size_seen": None,
        "min_sum_ask_seen": None,
        "required_depth": str(max_size),
        "required_edge_threshold": str(threshold),
    }

    # Accumulators for tracking worst-case seen values across the tape.
    min_yes_ask_size: Optional[Decimal] = None
    min_no_ask_size: Optional[Decimal] = None
    min_sum_ask: Optional[Decimal] = None

    try:
        with open(events_path, encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue

                stats["events_scanned"] += 1
                event_type = event.get("event_type", "")

                # ── Update books ──────────────────────────────────────────
                if event_type == EVENT_TYPE_PRICE_CHANGE and "price_changes" in event:
                    for entry in event.get("price_changes", []):
                        if not isinstance(entry, dict):
                            continue
                        entry_asset = str(entry.get("asset_id") or "")
                        if entry_asset == yes_id:
                            yes_book.apply_single_delta(entry)
                        elif entry_asset == no_id:
                            no_book.apply_single_delta(entry)
                elif event_type in (EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE):
                    asset_id = str(event.get("asset_id") or "")
                    if asset_id == yes_id:
                        yes_book.apply(event)
                    elif asset_id == no_id:
                        no_book.apply(event)
                else:
                    # last_trade_price / tick_size_change — skip
                    continue

                # ── Sample BBO state ──────────────────────────────────────
                yes_ask_f = yes_book.best_ask
                no_ask_f = no_book.best_ask
                if yes_ask_f is None or no_ask_f is None:
                    continue

                stats["ticks_with_both_bbo"] += 1
                yes_ask = Decimal(str(yes_ask_f))
                no_ask = Decimal(str(no_ask_f))
                sum_ask = yes_ask + no_ask

                if min_sum_ask is None or sum_ask < min_sum_ask:
                    min_sum_ask = sum_ask

                # ── Depth check ───────────────────────────────────────────
                yes_depth = _best_ask_size(yes_book)
                no_depth = _best_ask_size(no_book)

                if yes_depth is not None:
                    if min_yes_ask_size is None or yes_depth < min_yes_ask_size:
                        min_yes_ask_size = yes_depth
                if no_depth is not None:
                    if min_no_ask_size is None or no_depth < min_no_ask_size:
                        min_no_ask_size = no_depth

                depth_ok = (
                    yes_depth is not None
                    and yes_depth >= max_size
                    and no_depth is not None
                    and no_depth >= max_size
                )
                if depth_ok:
                    stats["ticks_with_depth_ok"] += 1

                # ── Edge check ────────────────────────────────────────────
                edge_ok = sum_ask < threshold
                if edge_ok:
                    stats["ticks_with_edge_ok"] += 1

                if depth_ok and edge_ok:
                    stats["ticks_with_depth_and_edge"] += 1

    except OSError as exc:
        return EligibilityResult(
            eligible=False,
            reason=f"could not read tape file: {exc}",
            stats=stats,
        )

    # Finalise human-readable stat fields.
    stats["min_yes_ask_size_seen"] = str(min_yes_ask_size) if min_yes_ask_size is not None else "none"
    stats["min_no_ask_size_seen"] = str(min_no_ask_size) if min_no_ask_size is not None else "none"
    stats["min_sum_ask_seen"] = str(min_sum_ask) if min_sum_ask is not None else "none"

    # ── Verdict ───────────────────────────────────────────────────────────
    eligible = stats["ticks_with_depth_and_edge"] > 0

    if eligible:
        return EligibilityResult(eligible=True, stats=stats)

    # Build a precise reason for the failure.
    depth_ever_ok = stats["ticks_with_depth_ok"] > 0
    edge_ever_ok = stats["ticks_with_edge_ok"] > 0

    if not depth_ever_ok and not edge_ever_ok:
        reason = (
            f"insufficient depth (YES min ask size={stats['min_yes_ask_size_seen']}, "
            f"NO min ask size={stats['min_no_ask_size_seen']}, "
            f"required={max_size}) AND no positive edge "
            f"(min sum_ask={stats['min_sum_ask_seen']}, "
            f"required < {threshold})"
        )
    elif not depth_ever_ok:
        reason = (
            f"insufficient depth: best-ask size never >= {max_size} on both sides "
            f"(YES min={stats['min_yes_ask_size_seen']}, "
            f"NO min={stats['min_no_ask_size_seen']})"
        )
    elif not edge_ever_ok:
        reason = (
            f"no positive edge: yes_ask + no_ask never < {threshold} "
            f"(min sum_ask seen={stats['min_sum_ask_seen']})"
        )
    else:
        # Depth and edge occurred on different ticks — never simultaneously.
        reason = (
            f"depth and edge never overlap on the same tick "
            f"(depth_ok_ticks={stats['ticks_with_depth_ok']}, "
            f"edge_ok_ticks={stats['ticks_with_edge_ok']})"
        )

    return EligibilityResult(eligible=False, reason=reason, stats=stats)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _best_ask_size(book: L2Book) -> Optional[Decimal]:
    """Return the size at the best ask level of *book*, or None if empty."""
    asks: dict[str, Decimal] = getattr(book, "_asks", {})
    if not asks:
        return None
    _, size = min(
        ((Decimal(price_str), size) for price_str, size in asks.items()),
        key=lambda row: row[0],
    )
    return size
