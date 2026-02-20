from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.cli.batch_run import (
    BatchRunner,
    _build_markdown,
    _resolve_run_roots,
    aggregate_only,
)


FIXED_NOW = datetime(2026, 2, 20, 18, 0, 0, tzinfo=timezone.utc)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_users_file(path: Path, users: list[str]) -> Path:
    path.write_text("\n".join(users) + "\n", encoding="utf-8")
    return path


def _candidate(
    segment_key: str,
    *,
    rank: int,
    weighting: str,
    metric_value: float,
    beat_close_value: float,
    count: int,
    count_used: int,
    weight_used: float,
) -> dict:
    is_notional = weighting == "notional"
    return {
        "segment_key": segment_key,
        "rank": rank,
        "metrics": {
            "count": count,
            "avg_clv_pct": metric_value,
            "avg_clv_pct_count_used": count_used,
            "beat_close_rate": beat_close_value,
            "beat_close_rate_count_used": count_used,
            "notional_weighted_avg_clv_pct": metric_value if is_notional else None,
            "notional_weighted_avg_clv_pct_weight_used": weight_used if is_notional else 0.0,
            "notional_weighted_beat_close_rate": beat_close_value if is_notional else None,
            "notional_weighted_beat_close_rate_weight_used": weight_used if is_notional else 0.0,
        },
        "denominators": {
            "count_used": count_used,
            "weight_used": weight_used if is_notional else 0.0,
            "weighting": weighting,
        },
        "falsification_plan": {
            "min_sample_size": 30,
            "min_coverage_rate": 0.8,
            "stop_conditions": [],
        },
    }


def _make_run_root(
    tmp_path: Path,
    run_name: str,
    candidates: list[dict],
    *,
    clv_coverage_rate: float = 1.0,
    entry_coverage_rate: float = 1.0,
    notional_weight_total_global: float = 100.0,
) -> Path:
    run_root = tmp_path / run_name
    run_root.mkdir(parents=True, exist_ok=True)

    eligible = 20
    present = int(round(eligible * entry_coverage_rate))

    _write_json(
        run_root / "hypothesis_candidates.json",
        {
            "generated_at": "2026-02-20T00:00:00+00:00",
            "run_id": run_name,
            "user_slug": run_name,
            "wallet": "0xabc",
            "candidates": candidates,
        },
    )
    _write_json(
        run_root / "coverage_reconciliation_report.json",
        {
            "generated_at": "2026-02-20T00:00:00+00:00",
            "clv_coverage": {
                "coverage_rate": clv_coverage_rate,
                "eligible_positions": eligible,
                "clv_present_count": int(round(eligible * clv_coverage_rate)),
                "clv_missing_count": eligible - int(round(eligible * clv_coverage_rate)),
                "missing_reason_counts": {},
            },
            "entry_context_coverage": {
                "eligible_positions": eligible,
                "price_at_entry_present_count": present,
                "price_1h_before_entry_present_count": present,
                "open_price_present_count": present,
                "movement_direction_present_count": present,
                "minutes_to_close_present_count": present,
                "missing_reason_counts": {},
            },
            "segment_analysis": {
                "hypothesis_meta": {
                    "notional_weight_total_global": notional_weight_total_global,
                }
            },
        },
    )
    _write_json(
        run_root / "segment_analysis.json",
        {
            "generated_at": "2026-02-20T00:00:00+00:00",
            "run_id": run_name,
            "user_slug": run_name,
            "wallet": "0xabc",
            "segment_analysis": {
                "hypothesis_meta": {
                    "notional_weight_total_global": notional_weight_total_global,
                }
            },
        },
    )
    return run_root


