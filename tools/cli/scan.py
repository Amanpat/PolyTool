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
from pathlib import Path
from typing import Any, Dict, Optional

import requests

from polytool.reports.coverage import build_coverage_report, normalize_fee_fields, write_coverage_report
from polytool.reports.manifest import build_run_manifest, write_run_manifest

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
MAX_BODY_SNIPPET = 800
TRUST_ARTIFACT_WINDOW_DAYS = 30
TRUST_ARTIFACT_MAX_TRADES = 200


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
        positions_count = max(
            _coerce_non_negative_int(row.get("positions_count")),
            dossier_summary["positions_len"],
        )
        trades_count = max(
            _coerce_non_negative_int(row.get("trades_count")),
            dossier_summary["trades_len"],
        )
        summaries.append({
            "row": row,
            "dossier_payload": dossier_payload,
            "export_id": str(row.get("export_id") or ""),
            "positions_count": positions_count,
            "trades_count": trades_count,
            "positions_len": dossier_summary["positions_len"],
            "trades_len": dossier_summary["trades_len"],
        })
    return summaries


def _select_history_hydration_row(
    summaries: list[Dict[str, Any]],
    export_id: str,
) -> Optional[Dict[str, Any]]:
    matching = [s for s in summaries if s["export_id"] == export_id and s["dossier_payload"] is not None]
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
        return endpoints_used, local_summary, {"history_rows": 0, "hydrated": False}

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
            f"top_positions_count={top['positions_count']} top_trades_count={top['trades_count']} "
            f"top_positions_len={top['positions_len']} top_trades_len={top['trades_len']}",
        )
    else:
        _debug_export(config, "endpoint=/api/export/user_dossier/history rows=0")

    export_id = str(dossier_export_response.get("export_id") or "")
    selected = _select_history_hydration_row(summaries, export_id)

    if selected and selected["positions_count"] > 0:
        _write_hydrated_dossier(output_dir, selected)
        hydrated_summary = _summarize_dossier_payload(_load_dossier_payload(output_dir))
        _debug_export(
            config,
            f"hydrated_from_history export_id={selected['export_id']} "
            f"positions_len={hydrated_summary['positions_len']} trades_len={hydrated_summary['trades_len']}",
        )
        return endpoints_used, hydrated_summary, {"history_rows": len(summaries), "hydrated": True}

    if local_payload is None:
        if selected:
            _write_hydrated_dossier(output_dir, selected)
            hydrated_summary = _summarize_dossier_payload(_load_dossier_payload(output_dir))
            return endpoints_used, hydrated_summary, {"history_rows": len(summaries), "hydrated": True}
        raise TrustArtifactError(
            f"Missing dossier.json at {output_dir / 'dossier.json'} and no usable history dossier payload found"
        )

    return endpoints_used, local_summary, {"history_rows": len(summaries), "hydrated": False}


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


def _emit_trust_artifacts(
    config: Dict[str, Any],
    argv: list[str],
    started_at: str,
    resolve_response: Dict[str, Any],
    dossier_export_response: Dict[str, Any],
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
    coverage_report = build_coverage_report(
        positions=positions,
        run_id=run_id,
        user_slug=username_slug,
        wallet=proxy_wallet,
        proxy_wallet=proxy_wallet,
        resolution_enrichment_response=resolution_enrichment_response,
        entry_price_tiers=config.get("entry_price_tiers"),
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

    wallets = [w for w in dict.fromkeys([proxy_wallet, resolve_response.get("proxy_wallet")]) if w]
    output_paths = {
        "run_root": output_dir.as_posix(),
        "dossier_path": output_dir.as_posix(),
        "dossier_json": (output_dir / "dossier.json").as_posix(),
        "coverage_reconciliation_report_json": coverage_paths["json"],
        "segment_analysis_json": segment_analysis_path.as_posix(),
        "resolution_parity_debug_json": parity_debug_path.as_posix(),
    }
    if "md" in coverage_paths:
        output_paths["coverage_reconciliation_report_md"] = coverage_paths["md"]

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
    manifest_path = write_run_manifest(manifest, output_dir)

    emitted = {
        "coverage_reconciliation_report_json": coverage_paths["json"],
        "segment_analysis_json": segment_analysis_path.as_posix(),
        "run_manifest": Path(manifest_path).as_posix(),
        "resolution_parity_debug_json": parity_debug_path.as_posix(),
    }
    if "md" in coverage_paths:
        emitted["coverage_reconciliation_report_md"] = coverage_paths["md"]
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
        "--config",
        help="Path to polytool.yaml config file (defaults to ./polytool.yaml if present)",
    )
    parser.add_argument("--api-base-url", help="Base URL for the PolyTool API")
    return parser


def build_config(args: argparse.Namespace) -> Dict[str, Any]:
    local_config = _load_local_config(args.config)
    entry_price_tiers = _extract_entry_price_tiers(local_config)

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
        "resolution_max_candidates": resolution_max_candidates,
        "resolution_batch_size": resolution_batch_size,
        "resolution_max_concurrency": resolution_max_concurrency,
        "debug_export": debug_export,
        "entry_price_tiers": entry_price_tiers,
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

    if config["ingest_markets"]:
        post_json(
            api_base_url,
            "/api/ingest/markets",
            {"active_only": True},
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
