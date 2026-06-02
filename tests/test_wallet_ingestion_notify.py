"""Wallet-ingestion pending-candidate notifications + display-time evidence.

Covers the post-v1 follow-up (WI-5 Vera two-way descoped):

A) ``compute_row_evidence`` recomputes :func:`summarize_evidence` from a wallet's
   scan data at DISPLAY TIME, so a worker-advanced row (generic stored reason)
   surfaces real evidence in ``discovery review --list-pending``.
B) ``notify_pending_candidate(s)`` posts exactly one deduped Discord message per
   pending candidate, carrying the full address, the evidence body, and the
   approve/deny CLI commands -- and NEVER raises on a webhook failure.

Fully offline: no network, no real ClickHouse, no Discord. The metrics reader
and the post callable are injected; the dedup state file is a tmp_path.
"""
from __future__ import annotations

import json

import pytest

from packages.polymarket.discovery.pending_notify import (
    compute_row_evidence,
    format_pending_notification,
    notify_pending_candidate,
    notify_pending_candidates,
)

_FULL = "0xcf6041b4c3d3c9e1f0a1b2c3d4e5f60718293a4b"  # 0x + 40 hex
_WORKER_REASON = "scan-worker drained scan_queue and produced a dossier"


def _worker_row(reason: str = _WORKER_REASON) -> dict:
    """A watchlist row as written by the WI-1 worker advancer (generic reason)."""
    return {
        "wallet_address": _FULL,
        "lifecycle_state": "scanned",
        "review_status": "pending",
        "tier": "candidate",
        "locked": 0,
        "reason": reason,
        "last_scan_run_id": "run_abc123",
    }


# real scan metrics as produced by wallet_scan._extract_user_metrics
_REAL_METRICS = {
    "realized_net_pnl": 24000.0,
    "positions_total": 180,
    "clv_coverage_rate": 0.72,
}
_REAL_EVIDENCE = "+$24.0k PnL, 180 trades, CLV 72%"


# ---------------------------------------------------------------------------
# Part A: compute_row_evidence
# ---------------------------------------------------------------------------


class TestComputeRowEvidence:
    def test_recomputes_real_evidence_over_generic_worker_reason(self):
        """Worker-advanced row (generic reason) -> real computed evidence."""
        row = _worker_row()
        summary = compute_row_evidence(row, metrics_reader=lambda r: dict(_REAL_METRICS))
        assert summary == _REAL_EVIDENCE
        assert summary != _WORKER_REASON

    def test_falls_back_to_stored_reason_when_no_scan_data(self):
        row = _worker_row(reason="+$5.0k PnL")
        summary = compute_row_evidence(row, metrics_reader=lambda r: None)
        assert summary == "+$5.0k PnL"

    def test_falls_back_to_no_evidence_when_nothing_available(self):
        row = {"wallet_address": _FULL, "reason": "", "last_scan_run_id": ""}
        summary = compute_row_evidence(row, metrics_reader=lambda r: None)
        assert summary == "no evidence available"

    def test_empty_metrics_fall_back_to_reason(self):
        row = _worker_row(reason="stored")
        # metrics present but yield no summarizable dimensions -> use stored reason
        summary = compute_row_evidence(row, metrics_reader=lambda r: {"foo": "bar"})
        assert summary == "stored"

    def test_reader_exception_falls_back_safely(self):
        def _boom(_row):
            raise RuntimeError("reader blew up")

        row = _worker_row(reason="stored")
        # must not raise; falls back to stored reason
        summary = compute_row_evidence(row, metrics_reader=_boom)
        assert summary == "stored"

    def test_non_dict_row_is_safe(self):
        assert compute_row_evidence(None) == "no evidence available"  # type: ignore[arg-type]


