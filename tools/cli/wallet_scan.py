#!/usr/bin/env python3
"""Wallet-Scan v0: batch scan many wallets/handles and produce a deterministic leaderboard.

CLI: python -m polytool wallet-scan --input wallets.txt [--profile lite] [--out DIR]

Output artifacts (under <out>/<YYYY-MM-DD>/<run_id>/):
  wallet_scan_manifest.json   - inputs, run_id, timestamps, scan flags
  per_user_results.jsonl      - one JSON object per identifier
  leaderboard.json            - sorted deterministic leaderboard
  leaderboard.md              - human-readable top-N summary
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from polytool.user_context import display_name, resolve_user_context

DEFAULT_OUTPUT_ROOT = Path("artifacts") / "research" / "wallet_scan"
DEFAULT_PROFILE = "lite"
DEFAULT_DOSSIER_DB = "kb/rag/knowledge/knowledge.sqlite3"
TOP_N_LEADERBOARD = 20

# Scan flags used for each profile. These are passed to the injected scan callable.
_PROFILE_FLAGS: Dict[str, Dict[str, Any]] = {
    "lite": {
        "lite": True,
        "ingest_positions": True,
        "compute_pnl": True,
        "enrich_resolutions": True,
        "compute_clv": True,
    },
    "full": {
        "full": True,
        "ingest_positions": True,
        "compute_pnl": True,
        "enrich_resolutions": True,
        "compute_clv": True,
    },
}

ScanCallable = Callable[[str, Dict[str, Any]], str]

# PostScanExtractor: called once per successful scan with the scan run root dir,
# the resolved user slug, and the wallet address.  Must never raise (errors are
# caught and logged non-fatally so the scan loop is never aborted).
PostScanExtractor = Callable[[Path, str, str], None]


# ---------------------------------------------------------------------------
# Dossier extraction helpers
# ---------------------------------------------------------------------------


def _read_wallet_from_dossier(scan_run_root: Path) -> str:
    """Return proxy_wallet from dossier.json in scan_run_root, or '' if absent."""
    dossier_path = scan_run_root / "dossier.json"
    if not dossier_path.exists():
        return ""
    try:
        raw = json.loads(dossier_path.read_text(encoding="utf-8"))
        return str(raw.get("header", {}).get("proxy_wallet", "") or "")
    except Exception:
        return ""


def _make_dossier_extractor(store_path: str = DEFAULT_DOSSIER_DB) -> PostScanExtractor:
    """Return a post-scan extractor callable that writes findings to KnowledgeStore.

    Uses lazy imports so the default (no-extractor) code path never pays the
    import cost of research packages.

    Parameters
    ----------
    store_path:
        SQLite path for KnowledgeStore.  Use ":memory:" in tests.
    """
    from packages.polymarket.rag.knowledge_store import KnowledgeStore
    from packages.research.integration.dossier_extractor import (
        extract_dossier_findings,
        ingest_dossier_findings,
    )

    store = KnowledgeStore(db_path=store_path)

    def _extract_and_ingest(scan_run_root: Path, slug: str, wallet: str) -> None:
        findings = extract_dossier_findings(scan_run_root)
        if not findings:
            return
        results = ingest_dossier_findings(findings, store, post_extract_claims=True)
        persisted = [
            r
            for r in (results or [])
            if r is not None
            and not getattr(r, "rejected", False)
            and getattr(r, "doc_id", "")
        ]
        if not persisted:
            # DEFECT 2 (2026-06-01): never report success on zero-persisted
            # ingest. An all-rejected/rolled-back result (e.g. the extractor
            # threw inside the per-wallet transaction) must surface as a failure
            # so the worker marks the queue item failed and does NOT advance the
            # watchlist to 'scanned'.
            raise RuntimeError(
                f"dossier ingest persisted 0 of {len(findings)} finding(s) for "
                f"{slug} ({wallet}) — all findings rejected/rolled back"
            )
        print(
            f"[dossier-extract] {slug}: {len(persisted)}/{len(findings)} finding(s) "
            f"ingested + claims extracted into {store_path}",
            file=sys.stderr,
        )

    return _extract_and_ingest


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int_or_none(value: Any) -> Optional[int]:
    """Coerce to int, or None when absent/unparseable.

    Unlike ``int(value or 0)``, a missing source yields None (not a misleading
    0) so downstream summaries omit the metric instead of fabricating a zero.
    """
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _win_rate_from_outcome_counts(outcome_counts: Dict[str, Any]) -> Optional[float]:
    """Compute overall win rate from a coverage report's ``outcome_counts``.

    Mirrors the canonical per-segment formula in polytool/reports/coverage.py
    (``_finalize_segment_bucket``): numerator = WIN + PROFIT_EXIT, denominator =
    WIN + LOSS + PROFIT_EXIT + LOSS_EXIT (resolved outcomes only; PENDING and
    UNKNOWN_RESOLUTION are excluded). Returns None when there are no resolved
    outcomes — never a misleading 0% — so callers omit win rate rather than
    imply a 0% win record for an unresolved book.
    """
    if not isinstance(outcome_counts, dict):
        return None

    def _n(key: str) -> int:
        return _coerce_int_or_none(outcome_counts.get(key)) or 0

    wins = _n("WIN")
    losses = _n("LOSS")
    profit_exits = _n("PROFIT_EXIT")
    loss_exits = _n("LOSS_EXIT")
    denominator = wins + losses + profit_exits + loss_exits
    if denominator <= 0:
        return None
    return round((wins + profit_exits) / denominator, 6)


def _dominant_category(by_category: Any) -> Optional[str]:
    """Return the *known* Polymarket category with the most positions.

    Reads ``segment_analysis.by_category`` (per-category buckets with a
    ``count``, built by polytool/reports/coverage.py). The synthetic "Unknown"
    bucket is excluded so a wallet whose positions are entirely uncategorised
    yields None -- the summary then omits category focus rather than display a
    meaningless "Unknown" focus (no fabrication). Ties broken alphabetically for
    a deterministic result. Never raises.
    """
    if not isinstance(by_category, dict):
        return None
    best_name: Optional[str] = None
    best_count = 0
    for name, bucket in by_category.items():
        if not isinstance(bucket, dict):
            continue
        if str(name).strip().lower() == "unknown":
            continue
        count = _coerce_int_or_none(bucket.get("count")) or 0
        if count <= 0:
            continue
        label = str(name)
        if (
            best_name is None
            or count > best_count
            or (count == best_count and label < best_name)
        ):
            best_count = count
            best_name = label
    return best_name


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


# Resolved-outcome buckets (mirror coverage.py KNOWN_OUTCOMES). A position is
# "resolved" (has a realized PnL to bucket by close date) iff its outcome is one
# of these; PENDING / UNKNOWN_RESOLUTION are excluded.
_RESOLVED_OUTCOMES = ("WIN", "LOSS", "PROFIT_EXIT", "LOSS_EXIT")


def _parse_iso_ts(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (``Z`` or ``+00:00``) to aware UTC, or None."""
    s = str(value or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_z(dt: datetime) -> str:
    """Render an aware datetime as a ``...Z`` ISO-8601 string."""
    return dt.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dossier_positions(dossier: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return the per-position list from a dossier, tolerating both shapes."""
    section = dossier.get("positions")
    if isinstance(section, dict):
        inner = section.get("positions")
        if isinstance(inner, list):
            return [p for p in inner if isinstance(p, dict)]
        items = section.get("items")
        if isinstance(items, list):
            return [p for p in items if isinstance(p, dict)]
    elif isinstance(section, list):
        return [p for p in section if isinstance(p, dict)]
    return []


def _newest_trade_ts(positions: List[Dict[str, Any]]) -> Optional[str]:
    """Newest TRADE timestamp across positions (entry/exit), as a ``...Z`` string.

    A trade is the user buying/selling — ``entry_ts``/``exit_ts`` — NOT the
    market's resolution (``close_ts``). Returns None when no parseable trade
    timestamp exists. This is the wallet's "last active" recency signal.
    """
    newest: Optional[datetime] = None
    for pos in positions:
        for key in ("entry_ts", "exit_ts"):
            dt = _parse_iso_ts(pos.get(key))
            if dt is not None and (newest is None or dt > newest):
                newest = dt
    return _iso_z(newest) if newest is not None else None


def _recent_form_from_positions(
    positions: List[Dict[str, Any]], sample_cap: Optional[int]
) -> Dict[str, Any]:
    """Surface RESOLVED-trade (close_date, realized_pnl) pairs for windowing.

    Each resolved position contributes one ``{"close": iso, "pnl": float}`` row,
    keyed on its resolution/close date (``close_ts`` preferred, then
    ``resolved_at`` / ``close_date_iso``). The realized PnL is
    ``realized_pnl_net_estimated_fees`` (the fee-aware figure consistent with the
    all-time PnL field), falling back to ``realized_pnl_net``. Display-time logic
    buckets these into Today/7d/30d under the honesty rule; ``sample_size`` +
    ``sample_cap`` let it decide whether a window is fully covered.
    """
    trades: List[Dict[str, Any]] = []
    for pos in positions:
        if str(pos.get("resolution_outcome") or "").strip().upper() not in _RESOLVED_OUTCOMES:
            continue
        close_dt = (
            _parse_iso_ts(pos.get("close_ts"))
            or _parse_iso_ts(pos.get("resolved_at"))
            or _parse_iso_ts(pos.get("close_date_iso"))
        )
        if close_dt is None:
            continue
        pnl = _safe_float(pos.get("realized_pnl_net_estimated_fees"))
        if pnl is None:
            pnl = _safe_float(pos.get("realized_pnl_net"))
        if pnl is None:
            continue
        trades.append({"close": _iso_z(close_dt), "pnl": pnl})
    return {
        "trades": trades,
        "sample_size": len(positions),
        "sample_cap": _coerce_int_or_none(sample_cap),
    }


def _detect_identifier_type(identifier: str) -> str:
    """Return 'handle' for @-prefixed identifiers, 'wallet' for 0x addresses."""
    stripped = identifier.strip()
    if stripped.startswith("@"):
        return "handle"
    if stripped.lower().startswith("0x"):
        return "wallet"
    # Best-effort: no @ and no 0x prefix — treat as handle slug
    return "handle"


def _load_username_sidecar(input_path: Path) -> Dict[str, str]:
    """Load the optional ``<input>.usernames.json`` display-name sidecar.

    Written by ``export-leaderboard`` (see leaderboard_export.write_username_sidecar):
    a flat ``{lowercased_wallet: username}`` map. The map is DISPLAY-ONLY; the
    input file's bare addresses remain the canonical keys. Missing/garbled
    sidecar => empty map (a bare-address input file still scans normally).
    """
    sidecar = input_path.with_name(input_path.name + ".usernames.json")
    if not sidecar.exists():
        return {}
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(k).strip().lower(): str(v).strip()
        for k, v in raw.items()
        if str(k).strip() and str(v).strip()
    }


def _stamp_dossier_username(scan_run_root: Path, username: str) -> None:
    """Carry a handoff username into ``dossier.json`` header (export->scan->dossier).

    The scan stamps ``header.username`` only when ``/api/resolve`` returns a real
    handle; pseudonymous wallets leave it empty. When the leaderboard handoff
    supplied a display name, stamp it here so the dossier (and everything that
    reads it back) carries the human name. Best-effort and NON-FATAL: never
    raises, and an already-present non-empty header.username is left untouched.
    """
    clean = (username or "").strip()
    if not clean:
        return
    dossier_path = scan_run_root / "dossier.json"
    if not dossier_path.exists():
        return
    try:
        dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
        header = dossier.get("header")
        if not isinstance(header, dict):
            header = {}
            dossier["header"] = header
        if str(header.get("username") or "").strip():
            return  # already stamped by the scan — do not overwrite
        header["username"] = clean
        dossier_path.write_text(
            json.dumps(dossier, indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
    except Exception:
        # Never break the scan loop on a display-only stamp.
        return


def parse_input_file(
    path: Path,
    max_entries: Optional[int] = None,
    username_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """Parse input file; return list of {identifier, kind, username} dicts.

    Deduplicated, in order. ``username`` is DISPLAY-ONLY and defaults to "" — a
    bare-address input file (no sidecar) yields empty usernames and still scans.
    When ``username_map`` (lowercased identifier -> username) is supplied, each
    entry's display username is attached from it. ``identifier`` (the address or
    @handle) remains the canonical key.
    """
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    umap = username_map or {}
    entries: List[Dict[str, str]] = []
    seen: set[str] = set()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue
        seen.add(line)
        entries.append(
            {
                "identifier": line,
                "kind": _detect_identifier_type(line),
                "username": umap.get(line.lower(), ""),
            }
        )
        if max_entries is not None and len(entries) >= max_entries:
            break

    return entries


# ---------------------------------------------------------------------------
# Scan integration
# ---------------------------------------------------------------------------


def _default_scan_callable(identifier: str, scan_flags: Dict[str, Any]) -> str:
    """Run a real scan via the scan CLI internals and return the run_root path."""
    from tools.cli import scan

    kind = _detect_identifier_type(identifier)
    # WI-1 arg-seam fix: scan.py's parser defines only --user (it accepts both
    # @handles and raw 0x wallet addresses; the API /api/resolve endpoint and
    # GammaClient.resolve both branch on the 0x-prefix). There is no --wallet
    # flag, so raw addresses must also be passed via --user, otherwise argparse
    # raised "unrecognized arguments: --wallet" and the whole handoff broke.
    argv = ["--user", identifier]

    if scan_flags.get("lite"):
        argv.append("--lite")
    elif scan_flags.get("full"):
        argv.append("--full")

    scan_parser = scan.build_parser()
    scan_args = scan_parser.parse_args(argv)
    scan_args = scan.apply_scan_defaults(scan_args, argv)
    scan_config = scan.build_config(scan_args)
    scan.validate_config(scan_config)
    emitted = scan.run_scan(
        config=scan_config,
        argv=argv,
        started_at=_iso_utc(_utcnow()),
    )

    # Resolve run_root from emitted paths (mirrors batch_run._resolve_run_root_from_emitted)
    manifest_path_raw = str(emitted.get("run_manifest") or "").strip()
    if manifest_path_raw:
        manifest_path = Path(manifest_path_raw)
        if manifest_path.exists():
            manifest = _read_json(manifest_path)
            output_paths = manifest.get("output_paths") or {}
            if isinstance(output_paths, dict):
                run_root = str(output_paths.get("run_root") or "").strip()
                if run_root:
                    return run_root
            return manifest_path.parent.as_posix()

    run_root_raw = str(emitted.get("run_root") or "").strip()
    if run_root_raw:
        return run_root_raw

    raise ValueError(f"Scan output missing run root for identifier '{identifier}'")


# ---------------------------------------------------------------------------
# Artifact extraction
# ---------------------------------------------------------------------------


def _extract_user_metrics(run_root: Path) -> Dict[str, Any]:
    """Extract summary metrics from a completed scan run_root."""
    coverage_path = run_root / "coverage_reconciliation_report.json"
    segment_path = run_root / "segment_analysis.json"

    if not coverage_path.exists():
        return {}

    coverage = _read_json(coverage_path)
    segment = _read_json(segment_path) if segment_path.exists() else {}

    pnl = coverage.get("pnl") or {}
    outcome_counts = coverage.get("outcome_counts") or {}
    # The persisted report keys outcome percentages as "outcome_percentages"
    # (polytool/reports/coverage.py build_coverage_report). Accept the legacy
    # "outcome_pcts" alias defensively so older artifacts still read.
    outcome_pcts = coverage.get("outcome_percentages") or coverage.get("outcome_pcts") or {}
    clv_section = coverage.get("clv_coverage") or {}
    # positions_total lives under report["totals"] in the persisted schema; a
    # bare top-level value is a legacy fallback only.
    totals = coverage.get("totals") or {}

    # Realized net PnL is the primary leaderboard sort metric
    realized_net_pnl = _safe_float(
        pnl.get("realized_pnl_net_estimated_fees_total")
        or pnl.get("realized_pnl_net_total")
    )
    gross_pnl = _safe_float(pnl.get("gross_pnl_total"))
    clv_coverage_rate = _safe_float(clv_section.get("coverage_rate"))

    # Read the trade/position count from its real (nested) location. When the
    # count is genuinely absent we keep None (NOT 0) so the summary omits trades
    # rather than show a misleading "0 trades" beside non-zero PnL/CLV.
    raw_positions = totals.get("positions_total")
    if raw_positions is None:
        raw_positions = coverage.get("positions_total")
    positions_total = _coerce_int_or_none(raw_positions)

    # Win rate is derivable from outcome_counts (was previously never extracted,
    # so summarize_evidence always omitted "% win"). None when no resolved book.
    win_rate = _win_rate_from_outcome_counts(outcome_counts)

    # Win numerator (WIN + PROFIT_EXIT) so the card can render "62% (25/40)".
    # None when there is no resolved book (mirrors win_rate's honesty).
    win_count: Optional[int] = None
    if win_rate is not None:
        win_count = (_coerce_int_or_none(outcome_counts.get("WIN")) or 0) + (
            _coerce_int_or_none(outcome_counts.get("PROFIT_EXIT")) or 0
        )

    unknown_resolution_pct = _safe_float(outcome_pcts.get("UNKNOWN_RESOLUTION"))

    # Per-trade display signals come from the dossier (handle headline, recency,
    # recent-form windows) — the coverage report only carries aggregates. Read is
    # additive + defensive: a missing/garbled dossier just omits these fields.
    handle: Optional[str] = None
    last_active: Optional[str] = None
    recent_form: Optional[Dict[str, Any]] = None
    dossier_path = run_root / "dossier.json"
    if dossier_path.exists():
        try:
            dossier = _read_json(dossier_path)
        except Exception:
            dossier = {}
        header = dossier.get("header") if isinstance(dossier.get("header"), dict) else {}
        raw_handle = str(header.get("username") or "").strip().lstrip("@").strip()
        handle = raw_handle or None
        positions = _dossier_positions(dossier)
        last_active = _newest_trade_ts(positions)
        recent_form = _recent_form_from_positions(positions, header.get("max_trades"))

    # Top segment highlights from segment_analysis
    segment_highlights: List[str] = []
    seg_analysis = segment.get("segment_analysis") or {}
    # Dominant *known* category from the per-category buckets (None when the
    # wallet's positions are entirely uncategorised -- summary omits focus).
    category_focus = _dominant_category(seg_analysis.get("by_category"))
    by_entry = seg_analysis.get("by_entry_price_tier") or {}
    if isinstance(by_entry, dict):
        for tier_key, tier_data in list(by_entry.items())[:3]:
            if isinstance(tier_data, dict):
                tier_pnl = _safe_float(tier_data.get("realized_pnl_net_total"))
                tier_count = tier_data.get("count")
                if tier_pnl is not None and tier_count:
                    segment_highlights.append(
                        f"tier={tier_key} count={tier_count} pnl={tier_pnl:.4f}"
                    )

    return {
        "realized_net_pnl": realized_net_pnl,
        "gross_pnl": gross_pnl,
        "positions_total": positions_total,
        "win_rate": win_rate,
        "win_count": win_count,
        "clv_coverage_rate": clv_coverage_rate,
        "unknown_resolution_pct": unknown_resolution_pct,
        "outcome_counts": {
            k: int(v) for k, v in outcome_counts.items() if isinstance(v, (int, float))
        },
        "category_focus": category_focus,
        "handle": handle,
        "last_active": last_active,
        "recent_form": recent_form,
        "segment_highlights": segment_highlights,
    }


# ---------------------------------------------------------------------------
# Per-user result builders
# ---------------------------------------------------------------------------


def _resolve_wallet_id(entry: Dict[str, str], run_root: Path) -> str:
    """Canonical wallet_id (0x) for an entry: the dossier's proxy_wallet, else
    the identifier when it is itself a wallet address. Never a username/slug."""
    wallet = _read_wallet_from_dossier(run_root)
    if wallet:
        return wallet
    if entry.get("kind") == "wallet":
        return str(entry.get("identifier") or "")
    return ""


def _success_result(
    entry: Dict[str, str],
    slug: str,
    run_root: Path,
) -> Dict[str, Any]:
    metrics = _extract_user_metrics(run_root)
    wallet_id = _resolve_wallet_id(entry, run_root)
    # Display username precedence: the scanned dossier handle (most authoritative,
    # from /api/resolve) wins; the export->scan handoff username is the fallback.
    # Both are DISPLAY-ONLY — wallet_id stays the canonical key.
    username = str(metrics.get("handle") or entry.get("username") or "").strip()
    return {
        "identifier": entry["identifier"],
        "kind": entry["kind"],
        "slug": slug,
        "wallet_id": wallet_id,
        "username": username,
        "display_name": display_name(username, wallet_id or entry["identifier"]),
        "run_root": run_root.as_posix(),
        "status": "success",
        "error": None,
        **metrics,
    }


def _failure_result(entry: Dict[str, str], slug: Optional[str], error: str) -> Dict[str, Any]:
    username = str(entry.get("username") or "").strip()
    wallet_id = str(entry.get("identifier") or "") if entry.get("kind") == "wallet" else ""
    return {
        "identifier": entry["identifier"],
        "kind": entry["kind"],
        "slug": slug,
        "wallet_id": wallet_id,
        "username": username,
        "display_name": display_name(username, wallet_id or entry["identifier"]),
        "run_root": None,
        "status": "failure",
        "error": error,
        "realized_net_pnl": None,
        "gross_pnl": None,
        "positions_total": None,
        "clv_coverage_rate": None,
        "unknown_resolution_pct": None,
        "outcome_counts": {},
        "segment_highlights": [],
    }


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------


def _sort_key_for_leaderboard(result: Dict[str, Any]) -> tuple:
    """Sort descending by realized_net_pnl (nulls last), tiebreak by slug."""
    pnl = _safe_float(result.get("realized_net_pnl"))
    slug = str(result.get("slug") or result.get("identifier") or "")
    # Negate pnl for descending order; None → float('-inf') so nulls go last
    sort_pnl = -pnl if pnl is not None else float("inf")
    return (sort_pnl, slug)


def _build_leaderboard(
    per_user_results: List[Dict[str, Any]],
    *,
    run_id: str,
    created_at: str,
    scan_flags: Dict[str, Any],
    profile: str,
    input_file: str,
    entries_attempted: int,
) -> Dict[str, Any]:
    succeeded = [r for r in per_user_results if r.get("status") == "success"]
    failed = [r for r in per_user_results if r.get("status") != "success"]

    ranked = sorted(succeeded, key=_sort_key_for_leaderboard)
    # Assign rank (1-based)
    ranked_entries = []
    for i, result in enumerate(ranked, start=1):
        ranked_entries.append({
            "rank": i,
            "slug": result.get("slug"),
            "identifier": result.get("identifier"),
            "wallet_id": result.get("wallet_id"),
            "username": result.get("username"),
            "display_name": result.get("display_name"),
            "realized_net_pnl": result.get("realized_net_pnl"),
            "gross_pnl": result.get("gross_pnl"),
            "positions_total": result.get("positions_total"),
            "clv_coverage_rate": result.get("clv_coverage_rate"),
            "unknown_resolution_pct": result.get("unknown_resolution_pct"),
            "run_root": result.get("run_root"),
        })

    return {
        "run_id": run_id,
        "created_at": created_at,
        "profile": profile,
        "scan_flags": scan_flags,
        "input_file": input_file,
        "entries_attempted": entries_attempted,
        "entries_succeeded": len(succeeded),
        "entries_failed": len(failed),
        "ranked": ranked_entries,
    }


def _build_leaderboard_md(leaderboard: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Wallet Scan Leaderboard")
    lines.append("")
    lines.append(f"- Run ID: `{leaderboard['run_id']}`")
    lines.append(f"- Created at: `{leaderboard['created_at']}`")
    lines.append(f"- Profile: `{leaderboard['profile']}`")
    lines.append(f"- Entries attempted: {leaderboard['entries_attempted']}")
    lines.append(f"- Entries succeeded: {leaderboard['entries_succeeded']}")
    lines.append(f"- Entries failed: {leaderboard['entries_failed']}")
    lines.append("")
    lines.append(f"## Top {TOP_N_LEADERBOARD} by Realized Net PnL")
    lines.append("")
    # `User` is the display_name (human handle, else truncated wallet ID); the
    # wallet ID stays a separate canonical column (never collapsed) so the
    # convention holds end-to-end into the DR-3 status card.
    lines.append("| Rank | User | Wallet ID | Slug | Net PnL | Gross PnL | Positions | CLV Cov% | Unk Res% |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")

    ranked = leaderboard.get("ranked") or []
    for row in ranked[:TOP_N_LEADERBOARD]:
        pnl = row.get("realized_net_pnl")
        gross = row.get("gross_pnl")
        clv = row.get("clv_coverage_rate")
        unk = row.get("unknown_resolution_pct")
        # Defensive: older callers may not have populated display_name/wallet_id.
        wallet_id = row.get("wallet_id") or row.get("identifier") or ""
        disp = row.get("display_name") or display_name(row.get("username"), wallet_id)
        lines.append(
            f"| {row['rank']} "
            f"| {disp or ''} "
            f"| `{wallet_id}` "
            f"| `{row.get('slug') or ''}` "
            f"| {f'{pnl:.4f}' if pnl is not None else 'null'} "
            f"| {f'{gross:.4f}' if gross is not None else 'null'} "
            f"| {row.get('positions_total') or 'null'} "
            f"| {f'{clv:.2%}' if clv is not None else 'null'} "
            f"| {f'{unk:.2%}' if unk is not None else 'null'} |"
        )

    if not ranked:
        lines.append("| - | _(none)_ | - | - | - | - | - | - | - |")

    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


class WalletScanner:
    """Batch-scan multiple wallets/handles and produce a deterministic leaderboard."""

    def __init__(
        self,
        scan_callable: Optional[ScanCallable] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
        post_scan_extractor: Optional[PostScanExtractor] = None,
        pacer: Optional[Any] = None,
    ) -> None:
        self._scan_callable = scan_callable or _default_scan_callable
        self._now_provider = now_provider or _utcnow
        self._post_scan_extractor = post_scan_extractor
        # DR-2 bulk pacing: optional inter-wallet spacer. None ⇒ no pacing
        # (default). When an enabled BulkPacer is supplied, a small delay is
        # applied between successive wallet scans so a 200-wallet batch stays
        # polite. The scheduler/worker path never sets this.
        self._pacer = pacer

    def run(
        self,
        *,
        entries: List[Dict[str, str]],
        output_root: Path,
        run_id: str,
        profile: str,
        input_file_path: str,
        continue_on_error: bool = True,
    ) -> Dict[str, str]:
        now = self._now_provider()
        created_at = _iso_utc(now)
        scan_date = now.date().isoformat()
        scan_flags = _PROFILE_FLAGS.get(profile, _PROFILE_FLAGS[DEFAULT_PROFILE])

        run_root = output_root / scan_date / run_id
        run_root.mkdir(parents=True, exist_ok=True)

        per_user_results: List[Dict[str, Any]] = []

        for idx, entry in enumerate(entries):
            # DR-2 bulk pacing: space out successive wallet scans when enabled.
            # No-op when self._pacer is None or disabled (default).
            if self._pacer is not None and idx > 0:
                self._pacer.pace()

            identifier = entry["identifier"]
            slug: Optional[str] = None
            try:
                # Resolve slug before scanning (for failure records)
                kind = entry["kind"]
                if kind == "handle":
                    ctx = resolve_user_context(handle=identifier, persist_mapping=False)
                else:
                    ctx = resolve_user_context(wallet=identifier, persist_mapping=False)
                slug = ctx.slug

                scan_run_root_str = self._scan_callable(identifier, scan_flags)
                scan_run_root = Path(scan_run_root_str)
                # Carry the export->scan handoff username into the dossier header
                # (display-only, never overwrites a real scanned handle) BEFORE
                # extracting metrics so it is read back consistently. Non-fatal.
                _stamp_dossier_username(scan_run_root, str(entry.get("username") or ""))
                result = _success_result(entry, slug, scan_run_root)

                # Post-scan hook: extract dossier findings into KnowledgeStore.
                # Non-fatal: errors are caught and logged; the scan loop always continues.
                if self._post_scan_extractor is not None:
                    wallet_addr = _read_wallet_from_dossier(scan_run_root)
                    try:
                        self._post_scan_extractor(
                            scan_run_root,
                            str(slug or ""),
                            wallet_addr,
                        )
                    except Exception as exc:
                        print(
                            f"[dossier-extract] Non-fatal error for {identifier!r}: {exc}",
                            file=sys.stderr,
                        )

                per_user_results.append(result)
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                per_user_results.append(_failure_result(entry, slug, error_text))
                if not continue_on_error:
                    raise

        leaderboard = _build_leaderboard(
            per_user_results,
            run_id=run_id,
            created_at=created_at,
            scan_flags=scan_flags,
            profile=profile,
            input_file=input_file_path,
            entries_attempted=len(entries),
        )

        # Write manifest
        manifest = {
            "run_id": run_id,
            "created_at": created_at,
            "profile": profile,
            "scan_flags": scan_flags,
            "input_file": input_file_path,
            "entries_attempted": len(entries),
            "entries_succeeded": leaderboard["entries_succeeded"],
            "entries_failed": leaderboard["entries_failed"],
            "output_paths": {
                "run_root": run_root.as_posix(),
                "wallet_scan_manifest_json": (run_root / "wallet_scan_manifest.json").as_posix(),
                "per_user_results_jsonl": (run_root / "per_user_results.jsonl").as_posix(),
                "leaderboard_json": (run_root / "leaderboard.json").as_posix(),
                "leaderboard_md": (run_root / "leaderboard.md").as_posix(),
            },
        }

        # Write per_user_results.jsonl
        jsonl_path = run_root / "per_user_results.jsonl"
        jsonl_path.write_text(
            "\n".join(json.dumps(r, sort_keys=True, allow_nan=False) for r in per_user_results)
            + ("\n" if per_user_results else ""),
            encoding="utf-8",
        )

        _write_json(run_root / "leaderboard.json", leaderboard)
        (run_root / "leaderboard.md").write_text(
            _build_leaderboard_md(leaderboard), encoding="utf-8"
        )
        _write_json(run_root / "wallet_scan_manifest.json", manifest)

        return {
            "run_root": run_root.as_posix(),
            "wallet_scan_manifest_json": (run_root / "wallet_scan_manifest.json").as_posix(),
            "per_user_results_jsonl": jsonl_path.as_posix(),
            "leaderboard_json": (run_root / "leaderboard.json").as_posix(),
            "leaderboard_md": (run_root / "leaderboard.md").as_posix(),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Wallet-Scan v0: batch-scan many wallets/handles and produce a "
            "deterministic leaderboard artifact."
        )
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a file with one identifier per line (@handle or 0xwallet).",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        choices=list(_PROFILE_FLAGS.keys()),
        help=f"Scan profile to use (default: {DEFAULT_PROFILE}).",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUTPUT_ROOT.as_posix(),
        help=f"Output root directory (default: {DEFAULT_OUTPUT_ROOT.as_posix()}).",
    )
    parser.add_argument(
        "--run-id",
        help="Optional run ID (default: random uuid4).",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        help="Optional safety cap on number of entries loaded from --input.",
    )
    parser.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continue on per-entry scan failures (default: true).",
    )
    parser.add_argument(
        "--extract-dossier",
        action="store_true",
        default=False,
        help=(
            "After each wallet scan, extract dossier findings and ingest into "
            "KnowledgeStore (requires dossier.json to be present in the scan run "
            "root). Findings are stored with source_family='dossier_report' and "
            "are queryable via rag-query command (use --hybrid --knowledge-store default for derived claims)."
        ),
    )
    parser.add_argument(
        "--extract-dossier-db",
        default=DEFAULT_DOSSIER_DB,
        help=(
            f"KnowledgeStore SQLite path for --extract-dossier "
            f"(default: {DEFAULT_DOSSIER_DB})."
        ),
    )
    parser.add_argument(
        "--pace",
        action="store_true",
        default=False,
        help=(
            "DR-2 bulk pacing: enable a small inter-wallet delay so a large "
            "batch (e.g. top-200) stays polite. OFF by default. When set "
            "without --pace-delay, the delay comes from config "
            "(config/discovery_scheduler.json -> bulk_pacing), else the "
            "conservative built-in default."
        ),
    )
    parser.add_argument(
        "--pace-delay",
        type=float,
        default=None,
        help=(
            "Seconds to wait between successive wallet scans when --pace is set "
            "(overrides config). Ignored unless --pace is passed."
        ),
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_root = Path(args.out)
    run_id = str(args.run_id or uuid.uuid4())

    # Optional display-name sidecar written by `export-leaderboard`
    # (<input>.usernames.json). Absent => bare-address input scans normally.
    username_map = _load_username_sidecar(input_path)

    try:
        entries = parse_input_file(
            input_path, max_entries=args.max_entries, username_map=username_map
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not entries:
        print("Error: input file produced zero entries after filtering blank/comment lines.", file=sys.stderr)
        return 1

    post_scan_extractor = None
    if getattr(args, "extract_dossier", False):
        post_scan_extractor = _make_dossier_extractor(
            store_path=getattr(args, "extract_dossier_db", DEFAULT_DOSSIER_DB)
        )

    # DR-2 bulk pacing: build a pacer only when --pace is set (default OFF).
    pacer = None
    if getattr(args, "pace", False):
        from packages.polymarket.discovery.bulk_pacing import BulkPacer, load_bulk_pacing

        if args.pace_delay is not None:
            pacer = BulkPacer(args.pace_delay, enabled=True)
        else:
            cfg_pacer = load_bulk_pacing()
            # --pace is an explicit opt-in; honour it even if config left
            # enabled=false, using the config delay (or built-in default).
            pacer = BulkPacer(cfg_pacer.delay_seconds, enabled=True)

    scanner = WalletScanner(post_scan_extractor=post_scan_extractor, pacer=pacer)
    try:
        output_paths = scanner.run(
            entries=entries,
            output_root=output_root,
            run_id=run_id,
            profile=args.profile,
            input_file_path=input_path.as_posix(),
            continue_on_error=bool(args.continue_on_error),
        )
    except Exception as exc:
        print(f"Wallet scan failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("Wallet scan complete")
    print(f"Run root: {output_paths['run_root']}")
    print(f"Manifest: {output_paths['wallet_scan_manifest_json']}")
    print(f"Leaderboard JSON: {output_paths['leaderboard_json']}")
    print(f"Leaderboard Markdown: {output_paths['leaderboard_md']}")
    print(f"Per-user results: {output_paths['per_user_results_jsonl']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
