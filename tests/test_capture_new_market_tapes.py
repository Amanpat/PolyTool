"""Offline tests for the new-market capture execution path.

Tests:
  - load_capture_targets(): valid, bad schema, missing array, bad JSON, OS error
  - canonical_tape_dir(): slug → path
  - resolve_both_token_ids(): success via mock picker, resolver exception
  - run_capture_batch(): success, skip (no slug, resolver error), failure (recorder raises),
      dry_run, metadata persistence (CH, JSONL fallback), benchmark_refresh default
  - _refresh_benchmark_curation(): manifest written, gap report updated, error path
  - CLI smoke: --help, --dry-run, missing manifest, bad schema, --benchmark-refresh flag,
      result artifact written, exit code contract
"""
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root on sys.path
# ---------------------------------------------------------------------------

_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tools.cli.capture_new_market_tapes import (
    CAPTURE_MANIFEST_SCHEMA,
    CAPTURE_RUN_SCHEMA,
    _refresh_benchmark_curation,
    _skip_outcome,
    canonical_tape_dir,
    load_capture_targets,
    main as capture_main,
    resolve_both_token_ids,
    run_capture_batch,
)


# ---------------------------------------------------------------------------
# Fake MarketPicker / ResolvedMarket
# ---------------------------------------------------------------------------

@dataclass
class _FakeResolved:
    yes_token_id: str = "0xYES0000000000000000000000000000000000000000000000000"
    no_token_id: str = "0xNO00000000000000000000000000000000000000000000000000"
    slug: str = "test-market"


class _FakePicker:
    def __init__(self, resolved=None, raise_msg=None):
        self._resolved = resolved or _FakeResolved()
        self._raise = raise_msg

    def resolve_slug(self, slug):
        if self._raise:
            raise RuntimeError(self._raise)
        return self._resolved


# ---------------------------------------------------------------------------
# Fake TapeRecorder
# ---------------------------------------------------------------------------

