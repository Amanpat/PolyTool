"""
tape_validator.py -- Post-capture tape validation for Gate 2 structural fitness.

Validates a newly captured tape directory to determine whether it has the L2
book data required for fill-based Gate 2 evaluation. This is a fast, lightweight
structural pre-check that runs inline after every shadow capture.

Does NOT: run arb eligibility checks (those require strategy config), modify any
file, touch benchmark manifests, call network APIs, or import heavy dependencies.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TapeValidationResult:
    tape_dir: str
    verdict: str              # "PASS", "BLOCKED", "WARN"
    reason: str               # human-readable explanation
    events_total: int         # raw parsed event count
    effective_events: int     # events // asset_count
    asset_count: int
    has_l2_book: bool         # at least one event_type == "book"
    has_price_change: bool    # at least one event_type == "price_change"
    has_watch_meta: bool
    has_meta_json: bool
    event_type_counts: dict = field(default_factory=dict)  # {event_type: count}


def validate_captured_tape(
    tape_dir: Path,
    min_effective_events: int = 50,
) -> TapeValidationResult:
    """Validate a newly captured tape directory for Gate 2 structural fitness.

    Returns a TapeValidationResult with a verdict of PASS, BLOCKED, or WARN.

    Verdict priorities:
    - BLOCKED: missing events.jsonl, no L2 book events, or empty tape
    - WARN: low effective event count or missing watch_meta.json
    - PASS: tape has L2 book data and sufficient effective events

    Args:
        tape_dir: Path to the tape directory (containing events.jsonl etc.)
        min_effective_events: Minimum effective events required for PASS (default 50)

    Returns:
        TapeValidationResult dataclass with verdict and diagnostics
    """
    tape_dir = Path(tape_dir)
    events_path = tape_dir / "events.jsonl"
    meta_path = tape_dir / "meta.json"
    watch_meta_path = tape_dir / "watch_meta.json"

    has_meta_json = meta_path.exists()
    has_watch_meta = watch_meta_path.exists()

    # Check 1: events.jsonl must exist
    if not events_path.exists():
        return TapeValidationResult(
            tape_dir=str(tape_dir),
            verdict="BLOCKED",
            reason="no events.jsonl found",
            events_total=0,
            effective_events=0,
            asset_count=0,
            has_l2_book=False,
            has_price_change=False,
            has_watch_meta=has_watch_meta,
            has_meta_json=has_meta_json,
            event_type_counts={},
        )

    # Parse events.jsonl line by line (streaming -- never load full file)
    parsed_events = 0
    asset_ids: set[str] = set()
    event_type_counts: dict[str, int] = {}

    try:
        with open(events_path, encoding="utf-8") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue

                parsed_events += 1

                # Track event types
                event_type = event.get("event_type")
                if event_type is not None:
                    event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1

                # Track asset IDs (top-level and batched price_changes[])
                asset_id = event.get("asset_id")
                if asset_id and isinstance(asset_id, str):
                    asset_ids.add(asset_id)
                for entry in event.get("price_changes", []):
                    if not isinstance(entry, dict):
                        continue
                    entry_asset_id = entry.get("asset_id")
                    if entry_asset_id and isinstance(entry_asset_id, str):
                        asset_ids.add(entry_asset_id)
    except OSError:
        # File unreadable -- treat as empty
        pass

    asset_count = max(1, len(asset_ids))
    effective_events = (
        parsed_events
        if asset_count == 1
        else parsed_events // asset_count
    )

    has_l2_book = event_type_counts.get("book", 0) > 0
    has_price_change = event_type_counts.get("price_change", 0) > 0

    # Evaluate verdict -- BLOCKED checks first, then WARN, then PASS

    # BLOCKED: empty tape
    if parsed_events == 0:
        return TapeValidationResult(
            tape_dir=str(tape_dir),
            verdict="BLOCKED",
            reason="empty tape -- no parseable events",
            events_total=0,
            effective_events=0,
            asset_count=len(asset_ids),
            has_l2_book=False,
            has_price_change=False,
            has_watch_meta=has_watch_meta,
            has_meta_json=has_meta_json,
            event_type_counts=event_type_counts,
        )

    # BLOCKED: no L2 book events
    if not has_l2_book:
        return TapeValidationResult(
            tape_dir=str(tape_dir),
            verdict="BLOCKED",
            reason=(
                "price-only tape -- no L2 book events, fill engine will reject "
                "all orders with book_not_initialized"
            ),
            events_total=parsed_events,
            effective_events=effective_events,
            asset_count=asset_count,
            has_l2_book=False,
            has_price_change=has_price_change,
            has_watch_meta=has_watch_meta,
            has_meta_json=has_meta_json,
            event_type_counts=event_type_counts,
        )

    # WARN checks -- collect all warn reasons
    warn_reasons: list[str] = []

    if effective_events < min_effective_events:
        warn_reasons.append(
            f"tape has only {effective_events} effective events, "
            f"need >= {min_effective_events} for Gate 2 corpus admission"
        )

    if not has_watch_meta:
        warn_reasons.append(
            "missing watch_meta.json -- corpus audit may not assign a bucket label"
        )

    if warn_reasons:
        return TapeValidationResult(
            tape_dir=str(tape_dir),
            verdict="WARN",
            reason="; ".join(warn_reasons),
            events_total=parsed_events,
            effective_events=effective_events,
            asset_count=asset_count,
            has_l2_book=has_l2_book,
            has_price_change=has_price_change,
            has_watch_meta=has_watch_meta,
            has_meta_json=has_meta_json,
            event_type_counts=event_type_counts,
        )

    # PASS
    return TapeValidationResult(
        tape_dir=str(tape_dir),
        verdict="PASS",
        reason=f"tape has {effective_events} effective events with L2 book data",
        events_total=parsed_events,
        effective_events=effective_events,
        asset_count=asset_count,
        has_l2_book=True,
        has_price_change=has_price_change,
        has_watch_meta=has_watch_meta,
        has_meta_json=has_meta_json,
        event_type_counts=event_type_counts,
    )
