"""Normalization helpers for Polymarket identifiers."""

from __future__ import annotations

from typing import Optional


def normalize_condition_id(value: Optional[str]) -> str:
    """Normalize condition_id to lowercase with 0x prefix.

    Returns empty string when value is falsy or only whitespace.
    """
    if value is None:
        return ""
    cleaned = str(value).strip()
    if not cleaned:
        return ""
    lowered = cleaned.lower()
    if lowered.startswith("0x"):
        normalized = lowered[2:]
    else:
        normalized = lowered
    if not normalized:
        return ""
    return f"0x{normalized}"


def normalize_outcome_name(value: Optional[str]) -> str:
    """Normalize outcome strings for joins (lowercase/trim)."""
    if value is None:
        return ""
    cleaned = str(value).strip().lower()
    return cleaned
