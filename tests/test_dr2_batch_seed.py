"""DR-2 Batch-Seed Top-200 Corpus — offline/deterministic tests.

Covers:
  * leaderboard export helper output shape (mock fetch -> wallet-scan input
    format: one 0x per line, deduped, `#` header lines the parser ignores),
  * top-N -> page-count mapping reuses fetch_leaderboard (no new fetch logic),
  * BulkPacer is default-OFF (zero sleep calls) and sleeps the right number of
    times when enabled, on BOTH the leaderboard page loop and the wallet-scan
    batch loop,
  * round-trip: exported file parses back through wallet_scan.parse_input_file.

All tests are offline: fetch_leaderboard is mocked; sleep is injected and
asserted. No network, no ClickHouse.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# BulkPacer
# ---------------------------------------------------------------------------

class TestBulkPacer:
    def test_disabled_never_sleeps(self):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer

        calls: list[float] = []
        pacer = BulkPacer(0.5, enabled=False, sleep_fn=calls.append)
        for _ in range(10):
            assert pacer.pace() == 0.0
        assert calls == []

    def test_disabled_factory(self):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer

        calls: list[float] = []
        pacer = BulkPacer.disabled()
        pacer._sleep = calls.append  # type: ignore[attr-defined]
        for _ in range(5):
            pacer.pace()
        assert calls == []

    def test_zero_delay_is_disabled_even_if_enabled(self):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer

        calls: list[float] = []
        pacer = BulkPacer(0.0, enabled=True, sleep_fn=calls.append)
        assert pacer.enabled is False
        pacer.pace()
        assert calls == []

    def test_enabled_sleeps_remaining_interval(self):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer

        # Monotonic clock that does not advance between calls -> every gap is the
        # full delay. First pace() is the anchor (no sleep); subsequent ones sleep.
        clock = [100.0]
        calls: list[float] = []
        pacer = BulkPacer(
            0.5,
            enabled=True,
            sleep_fn=calls.append,
            monotonic_fn=lambda: clock[0],
        )
        assert pacer.pace() == 0.0  # anchor
        assert pacer.pace() == pytest.approx(0.5)
        assert pacer.pace() == pytest.approx(0.5)
        assert calls == [pytest.approx(0.5), pytest.approx(0.5)]

    def test_enabled_skips_sleep_when_caller_already_slow(self):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer

        clock = [0.0]
        calls: list[float] = []
        pacer = BulkPacer(
            0.5,
            enabled=True,
            sleep_fn=calls.append,
            monotonic_fn=lambda: clock[0],
        )
        pacer.pace()       # anchor at t=0
        clock[0] = 10.0    # caller took 10s on its own
        slept = pacer.pace()
        assert slept == 0.0
        assert calls == []


class TestLoadBulkPacing:
    def test_default_config_is_disabled(self, tmp_path: Path):
        from packages.polymarket.discovery.bulk_pacing import load_bulk_pacing

        cfg = tmp_path / "c.json"
        cfg.write_text('{"bulk_pacing": {"enabled": false, "delay_seconds": 0.5}}', "utf-8")
        pacer = load_bulk_pacing(cfg)
        assert pacer.enabled is False
        assert pacer.delay_seconds == 0.5

    def test_missing_section_is_disabled(self, tmp_path: Path):
        from packages.polymarket.discovery.bulk_pacing import load_bulk_pacing

        cfg = tmp_path / "c.json"
        cfg.write_text("{}", "utf-8")
        assert load_bulk_pacing(cfg).enabled is False

    def test_missing_file_is_disabled(self, tmp_path: Path):
        from packages.polymarket.discovery.bulk_pacing import load_bulk_pacing

        assert load_bulk_pacing(tmp_path / "nope.json").enabled is False

    def test_enabled_config_builds_enabled_pacer(self, tmp_path: Path):
        from packages.polymarket.discovery.bulk_pacing import load_bulk_pacing

        cfg = tmp_path / "c.json"
        cfg.write_text('{"bulk_pacing": {"enabled": true, "delay_seconds": 1.25}}', "utf-8")
        pacer = load_bulk_pacing(cfg)
        assert pacer.enabled is True
        assert pacer.delay_seconds == 1.25

    def test_shipped_config_bulk_pacing_is_off(self):
        """The repo's shipped config MUST keep bulk pacing OFF by default."""
        from packages.polymarket.discovery.bulk_pacing import load_bulk_pacing

        pacer = load_bulk_pacing(Path("config") / "discovery_scheduler.json")
        assert pacer.enabled is False


