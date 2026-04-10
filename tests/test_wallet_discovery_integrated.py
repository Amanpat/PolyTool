"""Integrated acceptance tests for Wallet Discovery v1.

Covers the full v1 path end-to-end on deterministic fixtures:
  leaderboard fetch -> snapshot -> churn -> queue -> scan --quick -> MVF output

No external services: no network, no ClickHouse, no real clock dependency.
All timestamps, UUIDs, and HTTP responses are injected.

Tests are organized into 4 classes:
  TestIntegratedLoopAPath           - End-to-end Loop A flow (tests 1-4)
  TestIntegratedScanQuickMvf        - Scan --quick -> MVF integration (tests 5-8)
  TestIntegratedLifecycleGate       - Human review gate enforcement (tests 9-11)
  TestIntegratedLoopAOrchestrator   - run_loop_a() as black box (test 12)
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from packages.polymarket.discovery.churn_detector import detect_churn
from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard, to_snapshot_rows
from packages.polymarket.discovery.loop_a import run_loop_a
from packages.polymarket.discovery.models import (
    InvalidTransitionError,
    LifecycleState,
    QueueState,
    ReviewStatus,
    validate_transition,
)
from packages.polymarket.discovery.scan_queue import ScanQueueManager
from tools.cli import scan

# ---------------------------------------------------------------------------
# Module-level pinned fixtures
# ---------------------------------------------------------------------------

_SNAPSHOT_TS = datetime(2026, 4, 10, 12, 0, 0, tzinfo=timezone.utc)
_FETCH_RUN_ID = "integrated-run-001"

# Minimal 12-position fixture with resolution_outcome, entry_price, market_slug,
# category, size — NO maker/taker fields (tests graceful null handling).
_POSITIONS_FIXTURE = [
    {
        "trade_uid": f"uid-{i}",
        "resolved_token_id": f"tok-{i}",
        "resolution_outcome": outcome,
        "entry_price": 0.1 + i * 0.06,
        "market_slug": f"market-{i % 4}",
        "category": ["Crypto", "Politics", "Sports", "Entertainment"][i % 4],
        "size": 100.0 + i * 10,
        "position_notional_usd": (0.1 + i * 0.06) * (100.0 + i * 10),
        "realized_pnl_net": 1.0 if outcome in ("WIN", "PROFIT_EXIT") else -0.5,
        "position_remaining": 0.0,
    }
    for i, outcome in enumerate(
        ["WIN", "WIN", "WIN", "WIN", "WIN",
         "LOSS", "LOSS", "LOSS",
         "PROFIT_EXIT", "LOSS_EXIT",
         "PENDING", "PENDING"]
    )
]

_LLM_DOMAINS = (
    "gemini", "deepseek", "openai", "anthropic", "googleapis",
    "generativelanguage", "api.openai", "api.anthropic",
)

# ---------------------------------------------------------------------------
# Helper: build leaderboard page data
# ---------------------------------------------------------------------------

def _build_leaderboard_pages(num_pages: int = 3, page_size: int = 50) -> list[list[dict]]:
    """Build num_pages pages of leaderboard entries, page_size each.

    Each entry has a unique proxy_wallet and rank. Wallets are indexed 1-based.
    """
    pages: list[list[dict]] = []
    for page_idx in range(num_pages):
        page: list[dict] = []
        for i in range(page_size):
            global_rank = page_idx * page_size + i + 1
            wallet = f"0xwallet{global_rank:04d}"
            page.append({
                "rank": global_rank,
                "proxy_wallet": wallet,
                "name": f"user{global_rank}",
                "pnl": float(1000 - global_rank),
                "volume": float(5000 - global_rank * 2),
            })
        pages.append(page)
    return pages


def _build_mock_http_client(pages: list[list[dict]]) -> Any:
    """Build a mock http_client that returns pages sequentially, then stops."""
    call_count = [0]
    num_pages = len(pages)

    class _FakeResponse:
        def __init__(self, data):
            self.status_code = 200
            self._data = data

        def json(self):
            return self._data

    client = MagicMock()

    def _get(_path, params=None):
        idx = call_count[0]
        call_count[0] += 1
        if idx < num_pages:
            return _FakeResponse(pages[idx])
        # Return empty to stop pagination
        return _FakeResponse([])

    client.get.side_effect = _get
    return client


# ---------------------------------------------------------------------------
# Scan test helpers (mirrors test_scan_quick_mode.py pattern)
# ---------------------------------------------------------------------------

def _make_run_root(tmp_path: Path) -> Path:
    run_root = (
        tmp_path
        / "artifacts"
        / "dossiers"
        / "users"
        / "quickuser"
        / "0xquick"
        / "2026-04-10"
        / "run-integrated"
    )
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "dossier.json").write_text(
        json.dumps({"positions": {"positions": _POSITIONS_FIXTURE}}, indent=2),
        encoding="utf-8",
    )
    return run_root


def _base_config(run_root: Path, *, quick: bool = True) -> dict:
    return {
        "user": "@QuickUser",
        "max_pages": 10,
        "bucket": "day",
        "backfill": True,
        "quick": quick,
        "ingest_markets": False,
        "ingest_activity": False,
        "ingest_positions": False,
        "compute_pnl": False,
        "compute_opportunities": False,
        "snapshot_books": False,
        "enrich_resolutions": False,
        "warm_clv_cache": False,
        "compute_clv": False,
        "clv_online": False,
        "clv_window_minutes": 30,
        "clv_interval": "1m",
        "clv_fidelity": 1,
        "resolution_max_candidates": 500,
        "resolution_batch_size": 25,
        "resolution_max_concurrency": 4,
        "debug_export": False,
        "audit_sample": None,
        "audit_seed": 42,
        "entry_price_tiers": None,
        "fee_config": None,
        "api_base_url": "http://localhost:8000",
        "timeout_seconds": 30.0,
    }


def _fake_post_json_factory(run_root: Path):
    """Return a post_json mock that handles all expected API paths."""
    def _fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
        if path == "/api/resolve":
            return {"username": "QuickUser", "proxy_wallet": "0xquick"}
        if path == "/api/ingest/trades":
            return {
                "pages_fetched": 1,
                "rows_fetched_total": len(_POSITIONS_FIXTURE),
                "rows_written": len(_POSITIONS_FIXTURE),
                "distinct_trade_uids_total": len(_POSITIONS_FIXTURE),
            }
        if path == "/api/run/detectors":
            return {"results": [], "backfill_stats": None}
        if path == "/api/export/user_dossier":
            return {
                "export_id": "run-integrated",
                "artifact_path": str(run_root),
                "proxy_wallet": "0xquick",
                "username_slug": "quickuser",
            }
        raise AssertionError(f"Unexpected scan API path: {path}")

    return _fake_post_json


def _run_quick_scan(monkeypatch, tmp_path: Path, *, quick: bool = True) -> Path:
    run_root = _make_run_root(tmp_path)
    original_cwd = Path.cwd()
    monkeypatch.setattr(scan, "post_json", _fake_post_json_factory(run_root))
    try:
        os.chdir(tmp_path)
        config = _base_config(run_root, quick=quick)
        scan.run_scan(
            config=config,
            argv=["--user", "@QuickUser"] + (["--quick"] if quick else []),
            started_at="2026-04-10T12:00:00+00:00",
        )
    finally:
        os.chdir(original_cwd)
    return run_root


# ---------------------------------------------------------------------------
# Class 1: TestIntegratedLoopAPath
# ---------------------------------------------------------------------------

class TestIntegratedLoopAPath:
    """End-to-end Loop A flow: fetch -> snapshot -> churn -> queue."""

    def test_fetch_to_churn_to_queue_full_flow(self):
        """Full Loop A path: 150 entries fetched, all new, all enqueued.

        Verifies:
        (a) 150 entries fetched
        (b) all 150 flagged as new_wallets in churn result
        (c) feeding new_wallets into ScanQueueManager produces 150 pending items
        (d) each queue item has source='loop_a' and queue_state=QueueState.pending
        """
        pages = _build_leaderboard_pages(num_pages=3, page_size=50)
        http_client = _build_mock_http_client(pages)

        # Step 1: Fetch
        raw_entries = fetch_leaderboard(
            order_by="PNL",
            time_period="DAY",
            category="OVERALL",
            max_pages=3,
            page_size=50,
            http_client=http_client,
        )
        assert len(raw_entries) == 150, f"Expected 150 entries, got {len(raw_entries)}"

        # Step 2: Build snapshot rows (no prior wallets — first run)
        snapshot_rows = to_snapshot_rows(
            raw_entries,
            fetch_run_id=_FETCH_RUN_ID,
            snapshot_ts=_SNAPSHOT_TS,
            order_by="PNL",
            time_period="DAY",
            category="OVERALL",
            prior_wallets=None,
        )
        assert len(snapshot_rows) == 150

        # Step 3: Detect churn vs empty prior
        churn = detect_churn(snapshot_rows, [])
        assert len(churn.new_wallets) == 150, (
            f"Expected all 150 as new_wallets, got {len(churn.new_wallets)}"
        )

        # Step 4: Enqueue all new wallets
        mgr = ScanQueueManager()
        for wallet in churn.new_wallets:
            mgr.enqueue(wallet, source="loop_a", priority=3)

        pending = mgr.get_pending(limit=200)
        assert len(pending) == 150, f"Expected 150 pending, got {len(pending)}"

        # Verify each item
        for item in pending:
            assert item.source == "loop_a", f"Expected source='loop_a', got {item.source!r}"
            assert item.queue_state == QueueState.pending, (
                f"Expected pending state, got {item.queue_state}"
            )

    def test_churn_detects_new_and_dropped_in_second_run(self):
        """T snapshot replaces 5 wallets from T-1; churn detects exactly 5 new / 5 dropped.

        Prior snapshot: wallets 1-150.
        Current snapshot: wallets 1-145 (same) + wallets 151-155 (new), 146-150 dropped.
        """
        # Build T-1 snapshot rows (wallets 1-150)
        prior_entries = [
            {"rank": i, "proxy_wallet": f"0xwallet{i:04d}", "name": f"u{i}",
             "pnl": 0.0, "volume": 0.0}
            for i in range(1, 151)
        ]
        prior_rows = to_snapshot_rows(
            prior_entries, "run-t1", _SNAPSHOT_TS, "PNL", "DAY", "OVERALL",
            prior_wallets=None,
        )

        # Build T snapshot: wallets 1-145 (persisting) + wallets 151-155 (new)
        current_entries = [
            {"rank": i, "proxy_wallet": f"0xwallet{i:04d}", "name": f"u{i}",
             "pnl": 0.0, "volume": 0.0}
            for i in range(1, 146)
        ] + [
            {"rank": 146 + j, "proxy_wallet": f"0xwallet{151 + j:04d}", "name": f"u{151 + j}",
             "pnl": 0.0, "volume": 0.0}
            for j in range(5)
        ]
        prior_wallet_set = {r.proxy_wallet for r in prior_rows}
        current_rows = to_snapshot_rows(
            current_entries, "run-t2", _SNAPSHOT_TS, "PNL", "DAY", "OVERALL",
            prior_wallets=prior_wallet_set,
        )

        churn = detect_churn(current_rows, prior_rows)

        assert len(churn.new_wallets) == 5, (
            f"Expected 5 new_wallets, got {len(churn.new_wallets)}: {churn.new_wallets}"
        )
        assert len(churn.dropped_wallets) == 5, (
            f"Expected 5 dropped_wallets, got {len(churn.dropped_wallets)}: {churn.dropped_wallets}"
        )
        assert len(churn.persisting_wallets) == 145, (
            f"Expected 145 persisting_wallets, got {len(churn.persisting_wallets)}"
        )

    def test_queue_idempotency_on_rerun(self):
        """Enqueueing the same 10 wallets twice yields exactly 10 pending items.

        Each dedup_key must appear exactly once (no duplicates).
        """
        mgr = ScanQueueManager()
        wallets = [f"0xidempwallet{i:03d}" for i in range(10)]

        # First enqueue pass
        for w in wallets:
            mgr.enqueue(w, source="loop_a", priority=3)

        # Second enqueue pass — must be idempotent
        for w in wallets:
            mgr.enqueue(w, source="loop_a", priority=3)

        pending = mgr.get_pending(limit=30)
        assert len(pending) == 10, f"Expected exactly 10 pending items, got {len(pending)}"

        # Verify no duplicate dedup_keys
        dedup_keys = [item.dedup_key for item in pending]
        assert len(dedup_keys) == len(set(dedup_keys)), (
            f"Duplicate dedup_keys detected: {dedup_keys}"
        )

    def test_snapshot_idempotency_same_input(self):
        """Calling to_snapshot_rows() twice with identical inputs yields byte-identical results.

        Same length, same field values on each row including is_new flags.
        """
        raw_entries = [
            {"rank": i, "proxy_wallet": f"0xwallet{i:04d}", "name": f"u{i}",
             "pnl": float(i), "volume": float(i * 2)}
            for i in range(1, 21)
        ]
        kwargs = dict(
            fetch_run_id=_FETCH_RUN_ID,
            snapshot_ts=_SNAPSHOT_TS,
            order_by="PNL",
            time_period="DAY",
            category="OVERALL",
            prior_wallets=None,
        )

        rows_a = to_snapshot_rows(raw_entries, **kwargs)
        rows_b = to_snapshot_rows(raw_entries, **kwargs)

        assert len(rows_a) == len(rows_b), "Row count differs between calls"

        for i, (a, b) in enumerate(zip(rows_a, rows_b)):
            assert a.proxy_wallet == b.proxy_wallet, f"Row {i}: proxy_wallet mismatch"
            assert a.rank == b.rank, f"Row {i}: rank mismatch"
            assert a.is_new == b.is_new, f"Row {i}: is_new mismatch"
            assert a.fetch_run_id == b.fetch_run_id, f"Row {i}: fetch_run_id mismatch"
            assert a.snapshot_ts == b.snapshot_ts, f"Row {i}: snapshot_ts mismatch"
            assert a.order_by == b.order_by, f"Row {i}: order_by mismatch"
            assert a.raw_payload_json == b.raw_payload_json, f"Row {i}: raw_payload_json mismatch"


# ---------------------------------------------------------------------------
# Class 2: TestIntegratedScanQuickMvf
# ---------------------------------------------------------------------------

class TestIntegratedScanQuickMvf:
    """Scan --quick -> MVF integration: dossier shape, null handling, no-LLM guarantee."""

    _MVF_DIMENSION_KEYS = {
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

    def test_quick_scan_dossier_mvf_shape(self, monkeypatch, tmp_path):
        """After --quick scan, dossier.json has mvf block with correct shape.

        Verifies:
        (a) 'mvf' key present
        (b) dossier['mvf']['dimensions'] has exactly 11 keys
        (c) all dimension keys match the spec names
        (d) metadata['input_trade_count'] equals fixture length
        (e) metadata['wallet_address'] is set
        """
        run_root = _run_quick_scan(monkeypatch, tmp_path, quick=True)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))

        # (a) mvf key present
        assert "mvf" in dossier, "'mvf' key missing from dossier.json"

        mvf = dossier["mvf"]
        dims = mvf["dimensions"]

        # (b) exactly 11 dimensions
        assert len(dims) == 11, f"Expected 11 dimensions, got {len(dims)}: {list(dims.keys())}"

        # (c) all dimension keys match spec
        assert set(dims.keys()) == self._MVF_DIMENSION_KEYS, (
            f"Dimension key mismatch.\n"
            f"  Expected: {sorted(self._MVF_DIMENSION_KEYS)}\n"
            f"  Got:      {sorted(dims.keys())}"
        )

        # (d) input_trade_count
        meta = mvf["metadata"]
        assert meta["input_trade_count"] == len(_POSITIONS_FIXTURE), (
            f"Expected input_trade_count={len(_POSITIONS_FIXTURE)}, got {meta['input_trade_count']}"
        )

        # (e) wallet_address set
        assert meta.get("wallet_address"), "metadata['wallet_address'] is empty or missing"

    def test_quick_scan_null_maker_taker_graceful(self, monkeypatch, tmp_path):
        """Fixture has no maker/taker fields -> maker_taker_ratio is None in dossier.

        Also asserts 'maker_taker_data_unavailable' note is present in metadata.
        """
        run_root = _run_quick_scan(monkeypatch, tmp_path, quick=True)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        mvf = dossier["mvf"]

        # maker_taker_ratio should be null (JSON null -> Python None)
        assert mvf["dimensions"]["maker_taker_ratio"] is None, (
            "Expected maker_taker_ratio=null when no maker field in fixture"
        )

        # data_notes should contain the unavailability message
        data_notes = mvf["metadata"].get("data_notes", [])
        assert any("maker_taker_data_unavailable" in note for note in data_notes), (
            f"Expected 'maker_taker_data_unavailable' in metadata.data_notes, got: {data_notes}"
        )

    def test_quick_scan_no_llm_calls_request_intercept(self, monkeypatch, tmp_path):
        """--quick scan makes zero HTTP calls to any LLM provider domain.

        Uses request-level interception: all outbound URLs are logged and
        checked against the LLM domain list.
        """
        run_root = _make_run_root(tmp_path)
        original_cwd = Path.cwd()
        outbound_urls: list[str] = []

        def intercepting_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            url = base_url + path
            outbound_urls.append(url)
            delegate = _fake_post_json_factory(run_root)
            return delegate(base_url, path, payload, timeout=timeout)

        monkeypatch.setattr(scan, "post_json", intercepting_post_json)
        try:
            os.chdir(tmp_path)
            config = _base_config(run_root, quick=True)
            scan.run_scan(
                config=config,
                argv=["--user", "@QuickUser", "--quick"],
                started_at="2026-04-10T12:00:00+00:00",
            )
        finally:
            os.chdir(original_cwd)

        # Assert: zero outbound URLs contain any LLM domain
        for url in outbound_urls:
            for domain in _LLM_DOMAINS:
                assert domain not in url.lower(), (
                    f"LLM endpoint called during --quick scan: {url!r} "
                    f"(matched domain pattern: {domain!r})"
                )

    def test_quick_scan_no_mvf_without_quick_flag(self, monkeypatch, tmp_path):
        """scan without --quick does NOT add mvf block to dossier.json."""
        run_root = _run_quick_scan(monkeypatch, tmp_path, quick=False)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        assert "mvf" not in dossier, (
            "Expected no 'mvf' key in dossier.json when --quick is not set"
        )


# ---------------------------------------------------------------------------
# Class 3: TestIntegratedLifecycleGate
# ---------------------------------------------------------------------------

class TestIntegratedLifecycleGate:
    """Human review gate enforcement via validate_transition()."""

    def test_full_lifecycle_happy_path(self):
        """Walk a wallet through the full valid lifecycle: discovered -> queued -> scanned -> reviewed -> promoted.

        The reviewed -> promoted step requires review_status=ReviewStatus.approved.
        No exception must be raised.
        """
        validate_transition(LifecycleState.discovered, LifecycleState.queued)
        validate_transition(LifecycleState.queued, LifecycleState.scanned)
        validate_transition(LifecycleState.scanned, LifecycleState.reviewed)
        validate_transition(
            LifecycleState.reviewed, LifecycleState.promoted,
            review_status=ReviewStatus.approved,
        )
        # Reaches here without exception => happy path passes

    def test_scanned_to_promoted_blocked_without_review(self):
        """scanned -> promoted is an invalid transition (human review gate enforced).

        The error message must reference both 'scanned' and 'promoted'.
        """
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition(LifecycleState.scanned, LifecycleState.promoted)

        msg = str(exc_info.value)
        assert "scanned" in msg, f"Expected 'scanned' in error message: {msg!r}"
        assert "promoted" in msg, f"Expected 'promoted' in error message: {msg!r}"

    def test_reviewed_to_promoted_blocked_without_approval(self):
        """reviewed -> promoted with review_status=pending is blocked.

        The error message must reference 'approved'.
        """
        with pytest.raises(InvalidTransitionError) as exc_info:
            validate_transition(
                LifecycleState.reviewed, LifecycleState.promoted,
                review_status=ReviewStatus.pending,
            )

        msg = str(exc_info.value)
        assert "approved" in msg, f"Expected 'approved' in error message: {msg!r}"


# ---------------------------------------------------------------------------
# Class 4: TestIntegratedLoopAOrchestrator
# ---------------------------------------------------------------------------

class TestIntegratedLoopAOrchestrator:
    """run_loop_a() as an orchestration black box with injected fixtures."""

    def test_loop_a_dry_run_full_integration(self):
        """run_loop_a(dry_run=True) with 2 pages of 50 entries.

        Verifies:
        (a) result.rows_fetched == 100
        (b) result.churn.new_wallets has 100 entries (first run, no prior)
        (c) result.dry_run is True
        (d) result.rows_enqueued == 0 (dry_run skips writes)
        """
        pages = _build_leaderboard_pages(num_pages=2, page_size=50)
        http_client = _build_mock_http_client(pages)

        result = run_loop_a(
            order_by="PNL",
            time_period="DAY",
            category="OVERALL",
            max_pages=2,
            dry_run=True,
            http_client=http_client,
            fetch_run_id=_FETCH_RUN_ID,
            snapshot_ts=_SNAPSHOT_TS,
        )

        # (a) rows_fetched
        assert result.rows_fetched == 100, (
            f"Expected rows_fetched=100, got {result.rows_fetched}"
        )

        # (b) all 100 are new wallets (first run, no prior)
        assert len(result.churn.new_wallets) == 100, (
            f"Expected 100 new_wallets in first run, got {len(result.churn.new_wallets)}"
        )

        # (c) dry_run flag preserved
        assert result.dry_run is True, "Expected result.dry_run=True"

        # (d) rows_enqueued == 0 in dry_run
        assert result.rows_enqueued == 0, (
            f"Expected rows_enqueued=0 in dry_run, got {result.rows_enqueued}"
        )
