"""WI-5 — Vera text-bridge approval emit side (offline).

Covers the pure approval_request module (address validation, command parsing,
author-ID gate, message formatter, dedup state) plus the read-only
read_pending_candidates query builder and the CLI --list-pending / full-address
guards. No network, no real ClickHouse, no Discord.
"""
from __future__ import annotations

import json

import pytest

from packages.polymarket.discovery.approval_request import (
    format_approval_request,
    is_authorized_author,
    is_full_wallet_address,
    load_notified,
    mark_notified,
    notified_path,
    parse_approval_command,
)

_FULL = "0xcf6041b4c3d3c9e1f0a1b2c3d4e5f60718293a4b"  # 0x + 40 hex


# ---------------------------------------------------------------------------
# is_full_wallet_address
# ---------------------------------------------------------------------------


class TestFullWalletAddress:
    def test_accepts_full_42_char(self):
        assert is_full_wallet_address(_FULL)

    def test_accepts_uppercase_hex(self):
        assert is_full_wallet_address("0x" + "ABCDEF0123" * 4)

    def test_tolerates_surrounding_whitespace(self):
        assert is_full_wallet_address(f"  {_FULL}  ")

    def test_rejects_ellipsis_truncation(self):
        assert not is_full_wallet_address("0xcf60…")

    def test_rejects_short_truncation(self):
        assert not is_full_wallet_address("0xcf60")

    def test_rejects_wrong_length(self):
        assert not is_full_wallet_address("0x" + "a" * 39)
        assert not is_full_wallet_address("0x" + "a" * 41)

    def test_rejects_non_hex(self):
        assert not is_full_wallet_address("0x" + "g" * 40)

    def test_rejects_missing_prefix(self):
        assert not is_full_wallet_address("cf6041b4c3d3c9e1f0a1b2c3d4e5f60718293a4b")

    def test_rejects_empty(self):
        assert not is_full_wallet_address("")

    def test_rejects_multiple_tokens(self):
        assert not is_full_wallet_address(f"{_FULL} {_FULL}")

    def test_rejects_non_str(self):
        assert not is_full_wallet_address(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# parse_approval_command
# ---------------------------------------------------------------------------


class TestParseApprovalCommand:
    def test_parse_approve(self):
        assert parse_approval_command(f"approve {_FULL}") == ("approve", _FULL)

    def test_parse_deny(self):
        assert parse_approval_command(f"deny {_FULL}") == ("deny", _FULL)

    def test_verb_case_insensitive(self):
        assert parse_approval_command(f"APPROVE {_FULL}") == ("approve", _FULL)
        assert parse_approval_command(f"Deny {_FULL}") == ("deny", _FULL)

    def test_tolerates_surrounding_whitespace(self):
        assert parse_approval_command(f"   approve   {_FULL}   ") == ("approve", _FULL)

    def test_tolerates_leading_mention(self):
        assert parse_approval_command(f"<@123456789> approve {_FULL}") == ("approve", _FULL)

    def test_rejects_truncated_address(self):
        assert parse_approval_command("approve 0xcf60…") is None
        assert parse_approval_command("approve 0xcf60") is None

    def test_rejects_missing_address(self):
        assert parse_approval_command("approve") is None

    def test_rejects_bad_verb(self):
        assert parse_approval_command(f"yolo {_FULL}") is None

    def test_rejects_extra_tokens(self):
        assert parse_approval_command(f"approve {_FULL} now") is None

    def test_rejects_garbage(self):
        assert parse_approval_command("garbage input here") is None

    def test_rejects_empty(self):
        assert parse_approval_command("") is None

    def test_rejects_non_str(self):
        assert parse_approval_command(None) is None  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# is_authorized_author
# ---------------------------------------------------------------------------


class TestAuthorizedAuthor:
    def test_exact_match(self):
        assert is_authorized_author("12345", "12345")

    def test_mismatch(self):
        assert not is_authorized_author("12345", "99999")

    def test_none_author(self):
        assert not is_authorized_author(None, "12345")

    def test_none_allowed(self):
        assert not is_authorized_author("12345", None)

    def test_both_none(self):
        assert not is_authorized_author(None, None)

    def test_empty_strings(self):
        assert not is_authorized_author("", "")
        assert not is_authorized_author("12345", "")
        assert not is_authorized_author("", "12345")


# ---------------------------------------------------------------------------
# format_approval_request
# ---------------------------------------------------------------------------


class TestFormatApprovalRequest:
    def test_contains_evidence_body(self):
        reason = "+$24.0k PnL, 64% win / 180 trades, CLV 72%, churn-triggered"
        msg = format_approval_request(_FULL, reason)
        assert reason in msg

    def test_contains_full_approve_and_deny_lines(self):
        msg = format_approval_request(_FULL, "x")
        assert f"approve {_FULL}" in msg
        assert f"deny {_FULL}" in msg

    def test_renders_full_address_never_truncates(self):
        msg = format_approval_request(_FULL, "x")
        # full address appears (header + approve + deny = 3 times)
        assert msg.count(_FULL) == 3
        assert "…" not in msg

    def test_empty_evidence_falls_back(self):
        msg = format_approval_request(_FULL, "")
        assert "no evidence available" in msg

    def test_deterministic(self):
        a = format_approval_request(_FULL, "x")
        b = format_approval_request(_FULL, "x")
        assert a == b


# ---------------------------------------------------------------------------
# Dedup state helpers
# ---------------------------------------------------------------------------


class TestDedupState:
    def test_mark_then_load_roundtrip(self, tmp_path):
        p = tmp_path / "notified.json"
        mark_notified(p, _FULL)
        loaded = load_notified(p)
        assert _FULL.lower() in loaded

    def test_mark_lowercases(self, tmp_path):
        p = tmp_path / "notified.json"
        upper = "0x" + "ABCDEF0123" * 4
        mark_notified(p, upper)
        assert upper.lower() in load_notified(p)
        assert upper not in load_notified(p)

    def test_load_missing_file_is_empty(self, tmp_path):
        assert load_notified(tmp_path / "nope.json") == set()

    def test_mark_idempotent(self, tmp_path):
        p = tmp_path / "notified.json"
        mark_notified(p, _FULL)
        mark_notified(p, _FULL)
        assert len(load_notified(p)) == 1

    def test_mark_empty_wallet_noop(self, tmp_path):
        p = tmp_path / "notified.json"
        mark_notified(p, "")
        assert load_notified(p) == set()

    def test_load_malformed_file_is_empty(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert load_notified(p) == set()

    def test_default_notified_path(self):
        p = notified_path()
        assert p.name == "approvals_notified.json"
        assert "watchlists" in str(p)


# ---------------------------------------------------------------------------
# read_pending_candidates query/filter correctness (mocked _get_query)
# ---------------------------------------------------------------------------


class TestReadPendingCandidates:
    def test_strict_filter_query_and_shape(self, monkeypatch):
        import packages.polymarket.discovery.clickhouse_writer as chw

        captured = {}

        def _fake_get_query(sql, **kwargs):
            captured["sql"] = sql
            return json.dumps(
                {
                    "wallet_address": _FULL,
                    "lifecycle_state": "scanned",
                    "review_status": "pending",
                    "tier": "candidate",
                    "locked": 0,
                    "reason": "+$24.0k PnL",
                }
            )

        monkeypatch.setattr(chw, "_get_query", _fake_get_query)
        rows = chw.read_pending_candidates(password="pw")

        sql = captured["sql"]
        assert "tier = 'candidate'" in sql
        assert "review_status = 'pending'" in sql
        assert "locked = 0" in sql
        assert "lifecycle_state = 'scanned'" in sql
        assert len(rows) == 1
        assert rows[0]["wallet_address"] == _FULL
        assert rows[0]["reason"] == "+$24.0k PnL"

    def test_requires_password(self):
        import packages.polymarket.discovery.clickhouse_writer as chw

        with pytest.raises(ValueError):
            chw.read_pending_candidates(password="")

    def test_pre_migration_column_absence_degrades(self, monkeypatch):
        import packages.polymarket.discovery.clickhouse_writer as chw

        calls = []

        def _fake_get_query(sql, **kwargs):
            calls.append(sql)
            # Strict SELECT errors (columns absent) -> None; fallback returns a row.
            if "tier = 'candidate'" in sql:
                return None
            return json.dumps(
                {
                    "wallet_address": _FULL,
                    "lifecycle_state": "scanned",
                    "review_status": "pending",
                }
            )

        monkeypatch.setattr(chw, "_get_query", _fake_get_query)
        rows = chw.read_pending_candidates(password="pw")

        assert len(calls) == 2  # strict then fallback
        assert "tier = 'candidate'" not in calls[1]
        # synthesised stable shape
        assert rows[0]["tier"] == "candidate"
        assert rows[0]["locked"] == 0
        assert rows[0]["reason"] == ""

    def test_empty_result(self, monkeypatch):
        import packages.polymarket.discovery.clickhouse_writer as chw

        monkeypatch.setattr(chw, "_get_query", lambda *a, **k: "")
        assert chw.read_pending_candidates(password="pw") == []


# ---------------------------------------------------------------------------
# CLI: --list-pending / full-address guards (mocked read_pending_candidates)
# ---------------------------------------------------------------------------


class TestListPendingCLI:
    def test_help_shows_list_pending(self, capsys):
        import tools.cli.discovery as disc

        with pytest.raises(SystemExit):
            disc.main(["review", "--help"])
        out = capsys.readouterr().out
        assert "--list-pending" in out

    def test_list_pending_json_shape(self, monkeypatch, capsys):
        import tools.cli.discovery as disc
        import packages.polymarket.discovery.clickhouse_writer as chw

        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "pw")
        monkeypatch.setattr(
            chw,
            "read_pending_candidates",
            lambda **k: [
                {
                    "wallet_address": _FULL,
                    "reason": "+$24.0k PnL",
                    "lifecycle_state": "scanned",
                    "tier": "candidate",
                    "review_status": "pending",
                }
            ],
        )
        rc = disc.main(["review", "--list-pending", "--json"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert len(out) == 1
        item = out[0]
        assert item["wallet_address"] == _FULL
        assert item["evidence"] == "+$24.0k PnL"
        assert item["lifecycle_state"] == "scanned"
        assert f"approve {_FULL}" in item["request_text"]
        assert f"deny {_FULL}" in item["request_text"]

    def test_list_pending_unnotified_only_filters(self, monkeypatch, capsys, tmp_path):
        import tools.cli.discovery as disc
        import packages.polymarket.discovery.clickhouse_writer as chw
        import packages.polymarket.discovery.approval_request as ar

        state = tmp_path / "notified.json"
        # Patch the dedup state file the CLI uses (default path).
        monkeypatch.setattr(ar, "DEFAULT_NOTIFIED_PATH", state)
        ar.mark_notified(None, _FULL)

        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "pw")
        monkeypatch.setattr(
            chw,
            "read_pending_candidates",
            lambda **k: [
                {"wallet_address": _FULL, "reason": "x", "lifecycle_state": "scanned"}
            ],
        )
        rc = disc.main(["review", "--list-pending", "--unnotified-only", "--json"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out == []  # filtered out (already notified)

    def test_approve_without_wallet_errors(self, monkeypatch):
        import tools.cli.discovery as disc

        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "pw")
        rc = disc.main(["review", "--approve"])
        assert rc == 1

    def test_approve_truncated_address_rejected(self, monkeypatch):
        import tools.cli.discovery as disc

        monkeypatch.setenv("CLICKHOUSE_PASSWORD", "pw")
        rc = disc.main(["review", "--approve", "0xcf60…"])
        assert rc == 1

    def test_mark_notified_requires_full_address(self, monkeypatch):
        import tools.cli.discovery as disc

        rc = disc.main(["review", "--mark-notified", "0xcf60"])
        assert rc == 1

    def test_mark_notified_writes_state_only(self, monkeypatch, tmp_path):
        import tools.cli.discovery as disc
        import packages.polymarket.discovery.approval_request as ar

        state = tmp_path / "notified.json"
        monkeypatch.setattr(ar, "DEFAULT_NOTIFIED_PATH", state)
        rc = disc.main(["review", "--mark-notified", _FULL, "--json"])
        assert rc == 0
        assert _FULL.lower() in ar.load_notified(None)
