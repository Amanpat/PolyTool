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

from packages.polymarket.discovery.evidence_summary import (
    Evidence,
    summarize_evidence,
)
from packages.polymarket.discovery.pending_notify import (
    _fit_digest,
    _recent_form_values,
    _relative_age,
    _signal_line,
    build_digest_content,
    build_digest_embed,
    build_pending_embed,
    build_single_content,
    compute_row_evidence,
    format_pending_notification,
    notify_pending_candidate,
    notify_pending_candidates,
)


def _utc(iso: str):
    from datetime import datetime, timezone

    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)

_FULL = "0xcf6041b4c3d3c9e1f0a1b2c3d4e5f60718293a4b"  # 0x + 40 hex
_FULL2 = "0x84cfffc3f16dcc353094de30d4a45226eccd2f63"  # a second full address
_WORKER_REASON = "scan-worker drained scan_queue and produced a dossier"


def _worker_row(reason: str = _WORKER_REASON, wallet: str = _FULL,
                source: str | None = None) -> dict:
    """A watchlist row as written by the WI-1 worker advancer (generic reason)."""
    row = {
        "wallet_address": wallet,
        "lifecycle_state": "scanned",
        "review_status": "pending",
        "tier": "candidate",
        "locked": 0,
        "reason": reason,
        "last_scan_run_id": "run_abc123",
    }
    if source is not None:
        row["source"] = source
    return row


def _recorder():
    """Return (sent_list, poster) where poster captures (content, embeds)."""
    sent: list = []

    def _post(content, embeds=None):
        sent.append((content, embeds))
        return True

    return sent, _post


def _fields(embed: dict) -> dict:
    """Map embed field name -> value for assertions."""
    return {f["name"]: f["value"] for f in embed.get("fields", [])}


# real scan metrics as produced by wallet_scan._extract_user_metrics
_REAL_METRICS = {
    "realized_net_pnl": 24000.0,
    "positions_total": 180,
    "clv_coverage_rate": 0.72,
}
_REAL_EVIDENCE = "+$24.0k PnL, 180 trades, CLV coverage 72%"


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


# ---------------------------------------------------------------------------
# WP-1: open-vs-resolved split, category focus, and discovery source.
# Fixtures mirror the REAL persisted schema (polytool/reports/coverage.py
# outcome_counts: all six KNOWN_OUTCOMES keys present) and the two live pending
# wallets verified in the dev log.
# ---------------------------------------------------------------------------

# Real wallet 0x84cf...: 50 positions, ALL still open (PENDING=50).
_OUTCOME_COUNTS_ALL_OPEN = {
    "WIN": 0, "LOSS": 0, "PROFIT_EXIT": 0, "LOSS_EXIT": 0,
    "PENDING": 50, "UNKNOWN_RESOLUTION": 0,
}
# Real wallet 0xcf60...: 40 resolved (22+13+3+2), 10 open.
_OUTCOME_COUNTS_MIXED = {
    "WIN": 22, "LOSS": 13, "PROFIT_EXIT": 3, "LOSS_EXIT": 2,
    "PENDING": 10, "UNKNOWN_RESOLUTION": 0,
}


