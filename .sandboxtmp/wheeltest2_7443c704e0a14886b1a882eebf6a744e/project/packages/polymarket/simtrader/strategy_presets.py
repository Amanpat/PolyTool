"""Named strategy presets for SimTrader binary_complement_arb."""

from __future__ import annotations

from typing import Any, Mapping

STRATEGY_PRESET_CHOICES: tuple[str, ...] = ("sane", "loose")

_PRESET_OVERRIDES: dict[str, dict[str, Any]] = {
    # Conservative baseline: current default behavior.
    "sane": {},
    # Conceptual knobs:
    # - min_top_size=1     -> max_size=1
    # - min_edge=0.0005    -> buffer=0.0005
    # - max_notional=25    -> max_notional_usdc=25
    "loose": {
        "max_size": 1,
        "buffer": 0.0005,
        "max_notional_usdc": 25,
    },
}


def normalize_strategy_preset(raw: str | None) -> str:
    """Normalize preset token and validate it."""
    token = (raw or "sane").strip()
    if not token:
        token = "sane"
    token = token.removeprefix("preset:")
    if token not in _PRESET_OVERRIDES:
        known = ", ".join(f"'{name}'" for name in STRATEGY_PRESET_CHOICES)
        raise ValueError(
            f"unknown --strategy-preset {raw!r}. Known presets: {known}"
        )
    return token


def strategy_preset_overrides(preset: str) -> dict[str, Any]:
    """Return a copy of the override dict for one named preset."""
    key = normalize_strategy_preset(preset)
    return dict(_PRESET_OVERRIDES[key])


def build_binary_complement_strategy_config(
    *,
    yes_asset_id: str,
    no_asset_id: str,
    strategy_preset: str = "sane",
    user_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build final strategy config for binary_complement_arb."""
    config: dict[str, Any] = {
        "yes_asset_id": yes_asset_id,
        "no_asset_id": no_asset_id,
        "buffer": 0.01,
        "max_size": 50,
        "legging_policy": "wait_N_then_unwind",
        "unwind_wait_ticks": 5,
        "enable_merge_full_set": True,
    }
    config.update(strategy_preset_overrides(strategy_preset))
    if user_overrides:
        config.update(dict(user_overrides))
    return config

