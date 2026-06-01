"""Offline unit tests for WI-3 discovery + rescan scheduler.

All tests are offline / deterministic: no live scheduler runtime, no live API,
no ClickHouse. APScheduler is not required (injectable _scheduler_factory).
"""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fake scheduler (mirrors the RIS test fake)
# ---------------------------------------------------------------------------


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: list[dict] = []
        self.started = False
        self.stopped = False

    def add_job(self, fn: Any, trigger: Any, *, id: str, name: str) -> None:
        self.jobs.append({"id": id, "name": name, "fn": fn, "trigger": trigger})

    def start(self) -> None:
        self.started = True

    def shutdown(self) -> None:
        self.stopped = True


def _now() -> datetime:
    return datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# DISCOVERY_JOB_REGISTRY shape (gate 1 — reuse RIS pattern, parallel registry)
# ---------------------------------------------------------------------------


class TestDiscoveryJobRegistry:
    def test_has_three_jobs(self) -> None:
        from packages.research.scheduling.discovery_scheduler import DISCOVERY_JOB_REGISTRY

        assert len(DISCOVERY_JOB_REGISTRY) == 3

    def test_expected_ids(self) -> None:
        from packages.research.scheduling.discovery_scheduler import DISCOVERY_JOB_REGISTRY

        ids = {j["id"] for j in DISCOVERY_JOB_REGISTRY}
        assert ids == {"discovery_loop_a", "watchlist_rescan", "queue_drain"}

    def test_registry_shape_matches_ris(self) -> None:
        """Same dict keys as the RIS JOB_REGISTRY entries (reuse, don't reinvent)."""
        from packages.research.scheduling.discovery_scheduler import DISCOVERY_JOB_REGISTRY

        required = {"id", "name", "trigger_description", "callable_name"}
        for job in DISCOVERY_JOB_REGISTRY:
            assert required <= set(job.keys())

    def test_importable_without_apscheduler(self) -> None:
        import packages.research.scheduling.discovery_scheduler as mod

        assert hasattr(mod, "DISCOVERY_JOB_REGISTRY")


# ---------------------------------------------------------------------------
# Gate 2 — no RIS regression: RIS registry untouched
# ---------------------------------------------------------------------------


