"""Offline tests for market_picker, config_loader, and the quickrun CLI subcommand.

All tests are fully offline — no network calls are made.  External collaborators
(GammaClient, ClobClient, TapeRecorder, run_strategy) are replaced with
test doubles or patched out.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

YES_TOKEN = "aaa" * 20 + "1"
NO_TOKEN = "bbb" * 20 + "2"
SLUG = "will-it-rain-2026"
QUESTION = "Will it rain in 2026?"


def _make_market(slug=SLUG, outcomes=None, clob_token_ids=None, question=QUESTION):
    """Return a minimal Market-like mock."""
    m = MagicMock()
    m.market_slug = slug
    m.question = question
    m.outcomes = outcomes or ["Yes", "No"]
    m.clob_token_ids = clob_token_ids or [YES_TOKEN, NO_TOKEN]
    return m


def _make_book(bids=None, asks=None):
    return {
        "bids": bids if bids is not None else [{"price": "0.45", "size": "100"}],
        "asks": asks if asks is not None else [{"price": "0.55", "size": "100"}],
    }


# ---------------------------------------------------------------------------
# MarketPicker.resolve_slug tests
# ---------------------------------------------------------------------------


class TestResolveSlug:
    def _picker(self, markets):
        from packages.polymarket.simtrader.market_picker import MarketPicker

        gamma = MagicMock()
        gamma.fetch_markets_filtered.return_value = markets
        return MarketPicker(gamma, MagicMock())

    def test_resolve_slug_binary_yes_no(self):
        """Standard binary market: outcomes ["Yes", "No"] → correct token mapping."""
        from packages.polymarket.simtrader.market_picker import ResolvedMarket

        market = _make_market(outcomes=["Yes", "No"])
        picker = self._picker([market])
        result = picker.resolve_slug(SLUG)

        assert isinstance(result, ResolvedMarket)
        assert result.yes_token_id == YES_TOKEN
        assert result.no_token_id == NO_TOKEN
        assert result.yes_label == "Yes"
        assert result.no_label == "No"
        assert result.slug == SLUG

    def test_resolve_slug_reversed_order(self):
        """Outcomes in No/Yes order → YES still maps to token at index 1."""
        market = _make_market(
            outcomes=["No", "Yes"],
            clob_token_ids=[NO_TOKEN, YES_TOKEN],
        )
        picker = self._picker([market])
        result = picker.resolve_slug(SLUG)
        assert result.yes_token_id == YES_TOKEN
        assert result.no_token_id == NO_TOKEN

    def test_resolve_slug_nonbinary_raises(self):
        """Market with 3 outcomes raises MarketPickerError."""
        from packages.polymarket.simtrader.market_picker import MarketPickerError

        market = _make_market(
            outcomes=["A", "B", "C"],
            clob_token_ids=["t1", "t2", "t3"],
        )
        picker = self._picker([market])
        with pytest.raises(MarketPickerError, match="not binary"):
            picker.resolve_slug(SLUG)

    def test_resolve_slug_ambiguous_outcomes_raises(self):
        """Outcomes ["Rain", "Shine"] that don't match YES/NO patterns → error."""
        from packages.polymarket.simtrader.market_picker import MarketPickerError

        market = _make_market(outcomes=["Rain", "Shine"])
        picker = self._picker([market])
        with pytest.raises(MarketPickerError, match="cannot identify YES/NO"):
            picker.resolve_slug(SLUG)

    def test_resolve_slug_no_markets_raises(self):
        """Empty result from Gamma → MarketPickerError."""
        from packages.polymarket.simtrader.market_picker import MarketPickerError

        picker = self._picker([])
        with pytest.raises(MarketPickerError, match="no markets returned"):
            picker.resolve_slug(SLUG)


# ---------------------------------------------------------------------------
# MarketPicker.validate_book tests
# ---------------------------------------------------------------------------


class TestValidateBook:
    def _picker(self, fetch_book_side_effect=None, fetch_book_return=None):
        from packages.polymarket.simtrader.market_picker import MarketPicker

        clob = MagicMock()
        if fetch_book_side_effect is not None:
            clob.fetch_book.side_effect = fetch_book_side_effect
        else:
            clob.fetch_book.return_value = fetch_book_return or _make_book()
        return MarketPicker(MagicMock(), clob)

    def test_validate_book_error_response(self):
        """Book response with 'error' key → valid=False, reason=error_response."""
        picker = self._picker(
            fetch_book_return={"error": "No orderbook exists for the requested token id"}
        )
        result = picker.validate_book(YES_TOKEN)
        assert not result.valid
        assert result.reason == "error_response"

    def test_validate_book_empty_rejected_by_default(self):
        """Empty bids and asks → valid=False, reason=empty_book (default)."""
        picker = self._picker(fetch_book_return={"bids": [], "asks": []})
        result = picker.validate_book(YES_TOKEN)
        assert not result.valid
        assert result.reason == "empty_book"

    def test_validate_book_empty_allowed_with_flag(self):
        """Empty bids and asks with allow_empty=True → valid=True."""
        picker = self._picker(fetch_book_return={"bids": [], "asks": []})
        result = picker.validate_book(YES_TOKEN, allow_empty=True)
        assert result.valid
        assert result.reason == "ok"

    def test_validate_book_nonempty_accepted(self):
        """Non-empty book → valid=True, best_bid/best_ask extracted."""
        picker = self._picker(
            fetch_book_return=_make_book(
                bids=[{"price": "0.43", "size": "50"}],
                asks=[{"price": "0.58", "size": "50"}],
            )
        )
        result = picker.validate_book(YES_TOKEN)
        assert result.valid
        assert result.reason == "ok"
        assert result.best_bid == pytest.approx(0.43)
        assert result.best_ask == pytest.approx(0.58)

    def test_validate_book_fetch_failed(self):
        """fetch_book raises an exception → valid=False, reason=fetch_failed."""
        picker = self._picker(fetch_book_side_effect=ConnectionError("network error"))
        result = picker.validate_book(YES_TOKEN)
        assert not result.valid
        assert result.reason == "fetch_failed"


