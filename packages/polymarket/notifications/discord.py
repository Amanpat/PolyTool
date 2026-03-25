"""Discord webhook notification transport for PolyTool operator alerts.

This module is a thin, stateless transport layer.  It formats operator-relevant
events into Discord messages and posts them via a webhook URL loaded from the
``DISCORD_WEBHOOK_URL`` environment variable.

Design contract:
- Notification failure **never** propagates to callers.  All public functions
  return ``True`` on success or ``False`` on failure / unconfigured.
- Message formatting lives here exclusively; callers pass structured data.
- No global state, no background threads, no retries.

Environment:
    DISCORD_WEBHOOK_URL: full Discord incoming webhook URL.  If absent or empty,
                         all post attempts silently no-op and return False.

Usage::

    from packages.polymarket.notifications.discord import notify_gate_result
    notify_gate_result("sweep", passed=True, commit="abc1234")
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime, timezone
from typing import Any, Optional

import requests

_ENV_KEY = "DISCORD_WEBHOOK_URL"
_TIMEOUT_SECONDS = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_webhook_url() -> Optional[str]:
    url = os.environ.get(_ENV_KEY, "").strip()
    return url or None


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Core transport
# ---------------------------------------------------------------------------


def post_message(text: str, *, webhook_url: Optional[str] = None) -> bool:
    """Post a plain-text (markdown-capable) message to the Discord webhook.

    Args:
        text:        Message body.  Discord supports limited markdown.
        webhook_url: Override the env-var webhook URL.  Primarily for testing.

    Returns:
        True if the webhook returned HTTP 2xx, False for any other outcome
        (no URL, HTTP error, network error).  Never raises.
    """
    url = webhook_url or _get_webhook_url()
    if not url:
        return False
    try:
        resp = requests.post(
            url,
            json={"content": text},
            timeout=_TIMEOUT_SECONDS,
        )
        return resp.ok
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Typed event helpers
# ---------------------------------------------------------------------------


def notify_gate_result(
    gate: str,
    passed: bool,
    *,
    commit: str = "unknown",
    detail: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """Send a gate pass or fail notification.

    Args:
        gate:        Gate name (e.g. ``"replay"``, ``"sweep"``, ``"dry_run"``).
        passed:      True if the gate passed.
        commit:      Short git commit hash.
        detail:      Optional one-line detail appended to the message.
        webhook_url: Override webhook URL.

    Returns:
        True if delivered, False otherwise.  Never raises.
    """
    icon = "\u2705" if passed else "\u274c"
    status = "PASSED" if passed else "FAILED"
    label = gate.replace("_", " ").title()
    lines = [
        f"{icon} **Gate {label}** \u2014 {status}",
        f"commit: `{commit}`  |  {_now_utc()}",
    ]
    if detail:
        lines.append(detail)
    return post_message("\n".join(lines), webhook_url=webhook_url)


def notify_session_start(
    mode: str,
    strategy: str,
    asset_id: str,
    *,
    dry_run: bool = True,
    webhook_url: Optional[str] = None,
) -> bool:
    """Notify that a live runner session has started.

    Args:
        mode:        ``"live"`` or ``"shadow"``.
        strategy:    Strategy name.
        asset_id:    Token ID being traded.
        dry_run:     True if no real orders will be submitted.
        webhook_url: Override webhook URL.

    Returns:
        True if delivered.  Never raises.
    """
    dry_label = "DRY-RUN" if dry_run else "**LIVE \u26a0\ufe0f**"
    text = (
        f"\U0001f7e2 **Session Start** [{dry_label}]\n"
        f"mode: `{mode}`  |  strategy: `{strategy}`  |  asset: `{asset_id}`\n"
        f"{_now_utc()}"
    )
    return post_message(text, webhook_url=webhook_url)


def notify_session_stop(
    mode: str,
    strategy: str,
    asset_id: str,
    *,
    summary: Optional[dict[str, Any]] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """Notify that a live runner session stopped cleanly.

    Args:
        mode:        ``"live"`` or ``"shadow"``.
        strategy:    Strategy name.
        asset_id:    Token ID.
        summary:     Optional summary dict (e.g. from ``run_once`` result).
        webhook_url: Override webhook URL.

    Returns:
        True if delivered.  Never raises.
    """
    lines = [
        "\U0001f535 **Session Stop** [clean]",
        f"mode: `{mode}`  |  strategy: `{strategy}`  |  asset: `{asset_id}`",
        _now_utc(),
    ]
    if summary:
        attempted = summary.get("attempted", "?")
        submitted = summary.get("submitted", "?")
        rejected = summary.get("rejected", "?")
        lines.append(
            f"attempted: {attempted}  |  submitted: {submitted}  |  rejected: {rejected}"
        )
    return post_message("\n".join(lines), webhook_url=webhook_url)


def notify_session_error(
    context: str,
    exc: BaseException,
    *,
    webhook_url: Optional[str] = None,
) -> bool:
    """Notify that a runtime error occurred during a session.

    Args:
        context:     Short description of where the error occurred.
        exc:         The exception instance.
        webhook_url: Override webhook URL.

    Returns:
        True if delivered.  Never raises.
    """
    tb_tail = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )[-500:]
    text = (
        f"\U0001f534 **Runtime Error** \u2014 {context}\n"
        f"```\n{tb_tail}\n```\n"
        f"{_now_utc()}"
    )
    return post_message(text, webhook_url=webhook_url)


def notify_kill_switch(
    path: str,
    *,
    context: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """Notify that the kill switch has been tripped.

    Args:
        path:        Path to the kill-switch sentinel file.
        context:     Optional context (e.g. ``"run_once pre-tick check"``).
        webhook_url: Override webhook URL.

    Returns:
        True if delivered.  Never raises.
    """
    lines = [
        "\U0001f6d1 **Kill Switch Tripped**",
        f"file: `{path}`",
        _now_utc(),
    ]
    if context:
        lines.append(f"context: {context}")
    return post_message("\n".join(lines), webhook_url=webhook_url)


def notify_risk_halt(
    reason: str,
    *,
    context: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """Notify that the risk manager has triggered a halt.

    Args:
        reason:      The halt reason string from ``RiskManager``.
        context:     Optional context (e.g. asset ID or strategy name).
        webhook_url: Override webhook URL.

    Returns:
        True if delivered.  Never raises.
    """
    lines = [
        "\u26a0\ufe0f **Risk Manager Halt**",
        f"reason: {reason}",
        _now_utc(),
    ]
    if context:
        lines.append(f"context: {context}")
    return post_message("\n".join(lines), webhook_url=webhook_url)