def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_aggregation_determinism_stable_tie_breaker(tmp_path):
    users = ["@u1", "@u2"]
    users_file = _write_users_file(tmp_path / "users.txt", users)

    run_roots = {
        "@u1": _make_run_root(
            tmp_path,
            "run-u1",
            [
                _candidate(
                    "sport:beta",
                    rank=1,
                    weighting="notional",
                    metric_value=0.5,
                    beat_close_value=0.5,
                    count=10,
                    count_used=10,
                    weight_used=100.0,
                )
            ],
        ),
        "@u2": _make_run_root(
            tmp_path,
            "run-u2",
            [
                _candidate(
                    "sport:alpha",
                    rank=1,
                    weighting="notional",
                    metric_value=0.5,
                    beat_close_value=0.5,
                    count=10,
                    count_used=10,
                    weight_used=100.0,
                )
            ],
        ),
    }

    def fake_scan(user: str, _flags: dict) -> str:
        return run_roots[user].as_posix()

    runner = BatchRunner(scan_callable=fake_scan, now_provider=lambda: FIXED_NOW)
    out_a = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-a",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
    )
    out_b = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-b",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
    )

    leaderboard_a = _load_json(out_a["hypothesis_leaderboard_json"])
    leaderboard_b = _load_json(out_b["hypothesis_leaderboard_json"])

    assert leaderboard_a["top_lists"] == leaderboard_b["top_lists"]
    assert (
        leaderboard_a["top_lists"]["top_by_notional_weighted_avg_clv_pct"][:2]
        == ["sport:alpha", "sport:beta"]
    )
    assert [row["segment_key"] for row in leaderboard_a["segments"]] == [
        row["segment_key"] for row in leaderboard_b["segments"]
    ]


def test_weighted_combine_math_uses_weight_used(tmp_path):
    users = ["@u1", "@u2"]
    users_file = _write_users_file(tmp_path / "users.txt", users)

    run_roots = {
        "@u1": _make_run_root(
            tmp_path,
            "run-u1",
            [
                _candidate(
                    "sport:soccer",
                    rank=1,
                    weighting="notional",
                    metric_value=0.1,
                    beat_close_value=0.4,
                    count=10,
                    count_used=10,
                    weight_used=100.0,
                )
            ],
        ),
        "@u2": _make_run_root(
            tmp_path,
            "run-u2",
            [
                _candidate(
                    "sport:soccer",
                    rank=1,
                    weighting="notional",
                    metric_value=0.3,
                    beat_close_value=0.6,
                    count=20,
                    count_used=20,
                    weight_used=300.0,
                )
            ],
        ),
    }

    def fake_scan(user: str, _flags: dict) -> str:
        return run_roots[user].as_posix()

    runner = BatchRunner(scan_callable=fake_scan, now_provider=lambda: FIXED_NOW)
    output_paths = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-weighted",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
    )

    leaderboard = _load_json(output_paths["hypothesis_leaderboard_json"])
    segment = next(row for row in leaderboard["segments"] if row["segment_key"] == "sport:soccer")

    assert segment["scores"]["notional_weighted_avg_clv_pct"]["value"] == pytest.approx(0.25)
    assert segment["scores"]["notional_weighted_avg_clv_pct"]["weight_used"] == pytest.approx(400.0)
    assert segment["scores"]["notional_weighted_beat_close_rate"]["value"] == pytest.approx(0.55)
    assert segment["scores"]["notional_weighted_beat_close_rate"]["users_used"] == 2


def test_count_weighted_fallback_when_no_notional_contributors(tmp_path):
    users = ["@u1", "@u2"]
    users_file = _write_users_file(tmp_path / "users.txt", users)

    run_roots = {
        "@u1": _make_run_root(
            tmp_path,
            "run-u1",
            [
                _candidate(
                    "market_type:moneyline",
                    rank=1,
                    weighting="count",
                    metric_value=0.2,
                    beat_close_value=0.5,
                    count=5,
                    count_used=5,
                    weight_used=0.0,
                )
            ],
        ),
        "@u2": _make_run_root(
            tmp_path,
            "run-u2",
            [
                _candidate(
                    "market_type:moneyline",
                    rank=1,
                    weighting="count",
                    metric_value=0.4,
                    beat_close_value=0.7,
                    count=15,
                    count_used=15,
                    weight_used=0.0,
                )
            ],
        ),
    }

    def fake_scan(user: str, _flags: dict) -> str:
        return run_roots[user].as_posix()

    runner = BatchRunner(scan_callable=fake_scan, now_provider=lambda: FIXED_NOW)
    output_paths = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-count-fallback",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
    )

    leaderboard = _load_json(output_paths["hypothesis_leaderboard_json"])
    segment = next(row for row in leaderboard["segments"] if row["segment_key"] == "market_type:moneyline")

    assert segment["scores"]["notional_weighted_avg_clv_pct"]["value"] is None
    assert segment["scores"]["count_weighted_avg_clv_pct"]["value"] == pytest.approx(0.35)
    assert segment["scores"]["count_weighted_avg_clv_pct"]["count_used"] == pytest.approx(20.0)


