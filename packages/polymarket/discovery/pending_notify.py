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
   message when a candidate enters ``review_status='pending'``. The message
   carries the FULL wallet address, the computed evidence body, and the exact
   approve/deny CLI commands. Deduped through the WI-5
   ``approvals_notified.json`` state file so a candidate is notified exactly once
   (no re-notify on re-scans). The post NEVER raises -- a webhook failure is
   logged and swallowed so it can never fail or block the ingestion pipeline.

This module DOES touch the Discord transport (via a lazily-imported, injectable
``post`` callable); the pure WI-5 ``approval_request`` module deliberately does
not, so the transport-coupled logic lives here instead.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md ; wallet-ingestion follow-up.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from packages.polymarket.discovery.approval_request import (
    is_full_wallet_address,
    load_notified,
    mark_notified,
)
from packages.polymarket.discovery.evidence_summary import (
    Evidence,
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

# A post callable maps message text -> delivered-bool. Default wraps the Discord
# webhook transport; tests inject their own.
Poster = Callable[[str], bool]

_COVERAGE_REPORT = "coverage_reconciliation_report.json"


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


def compute_row_evidence(
    row: dict, *, metrics_reader: Optional[MetricsReader] = None
) -> str:
    """Return a display-time evidence summary for a pending watchlist row.

    Recomputes :func:`summarize_evidence` from the wallet's fresh scan metrics
    (so a worker-advanced row showing the generic reason gets real evidence at
    display time). Falls back to the row's stored ``reason``, then to
    "no evidence available". Never raises.
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

    if metrics:
        data: dict[str, Any] = _drop_inconsistent_zero(dict(metrics))
        data.setdefault("wallet_address", wallet)
        summary = summarize_evidence(Evidence.from_dict(data))
        if summary and summary != "no evidence available":
            return summary

    return stored or "no evidence available"


# ---------------------------------------------------------------------------
# Pending-candidate notification (Part B)
# ---------------------------------------------------------------------------


def format_pending_notification(wallet_address: str, evidence_reason: str) -> str:
    """Build the deterministic Discord message for a newly-pending candidate.

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


def _default_post(text: str) -> bool:
    """Default poster: the Discord webhook transport. Never raises.

    Lazily imported so this module carries no hard dependency on the
    notifications package (and tests need not configure a webhook).
    """
    try:
        from packages.polymarket.notifications.discord import post_message

        return bool(post_message(text))
    except Exception:  # pragma: no cover - defensive (post_message never raises)
        return False


def notify_pending_candidate(
    wallet_address: str,
    evidence_reason: str,
    *,
    post: Optional[Poster] = None,
    notified_path: Optional[Path] = None,
) -> dict:
    """Post a deduped pending-candidate notification. NEVER raises.

    Dedup: a wallet already recorded in the ``approvals_notified.json`` state
    file is skipped (``deduped=True``). On a genuine attempt, the wallet is
    recorded as notified ONLY when the post is delivered (``ok=True``), so a
    failed webhook is retried on the next pass rather than silently lost.

    A webhook failure (poster returns False OR raises) is caught and reported
    via the ``ok`` flag -- it never propagates, so it cannot block the pipeline.

    Returns a dict: ``{wallet, deduped, posted, ok}``.
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
    text = format_pending_notification(full, evidence_reason)

    try:
        ok = bool(poster(text))
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
    """Notify each pending-candidate row (deduped), computing real evidence.

    For each row: compute display-time evidence (Part A) and fire a deduped
    notification (Part B). NEVER raises -- per-row failures are counted, not
    propagated.

    Returns a summary dict: ``{considered, posted, deduped, failed}``.
    """
    summary = {"considered": 0, "posted": 0, "deduped": 0, "failed": 0}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        summary["considered"] += 1
        wallet = str(row.get("wallet_address") or "")
        evidence = compute_row_evidence(row, metrics_reader=metrics_reader)
        res = notify_pending_candidate(
            wallet, evidence, post=post, notified_path=notified_path
        )
        if res["deduped"]:
            summary["deduped"] += 1
        elif res["ok"]:
            summary["posted"] += 1
        elif res["posted"]:
            summary["failed"] += 1
    return summary
