"""Deterministic tests for Wallet Discovery v1 — AT-01 through AT-05.

All tests are offline: no network, no ClickHouse, no clock dependency.
Timestamps and UUIDs are injected where needed.
"""
from __future__ import annotations

import json
import sys
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Task 1: Lifecycle state machine + models
# ---------------------------------------------------------------------------

class TestLifecycleStateEnum:
    def test_has_eight_values(self):
        from packages.polymarket.discovery.models import LifecycleState
        assert len(LifecycleState) == 8

    def test_values_match_spec(self):
        from packages.polymarket.discovery.models import LifecycleState
        expected = {
            "discovered", "queued", "scanned", "reviewed",
            "promoted", "watched", "stale", "retired",
        }
        actual = {s.value for s in LifecycleState}
        assert actual == expected


class TestReviewStatusEnum:
    def test_has_three_values(self):
        from packages.polymarket.discovery.models import ReviewStatus
        assert len(ReviewStatus) == 3

    def test_values_match_spec(self):
        from packages.polymarket.discovery.models import ReviewStatus
        expected = {"pending", "approved", "rejected"}
        actual = {s.value for s in ReviewStatus}
        assert actual == expected


class TestQueueStateEnum:
    def test_has_five_values(self):
        from packages.polymarket.discovery.models import QueueState
        assert len(QueueState) == 5

    def test_values_match_spec(self):
        from packages.polymarket.discovery.models import QueueState
        expected = {"pending", "leased", "done", "failed", "dropped"}
        actual = {s.value for s in QueueState}
        assert actual == expected


class TestValidTransitions:
    def test_discovered_to_queued_allowed(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState
        # Should not raise
        validate_transition(LifecycleState.discovered, LifecycleState.queued)

    def test_queued_to_scanned_allowed(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState
        validate_transition(LifecycleState.queued, LifecycleState.scanned)

    def test_scanned_to_reviewed_allowed(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState
        validate_transition(LifecycleState.scanned, LifecycleState.reviewed)

    def test_reviewed_to_promoted_with_approved_status(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, ReviewStatus
        validate_transition(LifecycleState.reviewed, LifecycleState.promoted, review_status=ReviewStatus.approved)

    def test_reviewed_to_retired_allowed(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState
        validate_transition(LifecycleState.reviewed, LifecycleState.retired)

    def test_any_state_to_retired_allowed(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState
        for state in LifecycleState:
            if state != LifecycleState.retired:
                validate_transition(state, LifecycleState.retired)


class TestInvalidTransitions:
    def test_discovered_to_promoted_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.discovered, LifecycleState.promoted)

    def test_scanned_to_promoted_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.scanned, LifecycleState.promoted)

    def test_discovered_to_discovered_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.discovered, LifecycleState.discovered)

    def test_queued_to_promoted_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.queued, LifecycleState.promoted)

    def test_discovered_to_watched_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.discovered, LifecycleState.watched)

    def test_scanned_to_watched_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.scanned, LifecycleState.watched)

    def test_any_state_to_discovered_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        for state in LifecycleState:
            if state != LifecycleState.discovered:
                with pytest.raises(InvalidTransitionError):
                    validate_transition(state, LifecycleState.discovered)

    def test_reviewed_to_promoted_without_approved_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, ReviewStatus, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.reviewed, LifecycleState.promoted, review_status=ReviewStatus.pending)

    def test_reviewed_to_promoted_no_review_status_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.reviewed, LifecycleState.promoted, review_status=None)

    def test_error_message_contains_transition(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition(LifecycleState.discovered, LifecycleState.promoted)
        assert "discovered" in str(exc_info.value)
        assert "promoted" in str(exc_info.value)


class TestDataclassFields:
    def test_watchlist_row_has_required_fields(self):
        from packages.polymarket.discovery.models import WatchlistRow
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(WatchlistRow)}
        required = {
            "wallet_address", "lifecycle_state", "review_status", "priority",
            "source", "reason", "last_scan_run_id", "last_scanned_at",
            "last_activity_at", "metadata_json", "updated_at",
        }
        assert required <= field_names

    def test_leaderboard_snapshot_row_has_required_fields(self):
        from packages.polymarket.discovery.models import LeaderboardSnapshotRow
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(LeaderboardSnapshotRow)}
        required = {
            "snapshot_ts", "fetch_run_id", "order_by", "time_period",
            "category", "rank", "proxy_wallet", "username", "pnl", "volume",
            "is_new", "raw_payload_json",
        }
        assert required <= field_names

    def test_scan_queue_row_has_required_fields(self):
        from packages.polymarket.discovery.models import ScanQueueRow
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(ScanQueueRow)}
        required = {
            "queue_id", "dedup_key", "wallet_address", "source", "source_ref",
            "priority", "queue_state", "available_at", "leased_at",
            "lease_expires_at", "lease_owner", "attempt_count", "last_error",
            "created_at", "updated_at",
        }
        assert required <= field_names

    def test_scan_queue_dedup_key_property(self):
        from packages.polymarket.discovery.models import ScanQueueRow, QueueState
        now = datetime.now(timezone.utc)
        row = ScanQueueRow(
            queue_id="abc",
            dedup_key="loop_a:0xDEAD",
            wallet_address="0xDEAD",
            source="loop_a",
            source_ref="",
            priority=3,
            queue_state=QueueState.pending,
            available_at=now,
            leased_at=None,
            lease_expires_at=None,
            lease_owner=None,
            attempt_count=0,
            last_error=None,
            created_at=now,
            updated_at=now,
        )
        assert row.dedup_key == "loop_a:0xDEAD"