class TestEvidenceInternalConsistency:
    """The reported bug: '+$124.0k PnL, 0 trades, CLV 94%' must never render."""

    # metrics shaped exactly as _extract_user_metrics returns them
    _FULL_METRICS = {
        "realized_net_pnl": 124000.0,
        "positions_total": 180,
        "win_rate": 0.64,
        "clv_coverage_rate": 0.94,
    }

    def test_full_metrics_render_consistently(self):
        summary = compute_row_evidence(
            _worker_row(), metrics_reader=lambda r: dict(self._FULL_METRICS)
        )
        # exact string (avoids "180 trades" matching a "0 trades" substring check)
        assert summary == "+$124.0k PnL, 64% win / 180 trades, CLV 94%"

    def test_nonzero_pnl_never_shows_zero_trades(self):
        # Simulate a regressed source: PnL present but trade count defaulted to 0.
        bad = {"realized_net_pnl": 124000.0, "positions_total": 0, "clv_coverage_rate": 0.94}
        summary = compute_row_evidence(_worker_row(), metrics_reader=lambda r: dict(bad))
        # misleading "0 trades" suppressed; trades omitted (not fabricated)
        assert summary == "+$124.0k PnL, CLV 94%"
        assert "trades" not in summary

    def test_nonzero_clv_with_missing_trades_omits_trades(self):
        bad = {"realized_net_pnl": 0.0, "positions_total": None, "clv_coverage_rate": 0.42}
        summary = compute_row_evidence(_worker_row(), metrics_reader=lambda r: dict(bad))
        assert "trades" not in summary
        assert "CLV 42%" in summary

    def test_genuine_zero_activity_is_left_alone(self):
        # No activity signal -> nothing to be inconsistent with; falls back to reason.
        empty = {"realized_net_pnl": None, "positions_total": None, "clv_coverage_rate": None}
        summary = compute_row_evidence(
            _worker_row(reason="stored"), metrics_reader=lambda r: dict(empty)
        )
        assert summary == "stored"


# ---------------------------------------------------------------------------
# format_pending_notification
# ---------------------------------------------------------------------------


class TestFormatPendingNotification:
    def test_contains_full_address_evidence_and_cli_commands(self):
        msg = format_pending_notification(_FULL, _REAL_EVIDENCE)
        assert _FULL in msg
        assert _REAL_EVIDENCE in msg
        assert f"python3 -m polytool discovery review --approve {_FULL}" in msg
        assert f"python3 -m polytool discovery review --deny {_FULL}" in msg

    def test_never_truncates_address(self):
        msg = format_pending_notification(_FULL, "x")
        assert "…" not in msg

    def test_empty_evidence_falls_back(self):
        msg = format_pending_notification(_FULL, "")
        assert "no evidence available" in msg

    def test_ascii_only(self):
        # Windows webhook/console safety: no non-ASCII bytes.
        msg = format_pending_notification(_FULL, _REAL_EVIDENCE)
        msg.encode("ascii")  # raises if any non-ASCII char slipped in


# ---------------------------------------------------------------------------
# Part B: notify_pending_candidate(s) -- posting, dedup, failure-safety
# ---------------------------------------------------------------------------


class TestNotifyPostsOnce:
    def test_entering_pending_posts_exactly_one_message(self, tmp_path):
        posted: list[str] = []
        state = tmp_path / "notified.json"

        summary = notify_pending_candidates(
            [_worker_row()],
            post=lambda text: (posted.append(text) or True),
            notified_path=state,
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )

        assert summary == {"considered": 1, "posted": 1, "deduped": 0, "failed": 0}
        assert len(posted) == 1
        body = posted[0]
        # full address + real (computed, not generic) evidence + both CLI lines
        assert _FULL in body
        assert _REAL_EVIDENCE in body
        assert _WORKER_REASON not in body
        assert f"--approve {_FULL}" in body
        assert f"--deny {_FULL}" in body

    def test_post_records_wallet_as_notified(self, tmp_path):
        state = tmp_path / "notified.json"
        res = notify_pending_candidate(
            _FULL, _REAL_EVIDENCE, post=lambda t: True, notified_path=state
        )
        assert res["posted"] and res["ok"] and not res["deduped"]
        from packages.polymarket.discovery.approval_request import load_notified

        assert _FULL.lower() in load_notified(state)