# ---------------------------------------------------------------------------
# MarketPicker.auto_pick tests
# ---------------------------------------------------------------------------


class TestAutoPick:
    def _raw_market(self, slug, outcomes=None, token_ids=None):
        return {
            "slug": slug,
            "outcomes": json.dumps(outcomes or ["Yes", "No"]),
            "clobTokenIds": json.dumps(token_ids or [YES_TOKEN, NO_TOKEN]),
        }

    def test_auto_pick_skips_invalid_returns_first_valid(self):
        """First two markets fail book check, third passes → returns third."""
        from packages.polymarket.simtrader.market_picker import MarketPicker

        slug_a = "market-a"
        slug_b = "market-b"
        slug_c = "market-c"

        # Each market gets distinct token IDs so the book filter is unambiguous.
        yes_a, no_a = "yes_aaaa", "no_aaaa"
        yes_b, no_b = "yes_bbbb", "no_bbbb"
        yes_c, no_c = "yes_cccc", "no_cccc"

        market_a = _make_market(slug=slug_a, outcomes=["Yes", "No"], clob_token_ids=[yes_a, no_a])
        market_b = _make_market(slug=slug_b, outcomes=["Yes", "No"], clob_token_ids=[yes_b, no_b])
        market_c = _make_market(slug=slug_c, outcomes=["Yes", "No"], clob_token_ids=[yes_c, no_c])

        gamma = MagicMock()
        gamma.fetch_markets_page.return_value = [
            self._raw_market(slug_a, token_ids=[yes_a, no_a]),
            self._raw_market(slug_b, token_ids=[yes_b, no_b]),
            self._raw_market(slug_c, token_ids=[yes_c, no_c]),
        ]

        def _filtered(slugs=None, **_kw):
            by_slug = {slug_a: market_a, slug_b: market_b, slug_c: market_c}
            return [by_slug[slugs[0]]] if slugs else []

        gamma.fetch_markets_filtered.side_effect = _filtered

        _bad_tokens = {yes_a, no_a, yes_b, no_b}

        def _fetch_book(token_id):
            if token_id in _bad_tokens:
                return {"error": "no orderbook"}
            return _make_book()

        clob = MagicMock()
        clob.fetch_book.side_effect = _fetch_book

        picker = MarketPicker(gamma, clob)
        result = picker.auto_pick()
        assert result.slug == slug_c

    def test_auto_pick_no_candidates_raises(self):
        """All candidates fail → MarketPickerError."""
        from packages.polymarket.simtrader.market_picker import (
            MarketPicker,
            MarketPickerError,
        )

        gamma = MagicMock()
        gamma.fetch_markets_page.return_value = [
            self._raw_market("bad-market"),
        ]
        gamma.fetch_markets_filtered.return_value = [
            _make_market(slug="bad-market")
        ]

        clob = MagicMock()
        clob.fetch_book.return_value = {"error": "no orderbook"}

        picker = MarketPicker(gamma, clob)
        with pytest.raises(MarketPickerError, match="no valid binary market"):
            picker.auto_pick(max_candidates=1)


# ---------------------------------------------------------------------------
# config_loader tests
# ---------------------------------------------------------------------------


class TestConfigLoader:
    def test_config_loader_bom_regression(self, tmp_path):
        """JSON file with UTF-8 BOM bytes → parsed correctly (PowerShell 5.1 regression)."""
        from packages.polymarket.simtrader.config_loader import load_json_from_path

        p = tmp_path / "cfg.json"
        p.write_bytes(b"\xef\xbb\xbf" + b'{"buffer": 0.01}')  # UTF-8 BOM prefix
        result = load_json_from_path(p)
        assert result == {"buffer": 0.01}

    def test_config_loader_path_no_bom(self, tmp_path):
        """Normal UTF-8 file without BOM → parsed correctly."""
        from packages.polymarket.simtrader.config_loader import load_json_from_path

        p = tmp_path / "cfg.json"
        p.write_text('{"max_size": 25}', encoding="utf-8")
        result = load_json_from_path(p)
        assert result == {"max_size": 25}

    def test_config_loader_json_string(self):
        """load_json_from_string parses a valid JSON object string."""
        from packages.polymarket.simtrader.config_loader import load_json_from_string

        result = load_json_from_string('{"buffer": 0.02, "max_size": 10}')
        assert result == {"buffer": 0.02, "max_size": 10}

    def test_config_loader_json_string_bom(self):
        """load_json_from_string strips leading BOM (U+FEFF) before parsing."""
        from packages.polymarket.simtrader.config_loader import load_json_from_string

        bom_string = "\ufeff" + '{"buffer": 0.02}'
        result = load_json_from_string(bom_string)
        assert result == {"buffer": 0.02}

    def test_config_loader_missing_file_raises(self, tmp_path):
        """Non-existent file path raises ConfigLoadError."""
        from packages.polymarket.simtrader.config_loader import (
            ConfigLoadError,
            load_json_from_path,
        )

        with pytest.raises(ConfigLoadError, match="not found"):
            load_json_from_path(tmp_path / "does_not_exist.json")

    def test_config_loader_invalid_json_raises(self, tmp_path):
        """File with invalid JSON raises ConfigLoadError."""
        from packages.polymarket.simtrader.config_loader import (
            ConfigLoadError,
            load_json_from_path,
        )

        p = tmp_path / "bad.json"
        p.write_text("{not valid json}", encoding="utf-8")
        with pytest.raises(ConfigLoadError):
            load_json_from_path(p)

    def test_load_strategy_config_both_raises(self, tmp_path):
        """Providing both config_path and config_json raises ConfigLoadError."""
        from packages.polymarket.simtrader.config_loader import (
            ConfigLoadError,
            load_strategy_config,
        )

        p = tmp_path / "cfg.json"
        p.write_text("{}", encoding="utf-8")
        with pytest.raises(ConfigLoadError, match="only one"):
            load_strategy_config(config_path=p, config_json="{}")

    def test_load_strategy_config_neither_returns_empty(self):
        """Providing neither argument returns {}."""
        from packages.polymarket.simtrader.config_loader import load_strategy_config

        result = load_strategy_config()
        assert result == {}


