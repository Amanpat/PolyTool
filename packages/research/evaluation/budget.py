"""RIS daily budget tracker for cloud provider API calls.

Tracks per-provider request counts in a local JSON file.
Resets automatically when the calendar date changes.

Local providers (manual, ollama) are uncapped — they have no API cost.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

_LOCAL_PROVIDERS = frozenset({"manual", "ollama"})

_DEFAULT_TRACKER_PATH = (
    Path(__file__).resolve().parents[3] / "artifacts" / "research" / "budget_tracker.json"
)


def load_budget_tracker(tracker_path: Optional[Path] = None) -> dict:
    """Load today's budget tracker, resetting counts if the date has changed.

    Returns a dict with keys:
      "date": ISO date string (today)
      "counts": {provider_name: int, ...}
    """
    path = tracker_path or _DEFAULT_TRACKER_PATH
    today = date.today().isoformat()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("date") == today:
                if not isinstance(raw.get("counts"), dict):
                    raw["counts"] = {}
                return raw
        except (json.JSONDecodeError, OSError):
            pass
    return {"date": today, "counts": {}}


def save_budget_tracker(tracker: dict, tracker_path: Optional[Path] = None) -> None:
    """Persist the tracker dict to disk."""
    path = tracker_path or _DEFAULT_TRACKER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tracker, indent=2), encoding="utf-8")


def is_budget_available(
    provider_name: str,
    daily_cap: Optional[int],
    tracker: dict,
) -> bool:
    """Return True if the provider has remaining budget.

    Local providers (manual, ollama) are always available regardless of cap.
    A cap of None means uncapped.
    """
    if provider_name in _LOCAL_PROVIDERS:
        return True
    if daily_cap is None:
        return True
    used = tracker.get("counts", {}).get(provider_name, 0)
    return used < daily_cap


def increment_provider_count(provider_name: str, tracker: dict) -> dict:
    """Increment the call count for provider_name in tracker (mutates in place).

    Local providers are not counted (no cost).

    Returns the mutated tracker dict for convenience.
    """
    if provider_name in _LOCAL_PROVIDERS:
        return tracker
    counts = tracker.setdefault("counts", {})
    counts[provider_name] = counts.get(provider_name, 0) + 1
    return tracker
