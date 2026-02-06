from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from polytool.user_context import UserContext
from tools.cli import examine


def _to_posix(path: str) -> str:
    return path.replace("\\", "/")


def test_plan_output_paths_routes_to_handle_slug():
    ctx = UserContext(
        slug="drpufferfish",
        handle="@DrPufferfish",
        wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
    )

    planned = examine.plan_output_paths(ctx, now=datetime(2026, 2, 6, 12, 0, 0))
    dossier_root = _to_posix(planned["dossier_root"])
    bundle_root = _to_posix(planned["bundle_root"])

    assert dossier_root.startswith(
        "artifacts/dossiers/users/drpufferfish/0xdb27bf2ac5d428a9c63dbc914611036855a6c56e"
    )
    assert bundle_root.startswith("kb/users/drpufferfish/llm_bundles")
    assert "unknown" not in dossier_root
    assert "unknown" not in bundle_root
    assert "/wallet_" not in dossier_root
    assert "/wallet_" not in bundle_root


def test_examine_dry_run_prints_resolved_paths(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "kb").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)

    class DummyGammaClient:
        def __init__(self, *args, **kwargs):
            pass

    def fake_resolve_user(_user_input, _gamma_client):
        return {
            "username": "DrPufferfish",
            "proxy_wallet": "0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
            "user_handle": "@DrPufferfish",
            "original_input": "@DrPufferfish",
        }

    monkeypatch.setattr(examine, "GammaClient", DummyGammaClient)
    monkeypatch.setattr(examine, "_resolve_user", fake_resolve_user)

    exit_code = examine.main(["--user", "@DrPufferfish", "--days", "30", "--dry-run"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "handle: @DrPufferfish" in captured.out
    assert "slug: drpufferfish" in captured.out
    assert "wallet: 0xdb27bf2ac5d428a9c63dbc914611036855a6c56e" in captured.out
    assert "dossier root: artifacts/dossiers/users/drpufferfish/" in _to_posix(captured.out)
    assert "bundle root: kb/users/drpufferfish/llm_bundles" in _to_posix(captured.out)
    assert "unknown" not in captured.out
    assert "wallet_db27" not in captured.out
