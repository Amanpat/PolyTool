#!/usr/bin/env python3
"""Orchestrate full user examination workflow.

This command runs the complete examination pipeline:
1. Scan (if API available)
2. Export dossier
3. Build LLM bundle
4. Generate standardized prompt

Output:
- Dossier: artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id>/
- Bundle + Prompt: kb/users/<slug>/llm_bundles/<date>/<run_id>/
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add packages and polytool to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from polymarket.gamma import GammaClient
from polymarket.llm_research_packets import (
    DEFAULT_MAX_TRADES,
    DEFAULT_WINDOW_DAYS,
    export_user_dossier,
)
from polytool.user_context import resolve_user_context, UserContext
from polytool.reports.coverage import (
    build_coverage_report,
    normalize_fee_fields,
    write_coverage_report,
)
from polytool.reports.manifest import build_run_manifest, write_run_manifest

logger = logging.getLogger(__name__)

try:
    import clickhouse_connect
except ImportError:
    clickhouse_connect = None  # type: ignore

DEFAULT_CLICKHOUSE_HOST = "localhost"
DEFAULT_CLICKHOUSE_PORT = 8123
DEFAULT_CLICKHOUSE_USER = "polyttool_admin"
DEFAULT_CLICKHOUSE_PASSWORD = "polyttool_admin"
DEFAULT_CLICKHOUSE_DATABASE = "polyttool"
DEFAULT_GAMMA_BASE = "https://gamma-api.polymarket.com"
DEFAULT_HTTP_TIMEOUT = 20.0

# Golden case configurations
GOLDEN_CASES = {
    "drpufferfish": {
        "user": "@DrPufferfish",
        "wallet": "0xdb27bf2ac5d428a9c63dbc914611036855a6c56e",
    },
}

# Standardized prompt template
EXAMINATION_PROMPT_TEMPLATE = """You are an LLM assistant analyzing a Polymarket trader's activity.

INSTRUCTIONS:
1. Every factual claim MUST include a citation using [file_path: ...] format
2. Do NOT invent details or use outside knowledge
3. If a claim is not supported by evidence, say so explicitly

REQUIRED OUTPUTS:
1. hypothesis.md - Markdown report with:
   - Executive summary (3-6 bullets)
   - Key observations with citations
   - Hypotheses table with: claim, evidence, confidence, falsification method
   - Limitations section
   - Missing data for backtest section

2. hypothesis.json - JSON matching docs/specs/hypothesis_schema_v1.json with:
   - schema_version: "hypothesis_v1"
   - metadata (user_slug, run_id, created_at_utc, model)
   - executive_summary.bullets
   - hypotheses array (each with claim, evidence[], confidence, falsification)
   - observations, limitations, missing_data_for_backtest

EVIDENCE FILES (paste in this order):
1. memo.md - Human-readable research memo
2. dossier.json - Structured data (key sections)
3. manifest.json - Export metadata
4. RAG excerpts with [file_path: ...] headers

CITATION FORMAT:
[file_path: kb/users/drpufferfish/notes/2026-02-03.md]
[trade_uid: abc123...]

