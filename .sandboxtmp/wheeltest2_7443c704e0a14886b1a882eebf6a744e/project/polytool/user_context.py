"""Canonical user identity resolver for consistent path routing.

This module ensures that user identity is resolved consistently across all
CLI commands and MCP tools. The slug derived from a user handle controls
where outputs are written.

Key principles:
1. If --user handle is provided, derive slug from handle (drpufferfish)
2. Persist wallet-to-slug mapping so wallet-only calls find the same folder
3. Never use "unknown" - wallet-only with no mapping uses wallet_<first8>
4. Check for existing folders and prefer them
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)

_HANDLE_SLUG_RE = re.compile(r"[^a-z0-9_-]")


def normalize_handle(handle: Optional[str]) -> Optional[str]:
    """Normalize a user handle for slug derivation.

    Args:
        handle: User handle (e.g., "@DrPufferfish", "DrPufferfish")

    Returns:
        Normalized slug (e.g., "drpufferfish") or None if invalid
    """
    if handle is None:
        return None
    cleaned = handle.strip()
    if not cleaned or cleaned == "@":
        return None
    # Remove @ prefix
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    cleaned = cleaned.strip().lower()
    if not cleaned:
        return None
    # Replace invalid chars with underscore
    cleaned = _HANDLE_SLUG_RE.sub("_", cleaned)
    # Remove consecutive/trailing underscores
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned if cleaned else None


def wallet_to_slug(wallet: str) -> str:
    """Generate a slug from wallet address when no handle is available.

    Args:
        wallet: Wallet address (0x...)

    Returns:
        Slug in format "wallet_<first8>" (never "unknown")
    """
    if not wallet:
        return "wallet_unknown"
    # Take first 8 chars after 0x
    prefix = wallet.lower()
    if prefix.startswith("0x"):
        prefix = prefix[2:10]
    else:
        prefix = prefix[:8]
    return f"wallet_{prefix}"


@dataclass
class UserContext:
    """Resolved user identity with consistent paths."""

    slug: str
    handle: Optional[str]  # Original handle with @ (e.g., "@DrPufferfish")
    wallet: Optional[str]  # Proxy wallet address

    # Derived paths
    kb_root: Path = field(default_factory=lambda: Path("kb"))
    artifacts_root: Path = field(default_factory=lambda: Path("artifacts"))

    @property
    def kb_user_dir(self) -> Path:
        """User's KB directory: kb/users/<slug>/"""
        return self.kb_root / "users" / self.slug

    @property
    def artifacts_user_dir(self) -> Path:
        """User's artifacts directory: artifacts/dossiers/users/<slug>/"""
        return self.artifacts_root / "dossiers" / "users" / self.slug

    @property
    def llm_bundles_dir(self) -> Path:
        """LLM bundles directory: kb/users/<slug>/llm_bundles/"""
        return self.kb_user_dir / "llm_bundles"

    @property
    def llm_reports_dir(self) -> Path:
        """LLM reports directory: kb/users/<slug>/llm_reports/"""
        return self.kb_user_dir / "llm_reports"

    @property
    def llm_notes_dir(self) -> Path:
        """LLM notes directory: kb/users/<slug>/notes/LLM_notes/"""
        return self.kb_user_dir / "notes" / "LLM_notes"

    @property
    def profile_path(self) -> Path:
        """User profile path: kb/users/<slug>/profile.json"""
        return self.kb_user_dir / "profile.json"

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for logging/serialization."""
        return {
            "slug": self.slug,
            "handle": self.handle or "",
            "wallet": self.wallet or "",
            "kb_user_dir": str(self.kb_user_dir),
            "artifacts_user_dir": str(self.artifacts_user_dir),
        }


def _load_profile(profile_path: Path) -> Optional[Dict]:
    """Load user profile from disk."""
    if not profile_path.exists():
        return None
    try:
        return json.loads(profile_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not load profile {profile_path}: {e}")
        return None


def _lookup_wallet_via_gamma(handle: str) -> Optional[str]:
    """Resolve a wallet for a handle via Gamma."""
    try:
        from polymarket.gamma import GammaClient
    except ImportError:
        logger.debug("GammaClient unavailable for wallet lookup.")
        return None

    try:
        profile = GammaClient().resolve(handle)
    except Exception as exc:
        logger.debug("Wallet lookup failed for %s: %s", handle, exc)
        return None

    if profile and profile.proxy_wallet:
        return profile.proxy_wallet
    return None


def _save_profile(profile_path: Path, handle: Optional[str], wallet: Optional[str]) -> None:
    """Save user profile to disk."""
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "handle": handle or "",
        "wallet": wallet or "",
    }
    profile_path.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    logger.debug(f"Saved profile to {profile_path}")


def _find_existing_slug_for_wallet(
    wallet: str,
    kb_root: Path,
    artifacts_root: Path,
) -> Optional[str]:
    """Find existing slug for a wallet by checking profile.json files."""
    if not wallet:
        return None

    wallet_lower = wallet.lower()

    # Check kb/users/*/profile.json
    kb_users = kb_root / "users"
    if kb_users.exists():
        for user_dir in kb_users.iterdir():
            if not user_dir.is_dir():
                continue
            profile_path = user_dir / "profile.json"
            profile = _load_profile(profile_path)
            if profile and profile.get("wallet", "").lower() == wallet_lower:
                return user_dir.name

    return None


def _load_wallet_for_slug(slug: str, kb_root: Path) -> Optional[str]:
    """Load a persisted wallet from kb/users/<slug>/profile.json if present."""
    if not slug:
        return None
    profile = _load_profile(kb_root / "users" / slug / "profile.json")
    if not profile:
        return None
    wallet = str(profile.get("wallet", "")).strip()
    return wallet or None


def resolve_user_context(
    handle: Optional[str] = None,
    wallet: Optional[str] = None,
    kb_root: Path = Path("kb"),
    artifacts_root: Path = Path("artifacts"),
    persist_mapping: bool = True,
    require_wallet_for_handle: bool = False,
    wallet_lookup: Optional[Callable[[str], Optional[str]]] = None,
) -> UserContext:
    """Resolve user identity to a consistent UserContext.

    Priority for slug derivation:
    1. If handle provided: derive slug from handle
    2. If wallet provided and profile exists: use slug from profile
    3. If wallet provided and no profile: use wallet_<first8>

    Args:
        handle: User handle (e.g., "@DrPufferfish")
        wallet: Proxy wallet address
        kb_root: Root of KB directory (default: kb/)
        artifacts_root: Root of artifacts directory (default: artifacts/)
        persist_mapping: Whether to save wallet-to-slug mapping
        require_wallet_for_handle:
            If True and handle is provided, raise ValueError when wallet cannot be resolved.
        wallet_lookup:
            Optional callback used to resolve wallet for handle. If omitted and
            require_wallet_for_handle=True, falls back to Gamma lookup.

    Returns:
        UserContext with resolved slug and paths
    """
    slug: Optional[str] = None
    resolved_wallet = wallet.strip() if wallet else None

    # Priority 1: Handle provided - derive slug from handle.
    normalized_handle = None
    if handle:
        raw_handle = handle.strip()
        if raw_handle and raw_handle != "@":
            normalized_handle = raw_handle if raw_handle.startswith("@") else f"@{raw_handle}"
        slug = normalize_handle(raw_handle)
        if slug:
            logger.debug("Derived slug '%s' from handle '%s'", slug, handle)

            # If wallet wasn't supplied, first try persisted profile for this slug.
            if not resolved_wallet:
                resolved_wallet = _load_wallet_for_slug(slug, kb_root)
                if resolved_wallet:
                    logger.debug("Loaded persisted wallet for slug '%s'", slug)

            # If strict user-mode is enabled and wallet is still missing, attempt lookup.
            if not resolved_wallet and require_wallet_for_handle:
                lookup = wallet_lookup or _lookup_wallet_via_gamma
                resolved_wallet = lookup(normalized_handle or handle)

            if require_wallet_for_handle and not resolved_wallet:
                display_handle = normalized_handle or handle
                raise ValueError(
                    f"Could not resolve wallet for user '{display_handle}'. "
                    "Use a valid --user handle that resolves to a proxy wallet, "
                    "or use --wallet for wallet-first mode."
                )

    # Priority 2: Check for existing mapping via wallet
    if not slug and resolved_wallet:
        existing_slug = _find_existing_slug_for_wallet(resolved_wallet, kb_root, artifacts_root)
        if existing_slug:
            slug = existing_slug
            logger.debug("Found existing slug '%s' for wallet %s...", slug, resolved_wallet[:10])

    # Priority 3: Generate wallet-based slug
    if not slug:
        if resolved_wallet:
            slug = wallet_to_slug(resolved_wallet)
            logger.debug("Generated wallet-based slug '%s' for %s...", slug, resolved_wallet[:10])
        else:
            # Absolute fallback - should never happen in normal use
            slug = "wallet_unknown"
            logger.warning("No handle or wallet provided, using 'wallet_unknown'")

    ctx = UserContext(
        slug=slug,
        handle=normalized_handle,
        wallet=resolved_wallet,
        kb_root=kb_root,
        artifacts_root=artifacts_root,
    )

    # Persist mapping if wallet is known
    if persist_mapping and resolved_wallet and slug:
        try:
            _save_profile(ctx.profile_path, ctx.handle, resolved_wallet)
        except OSError as e:
            logger.warning(f"Could not persist user profile: {e}")

    return ctx


def get_slug_for_user(
    handle: Optional[str] = None,
    wallet: Optional[str] = None,
) -> str:
    """Convenience function to get just the slug.

    Use resolve_user_context() when you need full path information.
    """
    ctx = resolve_user_context(handle=handle, wallet=wallet, persist_mapping=False)
    return ctx.slug
