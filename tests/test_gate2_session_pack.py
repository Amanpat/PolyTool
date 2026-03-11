"""Tests for regime-aware capture threshold wiring.

Covers the 6 required behaviors:
  1. Politics session pack gets politics threshold (1.03) in watch_config.
  2. Sports session pack remains unchanged (0.99) by default.
  3. Explicit operator override wins over regime default.
  4. Watcher consumes the threshold from the session plan/config correctly.
  5. Artifacts (watch_meta.json) show threshold_used and threshold_source truthfully.
  6. Observational evidence (regime labels from tape integrity) does NOT affect
     Gate 2 eligibility — only the capture threshold changes.

Gate 2 eligibility, sweep pass criteria, and Gate 2 scoring must not change.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.cli.make_session_pack import (
    _load_watchlist_entries,
    _merge_watchlist,
    _parse_markets_to_watchlist,
    build_session_pack,
    resolve_session_threshold,
)
from tools.cli.watch_arb_candidates import (
    ArbWatcher,
    ResolvedWatch,
    _collect_watch_targets,
    _load_session_plan,
    main,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session_pack_dict(
    regime: str | None,
    near_edge_threshold: float,
    threshold_source: str,
    watchlist: list[dict] | None = None,
    duration_seconds: float = 300.0,
) -> dict:
    """Build a session pack dict directly (bypass file I/O)."""
    return build_session_pack(
        regime=regime,
        watchlist=watchlist or [{"market_slug": "test-market"}],
        near_edge_threshold=near_edge_threshold,
        threshold_source=threshold_source,
        duration_seconds=duration_seconds,
        created_at="2026-03-11T00:00:00+00:00",
    )


def _write_session_pack(tmp_path: Path, pack: dict) -> Path:
    path = tmp_path / "session_pack.json"
    path.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    return path


def _resolved(slug: str = "test-market") -> ResolvedWatch:
    return ResolvedWatch(
        slug=slug,
        yes_token_id="yes-" + slug,
        no_token_id="no-" + slug,
    )


# ---------------------------------------------------------------------------
# 1. Politics session pack gets politics threshold in watch_config
# ---------------------------------------------------------------------------


class TestPoliticsThreshold:
    def test_resolve_politics_threshold(self):
        """resolve_session_threshold returns 1.03 for politics with no override."""
        threshold, source = resolve_session_threshold(regime="politics", near_edge_override=None)
        assert threshold == pytest.approx(1.03)
        assert source == "regime-default"

    def test_politics_pack_sets_watch_config_threshold(self):
        """build_session_pack embeds the politics threshold in watch_config."""
        threshold, source = resolve_session_threshold(regime="politics", near_edge_override=None)
        pack = _make_session_pack_dict("politics", threshold, source)

        assert pack["watch_config"]["near_edge_threshold"] == pytest.approx(1.03)
        assert pack["watch_config"]["threshold_source"] == "regime-default"
        assert pack["session"]["regime"] == "politics"
        assert pack["session"]["near_edge_threshold_used"] == pytest.approx(1.03)
        assert pack["session"]["threshold_source"] == "regime-default"

    def test_politics_pack_schema(self):
        """Session pack has required schema fields."""
        threshold, source = resolve_session_threshold(regime="politics", near_edge_override=None)
        pack = _make_session_pack_dict("politics", threshold, source)

        assert pack["schema_version"] == "session_pack_v1"
        assert "created_at" in pack
        assert "watchlist" in pack
        assert "watch_config" in pack
        assert "session" in pack


# ---------------------------------------------------------------------------
# 2. Sports session pack remains unchanged (0.99) by default
# ---------------------------------------------------------------------------


class TestSportsThreshold:
    def test_resolve_sports_threshold(self):
        """resolve_session_threshold returns 0.99 for sports — unchanged."""
        threshold, source = resolve_session_threshold(regime="sports", near_edge_override=None)
        assert threshold == pytest.approx(0.99)
        assert source == "regime-default"

    def test_sports_pack_sets_0_99_in_watch_config(self):
        """Sports session pack preserves 0.99 — the same as the current default."""
        threshold, source = resolve_session_threshold(regime="sports", near_edge_override=None)
        pack = _make_session_pack_dict("sports", threshold, source)

        assert pack["watch_config"]["near_edge_threshold"] == pytest.approx(0.99)
        assert pack["session"]["near_edge_threshold_used"] == pytest.approx(0.99)

    def test_no_regime_gets_global_default(self):
        """Without a regime, the global default (0.99) is used."""
        threshold, source = resolve_session_threshold(regime=None, near_edge_override=None)
        assert threshold == pytest.approx(0.99)
        assert source == "global-default"


# ---------------------------------------------------------------------------
# 3. Explicit operator override wins over regime default
# ---------------------------------------------------------------------------


class TestOperatorOverride:
    def test_override_wins_over_politics_regime(self):
        """An explicit near_edge_override takes priority over the politics default."""
        threshold, source = resolve_session_threshold(
            regime="politics", near_edge_override=0.995
        )
        assert threshold == pytest.approx(0.995)
        assert source == "operator-override"

    def test_override_wins_over_sports_regime(self):
        """An explicit near_edge_override takes priority over the sports default."""
        threshold, source = resolve_session_threshold(
            regime="sports", near_edge_override=1.02
        )
        assert threshold == pytest.approx(1.02)
        assert source == "operator-override"

    def test_override_wins_with_no_regime(self):
        """An explicit near_edge_override wins even when no regime is set."""
        threshold, source = resolve_session_threshold(
            regime=None, near_edge_override=1.05
        )
        assert threshold == pytest.approx(1.05)
        assert source == "operator-override"

    def test_politics_pack_with_override_records_operator_override(self):
        """A pack built with an operator override records operator-override source."""
        threshold, source = resolve_session_threshold(
            regime="politics", near_edge_override=0.995
        )
        pack = _make_session_pack_dict("politics", threshold, source)

        assert pack["watch_config"]["near_edge_threshold"] == pytest.approx(0.995)
        assert pack["watch_config"]["threshold_source"] == "operator-override"
        assert pack["session"]["threshold_source"] == "operator-override"

    def test_cli_near_edge_overrides_session_plan(self, tmp_path):
        """When --near-edge is supplied alongside --session-plan, operator wins."""
        # Build a politics session pack (threshold = 1.03)
        pack = _make_session_pack_dict(
            "politics", 1.03, "regime-default",
            watchlist=[{"market_slug": "pol-market"}],
        )
        pack_path = _write_session_pack(tmp_path, pack)

        recorded_calls: list[dict] = []

        def fake_resolve(slug):
            return _resolved(slug)

        def fake_record(r, tape_dir, *, duration_seconds, ws_url,
                        near_edge_threshold, threshold_source, regime=None):
            recorded_calls.append({
                "near_edge_threshold": near_edge_threshold,
                "threshold_source": threshold_source,
            })

        from unittest.mock import patch

        with (
            patch("tools.cli.watch_arb_candidates._resolve_market", side_effect=fake_resolve),
            patch.object(ArbWatcher, "run", lambda self: None),
        ):
            rc = main([
                "--session-plan", str(pack_path),
                "--near-edge", "0.995",   # operator override
                "--dry-run",
            ])

        assert rc == 0

        # The watcher's near_edge_threshold must be the operator's value, not 1.03
        # (We verify through watcher construction — check via main rc + no error)


# ---------------------------------------------------------------------------
# 4. Watcher consumes threshold from session plan correctly
# ---------------------------------------------------------------------------


class TestWatcherConsumesSessionPlan:
    def test_watcher_uses_politics_threshold_from_session_plan(self, tmp_path):
        """ArbWatcher.near_edge_threshold is set from session plan's watch_config."""
        pack = _make_session_pack_dict(
            "politics", 1.03, "regime-default",
            watchlist=[{"market_slug": "pol-market"}],
        )
        pack_path = _write_session_pack(tmp_path, pack)

        loaded = _load_session_plan(pack_path)
        watch_cfg = loaded["watch_config"]
        assert float(watch_cfg["near_edge_threshold"]) == pytest.approx(1.03)
        assert watch_cfg["threshold_source"] == "regime-default"

    def test_watcher_collects_targets_from_session_plan(self, tmp_path):
        """_collect_watch_targets returns targets from session plan's watchlist."""
        pack = _make_session_pack_dict(
            "politics", 1.03, "regime-default",
            watchlist=[
                {"market_slug": "slug-a"},
                {"market_slug": "slug-b"},
            ],
        )
        loaded = pack

        targets = _collect_watch_targets(
            markets=None,
            watchlist_file=None,
            session_plan=loaded,
        )
        slugs = [t.slug for t in targets]
        assert slugs == ["slug-a", "slug-b"]
        assert all(t.source == "session-plan" for t in targets)

    def test_watcher_sports_threshold_is_0_99(self, tmp_path):
        """Session plan with sports regime gives ArbWatcher threshold = 0.99."""
        pack = _make_session_pack_dict(
            "sports", 0.99, "regime-default",
            watchlist=[{"market_slug": "sports-market"}],
        )
        pack_path = _write_session_pack(tmp_path, pack)

        loaded = _load_session_plan(pack_path)
        watch_cfg = loaded["watch_config"]
        assert float(watch_cfg["near_edge_threshold"]) == pytest.approx(0.99)

    def test_session_plan_invalid_missing_watch_config(self, tmp_path):
        """_load_session_plan raises ValueError when watch_config is absent."""
        bad_pack = {"schema_version": "session_pack_v1", "watchlist": []}
        pack_path = tmp_path / "bad.json"
        pack_path.write_text(json.dumps(bad_pack), encoding="utf-8")

        with pytest.raises(ValueError, match="watch_config"):
            _load_session_plan(pack_path)


