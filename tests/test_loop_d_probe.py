"""Deterministic offline tests for the Loop D feasibility probe helpers.

All tests are offline (no network, no ClickHouse, no external dependencies).

Coverage:
  - TestCountSubscribableTokens: count_subscribable_tokens()
  - TestAuditClobStreamGaps: audit_clob_stream_gaps()
  - TestAssessTradeEventSufficiency: assess_trade_event_sufficiency()
  - TestFormatFeasibilityVerdict: format_feasibility_verdict()
"""

from __future__ import annotations

import sys
import os
import pytest

# Ensure project root is on sys.path
_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from packages.polymarket.discovery.loop_d_probe import (
    assess_trade_event_sufficiency,
    audit_clob_stream_gaps,
    count_subscribable_tokens,
    format_feasibility_verdict,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_market_dict(
    token_count: int = 2,
    accepting_orders: bool = True,
    category: str = "crypto",
) -> dict:
    """Build a minimal market dict compatible with count_subscribable_tokens."""
    return {
        "clob_token_ids": [f"tok_{i}" for i in range(token_count)],
        "accepting_orders": accepting_orders,
        "category": category,
    }


def _full_trade_event() -> dict:
    """Return a last_trade_price event with all standard fields present."""
    return {
        "event_type": "last_trade_price",
        "asset_id": "0xabc",
        "price": "0.65",
        "size": "150",
        "side": "BUY",
        "timestamp": "1712345678",
        "fee_rate_bps": "200",
        "market": "btc-up-or-down-may-2026",
    }


# ---------------------------------------------------------------------------
# TestCountSubscribableTokens
# ---------------------------------------------------------------------------

class TestCountSubscribableTokens:
    def test_empty_list_returns_zeros(self):
        result = count_subscribable_tokens([])
        assert result["total_markets"] == 0
        assert result["total_tokens"] == 0
        assert result["accepting_orders_tokens"] == 0
        assert result["category_breakdown"] == {}

    def test_single_market_two_tokens(self):
        market = _make_market_dict(token_count=2, accepting_orders=True, category="crypto")
        result = count_subscribable_tokens([market])
        assert result["total_markets"] == 1
        assert result["total_tokens"] == 2
        assert result["accepting_orders_tokens"] == 2
        assert result["category_breakdown"] == {"crypto": 2}

    def test_multiple_markets_category_breakdown(self):
        markets = [
            _make_market_dict(2, True, "crypto"),
            _make_market_dict(2, True, "crypto"),
            _make_market_dict(2, True, "politics"),
            _make_market_dict(2, True, "sports"),
        ]
        result = count_subscribable_tokens(markets)
        assert result["total_markets"] == 4
        assert result["total_tokens"] == 8
        assert result["accepting_orders_tokens"] == 8
        assert result["category_breakdown"]["crypto"] == 4
        assert result["category_breakdown"]["politics"] == 2
        assert result["category_breakdown"]["sports"] == 2

    def test_accepting_orders_false_excluded_from_count(self):
        markets = [
            _make_market_dict(2, accepting_orders=True, category="crypto"),
            _make_market_dict(2, accepting_orders=False, category="politics"),
        ]
        result = count_subscribable_tokens(markets)
        assert result["total_tokens"] == 4
        # Only the accepting=True market contributes
        assert result["accepting_orders_tokens"] == 2

    def test_large_fixture_correct_totals(self):
        """500 markets with 2 tokens each = 1000 total tokens."""
        markets = [
            _make_market_dict(2, accepting_orders=True, category=f"cat_{i % 5}")
            for i in range(500)
        ]
        result = count_subscribable_tokens(markets)
        assert result["total_markets"] == 500
        assert result["total_tokens"] == 1000
        assert result["accepting_orders_tokens"] == 1000
        # 5 categories, 100 markets each with 2 tokens
        for cat_idx in range(5):
            assert result["category_breakdown"][f"cat_{cat_idx}"] == 200

    def test_dataclass_like_object(self):
        """count_subscribable_tokens also works with dataclass-style objects."""
        class FakeMarket:
            def __init__(self):
                self.clob_token_ids = ["t1", "t2", "t3"]
                self.accepting_orders = True
                self.category = "sports"

        result = count_subscribable_tokens([FakeMarket()])
        assert result["total_markets"] == 1
        assert result["total_tokens"] == 3
        assert result["accepting_orders_tokens"] == 3
        assert result["category_breakdown"] == {"sports": 3}

    def test_missing_category_falls_back_to_unknown(self):
        market = {"clob_token_ids": ["t1"], "accepting_orders": True}
        result = count_subscribable_tokens([market])
        assert "unknown" in result["category_breakdown"]
        assert result["category_breakdown"]["unknown"] == 1


# ---------------------------------------------------------------------------
# TestAuditClobStreamGaps
# ---------------------------------------------------------------------------

class TestAuditClobStreamGaps:
    def test_returns_nonempty_list(self):
        gaps = audit_clob_stream_gaps()
        assert isinstance(gaps, list)
        assert len(gaps) > 0

    def test_all_entries_have_required_keys(self):
        required_keys = {"gap_id", "description", "severity", "code_ref", "remediation"}
        gaps = audit_clob_stream_gaps()
        for entry in gaps:
            missing = required_keys - set(entry.keys())
            assert not missing, f"Gap {entry.get('gap_id')} missing keys: {missing}"

    def test_severity_values_are_valid(self):
        valid_severities = {"blocker", "constraint", "enhancement"}
        gaps = audit_clob_stream_gaps()
        for entry in gaps:
            assert entry["severity"] in valid_severities, (
                f"Gap {entry['gap_id']} has invalid severity '{entry['severity']}'"
            )

    def test_at_least_two_blockers(self):
        gaps = audit_clob_stream_gaps()
        blockers = [g for g in gaps if g["severity"] == "blocker"]
        assert len(blockers) >= 2, (
            f"Expected >= 2 blocker-severity gaps, found {len(blockers)}"
        )

    def test_all_blockers_have_nonempty_remediation(self):
        """Every blocker must have a remediation path (otherwise verdict = BLOCKED)."""
        gaps = audit_clob_stream_gaps()
        for g in gaps:
            if g["severity"] == "blocker":
                assert g["remediation"].strip(), (
                    f"Blocker {g['gap_id']} has no remediation"
                )

    def test_gap_ids_are_unique(self):
        gaps = audit_clob_stream_gaps()
        ids = [g["gap_id"] for g in gaps]
        assert len(ids) == len(set(ids)), "Gap IDs must be unique"


# ---------------------------------------------------------------------------
# TestAssessTradeEventSufficiency
# ---------------------------------------------------------------------------

class TestAssessTradeEventSufficiency:
    def test_full_event_all_pattern_detectors_ready(self):
        events = [_full_trade_event()]
        result = assess_trade_event_sufficiency(events)
        dr = result["detector_readiness"]
        assert dr["volume_spike"]["ready"] is True
        assert dr["price_anomaly"]["ready"] is True
        assert dr["trade_burst"]["ready"] is True
        assert dr["spread_divergence"]["ready"] is True
        # Wallet attribution requires fields NOT in CLOB events
        assert dr["wallet_attribution"]["ready"] is False
        assert "maker_address" in dr["wallet_attribution"]["missing_fields"]
        assert "taker_address" in dr["wallet_attribution"]["missing_fields"]

    def test_missing_size_field_volume_spike_not_ready(self):
        event = _full_trade_event()
        del event["size"]
        result = assess_trade_event_sufficiency([event])
        dr = result["detector_readiness"]
        assert dr["volume_spike"]["ready"] is False
        assert "size" in dr["volume_spike"]["missing_fields"]
        # Others unaffected
        assert dr["price_anomaly"]["ready"] is True
        assert dr["trade_burst"]["ready"] is True

    def test_empty_events_all_detectors_not_ready(self):
        result = assess_trade_event_sufficiency([])
        dr = result["detector_readiness"]
        for detector_name, info in dr.items():
            assert info["ready"] is False, (
                f"Detector {detector_name} should not be ready with empty events"
            )

    def test_wallet_attribution_note_always_nonempty(self):
        for events in [[], [_full_trade_event()]]:
            result = assess_trade_event_sufficiency(events)
            note = result["wallet_attribution_note"]
            assert isinstance(note, str) and len(note) > 0, (
                "wallet_attribution_note must be a non-empty string"
            )

    def test_fields_present_collected_correctly(self):
        events = [
            {"asset_id": "t1", "price": "0.5"},
            {"asset_id": "t2", "size": "100", "timestamp": "1712345678"},
        ]
        result = assess_trade_event_sufficiency(events)
        assert "asset_id" in result["fields_present"]
        assert "price" in result["fields_present"]
        assert "size" in result["fields_present"]
        assert "timestamp" in result["fields_present"]

    def test_fields_needed_for_detectors_present(self):
        result = assess_trade_event_sufficiency([])
        assert "volume_spike" in result["fields_needed_for_detectors"]
        assert "wallet_attribution" in result["fields_needed_for_detectors"]


# ---------------------------------------------------------------------------
# TestFormatFeasibilityVerdict
# ---------------------------------------------------------------------------

class TestFormatFeasibilityVerdict:
    def _make_token_inventory(self, n_markets=400, n_tokens=800, accepting=600) -> dict:
        return {
            "total_markets": n_markets,
            "total_tokens": n_tokens,
            "accepting_orders_tokens": accepting,
            "category_breakdown": {"crypto": 200, "politics": 300, "sports": 300},
        }

    def test_blocker_gaps_with_remediation_yields_ready_with_constraints(self):
        gaps = audit_clob_stream_gaps()  # real gaps — all have remediation
        inventory = self._make_token_inventory()
        events = [_full_trade_event()]
        sufficiency = assess_trade_event_sufficiency(events)

        result = format_feasibility_verdict(inventory, gaps, sufficiency)
        assert result["verdict"] == "READY_WITH_CONSTRAINTS"
        assert isinstance(result["constraints"], list)
        assert len(result["constraints"]) > 0

    def test_no_blocker_gaps_yields_ready(self):
        # Remove all blocker-severity gaps
        gaps = [g for g in audit_clob_stream_gaps() if g["severity"] != "blocker"]
        inventory = self._make_token_inventory()
        sufficiency = assess_trade_event_sufficiency([_full_trade_event()])

        result = format_feasibility_verdict(inventory, gaps, sufficiency)
        assert result["verdict"] == "READY"
        assert result["blockers"] == []

    def test_blocked_when_blocker_has_no_remediation(self):
        gaps = [
            {
                "gap_id": "G-XX",
                "description": "Critical gap with no known fix.",
                "severity": "blocker",
                "code_ref": "somewhere.py:10",
                "remediation": "",  # empty = no remediation path
            }
        ]
        inventory = self._make_token_inventory()
        sufficiency = assess_trade_event_sufficiency([])

        result = format_feasibility_verdict(inventory, gaps, sufficiency)
        assert result["verdict"] == "BLOCKED"
        assert len(result["blockers"]) > 0

    def test_constraints_and_next_steps_are_nonempty_lists(self):
        gaps = audit_clob_stream_gaps()
        inventory = self._make_token_inventory()
        sufficiency = assess_trade_event_sufficiency([_full_trade_event()])

        result = format_feasibility_verdict(inventory, gaps, sufficiency)
        assert isinstance(result["constraints"], list) and result["constraints"]
        assert isinstance(result["next_steps"], list) and result["next_steps"]

    def test_scale_assessment_keys_present(self):
        gaps = audit_clob_stream_gaps()
        inventory = self._make_token_inventory()
        sufficiency = assess_trade_event_sufficiency([_full_trade_event()])

        result = format_feasibility_verdict(inventory, gaps, sufficiency)
        sa = result["scale_assessment"]
        assert "total_tokens" in sa
        assert "throughput_bottleneck" in sa
        assert sa["throughput_bottleneck"] is False