class _FakeRecorder:
    """Writes meta.json and events.jsonl like a real TapeRecorder would."""

    def __init__(self, tape_dir: Path, asset_ids, event_count: int = 42, raise_msg=None):
        self._tape_dir = tape_dir
        self._raise = raise_msg
        self._event_count = event_count

    def record(self, duration_seconds=None):
        if self._raise:
            raise RuntimeError(self._raise)
        self._tape_dir.mkdir(parents=True, exist_ok=True)
        (self._tape_dir / "events.jsonl").write_text("{}\n", encoding="utf-8")
        meta = {"event_count": self._event_count, "frame_count": 10}
        (self._tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_target(
    slug: str = "my-new-market",
    token_id: str = "0xTOKEN000000000000000",
    priority: int = 1,
    listed_at: str = "2026-03-17T10:00:00Z",
    age_hours: float = 5.0,
    record_duration_seconds: int = 1800,
) -> dict:
    return {
        "bucket": "new_market",
        "slug": slug,
        "market_id": "123456",
        "token_id": token_id,
        "listed_at": listed_at,
        "age_hours": age_hours,
        "priority": priority,
        "record_duration_seconds": record_duration_seconds,
        "selection_reason": "age_hours=5.00 listed_at=2026-03-17T10:00:00Z slug=my-new-market",
    }


def _make_manifest(targets: list, schema_version: str = CAPTURE_MANIFEST_SCHEMA) -> dict:
    return {
        "schema_version": schema_version,
        "generated_at": "2026-03-17T12:00:00Z",
        "targets": targets,
    }


def _write_manifest(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "targets.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _picker_factory_for(resolved=None, raise_msg=None):
    def factory():
        return _FakePicker(resolved=resolved, raise_msg=raise_msg)
    return factory


def _recorder_factory_for(event_count=42, raise_msg=None):
    def factory(tape_dir, asset_ids):
        return _FakeRecorder(tape_dir, asset_ids, event_count=event_count, raise_msg=raise_msg)
    return factory


# ---------------------------------------------------------------------------
# TestLoadCaptureTargets
# ---------------------------------------------------------------------------

class TestLoadCaptureTargets:
    def test_valid_manifest(self, tmp_path):
        p = _write_manifest(tmp_path, _make_manifest([_make_target()]))
        result, err = load_capture_targets(p)
        assert err is None
        assert len(result) == 1
        assert result[0]["slug"] == "my-new-market"

    def test_empty_targets(self, tmp_path):
        p = _write_manifest(tmp_path, _make_manifest([]))
        result, err = load_capture_targets(p)
        assert err is None
        assert result == []

    def test_wrong_schema_version(self, tmp_path):
        p = _write_manifest(tmp_path, _make_manifest([], schema_version="wrong_v99"))
        result, err = load_capture_targets(p)
        assert result == []
        assert err is not None
        assert "schema_version" in err

    def test_missing_targets_key(self, tmp_path):
        data = {"schema_version": CAPTURE_MANIFEST_SCHEMA}
        p = tmp_path / "t.json"
        p.write_text(json.dumps(data))
        result, err = load_capture_targets(p)
        assert result == []
        assert "targets" in err

    def test_root_not_a_dict(self, tmp_path):
        p = tmp_path / "t.json"
        p.write_text("[1, 2, 3]")
        result, err = load_capture_targets(p)
        assert result == []
        assert err is not None

    def test_bad_json(self, tmp_path):
        p = tmp_path / "t.json"
        p.write_text("not-json{{{{")
        result, err = load_capture_targets(p)
        assert result == []
        assert err is not None

    def test_file_not_found(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        result, err = load_capture_targets(p)
        assert result == []
        assert "cannot read" in err

    def test_multiple_targets(self, tmp_path):
        targets = [_make_target(slug=f"market-{i}") for i in range(5)]
        p = _write_manifest(tmp_path, _make_manifest(targets))
        result, err = load_capture_targets(p)
        assert err is None
        assert len(result) == 5


# ---------------------------------------------------------------------------
# TestCanonicalTapeDir
# ---------------------------------------------------------------------------

class TestCanonicalTapeDir:
    def test_basic(self, tmp_path):
        d = canonical_tape_dir("will-trump-win", tmp_path)
        assert d == tmp_path / "will-trump-win"

    def test_slash_in_slug(self, tmp_path):
        d = canonical_tape_dir("a/b", tmp_path)
        assert "a" in str(d) and "b" in str(d)
        # Should not create nested directories from the slash
        assert "/" not in d.name or d.name == "a_b"

    def test_empty_slug(self, tmp_path):
        d = canonical_tape_dir("", tmp_path)
        assert d.name == "unknown"


# ---------------------------------------------------------------------------
# TestResolveBothTokenIds
# ---------------------------------------------------------------------------

class TestResolveBothTokenIds:
    def test_success(self):
        factory = _picker_factory_for()
        yes_id, no_id, err = resolve_both_token_ids("any-slug", _picker_factory=factory)
        assert yes_id.startswith("0xYES")
        assert no_id.startswith("0xNO0")
        assert err is None

    def test_resolver_raises(self):
        factory = _picker_factory_for(raise_msg="network error")
        yes_id, no_id, err = resolve_both_token_ids("any-slug", _picker_factory=factory)
        assert yes_id == ""
        assert no_id == ""
        assert err is not None
        assert "network error" in err

    def test_empty_yes_token_returned(self):
        resolved = _FakeResolved(yes_token_id="", no_token_id="0xNO")
        factory = _picker_factory_for(resolved=resolved)
        yes_id, no_id, err = resolve_both_token_ids("x", _picker_factory=factory)
        assert yes_id == ""

    def test_never_raises(self):
        # Even with a completely broken factory, must return an error string
        def bad_factory():
            raise OSError("disk error")
        yes_id, no_id, err = resolve_both_token_ids("slug", _picker_factory=bad_factory)
        assert err is not None


# ---------------------------------------------------------------------------
# TestRunCaptureBatch
# ---------------------------------------------------------------------------

class TestRunCaptureBatch:

    def test_single_target_success(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(event_count=77),
        )
        assert result["tapes_created"] == 1
        assert result["failure_count"] == 0
        assert result["skip_count"] == 0
        assert result["outcomes"][0]["status"] == "success"
        assert result["outcomes"][0]["event_count"] == 77
        assert result["outcomes"][0]["bucket"] == "new_market"

    def test_multiple_targets(self, tmp_path):
        targets = [_make_target(slug=f"market-{i}") for i in range(3)]
        result = run_capture_batch(
            targets=targets,
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["targets_attempted"] == 3
        assert result["tapes_created"] == 3

    def test_skip_missing_slug(self, tmp_path):
        bad = _make_target(slug="")
        result = run_capture_batch(
            targets=[bad],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["skip_count"] == 1
        assert result["tapes_created"] == 0
        assert "slug" in result["outcomes"][0]["skip_reason"]

    def test_skip_resolver_error(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(raise_msg="API down"),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["skip_count"] == 1
        assert result["tapes_created"] == 0

    def test_skip_target_not_a_dict(self, tmp_path):
        result = run_capture_batch(
            targets=["not-a-dict"],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["skip_count"] == 1

    def test_failure_recorder_raises(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(raise_msg="WS connection refused"),
        )
        assert result["failure_count"] == 1
        assert result["tapes_created"] == 0
        assert "WS connection refused" in result["outcomes"][0]["error"]

    def test_partial_failure_continues(self, tmp_path):
        """Second target recorder raises; batch continues for target 3."""
        call_count = [0]

        def factory(tape_dir, asset_ids):
            call_count[0] += 1
            if call_count[0] == 2:
                return _FakeRecorder(tape_dir, asset_ids, raise_msg="fail-2")
            return _FakeRecorder(tape_dir, asset_ids)

        targets = [_make_target(slug=f"m-{i}") for i in range(3)]
        result = run_capture_batch(
            targets=targets,
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=factory,
        )
        assert result["targets_attempted"] == 3
        assert result["tapes_created"] == 2
        assert result["failure_count"] == 1

    def test_dry_run_no_files_written(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target()],
            out_root=tmp_path,
            dry_run=True,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["dry_run"] is True
        assert result["tapes_created"] == 1  # resolved OK → would be created
        # No actual tape files written
        assert not list(tmp_path.rglob("events.jsonl"))

    def test_dry_run_skip_on_resolver_failure(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target()],
            out_root=tmp_path,
            dry_run=True,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(raise_msg="no network"),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["tapes_created"] == 0
        assert result["skip_count"] == 1

    def test_watch_meta_written(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target(slug="test-market")],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        tape_dir = tmp_path / "test-market"
        watch_meta_path = tape_dir / "watch_meta.json"
        assert watch_meta_path.exists()
        watch_meta = json.loads(watch_meta_path.read_text())
        assert watch_meta["market_slug"] == "test-market"
        assert watch_meta["regime"] == "new_market"
        assert watch_meta["bucket"] == "new_market"
        assert "yes_asset_id" in watch_meta
        assert "no_asset_id" in watch_meta

    def test_outcome_carries_listed_at_and_age_hours(self, tmp_path):
        target = _make_target(listed_at="2026-03-17T10:00:00Z", age_hours=5.25)
        result = run_capture_batch(
            targets=[target],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        outcome = result["outcomes"][0]
        assert outcome["listed_at"] == "2026-03-17T10:00:00Z"
        assert outcome["age_hours"] == 5.25

    def test_schema_version(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["schema_version"] == CAPTURE_RUN_SCHEMA

    def test_benchmark_refresh_field_default(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["benchmark_refresh"]["triggered"] is False
        assert result["benchmark_refresh"]["outcome"] == "not_requested"

    def test_batch_run_id_propagated(self, tmp_path):
        result = run_capture_batch(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            batch_run_id="test-run-999",
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["batch_run_id"] == "test-run-999"

    def test_empty_targets_returns_empty(self, tmp_path):
        result = run_capture_batch(
            targets=[],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=_recorder_factory_for(),
        )
        assert result["targets_attempted"] == 0
        assert result["tapes_created"] == 0
        assert result["outcomes"] == []

    def test_metadata_ch_success(self, tmp_path):
        with patch("tools.cli.capture_new_market_tapes.write_to_clickhouse", return_value=True):
            result = run_capture_batch(
                targets=[_make_target()],
                out_root=tmp_path,
                skip_metadata=False,
                _picker_factory=_picker_factory_for(),
                _recorder_factory=_recorder_factory_for(),
            )
        assert result["metadata_summary"]["clickhouse"] == 1

    def test_metadata_jsonl_fallback(self, tmp_path):
        fallback = tmp_path / "fallback.jsonl"
        with patch("tools.cli.capture_new_market_tapes.write_to_clickhouse", return_value=False):
            result = run_capture_batch(
                targets=[_make_target()],
                out_root=tmp_path,
                skip_metadata=False,
                metadata_fallback_path=fallback,
                _picker_factory=_picker_factory_for(),
                _recorder_factory=_recorder_factory_for(),
            )
        assert result["metadata_summary"]["jsonl_fallback"] == 1
        assert fallback.exists()

    def test_mixed_skip_success_failure(self, tmp_path):
        call_count = [0]

        def recorder_factory(tape_dir, asset_ids):
            call_count[0] += 1
            if call_count[0] == 2:
                return _FakeRecorder(tape_dir, asset_ids, raise_msg="boom")
            return _FakeRecorder(tape_dir, asset_ids)

        good = _make_target(slug="good-1")
        bad_slug = _make_target(slug="")
        bad_record = _make_target(slug="fail-market")

        result = run_capture_batch(
            targets=[good, bad_slug, bad_record],
            out_root=tmp_path,
            skip_metadata=True,
            _picker_factory=_picker_factory_for(),
            _recorder_factory=recorder_factory,
        )
        assert result["targets_attempted"] == 3
        assert result["tapes_created"] == 1
        assert result["skip_count"] == 1
        assert result["failure_count"] == 1


# ---------------------------------------------------------------------------
# TestBenchmarkRefreshHook
# ---------------------------------------------------------------------------

class TestBenchmarkRefreshHook:

    def test_manifest_written(self, tmp_path):
        manifest_out = str(tmp_path / "benchmark_v1.tape_manifest")

        def fake_run_build(argv):
            Path(manifest_out).write_text("[]")
            return 0

        with patch("tools.cli.benchmark_manifest._run_build", side_effect=fake_run_build):
            result = _refresh_benchmark_curation(
                manifest_out=manifest_out,
                gap_out=str(tmp_path / "gap.json"),
                audit_out=str(tmp_path / "audit.json"),
            )

        assert result["triggered"] is True
        assert result["manifest_written"] is True
        assert result["outcome"] == "manifest_written"
        assert result["manifest_path"] == manifest_out

    def test_gap_report_updated(self, tmp_path):
        manifest_out = str(tmp_path / "benchmark_v1.tape_manifest")
        with patch("tools.cli.benchmark_manifest._run_build", return_value=2):
            result = _refresh_benchmark_curation(
                manifest_out=manifest_out,
                gap_out=str(tmp_path / "gap.json"),
                audit_out=str(tmp_path / "audit.json"),
            )
        assert result["outcome"] == "gap_report_updated"
        assert result["manifest_written"] is False

    def test_internal_error_returns_error_dict(self):
        with patch(
            "tools.cli.benchmark_manifest._run_build",
            side_effect=RuntimeError("unexpected"),
        ):
            result = _refresh_benchmark_curation(
                manifest_out="config/benchmark_v1.tape_manifest",
                gap_out="config/benchmark_v1.gap_report.json",
                audit_out="config/benchmark_v1.audit.json",
            )
        assert result["triggered"] is True
        assert result["manifest_written"] is False
        assert result["outcome"] == "error"
        assert "error" in result


# ---------------------------------------------------------------------------
# TestCaptureCLI
# ---------------------------------------------------------------------------

class TestCaptureCLI:

    def _run(self, argv):
        return capture_main(argv)

    def _write_targets(self, tmp_path, targets=None):
        if targets is None:
            targets = [_make_target()]
        p = _write_manifest(tmp_path, _make_manifest(targets))
        return p

    def test_help(self):
        with pytest.raises(SystemExit) as exc:
            self._run(["--help"])
        assert exc.value.code == 0

    def test_missing_manifest_returns_1(self, tmp_path):
        rc = self._run([
            "--targets-manifest", str(tmp_path / "nonexistent.json"),
            "--dry-run",
            "--out-root", str(tmp_path),
        ])
        assert rc == 1

    def test_bad_schema_manifest_returns_1(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"schema_version": "wrong", "targets": []}))
        rc = self._run([
            "--targets-manifest", str(p),
            "--dry-run",
            "--out-root", str(tmp_path),
        ])
        assert rc == 1

    def test_dry_run_exits_zero_with_valid_manifest(self, tmp_path):
        manifest_path = self._write_targets(tmp_path)
        with patch("tools.cli.capture_new_market_tapes.run_capture_batch") as mock_batch:
            mock_batch.return_value = {
                "schema_version": CAPTURE_RUN_SCHEMA,
                "batch_run_id": "x",
                "started_at": "t",
                "ended_at": "t",
                "dry_run": True,
                "targets_attempted": 1,
                "tapes_created": 1,
                "failure_count": 0,
                "skip_count": 0,
                "metadata_summary": {"clickhouse": 0, "jsonl_fallback": 0, "skipped": 1},
                "out_root": str(tmp_path),
                "benchmark_refresh": {"triggered": False, "outcome": "not_requested"},
                "outcomes": [],
            }
            rc = self._run([
                "--targets-manifest", str(manifest_path),
                "--dry-run",
                "--out-root", str(tmp_path),
            ])
        assert rc == 0

    def test_result_artifact_written(self, tmp_path):
        manifest_path = self._write_targets(tmp_path)
        result_path = tmp_path / "result.json"
        with patch("tools.cli.capture_new_market_tapes.run_capture_batch") as mock_batch:
            mock_batch.return_value = {
                "schema_version": CAPTURE_RUN_SCHEMA,
                "batch_run_id": "abc",
                "started_at": "t",
                "ended_at": "t",
                "dry_run": False,
                "targets_attempted": 1,
                "tapes_created": 1,
                "failure_count": 0,
                "skip_count": 0,
                "metadata_summary": {"clickhouse": 0, "jsonl_fallback": 0, "skipped": 1},
                "out_root": str(tmp_path),
                "benchmark_refresh": {"triggered": False, "outcome": "not_requested"},
                "outcomes": [],
            }
            rc = self._run([
                "--targets-manifest", str(manifest_path),
                "--skip-metadata",
                "--out-root", str(tmp_path),
                "--result-out", str(result_path),
            ])
        assert rc == 0
        assert result_path.exists()
        data = json.loads(result_path.read_text())
        assert data["schema_version"] == CAPTURE_RUN_SCHEMA

    def test_benchmark_refresh_called_on_live_run(self, tmp_path):
        manifest_path = self._write_targets(tmp_path)
        result_path = tmp_path / "result.json"
        base_result = {
            "schema_version": CAPTURE_RUN_SCHEMA,
            "batch_run_id": "abc",
            "started_at": "t",
            "ended_at": "t",
            "dry_run": False,
            "targets_attempted": 1,
            "tapes_created": 1,
            "failure_count": 0,
            "skip_count": 0,
            "metadata_summary": {"clickhouse": 0, "jsonl_fallback": 0, "skipped": 1},
            "out_root": str(tmp_path),
            "benchmark_refresh": {"triggered": False, "outcome": "not_requested"},
            "outcomes": [],
        }
        with patch("tools.cli.capture_new_market_tapes.run_capture_batch", return_value=base_result):
            with patch(
                "tools.cli.capture_new_market_tapes._refresh_benchmark_curation",
            ) as mock_refresh:
                mock_refresh.return_value = {
                    "triggered": True,
                    "return_code": 2,
                    "manifest_written": False,
                    "outcome": "gap_report_updated",
                    "manifest_path": None,
                    "gap_report_path": "config/benchmark_v1.gap_report.json",
                }
                rc = self._run([
                    "--targets-manifest", str(manifest_path),
                    "--skip-metadata",
                    "--benchmark-refresh",
                    "--out-root", str(tmp_path),
                    "--result-out", str(result_path),
                ])
        assert rc == 0
        mock_refresh.assert_called_once()
        data = json.loads(result_path.read_text())
        assert data["benchmark_refresh"]["triggered"] is True

    def test_benchmark_refresh_skipped_on_dry_run(self, tmp_path):
        manifest_path = self._write_targets(tmp_path)
        dry_result = {
            "schema_version": CAPTURE_RUN_SCHEMA,
            "batch_run_id": "abc",
            "started_at": "t",
            "ended_at": "t",
            "dry_run": True,
            "targets_attempted": 1,
            "tapes_created": 1,
            "failure_count": 0,
            "skip_count": 0,
            "metadata_summary": {"clickhouse": 0, "jsonl_fallback": 0, "skipped": 1},
            "out_root": str(tmp_path),
            "benchmark_refresh": {"triggered": False, "outcome": "not_requested"},
            "outcomes": [],
        }
        with patch("tools.cli.capture_new_market_tapes.run_capture_batch", return_value=dry_result):
            with patch(
                "tools.cli.capture_new_market_tapes._refresh_benchmark_curation",
            ) as mock_refresh:
                rc = self._run([
                    "--targets-manifest", str(manifest_path),
                    "--dry-run",
                    "--benchmark-refresh",
                    "--out-root", str(tmp_path),
                ])
        assert rc == 0
        mock_refresh.assert_not_called()

    def test_all_targets_skipped_returns_1(self, tmp_path):
        """Exit non-zero when all targets fail to record (no tapes created)."""
        manifest_path = self._write_targets(tmp_path)
        no_tapes_result = {
            "schema_version": CAPTURE_RUN_SCHEMA,
            "batch_run_id": "abc",
            "started_at": "t",
            "ended_at": "t",
            "dry_run": False,
            "targets_attempted": 1,
            "tapes_created": 0,
            "failure_count": 0,
            "skip_count": 1,
            "metadata_summary": {"clickhouse": 0, "jsonl_fallback": 0, "skipped": 1},
            "out_root": str(tmp_path),
            "benchmark_refresh": {"triggered": False, "outcome": "not_requested"},
            "outcomes": [],
        }
        with patch("tools.cli.capture_new_market_tapes.run_capture_batch", return_value=no_tapes_result):
            rc = self._run([
                "--targets-manifest", str(manifest_path),
                "--skip-metadata",
                "--out-root", str(tmp_path),
            ])
        assert rc == 1

    def test_empty_manifest_exits_zero(self, tmp_path):
        """Empty target list → 0 attempted → exit 0 (nothing to do)."""
        manifest_path = _write_manifest(tmp_path, _make_manifest([]))
        empty_result = {
            "schema_version": CAPTURE_RUN_SCHEMA,
            "batch_run_id": "abc",
            "started_at": "t",
            "ended_at": "t",
            "dry_run": False,
            "targets_attempted": 0,
            "tapes_created": 0,
            "failure_count": 0,
            "skip_count": 0,
            "metadata_summary": {"clickhouse": 0, "jsonl_fallback": 0, "skipped": 0},
            "out_root": str(tmp_path),
            "benchmark_refresh": {"triggered": False, "outcome": "not_requested"},
            "outcomes": [],
        }
        with patch("tools.cli.capture_new_market_tapes.run_capture_batch", return_value=empty_result):
            rc = self._run([
                "--targets-manifest", str(manifest_path),
                "--skip-metadata",
                "--out-root", str(tmp_path),
            ])
        assert rc == 0
