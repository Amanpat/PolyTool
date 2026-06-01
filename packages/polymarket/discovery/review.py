"""WI-4 human-gate review planning (pure, offline-testable).

``plan_review`` decides the lifecycle_state + review_status a watchlist row
should hold after an operator approve/deny, ROUTING THROUGH the enforced
``validate_transition`` gate. It NEVER bypasses the gate and NEVER auto-promotes
beyond what the operator explicitly requested.

Gate semantics enforced:
- ``--approve`` sets review_status='approved'. If the row is at 'scanned', it is
  advanced 'scanned'->'reviewed' (a valid transition) so the wallet sits at the
  review boundary. The actual promotion 'reviewed'->'promoted' only happens when
  the operator also asks to ``--promote``, and that transition is validated with
  review_status='approved' (the human gate) — validate_transition raises if it
  is not approved.
- ``--deny`` sets review_status='rejected' and does NOT advance lifecycle_state.

The CLI injects ClickHouse read/write; this function does no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from packages.polymarket.discovery.models import (
    LifecycleState,
    ReviewStatus,
    validate_transition,
)


@dataclass(frozen=True)
class ReviewPlan:
    """Resulting state for a review action (after gate validation)."""

    wallet_address: str
    from_lifecycle: LifecycleState
    to_lifecycle: LifecycleState
    review_status: ReviewStatus
    note: str


def plan_review(
    *,
    wallet_address: str,
    current_lifecycle: LifecycleState,
    approve: bool,
    promote: bool = False,
) -> ReviewPlan:
    """Plan an approve/deny review through the enforced lifecycle gate.

    Raises ``InvalidTransitionError`` (from validate_transition) if any required
    transition is illegal — the gate is never bypassed.

    Parameters
    ----------
    approve:
        True for approve, False for deny.
    promote:
        Only meaningful with ``approve``: also advance reviewed->promoted through
        the gate (validated with review_status='approved').
    """
    if not approve:
        # Deny: record rejection, do not advance lifecycle_state.
        return ReviewPlan(
            wallet_address=wallet_address,
            from_lifecycle=current_lifecycle,
            to_lifecycle=current_lifecycle,
            review_status=ReviewStatus.rejected,
            note="denied: review_status set to 'rejected'; lifecycle unchanged",
        )

    # Approve path.
    review_status = ReviewStatus.approved
    to_state = current_lifecycle

    # If the row is at 'scanned', advance to 'reviewed' (validated) so it sits at
    # the review boundary, ready for promotion.
    if current_lifecycle == LifecycleState.scanned:
        validate_transition(LifecycleState.scanned, LifecycleState.reviewed)
        to_state = LifecycleState.reviewed

    note = "approved: review_status set to 'approved'"

    if promote:
        # Promotion goes THROUGH the gate with review_status='approved'. If the
        # row is not at 'reviewed' (or could not be advanced there), this raises.
        validate_transition(
            to_state, LifecycleState.promoted, review_status=review_status
        )
        to_state = LifecycleState.promoted
        note = "approved + promoted: review_status='approved', lifecycle->'promoted' (gate passed)"

    return ReviewPlan(
        wallet_address=wallet_address,
        from_lifecycle=current_lifecycle,
        to_lifecycle=to_state,
        review_status=review_status,
        note=note,
    )