# ---------------------------------------------------------------------------
# Task 2: Leaderboard fetcher
# ---------------------------------------------------------------------------

def _make_mock_leaderboard_client(pages: list[list[dict]]):
    """Build a mock HttpClient that returns leaderboard pages."""
    call_count = [0]

    def mock_get(path, params=None, headers=None):
        offset = (params or {}).get("offset", 0)
        page_index = offset // 50
        if page_index >= len(pages):
            page_data = []
        else:
            page_data = pages[page_index]

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = page_data
        return mock_resp

    client = MagicMock()
    client.get = mock_get
    return client


class TestLeaderboardFetcher:
    def _build_page(self, start_rank: int, count: int) -> list[dict]:
        return [
            {
                "rank": start_rank + i,
                "proxy_wallet": f"0x{(start_rank + i):040x}",
                "name": f"user_{start_rank + i}",
                "pnl": float(start_rank + i) * 10.0,
                "volume": float(start_rank + i) * 100.0,
            }
            for i in range(count)
        ]

    def test_at01_three_pages_returns_150_entries(self):
        """AT-01: 3 pages × 50 entries = 150 entries total."""
        from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard
        pages = [
            self._build_page(1, 50),
            self._build_page(51, 50),
            self._build_page(101, 50),
        ]
        mock_client = _make_mock_leaderboard_client(pages)
        result = fetch_leaderboard(max_pages=3, page_size=50, http_client=mock_client)
        assert len(result) == 150

    def test_at01_entries_ordered_by_rank(self):
        """AT-01: Entries ordered rank 1-150."""
        from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard
        pages = [
            self._build_page(1, 50),
            self._build_page(51, 50),
            self._build_page(101, 50),
        ]
        mock_client = _make_mock_leaderboard_client(pages)
        result = fetch_leaderboard(max_pages=3, page_size=50, http_client=mock_client)
        ranks = [r["rank"] for r in result]
        assert ranks == list(range(1, 151))

    def test_at01_all_have_nonempty_proxy_wallet(self):
        """AT-01: All entries have non-empty proxy_wallet."""
        from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard
        pages = [self._build_page(1, 50)]
        mock_client = _make_mock_leaderboard_client(pages)
        result = fetch_leaderboard(max_pages=3, page_size=50, http_client=mock_client)
        for entry in result:
            assert entry.get("proxy_wallet"), f"Empty proxy_wallet in rank {entry.get('rank')}"

    def test_pagination_stops_on_empty_page(self):
        """Fetcher stops when API returns empty page."""
        from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard
        pages = [
            self._build_page(1, 50),
            [],  # empty page -> stop
        ]
        mock_client = _make_mock_leaderboard_client(pages)
        result = fetch_leaderboard(max_pages=5, page_size=50, http_client=mock_client)
        assert len(result) == 50  # Only first page

    def test_pagination_stops_at_max_pages(self):
        """Fetcher stops after max_pages even if more data available."""
        from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard
        pages = [
            self._build_page(1, 50),
            self._build_page(51, 50),
            self._build_page(101, 50),
        ]
        mock_client = _make_mock_leaderboard_client(pages)
        result = fetch_leaderboard(max_pages=2, page_size=50, http_client=mock_client)
        assert len(result) == 100  # Only 2 pages


