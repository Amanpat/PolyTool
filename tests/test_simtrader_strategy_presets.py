"""Unit tests for named SimTrader strategy presets."""

from __future__ import annotations


def test_sane_preset_matches_current_default_strategy_config() -> None:
    from packages.polymarket.simtrader.strategy_presets import (
        build_binary_complement_strategy_config,
    )

    cfg = build_binary_complement_strategy_config(
        yes_asset_id="yes-token",
        no_asset_id="no-token",
        strategy_preset="sane",
    )
    assert cfg == {
        "yes_asset_id": "yes-token",
        "no_asset_id": "no-token",
        "buffer": 0.01,
        "max_size": 50,
        "legging_policy": "wait_N_then_unwind",
        "unwind_wait_ticks": 5,
        "enable_merge_full_set": True,
    }


def test_loose_preset_matches_explicit_json_overrides() -> None:
    from packages.polymarket.simtrader.strategy_presets import (
        build_binary_complement_strategy_config,
    )

    by_preset = build_binary_complement_strategy_config(
        yes_asset_id="yes-token",
        no_asset_id="no-token",
        strategy_preset="loose",
    )
    by_json_equivalent = build_binary_complement_strategy_config(
        yes_asset_id="yes-token",
        no_asset_id="no-token",
        strategy_preset="sane",
        user_overrides={
            "max_size": 1,
            "buffer": 0.0005,
            "max_notional_usdc": 25,
        },
    )

    assert by_preset == by_json_equivalent


def test_normalize_strategy_preset_accepts_preset_prefix() -> None:
    from packages.polymarket.simtrader.strategy_presets import normalize_strategy_preset

    assert normalize_strategy_preset("preset:loose") == "loose"

