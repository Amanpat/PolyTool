"""DR-3: read-only status assembler for the Vera ``/status`` slash command.

This module is the data layer behind ``/status``. It is deliberately split from
the Discord handler (in :mod:`packages.polymarket.discord_bot.bot`) so the
assembly + embed building can be unit-tested with NO Discord and NO ClickHouse —
the single ClickHouse touch point is one injectable ``query`` callable.

READ-ONLY CONTRACT (enforced by construction):
- Every SQL string this module builds is a ``SELECT``. There is no INSERT,
  ALTER, no lifecycle mutation, no subprocess, no writer import. The only DB
  interface is :func:`_ch_select` (HTTP GET, ``FORMAT JSONEachRow``), the same
  read pattern used by ``clickhouse_writer._get_query``. The Top-N block reads
  one ``leaderboard.json`` artifact (a plain file read). Nothing here can write.

Data sources (all existing — no new tables):
- ``polytool.scan_queue``    — in-queue / failed counts (queue_state).
- ``polytool.watchlist``     — scanned-today / pending-review counts.
- ``artifacts/research/wallet_scan/<date>/<run>/leaderboard.json`` — the Top-N
  leaderboard (lifetime realized PnL, positions, username, ranking). This is the
  SAME artifact ``wallet-scan`` emits, so the card's ordering and PnL match it
  exactly. The previous ``user_pnl_bucket`` source reported only the latest day
  bucket (≈0 — a windowed orderbook estimate, NOT the resolved lifetime PnL the
  leaderboard ranks on), and ``leaderboard_snapshots`` is never written by the
  ``wallet-scan --input`` path, so usernames came back blank. See dev log
  ``docs/dev_logs/2026-06-04_status-accuracy-fix.md``.

Best-effort everywhere: any datum that cannot be read is omitted gracefully
(``None``) and the embed renders an em-dash, never a fabricated value. A failing
sub-query or a missing leaderboard NEVER raises out of :func:`assemble_status` —
it degrades that tile. The Username column falls back to a truncated wallet ID
(via :func:`polytool.user_context.display_name`) so it is never blank.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from polytool.user_context import display_name

logger = logging.getLogger("vera.status")

# A query runner maps a SELECT string -> list of row dicts (or None on failure).
# Injectable so tests never touch a real ClickHouse.
QueryRunner = Callable[[str], Optional[list[dict]]]

_ABSENT = "—"  # em-dash — honest omission marker (matches pending_notify)
_TOPN_DEFAULT = 10
_COLOR_INFO = 0x3498DB  # blue, matches the pending-review card eyebrow


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TopWallet:
    """One row of the realized-PnL leaderboard.

    ``wallet_address`` and ``username`` are SEPARATE fields by design so the card
    can render them as distinct columns (DR-3 requirement).
    """

    wallet_address: str
    username: Optional[str]
    realized_pnl: Optional[float]
    open_positions: Optional[int]
    daily_pnl: Optional[float] = None


@dataclass
class StatusSnapshot:
    """Everything the ``/status`` card needs. All fields best-effort / optional."""

    generated_at: datetime
    in_queue: Optional[int] = None
    scanned_today: Optional[int] = None
    pending_review: Optional[int] = None
    failed: Optional[int] = None
    top_wallets: list[TopWallet] = field(default_factory=list)
    # Health / footer datums — omitted (None) when not cheaply queryable.
    last_drain_at: Optional[datetime] = None
    ris_docs_today: Optional[int] = None
    # Notes about omitted/degraded datums (operator-facing, surfaced in footer).
    degraded: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# ClickHouse SELECT runner (read-only)
# ---------------------------------------------------------------------------


def _ch_select(
    sql: str, *, host: str, port: int, user: str, password: str
) -> Optional[list[dict]]:
    """Run a single SELECT via ClickHouse HTTP GET. Returns rows or None on error.

    Read-only by construction: HTTP GET + ``FORMAT JSONEachRow``. Mirrors the
    ``clickhouse_writer._get_query`` pattern. Never logs the password.
    """
    try:
        full_sql = sql + " FORMAT JSONEachRow"
        url = f"http://{host}:{port}/?query={urllib.parse.quote(full_sql)}"
        credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Basic {credentials}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except Exception:
        logger.exception("status: ClickHouse SELECT failed (read-only path).")
        return None

    rows: list[dict] = []
    for line in (raw or "").strip().splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except Exception:
            continue
        if isinstance(d, dict):
            rows.append(d)
    return rows


def make_query_runner(
    *, host: str, port: int, user: str, password: str
) -> QueryRunner:
    """Bind a :data:`QueryRunner` to one ClickHouse connection (read-only)."""

    def _run(sql: str) -> Optional[list[dict]]:
        return _ch_select(sql, host=host, port=port, user=user, password=password)

    return _run


# ---------------------------------------------------------------------------
# Read-only SELECTs (each returns a scalar/list, None on failure)
# ---------------------------------------------------------------------------


def _scalar(rows: Optional[list[dict]], key: str) -> Optional[int]:
    if not rows:
        return None
    try:
        return int(rows[0].get(key))
    except (TypeError, ValueError):
        return None


def _count_queue_states(query: QueryRunner) -> tuple[Optional[int], Optional[int]]:
    """Return ``(in_queue, failed)`` from the latest scan_queue state per item.

    in_queue = items whose current state is pending or leased (work not done).
    failed   = items whose current state is failed.
    Uses FINAL so the ReplacingMergeTree collapses to the latest version per
    dedup_key before we bucket by queue_state.
    """
    sql = (
        "SELECT queue_state, count() AS c FROM polytool.scan_queue FINAL "
        "GROUP BY queue_state"
    )
    rows = query(sql)
    if rows is None:
        return None, None
    in_queue = 0
    failed = 0
    for r in rows:
        state = str(r.get("queue_state") or "")
        try:
            c = int(r.get("c") or 0)
        except (TypeError, ValueError):
            c = 0
        if state in ("pending", "leased"):
            in_queue += c
        elif state == "failed":
            failed += c
    return in_queue, failed


def _count_pending_review(query: QueryRunner) -> Optional[int]:
    """Candidate-tier wallets awaiting the human gate (same filter as the reader)."""
    sql = (
        "SELECT count() AS c FROM polytool.watchlist FINAL "
        "WHERE tier = 'candidate' AND review_status = 'pending' "
        "AND locked = 0 AND lifecycle_state = 'scanned'"
    )
    rows = query(sql)
    if rows is None:
        # Pre-migration fallback (tier/locked columns absent).
        rows = query(
            "SELECT count() AS c FROM polytool.watchlist FINAL "
            "WHERE review_status = 'pending' AND lifecycle_state = 'scanned'"
        )
    return _scalar(rows, "c")


def _count_scanned_today(query: QueryRunner) -> Optional[int]:
    """Wallets whose latest watchlist row was scanned today (UTC).

    Counts distinct wallets in lifecycle_state='scanned' whose last_scanned_at
    falls on the current UTC date.
    """
    sql = (
        "SELECT count() AS c FROM polytool.watchlist FINAL "
        "WHERE lifecycle_state = 'scanned' AND last_scanned_at IS NOT NULL "
        "AND toDate(last_scanned_at) = today()"
    )
    return _scalar(query(sql), "c")


def _last_drain_at(query: QueryRunner) -> Optional[datetime]:
    """Most recent updated_at among done/failed/leased queue items (a drain proxy)."""
    sql = (
        "SELECT max(updated_at) AS t FROM polytool.scan_queue FINAL "
        "WHERE queue_state IN ('done', 'failed', 'leased')"
    )
    rows = query(sql)
    if not rows:
        return None
    raw = rows[0].get("t")
    return _parse_ch_dt(raw)


def _ris_docs_today(query: QueryRunner) -> Optional[int]:
    """Best-effort: RIS source documents added today, if a ClickHouse mirror exists.

    The canonical RIS store is SQLite (KnowledgeStore); there is no guaranteed
    cheap ClickHouse count, so this is a best-effort probe that returns None when
    the table is absent. Omitted gracefully per the packet ("omit if not cheaply
    available").
    """
    exists_rows = query(
        "SELECT count() AS c FROM system.tables "
        "WHERE database = 'polytool' AND name = 'ris_documents'"
    )
    if _scalar(exists_rows, "c") != 1:
        return None

    sql = (
        "SELECT count() AS c FROM polytool.ris_documents "
        "WHERE toDate(created_at) = today()"
    )
    rows = query(sql)
    if rows is None:
        return None
    return _scalar(rows, "c")


def _daily_pnl_by_wallet(
    query: QueryRunner, wallet_addresses: list[str]
) -> Optional[dict[str, float]]:
    """Today's realized PnL by wallet, keyed on lowercased wallet address.

    This augments the leaderboard rows only. It does not sort or replace the
    lifetime net PnL from leaderboard.json.
    """
    keys = sorted(
        {str(w or "").strip().lower() for w in wallet_addresses if str(w or "").strip()}
    )
    if not keys:
        return {}

    wallets_sql = ", ".join(_sql_literal(k) for k in keys)
    sql = (
        "SELECT lower(proxy_wallet) AS wallet, "
        "argMax(realized_pnl, computed_at) AS daily_pnl "
        "FROM polytool.user_pnl_bucket "
        "WHERE bucket_type = 'day' "
        "AND toDate(bucket_start) = today() "
        f"AND lower(proxy_wallet) IN ({wallets_sql}) "
        "GROUP BY wallet"
    )
    rows = query(sql)
    if rows is None:
        return None

    out: dict[str, float] = {}
    for row in rows:
        wallet = str(row.get("wallet") or "").strip().lower()
        pnl = _as_float(row.get("daily_pnl"))
        if wallet and pnl is not None:
            out[wallet] = pnl
    return out


def _attach_daily_pnl(
    query: QueryRunner, top_wallets: list[TopWallet]
) -> Optional[list[TopWallet]]:
    daily = _daily_pnl_by_wallet(query, [w.wallet_address for w in top_wallets])
    if daily is None:
        return None
    return [
        TopWallet(
            wallet_address=w.wallet_address,
            username=w.username,
            realized_pnl=w.realized_pnl,
            open_positions=w.open_positions,
            daily_pnl=daily.get(w.wallet_address.lower()),
        )
        for w in top_wallets
    ]


# A leaderboard loader maps ``top_n`` -> the ranked Top-N (or None on failure).
# Injectable so tests never touch the filesystem.
LeaderboardLoader = Callable[[int], Optional[list["TopWallet"]]]

# wallet-scan writes ``<root>/research/wallet_scan/<YYYY-MM-DD>/<run_id>/leaderboard.json``.
_LEADERBOARD_GLOB = "research/wallet_scan/*/*/leaderboard.json"


def _artifacts_root() -> Path:
    """Artifacts root. Defaults to ``artifacts`` (CWD-relative; the vera-bot
    container's WORKDIR is ``/app`` and mounts ``./artifacts:/app/artifacts:ro``).
    Override with ``POLYTOOL_ARTIFACTS_ROOT`` for non-standard layouts."""
    return Path(os.environ.get("POLYTOOL_ARTIFACTS_ROOT", "artifacts"))


def _find_latest_leaderboard(artifacts_root: Path) -> Optional[Path]:
    """Newest ``leaderboard.json`` under the wallet_scan tree, by mtime."""
    candidates = list(artifacts_root.glob(_LEADERBOARD_GLOB))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_top_wallets_from_leaderboard(
    top_n: int, *, artifacts_root: Optional[Path] = None
) -> Optional[list[TopWallet]]:
    """Top-N wallets from the latest ``leaderboard.json`` artifact (read-only).

    This is the SAME artifact ``wallet-scan`` emits, so the card's ranking and
    realized PnL match it exactly. ``realized_net_pnl`` is the lifetime resolved
    PnL the leaderboard ranks on (NOT the ≈0 latest-day ``user_pnl_bucket``
    estimate the old query read). ``username`` is kept raw and SEPARATE from the
    wallet ID; the embed applies :func:`display_name` so a blank/auto-generated
    handle renders a truncated wallet ID, never an empty cell.

    Returns ``None`` (degraded "topN") when no leaderboard is found or it cannot
    be read/parsed — never raises.
    """
    root = artifacts_root or _artifacts_root()
    try:
        path = _find_latest_leaderboard(root)
        if path is None:
            logger.warning("status: no leaderboard.json under %s/%s", root, _LEADERBOARD_GLOB)
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("status: failed reading leaderboard.json (read-only path).")
        return None

    ranked = data.get("ranked") if isinstance(data, dict) else None
    if not isinstance(ranked, list):
        return None

    safe_n = max(1, int(top_n))
    out: list[TopWallet] = []
    for entry in ranked[:safe_n]:
        if not isinstance(entry, dict):
            continue
        wallet = str(entry.get("identifier") or entry.get("wallet_id") or "")
        if not wallet:
            continue
        username = entry.get("username")
        username = str(username).strip() if username else None
        out.append(
            TopWallet(
                wallet_address=wallet,
                username=username or None,
                realized_pnl=_as_float(entry.get("realized_net_pnl")),
                open_positions=_as_int(entry.get("positions_total")),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def assemble_status(
    query: QueryRunner,
    *,
    top_n: int = _TOPN_DEFAULT,
    now: Optional[datetime] = None,
    leaderboard_loader: Optional[LeaderboardLoader] = None,
) -> StatusSnapshot:
    """Assemble a :class:`StatusSnapshot` from the read-only readers.

    Pure orchestration: every sub-reader is best-effort and degrades to None on
    failure (the reader logs and returns None; we record a degraded note). This
    function NEVER raises and NEVER writes. ``leaderboard_loader`` is injectable
    (default :func:`load_top_wallets_from_leaderboard`) so tests never touch the
    filesystem.
    """
    snap = StatusSnapshot(generated_at=now or datetime.now(timezone.utc))

    in_queue, failed = _count_queue_states(query)
    snap.in_queue = in_queue
    snap.failed = failed
    if in_queue is None:
        snap.degraded.append("queue")

    snap.pending_review = _count_pending_review(query)
    if snap.pending_review is None:
        snap.degraded.append("pending")

    snap.scanned_today = _count_scanned_today(query)
    if snap.scanned_today is None:
        snap.degraded.append("scanned")

    snap.last_drain_at = _last_drain_at(query)
    snap.ris_docs_today = _ris_docs_today(query)

    loader = leaderboard_loader or load_top_wallets_from_leaderboard
    tops = loader(top_n)
    if tops is None:
        snap.degraded.append("topN")
    else:
        tops_with_daily = _attach_daily_pnl(query, tops)
        if tops_with_daily is None:
            snap.degraded.append("dailyPnL")
            snap.top_wallets = tops
        else:
            snap.top_wallets = tops_with_daily

    return snap


# ---------------------------------------------------------------------------
# Embed builder (pure — returns a discord.Embed-compatible dict)
# ---------------------------------------------------------------------------


def build_status_embed(snap: StatusSnapshot) -> dict:
    """Build the ``/status`` embed as a ``discord.Embed.from_dict`` payload.

    Layout:
      * title + timestamp; health line (last drain + degraded notes);
      * four metric tiles (in-queue / scanned today / pending review / failed);
      * a full-width Top-N block with wallet ID and username as SEPARATE columns,
        plus daily PnL, lifetime net PnL, and open positions;
      * footer: throughput (scans/hr proxy) + RIS docs today (best-effort).
    """
    now = snap.generated_at

    # Health line.
    if snap.last_drain_at is not None:
        drain = _relative_age(snap.last_drain_at, now) or _ABSENT
    else:
        drain = _ABSENT
    health = f"Last drain: {drain}"
    if snap.degraded:
        health += f"  ·  degraded: {', '.join(snap.degraded)}"

    fields = [
        {"name": "Health", "value": health, "inline": False},
        {"name": "In queue", "value": _tile(snap.in_queue), "inline": True},
        {"name": "Scanned today", "value": _tile(snap.scanned_today), "inline": True},
        {"name": "Pending review", "value": _tile(snap.pending_review), "inline": True},
        {"name": "Failed", "value": _tile(snap.failed), "inline": True},
    ]

    # Top-N leaderboard. Wallet ID and username are rendered as SEPARATE columns
    # using aligned inline fields (Discord's closest primitive to columns).
    if snap.top_wallets:
        ids, names, daily_pnls, net_pnls = [], [], [], []
        for w in snap.top_wallets:
            ids.append(f"`{_short_addr(w.wallet_address)}`")
            # display_name() returns the real handle when present, else a
            # truncated wallet ID — never blank, never an auto-generated handle.
            names.append(display_name(w.username, w.wallet_address))
            daily_pnls.append(
                _fmt_pnl(w.daily_pnl) if w.daily_pnl is not None else _ABSENT
            )
            pnl = _fmt_pnl(w.realized_pnl) if w.realized_pnl is not None else _ABSENT
            pos = "" if w.open_positions is None else f" · {w.open_positions} pos"
            net_pnls.append(f"{pnl}{pos}")
        fields.append(
            {"name": "Top by realized PnL", "value": "Wallet -> username -> daily PnL -> net PnL",
             "inline": False}
        )
        fields.append({"name": "Wallet ID", "value": "\n".join(ids), "inline": True})
        fields.append({"name": "Username", "value": "\n".join(names), "inline": True})
        fields.append({"name": "Daily PnL", "value": "\n".join(daily_pnls), "inline": True})
        fields.append({"name": "Net PnL", "value": "\n".join(net_pnls), "inline": True})
    else:
        fields.append(
            {"name": "Top by realized PnL", "value": _ABSENT, "inline": False}
        )

    footer = "Vera /status (read-only)"
    ris = "" if snap.ris_docs_today is None else f"  ·  RIS docs today: {snap.ris_docs_today}"
    footer += ris

    return {
        "author": {"name": "Scan status"},
        "title": "Wallet-discovery status",
        "color": _COLOR_INFO,
        "fields": fields,
        "footer": {"text": footer},
        "timestamp": _iso(now),
    }


# ---------------------------------------------------------------------------
# Small pure helpers (no Discord, no I/O)
# ---------------------------------------------------------------------------


def _tile(value: Optional[int]) -> str:
    return _ABSENT if value is None else f"**{value}**"


def _fmt_pnl(value: float) -> str:
    """Signed, compact USDC magnitude (mirrors evidence_summary._fmt_pnl)."""
    sign = "+" if value >= 0 else "-"
    mag = abs(value)
    if mag >= 1_000_000:
        return f"{sign}${mag / 1_000_000:.1f}m"
    if mag >= 1_000:
        return f"{sign}${mag / 1_000:.1f}k"
    return f"{sign}${mag:.0f}"


def _short_addr(addr: str) -> str:
    a = (addr or "").strip()
    if len(a) <= 13:
        return a
    return f"{a[:6]}…{a[-4:]}"


def _as_float(v: object) -> Optional[float]:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_int(v: object) -> Optional[int]:
    try:
        return int(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _parse_ch_dt(raw: object) -> Optional[datetime]:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s or s.startswith("1970-01-01") or s.startswith("0000-00-00"):
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _relative_age(then: datetime, now: datetime) -> Optional[str]:
    if then is None:
        return None
    delta = now - then
    secs = int(delta.total_seconds())
    if secs < 0:
        return "just now"
    if secs < 90:
        return f"{secs}s ago"
    mins = secs // 60
    if mins < 90:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 36:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def read_status_snapshot(
    *,
    host: str,
    port: int,
    user: str,
    top_n: int = _TOPN_DEFAULT,
) -> Optional[StatusSnapshot]:
    """Bind to ClickHouse from the environment and assemble a snapshot.

    Reads ``CLICKHOUSE_PASSWORD`` from the environment (fail-fast: returns None
    when unset, never a hardcoded fallback). READ-ONLY end to end. Returns None
    only when the password is absent — a reachable-but-failing ClickHouse still
    returns a (degraded) snapshot so the operator sees what IS available.
    """
    password = os.environ.get("CLICKHOUSE_PASSWORD", "").strip()
    if not password:
        logger.warning("/status: CLICKHOUSE_PASSWORD is not set; cannot read.")
        return None
    runner = make_query_runner(host=host, port=port, user=user, password=password)
    return assemble_status(runner, top_n=top_n)
