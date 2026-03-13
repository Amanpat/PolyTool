"""Bulk historical import execution engine for Phase 1.

Modes:
    dry-run  Validates layout, counts files/rows estimates, writes manifest. No CH writes.
    sample   Imports first --sample-rows rows from one file per source kind. CH writes.
    full     Imports all rows from all files. CH writes.

ClickHouse client is injectable for offline testing.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Protocol


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


class ImportMode(str, Enum):
    DRY_RUN = "dry-run"
    SAMPLE = "sample"
    FULL = "full"


_DESTINATION_TABLES: Dict[str, List[str]] = {
    "pmxt_archive": ["polytool.pmxt_l2_snapshots"],
    "jon_becker": ["polytool.jb_trades"],
    "price_history_2min": ["polytool.price_history_2min"],
}

_JON_BECKER_EXTENSIONS = {".parquet", ".csv", ".csv.gz", ".parquet.gz"}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ImportResult:
    source_kind: str
    import_mode: str
    run_id: str
    resolved_source_path: str
    destination_tables: List[str]
    files_processed: int = 0
    files_skipped: int = 0
    rows_loaded: int = 0
    rows_skipped: int = 0
    rows_rejected: int = 0
    import_completeness: str = "dry-run"  # dry-run / complete / partial / failed
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    snapshot_version: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "import_mode": self.import_mode,
            "run_id": self.run_id,
            "resolved_source_path": self.resolved_source_path,
            "destination_tables": list(self.destination_tables),
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "rows_loaded": self.rows_loaded,
            "rows_skipped": self.rows_skipped,
            "rows_rejected": self.rows_rejected,
            "import_completeness": self.import_completeness,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "snapshot_version": self.snapshot_version,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Protocol for CH client (injectable for testing)
# ---------------------------------------------------------------------------


class CHInsertClient(Protocol):
    def insert_rows(self, table: str, column_names: List[str], rows: List[list]) -> int:
        ...


# ---------------------------------------------------------------------------
# Real ClickHouse client wrapper
# ---------------------------------------------------------------------------


class ClickHouseClient:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 8123,
        user: str = "polytool_admin",
        password: str = "polytool_admin",
    ) -> None:
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import clickhouse_connect  # type: ignore
            except ImportError as exc:
                raise ImportError(
                    "clickhouse-connect is required for non-dry-run imports. "
                    "Install it: pip install clickhouse-connect"
                ) from exc
            self._client = clickhouse_connect.get_client(
                host=self._host,
                port=self._port,
                username=self._user,
                password=self._password,
            )
        return self._client

    def insert_rows(self, table: str, column_names: List[str], rows: List[list]) -> int:
        if not rows:
            return 0
        client = self._get_client()
        client.insert(table, rows, column_names=column_names)
        return len(rows)


# ---------------------------------------------------------------------------
# Parquet reading helper
# ---------------------------------------------------------------------------


def _try_import_pyarrow() -> Any:
    """Return pyarrow module or None."""
    try:
        import pyarrow.parquet as pq  # type: ignore
        return pq
    except ImportError:
        return None


def _read_parquet_rows(path: Path) -> Iterator[Dict[str, Any]]:
    pq = _try_import_pyarrow()
    if pq is None:
        raise ImportError(
            "pyarrow is required to read Parquet files. "
            "Install it: pip install pyarrow>=12.0.0  "
            "or: pip install polytool[historical-import]"
        )
    table = pq.read_table(str(path))
    col_names = table.schema.names
    for batch in table.to_batches():
        cols = {name: batch.column(name).to_pylist() for name in col_names}
        n = batch.num_rows
        for i in range(n):
            yield {name: cols[name][i] for name in col_names}


def _read_csv_rows(path: Path) -> Iterator[Dict[str, Any]]:
    """Read a CSV or CSV.GZ file, yielding row dicts."""
    name = path.name.lower()
    if name.endswith(".csv.gz"):
        with gzip.open(str(path), "rt", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield dict(row)
    else:
        with open(str(path), encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                yield dict(row)


def _read_jsonl_rows(path: Path) -> Iterator[Dict[str, Any]]:
    with open(str(path), encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _read_json_rows(path: Path) -> Iterator[Dict[str, Any]]:
    """Read a JSON file (list of objects or single object)."""
    with open(str(path), encoding="utf-8", errors="replace") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
    elif isinstance(data, dict):
        yield data


# ---------------------------------------------------------------------------
# Column mapping helpers
# ---------------------------------------------------------------------------


def _first_col(row: Dict[str, Any], candidates: List[str], default: Any = "") -> Any:
    """Return the first key from candidates that exists in row."""
    for key in candidates:
        if key in row:
            return row[key]
    return default


# ---------------------------------------------------------------------------
# Timestamp helpers
# ---------------------------------------------------------------------------


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# PmxtImporter
# ---------------------------------------------------------------------------


class PmxtImporter:
    """Importer for pmxt archive L2 Parquet snapshots.

    Expected layout:
        <local_path>/
          Polymarket/   <- required
          Kalshi/       <- optional
          Opinion/      <- optional
    """

    _SUBDIRS = ("Polymarket", "Kalshi", "Opinion")
    _PLATFORM_MAP = {
        "polymarket": "polymarket",
        "kalshi": "kalshi",
        "opinion": "opinion",
    }
    _TABLE = "polytool.pmxt_l2_snapshots"
    _COLUMNS = [
        "snapshot_ts", "platform", "market_id", "token_id",
        "side", "price", "size", "source_file", "import_run_id",
    ]

    def __init__(self, local_path: str) -> None:
        self._local_path = Path(local_path).resolve()

    def _find_files(self) -> List[Path]:
        files: List[Path] = []
        for sub in self._SUBDIRS:
            sub_path = self._local_path / sub
            if sub_path.is_dir():
                files.extend(sub_path.rglob("*.parquet"))
        return files

    def _platform_from_path(self, file_path: Path) -> str:
        # Walk up to find which top-level subdirectory this file sits under
        try:
            relative = file_path.relative_to(self._local_path)
            top = relative.parts[0].lower()
            return self._PLATFORM_MAP.get(top, top)
        except ValueError:
            return "unknown"

    def _row_from_record(
        self, record: Dict[str, Any], platform: str, source_file: str, run_id: str
    ) -> list:
        snapshot_ts = str(
            _first_col(record, ["ts", "timestamp", "datetime"], "")
        )
        market_id = str(_first_col(record, ["market_id", "condition_id", "market"], ""))
        token_id = str(_first_col(record, ["token_id", "outcome_token_id", "token"], ""))
        side = str(_first_col(record, ["side", "bid_ask"], ""))
        price = float(_first_col(record, ["price", "p"], 0.0))
        size = float(_first_col(record, ["size", "s", "quantity"], 0.0))
        return [snapshot_ts, platform, market_id, token_id, side, price, size, source_file, run_id]

    def run(
        self,
        mode: ImportMode,
        *,
        ch_client: Any,
        run_id: str,
        sample_rows: int = 1000,
    ) -> ImportResult:
        started_at = _utcnow()
        result = ImportResult(
            source_kind="pmxt_archive",
            import_mode=mode.value,
            run_id=run_id,
            resolved_source_path=str(self._local_path),
            destination_tables=[self._TABLE],
            started_at=started_at,
        )

        if not self._local_path.exists():
            result.errors.append(f"Path does not exist: {self._local_path}")
            result.import_completeness = "failed"
            result.completed_at = _utcnow()
            return result

        files = self._find_files()
        result.files_processed = len(files)

        if mode == ImportMode.DRY_RUN:
            result.import_completeness = "dry-run"
            result.completed_at = _utcnow()
            return result

        # sample or full
        files_to_process = files[:1] if mode == ImportMode.SAMPLE else files

        for file_path in files_to_process:
            source_file = str(file_path)
            platform = self._platform_from_path(file_path)
            try:
                rows_batch: List[list] = []
                for record in _read_parquet_rows(file_path):
                    rows_batch.append(
                        self._row_from_record(record, platform, source_file, run_id)
                    )
                    if mode == ImportMode.SAMPLE and len(rows_batch) >= sample_rows:
                        break

                if rows_batch:
                    loaded = ch_client.insert_rows(self._TABLE, self._COLUMNS, rows_batch)
                    result.rows_loaded += loaded

            except ImportError:
                raise  # re-raise pyarrow missing so caller can report properly
            except Exception as exc:
                result.errors.append(f"{source_file}: {exc}")

        result.import_completeness = "partial" if result.errors else "complete"
        result.completed_at = _utcnow()
        return result


# ---------------------------------------------------------------------------
# JonBeckerImporter
# ---------------------------------------------------------------------------


class JonBeckerImporter:
    """Importer for Jon-Becker trade dataset.

    Expected layout:
        <local_path>/data/polymarket/trades/
    """

    _TABLE = "polytool.jb_trades"
    _COLUMNS = [
        "ts", "platform", "market_id", "token_id", "price", "size",
        "taker_side", "resolution", "category", "source_file", "import_run_id",
    ]
    _EXTENSIONS = {".parquet", ".csv", ".csv.gz", ".parquet.gz"}

    def __init__(self, local_path: str) -> None:
        self._local_path = Path(local_path).resolve()

    def _find_files(self) -> List[Path]:
        base = self._local_path / "data" / "polymarket" / "trades"
        if not base.is_dir():
            return []
        return [
            f for f in base.rglob("*")
            if f.is_file() and any(str(f.name).endswith(ext) for ext in self._EXTENSIONS)
        ]

    def _row_from_record(
        self, record: Dict[str, Any], source_file: str, run_id: str
    ) -> list:
        ts = str(_first_col(record, ["timestamp", "ts", "time", "t"], ""))
        market_id = str(_first_col(record, ["market_id", "condition_id"], ""))
        token_id = str(_first_col(record, ["token_id", "outcome_token_id"], ""))
        price = float(_first_col(record, ["price", "p"], 0.0))
        size = float(_first_col(record, ["size", "s", "amount"], 0.0))
        taker_side = str(_first_col(record, ["taker_side", "side"], ""))
        resolution = str(_first_col(record, ["resolution", "resolved", "outcome"], ""))
        category = str(_first_col(record, ["category", "cat"], ""))
        platform = "polymarket"
        return [ts, platform, market_id, token_id, price, size, taker_side, resolution, category, source_file, run_id]

    def _iter_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        name = file_path.name.lower()
        if name.endswith(".parquet.gz"):
            # Not directly supported; try parquet after noting it
            raise ImportError(
                f"Compressed Parquet ({file_path.name}) is not directly supported. "
                "Decompress first or use pyarrow with native support."
            )
        elif name.endswith(".parquet"):
            yield from _read_parquet_rows(file_path)
        elif name.endswith(".csv.gz") or name.endswith(".csv"):
            yield from _read_csv_rows(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {file_path.name}")

    def run(
        self,
        mode: ImportMode,
        *,
        ch_client: Any,
        run_id: str,
        sample_rows: int = 1000,
    ) -> ImportResult:
        started_at = _utcnow()
        result = ImportResult(
            source_kind="jon_becker",
            import_mode=mode.value,
            run_id=run_id,
            resolved_source_path=str(self._local_path),
            destination_tables=[self._TABLE],
            started_at=started_at,
        )

        if not self._local_path.exists():
            result.errors.append(f"Path does not exist: {self._local_path}")
            result.import_completeness = "failed"
            result.completed_at = _utcnow()
            return result

        files = self._find_files()
        result.files_processed = len(files)

        if mode == ImportMode.DRY_RUN:
            result.import_completeness = "dry-run"
            result.completed_at = _utcnow()
            return result

        # sample: one file; full: all files
        files_to_process = files[:1] if mode == ImportMode.SAMPLE else files

        for file_path in files_to_process:
            source_file = str(file_path)
            try:
                rows_batch: List[list] = []
                for record in self._iter_file(file_path):
                    rows_batch.append(self._row_from_record(record, source_file, run_id))
                    if mode == ImportMode.SAMPLE and len(rows_batch) >= sample_rows:
                        break

                if rows_batch:
                    loaded = ch_client.insert_rows(self._TABLE, self._COLUMNS, rows_batch)
                    result.rows_loaded += loaded

            except ImportError:
                raise
            except Exception as exc:
                result.errors.append(f"{source_file}: {exc}")

        result.import_completeness = "partial" if result.errors else "complete"
        result.completed_at = _utcnow()
        return result


# ---------------------------------------------------------------------------
# PriceHistoryImporter
# ---------------------------------------------------------------------------


class PriceHistoryImporter:
    """Importer for 2-minute price history JSONL/CSV files.

    Expected layout:
        <local_path>/
          <token_id>.jsonl   <- one file per token
          <token_id>.csv     <- alternative format
    """

    _TABLE = "polytool.price_history_2min"
    _COLUMNS = ["token_id", "ts", "price", "source", "import_run_id"]

    def __init__(self, local_path: str) -> None:
        self._local_path = Path(local_path).resolve()

    def _find_files(self) -> List[Path]:
        if not self._local_path.is_dir():
            return []
        files: List[Path] = []
        for ext in ("*.jsonl", "*.csv", "*.json"):
            files.extend(self._local_path.rglob(ext))
        return files

    def _iter_file(self, file_path: Path) -> Iterator[Dict[str, Any]]:
        name = file_path.name.lower()
        if name.endswith(".jsonl"):
            yield from _read_jsonl_rows(file_path)
        elif name.endswith(".json"):
            yield from _read_json_rows(file_path)
        elif name.endswith(".csv"):
            yield from _read_csv_rows(file_path)
        else:
            raise ValueError(f"Unsupported file extension: {file_path.name}")

    def _token_id_from_path(self, file_path: Path) -> str:
        """Extract token_id from filename (without extension)."""
        name = file_path.name
        # Strip known extensions
        for ext in (".jsonl", ".json", ".csv"):
            if name.endswith(ext):
                return name[: -len(ext)]
        return file_path.stem

    def _row_from_record(
        self, record: Dict[str, Any], token_id: str, run_id: str
    ) -> list:
        ts = str(_first_col(record, ["t", "timestamp", "time"], ""))
        price = float(_first_col(record, ["p", "price", "mid"], 0.0))
        source = "polymarket_apis"
        return [token_id, ts, price, source, run_id]

    def run(
        self,
        mode: ImportMode,
        *,
        ch_client: Any,
        run_id: str,
        sample_rows: int = 1000,
    ) -> ImportResult:
        started_at = _utcnow()
        result = ImportResult(
            source_kind="price_history_2min",
            import_mode=mode.value,
            run_id=run_id,
            resolved_source_path=str(self._local_path),
            destination_tables=[self._TABLE],
            started_at=started_at,
        )

        if not self._local_path.exists():
            result.errors.append(f"Path does not exist: {self._local_path}")
            result.import_completeness = "failed"
            result.completed_at = _utcnow()
            return result

        files = self._find_files()
        result.files_processed = len(files)

        if mode == ImportMode.DRY_RUN:
            result.import_completeness = "dry-run"
            result.completed_at = _utcnow()
            return result

        # sample: one file; full: all files
        files_to_process = files[:1] if mode == ImportMode.SAMPLE else files

        for file_path in files_to_process:
            source_file = str(file_path)
            token_id = self._token_id_from_path(file_path)
            try:
                rows_batch: List[list] = []
                for record in self._iter_file(file_path):
                    rows_batch.append(self._row_from_record(record, token_id, run_id))
                    if mode == ImportMode.SAMPLE and len(rows_batch) >= sample_rows:
                        break

                if rows_batch:
                    loaded = ch_client.insert_rows(self._TABLE, self._COLUMNS, rows_batch)
                    result.rows_loaded += loaded

            except Exception as exc:
                result.errors.append(f"{source_file}: {exc}")

        result.import_completeness = "partial" if result.errors else "complete"
        result.completed_at = _utcnow()
        return result


# ---------------------------------------------------------------------------
# Dispatch function
# ---------------------------------------------------------------------------

_IMPORTER_MAP = {
    "pmxt_archive": PmxtImporter,
    "jon_becker": JonBeckerImporter,
    "price_history_2min": PriceHistoryImporter,
}


def run_import(
    source_kind: str,
    local_path: str,
    mode: ImportMode,
    *,
    ch_client: Any = None,
    run_id: Optional[str] = None,
    sample_rows: int = 1000,
    snapshot_version: str = "",
    notes: str = "",
) -> ImportResult:
    """Dispatch import to the correct importer class.

    Args:
        source_kind: One of 'pmxt_archive', 'jon_becker', 'price_history_2min'.
        local_path: Path to the data directory.
        mode: ImportMode enum value.
        ch_client: Injectable ClickHouse client (required for non-dry-run).
        run_id: Optional run identifier. Auto-generated UUID if None.
        sample_rows: Row limit for SAMPLE mode.
        snapshot_version: Optional version label for provenance.
        notes: Optional free-form notes.

    Returns:
        ImportResult with counts, errors, and completeness status.

    Raises:
        ValueError: If source_kind is unknown.
    """
    if source_kind not in _IMPORTER_MAP:
        raise ValueError(
            f"Unknown source_kind {source_kind!r}. "
            f"Valid values: {sorted(_IMPORTER_MAP.keys())}"
        )

    if run_id is None:
        run_id = str(uuid.uuid4())

    importer_cls = _IMPORTER_MAP[source_kind]
    importer = importer_cls(local_path)
    result = importer.run(mode, ch_client=ch_client, run_id=run_id, sample_rows=sample_rows)
    result.snapshot_version = snapshot_version
    result.notes = notes
    return result
