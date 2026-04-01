"""Freshness decay computation for the RIS v1 knowledge store.

Provides query-time freshness modifiers based on source-family half-lives
defined in ``config/freshness_decay.json``.  All functions are pure
(read-only) -- they never mutate stored records.

Usage::

    from packages.polymarket.rag.freshness import (
        load_freshness_config,
        compute_freshness_modifier,
    )

    modifier = compute_freshness_modifier("news", published_at=datetime(...))
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Default config path relative to repo root
_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "freshness_decay.json"


@lru_cache(maxsize=8)
def _cached_load(resolved_path: str) -> dict:
    """Internal cache keyed on the resolved absolute path string."""
    data = json.loads(Path(resolved_path).read_text(encoding="utf-8"))
    return data


def load_freshness_config(config_path: Optional[Path] = None) -> dict:
    """Load and return the freshness decay configuration.

    Parameters
    ----------
    config_path:
        Path to the JSON config file.  Defaults to
        ``config/freshness_decay.json`` relative to the repo root.

    Returns
    -------
    dict
        Parsed config dict with keys ``version``, ``decay_floor``,
        ``source_families``.
    """
    if config_path is None:
        config_path = _DEFAULT_CONFIG_PATH
    resolved = str(Path(config_path).resolve())
    return _cached_load(resolved)


def compute_freshness_modifier(
    source_family: str,
    published_at: Optional[datetime],
    config: Optional[dict] = None,
) -> float:
    """Compute the freshness modifier for a source document at query time.

    The modifier is computed using exponential decay::

        modifier = max(floor, 2 ^ (-age_months / half_life))

    Rules:
    - Returns ``1.0`` if the source family has ``null`` half-life (timeless).
    - Returns ``1.0`` if ``published_at`` is ``None`` (unknown age = no penalty).
    - Returns a value in ``[floor, 1.0]`` otherwise.

    This function is pure -- it NEVER mutates any stored records.

    Parameters
    ----------
    source_family:
        Source family key (e.g. ``"news"``, ``"blog"``, ``"academic_foundational"``).
        Unknown families default to ``null`` half-life (return 1.0).
    published_at:
        Publication datetime with or without timezone info.  If timezone-naive,
        treated as UTC.
    config:
        Optional pre-loaded config dict.  If ``None``, loads via
        :func:`load_freshness_config`.

    Returns
    -------
    float
        Freshness modifier in ``[decay_floor, 1.0]``.
    """
    if config is None:
        config = load_freshness_config()

    decay_floor: float = float(config.get("decay_floor", 0.3))
    source_families: dict = config.get("source_families", {})

    # Unknown family defaults to timeless (no penalty)
    half_life_months = source_families.get(source_family, None)

    # Timeless source or unknown published_at -> no penalty
    if half_life_months is None:
        return 1.0
    if published_at is None:
        return 1.0

    # Ensure timezone-aware for subtraction
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)

    now = datetime.now(tz=timezone.utc)
    age_seconds = (now - published_at).total_seconds()

    # Treat future dates as age=0 (modifier=1.0)
    if age_seconds <= 0:
        return 1.0

    # Convert seconds to months (approximate: 30.44 days/month)
    age_months = age_seconds / (30.44 * 24 * 3600)

    # Exponential decay: 2^(-age / half_life)
    modifier = math.pow(2.0, -age_months / float(half_life_months))

    # Apply floor
    return max(decay_floor, modifier)
