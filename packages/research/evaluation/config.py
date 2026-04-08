"""RIS Phase 2 evaluation configuration loader.

Loads gate parameters from config/ris_eval_config.json with env-var overrides.
Config is cached at module level (singleton pattern).

Env var overrides:
  RIS_EVAL_RELEVANCE_WEIGHT      float  (default: 0.30)
  RIS_EVAL_NOVELTY_WEIGHT        float  (default: 0.25)
  RIS_EVAL_ACTIONABILITY_WEIGHT  float  (default: 0.25)
  RIS_EVAL_CREDIBILITY_WEIGHT    float  (default: 0.20)
  RIS_EVAL_RELEVANCE_FLOOR       int    (default: 2)
  RIS_EVAL_CREDIBILITY_FLOOR     int    (default: 2)
  RIS_EVAL_P1_THRESHOLD          float  (default: 2.5)
  RIS_EVAL_P2_THRESHOLD          float  (default: 3.0)
  RIS_EVAL_P3_THRESHOLD          float  (default: 3.2)
  RIS_EVAL_P4_THRESHOLD          float  (default: 3.5)
  RIS_EVAL_DEFAULT_PRIORITY      str    (default: priority_3)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# -------------------------------------------------------------------------
# Default spec values (used when config file is missing or key is absent)
# -------------------------------------------------------------------------

_DEFAULT_WEIGHTS: dict[str, float] = {
    "relevance": 0.30,
    "novelty": 0.25,
    "actionability": 0.25,
    "credibility": 0.20,
}

_DEFAULT_FLOORS: dict[str, int] = {
    "relevance": 2,
    "credibility": 2,
}

_DEFAULT_FLOOR_WAIVE_TIERS: list[str] = ["priority_1"]

_DEFAULT_THRESHOLDS: dict[str, float] = {
    "priority_1": 2.5,
    "priority_2": 3.0,
    "priority_3": 3.2,
    "priority_4": 3.5,
}

_DEFAULT_PRIORITY_TIER: str = "priority_3"

# Config file path relative to project root
_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "ris_eval_config.json"


@dataclass(frozen=True)
class EvalConfig:
    """Frozen evaluation configuration.

    All gate parameters are immutable after construction.
    """
    weights: dict = field(default_factory=lambda: dict(_DEFAULT_WEIGHTS))
    floors: dict = field(default_factory=lambda: dict(_DEFAULT_FLOORS))
    floor_waive_tiers: tuple = field(default_factory=lambda: tuple(_DEFAULT_FLOOR_WAIVE_TIERS))
    thresholds: dict = field(default_factory=lambda: dict(_DEFAULT_THRESHOLDS))
    default_priority_tier: str = _DEFAULT_PRIORITY_TIER


# Module-level singleton
_config_cache: Optional[EvalConfig] = None


def load_eval_config() -> EvalConfig:
    """Load evaluation configuration from file + env var overrides.

    Priority: env vars > config file > hardcoded defaults.

    Returns:
        EvalConfig with frozen gate parameters.
    """
    # Start with defaults
    weights = dict(_DEFAULT_WEIGHTS)
    floors = dict(_DEFAULT_FLOORS)
    floor_waive_tiers = list(_DEFAULT_FLOOR_WAIVE_TIERS)
    thresholds = dict(_DEFAULT_THRESHOLDS)
    default_priority_tier = _DEFAULT_PRIORITY_TIER

    # Load from config file if it exists
    if _CONFIG_PATH.exists():
        try:
            raw = _CONFIG_PATH.read_text(encoding="utf-8")
            cfg = json.loads(raw)

            scoring = cfg.get("scoring", {})
            file_weights = scoring.get("weights", {})
            for dim in ("relevance", "novelty", "actionability", "credibility"):
                if dim in file_weights:
                    try:
                        weights[dim] = float(file_weights[dim])
                    except (TypeError, ValueError):
                        pass

            file_floors = scoring.get("floors", {})
            for dim in ("relevance", "credibility"):
                if dim in file_floors:
                    try:
                        floors[dim] = int(file_floors[dim])
                    except (TypeError, ValueError):
                        pass

            fwt = scoring.get("floor_waive_tiers", None)
            if isinstance(fwt, list):
                floor_waive_tiers = [str(t) for t in fwt]

            gates = cfg.get("acceptance_gates", {})
            for tier_key, tier_vals in gates.items():
                if isinstance(tier_vals, dict) and "threshold" in tier_vals:
                    try:
                        thresholds[tier_key] = float(tier_vals["threshold"])
                    except (TypeError, ValueError):
                        pass

            defaults_section = cfg.get("defaults", {})
            if "default_priority_tier" in defaults_section:
                default_priority_tier = str(defaults_section["default_priority_tier"])

        except (json.JSONDecodeError, OSError):
            # File exists but is malformed or unreadable — fall back to defaults
            pass

    # Apply env var overrides
    _env_float_override(weights, "relevance", "RIS_EVAL_RELEVANCE_WEIGHT")
    _env_float_override(weights, "novelty", "RIS_EVAL_NOVELTY_WEIGHT")
    _env_float_override(weights, "actionability", "RIS_EVAL_ACTIONABILITY_WEIGHT")
    _env_float_override(weights, "credibility", "RIS_EVAL_CREDIBILITY_WEIGHT")

    _env_int_override(floors, "relevance", "RIS_EVAL_RELEVANCE_FLOOR")
    _env_int_override(floors, "credibility", "RIS_EVAL_CREDIBILITY_FLOOR")

    _env_float_override(thresholds, "priority_1", "RIS_EVAL_P1_THRESHOLD")
    _env_float_override(thresholds, "priority_2", "RIS_EVAL_P2_THRESHOLD")
    _env_float_override(thresholds, "priority_3", "RIS_EVAL_P3_THRESHOLD")
    _env_float_override(thresholds, "priority_4", "RIS_EVAL_P4_THRESHOLD")

    env_priority = os.environ.get("RIS_EVAL_DEFAULT_PRIORITY", "").strip()
    if env_priority:
        default_priority_tier = env_priority

    return EvalConfig(
        weights=weights,
        floors=floors,
        floor_waive_tiers=tuple(floor_waive_tiers),
        thresholds=thresholds,
        default_priority_tier=default_priority_tier,
    )


def _env_float_override(d: dict, key: str, env_var: str) -> None:
    val = os.environ.get(env_var, "").strip()
    if val:
        try:
            d[key] = float(val)
        except ValueError:
            pass


def _env_int_override(d: dict, key: str, env_var: str) -> None:
    val = os.environ.get(env_var, "").strip()
    if val:
        try:
            d[key] = int(val)
        except ValueError:
            pass


def get_eval_config() -> EvalConfig:
    """Return the cached evaluation config (loads on first call).

    Uses a module-level cache. Call reset_eval_config() in tests that need
    to patch env vars or config file values.
    """
    global _config_cache
    if _config_cache is None:
        _config_cache = load_eval_config()
    return _config_cache


def reset_eval_config() -> None:
    """Reset the cached config so the next get_eval_config() call reloads.

    Call this in tests that manipulate env vars or mock config loading.
    """
    global _config_cache
    _config_cache = None
