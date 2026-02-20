#!/usr/bin/env python3
"""One-shot scan runner for PolyTool API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional

import requests

try:
    import clickhouse_connect
except ImportError:  # pragma: no cover - optional at runtime
    clickhouse_connect = None  # type: ignore

from polytool.reports.coverage import (
    build_coverage_report,
    normalize_fee_fields,
    write_coverage_report,
    write_hypothesis_candidates,
)
from polytool.reports.manifest import build_run_manifest, write_run_manifest
from tools.cli.audit_coverage import (
    DEFAULT_SEED as DEFAULT_AUDIT_SEED,
    write_audit_coverage_report,
)
from packages.polymarket.clob import ClobClient
from packages.polymarket.clv import (
    DEFAULT_CLOSING_WINDOW_SECONDS,
    DEFAULT_PRICES_FIDELITY,
    DEFAULT_PRICES_INTERVAL,
    MISSING_REASON_AUTH_MISSING,
    MISSING_REASON_OFFLINE,
    classify_prices_history_error,
    clv_recommended_next_action,
    enrich_positions_with_clv,
    format_prices_history_error_detail,
    normalize_prices_fidelity_minutes,
    resolve_close_ts,
    resolve_outcome_token_id,
    warm_clv_snapshot_cache,
)

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

ALLOWED_BUCKETS = {"day", "hour", "week"}
DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_MAX_PAGES = 50
DEFAULT_BUCKET = "day"
DEFAULT_BACKFILL = True
DEFAULT_INGEST_MARKETS = False
DEFAULT_INGEST_ACTIVITY = False
DEFAULT_INGEST_POSITIONS = False
DEFAULT_COMPUTE_PNL = False
DEFAULT_COMPUTE_OPPORTUNITIES = False
DEFAULT_SNAPSHOT_BOOKS = False
DEFAULT_ENRICH_RESOLUTIONS = False
DEFAULT_RESOLUTION_MAX_CANDIDATES = 500
DEFAULT_RESOLUTION_BATCH_SIZE = 25
DEFAULT_RESOLUTION_MAX_CONCURRENCY = 4
DEFAULT_TIMEOUT_SECONDS = 120.0
DEFAULT_PROFIT_FEE_RATE = 0.02
DEFAULT_FEE_SOURCE_LABEL = "estimated"
MAX_BODY_SNIPPET = 800
TRUST_ARTIFACT_WINDOW_DAYS = 30
TRUST_ARTIFACT_MAX_TRADES = 200
DEFAULT_COMPUTE_CLV = False
DEFAULT_WARM_CLV_CACHE = False
DEFAULT_CLV_ONLINE = True
DEFAULT_CLV_WINDOW_MINUTES = int(DEFAULT_CLOSING_WINDOW_SECONDS / 60)
DEFAULT_CLV_INTERVAL = DEFAULT_PRICES_INTERVAL
DEFAULT_CLV_FIDELITY = DEFAULT_PRICES_FIDELITY
DEFAULT_CLICKHOUSE_USER = "polyttool_admin"
DEFAULT_CLICKHOUSE_PASSWORD = "polyttool_admin"
DEFAULT_CLOB_API_BASE = "https://clob.polymarket.com"


class ApiError(Exception):
    """Raised when the API returns a non-200 response."""

    def __init__(self, method: str, url: str, status: int, body: str):
        super().__init__(f"{method} {url} -> {status}")
        self.method = method
        self.url = url
        self.status = status
        self.body = body


class NetworkError(Exception):
    """Raised when retries are exhausted for network errors."""

    def __init__(self, url: str, message: str, is_connection_error: bool = False):
        super().__init__(f"{url}: {message}")
        self.url = url
        self.message = message
        self.is_connection_error = is_connection_error


class TrustArtifactError(Exception):
    """Raised when trust artifacts cannot be emitted from scan."""


def _load_local_config(config_path: Optional[str]) -> Dict[str, Any]:
    """Load polytool local config (YAML preferred, JSON fallback)."""
    paths_to_try: list[Path] = []
    if config_path:
        paths_to_try.append(Path(config_path))
    else:
        paths_to_try.extend([Path("polytool.yaml"), Path("polytool.yml")])

    for path in paths_to_try:
        if not path.exists():
            continue
        try:
            raw_text = path.read_text(encoding="utf-8")
            payload: Any
            if yaml is not None:
                payload = yaml.safe_load(raw_text) or {}
            else:
                payload = json.loads(raw_text)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            continue
    return {}


def _extract_entry_price_tiers(local_config: Dict[str, Any]) -> Optional[list[dict[str, Any]]]:
    segment_config = local_config.get("segment_config")
    if not isinstance(segment_config, dict):
        return None
    tiers = segment_config.get("entry_price_tiers")
    if isinstance(tiers, list):
        return [tier for tier in tiers if isinstance(tier, dict)]
    return None


def _extract_fee_config(local_config: Dict[str, Any]) -> Dict[str, Any]:
    fee_config = local_config.get("fee_config")
    if not isinstance(fee_config, dict):
        return {
            "profit_fee_rate": DEFAULT_PROFIT_FEE_RATE,
            "source_label": DEFAULT_FEE_SOURCE_LABEL,
        }

    raw_rate = fee_config.get("profit_fee_rate")
    try:
        profit_fee_rate = float(raw_rate)
    except (TypeError, ValueError):
        profit_fee_rate = DEFAULT_PROFIT_FEE_RATE
    if profit_fee_rate < 0:
        profit_fee_rate = DEFAULT_PROFIT_FEE_RATE

    source_label = str(fee_config.get("source_label") or "").strip() or DEFAULT_FEE_SOURCE_LABEL
    return {
        "profit_fee_rate": profit_fee_rate,
        "source_label": source_label,
    }


def load_env_file(path: str) -> Dict[str, str]:
    """Load key/value pairs from a .env-style file."""
    if not os.path.exists(path):
        return {}

    env: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key:
                env[key] = value
    return env


def apply_env_defaults(env: Dict[str, str]) -> None:
    """Populate os.environ with defaults from .env without overriding existing vars."""
    for key, value in env.items():
        os.environ.setdefault(key, value)


def _running_in_docker() -> bool:
    if os.environ.get("POLYTOOL_IN_DOCKER") == "1":
        return True
    return Path("/.dockerenv").exists()


def _resolve_clickhouse_host() -> str:
    host = os.environ.get("CLICKHOUSE_HOST")
    if host:
        return host
    return "clickhouse" if _running_in_docker() else "localhost"


def _resolve_clickhouse_port() -> int:
    port = os.environ.get("CLICKHOUSE_PORT") or os.environ.get("CLICKHOUSE_HTTP_PORT")
    return int(port) if port else 8123


def _resolve_clickhouse_database() -> str:
    return os.environ.get("CLICKHOUSE_DATABASE") or os.environ.get("CLICKHOUSE_DB") or "polyttool"


def _get_clickhouse_client():
    if clickhouse_connect is None:
        return None
    try:
        return clickhouse_connect.get_client(
            host=_resolve_clickhouse_host(),
            port=_resolve_clickhouse_port(),
            username=os.getenv("CLICKHOUSE_USER", DEFAULT_CLICKHOUSE_USER),
            password=os.getenv("CLICKHOUSE_PASSWORD", DEFAULT_CLICKHOUSE_PASSWORD),
            database=_resolve_clickhouse_database(),
        )
    except Exception as exc:
        print(f"Warning: Could not connect to ClickHouse for CLV cache: {exc}", file=sys.stderr)
        return None


def parse_bool(value: Optional[str], key: str) -> Optional[bool]:
    """Parse a boolean env value. Returns None if value is None."""
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "y", "on"):
        return True
    if normalized in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError(f"{key} must be a boolean (true/false), got: {value}")


def parse_int(value: Optional[str], key: str) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer, got: {value}") from exc


def parse_float(value: Optional[str], key: str) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{key} must be a number, got: {value}") from exc


def request_with_retry(
    method: str,
    url: str,
    payload: Dict[str, Any],
    timeout: float,
    retries: int,
    backoff_seconds: float,
) -> requests.Response:
    attempt = 0
    last_is_connection_error = False
    while True:
        try:
            response = requests.request(method, url, json=payload, timeout=timeout)
            return response
        except requests.exceptions.RequestException as exc:
            last_is_connection_error = isinstance(exc, requests.exceptions.ConnectionError)
            if attempt >= retries:
                raise NetworkError(url, str(exc), is_connection_error=last_is_connection_error) from exc
            delay = backoff_seconds * (2**attempt)
            print(
                f"Network error contacting {url}: {exc}. Retrying in {delay:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(delay)
            attempt += 1


def post_json(
    base_url: str,
    path: str,
    payload: Dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = 3,
    backoff_seconds: float = 1.0,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    response = request_with_retry("POST", url, payload, timeout, retries, backoff_seconds)

    if response.status_code != 200:
        body = response.text.strip()
        if len(body) > MAX_BODY_SNIPPET:
            body = body[:MAX_BODY_SNIPPET] + "..."
        raise ApiError("POST", url, response.status_code, body)

    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("POST", url, response.status_code, "Invalid JSON response") from exc


def get_json(
    base_url: str,
    path: str,
    params: Dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    retries: int = 3,
    backoff_seconds: float = 1.0,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    attempt = 0
    while True:
        try:
            response = requests.get(url, params=params, timeout=timeout)
            break
        except requests.exceptions.RequestException as exc:
            if attempt >= retries:
                raise NetworkError(url, str(exc), is_connection_error=isinstance(exc, requests.exceptions.ConnectionError)) from exc
            delay = backoff_seconds * (2**attempt)
            print(
                f"Network error contacting {url}: {exc}. Retrying in {delay:.1f}s...",
                file=sys.stderr,
            )
            time.sleep(delay)
            attempt += 1

    if response.status_code != 200:
        body = response.text.strip()
        if len(body) > MAX_BODY_SNIPPET:
            body = body[:MAX_BODY_SNIPPET] + "..."
        raise ApiError("GET", url, response.status_code, body)

    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("GET", url, response.status_code, "Invalid JSON response") from exc


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _debug_export(config: Dict[str, Any], message: str) -> None:
    if config.get("debug_export"):
        print(f"[debug-export] {message}", file=sys.stderr)


def _extract_gamma_markets_sample(ingest_markets_response: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(ingest_markets_response, dict):
        return None
    sample = ingest_markets_response.get("gamma_markets_sample")
    if isinstance(sample, dict):
        return sample
    return None


def _write_gamma_markets_sample(
    *,
    output_dir: Path,
    config: Dict[str, Any],
    ingest_markets_response: Optional[Dict[str, Any]],
) -> Optional[Path]:
    if not config.get("debug_export"):
        return None
    sample = _extract_gamma_markets_sample(ingest_markets_response)
    if sample is None:
        _debug_export(config, "gamma_markets_sample unavailable in ingest-markets response")
        return None

    output_path = output_dir / "gamma_markets_sample.json"
    output_path.write_text(
        json.dumps(sample, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    _debug_export(config, f"gamma_markets_sample_path={output_path}")
    return output_path


def _coerce_non_negative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return parsed if parsed > 0 else 0


def _effective_resolution_config(config: Dict[str, Any]) -> Dict[str, int]:
    """Return explicit enrichment knobs, always populated from config or defaults."""
    return {
        "max_candidates": int(
            config.get("resolution_max_candidates") or DEFAULT_RESOLUTION_MAX_CANDIDATES
        ),
        "batch_size": int(
            config.get("resolution_batch_size") or DEFAULT_RESOLUTION_BATCH_SIZE
        ),
        "max_concurrency": int(
            config.get("resolution_max_concurrency") or DEFAULT_RESOLUTION_MAX_CONCURRENCY
        ),
    }


def _positions_identity_hash(positions: list[Dict[str, Any]]) -> str:
    """Compute a stable SHA-256 over sorted position identifiers.

    Uses (resolved_token_id|token_id|condition_id, outcome_name, market_slug)
    tuples so that two runs covering the same positions produce the same hash.
    """
    identity_tuples: list[str] = []
    for pos in positions:
        identifier = ""
        for key in ("resolved_token_id", "token_id", "condition_id"):
            value = str(pos.get(key) or "").strip()
            if value:
                identifier = value
                break
        outcome_name = str(pos.get("outcome_name") or pos.get("resolution_outcome") or "").strip()
        market_slug = str(pos.get("market_slug") or "").strip()
        identity_tuples.append(f"{identifier}|{outcome_name}|{market_slug}")
    identity_tuples.sort()
    canonical = "\n".join(identity_tuples)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_position_notional(positions: list[dict[str, Any]]) -> None:
    """Inject canonical position_notional_usd onto every position dict in-place.

    Uses the same priority chain as coverage.extract_position_notional_usd:
      1. existing position_notional_usd (if positive finite float)
      2. total_cost (if positive finite float)
      3. size * entry_price (if both present and entry_price > 0)

    Positions that yield None from all three sources are left unchanged
    (position_notional_usd absent); the debug artifact records why.
    """
    from polytool.reports.coverage import extract_position_notional_usd
    for pos in positions:
        existing = pos.get("position_notional_usd")
        # Avoid overwriting a valid value already present
        try:
            ev = float(existing) if existing is not None else None
        except (TypeError, ValueError):
            ev = None
        if ev is not None and ev > 0:
            continue
        extracted = extract_position_notional_usd(pos)
        if extracted is not None:
            pos["position_notional_usd"] = extracted


def _build_notional_weight_debug(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the notional_weight_debug.json payload from already-normalized positions."""
    import math as _math

    WEIGHT_FIELDS = ("position_notional_usd", "total_cost", "size", "entry_price")
    total = len(positions)
    extracted_total = 0.0
    count_missing = 0
    missing_reasons: dict[str, int] = {}
    samples = []

    for pos in positions:
        pnu = pos.get("position_notional_usd")
        try:
            v = float(pnu) if pnu is not None else None
        except (TypeError, ValueError):
            v = None

        if v is not None and v > 0 and _math.isfinite(v):
            extracted_total += v
        else:
            count_missing += 1
            # Classify reason
            has_tc = pos.get("total_cost") is not None
            has_size = pos.get("size") is not None
            has_ep = pos.get("entry_price") is not None
            if not has_tc and not has_size:
                reason = "NO_FIELDS"
            elif pnu is not None and v is None:
                reason = "NON_NUMERIC"
            elif v is not None and v <= 0:
                reason = "ZERO_OR_NEGATIVE"
            else:
                reason = "FALLBACK_FAILED"
            missing_reasons[reason] = missing_reasons.get(reason, 0) + 1

        if len(samples) < 10:
            sample_fields = {k: pos.get(k) for k in WEIGHT_FIELDS if pos.get(k) is not None}
            samples.append({
                "token_id": pos.get("token_id") or pos.get("resolved_token_id"),
                "market_slug": pos.get("market_slug"),
                "fields_present": list(sample_fields.keys()),
                "extracted_position_notional_usd": v if (v is not None and v > 0) else None,
            })

    top_missing = sorted(missing_reasons.items(), key=lambda x: -x[1])
    return {
        "total_positions": total,
        "extracted_weight_total": round(extracted_total, 6),
        "count_missing_weight": count_missing,
        "top_missing_reasons": [{"reason": r, "count": c} for r, c in top_missing],
        "samples": samples,
    }