class TestOpenResolvedSplit:
    def test_all_open_wallet_renders_split(self):
        # The honest explanation for "+$0 PnL, no win rate": every position open.
        ev = Evidence.from_dict(
            {"realized_net_pnl": 0.0, "positions_total": 50,
             "clv_coverage_rate": 0.42, "outcome_counts": _OUTCOME_COUNTS_ALL_OPEN}
        )
        assert ev.open_positions == 50
        assert ev.resolved_positions == 0
        assert "50 open / 0 resolved" in summarize_evidence(ev)

    def test_mixed_wallet_resolved_math(self):
        ev = Evidence.from_dict({"outcome_counts": _OUTCOME_COUNTS_MIXED})
        # resolved = WIN+LOSS+PROFIT_EXIT+LOSS_EXIT = 22+13+3+2 = 40
        assert ev.resolved_positions == 40
        assert ev.open_positions == 10
        assert "10 open / 40 resolved" in summarize_evidence(ev)

    def test_unknown_resolution_excluded_from_both(self):
        oc = {"WIN": 5, "LOSS": 5, "PROFIT_EXIT": 0, "LOSS_EXIT": 0,
              "PENDING": 2, "UNKNOWN_RESOLUTION": 7}
        ev = Evidence.from_dict({"outcome_counts": oc})
        assert ev.open_positions == 2       # PENDING only
        assert ev.resolved_positions == 10  # WIN+LOSS; UNKNOWN_RESOLUTION not counted

    def test_no_outcome_counts_omits_split(self):
        # Existing metrics dicts without outcome_counts must not gain a split.
        ev = Evidence.from_dict({"realized_net_pnl": 24000.0, "positions_total": 180})
        assert ev.open_positions is None and ev.resolved_positions is None
        assert "open" not in summarize_evidence(ev)

    def test_explicit_counts_take_precedence(self):
        ev = Evidence.from_dict({"open_positions": 3, "resolved_positions": 7})
        assert (ev.open_positions, ev.resolved_positions) == (3, 7)


class TestSourceSignal:
    def test_source_from_row_decorates_summary(self):
        # source lives on the ROW (loop_a/manual/loop_d), not in scan metrics.
        row = _worker_row()
        row["source"] = "loop_a"
        summary = compute_row_evidence(
            row, metrics_reader=lambda r: {"realized_net_pnl": 124000.0,
                                           "positions_total": 50,
                                           "outcome_counts": _OUTCOME_COUNTS_MIXED}
        )
        assert summary.endswith("via loop_a")
        assert "10 open / 40 resolved" in summary

    def test_source_only_does_not_masquerade_as_evidence(self):
        # A row with source but no substantive metrics must fall back to reason,
        # never present bare provenance ("via loop_a") as evidence.
        row = _worker_row(reason="stored")
        row["source"] = "loop_a"
        summary = compute_row_evidence(row, metrics_reader=lambda r: {"foo": "bar"})
        assert summary == "stored"

    def test_no_source_on_row_omits_via(self):
        row = _worker_row()  # no 'source' key
        summary = compute_row_evidence(
            row, metrics_reader=lambda r: {"realized_net_pnl": 5000.0,
                                           "positions_total": 10}
        )
        assert "via" not in summary


class TestCategoryFocusRendering:
    def test_category_focus_rendered_when_present(self):
        ev = Evidence.from_dict(
            {"realized_net_pnl": 5000.0, "category_focus": "Politics"}
        )
        assert "focus: Politics" in summarize_evidence(ev)

    def test_unknown_or_absent_category_omitted(self):
        # _extract_user_metrics yields None for all-Unknown wallets; None omits.
        ev = Evidence.from_dict({"realized_net_pnl": 5000.0, "category_focus": None})
        assert "focus" not in summarize_evidence(ev)

    def test_field_order_is_stable(self):
        # PnL, win/trades, open/resolved, CLV, churn, category focus, source.
        ev = Evidence(
            realized_net_pnl=24000.0, win_rate=0.64, trades=180,
            open_positions=10, resolved_positions=40, clv_coverage_rate=0.72,
            churn_triggered=True, category_focus="Politics", source="loop_a",
        )
        assert summarize_evidence(ev) == (
            "+$24.0k PnL, 64% win / 180 trades, 10 open / 40 resolved, "
            "CLV coverage 72%, churn-triggered, focus: Politics, via loop_a"
        )


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
        assert summary == "+$124.0k PnL, 64% win / 180 trades, CLV coverage 94%"

    def test_nonzero_pnl_never_shows_zero_trades(self):
        # Simulate a regressed source: PnL present but trade count defaulted to 0.
        bad = {"realized_net_pnl": 124000.0, "positions_total": 0, "clv_coverage_rate": 0.94}
        summary = compute_row_evidence(_worker_row(), metrics_reader=lambda r: dict(bad))
        # misleading "0 trades" suppressed; trades omitted (not fabricated)
        assert summary == "+$124.0k PnL, CLV coverage 94%"
        assert "trades" not in summary

    def test_nonzero_clv_with_missing_trades_omits_trades(self):
        bad = {"realized_net_pnl": 0.0, "positions_total": None, "clv_coverage_rate": 0.42}
        summary = compute_row_evidence(_worker_row(), metrics_reader=lambda r: dict(bad))
        assert "trades" not in summary
        assert "CLV coverage 42%" in summary

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


