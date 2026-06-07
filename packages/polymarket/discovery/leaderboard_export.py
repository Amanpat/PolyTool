"""Leaderboard export helper (DR-2 Batch-Seed Top-200 Corpus).

Read-only: materialize the current top-N leaderboard wallet addresses as a
``wallet-scan --input`` file (one ``0x...`` address per line). REUSES
``packages.polymarket.discovery.leaderboard_fetcher.fetch_leaderboard`` — this
module adds NO new leaderboard fetch or ranking logic; it only:

  * maps a ``--top N`` count onto the existing page-based fetch (max_pages),
  * applies the shared, config-driven bulk pacing between pages (default OFF),
  * dedups + writes the addresses in the exact format ``wallet-scan`` expects.

The output format is verified against ``tools/cli/wallet_scan.py:parse_input_file``
(one identifier per line; ``#`` comments and blank lines ignored; ``0x`` ⇒ wallet).

SPEC: docs/obsidian-vault/claude-memory/work-packets/work-packet-dr-2-batch-seed-top200.md
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable, Optional

from packages.polymarket.discovery.bulk_pacing import BulkPacer, load_bulk_pacing
from packages.polymarket.discovery.leaderboard_fetcher import fetch_leaderboard

# Match the fetcher's API default; top=200 ⇒ 4 pages.
_DEFAULT_PAGE_SIZE = 50


def export_leaderboard_entries(
    top: int = 200,
    *,
    order_by: str = "PNL",
    time_period: str = "DAY",
    category: str = "OVERALL",
    page_size: int = _DEFAULT_PAGE_SIZE,
    http_client=None,
    pacer: Optional[BulkPacer] = None,
    fetch_fn: Callable[..., list[dict]] = fetch_leaderboard,
) -> list[dict]:
    """Fetch the top-N leaderboard and return deduped ``{wallet, username}`` entries.

    Identical fetch/ranking/dedup logic to :func:`export_leaderboard_addresses`
    (which now wraps this), but ALSO carries the leaderboard ``userName`` so the
    export -> wallet-scan handoff can preserve human display names. ``wallet`` is
    the canonical key; ``username`` is display-only and may be empty.

    Returns:
        Ordered, deduplicated list of ``{"wallet": str, "username": str}`` dicts
        (rank-ascending), truncated to ``top``. Entries with an empty
        proxy_wallet are skipped.
    """
    if top <= 0:
        return []
    max_pages = max(1, math.ceil(top / max(1, page_size)))

    kwargs = dict(
        order_by=order_by,
        time_period=time_period,
        category=category,
        max_pages=max_pages,
        page_size=page_size,
        http_client=http_client,
    )
    # Only forward `pacer` when the fetcher accepts it (real fetch_leaderboard
    # does as of DR-2). This keeps a plain mocked fetch_fn working in tests.
    try:
        raw = fetch_fn(pacer=pacer, **kwargs)
    except TypeError:
        raw = fetch_fn(**kwargs)

    entries: list[dict] = []
    seen: set[str] = set()
    for entry in raw:
        # The data API returns the address under camelCase `proxyWallet`; older
        # code/tests used snake_case `proxy_wallet`. Read camelCase first and fall
        # back to snake_case so both the live API and existing fixtures work.
        wallet = str(
            entry.get("proxyWallet") or entry.get("proxy_wallet", "") or ""
        ).strip()
        if not wallet:
            continue
        key = wallet.lower()
        if key in seen:
            continue
        seen.add(key)
        # userName (camelCase, live API) -> name/username (snake fixtures).
        # Display-only; empty is fine (most wallets are pseudonymous).
        username = str(
            entry.get("userName")
            or entry.get("name")
            or entry.get("username", "")
            or ""
        ).strip()
        entries.append({"wallet": wallet, "username": username})
        if len(entries) >= top:
            break
    return entries


def export_leaderboard_addresses(
    top: int = 200,
    *,
    order_by: str = "PNL",
    time_period: str = "DAY",
    category: str = "OVERALL",
    page_size: int = _DEFAULT_PAGE_SIZE,
    http_client=None,
    pacer: Optional[BulkPacer] = None,
    fetch_fn: Callable[..., list[dict]] = fetch_leaderboard,
) -> list[str]:
    """Fetch the top-N leaderboard and return deduped proxy_wallet addresses.

    Thin wrapper over :func:`export_leaderboard_entries` (unchanged public
    behaviour) for callers/tests that only want the addresses.

    Returns:
        Ordered, deduplicated list of ``proxy_wallet`` strings (rank-ascending),
        truncated to ``top``. Entries with an empty proxy_wallet are skipped.
    """
    return [
        e["wallet"]
        for e in export_leaderboard_entries(
            top,
            order_by=order_by,
            time_period=time_period,
            category=category,
            page_size=page_size,
            http_client=http_client,
            pacer=pacer,
            fetch_fn=fetch_fn,
        )
    ]


def write_input_file(addresses: list[str], out_path: Path, *, header: bool = True) -> int:
    """Write addresses to a ``wallet-scan --input`` file (one per line).

    Args:
        addresses: proxy_wallet strings to write.
        out_path: destination path (parent dirs created as needed).
        header: prepend a ``#``-comment provenance header (ignored by the
            wallet-scan parser, which skips ``#`` lines).

    Returns:
        Number of address lines written.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if header:
        lines.append("# Top-N leaderboard export for `wallet-scan --input` (DR-2 batch-seed).")
        lines.append("# One proxy_wallet address per line; `#` lines and blanks are ignored.")
        lines.append(f"# count={len(addresses)}")
    lines.extend(addresses)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(addresses)


