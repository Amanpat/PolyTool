"""Phase B: `/pending` + one-tap approve/deny buttons (the FIRST write surface).

Design (ratified): the bot is a THIN TRIGGER over the already-Codex-verified
``discovery review`` CLI. It does NOT reimplement the lifecycle gate.

- READ (``/pending``): in-process, read-only reuse of ``read_pending_candidates``
  + ``_row_evidence`` + ``build_pending_embed`` — the exact evidence the webhook
  card shows. No writes.
- WRITE (button click): the ONLY mutation path. Shells out to the verified CLI
  via ``asyncio.create_subprocess_exec`` (list-form, NEVER a shell). The CLI's
  ``validate_transition`` is the sole writer; the bot never writes watchlist rows.

Security invariants (covered by Codex adversarial review + offline tests):
1. Author-guard on BOTH the list command and every button click — a click by a
   non-operator does nothing and is logged. Message visibility is never trusted
   as the only guard.
2. The button ``custom_id`` is parsed and the address is RE-VALIDATED against
   ``^0x[0-9a-fA-F]{40}$``; the action must be in ``{approve, deny}``. Any failure
   → ephemeral error, NO subprocess, NO write.
3. The subprocess is list-form (no shell, no shell string). The address is a
   single argv element; the action maps to a fixed ``--approve``/``--deny`` flag.
   The ClickHouse password is passed via the child ENV, never on argv.
4. Idempotency is driven by the CLI exit code: 0 → mark done + disable buttons;
   non-zero (already actioned / gate-rejected) → ephemeral "already actioned" +
   disable buttons. Never double-writes, never raises.
5. The interaction is deferred immediately (within 3s) because the subprocess
   outlasts the ack window.
6. No handler raises — a catch-all turns any unexpected error into an ephemeral
   message and a log line that never contains the token or ClickHouse password.

The bot may invoke ONLY ``discovery review --approve/--deny``. It does not import
or call kill_switch / execution / order placement / signing / risk_manager /
live bot / config writers — none are reachable from here.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Awaitable, Callable, Optional

import discord

from packages.polymarket.discovery.approval_request import is_full_wallet_address
from packages.polymarket.discord_bot.config import BotConfig, ClickHouseConfig

logger = logging.getLogger("vera.approvals")

_CID_PREFIX = "vera"
# Fixed action -> CLI flag map. An action absent from this map can NEVER reach
# the subprocess argv (defense-in-depth alongside parse_custom_id).
_ACTION_FLAGS = {"approve": "--approve", "deny": "--deny"}

_DIGEST_MAX = 10

# A runner maps (action, address, ch_config) -> (returncode, reason_text).
# Injectable so tests never spawn a real subprocess.
ReviewRunner = Callable[[str, str, ClickHouseConfig], Awaitable[tuple[int, str]]]


# ---------------------------------------------------------------------------
# custom_id encode / decode (pure)
# ---------------------------------------------------------------------------


def build_custom_id(action: str, address: str) -> str:
    """``vera:<action>:<address>`` — fits Discord's 100-char custom_id limit.

    ``vera:approve:`` (13) + 42-char address = 55 chars.
    """
    return f"{_CID_PREFIX}:{action}:{address}"


def parse_custom_id(custom_id: object) -> Optional[tuple[str, str]]:
    """Decode a button custom_id to ``(action, address)`` or ``None``.

    Returns ``None`` (caller rejects) for anything that is not exactly
    ``vera:<approve|deny>:<full-0x-address>``. An EVM address is hex-only, so a
    3-way split on ``:`` is unambiguous. This is the trust boundary: the address
    is re-validated here, never taken on faith from the component payload.
    """
    if not isinstance(custom_id, str):
        return None
    parts = custom_id.split(":")
    if len(parts) != 3:
        return None
    prefix, action, address = parts
    if prefix != _CID_PREFIX or action not in _ACTION_FLAGS:
        return None
    # Strict: reject any surrounding whitespace before validating. The canonical
    # validator strips, so a segment like " 0x..." would otherwise slip through
    # and the parsed address would carry the space into the argv.
    if address != address.strip():
        return None
    if not is_full_wallet_address(address):
        return None
    return action, address


# ---------------------------------------------------------------------------
# Subprocess to the verified CLI (list-form, no shell)
# ---------------------------------------------------------------------------


def build_review_argv(action: str, address: str, ch: ClickHouseConfig) -> list[str]:
    """Construct the exact verified CLI argv. Raises on a bad action/address.

    The address is a single argv element and the action resolves to a fixed flag
    — there is no user-controlled command string. The password is NOT here (the
    CLI reads CLICKHOUSE_PASSWORD from the inherited environment).
    """
    flag = _ACTION_FLAGS.get(action)
    if flag is None:
        raise ValueError(f"refusing unknown review action: {action!r}")
    if not is_full_wallet_address(address):
        raise ValueError("refusing review on a non-full wallet address")
    return [
        sys.executable, "-m", "polytool", "discovery", "review",
        flag, address,
        "--clickhouse-host", ch.host,
        "--clickhouse-port", str(ch.port),
        "--clickhouse-user", ch.user,
        "--json",
    ]


def _reason_from_output(returncode: int, stdout: str, stderr: str) -> str:
    """Extract a short, non-sensitive reason from CLI output for the operator.

    The CLI emits ``{"ok":false,"error":...}`` JSON on a gate refusal / not-found.
    Never includes credentials (the CLI error messages are about lifecycle state).
    """
    import json

    text = (stdout or "").strip()
    if text:
        try:
            obj = json.loads(text)
            if isinstance(obj, dict) and obj.get("error"):
                return str(obj["error"])[:300]
        except (ValueError, TypeError):
            pass
    tail = (stderr or "").strip().splitlines()
    if tail:
        return tail[-1][:300]
    return f"review exited with code {returncode}"


async def run_review_cli(
    action: str, address: str, ch: ClickHouseConfig
) -> tuple[int, str]:
    """Run ``discovery review --approve/--deny <address>`` as a subprocess.

    List-form exec, no shell. The ClickHouse password is inherited from the
    environment (never placed on argv). Returns ``(returncode, reason_text)``.
    """
    argv = build_review_argv(action, address, ch)
    # Inherit the environment so CLICKHOUSE_PASSWORD reaches the CLI; do NOT log it.
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=os.environ.copy(),
    )
    out_b, err_b = await proc.communicate()
    out = out_b.decode("utf-8", "replace") if out_b else ""
    err = err_b.decode("utf-8", "replace") if err_b else ""
    rc = proc.returncode if proc.returncode is not None else 1
    reason = "" if rc == 0 else _reason_from_output(rc, out, err)
    return rc, reason


# ---------------------------------------------------------------------------
# Author guard
# ---------------------------------------------------------------------------


def is_operator(interaction: discord.Interaction, config: BotConfig) -> bool:
    """True only if the interacting user is the configured operator.

    Fail-closed: an unset operator id authorizes NO ONE.
    """
    if config.operator_user_id is None:
        return False
    user = getattr(interaction, "user", None)
    return bool(user is not None and getattr(user, "id", None) == config.operator_user_id)


# ---------------------------------------------------------------------------
# Buttons + view
# ---------------------------------------------------------------------------


def _disabled_view(address: str) -> discord.ui.View:
    """A view with both buttons disabled (post-action / stale state)."""
    return ApproveDenyView(address, config=None, disabled=True)


class _ActionButton(discord.ui.Button):
    def __init__(self, *, action: str, address: str, style, label: str, disabled: bool):
        super().__init__(
            style=style,
            label=label,
            custom_id=build_custom_id(action, address),
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:  # pragma: no cover - thin delegate
        view = self.view
        if isinstance(view, ApproveDenyView):
            await view.handle(interaction)


class ApproveDenyView(discord.ui.View):
    """An Approve (green) / Deny (red) action row for one pending wallet."""

    def __init__(
        self,
        address: str,
        *,
        config: Optional[BotConfig],
        runner: Optional[ReviewRunner] = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(timeout=None)
        self._config = config
        self._runner = runner or run_review_cli
        self.add_item(
            _ActionButton(
                action="approve", address=address,
                style=discord.ButtonStyle.success, label="Approve", disabled=disabled,
            )
        )
        self.add_item(
            _ActionButton(
                action="deny", address=address,
                style=discord.ButtonStyle.danger, label="Deny", disabled=disabled,
            )
        )

    async def handle(self, interaction: discord.Interaction) -> None:
        # config is None only on disabled views, whose buttons cannot fire.
        if self._config is None:  # pragma: no cover - defensive
            return
        await handle_action(interaction, config=self._config, runner=self._runner)


# ---------------------------------------------------------------------------
# Button write handler (the mutation path)
# ---------------------------------------------------------------------------


async def handle_action(
    interaction: discord.Interaction,
    *,
    config: BotConfig,
    runner: ReviewRunner = run_review_cli,
) -> None:
    """Handle an Approve/Deny click. Defers, re-guards, validates, then triggers
    the verified CLI. Never raises (catch-all → ephemeral error)."""
    try:
        # 1. ACK immediately (within 3s) as a deferred message UPDATE so we can
        #    edit this component's message after the subprocess returns.
        try:
            await interaction.response.defer()
        except discord.InteractionResponded:  # pragma: no cover - already acked
            pass

        # 2. Author-guard AGAIN — never trust message visibility alone.
        if not is_operator(interaction, config):
            uid = getattr(getattr(interaction, "user", None), "id", None)
            logger.warning("Unauthorized approve/deny click by user id=%s — rejected.", uid)
            await interaction.followup.send("Not authorized.", ephemeral=True)
            return

        # 3. Parse + RE-VALIDATE the custom_id (the trust boundary).
        data = getattr(interaction, "data", None) or {}
        parsed = parse_custom_id(data.get("custom_id"))
        if parsed is None:
            logger.warning("Rejected malformed/tampered button custom_id — no write performed.")
            await interaction.followup.send(
                "Invalid or tampered action; ignored.", ephemeral=True
            )
            return
        action, address = parsed

        # 4. Trigger the verified CLI (list-form subprocess; the only writer).
        rc, reason = await runner(action, address, config.clickhouse)

        # 5. Idempotency via exit code.
        if rc == 0:
            await _finalize_done(interaction, action, address)
        else:
            logger.info(
                "review %s for %s returned rc=%s (already actioned / gate-rejected).",
                action, address, rc,
            )
            await _disable_only(interaction, address)
            await interaction.followup.send(
                f"No longer pending / already actioned: {reason or 'gate rejected the change'}",
                ephemeral=True,
            )
    except Exception:  # catch-all — a handler must never raise
        logger.exception("Unexpected error in approve/deny handler (no write assumed).")
        try:
            await interaction.followup.send(
                "Something went wrong handling that action; nothing was written.",
                ephemeral=True,
            )
        except Exception:  # pragma: no cover - last-resort guard
            pass


async def _finalize_done(
    interaction: discord.Interaction, action: str, address: str
) -> None:
    """On success: relabel this message's embed and disable both buttons."""
    label = "approved" if action == "approve" else "denied"
    color = discord.Color.green() if action == "approve" else discord.Color.red()
    message = getattr(interaction, "message", None)
    embeds = getattr(message, "embeds", None) if message is not None else None
    embed = embeds[0] if embeds else discord.Embed(description=f"Wallet `{address}`")
    embed.title = f"Wallet {label}"
    embed.color = color
    await interaction.edit_original_response(embed=embed, view=_disabled_view(address))


