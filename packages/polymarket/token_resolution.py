"""Token resolution helpers for mapping aliases to canonical CLOB token ids."""

from __future__ import annotations

from typing import Mapping, Optional, Sequence

from .normalization import normalize_condition_id, normalize_outcome_name


def _match_outcome_index(outcome: str, outcomes: Sequence[str]) -> Optional[int]:
    if not outcomes:
        return None
    normalized_outcome = normalize_outcome_name(outcome)
    if normalized_outcome:
        for idx, value in enumerate(outcomes):
            if normalize_outcome_name(value) == normalized_outcome:
                return idx

    # Allow numeric outcome index fallback (0-based)
    if normalized_outcome.isdigit():
        try:
            idx = int(normalized_outcome)
        except ValueError:
            return None
        if 0 <= idx < len(outcomes):
            return idx

    return None


def resolve_token_id(
    token_id: str,
    condition_id: Optional[str],
    outcome: Optional[str],
    direct_token_ids: set[str],
    alias_map: Mapping[str, str],
    markets_map: Mapping[str, Mapping[str, Sequence[str]]],
) -> str:
    """Resolve a token_id to the canonical CLOB token id when possible."""
    token_id = token_id or ""
    if token_id in direct_token_ids:
        return token_id

    alias_value = alias_map.get(token_id, "")
    if alias_value:
        return alias_value

    condition_norm = normalize_condition_id(condition_id)
    if condition_norm and condition_norm in markets_map:
        market = markets_map[condition_norm]
        outcomes = market.get("outcomes") or []
        clob_token_ids = market.get("clob_token_ids") or []
        outcome_index = _match_outcome_index(outcome or "", outcomes)
        if outcome_index is not None and outcome_index < len(clob_token_ids):
            return str(clob_token_ids[outcome_index])

    return token_id
