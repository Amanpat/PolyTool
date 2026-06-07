#!/usr/bin/env python3
"""scan-status reader for the wallet-discovery day run (DR-1).

Terminal complement to the Discord ``/status`` card. Prints, in order:

  1. Docker container state for the three day-run services
     (``clickhouse``, ``api``, ``discovery-scheduler``) via ``docker compose ps``.
  2. Current scan-queue depth (pending items awaiting a drain) read from
     ClickHouse, REUSING ``ScanQueueManager.load_from_clickhouse`` +
     ``get_pending`` (the same readers the worker uses).
  3. Watchlist pending count (candidate-tier rows awaiting the human gate),
     REUSING ``clickhouse_writer.read_pending_candidates`` -- the same reader the
     Discord notify path uses.

READ-ONLY. This never writes ClickHouse, never advances any lifecycle, and never
invokes ``docker compose down`` / ``-v``. It only reads container state and the
ClickHouse counts via the existing reader functions (no SQL is written here).

ClickHouse credentials: ``CLICKHOUSE_PASSWORD`` is read from the environment. For
a status snapshot this is fail-SOFT (not fail-fast): if the password is absent
the ClickHouse reads are skipped (state-only) with a clear note, so the
container-state section still works without creds. The underlying readers
(which DO touch ClickHouse) still enforce the project's password requirement.

Usage:
    python scripts/scan_status.py
    python -m scripts.scan_status         # if run as a module

Invoked by ``scripts/scan.sh status`` (the canonical wrapper).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Ensure the project root is importable for ``packages.*`` when run directly.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# The three day-run services this toggle manages. Kept in sync with
# scripts/scan.sh and docker-compose.yml.
DAY_RUN_SERVICES = ["clickhouse", "api", "discovery-scheduler"]


def _print_container_state() -> None:
    """Print ``docker compose ps`` for the three day-run services.

    Non-fatal: if Docker / compose is unavailable we say so and continue to the
    ClickHouse reads (which may themselves fail, that is fine -- status is a
    best-effort snapshot).
    """
    print("== Services (docker compose ps) ==")
    try:
        proc = subprocess.run(
            ["docker", "compose", "ps", *DAY_RUN_SERVICES],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print("  docker not found on PATH -- cannot read container state.")
        print("")
        return
    except Exception as exc:  # pragma: no cover - defensive
        print(f"  could not read container state: {exc}")
        print("")
        return

    out = (proc.stdout or "").rstrip()
    err = (proc.stderr or "").rstrip()
    if out:
        for line in out.splitlines():
            print(f"  {line}")
    if not out and err:
        print(f"  {err}")
    if not out and not err:
        print("  (no output -- services may be down)")
    print("")


def _read_clickhouse_counts() -> int:
    """Print scan-queue depth + watchlist pending count from ClickHouse.

    Returns a process-style int: 0 on success (or clean skip), 1 if a reader
    raised unexpectedly. Reuses existing readers only.
    """
    print("== ClickHouse reads ==")

    password = os.environ.get("CLICKHOUSE_PASSWORD", "")
    if not password:
        # Fail-soft for status (not fail-fast): the container-state section is
        # still useful without creds. State-only with a clear note.
        print("  CLICKHOUSE_PASSWORD not set -- skipping queue/pending reads.")
        print("  (set CLICKHOUSE_PASSWORD to see scan-queue depth + pending count)")
        print("")
        return 0

    host = os.environ.get("CLICKHOUSE_HOST", "localhost")
    port = int(os.environ.get("CLICKHOUSE_HTTP_PORT", "8123"))
    user = os.environ.get("CLICKHOUSE_USER", "polytool_admin")

    rc = 0

    # --- Scan-queue depth (REUSE ScanQueueManager.load_from_clickhouse) ---
    try:
        from packages.polymarket.discovery.scan_queue import ScanQueueManager

        queue = ScanQueueManager()
        loaded = queue.load_from_clickhouse(
            host=host, port=port, user=user, password=password
        )
        pending_items = queue.get_pending(limit=1_000_000)
        print(f"  scan_queue: loaded={loaded} rows, pending(available)={len(pending_items)}")
    except Exception as exc:
        print(f"  scan_queue: ERROR reading queue depth: {exc}")
        rc = 1

    # --- Watchlist pending count (REUSE read_pending_candidates) ---
    try:
        from packages.polymarket.discovery.clickhouse_writer import (
            read_pending_candidates,
        )

        pending_rows = read_pending_candidates(
            host=host, port=port, user=user, password=password
        )
        print(f"  watchlist: pending_review(candidate)={len(pending_rows)}")
    except Exception as exc:
        print(f"  watchlist: ERROR reading pending candidates: {exc}")
        rc = 1

    print("")
    return rc


def main(argv: list[str] | None = None) -> int:
    """Print the day-run status snapshot. Returns a process exit code."""
    print("PolyTool scan status (DR-1) -- READ ONLY")
    print("")
    _print_container_state()
    return _read_clickhouse_counts()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
