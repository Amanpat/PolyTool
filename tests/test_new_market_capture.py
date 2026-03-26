"""Offline tests for the new-market capture planner and CLI.

All tests are offline — no live network calls.  The Gamma API is mocked at the
``fetch_recent_markets`` import boundary.

Coverage:
  - discover_candidates: age filter (old, young, no-timestamp, no-token-id)
  - rank_candidates: age ascending, volume tiebreak, slug tiebreak
  - dedupe_candidates: deduplication by token_id
  - build_result: sufficient / insufficient / partial
  - plan_new_market_capture: end-to-end with mocked fetch
  - NewMarketCaptureResult.to_targets_manifest / to_insufficiency_report
  - CLI main(): targets written, insufficiency written, dry-run, error paths
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Ensure project root on sys.path
# ---------------------------------------------------------------------------

_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from packages.polymarket.new_market_capture_planner import (
    DEFAULT_RECORD_DURATION_SECONDS,
    DEFAULT_REQUIRED_TARGETS,
    NEW_MARKET_MAX_AGE_HOURS,
    NewMarketCaptureResult,
    NewMarketTarget,
    build_result,
    dedupe_candidates,
    discover_candidates,
    plan_new_market_capture,
    rank_candidates,
)
from tools.cli.new_market_capture import main as cli_main


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_REF_TIME = datetime(2026, 3, 17, 12, 0, 0, tzinfo=timezone.utc)


def _market(
    slug: str,
    age_hours: float,
    *,
    token_id: str | None = None,
    volume_24h: float = 1000.0,
    market_id: str = "99",
    condition_id: str = "0xabc",
    created_at: str | None = None,
) -> dict:
    """Build a minimal fake market dict.

    Pass ``token_id=""`` to simulate a market with an explicitly empty token_id.
    Pass ``token_id=None`` (default) to auto-generate one from the slug.
    """
    if created_at is None:
        dt = _REF_TIME - timedelta(hours=age_hours)
        created_at = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    resolved_token_id = f"token_{slug}" if token_id is None else token_id
    return {
        "slug": slug,
        "token_id": resolved_token_id,
        "market_id": market_id,
        "condition_id": condition_id,
        "volume_24h": volume_24h,
        "created_at": created_at,
    }


def _make_markets(count: int, *, age_hours: float = 10.0) -> list[dict]:
    return [
        _market(f"market-{i}", age_hours, token_id=f"tok{i}", volume_24h=float(1000 - i))
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# discover_candidates
# ---------------------------------------------------------------------------

class TestDiscoverCandidates:
    def test_keeps_young_market(self):
        m = _market("young", age_hours=10.0, token_id="tok1")
        result = discover_candidates([m], reference_time=_REF_TIME)
        assert len(result) == 1
        assert abs(result[0]["age_hours"] - 10.0) < 0.01

    def test_excludes_old_market(self):
        m = _market("old", age_hours=50.0, token_id="tok2")
        result = discover_candidates([m], reference_time=_REF_TIME)
        assert result == []

    def test_excludes_exactly_at_max_age(self):
        m = _market("boundary", age_hours=NEW_MARKET_MAX_AGE_HOURS, token_id="tok3")
        result = discover_candidates([m], reference_time=_REF_TIME)
        assert result == []

    def test_keeps_market_just_under_max_age(self):
        m = _market("just-under", age_hours=NEW_MARKET_MAX_AGE_HOURS - 0.1, token_id="tok4")
        result = discover_candidates([m], reference_time=_REF_TIME)
        assert len(result) == 1

    def test_excludes_no_timestamp(self):
        m = {"slug": "no-ts", "token_id": "tok5", "volume_24h": 500.0}
        result = discover_candidates([m], reference_time=_REF_TIME)
        assert result == []

    def test_excludes_empty_token_id(self):
        m = _market("no-token", age_hours=5.0, token_id="")  # explicitly empty
        result = discover_candidates([m], reference_time=_REF_TIME)
        assert result == []

    def test_excludes_future_dated(self):
        future_dt = _REF_TIME + timedelta(hours=1)
        m = _market("future", age_hours=0, token_id="tok6", created_at=future_dt.strftime("%Y-%m-%dT%H:%M:%SZ"))
        result = discover_candidates([m], reference_time=_REF_TIME)
        assert result == []

    def test_custom_max_age(self):
        m = _market("borderline", age_hours=25.0, token_id="tok7")
        result_48 = discover_candidates([m], reference_time=_REF_TIME, max_age_hours=48.0)
        result_24 = discover_candidates([m], reference_time=_REF_TIME, max_age_hours=24.0)
        assert len(result_48) == 1
        assert result_24 == []

    def test_mixed_batch(self):
        markets = [
            _market("young", age_hours=5.0, token_id="t1"),
            _market("old", age_hours=60.0, token_id="t2"),
            _market("young2", age_hours=10.0, token_id="t3"),
            {"slug": "no-ts", "token_id": "t4"},
        ]
        result = discover_candidates(markets, reference_time=_REF_TIME)
        slugs = {m["slug"] for m in result}
        assert slugs == {"young", "young2"}


# ---------------------------------------------------------------------------
# rank_candidates
# ---------------------------------------------------------------------------

class TestRankCandidates:
    def test_youngest_first(self):
        markets = [
            {**_market("old", 40.0, token_id="t1"), "age_hours": 40.0},
            {**_market("young", 5.0, token_id="t2"), "age_hours": 5.0},
            {**_market("mid", 20.0, token_id="t3"), "age_hours": 20.0},
        ]
        ranked = rank_candidates(markets)
        ages = [m["age_hours"] for m in ranked]
        assert ages == sorted(ages)

    def test_volume_tiebreak(self):
        m1 = {**_market("a", 10.0, token_id="t1", volume_24h=100.0), "age_hours": 10.0}
        m2 = {**_market("b", 10.0, token_id="t2", volume_24h=500.0), "age_hours": 10.0}
        ranked = rank_candidates([m1, m2])
        assert ranked[0]["slug"] == "b"  # higher volume first

    def test_slug_tiebreak_deterministic(self):
        m1 = {**_market("beta", 10.0, token_id="t1", volume_24h=100.0), "age_hours": 10.0}
        m2 = {**_market("alpha", 10.0, token_id="t2", volume_24h=100.0), "age_hours": 10.0}
        ranked = rank_candidates([m1, m2])
        assert ranked[0]["slug"] == "alpha"

    def test_empty_list(self):
        assert rank_candidates([]) == []


# ---------------------------------------------------------------------------
# dedupe_candidates
# ---------------------------------------------------------------------------

class TestDedupeCandidates:
    def test_keeps_first_occurrence(self):
        m1 = {**_market("first", 5.0, token_id="tok-dup"), "age_hours": 5.0}
        m2 = {**_market("second", 8.0, token_id="tok-dup"), "age_hours": 8.0}
        result = dedupe_candidates([m1, m2])
        assert len(result) == 1
        assert result[0]["slug"] == "first"

    def test_different_tokens_both_kept(self):
        m1 = {**_market("a", 5.0, token_id="tok1"), "age_hours": 5.0}
        m2 = {**_market("b", 8.0, token_id="tok2"), "age_hours": 8.0}
        result = dedupe_candidates([m1, m2])
        assert len(result) == 2

    def test_empty_token_id_excluded(self):
        m = {"slug": "no-tok", "token_id": "", "age_hours": 5.0}
        result = dedupe_candidates([m])
        assert result == []


# ---------------------------------------------------------------------------
# build_result
# ---------------------------------------------------------------------------

class TestBuildResult:
    def test_sufficient_result(self):
        candidates = _make_markets(5)
        for c in candidates:
            c["age_hours"] = 5.0
        result = build_result(candidates, required=5, reference_time=_REF_TIME)
        assert not result.insufficient
        assert result.insufficiency_reason is None
        assert len(result.targets) == 5
        assert result.candidates_found == 5

    def test_insufficient_result(self):
        candidates = _make_markets(2)
        for c in candidates:
            c["age_hours"] = 5.0
        result = build_result(candidates, required=5, reference_time=_REF_TIME)
        assert result.insufficient
        assert result.insufficiency_reason is not None
        assert len(result.targets) == 2

    def test_zero_candidates(self):
        result = build_result([], required=5, reference_time=_REF_TIME)
        assert result.insufficient
        assert result.targets == []
        assert result.candidates_found == 0

    def test_priority_assigned_correctly(self):
        candidates = _make_markets(3)
        for i, c in enumerate(candidates):
            c["age_hours"] = float(i + 1)
        result = build_result(candidates, required=5, reference_time=_REF_TIME)
        assert [t.priority for t in result.targets] == [1, 2, 3]

    def test_target_fields_populated(self):
        m = _market("test-slug", 12.5, token_id="tok999", market_id="42", condition_id="0xdef")
        m["age_hours"] = 12.5
        result = build_result([m], required=1, reference_time=_REF_TIME)
        assert len(result.targets) == 1
        t = result.targets[0]
        assert t.bucket == "new_market"
        assert t.slug == "test-slug"
        assert t.token_id == "tok999"
        assert t.market_id == "42"
        assert abs(t.age_hours - 12.5) < 0.01
        assert t.priority == 1
        assert t.record_duration_seconds == DEFAULT_RECORD_DURATION_SECONDS
        assert "age_hours" in t.selection_reason

    def test_record_duration_propagated(self):
        candidates = _make_markets(1)
        candidates[0]["age_hours"] = 5.0
        result = build_result(candidates, required=1, record_duration_seconds=3600, reference_time=_REF_TIME)
        assert result.targets[0].record_duration_seconds == 3600


# ---------------------------------------------------------------------------
# NewMarketCaptureResult serialization
# ---------------------------------------------------------------------------

class TestResultSerialization:
    def _make_sufficient_result(self) -> NewMarketCaptureResult:
        candidates = _make_markets(5)
        for c in candidates:
            c["age_hours"] = 5.0
        return build_result(candidates, required=5, reference_time=_REF_TIME)

    def _make_insufficient_result(self) -> NewMarketCaptureResult:
        candidates = _make_markets(2)
        for c in candidates:
            c["age_hours"] = 5.0
        return build_result(candidates, required=5, reference_time=_REF_TIME)

    def test_targets_manifest_schema(self):
        result = self._make_sufficient_result()
        manifest = result.to_targets_manifest()
        assert manifest["schema_version"] == "benchmark_new_market_capture_v1"
        assert "generated_at" in manifest
        assert isinstance(manifest["targets"], list)
        assert len(manifest["targets"]) == 5

    def test_targets_manifest_entry_keys(self):
        result = self._make_sufficient_result()
        manifest = result.to_targets_manifest()
        entry = manifest["targets"][0]
        required_keys = {
            "bucket", "slug", "market_id", "token_id", "listed_at",
            "age_hours", "priority", "record_duration_seconds", "selection_reason",
        }
        assert required_keys.issubset(entry.keys())
        assert entry["bucket"] == "new_market"

    def test_insufficiency_report_schema(self):
        result = self._make_insufficient_result()
        report = result.to_insufficiency_report()
        assert report["schema_version"] == "new_market_capture_insufficient_v1"
        assert report["bucket"] == "new_market"
        assert report["candidates_found"] == 2
        assert report["required"] == 5
        assert report["shortage"] == 3
        assert "reason" in report

    def test_manifest_roundtrip_json(self):
        result = self._make_sufficient_result()
        manifest = result.to_targets_manifest()
        # Ensure JSON serializable
        as_str = json.dumps(manifest)
        reloaded = json.loads(as_str)
        assert reloaded["schema_version"] == "benchmark_new_market_capture_v1"


# ---------------------------------------------------------------------------
# plan_new_market_capture end-to-end
# ---------------------------------------------------------------------------

class TestPlanNewMarketCapture:
    def _gamma_response(self, count: int, age_hours: float = 10.0) -> list[dict]:
        return _make_markets(count, age_hours=age_hours)

    def test_sufficient_live_fetch(self):
        with patch(
            "packages.polymarket.new_market_capture_planner.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = self._gamma_response(8, age_hours=10.0)
            result = plan_new_market_capture(required=5, reference_time=_REF_TIME)
        assert not result.insufficient
        assert len(result.targets) == 8
        assert result.candidates_found == 8

    def test_insufficient_live_fetch(self):
        with patch(
            "packages.polymarket.new_market_capture_planner.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = self._gamma_response(2, age_hours=10.0)
            result = plan_new_market_capture(required=5, reference_time=_REF_TIME)
        assert result.insufficient
        assert result.candidates_found == 2

    def test_zero_candidates_live_fetch(self):
        with patch(
            "packages.polymarket.new_market_capture_planner.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = []
            result = plan_new_market_capture(required=5, reference_time=_REF_TIME)
        assert result.insufficient
        assert result.candidates_found == 0
        assert result.targets == []

    def test_pre_fetched_markets(self):
        markets = _make_markets(6, age_hours=5.0)
        result = plan_new_market_capture(markets=markets, required=5, reference_time=_REF_TIME)
        assert not result.insufficient
        assert len(result.targets) == 6

    def test_deduplication_applied(self):
        markets = _make_markets(3, age_hours=5.0)
        # Add duplicate token_id
        dup = dict(markets[0])
        dup["slug"] = "dup-slug"
        markets.append(dup)
        result = plan_new_market_capture(markets=markets, required=3, reference_time=_REF_TIME)
        token_ids = [t.token_id for t in result.targets]
        assert len(token_ids) == len(set(token_ids))

    def test_filters_out_old_markets(self):
        old = _make_markets(3, age_hours=72.0)
        young = _make_markets(2, age_hours=10.0)
        for i, m in enumerate(young):
            m["token_id"] = f"young_tok_{i}"
            m["slug"] = f"young-{i}"
        all_markets = old + young
        result = plan_new_market_capture(markets=all_markets, required=5, reference_time=_REF_TIME)
        assert result.candidates_found == 2
        assert result.insufficient


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    def _make_markets_response(self, count: int, age_hours: float = 10.0) -> list[dict]:
        """Generate fake markets with timestamps relative to now so CLI age-filter passes."""
        now = datetime.now(timezone.utc)
        return [
            _market(f"market-{i}", age_hours, token_id=f"tok{i}", volume_24h=float(1000 - i),
                    created_at=(now - timedelta(hours=age_hours)).strftime("%Y-%m-%dT%H:%M:%SZ"))
            for i in range(count)
        ]

    def test_cli_writes_targets_when_sufficient(self, tmp_path):
        out = tmp_path / "targets.json"
        insuff = tmp_path / "insuff.json"
        with patch(
            "tools.cli.new_market_capture.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = self._make_markets_response(6, age_hours=10.0)
            rc = cli_main([
                "--output", str(out),
                "--insufficiency-output", str(insuff),
                "--required", "5",
            ])
        assert rc == 0
        assert out.exists()
        data = json.loads(out.read_text())
        assert data["schema_version"] == "benchmark_new_market_capture_v1"
        assert len(data["targets"]) == 6
        assert not insuff.exists()

    def test_cli_writes_insufficiency_when_zero(self, tmp_path):
        out = tmp_path / "targets.json"
        insuff = tmp_path / "insuff.json"
        with patch(
            "tools.cli.new_market_capture.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = []
            rc = cli_main([
                "--output", str(out),
                "--insufficiency-output", str(insuff),
                "--required", "5",
            ])
        assert rc == 1
        assert not out.exists()
        assert insuff.exists()
        data = json.loads(insuff.read_text())
        assert data["schema_version"] == "new_market_capture_insufficient_v1"
        assert data["candidates_found"] == 0
        assert data["shortage"] == 5

    def test_cli_partial_result(self, tmp_path):
        out = tmp_path / "targets.json"
        insuff = tmp_path / "insuff.json"
        with patch(
            "tools.cli.new_market_capture.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = self._make_markets_response(3, age_hours=10.0)
            rc = cli_main([
                "--output", str(out),
                "--insufficiency-output", str(insuff),
                "--required", "5",
            ])
        assert rc == 2  # partial
        assert out.exists()
        assert insuff.exists()
        data = json.loads(out.read_text())
        assert len(data["targets"]) == 3

    def test_cli_dry_run_no_files(self, tmp_path):
        out = tmp_path / "targets.json"
        insuff = tmp_path / "insuff.json"
        with patch(
            "tools.cli.new_market_capture.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = self._make_markets_response(6, age_hours=10.0)
            rc = cli_main([
                "--output", str(out),
                "--insufficiency-output", str(insuff),
                "--required", "5",
                "--dry-run",
            ])
        assert rc == 0
        assert not out.exists()
        assert not insuff.exists()

    def test_cli_dry_run_insufficient_returns_2(self, tmp_path):
        with patch(
            "tools.cli.new_market_capture.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = self._make_markets_response(2, age_hours=10.0)
            rc = cli_main(["--required", "5", "--dry-run"])
        assert rc == 2

    def test_cli_api_error_returns_1(self, tmp_path):
        with patch(
            "tools.cli.new_market_capture.fetch_recent_markets",
            side_effect=ConnectionError("timeout"),
        ):
            rc = cli_main(["--required", "5"])
        assert rc == 1

    def test_cli_invalid_limit(self, tmp_path):
        rc = cli_main(["--limit", "0"])
        assert rc == 1

    def test_cli_invalid_max_age(self, tmp_path):
        rc = cli_main(["--max-age-hours", "0"])
        assert rc == 1

    def test_cli_target_manifest_entry_structure(self, tmp_path):
        out = tmp_path / "targets.json"
        insuff = tmp_path / "insuff.json"
        with patch(
            "tools.cli.new_market_capture.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = self._make_markets_response(5, age_hours=12.0)
            cli_main([
                "--output", str(out),
                "--insufficiency-output", str(insuff),
                "--required", "5",
            ])
        data = json.loads(out.read_text())
        entry = data["targets"][0]
        assert entry["bucket"] == "new_market"
        assert "slug" in entry
        assert "market_id" in entry
        assert "token_id" in entry
        assert "listed_at" in entry
        assert "age_hours" in entry
        assert "priority" in entry
        assert "record_duration_seconds" in entry
        assert "selection_reason" in entry

    def test_cli_custom_record_duration(self, tmp_path):
        out = tmp_path / "targets.json"
        insuff = tmp_path / "insuff.json"
        with patch(
            "tools.cli.new_market_capture.fetch_recent_markets"
        ) as mock_fetch:
            mock_fetch.return_value = self._make_markets_response(5, age_hours=5.0)
            cli_main([
                "--output", str(out),
                "--insufficiency-output", str(insuff),
                "--required", "5",
                "--record-duration", "3600",
            ])
        data = json.loads(out.read_text())
        assert all(e["record_duration_seconds"] == 3600 for e in data["targets"])
