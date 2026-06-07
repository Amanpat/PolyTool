"""Offline unit tests for DR-3 — the Vera ``/status`` window (read-only).

Fully offline: no Discord gateway, no ClickHouse, no network. The status
assembler is exercised with an injected ``QueryRunner`` (a dict-keyed fake) and
the ``/status`` handler with mocked interactions + an injected snapshot reader.

Coverage:
- correct in-queue / scanned-today / pending-review / failed counts on seeded data
- top-N ordering by realized PnL (descending)
- wallet ID and username render as SEPARATE embed columns
- best-effort degradation when a sub-query fails (None tile, em-dash, no raise)
- author-guard: a non-operator /status is denied and reads NOTHING
- no write surface reachable from the assembler or handler

The ``status_window`` assembler tests do NOT require discord. The handler tests
require the optional ``discord`` extra and skip without it.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.polymarket.discord_bot import status_window as sw


# ---------------------------------------------------------------------------
# A seeded fake QueryRunner: matches on SQL substrings -> canned row lists.
# ---------------------------------------------------------------------------


def make_fake_query(responses: dict[str, object]):
    """Return a QueryRunner that matches the first substring key found in the SQL.

    ``responses`` maps a distinctive SQL substring -> the row list to return
    (or None to simulate a failed sub-query). An unmatched SQL returns []
    (a successful-but-empty result).
    """

    def _run(sql: str):
        for needle, rows in responses.items():
            if needle in sql:
                return rows
        return []

    return _run


_NOW = datetime(2026, 6, 4, 18, 0, 0, tzinfo=timezone.utc)


def _full_responses():
    """A fully-populated, seeded response set."""
    return {
        # queue state buckets
        "GROUP BY queue_state": [
            {"queue_state": "pending", "c": 7},
            {"queue_state": "leased", "c": 2},
            {"queue_state": "failed", "c": 3},
            {"queue_state": "done", "c": 40},
        ],
        # pending review (candidate-tier filter)
        "tier = 'candidate'": [{"c": 5}],
        # scanned today
        "toDate(last_scanned_at) = today()": [{"c": 12}],
        # last drain
        "max(updated_at)": [{"t": "2026-06-04 17:45:00"}],
        # RIS docs today (table absent -> None)
        "ris_documents": None,
        # daily PnL for the Top-N wallets
        "FROM polytool.user_pnl_bucket": [
            {"wallet": "0xaaaa000000000000000000000000000000000001", "daily_pnl": 120.0},
            {"wallet": "0xbbbb000000000000000000000000000000000002", "daily_pnl": -45.0},
            {"wallet": "0xcccc000000000000000000000000000000000003", "daily_pnl": 0.0},
        ],
    }


# ---------------------------------------------------------------------------
# Top-N now comes from a leaderboard.json artifact, not ClickHouse. Tests inject
# a fake loader (top_n -> list[TopWallet] | None) so they never touch the disk.
# ---------------------------------------------------------------------------


def _top_fixture():
    """A seeded, already-ranked Top-N (descending realized PnL).

    The third wallet has no username -> the embed must fall back to a truncated
    wallet ID via ``display_name`` (never blank).
    """
    return [
        sw.TopWallet("0xaaaa000000000000000000000000000000000001", "whale_one", 1500000.0, 12),
        sw.TopWallet("0xbbbb000000000000000000000000000000000002", "trader_two", 24000.0, 3),
        sw.TopWallet("0xcccc000000000000000000000000000000000003", None, -350.0, 0),
    ]


def make_fake_loader(rows):
    """Return a LeaderboardLoader yielding ``rows`` (a list or None)."""

    def _load(top_n):
        return rows

    return _load


def _assemble(responses=None, *, loader=None, now=_NOW):
    """Assemble with seeded tiles + a seeded Top-N loader (both default-full)."""
    query = make_fake_query(responses if responses is not None else _full_responses())
    return sw.assemble_status(
        query,
        now=now,
        leaderboard_loader=loader if loader is not None else make_fake_loader(_top_fixture()),
    )


# ---------------------------------------------------------------------------
# Counts on seeded data
# ---------------------------------------------------------------------------


def test_assemble_counts_on_seeded_data():
    snap = _assemble()
    assert snap.in_queue == 9   # pending(7) + leased(2)
    assert snap.failed == 3
    assert snap.pending_review == 5
    assert snap.scanned_today == 12
    assert snap.degraded == []  # nothing failed


def test_pending_review_falls_back_when_tier_columns_absent():
    # Strict (tier=...) SELECT errors -> None; fallback (review_status=...) returns.
    responses = _full_responses()
    responses["tier = 'candidate'"] = None
    responses["WHERE review_status = 'pending' AND lifecycle_state = 'scanned'"] = [{"c": 4}]
    snap = _assemble(responses)
    assert snap.pending_review == 4


# ---------------------------------------------------------------------------
# Top-N ordering + separate columns
# ---------------------------------------------------------------------------


def test_top_wallets_preserve_descending_order():
    snap = _assemble()
    pnls = [w.realized_pnl for w in snap.top_wallets]
    assert pnls == sorted(pnls, reverse=True)
    assert pnls == [1500000.0, 24000.0, -350.0]


def test_top_wallet_id_and_username_are_separate_fields():
    snap = _assemble()
    top = snap.top_wallets[0]
    # Distinct dataclass fields — the wallet ID is the address, username separate.
    assert top.wallet_address.startswith("0xaaaa")
    assert top.username == "whale_one"
    # A wallet with no username -> None (the embed falls back to a wallet ID).
    assert snap.top_wallets[2].username is None


def test_embed_renders_wallet_id_and_username_in_separate_columns():
    snap = _assemble()
    embed = sw.build_status_embed(snap)
    field_names = [f["name"] for f in embed["fields"]]
    # Three distinct inline fields acting as columns.
    assert "Wallet ID" in field_names
    assert "Username" in field_names
    assert "Daily PnL" in field_names
    assert "Net PnL" in field_names

    by_name = {f["name"]: f["value"] for f in embed["fields"]}
    # Wallet ID column holds shortened addresses, not usernames.
    assert "whale_one" not in by_name["Wallet ID"]
    assert "0xaaaa" in by_name["Wallet ID"]
    # Username column holds the real handle when present, and falls back to a
    # truncated wallet ID (NEVER blank/em-dash) for the wallet with no username.
    uname_lines = by_name["Username"].splitlines()
    assert uname_lines[0] == "whale_one"
    assert sw._ABSENT not in by_name["Username"]
    assert "0xcccc" in uname_lines[2]  # truncated-wallet fallback, not empty
    # Daily PnL comes before lifetime net PnL and is sourced separately.
    assert by_name["Daily PnL"].splitlines() == ["+$120", "-$45", "+$0"]
    # Net PnL column holds formatted PnL, descending.
    assert by_name["Net PnL"].splitlines()[0].startswith("+$1.5m")


def test_embed_metric_tiles_present():
    snap = _assemble()
    embed = sw.build_status_embed(snap)
    names = [f["name"] for f in embed["fields"]]
    for tile in ("In queue", "Scanned today", "Pending review", "Failed"):
        assert tile in names


# ---------------------------------------------------------------------------
# Best-effort degradation (graceful omission, no raise)
# ---------------------------------------------------------------------------


def test_failed_subqueries_degrade_to_none_and_note():
    responses = _full_responses()
    responses["GROUP BY queue_state"] = None   # queue read fails
    snap = _assemble(responses, loader=make_fake_loader(None))  # leaderboard read fails
    assert snap.in_queue is None
    assert snap.failed is None
    assert snap.top_wallets == []
    assert "queue" in snap.degraded
    assert "topN" in snap.degraded
    # The embed still builds (no raise) and shows em-dash tiles.
    embed = sw.build_status_embed(snap)
    by_name = {f["name"]: f["value"] for f in embed["fields"]}
    assert by_name["In queue"] == sw._ABSENT


def test_daily_pnl_failure_degrades_without_hiding_topn():
    responses = _full_responses()
    responses["FROM polytool.user_pnl_bucket"] = None
    snap = _assemble(responses)
    assert "dailyPnL" in snap.degraded
    assert snap.top_wallets
    assert all(w.daily_pnl is None for w in snap.top_wallets)
    embed = sw.build_status_embed(snap)
    by_name = {f["name"]: f["value"] for f in embed["fields"]}
    assert by_name["Daily PnL"].splitlines() == [sw._ABSENT, sw._ABSENT, sw._ABSENT]


def test_pnl_formatting_thresholds():
    assert sw._fmt_pnl(1_500_000.0) == "+$1.5m"
    assert sw._fmt_pnl(24_000.0) == "+$24.0k"
    assert sw._fmt_pnl(-350.0) == "-$350"


def test_load_top_wallets_from_leaderboard(tmp_path):
    """The loader maps leaderboard.json fields and picks the newest run by mtime."""
    import json as _json

    base = tmp_path / "research" / "wallet_scan" / "2026-06-04"
    older = base / "run-old"
    newer = base / "run-new"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)

    # An older run that should be IGNORED (newer mtime wins).
    (older / "leaderboard.json").write_text(
        _json.dumps({"ranked": [
            {"rank": 1, "identifier": "0xdead", "username": "stale", "realized_net_pnl": 1.0, "positions_total": 1},
        ]}),
        encoding="utf-8",
    )
    # The newest run: matches the real artifact shape (identifier / realized_net_pnl /
    # positions_total / empty username for a pseudonymous wallet).
    (newer / "leaderboard.json").write_text(
        _json.dumps({"ranked": [
            {"rank": 1, "identifier": "0xa380c504a480f591c7dfbf9944fac3994b9b21ff",
             "username": "", "realized_net_pnl": 885464.78, "positions_total": 5},
            {"rank": 2, "identifier": "0xdc71bed951076a6dfd27f6a341c441b8543ed033",
             "username": "JewishNinja", "realized_net_pnl": 193062.65, "positions_total": 4},
        ]}),
        encoding="utf-8",
    )
    # Make the newer file unambiguously the most-recently-modified.
    import os as _os
    _os.utime(older / "leaderboard.json", (1000, 1000))
    _os.utime(newer / "leaderboard.json", (2000, 2000))

    tops = sw.load_top_wallets_from_leaderboard(10, artifacts_root=tmp_path)
    assert tops is not None
    assert [w.wallet_address for w in tops] == [
        "0xa380c504a480f591c7dfbf9944fac3994b9b21ff",
        "0xdc71bed951076a6dfd27f6a341c441b8543ed033",
    ]
    # Lifetime realized PnL (NOT the ~0 day-bucket estimate) + real positions.
    assert tops[0].realized_pnl == 885464.78
    assert tops[0].open_positions == 5
    assert tops[1].open_positions == 4
    # Empty username -> None on the dataclass; the embed applies display_name().
    assert tops[0].username is None
    assert tops[1].username == "JewishNinja"
    # The embed renders the truncated wallet for the blank one, never blank.
    embed = sw.build_status_embed(
        sw.assemble_status(make_fake_query(_full_responses()), now=_NOW,
                           leaderboard_loader=lambda n: tops)
    )
    by_name = {f["name"]: f["value"] for f in embed["fields"]}
    uname_lines = by_name["Username"].splitlines()
    assert uname_lines[0].startswith("0xa380")  # truncated wallet fallback
    assert uname_lines[1] == "JewishNinja"


def test_load_top_wallets_missing_leaderboard_returns_none(tmp_path):
    # No leaderboard.json anywhere under the root -> degraded topN (None), no raise.
    assert sw.load_top_wallets_from_leaderboard(10, artifacts_root=tmp_path) is None


def test_short_addr_truncates():
    addr = "0xaaaa000000000000000000000000000000000001"
    short = sw._short_addr(addr)
    assert short.startswith("0xaaaa")
    assert short.endswith("0001")
    assert len(short) < len(addr)


# ---------------------------------------------------------------------------
# READ-ONLY: the assembler only ever builds SELECTs.
# ---------------------------------------------------------------------------


def test_assembler_emits_only_select_statements():
    seen: list[str] = []

    def _spy(sql: str):
        seen.append(sql)
        return []

    sw.assemble_status(_spy, now=_NOW, leaderboard_loader=make_fake_loader([]))
    assert seen, "expected at least one query"
    import re

    banned = ("INSERT", "ALTER", "UPDATE", "DELETE", "DROP", "CREATE", "TRUNCATE")
    for sql in seen:
        upper = sql.upper()
        assert upper.lstrip().startswith("SELECT"), f"non-SELECT query: {sql}"
        # Whole-word match so identifiers like ``updated_at`` (contains UPDATE)
        # don't false-positive — we only ban the SQL *statement* keywords.
        tokens = set(re.findall(r"[A-Z_]+", upper))
        for word in banned:
            assert word not in tokens, f"banned keyword {word} in: {sql}"


def test_read_status_snapshot_requires_password(monkeypatch):
    monkeypatch.delenv("CLICKHOUSE_PASSWORD", raising=False)
    out = sw.read_status_snapshot(host="localhost", port=8123, user="polytool_admin")
    assert out is None  # fail-fast, no hardcoded fallback


# ---------------------------------------------------------------------------
# Handler tests (require discord) — author-guard + read-only, no buttons.
# ---------------------------------------------------------------------------

discord = pytest.importorskip("discord", reason="requires the [discord] optional dependency")

from packages.polymarket.discord_bot import status_command as sc  # noqa: E402
from packages.polymarket.discord_bot.config import BotConfig, ClickHouseConfig  # noqa: E402

pytestmark = pytest.mark.optional_dep

OPERATOR_ID = 999_000_111


def _config(operator_id=OPERATOR_ID):
    return BotConfig(
        operator_user_id=operator_id,
        guild_id=None,
        clickhouse=ClickHouseConfig(host="clickhouse", port=8123, user="polytool_admin"),
    )


def _interaction(*, user_id):
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    return interaction


def _snapshot():
    return _assemble()


def test_non_operator_status_is_denied_and_reads_nothing():
    interaction = _interaction(user_id=12345)  # not the operator
    reader = MagicMock()  # would be called if guard failed
    asyncio.run(sc.status_command(interaction, config=_config(), reader=reader))

    interaction.response.send_message.assert_awaited_once_with(
        "Not authorized.", ephemeral=True
    )
    # The author-guard fires BEFORE any read — the reader is never invoked.
    reader.assert_not_called()
    interaction.response.defer.assert_not_awaited()


def test_unset_operator_denies_everyone():
    interaction = _interaction(user_id=OPERATOR_ID)
    reader = MagicMock()
    asyncio.run(sc.status_command(interaction, config=_config(operator_id=None), reader=reader))
    interaction.response.send_message.assert_awaited_once_with(
        "Not authorized.", ephemeral=True
    )
    reader.assert_not_called()


def test_operator_status_posts_public_card():
    interaction = _interaction(user_id=OPERATOR_ID)
    reader = MagicMock(return_value=_snapshot())
    asyncio.run(sc.status_command(interaction, config=_config(), reader=reader))

    # Public deferral (thinking=True), then a single embed edit. No buttons, no
    # ephemeral, no followup writes.
    interaction.response.defer.assert_awaited_once_with(thinking=True)
    interaction.edit_original_response.assert_awaited_once()
    kwargs = interaction.edit_original_response.await_args.kwargs
    assert "embed" in kwargs
    assert isinstance(kwargs["embed"], discord.Embed)
    # No action view/buttons are ever attached (read-only command).
    assert "view" not in kwargs


def test_operator_status_handles_unreadable_clickhouse():
    interaction = _interaction(user_id=OPERATOR_ID)
    reader = MagicMock(return_value=None)  # password unset / CH unreachable
    asyncio.run(sc.status_command(interaction, config=_config(), reader=reader))
    interaction.edit_original_response.assert_awaited_once()
    kwargs = interaction.edit_original_response.await_args.kwargs
    assert "content" in kwargs
    assert "Could not read" in kwargs["content"]


def test_status_handler_never_raises_on_reader_exception():
    interaction = _interaction(user_id=OPERATOR_ID)

    def _boom(_config):
        raise RuntimeError("ch exploded")

    # Must not propagate.
    asyncio.run(sc.status_command(interaction, config=_config(), reader=_boom))
    interaction.followup.send.assert_awaited_once()