class TestPendingEmbedCard:
    """Embed-payload construction for the single pending-review card."""

    def test_card_shape_color_footer_and_address(self):
        ev = Evidence.from_dict(
            {"realized_net_pnl": 124000.0, "positions_total": 50, "win_rate": 0.625,
             "win_count": 25, "clv_coverage_rate": 0.94,
             "outcome_counts": _OUTCOME_COUNTS_MIXED, "source": "loop_a",
             "handle": "whalewatch", "last_active": "2026-05-31T00:00:00Z"}
        )
        embed = build_pending_embed(_FULL, ev, now_iso="2026-06-02T00:00:00Z")
        # Title = handle headline; author eyebrow = "Pending wallet review".
        assert embed["title"] == "whalewatch"
        assert embed["author"]["name"] == "Pending wallet review"
        assert embed["color"] == 0x3498DB  # review/blue
        # Truncated address shown; profile link built from the FULL address.
        assert "0xcf60…3a4b" in embed["description"]
        assert f"https://polymarket.com/profile/{_FULL}" in embed["description"]
        assert embed["footer"]["text"] == "PolyTool · Vera"
        assert embed["timestamp"] == "2026-06-02T00:00:00Z"
        f = _fields(embed)
        assert f["PnL"] == "+$124.0k\nall-time · 40 resolved"
        assert f["Win rate"] == "62% (25/40)"  # with denominator
        assert f["Last active"] == "2d ago"
        assert f["Trades"] == "50 (sampled)"
        assert f["CLV coverage"] == "94%"  # relabelled coverage metric
        assert "CLV" not in f  # the bare "CLV" edge-signal label is gone
        assert f["Discovery"] == "leaderboard discovery"  # humanized
        # Recent-form separator + the windowed row.
        assert "Recent form — full trade history" in f
        names = [fld["name"] for fld in embed["fields"]]
        assert names[-3:] == ["Today", "7 days", "30 days"]

    def test_win_rate_dash_when_no_resolved_book(self):
        # All-open wallet: no resolved book -> win rate "—" (honest, not 0%).
        ev = Evidence.from_dict(
            {"realized_net_pnl": 0.0, "positions_total": 50,
             "clv_coverage_rate": 0.42, "outcome_counts": _OUTCOME_COUNTS_ALL_OPEN}
        )
        f = _fields(build_pending_embed(_FULL2, ev))
        assert f["Win rate"] == "—"

    def test_recent_form_windows_dash_without_data(self):
        # No recent_form ingredients -> all three windows show the honest marker.
        ev = Evidence.from_dict({"realized_net_pnl": 5000.0})
        f = _fields(build_pending_embed(_FULL, ev))
        assert f["Today"] == "—" and f["7 days"] == "—" and f["30 days"] == "—"

    def test_category_not_a_card_field(self):
        # Category focus moved OFF the single card (it remains in the digest
        # summary line); the redesigned card never renders a Category field.
        ev = Evidence.from_dict({"realized_net_pnl": 5000.0, "category_focus": "Politics"})
        assert "Category" not in _fields(build_pending_embed(_FULL, ev))

    def test_title_falls_back_to_truncated_address_without_handle(self):
        ev = Evidence.from_dict({"realized_net_pnl": 5000.0})
        assert build_pending_embed(_FULL, ev)["title"] == "0xcf60…3a4b"

    def test_humanized_sources(self):
        for src, label in (("loop_a", "leaderboard discovery"),
                           ("manual", "manual"), ("loop_d", "CLOB anomaly")):
            ev = Evidence.from_dict({"realized_net_pnl": 1.0, "source": src})
            assert _fields(build_pending_embed(_FULL, ev))["Discovery"] == label