# ---------------------------------------------------------------------------
# Export helper output shape
# ---------------------------------------------------------------------------

def _fake_entries(n: int, start: int = 1) -> list[dict]:
    return [
        {
            "rank": start + i,
            "proxy_wallet": f"0x{(start + i):040x}",
            "name": f"u{start + i}",
            "pnl": float(start + i),
            "volume": float(start + i) * 10,
        }
        for i in range(n)
    ]


class TestExportHelper:
    def test_returns_addresses_truncated_to_top(self):
        from packages.polymarket.discovery.leaderboard_export import (
            export_leaderboard_addresses,
        )

        fetch_fn = MagicMock(return_value=_fake_entries(200))
        addrs = export_leaderboard_addresses(top=200, fetch_fn=fetch_fn)
        assert len(addrs) == 200
        assert all(a.startswith("0x") for a in addrs)
        # top=200 with page_size 50 => 4 pages requested (reuses fetch, no new logic)
        assert fetch_fn.call_args.kwargs["max_pages"] == 4

    def test_dedup_preserves_order(self):
        from packages.polymarket.discovery.leaderboard_export import (
            export_leaderboard_addresses,
        )

        dup = _fake_entries(3) + _fake_entries(3)  # 6 entries, 3 unique
        addrs = export_leaderboard_addresses(top=10, fetch_fn=MagicMock(return_value=dup))
        assert addrs == [f"0x{i:040x}" for i in (1, 2, 3)]

    def test_skips_empty_proxy_wallet(self):
        from packages.polymarket.discovery.leaderboard_export import (
            export_leaderboard_addresses,
        )

        entries = _fake_entries(2) + [{"rank": 3, "proxy_wallet": ""}]
        addrs = export_leaderboard_addresses(top=10, fetch_fn=MagicMock(return_value=entries))
        assert addrs == [f"0x{i:040x}" for i in (1, 2)]

    def test_reads_camelcase_proxywallet_from_live_api_shape(self):
        """Regression (DR-2a): the live data API returns `proxyWallet` (camelCase)
        and string `rank`. The export must extract addresses from that shape, not
        only the snake_case `proxy_wallet` test fixtures used previously."""
        from packages.polymarket.discovery.leaderboard_export import (
            export_leaderboard_addresses,
        )

        live = [
            {"rank": "1", "proxyWallet": f"0x{1:040x}", "userName": "a", "pnl": 9.0, "vol": 90.0},
            {"rank": "2", "proxyWallet": f"0x{2:040x}", "userName": "b", "pnl": 8.0, "vol": 80.0},
            {"rank": "3", "proxyWallet": f"0x{3:040x}", "userName": "c", "pnl": 7.0, "vol": 70.0},
        ]
        addrs = export_leaderboard_addresses(top=5, fetch_fn=MagicMock(return_value=live))
        assert addrs == [f"0x{i:040x}" for i in (1, 2, 3)]

    def test_top_zero_returns_empty(self):
        from packages.polymarket.discovery.leaderboard_export import (
            export_leaderboard_addresses,
        )

        fetch_fn = MagicMock(return_value=_fake_entries(5))
        assert export_leaderboard_addresses(top=0, fetch_fn=fetch_fn) == []
        fetch_fn.assert_not_called()

    def test_write_input_file_format(self, tmp_path: Path):
        from packages.polymarket.discovery.leaderboard_export import write_input_file

        out = tmp_path / "top.txt"
        n = write_input_file([f"0x{i:040x}" for i in (1, 2, 3)], out)
        assert n == 3
        text = out.read_text("utf-8")
        # header lines are `#` comments (ignored by wallet-scan parser)
        assert text.startswith("# ")
        assert text.endswith("\n")
        addr_lines = [ln for ln in text.splitlines() if not ln.startswith("#") and ln.strip()]
        assert addr_lines == [f"0x{i:040x}" for i in (1, 2, 3)]

    def test_export_to_file_roundtrips_through_wallet_scan_parser(self, tmp_path: Path):
        """The exported file MUST parse back as wallet entries (verified format)."""
        from packages.polymarket.discovery.leaderboard_export import export_to_file
        from tools.cli.wallet_scan import parse_input_file

        out = tmp_path / "top.txt"
        summary = export_to_file(
            5, out, fetch_fn=MagicMock(return_value=_fake_entries(5)), pacer=None
        )
        assert summary["written"] == 5
        assert summary["pacing_enabled"] is False

        parsed = parse_input_file(out)
        assert len(parsed) == 5
        assert all(p["kind"] == "wallet" for p in parsed)
        assert parsed[0]["identifier"] == f"0x{1:040x}"


