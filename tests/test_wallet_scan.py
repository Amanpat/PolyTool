"""Tests for tools.cli.wallet_scan."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.cli.wallet_scan import (
    WalletScanner,
    _build_leaderboard,
    _build_leaderboard_md,
    _detect_identifier_type,
    _dominant_category,
    _extract_user_metrics,
    _load_username_sidecar,
    _make_dossier_extractor,
    _resolve_wallet_id,
    _sort_key_for_leaderboard,
    _read_wallet_from_dossier,
    _stamp_dossier_username,
    _win_rate_from_outcome_counts,
    parse_input_file,
)

FIXED_NOW = datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc)
FIXED_DATE = "2026-03-05"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _make_coverage_report(*, pnl_net: float, gross_pnl: float, positions_total: int) -> dict:
    # Mirrors the REAL persisted schema from
    # polytool/reports/coverage.py build_coverage_report: positions_total is
    # nested under "totals" and percentages under "outcome_percentages". (An
    # earlier top-level fixture masked a reader bug; keep this faithful.)
    return {
        "totals": {"positions_total": positions_total},
        "outcome_counts": {"WIN": 2, "LOSS": 1, "PENDING": 1},
        "outcome_percentages": {
            "WIN": 0.5,
            "LOSS": 0.25,
            "PENDING": 0.25,
            "UNKNOWN_RESOLUTION": 0.0,
        },
        "pnl": {
            "realized_pnl_net_estimated_fees_total": pnl_net,
            "gross_pnl_total": gross_pnl,
        },
        "clv_coverage": {"coverage_rate": 0.75},
    }


def _make_scan_run_root(
    base: Path,
    name: str,
    *,
    pnl_net: float = 0.0,
    gross_pnl: float = 0.0,
    positions_total: int = 10,
) -> Path:
    run_root = base / name
    run_root.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_root / "coverage_reconciliation_report.json",
        _make_coverage_report(
            pnl_net=pnl_net,
            gross_pnl=gross_pnl,
            positions_total=positions_total,
        ),
    )
    return run_root


def _seg_bucket(count: int) -> dict:
    # Minimal faithful subset of polytool/reports/coverage.py
    # _finalize_segment_bucket: the per-category 'count' is what
    # _dominant_category reads.
    return {"count": count, "wins": 0, "losses": 0, "win_rate": 0.0}


def _write_segment_analysis(run_root: Path, by_category: dict) -> None:
    # Mirrors the REAL persisted segment_analysis.json: a top-level
    # "segment_analysis" key holding "by_category" (keyed by category name with
    # a synthetic "Unknown" bucket always present). See _build_segment_analysis.
    _write_json(
        run_root / "segment_analysis.json",
        {
            "generated_at": "2026-06-01T00:00:00Z",
            "run_id": run_root.name,
            "user_slug": "unknown",
            "wallet": "0xabc",
            "segment_analysis": {"by_category": by_category},
        },
    )


# ---------------------------------------------------------------------------
# _extract_user_metrics — field sourcing against the REAL persisted schema
# ---------------------------------------------------------------------------


class TestExtractUserMetrics:
    def test_positions_total_read_from_nested_totals(self, tmp_path: Path) -> None:
        # Regression: positions_total lives under report["totals"], not top level.
        run_root = _make_scan_run_root(
            tmp_path, "run_x", pnl_net=124000.0, positions_total=180
        )
        metrics = _extract_user_metrics(run_root)
        assert metrics["positions_total"] == 180  # NOT 0

    def test_win_rate_extracted_from_outcome_counts(self, tmp_path: Path) -> None:
        run_root = _make_scan_run_root(tmp_path, "run_w", positions_total=4)
        metrics = _extract_user_metrics(run_root)
        # outcome_counts WIN=2, LOSS=1 -> 2/(2+1) = 0.6667 (PENDING excluded)
        assert metrics["win_rate"] == pytest.approx(2 / 3, abs=1e-4)

    def test_pnl_and_clv_still_read_correctly(self, tmp_path: Path) -> None:
        run_root = _make_scan_run_root(
            tmp_path, "run_p", pnl_net=124000.0, gross_pnl=130000.0, positions_total=180
        )
        metrics = _extract_user_metrics(run_root)
        assert metrics["realized_net_pnl"] == pytest.approx(124000.0)
        assert metrics["clv_coverage_rate"] == pytest.approx(0.75)

    def test_internal_consistency_nonzero_pnl_has_nonzero_trades(
        self, tmp_path: Path
    ) -> None:
        # The reported bug: +$124k PnL with "0 trades" must never happen.
        run_root = _make_scan_run_root(
            tmp_path, "run_c", pnl_net=124000.0, positions_total=180
        )
        metrics = _extract_user_metrics(run_root)
        if metrics.get("realized_net_pnl"):
            assert metrics["positions_total"], "non-zero PnL implies non-zero trades"

    def test_missing_positions_total_is_none_not_zero(self, tmp_path: Path) -> None:
        # No count anywhere in the report -> None, so the summary omits trades
        # rather than fabricate a misleading 0.
        run_root = tmp_path / "run_missing"
        run_root.mkdir(parents=True, exist_ok=True)
        _write_json(
            run_root / "coverage_reconciliation_report.json",
            {
                "pnl": {"realized_pnl_net_estimated_fees_total": 5.0},
                "clv_coverage": {"coverage_rate": 0.4},
                "outcome_counts": {},
            },
        )
        metrics = _extract_user_metrics(run_root)
        assert metrics["positions_total"] is None  # NOT 0

    def test_legacy_top_level_positions_total_fallback(self, tmp_path: Path) -> None:
        run_root = tmp_path / "run_legacy"
        run_root.mkdir(parents=True, exist_ok=True)
        _write_json(
            run_root / "coverage_reconciliation_report.json",
            {"positions_total": 42, "outcome_counts": {}},
        )
        metrics = _extract_user_metrics(run_root)
        assert metrics["positions_total"] == 42


class TestWinRateFromOutcomeCounts:
    def test_canonical_formula_excludes_pending(self) -> None:
        wr = _win_rate_from_outcome_counts(
            {"WIN": 6, "PROFIT_EXIT": 2, "LOSS": 1, "LOSS_EXIT": 1, "PENDING": 99}
        )
        assert wr == pytest.approx((6 + 2) / (6 + 2 + 1 + 1))

    def test_no_resolved_outcomes_returns_none_not_zero(self) -> None:
        assert _win_rate_from_outcome_counts({"PENDING": 5, "UNKNOWN_RESOLUTION": 3}) is None

    def test_empty_returns_none(self) -> None:
        assert _win_rate_from_outcome_counts({}) is None


class TestDominantCategory:
    """_dominant_category reads segment_analysis.by_category 'count' buckets."""

    def test_picks_highest_count_known_category(self) -> None:
        by_cat = {
            "Politics": _seg_bucket(30),
            "Sports": _seg_bucket(12),
            "Unknown": _seg_bucket(5),
        }
        assert _dominant_category(by_cat) == "Politics"

    def test_excludes_unknown_even_when_dominant(self) -> None:
        # The real wallets in this packet are ENTIRELY uncategorised: only the
        # synthetic "Unknown" bucket exists. Must yield None (never "Unknown")
        # so the summary omits category focus rather than show a non-signal.
        by_cat = {"Unknown": _seg_bucket(50)}
        assert _dominant_category(by_cat) is None

    def test_unknown_case_insensitive(self) -> None:
        assert _dominant_category({"unknown": _seg_bucket(7)}) is None

    def test_ties_broken_alphabetically(self) -> None:
        by_cat = {"Sports": _seg_bucket(10), "Crypto": _seg_bucket(10)}
        assert _dominant_category(by_cat) == "Crypto"

    def test_zero_count_buckets_ignored(self) -> None:
        assert _dominant_category({"Politics": _seg_bucket(0)}) is None

    def test_missing_or_malformed_is_none(self) -> None:
        assert _dominant_category(None) is None
        assert _dominant_category({}) is None
        assert _dominant_category({"Politics": "not-a-dict"}) is None


class TestExtractUserMetricsCategoryFocus:
    """category_focus surfaced into the metrics dict from the segment file."""

    def test_dominant_known_category_surfaced(self, tmp_path: Path) -> None:
        run_root = _make_scan_run_root(tmp_path, "run_cat", positions_total=42)
        _write_segment_analysis(
            run_root,
            {"Politics": _seg_bucket(30), "Sports": _seg_bucket(12),
             "Unknown": _seg_bucket(0)},
        )
        metrics = _extract_user_metrics(run_root)
        assert metrics["category_focus"] == "Politics"

    def test_all_unknown_yields_none(self, tmp_path: Path) -> None:
        # Mirrors BOTH real pending wallets: 50 positions, all uncategorised.
        run_root = _make_scan_run_root(tmp_path, "run_unk", positions_total=50)
        _write_segment_analysis(run_root, {"Unknown": _seg_bucket(50)})
        metrics = _extract_user_metrics(run_root)
        assert metrics["category_focus"] is None

    def test_missing_segment_file_is_none(self, tmp_path: Path) -> None:
        # No segment_analysis.json on disk -> category_focus omitted, not raised.
        run_root = _make_scan_run_root(tmp_path, "run_noseg", positions_total=10)
        metrics = _extract_user_metrics(run_root)
        assert metrics["category_focus"] is None


def _write_dossier(run_root: Path, *, username: str | None, positions: list[dict],
                   max_trades: int = 200) -> None:
    """Write a faithful dossier.json (header + positions) for reader tests."""
    header: dict = {"max_trades": max_trades, "proxy_wallet": "0xabc",
                    "user_input": "0xabc"}
    if username is not None:
        header["username"] = username
    _write_json(
        run_root / "dossier.json",
        {"header": header, "positions": {"count": len(positions),
                                         "positions": positions}},
    )


def _pos(*, outcome: str, close: str | None, entry: str | None = None,
         pnl: float | None = None) -> dict:
    p: dict = {"resolution_outcome": outcome}
    if close is not None:
        p["close_ts"] = close
        p["resolved_at"] = close
    if entry is not None:
        p["entry_ts"] = entry
    if pnl is not None:
        p["realized_pnl_net_estimated_fees"] = pnl
    return p


class TestExtractUserMetricsDossierFields:
    """handle / last_active / win_count / recent_form sourced from the dossier."""

    def test_handle_from_header_username(self, tmp_path: Path) -> None:
        run_root = _make_scan_run_root(tmp_path, "run_h", positions_total=2)
        _write_dossier(run_root, username="@WhaleWatch", positions=[])
        # Leading '@' and surrounding whitespace are stripped.
        assert _extract_user_metrics(run_root)["handle"] == "WhaleWatch"

    def test_handle_none_when_username_absent(self, tmp_path: Path) -> None:
        # Pseudonymous wallet: no header.username -> handle None (address fallback).
        run_root = _make_scan_run_root(tmp_path, "run_noh", positions_total=2)
        _write_dossier(run_root, username=None, positions=[])
        assert _extract_user_metrics(run_root)["handle"] is None

    def test_no_dossier_omits_fields(self, tmp_path: Path) -> None:
        # Coverage report only (no dossier.json) -> new fields are None.
        run_root = _make_scan_run_root(tmp_path, "run_nod", positions_total=2)
        m = _extract_user_metrics(run_root)
        assert m["handle"] is None and m["last_active"] is None
        assert m["recent_form"] is None

    def test_last_active_is_newest_trade_ts(self, tmp_path: Path) -> None:
        run_root = _make_scan_run_root(tmp_path, "run_la", positions_total=3)
        _write_dossier(run_root, username=None, positions=[
            _pos(outcome="WIN", close="2026-05-01T00:00:00Z",
                 entry="2026-04-20T00:00:00Z", pnl=10.0),
            _pos(outcome="LOSS", close="2026-05-10T00:00:00Z",
                 entry="2026-05-09T12:00:00Z", pnl=-5.0),
        ])
        # Newest TRADE (entry) ts wins — NOT the later resolution ts.
        assert _extract_user_metrics(run_root)["last_active"] == "2026-05-09T12:00:00Z"

    def test_recent_form_resolved_only(self, tmp_path: Path) -> None:
        run_root = _make_scan_run_root(tmp_path, "run_rf", positions_total=3)
        _write_dossier(run_root, username=None, max_trades=200, positions=[
            _pos(outcome="WIN", close="2026-05-01T00:00:00Z",
                 entry="2026-04-20T00:00:00Z", pnl=10.0),
            _pos(outcome="PROFIT_EXIT", close="2026-05-03T00:00:00Z",
                 entry="2026-05-02T00:00:00Z", pnl=4.0),
            # Open position: no resolution -> excluded from recent_form.
            _pos(outcome="PENDING", close=None, entry="2026-05-05T00:00:00Z"),
        ])
        rf = _extract_user_metrics(run_root)["recent_form"]
        assert rf["sample_size"] == 3 and rf["sample_cap"] == 200
        assert len(rf["trades"]) == 2  # only the two resolved positions
        assert {t["pnl"] for t in rf["trades"]} == {10.0, 4.0}

    def test_win_count_from_outcome_counts(self, tmp_path: Path) -> None:
        # WIN=2 (from the coverage fixture) + PROFIT_EXIT=0 -> win_count 2.
        run_root = _make_scan_run_root(tmp_path, "run_wc", positions_total=4)
        assert _extract_user_metrics(run_root)["win_count"] == 2


# ---------------------------------------------------------------------------
# parse_input_file
# ---------------------------------------------------------------------------


class TestParseInputFile:
    def test_parses_handles_and_wallets(self, tmp_path: Path) -> None:
        f = tmp_path / "ids.txt"
        _write_text(f, "@Alice\n0xdeadbeef1234\n@Bob\n")
        entries = parse_input_file(f)
        assert len(entries) == 3
        assert entries[0] == {"identifier": "@Alice", "kind": "handle", "username": ""}
        assert entries[1] == {"identifier": "0xdeadbeef1234", "kind": "wallet", "username": ""}
        assert entries[2] == {"identifier": "@Bob", "kind": "handle", "username": ""}

    def test_skips_blank_and_comment_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "ids.txt"
        _write_text(f, "# comment\n\n@Alice\n   \n# another\n@Bob\n")
        entries = parse_input_file(f)
        assert [e["identifier"] for e in entries] == ["@Alice", "@Bob"]

    def test_deduplicates(self, tmp_path: Path) -> None:
        f = tmp_path / "ids.txt"
        _write_text(f, "@Alice\n@Alice\n@Bob\n")
        entries = parse_input_file(f)
        assert [e["identifier"] for e in entries] == ["@Alice", "@Bob"]

    def test_respects_max_entries(self, tmp_path: Path) -> None:
        f = tmp_path / "ids.txt"
        _write_text(f, "@A\n@B\n@C\n@D\n")
        entries = parse_input_file(f, max_entries=2)
        assert len(entries) == 2

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            parse_input_file(tmp_path / "missing.txt")

    def test_mixed_case_wallet_detected(self, tmp_path: Path) -> None:
        f = tmp_path / "ids.txt"
        _write_text(f, "0XABCDEF\n")
        entries = parse_input_file(f)
        assert entries[0]["kind"] == "wallet"


# ---------------------------------------------------------------------------
# _detect_identifier_type
# ---------------------------------------------------------------------------


class TestDetectIdentifierType:
    def test_handle_at(self) -> None:
        assert _detect_identifier_type("@Alice") == "handle"

    def test_wallet_0x(self) -> None:
        assert _detect_identifier_type("0xdeadbeef") == "wallet"

    def test_wallet_0X_uppercase(self) -> None:
        assert _detect_identifier_type("0XDEADBEEF") == "wallet"

    def test_no_prefix_treated_as_handle(self) -> None:
        assert _detect_identifier_type("alice") == "handle"


# ---------------------------------------------------------------------------
# WalletScanner — artifact writing and manifest
# ---------------------------------------------------------------------------


class TestWalletScannerArtifacts:
    def _make_scanner(self, scan_results: dict[str, str]) -> WalletScanner:
        """Return a WalletScanner that uses a fake scan callable."""

        def fake_scan(identifier: str, scan_flags: dict) -> str:
            if identifier not in scan_results:
                raise RuntimeError(f"No fake scan result for {identifier!r}")
            return scan_results[identifier]

        return WalletScanner(
            scan_callable=fake_scan,
            now_provider=lambda: FIXED_NOW,
        )

    def test_writes_all_four_artifacts(self, tmp_path: Path) -> None:
        run_root_alice = _make_scan_run_root(tmp_path / "runs", "alice_run", pnl_net=10.0)

        scanner = self._make_scanner({"@Alice": run_root_alice.as_posix()})
        entries = [{"identifier": "@Alice", "kind": "handle"}]
        paths = scanner.run(
            entries=entries,
            output_root=tmp_path / "out",
            run_id="test-run-001",
            profile="lite",
            input_file_path="wallets.txt",
        )

        out_root = Path(paths["run_root"])
        assert (out_root / "wallet_scan_manifest.json").exists()
        assert (out_root / "per_user_results.jsonl").exists()
        assert (out_root / "leaderboard.json").exists()
        assert (out_root / "leaderboard.md").exists()

    def test_run_root_path_includes_date_and_run_id(self, tmp_path: Path) -> None:
        run_root_alice = _make_scan_run_root(tmp_path / "runs", "alice_run")
        scanner = self._make_scanner({"@Alice": run_root_alice.as_posix()})
        paths = scanner.run(
            entries=[{"identifier": "@Alice", "kind": "handle"}],
            output_root=tmp_path / "out",
            run_id="fixed-run-id",
            profile="lite",
            input_file_path="wallets.txt",
        )
        assert FIXED_DATE in paths["run_root"]
        assert "fixed-run-id" in paths["run_root"]

    def test_manifest_contents(self, tmp_path: Path) -> None:
        run_root_alice = _make_scan_run_root(tmp_path / "runs", "alice_run")
        scanner = self._make_scanner({"@Alice": run_root_alice.as_posix()})
        paths = scanner.run(
            entries=[{"identifier": "@Alice", "kind": "handle"}],
            output_root=tmp_path / "out",
            run_id="test-run-002",
            profile="lite",
            input_file_path="wallets.txt",
        )
        manifest = json.loads(Path(paths["wallet_scan_manifest_json"]).read_text(encoding="utf-8"))
        assert manifest["run_id"] == "test-run-002"
        assert manifest["profile"] == "lite"
        assert manifest["entries_attempted"] == 1
        assert manifest["entries_succeeded"] == 1
        assert manifest["entries_failed"] == 0
        assert "output_paths" in manifest

    def test_per_user_results_jsonl_format(self, tmp_path: Path) -> None:
        run_root_alice = _make_scan_run_root(tmp_path / "runs", "alice_run", pnl_net=5.0)
        scanner = self._make_scanner({"@Alice": run_root_alice.as_posix()})
        paths = scanner.run(
            entries=[{"identifier": "@Alice", "kind": "handle"}],
            output_root=tmp_path / "out",
            run_id="test-run-003",
            profile="lite",
            input_file_path="wallets.txt",
        )
        lines = Path(paths["per_user_results_jsonl"]).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["status"] == "success"
        assert record["identifier"] == "@Alice"
        assert record["realized_net_pnl"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# WalletScanner — partial failure handling
# ---------------------------------------------------------------------------


class TestWalletScannerPartialFailure:
    def test_continues_when_one_wallet_fails(self, tmp_path: Path) -> None:
        run_root_bob = _make_scan_run_root(tmp_path / "runs", "bob_run", pnl_net=3.0)

        call_count = {"n": 0}

        def flaky_scan(identifier: str, scan_flags: dict) -> str:
            call_count["n"] += 1
            if identifier == "@Alice":
                raise RuntimeError("Network error")
            return run_root_bob.as_posix()

        scanner = WalletScanner(
            scan_callable=flaky_scan,
            now_provider=lambda: FIXED_NOW,
        )
        paths = scanner.run(
            entries=[
                {"identifier": "@Alice", "kind": "handle"},
                {"identifier": "@Bob", "kind": "handle"},
            ],
            output_root=tmp_path / "out",
            run_id="partial-fail-run",
            profile="lite",
            input_file_path="wallets.txt",
            continue_on_error=True,
        )

        lines = Path(paths["per_user_results_jsonl"]).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        records = [json.loads(line) for line in lines]
        by_id = {r["identifier"]: r for r in records}

        assert by_id["@Alice"]["status"] == "failure"
        assert "RuntimeError" in by_id["@Alice"]["error"]
        assert by_id["@Bob"]["status"] == "success"

        # Leaderboard only includes succeeded entries
        leaderboard = json.loads(Path(paths["leaderboard_json"]).read_text(encoding="utf-8"))
        assert leaderboard["entries_failed"] == 1
        assert leaderboard["entries_succeeded"] == 1
        assert len(leaderboard["ranked"]) == 1

    def test_error_field_recorded_per_failed_entry(self, tmp_path: Path) -> None:
        def always_fail(identifier: str, scan_flags: dict) -> str:
            raise ValueError("bad wallet")

        scanner = WalletScanner(
            scan_callable=always_fail,
            now_provider=lambda: FIXED_NOW,
        )
        paths = scanner.run(
            entries=[{"identifier": "0xdeadbeef", "kind": "wallet"}],
            output_root=tmp_path / "out",
            run_id="all-fail-run",
            profile="lite",
            input_file_path="wallets.txt",
            continue_on_error=True,
        )
        lines = Path(paths["per_user_results_jsonl"]).read_text(encoding="utf-8").splitlines()
        record = json.loads(lines[0])
        assert record["status"] == "failure"
        assert record["error"] is not None
        assert record["realized_net_pnl"] is None


# ---------------------------------------------------------------------------
# Leaderboard ordering
# ---------------------------------------------------------------------------


class TestLeaderboardOrdering:
    def _result(self, slug: str, pnl: float | None) -> dict:
        return {
            "identifier": f"@{slug}",
            "kind": "handle",
            "slug": slug,
            "run_root": f"/tmp/{slug}",
            "status": "success",
            "realized_net_pnl": pnl,
            "gross_pnl": pnl,
            "positions_total": 10,
            "clv_coverage_rate": 0.5,
            "unknown_resolution_pct": 0.1,
            "outcome_counts": {},
            "segment_highlights": [],
        }

    def test_sorted_descending_by_pnl(self) -> None:
        results = [
            self._result("charlie", 1.0),
            self._result("alice", 5.0),
            self._result("bob", 3.0),
        ]
        leaderboard = _build_leaderboard(
            results,
            run_id="x",
            created_at="2026-03-05T12:00:00+00:00",
            scan_flags={},
            profile="lite",
            input_file="f.txt",
            entries_attempted=3,
        )
        slugs = [r["slug"] for r in leaderboard["ranked"]]
        assert slugs == ["alice", "bob", "charlie"]

    def test_tiebreak_by_slug(self) -> None:
        results = [
            self._result("zara", 5.0),
            self._result("alice", 5.0),
        ]
        leaderboard = _build_leaderboard(
            results,
            run_id="x",
            created_at="2026-03-05T12:00:00+00:00",
            scan_flags={},
            profile="lite",
            input_file="f.txt",
            entries_attempted=2,
        )
        slugs = [r["slug"] for r in leaderboard["ranked"]]
        assert slugs == ["alice", "zara"]

    def test_null_pnl_goes_last(self) -> None:
        results = [
            self._result("bob", None),
            self._result("alice", -1.0),
        ]
        leaderboard = _build_leaderboard(
            results,
            run_id="x",
            created_at="2026-03-05T12:00:00+00:00",
            scan_flags={},
            profile="lite",
            input_file="f.txt",
            entries_attempted=2,
        )
        slugs = [r["slug"] for r in leaderboard["ranked"]]
        # alice has -1.0 which is > -inf (null), so alice ranks above bob
        assert slugs == ["alice", "bob"]

    def test_rank_field_is_1_based(self) -> None:
        results = [self._result("alice", 5.0), self._result("bob", 3.0)]
        leaderboard = _build_leaderboard(
            results,
            run_id="x",
            created_at="2026-03-05T12:00:00+00:00",
            scan_flags={},
            profile="lite",
            input_file="f.txt",
            entries_attempted=2,
        )
        ranks = [r["rank"] for r in leaderboard["ranked"]]
        assert ranks == [1, 2]


# ---------------------------------------------------------------------------
# Leaderboard markdown
# ---------------------------------------------------------------------------


class TestLeaderboardMarkdown:
    def test_markdown_contains_run_id(self) -> None:
        lb = _build_leaderboard(
            [],
            run_id="unique-run-xyz",
            created_at="2026-03-05T12:00:00+00:00",
            scan_flags={},
            profile="lite",
            input_file="f.txt",
            entries_attempted=0,
        )
        md = _build_leaderboard_md(lb)
        assert "unique-run-xyz" in md

    def test_markdown_table_row_per_ranked_entry(self) -> None:
        results = [
            {
                "identifier": "@Alice",
                "kind": "handle",
                "slug": "alice",
                "run_root": "/tmp/alice",
                "status": "success",
                "realized_net_pnl": 5.0,
                "gross_pnl": 6.0,
                "positions_total": 10,
                "clv_coverage_rate": 0.8,
                "unknown_resolution_pct": 0.0,
                "outcome_counts": {},
                "segment_highlights": [],
            }
        ]
        lb = _build_leaderboard(
            results,
            run_id="test",
            created_at="2026-03-05T12:00:00+00:00",
            scan_flags={},
            profile="lite",
            input_file="f.txt",
            entries_attempted=1,
        )
        md = _build_leaderboard_md(lb)
        assert "alice" in md
        assert "5.0000" in md


# ---------------------------------------------------------------------------
# WalletScanner — post-scan dossier hook
# ---------------------------------------------------------------------------

MINIMAL_DOSSIER = {
    "header": {
        "export_id": "test-export-001",
        "proxy_wallet": "0xABC",
        "user_input": "testuser",
        "generated_at": "2026-04-03T10:00:00Z",
        "window_days": 90,
        "window_start": "2026-01-03",
        "window_end": "2026-04-03",
        "max_trades": 1000,
    },
    "detectors": {
        "latest": [
            {"detector": "holding_style", "label": "MOMENTUM", "score": 0.8}
        ]
    },
    "pnl_summary": {
        "pricing_confidence": "HIGH",
        "trend_30d": "POSITIVE",
        "latest_bucket": "profitable",
    },
}


class TestWalletScannerDossierHook:
    """Tests for the post_scan_extractor hook and --extract-dossier integration."""

    def _make_scanner_with_hook(
        self,
        scan_results: dict,
        extractor_calls: list,
        *,
        fail_extractor: bool = False,
    ) -> WalletScanner:
        """Build a WalletScanner with a call-tracking extractor."""
        from pathlib import Path as _Path

        def fake_scan(identifier: str, scan_flags: dict) -> str:
            if identifier not in scan_results:
                raise RuntimeError(f"No fake scan result for {identifier!r}")
            return scan_results[identifier]

        def tracking_extractor(scan_run_root: _Path, slug: str, wallet: str) -> None:
            if fail_extractor:
                raise ValueError("extractor exploded")
            extractor_calls.append((scan_run_root, slug, wallet))

        return WalletScanner(
            scan_callable=fake_scan,
            now_provider=lambda: FIXED_NOW,
            post_scan_extractor=tracking_extractor,
        )

    def test_no_extractor_runs_unchanged(self, tmp_path: Path) -> None:
        """WalletScanner with no post_scan_extractor runs without any dossier calls."""
        run_root = _make_scan_run_root(tmp_path / "runs", "alice_run", pnl_net=1.0)
        scanner = WalletScanner(
            scan_callable=lambda ident, flags: run_root.as_posix(),
            now_provider=lambda: FIXED_NOW,
        )
        paths = scanner.run(
            entries=[{"identifier": "@Alice", "kind": "handle"}],
            output_root=tmp_path / "out",
            run_id="no-extractor-run",
            profile="lite",
            input_file_path="wallets.txt",
        )
        assert Path(paths["leaderboard_json"]).exists()

    def test_extractor_called_for_each_successful_scan(self, tmp_path: Path) -> None:
        """post_scan_extractor receives (scan_run_root, slug, wallet) for each success."""
        run_root_alice = _make_scan_run_root(tmp_path / "runs", "alice_run", pnl_net=5.0)
        run_root_bob = _make_scan_run_root(tmp_path / "runs", "bob_run", pnl_net=3.0)

        calls: list = []
        scanner = self._make_scanner_with_hook(
            {
                "@Alice": run_root_alice.as_posix(),
                "@Bob": run_root_bob.as_posix(),
            },
            calls,
        )
        scanner.run(
            entries=[
                {"identifier": "@Alice", "kind": "handle"},
                {"identifier": "@Bob", "kind": "handle"},
            ],
            output_root=tmp_path / "out",
            run_id="hook-test-run",
            profile="lite",
            input_file_path="wallets.txt",
        )
        assert len(calls) == 2
        slugs_called = {c[1] for c in calls}
        # slug comes from resolve_user_context — just confirm it was called for both
        assert len(slugs_called) == 2

    def test_failed_scans_do_not_call_extractor(self, tmp_path: Path) -> None:
        """The extractor is NOT called for failed wallet scans."""
        run_root_bob = _make_scan_run_root(tmp_path / "runs", "bob_run", pnl_net=3.0)
        calls: list = []

        def flaky_scan(identifier: str, scan_flags: dict) -> str:
            if identifier == "@Alice":
                raise RuntimeError("scan failed")
            return run_root_bob.as_posix()

        def tracking_extractor(scan_run_root: Path, slug: str, wallet: str) -> None:
            calls.append((scan_run_root, slug, wallet))

        scanner = WalletScanner(
            scan_callable=flaky_scan,
            now_provider=lambda: FIXED_NOW,
            post_scan_extractor=tracking_extractor,
        )
        scanner.run(
            entries=[
                {"identifier": "@Alice", "kind": "handle"},
                {"identifier": "@Bob", "kind": "handle"},
            ],
            output_root=tmp_path / "out",
            run_id="fail-extractor-run",
            profile="lite",
            input_file_path="wallets.txt",
        )
        # Only the successful Bob scan should trigger the extractor
        assert len(calls) == 1

    def test_extractor_exception_is_non_fatal(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """An exception in the post_scan_extractor does NOT abort the scan loop."""
        run_root_alice = _make_scan_run_root(tmp_path / "runs", "alice_run", pnl_net=5.0)
        run_root_bob = _make_scan_run_root(tmp_path / "runs", "bob_run", pnl_net=3.0)

        calls: list = []
        call_count = {"n": 0}

        def failing_then_ok_extractor(scan_run_root: Path, slug: str, wallet: str) -> None:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ValueError("first extractor exploded")
            calls.append((scan_run_root, slug, wallet))

        scanner = WalletScanner(
            scan_callable=lambda ident, flags: (
                run_root_alice.as_posix() if "Alice" in ident else run_root_bob.as_posix()
            ),
            now_provider=lambda: FIXED_NOW,
            post_scan_extractor=failing_then_ok_extractor,
        )
        paths = scanner.run(
            entries=[
                {"identifier": "@Alice", "kind": "handle"},
                {"identifier": "@Bob", "kind": "handle"},
            ],
            output_root=tmp_path / "out",
            run_id="non-fatal-run",
            profile="lite",
            input_file_path="wallets.txt",
        )
        # Both scans ran; extractor was called twice (once raising, once ok)
        assert call_count["n"] == 2
        # The leaderboard still contains both entries (loop didn't abort)
        leaderboard = json.loads(Path(paths["leaderboard_json"]).read_text(encoding="utf-8"))
        assert leaderboard["entries_succeeded"] == 2
        # Error message was printed to stderr
        captured = capsys.readouterr()
        assert "dossier-extract" in captured.err
        assert "Non-fatal" in captured.err

    def test_read_wallet_from_dossier_present(self, tmp_path: Path) -> None:
        """_read_wallet_from_dossier returns proxy_wallet from dossier.json."""
        _write_json(tmp_path / "dossier.json", MINIMAL_DOSSIER)
        wallet = _read_wallet_from_dossier(tmp_path)
        assert wallet == "0xABC"

    def test_read_wallet_from_dossier_missing_returns_empty(self, tmp_path: Path) -> None:
        """_read_wallet_from_dossier returns '' when dossier.json is absent."""
        wallet = _read_wallet_from_dossier(tmp_path)
        assert wallet == ""

    def test_make_dossier_extractor_returns_callable(self) -> None:
        """_make_dossier_extractor returns a callable without importing at module level."""
        extractor = _make_dossier_extractor(store_path=":memory:")
        assert callable(extractor)

    def test_extract_dossier_cli_flag_in_help(self, tmp_path: Path) -> None:
        """--extract-dossier flag appears in wallet-scan CLI help output."""
        from tools.cli.wallet_scan import build_parser
        parser = build_parser()
        help_text = parser.format_help()
        assert "--extract-dossier" in help_text

    def test_no_extract_dossier_flag_default_off(self, tmp_path: Path) -> None:
        """Without --extract-dossier, args.extract_dossier is False."""
        from tools.cli.wallet_scan import build_parser
        parser = build_parser()
        args = parser.parse_args(["--input", "wallets.txt"])
        assert args.extract_dossier is False


# ---------------------------------------------------------------------------
# Username display convention (export -> scan -> dossier handoff)
# ---------------------------------------------------------------------------


def _write_dossier_header(run_root: Path, *, proxy_wallet: str, username: str | None = None) -> None:
    """Write a minimal dossier.json with a header (proxy_wallet + optional username)."""
    header: dict = {"proxy_wallet": proxy_wallet}
    if username is not None:
        header["username"] = username
    _write_json(run_root / "dossier.json", {"header": header, "positions": {"positions": []}})


class TestUsernameSidecarHandoff:
    """parse_input_file + sidecar loader carry display usernames; bare addresses still work."""

    WALLET = "0xa380c504a480f591c7dfbf9944fac3994b9b21ff"

    def test_parse_attaches_username_from_map(self, tmp_path: Path) -> None:
        f = tmp_path / "ids.txt"
        _write_text(f, f"{self.WALLET}\n0xdeadbeef1234\n")
        umap = {self.WALLET.lower(): "Scaly-Champion"}
        entries = parse_input_file(f, username_map=umap)
        assert entries[0]["username"] == "Scaly-Champion"
        # canonical key (identifier) is untouched; second wallet has no name
        assert entries[0]["identifier"] == self.WALLET
        assert entries[1]["username"] == ""

    def test_bare_address_no_map_yields_empty_username(self, tmp_path: Path) -> None:
        f = tmp_path / "ids.txt"
        _write_text(f, f"{self.WALLET}\n")
        entries = parse_input_file(f)  # no username_map at all
        assert entries[0]["username"] == ""
        assert entries[0]["identifier"] == self.WALLET

    def test_sidecar_loader_reads_and_lowercases_keys(self, tmp_path: Path) -> None:
        f = tmp_path / "wallets.txt"
        _write_text(f, f"{self.WALLET}\n")
        sidecar = tmp_path / "wallets.txt.usernames.json"
        _write_json(sidecar, {self.WALLET.upper(): "Alice", "0xother": ""})
        umap = _load_username_sidecar(f)
        # key lowercased; empty-username entry dropped
        assert umap == {self.WALLET.lower(): "Alice"}

    def test_sidecar_absent_returns_empty_map(self, tmp_path: Path) -> None:
        f = tmp_path / "wallets.txt"
        _write_text(f, f"{self.WALLET}\n")
        assert _load_username_sidecar(f) == {}

    def test_sidecar_garbled_returns_empty_map(self, tmp_path: Path) -> None:
        f = tmp_path / "wallets.txt"
        _write_text(f, f"{self.WALLET}\n")
        _write_text(tmp_path / "wallets.txt.usernames.json", "{not json")
        assert _load_username_sidecar(f) == {}


class TestResolveWalletId:
    """wallet_id is canonical: dossier proxy_wallet, else a wallet identifier, never a username."""

    def test_prefers_dossier_proxy_wallet(self, tmp_path: Path) -> None:
        run_root = tmp_path / "run"
        run_root.mkdir()
        _write_dossier_header(run_root, proxy_wallet="0xCANONICAL")
        entry = {"identifier": "@Alice", "kind": "handle", "username": "Alice"}
        assert _resolve_wallet_id(entry, run_root) == "0xCANONICAL"

    def test_falls_back_to_wallet_identifier(self, tmp_path: Path) -> None:
        run_root = tmp_path / "run"
        run_root.mkdir()  # no dossier.json
        entry = {"identifier": "0xWALLET", "kind": "wallet", "username": ""}
        assert _resolve_wallet_id(entry, run_root) == "0xWALLET"

    def test_handle_without_dossier_yields_empty(self, tmp_path: Path) -> None:
        run_root = tmp_path / "run"
        run_root.mkdir()
        entry = {"identifier": "@Alice", "kind": "handle", "username": "Alice"}
        assert _resolve_wallet_id(entry, run_root) == ""


class TestStampDossierUsername:
    def test_stamps_when_absent(self, tmp_path: Path) -> None:
        run_root = tmp_path / "run"
        run_root.mkdir()
        _write_dossier_header(run_root, proxy_wallet="0xabc")  # no username
        _stamp_dossier_username(run_root, "Scaly-Champion")
        d = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        assert d["header"]["username"] == "Scaly-Champion"

    def test_does_not_overwrite_existing(self, tmp_path: Path) -> None:
        run_root = tmp_path / "run"
        run_root.mkdir()
        _write_dossier_header(run_root, proxy_wallet="0xabc", username="RealHandle")
        _stamp_dossier_username(run_root, "FromHandoff")
        d = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        assert d["header"]["username"] == "RealHandle"

    def test_empty_username_is_noop(self, tmp_path: Path) -> None:
        run_root = tmp_path / "run"
        run_root.mkdir()
        _write_dossier_header(run_root, proxy_wallet="0xabc")
        _stamp_dossier_username(run_root, "")
        d = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        assert "username" not in d["header"]

    def test_missing_dossier_is_noop(self, tmp_path: Path) -> None:
        run_root = tmp_path / "run"
        run_root.mkdir()
        _stamp_dossier_username(run_root, "X")  # no dossier.json -> no raise


class TestWalletScannerUsernameCarry:
    """End-to-end: handoff username lands in the dossier, results, and leaderboard."""

    WALLET = "0xa380c504a480f591c7dfbf9944fac3994b9b21ff"

    def _scanner_for(self, run_root: Path) -> WalletScanner:
        def fake_scan(identifier: str, scan_flags: dict) -> str:
            return run_root.as_posix()

        return WalletScanner(scan_callable=fake_scan, now_provider=lambda: FIXED_NOW)

    def test_handoff_username_carried_into_artifacts_and_dossier(self, tmp_path: Path) -> None:
        run_root = _make_scan_run_root(tmp_path / "runs", "r", pnl_net=10.0)
        _write_dossier_header(run_root, proxy_wallet=self.WALLET)  # pseudonymous: no username

        scanner = self._scanner_for(run_root)
        entries = [{"identifier": self.WALLET, "kind": "wallet", "username": "Scaly-Champion"}]
        paths = scanner.run(
            entries=entries,
            output_root=tmp_path / "out",
            run_id="run-uc-1",
            profile="lite",
            input_file_path="wallets.txt",
        )

        # dossier header now carries the handoff username
        d = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        assert d["header"]["username"] == "Scaly-Champion"

        lb = json.loads(Path(paths["leaderboard_json"]).read_text(encoding="utf-8"))
        row = lb["ranked"][0]
        assert row["wallet_id"] == self.WALLET          # canonical
        assert row["username"] == "Scaly-Champion"      # display
        assert row["display_name"] == "Scaly-Champion"
        # markdown shows the human name AND the wallet id as separate columns
        md = Path(paths["leaderboard_md"]).read_text(encoding="utf-8")
        assert "Scaly-Champion" in md
        assert self.WALLET in md

    def test_pseudonymous_wallet_display_falls_back_to_truncated_id(self, tmp_path: Path) -> None:
        run_root = _make_scan_run_root(tmp_path / "runs", "r", pnl_net=1.0)
        _write_dossier_header(run_root, proxy_wallet=self.WALLET)

        scanner = self._scanner_for(run_root)
        # bare-address path: no username in the handoff
        entries = [{"identifier": self.WALLET, "kind": "wallet", "username": ""}]
        paths = scanner.run(
            entries=entries,
            output_root=tmp_path / "out",
            run_id="run-uc-2",
            profile="lite",
            input_file_path="wallets.txt",
        )
        lb = json.loads(Path(paths["leaderboard_json"]).read_text(encoding="utf-8"))
        row = lb["ranked"][0]
        assert row["wallet_id"] == self.WALLET
        assert row["username"] == ""
        # display falls back to a truncated wallet id, NOT the raw full address
        assert row["display_name"] == "0xa380...21ff"