class TestNoRisRegression:
    def test_ris_registry_still_8(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY

        assert len(JOB_REGISTRY) == 8

    def test_discovery_ids_not_in_ris_registry(self) -> None:
        from packages.research.scheduling.scheduler import JOB_REGISTRY
        from packages.research.scheduling.discovery_scheduler import DISCOVERY_JOB_REGISTRY

        ris_ids = {j["id"] for j in JOB_REGISTRY}
        disc_ids = {j["id"] for j in DISCOVERY_JOB_REGISTRY}
        assert ris_ids.isdisjoint(disc_ids)


# ---------------------------------------------------------------------------
# Tier resolution — forward-compatible fallback (pre-WI-4)
# ---------------------------------------------------------------------------


class TestTierResolution:
    def test_fallback_no_tier_columns_promoted_is_locked(self) -> None:
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        assert resolve_tier({"lifecycle_state": "promoted", "source": "loop_a"}) == "locked"
        assert resolve_tier({"lifecycle_state": "watched"}) == "locked"

    def test_fallback_reviewed_or_manual_is_candidate(self) -> None:
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        assert resolve_tier({"lifecycle_state": "reviewed"}) == "candidate"
        assert resolve_tier({"lifecycle_state": "scanned", "source": "manual"}) == "candidate"
        assert resolve_tier({"review_status": "approved", "lifecycle_state": "queued"}) == "candidate"

    def test_fallback_discovered_states(self) -> None:
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        for state in ("discovered", "queued", "scanned", "stale"):
            assert resolve_tier({"lifecycle_state": state, "source": "loop_a"}) == "discovered"

    def test_fallback_unknown_is_rest(self) -> None:
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        assert resolve_tier({}) == "rest"
        assert resolve_tier({"lifecycle_state": "retired"}) == "rest"

    def test_fallback_does_not_error_without_tier_columns(self) -> None:
        """The packet's key constraint: no tier/locked columns present -> no error."""
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        # A row exactly as today's watchlist DDL produces (no tier/locked cols).
        row = {
            "wallet_address": "0xabc",
            "lifecycle_state": "discovered",
            "review_status": "pending",
            "source": "loop_a",
        }
        assert resolve_tier(row) == "discovered"  # no KeyError, no AttributeError

    def test_wi4_locked_column_wins(self) -> None:
        """Once WI-4 adds a 'locked' column, it overrides the fallback."""
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        # lifecycle says discovered, but WI-4 locked=1 -> locked
        assert resolve_tier({"lifecycle_state": "discovered", "locked": 1}) == "locked"
        assert resolve_tier({"lifecycle_state": "discovered", "locked": "true"}) == "locked"

    def test_wi4_tier_column_wins(self) -> None:
        from packages.research.scheduling.discovery_scheduler import resolve_tier

        assert resolve_tier({"lifecycle_state": "discovered", "tier": "candidate"}) == "candidate"


# ---------------------------------------------------------------------------
# Skip-if-recent
# ---------------------------------------------------------------------------


class TestSkipIfRecent:
    def test_never_scanned_is_not_recent(self) -> None:
        from packages.research.scheduling.discovery_scheduler import is_recently_scanned

        assert is_recently_scanned(None, "locked", now=_now()) is False

    def test_within_window_is_recent(self) -> None:
        from packages.research.scheduling.discovery_scheduler import is_recently_scanned

        # locked window default = 6h; scanned 2h ago -> recent -> skip
        last = _now() - timedelta(hours=2)
        assert is_recently_scanned(last, "locked", now=_now()) is True

    def test_outside_window_is_not_recent(self) -> None:
        from packages.research.scheduling.discovery_scheduler import is_recently_scanned

        # locked window = 6h; scanned 8h ago -> not recent -> enqueue
        last = _now() - timedelta(hours=8)
        assert is_recently_scanned(last, "locked", now=_now()) is False

    def test_discovered_long_window(self) -> None:
        from packages.research.scheduling.discovery_scheduler import is_recently_scanned

        # discovered default window = 336h (14d); scanned 10 days ago -> still recent
        last = _now() - timedelta(days=10)
        assert is_recently_scanned(last, "discovered", now=_now()) is True
        last = _now() - timedelta(days=20)
        assert is_recently_scanned(last, "discovered", now=_now()) is False


# ---------------------------------------------------------------------------
# Rescan planning: skip-if-recent + priority ordering combined
# ---------------------------------------------------------------------------


class TestPlanRescanEnqueues:
    def _config(self) -> dict:
        from packages.research.scheduling.discovery_scheduler import load_config

        return load_config()  # uses repo config/defaults

    def test_recent_wallet_not_enqueued(self) -> None:
        from packages.research.scheduling.discovery_scheduler import plan_rescan_enqueues

        rows = [
            # locked, scanned 1h ago -> within 6h window -> SKIP
            {
                "wallet_address": "0xfresh",
                "lifecycle_state": "promoted",
                "last_scanned_at": (_now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            },
        ]
        plans = plan_rescan_enqueues(rows, self._config(), now=_now())
        assert plans == []

    def test_stale_wallet_is_enqueued(self) -> None:
        from packages.research.scheduling.discovery_scheduler import plan_rescan_enqueues

        rows = [
            # locked, scanned 10h ago -> outside 6h window -> ENQUEUE
            {
                "wallet_address": "0xstale",
                "lifecycle_state": "promoted",
                "last_scanned_at": (_now() - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S"),
            },
        ]
        plans = plan_rescan_enqueues(rows, self._config(), now=_now())
        assert len(plans) == 1
        assert plans[0]["wallet_address"] == "0xstale"
        assert plans[0]["tier"] == "locked"

    def test_never_scanned_is_enqueued(self) -> None:
        from packages.research.scheduling.discovery_scheduler import plan_rescan_enqueues

        rows = [
            {"wallet_address": "0xnew", "lifecycle_state": "discovered", "last_scanned_at": None},
        ]
        plans = plan_rescan_enqueues(rows, self._config(), now=_now())
        assert len(plans) == 1
        assert plans[0]["wallet_address"] == "0xnew"

    def test_priority_ordering_locked_candidate_discovered_rest(self) -> None:
        """Drain order proxy: enqueued wallets carry tier-correct priority and
        the plan is sorted locked(1) -> candidate(2) -> discovered(3) -> rest(4)."""
        from packages.research.scheduling.discovery_scheduler import plan_rescan_enqueues

        old = (_now() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            {"wallet_address": "0xrest", "lifecycle_state": "retired", "last_scanned_at": old},
            {"wallet_address": "0xdiscovered", "lifecycle_state": "discovered", "last_scanned_at": old},
            {"wallet_address": "0xlocked", "lifecycle_state": "promoted", "last_scanned_at": old},
            {"wallet_address": "0xcandidate", "lifecycle_state": "reviewed", "last_scanned_at": old},
        ]
        # Note: retired is filtered at the SQL layer in prod; here it resolves to
        # 'rest' priority and proves the ordering still sorts rest last.
        plans = plan_rescan_enqueues(rows, self._config(), now=_now())
        order = [p["wallet_address"] for p in plans]
        prio = [p["priority"] for p in plans]
        assert order == ["0xlocked", "0xcandidate", "0xdiscovered", "0xrest"]
        assert prio == [1, 2, 3, 4]

    def test_max_enqueue_cap_keeps_highest_priority(self) -> None:
        from packages.research.scheduling.discovery_scheduler import plan_rescan_enqueues

        old = (_now() - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            {"wallet_address": "0xa", "lifecycle_state": "discovered", "last_scanned_at": old},
            {"wallet_address": "0xb", "lifecycle_state": "promoted", "last_scanned_at": old},
        ]
        cfg = self._config()
        cfg["rescan"] = dict(cfg["rescan"])
        cfg["rescan"]["max_enqueue"] = 1
        plans = plan_rescan_enqueues(rows, cfg, now=_now())
        assert len(plans) == 1
        assert plans[0]["wallet_address"] == "0xb"  # locked beats discovered


# ---------------------------------------------------------------------------
# tier_to_priority mapping
# ---------------------------------------------------------------------------


class TestTierToPriority:
    def test_default_mapping(self) -> None:
        from packages.research.scheduling.discovery_scheduler import tier_to_priority

        assert tier_to_priority("locked") == 1
        assert tier_to_priority("candidate") == 2
        assert tier_to_priority("discovered") == 3
        assert tier_to_priority("rest") == 4
        assert tier_to_priority("unknown_tier") == 4  # falls to rest


# ---------------------------------------------------------------------------
# Config loading (defensive)
# ---------------------------------------------------------------------------


class TestConfigLoading:
    def test_missing_file_uses_defaults(self, tmp_path) -> None:
        from packages.research.scheduling.discovery_scheduler import load_config

        cfg = load_config(tmp_path / "does_not_exist.json")
        assert cfg["skip_if_recent"]["locked_hours"] == 6
        assert cfg["tier_priority"]["locked"] == 1

    def test_partial_config_merges_defaults(self, tmp_path) -> None:
        from packages.research.scheduling.discovery_scheduler import load_config

        p = tmp_path / "cfg.json"
        p.write_text(json.dumps({"skip_if_recent": {"locked_hours": 99}}), encoding="utf-8")
        cfg = load_config(p)
        assert cfg["skip_if_recent"]["locked_hours"] == 99  # override
        assert cfg["skip_if_recent"]["candidate_hours"] == 24  # default preserved
        assert cfg["tier_priority"]["locked"] == 1  # whole section defaulted

    def test_repo_config_loads(self) -> None:
        from packages.research.scheduling.discovery_scheduler import load_config

        cfg = load_config()  # actual config/discovery_scheduler.json
        assert "cadences" in cfg
        assert set(cfg["cadences"]) >= {"discovery_loop_a", "watchlist_rescan", "queue_drain"}


# ---------------------------------------------------------------------------
# start_discovery_scheduler (injectable; no APScheduler needed) — gate 1
# ---------------------------------------------------------------------------


class TestStartDiscoveryScheduler:
    def test_returns_started_fake(self) -> None:
        from packages.research.scheduling.discovery_scheduler import start_discovery_scheduler

        fake = _FakeScheduler()
        result = start_discovery_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: None,
        )
        assert result is fake
        assert fake.started

    def test_three_jobs_registered(self) -> None:
        from packages.research.scheduling.discovery_scheduler import (
            DISCOVERY_JOB_REGISTRY,
            start_discovery_scheduler,
        )

        fake = _FakeScheduler()
        start_discovery_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: None,
        )
        registered = {j["id"] for j in fake.jobs}
        assert registered == {j["id"] for j in DISCOVERY_JOB_REGISTRY}

    def test_exclude_job(self) -> None:
        from packages.research.scheduling.discovery_scheduler import start_discovery_scheduler

        fake = _FakeScheduler()
        start_discovery_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: None,
            exclude_job_ids=["queue_drain"],
        )
        ids = {j["id"] for j in fake.jobs}
        assert "queue_drain" not in ids
        assert len(ids) == 2

    def test_job_runner_receives_job_id(self) -> None:
        from packages.research.scheduling.discovery_scheduler import start_discovery_scheduler

        calls: list[str] = []
        fake = _FakeScheduler()
        start_discovery_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: calls.append(job_id),
        )
        for job in fake.jobs:
            job["fn"]()
        assert set(calls) == {"discovery_loop_a", "watchlist_rescan", "queue_drain"}

    def test_no_jobs_fire_at_start(self) -> None:
        from packages.research.scheduling.discovery_scheduler import start_discovery_scheduler

        calls: list[str] = []
        fake = _FakeScheduler()
        start_discovery_scheduler(
            _scheduler_factory=lambda: fake,
            _job_runner=lambda job_id: calls.append(job_id),
        )
        assert calls == []


