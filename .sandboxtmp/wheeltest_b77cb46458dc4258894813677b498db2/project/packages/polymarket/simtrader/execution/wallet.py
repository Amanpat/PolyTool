"""CLOB wallet helpers for the live execution layer.

Required environment variables
-------------------------------
PK
    Ethereum private key (hex, with or without 0x prefix).  Used to derive
    the on-chain address and sign CLOB authentication payloads.

CLOB_API_KEY
    API key returned by ``derive_and_print_creds`` on first run.

CLOB_API_SECRET
    API secret returned by ``derive_and_print_creds`` on first run.

CLOB_API_PASSPHRASE
    API passphrase returned by ``derive_and_print_creds`` on first run.

Never commit these values.  Store them in a ``.env`` file (gitignored) and
load them with ``python-dotenv`` or equivalent.
"""

from __future__ import annotations

import os

CHAIN_ID = 137  # Polygon mainnet
HOST = "https://clob.polymarket.com"


def _require_clob_client():
    """Import ClobClient or raise a helpful ImportError."""
    try:
        from py_clob_client.client import ClobClient  # type: ignore[import]

        return ClobClient
    except ModuleNotFoundError as exc:
        raise ImportError(
            "py_clob_client is not installed.  Install it with:\n"
            "  pip install py-clob-client\n"
            "or add it to your project dependencies."
        ) from exc


def build_client():
    """Build and return an authenticated ClobClient from environment variables.

    Reads ``PK`` from the environment.  The remaining CLOB credentials
    (``CLOB_API_KEY``, ``CLOB_API_SECRET``, ``CLOB_API_PASSPHRASE``) are
    optional at construction time but required for order placement — call
    ``derive_and_print_creds`` once to generate them.

    Returns:
        ClobClient instance connected to Polygon mainnet.

    Raises:
        ImportError: If ``py_clob_client`` is not installed.
        KeyError:    If the ``PK`` environment variable is not set.
    """
    ClobClient = _require_clob_client()

    pk = os.environ["PK"]  # raises KeyError with a clear message if absent

    api_key = os.environ.get("CLOB_API_KEY")
    api_secret = os.environ.get("CLOB_API_SECRET")
    api_passphrase = os.environ.get("CLOB_API_PASSPHRASE")

    if api_key and api_secret and api_passphrase:
        return ClobClient(
            HOST,
            key=pk,
            chain_id=CHAIN_ID,
            creds={
                "apiKey": api_key,
                "secret": api_secret,
                "passphrase": api_passphrase,
            },
        )

    # No credentials yet — return an unauthenticated client suitable for
    # calling derive_and_print_creds().
    return ClobClient(HOST, key=pk, chain_id=CHAIN_ID)


def derive_and_print_creds(client) -> dict:
    """Derive API credentials from the wallet and print them to stdout.

    Call this once after ``build_client()`` to generate the three credential
    values.  Copy them into your ``.env`` file, then restart with all four
    environment variables set.

    Args:
        client: ClobClient instance (from ``build_client()``).

    Returns:
        Dict with keys ``apiKey``, ``secret``, ``passphrase``.

    Raises:
        ImportError: If ``py_clob_client`` is not installed.
    """
    _require_clob_client()  # ensure package present before proceeding

    creds = client.derive_api_key()
    print("=== CLOB API Credentials (store in .env — never commit) ===")
    print(f"CLOB_API_KEY={creds['apiKey']}")
    print(f"CLOB_API_SECRET={creds['secret']}")
    print(f"CLOB_API_PASSPHRASE={creds['passphrase']}")
    print("===========================================================")
    return creds
