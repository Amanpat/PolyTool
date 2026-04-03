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

from polytool.user_context import resolve_user_context

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
        if findings:
            ingest_dossier_findings(findings, store, post_extract_claims=True)
            print(
                f"[dossier-extract] {slug}: {len(findings)} finding(s) ingested "
                f"+ claims extracted into {store_path}",
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


# ---------------------------------------------------------------------------
# Input parsing
# ---------------------------------------------------------------------------


def _detect_identifier_type(identifier: str) -> str:
    """Return 'handle' for @-prefixed identifiers, 'wallet' for 0x addresses."""
    stripped = identifier.strip()
    if stripped.startswith("@"):
        return "handle"
    if stripped.lower().startswith("0x"):
        return "wallet"
    # Best-effort: no @ and no 0x prefix — treat as handle slug
    return "handle"


def parse_input_file(path: Path, max_entries: Optional[int] = None) -> List[Dict[str, str]]:
    """Parse input file; return list of {identifier, kind} dicts (deduplicated, in order)."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    entries: List[Dict[str, str]] = []
    seen: set[str] = set()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue
        seen.add(line)
        entries.append({"identifier": line, "kind": _detect_identifier_type(line)})
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
    if kind == "handle":
        argv = ["--user", identifier]
    else:
        argv = ["--wallet", identifier]

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
    outcome_pcts = coverage.get("outcome_pcts") or {}
    clv_section = coverage.get("clv_coverage") or {}

    # Realized net PnL is the primary leaderboard sort metric
    realized_net_pnl = _safe_float(
        pnl.get("realized_pnl_net_estimated_fees_total")
        or pnl.get("realized_pnl_net_total")
    )
    gross_pnl = _safe_float(pnl.get("gross_pnl_total"))
    clv_coverage_rate = _safe_float(clv_section.get("coverage_rate"))

    positions_total = int(coverage.get("positions_total") or 0)
    unknown_resolution_pct = _safe_float(outcome_pcts.get("UNKNOWN_RESOLUTION"))

    # Top segment highlights from segment_analysis
    segment_highlights: List[str] = []
    seg_analysis = segment.get("segment_analysis") or {}
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
        "clv_coverage_rate": clv_coverage_rate,
        "unknown_resolution_pct": unknown_resolution_pct,
        "outcome_counts": {
            k: int(v) for k, v in outcome_counts.items() if isinstance(v, (int, float))
        },
        "segment_highlights": segment_highlights,
    }


# ---------------------------------------------------------------------------
# Per-user result builders
# ---------------------------------------------------------------------------


def _success_result(
    entry: Dict[str, str],
    slug: str,
    run_root: Path,
) -> Dict[str, Any]:
    metrics = _extract_user_metrics(run_root)
    return {
        "identifier": entry["identifier"],
        "kind": entry["kind"],
        "slug": slug,
        "run_root": run_root.as_posix(),
        "status": "success",
        "error": None,
        **metrics,
    }


def _failure_result(entry: Dict[str, str], slug: Optional[str], error: str) -> Dict[str, Any]:
    return {
        "identifier": entry["identifier"],
        "kind": entry["kind"],
        "slug": slug,
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
    lines.append("| Rank | Slug | Identifier | Net PnL | Gross PnL | Positions | CLV Cov% | Unk Res% |")
    lines.append("| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |")

    ranked = leaderboard.get("ranked") or []
    for row in ranked[:TOP_N_LEADERBOARD]:
        pnl = row.get("realized_net_pnl")
        gross = row.get("gross_pnl")
        clv = row.get("clv_coverage_rate")
        unk = row.get("unknown_resolution_pct")
        lines.append(
            f"| {row['rank']} "
            f"| `{row.get('slug') or ''}` "
            f"| `{row.get('identifier') or ''}` "
            f"| {f'{pnl:.4f}' if pnl is not None else 'null'} "
            f"| {f'{gross:.4f}' if gross is not None else 'null'} "
            f"| {row.get('positions_total') or 'null'} "
            f"| {f'{clv:.2%}' if clv is not None else 'null'} "
            f"| {f'{unk:.2%}' if unk is not None else 'null'} |"
        )

    if not ranked:
        lines.append("| - | _(none)_ | - | - | - | - | - | - |")

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
    ) -> None:
        self._scan_callable = scan_callable or _default_scan_callable
        self._now_provider = now_provider or _utcnow
        self._post_scan_extractor = post_scan_extractor

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

        for entry in entries:
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
            "are queryable via rag-query / research-query commands."
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
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    output_root = Path(args.out)
    run_id = str(args.run_id or uuid.uuid4())

    try:
        entries = parse_input_file(input_path, max_entries=args.max_entries)
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

    scanner = WalletScanner(post_scan_extractor=post_scan_extractor)
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
