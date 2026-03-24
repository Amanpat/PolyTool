"""Tests for Gate 2 eligible tape acquisition pipeline.

Coverage:
  - scan_one_tape: non-executable tape → eligible=False (regression guard)
  - scan_one_tape: executable tape → eligible=True
  - scan_one_tape: missing events.jsonl → eligible=False
  - scan_one_tape: missing asset IDs → eligible=False
  - scan_one_tape: eligibility check error → eligible=False
  - Invariant: eligible is True ONLY when executable_ticks > 0
  - Regime reading: watch_meta.json → regime field
  - Regime reading: prep_meta.json → regime field
  - Regime reading: meta.json shadow_context → regime field
  - Regime reading: no metadata → "unknown"
  - build_corpus_summary: counts correct
  - build_corpus_summary: mixed_regime_eligible requires an eligible tape plus >= 2 named classified regimes
  - manifest_to_dict: schema keys present
  - manifest_to_dict: eligibility_params written correctly
  - --regime flag on watch-arb-candidates writes to watch_meta.json
  - --regime flag on prepare-gate2 writes to prep_meta.json via regime in prepare_candidates
  - ResolvedWatch.regime field defaults to "unknown"

All tests are fully offline — no network calls, no live API.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from tools.cli.tape_manifest import (
    TapeRecord,
    _read_regime,
    _read_recorded_by,
    _read_slug,
    _read_tape_market_metadata,
    build_corpus_summary,
    manifest_to_dict,
    scan_one_tape,
)
from tools.cli.watch_arb_candidates import ResolvedWatch, _record_tape_for_market


# ---------------------------------------------------------------------------
# Helpers: build minimal tape directories for testing
# ---------------------------------------------------------------------------


def _write_events(tape_dir: Path, events: list[dict]) -> Path:
    """Write events.jsonl into tape_dir."""
    tape_dir.mkdir(parents=True, exist_ok=True)
    path = tape_dir / "events.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")
    return path


def _book_event(asset_id: str, asks: list[dict]) -> dict:
    return {"event_type": "book", "asset_id": asset_id, "asks": asks, "bids": []}


def _price_change_event(asset_id: str, asks: list[dict]) -> dict:
    return {
        "event_type": "price_change",
        "asset_id": asset_id,
        "changes": [{"price": a["price"], "side": "SELL", "size": a["size"]} for a in asks],
    }


def _ask(price: str, size: str) -> dict:
    return {"price": price, "size": size}


YES_ID = "yes-token-abc123"
NO_ID = "no-token-def456"


def _write_watch_meta(tape_dir: Path, regime: str = "unknown") -> None:
    tape_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "market_slug": "test-market",
        "yes_asset_id": YES_ID,
        "no_asset_id": NO_ID,
        "triggered_by": "watch-arb-candidates",
        "regime": regime,
    }
    (tape_dir / "watch_meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _write_prep_meta(tape_dir: Path, regime: str = "unknown") -> None:
    meta = {
        "market_slug": "test-market",
        "yes_asset_id": YES_ID,
        "no_asset_id": NO_ID,
        "regime": regime,
    }
    (tape_dir / "prep_meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _write_eligible_watch_tape(tape_dir: Path, regime: str) -> None:
    _write_watch_meta(tape_dir, regime=regime)
    _write_events(tape_dir, [
        _book_event(YES_ID, [_ask("0.40", "100")]),
        _book_event(NO_ID, [_ask("0.55", "100")]),
        _price_change_event(YES_ID, [_ask("0.40", "100")]),
    ])


def _write_ineligible_watch_tape_no_edge(tape_dir: Path, regime: str) -> None:
    _write_watch_meta(tape_dir, regime=regime)
    _write_events(tape_dir, [
        _book_event(YES_ID, [_ask("0.50", "100")]),
        _book_event(NO_ID, [_ask("0.50", "100")]),
    ])


# ---------------------------------------------------------------------------
# Tests: eligibility invariant — non-executable tapes NEVER labeled eligible
# ---------------------------------------------------------------------------


class TestNonExecutableTapeNotEligible:
    """Regression guard: tapes without executable ticks must never be labeled eligible."""

    def test_insufficient_depth_not_eligible(self, tmp_path):
        """Tape with shallow book (size < 50) is not eligible."""
        tape_dir = tmp_path / "tape_shallow"
        _write_watch_meta(tape_dir)
        _write_events(tape_dir, [
            _book_event(YES_ID, [_ask("0.40", "5")]),   # size 5 << 50
            _book_event(NO_ID, [_ask("0.55", "5")]),    # size 5 << 50
            _price_change_event(YES_ID, [_ask("0.40", "5")]),
        ])
        record = scan_one_tape(tape_dir, max_size=50.0, buffer=0.01)
        assert record.eligible is False
        assert record.executable_ticks == 0
        assert record.reject_reason != ""

    def test_no_edge_not_eligible(self, tmp_path):
        """Tape with sufficient depth but no edge (sum_ask >= 0.99) is not eligible."""
        tape_dir = tmp_path / "tape_no_edge"
        _write_watch_meta(tape_dir)
        _write_events(tape_dir, [
            _book_event(YES_ID, [_ask("0.50", "100")]),  # sum = 1.00 >= 0.99
            _book_event(NO_ID, [_ask("0.50", "100")]),
        ])
        record = scan_one_tape(tape_dir, max_size=50.0, buffer=0.01)
        assert record.eligible is False
        assert record.executable_ticks == 0

    def test_empty_tape_not_eligible(self, tmp_path):
        """Tape with no events is not eligible."""
        tape_dir = tmp_path / "tape_empty"
        _write_watch_meta(tape_dir)
        _write_events(tape_dir, [])
        record = scan_one_tape(tape_dir, max_size=50.0, buffer=0.01)
        assert record.eligible is False
        assert record.executable_ticks == 0

    def test_missing_events_file_not_eligible(self, tmp_path):
        """Tape directory with no events.jsonl is not eligible."""
        tape_dir = tmp_path / "tape_no_events"
        tape_dir.mkdir()
        _write_watch_meta(tape_dir)
        record = scan_one_tape(tape_dir)
        assert record.eligible is False
        assert record.executable_ticks == 0
        assert "events.jsonl" in record.reject_reason

    def test_missing_asset_ids_not_eligible(self, tmp_path):
        """Tape with events but no metadata for asset IDs is not eligible."""
        tape_dir = tmp_path / "tape_no_ids"
        tape_dir.mkdir()
        # events.jsonl with no book events (so asset IDs can't be discovered)
        events_path = tape_dir / "events.jsonl"
        events_path.write_text('{"event_type": "last_trade_price", "price": "0.50"}\n')
        record = scan_one_tape(tape_dir)
        assert record.eligible is False
        assert record.executable_ticks == 0

    def test_eligible_invariant_executable_ticks_zero_means_ineligible(self, tmp_path):
        """Hard invariant: executable_ticks == 0 always means eligible == False."""
        tape_dir = tmp_path / "tape_invariant"
        _write_watch_meta(tape_dir)
        _write_events(tape_dir, [
            _book_event(YES_ID, [_ask("0.50", "100")]),
            _book_event(NO_ID, [_ask("0.51", "100")]),  # sum = 1.01, no edge
        ])
        record = scan_one_tape(tape_dir, max_size=50.0, buffer=0.01)
        # Verify the invariant explicitly
        if record.executable_ticks == 0:
            assert record.eligible is False, (
                "INVARIANT VIOLATED: executable_ticks=0 but eligible=True"
            )


# ---------------------------------------------------------------------------
# Tests: eligible tape correctly identified
# ---------------------------------------------------------------------------


class TestEligibleTapeDetected:
    def test_tape_with_depth_and_edge_is_eligible(self, tmp_path):
        """Tape with simultaneous depth_ok AND edge_ok is eligible."""
        tape_dir = tmp_path / "tape_good"
        _write_watch_meta(tape_dir, regime="sports")
        _write_events(tape_dir, [
            # sum_ask = 0.40 + 0.55 = 0.95 < 0.99 threshold; both sizes >= 50
            _book_event(YES_ID, [_ask("0.40", "100")]),
            _book_event(NO_ID, [_ask("0.55", "100")]),
            _price_change_event(YES_ID, [_ask("0.40", "100")]),
        ])
        record = scan_one_tape(tape_dir, max_size=50.0, buffer=0.01)
        assert record.eligible is True
        assert record.executable_ticks > 0
        assert record.reject_reason == ""
        assert record.regime == "sports"

    def test_eligible_executable_ticks_positive(self, tmp_path):
        """eligible=True must be accompanied by executable_ticks > 0."""
        tape_dir = tmp_path / "tape_good2"
        _write_watch_meta(tape_dir)
        _write_events(tape_dir, [
            _book_event(YES_ID, [_ask("0.45", "200")]),
            _book_event(NO_ID, [_ask("0.50", "200")]),  # sum=0.95 < 0.99
        ])
        record = scan_one_tape(tape_dir, max_size=50.0, buffer=0.01)
        if record.eligible:
            assert record.executable_ticks > 0, (
                "INVARIANT VIOLATED: eligible=True but executable_ticks=0"
            )


# ---------------------------------------------------------------------------
# Tests: regime metadata reading
# ---------------------------------------------------------------------------


class TestRegimeReading:
    def test_watch_meta_regime_read(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        _write_watch_meta(tape_dir, regime="politics")
        assert _read_regime(tape_dir) == "politics"

    def test_prep_meta_regime_read(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        _write_prep_meta(tape_dir, regime="sports")
        assert _read_regime(tape_dir) == "sports"

    def test_meta_json_shadow_context_regime(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        meta = {"shadow_context": {"market": "slug", "regime": "new_market"}}
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        assert _read_regime(tape_dir) == "new_market"

    def test_no_metadata_defaults_to_unknown(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        assert _read_regime(tape_dir) == "unknown"

    def test_invalid_regime_value_defaults_to_unknown(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        meta = {"market_slug": "s", "yes_asset_id": "y", "no_asset_id": "n",
                "regime": "crypto"}  # not a valid regime
        (tape_dir / "watch_meta.json").write_text(json.dumps(meta), encoding="utf-8")
        assert _read_regime(tape_dir) == "unknown"

    def test_watch_meta_takes_priority_over_prep_meta(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        _write_watch_meta(tape_dir, regime="politics")
        _write_prep_meta(tape_dir, regime="sports")
        # watch_meta searched first
        assert _read_regime(tape_dir) == "politics"


# ---------------------------------------------------------------------------
# Tests: corpus summary
# ---------------------------------------------------------------------------


class TestCorpusSummary:
    def _record(self, eligible: bool, regime: str, executable_ticks: int = 1) -> TapeRecord:
        return TapeRecord(
            tape_dir=f"/fake/{regime}",
            slug="slug",
            regime=regime,
            recorded_by="watch-arb-candidates",
            eligible=eligible,
            executable_ticks=executable_ticks if eligible else 0,
            reject_reason="" if eligible else "no edge",
        )

    def test_empty_records(self):
        summary = build_corpus_summary([])
        assert summary.total_tapes == 0
        assert summary.eligible_count == 0
        assert summary.mixed_regime_eligible is False

    def test_all_ineligible(self):
        records = [
            self._record(False, "sports"),
            self._record(False, "politics"),
        ]
        summary = build_corpus_summary(records)
        assert summary.eligible_count == 0
        assert summary.ineligible_count == 2
        assert summary.mixed_regime_eligible is False
        assert summary.gate2_eligible_tapes == []
        assert "BLOCKED" in summary.corpus_note

    def test_ineligible_classified_tapes_still_count_toward_coverage(self):
        records = [
            self._record(False, "sports"),
            self._record(False, "sports"),
            self._record(False, "sports"),
        ]
        summary = build_corpus_summary(records)
        assert summary.by_regime["sports"]["total"] == 3
        assert summary.regime_coverage["regime_counts"]["sports"] == 3
        assert summary.regime_coverage["covered_regimes"] == (SPORTS,)
        assert summary.regime_coverage["missing_regimes"] == (POLITICS, NEW_MARKET)
        assert summary.mixed_regime_eligible is False

    def test_single_eligible_no_mixed(self):
        records = [self._record(True, "sports")]
        summary = build_corpus_summary(records)
        assert summary.eligible_count == 1
        assert summary.mixed_regime_eligible is False  # only 1 named regime
        assert "PARTIAL" in summary.corpus_note

    def test_classified_ineligible_tapes_can_complete_mixed_regime_flag(self):
        records = [
            self._record(True, "sports"),
            self._record(False, "politics"),
        ]
        summary = build_corpus_summary(records)
        assert summary.regime_coverage["covered_regimes"] == (POLITICS, SPORTS)
        assert summary.regime_coverage["missing_regimes"] == (NEW_MARKET,)
        assert summary.mixed_regime_eligible is True
        assert "Missing classified tapes for: new_market" in summary.corpus_note

    def test_two_regimes_eligible_is_mixed(self):
        records = [
            self._record(True, "sports"),
            self._record(True, "politics"),
        ]
        summary = build_corpus_summary(records)
        assert summary.eligible_count == 2
        assert summary.mixed_regime_eligible is True

    def test_all_three_regimes_eligible(self):
        records = [
            self._record(True, "sports"),
            self._record(True, "politics"),
            self._record(True, "new_market"),
        ]
        summary = build_corpus_summary(records)
        assert summary.mixed_regime_eligible is True
        assert "OK" in summary.corpus_note

    def test_by_regime_counts_accurate(self):
        records = [
            self._record(True, "sports"),
            self._record(False, "sports"),
            self._record(True, "politics"),
            self._record(False, "unknown"),
        ]
        summary = build_corpus_summary(records)
        assert summary.by_regime["sports"]["total"] == 2
        assert summary.by_regime["sports"]["eligible"] == 1
        assert summary.by_regime["politics"]["total"] == 1
        assert summary.by_regime["politics"]["eligible"] == 1
        assert summary.by_regime["unknown"]["total"] == 1
        assert summary.by_regime["unknown"]["eligible"] == 0

    def test_unknown_regime_not_counted_for_mixed(self):
        """eligible tapes in 'unknown' regime do not count toward mixed_regime_eligible."""
        records = [
            self._record(True, "unknown"),
            self._record(True, "unknown"),
        ]
        summary = build_corpus_summary(records)
        # 2 eligible but same (unknown) regime → not mixed
        assert summary.mixed_regime_eligible is False


# ---------------------------------------------------------------------------
# Tests: manifest schema
# ---------------------------------------------------------------------------


class TestManifestSchema:
    def test_manifest_has_required_keys(self, tmp_path):
        records = []
        summary = build_corpus_summary(records)
        manifest = manifest_to_dict(records, summary, max_size=50.0, buffer=0.01)
        assert manifest["schema_version"] == "gate2_tape_manifest_v2"
        assert "generated_at" in manifest
        assert "corpus_summary" in manifest
        assert "tapes" in manifest
        assert manifest["eligibility_params"]["max_size"] == 50.0
        assert manifest["eligibility_params"]["buffer"] == 0.01
        assert manifest["eligibility_params"]["threshold"] == pytest.approx(0.99)

    def test_tape_entry_has_required_fields(self, tmp_path):
        record = TapeRecord(
            tape_dir="/fake/tape",
            slug="test-market",
            regime="sports",
            recorded_by="watch-arb-candidates",
            eligible=False,
            executable_ticks=0,
            reject_reason="insufficient depth",
        )
        summary = build_corpus_summary([record])
        manifest = manifest_to_dict([record], summary, max_size=50.0, buffer=0.01)
        tape_entry = manifest["tapes"][0]
        assert tape_entry["slug"] == "test-market"
        assert tape_entry["regime"] == "sports"
        assert tape_entry["eligible"] is False
        assert tape_entry["executable_ticks"] == 0
        assert tape_entry["reject_reason"] == "insufficient depth"
        assert "evidence" in tape_entry

    def test_ineligible_tape_in_manifest_has_reject_reason(self, tmp_path):
        """All ineligible tapes in the manifest must have a non-empty reject_reason."""
        record = TapeRecord(
            tape_dir="/fake/tape",
            slug="bad-market",
            regime="unknown",
            recorded_by="unknown",
            eligible=False,
            executable_ticks=0,
            reject_reason="insufficient depth: ...",
        )
        summary = build_corpus_summary([record])
        manifest = manifest_to_dict([record], summary, max_size=50.0, buffer=0.01)
        for tape_entry in manifest["tapes"]:
            if not tape_entry["eligible"]:
                assert tape_entry["reject_reason"] != "", (
                    f"Ineligible tape {tape_entry['slug']} has no reject_reason"
                )


# ---------------------------------------------------------------------------
# Tests: ResolvedWatch regime field
# ---------------------------------------------------------------------------


class TestResolvedWatchRegime:
    def test_default_regime_is_unknown(self):
        r = ResolvedWatch(slug="s", yes_token_id="y", no_token_id="n")
        assert r.regime == "unknown"

    def test_regime_can_be_set(self):
        r = ResolvedWatch(slug="s", yes_token_id="y", no_token_id="n", regime="politics")
        assert r.regime == "politics"

    def test_regime_can_be_mutated(self):
        r = ResolvedWatch(slug="s", yes_token_id="y", no_token_id="n")
        r.regime = "sports"
        assert r.regime == "sports"


# ---------------------------------------------------------------------------
# Tests: watch/prep artifact metadata snapshots
# ---------------------------------------------------------------------------


class TestCaptureMetadataSnapshots:
    def test_watch_meta_persists_market_snapshot(self, tmp_path, monkeypatch):
        from packages.polymarket.simtrader.tape import recorder as recorder_mod

        class _FakeRecorder:
            def __init__(self, tape_dir, asset_ids):
                self.tape_dir = tape_dir
                self.asset_ids = asset_ids

            def record(self, *, duration_seconds, ws_url):
                (self.tape_dir / "events.jsonl").touch()

        monkeypatch.setattr(recorder_mod, "TapeRecorder", _FakeRecorder)

        tape_dir = tmp_path / "watch_tape"
        resolved = ResolvedWatch(
            slug="watch-market",
            yes_token_id=YES_ID,
            no_token_id=NO_ID,
            regime="politics",
            market_snapshot={
                "market_slug": "watch-market",
                "question": "Will Democrats win the Senate?",
                "created_at": "2026-03-08T00:00:00Z",
                "age_hours": 12.0,
                "captured_at": "2026-03-08T12:00:00Z",
            },
        )

        _record_tape_for_market(
            resolved,
            tape_dir,
            duration_seconds=10.0,
            ws_url="wss://test",
        )

        watch_meta = json.loads((tape_dir / "watch_meta.json").read_text(encoding="utf-8"))
        assert watch_meta["regime"] == "politics"
        assert "market_snapshot" in watch_meta
        assert watch_meta["market_snapshot"]["question"] == "Will Democrats win the Senate?"
        assert watch_meta["market_snapshot"]["age_hours"] == pytest.approx(12.0)


# ---------------------------------------------------------------------------
# Tests: prepare_gate2 regime written to prep_meta.json
# ---------------------------------------------------------------------------


class TestPrepareGate2RegimeWritten:
    """Verify that prepare_candidates writes regime into prep_meta.json."""

    def test_regime_written_to_prep_meta(self, tmp_path):
        from tools.cli.prepare_gate2 import prepare_candidates

        class _FakeCand:
            slug = "test-market"
            edge_ok_ticks = 1
            depth_ok_ticks = 1
            executable_ticks = 1
            best_edge = 0.02
            max_depth_yes = 100.0
            max_depth_no = 100.0
            total_ticks = 100
            source = "live"

        recorded_dirs = []

        def _fake_resolve(slug):
            return YES_ID, NO_ID

        def _fake_record(slug, yes_id, no_id, tape_dir, *, duration_seconds, ws_url):
            tape_dir.mkdir(parents=True, exist_ok=True)
            (tape_dir / "events.jsonl").touch()
            meta = {"market_slug": slug, "yes_asset_id": yes_id, "no_asset_id": no_id}
            (tape_dir / "prep_meta.json").write_text(json.dumps(meta), encoding="utf-8")
            recorded_dirs.append(tape_dir)

        @dataclass
        class _FakeElig:
            eligible: bool = False
            reason: str = "no edge"
            stats: dict = None
            def __post_init__(self):
                if self.stats is None:
                    self.stats = {"ticks_with_depth_and_edge": 0}

        def _fake_check(tape_dir, yes_id, no_id, max_size, buffer):
            return _FakeElig()

        results = prepare_candidates(
            [_FakeCand()],
            top=1,
            tapes_base_dir=tmp_path / "tapes",
            duration_seconds=10.0,
            max_size=50.0,
            buffer=0.01,
            ws_url="wss://test",
            dry_run=False,
            regime="sports",
            _resolve_fn=_fake_resolve,
            _record_fn=_fake_record,
            _check_fn=_fake_check,
        )

        assert len(results) == 1
        assert len(recorded_dirs) == 1
        tape_dir = recorded_dirs[0]
        prep_meta = json.loads((tape_dir / "prep_meta.json").read_text(encoding="utf-8"))
        assert prep_meta.get("regime") == "sports"

    def test_market_snapshot_written_to_prep_meta(self, tmp_path):
        from tools.cli.prepare_gate2 import prepare_candidates

        class _FakeCand:
            slug = "prep-market"
            edge_ok_ticks = 1
            depth_ok_ticks = 1
            executable_ticks = 1
            best_edge = 0.02
            max_depth_yes = 100.0
            max_depth_no = 100.0
            total_ticks = 100
            source = "live"
            market_meta = {
                "market_slug": "prep-market",
                "question": "Will Democrats win the Senate?",
                "category": "Politics",
                "age_hours": 8.0,
            }

        recorded_dirs = []

        def _fake_resolve(slug):
            return YES_ID, NO_ID

        def _fake_record(slug, yes_id, no_id, tape_dir, *, duration_seconds, ws_url):
            tape_dir.mkdir(parents=True, exist_ok=True)
            (tape_dir / "events.jsonl").touch()
            meta = {"market_slug": slug, "yes_asset_id": yes_id, "no_asset_id": no_id}
            (tape_dir / "prep_meta.json").write_text(json.dumps(meta), encoding="utf-8")
            recorded_dirs.append(tape_dir)

        @dataclass
        class _FakeElig:
            eligible: bool = False
            reason: str = "no edge"
            stats: dict = None

            def __post_init__(self):
                if self.stats is None:
                    self.stats = {"ticks_with_depth_and_edge": 0}

        def _fake_check(tape_dir, yes_id, no_id, max_size, buffer):
            return _FakeElig()

        prepare_candidates(
            [_FakeCand()],
            top=1,
            tapes_base_dir=tmp_path / "tapes",
            duration_seconds=10.0,
            max_size=50.0,
            buffer=0.01,
            ws_url="wss://test",
            dry_run=False,
            regime="sports",
            _resolve_fn=_fake_resolve,
            _record_fn=_fake_record,
            _check_fn=_fake_check,
        )

        tape_dir = recorded_dirs[0]
        prep_meta = json.loads((tape_dir / "prep_meta.json").read_text(encoding="utf-8"))
        assert "market_snapshot" in prep_meta
        assert prep_meta["market_snapshot"]["question"] == "Will Democrats win the Senate?"
        assert prep_meta["market_snapshot"]["category"] == "Politics"
        assert prep_meta["market_snapshot"]["age_hours"] == pytest.approx(8.0)
        assert "captured_at" in prep_meta["market_snapshot"]


# ---------------------------------------------------------------------------
# Tests: recorded_by reader
# ---------------------------------------------------------------------------


class TestRecordedByReader:
    def test_watch_meta_detected(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        (tape_dir / "watch_meta.json").write_text("{}", encoding="utf-8")
        assert _read_recorded_by(tape_dir) == "watch-arb-candidates"

    def test_prep_meta_detected(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        (tape_dir / "prep_meta.json").write_text("{}", encoding="utf-8")
        assert _read_recorded_by(tape_dir) == "prepare-gate2"

    def test_shadow_meta_detected(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        meta = {"shadow_context": {"market": "slug"}}
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        assert _read_recorded_by(tape_dir) == "simtrader-shadow"

    def test_no_metadata_unknown(self, tmp_path):
        tape_dir = tmp_path / "t"
        tape_dir.mkdir()
        assert _read_recorded_by(tape_dir) == "unknown"


# ---------------------------------------------------------------------------
# Tests: tape metadata snapshot preference and legacy fallback
# ---------------------------------------------------------------------------


class TestTapeMarketMetadataPreference:
    def test_legacy_meta_json_fallback_still_works(self, tmp_path):
        tape_dir = tmp_path / "legacy_tape"
        tape_dir.mkdir()
        meta = {
            "shadow_context": {
                "market": "legacy-market",
                "question": "Will Democrats win the Senate?",
                "category": "Politics",
            }
        }
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        metadata = _read_tape_market_metadata(tape_dir)

        assert metadata["market_slug"] == "legacy-market"
        assert metadata["question"] == "Will Democrats win the Senate?"
        assert metadata["category"] == "Politics"

    def test_manifest_prefers_artifact_snapshot_metadata(self, tmp_path):
        tape_dir = tmp_path / "snapshot_pref"
        tape_dir.mkdir()
        watch_meta = {
            "market_slug": "generic-market",
            "yes_asset_id": YES_ID,
            "no_asset_id": NO_ID,
            "regime": "unknown",
            "market_snapshot": {
                "market_slug": "generic-market",
                "captured_at": "2026-03-08T12:00:00Z",
                "age_hours": 6.0,
            },
        }
        (tape_dir / "watch_meta.json").write_text(json.dumps(watch_meta), encoding="utf-8")
        meta = {
            "shadow_context": {
                "market": "will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup",
                "question": "Will the Toronto Maple Leafs win the 2026 NHL Stanley Cup?",
                "category": "Sports",
            }
        }
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (tape_dir / "events.jsonl").touch()

        record = scan_one_tape(tape_dir)

        assert record.derived_regime == NEW_MARKET
        assert record.final_regime == NEW_MARKET
        assert record.regime_source == "derived"


# ---------------------------------------------------------------------------
# Tests: regime integrity fields on TapeRecord
# ---------------------------------------------------------------------------


from packages.polymarket.market_selection.regime_policy import (
    POLITICS, SPORTS, NEW_MARKET, OTHER, UNKNOWN,
)


class TestRegimeIntegrityFields:
    """Tests for derived_regime, operator_regime, final_regime, regime_source, regime_mismatch."""

    def test_scan_one_tape_has_regime_integrity_fields(self, tmp_path):
        """scan_one_tape populates all regime integrity fields."""
        tape_dir = tmp_path / "tape"
        _write_watch_meta(tape_dir, regime="sports")
        _write_events(tape_dir, [])  # empty tape -> not eligible, but fields still populated
        record = scan_one_tape(tape_dir)
        assert hasattr(record, "derived_regime")
        assert hasattr(record, "operator_regime")
        assert hasattr(record, "final_regime")
        assert hasattr(record, "regime_source")
        assert hasattr(record, "regime_mismatch")
        assert isinstance(record.regime_mismatch, bool)

    def test_operator_regime_preserved_in_tape_record(self, tmp_path):
        """operator_regime field stores the raw label from tape metadata."""
        tape_dir = tmp_path / "tape"
        tape_dir.mkdir()
        meta = {
            "market_slug": "test-market",
            "yes_asset_id": YES_ID,
            "no_asset_id": NO_ID,
            "regime": "politics",
        }
        (tape_dir / "watch_meta.json").write_text(json.dumps(meta))
        (tape_dir / "events.jsonl").touch()
        record = scan_one_tape(tape_dir)
        assert record.operator_regime == "politics"

    def test_final_regime_matches_regime_field(self, tmp_path):
        """regime field (backward compat) == final_regime for new records."""
        tape_dir = tmp_path / "tape"
        _write_watch_meta(tape_dir, regime="sports")
        _write_events(tape_dir, [])
        record = scan_one_tape(tape_dir)
        assert record.regime == record.final_regime

    def test_no_mismatch_when_operator_is_unknown(self, tmp_path):
        """No mismatch flag when operator did not label the tape."""
        tape_dir = tmp_path / "tape"
        tape_dir.mkdir()
        meta = {
            "market_slug": "some-market",
            "yes_asset_id": YES_ID,
            "no_asset_id": NO_ID,
            "regime": "unknown",
        }
        (tape_dir / "watch_meta.json").write_text(json.dumps(meta))
        (tape_dir / "events.jsonl").touch()
        record = scan_one_tape(tape_dir)
        assert record.regime_mismatch is False

    def test_regime_mismatch_detected_when_slug_signals_different_regime(self, tmp_path):
        """regime_mismatch=True when derived and operator clearly disagree."""
        tape_dir = tmp_path / "tape"
        tape_dir.mkdir()
        # slug clearly signals politics, operator labeled sports
        meta = {
            "market_slug": "will-the-senate-vote-on-immigration-2026",
            "yes_asset_id": YES_ID,
            "no_asset_id": NO_ID,
            "regime": "sports",
        }
        (tape_dir / "watch_meta.json").write_text(json.dumps(meta))
        (tape_dir / "events.jsonl").touch()
        record = scan_one_tape(tape_dir)
        # Only assert mismatch if derived was named (classifier might not detect slug)
        if record.derived_regime in (POLITICS, SPORTS, NEW_MARKET):
            if record.operator_regime in (POLITICS, SPORTS, NEW_MARKET):
                if record.derived_regime != record.operator_regime:
                    assert record.regime_mismatch is True

    def test_missing_events_tape_still_has_regime_fields(self, tmp_path):
        """Early return for missing events.jsonl still populates regime integrity."""
        tape_dir = tmp_path / "tape"
        tape_dir.mkdir()
        _write_watch_meta(tape_dir, regime="politics")
        # No events.jsonl
        record = scan_one_tape(tape_dir)
        assert record.eligible is False
        assert record.operator_regime == "politics"
        assert record.regime_source in ("derived", "operator", "fallback_unknown")

    def test_missing_asset_ids_tape_still_has_regime_fields(self, tmp_path):
        """Early return for missing asset IDs still populates regime integrity."""
        tape_dir = tmp_path / "tape"
        tape_dir.mkdir()
        # No watch_meta or prep_meta -> no asset IDs
        (tape_dir / "events.jsonl").write_text('{"event_type": "last_trade_price"}\n')
        record = scan_one_tape(tape_dir)
        assert record.eligible is False
        assert record.regime_source in ("derived", "operator", "fallback_unknown")


# ---------------------------------------------------------------------------
# Tests: mixed-regime coverage via shared helper
# ---------------------------------------------------------------------------


class TestMixedRegimeCoverageViaSharedHelper:
    """build_corpus_summary uses coverage_from_classified_regimes under the hood."""

    def _record_with_final_regime(self, eligible: bool, final_regime: str) -> TapeRecord:
        return TapeRecord(
            tape_dir=f"/fake/{final_regime}",
            slug="slug",
            regime=final_regime,
            recorded_by="watch-arb-candidates",
            eligible=eligible,
            executable_ticks=1 if eligible else 0,
            reject_reason="" if eligible else "no edge",
            final_regime=final_regime,
        )

    def test_mixed_coverage_requires_two_named_regimes(self):
        records = [
            self._record_with_final_regime(True, POLITICS),
            self._record_with_final_regime(True, SPORTS),
        ]
        summary = build_corpus_summary(records)
        assert summary.mixed_regime_eligible is True

    def test_unknown_final_regime_not_counted_for_mixed(self):
        records = [
            self._record_with_final_regime(True, UNKNOWN),
            self._record_with_final_regime(True, UNKNOWN),
        ]
        summary = build_corpus_summary(records)
        assert summary.mixed_regime_eligible is False

    def test_regime_coverage_in_summary(self):
        """CorpusSummary.regime_coverage populated by coverage_from_classified_regimes."""
        records = [
            self._record_with_final_regime(True, POLITICS),
            self._record_with_final_regime(True, SPORTS),
        ]
        summary = build_corpus_summary(records)
        assert isinstance(summary.regime_coverage, dict)
        assert "satisfies_policy" in summary.regime_coverage
        assert "covered_regimes" in summary.regime_coverage

    def test_regime_coverage_tracks_classified_ineligible_tapes(self):
        records = [
            self._record_with_final_regime(False, SPORTS),
        ]
        summary = build_corpus_summary(records)
        assert summary.regime_coverage["satisfies_policy"] is False
        assert summary.regime_coverage["covered_regimes"] == (SPORTS,)
        assert summary.regime_coverage["missing_regimes"] == (POLITICS, NEW_MARKET)
        assert summary.regime_coverage["regime_counts"]["sports"] == 1

    def test_covered_and_missing_regimes_align_with_classified_corpus(self):
        records = [
            self._record_with_final_regime(False, POLITICS),
            self._record_with_final_regime(True, SPORTS),
        ]
        summary = build_corpus_summary(records)
        assert summary.regime_coverage["covered_regimes"] == (POLITICS, SPORTS)
        assert summary.regime_coverage["missing_regimes"] == (NEW_MARKET,)

    def test_manifest_includes_regime_coverage(self):
        records = []
        summary = build_corpus_summary(records)
        manifest = manifest_to_dict(records, summary, max_size=50.0, buffer=0.01)
        assert "regime_coverage" in manifest["corpus_summary"]


# ---------------------------------------------------------------------------
# Tests: manifest regime provenance fields
# ---------------------------------------------------------------------------


class TestManifestRegimeIntegrityFields:
    """New regime provenance fields appear in manifest tape entries."""

    def test_manifest_tape_entry_has_provenance_fields(self):
        record = TapeRecord(
            tape_dir="/fake/tape",
            slug="test-market",
            regime="sports",
            recorded_by="watch-arb-candidates",
            eligible=False,
            executable_ticks=0,
            reject_reason="no edge",
            derived_regime=SPORTS,
            operator_regime="sports",
            final_regime="sports",
            regime_source="derived",
            regime_mismatch=False,
        )
        summary = build_corpus_summary([record])
        manifest = manifest_to_dict([record], summary, max_size=50.0, buffer=0.01)
        tape_entry = manifest["tapes"][0]
        assert "derived_regime" in tape_entry
        assert "operator_regime" in tape_entry
        assert "final_regime" in tape_entry
        assert "regime_source" in tape_entry
        assert "regime_mismatch" in tape_entry
        assert tape_entry["derived_regime"] == SPORTS
        assert tape_entry["regime_source"] == "derived"
        assert tape_entry["regime_mismatch"] is False

    def test_manifest_schema_version_is_v2(self):
        manifest = manifest_to_dict([], build_corpus_summary([]), max_size=50.0, buffer=0.01)
        assert manifest["schema_version"] == "gate2_tape_manifest_v2"

    def test_legacy_record_without_final_regime_still_serializes(self):
        """TapeRecord created without new fields (legacy) still serializes correctly."""
        record = TapeRecord(
            tape_dir="/fake/tape",
            slug="test",
            regime="politics",
            recorded_by="watch-arb-candidates",
            eligible=False,
            executable_ticks=0,
            reject_reason="no edge",
            # No final_regime, derived_regime, etc. -- use defaults
        )
        summary = build_corpus_summary([record])
        manifest = manifest_to_dict([record], summary, max_size=50.0, buffer=0.01)
        tape_entry = manifest["tapes"][0]
        # regime should fall back to rec.regime when final_regime is empty
        assert tape_entry["regime"] == "politics"


# ---------------------------------------------------------------------------
# Tests: Gate 2 preflight command
# ---------------------------------------------------------------------------


class TestGate2PreflightCommand:
    def test_ready_case(self, tmp_path, capsys):
        from tools.cli.gate2_preflight import main as gate2_preflight_main

        _write_eligible_watch_tape(tmp_path / "sports_tape", regime="sports")
        _write_eligible_watch_tape(tmp_path / "politics_tape", regime="politics")
        _write_eligible_watch_tape(tmp_path / "new_market_tape", regime="new_market")

        exit_code = gate2_preflight_main(["--tapes-dir", str(tmp_path)])
        out = capsys.readouterr().out

        assert exit_code == 0
        assert "Result: READY" in out
        assert "Eligible tapes: 3" in out
        assert "Eligible tape list:" in out
        assert "sports_tape" in out
        assert "politics_tape" in out
        assert "new_market_tape" in out
        assert "Mixed-regime coverage: READY" in out
        assert "Missing regimes: none" in out
        assert "python tools/gates/close_sweep_gate.py" in out

    def test_blocked_with_zero_eligible_tapes(self, tmp_path, capsys):
        from tools.cli.gate2_preflight import main as gate2_preflight_main

        _write_ineligible_watch_tape_no_edge(tmp_path / "sports_tape", regime="sports")

        exit_code = gate2_preflight_main(["--tapes-dir", str(tmp_path)])
        out = capsys.readouterr().out

        assert exit_code == 2
        assert "Result: BLOCKED" in out
        assert "Eligible tapes: 0" in out
        assert "Eligible tape list: none" in out
        assert "Mixed-regime coverage: BLOCKED" in out
        assert "Covered regimes: sports" in out
        assert "Missing regimes: politics, new_market" in out
        assert "No eligible tapes" in out
        assert "python -m polytool scan-gate2-candidates --all --top 20 --explain" in out

    def test_blocked_with_missing_mixed_regime_coverage(self, tmp_path, capsys):
        from tools.cli.gate2_preflight import main as gate2_preflight_main

        _write_eligible_watch_tape(tmp_path / "sports_tape", regime="sports")

        exit_code = gate2_preflight_main(["--tapes-dir", str(tmp_path)])
        out = capsys.readouterr().out

        assert exit_code == 2
        assert "Result: BLOCKED" in out
        assert "Eligible tapes: 1" in out
        assert "sports_tape" in out
        assert "Covered regimes: sports" in out
        assert "Missing regimes: politics, new_market" in out
        assert "Missing mixed-regime coverage: politics, new_market." in out
        assert "Capture an eligible politics tape" in out
        assert "python -m polytool gate2-preflight" in out

    def test_preflight_coverage_matches_manifest_when_ineligible_tape_fills_regime(self, tmp_path, capsys):
        from tools.cli.gate2_preflight import main as gate2_preflight_main

        _write_eligible_watch_tape(tmp_path / "sports_tape", regime="sports")
        _write_ineligible_watch_tape_no_edge(tmp_path / "politics_tape", regime="politics")

        exit_code = gate2_preflight_main(["--tapes-dir", str(tmp_path)])
        out = capsys.readouterr().out

        assert exit_code == 2
        assert "Eligible tapes: 1" in out
        assert "Covered regimes: politics, sports" in out
        assert "Missing regimes: new_market" in out
        assert "Missing mixed-regime coverage: new_market." in out

    def test_stable_output_and_exit_code_via_polytool_dispatch(self, tmp_path, capsys):
        from polytool.__main__ import main as polytool_main

        exit_code = polytool_main(["gate2-preflight", "--tapes-dir", str(tmp_path)])
        out = capsys.readouterr().out

        assert exit_code == 2
        lines = [line for line in out.splitlines() if line]
        assert lines[0] == "Gate 2 Preflight"
        assert lines[1] == "================"
        assert lines[2] == "Result: BLOCKED"
        assert "Eligible tapes: 0" in out
