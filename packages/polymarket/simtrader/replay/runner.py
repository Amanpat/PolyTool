"""SimTrader replay runner: events.jsonl -> best_bid_ask timeline.

Reads a tape's events.jsonl, drives the L2Book state machine in arrival
order (sorted by seq), and emits one row per book-affecting event.

Output:
  best_bid_ask.jsonl  (default) or  best_bid_ask.csv
  meta.json           — run quality summary + warning log

Run quality is "ok" when no events were skipped; "warnings" otherwise.
"""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Optional

from ..orderbook.l2book import L2Book, L2BookError
from ..tape.schema import EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE

logger = logging.getLogger(__name__)


class ReplayRunner:
    """Drives a deterministic replay of a SimTrader tape.

    Determinism guarantee: given the same events.jsonl, two calls to
    run() will produce byte-identical output files, because:
      1. Events are sorted by seq before processing.
      2. The L2Book is a pure state machine with no randomness.
      3. JSON output is serialized with sorted keys where order matters.
    """

    def __init__(
        self,
        events_path: Path,
        run_dir: Path,
        strict: bool = True,
        output_format: str = "jsonl",
    ) -> None:
        """
        Args:
            events_path:   Path to the events.jsonl tape file.
            run_dir:       Directory for output files (created if absent).
            strict:        If True, raise on missing book snapshot or bad events.
                           If False, log warnings and skip bad events.
            output_format: "jsonl" or "csv".
        """
        self.events_path = events_path
        self.run_dir = run_dir
        self.strict = strict
        self.output_format = output_format

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> Path:
        """Execute the replay and return the path to the output file.

        Raises:
            ValueError: If the tape is empty or contains no events.
            L2BookError: In strict mode, if the tape has missing snapshots.
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

        events = self._load_events()
        if not events:
            raise ValueError(f"No events found in {self.events_path}")

        # Collect all asset IDs present in the tape.
        asset_ids: set[str] = {
            e.get("asset_id", "") for e in events if e.get("asset_id")
        }
        if len(asset_ids) > 1:
            logger.warning(
                "Multiple asset_ids in tape: %s.  Replaying all.", sorted(asset_ids)
            )

        books: dict[str, L2Book] = {
            aid: L2Book(aid, strict=self.strict) for aid in asset_ids
        }

        timeline: list[dict] = []
        warnings: list[str] = []

        for event in events:
            asset_id: str = event.get("asset_id", "")
            event_type: str = event.get("event_type", "")

            if asset_id not in books:
                books[asset_id] = L2Book(asset_id, strict=self.strict)

            try:
                applied = books[asset_id].apply(event)
            except L2BookError as exc:
                msg = f"seq={event.get('seq')}: {exc}"
                if self.strict:
                    raise
                warnings.append(msg)
                logger.warning(msg)
                continue

            # Emit a timeline row only when the event was successfully applied.
            if applied and event_type in (EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE):
                book = books[asset_id]
                timeline.append(
                    {
                        "seq": event.get("seq"),
                        "ts_recv": event.get("ts_recv"),
                        "asset_id": asset_id,
                        "event_type": event_type,
                        "best_bid": book.best_bid,
                        "best_ask": book.best_ask,
                    }
                )

        # Write quality metadata.
        quality = "ok" if not warnings else "warnings"
        meta: dict = {
            "run_quality": quality,
            "events_path": str(self.events_path),
            "total_events": len(events),
            "timeline_rows": len(timeline),
            "warnings": warnings[:50],
        }
        meta_path = self.run_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

        # Write timeline.
        if self.output_format == "csv":
            out_path = self.run_dir / "best_bid_ask.csv"
            self._write_csv(out_path, timeline)
        else:
            out_path = self.run_dir / "best_bid_ask.jsonl"
            self._write_jsonl(out_path, timeline)

        logger.info(
            "Replay complete: %d timeline rows -> %s  (quality=%s)",
            len(timeline),
            out_path,
            quality,
        )
        return out_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_events(self) -> list[dict]:
        """Load events.jsonl and sort by seq for deterministic replay."""
        events: list[dict] = []
        with open(self.events_path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Skipping malformed line %d in %s: %s",
                        lineno,
                        self.events_path,
                        exc,
                    )
        # Sort by seq (monotonic arrival counter); ties are impossible
        # by construction but secondary-sort by lineno is implicit via
        # stable sort preserving file order for equal seqs.
        events.sort(key=lambda e: e.get("seq", 0))
        return events

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict]) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")

    @staticmethod
    def _write_csv(path: Path, rows: list[dict]) -> None:
        fieldnames = ["seq", "ts_recv", "asset_id", "event_type", "best_bid", "best_ask"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            if rows:
                writer.writerows(rows)