# ---------------------------------------------------------------------------
# run_discovery_job
# ---------------------------------------------------------------------------


class TestRunDiscoveryJob:
    def test_unknown_id_returns_1(self) -> None:
        from packages.research.scheduling.discovery_scheduler import run_discovery_job

        assert run_discovery_job("nope") == 1

    def test_known_id_runs_callable(self, monkeypatch) -> None:
        from packages.research.scheduling import discovery_scheduler as mod

        called = []
        monkeypatch.setitem(
            mod._JOB_FN_MAP, "_job_run_queue_drain", lambda: called.append("drain")
        )
        assert mod.run_discovery_job("queue_drain") == 0
        assert called == ["drain"]

    def test_callable_exception_returns_1(self, monkeypatch) -> None:
        from packages.research.scheduling import discovery_scheduler as mod

        def _boom() -> None:
            raise RuntimeError("boom")

        monkeypatch.setitem(mod._JOB_FN_MAP, "_job_run_queue_drain", _boom)
        assert mod.run_discovery_job("queue_drain") == 1

    def test_missing_password_fails_fast(self, monkeypatch) -> None:
        """Job callables require CLICKHOUSE_PASSWORD (CLAUDE.md fail-fast rule)."""
        from packages.research.scheduling import discovery_scheduler as mod

        monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
        # queue_drain calls _ch_password() early -> RuntimeError -> run returns 1
        assert mod.run_discovery_job("queue_drain") == 1


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


class TestCli:
    def test_scheduler_status(self) -> None:
        from tools.cli.discovery import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["scheduler", "status"])
        assert rc == 0
        out = buf.getvalue()
        assert "discovery_loop_a" in out
        assert "queue_drain" in out

    def test_scheduler_status_json(self) -> None:
        from tools.cli.discovery import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["scheduler", "status", "--json"])
        assert rc == 0
        data = json.loads(buf.getvalue())
        assert isinstance(data, list)
        assert len(data) == 3

    def test_scheduler_start_dry_run(self) -> None:
        from tools.cli.discovery import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["scheduler", "start", "--dry-run"])
        assert rc == 0
        assert "Dry-run" in buf.getvalue()

    def test_scheduler_run_job_unknown(self) -> None:
        from tools.cli.discovery import main

        rc = main(["scheduler", "run-job", "bogus", "--json"])
        assert rc == 1
