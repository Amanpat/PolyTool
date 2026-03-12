"""WS tape recorder: writes raw_ws.jsonl + events.jsonl.

raw_ws.jsonl  — one line per WS frame, preserving the exact message string.
events.jsonl  — one line per normalized event (one frame may yield N events).
meta.json    — recorder metadata (including reconnect count + warnings).

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
DEFAULT_RECV_TIMEOUT_SECONDS = 5.0
DEFAULT_RECONNECT_SLEEP_SECONDS = 1.0


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
        normalized_asset_ids = [str(asset_id) for asset_id in asset_ids if str(asset_id)]
        if not normalized_asset_ids:
            raise ValueError("asset_ids must include at least one non-empty asset ID")

        seen: set[str] = set()
        self.asset_ids = []
        for asset_id in normalized_asset_ids:
            if asset_id in seen:
                continue
            seen.add(asset_id)
            self.asset_ids.append(asset_id)
        self.strict = strict

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(
        self,
        duration_seconds: Optional[float] = None,
        ws_url: str = WS_MARKET_URL,
        recv_timeout_seconds: float = DEFAULT_RECV_TIMEOUT_SECONDS,
    ) -> None:
        """Connect to the Market Channel and record until done.

        Args:
            duration_seconds: Stop after this many seconds; None = run until signal.
            ws_url:           WebSocket URL to connect to.
            recv_timeout_seconds: Socket recv timeout. Timeout triggers keepalive ping.

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
        timeout_exc = getattr(websocket, "WebSocketTimeoutException", TimeoutError)
        closed_exc = getattr(websocket, "WebSocketConnectionClosedException", OSError)

        self.tape_dir.mkdir(parents=True, exist_ok=True)
        raw_path = self.tape_dir / "raw_ws.jsonl"
        events_path = self.tape_dir / "events.jsonl"
        meta_path = self.tape_dir / "meta.json"

        frame_seq = 0   # increments per WS frame
        event_seq = 0   # increments per normalized event (across all frames)
        deadline = (time.time() + duration_seconds) if duration_seconds else None
        stop = [False]
        reconnect_count = 0
        reconnect_warnings: list[str] = []
        ws: object | None = None

        def _on_signal(sig, frame):  # noqa: ARG001
            logger.info("Received signal %d — stopping recorder.", sig)
            stop[0] = True

        signal.signal(signal.SIGINT, _on_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _on_signal)

        subscribe_msg = json.dumps(
            {
                "assets_ids": self.asset_ids,
                "type": "market",
                "custom_feature_enabled": True,
                "initial_dump": True,
            }
        )

        def _connect_and_subscribe(*, reconnect: bool) -> object | None:
            nonlocal reconnect_count
            while not stop[0]:
                if deadline and time.time() >= deadline:
                    return None
                try:
                    ws_conn = websocket.WebSocket()
                    ws_conn.connect(ws_url)
                    ws_conn.settimeout(recv_timeout_seconds)
                    ws_conn.send(subscribe_msg)
                    if reconnect:
                        reconnect_count += 1
                        warning = (
                            f"WebSocket reconnect #{reconnect_count}: "
                            "connected and resubscribed."
                        )
                        reconnect_warnings.append(warning)
                        logger.warning(warning)
                    else:
                        logger.info("Connected to %s", ws_url)
                        logger.info("Subscribed: %s", subscribe_msg)
                    return ws_conn
                except Exception as exc:  # noqa: BLE001
                    logger.warning("WebSocket connect failed: %s", exc)
                    if self.strict:
                        raise
                    time.sleep(DEFAULT_RECONNECT_SLEEP_SECONDS)
            return None

        def _ping_keepalive(ws_conn: object) -> bool:
            try:
                ping = getattr(ws_conn, "ping", None)
                if callable(ping):
                    ping("simtrader-keepalive")
                    return True
                # websocket-client should expose .ping(); tests may use a minimal fake.
                logger.debug("WebSocket object has no .ping(); skipping keepalive ping.")
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Keepalive ping failed: %s", exc)
                if self.strict:
                    raise
                return False

        with (
            open(raw_path, "w", encoding="utf-8") as raw_fh,
            open(events_path, "w", encoding="utf-8") as events_fh,
        ):
            try:
                ws = _connect_and_subscribe(reconnect=False)
                while not stop[0]:
                    if deadline and time.time() >= deadline:
                        logger.info("Duration expired — stopping recorder.")
                        break

                    if ws is None:
                        ws = _connect_and_subscribe(reconnect=True)
                        if ws is None:
                            break

                    try:
                        raw_msg = ws.recv()
                    except timeout_exc:
                        if ws is not None and not _ping_keepalive(ws):
                            ws = _connect_and_subscribe(reconnect=True)
                            if ws is None:
                                break
                        continue
                    except closed_exc as exc:
                        warning = f"WebSocket disconnected: {exc}"
                        logger.warning("%s", warning)
                        reconnect_warnings.append(warning)
                        if ws is not None:
                            try:
                                ws.close()
                            except Exception:  # noqa: BLE001
                                pass
                        ws = _connect_and_subscribe(reconnect=True)
                        if ws is None:
                            break
                        continue
                    except OSError as exc:
                        warning = f"WebSocket socket error: {exc}"
                        logger.warning("%s", warning)
                        reconnect_warnings.append(warning)
                        if ws is not None:
                            try:
                                ws.close()
                            except Exception:  # noqa: BLE001
                                pass
                        ws = _connect_and_subscribe(reconnect=True)
                        if ws is None:
                            break
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
                if ws is not None:
                    ws.close()

        meta = {
            "ws_url": ws_url,
            "asset_ids": self.asset_ids,
            "recv_timeout_seconds": recv_timeout_seconds,
            "reconnect_count": reconnect_count,
            "frame_count": frame_seq,
            "event_count": event_seq,
            "warnings": reconnect_warnings[:200],
        }
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

        logger.info(
            "Tape written: %d frames / %d events. reconnects=%d raw=%s events=%s meta=%s",
            frame_seq,
            event_seq,
            reconnect_count,
            raw_path,
            events_path,
            meta_path,
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
