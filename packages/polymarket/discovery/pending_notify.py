"""Wallet-ingestion pending-candidate notifications + display-time evidence.

This is the post-v1 follow-up to WI-5 (Vera two-way approval is descoped). The
operator workflow is now: NOTIFICATIONS via the existing outbound Discord
webhook, APPROVALS via the CLI gate (``discovery review --approve/--deny``).

Two responsibilities, both kept deliberately I/O-injectable so they test
offline:

1. ``compute_row_evidence(row, ...)`` -- DISPLAY-TIME evidence. Given a watchlist
   row, locate the wallet's scan data and run :func:`summarize_evidence` over the
   *fresh* metrics, instead of trusting the ``reason`` column. This holds
   regardless of which code path advanced the row: the WI-1 worker advancer
   stores a generic reason ("scan-worker drained scan_queue ...") while the WI-4
   candidate-population path stores the real summary -- recomputing at display
   time normalises both. Falls back to the stored ``reason`` (then
   "no evidence available") when no scan data is locatable.

2. ``notify_pending_candidate`` / ``notify_pending_candidates`` -- post a Discord
   EMBED CARD when a candidate enters ``review_status='pending'``. The embed
   carries the FULL wallet address and the visual fields (PnL, win rate, trades,
   CLV, open/resolved split, humanized discovery source, category when present);
   the message CONTENT carries the approve/deny CLI commands as a fenced
   copy-block (Discord's reliable one-tap copy lives on content code blocks, not
   inside embeds). A notify pass with >1 unnotified candidate sends ONE digest
   message instead of N cards. Deduped through the WI-5 ``approvals_notified.json``
   state file so a candidate is notified exactly once (no re-notify on re-scans).
   The post NEVER raises -- a webhook failure is logged and swallowed so it can
   never fail or block the ingestion pipeline.

   Buttons (one-tap approve/deny) are intentionally NOT built: webhooks can send
   embeds but cannot RECEIVE component interactions, and the Vera/Hermes gateway
   cannot receive them either. Real interactive buttons are deferred to future
   Vera/Discord work; the copy-block + CLI gate is the v1 affordance.

This module DOES touch the Discord transport (via a lazily-imported, injectable
``post`` callable); the pure WI-5 ``approval_request`` module deliberately does
not, so the transport-coupled logic lives here instead.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md ; wallet-ingestion follow-up.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from packages.polymarket.discovery.approval_request import (
    is_full_wallet_address,
    load_notified,
    mark_notified,
)
from packages.polymarket.discovery.evidence_summary import (
    Evidence,
    _clean_str,
    _fmt_pnl,
    summarize_evidence,
)

logger = logging.getLogger(__name__)

# Repo root is four parents up: packages/polymarket/discovery/<file>
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DOSSIER_BASE = _REPO_ROOT / "artifacts" / "dossiers" / "users"

# A metrics reader maps a watchlist row -> a raw metrics dict (or None). The
# default implementation resolves the scan run_root from ``last_scan_run_id``
# and extracts metrics; tests inject their own.
MetricsReader = Callable[[dict], Optional[dict]]

# A post callable maps (content, embeds) -> delivered-bool. Default wraps the
# Discord webhook transport; tests inject their own.
Poster = Callable[[str, Optional[list]], bool]

_COVERAGE_REPORT = "coverage_reconciliation_report.json"

# Embed presentation. The color bar is the review SEVERITY (info/blue), not a
# signal of wallet quality -- quality is conveyed by the fields, not the bar.
_COLOR_INFO = 0x3498DB
_FOOTER_TEXT = "PolyTool · Vera"  # middle-dot separator (final card design)

# Honest-omission marker shown when a metric / window is unavailable or not fully
# covered. An em dash (never a fabricated 0) — see the recent-form honesty rule.
_ABSENT = "—"

# Canonical Polymarket profile URL, built from the wallet ADDRESS (handles are not
# always present; the address-keyed profile page always resolves).
_PROFILE_URL = "https://polymarket.com/profile/{address}"

# Digest: at most _DIGEST_MAX wallets per message, further bounded by a content
# char budget so we never exceed Discord's 2000-char content limit (overflow is
# reported, never silently dropped). Discord embeds allow <=25 fields / 6000 ch.
_DIGEST_MAX = 10
_CONTENT_BUDGET = 1800

# Humanize the watchlist discovery source for the operator.
_SOURCE_LABELS = {
    "loop_a": "leaderboard discovery",
    "manual": "manual",
    "loop_d": "CLOB anomaly",
}


# ---------------------------------------------------------------------------
# Display-time evidence (Part A)
# ---------------------------------------------------------------------------


def _locate_run_root(run_id: str, base: Path) -> Optional[Path]:
    """Find the scan run_root directory named ``run_id`` under ``base``.

    The dossier layout is ``artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id>/``
    and the worker stores ``last_scan_run_id = run_root.name``. We glob for the
    directory of that name that actually holds a coverage report (the file
    ``_extract_user_metrics`` reads). Best-effort and never raises.
    """
    run_id = (run_id or "").strip()
    if not run_id:
        return None
    try:
        if not base.exists():
            return None
        for cand in base.glob(f"**/{run_id}"):
            if cand.is_dir() and (cand / _COVERAGE_REPORT).exists():
                return cand
    except Exception:  # pragma: no cover - defensive filesystem guard
        return None
    return None


def default_metrics_reader(
    row: dict, *, dossier_base: Optional[Path] = None
) -> Optional[dict]:
    """Resolve fresh scan metrics for a watchlist row from its scan run_root.

    Locates the run_root via ``last_scan_run_id`` and reads
    ``_extract_user_metrics`` (lazy import to avoid paying the scan-CLI import
    cost on the offline/mocked path). Returns the metrics dict or None when no
    scan data is locatable. Never raises.
    """
    if not isinstance(row, dict):
        return None
    run_id = str(row.get("last_scan_run_id") or "").strip()
    base = Path(dossier_base) if dossier_base is not None else DEFAULT_DOSSIER_BASE
    run_root = _locate_run_root(run_id, base)
    if run_root is None:
        return None
    try:
        from tools.cli.wallet_scan import _extract_user_metrics

        metrics = _extract_user_metrics(run_root)
    except Exception:  # pragma: no cover - defensive
        return None
    return metrics or None


def _is_nonzero(value: Any) -> bool:
    """True if a numeric metric is present and non-zero."""
    try:
        return value is not None and float(value) != 0.0
    except (TypeError, ValueError):
        return False


def _drop_inconsistent_zero(data: dict) -> dict:
    """Suppress an impossible 0/missing trade count beside real activity.

    A trade count of 0 (or missing) alongside non-zero realized PnL or present
    CLV coverage is internally inconsistent — it cannot come from the same data
    and signals a mis-sourced/dropped field, not a real zero. In that case we
    mark the count UNAVAILABLE (None) so the summary omits "trades" rather than
    display a misleading "0 trades". Never fabricates a count; leaves a genuine
    positive count untouched. Defense-in-depth against source regressions.
    """
    trades = data.get("trades")
    if trades is None:
        trades = data.get("positions_total")
    has_activity = _is_nonzero(data.get("realized_net_pnl")) or _is_nonzero(
        data.get("clv_coverage_rate")
    )
    if has_activity and (trades is None or _coerce_zero(trades)):
        data["trades"] = None
        data["positions_total"] = None
    return data


def _coerce_zero(value: Any) -> bool:
    """True if value parses to exactly 0."""
    try:
        return float(value) == 0.0
    except (TypeError, ValueError):
        return False


def _has_substantive_evidence(ev: Evidence) -> bool:
    """True if the evidence carries any performance/position signal.

    Provenance-only fields (``source``, ``wallet_address``) do NOT count -- a row
    carrying nothing but a discovery ``source`` must fall back to the stored
    reason rather than present bare provenance ("via loop_a") as if it were
    evidence about the wallet.
    """
    return any(
        (
            ev.realized_net_pnl is not None,
            ev.win_rate is not None,
            ev.trades is not None,
            ev.clv_coverage_rate is not None,
            ev.open_positions is not None,
            ev.resolved_positions is not None,
            bool(ev.category_focus),
            ev.churn_triggered,
        )
    )


def _row_evidence(
    row: dict, *, metrics_reader: Optional[MetricsReader] = None
) -> tuple[Evidence, str]:
    """Return ``(evidence, display_string)`` for a pending watchlist row.

    The ``Evidence`` object (structured fields for the embed card) is ALWAYS
    returned -- it may be all-None when no scan data is locatable. The display
    string is the substantive :func:`summarize_evidence` body when available,
    else the row's stored ``reason``, else "no evidence available". The discovery
    ``source`` (loop_a/manual/loop_d) is read from the ROW, not the metrics, so
    the card can humanize it even on a worker-advanced row. Never raises.
    """
    if not isinstance(row, dict):
        row = {}
    wallet = str(row.get("wallet_address") or "")
    stored = str(row.get("reason") or "").strip()
    reader = metrics_reader if metrics_reader is not None else default_metrics_reader

    metrics: Optional[dict] = None
    try:
        metrics = reader(row)
    except Exception:  # pragma: no cover - defensive (readers must not raise)
        metrics = None

    data: dict[str, Any] = _drop_inconsistent_zero(dict(metrics)) if metrics else {}
    data.setdefault("wallet_address", wallet)
    # Discovery signal: provenance lives on the row, not in scan metrics.
    src = _clean_str(row.get("source"))
    if src:
        data.setdefault("source", src)
    ev = Evidence.from_dict(data)

    if _has_substantive_evidence(ev):
        summary = summarize_evidence(ev)
        if summary and summary != "no evidence available":
            return ev, summary

    return ev, (stored or "no evidence available")


def compute_row_evidence(
    row: dict, *, metrics_reader: Optional[MetricsReader] = None
) -> str:
    """Return a display-time evidence summary string for a pending watchlist row.

    Thin wrapper over :func:`_row_evidence` preserving the ``--list-pending``
    contract: substantive computed summary, else stored ``reason``, else
    "no evidence available". Never raises.
    """
    return _row_evidence(row, metrics_reader=metrics_reader)[1]


# ---------------------------------------------------------------------------
# Pending-candidate notification (Part B)
# ---------------------------------------------------------------------------


def format_pending_notification(wallet_address: str, evidence_reason: str) -> str:
    """LEGACY plain-text pending message (superseded by the embed card).

    Retained as a stable, tested text form (full-address + ASCII guarantees);
    the live notify path now uses :func:`build_pending_embed` +
    :func:`build_single_content`.

    Layout (stable for the operator)::

        New pending candidate for review
        wallet: <full_address>
        evidence: <summarize_evidence body>
        Approve or deny via CLI:
        python3 -m polytool discovery review --approve <full_address>
        python3 -m polytool discovery review --deny <full_address>

    The FULL address is always rendered (never truncated). ASCII only (Windows
    webhook/console safety). The approve/deny lines are the real CLI gate
    commands -- Discord two-way approval is descoped.
    """
    full = (wallet_address or "").strip()
    reason = (
        evidence_reason
        if (evidence_reason and evidence_reason.strip())
        else "no evidence available"
    )
    return (
        "New pending candidate for review\n"
        f"wallet: {full}\n"
        f"evidence: {reason}\n"
        "Approve or deny via CLI:\n"
        f"python3 -m polytool discovery review --approve {full}\n"
        f"python3 -m polytool discovery review --deny {full}"
    )


def _default_post(content: str, embeds: Optional[list] = None) -> bool:
    """Default poster: the Discord webhook transport. Never raises.

    Lazily imported so this module carries no hard dependency on the
    notifications package (and tests need not configure a webhook).
    """
    try:
        from packages.polymarket.notifications.discord import post_message

        return bool(post_message(content, embeds=embeds))
    except Exception:  # pragma: no cover - defensive (post_message never raises)
        return False


# ---------------------------------------------------------------------------
# Embed-card + copy-block builders (pure; deterministic given now_iso)
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string for the embed timestamp."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _humanize_source(source: Any) -> Optional[str]:
    """Map a watchlist source to an operator-facing label (None when absent)."""
    s = _clean_str(source)
    if not s:
        return None
    return _SOURCE_LABELS.get(s, s)


def _pct(value: Optional[float]) -> str:
    """Render a [0,1] fraction as a whole percent, or the absent marker."""
    return f"{round(value * 100)}%" if value is not None else _ABSENT


def _now_dt(now_iso: Optional[str] = None) -> datetime:
    """Resolve the reference 'now' for relative/window rendering (aware UTC)."""
    if now_iso:
        parsed = _parse_iso(now_iso)
        if parsed is not None:
            return parsed
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (``Z`` or offset) to aware UTC, or None."""
    s = str(value or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _short_addr(full: str) -> str:
    """Truncate a 0x address for display: ``0x84cf…2f63``. Short input is echoed."""
    f = (full or "").strip()
    if len(f) >= 12:
        return f"{f[:6]}…{f[-4:]}"
    return f


def _profile_url(full: str) -> Optional[str]:
    """Polymarket profile URL for a wallet address, or None when no address."""
    f = (full or "").strip()
    return _PROFILE_URL.format(address=f) if f else None


def _relative_age(iso_ts: Optional[str], now: datetime) -> Optional[str]:
    """Render a timestamp as ``Nd ago`` / ``Nh ago`` / ``<1h ago`` (None if absent)."""
    ts = _parse_iso(iso_ts)
    if ts is None:
        return None
    delta = now - ts
    secs = delta.total_seconds()
    if secs < 0:
        return "just now"
    days = int(secs // 86400)
    if days >= 1:
        return f"{days}d ago"
    hours = int(secs // 3600)
    if hours >= 1:
        return f"{hours}h ago"
    return "<1h ago"


def _signal_line(ev: "Evidence", now: datetime) -> Optional[str]:
    """Compose ONE honest signal line from data we already have.

    e.g. ``leaderboard discovery · 62% win (25/40) · active 2d ago``. Each
    component is included only when present (honest omission); rank / conviction
    are skipped because the evidence does not carry them. Returns None when no
    component is available.
    """
    parts: list[str] = []
    src = _humanize_source(ev.source)
    if src:
        parts.append(src)
    if ev.win_rate is not None and ev.win_count is not None and ev.resolved_positions:
        parts.append(f"{round(ev.win_rate * 100)}% win ({ev.win_count}/{ev.resolved_positions})")
    elif ev.win_rate is not None and ev.resolved_positions:
        parts.append(f"{round(ev.win_rate * 100)}% win")
    age = _relative_age(ev.last_active, now)
    if age:
        parts.append(f"active {age}")
    return " · ".join(parts) if parts else None


def _window_starts(now: datetime) -> dict[str, datetime]:
    """Start instants for the Today (UTC calendar day) / 7d / 30d windows."""
    return {
        "Today": now.replace(hour=0, minute=0, second=0, microsecond=0),
        "7 days": now - timedelta(days=7),
        "30 days": now - timedelta(days=30),
    }


def _recent_form_values(recent_form: Optional[dict], now: datetime) -> dict[str, str]:
    """Windowed realized PnL per the HONESTY RULE — covered windows only.

    A window W is shown iff the sample fully covers it:
      * the sample was not truncated (``sample_size < sample_cap`` — we hold all
        their trades), OR
      * the oldest sampled resolution is older than the window start (so nothing
        inside the window was dropped).
    An uncovered window renders the absent marker (never a partial/undercounted
    number). A covered window with no in-window trades renders ``+$0`` (honest:
    full coverage, nothing realized).
    """
    labels = ("Today", "7 days", "30 days")
    starts = _window_starts(now)
    if not isinstance(recent_form, dict):
        return {k: _ABSENT for k in labels}

    raw_trades = recent_form.get("trades")
    trades: list[tuple[datetime, float]] = []
    if isinstance(raw_trades, list):
        for t in raw_trades:
            if not isinstance(t, dict):
                continue
            dt = _parse_iso(t.get("close"))
            pnl = t.get("pnl")
            if dt is None or not isinstance(pnl, (int, float)):
                continue
            trades.append((dt, float(pnl)))

    sample_size = recent_form.get("sample_size")
    sample_cap = recent_form.get("sample_cap")
    not_truncated = (
        isinstance(sample_size, int)
        and isinstance(sample_cap, int)
        and sample_size < sample_cap
    )
    oldest = min((dt for dt, _ in trades), default=None)

    out: dict[str, str] = {}
    for label in labels:
        start = starts[label]
        covered = not_truncated or (oldest is not None and oldest <= start)
        if not covered:
            out[label] = _ABSENT
            continue
        total = sum(pnl for dt, pnl in trades if dt >= start)
        out[label] = _fmt_pnl(total)
    return out


def _command_block(wallet: str) -> str:
    """A fenced code block with the approve/deny CLI commands (one-tap copy).

    Full address only -- the CLI gate rejects truncated identifiers.
    """
    full = (wallet or "").strip()
    return (
        "```\n"
        f"python3 -m polytool discovery review --approve {full}\n"
        f"python3 -m polytool discovery review --deny {full}\n"
        "```"
    )


def build_pending_embed(
    wallet_address: str,
    evidence: "Evidence | dict",
    *,
    now_iso: Optional[str] = None,
) -> dict:
    """Build the single pending-review embed card (the SHARED builder).

    Used by BOTH surfaces: the webhook notification and the Vera ``/pending``
    card (via ``discord.Embed.from_dict``), so they improve together.

    Layout (Discord embed primitives, not HTML):
      * author eyebrow ``Pending wallet review``; TITLE is the handle (falls back
        to the truncated address, then ``Unnamed wallet``);
      * description = truncated address (inline code) + a *View on Polymarket*
        link (built from the address) + the composed signal line;
      * two rows of three inline fields (PnL all-time / Win rate / Last active,
        then Trades / CLV coverage / Discovery);
      * a full-width separator ``Recent form — full trade history`` followed by
        three inline windows Today / 7 days / 30 days (realized PnL, honesty-ruled);
      * blue color bar = review SEVERITY (not wallet quality), footer + timestamp.

    Honest omission throughout: absent metrics and uncovered windows render the
    em-dash marker — never a fabricated 0. The full address + gate commands live
    in the message CONTENT (:func:`build_single_content`), unchanged.
    """
    ev = evidence if isinstance(evidence, Evidence) else Evidence.from_dict(evidence)
    full = (wallet_address or "").strip()
    now = _now_dt(now_iso)

    short = _short_addr(full)
    title = ev.handle or short or "Unnamed wallet"

    # Description: truncated address (code) + profile link + signal line.
    url = _profile_url(full)
    head = f"`{short}`" if short else "`unknown`"
    if url:
        head += f" · [View on Polymarket]({url})"
    signal = _signal_line(ev, now)
    description = head + (f"\n{signal}" if signal else "")

    # PnL: all-time, qualified by the resolved-book size when known.
    if ev.realized_net_pnl is not None:
        pnl_val = _fmt_pnl(ev.realized_net_pnl)
        if ev.resolved_positions is not None:
            pnl_val += f"\nall-time · {ev.resolved_positions} resolved"
        else:
            pnl_val += "\nall-time"
    else:
        pnl_val = _ABSENT

    # Win rate with denominator, honest "—" with no resolved book.
    if ev.win_rate is not None and ev.win_count is not None and ev.resolved_positions:
        win_val = f"{round(ev.win_rate * 100)}% ({ev.win_count}/{ev.resolved_positions})"
    elif ev.win_rate is not None and ev.resolved_positions:
        win_val = f"{round(ev.win_rate * 100)}%"
    else:
        win_val = _ABSENT

    trades_val = f"{ev.trades} (sampled)" if ev.trades is not None else _ABSENT
    last_active_val = _relative_age(ev.last_active, now) or _ABSENT

    windows = _recent_form_values(ev.recent_form, now)

    fields = [
        {"name": "PnL", "value": pnl_val, "inline": True},
        {"name": "Win rate", "value": win_val, "inline": True},
        {"name": "Last active", "value": last_active_val, "inline": True},
        {"name": "Trades", "value": trades_val, "inline": True},
        {"name": "CLV coverage", "value": _pct(ev.clv_coverage_rate), "inline": True},
        {"name": "Discovery", "value": _humanize_source(ev.source) or _ABSENT, "inline": True},
        # Full-width separator labelling the windowed row below.
        {"name": "Recent form — full trade history",
         "value": "Realized PnL by resolution date", "inline": False},
        {"name": "Today", "value": windows["Today"], "inline": True},
        {"name": "7 days", "value": windows["7 days"], "inline": True},
        {"name": "30 days", "value": windows["30 days"], "inline": True},
    ]

    embed = {
        "author": {"name": "Pending wallet review"},
        "title": title,
        "color": _COLOR_INFO,
        "description": description,
        "fields": fields,
        "footer": {"text": _FOOTER_TEXT},
        "timestamp": now_iso or _now_iso(),
    }
    return embed


def build_single_content(wallet_address: str) -> str:
    """Message CONTENT for a single card: heading + copy-block of CLI commands."""
    full = (wallet_address or "").strip()
    return "Pending wallet review - approve or deny via CLI:\n" + _command_block(full)


def _fit_digest(wallets: list[str]) -> tuple[list[str], int]:
    """Greedily select wallets that fit the content budget + field cap.

    Returns ``(shown, overflow)``. Bounded by both ``_DIGEST_MAX`` and a
    character budget so the message never exceeds Discord's 2000-char content
    limit. The overflow count is surfaced to the operator (never silently
    dropped) -- see :func:`build_digest_content`.
    """
    shown: list[str] = []
    used = 80  # heading + overflow-note slack
    for w in wallets:
        if len(shown) >= _DIGEST_MAX:
            break
        block_len = len(f"`{w}`") + 1 + len(_command_block(w)) + 1
        if used + block_len > _CONTENT_BUDGET:
            break
        used += block_len
        shown.append(w)
    return shown, len(wallets) - len(shown)


def build_digest_content(wallets: list[str], *, overflow: int = 0) -> str:
    """Message CONTENT for a digest: heading + one copy-block per wallet."""
    lines = [f"{len(wallets)} pending wallet reviews - approve or deny via CLI:"]
    for w in wallets:
        lines.append(f"`{w}`")
        lines.append(_command_block(w))
    if overflow > 0:
        lines.append(
            f"... +{overflow} more not shown; run "
            "`python3 -m polytool discovery review --list-pending`"
        )
    return "\n".join(lines)


def build_digest_embed(
    items: list[tuple[str, str]], *, now_iso: Optional[str] = None
) -> dict:
    """Build the digest embed: one stacked field per wallet (compact metrics).

    ``items`` is a list of ``(wallet, compact_summary)`` where the summary is the
    one-line evidence body from :func:`_row_evidence`.
    """
    fields = [
        {"name": w, "value": (s or "-")[:1024], "inline": False} for w, s in items
    ]
    return {
        "title": f"{len(items)} pending wallet reviews",
        "color": _COLOR_INFO,
        "fields": fields,
        "footer": {"text": _FOOTER_TEXT},
        "timestamp": now_iso or _now_iso(),
    }


# ---------------------------------------------------------------------------
# Senders (deduped, never-raise)
# ---------------------------------------------------------------------------


def notify_pending_candidate(
    wallet_address: str,
    evidence: "Evidence | dict",
    *,
    post: Optional[Poster] = None,
    notified_path: Optional[Path] = None,
) -> dict:
    """Post ONE deduped pending-review embed card. NEVER raises.

    ``evidence`` is the structured :class:`Evidence` for the card's fields. Dedup:
    a wallet already in ``approvals_notified.json`` is skipped (``deduped=True``).
    The wallet is recorded as notified ONLY on a delivered post (``ok=True``), so
    a failed webhook is retried next pass. A poster that returns False OR raises
    is caught and reported via ``ok`` -- it never propagates.

    Returns ``{wallet, deduped, posted, ok}``.
    """
    full = (wallet_address or "").strip()
    out = {"wallet": full.lower(), "deduped": False, "posted": False, "ok": False}

    # Refuse to notify on anything but a single full address (never raises).
    if not is_full_wallet_address(full):
        return out

    if full.lower() in load_notified(notified_path):
        out["deduped"] = True
        return out

    poster = post if post is not None else _default_post
    content = build_single_content(full)
    embed = build_pending_embed(full, evidence)

    try:
        ok = bool(poster(content, [embed]))
    except Exception as exc:  # webhook failure must never block the pipeline
        logger.warning(
            "pending-notify: post raised for %s (non-fatal): %s: %s",
            full,
            type(exc).__name__,
            exc,
        )
        ok = False

    out["posted"] = True
    out["ok"] = ok
    if ok:
        mark_notified(notified_path, full)
    return out


def notify_pending_candidates(
    rows: list[dict],
    *,
    post: Optional[Poster] = None,
    notified_path: Optional[Path] = None,
    metrics_reader: Optional[MetricsReader] = None,
) -> dict:
    """Notify newly-pending candidates as a single card OR one digest. NEVER raises.

    Filters out invalid addresses and already-notified wallets (deduped), then:

      * 0 unnotified  -> nothing sent;
      * 1 unnotified  -> single embed card;
      * >1 unnotified -> ONE digest message (single embed listing each wallet +
        per-wallet copy-blocks in content), bounded by ``_DIGEST_MAX`` and the
        content budget; overflow is reported, not silently dropped.

    Wallets are marked notified only on a delivered send (all-or-nothing for the
    digest, so a failed webhook re-notifies next pass). Per-pass failures are
    counted, never propagated.

    Returns ``{considered, posted, deduped, failed, mode[, skipped_capped]}``.
    """
    summary: dict[str, Any] = {
        "considered": 0, "posted": 0, "deduped": 0, "failed": 0, "mode": "none",
    }
    notified = load_notified(notified_path)
    candidates: list[tuple[str, Evidence, str]] = []

    for row in rows or []:
        if not isinstance(row, dict):
            continue
        summary["considered"] += 1
        wallet = str(row.get("wallet_address") or "").strip()
        if not is_full_wallet_address(wallet):
            continue
        if wallet.lower() in notified:
            summary["deduped"] += 1
            continue
        ev, s = _row_evidence(row, metrics_reader=metrics_reader)
        candidates.append((wallet, ev, s))

    if not candidates:
        return summary

    if len(candidates) == 1:
        summary["mode"] = "single"
        wallet, ev, _ = candidates[0]
        res = notify_pending_candidate(
            wallet, ev, post=post, notified_path=notified_path
        )
        if res["ok"]:
            summary["posted"] += 1
        elif res["deduped"]:
            summary["deduped"] += 1
        else:
            summary["failed"] += 1
        return summary

    # Digest: one message for all unnotified candidates (capped + budgeted).
    summary["mode"] = "digest"
    shown, overflow = _fit_digest([w for w, _, _ in candidates])
    shown_set = set(shown)
    shown_items = [(w, s) for w, _, s in candidates if w in shown_set]

    poster = post if post is not None else _default_post
    content = build_digest_content(shown, overflow=overflow)
    embed = build_digest_embed(shown_items)

    try:
        ok = bool(poster(content, [embed]))
    except Exception as exc:  # never block the pipeline
        logger.warning(
            "pending-notify: digest post raised (non-fatal): %s: %s",
            type(exc).__name__,
            exc,
        )
        ok = False

    if ok:
        for w in shown:
            mark_notified(notified_path, w)
        summary["posted"] += len(shown)
        if overflow:
            summary["skipped_capped"] = overflow
    else:
        summary["failed"] += len(shown)
    return summary