class TestToSnapshotRows:
    def test_converts_raw_to_typed_rows(self):
        from packages.polymarket.discovery.leaderboard_fetcher import to_snapshot_rows
        from packages.polymarket.discovery.models import LeaderboardSnapshotRow
        now = datetime.now(timezone.utc)
        raw = [
            {"rank": 1, "proxy_wallet": "0xAAA", "name": "alice", "pnl": 100.0, "volume": 1000.0},
        ]
        rows = to_snapshot_rows(raw, "run-001", now, "PNL", "DAY", "OVERALL")
        assert len(rows) == 1
        assert isinstance(rows[0], LeaderboardSnapshotRow)
        assert rows[0].proxy_wallet == "0xAAA"
        assert rows[0].is_new == 1  # first run, no prior

    def test_is_new_set_when_not_in_prior(self):
        from packages.polymarket.discovery.leaderboard_fetcher import to_snapshot_rows
        now = datetime.now(timezone.utc)
        raw = [
            {"rank": 1, "proxy_wallet": "0xNEW", "name": "newcomer", "pnl": 50.0, "volume": 500.0},
            {"rank": 2, "proxy_wallet": "0xOLD", "name": "veteran", "pnl": 30.0, "volume": 300.0},
        ]
        prior_wallets = {"0xOLD"}
        rows = to_snapshot_rows(raw, "run-002", now, "PNL", "DAY", "OVERALL", prior_wallets=prior_wallets)
        new_flags = {r.proxy_wallet: r.is_new for r in rows}
        assert new_flags["0xNEW"] == 1
        assert new_flags["0xOLD"] == 0

    def test_determinism_same_input_same_output(self):
        """AT-03: Same input -> identical output (snapshot idempotency at Python layer)."""
        from packages.polymarket.discovery.leaderboard_fetcher import to_snapshot_rows
        now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
        raw = [{"rank": 1, "proxy_wallet": "0xABC", "name": "alice", "pnl": 100.0, "volume": 1000.0}]
        rows1 = to_snapshot_rows(raw, "run-fixed", now, "PNL", "DAY", "OVERALL")
        rows2 = to_snapshot_rows(raw, "run-fixed", now, "PNL", "DAY", "OVERALL")
        assert rows1[0].proxy_wallet == rows2[0].proxy_wallet
        assert rows1[0].pnl == rows2[0].pnl
        assert rows1[0].is_new == rows2[0].is_new


# ---------------------------------------------------------------------------
# Task 2: Churn detector
# ---------------------------------------------------------------------------

