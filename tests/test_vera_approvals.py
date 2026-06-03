"""Offline unit tests for the Vera Phase B approve/deny write surface.

Fully offline: no Discord gateway, no real subprocess, no ClickHouse. The button
handler, custom_id parsing, argv construction, author-guard, and /pending command
are exercised with mocked interactions and an injected review runner.

These tests are the evidence for the mandatory Codex adversarial-review criteria
(non-operator rejected; tampered/garbage address rejected; action constrained to
{approve,deny}; idempotent double-click; list-form subprocess; gate not bypassed;
secrets never logged; buttons disabled; deferred within 3s; no handler raises).

Requires the optional ``discord`` extra; skipped when discord.py is absent.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("discord", reason="requires the [discord] optional dependency")

import discord  # noqa: E402

from packages.polymarket.discord_bot import approvals  # noqa: E402
from packages.polymarket.discord_bot.config import BotConfig, ClickHouseConfig  # noqa: E402

pytestmark = pytest.mark.optional_dep


@pytest.fixture(autouse=True)
def _clear_idempotency_guard():
    """Reset the in-process actioned-wallet guard between tests."""
    approvals._actioned_wallets.clear()
    yield
    approvals._actioned_wallets.clear()


OPERATOR_ID = 999_000_111
ADDR = "0x1234567890abcdef1234567890abcdef12345678"  # valid 0x + 40 hex
ADDR2 = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"


def _config(operator_id=OPERATOR_ID):
    return BotConfig(
        operator_user_id=operator_id,
        guild_id=None,
        clickhouse=ClickHouseConfig(host="clickhouse", port=8123, user="polytool_admin"),
    )


def _interaction(*, user_id, custom_id=None):
    """A fake component interaction with async response/followup/edit methods."""
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.data = {"custom_id": custom_id} if custom_id is not None else {}
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    # message with a real embed so _finalize_done can mutate it
    interaction.message = MagicMock()
    interaction.message.embeds = [discord.Embed(title="Pending wallet review")]
    return interaction


# ---------------------------------------------------------------------------
# custom_id parse / build (criteria 2, 3, 5)
# ---------------------------------------------------------------------------


def test_build_and_parse_roundtrip():
    assert approvals.parse_custom_id(approvals.build_custom_id("approve", ADDR)) == (
        "approve", ADDR,
    )
    assert approvals.parse_custom_id(approvals.build_custom_id("deny", ADDR)) == (
        "deny", ADDR,
    )


def test_custom_id_within_discord_limit():
    assert len(approvals.build_custom_id("approve", ADDR)) <= 100


@pytest.mark.parametrize(
    "bad",
    [
        None,
        123,
        "",
        "vera:approve",  # too few parts
        "vera:approve:0xshort",  # truncated address
        "vera:approve:" + ADDR + ":extra",  # too many parts
        "vera:promote:" + ADDR,  # action not in {approve,deny}
        "evil:approve:" + ADDR,  # wrong prefix
        "vera:approve:0xZZ34567890abcdef1234567890abcdef12345678",  # non-hex
        "vera:approve:" + ADDR + "00",  # too long
        "vera:approve: " + ADDR,  # embedded space
    ],
)
def test_parse_custom_id_rejects_garbage(bad):
    assert approvals.parse_custom_id(bad) is None


# ---------------------------------------------------------------------------
# argv construction (criteria 3, 5, 7) — list-form, no shell, no password on argv
# ---------------------------------------------------------------------------


def test_build_review_argv_list_form_approve():
    ch = ClickHouseConfig(host="clickhouse", port=8123, user="polytool_admin")
    argv = approvals.build_review_argv("approve", ADDR, ch)
    assert isinstance(argv, list)
    assert "--approve" in argv and "--deny" not in argv
    # address is exactly one argv element (never concatenated into a string)
    assert argv.count(ADDR) == 1
    assert ["discovery", "review"] == argv[argv.index("discovery"):argv.index("review") + 1]
    assert "--clickhouse-host" in argv and "clickhouse" in argv


def test_build_review_argv_deny_flag():
    ch = ClickHouseConfig()
    argv = approvals.build_review_argv("deny", ADDR, ch)
    assert "--deny" in argv and "--approve" not in argv


def test_build_review_argv_rejects_unknown_action():
    with pytest.raises(ValueError):
        approvals.build_review_argv("promote", ADDR, ClickHouseConfig())
    with pytest.raises(ValueError):
        approvals.build_review_argv("rm -rf", ADDR, ClickHouseConfig())


def test_build_review_argv_rejects_bad_address():
    with pytest.raises(ValueError):
        approvals.build_review_argv("approve", "0xshort", ClickHouseConfig())


def test_argv_never_contains_password(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "s3kret-should-not-appear")
    argv = approvals.build_review_argv("approve", ADDR, ClickHouseConfig())
    assert not any("s3kret" in part for part in argv)


# ---------------------------------------------------------------------------
# run_review_cli (criteria 3, 5, 7) — exec list-form, password via env only
# ---------------------------------------------------------------------------


def test_run_review_cli_uses_exec_and_env(monkeypatch):
    monkeypatch.setenv("CLICKHOUSE_PASSWORD", "s3kret")
    captured = {}

    class FakeProc:
        returncode = 0

        async def communicate(self):
            return (b'{"ok":true}', b"")

    async def fake_exec(*argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs.get("env")
        return FakeProc()

    monkeypatch.setattr(approvals.asyncio, "create_subprocess_exec", fake_exec)

    rc, reason = asyncio.run(
        approvals.run_review_cli("approve", ADDR, ClickHouseConfig())
    )
    assert rc == 0
    assert reason == ""
    # list-form: each token is its own positional arg; no shell string anywhere
    assert "--approve" in captured["argv"]
    assert ADDR in captured["argv"]
    assert all(isinstance(a, str) for a in captured["argv"])
    # password is in the child ENV, never on argv
    assert captured["env"].get("CLICKHOUSE_PASSWORD") == "s3kret"
    assert not any("s3kret" in a for a in captured["argv"])


def test_run_review_cli_nonzero_returns_reason(monkeypatch):
    class FakeProc:
        returncode = 1

        async def communicate(self):
            return (b'{"ok":false,"error":"gate refused: scanned->reviewed"}', b"")

    async def fake_exec(*argv, **kwargs):
        return FakeProc()

    monkeypatch.setattr(approvals.asyncio, "create_subprocess_exec", fake_exec)
    rc, reason = asyncio.run(approvals.run_review_cli("deny", ADDR, ClickHouseConfig()))
    assert rc == 1
    assert "gate refused" in reason


def test_reason_from_output_prefers_json_error():
    assert "already" in approvals._reason_from_output(
        1, '{"ok":false,"error":"already actioned"}', ""
    )
    # falls back to stderr tail when stdout is not JSON
    assert "boom" in approvals._reason_from_output(1, "", "trace\nboom")


# ---------------------------------------------------------------------------
# author guard (criterion 1)
# ---------------------------------------------------------------------------


def test_is_operator_true_for_operator():
    assert approvals.is_operator(_interaction(user_id=OPERATOR_ID), _config()) is True


def test_is_operator_false_for_other_user():
    assert approvals.is_operator(_interaction(user_id=123), _config()) is False


def test_is_operator_false_when_unconfigured():
    assert approvals.is_operator(_interaction(user_id=OPERATOR_ID), _config(None)) is False


# ---------------------------------------------------------------------------
# handle_action — the write path (criteria 1,2,3,4,5,6,8,9,10)
# ---------------------------------------------------------------------------


def test_handle_action_non_operator_rejected_no_subprocess():
    interaction = _interaction(
        user_id=555, custom_id=approvals.build_custom_id("approve", ADDR)
    )
    runner = AsyncMock(return_value=(0, ""))
    asyncio.run(approvals.handle_action(interaction, config=_config(), runner=runner))

    interaction.response.defer.assert_awaited_once()  # deferred within 3s first
    runner.assert_not_awaited()  # NO subprocess
    interaction.edit_original_response.assert_not_awaited()  # NO write/edit
    interaction.followup.send.assert_awaited_once()
    assert "Not authorized" in interaction.followup.send.call_args.args[0]


def test_handle_action_malformed_custom_id_rejected_no_subprocess():
    interaction = _interaction(user_id=OPERATOR_ID, custom_id="vera:promote:" + ADDR)
    runner = AsyncMock(return_value=(0, ""))
    asyncio.run(approvals.handle_action(interaction, config=_config(), runner=runner))

    runner.assert_not_awaited()
    interaction.edit_original_response.assert_not_awaited()
    assert "Invalid or tampered" in interaction.followup.send.call_args.args[0]


def test_handle_action_tampered_address_rejected_no_subprocess():
    interaction = _interaction(
        user_id=OPERATOR_ID, custom_id="vera:approve:0xdeadbeef"
    )
    runner = AsyncMock(return_value=(0, ""))
    asyncio.run(approvals.handle_action(interaction, config=_config(), runner=runner))
    runner.assert_not_awaited()


def test_handle_action_approve_success_disables_and_marks():
    interaction = _interaction(
        user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("approve", ADDR)
    )
    runner = AsyncMock(return_value=(0, ""))
    asyncio.run(approvals.handle_action(interaction, config=_config(), runner=runner))

    runner.assert_awaited_once()
    # the only writer is the CLI runner; the message is edited to reflect success
    interaction.edit_original_response.assert_awaited_once()
    kwargs = interaction.edit_original_response.call_args.kwargs
    assert kwargs["embed"].title == "Wallet approved"
    view = kwargs["view"]
    assert all(item.disabled for item in view.children)  # buttons disabled


def test_handle_action_deny_success():
    interaction = _interaction(
        user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("deny", ADDR)
    )
    runner = AsyncMock(return_value=(0, ""))
    asyncio.run(approvals.handle_action(interaction, config=_config(), runner=runner))
    assert interaction.edit_original_response.call_args.kwargs["embed"].title == "Wallet denied"


def test_handle_action_stale_click_idempotent_no_double_write():
    interaction = _interaction(
        user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("approve", ADDR)
    )
    runner = AsyncMock(return_value=(1, "already actioned"))
    asyncio.run(approvals.handle_action(interaction, config=_config(), runner=runner))

    runner.assert_awaited_once()
    # buttons disabled, embed NOT relabelled to success, operator told it's stale
    interaction.edit_original_response.assert_awaited_once()
    view = interaction.edit_original_response.call_args.kwargs["view"]
    assert all(item.disabled for item in view.children)
    assert "already actioned" in interaction.followup.send.call_args.args[0]


def test_handle_action_runner_raises_is_caught():
    interaction = _interaction(
        user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("approve", ADDR)
    )

    async def boom(*a, **k):
        raise RuntimeError("subprocess blew up")

    # must not raise out of the handler
    asyncio.run(approvals.handle_action(interaction, config=_config(), runner=boom))
    interaction.followup.send.assert_awaited()  # ephemeral error sent
    assert "went wrong" in interaction.followup.send.call_args.args[0]


def test_handle_action_duplicate_click_no_second_write():
    """A second click on a duplicate card for an already-actioned wallet must
    NOT trigger a second subprocess (the Codex-flagged double-write race)."""
    cfg = _config()
    runner = AsyncMock(return_value=(0, ""))

    i1 = _interaction(
        user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("approve", ADDR)
    )
    asyncio.run(approvals.handle_action(i1, config=cfg, runner=runner))

    # duplicate card for the SAME wallet, even with the other action
    i2 = _interaction(
        user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("deny", ADDR)
    )
    asyncio.run(approvals.handle_action(i2, config=cfg, runner=runner))

    runner.assert_awaited_once()  # only the first click reached the CLI
    assert "already actioned" in i2.followup.send.call_args.args[0]
    i2.edit_original_response.assert_awaited()  # dup card buttons disabled


def test_handle_action_failure_keeps_reservation_no_double_write():
    """A non-zero result is fail-safe: the reservation is KEPT (the write may have
    landed despite an ambiguous transport failure), so the bot never re-triggers
    in-session — guaranteeing no double-write."""
    cfg = _config()
    runner = AsyncMock(return_value=(1, "ambiguous write failure"))

    i1 = _interaction(
        user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("approve", ADDR)
    )
    asyncio.run(approvals.handle_action(i1, config=cfg, runner=runner))
    assert ADDR.lower() in approvals._actioned_wallets  # KEPT (fail-safe)

    # a duplicate card for the same wallet must NOT spawn a second subprocess
    i2 = _interaction(
        user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("approve", ADDR)
    )
    asyncio.run(approvals.handle_action(i2, config=cfg, runner=runner))
    runner.assert_awaited_once()  # no second attempt -> no double-write


def test_concurrent_clicks_same_wallet_single_subprocess():
    """Two concurrent clicks for the same wallet → exactly one subprocess.

    Proves the synchronous reserve (no await between check and add) closes the
    race on the single asyncio event loop.
    """
    cfg = _config()

    async def _scenario():
        gate = asyncio.Event()
        calls = []

        async def slow_runner(action, address, ch):
            calls.append(address)
            await gate.wait()
            return (0, "")

        i1 = _interaction(
            user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("approve", ADDR)
        )
        i2 = _interaction(
            user_id=OPERATOR_ID, custom_id=approvals.build_custom_id("approve", ADDR)
        )
        t1 = asyncio.create_task(
            approvals.handle_action(i1, config=cfg, runner=slow_runner)
        )
        t2 = asyncio.create_task(
            approvals.handle_action(i2, config=cfg, runner=slow_runner)
        )
        await asyncio.sleep(0.02)  # let both reach the reservation guard
        gate.set()
        await asyncio.gather(t1, t2)
        return calls

    calls = asyncio.run(_scenario())
    assert len(calls) == 1  # only one click spawned a subprocess


def test_handle_action_defers_before_anything_else():
    interaction = _interaction(
        user_id=555, custom_id=approvals.build_custom_id("approve", ADDR)
    )
    asyncio.run(
        approvals.handle_action(
            interaction, config=_config(), runner=AsyncMock(return_value=(0, ""))
        )
    )
    interaction.response.defer.assert_awaited_once()


# ---------------------------------------------------------------------------
# /pending command (criteria 1, read-only listing)
# ---------------------------------------------------------------------------


def test_pending_non_operator_rejected_no_read(monkeypatch):
    called = {"read": False}
    monkeypatch.setattr(
        approvals, "_read_pending", lambda ch: called.__setitem__("read", True)
    )
    interaction = _interaction(user_id=555)
    asyncio.run(approvals.pending_command(interaction, config=_config()))

    assert called["read"] is False
    interaction.response.send_message.assert_awaited_once()
    assert "Not authorized" in interaction.response.send_message.call_args.args[0]


def test_pending_empty(monkeypatch):
    monkeypatch.setattr(approvals, "_read_pending", lambda ch: [])
    interaction = _interaction(user_id=OPERATOR_ID)
    asyncio.run(approvals.pending_command(interaction, config=_config()))
    assert "No wallets pending review" in interaction.followup.send.call_args.args[0]


def test_pending_read_failure(monkeypatch):
    monkeypatch.setattr(approvals, "_read_pending", lambda ch: None)
    interaction = _interaction(user_id=OPERATOR_ID)
    asyncio.run(approvals.pending_command(interaction, config=_config()))
    assert "Could not read" in interaction.followup.send.call_args.args[0]


def test_pending_lists_one_card_per_wallet(monkeypatch):
    rows = [{"wallet_address": ADDR}, {"wallet_address": ADDR2}]
    monkeypatch.setattr(approvals, "_read_pending", lambda ch: rows)
    monkeypatch.setattr(
        approvals, "_build_embed", lambda row, wallet: discord.Embed(title=wallet)
    )
    interaction = _interaction(user_id=OPERATOR_ID)
    asyncio.run(approvals.pending_command(interaction, config=_config()))

    # one ephemeral followup per wallet
    assert interaction.followup.send.await_count == 2
    for call in interaction.followup.send.await_args_list:
        assert call.kwargs.get("ephemeral") is True
        assert isinstance(call.kwargs.get("view"), approvals.ApproveDenyView)


def test_pending_caps_at_ten_and_reports_overflow(monkeypatch):
    rows = [{"wallet_address": ADDR} for _ in range(11)]
    monkeypatch.setattr(approvals, "_read_pending", lambda ch: rows)
    monkeypatch.setattr(
        approvals, "_build_embed", lambda row, wallet: discord.Embed(title="x")
    )
    interaction = _interaction(user_id=OPERATOR_ID)
    asyncio.run(approvals.pending_command(interaction, config=_config()))

    # 10 cards + 1 overflow note
    assert interaction.followup.send.await_count == 11
    assert "+1 more" in interaction.followup.send.await_args_list[-1].args[0]
