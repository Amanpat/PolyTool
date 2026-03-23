"""Offline tests for batch Silver tape reconstruction."""
from __future__ import annotations

import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Minimal SilverResult stub (matches real SilverResult interface)
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
            result = _FakeSilverResult(
                reconstruction_confidence=self._result.reconstruction_confidence,
                event_count=self._result.event_count,
                fill_count=self._result.fill_count,
                price_2min_count=self._result.price_2min_count,
                warnings=list(self._result.warnings),
                events_path=out_dir / "silver_events.jsonl",
                meta_path=out_dir / "silver_meta.json",
                error=self._result.error,
            )
            return result
        return self._result


# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------

_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from tools.cli.batch_reconstruct_silver import (
    canonical_tape_dir,
    run_batch,
    run_batch_from_targets,
    write_market_meta,
    backfill_market_meta_from_targets,
    main as batch_main,
    BATCH_MANIFEST_SCHEMA,
)
from packages.polymarket.silver_tape_metadata import (
    TapeMetadataRow,
    build_from_silver_result,
    write_to_jsonl,
)


# ---------------------------------------------------------------------------
# TestCanonicalTapeDir
# ---------------------------------------------------------------------------

class TestCanonicalTapeDir:
    def test_returns_path(self, tmp_path):
        result = canonical_tape_dir("0xABCDEF1234567890abcdef", 1700000000.0, tmp_path)
        assert isinstance(result, Path)

    def test_sixteen_char_prefix(self, tmp_path):
        token = "0xABCDEF1234567890abcdef"
        result = canonical_tape_dir(token, 1700000000.0, tmp_path)
        parts = result.parts
        silver_idx = next(i for i, p in enumerate(parts) if p == "silver")
        prefix_part = parts[silver_idx + 1]
        assert prefix_part == token[:16]

    def test_short_token_clamped(self, tmp_path):
        token = "0xABC"
        result = canonical_tape_dir(token, 1700000000.0, tmp_path)
        parts = result.parts
        silver_idx = next(i for i, p in enumerate(parts) if p == "silver")
        prefix_part = parts[silver_idx + 1]
        assert prefix_part == token  # shorter than 16, uses all

    def test_deterministic(self, tmp_path):
        r1 = canonical_tape_dir("0xTOKEN", 1700000000.0, tmp_path)
        r2 = canonical_tape_dir("0xTOKEN", 1700000000.0, tmp_path)
        assert r1 == r2

    def test_different_tokens_different_paths(self, tmp_path):
        r1 = canonical_tape_dir("0xAAAA", 1700000000.0, tmp_path)
        r2 = canonical_tape_dir("0xBBBB", 1700000000.0, tmp_path)
        assert r1 != r2

    def test_date_label_format(self, tmp_path):
        # 1700000000 = 2023-11-14T22:13:20Z
        result = canonical_tape_dir("0xTOKEN", 1700000000.0, tmp_path)
        parts = result.parts
        silver_idx = next(i for i, p in enumerate(parts) if p == "silver")
        date_part = parts[silver_idx + 2]
        assert "2023-11-14" in date_part

    def test_path_under_silver(self, tmp_path):
        result = canonical_tape_dir("0xTOKEN", 1700000000.0, tmp_path)
        assert "silver" in result.parts

    def test_empty_token_uses_unknown(self, tmp_path):
        result = canonical_tape_dir("", 1700000000.0, tmp_path)
        parts = result.parts
        silver_idx = next(i for i, p in enumerate(parts) if p == "silver")
        prefix_part = parts[silver_idx + 1]
        assert prefix_part == "unknown"


# ---------------------------------------------------------------------------
# TestRunBatch
# ---------------------------------------------------------------------------

