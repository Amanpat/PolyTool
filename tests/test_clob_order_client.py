"""Offline tests for clob_order_client — no real API calls.

All tests mock py_clob_client via sys.modules patching so the test suite
runs without py-clob-client installed in the base environment.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out py_clob_client before any module-level imports that might trigger
# the deferred import path.  This ensures offline test isolation even when
# py-clob-client is not installed.
# ---------------------------------------------------------------------------
_mock_clob_module = MagicMock()
_mock_clob_types = MagicMock()
_mock_clob_ob_constants = MagicMock()
_mock_clob_ob = MagicMock()

# Constants that place_limit_order uses at runtime
_mock_clob_ob_constants.BUY = "BUY"
_mock_clob_ob_constants.SELL = "SELL"

for _mod_name, _mod in [
    ("py_clob_client", _mock_clob_module),
    ("py_clob_client.client", _mock_clob_module),
    ("py_clob_client.clob_types", _mock_clob_types),
    ("py_clob_client.order_builder", _mock_clob_ob),
    ("py_clob_client.order_builder.constants", _mock_clob_ob_constants),
]:
    sys.modules.setdefault(_mod_name, _mod)


# Now it is safe to import the module under test.
from packages.polymarket.crypto_pairs.clob_order_client import (  # noqa: E402
    ClobOrderClientConfig,
    ClobOrderClientConfigError,
    PolymarketClobOrderClient,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def _full_env(monkeypatch):
    """Monkeypatch all four required env vars to placeholder values."""
    monkeypatch.setenv("PK", "abc123privatekey")
    monkeypatch.setenv("CLOB_API_KEY", "myapikey")
    monkeypatch.setenv("CLOB_API_SECRET", "myapisecret")
    monkeypatch.setenv("CLOB_API_PASSPHRASE", "mypassphrase")


@pytest.fixture()
def _mock_clob_client():
    """Return a MagicMock that acts as the py_clob_client ClobClient instance."""
    mock = MagicMock()
    mock.create_order.return_value = MagicMock()  # signed order stub
    mock.post_order.return_value = {"orderID": "ord-abc", "status": "LIVE"}
    mock.cancel.return_value = {"cancelled": True, "order_id": "ord-abc"}
    return mock


# ---------------------------------------------------------------------------
# Test 1 — config_from_env_missing_key
# ---------------------------------------------------------------------------

def test_config_from_env_missing_key(monkeypatch):
    """Missing PK env var raises ClobOrderClientConfigError listing the missing key."""
    for var in ("PK", "CLOB_API_KEY", "CLOB_API_SECRET", "CLOB_API_PASSPHRASE"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ClobOrderClientConfigError, match="PK"):
        ClobOrderClientConfig.from_env()


# ---------------------------------------------------------------------------
# Test 2 — config_from_env_success
# ---------------------------------------------------------------------------

def test_config_from_env_success(_full_env):
    """All four required env vars present — config fields match env values."""
    config = ClobOrderClientConfig.from_env()
    assert config.private_key == "abc123privatekey"
    assert config.api_key == "myapikey"
    assert config.api_secret == "myapisecret"
    assert config.api_passphrase == "mypassphrase"
    assert config.clob_api_base == "https://clob.polymarket.com"


# ---------------------------------------------------------------------------
# Test 3 — place_limit_order_returns_dict
# ---------------------------------------------------------------------------

def test_place_limit_order_returns_dict(_mock_clob_client):
    """place_limit_order returns the dict from the CLOB API response."""
    config = ClobOrderClientConfig(
        private_key="key",
        api_key="k",
        api_secret="s",
        api_passphrase="p",
    )

    client = PolymarketClobOrderClient.__new__(PolymarketClobOrderClient)
    client._config = config
    client._client = _mock_clob_client

    request = MagicMock()
    request.side = "BUY"
    request.price = 0.45
    request.size = 10.0
    request.token_id = "tok123"

    result = client.place_limit_order(request)

    assert isinstance(result, dict)
    assert result.get("orderID") == "ord-abc"
    _mock_clob_client.create_order.assert_called_once()
    _mock_clob_client.post_order.assert_called_once()


# ---------------------------------------------------------------------------
# Test 4 — cancel_order_returns_dict
# ---------------------------------------------------------------------------

def test_cancel_order_returns_dict(_mock_clob_client):
    """cancel_order returns the dict from the CLOB API cancel response."""
    config = ClobOrderClientConfig(
        private_key="key",
        api_key="k",
        api_secret="s",
        api_passphrase="p",
    )

    client = PolymarketClobOrderClient.__new__(PolymarketClobOrderClient)
    client._config = config
    client._client = _mock_clob_client

    result = client.cancel_order("ord-abc")

    assert isinstance(result, dict)
    _mock_clob_client.cancel.assert_called_once_with("ord-abc")


# ---------------------------------------------------------------------------
# Test 5 — live_runner_refuses_without_key
# ---------------------------------------------------------------------------

def test_live_runner_refuses_without_key(monkeypatch):
    """ClobOrderClientConfig.from_env() raises ValueError before any runner starts."""
    for var in ("PK", "CLOB_API_KEY", "CLOB_API_SECRET", "CLOB_API_PASSPHRASE"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(ValueError, match="PK"):
        ClobOrderClientConfig.from_env()


# ---------------------------------------------------------------------------
# Test 6 — trade_event_logging
# ---------------------------------------------------------------------------

def test_trade_event_logging(tmp_path):
    """_log_trade_event writes one JSONL line per call and appends on subsequent calls."""
    from packages.polymarket.crypto_pairs.live_runner import _log_trade_event

    # First event — place
    event_place = {
        "action": "place",
        "market_id": "btc-up-5m",
        "order_id": "ord001",
        "accepted": True,
        "submitted": True,
        "reason": "",
    }
    _log_trade_event(tmp_path, event_place)

    log_path = tmp_path / "trade_log.jsonl"
    assert log_path.exists(), "trade_log.jsonl should be created after first event"

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["action"] == "place"
    assert parsed["market_id"] == "btc-up-5m"
    assert "logged_at" in parsed

    # Second event — cancel (appended)
    event_cancel = {
        "action": "cancel",
        "market_id": "btc-up-5m",
        "order_id": "ord001",
        "accepted": True,
        "submitted": True,
        "reason": "",
    }
    _log_trade_event(tmp_path, event_cancel)

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    parsed2 = json.loads(lines[1])
    assert parsed2["action"] == "cancel"
    assert "logged_at" in parsed2
