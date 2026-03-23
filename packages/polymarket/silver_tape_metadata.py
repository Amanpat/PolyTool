"""Silver tape metadata: row builder and persistence (ClickHouse + JSONL fallback)."""
from __future__ import annotations

import json
import urllib.request
import urllib.parse
import urllib.error
import base64
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from packages.polymarket.silver_reconstructor import SilverResult

TAPE_METADATA_SCHEMA_VERSION = "tape_metadata_v1"


@dataclass
class TapeMetadataRow:
    run_id: str
    tape_path: str
    tier: str                          # "silver"
    token_id: str
    window_start: str                  # ISO8601 UTC
    window_end: str                    # ISO8601 UTC
    reconstruction_confidence: str
    warning_count: int
    source_inputs_json: str            # JSON string of source_inputs dict
    generated_at: str                  # ISO8601 UTC
    batch_run_id: str                  # "" if not a batch run

    def to_ch_row(self) -> dict:
        """Convert to ClickHouse-ready dict (DateTime64 values as epoch milliseconds)."""
        def _iso_to_epoch_ms(s: str) -> int:
            try:
                dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                return int(dt.timestamp() * 1000)
            except Exception:
                return 0
        return {
            "run_id": self.run_id,
            "tape_path": self.tape_path,
            "tier": self.tier,
            "token_id": self.token_id,
            "window_start": _iso_to_epoch_ms(self.window_start),
            "window_end": _iso_to_epoch_ms(self.window_end),
            "reconstruction_confidence": self.reconstruction_confidence,
            "warning_count": self.warning_count,
            "source_inputs_json": self.source_inputs_json,
            "generated_at": _iso_to_epoch_ms(self.generated_at),
            "batch_run_id": self.batch_run_id,
        }


def build_from_silver_result(
    result: "SilverResult",
    *,
    tier: str = "silver",
    batch_run_id: str = "",
    tape_path: str = "",
) -> TapeMetadataRow:
    """Build a TapeMetadataRow from a SilverResult."""
    now_iso = datetime.now(timezone.utc).isoformat()

    result_dict = result.to_dict()
    source_inputs = result_dict.get("source_inputs") or {}

    tape_path_resolved = tape_path
    if not tape_path_resolved and result.events_path:
        tape_path_resolved = str(result.events_path)

    return TapeMetadataRow(
        run_id=result_dict.get("run_id", ""),
        tape_path=tape_path_resolved,
        tier=tier,
        token_id=result_dict.get("token_id", ""),
        window_start=result_dict.get("window_start", ""),
        window_end=result_dict.get("window_end", ""),
        reconstruction_confidence=result_dict.get("reconstruction_confidence", "none"),
        warning_count=len(result_dict.get("warnings") or []),
        source_inputs_json=json.dumps(source_inputs),
        generated_at=now_iso,
        batch_run_id=batch_run_id,
    )


def write_to_clickhouse(
    row: TapeMetadataRow,
    *,
    host: str = "localhost",
    port: int = 8123,
    user: str = "polytool_admin",
    password: str = "polytool_admin",
) -> bool:
    """Insert one row into polytool.tape_metadata via ClickHouse HTTP interface.
    Returns True on success, False on any error (never raises).
    """
    try:
        ch_row = row.to_ch_row()
        ndjson = json.dumps(ch_row)
        query = "INSERT INTO polytool.tape_metadata FORMAT JSONEachRow"
        url = f"http://{host}:{port}/?query={urllib.parse.quote(query)}"
        data = ndjson.encode("utf-8")
        credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {credentials}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception:
        return False


def write_to_jsonl(row: TapeMetadataRow, jsonl_path: Path) -> bool:
    """Append one metadata row to a JSONL fallback file.
    Returns True on success, False on any error (never raises).
    """
    try:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        record = asdict(row)
        record["schema_version"] = TAPE_METADATA_SCHEMA_VERSION
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return True
    except Exception:
        return False