# ---------------------------------------------------------------------------
# Pacing applied on the real code paths (page loop + batch loop)
# ---------------------------------------------------------------------------

class TestPacingWiredIntoLeaderboardPageLoop:
    def _mock_client(self, pages: list[list[dict]]):
        def mock_get(path, params=None, headers=None):
            offset = (params or {}).get("offset", 0)
            idx = offset // 50
            data = pages[idx] if idx < len(pages) else []
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = data
            return resp

        client = MagicMock()
        client.get = mock_get
        return client

    def test_no_pacer_means_no_sleep(self):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer
        from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard

        calls: list[float] = []
        pacer = BulkPacer(0.5, enabled=False, sleep_fn=calls.append)
        pages = [_fake_entries(50, 1), _fake_entries(50, 51)]
        fetch_leaderboard(max_pages=2, page_size=50,
                          http_client=self._mock_client(pages), pacer=pacer)
        assert calls == []

    def test_enabled_paces_once_per_page_after_first(self):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer
        from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard

        clock = [0.0]
        calls: list[float] = []
        pacer = BulkPacer(0.5, enabled=True, sleep_fn=calls.append,
                          monotonic_fn=lambda: clock[0])
        pages = [
            _fake_entries(50, 1), _fake_entries(50, 51),
            _fake_entries(50, 101), _fake_entries(50, 151),
        ]
        fetch_leaderboard(max_pages=4, page_size=50,
                          http_client=self._mock_client(pages), pacer=pacer)
        # pace() is called before pages 2,3,4 (page_num>0): 1st call is the
        # cadence anchor (no sleep), the next 2 sleep -> 2 sleeps for 4 pages.
        assert len(calls) == 2


class TestPacingWiredIntoWalletScanBatchLoop:
    def _scanner(self, pacer, run_dir: Path):
        from tools.cli.wallet_scan import WalletScanner

        def scan_callable(identifier, flags):
            # minimal scan run root with a dossier.json-less dir
            d = run_dir / identifier.replace("0x", "w")
            d.mkdir(parents=True, exist_ok=True)
            return str(d)

        return WalletScanner(scan_callable=scan_callable, pacer=pacer)

    def _entries(self, n: int):
        return [{"identifier": f"0x{i:040x}", "kind": "wallet"} for i in range(1, n + 1)]

    def test_no_pacer_no_sleep(self, tmp_path: Path):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer

        calls: list[float] = []
        pacer = BulkPacer(0.5, enabled=False, sleep_fn=calls.append)
        scanner = self._scanner(pacer, tmp_path / "runs")
        scanner.run(
            entries=self._entries(4),
            output_root=tmp_path / "out",
            run_id="r1",
            profile="lite",
            input_file_path="x.txt",
        )
        assert calls == []

    def test_enabled_paces_between_wallets(self, tmp_path: Path):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer

        clock = [0.0]
        calls: list[float] = []
        pacer = BulkPacer(0.5, enabled=True, sleep_fn=calls.append,
                          monotonic_fn=lambda: clock[0])
        scanner = self._scanner(pacer, tmp_path / "runs")
        scanner.run(
            entries=self._entries(5),
            output_root=tmp_path / "out",
            run_id="r1",
            profile="lite",
            input_file_path="x.txt",
        )
        # pace() before wallets 2,3,4,5 (idx>0): 1st is the anchor (no sleep),
        # the next 3 sleep -> 3 sleeps for 5 wallets.
        assert len(calls) == 3


def _fake_entries_named(n: int, start: int = 1, named_only_even: bool = False) -> list[dict]:
    """Fake live-API entries with camelCase userName (some possibly blank)."""
    out = []
    for i in range(n):
        idx = start + i
        username = "" if (named_only_even and idx % 2 == 1) else f"User{idx}"
        out.append(
            {
                "rank": str(idx),
                "proxyWallet": f"0x{idx:040x}",
                "userName": username,
                "pnl": float(idx),
                "vol": float(idx) * 10,
            }
        )
    return out


