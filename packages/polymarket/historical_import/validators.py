"""Local-path layout validators for bulk historical import sources.

Each validator inspects the filesystem only (no file content reads,
no network calls) and returns a ValidationResult. Designed for --dry-run
mode: tells the operator whether their downloaded dataset has the
expected layout before any import is attempted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class ValidationResult:
    source_kind: str
    local_path: str
    valid: bool
    file_count: int = 0
    checksum: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: str = ""


def _file_list_checksum(paths: List[Path]) -> str:
    """Deterministic checksum: sha256 of sorted file names."""
    names = sorted(p.name for p in paths)
    raw = "\n".join(names).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


_PMXT_REQUIRED_DIRS = ("Polymarket",)
_PMXT_OPTIONAL_DIRS = ("Kalshi", "Opinion")


def validate_pmxt_layout(local_path: str) -> ValidationResult:
    """Validate pmxt archive directory layout.

    Expected::

        <local_path>/
          Polymarket/  <- required; *.parquet files
          Kalshi/      <- optional
          Opinion/     <- optional
    """
    p = Path(local_path)
    result = ValidationResult(source_kind="pmxt_archive", local_path=local_path, valid=False)
    if not p.exists():
        result.errors.append(f"Path does not exist: {local_path}")
        return result
    if not p.is_dir():
        result.errors.append(f"Path is not a directory: {local_path}")
        return result

    parquet_files: List[Path] = []
    for sub in _PMXT_REQUIRED_DIRS:
        sub_path = p / sub
        if not sub_path.is_dir():
            result.errors.append(f"Required subdirectory missing: {sub}/")
        else:
            pq = list(sub_path.rglob("*.parquet"))
            if not pq:
                result.errors.append(f"{sub}/ exists but contains no .parquet files")
            else:
                parquet_files.extend(pq)

    for sub in _PMXT_OPTIONAL_DIRS:
        sub_path = p / sub
        if sub_path.is_dir():
            pq = list(sub_path.rglob("*.parquet"))
            parquet_files.extend(pq)
            result.notes = (result.notes + f" {sub}/: {len(pq)} parquet files").strip()

    result.file_count = len(parquet_files)
    if parquet_files:
        result.checksum = _file_list_checksum(parquet_files)
    result.valid = len(result.errors) == 0
    return result


_JON_BECKER_REQUIRED_PATHS = (("data", "polymarket", "trades"),)
_JON_BECKER_OPTIONAL_PATHS = (("data", "kalshi", "trades"),)
_JON_BECKER_EXTENSIONS = {".parquet", ".csv", ".csv.gz", ".parquet.gz"}


def validate_jon_becker_layout(local_path: str) -> ValidationResult:
    """Validate Jon-Becker dataset directory layout.

    Expected (after extracting data.tar.zst)::

        <local_path>/
          data/
            polymarket/trades/  <- required; *.parquet or *.csv
            kalshi/trades/      <- optional
    """
    p = Path(local_path)
    result = ValidationResult(source_kind="jon_becker", local_path=local_path, valid=False)
    if not p.exists():
        result.errors.append(f"Path does not exist: {local_path}")
        return result
    if not p.is_dir():
        result.errors.append(f"Path is not a directory: {local_path}")
        return result

    trade_files: List[Path] = []
    for path_parts in _JON_BECKER_REQUIRED_PATHS:
        sub_path = p.joinpath(*path_parts)
        if not sub_path.is_dir():
            result.errors.append(f"Required subdirectory missing: {'/'.join(path_parts)}/")
        else:
            found = [
                f for f in sub_path.rglob("*")
                if f.is_file() and any(str(f.name).endswith(ext) for ext in _JON_BECKER_EXTENSIONS)
            ]
            if not found:
                result.errors.append(
                    f"{'/'.join(path_parts)}/ exists but contains no trade files "
                    f"({', '.join(sorted(_JON_BECKER_EXTENSIONS))})"
                )
            else:
                trade_files.extend(found)

    for path_parts in _JON_BECKER_OPTIONAL_PATHS:
        sub_path = p.joinpath(*path_parts)
        if sub_path.is_dir():
            found = [
                f for f in sub_path.rglob("*")
                if f.is_file() and any(str(f.name).endswith(ext) for ext in _JON_BECKER_EXTENSIONS)
            ]
            trade_files.extend(found)
            result.notes = (result.notes + f" kalshi trades: {len(found)} files").strip()

    zst_path = p / "data.tar.zst"
    if zst_path.exists() and not trade_files:
        result.warnings.append(
            "data.tar.zst found but data/ directory not extracted. "
            "Run: tar --use-compress-program=zstd -xf data.tar.zst"
        )

    result.file_count = len(trade_files)
    if trade_files:
        result.checksum = _file_list_checksum(trade_files)
    result.valid = len(result.errors) == 0
    return result


def validate_price_history_layout(local_path: str) -> ValidationResult:
    """Validate 2-minute price history data directory.

    Expected::

        <local_path>/
          *.jsonl  <- one file per token_id (polymarket-apis output), OR
          *.csv

    At least one .jsonl, .csv, or .json file must be present.
    """
    p = Path(local_path)
    result = ValidationResult(source_kind="price_history_2min", local_path=local_path, valid=False)
    if not p.exists():
        result.errors.append(f"Path does not exist: {local_path}")
        return result
    if not p.is_dir():
        result.errors.append(f"Path is not a directory: {local_path}")
        return result

    price_files = (
        list(p.rglob("*.jsonl"))
        + list(p.rglob("*.csv"))
        + list(p.rglob("*.json"))
    )

    if not price_files:
        result.errors.append(
            "No price history files found (.jsonl, .csv, or .json). "
            "Download via polymarket-apis: get_all_price_history_by_token_id()"
        )

    result.file_count = len(price_files)
    if price_files:
        result.checksum = _file_list_checksum(price_files)
    result.valid = len(result.errors) == 0
    return result