# ---------------------------------------------------------------------------
# quickrun dry-run CLI test
# ---------------------------------------------------------------------------


class TestQuickrunDryRunCli:
    def test_quickrun_dry_run_cli(self, tmp_path):
        """--dry-run with mocked market picker prints exit message and returns 0."""
        from packages.polymarket.simtrader.market_picker import ResolvedMarket

        mock_resolved = ResolvedMarket(
            slug=SLUG,
            yes_token_id=YES_TOKEN,
            no_token_id=NO_TOKEN,
            yes_label="Yes",
            no_label="No",
            question=QUESTION,
        )

        mock_picker = MagicMock()
        mock_picker.resolve_slug.return_value = mock_resolved
        mock_picker.validate_book.return_value = MagicMock(valid=True, reason="ok")

        with (
            patch(
                "packages.polymarket.gamma.GammaClient",
                return_value=MagicMock(),
            ),
            patch(
                "packages.polymarket.clob.ClobClient",
                return_value=MagicMock(),
            ),
            patch(
                "packages.polymarket.simtrader.market_picker.MarketPicker",
                return_value=mock_picker,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "quickrun",
                    "--market",
                    SLUG,
                    "--dry-run",
                ]
            )

        assert exit_code == 0


# ---------------------------------------------------------------------------
# Sweep config BOM regression test
# ---------------------------------------------------------------------------


class TestSweepConfigBom:
    def test_parse_sweep_config_json_bom(self):
        """parse_sweep_config_json accepts BOM-prefixed JSON (PowerShell regression)."""
        from packages.polymarket.simtrader.sweeps.runner import parse_sweep_config_json

        bom_json = "\ufeff" + '{"scenarios": [{"name": "s1", "overrides": {}}]}'
        result = parse_sweep_config_json(bom_json)
        assert "scenarios" in result
        assert result["scenarios"][0]["name"] == "s1"


# ---------------------------------------------------------------------------
# Full offline non-dry-run quickrun test
# ---------------------------------------------------------------------------


class TestQuickrunFullCli:
    """End-to-end quickrun with all network calls mocked.

    Validates:
    - Exit code 0
    - Console summary shows net_profit, Decisions/Orders/Fills counts
    - Orders count matches orders.jsonl line count (not a missing manifest key)
    - Reproduce command present
    - tape/meta.json contains quickrun_context with expected fields
    - run_manifest.json contains quickrun_context
    - --strategy-config-json override reaches strategy_config
    """

    def test_quickrun_full_offline(self, tmp_path, capsys, monkeypatch):
        import json as _json

        from packages.polymarket.simtrader.market_picker import ResolvedMarket
        from packages.polymarket.simtrader.strategy.facade import StrategyRunResult

        mock_resolved = ResolvedMarket(
            slug=SLUG,
            yes_token_id=YES_TOKEN,
            no_token_id=NO_TOKEN,
            yes_label="Yes",
            no_label="No",
            question=QUESTION,
        )
        mock_validation = MagicMock()
        mock_validation.valid = True
        mock_validation.reason = "ok"

        mock_picker = MagicMock()
        mock_picker.resolve_slug.return_value = mock_resolved
        mock_picker.validate_book.return_value = mock_validation

        # Capture what was passed to run_strategy so we can assert on it.
        tape_dir_capture: list = [None]
        run_dir_capture: list = [None]
        strategy_config_capture: list = [None]

        def FakeTapeRecorder(tape_dir, asset_ids, strict=False):
            """Write a minimal valid tape without network."""
            tape_dir_capture[0] = tape_dir
            rec = MagicMock()

            def fake_record(duration_seconds=None, ws_url=None):
                tape_dir.mkdir(parents=True, exist_ok=True)
                ev1 = _json.dumps(
                    {
                        "seq": 0,
                        "ts_recv": 1.0,
                        "asset_id": YES_TOKEN,
                        "event_type": "book",
                        "bids": [],
                        "asks": [],
                    }
                )
                ev2 = _json.dumps(
                    {
                        "seq": 1,
                        "ts_recv": 1.1,
                        "asset_id": NO_TOKEN,
                        "event_type": "book",
                        "bids": [],
                        "asks": [],
                    }
                )
                (tape_dir / "events.jsonl").write_text(
                    ev1 + "\n" + ev2 + "\n", encoding="utf-8"
                )
                tape_meta = {
                    "ws_url": "wss://fake",
                    "asset_ids": asset_ids,
                    "event_count": 2,
                    "warnings": [],
                }
                (tape_dir / "meta.json").write_text(
                    _json.dumps(tape_meta) + "\n", encoding="utf-8"
                )

            rec.record = fake_record
            return rec

        def fake_run_strategy(params):
            """Write minimal run artifacts without executing real strategy."""
            params.run_dir.mkdir(parents=True, exist_ok=True)
            run_dir_capture[0] = params.run_dir
            strategy_config_capture[0] = params.strategy_config

            # orders.jsonl: 3 broker events → orders_count should be 3
            orders = [
                {"order_id": "o1", "event": "submitted", "asset_id": YES_TOKEN},
                {"order_id": "o1", "event": "activated", "asset_id": YES_TOKEN},
                {"order_id": "o1", "event": "fill", "fill_status": "full", "asset_id": YES_TOKEN},
            ]
            (params.run_dir / "orders.jsonl").write_text(
                "\n".join(_json.dumps(o) for o in orders) + "\n", encoding="utf-8"
            )

            # decisions.jsonl: 2 entries
            decisions = [{"action": "submit"}, {"action": "submit"}]
            (params.run_dir / "decisions.jsonl").write_text(
                "\n".join(_json.dumps(d) for d in decisions) + "\n", encoding="utf-8"
            )

            # fills.jsonl: 1 fill
            (params.run_dir / "fills.jsonl").write_text(
                _json.dumps({"order_id": "o1", "fill_size": "50"}) + "\n",
                encoding="utf-8",
            )

            summary = {
                "net_profit": "5.25",
                "realized_pnl": "5.25",
                "unrealized_pnl": "0.0",
                "total_fees": "1.05",
            }
            (params.run_dir / "summary.json").write_text(
                _json.dumps(summary) + "\n", encoding="utf-8"
            )

            run_manifest = {
                "run_id": params.run_dir.name,
                "fills_count": 1,
                "decisions_count": 2,
                "run_quality": "ok",
                "warnings": [],
                "net_profit": "5.25",
            }
            (params.run_dir / "run_manifest.json").write_text(
                _json.dumps(run_manifest) + "\n", encoding="utf-8"
            )

            return StrategyRunResult(
                run_id=params.run_dir.name,
                run_dir=params.run_dir,
                summary=summary,
                metrics={
                    k: str(summary.get(k, "0"))
                    for k in ("net_profit", "realized_pnl", "unrealized_pnl", "total_fees")
                },
                warnings_count=0,
            )

        # Route all file output under tmp_path so tests never pollute the repo.
        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.market_picker.MarketPicker",
                return_value=mock_picker,
            ),
            patch(
                "packages.polymarket.simtrader.tape.recorder.TapeRecorder",
                side_effect=FakeTapeRecorder,
            ),
            patch(
                "packages.polymarket.simtrader.strategy.facade.run_strategy",
                side_effect=fake_run_strategy,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "quickrun",
                    "--market",
                    SLUG,
                    "--duration",
                    "1",
                    "--strategy-config-json",
                    '{"buffer": 0.02}',
                ]
            )

        assert exit_code == 0

        captured = capsys.readouterr()
        out = captured.out

        # Net profit visible in output
        assert "5.25" in out

        # Counts line present and correct
        # format: "  Decisions  : 2   Orders: 3   Fills: 1"
        assert "Decisions" in out
        assert "Orders" in out
        assert "Fills" in out
        assert "Orders: 3" in out, f"Expected 'Orders: 3' in output, got:\n{out}"
        assert "Decisions  : 2" in out
        assert "Fills: 1" in out

        # Reproduce command present
        assert "Reproduce" in out
        assert SLUG in out

        # tape/meta.json has quickrun_context
        assert tape_dir_capture[0] is not None
        tape_meta_path = tape_dir_capture[0] / "meta.json"
        tape_meta = _json.loads(tape_meta_path.read_text(encoding="utf-8"))
        assert "quickrun_context" in tape_meta, "tape/meta.json missing quickrun_context"
        ctx = tape_meta["quickrun_context"]
        assert ctx["selected_slug"] == SLUG
        assert ctx["yes_token_id"] == YES_TOKEN
        assert ctx["no_token_id"] == NO_TOKEN
        assert ctx["selection_mode"] == "explicit"
        assert ctx["allow_empty_book"] is False
        assert "yes_book_validation" in ctx
        assert ctx["yes_book_validation"]["reason"] == "ok"
        assert "no_book_validation" in ctx
        assert ctx["no_book_validation"]["reason"] == "ok"
        assert "selected_at" in ctx

        # run_manifest.json also has quickrun_context
        assert run_dir_capture[0] is not None
        manifest_path = run_dir_capture[0] / "run_manifest.json"
        run_manifest = _json.loads(manifest_path.read_text(encoding="utf-8"))
        assert "quickrun_context" in run_manifest, "run_manifest.json missing quickrun_context"
        assert run_manifest["quickrun_context"]["selected_slug"] == SLUG

        # --strategy-config-json override reached strategy_config
        assert strategy_config_capture[0] is not None
        assert abs(strategy_config_capture[0].get("buffer", 0) - 0.02) < 1e-9


