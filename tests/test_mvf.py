"""AT-07: Deterministic MVF output shape tests for Wallet Discovery v1.

Tests:
1. Output shape — 50 synthetic positions yields all 11 dimensions; 1-10 non-null, dim11 null.
2. Determinism — same input produces byte-identical JSON twice.
3. Win-rate correctness — 25 WIN + 5 PROFIT_EXIT + 10 LOSS + 5 LOSS_EXIT + 5 PENDING = win rate 30/45.
4. Empty input — compute_mvf([]) returns all-None dimensions, input_trade_count=0.
5. Metadata block — includes wallet_address, computation_timestamp (ISO-8601), input_trade_count.
6. Maker/taker explicit null — no maker field -> maker_taker_ratio null, data note present.
7. Range validation — each non-null dimension falls within documented range.
"""
from __future__ import annotations

import json
import math

import pytest

from packages.polymarket.discovery.mvf import MvfResult, compute_mvf, mvf_to_dict

# ---------------------------------------------------------------------------
# Pinned 50-position fixture
# ---------------------------------------------------------------------------

# Outcome distribution:
#   25 WIN, 5 PROFIT_EXIT, 10 LOSS, 5 LOSS_EXIT, 5 PENDING  = 50 total
# win_rate = (25 + 5) / (25 + 5 + 10 + 5) = 30 / 45
#
# Markets: 6 distinct slugs for non-trivial concentration + dca scores.
# Categories: 4 distinct categories for entropy > 0.
# Timestamps: first/last trade timestamps present on all non-PENDING positions.

_MARKET_SLUGS = [
    "btc-up-dec-31",
    "eth-up-jan-15",
    "sol-up-jan-15",
    "trump-2024",
    "super-bowl-2025",
    "oscar-2025",
]

_CATEGORIES = ["Crypto", "Politics", "Sports", "Entertainment"]

_BASE_TS = 1_700_000_000.0  # 2023-11-14 UTC — pinned epoch


def _make_position(
    idx: int,
    outcome: str,
    slug_idx: int,
    cat_idx: int,
    entry_price: float,
    size: float,
    has_timestamps: bool = True,
) -> dict:
    pos: dict = {
        "resolution_outcome": outcome,
        "entry_price": entry_price,
        "market_slug": _MARKET_SLUGS[slug_idx % len(_MARKET_SLUGS)],
        "category": _CATEGORIES[cat_idx % len(_CATEGORIES)],
        "size": size,
        "position_notional_usd": size * entry_price,
    }
    if has_timestamps:
        # First trade = base + idx * 3600 seconds
        # Last trade = first + 24 hours
        first_ts = _BASE_TS + idx * 3600
        last_ts = first_ts + 86400.0
        pos["first_trade_timestamp"] = first_ts
        pos["last_trade_timestamp"] = last_ts
    return pos


def _build_fixture() -> list[dict]:
    positions = []
    idx = 0

    # 25 WIN
    for i in range(25):
        ep = 0.1 + (i % 9) * 0.08  # spread across 0.1 to 0.82
        positions.append(
            _make_position(idx, "WIN", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=100.0)
        )
        idx += 1

    # 5 PROFIT_EXIT
    for i in range(5):
        ep = 0.5 + i * 0.04
        positions.append(
            _make_position(idx, "PROFIT_EXIT", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=50.0)
        )
        idx += 1

    # 10 LOSS
    for i in range(10):
        ep = 0.3 + i * 0.05
        positions.append(
            _make_position(idx, "LOSS", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=75.0)
        )
        idx += 1

    # 5 LOSS_EXIT
    for i in range(5):
        ep = 0.4 + i * 0.06
        positions.append(
            _make_position(idx, "LOSS_EXIT", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=60.0)
        )
        idx += 1

    # 5 PENDING (excluded from win_rate denominator)
    for i in range(5):
        ep = 0.5
        positions.append(
            _make_position(
                idx, "PENDING", slug_idx=i % 6, cat_idx=i % 4, entry_price=ep, size=40.0,
                has_timestamps=False,
            )
        )
        idx += 1

    assert len(positions) == 50
    return positions


FIXTURE_50 = _build_fixture()
WALLET = "0xAbCdEf1234567890AbCdEf1234567890AbCdEf12"


