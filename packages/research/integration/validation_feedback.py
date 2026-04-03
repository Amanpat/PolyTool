"""RIS SimTrader bridge v1 -- validation feedback hook.

Provides ``record_validation_outcome()``, which maps a SimTrader validation
outcome (confirmed / contradicted / inconclusive) to the corresponding
KnowledgeStore claim validation_status and updates all specified claims.

This is a manual feedback function. The operator or a future orchestrator
calls it after reviewing SimTrader replay results -- not automatically.

Deferred (R5 / v2)
------------------
- Automatic validation outcome detection from run_manifest.json
- Auto-hypothesis promotion on confirmed outcomes
- Discord approval integration
- Scheduled re-validation pass
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from packages.polymarket.rag.knowledge_store import KnowledgeStore

# ---------------------------------------------------------------------------
# Outcome mapping
# ---------------------------------------------------------------------------

OUTCOME_MAP: dict[str, str] = {
    "confirmed": "CONSISTENT_WITH_RESULTS",
    "contradicted": "CONTRADICTED",
    "inconclusive": "INCONCLUSIVE",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_validation_outcome(
    store: KnowledgeStore,
    hypothesis_id: str,
    claim_ids: list[str],
    outcome: str,
    reason: str,
) -> dict:
    """Update claim validation_status in the KnowledgeStore for a validation outcome.

    Parameters
    ----------
    store:
        KnowledgeStore instance (in-memory or disk-backed).
    hypothesis_id:
        The hypothesis whose validation produced this outcome.
    claim_ids:
        List of claim IDs to update. Claims not found in the store are counted
        as ``claims_not_found`` and silently skipped.
    outcome:
        One of: ``"confirmed"`` (sets CONSISTENT_WITH_RESULTS),
        ``"contradicted"`` (sets CONTRADICTED),
        ``"inconclusive"`` (sets INCONCLUSIVE).
    reason:
        Human-readable explanation of the outcome (stored in actor field context,
        but not persisted to claim row -- the actor field carries the hypothesis_id).

    Returns
    -------
    dict
        Summary dict with keys:
        ``hypothesis_id``, ``outcome``, ``validation_status``, ``reason``,
        ``claims_updated``, ``claims_not_found``, ``claims_failed``,
        ``claim_ids``.

    Raises
    ------
    ValueError
        If ``outcome`` is not one of the valid outcome strings.
    """
    if outcome not in OUTCOME_MAP:
        raise ValueError(
            f"invalid outcome '{outcome}'. Must be one of: {', '.join(OUTCOME_MAP.keys())}"
        )

    validation_status = OUTCOME_MAP[outcome]
    actor = f"validation_feedback:{hypothesis_id}"

    claims_updated = 0
    claims_not_found = 0
    claims_failed = 0

    for claim_id in claim_ids:
        try:
            store.update_claim_validation_status(claim_id, validation_status, actor)
            claims_updated += 1
        except ValueError as exc:
            err_str = str(exc)
            if "claim not found" in err_str:
                claims_not_found += 1
            else:
                # Invalid status or other ValueError from the store
                claims_failed += 1
        except Exception:
            claims_failed += 1

    return {
        "hypothesis_id": hypothesis_id,
        "outcome": outcome,
        "validation_status": validation_status,
        "reason": reason,
        "claims_updated": claims_updated,
        "claims_not_found": claims_not_found,
        "claims_failed": claims_failed,
        "claim_ids": claim_ids,
    }