def _build_parity_debug(
    positions: list[Dict[str, Any]],
    enrichment_request_payload: Dict[str, Any],
    enrichment_response: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a resolution_parity_debug artifact for one run."""
    identity_hash = _positions_identity_hash(positions)

    identifiers_sample = []
    for pos in positions[:10]:
        sample = {}
        for key in ("resolved_token_id", "token_id", "condition_id"):
            value = str(pos.get(key) or "").strip()
            if value:
                sample[key] = value
        identifiers_sample.append(sample)

    enrichment_summary: Dict[str, Any] = {}
    if enrichment_response:
        for key in (
            "candidates_total", "candidates_selected", "truncated",
            "cached_hits", "resolved_written", "unresolved_network",
            "skipped_missing_identifiers", "errors",
            "lifecycle_token_universe_size_used_for_selection",
        ):
            enrichment_summary[key] = enrichment_response.get(key)

    return {
        "positions_identity_hash": identity_hash,
        "positions_count": len(positions),
        "identifiers_sample": identifiers_sample,
        "enrichment_request_payload": enrichment_request_payload,
        "enrichment_response_summary": enrichment_summary,
        "lifecycle_token_universe_size_used_for_selection": _coerce_non_negative_int(
            (enrichment_response or {}).get("lifecycle_token_universe_size_used_for_selection")
        ),
    }


def _extract_trades_total(dossier: Dict[str, Any]) -> int:
    coverage = dossier.get("coverage")
    if isinstance(coverage, dict):
        coverage_count = _coerce_non_negative_int(coverage.get("trades_count"))
        if coverage_count > 0:
            return coverage_count

    trades_section = dossier.get("trades")
    if isinstance(trades_section, list):
        return len(trades_section)
    if isinstance(trades_section, dict):
        for key in ("trades", "rows", "items"):
            value = trades_section.get(key)
            if isinstance(value, list):
                return len(value)
        count = _coerce_non_negative_int(trades_section.get("count"))
        if count > 0:
            return count

    anchors = dossier.get("anchors")
    if isinstance(anchors, dict):
        # Not full trades, but better than reporting zero in debug when anchors exist.
        anchor_count = _coerce_non_negative_int(anchors.get("total_anchors"))
        if anchor_count > 0:
            return anchor_count

    return 0


def _extract_positions_payload(dossier: Dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []

    positions_section = dossier.get("positions")
    if isinstance(positions_section, dict):
        if isinstance(positions_section.get("positions"), list):
            candidates = positions_section["positions"]
        elif isinstance(positions_section.get("items"), list):
            candidates = positions_section["items"]
    elif isinstance(positions_section, list):
        candidates = positions_section

    if not candidates:
        for key in ("positions_lifecycle", "position_lifecycle", "position_lifecycles"):
            alt = dossier.get(key)
            if isinstance(alt, list):
                candidates = alt
                break
            if isinstance(alt, dict) and isinstance(alt.get("positions"), list):
                candidates = alt["positions"]
                break

    extracted: list[dict[str, Any]] = []
    for item in candidates:
        if isinstance(item, dict):
            extracted.append(dict(item))
    return extracted


def _extract_declared_positions_count(dossier: Dict[str, Any]) -> int:
    declared_count = 0
    positions_section = dossier.get("positions")
    if isinstance(positions_section, dict):
        declared_count = max(declared_count, _coerce_non_negative_int(positions_section.get("count")))
    coverage = dossier.get("coverage")
    if isinstance(coverage, dict):
        declared_count = max(declared_count, _coerce_non_negative_int(coverage.get("positions_count")))
    return declared_count


def _parse_dossier_payload(payload: Any) -> Optional[Dict[str, Any]]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _summarize_dossier_payload(dossier: Optional[Dict[str, Any]]) -> Dict[str, int]:
    if not isinstance(dossier, dict):
        return {"positions_len": 0, "trades_len": 0}
    positions_len = len(_extract_positions_payload(dossier))
    trades_len = _extract_trades_total(dossier)
    return {"positions_len": positions_len, "trades_len": trades_len}


def _load_dossier_payload(output_dir: Path) -> Optional[Dict[str, Any]]:
    dossier_json_path = output_dir / "dossier.json"
    if not dossier_json_path.exists():
        return None
    try:
        parsed = json.loads(dossier_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _history_row_summaries(rows: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    summaries: list[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        dossier_payload = _parse_dossier_payload(row.get("dossier_json"))
        dossier_summary = _summarize_dossier_payload(dossier_payload)
        positions_count_raw = _coerce_non_negative_int(row.get("positions_count"))
        trades_count_raw = _coerce_non_negative_int(row.get("trades_count"))
        declared_positions_count = (
            _extract_declared_positions_count(dossier_payload)
            if isinstance(dossier_payload, dict)
            else 0
        )
        positions_count = max(
            positions_count_raw,
            declared_positions_count,
            dossier_summary["positions_len"],
        )
        trades_count = max(trades_count_raw, dossier_summary["trades_len"])
        summaries.append({
            "row": row,
            "dossier_payload": dossier_payload,
            "export_id": str(row.get("export_id") or ""),
            "positions_count": positions_count,
            "positions_count_raw": positions_count_raw,
            "declared_positions_count": declared_positions_count,
            "trades_count": trades_count,
            "trades_count_raw": trades_count_raw,
            "positions_len": dossier_summary["positions_len"],
            "trades_len": dossier_summary["trades_len"],
        })
    return summaries


def _select_history_hydration_row(
    summaries: list[Dict[str, Any]],
    export_id: str,
) -> Optional[Dict[str, Any]]:
    matching = [s for s in summaries if s["export_id"] == export_id and s["dossier_payload"] is not None]
    matching_with_positions_rows = [s for s in matching if s["positions_len"] > 0]
    if matching_with_positions_rows:
        return matching_with_positions_rows[0]

    any_with_positions_rows = [s for s in summaries if s["dossier_payload"] is not None and s["positions_len"] > 0]
    if any_with_positions_rows:
        return any_with_positions_rows[0]

    matching_with_positions = [s for s in matching if s["positions_count"] > 0]
    if matching_with_positions:
        return matching_with_positions[0]

    any_with_positions = [s for s in summaries if s["dossier_payload"] is not None and s["positions_count"] > 0]
    if any_with_positions:
        return any_with_positions[0]

    if matching:
        return matching[0]

    any_with_payload = [s for s in summaries if s["dossier_payload"] is not None]
    if any_with_payload:
        return any_with_payload[0]
    return None


def _write_hydrated_dossier(output_dir: Path, history_summary: Dict[str, Any]) -> None:
    dossier_payload = history_summary.get("dossier_payload")
    if not isinstance(dossier_payload, dict):
        raise TrustArtifactError("Selected history row has no dossier_json payload to hydrate")

    output_dir.mkdir(parents=True, exist_ok=True)
    dossier_json_path = output_dir / "dossier.json"
    dossier_json_path.write_text(
        json.dumps(dossier_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    memo_payload = history_summary.get("row", {}).get("memo_md")
    if memo_payload:
        (output_dir / "memo.md").write_text(str(memo_payload), encoding="utf-8")


def _load_dossier_positions(dossier_root: Path) -> list[dict[str, Any]]:
    dossier_json_path = dossier_root / "dossier.json"
    if not dossier_json_path.exists():
        raise TrustArtifactError(f"Missing dossier.json at {dossier_json_path}")

    try:
        dossier = json.loads(dossier_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrustArtifactError(f"Invalid dossier JSON at {dossier_json_path}: {exc}") from exc

    positions = _extract_positions_payload(dossier)

    normalized: list[dict[str, Any]] = []
    for pos in positions:
        normalize_fee_fields(pos)
        normalized.append(pos)
    return normalized


def _load_dossier_json(dossier_root: Path) -> Dict[str, Any]:
    dossier_json_path = dossier_root / "dossier.json"
    if not dossier_json_path.exists():
        raise TrustArtifactError(f"Missing dossier.json at {dossier_json_path}")
    try:
        dossier = json.loads(dossier_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrustArtifactError(f"Invalid dossier JSON at {dossier_json_path}: {exc}") from exc
    if not isinstance(dossier, dict):
        raise TrustArtifactError(f"dossier.json at {dossier_json_path} is not a JSON object")
    return dossier


def _replace_positions_payload(dossier: Dict[str, Any], positions: list[dict[str, Any]]) -> None:
    """Replace dossier position payload while preserving existing shape when possible."""
    replacement = [dict(pos) for pos in positions]

    positions_section = dossier.get("positions")
    if isinstance(positions_section, dict):
        if "positions" in positions_section or isinstance(positions_section.get("positions"), list):
            positions_section["positions"] = replacement
            positions_section["count"] = len(replacement)
            dossier["positions"] = positions_section
            return
        if "items" in positions_section or isinstance(positions_section.get("items"), list):
            positions_section["items"] = replacement
            positions_section["count"] = len(replacement)
            dossier["positions"] = positions_section
            return
    elif isinstance(positions_section, list):
        dossier["positions"] = replacement
        return

    for key in ("positions_lifecycle", "position_lifecycle", "position_lifecycles"):
        alt = dossier.get(key)
        if isinstance(alt, list):
            dossier[key] = replacement
            return
        if isinstance(alt, dict):
            if "positions" in alt or isinstance(alt.get("positions"), list):
                alt["positions"] = replacement
                alt["count"] = len(replacement)
                dossier[key] = alt
                return

    dossier["positions"] = {"count": len(replacement), "positions": replacement}


def _write_dossier_json(dossier_root: Path, dossier: Dict[str, Any]) -> None:
    dossier_json_path = dossier_root / "dossier.json"
    dossier_json_path.write_text(
        json.dumps(dossier, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _hydrate_dossier_from_history_if_needed(
    output_dir: Path,
    config: Dict[str, Any],
    dossier_export_response: Dict[str, Any],
) -> tuple[list[str], Dict[str, Any], Dict[str, Any]]:
    endpoints_used = ["/api/export/user_dossier"]
    local_payload = _load_dossier_payload(output_dir)
    local_summary = _summarize_dossier_payload(local_payload)

    export_stats = dossier_export_response.get("stats")
    export_positions_count: Optional[int] = None
    export_trades_count: Optional[int] = None
    if isinstance(export_stats, dict):
        if "positions_count" in export_stats:
            export_positions_count = _coerce_non_negative_int(export_stats.get("positions_count"))
        if "trades_count" in export_stats:
            export_trades_count = _coerce_non_negative_int(export_stats.get("trades_count"))

    _debug_export(
        config,
        "endpoint=/api/export/user_dossier "
        f"positions_count={export_positions_count if export_positions_count is not None else 'n/a'} "
        f"trades_count={export_trades_count if export_trades_count is not None else 'n/a'} "
        f"local_positions_len={local_summary['positions_len']} local_trades_len={local_summary['trades_len']}",
    )

    # When export reports an empty dossier, consult history even if a stale local dossier exists.
    export_indicates_empty = export_positions_count == 0 if export_positions_count is not None else False
    should_query_history = local_payload is None or local_summary["positions_len"] == 0 or export_indicates_empty
    if not should_query_history:
        return endpoints_used, local_summary, {
            "history_rows": 0,
            "hydrated": False,
            "export_positions_count": export_positions_count,
            "export_trades_count": export_trades_count,
            "history_positions_fallback_used": False,
        }

    history = get_json(
        config["api_base_url"],
        "/api/export/user_dossier/history",
        {
            "user": str(config["user"]),
            "limit": 5,
            "include_body": "true",
        },
        timeout=float(config["timeout_seconds"]),
    )
    endpoints_used.append("/api/export/user_dossier/history")
    rows = history.get("rows") or []
    summaries = _history_row_summaries(rows if isinstance(rows, list) else [])
    if summaries:
        top = summaries[0]
        _debug_export(
            config,
            "endpoint=/api/export/user_dossier/history "
            f"rows={len(summaries)} top_export_id={top['export_id']} "
            f"top_positions_count={top['positions_count']} top_positions_count_raw={top['positions_count_raw']} "
            f"top_declared_positions_count={top['declared_positions_count']} "
            f"top_trades_count={top['trades_count']} "
            f"top_positions_len={top['positions_len']} top_trades_len={top['trades_len']}",
        )
    else:
        _debug_export(config, "endpoint=/api/export/user_dossier/history rows=0")

    export_id = str(dossier_export_response.get("export_id") or "")
    selected = _select_history_hydration_row(summaries, export_id)
    selected_meta = {
        "history_positions_count_raw": selected.get("positions_count_raw") if selected else None,
        "history_positions_count": selected.get("positions_count") if selected else None,
        "history_declared_positions_count": selected.get("declared_positions_count") if selected else None,
        "history_positions_len": selected.get("positions_len") if selected else None,
        "history_export_id": selected.get("export_id") if selected else None,
    }

    if selected and selected["positions_count"] > 0:
        _write_hydrated_dossier(output_dir, selected)
        hydrated_summary = _summarize_dossier_payload(_load_dossier_payload(output_dir))
        history_positions_fallback_used = (
            selected.get("positions_count_raw", 0) == 0
            and selected.get("declared_positions_count", 0) > 0
            and hydrated_summary["positions_len"] > 0
        )
        _debug_export(
            config,
            f"hydrated_from_history export_id={selected['export_id']} "
            f"positions_len={hydrated_summary['positions_len']} trades_len={hydrated_summary['trades_len']} "
            f"history_positions_fallback_used={history_positions_fallback_used}",
        )
        return endpoints_used, hydrated_summary, {
            "history_rows": len(summaries),
            "hydrated": True,
            "export_positions_count": export_positions_count,
            "export_trades_count": export_trades_count,
            "history_positions_fallback_used": history_positions_fallback_used,
            **selected_meta,
        }

    if local_payload is None:
        if selected:
            _write_hydrated_dossier(output_dir, selected)
            hydrated_summary = _summarize_dossier_payload(_load_dossier_payload(output_dir))
            history_positions_fallback_used = (
                selected.get("positions_count_raw", 0) == 0
                and selected.get("declared_positions_count", 0) > 0
                and hydrated_summary["positions_len"] > 0
            )
            return endpoints_used, hydrated_summary, {
                "history_rows": len(summaries),
                "hydrated": True,
                "export_positions_count": export_positions_count,
                "export_trades_count": export_trades_count,
                "history_positions_fallback_used": history_positions_fallback_used,
                **selected_meta,
            }
        raise TrustArtifactError(
            f"Missing dossier.json at {output_dir / 'dossier.json'} and no usable history dossier payload found"
        )

    return endpoints_used, local_summary, {
        "history_rows": len(summaries),
        "hydrated": False,
        "export_positions_count": export_positions_count,
        "export_trades_count": export_trades_count,
        "history_positions_fallback_used": False,
        **selected_meta,
    }


def _materialize_dossier_if_missing(
    output_dir: Path,
    config: Dict[str, Any],
    dossier_export_response: Dict[str, Any],
) -> tuple[list[str], Dict[str, Any], Dict[str, Any]]:
    # Historical function name kept for compatibility; this now also supports hydration from history
    # when the latest export is empty.
    wallet_hint = str(dossier_export_response.get("proxy_wallet") or config.get("user") or "")
    _debug_export(
        config,
        f"wallet={wallet_hint} run_root={output_dir}",
    )
    endpoints_used, dossier_summary, hydration_meta = _hydrate_dossier_from_history_if_needed(
        output_dir=output_dir,
        config=config,
        dossier_export_response=dossier_export_response,
    )
    _debug_export(
        config,
        f"endpoints_used={','.join(endpoints_used)} "
        f"hydrated={hydration_meta.get('hydrated')} history_rows={hydration_meta.get('history_rows', 0)} "
        f"positions_len={dossier_summary['positions_len']} trades_len={dossier_summary['trades_len']}",
    )
    return endpoints_used, dossier_summary, hydration_meta


def _build_metadata_map_from_positions(
    positions: list[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a token/condition → market-metadata mapping from positions that already have metadata.

    This enables self-referential backfill: when different records in the same
    dossier share a token_id or condition_id, positions that happen to carry
    complete market_slug/question/outcome_name can fill in the gaps for those
    that don't.

    Only populates the map from positions where at least one metadata field is
    non-empty. A position can populate multiple identifiers (`token_id`,
    `resolved_token_id`, and `condition_id`) when present.

    When two positions share an identifier but disagree on relevant metadata
    values, the first entry wins deterministically and the collision is counted.
    For `condition_id` conflicts, `outcome_name` is ignored because condition IDs
    are market-level and cannot safely determine outcome names.

    Returns
    -------
    dict with keys:
        ``map``               – the token/condition → metadata dict
        ``conflicts_count``   – number of disagreeing entries detected
        ``conflict_sample``   – up to 5 conflict examples for debugging
    """
    mapping: Dict[str, Dict[str, str]] = {}
    conflicts_count = 0
    conflict_sample: list[Dict[str, Any]] = []

    for pos in positions:
        slug = str(pos.get("market_slug") or "").strip()
        question = str(pos.get("question") or "").strip()
        outcome_name = str(pos.get("outcome_name") or "").strip()
        category = str(pos.get("category") or "").strip()
        if not any([slug, question, outcome_name, category]):
            continue

        candidate = {
            "market_slug": slug,
            "question": question,
            "outcome_name": outcome_name,
            "category": category,
        }

        for key in ("token_id", "resolved_token_id", "condition_id"):
            identifier = str(pos.get(key) or "").strip()
            if not identifier:
                continue

            candidate_for_key = dict(candidate)
            conflict_fields = ("market_slug", "question", "outcome_name", "category")
            if key == "condition_id":
                # condition_id is market-level only; outcome_name is token-level.
                candidate_for_key["outcome_name"] = ""
                conflict_fields = ("market_slug", "question", "category")

            if identifier not in mapping:
                mapping[identifier] = candidate_for_key
            else:
                existing = mapping[identifier]
                # Detect a real conflict: at least one shared non-empty field disagrees.
                conflict = any(
                    existing.get(f) and candidate_for_key.get(f) and existing[f] != candidate_for_key[f]
                    for f in conflict_fields
                )
                if conflict:
                    conflicts_count += 1
                    if len(conflict_sample) < 5:
                        conflict_sample.append({
                            "identifier": identifier,
                            "first": dict(existing),
                            "second": dict(candidate_for_key),
                        })
                # First entry wins — do not overwrite.

    return {
        "map": mapping,
        "conflicts_count": conflicts_count,
        "conflict_sample": conflict_sample,
    }


def _build_clob_auth_headers() -> Dict[str, str]:
    """Build optional CLOB auth headers from env without exposing secret values."""
    headers: Dict[str, str] = {}

    raw_header_name = str(os.getenv("CLOB_AUTH_HEADER") or "").strip()
    raw_header_value = str(os.getenv("CLOB_AUTH_VALUE") or "").strip()
    if raw_header_name and raw_header_value:
        headers[raw_header_name] = raw_header_value

    bearer = str(
        os.getenv("CLOB_API_BEARER_TOKEN")
        or os.getenv("CLOB_API_KEY")
        or ""
    ).strip()
    if bearer and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {bearer}"

    x_api_key = str(os.getenv("CLOB_X_API_KEY") or "").strip()
    if x_api_key and "X-API-Key" not in headers:
        headers["X-API-Key"] = x_api_key

    return headers


def _build_clv_runtime(config: Dict[str, Any]) -> Dict[str, Any]:
    clickhouse_client = _get_clickhouse_client()
    clv_online = bool(config.get("clv_online", DEFAULT_CLV_ONLINE))
    clob_headers = _build_clob_auth_headers()
    clob_client = (
        ClobClient(
            base_url=os.getenv("CLOB_API_BASE", DEFAULT_CLOB_API_BASE),
            default_headers=clob_headers,
        )
        if clv_online
        else None
    )

    clv_window_minutes = int(config.get("clv_window_minutes") or DEFAULT_CLV_WINDOW_MINUTES)
    clv_window_seconds = max(clv_window_minutes, 1) * 60
    clv_interval = str(config.get("clv_interval") or DEFAULT_CLV_INTERVAL).strip() or DEFAULT_CLV_INTERVAL
    clv_fidelity = normalize_prices_fidelity_minutes(
        config.get("clv_fidelity", DEFAULT_CLV_FIDELITY)
    )

    return {
        "clickhouse_client": clickhouse_client,
        "clob_client": clob_client,
        "clv_online": clv_online,
        "clv_window_seconds": clv_window_seconds,
        "clv_interval": clv_interval,
        "clv_fidelity": clv_fidelity,
    }


def _extract_prices_history_points_count(payload: Any) -> int:
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return 0
    for key in ("history", "prices", "priceHistory", "prices_history", "data", "result"):
        candidate = payload.get(key)
        if isinstance(candidate, list):
            return len(candidate)
    return 0


def _select_clv_preflight_probe(positions: list[Dict[str, Any]]) -> tuple[Optional[str], Optional[datetime]]:
    for pos in positions:
        token_id = resolve_outcome_token_id(pos)
        close_ts, _ = resolve_close_ts(pos)
        if token_id and close_ts is not None:
            return token_id, close_ts
    return None, None


def _run_clv_preflight(
    *,
    output_dir: Path,
    positions: list[Dict[str, Any]],
    clob_client: Any,
    clv_online: bool,
    clv_interval: str,
    clv_fidelity: int,
) -> Dict[str, Any]:
    endpoint_used = "/prices-history"
    auth_present = bool(
        clob_client is not None
        and getattr(clob_client, "has_auth_headers", lambda: False)()
    )
    payload: Dict[str, Any] = {
        "generated_at": _now_utc_iso(),
        "endpoint_used": endpoint_used,
        "clv_online": bool(clv_online),
        "clv_interval": clv_interval,
        "clv_fidelity_minutes": int(clv_fidelity),
        "auth_present": auth_present,
        "preflight_ok": False,
        "error_class": None,
        "recommended_next_action": None,
    }

    if not clv_online:
        payload["error_class"] = MISSING_REASON_OFFLINE
        payload["recommended_next_action"] = clv_recommended_next_action(MISSING_REASON_OFFLINE)
    elif clob_client is None:
        payload["error_class"] = MISSING_REASON_AUTH_MISSING
        payload["recommended_next_action"] = clv_recommended_next_action(MISSING_REASON_AUTH_MISSING)
    else:
        token_id, close_ts = _select_clv_preflight_probe(positions)
        payload["probe_token_id"] = token_id
        payload["probe_close_ts"] = close_ts.replace(microsecond=0).isoformat() if close_ts else None
        if not token_id or close_ts is None:
            payload["error_class"] = "NO_ELIGIBLE_POSITION"
            payload["recommended_next_action"] = (
                "No eligible position with token_id + close_ts was available for preflight. "
                "Run with --enrich-resolutions and ensure at least one resolved market is present."
            )
        else:
            try:
                probe_start = close_ts - timedelta(minutes=5)
                response_payload = clob_client.get_prices_history(
                    token_id=token_id,
                    start_ts=probe_start,
                    end_ts=close_ts,
                    fidelity=clv_fidelity,
                )
                payload["preflight_ok"] = True
                payload["error_class"] = None
                payload["response_points_count"] = _extract_prices_history_points_count(response_payload)
                payload["recommended_next_action"] = (
                    "Preflight succeeded. Proceed with CLV compute or warm-cache."
                )
            except Exception as exc:
                reason = classify_prices_history_error(exc)
                payload["error_class"] = reason
                payload["recommended_next_action"] = clv_recommended_next_action(reason)
                payload["error_detail"] = format_prices_history_error_detail(exc)

    output_path = output_dir / "clv_preflight.json"
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return {
        "path": output_path.as_posix(),
        "payload": payload,
    }


def _run_clv_warm_cache(
    *,
    output_dir: Path,
    positions: list[Dict[str, Any]],
    clickhouse_client: Any,
    clob_client: Any,
    clv_online: bool,
    clv_window_seconds: int,
    clv_interval: str,
    clv_fidelity: int,
) -> Dict[str, Any]:
    summary = warm_clv_snapshot_cache(
        positions,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=clv_online,
        closing_window_seconds=clv_window_seconds,
        interval=clv_interval,
        fidelity=clv_fidelity,
    )
    payload = {
        "generated_at": _now_utc_iso(),
        "online_enabled": bool(clv_online),
        **summary,
    }
    output_path = output_dir / "clv_warm_cache_summary.json"
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    print(
        "CLV warm-cache: "
        f"attempted={payload.get('attempted', 0)}, "
        f"succeeded={payload.get('succeeded', 0)}, "
        f"failed={payload.get('failed', 0)}",
        file=sys.stderr,
    )
    return {
        "path": output_path.as_posix(),
        "payload": payload,
    }


def _apply_clv_enrichment(
    *,
    output_dir: Path,
    positions: list[Dict[str, Any]],
    clickhouse_client: Any,
    clob_client: Any,
    clv_online: bool,
    clv_window_seconds: int,
    clv_interval: str,
    clv_fidelity: int,
) -> Dict[str, Any]:
    """Enrich positions with CLV fields and persist back to dossier.json."""
    summary = enrich_positions_with_clv(
        positions,
        clickhouse_client=clickhouse_client,
        clob_client=clob_client,
        allow_online=clv_online,
        closing_window_seconds=clv_window_seconds,
        interval=clv_interval,
        fidelity=clv_fidelity,
    )
    print(
        "CLV enrichment: "
        f"positions={summary.get('positions_total', 0)}, "
        f"present={summary.get('clv_present_count', 0)}, "
        f"missing={summary.get('clv_missing_count', 0)}, "
        f"online={clv_online}",
        file=sys.stderr,
    )

    dossier = _load_dossier_json(output_dir)
    _replace_positions_payload(dossier, positions)
    _write_dossier_json(output_dir, dossier)
    return summary


def _emit_trust_artifacts(
    config: Dict[str, Any],
    argv: list[str],
    started_at: str,
    resolve_response: Dict[str, Any],
    dossier_export_response: Dict[str, Any],
    ingest_markets_response: Optional[Dict[str, Any]] = None,
    resolution_enrichment_response: Optional[Dict[str, Any]] = None,
    effective_enrichment_config: Optional[Dict[str, int]] = None,
    enrichment_request_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    artifact_path = str(dossier_export_response.get("artifact_path") or "").strip()
    if not artifact_path:
        raise TrustArtifactError("Export response missing artifact_path")

    output_dir = Path(artifact_path)
    run_id = str(dossier_export_response.get("export_id") or uuid.uuid4().hex[:8])
    proxy_wallet = str(
        dossier_export_response.get("proxy_wallet")
        or resolve_response.get("proxy_wallet")
        or ""
    )
    username_slug = str(dossier_export_response.get("username_slug") or "").strip()
    if not username_slug:
        username = str(resolve_response.get("username") or "").strip()
        username_slug = username.lower() if username else str(config["user"]).strip().lstrip("@").lower()

    endpoints_used, dossier_summary, hydration_meta = _materialize_dossier_if_missing(
        output_dir,
        config,
        dossier_export_response,
    )
    _debug_export(
        config,
        f"coverage_input positions_len={dossier_summary['positions_len']} "
        f"trades_len={dossier_summary['trades_len']} hydrated={hydration_meta.get('hydrated')}",
    )
    dossier_payload = _load_dossier_payload(output_dir)
    declared_positions_count = (
        _extract_declared_positions_count(dossier_payload)
        if isinstance(dossier_payload, dict)
        else 0
    )
    positions = _load_dossier_positions(output_dir)
    clv_preflight_artifact: Optional[Dict[str, Any]] = None
    clv_warm_cache_artifact: Optional[Dict[str, Any]] = None
    clv_runtime: Optional[Dict[str, Any]] = None
    if bool(config.get("compute_clv", DEFAULT_COMPUTE_CLV)) or bool(
        config.get("warm_clv_cache", DEFAULT_WARM_CLV_CACHE)
    ):
        clv_runtime = _build_clv_runtime(config)

    if bool(config.get("compute_clv", DEFAULT_COMPUTE_CLV)) and clv_runtime is not None:
        clv_preflight_artifact = _run_clv_preflight(
            output_dir=output_dir,
            positions=positions,
            clob_client=clv_runtime["clob_client"],
            clv_online=bool(clv_runtime["clv_online"]),
            clv_interval=str(clv_runtime["clv_interval"]),
            clv_fidelity=int(clv_runtime["clv_fidelity"]),
        )

    if bool(config.get("warm_clv_cache", DEFAULT_WARM_CLV_CACHE)) and clv_runtime is not None:
        clv_warm_cache_artifact = _run_clv_warm_cache(
            output_dir=output_dir,
            positions=positions,
            clickhouse_client=clv_runtime["clickhouse_client"],
            clob_client=clv_runtime["clob_client"],
            clv_online=bool(clv_runtime["clv_online"]),
            clv_window_seconds=int(clv_runtime["clv_window_seconds"]),
            clv_interval=str(clv_runtime["clv_interval"]),
            clv_fidelity=int(clv_runtime["clv_fidelity"]),
        )

    if bool(config.get("compute_clv", DEFAULT_COMPUTE_CLV)) and clv_runtime is not None:
        _apply_clv_enrichment(
            output_dir=output_dir,
            positions=positions,
            clickhouse_client=clv_runtime["clickhouse_client"],
            clob_client=clv_runtime["clob_client"],
            clv_online=bool(clv_runtime["clv_online"]),
            clv_window_seconds=int(clv_runtime["clv_window_seconds"]),
            clv_interval=str(clv_runtime["clv_interval"]),
            clv_fidelity=int(clv_runtime["clv_fidelity"]),
        )
    # Build a local market-metadata map from positions that already carry metadata.
    # When backfill is enabled this lets the coverage builder fill in missing
    # market_slug/question/outcome_name from sibling records in the same dossier.
    market_metadata_map: Optional[Dict[str, Dict[str, str]]] = None
    metadata_conflicts_count = 0
    metadata_conflict_sample: list[Dict[str, Any]] = []
    if config.get("backfill", DEFAULT_BACKFILL):
        metadata_result = _build_metadata_map_from_positions(positions)
        market_metadata_map = metadata_result["map"]
        metadata_conflicts_count = metadata_result["conflicts_count"]
        metadata_conflict_sample = metadata_result["conflict_sample"]
    # Normalize position_notional_usd so weighted metrics are non-null.
    _normalize_position_notional(positions)
    notional_debug = _build_notional_weight_debug(positions)

    coverage_report = build_coverage_report(
        positions=positions,
        run_id=run_id,
        user_slug=username_slug,
        wallet=proxy_wallet,
        proxy_wallet=proxy_wallet,
        resolution_enrichment_response=resolution_enrichment_response,
        entry_price_tiers=config.get("entry_price_tiers"),
        fee_config=config.get("fee_config"),
        market_metadata_map=market_metadata_map,
        metadata_conflicts_count=metadata_conflicts_count,
        metadata_conflict_sample=metadata_conflict_sample if metadata_conflict_sample else None,
    )
    # Defensive check: scan trust artifacts must use split UID coverage schema.
    if "trade_uid_coverage" in coverage_report:
        coverage_report.pop("trade_uid_coverage", None)
    for required_key in ("deterministic_trade_uid_coverage", "fallback_uid_coverage"):
        if required_key not in coverage_report:
            raise TrustArtifactError(f"Coverage report missing required field: {required_key}")
    warnings = coverage_report.setdefault("warnings", [])
    if not isinstance(warnings, list):
        warnings = []
        coverage_report["warnings"] = warnings

    if clv_preflight_artifact is not None:
        preflight_payload = clv_preflight_artifact.get("payload", {})
        preflight_ok = bool(preflight_payload.get("preflight_ok"))
        if not preflight_ok:
            error_class = str(preflight_payload.get("error_class") or "UNKNOWN")
            next_action = str(preflight_payload.get("recommended_next_action") or "").strip()
            warning = f"clv_preflight_failed: error_class={error_class}"
            if next_action:
                warning = f"{warning}. {next_action}"
            if warning not in warnings:
                warnings.append(warning)
            print(f"Warning: {warning}", file=sys.stderr)

    if clv_warm_cache_artifact is not None:
        warm_payload = clv_warm_cache_artifact.get("payload", {})
        warm_failed = _coerce_non_negative_int(warm_payload.get("failed"))
        if warm_failed > 0:
            reasons = warm_payload.get("failure_reason_counts") or {}
            warning = (
                "clv_warm_cache_failures: "
                f"failed={warm_failed}, reasons={json.dumps(reasons, separators=(',', ':'))}"
            )
            if warning not in warnings:
                warnings.append(warning)
            print(f"Warning: {warning}", file=sys.stderr)

    if hydration_meta.get("history_positions_fallback_used"):
        endpoints_text = ", ".join(endpoints_used) if endpoints_used else "(none)"
        export_positions_count = hydration_meta.get("export_positions_count")
        export_positions_text = (
            str(_coerce_non_negative_int(export_positions_count))
            if export_positions_count is not None
            else "n/a"
        )
        history_positions_raw = hydration_meta.get("history_positions_count_raw")
        history_positions_raw_text = (
            str(_coerce_non_negative_int(history_positions_raw))
            if history_positions_raw is not None
            else "n/a"
        )
        history_declared_positions_count = hydration_meta.get("history_declared_positions_count")
        declared_positions_text = (
            str(_coerce_non_negative_int(history_declared_positions_count))
            if history_declared_positions_count is not None
            else "n/a"
        )
        history_positions_len = hydration_meta.get("history_positions_len")
        history_positions_len_text = (
            str(_coerce_non_negative_int(history_positions_len))
            if history_positions_len is not None
            else "n/a"
        )
        fallback_warning = (
            "history_positions_fallback_used: /api/export/user_dossier/history reported "
            f"positions_count={history_positions_raw_text}, but dossier payload declared "
            f"positions_count={declared_positions_text} and contained positions_rows={history_positions_len_text}. "
            "Using dossier positions list for coverage/segment/audit inputs. "
            f"endpoints_used={endpoints_text}; "
            f"/api/export/user_dossier positions_count={export_positions_text}; "
            f"/api/export/user_dossier/history positions_count={history_positions_raw_text}."
        )
        if fallback_warning not in warnings:
            warnings.append(fallback_warning)
        print(f"Warning: {fallback_warning}", file=sys.stderr)

    positions_total = int(coverage_report.get("totals", {}).get("positions_total") or 0)
    if positions_total == 0:
        wallet_for_warning = proxy_wallet or str(resolve_response.get("proxy_wallet") or config["user"])
        endpoints_text = ", ".join(endpoints_used) if endpoints_used else "(none)"
        zero_warning = (
            f"positions_total=0 for wallet={wallet_for_warning}; endpoints_used={endpoints_text}. "
            "Next checks: confirm wallet mapping/proxy_wallet and increase lookback (export days/history limit)."
        )
        if zero_warning not in warnings:
            warnings.append(zero_warning)
        print(f"Warning: {zero_warning}", file=sys.stderr)
        if declared_positions_count > 0:
            mismatch_warning = (
                f"dossier_declares_positions_count={declared_positions_count} but exported positions rows=0. "
                "Likely lifecycle export/schema mismatch (check user_trade_lifecycle_enriched/user_trade_lifecycle)."
            )
            if mismatch_warning not in warnings:
                warnings.append(mismatch_warning)
            print(f"Warning: {mismatch_warning}", file=sys.stderr)

    resolution_coverage = coverage_report.get("resolution_coverage", {})
    resolved_total = int(resolution_coverage.get("resolved_total") or 0)
    enrichment_truncated = bool((resolution_enrichment_response or {}).get("truncated"))
    if enrichment_truncated and positions_total > 0 and resolved_total == 0:
        total_candidates = _coerce_non_negative_int(
            (resolution_enrichment_response or {}).get("candidates_total")
        )
        selected_candidates = _coerce_non_negative_int(
            (resolution_enrichment_response or {}).get("candidates_selected")
        )
        max_candidates = _coerce_non_negative_int(
            (resolution_enrichment_response or {}).get("max_candidates")
        )
        truncation_warning = (
            "resolution_enrichment_truncated_with_zero_resolved: "
            f"selected={selected_candidates}/{total_candidates} "
            f"(max_candidates={max_candidates}), positions_total={positions_total}, resolved_total=0. "
            "Coverage outcome distribution is likely invalid."
        )
        if truncation_warning not in warnings:
            warnings.append(truncation_warning)
        print(f"Warning: {truncation_warning}", file=sys.stderr)

    coverage_paths = write_coverage_report(coverage_report, output_dir, write_markdown=True)

    hypothesis_candidates_path = write_hypothesis_candidates(
        candidates=coverage_report.get("hypothesis_candidates", []),
        output_dir=output_dir,
        generated_at=coverage_report.get("generated_at", ""),
        run_id=run_id,
        user_slug=username_slug,
        wallet=proxy_wallet,
    )

    segment_analysis_path = output_dir / "segment_analysis.json"
    segment_analysis_payload = {
        "generated_at": coverage_report.get("generated_at"),
        "run_id": run_id,
        "user_slug": username_slug,
        "wallet": proxy_wallet,
        "segment_analysis": coverage_report.get("segment_analysis", {}),
    }
    segment_analysis_path.write_text(
        json.dumps(segment_analysis_payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )

    # Emit resolution_parity_debug.json for cross-run comparison.
    enrichment_cfg = effective_enrichment_config or _effective_resolution_config(config)
    parity_payload = enrichment_request_payload or enrichment_cfg
    parity_debug = _build_parity_debug(positions, parity_payload, resolution_enrichment_response)
    parity_debug_path = output_dir / "resolution_parity_debug.json"
    parity_debug_path.write_text(
        json.dumps(parity_debug, indent=2, sort_keys=True), encoding="utf-8"
    )

    notional_debug_path = output_dir / "notional_weight_debug.json"
    notional_debug_path.write_text(
        json.dumps(notional_debug, indent=2, sort_keys=True), encoding="utf-8"
    )

    gamma_sample_path = _write_gamma_markets_sample(
        output_dir=output_dir,
        config=config,
        ingest_markets_response=ingest_markets_response,
    )

    raw_seed = config.get("audit_seed")
    audit_seed = raw_seed if isinstance(raw_seed, int) else DEFAULT_AUDIT_SEED
    audit_sample = config.get("audit_sample")  # None => all positions; int => sample
    audit_report_path = write_audit_coverage_report(
        run_root=output_dir,
        user_input=str(config["user"]),
        user_slug=username_slug,
        wallet=proxy_wallet,
        run_id=run_id,
        sample=audit_sample,
        seed=audit_seed,
        fmt="md",
        output_path=output_dir / "audit_coverage_report.md",
    )

    wallets = [w for w in dict.fromkeys([proxy_wallet, resolve_response.get("proxy_wallet")]) if w]
    output_paths = {
        "run_root": output_dir.as_posix(),
        "dossier_path": output_dir.as_posix(),
        "dossier_json": (output_dir / "dossier.json").as_posix(),
        "coverage_reconciliation_report_json": coverage_paths["json"],
        "segment_analysis_json": segment_analysis_path.as_posix(),
        "hypothesis_candidates_json": hypothesis_candidates_path,
        "resolution_parity_debug_json": parity_debug_path.as_posix(),
        "notional_weight_debug_json": notional_debug_path.as_posix(),
    }
    if clv_preflight_artifact is not None:
        output_paths["clv_preflight_json"] = str(clv_preflight_artifact.get("path"))
    if clv_warm_cache_artifact is not None:
        output_paths["clv_warm_cache_summary_json"] = str(clv_warm_cache_artifact.get("path"))
    if gamma_sample_path is not None:
        output_paths["gamma_markets_sample_json"] = gamma_sample_path.as_posix()
    if "md" in coverage_paths:
        output_paths["coverage_reconciliation_report_md"] = coverage_paths["md"]
    output_paths["audit_coverage_report_md"] = audit_report_path.as_posix()

    effective_config = {
        **config,
        "trust_artifact_window_days": TRUST_ARTIFACT_WINDOW_DAYS,
        "trust_artifact_max_trades": TRUST_ARTIFACT_MAX_TRADES,
        # Persist effective enrichment knobs explicitly in the manifest.
        "resolution_enrichment_effective": enrichment_cfg,
    }
    manifest = build_run_manifest(
        run_id=run_id,
        started_at=started_at,
        command_name="scan",
        argv=argv,
        user_input=str(config["user"]),
        user_slug=username_slug,
        wallets=wallets,
        output_paths=output_paths,
        effective_config=effective_config,
        finished_at=_now_utc_iso(),
    )
    manifest["diagnostics"] = {
        "clv_preflight": (clv_preflight_artifact or {}).get("payload"),
        "clv_warm_cache": (clv_warm_cache_artifact or {}).get("payload"),
    }
    manifest_path = write_run_manifest(manifest, output_dir)

    emitted = {
        "coverage_reconciliation_report_json": coverage_paths["json"],
        "segment_analysis_json": segment_analysis_path.as_posix(),
        "hypothesis_candidates_json": hypothesis_candidates_path,
        "run_manifest": Path(manifest_path).as_posix(),
        "resolution_parity_debug_json": parity_debug_path.as_posix(),
        "notional_weight_debug_json": notional_debug_path.as_posix(),
    }
    if clv_preflight_artifact is not None:
        emitted["clv_preflight_json"] = str(clv_preflight_artifact.get("path"))
    if clv_warm_cache_artifact is not None:
        emitted["clv_warm_cache_summary_json"] = str(clv_warm_cache_artifact.get("path"))
    if gamma_sample_path is not None:
        emitted["gamma_markets_sample_json"] = gamma_sample_path.as_posix()
    if "md" in coverage_paths:
        emitted["coverage_reconciliation_report_md"] = coverage_paths["md"]
    if audit_report_path is not None:
        emitted["audit_coverage_report_md"] = audit_report_path.as_posix()
    return emitted


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a one-shot Polymarket scan via the PolyTool API.",
    )
    parser.add_argument("--user", help="Target Polymarket username (@name) or wallet address")
    parser.add_argument("--max-pages", type=int, help="Max pages to fetch for trade ingestion")
    parser.add_argument(
        "--bucket",
        choices=sorted(ALLOWED_BUCKETS),
        help="Bucket type for detectors (day, hour, week)",
    )
    parser.add_argument(
        "--no-backfill",
        action="store_true",
        default=None,
        help="Disable backfill of missing market mappings",
    )
    parser.add_argument(
        "--ingest-markets",
        action="store_true",
        default=None,
        help="Ingest active market metadata before scanning",
    )
    parser.add_argument(
        "--ingest-activity",
        action="store_true",
        default=None,
        help="Ingest user activity before running detectors",
    )
    parser.add_argument(
        "--ingest-positions",
        action="store_true",
        default=None,
        help="Ingest a user positions snapshot before running detectors",
    )
    parser.add_argument(
        "--compute-pnl",
        action="store_true",
        default=None,
        help="Compute PnL after running detectors",
    )
    parser.add_argument(
        "--compute-opportunities",
        action="store_true",
        default=None,
        help="Compute low-cost opportunity candidates after scanning",
    )
    parser.add_argument(
        "--snapshot-books",
        action="store_true",
        default=None,
        help="Snapshot orderbook metrics before computing PnL/arb",
    )
    parser.add_argument(
        "--enrich-resolutions",
        action="store_true",
        default=None,
        help=(
            "Run scan-stage resolution enrichment (ClickHouse -> on-chain -> subgraph -> gamma) "
            "before detectors/export"
        ),
    )
    parser.add_argument(
        "--compute-clv",
        action="store_true",
        default=None,
        help=(
            "Compute per-position CLV fields from cache-first CLOB /prices-history "
            "and persist into dossier + coverage artifacts."
        ),
    )
    parser.add_argument(
        "--warm-clv-cache",
        action="store_true",
        default=None,
        help=(
            "Warm market_price_snapshots via bounded /prices-history fetches before CLV compute. "
            "Writes a warm-cache summary artifact and never blocks the scan."
        ),
    )
    parser.add_argument(
        "--clv-offline",
        action="store_true",
        default=None,
        help="Disable live /prices-history fetches; resolve CLV from ClickHouse cache only.",
    )
    parser.add_argument(
        "--clv-window-minutes",
        type=int,
        metavar="MINUTES",
        help=f"Closing-price lookback window in minutes (default: {DEFAULT_CLV_WINDOW_MINUTES}).",
    )
    parser.add_argument(
        "--resolution-max-candidates",
        type=int,
        help="Hard cap on tokens to enrich (default: 500)",
    )
    parser.add_argument(
        "--resolution-batch-size",
        type=int,
        help="Batch size per enrichment wave (default: 25)",
    )
    parser.add_argument(
        "--resolution-max-concurrency",
        type=int,
        help="Max concurrent provider calls per batch (default: 4)",
    )
    parser.add_argument(
        "--debug-export",
        action="store_true",
        default=None,
        help="Print trust artifact export diagnostics (wallet, endpoints, counts)",
    )
    parser.add_argument(
        "--audit-sample",
        type=int,
        metavar="N",
        help=(
            "Limit the audit report to a deterministic sample of N positions. "
            "Omit to include ALL positions (default)."
        ),
    )
    parser.add_argument(
        "--audit-seed",
        type=int,
        metavar="INT",
        help=f"Sampling seed when --audit-sample is set (default: {DEFAULT_AUDIT_SEED}).",
    )
    parser.add_argument(
        "--config",
        help="Path to polytool.yaml config file (defaults to ./polytool.yaml if present)",
    )
    parser.add_argument("--api-base-url", help="Base URL for the PolyTool API")
    return parser


def build_config(args: argparse.Namespace) -> Dict[str, Any]:
    local_config = _load_local_config(args.config)
    entry_price_tiers = _extract_entry_price_tiers(local_config)
    fee_config = _extract_fee_config(local_config)

    env_user = os.getenv("TARGET_USER")
    env_max_pages = parse_int(os.getenv("SCAN_MAX_PAGES"), "SCAN_MAX_PAGES")
    env_bucket = os.getenv("SCAN_BUCKET")
    env_backfill = parse_bool(os.getenv("SCAN_BACKFILL"), "SCAN_BACKFILL")
    env_ingest_markets = parse_bool(os.getenv("SCAN_INGEST_MARKETS"), "SCAN_INGEST_MARKETS")
    env_ingest_activity = parse_bool(os.getenv("SCAN_INGEST_ACTIVITY"), "SCAN_INGEST_ACTIVITY")
    env_ingest_positions = parse_bool(os.getenv("SCAN_INGEST_POSITIONS"), "SCAN_INGEST_POSITIONS")
    env_compute_pnl = parse_bool(os.getenv("SCAN_COMPUTE_PNL"), "SCAN_COMPUTE_PNL")
    env_compute_opportunities = parse_bool(
        os.getenv("SCAN_COMPUTE_OPPORTUNITIES"), "SCAN_COMPUTE_OPPORTUNITIES"
    )
    env_snapshot_books = parse_bool(os.getenv("SCAN_SNAPSHOT_BOOKS"), "SCAN_SNAPSHOT_BOOKS")
    env_enrich_resolutions = parse_bool(
        os.getenv("SCAN_ENRICH_RESOLUTIONS"), "SCAN_ENRICH_RESOLUTIONS"
    )
    env_compute_clv = parse_bool(os.getenv("SCAN_COMPUTE_CLV"), "SCAN_COMPUTE_CLV")
    env_warm_clv_cache = parse_bool(os.getenv("SCAN_WARM_CLV_CACHE"), "SCAN_WARM_CLV_CACHE")
    env_clv_offline = parse_bool(os.getenv("SCAN_CLV_OFFLINE"), "SCAN_CLV_OFFLINE")
    env_clv_window_minutes = parse_int(
        os.getenv("SCAN_CLV_WINDOW_MINUTES"),
        "SCAN_CLV_WINDOW_MINUTES",
    )
    env_clv_interval = os.getenv("SCAN_CLV_INTERVAL")
    env_clv_fidelity = os.getenv("SCAN_CLV_FIDELITY")
    env_resolution_max_candidates = parse_int(
        os.getenv("SCAN_RESOLUTION_MAX_CANDIDATES"),
        "SCAN_RESOLUTION_MAX_CANDIDATES",
    )
    env_resolution_batch_size = parse_int(
        os.getenv("SCAN_RESOLUTION_BATCH_SIZE"),
        "SCAN_RESOLUTION_BATCH_SIZE",
    )
    env_resolution_max_concurrency = parse_int(
        os.getenv("SCAN_RESOLUTION_MAX_CONCURRENCY"),
        "SCAN_RESOLUTION_MAX_CONCURRENCY",
    )
    env_debug_export = parse_bool(os.getenv("SCAN_DEBUG_EXPORT"), "SCAN_DEBUG_EXPORT")
    env_api_base = os.getenv("API_BASE_URL")
    env_timeout = parse_float(os.getenv("SCAN_HTTP_TIMEOUT_SECONDS"), "SCAN_HTTP_TIMEOUT_SECONDS")

    user = args.user or (env_user.strip() if env_user else "")
    max_pages = args.max_pages or env_max_pages or DEFAULT_MAX_PAGES
    bucket = (args.bucket or env_bucket or DEFAULT_BUCKET).lower()
    api_base_url = args.api_base_url or env_api_base or DEFAULT_API_BASE_URL
    timeout_seconds = env_timeout or DEFAULT_TIMEOUT_SECONDS

    if args.no_backfill is True:
        backfill = False
    elif env_backfill is not None:
        backfill = env_backfill
    else:
        backfill = DEFAULT_BACKFILL

    if args.ingest_markets is True:
        ingest_markets = True
    elif env_ingest_markets is not None:
        ingest_markets = env_ingest_markets
    else:
        ingest_markets = DEFAULT_INGEST_MARKETS

    if args.ingest_activity is True:
        ingest_activity = True
    elif env_ingest_activity is not None:
        ingest_activity = env_ingest_activity
    else:
        ingest_activity = DEFAULT_INGEST_ACTIVITY

    if args.ingest_positions is True:
        ingest_positions = True
    elif env_ingest_positions is not None:
        ingest_positions = env_ingest_positions
    else:
        ingest_positions = DEFAULT_INGEST_POSITIONS

    if args.compute_pnl is True:
        compute_pnl = True
    elif env_compute_pnl is not None:
        compute_pnl = env_compute_pnl
    else:
        compute_pnl = DEFAULT_COMPUTE_PNL

    if args.compute_opportunities is True:
        compute_opportunities = True
    elif env_compute_opportunities is not None:
        compute_opportunities = env_compute_opportunities
    else:
        compute_opportunities = DEFAULT_COMPUTE_OPPORTUNITIES

    if args.snapshot_books is True:
        snapshot_books = True
    elif env_snapshot_books is not None:
        snapshot_books = env_snapshot_books
    else:
        snapshot_books = DEFAULT_SNAPSHOT_BOOKS

    if args.enrich_resolutions is True:
        enrich_resolutions = True
    elif env_enrich_resolutions is not None:
        enrich_resolutions = env_enrich_resolutions
    else:
        enrich_resolutions = DEFAULT_ENRICH_RESOLUTIONS

    if args.compute_clv is True:
        compute_clv = True
    elif env_compute_clv is not None:
        compute_clv = env_compute_clv
    else:
        compute_clv = DEFAULT_COMPUTE_CLV

    if args.warm_clv_cache is True:
        warm_clv_cache = True
    elif env_warm_clv_cache is not None:
        warm_clv_cache = env_warm_clv_cache
    else:
        warm_clv_cache = DEFAULT_WARM_CLV_CACHE

    if args.clv_offline is True:
        clv_online = False
    elif env_clv_offline is not None:
        clv_online = not env_clv_offline
    else:
        clv_online = DEFAULT_CLV_ONLINE

    clv_window_minutes = (
        args.clv_window_minutes
        or env_clv_window_minutes
        or DEFAULT_CLV_WINDOW_MINUTES
    )
    clv_interval = str(env_clv_interval or DEFAULT_CLV_INTERVAL).strip() or DEFAULT_CLV_INTERVAL
    clv_fidelity: Any = env_clv_fidelity if env_clv_fidelity is not None else DEFAULT_CLV_FIDELITY
    if isinstance(clv_fidelity, str):
        clv_fidelity = clv_fidelity.strip() or DEFAULT_CLV_FIDELITY

    resolution_max_candidates = (
        args.resolution_max_candidates
        or env_resolution_max_candidates
        or DEFAULT_RESOLUTION_MAX_CANDIDATES
    )
    resolution_batch_size = (
        args.resolution_batch_size
        or env_resolution_batch_size
        or DEFAULT_RESOLUTION_BATCH_SIZE
    )
    resolution_max_concurrency = (
        args.resolution_max_concurrency
        or env_resolution_max_concurrency
        or DEFAULT_RESOLUTION_MAX_CONCURRENCY
    )

    if args.debug_export is True:
        debug_export = True
    elif env_debug_export is not None:
        debug_export = env_debug_export
    else:
        debug_export = False

    return {
        "user": user,
        "max_pages": max_pages,
        "bucket": bucket,
        "backfill": backfill,
        "ingest_markets": ingest_markets,
        "ingest_activity": ingest_activity,
        "ingest_positions": ingest_positions,
        "compute_pnl": compute_pnl,
        "compute_opportunities": compute_opportunities,
        "snapshot_books": snapshot_books,
        "enrich_resolutions": enrich_resolutions,
        "compute_clv": compute_clv,
        "warm_clv_cache": warm_clv_cache,
        "clv_online": clv_online,
        "clv_window_minutes": clv_window_minutes,
        "clv_interval": clv_interval,
        "clv_fidelity": clv_fidelity,
        "resolution_max_candidates": resolution_max_candidates,
        "resolution_batch_size": resolution_batch_size,
        "resolution_max_concurrency": resolution_max_concurrency,
        "debug_export": debug_export,
        "audit_sample": args.audit_sample,
        "audit_seed": args.audit_seed,
        "entry_price_tiers": entry_price_tiers,
        "fee_config": fee_config,
        "api_base_url": api_base_url,
        "timeout_seconds": timeout_seconds,
    }


def validate_config(config: Dict[str, Any]) -> None:
    errors = []
    if not config["user"]:
        errors.append("TARGET_USER or --user is required.")
    if config["bucket"] not in ALLOWED_BUCKETS:
        errors.append(f"SCAN_BUCKET must be one of {sorted(ALLOWED_BUCKETS)}.")
    if not isinstance(config["max_pages"], int) or config["max_pages"] <= 0:
        errors.append("SCAN_MAX_PAGES must be a positive integer.")
    if not isinstance(config.get("resolution_max_candidates"), int) or config["resolution_max_candidates"] <= 0:
        errors.append("SCAN_RESOLUTION_MAX_CANDIDATES must be a positive integer.")
    if not isinstance(config.get("resolution_batch_size"), int) or config["resolution_batch_size"] <= 0:
        errors.append("SCAN_RESOLUTION_BATCH_SIZE must be a positive integer.")
    if not isinstance(config.get("resolution_max_concurrency"), int) or config["resolution_max_concurrency"] <= 0:
        errors.append("SCAN_RESOLUTION_MAX_CONCURRENCY must be a positive integer.")
    if not isinstance(config.get("clv_window_minutes"), int) or config["clv_window_minutes"] <= 0:
        errors.append("SCAN_CLV_WINDOW_MINUTES must be a positive integer.")
    clv_interval = str(config.get("clv_interval") or "").strip()
    if not clv_interval:
        errors.append("SCAN_CLV_INTERVAL must be a non-empty string.")
    clv_fidelity = str(config.get("clv_fidelity") or "").strip()
    if not clv_fidelity:
        errors.append("SCAN_CLV_FIDELITY must be a non-empty string.")
    audit_sample = config.get("audit_sample")
    if audit_sample is not None:
        if not isinstance(audit_sample, int) or audit_sample < 0:
            errors.append("--audit-sample must be a non-negative integer.")
    audit_seed = config.get("audit_seed")
    if audit_seed is not None and not isinstance(audit_seed, int):
        errors.append("--audit-seed must be an integer.")
    fee_config = config.get("fee_config")
    if not isinstance(fee_config, dict):
        errors.append("fee_config must be a mapping.")
    else:
        try:
            fee_rate = float(fee_config.get("profit_fee_rate"))
            if fee_rate < 0:
                raise ValueError("negative")
        except (TypeError, ValueError):
            errors.append("fee_config.profit_fee_rate must be a non-negative number.")
        source_label = str(fee_config.get("source_label") or "").strip()
        if not source_label:
            errors.append("fee_config.source_label must be a non-empty string.")

    if errors:
        for err in errors:
            print(f"Config error: {err}", file=sys.stderr)
        raise SystemExit(1)

    if config["timeout_seconds"] <= 0:
        print("Config error: SCAN_HTTP_TIMEOUT_SECONDS must be positive.", file=sys.stderr)
        raise SystemExit(1)
    if config["resolution_max_candidates"] > 1000:
        print("Config error: SCAN_RESOLUTION_MAX_CANDIDATES must be <= 1000.", file=sys.stderr)
        raise SystemExit(1)
    if config["resolution_batch_size"] > 200:
        print("Config error: SCAN_RESOLUTION_BATCH_SIZE must be <= 200.", file=sys.stderr)
        raise SystemExit(1)
    if config["resolution_max_concurrency"] > 16:
        print("Config error: SCAN_RESOLUTION_MAX_CONCURRENCY must be <= 16.", file=sys.stderr)
        raise SystemExit(1)


def summarize_detector_results(results: list[dict]) -> list[dict]:
    top_by_detector: Dict[str, dict] = {}
    for item in results:
        name = item.get("detector") or "unknown"
        score = item.get("score")
        if score is None:
            continue
        current = top_by_detector.get(name)
        if current is None or score > current["score"]:
            top_by_detector[name] = {
                "detector": name,
                "score": score,
                "label": item.get("label"),
                "bucket_start": item.get("bucket_start"),
            }
    return sorted(top_by_detector.values(), key=lambda row: row["score"], reverse=True)


def print_summary(
    config: Dict[str, Any],
    resolve_response: Dict[str, Any],
    ingest_response: Dict[str, Any],
    resolution_enrichment_response: Optional[Dict[str, Any]],
    activity_response: Optional[Dict[str, Any]],
    positions_response: Optional[Dict[str, Any]],
    snapshot_response: Optional[Dict[str, Any]],
    detectors_response: Dict[str, Any],
    pnl_response: Optional[Dict[str, Any]],
    opportunities_response: Optional[Dict[str, Any]],
    dossier_export_response: Optional[Dict[str, Any]] = None,
    trust_artifacts: Optional[Dict[str, str]] = None,
) -> None:
    username = resolve_response.get("username") or config["user"]
    proxy_wallet = resolve_response.get("proxy_wallet") or "unknown"

    print("")
    print("Scan complete")
    print(f"Username: {username}")
    print(f"Proxy wallet: {proxy_wallet}")

    print(
        "Trades ingested: "
        f"pages={ingest_response.get('pages_fetched')}, "
        f"fetched={ingest_response.get('rows_fetched_total')}, "
        f"written={ingest_response.get('rows_written')}, "
        f"distinct={ingest_response.get('distinct_trade_uids_total')}"
    )

    if resolution_enrichment_response:
        selected_candidates = resolution_enrichment_response.get("candidates_selected")
        if selected_candidates is None:
            selected_candidates = resolution_enrichment_response.get("candidates_processed")
        truncated = bool(resolution_enrichment_response.get("truncated"))
        print(
            "Resolution enrichment: "
            f"candidates={resolution_enrichment_response.get('candidates_total')}, "
            f"selected={selected_candidates}, "
            f"truncated={truncated}, "
            f"processed={resolution_enrichment_response.get('candidates_processed')}, "
            f"cached={resolution_enrichment_response.get('cached_hits')}, "
            f"written={resolution_enrichment_response.get('resolved_written')}, "
            f"unresolved={resolution_enrichment_response.get('unresolved_network')}, "
            f"skipped_missing={resolution_enrichment_response.get('skipped_missing_identifiers')}, "
            f"errors={resolution_enrichment_response.get('errors')}"
        )
        warnings = resolution_enrichment_response.get("warnings") or []
        if isinstance(warnings, list):
            for warning in warnings[:3]:
                print(f"  Warning: {warning}")

    if activity_response:
        print(
            "Activity ingested: "
            f"pages={activity_response.get('pages_fetched')}, "
            f"fetched={activity_response.get('rows_fetched_total')}, "
            f"written={activity_response.get('rows_written')}, "
            f"distinct={activity_response.get('distinct_activity_uids_total')}"
        )

    if positions_response:
        print(
            "Positions snapshot: "
            f"rows={positions_response.get('rows_written')}, "
            f"snapshot_ts={positions_response.get('snapshot_ts')}"
        )

    if snapshot_response:
        # Token selection diagnostics
        candidates = snapshot_response.get('tokens_candidates_before_filter', 0)
        with_metadata = snapshot_response.get('tokens_with_market_metadata', 0)
        after_filter = snapshot_response.get('tokens_after_active_filter', 0)
        selected = snapshot_response.get('tokens_selected_total', 0)
        # Execution results
        ok = snapshot_response.get('tokens_ok', 0)
        error = snapshot_response.get('tokens_error', 0)
        no_orderbook = snapshot_response.get('tokens_no_orderbook', 0)
        http_429 = snapshot_response.get('tokens_http_429', 0)
        http_5xx = snapshot_response.get('tokens_http_5xx', 0)
        skipped_ttl = snapshot_response.get('tokens_skipped_no_orderbook_ttl', 0)
        no_ok_reason = snapshot_response.get('no_ok_reason')

        print(
            f"Books snapshotted: candidates={candidates} -> "
            f"metadata={with_metadata} -> active={after_filter} -> selected={selected}"
        )
        print(
            f"  Results: ok={ok}, empty={snapshot_response.get('tokens_empty', 0)}, "
            f"one_sided={snapshot_response.get('tokens_one_sided', 0)}, "
            f"no_orderbook={no_orderbook}, error={error} "
            f"(429={http_429}, 5xx={http_5xx}), skipped_ttl={skipped_ttl}"
        )
        if no_ok_reason:
            print(f"  Reason: {no_ok_reason}")

    backfill_stats = detectors_response.get("backfill_stats")
    if backfill_stats:
        backfill_text = json.dumps(backfill_stats, separators=(",", ":"))
    else:
        backfill_text = "disabled" if not config["backfill"] else "none"
    print(f"Backfill: {backfill_text}")

    detector_results = summarize_detector_results(detectors_response.get("results", []))
    if detector_results:
        print("Detector scores:")
        for item in detector_results:
            bucket_start = item.get("bucket_start") or "n/a"
            print(
                f"  {item['detector']}: score={item['score']} "
                f"label={item.get('label')} bucket_start={bucket_start}"
            )
    else:
        print("Detector scores: none")

    if pnl_response:
        latest_bucket = pnl_response.get("latest_bucket") or {}
        if latest_bucket:
            print(
                "PnL latest bucket: "
                f"realized={latest_bucket.get('realized_pnl')}, "
                f"mtm={latest_bucket.get('mtm_pnl_estimate')}, "
                f"exposure={latest_bucket.get('exposure_notional_estimate')}"
            )
        else:
            print("PnL latest bucket: none")

    if opportunities_response:
        print(
            "Opportunities: "
            f"candidates={opportunities_response.get('candidates_considered')}, "
            f"returned={opportunities_response.get('returned_count')}, "
            f"bucket={opportunities_response.get('bucket_start')}"
        )

    api_base_url = config["api_base_url"].rstrip("/")
    print("")
    print("URLs")
    print("  Grafana: http://localhost:3000")
    print("  Dashboards: PolyTool - User Trades, PolyTool - Strategy Detectors, PolyTool - PnL")
    print(f"  Swagger: {api_base_url}/docs")

    if dossier_export_response:
        print("")
        print("Trust artifacts")
        print(f"  Run root: {dossier_export_response.get('artifact_path')}")
        if trust_artifacts:
            for label, path in trust_artifacts.items():
                print(f"  {label}: {path}")


def run_scan(
    config: Dict[str, Any],
    argv: Optional[list[str]] = None,
    started_at: Optional[str] = None,
) -> Dict[str, str]:
    api_base_url = config["api_base_url"]
    timeout_seconds = config["timeout_seconds"]
    safe_argv = argv or []
    started_at_value = started_at or _now_utc_iso()

    ingest_markets_response = None
    if config["ingest_markets"]:
        ingest_markets_response = post_json(
            api_base_url,
            "/api/ingest/markets",
            {
                "active_only": True,
                "debug_sample": bool(config.get("debug_export")),
            },
            timeout=timeout_seconds,
        )

    activity_response = None
    if config["ingest_activity"]:
        activity_response = post_json(
            api_base_url,
            "/api/ingest/activity",
            {"user": config["user"], "max_pages": config["max_pages"]},
            timeout=timeout_seconds,
        )

    positions_response = None
    if config["ingest_positions"]:
        positions_response = post_json(
            api_base_url,
            "/api/ingest/positions",
            {"user": config["user"]},
            timeout=timeout_seconds,
        )

    snapshot_response = None
    if config["snapshot_books"]:
        snapshot_response = post_json(
            api_base_url,
            "/api/snapshot/books",
            {"user": config["user"]},
            timeout=timeout_seconds,
        )

    resolve_response = post_json(
        api_base_url,
        "/api/resolve",
        {"input": config["user"]},
        timeout=timeout_seconds,
    )
    ingest_response = post_json(
        api_base_url,
        "/api/ingest/trades",
        {"user": config["user"], "max_pages": config["max_pages"]},
        timeout=timeout_seconds,
    )

    resolution_enrichment_response = None
    effective_enrichment_config = _effective_resolution_config(config)
    enrichment_request_payload = {"user": config["user"], **effective_enrichment_config}

    detectors_response = post_json(
        api_base_url,
        "/api/run/detectors",
        {
            "user": config["user"],
            "bucket": config["bucket"],
            "backfill_mappings": config["backfill"],
        },
        timeout=timeout_seconds,
    )

    pnl_response = None
    if config["compute_pnl"]:
        pnl_response = post_json(
            api_base_url,
            "/api/compute/pnl",
            {"user": config["user"], "bucket": config["bucket"]},
            timeout=timeout_seconds,
        )

    opportunities_response = None
    if config["compute_opportunities"]:
        opportunities_response = post_json(
            api_base_url,
            "/api/compute/opportunities",
            {"user": config["user"], "bucket": config["bucket"]},
            timeout=timeout_seconds,
        )

    if config.get("enrich_resolutions", DEFAULT_ENRICH_RESOLUTIONS):
        resolution_enrichment_response = post_json(
            api_base_url,
            "/api/enrich/resolutions",
            enrichment_request_payload,
            timeout=timeout_seconds,
        )

    dossier_export_response = post_json(
        api_base_url,
        "/api/export/user_dossier",
        {
            "user": config["user"],
            "days": TRUST_ARTIFACT_WINDOW_DAYS,
            "max_trades": TRUST_ARTIFACT_MAX_TRADES,
        },
        timeout=timeout_seconds,
    )
    trust_artifacts = _emit_trust_artifacts(
        config=config,
        argv=safe_argv,
        started_at=started_at_value,
        resolve_response=resolve_response,
        dossier_export_response=dossier_export_response,
        ingest_markets_response=ingest_markets_response,
        resolution_enrichment_response=resolution_enrichment_response,
        effective_enrichment_config=effective_enrichment_config,
        enrichment_request_payload=enrichment_request_payload,
    )

    print_summary(
        config,
        resolve_response,
        ingest_response,
        resolution_enrichment_response,
        activity_response,
        positions_response,
        snapshot_response,
        detectors_response,
        pnl_response,
        opportunities_response,
        dossier_export_response=dossier_export_response,
        trust_artifacts=trust_artifacts,
    )
    return trust_artifacts


def main(argv: Optional[list[str]] = None) -> int:
    env_values = load_env_file(os.path.join(os.getcwd(), ".env"))
    apply_env_defaults(env_values)

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = build_config(args)
        validate_config(config)
        run_scan(config, argv=argv or [], started_at=_now_utc_iso())
        return 0
    except ApiError as exc:
        print(
            f"API error: {exc.method} {exc.url} -> {exc.status}",
            file=sys.stderr,
        )
        if exc.body:
            print(f"Response body: {exc.body}", file=sys.stderr)
        if exc.status in (502, 503, 504):
            print("Start docker compose up -d --build", file=sys.stderr)
        return 1
    except NetworkError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        if exc.is_connection_error:
            print("Start docker compose up -d --build", file=sys.stderr)
        return 1
    except TrustArtifactError as exc:
        print(f"Trust artifact error: {exc}", file=sys.stderr)
        return 1
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1


if __name__ == "__main__":
    raise SystemExit(main())