User: {user_handle}
Window: {window_days} days
Dossier path: {dossier_path}
Bundle path: {bundle_path}
"""


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
    """Populate os.environ with defaults from .env."""
    for key, value in env.items():
        os.environ.setdefault(key, value)


def _utcnow() -> datetime:
    return datetime.utcnow()


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


def _format_utc(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def _get_clickhouse_client():
    """Get ClickHouse client or None if unavailable."""
    if clickhouse_connect is None:
        return None
    try:
        return clickhouse_connect.get_client(
            host=os.getenv("CLICKHOUSE_HOST", DEFAULT_CLICKHOUSE_HOST),
            port=int(os.getenv("CLICKHOUSE_PORT", str(DEFAULT_CLICKHOUSE_PORT))),
            username=os.getenv("CLICKHOUSE_USER", DEFAULT_CLICKHOUSE_USER),
            password=os.getenv("CLICKHOUSE_PASSWORD", DEFAULT_CLICKHOUSE_PASSWORD),
            database=os.getenv("CLICKHOUSE_DATABASE", DEFAULT_CLICKHOUSE_DATABASE),
        )
    except Exception as e:
        print(f"Warning: Could not connect to ClickHouse: {e}", file=sys.stderr)
        return None


def _resolve_user(user_input: str, gamma_client: GammaClient) -> Optional[Dict[str, str]]:
    """Resolve user to username and wallet, preserving original input for slug derivation."""
    profile = gamma_client.resolve(user_input)
    if profile is None:
        return None

    # Preserve the original user_input as the handle for consistent slug derivation
    # This ensures --user "@DrPufferfish" always routes to "drpufferfish/" folder
    original_handle = user_input.strip()
    if original_handle and not original_handle.startswith("@"):
        if not original_handle.startswith("0x"):  # Not a wallet address
            original_handle = f"@{original_handle}"

    return {
        "username": profile.username,
        "proxy_wallet": profile.proxy_wallet,
        "user_handle": original_handle if original_handle else (
            f"@{profile.username}" if profile.username else profile.proxy_wallet[:10] + "..."
        ),
        "original_input": user_input,  # Preserve for UserContext
    }


def _run_export_dossier(
    client,
    user_ctx: UserContext,
    user_info: Dict[str, str],
    window_days: int,
    max_trades: int,
    artifacts_dir: str,
) -> Optional[Dict[str, Any]]:
    """Run dossier export and return result."""
    if client is None:
        print("Error: ClickHouse not available for dossier export.", file=sys.stderr)
        return None

    try:
        result = export_user_dossier(
            clickhouse_client=client,
            proxy_wallet=user_info["proxy_wallet"],
            user_input=user_info["user_handle"],
            username=user_ctx.handle or user_info["username"],
            window_days=window_days,
            max_trades=max_trades,
            artifacts_base_path=artifacts_dir,
            user_slug_override=user_ctx.slug,
        )
        return {
            "export_id": result.export_id,
            "artifact_path": result.artifact_path,
            "path_json": result.path_json,
            "path_md": result.path_md,
            "manifest_path": result.manifest_path,
            "stats": result.stats,
        }
    except Exception as e:
        print(f"Error during dossier export: {e}", file=sys.stderr)
        return None


def plan_output_paths(user_ctx: UserContext, now: Optional[datetime] = None) -> Dict[str, str]:
    """Build canonical output roots from UserContext."""
    timestamp = now or _utcnow()
    date_label = timestamp.strftime("%Y-%m-%d")
    wallet_segment = user_ctx.wallet or "<wallet>"

    dossier_root = user_ctx.artifacts_user_dir / wallet_segment
    bundle_root = user_ctx.llm_bundles_dir

    return {
        "date_label": date_label,
        "dossier_root": str(dossier_root),
        "bundle_root": str(bundle_root),
    }


def _run_llm_bundle(
    user_slug: str,
    dossier_path: str,
) -> Optional[Dict[str, Any]]:
    """Run LLM bundle creation."""
    try:
        from tools.cli.llm_bundle import main as llm_bundle_main
        # Call llm_bundle with the user and dossier path
        # Note: llm_bundle writes files and prints output
        result = llm_bundle_main([
            "--user", user_slug,
            "--dossier-path", dossier_path,
            "--no-devlog",  # We'll write our own consolidated devlog
        ])
        if result != 0:
            return None

        # Find the latest bundle directory
        now = _utcnow()
        date_label = now.strftime("%Y-%m-%d")
        bundle_base = Path("kb") / "users" / user_slug / "llm_bundles" / date_label

        if not bundle_base.exists():
            return None

        # Find most recent run_id directory
        run_dirs = sorted(bundle_base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if not run_dirs:
            return None

        bundle_dir = run_dirs[0]
        bundle_path = bundle_dir / "bundle.md"
        manifest_path = bundle_dir / "bundle_manifest.json"

        if not bundle_path.exists():
            return None

        return {
            "bundle_dir": str(bundle_dir),
            "bundle_path": str(bundle_path),
            "manifest_path": str(manifest_path) if manifest_path.exists() else None,
            "run_id": bundle_dir.name,
        }
    except Exception as e:
        print(f"Error during LLM bundle creation: {e}", file=sys.stderr)
        return None


def _write_prompt(
    bundle_dir: Path,
    user_handle: str,
    user_slug: str,
    window_days: int,
    dossier_path: str,
    bundle_path: str,
) -> Path:
    """Write standardized prompt file."""
    prompt_text = EXAMINATION_PROMPT_TEMPLATE.format(
        user_handle=user_handle,
        window_days=window_days,
        dossier_path=dossier_path,
        bundle_path=bundle_path,
    )

    prompt_path = bundle_dir / "prompt.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    return prompt_path


def _load_dossier_positions(artifact_path: str) -> List[Dict[str, Any]]:
    """Load position lifecycle data from a dossier.json file."""
    dossier_json_path = Path(artifact_path) / "dossier.json"
    if not dossier_json_path.exists():
        return []
    try:
        dossier = json.loads(dossier_json_path.read_text(encoding="utf-8"))
        positions = dossier.get("positions", {}).get("positions", [])
        # Normalize fee fields on every position
        for pos in positions:
            normalize_fee_fields(pos)
        return positions
    except (json.JSONDecodeError, KeyError):
        return []


def _emit_trust_artifacts(
    dossier_path: str,
    run_id: str,
    started_at: str,
    user_ctx: UserContext,
    user_info: Dict[str, str],
    window_days: int,
    max_trades: int,
    artifacts_dir: str,
    argv: List[str],
    bundle_result: Optional[Dict[str, Any]],
) -> Dict[str, str]:
    """Emit Coverage & Reconciliation Report + Run Manifest into the dossier run dir.

    Returns dict of written file paths.
    """
    output_dir = Path(dossier_path)
    emitted: Dict[str, str] = {}

    # --- Coverage Report ---
    positions = _load_dossier_positions(dossier_path)
    coverage_report = build_coverage_report(
        positions=positions,
        run_id=run_id,
        user_slug=user_ctx.slug,
        wallet=user_ctx.wallet or "",
        proxy_wallet=user_info.get("proxy_wallet", ""),
    )
    coverage_paths = write_coverage_report(coverage_report, output_dir, write_markdown=True)
    emitted.update(coverage_paths)

    # --- Run Manifest ---
    from datetime import datetime, timezone
    finished_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    output_paths_map = {
        "run_root": dossier_path,
        "dossier_path": dossier_path,
    }
    if bundle_result:
        output_paths_map["kb_bundle_path"] = bundle_result.get("bundle_dir", "")

    effective_config = {
        "window_days": window_days,
        "max_trades": max_trades,
        "artifacts_dir": artifacts_dir,
    }

    manifest = build_run_manifest(
        run_id=run_id,
        started_at=started_at,
        command_name="examine",
        argv=argv,
        user_input=user_info.get("original_input", ""),
        user_slug=user_ctx.slug,
        wallets=[w for w in [user_ctx.wallet, user_info.get("proxy_wallet")] if w],
        output_paths=output_paths_map,
        effective_config=effective_config,
        finished_at=finished_at,
    )
    manifest_path = write_run_manifest(manifest, output_dir)
    emitted["run_manifest"] = manifest_path

    return emitted


def _write_examine_manifest(
    bundle_dir: Path,
    user_ctx: UserContext,
    window_days: int,
    dossier_result: Dict[str, Any],
    bundle_result: Dict[str, Any],
    run_id: str,
) -> Path:
    """Write examination manifest."""
    now = _utcnow()
    manifest = {
        "examine_run_id": run_id,
        "created_at_utc": _format_utc(now),
        "user_slug": user_ctx.slug,
        "user_handle": user_ctx.handle or "",
        "proxy_wallet": user_ctx.wallet or "",
        "window_days": window_days,
        "dossier": {
            "export_id": dossier_result.get("export_id"),
            "artifact_path": dossier_result.get("artifact_path"),
        },
        "bundle": {
            "run_id": bundle_result.get("run_id"),
            "bundle_dir": bundle_result.get("bundle_dir"),
        },
        "stats": dossier_result.get("stats", {}),
    }

    manifest_path = bundle_dir / "examine_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run complete user examination workflow.",
    )
    parser.add_argument(
        "--user",
        help="Target Polymarket username (@name) or wallet address",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help=f"Lookback window in days (default: {DEFAULT_WINDOW_DAYS})",
    )
    parser.add_argument(
        "--max-trades",
        type=int,
        default=DEFAULT_MAX_TRADES,
        help=f"Max anchor trades (default: {DEFAULT_MAX_TRADES})",
    )
    parser.add_argument(
        "--output",
        default="./reports",
        help="Output directory for reports (default: ./reports)",
    )
    parser.add_argument(
        "--artifacts-dir",
        default="artifacts",
        help="Base path for artifacts (default: artifacts)",
    )
    parser.add_argument(
        "--config",
        help="Path to polytool.yaml config file",
    )
    parser.add_argument(
        "--all-golden",
        action="store_true",
        help="Run examination for all golden cases (MVP: DrPufferfish only)",
    )
    parser.add_argument(
        "--skip-scan",
        action="store_true",
        help="Skip scan step (use existing ClickHouse data)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without executing",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    env_values = load_env_file(os.path.join(os.getcwd(), ".env"))
    apply_env_defaults(env_values)

    parser = build_parser()
    args = parser.parse_args(argv)

    # Determine target users
    users_to_examine: List[Dict[str, str]] = []

    if args.all_golden:
        # MVP: Only DrPufferfish
        for name, config in GOLDEN_CASES.items():
            users_to_examine.append({
                "user_input": config["user"],
                "name": name,
            })
    elif args.user:
        users_to_examine.append({
            "user_input": args.user.strip(),
            "name": args.user.strip(),
        })
    else:
        print("Error: --user or --all-golden is required.", file=sys.stderr)
        return 1

    # Load config if provided
    config: Dict[str, Any] = {}
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            try:
                import yaml  # type: ignore
                config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except ImportError:
                # Fall back to JSON if yaml not available
                try:
                    config = json.loads(config_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse config file: {args.config}", file=sys.stderr)
        else:
            print(f"Warning: Config file not found: {args.config}", file=sys.stderr)

    # Apply config defaults
    window_days = args.days or config.get("defaults", {}).get("days", DEFAULT_WINDOW_DAYS)
    max_trades = args.max_trades or config.get("defaults", {}).get("max_trades", DEFAULT_MAX_TRADES)
    artifacts_dir = args.artifacts_dir or config.get("defaults", {}).get("artifacts_dir", "artifacts")

    # Initialize Gamma client for identity resolution (used in both dry-run and execute mode).
    gamma_client = GammaClient(
        base_url=os.getenv("GAMMA_API_BASE", DEFAULT_GAMMA_BASE),
        timeout=float(os.getenv("HTTP_TIMEOUT_SECONDS", str(DEFAULT_HTTP_TIMEOUT))),
    )

    if args.dry_run:
        print("DRY RUN - would examine:")
        had_errors = False
        for u in users_to_examine:
            user_input = u["user_input"]
            user_info = _resolve_user(user_input, gamma_client)
            if user_info is None:
                had_errors = True
                print(f"  - {user_input}: ERROR could not resolve user")
                continue
            try:
                user_ctx = resolve_user_context(
                    handle=user_info["user_handle"],
                    wallet=user_info["proxy_wallet"],
                    kb_root=Path("kb"),
                    artifacts_root=Path(artifacts_dir),
                    require_wallet_for_handle=True,
                )
            except ValueError as exc:
                had_errors = True
                print(f"  - {user_input}: ERROR {exc}")
                continue

            planned = plan_output_paths(user_ctx)
            print(f"  - input: {user_input}")
            print(f"    handle: {user_ctx.handle}")
            print(f"    slug: {user_ctx.slug}")
            print(f"    wallet: {user_ctx.wallet}")
            print(f"    dossier root: {planned['dossier_root']}")
            print(f"    bundle root: {planned['bundle_root']}")
            print(f"    days={window_days}, max_trades={max_trades}")
        return 1 if had_errors else 0

    # Initialize ClickHouse client
    ch_client = _get_clickhouse_client()

    results: List[Dict[str, Any]] = []

    for user_target in users_to_examine:
        user_input = user_target["user_input"]
        from datetime import timezone as _tz
        _started_at = datetime.now(_tz.utc).replace(microsecond=0).isoformat()
        print(f"\n{'='*60}")
        print(f"Examining: {user_input}")
        print(f"{'='*60}")

        # 1. Resolve user
        user_info = _resolve_user(user_input, gamma_client)
        if user_info is None:
            print(f"Error: Could not resolve user: {user_input}", file=sys.stderr)
            continue

        # Use canonical identity resolver - handle-first slug derivation
        try:
            user_ctx = resolve_user_context(
                handle=user_info["user_handle"],
                wallet=user_info["proxy_wallet"],
                kb_root=Path("kb"),
                artifacts_root=Path(artifacts_dir),
                require_wallet_for_handle=True,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            continue
        user_slug = user_ctx.slug

        # Debug log: show resolved context + output roots
        logger.debug(
            "Resolved UserContext: %s | kb_user_dir=%s | artifacts_user_dir=%s",
            user_ctx.to_dict(),
            user_ctx.kb_user_dir,
            user_ctx.artifacts_user_dir,
        )
        print(f"Resolved: {user_info['user_handle']} -> slug={user_slug} ({user_info['proxy_wallet'][:10]}...)")

        # 2. Export dossier
        print("\n[1/3] Exporting dossier...")
        dossier_result = _run_export_dossier(
            ch_client,
            user_ctx,
            user_info,
            window_days,
            max_trades,
            artifacts_dir,
        )
        if dossier_result is None:
            print("Error: Dossier export failed.", file=sys.stderr)
            continue

        print(f"  Dossier: {dossier_result['artifact_path']}")
        print(f"  Stats: trades={dossier_result['stats'].get('trades_count', 0)}, "
              f"coverage={dossier_result['stats'].get('mapping_coverage', 0):.1%}")

        # 3. Build LLM bundle
        print("\n[2/3] Building LLM bundle...")
        bundle_result = _run_llm_bundle(user_slug, dossier_result["artifact_path"])
        if bundle_result is None:
            print("Error: LLM bundle creation failed.", file=sys.stderr)
            continue

        print(f"  Bundle: {bundle_result['bundle_dir']}")

        # 4. Write prompt
        print("\n[3/3] Generating prompt...")
        bundle_dir = Path(bundle_result["bundle_dir"])
        run_id = _short_uuid()

        prompt_path = _write_prompt(
            bundle_dir,
            user_info["user_handle"],
            user_slug,
            window_days,
            dossier_result["artifact_path"],
            bundle_result["bundle_path"],
        )
        print(f"  Prompt: {prompt_path}")

        # Write manifest
        manifest_path = _write_examine_manifest(
            bundle_dir,
            user_ctx,
            window_days,
            dossier_result,
            bundle_result,
            run_id,
        )
        print(f"  Manifest: {manifest_path}")

        # Emit trust & validation artifacts
        trust_paths = _emit_trust_artifacts(
            dossier_path=dossier_result["artifact_path"],
            run_id=run_id,
            started_at=_started_at,
            user_ctx=user_ctx,
            user_info=user_info,
            window_days=window_days,
            max_trades=max_trades,
            artifacts_dir=artifacts_dir,
            argv=argv or [],
            bundle_result=bundle_result,
        )
        for label, fpath in trust_paths.items():
            print(f"  Trust artifact ({label}): {fpath}")

        results.append({
            "user": user_info["user_handle"],
            "user_slug": user_slug,
            "dossier_path": dossier_result["artifact_path"],
            "bundle_path": bundle_result["bundle_path"],
            "prompt_path": str(prompt_path),
            "stats": dossier_result["stats"],
        })

    # Summary
    print(f"\n{'='*60}")
    print("EXAMINATION COMPLETE")
    print(f"{'='*60}")

    for r in results:
        print(f"\n{r['user']}:")
        print(f"  Dossier: {r['dossier_path']}")
        print(f"  Bundle:  {r['bundle_path']}")
        print(f"  Prompt:  {r['prompt_path']}")
        print(f"  Trades:  {r['stats'].get('trades_count', 0)}")

    if results:
        print("\nNEXT STEPS:")
        print("1. Review the bundle.md file")
        print("2. Copy prompt.txt to your LLM (Claude, etc.)")
        print("3. Paste bundle.md content after the prompt")
        print("4. Save the generated hypothesis.md and hypothesis.json")
        print("5. Run: polytool llm-save --user <slug> --model <model> ...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