class TestNotifyDedup:
    def test_second_pass_does_not_re_notify(self, tmp_path):
        posted: list[str] = []
        state = tmp_path / "notified.json"
        rows = [_worker_row()]
        kw = dict(
            post=lambda text: (posted.append(text) or True),
            notified_path=state,
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )

        first = notify_pending_candidates(rows, **kw)
        second = notify_pending_candidates(rows, **kw)

        assert first["posted"] == 1
        assert second["posted"] == 0
        assert second["deduped"] == 1
        # exactly one webhook message across both passes
        assert len(posted) == 1

    def test_already_notified_wallet_is_skipped(self, tmp_path):
        state = tmp_path / "notified.json"
        from packages.polymarket.discovery.approval_request import mark_notified

        mark_notified(state, _FULL)
        posted: list[str] = []
        res = notify_pending_candidate(
            _FULL, "x", post=lambda t: (posted.append(t) or True), notified_path=state
        )
        assert res["deduped"] is True
        assert res["posted"] is False
        assert posted == []


class TestNotifyNeverRaises:
    def test_post_returning_false_is_not_fatal_and_not_marked(self, tmp_path):
        state = tmp_path / "notified.json"
        res = notify_pending_candidate(
            _FULL, "x", post=lambda t: False, notified_path=state
        )
        assert res["posted"] is True
        assert res["ok"] is False
        # failed delivery is NOT marked notified -> retried next pass
        from packages.polymarket.discovery.approval_request import load_notified

        assert _FULL.lower() not in load_notified(state)

    def test_post_raising_is_swallowed(self, tmp_path):
        state = tmp_path / "notified.json"

        def _raising_post(_text):
            raise ConnectionError("webhook down")

        # must not raise
        res = notify_pending_candidate(
            _FULL, "x", post=_raising_post, notified_path=state
        )
        assert res["ok"] is False
        assert res["posted"] is True

    def test_batch_failure_is_counted_not_raised(self, tmp_path):
        state = tmp_path / "notified.json"
        summary = notify_pending_candidates(
            [_worker_row()],
            post=lambda t: False,
            notified_path=state,
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )
        assert summary["failed"] == 1
        assert summary["posted"] == 0

    def test_bad_address_is_not_notified(self, tmp_path):
        state = tmp_path / "notified.json"
        posted: list[str] = []
        res = notify_pending_candidate(
            "0xcf60", "x", post=lambda t: (posted.append(t) or True), notified_path=state
        )
        assert res["posted"] is False
        assert posted == []


# ---------------------------------------------------------------------------
# CLI: --list-pending shows computed evidence (incl. worker-advanced row)
# ---------------------------------------------------------------------------


class TestListPendingShowsComputedEvidence:
    def test_list_pending_recomputes_evidence_for_worker_row(
        self, monkeypatch, capsys
    ):
        import tools.cli.discovery as disc
        import packages.polymarket.discovery.clickhouse_writer as chw
        import packages.polymarket.discovery.pending_notify as pn

        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "pw")
        # Row as written by the worker advancer: generic reason, has a run id.
        monkeypatch.setattr(chw, "read_pending_candidates", lambda **k: [_worker_row()])
        # Scan data is available at display time -> compute real evidence.
        monkeypatch.setattr(
            pn, "default_metrics_reader", lambda row: dict(_REAL_METRICS)
        )

        rc = disc.main(["review", "--list-pending", "--json"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert len(out) == 1
        item = out[0]
        assert item["wallet_address"] == _FULL
        # real computed evidence, NOT the generic worker reason
        assert item["evidence"] == _REAL_EVIDENCE
        assert item["evidence"] != _WORKER_REASON
        assert _REAL_EVIDENCE in item["request_text"]

    def test_list_pending_falls_back_to_stored_reason_without_scan_data(
        self, monkeypatch, capsys
    ):
        import tools.cli.discovery as disc
        import packages.polymarket.discovery.clickhouse_writer as chw
        import packages.polymarket.discovery.pending_notify as pn

        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "pw")
        monkeypatch.setattr(
            chw,
            "read_pending_candidates",
            lambda **k: [_worker_row(reason="+$9.0k PnL")],
        )
        monkeypatch.setattr(pn, "default_metrics_reader", lambda row: None)

        rc = disc.main(["review", "--list-pending", "--json"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out[0]["evidence"] == "+$9.0k PnL"

    def test_help_shows_no_notify_flag(self, capsys):
        import tools.cli.discovery as disc

        with pytest.raises(SystemExit):
            disc.main(["run-worker", "--help"])
        assert "--no-notify" in capsys.readouterr().out