def test_continue_on_error_marks_failure_and_still_writes_outputs(tmp_path):
    users = ["@ok", "@bad"]
    users_file = _write_users_file(tmp_path / "users.txt", users)

    run_root_ok = _make_run_root(
        tmp_path,
        "run-ok",
        [
            _candidate(
                "sport:nba",
                rank=1,
                weighting="notional",
                metric_value=0.12,
                beat_close_value=0.6,
                count=12,
                count_used=12,
                weight_used=120.0,
            )
        ],
    )

    def fake_scan(user: str, _flags: dict) -> str:
        if user == "@bad":
            raise RuntimeError("boom")
        return run_root_ok.as_posix()

    runner = BatchRunner(scan_callable=fake_scan, now_provider=lambda: FIXED_NOW)
    output_paths = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-continue",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
    )

    assert Path(output_paths["hypothesis_leaderboard_json"]).exists()
    assert Path(output_paths["hypothesis_leaderboard_md"]).exists()
    assert Path(output_paths["batch_manifest_json"]).exists()

    leaderboard = _load_json(output_paths["hypothesis_leaderboard_json"])
    assert leaderboard["users_attempted"] == 2
    assert leaderboard["users_succeeded"] == 1
    assert leaderboard["users_failed"] == 1

    bad_row = next(row for row in leaderboard["per_user"] if row["user"] == "@bad")
    assert bad_row["status"] == "failure"
    assert "RuntimeError" in bad_row["error"]


def test_batch_manifest_exists_and_lists_outputs(tmp_path):
    users = ["@u1"]
    users_file = _write_users_file(tmp_path / "users.txt", users)
    run_root = _make_run_root(
        tmp_path,
        "run-u1",
        [
            _candidate(
                "category:Unknown",
                rank=1,
                weighting="notional",
                metric_value=0.22,
                beat_close_value=0.65,
                count=9,
                count_used=9,
                weight_used=90.0,
            )
        ],
    )

    def fake_scan(user: str, _flags: dict) -> str:
        return run_root.as_posix()

    runner = BatchRunner(scan_callable=fake_scan, now_provider=lambda: FIXED_NOW)
    output_paths = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-manifest",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
    )

    manifest = _load_json(output_paths["batch_manifest_json"])
    output_map = manifest["output_paths"]
    assert output_map["hypothesis_leaderboard_json"] == output_paths["hypothesis_leaderboard_json"]
    assert output_map["hypothesis_leaderboard_md"] == output_paths["hypothesis_leaderboard_md"]
    assert output_map["per_user_results_json"] == output_paths["per_user_results_json"]
    assert manifest["per_user_run_roots"] == [
        {"user": "@u1", "status": "success", "run_root": run_root.as_posix()}
    ]


def test_build_markdown_includes_robust_clv_stats():
    example_metrics = {
        "count": 10,
        "avg_clv_pct": 0.05,
        "avg_clv_pct_count_used": 10,
        "notional_weighted_avg_clv_pct": 0.06,
        "notional_weighted_avg_clv_pct_weight_used": 500.0,
        "notional_weighted_beat_close_rate": 0.6,
        "notional_weighted_beat_close_rate_weight_used": 500.0,
        "beat_close_rate": 0.6,
        "beat_close_rate_count_used": 10,
        "median_clv_pct": 0.04,
        "trimmed_mean_clv_pct": 0.045,
        "robust_clv_pct_count_used": 10,
    }
    leaderboard = {
        "batch_id": "test-batch",
        "created_at": "2026-02-20T18:00:00+00:00",
        "users_attempted": 1,
        "users_succeeded": 1,
        "users_failed": 0,
        "segments": [
            {
                "segment_key": "sport:basketball",
                "users_with_segment": 1,
                "total_count": 10,
                "total_notional_weight_used": 500.0,
                "scores": {
                    "notional_weighted_avg_clv_pct": {"value": 0.06, "users_used": 1, "weight_used": 500.0},
                    "notional_weighted_beat_close_rate": {"value": 0.6, "users_used": 1, "weight_used": 500.0},
                    "count_weighted_avg_clv_pct": {"value": 0.05, "users_used": 1, "count_used": 10},
                    "count_weighted_beat_close_rate": {"value": 0.6, "users_used": 1, "count_used": 10},
                },
                "examples": [
                    {
                        "user": "alice",
                        "rank": 1,
                        "weighting": "notional",
                        "metrics": example_metrics,
                        "denominators": {"weight_used": 500.0, "weighting": "notional"},
                    }
                ],
            }
        ],
        "top_lists": {
            "top_by_notional_weighted_avg_clv_pct": ["sport:basketball"],
            "top_by_notional_weighted_beat_close_rate": [],
            "top_by_persistence_users": [],
        },
        "per_user": [],
    }
    md = _build_markdown(leaderboard)
    assert "median_clv_pct" in md
    assert "trimmed_mean_clv_pct" in md
    assert "0.040000" in md  # median value formatted


