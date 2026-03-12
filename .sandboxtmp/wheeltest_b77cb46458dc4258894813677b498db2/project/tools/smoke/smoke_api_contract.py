"""Minimal API contract smoke check.

Assumes the stack is already running.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _post(url: str, payload: dict, timeout: int = 30) -> tuple[int, str]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def _assert_not_5xx(status: int, label: str) -> None:
    if status >= 500:
        raise RuntimeError(f"{label} returned {status}")


def main() -> int:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    user = os.getenv("TARGET_USER", "@432614799197")
    bucket = os.getenv("PNL_BUCKET", "day")

    health_status, health_body = _get(f"{base_url}/health")
    print(f"/health => {health_status} {health_body}")
    _assert_not_5xx(health_status, "/health")

    pnl_payload = {"user": user, "bucket": bucket}
    pnl_status, pnl_body = _post(f"{base_url}/api/compute/pnl", pnl_payload)
    print(f"/api/compute/pnl => {pnl_status} {pnl_body[:300]}")
    _assert_not_5xx(pnl_status, "/api/compute/pnl")

    arb_max_tokens = int(os.getenv("ARB_MAX_TOKENS_SMOKE", "50"))
    arb_payload = {"user": user, "bucket": bucket, "max_tokens": arb_max_tokens}
    arb_status, arb_body = _post(
        f"{base_url}/api/compute/arb_feasibility",
        arb_payload,
        timeout=60,
    )
    print(f"/api/compute/arb_feasibility => {arb_status} {arb_body[:300]}")
    _assert_not_5xx(arb_status, "/api/compute/arb_feasibility")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Smoke check failed: {exc}")
        sys.exit(1)