class TestRecentFormHonesty:
    """The window honesty rule: only fully-covered windows show a number."""

    _NOW = "2026-06-02T12:00:00Z"

    def _rf(self, trades, *, sample_size, sample_cap):
        return {"trades": trades, "sample_size": sample_size, "sample_cap": sample_cap}

    def test_full_coverage_untruncated_sample_all_windows(self):
        # sample_size < cap -> not truncated -> every window is covered.
        rf = self._rf(
            [{"close": "2026-06-02T01:00:00Z", "pnl": 40.0},   # today
             {"close": "2026-05-30T00:00:00Z", "pnl": -10.0},  # within 7d
             {"close": "2026-05-10T00:00:00Z", "pnl": 100.0}], # within 30d only
            sample_size=50, sample_cap=200,
        )
        out = _recent_form_values(rf, _utc(self._NOW))
        assert out["Today"] == "+$40"
        assert out["7 days"] == "+$30"     # 40 - 10
        assert out["30 days"] == "+$130"   # 40 - 10 + 100

    def test_truncated_sample_uncovered_window_is_dash(self):
        # sample_size == cap (truncated) and oldest resolved is only 10d ago:
        # Today/7d are covered (oldest older than their start), 30d is NOT.
        rf = self._rf(
            [{"close": "2026-05-23T00:00:00Z", "pnl": 100.0},  # 10d ago (oldest)
             {"close": "2026-06-02T01:00:00Z", "pnl": 40.0}],  # today
            sample_size=200, sample_cap=200,
        )
        out = _recent_form_values(rf, _utc(self._NOW))
        assert out["Today"] == "+$40"
        # 7d is covered (oldest 10d ago precedes the 7d start) but the 10d-old
        # trade is OUTSIDE the 7d window, so only today's +$40 counts.
        assert out["7 days"] == "+$40"
        assert out["30 days"] == "—"  # older in-window trades may be missing

    def test_covered_window_with_no_trades_is_zero_not_dash(self):
        # Full coverage, nothing resolved in-window -> honest +$0 (NOT a dash).
        rf = self._rf([], sample_size=50, sample_cap=200)
        out = _recent_form_values(rf, _utc(self._NOW))
        assert out == {"Today": "+$0", "7 days": "+$0", "30 days": "+$0"}

    def test_no_recent_form_all_dashes(self):
        out = _recent_form_values(None, _utc(self._NOW))
        assert out == {"Today": "—", "7 days": "—", "30 days": "—"}


class TestSignalLineAndRecency:
    _NOW = "2026-06-02T12:00:00Z"

    def test_relative_age_units(self):
        now = _utc(self._NOW)
        assert _relative_age("2026-05-31T12:00:00Z", now) == "2d ago"
        assert _relative_age("2026-06-02T09:00:00Z", now) == "3h ago"
        assert _relative_age("2026-06-02T11:40:00Z", now) == "<1h ago"
        assert _relative_age(None, now) is None

    def test_signal_line_composes_present_components(self):
        ev = Evidence.from_dict(
            {"source": "loop_a", "win_rate": 0.62, "win_count": 25,
             "resolved_positions": 40, "last_active": "2026-05-31T12:00:00Z"}
        )
        assert _signal_line(ev, _utc(self._NOW)) == (
            "leaderboard discovery · 62% win (25/40) · active 2d ago"
        )

    def test_signal_line_omits_absent_components(self):
        # Only a source -> just the discovery label (honest omission elsewhere).
        ev = Evidence.from_dict({"source": "manual"})
        assert _signal_line(ev, _utc(self._NOW)) == "manual"

    def test_signal_line_none_when_empty(self):
        assert _signal_line(Evidence.from_dict({}), _utc(self._NOW)) is None


