"""Offline tests for the Silver tape reconstructor.

All tests are fully offline: no DuckDB parquet files, no ClickHouse connection.
Injectable fetch functions return fixture data.

Test coverage:
  - Confidence model: high / medium / low / none
  - Missing pmxt source -> warning + confidence degraded
  - Missing Jon fills -> warning + confidence degraded
  - Missing price_2min -> warning + confidence degraded
  - All sources missing -> confidence = "none"
  - pmxt root not configured -> warning emitted
  - Jon root not configured -> warning emitted
  - price_2min skipped -> warning emitted
  - Jon timestamp ambiguity detection
  - Deterministic output for the same inputs
  - Output files written with correct structure
  - silver_events.jsonl: seq monotonic, required fields present, source tags correct
  - silver_meta.json: schema_version, all required fields, JSON-serializable
  - dry_run skips file writes
  - SilverResult.to_dict round-trip
  - CLI smoke: dry-run returns 0
  - CLI smoke: missing required args -> nonzero
  - CLI smoke: window_end <= window_start -> nonzero
  - CLI smoke: out-dir written when provided
  - CLI smoke: ISO timestamp string accepted
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from packages.polymarket.silver_reconstructor import (
    EVENT_TYPE_PRICE_2MIN_GUIDE,
    SILVER_SCHEMA_VERSION,
    ReconstructConfig,
    SilverReconstructor,
    SourceInputs,
    _compute_confidence,
    _detect_col,
    _to_float_ts,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_TOKEN = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_WIN_START = 1700000000.0  # 2023-11-14T22:13:20Z
_WIN_END = 1700007200.0    # 2023-11-15T00:13:20Z  (2 hours later)

# A minimal pmxt anchor row (simulates what DuckDB would return)
_PMXT_ROW: Dict[str, Any] = {
    "token_id": _TOKEN,
    "snapshot_ts": "2023-11-14T22:00:00+00:00",
    "best_bid": 0.54,
    "best_ask": 0.56,
    "bid_depth": 100.0,
    "ask_depth": 120.0,
}

# Minimal Jon-Becker fill rows
_JON_ROWS: List[Dict[str, Any]] = [
    {
        "asset_id": _TOKEN,
        "timestamp": "2023-11-14T22:30:00+00:00",
        "price": 0.55,
        "size": 10.0,
        "side": "BUY",
    },
    {
        "asset_id": _TOKEN,
        "timestamp": "2023-11-14T23:00:00+00:00",
        "price": 0.57,
        "size": 5.0,
        "side": "SELL",
    },
]

# Minimal price_2min rows (ts as epoch int, matching ClickHouse JSONEachRow output)
_PRICE_ROWS: List[Dict[str, Any]] = [
    {"ts": 1700001600, "price": 0.55},
    {"ts": 1700003200, "price": 0.56},
]


def _make_pmxt_fn(row: Optional[Dict[str, Any]]):
    """Return an injectable pmxt fetch function that always returns row."""
    def _fetch(pmxt_root: str, token_id: str, window_start: float):
        return row
    return _fetch


def _make_jon_fn(rows: List[Dict[str, Any]]):
    """Return an injectable Jon fetch function that always returns rows."""
    def _fetch(jon_root: str, token_id: str, window_start: float, window_end: float):
        return list(rows)
    return _fetch


def _make_price_fn(rows: List[Dict[str, Any]]):
    """Return an injectable price_2min fetch function (3-arg protocol)."""
    def _fetch(token_id: str, window_start: float, window_end: float):
        return list(rows)
    return _fetch


def _make_reconstructor(
    pmxt_row=_PMXT_ROW,
    jon_rows=None,
    price_rows=None,
    pmxt_root="/fake/pmxt",
    jon_root="/fake/jon",
    skip_price_2min=False,
) -> SilverReconstructor:
    if jon_rows is None:
        jon_rows = list(_JON_ROWS)
    if price_rows is None:
        price_rows = list(_PRICE_ROWS)
    config = ReconstructConfig(
        pmxt_root=pmxt_root,
        jon_root=jon_root,
        skip_price_2min=skip_price_2min,
    )
    return SilverReconstructor(
        config,
        _pmxt_fetch_fn=_make_pmxt_fn(pmxt_row),
        _jon_fetch_fn=_make_jon_fn(jon_rows),
        _price_2min_fetch_fn=_make_price_fn(price_rows),
    )


# ---------------------------------------------------------------------------
# _compute_confidence
# ---------------------------------------------------------------------------


class TestComputeConfidence:
    def test_high_all_three(self):
        inputs = SourceInputs(pmxt_anchor_found=True, jon_fill_count=2, price_2min_count=3)
        assert _compute_confidence(inputs) == "high"

    def test_medium_anchor_plus_fills(self):
        inputs = SourceInputs(pmxt_anchor_found=True, jon_fill_count=1, price_2min_count=0)
        assert _compute_confidence(inputs) == "medium"

    def test_medium_anchor_plus_price(self):
        inputs = SourceInputs(pmxt_anchor_found=True, jon_fill_count=0, price_2min_count=2)
        assert _compute_confidence(inputs) == "medium"

    def test_low_only_anchor(self):
        inputs = SourceInputs(pmxt_anchor_found=True, jon_fill_count=0, price_2min_count=0)
        assert _compute_confidence(inputs) == "low"

    def test_low_only_fills(self):
        inputs = SourceInputs(pmxt_anchor_found=False, jon_fill_count=3, price_2min_count=0)
        assert _compute_confidence(inputs) == "low"

    def test_low_only_price(self):
        inputs = SourceInputs(pmxt_anchor_found=False, jon_fill_count=0, price_2min_count=5)
        assert _compute_confidence(inputs) == "low"

    def test_none_all_missing(self):
        inputs = SourceInputs(pmxt_anchor_found=False, jon_fill_count=0, price_2min_count=0)
        assert _compute_confidence(inputs) == "none"


# ---------------------------------------------------------------------------
# _detect_col
# ---------------------------------------------------------------------------


class TestDetectCol:
    def test_exact_match(self):
        assert _detect_col(["token_id", "price"], ["token_id"]) == "token_id"

    def test_case_insensitive(self):
        assert _detect_col(["Token_ID", "price"], ["token_id"]) == "Token_ID"

    def test_first_candidate_wins(self):
        # "timestamp" appears in columns and is first in candidates
        assert _detect_col(["ts", "timestamp"], ["timestamp", "ts"]) == "timestamp"

    def test_none_on_no_match(self):
        assert _detect_col(["foo", "bar"], ["token_id", "asset_id"]) is None


# ---------------------------------------------------------------------------
# _to_float_ts
# ---------------------------------------------------------------------------


class TestToFloatTs:
    def test_epoch_int(self):
        assert _to_float_ts(1700000000) == pytest.approx(1700000000.0)

    def test_epoch_float(self):
        assert _to_float_ts(1700000000.5) == pytest.approx(1700000000.5)

    def test_iso_string_with_offset(self):
        result = _to_float_ts("2023-11-14T22:13:20+00:00")
        assert result == pytest.approx(1700000000.0)

    def test_iso_z_suffix(self):
        result = _to_float_ts("2023-11-14T22:13:20Z")
        assert result == pytest.approx(1700000000.0)

    def test_datetime_object(self):
        dt = datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
        assert _to_float_ts(dt) == pytest.approx(1700000000.0)

    def test_none_returns_none(self):
        assert _to_float_ts(None) is None

    def test_bad_string_returns_none(self):
        assert _to_float_ts("not-a-timestamp") is None


# ---------------------------------------------------------------------------
# SilverReconstructor: confidence
# ---------------------------------------------------------------------------


class TestReconstructorConfidence:
    def test_high_confidence_all_sources(self):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.reconstruction_confidence == "high"
        assert result.ok

    def test_medium_confidence_no_fills(self):
        rec = _make_reconstructor(jon_rows=[])
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.reconstruction_confidence == "medium"

    def test_medium_confidence_no_price(self):
        rec = _make_reconstructor(price_rows=[])
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.reconstruction_confidence == "medium"

    def test_low_confidence_anchor_only(self):
        rec = _make_reconstructor(jon_rows=[], price_rows=[])
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.reconstruction_confidence == "low"

    def test_low_confidence_fills_only(self):
        rec = _make_reconstructor(pmxt_row=None, price_rows=[])
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.reconstruction_confidence == "low"

    def test_none_confidence_all_missing(self):
        rec = _make_reconstructor(pmxt_row=None, jon_rows=[], price_rows=[])
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.reconstruction_confidence == "none"


# ---------------------------------------------------------------------------
# SilverReconstructor: event counts
# ---------------------------------------------------------------------------


class TestReconstructorEventCounts:
    def test_event_count_all_sources(self):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        # 1 anchor + 2 fills + 2 price_2min = 5 events
        assert result.event_count == 5
        assert result.fill_count == 2
        assert result.price_2min_count == 2

    def test_single_fill(self):
        rec = _make_reconstructor(jon_rows=list(_JON_ROWS[:1]))
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.fill_count == 1

    def test_no_events_all_missing(self):
        rec = _make_reconstructor(pmxt_row=None, jon_rows=[], price_rows=[])
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.event_count == 0
        assert result.fill_count == 0
        assert result.price_2min_count == 0


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


class TestReconstructorWarnings:
    def test_missing_pmxt_warning(self):
        rec = _make_reconstructor(pmxt_row=None)
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert any("pmxt_anchor_missing" in w for w in result.warnings)

    def test_missing_jon_warning(self):
        rec = _make_reconstructor(jon_rows=[])
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert any("jon_fills_missing" in w for w in result.warnings)

    def test_missing_price_warning(self):
        rec = _make_reconstructor(price_rows=[])
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert any("price_2min_missing" in w for w in result.warnings)

    def test_pmxt_root_not_configured(self):
        config = ReconstructConfig(pmxt_root=None, jon_root="/fake/jon", skip_price_2min=True)
        rec = SilverReconstructor(
            config,
            _jon_fetch_fn=_make_jon_fn(_JON_ROWS),
            _price_2min_fetch_fn=_make_price_fn([]),
        )
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert any("pmxt_root_not_configured" in w for w in result.warnings)

    def test_jon_root_not_configured(self):
        config = ReconstructConfig(pmxt_root="/fake/pmxt", jon_root=None, skip_price_2min=True)
        rec = SilverReconstructor(
            config,
            _pmxt_fetch_fn=_make_pmxt_fn(_PMXT_ROW),
            _price_2min_fetch_fn=_make_price_fn([]),
        )
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert any("jon_root_not_configured" in w for w in result.warnings)

    def test_price_2min_skipped_warning(self):
        config = ReconstructConfig(
            pmxt_root="/fake/pmxt", jon_root="/fake/jon", skip_price_2min=True
        )
        rec = SilverReconstructor(
            config,
            _pmxt_fetch_fn=_make_pmxt_fn(_PMXT_ROW),
            _jon_fetch_fn=_make_jon_fn(_JON_ROWS),
        )
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert any("price_2min_skipped" in w for w in result.warnings)

    def test_jon_timestamp_ambiguity_warning(self):
        dup_rows = [
            {"asset_id": _TOKEN, "timestamp": "2023-11-14T22:30:00+00:00",
             "price": 0.55, "size": 10.0, "side": "BUY"},
            {"asset_id": _TOKEN, "timestamp": "2023-11-14T22:30:00+00:00",
             "price": 0.56, "size": 5.0, "side": "SELL"},
        ]
        rec = _make_reconstructor(jon_rows=dup_rows)
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert any("jon_timestamp_ambiguity" in w for w in result.warnings)

    def test_no_ambiguity_for_unique_timestamps(self):
        rec = _make_reconstructor()  # _JON_ROWS has distinct timestamps
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert not any("jon_timestamp_ambiguity" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_inputs_produce_same_counts(self):
        """Two runs with the same fixture data must produce identical counts."""
        rec1 = _make_reconstructor()
        rec2 = _make_reconstructor()
        r1 = rec1.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        r2 = rec2.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert r1.reconstruction_confidence == r2.reconstruction_confidence
        assert r1.event_count == r2.event_count
        assert r1.fill_count == r2.fill_count
        assert r1.price_2min_count == r2.price_2min_count
        assert r1.warnings == r2.warnings

    def test_run_id_unique_per_call(self):
        rec = _make_reconstructor()
        r1 = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        r2 = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert r1.run_id != r2.run_id


# ---------------------------------------------------------------------------
# Output files
# ---------------------------------------------------------------------------


class TestOutputFiles:
    def test_events_jsonl_written(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        assert result.events_path is not None
        assert result.events_path.exists()
        lines = result.events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == result.event_count

    def test_events_are_valid_json_with_required_fields(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        lines = result.events_path.read_text(encoding="utf-8").strip().splitlines()
        for line in lines:
            evt = json.loads(line)
            assert "event_type" in evt
            assert "seq" in evt
            assert "ts_recv" in evt
            assert "asset_id" in evt
            assert "silver_source" in evt

    def test_meta_json_written(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        assert result.meta_path is not None
        assert result.meta_path.exists()

    def test_meta_json_schema_version(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
        assert meta["schema_version"] == SILVER_SCHEMA_VERSION

    def test_meta_json_has_required_fields(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        meta = json.loads(result.meta_path.read_text(encoding="utf-8"))
        for f in [
            "schema_version", "run_id", "token_id", "window_start", "window_end",
            "reconstruction_confidence", "warnings", "event_count",
            "fill_count", "price_2min_count", "source_inputs",
        ]:
            assert f in meta, f"Missing field in silver_meta.json: {f}"

    def test_dry_run_no_files_written(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path, dry_run=True)
        assert result.events_path is None
        assert result.meta_path is None
        assert result.out_dir is None
        assert not list(tmp_path.iterdir())

    def test_seq_is_monotonic(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        lines = result.events_path.read_text(encoding="utf-8").strip().splitlines()
        seqs = [json.loads(l)["seq"] for l in lines]
        assert seqs == list(range(len(seqs)))

    def test_event_types_present(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        lines = result.events_path.read_text(encoding="utf-8").strip().splitlines()
        event_types = {json.loads(l)["event_type"] for l in lines}
        assert "book" in event_types                       # pmxt anchor
        assert "last_trade_price" in event_types           # Jon fills
        assert EVENT_TYPE_PRICE_2MIN_GUIDE in event_types  # price_2min guide

    def test_silver_source_tags(self, tmp_path):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        lines = result.events_path.read_text(encoding="utf-8").strip().splitlines()
        sources = {json.loads(l)["silver_source"] for l in lines}
        assert "pmxt_anchor" in sources
        assert "jon_fill" in sources
        assert "price_2min" in sources

    def test_price_2min_guide_has_note(self, tmp_path):
        """price_2min_guide events must carry an explicit 'not tick data' note."""
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=tmp_path)
        lines = result.events_path.read_text(encoding="utf-8").strip().splitlines()
        guide_events = [
            json.loads(l) for l in lines
            if json.loads(l)["event_type"] == EVENT_TYPE_PRICE_2MIN_GUIDE
        ]
        assert guide_events, "Expected at least one price_2min_guide event"
        for evt in guide_events:
            assert "note" in evt
            assert "NOT" in evt["note"].upper() or "not" in evt["note"]


# ---------------------------------------------------------------------------
# SilverResult.to_dict
# ---------------------------------------------------------------------------


class TestSilverResultToDict:
    def test_round_trips_as_json(self):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        d = result.to_dict()
        serialized = json.dumps(d)  # must not raise
        reloaded = json.loads(serialized)
        assert reloaded["token_id"] == _TOKEN
        assert reloaded["reconstruction_confidence"] == "high"
        assert isinstance(reloaded["warnings"], list)
        assert isinstance(reloaded["source_inputs"], dict)

    def test_dry_run_paths_are_none(self):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        d = result.to_dict()
        assert d["out_dir"] is None
        assert d["events_path"] is None
        assert d["meta_path"] is None

    def test_error_is_none_on_success(self):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        assert result.to_dict()["error"] is None

    def test_source_inputs_subfields(self):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, dry_run=True)
        si = result.to_dict()["source_inputs"]
        assert si["pmxt_anchor_found"] is True
        assert si["jon_fill_count"] == 2
        assert si["price_2min_count"] == 2


# ---------------------------------------------------------------------------
# error path: out_dir=None without dry_run
# ---------------------------------------------------------------------------


class TestErrorPath:
    def test_no_out_dir_without_dry_run_returns_error(self):
        rec = _make_reconstructor()
        result = rec.reconstruct(_TOKEN, _WIN_START, _WIN_END, out_dir=None, dry_run=False)
        assert result.error is not None
        assert not result.ok


# ---------------------------------------------------------------------------
# CLI smoke (monkeypatching module-level real fetch functions)
# ---------------------------------------------------------------------------


class TestCLISmoke:
    def test_dry_run_returns_zero(self, monkeypatch):
        from tools.cli.reconstruct_silver import main
        import packages.polymarket.silver_reconstructor as sr

        monkeypatch.setattr(sr, "_real_fetch_pmxt_anchor",
                            lambda *a, **kw: _PMXT_ROW)
        monkeypatch.setattr(sr, "_real_fetch_jon_fills",
                            lambda *a, **kw: list(_JON_ROWS))
        monkeypatch.setattr(sr, "_real_fetch_price_2min",
                            lambda *a, **kw: list(_PRICE_ROWS))

        rc = main([
            "--token-id", _TOKEN,
            "--window-start", str(_WIN_START),
            "--window-end", str(_WIN_END),
            "--pmxt-root", "/fake/pmxt",
            "--jon-root", "/fake/jon",
            "--dry-run",
        ])
        assert rc == 0

    def test_missing_required_args_exits_nonzero(self):
        from tools.cli.reconstruct_silver import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--token-id", _TOKEN])
        assert exc_info.value.code != 0

    def test_window_end_before_start_returns_nonzero(self):
        from tools.cli.reconstruct_silver import main
        rc = main([
            "--token-id", _TOKEN,
            "--window-start", str(_WIN_END),   # reversed intentionally
            "--window-end", str(_WIN_START),
            "--pmxt-root", "/fake/pmxt",
            "--dry-run",
        ])
        assert rc != 0

    def test_out_dir_written(self, tmp_path, monkeypatch):
        from tools.cli.reconstruct_silver import main
        import packages.polymarket.silver_reconstructor as sr

        monkeypatch.setattr(sr, "_real_fetch_pmxt_anchor",
                            lambda *a, **kw: _PMXT_ROW)
        monkeypatch.setattr(sr, "_real_fetch_jon_fills",
                            lambda *a, **kw: list(_JON_ROWS))
        monkeypatch.setattr(sr, "_real_fetch_price_2min",
                            lambda *a, **kw: list(_PRICE_ROWS))

        out_dir = tmp_path / "silver_out"
        rc = main([
            "--token-id", _TOKEN,
            "--window-start", str(_WIN_START),
            "--window-end", str(_WIN_END),
            "--pmxt-root", "/fake/pmxt",
            "--jon-root", "/fake/jon",
            "--skip-price-2min",
            "--out-dir", str(out_dir),
        ])
        assert rc == 0
        assert (out_dir / "silver_events.jsonl").exists()
        assert (out_dir / "silver_meta.json").exists()

    def test_iso_timestamp_string_accepted(self, monkeypatch):
        from tools.cli.reconstruct_silver import main
        import packages.polymarket.silver_reconstructor as sr

        monkeypatch.setattr(sr, "_real_fetch_pmxt_anchor",
                            lambda *a, **kw: None)
        monkeypatch.setattr(sr, "_real_fetch_jon_fills",
                            lambda *a, **kw: [])
        monkeypatch.setattr(sr, "_real_fetch_price_2min",
                            lambda *a, **kw: [])

        rc = main([
            "--token-id", _TOKEN,
            "--window-start", "2023-11-14T22:13:20Z",
            "--window-end", "2023-11-15T00:13:20Z",
            "--pmxt-root", "/fake/pmxt",
            "--skip-price-2min",
            "--dry-run",
        ])
        assert rc == 0

    def test_skip_price_2min_flag(self, tmp_path, monkeypatch):
        from tools.cli.reconstruct_silver import main
        import packages.polymarket.silver_reconstructor as sr

        price_fn_called = []

        def _never_called(*a, **kw):
            price_fn_called.append(True)
            return []

        monkeypatch.setattr(sr, "_real_fetch_pmxt_anchor",
                            lambda *a, **kw: _PMXT_ROW)
        monkeypatch.setattr(sr, "_real_fetch_jon_fills",
                            lambda *a, **kw: list(_JON_ROWS))
        monkeypatch.setattr(sr, "_real_fetch_price_2min", _never_called)

        rc = main([
            "--token-id", _TOKEN,
            "--window-start", str(_WIN_START),
            "--window-end", str(_WIN_END),
            "--pmxt-root", "/fake/pmxt",
            "--jon-root", "/fake/jon",
            "--skip-price-2min",
            "--dry-run",
        ])
        assert rc == 0
        # price_2min was not called because --skip-price-2min was set
        assert not price_fn_called