def username_sidecar_path(input_path: Path) -> Path:
    """Return the username-sidecar path for a ``wallet-scan --input`` file.

    Convention: ``<input>.usernames.json`` (sits next to the input file). The
    input file itself stays bare addresses (one per line) so a plain
    bare-address file remains 100% backward-compatible — the sidecar is purely
    additive and ignored when absent.
    """
    p = Path(input_path)
    return p.with_name(p.name + ".usernames.json")


def write_username_sidecar(entries: list[dict], out_path: Path) -> int:
    """Write an ``address -> username`` sidecar map next to ``out_path``.

    Args:
        entries: ``{"wallet": str, "username": str}`` dicts (from
            :func:`export_leaderboard_entries`).
        out_path: the ``wallet-scan --input`` file path; the sidecar is written
            at :func:`username_sidecar_path`.

    Only entries with a NON-EMPTY username are written (keyed by lowercased
    wallet). Returns the number of username mappings written. When no entry has
    a username, no sidecar is written and 0 is returned.
    """
    mapping = {
        str(e.get("wallet", "")).strip().lower(): str(e.get("username", "")).strip()
        for e in entries
        if str(e.get("wallet", "")).strip() and str(e.get("username", "")).strip()
    }
    if not mapping:
        return 0
    sidecar = username_sidecar_path(out_path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(mapping, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return len(mapping)


def export_to_file(
    top: int,
    out_path: Path,
    *,
    order_by: str = "PNL",
    time_period: str = "DAY",
    category: str = "OVERALL",
    page_size: int = _DEFAULT_PAGE_SIZE,
    http_client=None,
    pacer: Optional[BulkPacer] = None,
    config_path: Optional[Path] = None,
    fetch_fn: Callable[..., list[dict]] = fetch_leaderboard,
) -> dict:
    """Fetch top-N entries and write the input file + username sidecar.

    The input file stays bare addresses (one per line). A companion
    ``<out>.usernames.json`` sidecar carries display usernames so wallet-scan
    can preserve them. When ``pacer`` is None, a BulkPacer is loaded from config
    (default OFF, so a normal export does not sleep). Returns a summary dict.
    """
    if pacer is None:
        pacer = load_bulk_pacing(config_path)
    entries = export_leaderboard_entries(
        top,
        order_by=order_by,
        time_period=time_period,
        category=category,
        page_size=page_size,
        http_client=http_client,
        pacer=pacer,
        fetch_fn=fetch_fn,
    )
    addresses = [e["wallet"] for e in entries]
    written = write_input_file(addresses, out_path)
    usernames_written = write_username_sidecar(entries, out_path)
    return {
        "requested": top,
        "written": written,
        "usernames_written": usernames_written,
        "out_path": Path(out_path).as_posix(),
        "username_sidecar_path": (
            username_sidecar_path(out_path).as_posix() if usernames_written else None
        ),
        "pacing_enabled": bool(pacer and pacer.enabled),
    }
