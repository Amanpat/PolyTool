"""Offline tests for the WI-1 scan queue consumer (ScanWorker).

All tests are offline: the scan callable is mocked, no live API, no ClickHouse.
Covers: lease -> scan -> ingest -> complete; failure -> fail + attempt increment;
expired-lease requeue; idempotency (running twice does not double-scan a leased
row); poison-pill dead-letter ceiling; watchlist lifecycle advance; RMT
latest-state collapse on load_from_clickhouse; and the arg-seam regression
(raw 0x address routes through _default_scan_callable to --user, not --wallet).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from packages.polymarket.discovery.models import QueueState
from packages.polymarket.discovery.scan_queue import ScanQueueManager
from packages.polymarket.discovery.scan_worker import ScanWorker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _manager_with(*wallets: str, source: str = "loop_a") -> ScanQueueManager:
    mgr = ScanQueueManager()
    for w in wallets:
        mgr.enqueue(w, source=source)
    return mgr


def _record_scan():
    """Return (callable, calls-list). The callable records each wallet scanned."""
    calls: list[tuple[str, dict]] = []

    def _scan(wallet: str, flags: dict) -> str:
        calls.append((wallet, flags))
        return f"/tmp/runs/{wallet}"

    return _scan, calls


# ---------------------------------------------------------------------------
# Happy path: lease -> scan -> ingest -> complete
# ---------------------------------------------------------------------------


class TestScanWorkerHappyPath:
    def test_lease_scan_ingest_complete(self):
        mgr = _manager_with("0xAAA")
        scan, calls = _record_scan()
        ingest_calls: list[tuple] = []

        def extractor(run_root: Path, slug: str, wallet: str) -> None:
            ingest_calls.append((run_root, slug, wallet))

        worker = ScanWorker(mgr, scan_callable=scan, post_scan_extractor=extractor)
        result = worker.run(max_items=1)

        assert result.completed == 1
        assert result.failed == 0
        assert calls == [("0xAAA", worker._scan_flags)]
        # Ingest ran exactly once for the scanned wallet
        assert len(ingest_calls) == 1
        assert ingest_calls[0][2] == "0xAAA"
        # Queue row is terminal-done
        assert mgr._items["loop_a:0xAAA"].queue_state == QueueState.done

    def test_watchlist_advancer_called_on_success(self):
        mgr = _manager_with("0xAAA")
        scan, _ = _record_scan()
        advanced: list[str] = []

        worker = ScanWorker(
            mgr,
            scan_callable=scan,
            watchlist_advancer=lambda wallet, run_root: advanced.append(wallet),
        )
        worker.run(max_items=1)

        assert advanced == ["0xAAA"]

    def test_extractor_none_is_scan_only(self):
        mgr = _manager_with("0xAAA")
        scan, calls = _record_scan()
        worker = ScanWorker(mgr, scan_callable=scan)  # no extractor
        result = worker.run(max_items=1)
        assert result.completed == 1
        assert len(calls) == 1


# ---------------------------------------------------------------------------
# Failure path: fail + attempt increment
# ---------------------------------------------------------------------------


class TestScanWorkerFailure:
    def test_scan_exception_marks_failed_and_increments_attempt(self):
        mgr = _manager_with("0xBAD")

        def boom(wallet: str, flags: dict) -> str:
            raise RuntimeError("scan blew up")

        worker = ScanWorker(mgr, scan_callable=boom)
        result = worker.run(max_items=1)

        assert result.failed == 1
        assert result.completed == 0
        item = mgr._items["loop_a:0xBAD"]
        assert item.queue_state == QueueState.failed
        assert item.attempt_count == 1
        assert "scan blew up" in (item.last_error or "")

    def test_ingest_failure_does_not_fail_the_queue_row(self):
        """A non-fatal dossier/ingest error must not flip a good scan to failed."""
        mgr = _manager_with("0xAAA")
        scan, _ = _record_scan()

        def bad_extractor(run_root: Path, slug: str, wallet: str) -> None:
            raise ValueError("ingest exploded")

        worker = ScanWorker(mgr, scan_callable=scan, post_scan_extractor=bad_extractor)
        result = worker.run(max_items=1)

        assert result.completed == 1
        assert result.failed == 0
        assert mgr._items["loop_a:0xAAA"].queue_state == QueueState.done


# ---------------------------------------------------------------------------
# Expired-lease requeue
# ---------------------------------------------------------------------------


class TestScanWorkerRequeue:
    def test_expired_lease_is_requeued_then_processed(self):
        mgr = _manager_with("0xAAA")
        # Simulate a prior worker that leased then died: lease and expire it.
        mgr.lease("loop_a:0xAAA", "dead-worker", lease_duration_seconds=300)
        mgr._items["loop_a:0xAAA"].lease_expires_at = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        )

        scan, calls = _record_scan()
        worker = ScanWorker(mgr, scan_callable=scan)
        result = worker.run(max_items=1)

        assert result.requeued == 1
        assert result.completed == 1
        assert len(calls) == 1
        # attempt_count incremented by the requeue
        assert mgr._items["loop_a:0xAAA"].attempt_count == 1


# ---------------------------------------------------------------------------
# Idempotency: running twice does not double-scan a leased row
# ---------------------------------------------------------------------------


class TestScanWorkerIdempotency:
    def test_running_twice_does_not_double_scan(self):
        mgr = _manager_with("0xAAA")
        scan, calls = _record_scan()
        worker = ScanWorker(mgr, scan_callable=scan)

        worker.run(max_items=1)
        # Second run: the row is already done -> not pending -> not re-leased.
        worker.run(max_items=1)

        assert len(calls) == 1, "wallet was scanned more than once"

    def test_already_leased_row_is_not_double_grabbed(self):
        """A row leased by another owner (still within TTL) is not re-leased."""
        mgr = _manager_with("0xAAA")
        mgr.lease("loop_a:0xAAA", "other-worker", lease_duration_seconds=300)

        scan, calls = _record_scan()
        worker = ScanWorker(mgr, scan_callable=scan)
        result = worker.run(max_items=1)

        # Nothing pending (it's leased and not expired) -> no scan.
        assert len(calls) == 0
        assert result.completed == 0


# ---------------------------------------------------------------------------
# Poison-pill dead-letter ceiling (check #5)
# ---------------------------------------------------------------------------


class TestScanWorkerPoisonPill:
    def test_row_over_ceiling_is_dead_lettered(self):
        mgr = _manager_with("0xBAD")
        item = mgr._items["loop_a:0xBAD"]
        item.attempt_count = 5  # at the default ceiling

        scan, calls = _record_scan()
        worker = ScanWorker(mgr, scan_callable=scan, max_attempts=5)
        result = worker.run(max_items=1)

        assert result.dropped == 1
        assert len(calls) == 0, "a dead-lettered row must not be scanned"
        assert mgr._items["loop_a:0xBAD"].queue_state == QueueState.dropped

    def test_dropped_row_stays_terminal(self):
        mgr = _manager_with("0xBAD")
        mgr._items["loop_a:0xBAD"].attempt_count = 99
        worker = ScanWorker(mgr, scan_callable=lambda w, f: "/tmp/x", max_attempts=5)
        worker.run(max_items=1)
        worker.run(max_items=1)  # second drain
        # Still dropped, never leased/scanned.
        assert mgr._items["loop_a:0xBAD"].queue_state == QueueState.dropped


# ---------------------------------------------------------------------------
# Bounded multi-item drain
# ---------------------------------------------------------------------------


class TestScanWorkerBounded:
    def test_max_items_limits_processing(self):
        mgr = _manager_with("0xA", "0xB", "0xC")
        scan, calls = _record_scan()
        worker = ScanWorker(mgr, scan_callable=scan)
        result = worker.run(max_items=2)
        assert result.completed == 2
        assert len(calls) == 2
        # One still pending
        assert len(mgr.get_pending(limit=10)) == 1


# ---------------------------------------------------------------------------
# RMT latest-state collapse on load_from_clickhouse (check #4)
# ---------------------------------------------------------------------------


class TestRmtCollapse:
    def test_latest_updated_at_version_wins(self, monkeypatch):
        """Two versions of the same dedup_key -> the latest updated_at wins.

        The loader now SELECTs ... FINAL ORDER BY dedup_key, updated_at ASC, so
        the simulated ClickHouse response is returned oldest-first per key and
        the loader's `self._items[dedup_key] = row` keeps the newest.
        """
        import urllib.request

        import packages.polymarket.discovery.scan_queue as sq

        # Older version: pending, attempt 0. Newer version: done, attempt 2.
        # Returned in ASC(updated_at) order, exactly as the new SQL requests.
        ndjson = "\n".join(
            [
                (
                    '{"queue_id":"q1","dedup_key":"loop_a:0xAAA","wallet_address":"0xAAA",'
                    '"source":"loop_a","source_ref":"","priority":3,"queue_state":"pending",'
                    '"available_at":"2026-05-30 10:00:00","leased_at":null,'
                    '"lease_expires_at":null,"lease_owner":null,"attempt_count":0,'
                    '"last_error":null,"created_at":"2026-05-30 10:00:00",'
                    '"updated_at":"2026-05-30 10:00:00"}'
                ),
                (
                    '{"queue_id":"q1","dedup_key":"loop_a:0xAAA","wallet_address":"0xAAA",'
                    '"source":"loop_a","source_ref":"","priority":3,"queue_state":"done",'
                    '"available_at":"2026-05-30 10:00:00","leased_at":null,'
                    '"lease_expires_at":null,"lease_owner":null,"attempt_count":2,'
                    '"last_error":null,"created_at":"2026-05-30 10:00:00",'
                    '"updated_at":"2026-05-31 12:00:00"}'
                ),
            ]
        )

        class _FakeResp:
            def __init__(self, data: str):
                self._data = data.encode("utf-8")

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        captured_url = {}

        def _fake_urlopen(req, timeout=10):
            captured_url["url"] = req.full_url
            return _FakeResp(ndjson)

        monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

        mgr = sq.ScanQueueManager()
        count = mgr.load_from_clickhouse(password="x")

        assert count == 2  # both lines parsed
        row = mgr._items["loop_a:0xAAA"]
        # The NEWER version (done, attempt 2) must win.
        assert row.queue_state == QueueState.done
        assert row.attempt_count == 2
        # The query must use FINAL + order by the real version column.
        assert "FINAL" in captured_url["url"]
        assert "updated_at" in captured_url["url"]


# ---------------------------------------------------------------------------
# Arg-seam regression: raw 0x address routes through --user (not --wallet)
# ---------------------------------------------------------------------------


class TestArgSeamRegression:
    def test_raw_address_builds_user_argv(self, monkeypatch):
        """_default_scan_callable must build ['--user', '0x...'] for raw addresses.

        scan.py defines only --user; passing --wallet raised an argparse error
        and broke the discovery->scan handoff. We assert the argv shape and
        mock all scan internals so no network call happens.
        """
        from tools.cli import wallet_scan
        from tools.cli import scan as scan_cli

        seen_argv = {}

        # Capture argv as parsed by the real scan parser (proves --user is valid).
        real_parse = scan_cli.build_parser

        def fake_run_scan(*, config, argv, started_at):
            seen_argv["argv"] = list(argv)
            return {"run_root": "/tmp/runs/0xfeed"}

        monkeypatch.setattr(scan_cli, "run_scan", fake_run_scan)
        monkeypatch.setattr(scan_cli, "apply_scan_defaults", lambda a, argv: a)
        monkeypatch.setattr(scan_cli, "build_config", lambda a: {"_": True})
        monkeypatch.setattr(scan_cli, "validate_config", lambda c: None)

        raw_addr = "0x" + "1" * 40
        run_root = wallet_scan._default_scan_callable(raw_addr, {"lite": True})

        assert run_root == "/tmp/runs/0xfeed"
        assert "--user" in seen_argv["argv"]
        assert raw_addr in seen_argv["argv"]
        # The broken flag must NOT be used.
        assert "--wallet" not in seen_argv["argv"]
        # The real scan parser accepts the argv we built (no argparse error).
        parsed = real_parse().parse_args(seen_argv["argv"])
        assert parsed.user == raw_addr
