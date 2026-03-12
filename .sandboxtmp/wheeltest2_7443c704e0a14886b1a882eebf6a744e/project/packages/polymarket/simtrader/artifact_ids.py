"""Helpers for compact, human-readable SimTrader artifact directory IDs."""

from __future__ import annotations

import hashlib
import re
from typing import Any

_COMPONENT_RE = re.compile(r"[^a-z0-9_-]+")
_MAX_KIND_LEN = 12
_MAX_SLUG_LEN = 36
_MAX_STRATEGY_LEN = 24
_MAX_PRESET_LEN = 16
_MAX_BATCH_SIZE_LEN = 12
_MAX_SUFFIX_LEN = 8


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_component(value: Any, *, max_length: int, fallback: str) -> str:
    text = (_as_text(value) or fallback).lower()
    text = _COMPONENT_RE.sub("-", text).strip("-_")
    if not text:
        text = fallback
    if len(text) <= max_length:
        return text
    clipped = text[:max_length].rstrip("-_")
    return clipped or fallback


def short_hash(*parts: Any, length: int = _MAX_SUFFIX_LEN) -> str:
    """Return a short stable digest suitable for a compact uniqueness suffix."""
    capped = max(4, min(int(length), 16))
    payload = "|".join(_as_text(part) or "-" for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:capped]


def build_timestamped_artifact_id(
    *,
    timestamp: Any,
    kind: str,
    market_slug: str | None = None,
    strategy: str | None = None,
    preset: str | None = None,
    batch_size: int | None = None,
    suffix: str | None = None,
) -> str:
    """Build a timestamp-leading artifact ID that stays easy to scan."""
    timestamp_text = _as_text(timestamp) or "unknown-time"
    parts = [
        timestamp_text,
        _normalize_component(kind, max_length=_MAX_KIND_LEN, fallback="artifact"),
    ]

    if market_slug is not None:
        parts.append(
            _normalize_component(
                market_slug,
                max_length=_MAX_SLUG_LEN,
                fallback="market",
            )
        )
    if strategy is not None:
        parts.append(
            _normalize_component(
                strategy,
                max_length=_MAX_STRATEGY_LEN,
                fallback="strategy",
            )
        )
    if preset is not None:
        parts.append(
            _normalize_component(
                preset,
                max_length=_MAX_PRESET_LEN,
                fallback="preset",
            )
        )
    if batch_size is not None:
        parts.append(
            _normalize_component(
                f"{int(batch_size)}markets",
                max_length=_MAX_BATCH_SIZE_LEN,
                fallback="markets",
            )
        )
    if suffix is not None:
        parts.append(
            _normalize_component(
                suffix,
                max_length=_MAX_SUFFIX_LEN,
                fallback="id",
            )
        )

    return "_".join(parts)


def build_deterministic_sweep_id(
    *,
    digest: str,
    market_slug: str | None = None,
    strategy: str | None = None,
    preset: str | None = None,
) -> str:
    """Build a stable sweep ID for non-CLI/default sweep runs."""
    parts = ["sweep"]

    if market_slug is not None:
        parts.append(
            _normalize_component(
                market_slug,
                max_length=_MAX_SLUG_LEN,
                fallback="market",
            )
        )
    if strategy is not None:
        parts.append(
            _normalize_component(
                strategy,
                max_length=_MAX_STRATEGY_LEN,
                fallback="strategy",
            )
        )
    if preset is not None:
        parts.append(
            _normalize_component(
                preset,
                max_length=_MAX_PRESET_LEN,
                fallback="preset",
            )
        )

    parts.append(
        _normalize_component(
            digest,
            max_length=_MAX_SUFFIX_LEN,
            fallback="id",
        )
    )
    return "_".join(parts)
