"""Silver tape reconstruction foundation v0.

Reconstructs a Silver-tier deterministic tape for a single market/token over a
bounded time window using three source tiers:

  1. pmxt anchor  — DuckDB reads pmxt Parquet snapshots; nearest L2 book state
                    at or before window_start.
  2. Jon-Becker   — DuckDB reads Jon-Becker trade Parquet/CSV; fills within the
                    window applied chronologically as trade events.
  3. price_2min   — ClickHouse reads polytool.price_2min; 2-minute midpoint
                    series used as a constraint/guide, NOT as fake tick data.

Database split (v4.2 rule):
  DuckDB = historical Parquet reads (pmxt, Jon-Becker)
  ClickHouse = live streaming writes (price_2min)
  The two databases never share data and never communicate.

Confidence model:
  "high"   — pmxt anchor + Jon fills + price_2min all present
  "medium" — pmxt anchor + at least one of (Jon fills OR price_2min)
  "low"    — exactly one source contributed data
  "none"   — no data from any source

Warnings are emitted (not exceptions) for:
  - Missing pmxt anchor (confidence degraded)
  - Missing Jon fills (confidence degraded)
  - Missing price_2min (confidence degraded)
  - Jon timestamp ambiguity (bucketized or non-unique timestamps flagged)
  - pmxt token column not found (cannot query)

Usage::

    from packages.polymarket.silver_reconstructor import SilverReconstructor, ReconstructConfig

    config = ReconstructConfig(
        pmxt_root="/data/raw/pmxt_archive",
        jon_root="/data/raw/jon_becker",
    )
    rec = SilverReconstructor(config)
    result = rec.reconstruct(
        token_id="0xabc...",
        window_start=1700000000.0,
        window_end=1700007200.0,
        out_dir=Path("artifacts/tapes/silver/0xabc/2023-11"),
    )
    print(result.reconstruction_confidence, result.warnings)
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from packages.polymarket.simtrader.tape.schema import PARSER_VERSION as _TAPE_PARSER_VERSION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SILVER_SCHEMA_VERSION = "silver_tape_v0"

# Silver-specific event type for price_2min midpoint guides.
# This does NOT appear in KNOWN_EVENT_TYPES (live WS schema) by design;
# ReplayRunner will skip it, which is correct — it is not fake tick data.
EVENT_TYPE_PRICE_2MIN_GUIDE = "price_2min_guide"

# Column name candidates (mirrors smoke-historical heuristics)
_PMXT_TOKEN_CANDIDATES = ["token_id", "asset_id", "condition_id", "market_id"]
_PMXT_TS_CANDIDATES = [
    "snapshot_ts", "timestamp_received", "timestamp_created_at",
    "ts", "timestamp", "datetime",
]
_JON_TOKEN_CANDIDATES = ["asset_id", "token_id", "market_id", "condition_id"]
_JON_TS_CANDIDATES = ["timestamp", "ts", "time", "t", "_fetched_at"]
_JON_PRICE_CANDIDATES = ["price", "p", "trade_price"]
_JON_SIZE_CANDIDATES = ["size", "amount", "quantity", "qty"]
_JON_SIDE_CANDIDATES = ["side", "trade_side", "direction"]

_PRICE_2MIN_TABLE = "polytool.price_2min"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class ReconstructConfig:
    """Configuration for SilverReconstructor.

    Attributes:
        pmxt_root:          Root of the pmxt_archive dataset. Expects a
                            Polymarket/ subdirectory with .parquet files.
                            None disables pmxt source.
        jon_root:           Root of the jon_becker dataset. Expects
                            data/polymarket/trades/ with Parquet/CSV files.
                            None disables Jon-Becker source.
        clickhouse_host:    ClickHouse host for price_2min reads.
        clickhouse_port:    ClickHouse HTTP port.
        clickhouse_user:    ClickHouse username.
        clickhouse_password: ClickHouse password.
        skip_price_2min:    When True, skip the ClickHouse price_2min query
                            entirely (useful for offline testing or when CH
                            is not available).
    """

    pmxt_root: Optional[str] = None
    jon_root: Optional[str] = None
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "polytool_admin"
    clickhouse_password: str = ""
    skip_price_2min: bool = False


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class SourceInputs:
    """Summary of which sources contributed data to the reconstruction."""

    pmxt_anchor_found: bool = False
    pmxt_anchor_ts: Optional[str] = None
    pmxt_columns_found: List[str] = field(default_factory=list)
    jon_fill_count: int = 0
    jon_columns_found: List[str] = field(default_factory=list)
    price_2min_count: int = 0


@dataclass
class SilverResult:
    """Outcome of a single Silver tape reconstruction run.

    Attributes:
        run_id:                    UUID for this reconstruction run.
        token_id:                  The market/token that was reconstructed.
        window_start:              Window start as Unix epoch float.
        window_end:                Window end as Unix epoch float.
        reconstruction_confidence: "high" | "medium" | "low" | "none".
        warnings:                  List of human-readable warning messages.
        event_count:               Total events emitted to silver_events.jsonl.
        fill_count:                Jon-Becker fill events emitted.
        price_2min_count:          price_2min_guide events emitted.
        source_inputs:             Per-source contribution summary.
        out_dir:                   Output directory path (None if dry_run).
        events_path:               Path to silver_events.jsonl (None if dry_run).
        meta_path:                 Path to silver_meta.json (None if dry_run).
        error:                     Top-level error string, or None on success.
    """

    run_id: str
    token_id: str
    window_start: float
    window_end: float
    reconstruction_confidence: str
    warnings: List[str]
    event_count: int
    fill_count: int
    price_2min_count: int
    source_inputs: SourceInputs
    out_dir: Optional[Path]
    events_path: Optional[Path]
    meta_path: Optional[Path]
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SILVER_SCHEMA_VERSION,
            "run_id": self.run_id,
            "token_id": self.token_id,
            "window_start": _ts_to_iso(self.window_start),
            "window_end": _ts_to_iso(self.window_end),
            "reconstruction_confidence": self.reconstruction_confidence,
            "warnings": list(self.warnings),
            "event_count": self.event_count,
            "fill_count": self.fill_count,
            "price_2min_count": self.price_2min_count,
            "source_inputs": {
                "pmxt_anchor_found": self.source_inputs.pmxt_anchor_found,
                "pmxt_anchor_ts": self.source_inputs.pmxt_anchor_ts,
                "pmxt_columns_found": list(self.source_inputs.pmxt_columns_found),
                "jon_fill_count": self.source_inputs.jon_fill_count,
                "jon_columns_found": list(self.source_inputs.jon_columns_found),
                "price_2min_count": self.source_inputs.price_2min_count,
            },
            "out_dir": str(self.out_dir) if self.out_dir else None,
            "events_path": str(self.events_path) if self.events_path else None,
            "meta_path": str(self.meta_path) if self.meta_path else None,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ts_to_iso(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return str(ts)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _detect_col(columns: List[str], candidates: List[str]) -> Optional[str]:
    """Return first matching column name from candidates (case-insensitive)."""
    lower_map = {c.lower(): c for c in columns}
    for cand in candidates:
        match = lower_map.get(cand.lower())
        if match is not None:
            return match
    return None


def _compute_confidence(inputs: SourceInputs) -> str:
    """Derive reconstruction_confidence from source availability."""
    has_anchor = inputs.pmxt_anchor_found
    has_fills = inputs.jon_fill_count > 0
    has_price = inputs.price_2min_count > 0

    sources_present = sum([has_anchor, has_fills, has_price])

    if sources_present == 3:
        return "high"
    if has_anchor and sources_present >= 2:
        return "medium"
    if sources_present == 1:
        return "low"
    return "none"


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_float_ts(value: Any) -> Optional[float]:
    """Convert a DB timestamp (datetime object, ISO str, or epoch float) to Unix float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, datetime):
        return value.timestamp()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            pass
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# DuckDB column detection helpers
# ---------------------------------------------------------------------------