class TestUsernameSidecarExport:
    """export->scan handoff: username sidecar is emitted; bare addresses unchanged."""

    def test_entries_carry_username_camelcase(self):
        from packages.polymarket.discovery.leaderboard_export import (
            export_leaderboard_entries,
        )

        entries = export_leaderboard_entries(
            top=3, fetch_fn=MagicMock(return_value=_fake_entries_named(3))
        )
        assert entries[0] == {"wallet": f"0x{1:040x}", "username": "User1"}
        assert [e["wallet"] for e in entries] == [f"0x{i:040x}" for i in (1, 2, 3)]

    def test_addresses_wrapper_unchanged(self):
        from packages.polymarket.discovery.leaderboard_export import (
            export_leaderboard_addresses,
        )

        addrs = export_leaderboard_addresses(
            top=3, fetch_fn=MagicMock(return_value=_fake_entries_named(3))
        )
        assert addrs == [f"0x{i:040x}" for i in (1, 2, 3)]

    def test_write_username_sidecar_only_nonempty_lowercased(self, tmp_path: Path):
        from packages.polymarket.discovery.leaderboard_export import (
            username_sidecar_path,
            write_username_sidecar,
        )

        out = tmp_path / "top.txt"
        entries = [
            {"wallet": "0xAAA", "username": "Alice"},
            {"wallet": "0xBBB", "username": ""},  # dropped
        ]
        n = write_username_sidecar(entries, out)
        assert n == 1
        sidecar = username_sidecar_path(out)
        assert sidecar.name == "top.txt.usernames.json"
        data = json.loads(sidecar.read_text("utf-8"))
        assert data == {"0xaaa": "Alice"}

    def test_no_usernames_writes_no_sidecar(self, tmp_path: Path):
        from packages.polymarket.discovery.leaderboard_export import (
            username_sidecar_path,
            write_username_sidecar,
        )

        out = tmp_path / "top.txt"
        n = write_username_sidecar([{"wallet": "0xAAA", "username": ""}], out)
        assert n == 0
        assert not username_sidecar_path(out).exists()

    def test_export_to_file_emits_sidecar_and_roundtrips(self, tmp_path: Path):
        """End-to-end: export writes input + sidecar; wallet-scan parser reattaches names."""
        from packages.polymarket.discovery.leaderboard_export import export_to_file
        from tools.cli.wallet_scan import _load_username_sidecar, parse_input_file

        out = tmp_path / "top.txt"
        summary = export_to_file(
            3, out, fetch_fn=MagicMock(return_value=_fake_entries_named(3)), pacer=None
        )
        assert summary["written"] == 3
        assert summary["usernames_written"] == 3
        assert summary["username_sidecar_path"].endswith("top.txt.usernames.json")

        # input file itself is still bare addresses (backward compatible)
        addr_lines = [
            ln for ln in out.read_text("utf-8").splitlines()
            if ln.strip() and not ln.startswith("#")
        ]
        assert addr_lines == [f"0x{i:040x}" for i in (1, 2, 3)]

        # wallet-scan side reattaches the display username via the sidecar
        umap = _load_username_sidecar(out)
        parsed = parse_input_file(out, username_map=umap)
        assert parsed[0]["identifier"] == f"0x{1:040x}"
        assert parsed[0]["username"] == "User1"

    def test_export_to_file_no_names_no_sidecar(self, tmp_path: Path):
        from packages.polymarket.discovery.leaderboard_export import export_to_file

        out = tmp_path / "top.txt"
        # all-odd blank usernames via named_only_even with n=1 (idx 1 -> blank)
        entries = [{"rank": "1", "proxyWallet": f"0x{1:040x}", "userName": ""}]
        summary = export_to_file(
            1, out, fetch_fn=MagicMock(return_value=entries), pacer=None
        )
        assert summary["written"] == 1
        assert summary["usernames_written"] == 0
        assert summary["username_sidecar_path"] is None
        # bare-address file still parses normally
        from tools.cli.wallet_scan import parse_input_file

        parsed = parse_input_file(out)
        assert parsed[0]["username"] == ""