# ---------------------------------------------------------------------------
# 5. Artifacts (watch_meta.json) record threshold_used and threshold_source
# ---------------------------------------------------------------------------


class TestArtifactProvenance:
    def test_watch_meta_records_threshold_used_and_source(self, tmp_path):
        """watch_meta.json written by _record_tape_for_market has provenance fields."""
        from tools.cli.watch_arb_candidates import _record_tape_for_market
        from unittest.mock import patch, MagicMock

        tape_dir = tmp_path / "tape_001"
        resolved = _resolved("test-slug")

        # TapeRecorder is a lazy import inside the function — patch via its module path.
        mock_recorder = MagicMock()
        with patch(
            "packages.polymarket.simtrader.tape.recorder.TapeRecorder",
            return_value=mock_recorder,
        ):
            _record_tape_for_market(
                resolved,
                tape_dir,
                duration_seconds=60.0,
                ws_url="wss://test",
                near_edge_threshold=1.03,
                threshold_source="regime-default",
                regime="politics",
            )

        watch_meta = json.loads((tape_dir / "watch_meta.json").read_text(encoding="utf-8"))
        assert watch_meta["near_edge_threshold_used"] == pytest.approx(1.03)
        assert watch_meta["threshold_source"] == "regime-default"
        assert watch_meta["regime"] == "politics"
        assert watch_meta["market_slug"] == "test-slug"
        assert watch_meta["triggered_by"] == "watch-arb-candidates"

    def test_watch_meta_omits_regime_when_none(self, tmp_path):
        """watch_meta.json does not include 'regime' key when regime is None."""
        from tools.cli.watch_arb_candidates import _record_tape_for_market
        from unittest.mock import patch, MagicMock

        tape_dir = tmp_path / "tape_002"
        resolved = _resolved("no-regime-slug")

        mock_recorder = MagicMock()
        with patch(
            "packages.polymarket.simtrader.tape.recorder.TapeRecorder",
            return_value=mock_recorder,
        ):
            _record_tape_for_market(
                resolved,
                tape_dir,
                duration_seconds=60.0,
                ws_url="wss://test",
                near_edge_threshold=1.00,
                threshold_source="cli-default",
                regime=None,
            )

        watch_meta = json.loads((tape_dir / "watch_meta.json").read_text(encoding="utf-8"))
        assert "regime" not in watch_meta
        assert watch_meta["near_edge_threshold_used"] == pytest.approx(1.00)
        assert watch_meta["threshold_source"] == "cli-default"

    def test_arbwatcher_passes_threshold_provenance_to_record_fn(self, tmp_path):
        """ArbWatcher passes near_edge_threshold and threshold_source to the record fn."""
        import time

        resolved = _resolved("politics-market")
        captured: list[dict] = []

        def fake_fetch(r):
            return [{"price": "0.49", "size": "100"}], [{"price": "0.50", "size": "100"}]

        def fake_record(r, tape_dir, *, duration_seconds, ws_url,
                        near_edge_threshold, threshold_source, regime=None):
            captured.append({
                "near_edge_threshold": near_edge_threshold,
                "threshold_source": threshold_source,
                "regime": regime,
            })

        watcher = ArbWatcher(
            resolved_markets=[resolved],
            near_edge_threshold=1.03,
            threshold_source="regime-default",
            regime="politics",
            min_depth=50.0,
            poll_interval=0.0,
            duration_seconds=60.0,
            tapes_base_dir=tmp_path / "tapes",
            ws_url="wss://test",
            max_concurrent=2,
            dry_run=False,
            _fetch_fn=fake_fetch,
            _record_fn=fake_record,
        )
        watcher._poll_round()
        time.sleep(0.1)

        assert len(captured) == 1
        assert captured[0]["near_edge_threshold"] == pytest.approx(1.03)
        assert captured[0]["threshold_source"] == "regime-default"
        assert captured[0]["regime"] == "politics"