def _parquet_columns(conn: Any, ddb_glob: str) -> Optional[List[str]]:
    try:
        rel = conn.execute(
            f"SELECT * FROM read_parquet('{ddb_glob}', union_by_name=true) LIMIT 0"
        )
        return [d[0] for d in rel.description]
    except Exception:
        return None


def _csv_columns(conn: Any, ddb_glob: str) -> Optional[List[str]]:
    try:
        rel = conn.execute(
            f"SELECT * FROM read_csv('{ddb_glob}', auto_detect=true) LIMIT 0"
        )
        return [d[0] for d in rel.description]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Default (real) fetch functions
# ---------------------------------------------------------------------------


def _real_fetch_pmxt_anchor(
    pmxt_root: str,
    token_id: str,
    window_start: float,
) -> Optional[Dict[str, Any]]:
    """Fetch the pmxt L2 snapshot nearest/before window_start for token_id.

    Returns a raw column->value dict for the matching row, or None.
    """
    from packages.polymarket import duckdb_helper as dh

    root = Path(pmxt_root).resolve()
    glob = str(root / "Polymarket" / "**" / "*.parquet").replace("\\", "/")

    try:
        with dh.connection() as conn:
            columns = _parquet_columns(conn, glob)
            if columns is None:
                logger.warning("pmxt: no readable parquet files at %s", glob)
                return None

            token_col = _detect_col(columns, _PMXT_TOKEN_CANDIDATES)
            ts_col = _detect_col(columns, _PMXT_TS_CANDIDATES)

            if not token_col:
                logger.warning(
                    "pmxt: no token column detected (tried: %s); columns: %s",
                    _PMXT_TOKEN_CANDIDATES, columns[:20],
                )
                return None
            if not ts_col:
                logger.warning(
                    "pmxt: no timestamp column detected (tried: %s); columns: %s",
                    _PMXT_TS_CANDIDATES, columns[:20],
                )
                return None

            read_expr = f"read_parquet('{glob}', union_by_name=true)"
            query = (
                f'SELECT * FROM {read_expr} '
                f'WHERE "{token_col}" = ? AND "{ts_col}" <= ? '
                f'ORDER BY "{ts_col}" DESC LIMIT 1'
            )
            # Try ISO timestamp first, then epoch float
            for ts_param in [_ts_to_iso(window_start), window_start]:
                try:
                    row = conn.execute(query, [token_id, ts_param]).fetchone()
                    if row is not None:
                        return dict(zip(columns, row))
                except Exception:
                    continue
            return None

    except Exception as exc:
        logger.warning("pmxt: connection/query error: %s", exc)
        return None