class TestCopyBlockContent:
    """Approve/deny commands live in CONTENT as a fenced copy-block."""

    def test_single_content_has_fenced_full_address_commands(self):
        content = build_single_content(_FULL)
        assert "```" in content  # fenced -> Discord one-tap copy
        assert f"python3 -m polytool discovery review --approve {_FULL}" in content
        assert f"python3 -m polytool discovery review --deny {_FULL}" in content

    def test_content_is_ascii(self):
        build_single_content(_FULL).encode("ascii")  # raises if non-ASCII


class TestNotifySingle:
    def test_single_card_posts_once_with_content_and_embed(self, tmp_path):
        sent, post = _recorder()
        state = tmp_path / "notified.json"

        summary = notify_pending_candidates(
            [_worker_row()], post=post, notified_path=state,
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )

        assert summary["mode"] == "single"
        assert summary["posted"] == 1 and summary["failed"] == 0
        assert len(sent) == 1
        content, embeds = sent[0]
        # commands in content; full address never truncated
        assert f"--approve {_FULL}" in content and f"--deny {_FULL}" in content
        assert _WORKER_REASON not in content
        # exactly one embed card carrying the visual fields
        assert isinstance(embeds, list) and len(embeds) == 1
        # Full address is reachable via the profile link in the description.
        assert _FULL in embeds[0]["description"]
        # PnL is the all-time figure (no resolved count without an outcome book).
        assert _fields(embeds[0])["PnL"] == "+$24.0k\nall-time"

    def test_records_wallet_as_notified(self, tmp_path):
        sent, post = _recorder()
        state = tmp_path / "notified.json"
        res = notify_pending_candidate(
            _FULL, Evidence.from_dict(dict(_REAL_METRICS)),
            post=post, notified_path=state,
        )
        assert res["ok"] and res["posted"] and not res["deduped"]
        from packages.polymarket.discovery.approval_request import load_notified

        assert _FULL.lower() in load_notified(state)


class TestNotifyDigest:
    def _two_rows(self):
        return [_worker_row(wallet=_FULL, source="loop_a"),
                _worker_row(wallet=_FULL2, source="loop_a")]

    def test_more_than_one_sends_single_digest_message(self, tmp_path):
        sent, post = _recorder()
        state = tmp_path / "notified.json"

        summary = notify_pending_candidates(
            self._two_rows(), post=post, notified_path=state,
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )

        assert summary["mode"] == "digest"
        assert summary["posted"] == 2
        assert len(sent) == 1  # ONE digest message, not two cards
        content, embeds = sent[0]
        # per-wallet copy-blocks in content (2 wallets -> 4 fence markers)
        assert content.count("```") == 4
        assert f"--approve {_FULL}" in content and f"--approve {_FULL2}" in content
        # single digest embed lists each wallet as a field
        assert len(embeds) == 1
        names = {f["name"] for f in embeds[0]["fields"]}
        assert names == {_FULL, _FULL2}

    def test_digest_marks_all_on_success(self, tmp_path):
        _, post = _recorder()
        state = tmp_path / "notified.json"
        notify_pending_candidates(
            self._two_rows(), post=post, notified_path=state,
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )
        from packages.polymarket.discovery.approval_request import load_notified

        nf = load_notified(state)
        assert _FULL.lower() in nf and _FULL2.lower() in nf

    def test_digest_dedup_second_pass(self, tmp_path):
        sent, post = _recorder()
        state = tmp_path / "notified.json"
        kw = dict(post=post, notified_path=state,
                  metrics_reader=lambda r: dict(_REAL_METRICS))
        first = notify_pending_candidates(self._two_rows(), **kw)
        second = notify_pending_candidates(self._two_rows(), **kw)
        assert first["posted"] == 2
        assert second["posted"] == 0 and second["deduped"] == 2
        assert len(sent) == 1  # only the first pass sent anything

    def test_threshold_exactly_one_is_single_not_digest(self, tmp_path):
        sent, post = _recorder()
        notify_pending_candidates(
            [_worker_row()], post=post, notified_path=tmp_path / "n.json",
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )
        # single mode -> one single-card embed (author eyebrow identifies it;
        # the title is now the wallet handle/address headline, not a fixed label).
        assert sent[0][1][0]["author"]["name"] == "Pending wallet review"


