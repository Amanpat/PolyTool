"""WI-5 approval-request emit side (pure, offline-testable).

This module is the PolyTool surface of the Vera text-bridge approval flow. It
builds the approval-request message a human operator sees in Discord, and the
parser/guards Vera (and our tests) use to interpret operator replies. It does
NOT touch ClickHouse, the lifecycle gate, or any Discord transport — those live
elsewhere. The actual approve/deny action always routes through
``discovery review --approve/--deny`` -> ``plan_review`` -> ``validate_transition``.

Dedup state is a PolyTool-side JSON file (no DDL, no new column): we record
which pending candidates have already been posted so Vera does not re-post the
same wallet on every poll cycle.

Contracts (kept stable for Vera's SKILL.md):

- ``is_full_wallet_address`` — only a single, full 42-char EVM address passes
  (no truncation, no extra tokens).
- ``parse_approval_command`` — parse ``approve <full>`` / ``deny <full>``.
- ``is_authorized_author`` — author-ID equality gate (unit-tested rule).
- ``format_approval_request`` — deterministic approval-request message body.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md ; WI-5 work packet.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

# Repo root is four parents up: packages/polymarket/discovery/<file>
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_NOTIFIED_PATH = _REPO_ROOT / "artifacts" / "watchlists" / "approvals_notified.json"

# Exactly one full EVM address: 0x followed by 40 hex chars, nothing else.
_FULL_ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")

_VALID_VERBS = {"approve", "deny"}


# ---------------------------------------------------------------------------
# Address / command parsing
# ---------------------------------------------------------------------------


def is_full_wallet_address(s: str) -> bool:
    """True only for exactly one full EVM address (``0x`` + 40 hex chars).

    Rejects truncated forms (``0xcf60…``, ``0xcf60``), wrong length, non-hex,
    empty, or anything with extra tokens/whitespace embedded.
    """
    if not isinstance(s, str):
        return False
    return bool(_FULL_ADDR_RE.match(s.strip()))


def parse_approval_command(text: str) -> Optional[tuple[str, str]]:
    """Parse a Discord reply ``approve <addr>`` / ``deny <addr>``.

    Case-insensitive verb; tolerates surrounding whitespace and a leading
    Discord mention token (e.g. ``<@123>``). Returns ``(action, address)`` ONLY
    if the command resolves to exactly one FULL wallet address (per
    ``is_full_wallet_address``); otherwise returns ``None`` (reject).

    ``action`` is normalised to lowercase ``"approve"`` / ``"deny"``. The address
    is returned verbatim (original case preserved).
    """
    if not isinstance(text, str):
        return None

    tokens = text.strip().split()
    if not tokens:
        return None

    # Tolerate a single leading mention token (e.g. "<@123456789> approve 0x..").
    if tokens and tokens[0].startswith("<@") and tokens[0].endswith(">"):
        tokens = tokens[1:]

    # Require exactly: <verb> <address> — no extra tokens (unambiguous target).
    if len(tokens) != 2:
        return None

    verb = tokens[0].lower()
    addr = tokens[1]
    if verb not in _VALID_VERBS:
        return None
    if not is_full_wallet_address(addr):
        return None
    return (verb, addr)


# ---------------------------------------------------------------------------
# Author-ID authorization gate
# ---------------------------------------------------------------------------


def is_authorized_author(
    author_id: Optional[str], allowed_operator_id: Optional[str]
) -> bool:
    """True only if both IDs are non-empty and exactly equal (string compare).

    Encodes the mandatory author-ID gate as a unit-tested rule: a command is
    honoured ONLY when it comes from the authenticated operator's Discord user
    ID. None / empty / mismatch all return False.
    """
    if not author_id or not allowed_operator_id:
        return False
    return str(author_id) == str(allowed_operator_id)


# ---------------------------------------------------------------------------
# Approval-request message formatter (deterministic)
# ---------------------------------------------------------------------------


def format_approval_request(wallet_address: str, evidence_reason: str) -> str:
    """Build the deterministic approval-request message for a pending candidate.

    Layout (stable — Vera's SKILL.md matches this shape)::

        Pending candidate: <full_address>
        Evidence: <summarize_evidence reason body>
        Reply to approve/deny:
        approve <full_address>
        deny <full_address>

    The FULL address is always rendered (never truncated) so the operator can
    reply by copy/paste and the full-address requirement is satisfiable.
    """
    full = (wallet_address or "").strip()
    reason = evidence_reason if (evidence_reason and evidence_reason.strip()) else "no evidence available"
    return (
        f"Pending candidate: {full}\n"
        f"Evidence: {reason}\n"
        f"Reply to approve/deny:\n"
        f"approve {full}\n"
        f"deny {full}"
    )


# ---------------------------------------------------------------------------
# Dedup state helpers (PolyTool-side JSON state — NO DDL)
# ---------------------------------------------------------------------------


def notified_path(path: Optional[Path] = None) -> Path:
    """Return the dedup state-file path (default ``artifacts/watchlists/approvals_notified.json``)."""
    return Path(path) if path is not None else DEFAULT_NOTIFIED_PATH


def load_notified(path: Optional[Path] = None) -> set[str]:
    """Load the set of already-notified wallets (lowercased) from the state file.

    Missing or malformed file => empty set (never raises).
    """
    p = notified_path(path)
    try:
        if not p.exists():
            return set()
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(data, dict):
        items = data.get("notified", [])
    elif isinstance(data, list):
        items = data
    else:
        return set()
    return {str(w).strip().lower() for w in items if str(w).strip()}


def mark_notified(path: Optional[Path], wallet: str) -> None:
    """Record ``wallet`` (lowercased) as notified in the JSON state file.

    Writes ONLY the JSON state file — never the DB or the lifecycle gate.
    Idempotent: re-marking an already-present wallet is a no-op write.
    """
    if not wallet or not str(wallet).strip():
        return
    p = notified_path(path)
    current = load_notified(p)
    current.add(str(wallet).strip().lower())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"notified": sorted(current)}, indent=2),
        encoding="utf-8",
    )