async def _disable_only(interaction: discord.Interaction, address: str) -> None:
    """Disable the buttons without changing the embed (stale / failed action)."""
    await interaction.edit_original_response(view=_disabled_view(address))


# ---------------------------------------------------------------------------
# /pending slash command (read-only list)
# ---------------------------------------------------------------------------


async def pending_command(
    interaction: discord.Interaction,
    *,
    config: BotConfig,
    runner: ReviewRunner = run_review_cli,
) -> None:
    """List current pending wallets, each with an Approve/Deny action row.

    Author-guarded and EPHEMERAL (only the invoker sees the cards, so only the
    operator can click the buttons). Read-only: never writes.
    """
    try:
        # Author-guard on the list itself.
        if not is_operator(interaction, config):
            uid = getattr(getattr(interaction, "user", None), "id", None)
            logger.warning("Unauthorized /pending by user id=%s — rejected.", uid)
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        rows = _read_pending(config.clickhouse)
        if rows is None:
            await interaction.followup.send(
                "Could not read pending wallets right now (is ClickHouse reachable "
                "and CLICKHOUSE_PASSWORD set?).",
                ephemeral=True,
            )
            return
        if not rows:
            await interaction.followup.send("No wallets pending review.", ephemeral=True)
            return

        shown = rows[:_DIGEST_MAX]
        overflow = len(rows) - len(shown)

        for row in shown:
            wallet = str(row.get("wallet_address") or "")
            embed = _build_embed(row, wallet)
            view = ApproveDenyView(wallet, config=config, runner=runner)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        if overflow > 0:
            await interaction.followup.send(
                f"+{overflow} more — action these first.", ephemeral=True
            )
    except Exception:  # never raise out of a command callback
        logger.exception("Unexpected error in /pending (read-only path).")
        try:
            await interaction.followup.send(
                "Something went wrong listing pending wallets.", ephemeral=True
            )
        except Exception:  # pragma: no cover
            pass


def _read_pending(ch: ClickHouseConfig) -> Optional[list[dict]]:
    """In-process, read-only pending-candidate read. Returns None on failure.

    Reuses the same reader the webhook path uses. The password is read from the
    environment here and never logged.
    """
    password = os.environ.get("CLICKHOUSE_PASSWORD", "").strip()
    if not password:
        logger.warning("/pending: CLICKHOUSE_PASSWORD is not set; cannot read.")
        return None
    try:
        from packages.polymarket.discovery.clickhouse_writer import read_pending_candidates

        return read_pending_candidates(
            host=ch.host, port=ch.port, user=ch.user, password=password
        )
    except Exception:
        logger.exception("/pending: failed to read pending candidates.")
        return None


def _build_embed(row: dict, wallet: str) -> discord.Embed:
    """Build the same evidence embed the webhook card shows, as a discord.Embed."""
    from packages.polymarket.discovery.pending_notify import (
        _row_evidence,
        build_pending_embed,
    )

    ev, _summary = _row_evidence(row)
    return discord.Embed.from_dict(build_pending_embed(wallet, ev))
