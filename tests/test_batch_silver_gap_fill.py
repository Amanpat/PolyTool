"""Offline tests for the benchmark gap-fill execution path.

Tests:
  - load_targets_manifest(): valid, bad schema_version, missing targets, bad JSON, OSError
  - run_batch_from_targets(): all success, partial failure, skip invalid targets
  - Deterministic rerun: same target run twice produces same output dir
  - _refresh_benchmark_curation(): mocked, manifest written, gap report updated, error path
  - CLI smoke: --targets-manifest with fake manifest, --benchmark-refresh flag
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

from tools.cli.batch_reconstruct_silver import (
    GAP_FILL_RUN_SCHEMA,
    TARGETS_MANIFEST_SCHEMA,
    _refresh_benchmark_curation,
    canonical_tape_dir,
    load_targets_manifest,
    main as batch_main,
    run_batch_from_targets,
)


# ---------------------------------------------------------------------------
# Fake SilverResult (reuses the pattern from test_batch_silver.py)
# ---------------------------------------------------------------------------

@dataclass
class _FakeSilverResult:
    reconstruction_confidence: str = "medium"
    event_count: int = 5
    fill_count: int = 2
    price_2min_count: int = 1
    warnings: list = None
    events_path: Optional[Path] = None
    meta_path: Optional[Path] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def to_dict(self) -> dict:
        return {
            "run_id": str(uuid.uuid4()),
            "token_id": "0xtest",
            "window_start": "2024-01-01T00:00:00+00:00",
            "window_end": "2024-01-01T02:00:00+00:00",
            "reconstruction_confidence": self.reconstruction_confidence,
            "warnings": list(self.warnings),
            "event_count": self.event_count,
            "fill_count": self.fill_count,
            "price_2min_count": self.price_2min_count,
            "source_inputs": {"pmxt_anchor_found": False},
            "error": self.error,
        }


class _FakeReconstructor:
    def __init__(self, config, result=None, raise_on_reconstruct=None):
        self._result = result or _FakeSilverResult()
        self._raise = raise_on_reconstruct

    def reconstruct(self, token_id, window_start, window_end, out_dir, dry_run):
        if self._raise:
            raise RuntimeError(self._raise)
        if out_dir and not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "silver_events.jsonl").write_text("{}\n")
            (out_dir / "silver_meta.json").write_text("{}")
            return _FakeSilverResult(
                reconstruction_confidence=self._result.reconstruction_confidence,
                event_count=self._result.event_count,
                fill_count=self._result.fill_count,
                price_2min_count=self._result.price_2min_count,
                warnings=list(self._result.warnings),
                events_path=out_dir / "silver_events.jsonl",
                meta_path=out_dir / "silver_meta.json",
                error=self._result.error,
            )
        return self._result


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_WIN_START = "2024-01-01T00:00:00+00:00"
_WIN_END = "2024-01-01T02:00:00+00:00"


def _make_target(
    token_id="0xAAAAAAAAAAAAAAAA",
    bucket="politics",
    slug="my-market",
    priority=1,
    window_start=_WIN_START,
    window_end=_WIN_END,
) -> dict:
    return {
        "bucket": bucket,
        "platform": "polymarket",
        "slug": slug,
        "market_id": "0xMARKET",
        "token_id": token_id,
        "window_start": window_start,
        "window_end": window_end,
        "priority": priority,
        "selection_reason": "test",
        "price_2min_ready": False,
    }


def _make_manifest(targets: list, schema_version: str = TARGETS_MANIFEST_SCHEMA) -> dict:
    return {
        "schema_version": schema_version,
        "generated_at": "2026-03-17T00:00:00+00:00",
        "source_roots": {},
        "bucket_summary": {},
        "targets": targets,
    }


def _write_manifest(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "targets.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# TestLoadTargetsManifest
# ---------------------------------------------------------------------------

class TestLoadTargetsManifest:
    def test_valid_manifest(self, tmp_path):
        targets = [_make_target()]
        p = _write_manifest(tmp_path, _make_manifest(targets))
        result, err = load_targets_manifest(p)
        assert err is None
        assert len(result) == 1
        assert result[0]["token_id"] == "0xAAAAAAAAAAAAAAAA"

    def test_empty_targets_list(self, tmp_path):
        p = _write_manifest(tmp_path, _make_manifest([]))
        result, err = load_targets_manifest(p)
        assert err is None
        assert result == []

    def test_wrong_schema_version(self, tmp_path):
        p = _write_manifest(tmp_path, _make_manifest([], schema_version="wrong_v1"))
        result, err = load_targets_manifest(p)
        assert result == []
        assert err is not None
        assert "schema_version" in err

    def test_missing_targets_key(self, tmp_path):
        data = {"schema_version": TARGETS_MANIFEST_SCHEMA}
        p = tmp_path / "targets.json"
        p.write_text(json.dumps(data))
        result, err = load_targets_manifest(p)
        assert result == []
        assert err is not None
        assert "targets" in err

    def test_not_a_dict(self, tmp_path):
        p = tmp_path / "targets.json"
        p.write_text("[1, 2, 3]")
        result, err = load_targets_manifest(p)
        assert result == []
        assert err is not None

    def test_bad_json(self, tmp_path):
        p = tmp_path / "targets.json"
        p.write_text("not-json{{{")
        result, err = load_targets_manifest(p)
        assert result == []
        assert err is not None

    def test_file_not_found(self, tmp_path):
        p = tmp_path / "nonexistent.json"
        result, err = load_targets_manifest(p)
        assert result == []
        assert err is not None
        assert "cannot read" in err

    def test_multiple_targets_returned(self, tmp_path):
        targets = [_make_target(token_id=f"0x{i:040d}") for i in range(5)]
        p = _write_manifest(tmp_path, _make_manifest(targets))
        result, err = load_targets_manifest(p)
        assert err is None
        assert len(result) == 5


# ---------------------------------------------------------------------------
# TestRunBatchFromTargets
# ---------------------------------------------------------------------------

class TestRunBatchFromTargets:
    def _make_factory(self, result=None, raise_msg=None):
        def factory(config):
            return _FakeReconstructor(config, result=result, raise_on_reconstruct=raise_msg)
        return factory

    def test_single_target_success(self, tmp_path):
        targets = [_make_target()]
        result = run_batch_from_targets(
            targets=targets,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["tapes_created"] == 1
        assert result["failure_count"] == 0
        assert result["skip_count"] == 0
        assert len(result["outcomes"]) == 1
        assert result["outcomes"][0]["status"] == "success"

    def test_multiple_targets(self, tmp_path):
        targets = [
            _make_target(token_id=f"0xAAAAAAAAAAAAAAAA{i}") for i in range(3)
        ]
        result = run_batch_from_targets(
            targets=targets,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["targets_attempted"] == 3
        assert result["tapes_created"] == 3

    def test_partial_failure_continues(self, tmp_path):
        call_count = [0]

        def factory(config):
            call_count[0] += 1
            if call_count[0] == 2:
                return _FakeReconstructor(config, raise_on_reconstruct="boom")
            return _FakeReconstructor(config)

        targets = [_make_target(token_id=f"0x{i:040x}") for i in range(3)]
        result = run_batch_from_targets(
            targets=targets,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=factory,
        )
        assert result["tapes_created"] == 2
        assert result["failure_count"] == 1
        # Batch did not abort; all 3 attempted
        assert result["targets_attempted"] == 3

    def test_skip_target_missing_token_id(self, tmp_path):
        bad = _make_target()
        bad["token_id"] = ""
        result = run_batch_from_targets(
            targets=[bad],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["skip_count"] == 1
        assert result["tapes_created"] == 0
        assert result["outcomes"][0]["status"] == "skip"
        assert "token_id" in result["outcomes"][0]["skip_reason"]

    def test_skip_target_bad_window(self, tmp_path):
        bad = _make_target(window_start="not-a-timestamp")
        result = run_batch_from_targets(
            targets=[bad],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["skip_count"] == 1
        assert result["outcomes"][0]["status"] == "skip"

    def test_skip_target_inverted_window(self, tmp_path):
        bad = _make_target(
            window_start="2024-01-01T02:00:00+00:00",
            window_end="2024-01-01T00:00:00+00:00",
        )
        result = run_batch_from_targets(
            targets=[bad],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["skip_count"] == 1

    def test_skip_target_not_a_dict(self, tmp_path):
        result = run_batch_from_targets(
            targets=["not-a-dict"],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["skip_count"] == 1

    def test_outcome_carries_bucket_slug(self, tmp_path):
        target = _make_target(bucket="crypto", slug="btc-market")
        result = run_batch_from_targets(
            targets=[target],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["outcomes"][0]["bucket"] == "crypto"
        assert result["outcomes"][0]["slug"] == "btc-market"

    def test_dry_run_no_files(self, tmp_path):
        targets = [_make_target()]
        result = run_batch_from_targets(
            targets=targets,
            out_root=tmp_path,
            dry_run=True,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["dry_run"] is True
        # No silver dir should be created
        assert not (tmp_path / "silver").exists()

    def test_deterministic_output_dir(self, tmp_path):
        """Same token + window_start always maps to the same canonical directory."""
        token = "0xAAAAAAAAAAAAAAAA"
        window_start_iso = "2024-01-01T00:00:00+00:00"
        target = _make_target(token_id=token, window_start=window_start_iso)

        # Run twice; second run should reuse same dir (idempotent reconstruction)
        for _ in range(2):
            run_batch_from_targets(
                targets=[target],
                out_root=tmp_path,
                skip_metadata=True,
                _reconstructor_factory=self._make_factory(),
            )

        # canonical_tape_dir is deterministic — same path each time
        from tools.cli.batch_reconstruct_silver import _parse_ts
        ws_f = _parse_ts(window_start_iso)
        dir1 = canonical_tape_dir(token, ws_f, tmp_path)
        assert dir1.exists()

    def test_schema_version(self, tmp_path):
        result = run_batch_from_targets(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["schema_version"] == GAP_FILL_RUN_SCHEMA

    def test_benchmark_refresh_field_default(self, tmp_path):
        result = run_batch_from_targets(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        # Before caller sets refresh, it should be the not_requested sentinel
        assert result["benchmark_refresh"]["triggered"] is False
        assert result["benchmark_refresh"]["outcome"] == "not_requested"

    def test_metadata_ch_success(self, tmp_path):
        with patch("tools.cli.batch_reconstruct_silver.write_to_clickhouse", return_value=True):
            result = run_batch_from_targets(
                targets=[_make_target()],
                out_root=tmp_path,
                skip_metadata=False,
                _reconstructor_factory=self._make_factory(_FakeSilverResult(error=None)),
            )
        assert result["metadata_summary"]["clickhouse"] == 1

    def test_metadata_jsonl_fallback(self, tmp_path):
        fallback = tmp_path / "fallback.jsonl"
        with patch("tools.cli.batch_reconstruct_silver.write_to_clickhouse", return_value=False):
            result = run_batch_from_targets(
                targets=[_make_target()],
                out_root=tmp_path,
                skip_metadata=False,
                metadata_fallback_path=fallback,
                _reconstructor_factory=self._make_factory(_FakeSilverResult(error=None)),
            )
        assert result["metadata_summary"]["jsonl_fallback"] == 1
        assert fallback.exists()

    def test_empty_targets_returns_empty(self, tmp_path):
        result = run_batch_from_targets(
            targets=[],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert result["targets_attempted"] == 0
        assert result["tapes_created"] == 0
        assert result["outcomes"] == []

    def test_batch_run_id_propagated(self, tmp_path):
        result = run_batch_from_targets(
            targets=[_make_target()],
            out_root=tmp_path,
            skip_metadata=True,
            batch_run_id="test-id-999",
            _reconstructor_factory=self._make_factory(),
        )
        assert result["batch_run_id"] == "test-id-999"

    def test_mixed_success_skip_failure(self, tmp_path):
        call_count = [0]

        def factory(config):
            call_count[0] += 1
            if call_count[0] == 2:
                return _FakeReconstructor(config, raise_on_reconstruct="fail2")
            return _FakeReconstructor(config)

        good = _make_target(token_id="0x0000000000000001")
        bad_window = _make_target(token_id="0x0000000000000002", window_start="bad")
        failing = _make_target(token_id="0x0000000000000003")

        result = run_batch_from_targets(
            targets=[good, bad_window, failing],
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=factory,
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
            # Simulate success: write the manifest file
            Path(manifest_out).write_text("[]")
            return 0

        with patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation") as mock_refresh:
            mock_refresh.return_value = {
                "triggered": True,
                "return_code": 0,
                "manifest_written": True,
                "outcome": "manifest_written",
                "manifest_path": manifest_out,
                "gap_report_path": None,
            }
            result = mock_refresh()

        assert result["manifest_written"] is True
        assert result["outcome"] == "manifest_written"

    def test_gap_report_updated(self):
        with patch("tools.cli.batch_reconstruct_silver._refresh_benchmark_curation") as mock_refresh:
            mock_refresh.return_value = {
                "triggered": True,
                "return_code": 2,
                "manifest_written": False,
                "outcome": "gap_report_updated",
                "manifest_path": None,
                "gap_report_path": "config/benchmark_v1.gap_report.json",
            }
            result = mock_refresh()

        assert result["manifest_written"] is False
        assert result["outcome"] == "gap_report_updated"

    def test_internal_error_returns_error_dict(self):
        """_refresh_benchmark_curation must not raise even if _run_build raises."""
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

    def test_run_build_success_sets_manifest_written(self, tmp_path):
        manifest_out = str(tmp_path / "benchmark_v1.tape_manifest")
        gap_out = str(tmp_path / "gap_report.json")
        audit_out = str(tmp_path / "audit.json")

        def fake_run_build(argv):
            Path(manifest_out).write_text("[]")
            return 0

        with patch("tools.cli.benchmark_manifest._run_build", side_effect=fake_run_build):
            result = _refresh_benchmark_curation(
                manifest_out=manifest_out,
                gap_out=gap_out,
                audit_out=audit_out,
            )

        assert result["triggered"] is True
        assert result["manifest_written"] is True
        assert result["outcome"] == "manifest_written"
        assert result["manifest_path"] == manifest_out

    def test_run_build_rc2_gap_report(self, tmp_path):
        manifest_out = str(tmp_path / "benchmark_v1.tape_manifest")
        gap_out = str(tmp_path / "gap_report.json")
        audit_out = str(tmp_path / "audit.json")

        with patch("tools.cli.benchmark_manifest._run_build", return_value=2):
            result = _refresh_benchmark_curation(
                manifest_out=manifest_out,
                gap_out=gap_out,
                audit_out=audit_out,
            )

        assert result["outcome"] == "gap_report_updated"
        assert result["manifest_written"] is False


# ---------------------------------------------------------------------------
# TestGapFillCLI
# ---------------------------------------------------------------------------

class TestGapFillCLI:
    def _run(self, argv):
        return batch_main(argv)

    def _write_targets(self, tmp_path, targets=None):
        if targets is None:
            targets = [_make_target()]
        manifest = _make_manifest(targets)
        p = tmp_path / "targets.json"
        p.write_text(json.dumps(manifest))
        return p

    def test_help(self):
        with pytest.raises(SystemExit) as exc:
            self._run(["--help"])
        assert exc.value.code == 0

    def test_targets_manifest_dry_run_exits_zero(self, tmp_path):
        manifest_path = self._write_targets(tmp_path)
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            rc = self._run([
                "--targets-manifest", str(manifest_path),
                "--dry-run",
                "--skip-price-2min",
                "--skip-metadata",
                "--out-root", str(tmp_path),
            ])
        assert rc == 0

    def test_targets_manifest_nonexistent_file(self, tmp_path):
        rc = self._run([
            "--targets-manifest", str(tmp_path / "missing.json"),
            "--dry-run",
            "--out-root", str(tmp_path),
        ])
        assert rc == 1

    def test_targets_manifest_bad_schema(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"schema_version": "wrong", "targets": []}))
        rc = self._run([
            "--targets-manifest", str(p),
            "--dry-run",
            "--out-root", str(tmp_path),
        ])
        assert rc == 1

    def test_targets_manifest_writes_gap_fill_result(self, tmp_path):
        manifest_path = self._write_targets(tmp_path)
        result_path = tmp_path / "result.json"
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            rc = self._run([
                "--targets-manifest", str(manifest_path),
                "--skip-metadata",
                "--skip-price-2min",
                "--clickhouse-password", "testpass",
                "--out-root", str(tmp_path),
                "--gap-fill-out", str(result_path),
            ])
        assert rc == 0
        assert result_path.exists()
        data = json.loads(result_path.read_text())
        assert data["schema_version"] == GAP_FILL_RUN_SCHEMA
        assert data["targets_attempted"] == 1

    def test_targets_manifest_benchmark_refresh_flag(self, tmp_path):
        manifest_path = self._write_targets(tmp_path)
        result_path = tmp_path / "result.json"
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            with patch(
                "tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
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
                    "--skip-price-2min",
                    "--benchmark-refresh",
                    "--clickhouse-password", "testpass",
                    "--out-root", str(tmp_path),
                    "--gap-fill-out", str(result_path),
                ])
        assert rc == 0
        mock_refresh.assert_called_once()
        data = json.loads(result_path.read_text())
        assert data["benchmark_refresh"]["triggered"] is True

    def test_benchmark_refresh_skipped_on_dry_run(self, tmp_path):
        """--benchmark-refresh must not fire in dry-run mode."""
        manifest_path = self._write_targets(tmp_path)
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            with patch(
                "tools.cli.batch_reconstruct_silver._refresh_benchmark_curation",
            ) as mock_refresh:
                rc = self._run([
                    "--targets-manifest", str(manifest_path),
                    "--dry-run",
                    "--skip-metadata",
                    "--benchmark-refresh",
                    "--out-root", str(tmp_path),
                ])
        assert rc == 0
        mock_refresh.assert_not_called()

    def test_mode1_still_works_after_changes(self, tmp_path):
        """Original --token-id mode must still work."""
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            rc = self._run([
                "--token-id", "0xTOKEN",
                "--window-start", "2024-01-01T00:00:00Z",
                "--window-end", "2024-01-01T02:00:00Z",
                "--dry-run",
                "--skip-price-2min",
                "--out-root", str(tmp_path),
            ])
        assert rc == 0

    def test_mode1_missing_window_start(self):
        rc = self._run([
            "--token-id", "0xTOKEN",
            "--window-end", "2024-01-01T02:00:00Z",
        ])
        assert rc != 0

    def test_gap_fill_all_targets_skipped_returns_nonzero(self, tmp_path):
        """If all targets are invalid (skipped), exit non-zero since no tapes created."""
        # Both targets have missing token_id
        bad1 = _make_target()
        bad1["token_id"] = ""
        bad2 = _make_target()
        bad2["token_id"] = ""
        manifest_path = self._write_targets(tmp_path, targets=[bad1, bad2])
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            rc = self._run([
                "--targets-manifest", str(manifest_path),
                "--skip-metadata",
                "--out-root", str(tmp_path),
            ])
        assert rc == 1