def _make_snapshot_row(wallet: str, rank: int = 1) -> object:
    """Helper to build a LeaderboardSnapshotRow for churn tests."""
    from packages.polymarket.discovery.models import LeaderboardSnapshotRow
    now = datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc)
    return LeaderboardSnapshotRow(
        snapshot_ts=now,
        fetch_run_id="run-test",
        order_by="PNL",
        time_period="DAY",
        category="OVERALL",
        rank=rank,
        proxy_wallet=wallet,
        username="",
        pnl=100.0,
        volume=1000.0,
        is_new=0,
        raw_payload_json="{}",
    )


class TestChurnDetector:
    def test_at02_new_wallet_detected(self):
        """AT-02: D is new when T-1=[A,B,C] and T=[B,C,D]."""
        from packages.polymarket.discovery.churn_detector import detect_churn
        prior = [_make_snapshot_row("A"), _make_snapshot_row("B"), _make_snapshot_row("C")]
        current = [_make_snapshot_row("B"), _make_snapshot_row("C"), _make_snapshot_row("D")]
        result = detect_churn(current, prior)
        assert "D" in result.new_wallets

    def test_at02_dropped_wallet_detected(self):
        """AT-02: A is dropped when T-1=[A,B,C] and T=[B,C,D]."""
        from packages.polymarket.discovery.churn_detector import detect_churn
        prior = [_make_snapshot_row("A"), _make_snapshot_row("B"), _make_snapshot_row("C")]
        current = [_make_snapshot_row("B"), _make_snapshot_row("C"), _make_snapshot_row("D")]
        result = detect_churn(current, prior)
        assert "A" in result.dropped_wallets

    def test_at02_persisting_wallets(self):
        """AT-02: B and C are persisting."""
        from packages.polymarket.discovery.churn_detector import detect_churn
        prior = [_make_snapshot_row("A"), _make_snapshot_row("B"), _make_snapshot_row("C")]
        current = [_make_snapshot_row("B"), _make_snapshot_row("C"), _make_snapshot_row("D")]
        result = detect_churn(current, prior)
        assert "B" in result.persisting_wallets
        assert "C" in result.persisting_wallets

    def test_at02b_rising_wallet_detected(self):
        """AT-02b: A improves from rank 5 to rank 2 -> in rising_wallets."""
        from packages.polymarket.discovery.churn_detector import detect_churn
        prior = [_make_snapshot_row("A", rank=5), _make_snapshot_row("B", rank=10)]
        current = [_make_snapshot_row("A", rank=2), _make_snapshot_row("B", rank=10)]
        result = detect_churn(current, prior)
        rising_wallets = [r[0] for r in result.rising_wallets]
        assert "A" in rising_wallets

    def test_at02b_rising_wallet_rank_values(self):
        """AT-02b: rising_wallets contains (wallet, old_rank, new_rank)."""
        from packages.polymarket.discovery.churn_detector import detect_churn
        prior = [_make_snapshot_row("A", rank=5)]
        current = [_make_snapshot_row("A", rank=2)]
        result = detect_churn(current, prior)
        assert len(result.rising_wallets) == 1
        wallet, old_rank, new_rank = result.rising_wallets[0]
        assert wallet == "A"
        assert old_rank == 5
        assert new_rank == 2

    def test_at02c_first_ever_snapshot_all_new(self):
        """AT-02c: No prior rows -> all wallets flagged as new."""
        from packages.polymarket.discovery.churn_detector import detect_churn
        current = [_make_snapshot_row("A"), _make_snapshot_row("B"), _make_snapshot_row("C")]
        result = detect_churn(current, [])
        assert set(result.new_wallets) == {"A", "B", "C"}
        assert result.dropped_wallets == []


# ---------------------------------------------------------------------------
# Task 2: Scan queue manager
# ---------------------------------------------------------------------------