def _real_fetch_jon_fills(
    jon_root: str,
    token_id: str,
    window_start: float,
    window_end: float,
) -> List[Dict[str, Any]]:
    """Fetch Jon-Becker fills for token_id within [window_start, window_end].

    Returns list of raw column->value dicts sorted by timestamp, or [].
    """
    from packages.polymarket import duckdb_helper as dh

    root = Path(jon_root).resolve()
    trades_dir = root / "data" / "polymarket" / "trades"

    parquet_files = list(trades_dir.rglob("*.parquet")) if trades_dir.is_dir() else []
    csv_files = list(trades_dir.rglob("*.csv")) if trades_dir.is_dir() else []

    if parquet_files:
        glob = str(trades_dir / "**" / "*.parquet").replace("\\", "/")
        read_expr = f"read_parquet('{glob}', union_by_name=true)"
        get_cols = _parquet_columns
    elif csv_files:
        glob = str(trades_dir / "**" / "*.csv").replace("\\", "/")
        read_expr = f"read_csv('{glob}', auto_detect=true)"
        get_cols = _csv_columns
    else:
        logger.warning("jon: no parquet or csv files under %s", trades_dir)
        return []

    try:
        with dh.connection() as conn:
            columns = get_cols(conn, glob)
            if columns is None:
                logger.warning("jon: could not read schema from %s", glob)
                return []

            token_col = _detect_col(columns, _JON_TOKEN_CANDIDATES)
            ts_col = _detect_col(columns, _JON_TS_CANDIDATES)

            # Detect maker/taker schema (Jon-Becker real dataset uses
            # maker_asset_id + taker_asset_id instead of a single asset_id)
            _col_lower = {c.lower(): c for c in columns}
            _maker_col = _col_lower.get("maker_asset_id")
            _taker_col = _col_lower.get("taker_asset_id")
            _maker_taker = bool(_maker_col and _taker_col)

            if not ts_col or (not token_col and not _maker_taker):
                logger.warning(
                    "jon: missing required columns. token_col=%s ts_col=%s in %s",
                    token_col, ts_col, columns[:20],
                )
                return []

            if _maker_taker and not token_col:
                query = (
                    f'SELECT * FROM {read_expr} '
                    f'WHERE ("{_maker_col}" = ? OR "{_taker_col}" = ?) '
                    f'AND "{ts_col}" >= ? AND "{ts_col}" <= ? '
                    f'ORDER BY "{ts_col}" ASC'
                )
                params_prefix: List[Any] = [token_id, token_id]
            else:
                query = (
                    f'SELECT * FROM {read_expr} '
                    f'WHERE "{token_col}" = ? AND "{ts_col}" >= ? AND "{ts_col}" <= ? '
                    f'ORDER BY "{ts_col}" ASC'
                )
                params_prefix = [token_id]

            for ts_start, ts_end in [
                (_ts_to_iso(window_start), _ts_to_iso(window_end)),
                (window_start, window_end),
            ]:
                try:
                    rows = conn.execute(query, params_prefix + [ts_start, ts_end]).fetchall()
                    return [dict(zip(columns, r)) for r in rows]
                except Exception:
                    continue
            return []

    except Exception as exc:
        logger.warning("jon: connection/query error: %s", exc)
        return []


