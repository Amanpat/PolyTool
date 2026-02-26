"""Tests for SimTrader tape replay and L2 book reconstruction.

Test plan
---------
1. L2Book snapshot:       applying a 'book' event initializes bids/asks correctly.
2. L2Book price_change:   delta events update levels; size-0 removes a level.
3. Strict mode:           price_change before book raises L2BookError.
4. Lenient mode:          price_change before book warns and no-ops.
5. Replay produces rows:  ReplayRunner emits one row per book-affecting event.
6. Replay values:         best_bid/best_ask are correct after each step.
7. Determinism:           same events.jsonl -> byte-identical output files.
8. CSV output:            --format csv produces a valid CSV with header.
9. Multi-level best:      best_bid = max of all bid prices.
10. Snapshot clears book: second snapshot replaces the first entirely.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.polymarket.simtrader.orderbook.l2book import L2Book, L2BookError
from packages.polymarket.simtrader.replay.runner import ReplayRunner
from packages.polymarket.simtrader.tape.schema import PARSER_VERSION

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _book_event(
    seq: int = 0,
    ts: float = 1000.0,
    asset_id: str = "tok1",
    bids: list | None = None,
    asks: list | None = None,
) -> dict:
    return {
        "parser_version": PARSER_VERSION,
        "seq": seq,
        "ts_recv": ts,
        "event_type": "book",
        "asset_id": asset_id,
        "market": "0xabc",
        "bids": bids if bids is not None else [{"price": "0.55", "size": "100"}],
        "asks": asks if asks is not None else [{"price": "0.57", "size": "200"}],
    }


def _price_change(
    seq: int,
    ts: float = 1001.0,
    asset_id: str = "tok1",
    changes: list | None = None,
) -> dict:
    return {
        "parser_version": PARSER_VERSION,
        "seq": seq,
        "ts_recv": ts,
        "event_type": "price_change",
        "asset_id": asset_id,
        "changes": changes if changes is not None else [],
    }


def _write_events(path: Path, events: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for evt in events:
            fh.write(json.dumps(evt) + "\n")


# ---------------------------------------------------------------------------
# 1-2. L2Book: snapshot
# ---------------------------------------------------------------------------


class TestL2BookSnapshot:
    def test_book_initializes_best_bid_and_ask(self):
        book = L2Book("tok1")
        book.apply(
            _book_event(
                bids=[{"price": "0.55", "size": "100"}],
                asks=[{"price": "0.57", "size": "200"}],
            )
        )
        assert book.best_bid == pytest.approx(0.55)
        assert book.best_ask == pytest.approx(0.57)

    def test_best_bid_is_highest_bid_price(self):
        book = L2Book("tok1")
        book.apply(
            _book_event(
                bids=[
                    {"price": "0.50", "size": "50"},
                    {"price": "0.55", "size": "100"},
                    {"price": "0.52", "size": "75"},
                ],
                asks=[{"price": "0.57", "size": "200"}],
            )
        )
        assert book.best_bid == pytest.approx(0.55)

    def test_best_ask_is_lowest_ask_price(self):
        book = L2Book("tok1")
        book.apply(
            _book_event(
                bids=[{"price": "0.55", "size": "100"}],
                asks=[
                    {"price": "0.60", "size": "50"},
                    {"price": "0.57", "size": "200"},
                    {"price": "0.65", "size": "30"},
                ],
            )
        )
        assert book.best_ask == pytest.approx(0.57)

    def test_empty_book_returns_none(self):
        book = L2Book("tok1")
        book.apply(_book_event(bids=[], asks=[]))
        assert book.best_bid is None
        assert book.best_ask is None

    def test_second_snapshot_clears_previous_state(self):
        book = L2Book("tok1")
        book.apply(
            _book_event(
                bids=[{"price": "0.55", "size": "100"}],
                asks=[{"price": "0.57", "size": "200"}],
            )
        )
        # Replace with entirely different levels.
        book.apply(
            _book_event(
                bids=[{"price": "0.60", "size": "10"}],
                asks=[{"price": "0.61", "size": "20"}],
            )
        )
        assert book.best_bid == pytest.approx(0.60)
        assert book.best_ask == pytest.approx(0.61)


# ---------------------------------------------------------------------------
# L2Book: price_change
# ---------------------------------------------------------------------------


class TestL2BookPriceChange:
    def _initialized_book(self) -> L2Book:
        book = L2Book("tok1")
        book.apply(
            _book_event(
                bids=[
                    {"price": "0.54", "size": "50"},
                    {"price": "0.55", "size": "100"},
                ],
                asks=[{"price": "0.57", "size": "200"}],
            )
        )
        return book

    def test_add_better_bid_updates_best_bid(self):
        book = self._initialized_book()
        book.apply(
            _price_change(1, changes=[{"side": "BUY", "price": "0.56", "size": "75"}])
        )
        assert book.best_bid == pytest.approx(0.56)

    def test_remove_best_bid_exposes_next_level(self):
        book = self._initialized_book()
        # Remove the 0.55 bid (best); 0.54 should become best.
        book.apply(
            _price_change(1, changes=[{"side": "BUY", "price": "0.55", "size": "0"}])
        )
        assert book.best_bid == pytest.approx(0.54)

    def test_update_ask_size_does_not_change_best_ask(self):
        book = self._initialized_book()
        book.apply(
            _price_change(1, changes=[{"side": "SELL", "price": "0.57", "size": "350"}])
        )
        # Price unchanged; size update only.
        assert book.best_ask == pytest.approx(0.57)

    def test_add_better_ask_updates_best_ask(self):
        book = self._initialized_book()
        book.apply(
            _price_change(1, changes=[{"side": "SELL", "price": "0.56", "size": "120"}])
        )
        assert book.best_ask == pytest.approx(0.56)

    def test_multiple_changes_in_single_event(self):
        book = self._initialized_book()
        book.apply(
            _price_change(
                1,
                changes=[
                    {"side": "BUY", "price": "0.55", "size": "0"},   # remove
                    {"side": "BUY", "price": "0.53", "size": "200"},  # add
                    {"side": "SELL", "price": "0.58", "size": "80"},  # add
                ],
            )
        )
        # best bid: 0.54 (0.55 removed; 0.54 and 0.53 remain; 0.54 is higher)
        assert book.best_bid == pytest.approx(0.54)
        # best ask: 0.57 (0.58 added but 0.57 is lower)
        assert book.best_ask == pytest.approx(0.57)

    def test_price_change_before_snapshot_raises_in_strict_mode(self):
        book = L2Book("tok1", strict=True)
        with pytest.raises(L2BookError, match="before book snapshot"):
            book.apply(
                _price_change(0, changes=[{"side": "BUY", "price": "0.55", "size": "100"}])
            )

    def test_price_change_before_snapshot_noop_in_lenient_mode(self):
        book = L2Book("tok1", strict=False)
        # Should not raise; book stays uninitialized.
        book.apply(
            _price_change(0, changes=[{"side": "BUY", "price": "0.55", "size": "100"}])
        )
        assert book.best_bid is None


# ---------------------------------------------------------------------------
# ReplayRunner: correctness + determinism
# ---------------------------------------------------------------------------


class TestReplayRunner:
    # A simple four-event sequence used by multiple tests.
    _EVENTS = [
        _book_event(
            0, 1000.0,
            bids=[{"price": "0.55", "size": "100"}],
            asks=[{"price": "0.57", "size": "200"}],
        ),
        _price_change(1, 1001.0, changes=[{"side": "BUY", "price": "0.56", "size": "75"}]),
        _price_change(2, 1002.0, changes=[{"side": "BUY", "price": "0.55", "size": "0"}]),
        _price_change(3, 1003.0, changes=[{"side": "SELL", "price": "0.58", "size": "50"}]),
    ]

    def _run(self, tmp_path: Path, run_name: str = "run1", **kwargs) -> Path:
        tape = tmp_path / "events.jsonl"
        _write_events(tape, self._EVENTS)
        return ReplayRunner(tape, tmp_path / run_name, **kwargs).run()

    # --- basic output ---

    def test_replay_creates_output_file(self, tmp_path):
        out = self._run(tmp_path)
        assert out.exists()

    def test_replay_produces_one_row_per_book_affecting_event(self, tmp_path):
        out = self._run(tmp_path)
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        # 1 book + 3 price_change events
        assert len(rows) == 4

    def test_replay_row_has_required_fields(self, tmp_path):
        out = self._run(tmp_path)
        row = json.loads(out.read_text().splitlines()[0])
        assert {"seq", "ts_recv", "asset_id", "event_type", "best_bid", "best_ask"} <= row.keys()

    # --- correct values ---

    def test_initial_best_bid_ask_from_snapshot(self, tmp_path):
        out = self._run(tmp_path)
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        assert rows[0]["best_bid"] == pytest.approx(0.55)
        assert rows[0]["best_ask"] == pytest.approx(0.57)
        assert rows[0]["event_type"] == "book"

    def test_best_bid_updates_after_better_bid(self, tmp_path):
        out = self._run(tmp_path)
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        # seq=1: added 0.56 bid
        assert rows[1]["best_bid"] == pytest.approx(0.56)

    def test_best_bid_unchanged_after_removing_lower_level(self, tmp_path):
        out = self._run(tmp_path)
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        # seq=2: removed 0.55; best is still 0.56
        assert rows[2]["best_bid"] == pytest.approx(0.56)

    def test_best_ask_unchanged_when_worse_ask_added(self, tmp_path):
        out = self._run(tmp_path)
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        # seq=3: added 0.58 ask; 0.57 is still better
        assert rows[3]["best_ask"] == pytest.approx(0.57)

    # --- determinism ---

    def test_two_replays_produce_identical_output(self, tmp_path):
        tape = tmp_path / "events.jsonl"
        _write_events(tape, self._EVENTS)

        out1 = ReplayRunner(tape, tmp_path / "run1", strict=True).run()
        out2 = ReplayRunner(tape, tmp_path / "run2", strict=True).run()

        assert out1.read_text() == out2.read_text(), (
            "Replay is not deterministic: two runs on the same tape produced different output."
        )

    def test_determinism_unaffected_by_run_id(self, tmp_path):
        tape = tmp_path / "events.jsonl"
        _write_events(tape, self._EVENTS)

        out_a = ReplayRunner(tape, tmp_path / "runA", strict=True).run()
        out_b = ReplayRunner(tape, tmp_path / "runB", strict=True).run()

        assert out_a.read_text() == out_b.read_text()

    # --- CSV output ---

    def test_csv_output_has_correct_extension(self, tmp_path):
        out = self._run(tmp_path, output_format="csv")
        assert out.suffix == ".csv"

    def test_csv_output_has_header_and_data(self, tmp_path):
        out = self._run(tmp_path, output_format="csv")
        lines = out.read_text().splitlines()
        assert lines[0] == "seq,ts_recv,asset_id,event_type,best_bid,best_ask"
        assert len(lines) == 5  # header + 4 data rows

    # --- meta.json ---

    def test_meta_json_written(self, tmp_path):
        tape = tmp_path / "events.jsonl"
        _write_events(tape, self._EVENTS)
        run_dir = tmp_path / "run1"
        ReplayRunner(tape, run_dir, strict=True).run()
        meta = json.loads((run_dir / "meta.json").read_text())
        assert meta["run_quality"] == "ok"
        assert meta["total_events"] == 4
        assert meta["timeline_rows"] == 4
        assert meta["warnings"] == []

    # --- strict mode ---

    def test_strict_mode_raises_on_price_change_before_snapshot(self, tmp_path):
        tape = tmp_path / "events.jsonl"
        _write_events(
            tape,
            [_price_change(0, changes=[{"side": "BUY", "price": "0.55", "size": "100"}])],
        )
        with pytest.raises(L2BookError):
            ReplayRunner(tape, tmp_path / "run1", strict=True).run()

    def test_lenient_mode_skips_price_change_before_snapshot(self, tmp_path):
        tape = tmp_path / "events.jsonl"
        _write_events(
            tape,
            [_price_change(0, changes=[{"side": "BUY", "price": "0.55", "size": "100"}])],
        )
        # Should not raise; produces 0 timeline rows.
        out = ReplayRunner(tape, tmp_path / "run1", strict=False).run()
        rows = [l for l in out.read_text().splitlines() if l.strip()]
        assert rows == []

    # --- empty tape ---

    def test_empty_tape_raises_value_error(self, tmp_path):
        tape = tmp_path / "events.jsonl"
        tape.write_text("")
        with pytest.raises(ValueError, match="No events found"):
            ReplayRunner(tape, tmp_path / "run1").run()


# ---------------------------------------------------------------------------
# L2Book: apply_single_delta (modern batched format)
# ---------------------------------------------------------------------------


class TestL2BookSingleDelta:
    """Tests for L2Book.apply_single_delta — the modern price_changes[] path."""

    def _initialized_book(self) -> L2Book:
        book = L2Book("tok1", strict=True)
        book.apply(
            _book_event(
                bids=[{"price": "0.55", "size": "100"}],
                asks=[{"price": "0.57", "size": "200"}],
            )
        )
        return book

    def test_apply_single_delta_updates_bid(self):
        book = self._initialized_book()
        book.apply_single_delta({"side": "BUY", "price": "0.56", "size": "75"})
        assert book.best_bid == pytest.approx(0.56)

    def test_apply_single_delta_updates_ask(self):
        book = self._initialized_book()
        book.apply_single_delta({"side": "SELL", "price": "0.54", "size": "50"})
        assert book.best_ask == pytest.approx(0.54)

    def test_apply_single_delta_removes_level_on_size_zero(self):
        book = self._initialized_book()
        # Remove the only bid level.
        book.apply_single_delta({"side": "BUY", "price": "0.55", "size": "0"})
        assert book.best_bid is None

    def test_apply_single_delta_returns_true_when_applied(self):
        book = self._initialized_book()
        result = book.apply_single_delta({"side": "BUY", "price": "0.56", "size": "50"})
        assert result is True

    def test_apply_single_delta_strict_before_snapshot_raises(self):
        book = L2Book("tok1", strict=True)
        with pytest.raises(L2BookError, match="before book snapshot"):
            book.apply_single_delta({"side": "BUY", "price": "0.55", "size": "100"})

    def test_apply_single_delta_lenient_before_snapshot_returns_false(self):
        book = L2Book("tok1", strict=False)
        result = book.apply_single_delta({"side": "BUY", "price": "0.55", "size": "100"})
        assert result is False
        assert book.best_bid is None


# ---------------------------------------------------------------------------
# ReplayRunner: modern batched price_changes[] format
# ---------------------------------------------------------------------------


def _batched_price_change(
    seq: int,
    ts: float,
    entries: list[dict],
) -> dict:
    """Build a modern batched price_change event (no top-level asset_id)."""
    return {
        "parser_version": PARSER_VERSION,
        "seq": seq,
        "ts_recv": ts,
        "event_type": "price_change",
        "price_changes": entries,
    }


class TestReplayRunnerBatchedPriceChange:
    """ReplayRunner handles the modern Polymarket batched price_changes[] format."""

    # Tape: two book snapshots (YES + NO) then one batched price_change.
    _YES = "yes-tok"
    _NO = "no-tok"

    def _make_tape(self, tmp_path: Path) -> Path:
        tape = tmp_path / "events.jsonl"
        events = [
            # YES snapshot
            _book_event(seq=0, ts=0.0, asset_id=self._YES,
                        bids=[{"price": "0.44", "size": "300"}],
                        asks=[{"price": "0.46", "size": "200"}]),
            # NO snapshot
            _book_event(seq=1, ts=1.0, asset_id=self._NO,
                        bids=[{"price": "0.52", "size": "100"}],
                        asks=[{"price": "0.54", "size": "150"}]),
            # Batched delta: updates YES bid AND NO ask simultaneously.
            _batched_price_change(seq=2, ts=2.0, entries=[
                {"asset_id": self._YES, "side": "BUY", "price": "0.45", "size": "80"},
                {"asset_id": self._NO, "side": "SELL", "price": "0.53", "size": "90"},
            ]),
        ]
        _write_events(tape, events)
        return tape

    def test_both_books_updated_by_batch(self, tmp_path):
        tape = self._make_tape(tmp_path)
        out = ReplayRunner(tape, tmp_path / "run1", strict=True).run()
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        # Extract final row per asset_id to check end state.
        yes_rows = [r for r in rows if r["asset_id"] == self._YES]
        no_rows  = [r for r in rows if r["asset_id"] == self._NO]
        assert yes_rows, "Expected timeline rows for YES asset"
        assert no_rows, "Expected timeline rows for NO asset"
        # YES bid updated to 0.45 by the batch.
        assert yes_rows[-1]["best_bid"] == pytest.approx(0.45)
        # NO ask updated to 0.53 (lower than 0.54 snapshot).
        assert no_rows[-1]["best_ask"] == pytest.approx(0.53)

    def test_batched_event_emits_multiple_timeline_rows(self, tmp_path):
        tape = self._make_tape(tmp_path)
        out = ReplayRunner(tape, tmp_path / "run1", strict=True).run()
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        # 2 snapshot rows + 2 rows from the batched price_change (one per entry).
        assert len(rows) == 4

    def test_batched_event_rows_carry_correct_event_type(self, tmp_path):
        tape = self._make_tape(tmp_path)
        out = ReplayRunner(tape, tmp_path / "run1", strict=True).run()
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        batched_rows = [r for r in rows if r["seq"] == 2]
        assert len(batched_rows) == 2
        assert all(r["event_type"] == "price_change" for r in batched_rows)

    def test_meta_json_counts_batched_events_correctly(self, tmp_path):
        tape = self._make_tape(tmp_path)
        run_dir = tmp_path / "run1"
        ReplayRunner(tape, run_dir, strict=True).run()
        meta = json.loads((run_dir / "meta.json").read_text())
        assert meta["total_events"] == 3   # 2 snapshots + 1 batched
        assert meta["timeline_rows"] == 4  # 2 snapshots + 2 entries from batch

    def test_batched_event_with_unknown_asset_is_skipped(self, tmp_path):
        tape = tmp_path / "events.jsonl"
        events = [
            _book_event(seq=0, ts=0.0, asset_id=self._YES,
                        bids=[{"price": "0.44", "size": "100"}],
                        asks=[{"price": "0.46", "size": "100"}]),
            # Batch includes an unknown asset (not in books).
            _batched_price_change(seq=1, ts=1.0, entries=[
                {"asset_id": self._YES, "side": "BUY", "price": "0.45", "size": "50"},
                {"asset_id": "unknown-tok", "side": "BUY", "price": "0.30", "size": "10"},
            ]),
        ]
        _write_events(tape, events)
        out = ReplayRunner(tape, tmp_path / "run1", strict=False).run()
        rows = [json.loads(l) for l in out.read_text().splitlines() if l.strip()]
        # The unknown-tok book is lazily created; strict=False means no raise.
        yes_rows = [r for r in rows if r["asset_id"] == self._YES]
        assert yes_rows[-1]["best_bid"] == pytest.approx(0.45)