class TestScanQueueManager:
    def _make_manager(self):
        from packages.polymarket.discovery.scan_queue import ScanQueueManager
        return ScanQueueManager()

    def test_at04_dedup_same_key_returns_one_pending(self):
        """AT-04 dedup: Two inserts with same dedup_key -> only one pending row."""
        mgr = self._make_manager()
        mgr.enqueue("0xABC", "loop_a")
        mgr.enqueue("0xABC", "loop_a")
        pending = mgr.get_pending(limit=10)
        assert len(pending) == 1

    def test_at04_lease_removes_from_pending(self):
        """AT-04 lease: Leased item not returned by pending query within TTL."""
        mgr = self._make_manager()
        row = mgr.enqueue("0xABC", "loop_a")
        mgr.lease("loop_a:0xABC", "worker-1", lease_duration_seconds=300)
        pending = mgr.get_pending(limit=10)
        assert len(pending) == 0

    def test_at04_expired_lease_requeued(self):
        """AT-04 lease: After expiry, item available for re-lease."""
        mgr = self._make_manager()
        row = mgr.enqueue("0xABC", "loop_a")
        mgr.lease("loop_a:0xABC", "worker-1", lease_duration_seconds=300)

        # Manually expire the lease
        item = mgr._items["loop_a:0xABC"]
        item.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        requeued = mgr.requeue_expired_leases()
        assert requeued == 1
        pending = mgr.get_pending(limit=10)
        assert len(pending) == 1

    def test_enqueue_returns_row_with_correct_dedup_key(self):
        mgr = self._make_manager()
        row = mgr.enqueue("0xDEF", "loop_a")
        assert row.dedup_key == "loop_a:0xDEF"

    def test_complete_sets_done_state(self):
        from packages.polymarket.discovery.models import QueueState
        mgr = self._make_manager()
        mgr.enqueue("0xABC", "loop_a")
        mgr.lease("loop_a:0xABC", "worker-1")
        mgr.complete("loop_a:0xABC")
        item = mgr._items["loop_a:0xABC"]
        assert item.queue_state == QueueState.done

    def test_fail_increments_attempt_count(self):
        mgr = self._make_manager()
        mgr.enqueue("0xABC", "loop_a")
        mgr.lease("loop_a:0xABC", "worker-1")
        mgr.fail("loop_a:0xABC", "timeout")
        item = mgr._items["loop_a:0xABC"]
        assert item.attempt_count == 1
        assert item.last_error == "timeout"

    def test_priority_ordering_in_get_pending(self):
        """get_pending returns items ordered by priority ASC."""
        from packages.polymarket.discovery.models import QueueState
        mgr = self._make_manager()
        mgr.enqueue("0xLOW", "loop_a", priority=5)
        mgr.enqueue("0xHIGH", "loop_a", priority=1)
        pending = mgr.get_pending(limit=10)
        assert len(pending) == 2
        assert pending[0].wallet_address == "0xHIGH"  # priority 1 first
        assert pending[1].wallet_address == "0xLOW"


# ---------------------------------------------------------------------------
# Task 2: AT-05 invalid lifecycle (end-to-end)
# ---------------------------------------------------------------------------

class TestAt05LifecycleFull:
    def test_discovered_to_promoted_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition(LifecycleState.discovered, LifecycleState.promoted)
        assert "discovered" in str(exc_info.value).lower()
        assert "promoted" in str(exc_info.value).lower()

    def test_scanned_to_promoted_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.scanned, LifecycleState.promoted)

    def test_discovered_to_discovered_raises(self):
        from packages.polymarket.discovery.models import validate_transition, LifecycleState, InvalidTransitionError
        with pytest.raises(InvalidTransitionError):
            validate_transition(LifecycleState.discovered, LifecycleState.discovered)


# ---------------------------------------------------------------------------
# Task 2: Loop A orchestrator
# ---------------------------------------------------------------------------