def _real_fetch_price_2min(
    token_id: str,
    window_start: float,
    window_end: float,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str = "",
) -> List[Dict[str, Any]]:
    """Fetch price_2min rows from ClickHouse for token_id within the window.

    Returns list of {"ts": float_epoch, "price": float} dicts sorted by ts.
    Uses the ClickHouse HTTP interface at port 8123 with JSONEachRow output.
    """
    try:
        import requests

        query = (
            f"SELECT toUnixTimestamp(ts) AS ts, price "
            f"FROM {_PRICE_2MIN_TABLE} "
            f"WHERE token_id = '{token_id}' "
            f"AND ts >= toDateTime({int(window_start)}) "
            f"AND ts <= toDateTime({int(window_end)}) "
            f"ORDER BY ts ASC "
            f"FORMAT JSONEachRow"
        )
        resp = requests.get(
            f"http://{clickhouse_host}:{clickhouse_port}/",
            params={"query": query},
            auth=(clickhouse_user, clickhouse_password),
            timeout=30,
        )
        resp.raise_for_status()
        rows = []
        for line in resp.text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
    except Exception as exc:
        logger.warning("price_2min: ClickHouse query failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Event builders
# ---------------------------------------------------------------------------


def _build_pmxt_anchor_event(
    seq: int,
    token_id: str,
    row: Dict[str, Any],
    columns: List[str],
) -> Dict[str, Any]:
    """Convert a pmxt anchor row into a Silver book event.

    Emits a synthetic "book" event with whatever L2 state the pmxt snapshot
    provides.  Unknown columns are included as raw fields so no data is lost.
    """
    ts_col = _detect_col(columns, _PMXT_TS_CANDIDATES)
    raw_ts = row.get(ts_col) if ts_col else None
    ts_recv = _to_float_ts(raw_ts) or 0.0

    event = {
        "parser_version": _TAPE_PARSER_VERSION,
        "seq": seq,
        "ts_recv": ts_recv,
        "event_type": "book",
        "asset_id": token_id,
        "silver_source": "pmxt_anchor",
        # Include all raw pmxt fields for transparency; consumers can ignore unknowns.
        "pmxt_raw": {k: str(v) for k, v in row.items() if v is not None},
    }
    return event


def _build_jon_fill_event(
    seq: int,
    token_id: str,
    row: Dict[str, Any],
    columns: List[str],
) -> Dict[str, Any]:
    """Convert a Jon-Becker fill row into a Silver last_trade_price event."""
    ts_col = _detect_col(columns, _JON_TS_CANDIDATES)
    raw_ts = row.get(ts_col) if ts_col else None
    ts_recv = _to_float_ts(raw_ts) or 0.0

    price_col = _detect_col(columns, _JON_PRICE_CANDIDATES)
    size_col = _detect_col(columns, _JON_SIZE_CANDIDATES)
    side_col = _detect_col(columns, _JON_SIDE_CANDIDATES)

    price = _safe_float(row.get(price_col) if price_col else None)
    size = _safe_float(row.get(size_col) if size_col else None)
    side = str(row.get(side_col, "")) if side_col else ""

    event = {
        "parser_version": _TAPE_PARSER_VERSION,
        "seq": seq,
        "ts_recv": ts_recv,
        "event_type": "last_trade_price",
        "asset_id": token_id,
        "price": price,
        "size": size,
        "side": side,
        "silver_source": "jon_fill",
    }
    return event


def _build_price_2min_guide_event(
    seq: int,
    token_id: str,
    row: Dict[str, Any],
) -> Dict[str, Any]:
    """Convert a price_2min row into a Silver price_2min_guide event.

    This event type is Silver-specific.  It is NOT fake tick data — it
    represents the 2-minute midpoint constraint series and should be used
    as a constraint/guide only, never as a synthetic fill.
    """
    raw_ts = row.get("ts")
    ts_recv = _to_float_ts(raw_ts) or 0.0
    price = _safe_float(row.get("price"))

    return {
        "parser_version": _TAPE_PARSER_VERSION,
        "seq": seq,
        "ts_recv": ts_recv,
        "event_type": EVENT_TYPE_PRICE_2MIN_GUIDE,
        "asset_id": token_id,
        "price": price,
        "silver_source": "price_2min",
        "note": "2-min midpoint constraint; NOT synthetic tick data",
    }


# ---------------------------------------------------------------------------
# Warning helpers
# ---------------------------------------------------------------------------


def _check_jon_timestamp_ambiguity(fills: List[Dict[str, Any]], columns: List[str]) -> Optional[str]:
    """Detect bucketized or non-unique timestamps in Jon fills.

    Returns a warning string if ambiguity is detected, else None.
    """
    ts_col = _detect_col(columns, _JON_TS_CANDIDATES)
    if not ts_col or not fills:
        return None

    timestamps = [str(r.get(ts_col, "")) for r in fills]
    unique_ts = len(set(timestamps))
    total = len(timestamps)
    if unique_ts < total:
        dup_count = total - unique_ts
        return (
            f"jon_timestamp_ambiguity: {dup_count}/{total} fills share non-unique "
            f"timestamps in column '{ts_col}'. Fill ordering within equal-timestamp "
            "buckets is deterministic (file order) but not clock-accurate."
        )
    return None


# ---------------------------------------------------------------------------
# Core reconstructor
# ---------------------------------------------------------------------------


# Type aliases for injectable fetch functions
PmxtFetchFn = Callable[[str, str, float], Optional[Dict[str, Any]]]
# (pmxt_root, token_id, window_start) -> Optional[row dict]

JonFetchFn = Callable[[str, str, float, float], List[Dict[str, Any]]]
# (jon_root, token_id, window_start, window_end) -> list of row dicts

Price2minFetchFn = Callable[[str, float, float], List[Dict[str, Any]]]
# (token_id, window_start, window_end) -> list of {ts, price} dicts


class SilverReconstructor:
    """Reconstruct a Silver tape for one market/token over a bounded window.

    All three fetch functions are injectable for offline testing:
        _pmxt_fetch_fn, _jon_fetch_fn, _price_2min_fetch_fn

    When not injected, the real DuckDB + ClickHouse implementations are used.

    Args:
        config:             ReconstructConfig with source roots and CH settings.
        _pmxt_fetch_fn:     Override pmxt anchor fetch (for testing).
        _jon_fetch_fn:      Override Jon fill fetch (for testing).
        _price_2min_fetch_fn: Override price_2min fetch (for testing).
    """

    def __init__(
        self,
        config: Optional[ReconstructConfig] = None,
        *,
        _pmxt_fetch_fn: Optional[PmxtFetchFn] = None,
        _jon_fetch_fn: Optional[JonFetchFn] = None,
        _price_2min_fetch_fn: Optional[Price2minFetchFn] = None,
    ) -> None:
        self._config = config or ReconstructConfig()
        self._pmxt_fetch_fn = _pmxt_fetch_fn
        self._jon_fetch_fn = _jon_fetch_fn
        self._price_2min_fetch_fn = _price_2min_fetch_fn

    def reconstruct(
        self,
        token_id: str,
        window_start: float,
        window_end: float,
        out_dir: Optional[Path] = None,
        *,
        run_id: Optional[str] = None,
        dry_run: bool = False,
    ) -> SilverResult:
        """Reconstruct a Silver tape for the given token and time window.

        Args:
            token_id:     Polymarket CLOB token ID (hex string).
            window_start: Window start as Unix epoch seconds (float).
            window_end:   Window end as Unix epoch seconds (float).
            out_dir:      Directory to write silver_events.jsonl + silver_meta.json.
                          If None and dry_run=False, a ValueError is raised.
            run_id:       Optional run identifier (auto-generated UUID if None).
            dry_run:      When True, run all fetch logic but skip disk writes.

        Returns:
            SilverResult with confidence, warnings, event counts, and paths.
        """
        if run_id is None:
            run_id = str(uuid.uuid4())

        if not dry_run and out_dir is None:
            return SilverResult(
                run_id=run_id,
                token_id=token_id,
                window_start=window_start,
                window_end=window_end,
                reconstruction_confidence="none",
                warnings=[],
                event_count=0,
                fill_count=0,
                price_2min_count=0,
                source_inputs=SourceInputs(),
                out_dir=None,
                events_path=None,
                meta_path=None,
                error="out_dir is required when dry_run=False",
            )

        warnings: List[str] = []
        inputs = SourceInputs()
        events: List[Dict[str, Any]] = []
        seq = 0

        # --- Source 1: pmxt anchor ---
        pmxt_row: Optional[Dict[str, Any]] = None
        pmxt_columns: List[str] = []
        if self._config.pmxt_root:
            fetch_fn = self._pmxt_fetch_fn or (
                lambda root, tid, ws: _real_fetch_pmxt_anchor(root, tid, ws)
            )
            pmxt_row = fetch_fn(self._config.pmxt_root, token_id, window_start)
            if pmxt_row is not None:
                pmxt_columns = list(pmxt_row.keys())
                inputs.pmxt_anchor_found = True
                raw_ts = pmxt_row.get(
                    _detect_col(pmxt_columns, _PMXT_TS_CANDIDATES) or ""
                )
                inputs.pmxt_anchor_ts = str(raw_ts) if raw_ts is not None else None
                inputs.pmxt_columns_found = pmxt_columns
                anchor_event = _build_pmxt_anchor_event(seq, token_id, pmxt_row, pmxt_columns)
                events.append(anchor_event)
                seq += 1
            else:
                warnings.append(
                    "pmxt_anchor_missing: no pmxt snapshot found at or before "
                    f"window_start={_ts_to_iso(window_start)} for token {token_id}. "
                    "The book state at window open is unknown; confidence is degraded."
                )
        else:
            warnings.append(
                "pmxt_root_not_configured: pmxt source skipped. "
                "Set ReconstructConfig.pmxt_root to enable anchor state."
            )

        # --- Source 2: Jon-Becker fills ---
        jon_fills: List[Dict[str, Any]] = []
        jon_columns: List[str] = []
        if self._config.jon_root:
            fetch_fn = self._jon_fetch_fn or (
                lambda root, tid, ws, we: _real_fetch_jon_fills(root, tid, ws, we)
            )
            jon_fills = fetch_fn(self._config.jon_root, token_id, window_start, window_end)
            if jon_fills:
                jon_columns = list(jon_fills[0].keys())
                inputs.jon_fill_count = len(jon_fills)
                inputs.jon_columns_found = jon_columns
                # Check for timestamp ambiguity before emitting
                ts_ambiguity = _check_jon_timestamp_ambiguity(jon_fills, jon_columns)
                if ts_ambiguity:
                    warnings.append(ts_ambiguity)
                for fill_row in jon_fills:
                    fill_event = _build_jon_fill_event(seq, token_id, fill_row, jon_columns)
                    events.append(fill_event)
                    seq += 1
            else:
                warnings.append(
                    f"jon_fills_missing: no Jon-Becker fills found for token {token_id} "
                    f"in window [{_ts_to_iso(window_start)}, {_ts_to_iso(window_end)}]. "
                    "Fill events omitted; confidence is degraded."
                )
        else:
            warnings.append(
                "jon_root_not_configured: Jon-Becker source skipped. "
                "Set ReconstructConfig.jon_root to enable fill events."
            )

        # --- Source 3: price_2min (ClickHouse) ---
        price_rows: List[Dict[str, Any]] = []
        if not self._config.skip_price_2min:
            fetch_fn = self._price_2min_fetch_fn or (
                lambda tid, ws, we: _real_fetch_price_2min(
                    tid, ws, we,
                    self._config.clickhouse_host,
                    self._config.clickhouse_port,
                    self._config.clickhouse_user,
                    self._config.clickhouse_password,
                )
            )
            price_rows = fetch_fn(token_id, window_start, window_end)
            if price_rows:
                inputs.price_2min_count = len(price_rows)
                for price_row in price_rows:
                    guide_event = _build_price_2min_guide_event(seq, token_id, price_row)
                    events.append(guide_event)
                    seq += 1
            else:
                warnings.append(
                    f"price_2min_missing: no price_2min rows found for token {token_id} "
                    f"in window [{_ts_to_iso(window_start)}, {_ts_to_iso(window_end)}]. "
                    "Run 'fetch-price-2min --token-id <ID>' to populate this table. "
                    "Midpoint constraint series omitted; confidence is degraded."
                )
        else:
            warnings.append(
                "price_2min_skipped: ClickHouse price_2min query disabled via skip_price_2min=True."
            )

        # Sort events by ts_recv for deterministic output
        events.sort(key=lambda e: (e.get("ts_recv", 0.0), e.get("seq", 0)))
        # Re-assign seq after sort to ensure monotonic ordering
        for i, evt in enumerate(events):
            evt["seq"] = i

        # Compute confidence
        confidence = _compute_confidence(inputs)

        fill_count = inputs.jon_fill_count
        price_2min_count = inputs.price_2min_count
        event_count = len(events)

        # Write output
        events_path: Optional[Path] = None
        meta_path: Optional[Path] = None

        if not dry_run and out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            events_path = out_dir / "silver_events.jsonl"
            meta_path = out_dir / "silver_meta.json"

            with open(events_path, "w", encoding="utf-8") as fh:
                for evt in events:
                    fh.write(json.dumps(evt) + "\n")

            result_stub = SilverResult(
                run_id=run_id,
                token_id=token_id,
                window_start=window_start,
                window_end=window_end,
                reconstruction_confidence=confidence,
                warnings=warnings,
                event_count=event_count,
                fill_count=fill_count,
                price_2min_count=price_2min_count,
                source_inputs=inputs,
                out_dir=out_dir,
                events_path=events_path,
                meta_path=meta_path,
            )
            meta_path.write_text(
                json.dumps(result_stub.to_dict(), indent=2, default=str) + "\n",
                encoding="utf-8",
            )

        return SilverResult(
            run_id=run_id,
            token_id=token_id,
            window_start=window_start,
            window_end=window_end,
            reconstruction_confidence=confidence,
            warnings=warnings,
            event_count=event_count,
            fill_count=fill_count,
            price_2min_count=price_2min_count,
            source_inputs=inputs,
            out_dir=out_dir if not dry_run else None,
            events_path=events_path,
            meta_path=meta_path,
        )
