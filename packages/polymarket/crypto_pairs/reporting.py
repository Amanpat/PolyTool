"""Artifact-first paper-soak reporting for crypto-pair paper runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Optional


REPORT_SCHEMA_VERSION = "crypto_pair_paper_soak_report_v0"
GRACEFUL_PAPER_STOP_REASONS = frozenset({"completed", "operator_interrupt"})

PAPER_SOAK_SUMMARY_JSON = "paper_soak_summary.json"
PAPER_SOAK_SUMMARY_MD = "paper_soak_summary.md"

_PROMOTE_VERDICT = "PROMOTE TO MICRO LIVE CANDIDATE"
_RERUN_VERDICT = "RERUN PAPER SOAK"
_REJECT_VERDICT = "REJECT CURRENT CONFIG / DO NOT PROMOTE"

_BAND_PASS = "pass"
_BAND_RERUN = "rerun"
_BAND_REJECT = "reject"
_BAND_INSUFFICIENT = "insufficient_data"

_ZERO = Decimal("0")
_ONE = Decimal("1")

_REQUIRED_FILES = (
    "run_manifest.json",
    "run_summary.json",
    "runtime_events.jsonl",
)


class CryptoPairReportError(ValueError):
    """Raised when a paper run cannot be summarized into a report."""


@dataclass(frozen=True)
class LoadedPaperRun:
    run_dir: Path
    manifest_path: Path
    summary_path: Path
    runtime_events_path: Path
    manifest: dict[str, Any]
    run_summary: dict[str, Any]
    runtime_events: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    intents: list[dict[str, Any]]
    fills: list[dict[str, Any]]
    exposures: list[dict[str, Any]]
    settlements: list[dict[str, Any]]


@dataclass(frozen=True)
class CryptoPairReportResult:
    report: dict[str, Any]
    json_path: Path
    markdown_path: Path


def is_graceful_paper_stop_reason(stopped_reason: Any) -> bool:
    return str(stopped_reason or "").strip() in GRACEFUL_PAPER_STOP_REASONS


def build_report_artifact_paths(result: CryptoPairReportResult) -> dict[str, str]:
    return {
        "summary_json": str(result.json_path),
        "summary_markdown": str(result.markdown_path),
    }


def generate_crypto_pair_paper_report(run_path: Path | str) -> CryptoPairReportResult:
    """Load a completed paper run, compute rubric metrics, and write summary artifacts."""

    loaded = load_paper_run(run_path)
    report = build_paper_soak_summary(loaded)

    json_path = loaded.run_dir / PAPER_SOAK_SUMMARY_JSON
    markdown_path = loaded.run_dir / PAPER_SOAK_SUMMARY_MD

    json_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_paper_soak_summary_markdown(report) + "\n",
        encoding="utf-8",
    )

    return CryptoPairReportResult(
        report=report,
        json_path=json_path,
        markdown_path=markdown_path,
    )


def load_paper_run(run_path: Path | str) -> LoadedPaperRun:
    """Resolve *run_path* to a run directory and load its artifact bundle."""

    run_dir = _resolve_run_dir(Path(run_path))
    missing = [name for name in _REQUIRED_FILES if not (run_dir / name).exists()]
    if missing:
        raise CryptoPairReportError(
            "run directory is missing required artifact(s): "
            + ", ".join(sorted(missing))
        )

    manifest_path = run_dir / "run_manifest.json"
    summary_path = run_dir / "run_summary.json"
    runtime_events_path = run_dir / "runtime_events.jsonl"

    manifest = _read_json_dict(manifest_path)
    run_summary = _read_json_dict(summary_path)
    runtime_events = _read_jsonl(runtime_events_path)

    if not run_summary and isinstance(manifest.get("run_summary"), dict):
        run_summary = dict(manifest["run_summary"])

    if not run_summary:
        raise CryptoPairReportError("run_summary.json is empty or invalid")

    return LoadedPaperRun(
        run_dir=run_dir,
        manifest_path=manifest_path,
        summary_path=summary_path,
        runtime_events_path=runtime_events_path,
        manifest=manifest,
        run_summary=run_summary,
        runtime_events=runtime_events,
        observations=_read_jsonl(run_dir / "observations.jsonl"),
        intents=_read_jsonl(run_dir / "order_intents.jsonl"),
        fills=_read_jsonl(run_dir / "fills.jsonl"),
        exposures=_read_jsonl(run_dir / "exposures.jsonl"),
        settlements=_read_jsonl(run_dir / "settlements.jsonl"),
    )


def build_paper_soak_summary(
    loaded_run: LoadedPaperRun,
    *,
    generated_at: Optional[datetime] = None,
) -> dict[str, Any]:
    """Compute the paper-soak rubric summary for one loaded run."""

    manifest = loaded_run.manifest
    run_summary = loaded_run.run_summary
    runtime_events = loaded_run.runtime_events
    exposures = loaded_run.exposures
    fills = loaded_run.fills
    observations = loaded_run.observations

    generated_at_iso = _iso_utc(generated_at or _utc_now())
    run_id = str(
        manifest.get("run_id")
        or run_summary.get("run_id")
        or loaded_run.run_dir.name
    )

    market_to_symbol = _build_market_symbol_index(observations, loaded_run.intents)
    feed_summary = _summarize_feed_state(runtime_events)
    freeze_window_breaches = _find_freeze_window_breaches(
        runtime_events=runtime_events,
        market_to_symbol=market_to_symbol,
    )
    safety_violations = _detect_safety_violations(
        manifest=manifest,
        runtime_events=runtime_events,
        freeze_window_breaches=freeze_window_breaches,
    )
    safety_violation_count = sum(item["count"] for item in safety_violations)

    started_at = _parse_iso_datetime(manifest.get("started_at"))
    completed_at = _parse_iso_datetime(manifest.get("completed_at"))
    soak_duration_hours = _duration_hours(started_at, completed_at)

    opportunities_observed = _coerce_int(
        run_summary.get("opportunities_observed"),
        default=len(observations),
    )
    intents_generated = _coerce_int(
        run_summary.get("order_intents_generated"),
        default=len(loaded_run.intents),
    )
    paired_exposure_count = _coerce_int(
        run_summary.get("paired_exposure_count"),
        default=sum(
            1
            for exposure in exposures
            if _coerce_decimal(exposure.get("paired_size"), default=_ZERO) > _ZERO
        ),
    )
    partial_exposure_count = _coerce_int(
        run_summary.get("partial_exposure_count"),
        default=sum(
            1
            for exposure in exposures
            if _coerce_decimal(exposure.get("unpaired_size"), default=_ZERO) > _ZERO
        ),
    )
    settled_pair_count = _coerce_int(
        run_summary.get("settled_pair_count"),
        default=len(loaded_run.settlements),
    )
    net_pnl_usdc = _coerce_decimal(run_summary.get("net_pnl_usdc"), default=_ZERO)

    completed_exposures = [
        exposure
        for exposure in exposures
        if str(exposure.get("exposure_status", "")).strip().lower() == "paired"
    ]
    avg_completed_pair_cost = _mean_decimal(
        [
            _coerce_decimal(exposure.get("paired_cost_usdc"), default=_ZERO)
            for exposure in completed_exposures
        ]
    )
    est_profit_per_completed_pair = _mean_decimal(
        [
            _ONE
            - _coerce_decimal(exposure.get("paired_net_cash_outflow_usdc"), default=_ZERO)
            for exposure in completed_exposures
        ]
    )
    pair_completion_rate = _safe_div(
        Decimal(paired_exposure_count),
        Decimal(intents_generated),
    )
    maker_fill_rate_floor = _safe_div(
        Decimal(len(fills)),
        Decimal(2 * intents_generated),
    )
    partial_leg_incidence = _safe_div(
        Decimal(partial_exposure_count),
        Decimal(intents_generated),
    )

    evidence_floor_checks = {
        "minimum_soak_duration_24h": {
            "actual_hours": _decimal_to_float(soak_duration_hours),
            "required_hours": 24.0,
            "passed": soak_duration_hours is not None
            and soak_duration_hours >= Decimal("24"),
        },
        "order_intents_generated": {
            "actual": intents_generated,
            "required": 30,
            "passed": intents_generated >= 30,
        },
        "paired_exposure_count": {
            "actual": paired_exposure_count,
            "required": 20,
            "passed": paired_exposure_count >= 20,
        },
        "settled_pair_count": {
            "actual": settled_pair_count,
            "required": 20,
            "passed": settled_pair_count >= 20,
        },
    }
    evidence_floor_met = all(
        bool(check["passed"]) for check in evidence_floor_checks.values()
    )

    metric_bands = {
        "pair_completion_rate": _band_gte(
            value=pair_completion_rate,
            pass_floor=Decimal("0.90"),
            rerun_floor=Decimal("0.80"),
            rule_pass=">= 0.90",
            rule_rerun=">= 0.80 and < 0.90",
            rule_reject="< 0.80",
        ),
        "average_completed_pair_cost": _band_lte(
            value=avg_completed_pair_cost,
            pass_ceiling=Decimal("0.965"),
            rerun_ceiling=Decimal("0.970"),
            rule_pass="<= 0.965",
            rule_rerun="> 0.965 and <= 0.970",
            rule_reject="> 0.970",
        ),
        "estimated_profit_per_completed_pair": _band_gte(
            value=est_profit_per_completed_pair,
            pass_floor=Decimal("0.035"),
            rerun_floor=Decimal("0.030"),
            rule_pass=">= 0.035",
            rule_rerun=">= 0.030 and < 0.035",
            rule_reject="< 0.030",
        ),
        "maker_fill_rate_floor": _band_gte(
            value=maker_fill_rate_floor,
            pass_floor=Decimal("0.95"),
            rerun_floor=Decimal("0.90"),
            rule_pass=">= 0.95",
            rule_rerun=">= 0.90 and < 0.95",
            rule_reject="< 0.90",
        ),
        "partial_leg_incidence": _band_lte(
            value=partial_leg_incidence,
            pass_ceiling=Decimal("0.10"),
            rerun_ceiling=Decimal("0.20"),
            rule_pass="<= 0.10",
            rule_rerun="> 0.10 and <= 0.20",
            rule_reject="> 0.20",
        ),
        "feed_state_transitions": _evaluate_feed_state_band(
            stale_count=feed_summary["stale_count"],
            disconnect_count=feed_summary["disconnect_count"],
            latest_states=feed_summary["latest_states"],
            freeze_window_breach_count=len(freeze_window_breaches),
        ),
        "safety_violations": {
            "value": safety_violation_count,
            "band": _BAND_PASS if safety_violation_count == 0 else _BAND_REJECT,
            "rule": "0",
            "details": "0 passes; >= 1 rejects",
        },
        "net_pnl_positive": {
            "value": float(net_pnl_usdc),
            "band": _BAND_PASS if net_pnl_usdc > _ZERO else _BAND_RERUN,
            "rule": "net_pnl_usdc > 0",
            "details": "Positive net paper PnL is required for promote.",
        },
    }

    reject_reasons = []
    rerun_reasons = []

    if safety_violation_count > 0:
        reject_reasons.append(f"safety violation count is {safety_violation_count}")

    for metric_key in (
        "pair_completion_rate",
        "average_completed_pair_cost",
        "estimated_profit_per_completed_pair",
        "maker_fill_rate_floor",
        "partial_leg_incidence",
        "feed_state_transitions",
    ):
        band = metric_bands[metric_key]["band"]
        if band == _BAND_REJECT:
            reject_reasons.append(
                f"{metric_key.replace('_', ' ')} landed in the reject band"
            )
        elif band == _BAND_RERUN:
            rerun_reasons.append(
                f"{metric_key.replace('_', ' ')} landed in the rerun band"
            )
        elif band == _BAND_INSUFFICIENT:
            rerun_reasons.append(
                f"{metric_key.replace('_', ' ')} is unavailable from the artifact bundle"
            )

    if not evidence_floor_met:
        failed_checks = [
            check_name
            for check_name, check in evidence_floor_checks.items()
            if not bool(check["passed"])
        ]
        rerun_reasons.append(
            "evidence floor not met: " + ", ".join(failed_checks)
        )

    if metric_bands["net_pnl_positive"]["band"] != _BAND_PASS:
        rerun_reasons.append("net_pnl_usdc is not positive")

    if reject_reasons:
        decision = "reject"
        verdict = _REJECT_VERDICT
        decision_reasons = _unique_preserving_order(reject_reasons)
    elif rerun_reasons:
        decision = "rerun"
        verdict = _RERUN_VERDICT
        decision_reasons = _unique_preserving_order(rerun_reasons)
    else:
        decision = "promote"
        verdict = _PROMOTE_VERDICT
        decision_reasons = ["all rubric gates passed"]

    notes = []
    if not loaded_run.settlements:
        notes.append(
            "settlements.jsonl is empty or absent; settled_pair_count comes from run_summary.json if present."
        )
    if not loaded_run.exposures:
        notes.append(
            "exposures.jsonl is empty or absent; completed-pair cost and profit metrics may be unavailable."
        )
    sink_result = manifest.get("sink_write_result")
    if isinstance(sink_result, dict) and not bool(sink_result.get("enabled")):
        notes.append(
            "ClickHouse sink was disabled for this run; report uses local artifacts only."
        )

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": generated_at_iso,
        "run_id": run_id,
        "run_dir": str(loaded_run.run_dir),
        "source_artifacts": {
            "run_manifest": str(loaded_run.manifest_path),
            "run_summary": str(loaded_run.summary_path),
            "runtime_events": str(loaded_run.runtime_events_path),
        },
        "metrics": {
            "soak_duration_hours": _decimal_to_float(soak_duration_hours),
            "opportunities_observed": opportunities_observed,
            "intents_generated": intents_generated,
            "completed_pairs": paired_exposure_count,
            "paired_exposure_count": paired_exposure_count,
            "settled_pair_count": settled_pair_count,
            "pair_completion_rate": _decimal_to_float(pair_completion_rate),
            "average_completed_pair_cost": _decimal_to_float(avg_completed_pair_cost),
            "estimated_profit_per_completed_pair": _decimal_to_float(
                est_profit_per_completed_pair
            ),
            "maker_fill_rate_floor": _decimal_to_float(maker_fill_rate_floor),
            "partial_leg_incidence": _decimal_to_float(partial_leg_incidence),
            "stale_count": feed_summary["stale_count"],
            "disconnect_count": feed_summary["disconnect_count"],
            "net_pnl_usdc": float(net_pnl_usdc),
            "safety_violation_count": safety_violation_count,
        },
        "evidence_floor": {
            "met": evidence_floor_met,
            "checks": evidence_floor_checks,
        },
        "rubric": {
            "decision": decision,
            "verdict": verdict,
            "rubric_pass": decision == "promote",
            "decision_reasons": decision_reasons,
            "metric_bands": metric_bands,
        },
        "feed_state": {
            "latest_states": dict(feed_summary["latest_states"]),
            "freeze_window_breach_count": len(freeze_window_breaches),
            "freeze_window_breaches": freeze_window_breaches,
        },
        "safety_violations": safety_violations,
        "notes": notes,
    }


def render_paper_soak_summary_markdown(report: Mapping[str, Any]) -> str:
    """Render a compact operator-facing Markdown summary."""

    metrics = report.get("metrics", {})
    rubric = report.get("rubric", {})
    evidence_floor = report.get("evidence_floor", {})
    metric_bands = rubric.get("metric_bands", {})
    safety_violations = report.get("safety_violations", [])
    notes = report.get("notes", [])

    lines = [
        "# Crypto Pair Paper Soak Summary",
        "",
        f"**Run ID:** {report.get('run_id', 'unknown')}  ",
        f"**Verdict:** {rubric.get('verdict', 'unknown')}  ",
        f"**Rubric Pass:** {'yes' if rubric.get('rubric_pass') else 'no'}  ",
        f"**Generated At:** {report.get('generated_at', 'unknown')}  ",
        f"**Run Dir:** {report.get('run_dir', 'unknown')}  ",
        "",
        "## Key Metrics",
        "",
        "| Metric | Value |",
        "| ------ | ----- |",
        f"| soak_duration_hours | {_fmt_metric(metrics.get('soak_duration_hours'), places=2)} |",
        f"| opportunities_observed | {_fmt_metric(metrics.get('opportunities_observed'))} |",
        f"| intents_generated | {_fmt_metric(metrics.get('intents_generated'))} |",
        f"| completed_pairs | {_fmt_metric(metrics.get('completed_pairs'))} |",
        f"| settled_pair_count | {_fmt_metric(metrics.get('settled_pair_count'))} |",
        f"| pair_completion_rate | {_fmt_metric(metrics.get('pair_completion_rate'), places=4)} |",
        f"| avg_completed_pair_cost | {_fmt_metric(metrics.get('average_completed_pair_cost'), places=4)} |",
        f"| est_profit_per_completed_pair | {_fmt_metric(metrics.get('estimated_profit_per_completed_pair'), places=4)} |",
        f"| maker_fill_rate_floor | {_fmt_metric(metrics.get('maker_fill_rate_floor'), places=4)} |",
        f"| partial_leg_incidence | {_fmt_metric(metrics.get('partial_leg_incidence'), places=4)} |",
        f"| stale_count | {_fmt_metric(metrics.get('stale_count'))} |",
        f"| disconnect_count | {_fmt_metric(metrics.get('disconnect_count'))} |",
        f"| safety_violation_count | {_fmt_metric(metrics.get('safety_violation_count'))} |",
        "",
        "## Evidence Floor",
        "",
        "| Check | Actual | Required | Result |",
        "| ----- | ------ | -------- | ------ |",
    ]

    for check_name, payload in evidence_floor.get("checks", {}).items():
        if "actual_hours" in payload:
            actual = _fmt_metric(payload.get("actual_hours"), places=2)
            required = _fmt_metric(payload.get("required_hours"), places=2)
        else:
            actual = _fmt_metric(payload.get("actual"))
            required = _fmt_metric(payload.get("required"))
        lines.append(
            f"| {check_name} | {actual} | {required} | {'pass' if payload.get('passed') else 'fail'} |"
        )

    lines.extend(
        [
            "",
            "## Rubric Bands",
            "",
            "| Metric | Value | Band | Rule |",
            "| ------ | ----- | ---- | ---- |",
        ]
    )

    rubric_rows = (
        ("pair_completion_rate", metrics.get("pair_completion_rate")),
        ("average_completed_pair_cost", metrics.get("average_completed_pair_cost")),
        (
            "estimated_profit_per_completed_pair",
            metrics.get("estimated_profit_per_completed_pair"),
        ),
        ("maker_fill_rate_floor", metrics.get("maker_fill_rate_floor")),
        ("partial_leg_incidence", metrics.get("partial_leg_incidence")),
        (
            "feed_state_transitions",
            _feed_band_value(report.get("feed_state", {}), metrics),
        ),
        ("safety_violations", metrics.get("safety_violation_count")),
        ("net_pnl_positive", metrics.get("net_pnl_usdc")),
    )

    for metric_name, metric_value in rubric_rows:
        payload = metric_bands.get(metric_name, {})
        lines.append(
            f"| {metric_name} | {_fmt_metric(metric_value, places=4)} | "
            f"{payload.get('band', 'unknown')} | {payload.get('rule', '')} |"
        )

    lines.extend(["", "## Decision", ""])
    for reason in rubric.get("decision_reasons", []):
        lines.append(f"- {reason}")

    lines.extend(["", "## Safety Violations", ""])

    if safety_violations:
        for violation in safety_violations:
            detail_suffix = ""
            details = violation.get("details") or []
            if details:
                detail_suffix = f": {details[0]}"
            lines.append(
                f"- {violation.get('code', 'unknown')} x{violation.get('count', 0)}{detail_suffix}"
            )
    else:
        lines.append("- none")

    if notes:
        lines.extend(["", "## Notes", ""])
        for note in notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def _resolve_run_dir(path: Path) -> Path:
    if not path.exists():
        raise CryptoPairReportError(f"run path not found: {path}")
    if path.is_dir():
        return path
    if path.name in {"run_manifest.json", "run_summary.json"}:
        return path.parent
    raise CryptoPairReportError(
        "run path must be a run directory or one of: run_manifest.json, run_summary.json"
    )


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CryptoPairReportError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CryptoPairReportError(f"expected JSON object in {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise CryptoPairReportError(
                f"invalid JSONL in {path} on line {line_no}: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise CryptoPairReportError(
                f"expected JSON object in {path} on line {line_no}"
            )
        rows.append(payload)
    return rows


def _build_market_symbol_index(
    observations: list[dict[str, Any]],
    intents: list[dict[str, Any]],
) -> dict[str, str]:
    market_to_symbol: dict[str, str] = {}
    for row in observations + intents:
        market_id = str(row.get("market_id", "")).strip()
        symbol = str(row.get("symbol", "")).strip().upper()
        if market_id and symbol:
            market_to_symbol[market_id] = symbol
    return market_to_symbol


def _summarize_feed_state(runtime_events: list[dict[str, Any]]) -> dict[str, Any]:
    stale_count = 0
    disconnect_count = 0
    latest_states: dict[str, str] = {}

    for event in runtime_events:
        if str(event.get("event_type", "")).strip() != "feed_state_changed":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        symbol = str(payload.get("symbol", "")).strip().upper()
        to_state = str(payload.get("to_state", "")).strip()
        if to_state == "stale":
            stale_count += 1
        elif to_state == "disconnected":
            disconnect_count += 1
        if symbol and to_state:
            latest_states[symbol] = to_state

    return {
        "stale_count": stale_count,
        "disconnect_count": disconnect_count,
        "latest_states": latest_states,
    }


def _find_freeze_window_breaches(
    *,
    runtime_events: list[dict[str, Any]],
    market_to_symbol: Mapping[str, str],
) -> list[dict[str, Any]]:
    frozen_symbols: dict[str, str] = {}
    breaches: list[dict[str, Any]] = []

    for event in runtime_events:
        event_type = str(event.get("event_type", "")).strip()
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        if event_type == "feed_state_changed":
            symbol = str(payload.get("symbol", "")).strip().upper()
            to_state = str(payload.get("to_state", "")).strip()
            recorded_at = str(event.get("recorded_at", "")).strip()
            if not symbol:
                continue
            if to_state in {"stale", "disconnected"}:
                frozen_symbols[symbol] = recorded_at
            elif to_state == "connected_fresh":
                frozen_symbols.pop(symbol, None)
            continue

        if event_type != "order_intent_created":
            continue

        market_id = str(payload.get("market_id", "")).strip()
        symbol = str(market_to_symbol.get(market_id, "")).strip().upper()
        if symbol and symbol in frozen_symbols:
            breaches.append(
                {
                    "market_id": market_id,
                    "symbol": symbol,
                    "recorded_at": str(event.get("recorded_at", "")).strip(),
                    "frozen_since": frozen_symbols[symbol],
                }
            )

    return breaches


def _detect_safety_violations(
    *,
    manifest: Mapping[str, Any],
    runtime_events: list[dict[str, Any]],
    freeze_window_breaches: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    stopped_reason = str(manifest.get("stopped_reason", "")).strip()
    if not is_graceful_paper_stop_reason(stopped_reason):
        violations.append(
            {
                "code": "stopped_reason_not_completed",
                "count": 1,
                "details": [f"stopped_reason={stopped_reason or 'missing'}"],
            }
        )

    if bool(manifest.get("has_open_unpaired_exposure_final")):
        violations.append(
            {
                "code": "open_unpaired_exposure_final",
                "count": 1,
                "details": ["has_open_unpaired_exposure_final=true"],
            }
        )

    kill_switch_events = [
        event
        for event in runtime_events
        if str(event.get("event_type", "")).strip() == "kill_switch_tripped"
    ]
    if kill_switch_events:
        violations.append(
            {
                "code": "kill_switch_tripped",
                "count": len(kill_switch_events),
                "details": [
                    str(kill_switch_events[0].get("recorded_at", "")).strip()
                    or "runtime event present"
                ],
            }
        )

    daily_loss_cap_blocks = [
        event
        for event in runtime_events
        if str(event.get("event_type", "")).strip() == "order_intent_blocked"
        and isinstance(event.get("payload"), dict)
        and str(event["payload"].get("block_reason", "")).strip()
        == "daily_loss_cap_reached"
    ]
    if daily_loss_cap_blocks:
        violations.append(
            {
                "code": "daily_loss_cap_reached",
                "count": len(daily_loss_cap_blocks),
                "details": [
                    "order_intent_blocked with block_reason=daily_loss_cap_reached"
                ],
            }
        )

    sink_write_result = manifest.get("sink_write_result")
    if isinstance(sink_write_result, dict) and bool(sink_write_result.get("enabled")):
        sink_error = str(sink_write_result.get("error", "")).strip()
        skipped_reason = str(sink_write_result.get("skipped_reason", "")).strip()
        if sink_error or skipped_reason == "write_failed":
            violations.append(
                {
                    "code": "sink_write_failed",
                    "count": 1,
                    "details": [
                        sink_error or f"skipped_reason={skipped_reason or 'missing'}"
                    ],
                }
            )

    if freeze_window_breaches:
        first_breach = freeze_window_breaches[0]
        violations.append(
            {
                "code": "intent_created_during_frozen_feed_window",
                "count": len(freeze_window_breaches),
                "details": [
                    "symbol="
                    f"{first_breach.get('symbol', 'unknown')} "
                    f"market_id={first_breach.get('market_id', 'unknown')} "
                    f"recorded_at={first_breach.get('recorded_at', 'unknown')}"
                ],
            }
        )

    return violations


def _evaluate_feed_state_band(
    *,
    stale_count: int,
    disconnect_count: int,
    latest_states: Mapping[str, str],
    freeze_window_breach_count: int,
) -> dict[str, Any]:
    unrecovered_symbols = sorted(
        symbol
        for symbol, state in latest_states.items()
        if state and state != "connected_fresh"
    )

    if (
        disconnect_count > 1
        or stale_count > 5
        or freeze_window_breach_count > 0
        or unrecovered_symbols
    ):
        band = _BAND_REJECT
    elif disconnect_count == 1 or 3 <= stale_count <= 5:
        band = _BAND_RERUN
    else:
        band = _BAND_PASS

    return {
        "value": {
            "stale_count": stale_count,
            "disconnect_count": disconnect_count,
            "latest_states": dict(latest_states),
            "unrecovered_symbols": unrecovered_symbols,
        },
        "band": band,
        "rule": (
            "pass: disconnect_count = 0, stale_count <= 2, and all degraded symbols recover "
            "to connected_fresh; rerun: disconnect_count = 1 or stale_count in [3,5] with "
            "clean recovery; reject: disconnect_count > 1, stale_count > 5, unrecovered "
            "degraded state, or freeze-window audit failure"
        ),
        "details": (
            "freeze-window breaches="
            f"{freeze_window_breach_count}, unrecovered_symbols={unrecovered_symbols}"
        ),
    }


def _band_gte(
    *,
    value: Optional[Decimal],
    pass_floor: Decimal,
    rerun_floor: Decimal,
    rule_pass: str,
    rule_rerun: str,
    rule_reject: str,
) -> dict[str, Any]:
    if value is None:
        band = _BAND_INSUFFICIENT
    elif value >= pass_floor:
        band = _BAND_PASS
    elif value >= rerun_floor:
        band = _BAND_RERUN
    else:
        band = _BAND_REJECT
    return {
        "value": _decimal_to_float(value),
        "band": band,
        "rule": f"pass: {rule_pass}; rerun: {rule_rerun}; reject: {rule_reject}",
    }


def _band_lte(
    *,
    value: Optional[Decimal],
    pass_ceiling: Decimal,
    rerun_ceiling: Decimal,
    rule_pass: str,
    rule_rerun: str,
    rule_reject: str,
) -> dict[str, Any]:
    if value is None:
        band = _BAND_INSUFFICIENT
    elif value <= pass_ceiling:
        band = _BAND_PASS
    elif value <= rerun_ceiling:
        band = _BAND_RERUN
    else:
        band = _BAND_REJECT
    return {
        "value": _decimal_to_float(value),
        "band": band,
        "rule": f"pass: {rule_pass}; rerun: {rule_rerun}; reject: {rule_reject}",
    }


def _mean_decimal(values: list[Decimal]) -> Optional[Decimal]:
    if not values:
        return None
    return sum(values, start=_ZERO) / Decimal(len(values))


def _safe_div(numerator: Decimal, denominator: Decimal) -> Optional[Decimal]:
    if denominator <= _ZERO:
        return None
    return numerator / denominator


def _coerce_decimal(value: Any, *, default: Optional[Decimal] = None) -> Decimal:
    if value is None:
        if default is None:
            raise CryptoPairReportError("expected decimal-compatible value, got None")
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        if default is not None:
            return default
        raise CryptoPairReportError(
            f"expected decimal-compatible value, got {value!r}"
        ) from exc


def _coerce_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _duration_hours(
    started_at: Optional[datetime],
    completed_at: Optional[datetime],
) -> Optional[Decimal]:
    if started_at is None or completed_at is None:
        return None
    elapsed_seconds = Decimal(str((completed_at - started_at).total_seconds()))
    if elapsed_seconds < _ZERO:
        return None
    return elapsed_seconds / Decimal("3600")


def _decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _fmt_metric(value: Any, *, places: int = 0) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        format_spec = f".{places}f" if places > 0 else ".0f"
        return format(value, format_spec)
    return str(value)


def _feed_band_value(feed_state: Mapping[str, Any], metrics: Mapping[str, Any]) -> str:
    latest_states = feed_state.get("latest_states") or {}
    if isinstance(latest_states, dict) and latest_states:
        latest_state_text = ", ".join(
            f"{symbol}={state}" for symbol, state in sorted(latest_states.items())
        )
    else:
        latest_state_text = "none"
    return (
        f"stale={metrics.get('stale_count', 0)}, "
        f"disconnect={metrics.get('disconnect_count', 0)}, "
        f"latest={latest_state_text}"
    )


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