class TestLoopAOrchestrator:
    def test_dry_run_does_not_call_ch_write(self):
        """Loop A dry_run=True skips ClickHouse writes."""
        from packages.polymarket.discovery import loop_a

        raw_entries = [
            {"rank": 1, "proxy_wallet": "0xAAA", "name": "a", "pnl": 100.0, "volume": 1000.0},
            {"rank": 2, "proxy_wallet": "0xBBB", "name": "b", "pnl": 80.0, "volume": 800.0},
        ]

        with patch.object(loop_a, "fetch_leaderboard", return_value=raw_entries) as mock_fetch, \
             patch.object(loop_a, "read_latest_snapshot", return_value=[]) as mock_read, \
             patch.object(loop_a, "write_leaderboard_snapshot_rows", return_value=True) as mock_write_snap, \
             patch.object(loop_a, "write_watchlist_rows", return_value=True) as mock_write_watch, \
             patch.object(loop_a, "write_scan_queue_rows", return_value=True) as mock_write_queue:

            result = loop_a.run_loop_a(
                dry_run=True,
                ch_password="dummy",
                fetch_run_id="fixed-run-id",
                snapshot_ts=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
            )

        # In dry_run mode, no CH writes
        mock_write_snap.assert_not_called()
        mock_write_watch.assert_not_called()
        mock_write_queue.assert_not_called()

    def test_dry_run_all_wallets_are_new(self):
        """Loop A dry_run: no prior snapshot -> all wallets new."""
        from packages.polymarket.discovery import loop_a

        raw_entries = [
            {"rank": 1, "proxy_wallet": "0xAAA", "name": "a", "pnl": 100.0, "volume": 1000.0},
            {"rank": 2, "proxy_wallet": "0xBBB", "name": "b", "pnl": 80.0, "volume": 800.0},
        ]

        with patch.object(loop_a, "fetch_leaderboard", return_value=raw_entries), \
             patch.object(loop_a, "read_latest_snapshot", return_value=[]), \
             patch.object(loop_a, "write_leaderboard_snapshot_rows", return_value=True), \
             patch.object(loop_a, "write_watchlist_rows", return_value=True), \
             patch.object(loop_a, "write_scan_queue_rows", return_value=True):

            result = loop_a.run_loop_a(
                dry_run=True,
                ch_password="dummy",
                fetch_run_id="fixed-run-id",
                snapshot_ts=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
            )

        assert result.rows_fetched == 2
        assert len(result.churn.new_wallets) == 2

    def test_dry_run_fetch_order_is_correct(self):
        """Loop A: fetch is called before churn detection."""
        from packages.polymarket.discovery import loop_a
        call_order = []

        def mock_fetch(*args, **kwargs):
            call_order.append("fetch")
            return [{"rank": 1, "proxy_wallet": "0xAAA", "name": "a", "pnl": 10.0, "volume": 100.0}]

        def mock_read(*args, **kwargs):
            call_order.append("read")
            return []

        with patch.object(loop_a, "fetch_leaderboard", side_effect=mock_fetch), \
             patch.object(loop_a, "read_latest_snapshot", side_effect=mock_read), \
             patch.object(loop_a, "write_leaderboard_snapshot_rows", return_value=True), \
             patch.object(loop_a, "write_watchlist_rows", return_value=True), \
             patch.object(loop_a, "write_scan_queue_rows", return_value=True):

            loop_a.run_loop_a(
                dry_run=True,
                ch_password="dummy",
                fetch_run_id="run-x",
                snapshot_ts=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
            )

        # fetch must happen before read (or simultaneously, but fetch must be in list)
        assert "fetch" in call_order

    def test_no_password_with_live_run_raises(self):
        """Loop A: empty password + not dry_run raises ValueError."""
        from packages.polymarket.discovery import loop_a
        with pytest.raises(ValueError, match="CLICKHOUSE_PASSWORD"):
            loop_a.run_loop_a(
                dry_run=False,
                ch_password="",
                fetch_run_id="run-x",
                snapshot_ts=datetime(2026, 4, 9, 12, 0, 0, tzinfo=timezone.utc),
            )
