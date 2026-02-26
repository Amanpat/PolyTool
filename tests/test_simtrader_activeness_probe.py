"""Offline tests for the activeness probe module and its integration with MarketPicker.

All tests are fully offline — no network calls are made.  The WebSocket is never
opened; probe logic is exercised via ``run_from_source`` or mock injection.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Token / market fixtures
# ---------------------------------------------------------------------------

YES_TOKEN = "yes" * 20 + "0001"
NO_TOKEN = "no_" * 20 + "0002"
SLUG = "will-probe-work-2026"
QUESTION = "Will the probe work in 2026?"


def _price_change(asset_id: str) -> dict:
    """Minimal price_change event for *asset_id*."""
    return {"event_type": "price_change", "asset_id": asset_id, "price": "0.5", "size": "10"}


def _batched_price_change(*asset_ids: str) -> dict:
    """Modern batched price_change event covering multiple assets."""
    return {
        "event_type": "price_change",
        "price_changes": [
            {"asset_id": aid, "price": "0.5", "size": "10"} for aid in asset_ids
        ],
    }


def _last_trade(asset_id: str) -> dict:
    return {"event_type": "last_trade_price", "asset_id": asset_id, "price": "0.5"}


def _book_snapshot(asset_id: str) -> dict:
    """Initial book dump — should NOT be counted by the probe."""
    return {"event_type": "book", "asset_id": asset_id, "bids": [], "asks": []}


def _tick_size_change(asset_id: str) -> dict:
    """Tick-size change — should NOT be counted by the probe."""
    return {"event_type": "tick_size_change", "asset_id": asset_id}


# ---------------------------------------------------------------------------
# ProbeResult
# ---------------------------------------------------------------------------


class TestProbeResult:
    def test_active_true_when_updates_meets_min(self):
        from packages.polymarket.simtrader.activeness_probe import ProbeResult

        pr = ProbeResult(token_id=YES_TOKEN, probe_seconds=5.0, updates=3, active=True)
        assert pr.active is True
        assert pr.updates == 3

    def test_active_false(self):
        from packages.polymarket.simtrader.activeness_probe import ProbeResult

        pr = ProbeResult(token_id=NO_TOKEN, probe_seconds=5.0, updates=0, active=False)
        assert pr.active is False


# ---------------------------------------------------------------------------
# ActivenessProbe.run_from_source
# ---------------------------------------------------------------------------


class TestActivenessProbeFromSource:
    def _probe(self, asset_ids=None, min_updates=1):
        from packages.polymarket.simtrader.activeness_probe import ActivenessProbe

        return ActivenessProbe(
            asset_ids=asset_ids or [YES_TOKEN, NO_TOKEN],
            probe_seconds=5.0,
            min_updates=min_updates,
        )

    # ------ baseline ------

    def test_no_events_all_inactive(self):
        results = self._probe().run_from_source([])
        assert YES_TOKEN in results
        assert NO_TOKEN in results
        assert results[YES_TOKEN].active is False
        assert results[YES_TOKEN].updates == 0
        assert results[NO_TOKEN].active is False

    def test_price_change_counts_for_correct_asset(self):
        results = self._probe().run_from_source([_price_change(YES_TOKEN)])
        assert results[YES_TOKEN].updates == 1
        assert results[YES_TOKEN].active is True
        assert results[NO_TOKEN].updates == 0
        assert results[NO_TOKEN].active is False

    def test_last_trade_price_counts(self):
        results = self._probe().run_from_source([_last_trade(NO_TOKEN)])
        assert results[NO_TOKEN].updates == 1
        assert results[NO_TOKEN].active is True
        assert results[YES_TOKEN].updates == 0

    def test_book_event_not_counted(self):
        """Initial book snapshots must not inflate activeness counts."""
        results = self._probe().run_from_source(
            [_book_snapshot(YES_TOKEN), _book_snapshot(NO_TOKEN)]
        )
        assert results[YES_TOKEN].updates == 0
        assert results[NO_TOKEN].updates == 0

    def test_tick_size_change_not_counted(self):
        results = self._probe().run_from_source(
            [_tick_size_change(YES_TOKEN), _tick_size_change(NO_TOKEN)]
        )
        assert results[YES_TOKEN].updates == 0
        assert results[NO_TOKEN].updates == 0

    def test_unknown_asset_id_not_counted(self):
        results = self._probe().run_from_source([_price_change("unknown-token-999")])
        assert results[YES_TOKEN].updates == 0
        assert results[NO_TOKEN].updates == 0

    # ------ batched format ------

    def test_batched_price_changes_counted_per_asset(self):
        evt = _batched_price_change(YES_TOKEN, NO_TOKEN)
        results = self._probe().run_from_source([evt])
        assert results[YES_TOKEN].updates == 1
        assert results[NO_TOKEN].updates == 1

    def test_batched_price_changes_partial_match(self):
        """Only tracked assets within price_changes[] are counted."""
        evt = _batched_price_change(YES_TOKEN, "some-other-token")
        results = self._probe().run_from_source([evt])
        assert results[YES_TOKEN].updates == 1
        assert results[NO_TOKEN].updates == 0

    def test_batched_price_changes_multiple_events(self):
        evts = [
            _batched_price_change(YES_TOKEN),
            _batched_price_change(YES_TOKEN, NO_TOKEN),
        ]
        results = self._probe().run_from_source(evts)
        assert results[YES_TOKEN].updates == 2
        assert results[NO_TOKEN].updates == 1

    # ------ min_updates ------

    def test_min_updates_threshold(self):
        probe = self._probe(min_updates=3)
        evts = [_price_change(YES_TOKEN)] * 2 + [_price_change(NO_TOKEN)] * 3
        results = probe.run_from_source(evts)
        assert results[YES_TOKEN].active is False  # only 2 < 3
        assert results[NO_TOKEN].active is True  # 3 >= 3

    # ------ early exit ------

    def test_early_exit_stops_consuming(self):
        """Iterator is consumed only until all assets reach min_updates."""
        events_consumed: list[dict] = []

        def tracking_source():
            for e in [
                _price_change(YES_TOKEN),
                _price_change(NO_TOKEN),
                _price_change(YES_TOKEN),  # would be a 3rd event — should not be reached
            ]:
                events_consumed.append(e)
                yield e

        probe = self._probe(min_updates=1)
        results = probe.run_from_source(tracking_source())
        # Both active after first two events; third event should be short-circuited.
        assert results[YES_TOKEN].active is True
        assert results[NO_TOKEN].active is True
        assert len(events_consumed) == 2

    def test_early_exit_not_triggered_until_all_assets_met(self):
        """Early exit only fires when ALL assets meet min_updates."""
        probe = self._probe(min_updates=1)
        # YES meets threshold first; NO has no events → no early exit, both processed.
        evts = [_price_change(YES_TOKEN), _price_change(NO_TOKEN)]
        results = probe.run_from_source(evts)
        assert results[YES_TOKEN].active is True
        assert results[NO_TOKEN].active is True

    # ------ probe_seconds in result ------

    def test_probe_seconds_populated(self):
        results = self._probe().run_from_source([])
        for pr in results.values():
            assert pr.probe_seconds >= 0.0

    # ------ mixed event stream ------

    def test_mixed_event_types(self):
        evts = [
            _book_snapshot(YES_TOKEN),  # not counted
            _price_change(YES_TOKEN),  # counted
            _tick_size_change(NO_TOKEN),  # not counted
            _last_trade(NO_TOKEN),  # counted
        ]
        results = self._probe().run_from_source(evts)
        assert results[YES_TOKEN].updates == 1
        assert results[NO_TOKEN].updates == 1


# ---------------------------------------------------------------------------
# MarketPicker.auto_pick_many with probe_config
# ---------------------------------------------------------------------------


def _make_market_obj(slug, yes_token=YES_TOKEN, no_token=NO_TOKEN, question=QUESTION):
    """Build a raw market dict as returned by gamma.fetch_markets_page."""
    return {
        "slug": slug,
        "market_slug": slug,
        "clobTokenIds": [yes_token, no_token],
        "outcomes": '["Yes", "No"]',
        "question": question,
    }


def _make_resolved(slug, yes_token=YES_TOKEN, no_token=NO_TOKEN):
    from packages.polymarket.simtrader.market_picker import ResolvedMarket

    return ResolvedMarket(
        slug=slug,
        yes_token_id=yes_token,
        no_token_id=no_token,
        yes_label="Yes",
        no_label="No",
        question=QUESTION,
    )


def _make_picker(resolved, book_valid=True):
    """Build a MarketPicker whose gamma and clob clients return fixed data."""
    from packages.polymarket.simtrader.market_picker import BookValidation, MarketPicker

    gamma = MagicMock()
    # fetch_markets_page used by auto_pick_many
    gamma.fetch_markets_page.return_value = [
        {
            "slug": resolved.slug,
            "clobTokenIds": [resolved.yes_token_id, resolved.no_token_id],
            "outcomes": ["Yes", "No"],
        }
    ]
    # fetch_markets_filtered used by resolve_slug
    market_obj = MagicMock()
    market_obj.market_slug = resolved.slug
    market_obj.question = QUESTION
    market_obj.outcomes = ["Yes", "No"]
    market_obj.clob_token_ids = [resolved.yes_token_id, resolved.no_token_id]
    gamma.fetch_markets_filtered.return_value = [market_obj]

    clob = MagicMock()
    if book_valid:
        clob.fetch_book.return_value = {
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "100"}],
        }
    else:
        clob.fetch_book.return_value = {"bids": [], "asks": []}

    return MarketPicker(gamma, clob)


class TestMarketPickerWithProbe:
    def test_no_probe_config_returns_none_probe_results(self):
        """probe_config=None → probe not run, ResolvedMarket.probe_results is None."""
        resolved = _make_resolved(SLUG)
        picker = _make_picker(resolved)

        results = picker.auto_pick_many(n=1, probe_config=None)
        assert len(results) == 1
        assert results[0].probe_results is None

    def test_probe_runs_and_results_attached(self):
        """probe_config without require_active → probe_results set on ResolvedMarket."""
        resolved = _make_resolved(SLUG)
        picker = _make_picker(resolved)

        # Inject one price_change for YES and one for NO via _event_source.
        evts = [_price_change(YES_TOKEN), _price_change(NO_TOKEN)]
        cfg = {
            "probe_seconds": 5.0,
            "min_updates": 1,
            "require_active": False,
            "_event_source": iter(evts),
        }

        results = picker.auto_pick_many(n=1, probe_config=cfg)
        assert len(results) == 1
        mkt = results[0]
        assert mkt.probe_results is not None
        assert mkt.probe_results[YES_TOKEN].updates == 1
        assert mkt.probe_results[YES_TOKEN].active is True
        assert mkt.probe_results[NO_TOKEN].updates == 1

    def test_require_active_rejects_inactive_market(self):
        """require_active=True with no events → market skipped, returns empty list."""
        resolved = _make_resolved(SLUG)
        picker = _make_picker(resolved)

        cfg = {
            "probe_seconds": 5.0,
            "min_updates": 1,
            "require_active": True,
            "_event_source": iter([]),  # no WS events → inactive
        }

        results = picker.auto_pick_many(n=1, probe_config=cfg)
        assert results == []

    def test_require_active_accepts_active_market(self):
        """require_active=True with enough events → market included."""
        resolved = _make_resolved(SLUG)
        picker = _make_picker(resolved)

        evts = [_price_change(YES_TOKEN), _price_change(NO_TOKEN)]
        cfg = {
            "probe_seconds": 5.0,
            "min_updates": 1,
            "require_active": True,
            "_event_source": iter(evts),
        }

        results = picker.auto_pick_many(n=1, probe_config=cfg)
        assert len(results) == 1

    def test_require_active_adds_skip_reason(self):
        """probe_inactive markets appear in collect_skips with correct reason."""
        resolved = _make_resolved(SLUG)
        picker = _make_picker(resolved)

        skip_log: list = []
        cfg = {
            "probe_seconds": 5.0,
            "min_updates": 1,
            "require_active": True,
            "_event_source": iter([]),
        }

        picker.auto_pick_many(n=1, probe_config=cfg, collect_skips=skip_log)
        assert len(skip_log) == 1
        assert skip_log[0]["reason"] == "probe_inactive"
        assert skip_log[0]["slug"] == SLUG
        assert "probe_seconds" in skip_log[0]
        assert "probe_updates" in skip_log[0]

    def test_require_false_no_skip_reason(self):
        """require_active=False never appends probe_inactive to collect_skips."""
        resolved = _make_resolved(SLUG)
        picker = _make_picker(resolved)

        skip_log: list = []
        cfg = {
            "probe_seconds": 5.0,
            "min_updates": 1,
            "require_active": False,
            "_event_source": iter([]),  # inactive — but require_active is False
        }

        results = picker.auto_pick_many(n=1, probe_config=cfg, collect_skips=skip_log)
        # Market is still included.
        assert len(results) == 1
        # No probe_inactive skip.
        probe_skips = [s for s in skip_log if s.get("reason") == "probe_inactive"]
        assert probe_skips == []

    def test_auto_pick_forwards_probe_config(self):
        """auto_pick() accepts and forwards probe_config to auto_pick_many."""
        resolved = _make_resolved(SLUG)
        picker = _make_picker(resolved)

        evts = [_price_change(YES_TOKEN), _price_change(NO_TOKEN)]
        cfg = {
            "probe_seconds": 3.0,
            "min_updates": 1,
            "require_active": False,
            "_event_source": iter(evts),
        }

        market = picker.auto_pick(probe_config=cfg)
        assert market.probe_results is not None
        assert market.probe_results[YES_TOKEN].active is True


# ---------------------------------------------------------------------------
# CLI: flag threading
# ---------------------------------------------------------------------------


def _patch_quickrun(mock_picker):
    return (
        patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
        patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
        patch(
            "packages.polymarket.simtrader.market_picker.MarketPicker",
            return_value=mock_picker,
        ),
    )


def _resolved(slug=SLUG):
    from packages.polymarket.simtrader.market_picker import ResolvedMarket

    return ResolvedMarket(
        slug=slug,
        yes_token_id=YES_TOKEN,
        no_token_id=NO_TOKEN,
        yes_label="Yes",
        no_label="No",
        question=QUESTION,
    )


class TestCLIActivenessProbeFlags:
    """Verify that CLI flags are threaded to auto_pick / auto_pick_many."""

    def _run_dry(self, extra_args, mock_picker, capsys):
        from contextlib import ExitStack

        from tools.cli.simtrader import main

        patchers = _patch_quickrun(mock_picker)
        with ExitStack() as stack:
            for p in patchers:
                stack.enter_context(p)
            exit_code = main(["quickrun", "--dry-run"] + extra_args)

        captured = capsys.readouterr()
        return exit_code, captured.out, captured.err

    def _run_list(self, extra_args, mock_picker, capsys):
        from contextlib import ExitStack

        from tools.cli.simtrader import main

        patchers = _patch_quickrun(mock_picker)
        with ExitStack() as stack:
            for p in patchers:
                stack.enter_context(p)
            exit_code = main(["quickrun", "--list-candidates", "1"] + extra_args)

        captured = capsys.readouterr()
        return exit_code, captured.out, captured.err

    # ------ probe_config=None when disabled (default) ------

    def test_default_no_probe_config(self, capsys):
        """Default (--activeness-probe-seconds not set) → probe_config=None to auto_pick."""
        seen: list = []

        def fake_auto_pick(**kwargs):
            seen.append(kwargs)
            return _resolved()

        mock_picker = MagicMock()
        mock_picker.auto_pick.side_effect = fake_auto_pick
        mock_picker.validate_book.return_value = MagicMock(
            valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=None
        )

        self._run_dry([], mock_picker, capsys)

        assert len(seen) == 1
        assert seen[0].get("probe_config") is None

    def test_zero_probe_seconds_no_probe_config(self, capsys):
        """--activeness-probe-seconds 0 is treated the same as unset."""
        seen: list = []

        def fake_auto_pick(**kwargs):
            seen.append(kwargs)
            return _resolved()

        mock_picker = MagicMock()
        mock_picker.auto_pick.side_effect = fake_auto_pick
        mock_picker.validate_book.return_value = MagicMock(
            valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=None
        )

        self._run_dry(["--activeness-probe-seconds", "0"], mock_picker, capsys)

        assert seen[0].get("probe_config") is None

    # ------ probe_config passed when enabled ------

    def test_probe_seconds_sets_probe_config(self, capsys):
        """--activeness-probe-seconds 7 → probe_config dict with probe_seconds=7."""
        seen: list = []

        def fake_auto_pick(**kwargs):
            seen.append(kwargs)
            return _resolved()

        mock_picker = MagicMock()
        mock_picker.auto_pick.side_effect = fake_auto_pick
        mock_picker.validate_book.return_value = MagicMock(
            valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=None
        )

        self._run_dry(["--activeness-probe-seconds", "7"], mock_picker, capsys)

        assert len(seen) == 1
        cfg = seen[0].get("probe_config")
        assert cfg is not None
        assert cfg["probe_seconds"] == 7.0
        assert cfg["require_active"] is False  # default
        assert cfg["min_updates"] == 1  # default

    def test_require_active_flag(self, capsys):
        """--require-active → probe_config["require_active"]=True."""
        seen: list = []

        def fake_auto_pick(**kwargs):
            seen.append(kwargs)
            return _resolved()

        mock_picker = MagicMock()
        mock_picker.auto_pick.side_effect = fake_auto_pick
        mock_picker.validate_book.return_value = MagicMock(
            valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=None
        )

        self._run_dry(
            ["--activeness-probe-seconds", "5", "--require-active"],
            mock_picker,
            capsys,
        )

        cfg = seen[0].get("probe_config")
        assert cfg is not None
        assert cfg["require_active"] is True

    def test_min_probe_updates_forwarded(self, capsys):
        """--min-probe-updates 4 → probe_config["min_updates"]=4."""
        seen: list = []

        def fake_auto_pick(**kwargs):
            seen.append(kwargs)
            return _resolved()

        mock_picker = MagicMock()
        mock_picker.auto_pick.side_effect = fake_auto_pick
        mock_picker.validate_book.return_value = MagicMock(
            valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=None
        )

        self._run_dry(
            ["--activeness-probe-seconds", "5", "--min-probe-updates", "4"],
            mock_picker,
            capsys,
        )

        cfg = seen[0].get("probe_config")
        assert cfg is not None
        assert cfg["min_updates"] == 4

    # ------ list-candidates forwards probe_config ------

    def test_list_candidates_forwards_probe_config(self, capsys):
        """--list-candidates with --activeness-probe-seconds passes probe_config to auto_pick_many."""
        seen: list = []

        cand = _resolved("market-probe")
        cand.probe_results = None  # simulate no probe_results attached by mock

        def fake_auto_pick_many(**kwargs):
            seen.append(kwargs)
            return [cand]

        mock_picker = MagicMock()
        mock_picker.auto_pick_many.side_effect = fake_auto_pick_many
        mock_picker.validate_book.return_value = MagicMock(
            valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=None
        )

        self._run_list(
            ["--activeness-probe-seconds", "10", "--require-active"],
            mock_picker,
            capsys,
        )

        assert len(seen) == 1
        cfg = seen[0].get("probe_config")
        assert cfg is not None
        assert cfg["probe_seconds"] == 10.0
        assert cfg["require_active"] is True

    # ------ probe stats shown in list-candidates output ------

    def test_list_candidates_shows_probe_stats(self, capsys):
        """Probe stats appear in --list-candidates output when probe_results are attached."""
        from packages.polymarket.simtrader.activeness_probe import ProbeResult

        cand = _resolved("market-with-probe")
        cand.probe_results = {
            YES_TOKEN: ProbeResult(
                token_id=YES_TOKEN, probe_seconds=5.0, updates=3, active=True
            ),
            NO_TOKEN: ProbeResult(
                token_id=NO_TOKEN, probe_seconds=5.0, updates=0, active=False
            ),
        }

        mock_picker = MagicMock()
        mock_picker.auto_pick_many.return_value = [cand]
        mock_picker.validate_book.return_value = MagicMock(
            valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=None
        )

        _exit_code, out, _err = self._run_list(
            ["--activeness-probe-seconds", "5"], mock_picker, capsys
        )

        assert "YES probe" in out
        assert "3 updates" in out
        assert "ACTIVE" in out
        assert "NO probe" in out
        assert "0 updates" in out
        assert "inactive" in out

    def test_list_candidates_no_probe_stats_when_disabled(self, capsys):
        """Probe stats do NOT appear when probe is disabled (probe_results=None)."""
        cand = _resolved("market-quiet")
        cand.probe_results = None

        mock_picker = MagicMock()
        mock_picker.auto_pick_many.return_value = [cand]
        mock_picker.validate_book.return_value = MagicMock(
            valid=True, reason="ok", best_bid=0.45, best_ask=0.55, depth_total=None
        )

        _exit_code, out, _err = self._run_list([], mock_picker, capsys)

        # "YES probe :" and "NO probe :" lines should not appear.
        assert "probe :" not in out