# ---------------------------------------------------------------------------
# New tests: aggregate-only mode
# ---------------------------------------------------------------------------


def test_aggregate_only_from_run_roots(tmp_path):
    """aggregate_only() builds a leaderboard from two existing run roots (no scans)."""
    run_root_u1 = _make_run_root(
        tmp_path,
        "run-u1",
        [
            _candidate(
                "sport:tennis",
                rank=1,
                weighting="notional",
                metric_value=0.15,
                beat_close_value=0.6,
                count=10,
                count_used=10,
                weight_used=100.0,
            )
        ],
    )
    run_root_u2 = _make_run_root(
        tmp_path,
        "run-u2",
        [
            _candidate(
                "sport:cricket",
                rank=1,
                weighting="notional",
                metric_value=0.20,
                beat_close_value=0.65,
                count=12,
                count_used=12,
                weight_used=120.0,
            )
        ],
    )

    output_paths = aggregate_only(
        run_roots=[run_root_u1, run_root_u2],
        output_root=tmp_path / "out",
        batch_id="batch-agg",
        now_provider=lambda: FIXED_NOW,
    )

    assert Path(output_paths["hypothesis_leaderboard_json"]).exists()
    assert Path(output_paths["batch_manifest_json"]).exists()

    leaderboard = _load_json(output_paths["hypothesis_leaderboard_json"])
    assert leaderboard["users_attempted"] == 2
    assert leaderboard["users_succeeded"] == 2

    segment_keys = {row["segment_key"] for row in leaderboard["segments"]}
    assert "sport:tennis" in segment_keys
    assert "sport:cricket" in segment_keys


def test_aggregate_only_directory_input(tmp_path):
    """_resolve_run_roots() returns all immediate subdirs of a directory."""
    roots_dir = tmp_path / "roots"
    roots_dir.mkdir()

    # Create two subdirectories (simulate run roots).
    (roots_dir / "run-a").mkdir()
    (roots_dir / "run-b").mkdir()
    # A plain file inside should be ignored.
    (roots_dir / "not_a_dir.txt").write_text("ignore me", encoding="utf-8")

    resolved = _resolve_run_roots(roots_dir)
    assert len(resolved) == 2
    assert all(p.is_dir() for p in resolved)
    resolved_names = {p.name for p in resolved}
    assert resolved_names == {"run-a", "run-b"}


def test_aggregate_only_file_input(tmp_path):
    """_resolve_run_roots() reads paths from a text file (one per line)."""
    run_a = tmp_path / "run-a"
    run_b = tmp_path / "run-b"
    run_a.mkdir()
    run_b.mkdir()

    roots_file = tmp_path / "roots.txt"
    roots_file.write_text(
        f"# comment\n{run_a.as_posix()}\n\n{run_b.as_posix()}\n",
        encoding="utf-8",
    )

    resolved = _resolve_run_roots(roots_file)
    assert len(resolved) == 2
    resolved_paths = {p.resolve() for p in resolved}
    assert run_a.resolve() in resolved_paths
    assert run_b.resolve() in resolved_paths


# ---------------------------------------------------------------------------
# New tests: --workers parallel scans
# ---------------------------------------------------------------------------