class TestDigestFitAndOverflow:
    def test_fit_caps_and_reports_overflow(self):
        wallets = [f"0x{i:040x}" for i in range(30)]
        shown, overflow = _fit_digest(wallets)
        assert 0 < len(shown) <= 10
        assert overflow == len(wallets) - len(shown)

    def test_content_never_exceeds_discord_limit(self):
        wallets = [f"0x{i:040x}" for i in range(30)]
        shown, overflow = _fit_digest(wallets)
        content = build_digest_content(shown, overflow=overflow)
        assert len(content) <= 2000  # Discord hard content limit
        assert f"+{overflow} more" in content  # overflow surfaced, not silent

    def test_overflow_marks_only_shown(self, tmp_path):
        sent, post = _recorder()
        state = tmp_path / "n.json"
        rows = [_worker_row(wallet=f"0x{i:040x}", source="loop_a") for i in range(30)]
        summary = notify_pending_candidates(
            rows, post=post, notified_path=state,
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )
        from packages.polymarket.discovery.approval_request import load_notified

        marked = load_notified(state)
        assert summary["posted"] == len(marked)  # only shown wallets marked
        assert summary.get("skipped_capped", 0) == 30 - summary["posted"]


class TestNotifyNeverRaises:
    def test_post_returning_false_is_not_fatal_and_not_marked(self, tmp_path):
        state = tmp_path / "notified.json"
        res = notify_pending_candidate(
            _FULL, Evidence.from_dict({"realized_net_pnl": 1.0}),
            post=lambda content, embeds=None: False, notified_path=state,
        )
        assert res["posted"] is True
        assert res["ok"] is False
        from packages.polymarket.discovery.approval_request import load_notified

        assert _FULL.lower() not in load_notified(state)

    def test_post_raising_is_swallowed(self, tmp_path):
        state = tmp_path / "notified.json"

        def _raising_post(content, embeds=None):
            raise ConnectionError("webhook down")

        res = notify_pending_candidate(
            _FULL, Evidence.from_dict({"realized_net_pnl": 1.0}),
            post=_raising_post, notified_path=state,
        )
        assert res["ok"] is False
        assert res["posted"] is True

    def test_digest_post_raising_is_swallowed_and_not_marked(self, tmp_path):
        state = tmp_path / "notified.json"

        def _raising_post(content, embeds=None):
            raise ConnectionError("down")

        rows = [_worker_row(wallet=_FULL, source="loop_a"),
                _worker_row(wallet=_FULL2, source="loop_a")]
        summary = notify_pending_candidates(
            rows, post=_raising_post, notified_path=state,
            metrics_reader=lambda r: dict(_REAL_METRICS),
        )
        assert summary["failed"] == 2 and summary["posted"] == 0
        from packages.polymarket.discovery.approval_request import load_notified

        assert load_notified(state) == set()  # nothing marked on failure

    def test_batch_failure_is_counted_not_raised(self, tmp_path):
        state = tmp_path / "notified.json"
        summary = notify_pending_candidates(
            [_worker_row()], post=lambda content, embeds=None: False,
            notified_path=state, metrics_reader=lambda r: dict(_REAL_METRICS),
        )
        assert summary["failed"] == 1
        assert summary["posted"] == 0

    def test_bad_address_is_not_notified(self, tmp_path):
        state = tmp_path / "notified.json"
        sent, post = _recorder()
        res = notify_pending_candidate(
            "0xcf60", Evidence(), post=post, notified_path=state
        )
        assert res["posted"] is False
        assert sent == []


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
