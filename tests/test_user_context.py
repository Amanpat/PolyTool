"""Tests for polytool.user_context canonical identity resolver."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from polytool.user_context import (
    normalize_handle,
    wallet_to_slug,
    resolve_user_context,
    UserContext,
    get_slug_for_user,
)


class TestNormalizeHandle:
    """Tests for normalize_handle function."""

    def test_basic_handle(self):
        assert normalize_handle("DrPufferfish") == "drpufferfish"

    def test_handle_with_at(self):
        assert normalize_handle("@DrPufferfish") == "drpufferfish"

    def test_lowercase(self):
        assert normalize_handle("@ALLCAPS") == "allcaps"
        assert normalize_handle("MixedCase") == "mixedcase"

    def test_whitespace(self):
        assert normalize_handle("  @DrPufferfish  ") == "drpufferfish"
        assert normalize_handle("  DrPufferfish  ") == "drpufferfish"

    def test_empty_inputs(self):
        assert normalize_handle(None) is None
        assert normalize_handle("") is None
        assert normalize_handle("   ") is None
        assert normalize_handle("@") is None
        assert normalize_handle("  @  ") is None

    def test_special_characters(self):
        # Special chars replaced with underscore, consecutive underscores collapsed
        assert normalize_handle("user.name") == "user_name"
        assert normalize_handle("user-name") == "user-name"  # hyphen kept
        assert normalize_handle("user_name") == "user_name"

    def test_numeric(self):
        assert normalize_handle("user123") == "user123"
        assert normalize_handle("@123user") == "123user"


class TestWalletToSlug:
    """Tests for wallet_to_slug function."""

    def test_basic_wallet(self):
        assert wallet_to_slug("0xdb27bf2ac5d428a9c63dbc914611036855a6c56e") == "wallet_db27bf2a"

    def test_uppercase_wallet(self):
        assert wallet_to_slug("0xDB27BF2AC5D428A9C63DBC914611036855A6C56E") == "wallet_db27bf2a"

    def test_no_0x_prefix(self):
        # Should still work, take first 8 chars
        assert wallet_to_slug("db27bf2ac5d428a9") == "wallet_db27bf2a"

    def test_short_wallet(self):
        assert wallet_to_slug("0x1234") == "wallet_1234"
        assert wallet_to_slug("0x") == "wallet_"

    def test_empty_wallet(self):
        assert wallet_to_slug("") == "wallet_unknown"

    def test_never_returns_unknown_for_valid_wallet(self):
        # The function should never return just "unknown"
        result = wallet_to_slug("0xabc123")
        assert result.startswith("wallet_")
        assert result != "unknown"


class TestUserContext:
    """Tests for UserContext dataclass."""

    def test_path_properties(self):
        ctx = UserContext(
            slug="drpufferfish",
            handle="@DrPufferfish",
            wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
            kb_root=Path("kb"),
            artifacts_root=Path("artifacts"),
        )

        assert ctx.kb_user_dir == Path("kb/users/drpufferfish")
        assert ctx.artifacts_user_dir == Path("artifacts/dossiers/users/drpufferfish")
        assert ctx.llm_bundles_dir == Path("kb/users/drpufferfish/llm_bundles")
        assert ctx.llm_reports_dir == Path("kb/users/drpufferfish/llm_reports")
        assert ctx.llm_notes_dir == Path("kb/users/drpufferfish/notes/LLM_notes")
        assert ctx.profile_path == Path("kb/users/drpufferfish/profile.json")

    def test_to_dict(self):
        ctx = UserContext(
            slug="drpufferfish",
            handle="@DrPufferfish",
            wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
        )
        d = ctx.to_dict()
        assert d["slug"] == "drpufferfish"
        assert d["handle"] == "@DrPufferfish"
        assert d["wallet"] == "0xdb27bf2ac5d428a9c63dbc914611036855a6c56e"


class TestResolveUserContext:
    """Tests for resolve_user_context function."""

    def test_handle_only(self):
        """When handle is provided, derive slug from handle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"

            ctx = resolve_user_context(
                handle="@DrPufferfish",
                wallet=None,
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=False,
            )

            assert ctx.slug == "drpufferfish"
            assert ctx.handle == "@DrPufferfish"
            assert ctx.wallet is None

    def test_wallet_only_no_profile(self):
        """When only wallet is provided with no profile, use wallet_<first8>."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"

            ctx = resolve_user_context(
                handle=None,
                wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=False,
            )

            assert ctx.slug == "wallet_db27bf2a"
            assert ctx.handle is None
            assert ctx.wallet == "0xdb27bf2ac5d428a9c63dbc914611036855a6c56e"

    def test_handle_and_wallet(self):
        """When both are provided, prefer handle for slug."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"

            ctx = resolve_user_context(
                handle="@DrPufferfish",
                wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=False,
            )

            assert ctx.slug == "drpufferfish"
            assert ctx.handle == "@DrPufferfish"
            assert ctx.wallet == "0xdb27bf2ac5d428a9c63dbc914611036855a6c56e"

    def test_persist_mapping(self):
        """Profile should be saved when persist_mapping=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"

            ctx = resolve_user_context(
                handle="@DrPufferfish",
                wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=True,
            )

            # Check profile was created
            profile_path = kb_root / "users" / "drpufferfish" / "profile.json"
            assert profile_path.exists()

            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            assert profile["handle"] == "@DrPufferfish"
            assert profile["wallet"] == "0xdb27bf2ac5d428a9c63dbc914611036855a6c56e"

    def test_wallet_finds_existing_profile(self):
        """Wallet-only lookup should find existing profile with that wallet."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"

            # First, create a profile with handle + wallet
            ctx1 = resolve_user_context(
                handle="@DrPufferfish",
                wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=True,
            )
            assert ctx1.slug == "drpufferfish"

            # Now lookup with wallet only - should find existing profile
            ctx2 = resolve_user_context(
                handle=None,
                wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=False,
            )

            assert ctx2.slug == "drpufferfish"  # Found the existing profile!

    def test_handle_without_at_prefix(self):
        """Handle without @ should be normalized correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"

            ctx = resolve_user_context(
                handle="DrPufferfish",
                wallet=None,
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=False,
            )

            assert ctx.slug == "drpufferfish"
            assert ctx.handle == "@DrPufferfish"  # @ prefix added

    def test_no_handle_no_wallet_fallback(self):
        """With neither handle nor wallet, use wallet_unknown fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"

            ctx = resolve_user_context(
                handle=None,
                wallet=None,
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=False,
            )

            assert ctx.slug == "wallet_unknown"

    def test_handle_requires_wallet_raises_when_unresolved(self):
        """Strict handle mode must raise if wallet cannot be resolved."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"

            with pytest.raises(ValueError, match="Could not resolve wallet"):
                resolve_user_context(
                    handle="@DrPufferfish",
                    wallet=None,
                    kb_root=kb_root,
                    artifacts_root=artifacts_root,
                    persist_mapping=False,
                    require_wallet_for_handle=True,
                    wallet_lookup=lambda _handle: None,
                )

    def test_handle_strict_mode_uses_handle_slug_not_fallback(self):
        """Strict handle mode uses normalized handle slug, never unknown/wallet_*."""
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_root = Path(tmpdir) / "kb"
            artifacts_root = Path(tmpdir) / "artifacts"
            (kb_root / "users" / "drpufferfish").mkdir(parents=True, exist_ok=True)

            ctx = resolve_user_context(
                handle="@DrPufferfish",
                wallet=None,
                kb_root=kb_root,
                artifacts_root=artifacts_root,
                persist_mapping=False,
                require_wallet_for_handle=True,
                wallet_lookup=lambda _handle: "0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
            )

            assert ctx.slug == "drpufferfish"
            assert ctx.wallet == "0xdb27bf2ac5d428a9c63dbc914611036855a6c56e"
            assert "unknown" not in str(ctx.kb_user_dir)
            assert "unknown" not in str(ctx.artifacts_user_dir)
            assert not ctx.slug.startswith("wallet_")


class TestGetSlugForUser:
    """Tests for get_slug_for_user convenience function."""

    def test_handle_only(self):
        assert get_slug_for_user(handle="@DrPufferfish") == "drpufferfish"

    def test_wallet_only(self):
        result = get_slug_for_user(wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e")
        assert result in ("wallet_db27bf2a", "drpufferfish")

    def test_handle_preferred(self):
        result = get_slug_for_user(
            handle="@DrPufferfish",
            wallet="0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
        )
        assert result == "drpufferfish"