class TestQuickrunMinEventsWarning:
    def test_warns_when_tape_is_shorter_than_min_events(
        self, tmp_path, capsys, monkeypatch
    ):
        import json as _json

        from packages.polymarket.simtrader.market_picker import ResolvedMarket
        from packages.polymarket.simtrader.strategy.facade import StrategyRunResult

        mock_resolved = ResolvedMarket(
            slug=SLUG,
            yes_token_id=YES_TOKEN,
            no_token_id=NO_TOKEN,
            yes_label="Yes",
            no_label="No",
            question=QUESTION,
        )
        mock_picker = MagicMock()
        mock_picker.resolve_slug.return_value = mock_resolved
        mock_picker.validate_book.return_value = MagicMock(valid=True, reason="ok")

        def FakeTapeRecorder(tape_dir, asset_ids, strict=False):
            rec = MagicMock()

            def fake_record(duration_seconds=None, ws_url=None):
                tape_dir.mkdir(parents=True, exist_ok=True)
                (tape_dir / "events.jsonl").write_text(
                    _json.dumps(
                        {
                            "seq": 0,
                            "ts_recv": 1.0,
                            "asset_id": YES_TOKEN,
                            "event_type": "book",
                            "bids": [],
                            "asks": [],
                        }
                    )
                    + "\n"
                    + _json.dumps(
                        {
                            "seq": 1,
                            "ts_recv": 1.1,
                            "asset_id": NO_TOKEN,
                            "event_type": "book",
                            "bids": [],
                            "asks": [],
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
                (tape_dir / "meta.json").write_text(
                    _json.dumps(
                        {
                            "ws_url": "wss://fake",
                            "asset_ids": asset_ids,
                            "event_count": 2,
                            "warnings": [],
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )

            rec.record = fake_record
            return rec

        def fake_run_strategy(params):
            params.run_dir.mkdir(parents=True, exist_ok=True)
            (params.run_dir / "orders.jsonl").write_text("", encoding="utf-8")
            (params.run_dir / "decisions.jsonl").write_text("", encoding="utf-8")
            (params.run_dir / "fills.jsonl").write_text("", encoding="utf-8")

            summary = {
                "net_profit": "0",
                "realized_pnl": "0",
                "unrealized_pnl": "0",
                "total_fees": "0",
            }
            (params.run_dir / "summary.json").write_text(
                _json.dumps(summary) + "\n",
                encoding="utf-8",
            )
            (params.run_dir / "run_manifest.json").write_text(
                _json.dumps(
                    {
                        "run_id": params.run_dir.name,
                        "fills_count": 0,
                        "decisions_count": 0,
                        "run_quality": "ok",
                        "warnings": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            return StrategyRunResult(
                run_id=params.run_dir.name,
                run_dir=params.run_dir,
                summary=summary,
                metrics=summary,
                warnings_count=0,
            )

        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.market_picker.MarketPicker",
                return_value=mock_picker,
            ),
            patch(
                "packages.polymarket.simtrader.tape.recorder.TapeRecorder",
                side_effect=FakeTapeRecorder,
            ),
            patch(
                "packages.polymarket.simtrader.strategy.facade.run_strategy",
                side_effect=fake_run_strategy,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                [
                    "quickrun",
                    "--market",
                    SLUG,
                    "--duration",
                    "1",
                    "--min-events",
                    "10",
                ]
            )

        assert exit_code == 0
        stderr = capsys.readouterr().err
        assert "tape has 2 parsed events (< --min-events 10)" in stderr
        assert "rerun with a longer --duration" in stderr


# ---------------------------------------------------------------------------
# Quick sweep preset unit tests
# ---------------------------------------------------------------------------


class TestBuildQuickSweepConfig:
    def test_returns_24_scenarios(self):
        """'quick' preset produces exactly 4 × 3 × 2 = 24 scenarios."""
        from tools.cli.simtrader import _build_quick_sweep_config

        cfg = _build_quick_sweep_config()
        assert "scenarios" in cfg
        assert len(cfg["scenarios"]) == 24

    def test_all_scenarios_unique_names(self):
        """All 24 scenario names are distinct."""
        from tools.cli.simtrader import _build_quick_sweep_config

        cfg = _build_quick_sweep_config()
        names = [s["name"] for s in cfg["scenarios"]]
        assert len(names) == len(set(names)), f"Duplicate scenario names: {names}"

    def test_each_scenario_has_overrides(self):
        """Every scenario dict has an 'overrides' key with required fields."""
        from tools.cli.simtrader import _build_quick_sweep_config

        cfg = _build_quick_sweep_config()
        for s in cfg["scenarios"]:
            ov = s["overrides"]
            assert "fee_rate_bps" in ov, f"Missing fee_rate_bps in {s}"
            assert "cancel_latency_ticks" in ov, f"Missing cancel_latency_ticks in {s}"
            assert "mark_method" in ov, f"Missing mark_method in {s}"

    def test_fee_rates_covered(self):
        """All four fee rate values appear in the scenario set."""
        from tools.cli.simtrader import (
            _QUICK_SWEEP_FEE_RATES,
            _build_quick_sweep_config,
        )

        cfg = _build_quick_sweep_config()
        seen_fees = {s["overrides"]["fee_rate_bps"] for s in cfg["scenarios"]}
        assert seen_fees == set(_QUICK_SWEEP_FEE_RATES)

    def test_cancel_ticks_covered(self):
        """All three cancel_latency_ticks values appear in the scenario set."""
        from tools.cli.simtrader import (
            _QUICK_SWEEP_CANCEL_TICKS,
            _build_quick_sweep_config,
        )

        cfg = _build_quick_sweep_config()
        seen = {s["overrides"]["cancel_latency_ticks"] for s in cfg["scenarios"]}
        assert seen == set(_QUICK_SWEEP_CANCEL_TICKS)

    def test_mark_methods_covered(self):
        """Both mark_method values appear in the scenario set."""
        from tools.cli.simtrader import (
            _QUICK_SWEEP_MARK_METHODS,
            _build_quick_sweep_config,
        )

        cfg = _build_quick_sweep_config()
        seen = {s["overrides"]["mark_method"] for s in cfg["scenarios"]}
        assert seen == set(_QUICK_SWEEP_MARK_METHODS)

    def test_preset_registry_contains_quick(self):
        """_SWEEP_PRESETS maps 'quick' to a callable."""
        from tools.cli.simtrader import _SWEEP_PRESETS

        assert "quick" in _SWEEP_PRESETS
        factory = _SWEEP_PRESETS["quick"]
        result = factory()
        assert "scenarios" in result
        assert len(result["scenarios"]) == 24


class TestQuickrunSweepCli:
    """Test that --sweep quick routes to run_sweep and prints a leaderboard."""

    def _make_resolved(self):
        from packages.polymarket.simtrader.market_picker import ResolvedMarket

        return ResolvedMarket(
            slug=SLUG,
            yes_token_id=YES_TOKEN,
            no_token_id=NO_TOKEN,
            yes_label="Yes",
            no_label="No",
            question=QUESTION,
        )

    def test_sweep_quick_calls_run_sweep_not_run_strategy(
        self, tmp_path, capsys, monkeypatch
    ):
        """--sweep quick must call run_sweep (not run_strategy)."""
        import json as _json

        from packages.polymarket.simtrader.sweeps.runner import SweepRunResult

        mock_picker = MagicMock()
        mock_picker.resolve_slug.return_value = self._make_resolved()
        mock_picker.validate_book.return_value = MagicMock(valid=True, reason="ok")

        sweep_params_capture: list = [None]
        sweep_config_capture: list = [None]

        def FakeTapeRecorder(tape_dir, asset_ids, strict=False):
            rec = MagicMock()

            def fake_record(duration_seconds=None, ws_url=None):
                tape_dir.mkdir(parents=True, exist_ok=True)
                ev1 = _json.dumps(
                    {"seq": 0, "ts_recv": 1.0, "asset_id": YES_TOKEN,
                     "event_type": "book", "bids": [], "asks": []}
                )
                ev2 = _json.dumps(
                    {"seq": 1, "ts_recv": 1.1, "asset_id": NO_TOKEN,
                     "event_type": "book", "bids": [], "asks": []}
                )
                (tape_dir / "events.jsonl").write_text(ev1 + "\n" + ev2 + "\n")
                (tape_dir / "meta.json").write_text(
                    _json.dumps({"ws_url": "wss://fake", "asset_ids": asset_ids,
                                 "event_count": 2, "warnings": []}) + "\n"
                )

            rec.record = fake_record
            return rec

        def fake_run_sweep(params, sweep_config):
            sweep_params_capture[0] = params
            sweep_config_capture[0] = sweep_config
            sweep_dir = params.artifacts_root / "sweeps" / params.sweep_id
            sweep_dir.mkdir(parents=True, exist_ok=True)
            summary = {
                "sweep_id": params.sweep_id,
                "scenarios": [
                    {"scenario_id": "s1", "net_profit": "1.0"},
                    {"scenario_id": "s2", "net_profit": "0.5"},
                ],
                "aggregate": {
                    "best_net_profit": "1.0", "best_scenario": "s1",
                    "median_net_profit": "0.75", "median_scenario": "s1",
                    "worst_net_profit": "0.5", "worst_scenario": "s2",
                },
            }
            manifest = {"sweep_id": params.sweep_id}
            (sweep_dir / "sweep_manifest.json").write_text(
                _json.dumps(manifest) + "\n"
            )
            (sweep_dir / "sweep_summary.json").write_text(
                _json.dumps(summary) + "\n"
            )
            return SweepRunResult(
                sweep_id=params.sweep_id,
                sweep_dir=sweep_dir,
                summary=summary,
                manifest=manifest,
            )

        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.market_picker.MarketPicker",
                return_value=mock_picker,
            ),
            patch(
                "packages.polymarket.simtrader.tape.recorder.TapeRecorder",
                side_effect=FakeTapeRecorder,
            ),
            patch(
                "packages.polymarket.simtrader.sweeps.runner.run_sweep",
                side_effect=fake_run_sweep,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                ["quickrun", "--market", SLUG, "--duration", "1", "--sweep", "quick"]
            )

        assert exit_code == 0, f"Expected exit 0 for sweep quickrun, got {exit_code}"

        # run_sweep was called (not run_strategy)
        assert sweep_params_capture[0] is not None, "run_sweep was not called"

        # sweep_config has 24 scenarios (the quick preset)
        assert sweep_config_capture[0] is not None
        assert len(sweep_config_capture[0]["scenarios"]) == 24

        # Output contains leaderboard keywords
        out = capsys.readouterr().out
        assert "LEADERBOARD" in out
        assert "Best" in out
        assert "Worst" in out
        assert "Reproduce" in out
        assert "--sweep quick" in out

    def test_sweep_preset_colon_syntax(self, tmp_path, monkeypatch):
        """--sweep preset:quick is accepted as an alias for --sweep quick."""
        import json as _json

        from packages.polymarket.simtrader.sweeps.runner import SweepRunResult

        mock_picker = MagicMock()
        mock_picker.resolve_slug.return_value = self._make_resolved()
        mock_picker.validate_book.return_value = MagicMock(valid=True, reason="ok")

        sweep_called: list = [False]

        def FakeTapeRecorder(tape_dir, asset_ids, strict=False):
            rec = MagicMock()

            def fake_record(duration_seconds=None, ws_url=None):
                tape_dir.mkdir(parents=True, exist_ok=True)
                (tape_dir / "events.jsonl").write_text(
                    _json.dumps({"seq": 0, "ts_recv": 1.0, "asset_id": YES_TOKEN,
                                 "event_type": "book", "bids": [], "asks": []}) + "\n"
                    + _json.dumps({"seq": 1, "ts_recv": 1.1, "asset_id": NO_TOKEN,
                                  "event_type": "book", "bids": [], "asks": []}) + "\n"
                )
                (tape_dir / "meta.json").write_text(
                    _json.dumps({"ws_url": "wss://fake", "asset_ids": asset_ids,
                                 "event_count": 2, "warnings": []}) + "\n"
                )

            rec.record = fake_record
            return rec

        def fake_run_sweep(params, sweep_config):
            sweep_called[0] = True
            sweep_dir = params.artifacts_root / "sweeps" / params.sweep_id
            sweep_dir.mkdir(parents=True, exist_ok=True)
            summary = {
                "sweep_id": params.sweep_id, "scenarios": [],
                "aggregate": {
                    "best_net_profit": "0", "best_scenario": None,
                    "median_net_profit": "0", "median_scenario": None,
                    "worst_net_profit": "0", "worst_scenario": None,
                },
            }
            (sweep_dir / "sweep_manifest.json").write_text(_json.dumps({}) + "\n")
            (sweep_dir / "sweep_summary.json").write_text(_json.dumps(summary) + "\n")
            return SweepRunResult(
                sweep_id=params.sweep_id, sweep_dir=sweep_dir,
                summary=summary, manifest={},
            )

        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.market_picker.MarketPicker",
                return_value=mock_picker,
            ),
            patch(
                "packages.polymarket.simtrader.tape.recorder.TapeRecorder",
                side_effect=FakeTapeRecorder,
            ),
            patch(
                "packages.polymarket.simtrader.sweeps.runner.run_sweep",
                side_effect=fake_run_sweep,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                ["quickrun", "--market", SLUG, "--duration", "1", "--sweep", "preset:quick"]
            )

        assert exit_code == 0
        assert sweep_called[0], "run_sweep was not called for preset:quick"

    def test_unknown_sweep_preset_returns_error(self, tmp_path, monkeypatch):
        """An unknown --sweep preset returns exit code 1."""
        import json as _json

        mock_picker = MagicMock()
        mock_picker.resolve_slug.return_value = self._make_resolved()
        mock_picker.validate_book.return_value = MagicMock(valid=True, reason="ok")

        def FakeTapeRecorder(tape_dir, asset_ids, strict=False):
            rec = MagicMock()

            def fake_record(duration_seconds=None, ws_url=None):
                tape_dir.mkdir(parents=True, exist_ok=True)
                (tape_dir / "events.jsonl").write_text(
                    _json.dumps({"seq": 0, "ts_recv": 1.0, "asset_id": YES_TOKEN,
                                 "event_type": "book", "bids": [], "asks": []}) + "\n"
                    + _json.dumps({"seq": 1, "ts_recv": 1.1, "asset_id": NO_TOKEN,
                                  "event_type": "book", "bids": [], "asks": []}) + "\n"
                )
                (tape_dir / "meta.json").write_text(
                    _json.dumps({"ws_url": "wss://fake", "asset_ids": asset_ids,
                                 "event_count": 2, "warnings": []}) + "\n"
                )

            rec.record = fake_record
            return rec

        monkeypatch.setattr("tools.cli.simtrader.DEFAULT_ARTIFACTS_DIR", tmp_path / "sim")

        with (
            patch("packages.polymarket.gamma.GammaClient", return_value=MagicMock()),
            patch("packages.polymarket.clob.ClobClient", return_value=MagicMock()),
            patch(
                "packages.polymarket.simtrader.market_picker.MarketPicker",
                return_value=mock_picker,
            ),
            patch(
                "packages.polymarket.simtrader.tape.recorder.TapeRecorder",
                side_effect=FakeTapeRecorder,
            ),
        ):
            from tools.cli.simtrader import main

            exit_code = main(
                ["quickrun", "--market", SLUG, "--duration", "1", "--sweep", "bogus_preset"]
            )

        assert exit_code == 1


# ---------------------------------------------------------------------------
# YES/NO mapping robustness tests (Task 1)
# ---------------------------------------------------------------------------


class TestYesNoMapping:
    """Tests for the two-tier YES/NO identification in MarketPicker."""

    def _picker(self, outcomes, token_ids=None):
        from packages.polymarket.simtrader.market_picker import MarketPicker

        ids = token_ids or [YES_TOKEN, NO_TOKEN]
        market = _make_market(outcomes=outcomes, clob_token_ids=ids)
        gamma = MagicMock()
        gamma.fetch_markets_filtered.return_value = [market]
        return MarketPicker(gamma, MagicMock())

    def test_yes_no_standard(self):
        """Yes/No → yes_token_id=YES_TOKEN, mapping_tier=explicit."""
        picker = self._picker(["Yes", "No"])
        result = picker.resolve_slug(SLUG)
        assert result.yes_token_id == YES_TOKEN
        assert result.no_token_id == NO_TOKEN
        assert result.mapping_tier == "explicit"

    def test_true_false_mapping(self):
        """True/False outcomes are mapped correctly via alias tier."""
        picker = self._picker(["True", "False"])
        result = picker.resolve_slug(SLUG)
        assert result.yes_token_id == YES_TOKEN
        assert result.no_token_id == NO_TOKEN
        assert result.mapping_tier == "alias"

    def test_up_down_mapping(self):
        """Up/Down outcomes → Up=YES, Down=NO via alias tier."""
        picker = self._picker(["Up", "Down"])
        result = picker.resolve_slug(SLUG)
        assert result.yes_token_id == YES_TOKEN
        assert result.no_token_id == NO_TOKEN
        assert result.mapping_tier == "alias"

    def test_down_up_reversed_mapping(self):
        """Down/Up reversed order → Up still maps to YES (index 1)."""
        picker = self._picker(
            ["Down", "Up"],
            token_ids=[NO_TOKEN, YES_TOKEN],
        )
        result = picker.resolve_slug(SLUG)
        assert result.yes_token_id == YES_TOKEN
        assert result.no_token_id == NO_TOKEN

    def test_yes_beats_up_when_both_present(self):
        """If one outcome is 'Yes' (tier-1), it wins over 'Up' (tier-2)."""
        picker = self._picker(
            ["Up", "Yes"],
            token_ids=[NO_TOKEN, YES_TOKEN],
        )
        result = picker.resolve_slug(SLUG)
        # 'Yes' is at index 1 → YES_TOKEN at index 1
        assert result.yes_token_id == YES_TOKEN
        assert result.yes_label == "Yes"

    def test_false_true_reversed(self):
        """False/True reversed order → True still maps to YES."""
        picker = self._picker(
            ["False", "True"],
            token_ids=[NO_TOKEN, YES_TOKEN],
        )
        result = picker.resolve_slug(SLUG)
        assert result.yes_token_id == YES_TOKEN

    def test_ambiguous_outcomes_raise_clear_error(self):
        """Rain/Shine outcomes → MarketPickerError with raw names in message."""
        from packages.polymarket.simtrader.market_picker import MarketPickerError

        picker = self._picker(["Rain", "Shine"])
        with pytest.raises(MarketPickerError) as exc_info:
            picker.resolve_slug(SLUG)
        msg = str(exc_info.value)
        assert "Rain" in msg
        assert "Shine" in msg
        assert SLUG in msg

    def test_ambiguous_outcomes_error_includes_market_slug(self):
        """Error message must include the slug so user can diagnose."""
        from packages.polymarket.simtrader.market_picker import MarketPickerError

        slug = "will-team-x-win-championship"
        market = _make_market(slug=slug, outcomes=["Team X", "Team Y"])
        gamma = MagicMock()
        gamma.fetch_markets_filtered.return_value = [market]
        from packages.polymarket.simtrader.market_picker import MarketPicker

        picker = MarketPicker(gamma, MagicMock())
        with pytest.raises(MarketPickerError) as exc_info:
            picker.resolve_slug(slug)
        assert slug in str(exc_info.value)


# ---------------------------------------------------------------------------
# Depth / liquidity filter tests (Task 1)
# ---------------------------------------------------------------------------


class TestDepthFilter:
    """Tests for min_depth_size filtering in validate_book."""

    def _picker(self, book_data):
        from packages.polymarket.simtrader.market_picker import MarketPicker

        clob = MagicMock()
        clob.fetch_book.return_value = book_data
        return MarketPicker(MagicMock(), clob)

    def test_empty_book_still_rejected_before_depth_check(self):
        """Empty book is rejected as empty_book before depth filter runs."""
        picker = self._picker({"bids": [], "asks": []})
        result = picker.validate_book(YES_TOKEN, min_depth_size=10.0)
        assert not result.valid
        assert result.reason == "empty_book"

    def test_shallow_book_rejected_when_below_threshold(self):
        """Book with total depth 30 rejected when min_depth_size=50."""
        book = {
            "bids": [{"price": "0.48", "size": "10"}, {"price": "0.47", "size": "5"}],
            "asks": [{"price": "0.52", "size": "10"}, {"price": "0.53", "size": "5"}],
        }
        picker = self._picker(book)
        result = picker.validate_book(YES_TOKEN, min_depth_size=50.0, top_n_levels=3)
        assert not result.valid
        assert result.reason == "shallow_book"
        assert result.depth_total is not None
        assert result.depth_total == pytest.approx(30.0)

    def test_deep_book_accepted_above_threshold(self):
        """Book with depth 200 accepted when min_depth_size=100."""
        book = {
            "bids": [
                {"price": "0.48", "size": "50"},
                {"price": "0.47", "size": "50"},
            ],
            "asks": [
                {"price": "0.52", "size": "50"},
                {"price": "0.53", "size": "50"},
            ],
        }
        picker = self._picker(book)
        result = picker.validate_book(YES_TOKEN, min_depth_size=100.0, top_n_levels=3)
        assert result.valid
        assert result.reason == "ok"
        assert result.depth_total == pytest.approx(200.0)

    def test_depth_filter_disabled_when_zero(self):
        """min_depth_size=0 (default) disables depth check."""
        # Only 5 total size — would fail depth check if enabled
        book = {
            "bids": [{"price": "0.48", "size": "1"}],
            "asks": [{"price": "0.52", "size": "4"}],
        }
        picker = self._picker(book)
        result = picker.validate_book(YES_TOKEN, min_depth_size=0.0)
        assert result.valid
        assert result.reason == "ok"
        assert result.depth_total is None  # Not computed when disabled

    def test_depth_respects_top_n_levels(self):
        """Only top N levels per side are included in depth sum."""
        book = {
            "bids": [
                {"price": "0.49", "size": "10"},  # top 1
                {"price": "0.48", "size": "10"},  # top 2
                {"price": "0.47", "size": "10"},  # top 3
                {"price": "0.46", "size": "100"},  # excluded (beyond top 3)
            ],
            "asks": [
                {"price": "0.51", "size": "10"},  # top 1
                {"price": "0.52", "size": "10"},  # top 2
                {"price": "0.53", "size": "10"},  # top 3
                {"price": "0.54", "size": "100"},  # excluded
            ],
        }
        picker = self._picker(book)
        # top 3 per side = 30 bids + 30 asks = 60 total
        result = picker.validate_book(YES_TOKEN, min_depth_size=50.0, top_n_levels=3)
        assert result.valid
        assert result.depth_total == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# auto_pick collect_skips / dry_run verbose (Task 1)
# ---------------------------------------------------------------------------


class TestAutoPickCollectSkips:
    """Tests for collect_skips parameter in auto_pick."""

    def test_collect_skips_captures_empty_book_reason(self):
        """collect_skips records empty_book reason for skipped market."""
        from packages.polymarket.simtrader.market_picker import MarketPicker

        slug_bad = "market-bad"
        slug_good = "market-good"
        yes_bad, no_bad = "yes_bad0", "no_bad0"
        yes_good, no_good = "yes_good", "no_good"

        market_bad = _make_market(slug=slug_bad, outcomes=["Yes", "No"],
                                  clob_token_ids=[yes_bad, no_bad])
        market_good = _make_market(slug=slug_good, outcomes=["Yes", "No"],
                                   clob_token_ids=[yes_good, no_good])

        gamma = MagicMock()
        gamma.fetch_markets_page.return_value = [
            {"slug": slug_bad, "outcomes": '["Yes","No"]',
             "clobTokenIds": f'["{yes_bad}","{no_bad}"]'},
            {"slug": slug_good, "outcomes": '["Yes","No"]',
             "clobTokenIds": f'["{yes_good}","{no_good}"]'},
        ]

        def _filtered(slugs=None, **_kw):
            by_slug = {slug_bad: market_bad, slug_good: market_good}
            return [by_slug[slugs[0]]] if slugs else []

        gamma.fetch_markets_filtered.side_effect = _filtered

        clob = MagicMock()
        clob.fetch_book.side_effect = lambda tid: (
            {"bids": [], "asks": []} if tid in (yes_bad, no_bad) else _make_book()
        )

        picker = MarketPicker(gamma, clob)
        skip_log: list = []
        result = picker.auto_pick(collect_skips=skip_log)

        assert result.slug == slug_good
        assert len(skip_log) == 1
        assert skip_log[0]["slug"] == slug_bad
        assert skip_log[0]["reason"] == "empty_book"
        assert skip_log[0]["side"] in ("YES", "NO")

    def test_collect_skips_captures_shallow_book_with_depth(self):
        """collect_skips includes depth_total when book is shallow."""
        from packages.polymarket.simtrader.market_picker import MarketPicker

        slug_shallow = "shallow-mkt"
        slug_deep = "deep-mkt"
        yes_s, no_s = "yes_shll", "no_shll0"
        yes_d, no_d = "yes_deep", "no_deep"

        market_s = _make_market(slug=slug_shallow, clob_token_ids=[yes_s, no_s])
        market_d = _make_market(slug=slug_deep, clob_token_ids=[yes_d, no_d])

        gamma = MagicMock()
        gamma.fetch_markets_page.return_value = [
            {"slug": slug_shallow, "outcomes": '["Yes","No"]',
             "clobTokenIds": f'["{yes_s}","{no_s}"]'},
            {"slug": slug_deep, "outcomes": '["Yes","No"]',
             "clobTokenIds": f'["{yes_d}","{no_d}"]'},
        ]

        def _filtered(slugs=None, **_kw):
            by_slug = {slug_shallow: market_s, slug_deep: market_d}
            return [by_slug[slugs[0]]] if slugs else []

        gamma.fetch_markets_filtered.side_effect = _filtered

        def _fetch_book(tid):
            if tid in (yes_s, no_s):
                return {"bids": [{"price": "0.49", "size": "2"}],
                        "asks": [{"price": "0.51", "size": "3"}]}
            return _make_book()  # default: 100 size each side

        clob = MagicMock()
        clob.fetch_book.side_effect = _fetch_book

        picker = MarketPicker(gamma, clob)
        skip_log: list = []
        result = picker.auto_pick(
            min_depth_size=50.0, collect_skips=skip_log
        )

        assert result.slug == slug_deep
        assert len(skip_log) == 1
        skip = skip_log[0]
        assert skip["slug"] == slug_shallow
        assert skip["reason"] == "shallow_book"
        assert skip["depth_total"] is not None
        assert skip["depth_total"] < 50.0
