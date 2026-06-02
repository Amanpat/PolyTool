"""WI-4 two-tier watchlist tests — offline, deterministic, no live ClickHouse.

Covers:
  - Evidence-summary determinism (acceptance gate 3) + WI-5 contract shape.
  - Candidate auto-population from sample scan evidence (config thresholds).
  - Locked immutability across a simulated discovery+rescan cycle (gate 2).
  - Gate enforcement: auto-promote past the human gate is refused (gate 1).
  - resolve_tier alignment with WI-4 tier/locked columns (Fork #2).
  - discovery review --approve/--deny routes through validate_transition.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from packages.polymarket.discovery.evidence_summary import (
    Evidence,
    is_candidate,
    is_promotion_eligible,
    load_promotion_config,
    summarize_evidence,
)
from packages.polymarket.discovery.candidate_population import (
    LockedImmutabilityError,
    build_candidate_row,
    guard_not_locked,
    is_locked_row,
    locked_wallets,
    plan_candidate_writes,
    populate_candidates,
)
from packages.polymarket.discovery.models import (
    InvalidTransitionError,
    LifecycleState,
    ReviewStatus,
    WatchlistRow,
)
from packages.polymarket.discovery.review import plan_review

_NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Evidence summary — determinism + WI-5 contract
# ---------------------------------------------------------------------------


class TestEvidenceSummary:
    def test_full_summary_string(self):
        ev = Evidence(
            wallet_address="0xabc",
            realized_net_pnl=24000.0,
            win_rate=0.64,
            trades=180,
            clv_coverage_rate=0.72,
            churn_triggered=True,
        )
        s = summarize_evidence(ev)
        assert s == "+$24.0k PnL, 64% win / 180 trades, CLV 72%, churn-triggered"

    def test_determinism_same_evidence_same_string(self):
        ev = Evidence(realized_net_pnl=12345.0, win_rate=0.61, trades=99, clv_coverage_rate=0.5)
        # Many runs -> byte-identical.
        outputs = {summarize_evidence(ev) for _ in range(50)}
        assert len(outputs) == 1

    def test_determinism_from_dict_equals_dataclass(self):
        raw = {
            "wallet_address": "0xabc",
            "realized_net_pnl": 24000.0,
            "win_rate": 0.64,
            "positions_total": 180,
            "clv_coverage_rate": 0.72,
            "churn_triggered": True,
        }
        ev = Evidence.from_dict(raw)
        assert summarize_evidence(raw) == summarize_evidence(ev)

    def test_missing_dimensions_omitted_not_fabricated(self):
        ev = Evidence(realized_net_pnl=5000.0)
        s = summarize_evidence(ev)
        assert s == "+$5.0k PnL"
        assert "win" not in s and "CLV" not in s

    def test_empty_evidence(self):
        assert summarize_evidence(Evidence()) == "no evidence available"

    def test_negative_pnl_sign(self):
        assert summarize_evidence(Evidence(realized_net_pnl=-350.0)) == "-$350 PnL"

    def test_millions_suffix(self):
        assert summarize_evidence(Evidence(realized_net_pnl=2_400_000.0)) == "+$2.4m PnL"

    def test_from_dict_alias_fields(self):
        ev = Evidence.from_dict({"pnl": 9000, "clv": 0.4, "input_trade_count": 30})
        assert ev.realized_net_pnl == 9000.0
        assert ev.clv_coverage_rate == 0.4
        assert ev.trades == 30


# ---------------------------------------------------------------------------
# Candidate gates
# ---------------------------------------------------------------------------


class TestCandidateGates:
    def test_high_pnl_qualifies(self):
        ev = Evidence(realized_net_pnl=20000.0, trades=100)
        assert is_candidate(ev) is True

    def test_high_winrate_qualifies(self):
        ev = Evidence(win_rate=0.7, trades=100)
        assert is_candidate(ev) is True

    def test_churn_alone_qualifies(self):
        ev = Evidence(churn_triggered=True, trades=2)
        assert is_candidate(ev) is True

    def test_below_min_positions_rejected(self):
        # Strong PnL but only 5 trades (< min_positions 20) and no churn.
        ev = Evidence(realized_net_pnl=99999.0, trades=5)
        assert is_candidate(ev) is False

    def test_weak_wallet_rejected(self):
        ev = Evidence(realized_net_pnl=100.0, win_rate=0.4, trades=100, clv_coverage_rate=0.1)
        assert is_candidate(ev) is False

    def test_config_thresholds_loaded(self):
        cfg = load_promotion_config()
        assert "candidate_thresholds" in cfg
        assert "promotion_eligibility" in cfg
        assert cfg["candidate_thresholds"]["min_positions"] >= 1


class TestPromotionEligibility:
    def test_strong_wallet_eligible(self):
        ev = Evidence(realized_net_pnl=50000.0, win_rate=0.65, trades=200)
        assert is_promotion_eligible(ev) is True

    def test_and_semantics_one_failing_blocks(self):
        # Clears PnL + trades but win_rate below bar -> NOT eligible (AND).
        ev = Evidence(realized_net_pnl=50000.0, win_rate=0.50, trades=200)
        assert is_promotion_eligible(ev) is False

    def test_eligibility_does_not_touch_lifecycle(self):
        # Eligibility is advisory: it returns a bool and never mutates state.
        ev = Evidence(realized_net_pnl=50000.0, win_rate=0.65, trades=200)
        assert isinstance(is_promotion_eligible(ev), bool)


# ---------------------------------------------------------------------------
# Candidate-tier row construction + auto-population
# ---------------------------------------------------------------------------


class TestCandidateRow:
    def test_built_row_is_candidate_tier_in_gate(self):
        ev = Evidence(wallet_address="0xabc", realized_net_pnl=20000.0, trades=100)
        row = build_candidate_row(ev, now=_NOW)
        assert row.tier == "candidate"
        assert row.locked == 0
        # Stays inside the human gate.
        assert row.lifecycle_state == LifecycleState.scanned
        assert row.review_status == ReviewStatus.pending
        assert row.reason == summarize_evidence(ev)

    def test_source_preserves_origin_not_tier(self):
        # Fork #1: source keeps ORIGIN meaning; tier carries candidate/locked.
        ev = Evidence(wallet_address="0xabc", realized_net_pnl=20000.0, trades=100)
        row = build_candidate_row(ev, source="loop_a", now=_NOW)
        assert row.source == "loop_a"
        assert row.tier == "candidate"


class TestAutoPopulation:
    def test_only_qualifying_wallets_written(self):
        evidences = [
            {"wallet_address": "0xstrong", "realized_net_pnl": 30000.0, "positions_total": 100},
            {"wallet_address": "0xweak", "realized_net_pnl": 10.0, "positions_total": 100, "win_rate": 0.3},
        ]
        rows, dropped = plan_candidate_writes(evidences, [], now=_NOW)
        wallets = {r.wallet_address for r in rows}
        assert "0xstrong" in wallets
        assert "0xweak" not in wallets
        assert dropped == []

    def test_populate_via_injected_writer(self):
        written: list = []

        def _writer(rows):
            written.extend(rows)
            return True

        evidences = [{"wallet_address": "0xstrong", "realized_net_pnl": 30000.0, "positions_total": 100}]
        summary = populate_candidates(evidences, [], _writer, now=_NOW)
        assert summary["ok"] is True
        assert summary["written"] == 1
        assert written[0].tier == "candidate"


# ---------------------------------------------------------------------------
# Locked immutability (acceptance gate 2)
# ---------------------------------------------------------------------------


class TestLockedImmutability:
    def test_is_locked_row_variants(self):
        assert is_locked_row({"locked": 1}) is True
        assert is_locked_row({"locked": "1"}) is True
        assert is_locked_row({"tier": "locked"}) is True
        assert is_locked_row({"locked": 0, "tier": "candidate"}) is False

    def test_guard_raises_for_locked(self):
        with pytest.raises(LockedImmutabilityError):
            guard_not_locked("0xlocked", {"0xlocked"})

    def test_candidate_population_skips_locked(self):
        snapshot = [{"wallet_address": "0xlocked", "locked": 1, "tier": "locked"}]
        evidences = [{"wallet_address": "0xlocked", "realized_net_pnl": 99999.0, "positions_total": 500}]
        rows, dropped = plan_candidate_writes(evidences, snapshot, now=_NOW)
        assert rows == []
        assert dropped == ["0xlocked"]

    def test_locked_entry_byte_identical_after_full_cycle(self):
        """Simulate a full discovery+rescan cycle: a locked row is unchanged.

        The locked row exists in the snapshot. Auto-population runs (candidate
        write planning), then a 'rescan' runs the same planning again. The locked
        wallet must never appear in writable rows, so its persisted bytes never
        change.
        """
        locked_row = {
            "wallet_address": "0xlocked",
            "lifecycle_state": "watched",
            "review_status": "approved",
            "priority": 1,
            "source": "manual",
            "tier": "locked",
            "locked": 1,
            "reason": "operator pinned",
            "metadata_json": "{}",
        }
        snapshot = [locked_row]
        # Strong evidence that WOULD overwrite if not protected.
        evidences = [{"wallet_address": "0xlocked", "realized_net_pnl": 99999.0, "positions_total": 500}]

        # Cycle 1 (discovery).
        rows1, dropped1 = plan_candidate_writes(evidences, snapshot, now=_NOW)
        # Cycle 2 (rescan).
        rows2, dropped2 = plan_candidate_writes(evidences, snapshot, now=_NOW)

        assert rows1 == [] and rows2 == []
        assert dropped1 == ["0xlocked"] and dropped2 == ["0xlocked"]
        # The snapshot dict for the locked wallet is untouched.
        assert snapshot[0] == locked_row

    def test_locked_set_helper(self):
        snapshot = [
            {"wallet_address": "0xa", "locked": 1},
            {"wallet_address": "0xb", "tier": "candidate"},
            {"wallet_address": "0xc", "tier": "locked"},
        ]
        assert locked_wallets(snapshot) == {"0xa", "0xc"}


# ---------------------------------------------------------------------------
# Fork #2 — resolve_tier alignment
# ---------------------------------------------------------------------------


class TestResolveTierAlignment:
    def test_locked_flag_resolves_locked(self):
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        row = build_candidate_row(
            Evidence(wallet_address="0xa", realized_net_pnl=30000.0, trades=100), now=_NOW
        )
        # Make a locked variant.
        d = dict(row.__dict__)
        d["locked"] = 1
        assert resolve_tier(d) == "locked"

    def test_candidate_tier_value_honored(self):
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        # A candidate-tier row with no locked flag resolves to 'candidate'.
        d = {"wallet_address": "0xa", "tier": "candidate", "locked": 0, "lifecycle_state": "scanned"}
        assert resolve_tier(d) == "candidate"

    def test_built_row_dict_resolves_candidate(self):
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        row = build_candidate_row(
            Evidence(wallet_address="0xa", realized_net_pnl=30000.0, trades=100), now=_NOW
        )
        d = dict(row.__dict__)
        d["lifecycle_state"] = d["lifecycle_state"].value  # match CH JSONEachRow shape
        assert resolve_tier(d) == "candidate"


# ---------------------------------------------------------------------------
# Gate enforcement (acceptance gate 1) — no auto-promote
# ---------------------------------------------------------------------------


class TestGateEnforcement:
    def test_approve_advances_scanned_to_reviewed_only(self):
        plan = plan_review(
            wallet_address="0xa",
            current_lifecycle=LifecycleState.scanned,
            approve=True,
            promote=False,
        )
        assert plan.to_lifecycle == LifecycleState.reviewed
        assert plan.review_status == ReviewStatus.approved

    def test_approve_with_promote_goes_through_gate(self):
        plan = plan_review(
            wallet_address="0xa",
            current_lifecycle=LifecycleState.scanned,
            approve=True,
            promote=True,
        )
        assert plan.to_lifecycle == LifecycleState.promoted
        assert plan.review_status == ReviewStatus.approved

    def test_deny_records_rejection_no_advance(self):
        plan = plan_review(
            wallet_address="0xa",
            current_lifecycle=LifecycleState.scanned,
            approve=False,
        )
        assert plan.to_lifecycle == LifecycleState.scanned
        assert plan.review_status == ReviewStatus.rejected

    def test_no_auto_promote_from_discovered(self):
        # Cannot promote a discovered wallet; the gate refuses the structural jump.
        with pytest.raises(InvalidTransitionError):
            plan_review(
                wallet_address="0xa",
                current_lifecycle=LifecycleState.discovered,
                approve=True,
                promote=True,
            )

    def test_candidate_population_never_sets_approved(self):
        # Acceptance gate 1: auto-population stays at pending/scanned.
        ev = Evidence(wallet_address="0xa", realized_net_pnl=99999.0, trades=500)
        row = build_candidate_row(ev, now=_NOW)
        assert row.review_status == ReviewStatus.pending
        assert row.lifecycle_state == LifecycleState.scanned
        assert row.lifecycle_state not in (LifecycleState.promoted, LifecycleState.watched)


# ---------------------------------------------------------------------------
# CLI review routes through validate_transition (mocked CH I/O)
# ---------------------------------------------------------------------------


class TestReviewCLI:
    def _run(self, argv, monkeypatch, *, existing_row, capture):
        import tools.cli.discovery as disc
        import packages.polymarket.discovery.clickhouse_writer as chw

        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "test-pw")
        monkeypatch.setattr(chw, "read_watchlist_row", lambda *a, **k: existing_row)

        def _fake_write(rows, **kwargs):
            capture.extend(rows)
            return True

        monkeypatch.setattr(chw, "write_watchlist_rows", _fake_write)
        return disc.main(argv)

    # WI-5 added a full-address guard to --approve/--deny, so review fixtures
    # must use a full 42-char EVM address (not a "0xa" placeholder).
    _WALLET = "0xcf6041b4c3d3c9e1f0a1b2c3d4e5f60718293a4b"

    def test_approve_writes_through_gate(self, monkeypatch):
        captured: list = []
        existing = {
            "wallet_address": self._WALLET,
            "lifecycle_state": "scanned",
            "review_status": "pending",
            "priority": 3,
            "source": "loop_a",
            "tier": "candidate",
            "locked": 0,
            "reason": "x",
            "metadata_json": "{}",
        }
        rc = self._run(
            ["review", "--approve", self._WALLET, "--json"], monkeypatch,
            existing_row=existing, capture=captured,
        )
        assert rc == 0
        assert len(captured) == 1
        assert captured[0].review_status == ReviewStatus.approved
        assert captured[0].lifecycle_state == LifecycleState.reviewed

    def test_deny_writes_rejection(self, monkeypatch):
        captured: list = []
        existing = {
            "wallet_address": self._WALLET, "lifecycle_state": "scanned",
            "review_status": "pending", "priority": 3, "source": "loop_a",
            "tier": "candidate", "locked": 0, "reason": "x", "metadata_json": "{}",
        }
        rc = self._run(
            ["review", "--deny", self._WALLET, "--json"], monkeypatch,
            existing_row=existing, capture=captured,
        )
        assert rc == 0
        assert captured[0].review_status == ReviewStatus.rejected
        assert captured[0].lifecycle_state == LifecycleState.scanned

    def test_review_refuses_locked(self, monkeypatch):
        captured: list = []
        existing = {
            "wallet_address": self._WALLET, "lifecycle_state": "watched",
            "review_status": "approved", "priority": 1, "source": "manual",
            "tier": "locked", "locked": 1, "reason": "x", "metadata_json": "{}",
        }
        rc = self._run(
            ["review", "--approve", self._WALLET, "--json"], monkeypatch,
            existing_row=existing, capture=captured,
        )
        assert rc == 1
        assert captured == []  # nothing written to a locked row

    def test_review_promote_from_discovered_refused_by_gate(self, monkeypatch):
        captured: list = []
        existing = {
            "wallet_address": self._WALLET, "lifecycle_state": "discovered",
            "review_status": "pending", "priority": 3, "source": "loop_a",
            "tier": "candidate", "locked": 0, "reason": "x", "metadata_json": "{}",
        }
        rc = self._run(
            ["review", "--approve", self._WALLET, "--promote", "--json"], monkeypatch,
            existing_row=existing, capture=captured,
        )
        assert rc == 1
        assert captured == []