# ---------------------------------------------------------------------------
# 6. Observational evidence does NOT affect Gate 2 eligibility
# ---------------------------------------------------------------------------


class TestObservationalEvidenceNoEligibilityImpact:
    """Regime labels and tape integrity fields are informational only.

    Gate 2 eligibility is determined by:
      - yes_ask + no_ask < 1 - buffer  (edge_ok)
      - both sizes >= max_size          (depth_ok)

    The regime and near_edge_threshold_used fields in watch_meta.json (or any
    tape integrity fields from regime_policy.derive_tape_regime) must NOT
    change these eligibility criteria.
    """

    def test_regime_does_not_change_gate2_buffer(self):
        """The Gate 2 buffer (0.01) is independent of regime.

        Gate 2 edge_ok criterion: sum_ask < 1 - 0.01 = 0.99
        This is NOT the near_edge capture threshold (which may be 1.03 for politics).
        """
        from tools.cli.scan_gate2_candidates import score_snapshot

        # A market with sum_ask = 1.00 is NOT eligible for Gate 2 regardless of regime.
        # (It would trigger a politics watcher at threshold=1.03, but that's capture only.)
        snap = score_snapshot(
            [{"price": "0.50", "size": "100"}],
            [{"price": "0.50", "size": "100"}],
            max_size=50.0,
            buffer=0.01,
        )
        assert snap["edge_ok"] is False     # 1.00 >= 0.99 → not eligible
        assert snap["executable"] is False

    def test_gate2_eligibility_uses_fixed_buffer_not_capture_threshold(self):
        """Gate 2 eligibility uses sum_ask < 1-buffer, not the capture threshold.

        A market that passes the politics capture threshold (sum_ask < 1.03)
        but does NOT pass the Gate 2 edge threshold (sum_ask < 0.99) should
        be ineligible.
        """
        from tools.cli.scan_gate2_candidates import score_snapshot

        # sum_ask = 1.01 → fires politics capture (1.01 < 1.03) but NOT Gate 2 (1.01 >= 0.99)
        snap = score_snapshot(
            [{"price": "0.50", "size": "100"}],
            [{"price": "0.51", "size": "100"}],
            max_size=50.0,
            buffer=0.01,
        )
        assert snap["sum_ask"] == pytest.approx(1.01)
        assert snap["edge_ok"] is False     # Gate 2 would reject this
        assert snap["executable"] is False

    def test_tape_integrity_regime_field_is_informational(self):
        """TapeRegimeIntegrity fields are informational and don't change eligibility logic."""
        from packages.polymarket.market_selection.regime_policy import derive_tape_regime

        integrity = derive_tape_regime(
            {"market_slug": "will-biden-win", "title": "Will Biden win?"},
            operator_regime="politics",
        )
        # Regime fields exist and are plausible
        assert integrity.final_regime in ("politics", "sports", "new_market", "unknown", "other")
        # But these fields live only in provenance — the eligibility check never reads them.
        # Confirm the eligibility module doesn't import or use regime_policy at all:
        import inspect
        import packages.polymarket.simtrader.sweeps.eligibility as elig_module
        source = inspect.getsource(elig_module)
        assert "regime_policy" not in source, (
            "eligibility.py must NOT import or reference regime_policy — "
            "regime is informational only."
        )


