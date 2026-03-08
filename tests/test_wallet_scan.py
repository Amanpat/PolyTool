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
    _sort_key_for_leaderboard,
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
    return {
        "positions_total": positions_total,
        "outcome_counts": {"WIN": 2, "LOSS": 1, "PENDING": 1},
        "outcome_pcts": {"WIN": 0.5, "LOSS": 0.25, "PENDING": 0.25, "UNKNOWN_RESOLUTION": 0.0},
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


# ---------------------------------------------------------------------------
# parse_input_file
# ---------------------------------------------------------------------------


class TestParseInputFile:
    def test_parses_handles_and_wallets(self, tmp_path: Path) -> None:
        f = tmp_path / "ids.txt"
        _write_text(f, "@Alice\n0xdeadbeef1234\n@Bob\n")
        entries = parse_input_file(f)
        assert len(entries) == 3
        assert entries[0] == {"identifier": "@Alice", "kind": "handle"}
        assert entries[1] == {"identifier": "0xdeadbeef1234", "kind": "wallet"}
        assert entries[2] == {"identifier": "@Bob", "kind": "handle"}

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
