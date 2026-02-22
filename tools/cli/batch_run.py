#!/usr/bin/env python3
"""Batch-run harness for multi-user scan + hypothesis leaderboard aggregation."""

from __future__ import annotations

import argparse
import concurrent.futures
import copy
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from tools.cli import scan

DEFAULT_OUTPUT_ROOT = Path("artifacts") / "research" / "batch_runs"
TOP_LIST_LIMIT = 10
TOP_CANDIDATES_PER_USER = 5
TOP_EXAMPLES_PER_SEGMENT = 5

SCAN_PASSTHROUGH_OPTIONS = [
    "--api-base-url",
    "--full",
    "--lite",
    "--ingest-positions",
    "--compute-pnl",
    "--enrich-resolutions",
    "--debug-export",
    "--warm-clv-cache",
    "--compute-clv",
]

ENTRY_CONTEXT_COUNT_FIELDS = (
    "price_at_entry_present_count",
    "price_1h_before_entry_present_count",
    "open_price_present_count",
    "movement_direction_present_count",
    "minutes_to_close_present_count",
)

ScanCallable = Callable[[str, Dict[str, Any]], str]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _to_float(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _to_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _round6(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(value, 6)


def _fmt_number(value: Optional[float]) -> str:
    if value is None:
        return "null"
    return f"{value:.6f}"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )


def _read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _clone_scan_passthrough_actions(parser: argparse.ArgumentParser) -> None:
    scan_parser = scan.build_parser()
    scan_actions_by_option: dict[str, argparse.Action] = {}
    for action in scan_parser._actions:  # noqa: SLF001 - argparse internals are stable here.
        for option in action.option_strings:
            scan_actions_by_option[option] = action

    for option in SCAN_PASSTHROUGH_OPTIONS:
        action = scan_actions_by_option.get(option)
        if action is None:
            raise RuntimeError(f"Unable to locate scan action for {option}")
        cloned = copy.deepcopy(action)
        parser._add_action(cloned)  # noqa: SLF001 - reuse exact scan flag behavior.


def _parse_users_file(path: Path, max_users: Optional[int] = None) -> list[str]:
    if max_users is not None and max_users <= 0:
        raise ValueError("--max-users must be a positive integer when provided.")
    if not path.exists():
        raise FileNotFoundError(f"Users file not found: {path}")

    users: list[str] = []
    seen: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue
        users.append(line)
        seen.add(line)
        if max_users is not None and len(users) >= max_users:
            break
    return users


def _scan_flags_from_args(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "api_base_url": args.api_base_url,
        "full": bool(getattr(args, "full", False)),
        "lite": bool(getattr(args, "lite", False)),
        "ingest_positions": bool(args.ingest_positions),
        "compute_pnl": bool(args.compute_pnl),
        "enrich_resolutions": bool(args.enrich_resolutions),
        "debug_export": bool(args.debug_export),
        "warm_clv_cache": bool(args.warm_clv_cache),
        "compute_clv": bool(args.compute_clv),
    }


def _scan_argv_for_user(user: str, scan_flags: Dict[str, Any]) -> list[str]:
    argv = ["--user", user]
    api_base_url = str(scan_flags.get("api_base_url") or "").strip()
    if api_base_url:
        argv.extend(["--api-base-url", api_base_url])
    if scan_flags.get("full"):
        argv.append("--full")
    if scan_flags.get("lite"):
        argv.append("--lite")
    if scan_flags.get("ingest_positions"):
        argv.append("--ingest-positions")
    if scan_flags.get("compute_pnl"):
        argv.append("--compute-pnl")
    if scan_flags.get("enrich_resolutions"):
        argv.append("--enrich-resolutions")
    if scan_flags.get("debug_export"):
        argv.append("--debug-export")
    if scan_flags.get("warm_clv_cache"):
        argv.append("--warm-clv-cache")
    if scan_flags.get("compute_clv"):
        argv.append("--compute-clv")
    return argv


def _resolve_run_root_from_emitted(emitted: Dict[str, str]) -> str:
    manifest_path_raw = str(emitted.get("run_manifest") or "").strip()
    if manifest_path_raw:
        manifest_path = Path(manifest_path_raw)
        if not manifest_path.exists():
            raise FileNotFoundError(f"run_manifest.json not found: {manifest_path}")
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
    raise ValueError("Scan output missing run root and run_manifest path.")


def _default_scan_callable(user: str, scan_flags: Dict[str, Any]) -> str:
    scan_argv = _scan_argv_for_user(user, scan_flags)
    scan_parser = scan.build_parser()
    scan_args = scan_parser.parse_args(scan_argv)
    scan_args = scan.apply_scan_defaults(scan_args, scan_argv)
    scan_config = scan.build_config(scan_args)
    scan.validate_config(scan_config)
    emitted = scan.run_scan(config=scan_config, argv=scan_argv, started_at=_iso_utc(_utcnow()))
    return _resolve_run_root_from_emitted(emitted)


def _extract_entry_context_coverage_rate(entry_context: Dict[str, Any]) -> Optional[float]:
    eligible = _to_int(entry_context.get("eligible_positions"))
    if eligible is None or eligible <= 0:
        return None
    rates: list[float] = []
    for field in ENTRY_CONTEXT_COUNT_FIELDS:
        present_count = _to_int(entry_context.get(field))
        if present_count is None:
            continue
        rates.append(present_count / eligible)
    if not rates:
        return None
    # Conservative definition: lowest field coverage rate in the entry-context bundle.
    return _round6(min(rates))


def _extract_notional_weight_total(
    coverage_payload: Dict[str, Any],
    segment_payload: Dict[str, Any],
) -> Optional[float]:
    segment_analysis = coverage_payload.get("segment_analysis") or {}
    if isinstance(segment_analysis, dict):
        hypothesis_meta = segment_analysis.get("hypothesis_meta") or {}
        if isinstance(hypothesis_meta, dict):
            value = _to_float(hypothesis_meta.get("notional_weight_total_global"))
            if value is not None:
                return _round6(value)

    segment_analysis_payload = segment_payload.get("segment_analysis") or {}
    if isinstance(segment_analysis_payload, dict):
        hypothesis_meta = segment_analysis_payload.get("hypothesis_meta") or {}
        if isinstance(hypothesis_meta, dict):
            value = _to_float(hypothesis_meta.get("notional_weight_total_global"))
            if value is not None:
                return _round6(value)
    return None


def _success_user_result(user: str, run_root: Path) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
    candidates_path = run_root / "hypothesis_candidates.json"
    coverage_path = run_root / "coverage_reconciliation_report.json"
    segment_path = run_root / "segment_analysis.json"

    candidates_payload = _read_json(candidates_path)
    coverage_payload = _read_json(coverage_path)
    segment_payload = _read_json(segment_path) if segment_path.exists() else {}

    candidates = candidates_payload.get("candidates") or []
    if not isinstance(candidates, list):
        candidates = []

    clv_coverage = coverage_payload.get("clv_coverage") or {}
    entry_context_coverage = coverage_payload.get("entry_context_coverage") or {}
    coverage_summary = {
        "clv_coverage_rate": _round6(_to_float(clv_coverage.get("coverage_rate"))),
        "entry_context_coverage_rate": _extract_entry_context_coverage_rate(
            entry_context_coverage if isinstance(entry_context_coverage, dict) else {}
        ),
        "notional_weight_total_global": _extract_notional_weight_total(
            coverage_payload=coverage_payload,
            segment_payload=segment_payload,
        ),
    }

    result = {
        "user": user,
        "run_root": run_root.as_posix(),
        "hypothesis_candidates_path": candidates_path.as_posix(),
        "status": "success",
        "error": None,
        "coverage": coverage_summary,
        "top_candidates": candidates[:TOP_CANDIDATES_PER_USER],
    }
    return result, [candidate for candidate in candidates if isinstance(candidate, dict)]


def _failure_user_result(user: str, error: str) -> Dict[str, Any]:
    return {
        "user": user,
        "run_root": None,
        "hypothesis_candidates_path": None,
        "status": "failure",
        "error": error,
        "coverage": {
            "clv_coverage_rate": None,
            "entry_context_coverage_rate": None,
            "notional_weight_total_global": None,
        },
        "top_candidates": [],
    }


def _weighted_metric(
    contributions: list[Dict[str, Any]],
    *,
    expected_weighting: str,
    metric_field: str,
    denominator_field: str,
    denominator_label: str,
) -> Dict[str, Any]:
    weighted_sum = 0.0
    denominator_sum = 0.0
    users: set[str] = set()
    for contribution in contributions:
        if contribution.get("weighting") != expected_weighting:
            continue
        metrics = contribution.get("metrics") or {}
        denominators = contribution.get("denominators") or {}
        metric_value = _to_float(metrics.get(metric_field))
        denominator_value = _to_float(denominators.get(denominator_field))
        if metric_value is None or denominator_value is None or denominator_value <= 0:
            continue
        weighted_sum += metric_value * denominator_value
        denominator_sum += denominator_value
        users.add(str(contribution.get("user") or ""))

    value = None
    if denominator_sum > 0:
        value = _round6(weighted_sum / denominator_sum)
    return {
        "value": value,
        "users_used": len([user for user in users if user]),
        denominator_label: _round6(denominator_sum) if denominator_sum > 0 else 0.0,
    }


def _segment_rows_from_candidates(
    segment_contributions: Dict[str, list[Dict[str, Any]]],
) -> list[Dict[str, Any]]:
    rows: list[Dict[str, Any]] = []
    for segment_key, raw_contribs in sorted(segment_contributions.items(), key=lambda item: item[0]):
        users_with_segment = sorted(
            {str(item.get("user") or "") for item in raw_contribs if str(item.get("user") or "")}
        )
        total_count = 0
        total_notional_weight_used = 0.0
        for contribution in raw_contribs:
            metrics = contribution.get("metrics") or {}
            denominators = contribution.get("denominators") or {}
            count_value = _to_int(metrics.get("count")) or 0
            total_count += max(0, count_value)
            if contribution.get("weighting") == "notional":
                weight_used = _to_float(denominators.get("weight_used")) or 0.0
                if weight_used > 0:
                    total_notional_weight_used += weight_used

        scores = {
            "notional_weighted_avg_clv_pct": _weighted_metric(
                raw_contribs,
                expected_weighting="notional",
                metric_field="notional_weighted_avg_clv_pct",
                denominator_field="weight_used",
                denominator_label="weight_used",
            ),
            "notional_weighted_beat_close_rate": _weighted_metric(
                raw_contribs,
                expected_weighting="notional",
                metric_field="notional_weighted_beat_close_rate",
                denominator_field="weight_used",
                denominator_label="weight_used",
            ),
            "count_weighted_avg_clv_pct": _weighted_metric(
                raw_contribs,
                expected_weighting="count",
                metric_field="avg_clv_pct",
                denominator_field="count_used",
                denominator_label="count_used",
            ),
            "count_weighted_beat_close_rate": _weighted_metric(
                raw_contribs,
                expected_weighting="count",
                metric_field="beat_close_rate",
                denominator_field="count_used",
                denominator_label="count_used",
            ),
        }

        weighting_order = {"notional": 0, "count": 1}
        ordered_examples = sorted(
            raw_contribs,
            key=lambda item: (
                weighting_order.get(str(item.get("weighting") or ""), 99),
                _to_int(item.get("rank")) or 0,
                str(item.get("user") or ""),
            ),
        )
        examples = [
            {
                "user": item.get("user"),
                "rank": _to_int(item.get("rank")) or 0,
                "weighting": item.get("weighting"),
                "metrics": item.get("metrics"),
                "denominators": item.get("denominators"),
            }
            for item in ordered_examples[:TOP_EXAMPLES_PER_SEGMENT]
        ]

        rows.append(
            {
                "segment_key": segment_key,
                "users_with_segment": len(users_with_segment),
                "total_count": total_count,
                "total_notional_weight_used": _round6(total_notional_weight_used),
                "scores": scores,
                "examples": examples,
            }
        )
    return rows


def _top_segments_by_metric(
    segment_rows: list[Dict[str, Any]],
    *,
    metric_name: str,
) -> list[str]:
    ranked = [
        row
        for row in segment_rows
        if (row.get("scores") or {}).get(metric_name, {}).get("value") is not None
    ]
    ranked.sort(
        key=lambda row: (
            -float((row.get("scores") or {}).get(metric_name, {}).get("value")),
            str(row.get("segment_key") or ""),
        )
    )
    return [str(row.get("segment_key") or "") for row in ranked[:TOP_LIST_LIMIT]]


def _top_segments_by_persistence(segment_rows: list[Dict[str, Any]]) -> list[str]:
    ranked = list(segment_rows)
    ranked.sort(
        key=lambda row: (
            -(_to_int(row.get("users_with_segment")) or 0),
            str(row.get("segment_key") or ""),
        )
    )
    return [str(row.get("segment_key") or "") for row in ranked[:TOP_LIST_LIMIT]]


def _build_markdown(leaderboard: Dict[str, Any]) -> str:
    segment_by_key = {
        str(row.get("segment_key") or ""): row for row in leaderboard.get("segments", [])
    }
    top_lists = leaderboard.get("top_lists") or {}

    lines: list[str] = []
    lines.append("# Hypothesis Leaderboard")
    lines.append("")
    lines.append(
        "This report combines hypothesis candidates across users to highlight which segment patterns appear strongest and most repeatable."
    )
    lines.append("")
    lines.append("## Batch Metadata")
    lines.append(f"- Batch ID: `{leaderboard.get('batch_id')}`")
    lines.append(f"- Created at: `{leaderboard.get('created_at')}`")
    lines.append(f"- Users attempted: {leaderboard.get('users_attempted')}")
    lines.append(f"- Users succeeded: {leaderboard.get('users_succeeded')}")
    lines.append(f"- Users failed: {leaderboard.get('users_failed')}")
    lines.append("")

    sections = [
        (
            "Top 10 by notional_weighted_avg_clv_pct",
            top_lists.get("top_by_notional_weighted_avg_clv_pct") or [],
            "notional_weighted_avg_clv_pct",
        ),
        (
            "Top 10 by notional_weighted_beat_close_rate",
            top_lists.get("top_by_notional_weighted_beat_close_rate") or [],
            "notional_weighted_beat_close_rate",
        ),
        (
            "Top 10 by persistence (users_with_segment)",
            top_lists.get("top_by_persistence_users") or [],
            None,
        ),
    ]

    for title, segment_keys, metric_name in sections:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| Rank | Segment | Score | Users | Denominator |")
        lines.append("| --- | --- | ---: | ---: | ---: |")
        for idx, segment_key in enumerate(segment_keys, start=1):
            row = segment_by_key.get(str(segment_key))
            if row is None:
                continue
            if metric_name is None:
                score_text = str(row.get("users_with_segment"))
                denominator = str(row.get("total_count"))
            else:
                score = (row.get("scores") or {}).get(metric_name, {})
                score_text = _fmt_number(_to_float(score.get("value")))
                if metric_name.startswith("notional_"):
                    denominator = _fmt_number(_to_float(score.get("weight_used")))
                else:
                    denominator = str(_to_int(score.get("count_used")) or 0)
            lines.append(
                f"| {idx} | `{segment_key}` | {score_text} | {row.get('users_with_segment', 0)} | {denominator} |"
            )
        if not segment_keys:
            lines.append("| - | _(none)_ | - | - | - |")
        lines.append("")

    lines.append("## Top Segment Detail")
    lines.append("")
    top_detail_keys = (top_lists.get("top_by_notional_weighted_avg_clv_pct") or [])[:3]
    for idx, segment_key in enumerate(top_detail_keys, start=1):
        row = segment_by_key.get(str(segment_key))
        if row is None:
            continue
        scores = row.get("scores") or {}
        notional_users = sorted(
            {
                str(example.get("user") or "")
                for example in row.get("examples", [])
                if str(example.get("weighting") or "") == "notional" and str(example.get("user") or "")
            }
        )
        lines.append(f"### {idx}. `{segment_key}`")
        lines.append(f"- users_with_segment: {row.get('users_with_segment', 0)}")
        lines.append(f"- total_count: {row.get('total_count', 0)}")
        lines.append(
            f"- total_notional_weight_used: {_fmt_number(_to_float(row.get('total_notional_weight_used')))}"
        )
        lines.append(
            "- notional_weighted_avg_clv_pct: "
            f"{_fmt_number(_to_float((scores.get('notional_weighted_avg_clv_pct') or {}).get('value')))} "
            f"(users_used={(scores.get('notional_weighted_avg_clv_pct') or {}).get('users_used', 0)}, "
            f"weight_used={_fmt_number(_to_float((scores.get('notional_weighted_avg_clv_pct') or {}).get('weight_used')))})"
        )
        lines.append(
            "- notional_weighted_beat_close_rate: "
            f"{_fmt_number(_to_float((scores.get('notional_weighted_beat_close_rate') or {}).get('value')))} "
            f"(users_used={(scores.get('notional_weighted_beat_close_rate') or {}).get('users_used', 0)}, "
            f"weight_used={_fmt_number(_to_float((scores.get('notional_weighted_beat_close_rate') or {}).get('weight_used')))})"
        )
        # Pull robust CLV stats from the first notional example's metrics
        first_notional_metrics = next(
            (
                ex.get("metrics") or {}
                for ex in row.get("examples", [])
                if str(ex.get("weighting") or "") == "notional" and str(ex.get("user") or "")
            ),
            {},
        )
        median_clv = _to_float(first_notional_metrics.get("median_clv_pct"))
        trimmed_clv = _to_float(first_notional_metrics.get("trimmed_mean_clv_pct"))
        robust_count = _to_int(first_notional_metrics.get("robust_clv_pct_count_used"))
        if median_clv is not None or trimmed_clv is not None:
            lines.append(
                f"- median_clv_pct: {_fmt_number(median_clv)} | "
                f"trimmed_mean_clv_pct: {_fmt_number(trimmed_clv)} "
                f"(robust_count_used={robust_count})"
            )
        contributors = ", ".join(f"`{user}`" for user in notional_users) if notional_users else "_none_"
        lines.append(f"- notional contributors: {contributors}")
        lines.append("")

    if not top_detail_keys:
        lines.append("_No segments qualified for detailed view._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _resolve_run_roots(path: Path) -> list[Path]:
    """Resolve run root directories from a directory or a file listing paths.

    If ``path`` is a directory, all immediate subdirectories are returned (non-
    recursive; plain files inside are skipped).  If ``path`` is a file, each
    non-blank, non-comment line is interpreted as a path to a run root
    directory.  Raises ``FileNotFoundError`` if any resolved run root does not
    exist as a directory.
    """
    if not path.exists():
        raise FileNotFoundError(f"--run-roots path does not exist: {path}")

    if path.is_dir():
        roots = [child for child in sorted(path.iterdir()) if child.is_dir()]
    else:
        # Treat as a text file with one run-root path per line.
        roots = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            roots.append(Path(line))

    # Validate all resolved roots exist as directories.
    for root in roots:
        if not root.is_dir():
            raise FileNotFoundError(f"Run root directory does not exist: {root}")

    return roots


def aggregate_from_roots(
    run_roots: list[Path],
) -> tuple[list[Dict[str, Any]], Dict[str, list[Dict[str, Any]]]]:
    """Aggregate per-user results and segment contributions from existing run root directories.

    Returns ``(per_user_results, segment_contributions)`` using the same shape
    that ``BatchRunner.run_batch`` builds internally.  The user slug is read
    from ``hypothesis_candidates.json`` (``user_slug`` field) when present;
    otherwise the directory name is used as the slug.
    """
    per_user_results: list[Dict[str, Any]] = []
    segment_contributions: Dict[str, list[Dict[str, Any]]] = {}

    for run_root in run_roots:
        # Determine user slug.
        candidates_path = run_root / "hypothesis_candidates.json"
        try:
            candidates_payload = _read_json(candidates_path)
        except Exception:
            candidates_payload = {}
        user = str(candidates_payload.get("user_slug") or run_root.name).strip() or run_root.name

        try:
            success_result, candidates = _success_user_result(user=user, run_root=run_root)
            per_user_results.append(success_result)
            for candidate in candidates:
                segment_key = str(candidate.get("segment_key") or "").strip()
                if not segment_key:
                    continue
                contribution = {
                    "user": user,
                    "rank": _to_int(candidate.get("rank")) or 0,
                    "weighting": str(
                        (candidate.get("denominators") or {}).get("weighting") or ""
                    ).strip(),
                    "metrics": candidate.get("metrics") or {},
                    "denominators": candidate.get("denominators") or {},
                }
                segment_contributions.setdefault(segment_key, []).append(contribution)
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            per_user_results.append(_failure_user_result(user=user, error=error_text))

    return per_user_results, segment_contributions


def aggregate_only(
    *,
    run_roots: list[Path],
    output_root: Path,
    batch_id: str,
    now_provider: Optional[Callable[[], datetime]] = None,
) -> Dict[str, str]:
    """Re-aggregate existing run roots into a leaderboard without running scans.

    Constructs a ``BatchRunner`` and delegates to ``run_batch`` with
    ``run_roots_override`` set so the scan loop is bypassed entirely.
    """
    runner = BatchRunner(now_provider=now_provider)
    return runner.run_batch(
        users=[],
        users_file=Path(""),
        output_root=output_root,
        batch_id=batch_id,
        continue_on_error=True,
        scan_flags={},
        run_roots_override=run_roots,
    )


class BatchRunner:
    """Execute multi-user scans and aggregate hypothesis candidates."""

    def __init__(
        self,
        scan_callable: Optional[ScanCallable] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._scan_callable = scan_callable or _default_scan_callable
        self._now_provider = now_provider or _utcnow

    def run_batch(
        self,
        *,
        users: list[str],
        users_file: Path,
        output_root: Path,
        batch_id: str,
        continue_on_error: bool,
        scan_flags: Dict[str, Any],
        run_roots_override: Optional[list[Path]] = None,
        workers: int = 1,
    ) -> Dict[str, str]:
        now = self._now_provider()
        created_at = _iso_utc(now)
        batch_date = now.date().isoformat()
        batch_root = output_root / batch_date / batch_id
        batch_root.mkdir(parents=True, exist_ok=True)

        per_user_results: list[Dict[str, Any]] = []
        segment_contributions: Dict[str, list[Dict[str, Any]]] = {}

        if run_roots_override is not None:
            # Aggregate-only mode: skip scanning, read from existing run roots.
            per_user_results, segment_contributions = aggregate_from_roots(run_roots_override)
        elif workers > 1:
            # Parallel scan mode: submit one future per user, collect in original order.
            futures: list[concurrent.futures.Future[tuple[Dict[str, Any], list[Dict[str, Any]]]]] = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                for user in users:
                    future = executor.submit(self._scan_user, user, scan_flags, continue_on_error)
                    futures.append(future)

                # Collect in submission order to guarantee determinism.
                for user, future in zip(users, futures):
                    try:
                        success_result, candidates = future.result()
                        per_user_results.append(success_result)
                        for candidate in candidates:
                            segment_key = str(candidate.get("segment_key") or "").strip()
                            if not segment_key:
                                continue
                            contribution = {
                                "user": user,
                                "rank": _to_int(candidate.get("rank")) or 0,
                                "weighting": str(
                                    (candidate.get("denominators") or {}).get("weighting") or ""
                                ).strip(),
                                "metrics": candidate.get("metrics") or {},
                                "denominators": candidate.get("denominators") or {},
                            }
                            segment_contributions.setdefault(segment_key, []).append(contribution)
                    except Exception as exc:
                        error_text = f"{type(exc).__name__}: {exc}"
                        per_user_results.append(_failure_user_result(user=user, error=error_text))
                        if not continue_on_error:
                            raise
        else:
            # Sequential scan mode (original behaviour).
            for user in users:
                try:
                    run_root = Path(self._scan_callable(user, scan_flags))
                    success_result, candidates = _success_user_result(user=user, run_root=run_root)
                    per_user_results.append(success_result)
                    for candidate in candidates:
                        segment_key = str(candidate.get("segment_key") or "").strip()
                        if not segment_key:
                            continue
                        contribution = {
                            "user": user,
                            "rank": _to_int(candidate.get("rank")) or 0,
                            "weighting": str(
                                (candidate.get("denominators") or {}).get("weighting") or ""
                            ).strip(),
                            "metrics": candidate.get("metrics") or {},
                            "denominators": candidate.get("denominators") or {},
                        }
                        segment_contributions.setdefault(segment_key, []).append(contribution)
                except Exception as exc:
                    error_text = f"{type(exc).__name__}: {exc}"
                    per_user_results.append(_failure_user_result(user=user, error=error_text))
                    if not continue_on_error:
                        raise

        segment_rows = _segment_rows_from_candidates(segment_contributions)
        top_lists = {
            "top_by_notional_weighted_avg_clv_pct": _top_segments_by_metric(
                segment_rows,
                metric_name="notional_weighted_avg_clv_pct",
            ),
            "top_by_notional_weighted_beat_close_rate": _top_segments_by_metric(
                segment_rows,
                metric_name="notional_weighted_beat_close_rate",
            ),
            "top_by_persistence_users": _top_segments_by_persistence(segment_rows),
        }

        users_succeeded = sum(1 for row in per_user_results if row.get("status") == "success")
        users_failed = len(per_user_results) - users_succeeded

        leaderboard = {
            "batch_id": batch_id,
            "created_at": created_at,
            "users_attempted": len(per_user_results),
            "users_succeeded": users_succeeded,
            "users_failed": users_failed,
            "inputs": {
                "users_file": users_file.as_posix() if users_file != Path("") else None,
                "scan_flags": scan_flags,
            },
            "per_user": per_user_results,
            "segments": segment_rows,
            "top_lists": top_lists,
        }

        per_user_results_payload = {
            "batch_id": batch_id,
            "created_at": created_at,
            "per_user": per_user_results,
        }

        leaderboard_json_path = batch_root / "hypothesis_leaderboard.json"
        leaderboard_md_path = batch_root / "hypothesis_leaderboard.md"
        per_user_results_path = batch_root / "per_user_results.json"
        batch_manifest_path = batch_root / "batch_manifest.json"

        _write_json(leaderboard_json_path, leaderboard)
        _write_json(per_user_results_path, per_user_results_payload)
        leaderboard_md_path.write_text(_build_markdown(leaderboard), encoding="utf-8")

        batch_manifest = {
            "batch_id": batch_id,
            "created_at": created_at,
            "users_attempted": len(per_user_results),
            "users_succeeded": users_succeeded,
            "users_failed": users_failed,
            "output_paths": {
                "batch_root": batch_root.as_posix(),
                "batch_manifest_json": batch_manifest_path.as_posix(),
                "hypothesis_leaderboard_json": leaderboard_json_path.as_posix(),
                "hypothesis_leaderboard_md": leaderboard_md_path.as_posix(),
                "per_user_results_json": per_user_results_path.as_posix(),
            },
            "per_user_run_roots": [
                {
                    "user": row.get("user"),
                    "status": row.get("status"),
                    "run_root": row.get("run_root"),
                }
                for row in per_user_results
            ],
        }
        _write_json(batch_manifest_path, batch_manifest)

        return {
            "batch_root": batch_root.as_posix(),
            "batch_manifest_json": batch_manifest_path.as_posix(),
            "hypothesis_leaderboard_json": leaderboard_json_path.as_posix(),
            "hypothesis_leaderboard_md": leaderboard_md_path.as_posix(),
            "per_user_results_json": per_user_results_path.as_posix(),
        }

    def _scan_user(
        self,
        user: str,
        scan_flags: Dict[str, Any],
        continue_on_error: bool,
    ) -> tuple[Dict[str, Any], list[Dict[str, Any]]]:
        """Run scan for a single user; raises on failure (caller handles continue_on_error)."""
        run_root = Path(self._scan_callable(user, scan_flags))
        return _success_user_result(user=user, run_root=run_root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Batch-run PolyTool scan for multiple users and aggregate hypothesis candidates "
            "into deterministic leaderboard artifacts."
        )
    )
    parser.add_argument(
        "--users",
        required=False,
        help="Path to a file containing one @handle per line.",
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT.as_posix(),
        help=f"Root directory for batch artifacts (default: {DEFAULT_OUTPUT_ROOT.as_posix()}).",
    )
    parser.add_argument(
        "--batch-id",
        help="Optional batch id (default: random uuid4).",
    )
    parser.add_argument(
        "--continue-on-error",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Continue processing remaining users after a per-user scan failure (default: true).",
    )
    parser.add_argument(
        "--max-users",
        type=int,
        help="Optional safety cap on number of users loaded from --users.",
    )
    parser.add_argument(
        "--aggregate-only",
        action="store_true",
        default=False,
        help="Skip scanning; aggregate existing run roots into a leaderboard.",
    )
    parser.add_argument(
        "--run-roots",
        help=(
            "Path to a directory of run roots OR a file listing run root paths, "
            "one per line. Required when --aggregate-only is set."
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel scan workers (default: 1, sequential).",
    )
    _clone_scan_passthrough_actions(parser)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_root = Path(args.output_root)
    batch_id = str(args.batch_id or uuid.uuid4())

    if args.aggregate_only:
        if args.run_roots is None:
            print("Error: --run-roots is required when --aggregate-only is set.", file=sys.stderr)
            return 1
        try:
            run_roots = _resolve_run_roots(Path(args.run_roots))
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        runner = BatchRunner()
        try:
            output_paths = aggregate_only(
                run_roots=run_roots,
                output_root=output_root,
                batch_id=batch_id,
            )
        except Exception as exc:
            print(f"Aggregate-only run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
    else:
        if not args.users:
            print("Error: --users is required when not using --aggregate-only.", file=sys.stderr)
            return 1

        users_file = Path(args.users)
        scan_flags = _scan_flags_from_args(args)

        try:
            users = _parse_users_file(users_file, max_users=args.max_users)
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        if not users:
            print("Error: users file produced zero users after filtering blank/comment lines.", file=sys.stderr)
            return 1

        runner = BatchRunner()
        try:
            output_paths = runner.run_batch(
                users=users,
                users_file=users_file,
                output_root=output_root,
                batch_id=batch_id,
                continue_on_error=bool(args.continue_on_error),
                scan_flags=scan_flags,
                workers=args.workers,
            )
        except Exception as exc:
            print(f"Batch run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1

    print("Batch run complete")
    print(f"Batch root: {output_paths['batch_root']}")
    print(f"Manifest: {output_paths['batch_manifest_json']}")
    print(f"Leaderboard JSON: {output_paths['hypothesis_leaderboard_json']}")
    print(f"Leaderboard Markdown: {output_paths['hypothesis_leaderboard_md']}")
    print(f"Per-user results: {output_paths['per_user_results_json']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