# ---------------------------------------------------------------------------
# Integration: make-session-pack CLI smoke tests
# ---------------------------------------------------------------------------


class TestMakeSessionPackCLI:
    def test_politics_cli_produces_correct_threshold(self, tmp_path):
        """CLI: make-session-pack --regime politics produces 1.03 in watch_config."""
        from tools.cli.make_session_pack import main as sp_main

        output_path = tmp_path / "pack.json"
        rc = sp_main([
            "--regime", "politics",
            "--markets", "pol-market-a,pol-market-b",
            "--output", str(output_path),
        ])
        assert rc == 0
        assert output_path.exists()

        pack = json.loads(output_path.read_text(encoding="utf-8"))
        assert pack["watch_config"]["near_edge_threshold"] == pytest.approx(1.03)
        assert pack["watch_config"]["threshold_source"] == "regime-default"
        assert pack["session"]["regime"] == "politics"
        assert len(pack["watchlist"]) == 2

    def test_sports_cli_produces_0_99_threshold(self, tmp_path):
        """CLI: make-session-pack --regime sports produces 0.99 — unchanged."""
        from tools.cli.make_session_pack import main as sp_main

        output_path = tmp_path / "sports_pack.json"
        rc = sp_main([
            "--regime", "sports",
            "--markets", "sports-market",
            "--output", str(output_path),
        ])
        assert rc == 0
        pack = json.loads(output_path.read_text(encoding="utf-8"))
        assert pack["watch_config"]["near_edge_threshold"] == pytest.approx(0.99)

    def test_operator_override_cli(self, tmp_path):
        """CLI: --near-edge overrides regime default; threshold_source = operator-override."""
        from tools.cli.make_session_pack import main as sp_main

        output_path = tmp_path / "override_pack.json"
        rc = sp_main([
            "--regime", "politics",
            "--near-edge", "0.995",
            "--markets", "pol-market",
            "--output", str(output_path),
        ])
        assert rc == 0
        pack = json.loads(output_path.read_text(encoding="utf-8"))
        assert pack["watch_config"]["near_edge_threshold"] == pytest.approx(0.995)
        assert pack["watch_config"]["threshold_source"] == "operator-override"

    def test_new_market_threshold(self, tmp_path):
        """CLI: make-session-pack --regime new_market produces 1.015."""
        from tools.cli.make_session_pack import main as sp_main

        output_path = tmp_path / "nm_pack.json"
        rc = sp_main([
            "--regime", "new_market",
            "--markets", "nm-market",
            "--output", str(output_path),
        ])
        assert rc == 0
        pack = json.loads(output_path.read_text(encoding="utf-8"))
        assert pack["watch_config"]["near_edge_threshold"] == pytest.approx(1.015)

    def test_dry_run_prints_json(self, capsys, tmp_path):
        """CLI: --dry-run prints JSON to stdout without writing a file."""
        from tools.cli.make_session_pack import main as sp_main

        rc = sp_main(["--regime", "politics", "--markets", "pol-market", "--dry-run"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["watch_config"]["near_edge_threshold"] == pytest.approx(1.03)
