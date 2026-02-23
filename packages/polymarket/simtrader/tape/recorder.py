"""WS tape recorder: writes raw_ws.jsonl + events.jsonl.

raw_ws.jsonl  — one line per WS frame, preserving the exact message string.
events.jsonl  — one line per normalized event (one frame may yield N events).

Both files use newline-delimited JSON for streaming append safety.
"""

from __future__ import annotations

import json
import logging
import signal
import time
from pathlib import Path
from typing import Optional

from .schema import KNOWN_EVENT_TYPES, PARSER_VERSION

logger = logging.getLogger(__name__)

WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class TapeRecorder:
    """Records Polymarket Market Channel WS messages to a tape directory.

    Output layout (tape_dir/):
        raw_ws.jsonl    — exact WS frames: {"frame_seq": N, "ts_recv": F, "raw": "..."}
        events.jsonl    — normalized events with parser_version + seq envelope
    """

    def __init__(
        self,
        tape_dir: Path,
        asset_ids: list[str],
        strict: bool = False,
    ) -> None:
        """
        Args:
            tape_dir:   Directory to write tape files into (created if absent).
            asset_ids:  Token/asset IDs to subscribe to on the Market Channel.
            strict:     If True, raise on unexpected message shapes instead of warning.
        """
        self.tape_dir = tape_dir
        self.asset_ids = asset_ids
        self.strict = strict

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        duration_seconds: Optional[float] = None,
        ws_url: str = WS_MARKET_URL,
    ) -> None:
        """Connect to the Market Channel and record until done.

        Args:
            duration_seconds: Stop after this many seconds; None = run until signal.
            ws_url:           WebSocket URL to connect to.

        Raises:
            ImportError: If websocket-client is not installed.
        """
        try:
            import websocket  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "websocket-client is required for recording. "
                "Run: pip install 'websocket-client>=1.6'"
            ) from exc

        self.tape_dir.mkdir(parents=True, exist_ok=True)
        raw_path = self.tape_dir / "raw_ws.jsonl"
        events_path = self.tape_dir / "events.jsonl"

        frame_seq = 0   # increments per WS frame
        event_seq = 0   # increments per normalized event (across all frames)
        deadline = (time.time() + duration_seconds) if duration_seconds else None
        stop = [False]

        def _on_signal(sig, frame):  # noqa: ARG001
            logger.info("Received signal %d — stopping recorder.", sig)
            stop[0] = True

        signal.signal(signal.SIGINT, _on_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _on_signal)

        with (
            open(raw_path, "w", encoding="utf-8") as raw_fh,
            open(events_path, "w", encoding="utf-8") as events_fh,
        ):
            ws = websocket.WebSocket()
            ws.connect(ws_url)
            logger.info("Connected to %s", ws_url)

            subscribe_msg = json.dumps(
                {"assets_ids": self.asset_ids, "type": "market"}
            )
            ws.send(subscribe_msg)
            logger.info("Subscribed: %s", subscribe_msg)

            try:
                while not stop[0]:
                    if deadline and time.time() >= deadline:
                        logger.info("Duration expired — stopping recorder.")
                        break

                    ws.settimeout(1.0)
                    try:
                        raw_msg = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        continue

                    ts_recv = time.time()

                    # --- raw frame ---
                    raw_line = {"frame_seq": frame_seq, "ts_recv": ts_recv, "raw": raw_msg}
                    raw_fh.write(json.dumps(raw_line) + "\n")
                    raw_fh.flush()

                    # --- normalize + write events ---
                    try:
                        parsed = json.loads(raw_msg)
                        if not isinstance(parsed, list):
                            parsed = [parsed]
                        for evt in parsed:
                            normalized = self._normalize(evt, event_seq, ts_recv)
                            if normalized is not None:
                                events_fh.write(json.dumps(normalized) + "\n")
                                events_fh.flush()
                                event_seq += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Failed to parse frame frame_seq=%d: %s  (raw=%r)",
                            frame_seq,
                            exc,
                            raw_msg[:200],
                        )
                        if self.strict:
                            raise

                    frame_seq += 1
            finally:
                ws.close()

        logger.info(
            "Tape written: %d frames / %d events.  raw=%s  events=%s",
            frame_seq,
            event_seq,
            raw_path,
            events_path,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize(
        self, evt: object, seq: int, ts_recv: float
    ) -> Optional[dict]:
        """Normalize a parsed WS event object into a tape event dict.

        Returns None (and optionally warns) for unknown event types.
        Raises ValueError in strict mode for unknown types.
        """
        if not isinstance(evt, dict):
            logger.warning("Expected dict event, got %r — skipping.", type(evt))
            return None

        event_type = evt.get("event_type") or evt.get("type")

        if event_type not in KNOWN_EVENT_TYPES:
            if self.strict:
                raise ValueError(f"Unknown event_type: {event_type!r}")
            logger.debug("Skipping unknown event_type: %r", event_type)
            return None

        return {
            "parser_version": PARSER_VERSION,
            "seq": seq,
            "ts_recv": ts_recv,
            **evt,
        }