def test_workers_ordering_matches_serial(tmp_path):
    """Per-user result order from workers=3 is identical to workers=1 (serial)."""
    users = ["@u1", "@u2", "@u3"]
    users_file = _write_users_file(tmp_path / "users.txt", users)

    run_roots = {
        "@u1": _make_run_root(
            tmp_path,
            "run-u1",
            [
                _candidate(
                    "sport:football",
                    rank=1,
                    weighting="notional",
                    metric_value=0.10,
                    beat_close_value=0.55,
                    count=10,
                    count_used=10,
                    weight_used=100.0,
                )
            ],
        ),
        "@u2": _make_run_root(
            tmp_path,
            "run-u2",
            [
                _candidate(
                    "sport:baseball",
                    rank=1,
                    weighting="notional",
                    metric_value=0.20,
                    beat_close_value=0.60,
                    count=15,
                    count_used=15,
                    weight_used=150.0,
                )
            ],
        ),
        "@u3": _make_run_root(
            tmp_path,
            "run-u3",
            [
                _candidate(
                    "sport:hockey",
                    rank=1,
                    weighting="notional",
                    metric_value=0.30,
                    beat_close_value=0.70,
                    count=20,
                    count_used=20,
                    weight_used=200.0,
                )
            ],
        ),
    }

    def fake_scan(user: str, _flags: dict) -> str:
        return run_roots[user].as_posix()

    runner = BatchRunner(scan_callable=fake_scan, now_provider=lambda: FIXED_NOW)

    out_serial = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-serial",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
        workers=1,
    )
    out_parallel = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-par",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
        workers=3,
    )

    lb_serial = _load_json(out_serial["hypothesis_leaderboard_json"])
    lb_parallel = _load_json(out_parallel["hypothesis_leaderboard_json"])

    # Per-user order must match.
    serial_users = [row["user"] for row in lb_serial["per_user"]]
    parallel_users = [row["user"] for row in lb_parallel["per_user"]]
    assert serial_users == parallel_users == users

    # Top-lists must be identical.
    assert lb_serial["top_lists"] == lb_parallel["top_lists"]


def test_workers_continue_on_error_parallel(tmp_path):
    """Under workers>1, continue_on_error=True records failures without dropping users."""
    users = ["@ok1", "@bad", "@ok2"]
    users_file = _write_users_file(tmp_path / "users.txt", users)

    run_root_ok1 = _make_run_root(
        tmp_path,
        "run-ok1",
        [
            _candidate(
                "sport:tennis",
                rank=1,
                weighting="notional",
                metric_value=0.15,
                beat_close_value=0.6,
                count=10,
                count_used=10,
                weight_used=100.0,
            )
        ],
    )
    run_root_ok2 = _make_run_root(
        tmp_path,
        "run-ok2",
        [
            _candidate(
                "sport:cricket",
                rank=1,
                weighting="notional",
                metric_value=0.20,
                beat_close_value=0.65,
                count=12,
                count_used=12,
                weight_used=120.0,
            )
        ],
    )

    run_root_map = {"@ok1": run_root_ok1, "@ok2": run_root_ok2}

    def fake_scan(user: str, _flags: dict) -> str:
        if user == "@bad":
            raise RuntimeError("intentional failure")
        return run_root_map[user].as_posix()

    runner = BatchRunner(scan_callable=fake_scan, now_provider=lambda: FIXED_NOW)
    output_paths = runner.run_batch(
        users=users,
        users_file=users_file,
        output_root=tmp_path / "out",
        batch_id="batch-par-error",
        continue_on_error=True,
        scan_flags={"api_base_url": "http://127.0.0.1:8000"},
        workers=2,
    )

    leaderboard = _load_json(output_paths["hypothesis_leaderboard_json"])
    assert leaderboard["users_attempted"] == 3
    assert leaderboard["users_succeeded"] == 2
    assert leaderboard["users_failed"] == 1

    bad_row = next(row for row in leaderboard["per_user"] if row["user"] == "@bad")
    assert bad_row["status"] == "failure"

    # Per-user order must preserve original user list order.
    per_user_order = [row["user"] for row in leaderboard["per_user"]]
    assert per_user_order == users