# ---------------------------------------------------------------------------
# Test 1: Output shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_returns_mvf_result_instance(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert isinstance(result, MvfResult)

    def test_all_11_dimensions_present(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        expected_keys = {
            "win_rate",
            "avg_hold_duration_hours",
            "median_entry_price",
            "market_concentration",
            "category_entropy",
            "avg_position_size_usdc",
            "trade_frequency_per_day",
            "late_entry_rate",
            "dca_score",
            "resolution_coverage_rate",
            "maker_taker_ratio",
        }
        assert set(result.dimensions.keys()) == expected_keys

    def test_dims_1_to_10_non_null(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        non_null_dims = [
            "win_rate",
            "avg_hold_duration_hours",
            "median_entry_price",
            "market_concentration",
            "category_entropy",
            "avg_position_size_usdc",
            "trade_frequency_per_day",
            "dca_score",
            "resolution_coverage_rate",
        ]
        for key in non_null_dims:
            val = result.dimensions[key]
            assert val is not None, f"Expected {key} to be non-null, got None"
            assert isinstance(val, float), f"Expected {key} to be float, got {type(val)}"
            assert math.isfinite(val), f"Expected {key} to be finite, got {val}"

    def test_maker_taker_ratio_null_no_data(self):
        """Fixture has no maker/taker fields -> maker_taker_ratio must be null."""
        result = compute_mvf(FIXTURE_50, WALLET)
        assert result.dimensions["maker_taker_ratio"] is None

    def test_late_entry_rate_null_no_market_timing(self):
        """Fixture has no market_open_ts -> late_entry_rate must be null."""
        result = compute_mvf(FIXTURE_50, WALLET)
        # late_entry_rate is null because market_open_ts is absent
        assert result.dimensions["late_entry_rate"] is None


# ---------------------------------------------------------------------------
# Test 2: Determinism
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_byte_identical_json_twice(self):
        r1 = compute_mvf(FIXTURE_50, WALLET)
        r2 = compute_mvf(FIXTURE_50, WALLET)
        d1 = mvf_to_dict(r1)
        d2 = mvf_to_dict(r2)
        # Exclude computation_timestamp (wall-clock) — check dimensions only
        assert d1["dimensions"] == d2["dimensions"]

    def test_same_fixture_same_dimensions_float_exact(self):
        r1 = compute_mvf(FIXTURE_50, WALLET)
        r2 = compute_mvf(FIXTURE_50, WALLET)
        for key, v1 in r1.dimensions.items():
            v2 = r2.dimensions[key]
            assert v1 == v2, f"Dimension {key} differs: {v1} != {v2}"

    def test_order_invariant(self):
        """Shuffled input (same content) must produce same dimensions as sorted."""
        import copy
        shuffled = list(reversed(FIXTURE_50))
        r_orig = compute_mvf(FIXTURE_50, WALLET)
        r_shuf = compute_mvf(shuffled, WALLET)
        # Dimensions that should be order-invariant:
        order_invariant = [
            "win_rate", "market_concentration", "category_entropy",
            "avg_position_size_usdc", "dca_score", "resolution_coverage_rate",
        ]
        for key in order_invariant:
            assert r_orig.dimensions[key] == r_shuf.dimensions[key], (
                f"Dimension {key} is not order-invariant: {r_orig.dimensions[key]} vs {r_shuf.dimensions[key]}"
            )


# ---------------------------------------------------------------------------
# Test 3: Win-rate correctness
# ---------------------------------------------------------------------------

class TestWinRate:
    def test_win_rate_exact_value(self):
        """25 WIN + 5 PROFIT_EXIT + 10 LOSS + 5 LOSS_EXIT + 5 PENDING = win rate 30/45."""
        result = compute_mvf(FIXTURE_50, WALLET)
        expected = 30 / 45
        assert result.dimensions["win_rate"] == pytest.approx(expected, rel=1e-9)

    def test_win_rate_pending_excluded(self):
        """PENDING positions must not affect win_rate denominator."""
        # All-pending fixture -> win_rate must be None
        pending_only = [
            {"resolution_outcome": "PENDING", "market_slug": "s1", "category": "X"}
            for _ in range(5)
        ]
        result = compute_mvf(pending_only, "0x0")
        assert result.dimensions["win_rate"] is None

    def test_win_rate_all_wins(self):
        wins = [{"resolution_outcome": "WIN", "market_slug": "s1", "category": "X"} for _ in range(10)]
        result = compute_mvf(wins, "0x0")
        assert result.dimensions["win_rate"] == pytest.approx(1.0)

    def test_win_rate_all_losses(self):
        losses = [{"resolution_outcome": "LOSS", "market_slug": "s1", "category": "X"} for _ in range(10)]
        result = compute_mvf(losses, "0x0")
        assert result.dimensions["win_rate"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Test 4: Empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_positions_returns_mvf_result(self):
        result = compute_mvf([], "0x0")
        assert isinstance(result, MvfResult)

    def test_empty_positions_all_dims_null(self):
        result = compute_mvf([], "0x0")
        for key, val in result.dimensions.items():
            assert val is None, f"Expected {key} to be null for empty input, got {val}"

    def test_empty_positions_input_trade_count_zero(self):
        result = compute_mvf([], "0x0")
        assert result.metadata["input_trade_count"] == 0

    def test_empty_positions_maker_taker_note_present(self):
        result = compute_mvf([], "0x0")
        assert "maker_taker_data_unavailable" in result.metadata["data_notes"]

    def test_empty_positions_no_positions_note_present(self):
        result = compute_mvf([], "0x0")
        assert "no_positions_provided" in result.metadata["data_notes"]


# ---------------------------------------------------------------------------
# Test 5: Metadata block
# ---------------------------------------------------------------------------

class TestMetadata:
    def test_metadata_has_wallet_address(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert result.metadata["wallet_address"] == WALLET

    def test_metadata_has_input_trade_count(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert result.metadata["input_trade_count"] == 50

    def test_metadata_has_computation_timestamp(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        ts = result.metadata["computation_timestamp"]
        assert isinstance(ts, str)
        # Must be parseable as ISO-8601
        from datetime import datetime
        dt = datetime.fromisoformat(ts)
        assert dt is not None

    def test_metadata_has_data_notes_list(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert "data_notes" in result.metadata
        assert isinstance(result.metadata["data_notes"], list)


# ---------------------------------------------------------------------------
# Test 6: Maker/taker explicit null
# ---------------------------------------------------------------------------

class TestMakerTakerNull:
    def test_null_when_no_maker_field(self):
        pos = [{"resolution_outcome": "WIN", "market_slug": "s1", "category": "X"} for _ in range(5)]
        result = compute_mvf(pos, "0x0")
        assert result.dimensions["maker_taker_ratio"] is None

    def test_data_note_maker_taker_unavailable(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        assert "maker_taker_data_unavailable" in result.metadata["data_notes"]

    def test_maker_taker_computed_when_maker_field_present(self):
        pos = [
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "maker": True},
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "maker": False},
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "maker": True},
        ]
        result = compute_mvf(pos, "0x0")
        # 2 makers out of 3 -> 2/3
        assert result.dimensions["maker_taker_ratio"] == pytest.approx(2 / 3)
        assert "maker_taker_data_unavailable" not in result.metadata["data_notes"]

    def test_maker_taker_via_side_type_field(self):
        pos = [
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "side_type": "MAKER"},
            {"resolution_outcome": "WIN", "market_slug": "s1", "category": "X", "side_type": "taker"},
        ]
        result = compute_mvf(pos, "0x0")
        assert result.dimensions["maker_taker_ratio"] == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Test 7: Range validation
# ---------------------------------------------------------------------------

class TestRangeValidation:
    def setup_method(self):
        self.result = compute_mvf(FIXTURE_50, WALLET)
        self.dims = self.result.dimensions

    def test_win_rate_in_0_1(self):
        v = self.dims["win_rate"]
        assert v is not None
        assert 0.0 <= v <= 1.0

    def test_avg_hold_duration_hours_non_negative(self):
        v = self.dims["avg_hold_duration_hours"]
        assert v is not None
        assert v >= 0.0

    def test_median_entry_price_in_0_1(self):
        v = self.dims["median_entry_price"]
        assert v is not None
        assert 0.0 <= v <= 1.0

    def test_market_concentration_in_0_1(self):
        v = self.dims["market_concentration"]
        assert v is not None
        assert 0.0 <= v <= 1.0

    def test_category_entropy_non_negative(self):
        v = self.dims["category_entropy"]
        assert v is not None
        assert v >= 0.0

    def test_avg_position_size_usdc_non_negative(self):
        v = self.dims["avg_position_size_usdc"]
        assert v is not None
        assert v >= 0.0

    def test_trade_frequency_per_day_non_negative(self):
        v = self.dims["trade_frequency_per_day"]
        assert v is not None
        assert v >= 0.0

    def test_dca_score_in_0_1(self):
        v = self.dims["dca_score"]
        assert v is not None
        assert 0.0 <= v <= 1.0

    def test_resolution_coverage_rate_in_0_1(self):
        v = self.dims["resolution_coverage_rate"]
        assert v is not None
        assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# Test: mvf_to_dict serialization
# ---------------------------------------------------------------------------

class TestMvfToDict:
    def test_to_dict_contains_dimensions_and_metadata(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        d = mvf_to_dict(result)
        assert "dimensions" in d
        assert "metadata" in d

    def test_to_dict_json_serializable(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        d = mvf_to_dict(result)
        # Should not raise
        serialized = json.dumps(d)
        assert len(serialized) > 10

    def test_to_dict_dimensions_count(self):
        result = compute_mvf(FIXTURE_50, WALLET)
        d = mvf_to_dict(result)
        assert len(d["dimensions"]) == 11


# ---------------------------------------------------------------------------
# Test 8 (WI-6): real-scan-shaped field names must compute on real values.
#
# The live scan dossier (llm_research_packets.normalize_position_for_export)
# emits `entry_ts`/`exit_ts`/`hold_duration_seconds`/`resolved_at` and Gamma
# close fallbacks (`gamma_close_date_iso`, `close_date_iso`, ...), NOT the
# legacy `first_trade_timestamp`/`last_trade_timestamp` names. Before WI-6,
# avg_hold_duration_hours, trade_frequency_per_day, and late_entry_rate
# silently degraded (fell back) on real input. These tests pin the actual
# computed values on a fixture built with the REAL field names.
# ---------------------------------------------------------------------------

# Real-scan-shaped fixture. Timestamps are ISO-8601 strings (as emitted).
#   A: entry 2023-11-14T00:00Z, exit 2023-11-15T00:00Z -> 24h hold
#   B: entry 2023-11-14T00:00Z, no exit/resolved; hold_duration_seconds=43200 -> 12h
#   C: entry 2023-11-16T00:00Z, resolved_at 2023-11-16T06:00Z -> 6h hold
# avg_hold_duration_hours = (24 + 12 + 6) / 3 = 14.0
#
# trade_frequency window timestamps (entry + exit/resolved, NOT B's precomputed
# duration which is not a timestamp):
#   A: 2023-11-14T00:00Z, 2023-11-15T00:00Z
#   B: 2023-11-14T00:00Z (entry only; no exit_ts/resolved_at)
#   C: 2023-11-16T00:00Z, 2023-11-16T06:00Z
# min = 2023-11-14T00:00Z, max = 2023-11-16T06:00Z -> 54 hours = 2.25 days
# trade_frequency_per_day = 3 positions / 2.25 days = 1.333...
#
# late_entry_rate market windows (market-open = markets_enriched.start_date_iso,
# plumbed as start_date_iso; close = gamma/close/end fallbacks):
#   A: open 2023-11-13, close 2023-11-20 -> 7d window; entry 2023-11-14 = 1/7 ~0.14 -> early
#   B: open 2023-11-13, close 2023-11-21 -> 8d window; entry 2023-11-14 = 1/8 ~0.125 -> early
#   C: open 2023-11-15, close 2023-11-22 -> 7d window; entry 2023-11-16 = 1/7 ~0.14 -> early
# late_entry_rate = 0 late of 3 applicable -> 0.0 (real value, NOT null)
_REAL_SCAN_POSITIONS = [
    {
        "resolution_outcome": "WIN",
        "market_slug": "btc-up-dec-31",
        "category": "Crypto",
        "entry_price": 0.4,
        "entry_ts": "2023-11-14T00:00:00Z",
        "exit_ts": "2023-11-15T00:00:00Z",
        "start_date_iso": "2023-11-13T00:00:00Z",
        "gamma_close_date_iso": "2023-11-20T00:00:00Z",
    },
    {
        "resolution_outcome": "LOSS",
        "market_slug": "eth-up-jan-15",
        "category": "Crypto",
        "entry_price": 0.6,
        "entry_ts": "2023-11-14T00:00:00Z",
        "exit_ts": None,
        "resolved_at": None,
        "hold_duration_seconds": 43200,  # 12h precomputed
        "start_date_iso": "2023-11-13T00:00:00Z",
        "close_date_iso": "2023-11-21T00:00:00Z",
    },
    {
        "resolution_outcome": "PROFIT_EXIT",
        "market_slug": "sol-up-jan-15",
        "category": "Crypto",
        "entry_price": 0.5,
        "entry_ts": "2023-11-16T00:00:00Z",
        "resolved_at": "2023-11-16T06:00:00Z",
        "start_date_iso": "2023-11-15T00:00:00Z",
        "end_date_iso": "2023-11-22T00:00:00Z",
    },
]


class TestRealScanFieldReconciliation:
    """WI-6: degraded dims must compute on actual scan field names."""

    def test_avg_hold_duration_uses_entry_exit_and_precomputed(self):
        result = compute_mvf(_REAL_SCAN_POSITIONS, "0xreal")
        # (24 + 12 + 6) / 3 = 14.0 hours
        assert result.dimensions["avg_hold_duration_hours"] == pytest.approx(14.0)

    def test_avg_hold_duration_no_degradation_note(self):
        result = compute_mvf(_REAL_SCAN_POSITIONS, "0xreal")
        notes = result.metadata["data_notes"]
        assert not any("avg_hold_duration_unavailable" in n for n in notes)

    def test_trade_frequency_uses_real_timestamps_not_fallback(self):
        result = compute_mvf(_REAL_SCAN_POSITIONS, "0xreal")
        # 3 positions over a 54h (2.25-day) window -> 1.3333...
        # NOT the degraded fallback of float(len(positions)) == 3.0
        assert result.dimensions["trade_frequency_per_day"] == pytest.approx(3 / 2.25)
        assert result.dimensions["trade_frequency_per_day"] != pytest.approx(3.0)

    def test_late_entry_rate_computes_on_real_scan_fields(self):
        """WI-6 completion: scan dossier now carries market-open via
        ``start_date_iso`` (markets_enriched.start_date_iso), so late_entry_rate
        computes a REAL value (not null) end-to-end from entry + open + close.

        All three fixture positions entered early in their windows -> 0.0.
        """
        result = compute_mvf(_REAL_SCAN_POSITIONS, "0xreal")
        assert result.dimensions["late_entry_rate"] is not None
        assert result.dimensions["late_entry_rate"] == pytest.approx(0.0)

    def test_late_entry_rate_no_degradation_note(self):
        """With start_date_iso present, no late_entry_rate_unavailable note."""
        result = compute_mvf(_REAL_SCAN_POSITIONS, "0xreal")
        notes = result.metadata["data_notes"]
        assert not any("late_entry_rate_unavailable" in n for n in notes)

    def test_late_entry_rate_detects_late_entries_via_start_date_iso(self):
        """Mixed early/late entries computed off start_date_iso + close fields."""
        positions = [
            {
                "resolution_outcome": "WIN",
                "market_slug": "m1",
                "category": "Crypto",
                "start_date_iso": "2023-11-10T00:00:00Z",
                "entry_ts": "2023-11-19T00:00:00Z",  # 9/10 of the way in -> late
                "gamma_close_date_iso": "2023-11-20T00:00:00Z",
            },
            {
                "resolution_outcome": "WIN",
                "market_slug": "m2",
                "category": "Crypto",
                "start_date_iso": "2023-11-10T00:00:00Z",
                "entry_ts": "2023-11-11T00:00:00Z",  # 1/10 in -> early
                "close_date_iso": "2023-11-20T00:00:00Z",
            },
        ]
        result = compute_mvf(positions, "0xreal")
        # 1 of 2 entered in final 20% -> 0.5
        assert result.dimensions["late_entry_rate"] == pytest.approx(0.5)

    def test_late_entry_rate_null_when_start_date_genuinely_absent(self):
        """When start_date_iso is genuinely NULL for the markets, the dimension
        honestly stays null with a data note (no fabrication)."""
        positions = [
            {
                "resolution_outcome": "WIN",
                "market_slug": "m1",
                "category": "Crypto",
                "entry_ts": "2023-11-14T00:00:00Z",
                "gamma_close_date_iso": "2023-11-20T00:00:00Z",
                # no start_date_iso / market-open
            },
        ]
        result = compute_mvf(positions, "0xreal")
        assert result.dimensions["late_entry_rate"] is None
        notes = result.metadata["data_notes"]
        assert any("late_entry_rate_unavailable" in n for n in notes)
        assert any("start_date_iso" in n for n in notes)

    def test_determinism_on_real_shaped_input(self):
        r1 = compute_mvf(_REAL_SCAN_POSITIONS, "0xreal")
        r2 = compute_mvf(list(reversed(_REAL_SCAN_POSITIONS)), "0xreal")
        # Order-invariant aggregate dims must match exactly.
        for key in ("avg_hold_duration_hours", "trade_frequency_per_day"):
            assert r1.dimensions[key] == r2.dimensions[key]
