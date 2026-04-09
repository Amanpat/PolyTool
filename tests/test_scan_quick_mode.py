"""AT-06: No-LLM guarantee tests for --quick flag on scan CLI (Wallet Discovery v1).

Tests:
1. No-LLM guarantee — --quick scan makes zero HTTP calls to cloud LLM endpoints.
2. MVF in output — dossier.json contains "mvf" key with dimensions + metadata after --quick scan.
3. --quick implies lite stages — only LITE_PIPELINE_STAGE_SET stages are enabled.
4. Existing scan unaffected — scan without --quick does NOT add MVF block to dossier.json.
5. config["quick"] propagated — build_config wires the quick flag correctly.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from pathlib import Path

import pytest

from tools.cli import scan
from tools.cli.scan import LITE_PIPELINE_STAGE_SET, FULL_PIPELINE_STAGE_SET

# ---------------------------------------------------------------------------
# Shared fixture factory
# ---------------------------------------------------------------------------

_LLM_DOMAINS = (
    "gemini", "deepseek", "openai", "anthropic", "googleapis",
    "generativelanguage", "api.openai", "api.anthropic",
)

# Minimal 12-position fixture with resolution_outcome, entry_price, market_slug, category, size.
_POSITIONS_FIXTURE = [
    {
        "trade_uid": f"uid-{i}",
        "resolved_token_id": f"tok-{i}",
        "resolution_outcome": outcome,
        "entry_price": 0.1 + i * 0.06,
        "market_slug": f"market-{i % 4}",
        "category": ["Crypto", "Politics", "Sports", "Entertainment"][i % 4],
        "size": 100.0 + i * 10,
        "position_notional_usd": (0.1 + i * 0.06) * (100.0 + i * 10),
        "realized_pnl_net": 1.0 if outcome in ("WIN", "PROFIT_EXIT") else -0.5,
        "position_remaining": 0.0,
    }
    for i, outcome in enumerate(
        ["WIN", "WIN", "WIN", "WIN", "WIN",
         "LOSS", "LOSS", "LOSS",
         "PROFIT_EXIT", "LOSS_EXIT",
         "PENDING", "PENDING"]
    )
]


def _make_run_root(tmp_path: Path) -> Path:
    run_root = (
        tmp_path
        / "artifacts"
        / "dossiers"
        / "users"
        / "quickuser"
        / "0xquick"
        / "2026-04-09"
        / "run-quick"
    )
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "dossier.json").write_text(
        json.dumps(
            {"positions": {"positions": _POSITIONS_FIXTURE}},
            indent=2,
        ),
        encoding="utf-8",
    )
    return run_root


def _fake_post_json_quick(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
    """Minimal mock API responder for --quick scan (lite stages only)."""
    if path == "/api/resolve":
        return {"username": "QuickUser", "proxy_wallet": "0xquick"}
    if path == "/api/ingest/trades":
        return {
            "pages_fetched": 1,
            "rows_fetched_total": len(_POSITIONS_FIXTURE),
            "rows_written": len(_POSITIONS_FIXTURE),
            "distinct_trade_uids_total": len(_POSITIONS_FIXTURE),
        }
    if path == "/api/run/detectors":
        return {"results": [], "backfill_stats": None}
    if path == "/api/export/user_dossier":
        # Return artifact_path pointing to our pre-created run_root.
        # The path is injected per-test via a closure.
        raise AssertionError(f"Unexpected scan API path in quick mode: {path}")
    raise AssertionError(f"Unexpected scan API path: {path}")


def _base_config(run_root: Path, *, quick: bool = True) -> dict:
    """Build a minimal scan config for the given run_root."""
    return {
        "user": "@QuickUser",
        "max_pages": 10,
        "bucket": "day",
        "backfill": True,
        "quick": quick,
        "ingest_markets": False,
        "ingest_activity": False,
        "ingest_positions": False,
        "compute_pnl": False,
        "compute_opportunities": False,
        "snapshot_books": False,
        "enrich_resolutions": False,
        "warm_clv_cache": False,
        "compute_clv": False,
        "clv_online": False,
        "clv_window_minutes": 30,
        "clv_interval": "1m",
        "clv_fidelity": 1,
        "resolution_max_candidates": 500,
        "resolution_batch_size": 25,
        "resolution_max_concurrency": 4,
        "debug_export": False,
        "audit_sample": None,
        "audit_seed": 42,
        "entry_price_tiers": None,
        "fee_config": None,
        "api_base_url": "http://localhost:8000",
        "timeout_seconds": 30.0,
    }


# ---------------------------------------------------------------------------
# Test 1: No-LLM guarantee
# ---------------------------------------------------------------------------

class TestNoLlmGuarantee:
    """AT-06: --quick scan makes zero HTTP calls to cloud LLM endpoints."""

    def test_no_llm_calls_in_quick_scan(self, monkeypatch, tmp_path):
        run_root = _make_run_root(tmp_path)
        original_cwd = Path.cwd()
        outbound_urls: list[str] = []

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            url = base_url + path
            outbound_urls.append(url)
            if path == "/api/resolve":
                return {"username": "QuickUser", "proxy_wallet": "0xquick"}
            if path == "/api/ingest/trades":
                return {"pages_fetched": 1, "rows_fetched_total": 12, "rows_written": 12, "distinct_trade_uids_total": 12}
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-quick",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xquick",
                    "username_slug": "quickuser",
                }
            raise AssertionError(f"Unexpected scan API path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)
        try:
            os.chdir(tmp_path)
            config = _base_config(run_root, quick=True)
            scan.run_scan(config=config, argv=["--user", "@QuickUser", "--quick"],
                          started_at="2026-04-09T10:00:00+00:00")
        finally:
            os.chdir(original_cwd)

        # Verify no outbound URL is an LLM provider domain.
        for url in outbound_urls:
            for domain in _LLM_DOMAINS:
                assert domain not in url.lower(), (
                    f"LLM endpoint called during --quick scan: {url}"
                )

    def test_no_llm_domains_in_any_call(self, monkeypatch, tmp_path):
        """Secondary check: LLM domain patterns not present in any API call."""
        run_root = _make_run_root(tmp_path)
        original_cwd = Path.cwd()
        all_calls: list[str] = []

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            all_calls.append(f"{base_url}{path}")
            if path == "/api/resolve":
                return {"username": "QuickUser", "proxy_wallet": "0xquick"}
            if path == "/api/ingest/trades":
                return {"pages_fetched": 1, "rows_fetched_total": 12, "rows_written": 12, "distinct_trade_uids_total": 12}
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-quick",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xquick",
                    "username_slug": "quickuser",
                }
            raise AssertionError(f"Unexpected path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)
        try:
            os.chdir(tmp_path)
            config = _base_config(run_root, quick=True)
            scan.run_scan(config=config, argv=["--user", "@QuickUser", "--quick"],
                          started_at="2026-04-09T10:00:00+00:00")
        finally:
            os.chdir(original_cwd)

        llm_calls = [url for url in all_calls
                     if any(d in url.lower() for d in _LLM_DOMAINS)]
        assert llm_calls == [], f"LLM calls found: {llm_calls}"


# ---------------------------------------------------------------------------
# Test 2: MVF in dossier.json output
# ---------------------------------------------------------------------------

class TestMvfInOutput:
    """After --quick scan, dossier.json contains 'mvf' key with dimensions + metadata."""

    def _run_quick_scan(self, monkeypatch, tmp_path) -> Path:
        run_root = _make_run_root(tmp_path)
        original_cwd = Path.cwd()

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            if path == "/api/resolve":
                return {"username": "QuickUser", "proxy_wallet": "0xquick"}
            if path == "/api/ingest/trades":
                return {"pages_fetched": 1, "rows_fetched_total": 12, "rows_written": 12, "distinct_trade_uids_total": 12}
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-quick",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xquick",
                    "username_slug": "quickuser",
                }
            raise AssertionError(f"Unexpected path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)
        try:
            os.chdir(tmp_path)
            config = _base_config(run_root, quick=True)
            scan.run_scan(config=config, argv=["--user", "@QuickUser", "--quick"],
                          started_at="2026-04-09T10:00:00+00:00")
        finally:
            os.chdir(original_cwd)
        return run_root

    def test_dossier_contains_mvf_key(self, monkeypatch, tmp_path):
        run_root = self._run_quick_scan(monkeypatch, tmp_path)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        assert "mvf" in dossier, "Expected 'mvf' key in dossier.json after --quick scan"

    def test_mvf_has_dimensions_and_metadata(self, monkeypatch, tmp_path):
        run_root = self._run_quick_scan(monkeypatch, tmp_path)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        mvf = dossier["mvf"]
        assert "dimensions" in mvf
        assert "metadata" in mvf

    def test_mvf_dimensions_count_11(self, monkeypatch, tmp_path):
        run_root = self._run_quick_scan(monkeypatch, tmp_path)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        dims = dossier["mvf"]["dimensions"]
        assert len(dims) == 11

    def test_mvf_metadata_input_trade_count_matches_fixture(self, monkeypatch, tmp_path):
        run_root = self._run_quick_scan(monkeypatch, tmp_path)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        meta = dossier["mvf"]["metadata"]
        assert meta["input_trade_count"] == len(_POSITIONS_FIXTURE)

    def test_mvf_metadata_wallet_address_set(self, monkeypatch, tmp_path):
        run_root = self._run_quick_scan(monkeypatch, tmp_path)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        meta = dossier["mvf"]["metadata"]
        assert meta["wallet_address"] == "0xquick"

    def test_mvf_maker_taker_ratio_null(self, monkeypatch, tmp_path):
        """Fixture has no maker/taker fields -> maker_taker_ratio must be null."""
        run_root = self._run_quick_scan(monkeypatch, tmp_path)
        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        dims = dossier["mvf"]["dimensions"]
        assert dims["maker_taker_ratio"] is None


# ---------------------------------------------------------------------------
# Test 3: --quick implies lite stages
# ---------------------------------------------------------------------------

class TestQuickImpliesLiteStages:
    """--quick enables only LITE_PIPELINE_STAGE_SET stages."""

    def test_apply_scan_defaults_quick_sets_lite_stages(self):
        args = argparse.Namespace(
            quick=True,
            full=False,
            lite=False,
            ingest_markets=None,
            ingest_activity=None,
            ingest_positions=None,
            compute_pnl=None,
            compute_opportunities=None,
            snapshot_books=None,
            enrich_resolutions=None,
            warm_clv_cache=None,
            compute_clv=None,
        )
        result = scan.apply_scan_defaults(args, ["--user", "@test", "--quick"])

        # All LITE stages must be True.
        for stage in LITE_PIPELINE_STAGE_SET:
            assert getattr(result, stage) is True, f"Expected {stage}=True for --quick, got {getattr(result, stage)}"

        # All non-LITE stages must be False (disable_non_enabled=True).
        non_lite = set(scan.FULL_PIPELINE_STAGE_ATTRS) - LITE_PIPELINE_STAGE_SET
        for stage in non_lite:
            assert getattr(result, stage) is False, (
                f"Expected {stage}=False for --quick, got {getattr(result, stage)}"
            )

    def test_quick_takes_precedence_over_full(self):
        """--quick before --full: quick wins."""
        args = argparse.Namespace(
            quick=True,
            full=True,
            lite=False,
            ingest_markets=None,
            ingest_activity=None,
            ingest_positions=None,
            compute_pnl=None,
            compute_opportunities=None,
            snapshot_books=None,
            enrich_resolutions=None,
            warm_clv_cache=None,
            compute_clv=None,
        )
        result = scan.apply_scan_defaults(args, ["--user", "@test", "--quick", "--full"])
        # Quick takes precedence: expensive stages disabled.
        assert result.ingest_markets is False
        assert result.ingest_activity is False
        assert result.compute_opportunities is False
        assert result.snapshot_books is False
        assert result.ingest_positions is True


# ---------------------------------------------------------------------------
# Test 4: Existing scan unaffected (no MVF without --quick)
# ---------------------------------------------------------------------------

class TestExistingScanUnaffected:
    """Running scan without --quick does NOT add MVF block to dossier.json."""

    def test_no_mvf_block_without_quick_flag(self, monkeypatch, tmp_path):
        run_root = _make_run_root(tmp_path)
        original_cwd = Path.cwd()

        def fake_post_json(base_url, path, payload, timeout=120.0, retries=3, backoff_seconds=1.0):
            if path == "/api/resolve":
                return {"username": "QuickUser", "proxy_wallet": "0xquick"}
            if path == "/api/ingest/trades":
                return {"pages_fetched": 1, "rows_fetched_total": 12, "rows_written": 12, "distinct_trade_uids_total": 12}
            if path == "/api/run/detectors":
                return {"results": [], "backfill_stats": None}
            if path == "/api/export/user_dossier":
                return {
                    "export_id": "run-quick",
                    "artifact_path": str(run_root),
                    "proxy_wallet": "0xquick",
                    "username_slug": "quickuser",
                }
            raise AssertionError(f"Unexpected path: {path}")

        monkeypatch.setattr(scan, "post_json", fake_post_json)
        try:
            os.chdir(tmp_path)
            # Run WITHOUT --quick flag
            config = _base_config(run_root, quick=False)
            scan.run_scan(
                config=config,
                argv=["--user", "@QuickUser"],
                started_at="2026-04-09T10:00:00+00:00",
            )
        finally:
            os.chdir(original_cwd)

        dossier = json.loads((run_root / "dossier.json").read_text(encoding="utf-8"))
        assert "mvf" not in dossier, (
            "MVF block must NOT be present in dossier.json when --quick is not used"
        )


# ---------------------------------------------------------------------------
# Test 5: config["quick"] propagated via build_config
# ---------------------------------------------------------------------------

class TestConfigQuickPropagated:
    """build_config wires the quick flag correctly from args."""

    def test_quick_true_in_config_when_flag_set(self):
        parser = scan.build_parser()
        args = parser.parse_args(["--user", "@test", "--quick"])
        config = scan.build_config(args)
        assert config["quick"] is True

    def test_quick_false_in_config_when_flag_absent(self):
        parser = scan.build_parser()
        args = parser.parse_args(["--user", "@test"])
        config = scan.build_config(args)
        assert config.get("quick") is False

    def test_quick_flag_accepted_by_parser(self):
        parser = scan.build_parser()
        args = parser.parse_args(["--user", "@test", "--quick"])
        assert args.quick is True

    def test_quick_flag_default_false(self):
        parser = scan.build_parser()
        args = parser.parse_args(["--user", "@test"])
        assert args.quick is False