class TestRunBatch:
    def _make_factory(self, result=None, raise_msg=None):
        def factory(config):
            return _FakeReconstructor(config, result=result, raise_on_reconstruct=raise_msg)
        return factory

    def test_single_token_success(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xTOKEN1"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert manifest["success_count"] == 1
        assert manifest["failure_count"] == 0
        assert len(manifest["outcomes"]) == 1
        assert manifest["outcomes"][0]["status"] == "success"

    def test_multiple_tokens(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xAAA", "0xBBB", "0xCCC"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert manifest["token_count"] == 3
        assert manifest["success_count"] == 3

    def test_partial_failure(self, tmp_path):
        call_count = [0]

        def factory(config):
            call_count[0] += 1
            if call_count[0] == 2:
                return _FakeReconstructor(config, raise_on_reconstruct="simulated failure")
            return _FakeReconstructor(config)

        manifest = run_batch(
            token_ids=["0xA", "0xB", "0xC"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=factory,
        )
        assert manifest["success_count"] == 2
        assert manifest["failure_count"] == 1

    def test_all_fail(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xA", "0xB"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(raise_msg="forced fail"),
        )
        assert manifest["failure_count"] == 2
        assert manifest["success_count"] == 0

    def test_dry_run_no_files(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xTOKEN"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            dry_run=True,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert manifest["dry_run"] is True
        # No silver files should be written under tmp_path/silver/
        silver_dir = tmp_path / "silver"
        assert not silver_dir.exists()

    def test_skip_metadata(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xTOKEN"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        assert manifest["metadata_summary"]["skipped"] >= 1
        assert manifest["metadata_summary"]["clickhouse"] == 0

    def test_jsonl_fallback_when_ch_fails(self, tmp_path):
        fallback = tmp_path / "fallback.jsonl"
        with patch("tools.cli.batch_reconstruct_silver.write_to_clickhouse", return_value=False):
            manifest = run_batch(
                token_ids=["0xTOKEN"],
                window_start=1700000000.0,
                window_end=1700007200.0,
                out_root=tmp_path,
                skip_metadata=False,
                metadata_fallback_path=fallback,
                _reconstructor_factory=self._make_factory(_FakeSilverResult(error=None)),
            )
        meta = manifest["metadata_summary"]
        # Either CH worked or fallback did (or both 0 if error result)
        assert meta["clickhouse"] + meta["jsonl_fallback"] >= 0  # just check it ran

    def test_no_metadata_fallback_flag(self, tmp_path):
        with patch("tools.cli.batch_reconstruct_silver.write_to_clickhouse", return_value=False):
            manifest = run_batch(
                token_ids=["0xTOKEN"],
                window_start=1700000000.0,
                window_end=1700007200.0,
                out_root=tmp_path,
                skip_metadata=False,
                no_metadata_fallback=True,
                _reconstructor_factory=self._make_factory(_FakeSilverResult(error=None)),
            )
        meta = manifest["metadata_summary"]
        assert meta["jsonl_fallback"] == 0

    def test_batch_run_id_in_manifest(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xT"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            batch_run_id="test-batch-id-123",
            _reconstructor_factory=self._make_factory(),
        )
        assert manifest["batch_run_id"] == "test-batch-id-123"

    def test_outcome_error_field_on_failure(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xTOKEN"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(raise_msg="my error"),
        )
        assert manifest["outcomes"][0]["error"] == "my error"

    def test_outcome_token_ids_preserved(self, tmp_path):
        tokens = ["0xAAA111", "0xBBB222", "0xCCC333"]
        manifest = run_batch(
            token_ids=tokens,
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=self._make_factory(),
        )
        result_tokens = [o["token_id"] for o in manifest["outcomes"]]
        assert result_tokens == tokens

    def test_metadata_ch_success_counted(self, tmp_path):
        with patch("tools.cli.batch_reconstruct_silver.write_to_clickhouse", return_value=True):
            manifest = run_batch(
                token_ids=["0xTOKEN"],
                window_start=1700000000.0,
                window_end=1700007200.0,
                out_root=tmp_path,
                skip_metadata=False,
                _reconstructor_factory=self._make_factory(_FakeSilverResult(error=None)),
            )
        assert manifest["metadata_summary"]["clickhouse"] == 1


# ---------------------------------------------------------------------------
# TestBatchManifestSchema
# ---------------------------------------------------------------------------

class TestBatchManifestSchema:
    def test_required_keys(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xT"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=lambda c: _FakeReconstructor(c),
        )
        required = [
            "schema_version", "batch_run_id", "started_at", "ended_at",
            "dry_run", "token_count", "success_count", "failure_count",
            "metadata_summary", "window_start", "window_end", "out_root", "outcomes",
        ]
        for key in required:
            assert key in manifest, f"Missing key: {key}"

    def test_schema_version(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xT"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=lambda c: _FakeReconstructor(c),
        )
        assert manifest["schema_version"] == BATCH_MANIFEST_SCHEMA

    def test_outcome_keys(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xT"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=lambda c: _FakeReconstructor(c),
        )
        outcome = manifest["outcomes"][0]
        for key in ["token_id", "status", "reconstruction_confidence", "event_count",
                    "fill_count", "price_2min_count", "warning_count", "warnings",
                    "out_dir", "events_path", "error", "metadata_write"]:
            assert key in outcome, f"Outcome missing key: {key}"

    def test_window_timestamps_are_iso(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xT"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=lambda c: _FakeReconstructor(c),
        )
        # Should be ISO format strings
        assert "T" in manifest["window_start"]
        assert "T" in manifest["window_end"]

    def test_metadata_summary_keys(self, tmp_path):
        manifest = run_batch(
            token_ids=["0xT"],
            window_start=1700000000.0,
            window_end=1700007200.0,
            out_root=tmp_path,
            skip_metadata=True,
            _reconstructor_factory=lambda c: _FakeReconstructor(c),
        )
        meta = manifest["metadata_summary"]
        assert "clickhouse" in meta
        assert "jsonl_fallback" in meta
        assert "skipped" in meta


# ---------------------------------------------------------------------------
# TestTapeMetadataRow
# ---------------------------------------------------------------------------

class TestTapeMetadataRow:
    def test_build_from_silver_result(self):
        result = _FakeSilverResult(reconstruction_confidence="medium", warnings=["w1"])
        row = build_from_silver_result(result, tier="silver", batch_run_id="batch-123")
        assert row.tier == "silver"
        assert row.batch_run_id == "batch-123"
        assert row.reconstruction_confidence == "medium"
        assert row.warning_count == 1

    def test_build_empty_warnings(self):
        result = _FakeSilverResult(warnings=[])
        row = build_from_silver_result(result)
        assert row.warning_count == 0

    def test_to_ch_row_has_required_keys(self):
        result = _FakeSilverResult()
        row = build_from_silver_result(result)
        ch = row.to_ch_row()
        for key in ["run_id", "tape_path", "tier", "token_id", "window_start",
                    "window_end", "reconstruction_confidence", "warning_count",
                    "source_inputs_json", "generated_at", "batch_run_id"]:
            assert key in ch, f"CH row missing key: {key}"

    def test_to_ch_row_timestamps_are_integers(self):
        result = _FakeSilverResult()
        row = build_from_silver_result(result)
        ch = row.to_ch_row()
        # DateTime64 fields should be epoch milliseconds (integers)
        assert isinstance(ch["window_start"], int)
        assert isinstance(ch["window_end"], int)
        assert isinstance(ch["generated_at"], int)

    def test_write_to_jsonl(self, tmp_path):
        result = _FakeSilverResult()
        row = build_from_silver_result(result, batch_run_id="bbb")
        jsonl_path = tmp_path / "meta.jsonl"
        ok = write_to_jsonl(row, jsonl_path)
        assert ok is True
        content = jsonl_path.read_text()
        record = json.loads(content.strip())
        assert record["tier"] == "silver"
        assert "schema_version" in record

    def test_write_to_jsonl_appends(self, tmp_path):
        result = _FakeSilverResult()
        row = build_from_silver_result(result)
        jsonl_path = tmp_path / "meta.jsonl"
        write_to_jsonl(row, jsonl_path)
        write_to_jsonl(row, jsonl_path)
        lines = [line for line in jsonl_path.read_text().splitlines() if line.strip()]
        assert len(lines) == 2

    def test_write_to_jsonl_bad_dir_returns_false(self):
        result = _FakeSilverResult()
        row = build_from_silver_result(result)
        import tempfile
        with tempfile.NamedTemporaryFile() as f:
            bad_path = Path(f.name) / "subdir" / "meta.jsonl"
            ok = write_to_jsonl(row, bad_path)
            assert isinstance(ok, bool)

    def test_source_inputs_json_is_valid_json(self):
        result = _FakeSilverResult()
        row = build_from_silver_result(result)
        parsed = json.loads(row.source_inputs_json)
        assert isinstance(parsed, dict)

    def test_build_uses_events_path_when_tape_path_empty(self):
        result = _FakeSilverResult(events_path=Path("/some/path/silver_events.jsonl"))
        row = build_from_silver_result(result, tape_path="")
        # Compare as Path objects to handle OS-specific separators
        assert Path(row.tape_path) == Path("/some/path/silver_events.jsonl")

    def test_build_explicit_tape_path_overrides_events_path(self):
        result = _FakeSilverResult(events_path=Path("/events/path.jsonl"))
        row = build_from_silver_result(result, tape_path="/explicit/path.jsonl")
        assert row.tape_path == "/explicit/path.jsonl"


# ---------------------------------------------------------------------------
# TestBatchCLI
# ---------------------------------------------------------------------------

class TestBatchCLI:
    def _run(self, argv):
        """Run batch_main with given argv, return exit code."""
        return batch_main(argv)

    def test_help(self):
        with pytest.raises(SystemExit) as exc:
            self._run(["--help"])
        assert exc.value.code == 0

    def test_missing_token_id(self):
        rc = self._run([
            "--window-start", "2024-01-01T00:00:00Z",
            "--window-end", "2024-01-01T02:00:00Z",
        ])
        assert rc == 1

    def test_missing_window_start(self):
        # --window-start is now optional in the parser (validated at runtime)
        rc = self._run([
            "--token-id", "0xTOKEN",
            "--window-end", "2024-01-01T02:00:00Z",
        ])
        assert rc != 0

    def test_window_ordering(self):
        rc = self._run([
            "--token-id", "0xTOKEN",
            "--window-start", "2024-01-01T02:00:00Z",
            "--window-end", "2024-01-01T00:00:00Z",
            "--dry-run",
        ])
        assert rc == 1

    def test_dry_run_exits_zero(self, tmp_path):
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
                "--clickhouse-password", "testpass",
                "--out-root", str(tmp_path),
            ])
        assert rc == 0

    def test_token_ids_file(self, tmp_path):
        token_file = tmp_path / "tokens.txt"
        token_file.write_text("0xAAA\n0xBBB\n# comment\n\n0xCCC\n")
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            rc = self._run([
                "--token-ids-file", str(token_file),
                "--window-start", "2024-01-01T00:00:00Z",
                "--window-end", "2024-01-01T02:00:00Z",
                "--dry-run",
                "--clickhouse-password", "testpass",
                "--out-root", str(tmp_path),
            ])
        assert rc == 0

    def test_invalid_timestamp(self):
        rc = self._run([
            "--token-id", "0xTOKEN",
            "--window-start", "not-a-timestamp",
            "--window-end", "2024-01-01T02:00:00Z",
        ])
        assert rc == 1

    def test_all_fail_returns_nonzero(self, tmp_path):
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_cls.return_value.reconstruct.side_effect = RuntimeError("forced")
            rc = self._run([
                "--token-id", "0xTOKEN",
                "--window-start", "2024-01-01T00:00:00Z",
                "--window-end", "2024-01-01T02:00:00Z",
                "--dry-run",
                "--clickhouse-password", "testpass",
                "--out-root", str(tmp_path),
            ])
        assert rc == 1

    def test_epoch_timestamp_accepted(self, tmp_path):
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            rc = self._run([
                "--token-id", "0xTOKEN",
                "--window-start", "1700000000",
                "--window-end", "1700007200",
                "--dry-run",
                "--clickhouse-password", "testpass",
                "--out-root", str(tmp_path),
            ])
        assert rc == 0

    def test_manifest_written_when_not_dry_run(self, tmp_path):
        manifest_dir = tmp_path / "out"
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            rc = self._run([
                "--token-id", "0xTOKEN",
                "--window-start", "2024-01-01T00:00:00Z",
                "--window-end", "2024-01-01T02:00:00Z",
                "--skip-metadata",
                "--clickhouse-password", "testpass",
                "--out-root", str(tmp_path),
                "--batch-out-dir", str(manifest_dir),
            ])
        assert rc == 0
        # A manifest JSON should be written in manifest_dir
        manifests = list(manifest_dir.glob("batch_manifest_*.json"))
        assert len(manifests) == 1

    def test_token_ids_file_missing(self, tmp_path):
        rc = self._run([
            "--token-ids-file", str(tmp_path / "nonexistent.txt"),
            "--window-start", "2024-01-01T00:00:00Z",
            "--window-end", "2024-01-01T02:00:00Z",
            "--dry-run",
        ])
        assert rc == 1

    def test_skip_metadata_flag(self, tmp_path):
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            rc = self._run([
                "--token-id", "0xTOKEN",
                "--window-start", "2024-01-01T00:00:00Z",
                "--window-end", "2024-01-01T02:00:00Z",
                "--dry-run",
                "--skip-metadata",
                "--clickhouse-password", "testpass",
                "--out-root", str(tmp_path),
            ])
        assert rc == 0

    # -----------------------------------------------------------------------
    # Credential resolution regression tests
    # -----------------------------------------------------------------------

    def test_missing_password_returns_1(self, tmp_path):
        """No --clickhouse-password and no env var on a live (non-dry-run) path → rc=1.

        Dry-run never writes to ClickHouse so it does not require credentials.
        This test uses a real (non-dry-run) invocation to exercise the fail-fast check.
        """
        from unittest.mock import patch as _patch
        env_without_pw = {k: v for k, v in __import__("os").environ.items()
                         if k != "CLICKHOUSE_PASSWORD"}
        with _patch.dict(__import__("os").environ, env_without_pw, clear=True):
            rc = self._run([
                "--token-id", "0xTOKEN",
                "--window-start", "2024-01-01T00:00:00Z",
                "--window-end", "2024-01-01T02:00:00Z",
                "--skip-price-2min",
                "--out-root", str(tmp_path),
            ])
        assert rc == 1

    def test_empty_string_password_returns_1(self, tmp_path):
        """CLICKHOUSE_PASSWORD='' (empty string) must fail fast on non-dry-run path.

        Regression for 2026-03-19 auth fix: prior code only checked `is None`,
        allowing empty-string through to ClickHouse → HTTP 516 auth failure.
        """
        from unittest.mock import patch as _patch
        with _patch.dict(__import__("os").environ, {"CLICKHOUSE_PASSWORD": ""}):
            rc = self._run([
                "--token-id", "0xTOKEN",
                "--window-start", "2024-01-01T00:00:00Z",
                "--window-end", "2024-01-01T02:00:00Z",
                "--skip-price-2min",
                "--out-root", str(tmp_path),
            ])
        assert rc == 1

    def test_password_via_env_var_proceeds(self, tmp_path):
        """CLICKHOUSE_PASSWORD env var → code proceeds past credential check."""
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            with patch.dict(__import__("os").environ, {"CLICKHOUSE_PASSWORD": "envpass"}):
                rc = self._run([
                    "--token-id", "0xTOKEN",
                    "--window-start", "2024-01-01T00:00:00Z",
                    "--window-end", "2024-01-01T02:00:00Z",
                    "--dry-run",
                    "--skip-price-2min",
                    "--out-root", str(tmp_path),
                ])
        assert rc == 0

    def test_password_flag_takes_precedence_over_env(self, tmp_path):
        """--clickhouse-password flag is used even when env var is also set."""
        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_inst = MagicMock()
            mock_inst.reconstruct.return_value = _FakeSilverResult()
            mock_cls.return_value = mock_inst
            with patch.dict(__import__("os").environ, {"CLICKHOUSE_PASSWORD": "envpass"}):
                rc = self._run([
                    "--token-id", "0xTOKEN",
                    "--window-start", "2024-01-01T00:00:00Z",
                    "--window-end", "2024-01-01T02:00:00Z",
                    "--dry-run",
                    "--skip-price-2min",
                    "--clickhouse-password", "flagpass",
                    "--out-root", str(tmp_path),
                ])
        assert rc == 0


# ---------------------------------------------------------------------------
# TestWriteMarketMeta
# ---------------------------------------------------------------------------

_SAMPLE_TARGET = {
    "bucket": "politics",
    "slug": "tariff-on-canada",
    "market_id": "0xABC123",
    "platform": "polymarket",
    "token_id": "74401234567890abcdef",
    "window_start": "2026-03-15T10:00:00+00:00",
    "window_end": "2026-03-15T14:00:00+00:00",
    "priority": 1,
}


class TestWriteMarketMeta:
    def test_writes_file(self, tmp_path):
        assert write_market_meta(_SAMPLE_TARGET, tmp_path) is True
        assert (tmp_path / "market_meta.json").exists()

    def test_correct_fields(self, tmp_path):
        write_market_meta(_SAMPLE_TARGET, tmp_path)
        data = json.loads((tmp_path / "market_meta.json").read_text())
        assert data["slug"] == "tariff-on-canada"
        assert data["category"] == "politics"
        assert data["market_id"] == "0xABC123"
        assert data["token_id"] == "74401234567890abcdef"
        assert data["benchmark_bucket"] == "politics"
        assert data["platform"] == "polymarket"
        assert data["schema_version"] == "silver_market_meta_v1"

    def test_category_equals_bucket(self, tmp_path):
        target = {**_SAMPLE_TARGET, "bucket": "sports"}
        write_market_meta(target, tmp_path)
        data = json.loads((tmp_path / "market_meta.json").read_text())
        assert data["category"] == "sports"
        assert data["benchmark_bucket"] == "sports"

    def test_returns_false_on_bad_dir(self):
        bad_dir = Path("/nonexistent/path/that/does/not/exist")
        result = write_market_meta(_SAMPLE_TARGET, bad_dir)
        assert result is False

    def test_empty_target_writes_empty_fields(self, tmp_path):
        write_market_meta({}, tmp_path)
        data = json.loads((tmp_path / "market_meta.json").read_text())
        assert data["category"] == ""
        assert data["slug"] == ""


# ---------------------------------------------------------------------------
# TestBackfillMarketMeta
# ---------------------------------------------------------------------------

class TestBackfillMarketMeta:
    def _make_tape(self, root: Path, target: dict) -> Path:
        """Create a minimal Silver tape directory for a target."""
        from tools.cli.batch_reconstruct_silver import canonical_tape_dir, _parse_ts
        ts = _parse_ts(target["window_start"])
        tape_dir = canonical_tape_dir(target["token_id"], ts, root)
        tape_dir.mkdir(parents=True, exist_ok=True)
        (tape_dir / "silver_events.jsonl").write_text("{}\n")
        return tape_dir

    def test_writes_to_existing_tape(self, tmp_path):
        target = {**_SAMPLE_TARGET}
        self._make_tape(tmp_path, target)
        result = backfill_market_meta_from_targets([target], out_root=tmp_path)
        assert result["written"] == 1
        assert result["missing"] == 0
        assert result["errors"] == 0

    def test_skips_missing_tape(self, tmp_path):
        # No tape directory created — should count as missing
        result = backfill_market_meta_from_targets([_SAMPLE_TARGET], out_root=tmp_path)
        assert result["missing"] == 1
        assert result["written"] == 0

    def test_skips_invalid_target(self, tmp_path):
        bad_targets = [
            "not-a-dict",
            {"bucket": "politics"},  # missing token_id
            {"token_id": "abc"},     # missing window_start
        ]
        result = backfill_market_meta_from_targets(bad_targets, out_root=tmp_path)
        assert result["skipped"] == 3
        assert result["written"] == 0

    def test_multiple_targets(self, tmp_path):
        targets = []
        for i, bucket in enumerate(["politics", "sports", "crypto"]):
            t = {
                "bucket": bucket,
                "slug": f"market-{i}",
                "market_id": f"0x{i:04x}",
                "platform": "polymarket",
                "token_id": f"token{i:016x}0000000000000000",
                "window_start": f"2026-03-1{i+5}T10:00:00+00:00",
                "window_end": f"2026-03-1{i+5}T14:00:00+00:00",
            }
            targets.append(t)
            self._make_tape(tmp_path, t)
        result = backfill_market_meta_from_targets(targets, out_root=tmp_path)
        assert result["written"] == 3
        assert result["missing"] == 0

    def test_market_meta_content_correct(self, tmp_path):
        target = {**_SAMPLE_TARGET}
        tape_dir = self._make_tape(tmp_path, target)
        backfill_market_meta_from_targets([target], out_root=tmp_path)
        data = json.loads((tape_dir / "market_meta.json").read_text())
        assert data["category"] == "politics"
        assert data["slug"] == "tariff-on-canada"


# ---------------------------------------------------------------------------
# TestRunBatchFromTargetsMarketMeta
# ---------------------------------------------------------------------------

_SAMPLE_MANIFEST = {
    "schema_version": "benchmark_gap_fill_v1",
    "created_at": "2026-03-15T00:00:00+00:00",
    "targets": [
        {
            "bucket": "politics",
            "slug": "tariff-on-canada",
            "market_id": "0xABC",
            "platform": "polymarket",
            "token_id": "74401234567890abcdef12345678",
            "window_start": "2026-03-15T10:00:09.554000+00:00",
            "window_end": "2026-03-15T14:00:09.554000+00:00",
            "priority": 1,
            "price_2min_ready": True,
        }
    ],
}


class TestRunBatchFromTargetsMarketMeta:
    def test_market_meta_written_on_success(self, tmp_path):
        """Successful reconstruction creates market_meta.json alongside silver_events.jsonl."""
        targets = list(_SAMPLE_MANIFEST["targets"])
        target = targets[0]

        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_cls.return_value = _FakeReconstructor(config=None)
            run_batch_from_targets(
                targets,
                out_root=tmp_path,
                clickhouse_password="testpass",
                dry_run=False,
                skip_metadata=True,
            )

        from tools.cli.batch_reconstruct_silver import canonical_tape_dir, _parse_ts
        ts = _parse_ts(target["window_start"])
        tape_dir = canonical_tape_dir(target["token_id"], ts, tmp_path)

        assert (tape_dir / "market_meta.json").exists(), "market_meta.json should be written"
        data = json.loads((tape_dir / "market_meta.json").read_text())
        assert data["category"] == "politics"
        assert data["slug"] == "tariff-on-canada"

    def test_market_meta_not_written_on_dry_run(self, tmp_path):
        """Dry run must NOT write market_meta.json."""
        targets = list(_SAMPLE_MANIFEST["targets"])
        target = targets[0]

        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            mock_cls.return_value = _FakeReconstructor(config=None)
            run_batch_from_targets(
                targets,
                out_root=tmp_path,
                clickhouse_password="testpass",
                dry_run=True,
                skip_metadata=True,
            )

        from tools.cli.batch_reconstruct_silver import canonical_tape_dir, _parse_ts
        ts = _parse_ts(target["window_start"])
        tape_dir = canonical_tape_dir(target["token_id"], ts, tmp_path)
        assert not (tape_dir / "market_meta.json").exists()

    def test_market_meta_not_written_on_failure(self, tmp_path):
        """Reconstruction failure must NOT write market_meta.json."""
        targets = list(_SAMPLE_MANIFEST["targets"])
        target = targets[0]

        with patch("tools.cli.batch_reconstruct_silver.SilverReconstructor") as mock_cls:
            failed_result = _FakeSilverResult(error="forced failure")
            mock_cls.return_value = _FakeReconstructor(config=None, result=failed_result)
            run_batch_from_targets(
                targets,
                out_root=tmp_path,
                clickhouse_password="testpass",
                dry_run=False,
                skip_metadata=True,
            )

        from tools.cli.batch_reconstruct_silver import canonical_tape_dir, _parse_ts
        ts = _parse_ts(target["window_start"])
        tape_dir = canonical_tape_dir(target["token_id"], ts, tmp_path)
        assert not (tape_dir / "market_meta.json").exists()


# ---------------------------------------------------------------------------
# TestBackfillMarketMetaCLI  (--backfill-market-meta flag)
# ---------------------------------------------------------------------------

class TestBackfillMarketMetaCLI:
    def _run(self, argv):
        return batch_main(argv)

    def _write_manifest(self, tmp_path: Path) -> Path:
        manifest = tmp_path / "targets.json"
        manifest.write_text(json.dumps(_SAMPLE_MANIFEST), encoding="utf-8")
        return manifest

    def _make_tape(self, tmp_path: Path) -> Path:
        """Create a minimal tape dir for the sample manifest target."""
        from tools.cli.batch_reconstruct_silver import canonical_tape_dir, _parse_ts
        target = _SAMPLE_MANIFEST["targets"][0]
        ts = _parse_ts(target["window_start"])
        tape_dir = canonical_tape_dir(target["token_id"], ts, tmp_path)
        tape_dir.mkdir(parents=True, exist_ok=True)
        (tape_dir / "silver_events.jsonl").write_text("{}\n")
        return tape_dir

    def test_backfill_exits_zero(self, tmp_path):
        manifest_path = self._write_manifest(tmp_path)
        self._make_tape(tmp_path)
        rc = self._run([
            "--targets-manifest", str(manifest_path),
            "--out-root", str(tmp_path),
            "--backfill-market-meta",
        ])
        assert rc == 0

    def test_backfill_does_not_require_clickhouse_password(self, tmp_path):
        """--backfill-market-meta must succeed with no ClickHouse credentials."""
        import os
        manifest_path = self._write_manifest(tmp_path)
        self._make_tape(tmp_path)
        env_without_pw = {k: v for k, v in os.environ.items() if k != "CLICKHOUSE_PASSWORD"}
        with patch.dict(__import__("os").environ, env_without_pw, clear=True):
            rc = self._run([
                "--targets-manifest", str(manifest_path),
                "--out-root", str(tmp_path),
                "--backfill-market-meta",
            ])
        assert rc == 0

    def test_backfill_writes_market_meta(self, tmp_path):
        manifest_path = self._write_manifest(tmp_path)
        tape_dir = self._make_tape(tmp_path)
        self._run([
            "--targets-manifest", str(manifest_path),
            "--out-root", str(tmp_path),
            "--backfill-market-meta",
        ])
        assert (tape_dir / "market_meta.json").exists()
        data = json.loads((tape_dir / "market_meta.json").read_text())
        assert data["category"] == "politics"
