"""Local HTML report generation for SimTrader run/sweep/batch artifacts."""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class SimTraderReportError(ValueError):
    """Raised when report generation cannot proceed."""


@dataclass(frozen=True)
class SimTraderReportResult:
    """Outcome of one generated report."""

    artifact_type: str
    artifact_id: str
    report_path: Path


@dataclass(frozen=True)
class _ReportView:
    artifact_type: str
    artifact_id: str
    header_rows: list[tuple[str, str]]
    metric_rows: list[tuple[str, str]]
    dominant_rejections: list[tuple[str, int]]
    sections_html: list[str]


def generate_report(artifact_dir: Path) -> SimTraderReportResult:
    """Generate ``report.html`` inside *artifact_dir* and return metadata."""
    if not artifact_dir.exists():
        raise SimTraderReportError(f"artifact directory not found: {artifact_dir}")
    if not artifact_dir.is_dir():
        raise SimTraderReportError(f"artifact path is not a directory: {artifact_dir}")

    artifact_type = _detect_artifact_type(artifact_dir)
    if artifact_type == "sweep":
        view = _build_sweep_view(artifact_dir)
    elif artifact_type == "batch":
        view = _build_batch_view(artifact_dir)
    elif artifact_type == "run":
        view = _build_run_view(artifact_dir)
    else:
        raise SimTraderReportError(f"unsupported artifact type: {artifact_type}")

    report_path = artifact_dir / "report.html"
    report_html = _render_page(view)
    report_path.write_text(report_html, encoding="utf-8")

    return SimTraderReportResult(
        artifact_type=view.artifact_type,
        artifact_id=view.artifact_id,
        report_path=report_path,
    )


def _detect_artifact_type(artifact_dir: Path) -> str:
    if (artifact_dir / "sweep_summary.json").exists():
        return "sweep"
    if (artifact_dir / "batch_summary.json").exists():
        return "batch"
    if (artifact_dir / "run_manifest.json").exists():
        return "run"
    raise SimTraderReportError(
        "could not detect artifact type; expected one of: "
        "sweep_summary.json, batch_summary.json, run_manifest.json"
    )


def _load_header_rows(artifact_dir: Path) -> list[tuple[str, str]]:
    """Centralized header metadata loader by artifact type.

    Returns a list of (key, value) pairs to render in the header block.
    The returned set varies by artifact type and includes sensible fallbacks
    like "unknown" when data is missing.
    """
    artifact_type = _detect_artifact_type(artifact_dir)

    # Small helper to ensure a string value with a default
    def _sv(v: object, default: str = "unknown") -> str:
        if isinstance(v, str) and v.strip():
            return v.strip()
        return default

    if artifact_type == "run":
        manifest = _read_json_dict(artifact_dir / "run_manifest.json")

        artifact_id = _sv(manifest.get("run_id"), default=artifact_dir.name)
        quickrun_context = (
            manifest.get("quickrun_context")
            if isinstance(manifest.get("quickrun_context"), dict)
            else {}
        )
        shadow_context = (
            manifest.get("shadow_context")
            if isinstance(manifest.get("shadow_context"), dict)
            else {}
        )
        market_slug = (
            _sv(quickrun_context.get("selected_slug"), default="")
            or _sv(shadow_context.get("selected_slug"), default="")
            or _market_slug_from_tape_meta(manifest)
        )
        if not market_slug:
            market_slug = "- (missing tape linkage)"

        started_at = manifest.get("started_at")
        created_at = started_at if isinstance(started_at, str) and started_at else _sv(manifest.get("created_at"))
        if created_at == "unknown":
            created_at = "unknown"

        portfolio = manifest.get("portfolio_config") if isinstance(manifest.get("portfolio_config"), dict) else {}
        fee_rate_bps = _sv(portfolio.get("fee_rate_bps"), default="-")
        latency = manifest.get("latency_config") if isinstance(manifest.get("latency_config"), dict) else {}
        cancel_latency_ticks = _sv(latency.get("cancel_ticks"), default="-")
        mark_method = _sv(portfolio.get("mark_method"), default="-")

        strategy_value = _sv(manifest.get("strategy"), default="unknown")
        exit_reason_value = _sv(manifest.get("exit_reason"), default="unknown")
        run_metrics = manifest.get("run_metrics") if isinstance(manifest.get("run_metrics"), dict) else None
        run_metrics_value = json.dumps(run_metrics) if isinstance(run_metrics, dict) else "unknown"

        return [
            ("artifact_id", artifact_id),
            ("market_slug", market_slug),
            ("created_at", created_at),
            ("fee_rate_bps", fee_rate_bps),
            ("cancel_latency_ticks", cancel_latency_ticks),
            ("mark_method", mark_method),
            ("strategy", strategy_value),
            ("exit_reason", exit_reason_value),
            ("run_metrics", run_metrics_value),
        ]

    if artifact_type == "sweep":
        sweep_manifest = _read_json_dict(artifact_dir / "sweep_manifest.json")
        sweep_summary = _read_json_dict(artifact_dir / "sweep_summary.json")

        artifact_id = _as_text(
            sweep_summary.get("sweep_id", sweep_manifest.get("sweep_id", artifact_dir.name)),
            default=artifact_dir.name,
        )
        quickrun_context = (
            sweep_manifest.get("quickrun_context")
            if isinstance(sweep_manifest.get("quickrun_context"), dict)
            else {}
        )
        market_slug = _sv(quickrun_context.get("selected_slug"), default="-")
        created_at = _sv(quickrun_context.get("selected_at"), default="-")
        if created_at == "-":
            created_at = _extract_timestamp_from_text(artifact_id) or "-"
        scenarios = (
            sweep_manifest.get("scenarios")
            if isinstance(sweep_manifest.get("scenarios"), list)
            else []
        )
        scenario_count = str(len(scenarios))

        return [
            ("artifact_id", artifact_id),
            ("market_slug", market_slug or "-"),
            ("created_at", created_at),
            ("scenario_count", scenario_count),
        ]

    if artifact_type == "batch":
        batch_manifest = _read_json_dict(artifact_dir / "batch_manifest.json")
        batch_summary = _read_json_dict(artifact_dir / "batch_summary.json")

        artifact_id = _as_text(
            batch_summary.get("batch_id", batch_manifest.get("batch_id", artifact_dir.name)),
            default=artifact_dir.name,
        )
        created_at = _as_text(
            batch_manifest.get("created_at", batch_summary.get("created_at")), default="-"
        )

        markets = (
            batch_summary.get("markets")
            if isinstance(batch_summary.get("markets"), list)
            else []
        )
        market_slug = f"multiple ({len(markets)})"  if isinstance(markets, list) else "-"
        markets_count = len(markets) if isinstance(markets, list) else 0

        return [
            ("artifact_id", artifact_id),
            ("market_slug", market_slug),
            ("created_at", created_at),
            ("markets_count", str(markets_count)),
            ("fee_rate_bps", _as_text(batch_manifest.get("fee_rate_bps"), default="scenario-specific")),
            ("cancel_latency_ticks", "scenario-specific"),
            ("mark_method", _as_text(batch_manifest.get("mark_method"), default="scenario-specific")),
        ]

    # Fallback
    return [("artifact_id", artifact_dir.name)]


def _build_run_view(artifact_dir: Path) -> _ReportView:
    run_manifest = _read_json_dict(artifact_dir / "run_manifest.json")
    summary = _read_json_dict(artifact_dir / "summary.json")

    artifact_id = str(run_manifest.get("run_id") or artifact_dir.name)
    created_at = _as_text(run_manifest.get("created_at"), default="unknown")

    quickrun_context = (
        run_manifest.get("quickrun_context")
        if isinstance(run_manifest.get("quickrun_context"), dict)
        else {}
    )
    shadow_context = (
        run_manifest.get("shadow_context")
        if isinstance(run_manifest.get("shadow_context"), dict)
        else {}
    )
    market_slug = (
        _as_text(quickrun_context.get("selected_slug"), default="")
        or _as_text(shadow_context.get("selected_slug"), default="")
        or _market_slug_from_tape_meta(run_manifest)
    )
    if not market_slug:
        market_slug = "- (missing tape linkage)"

    portfolio = (
        run_manifest.get("portfolio_config")
        if isinstance(run_manifest.get("portfolio_config"), dict)
        else {}
    )
    latency = (
        run_manifest.get("latency_config")
        if isinstance(run_manifest.get("latency_config"), dict)
        else {}
    )

    fee_rate_bps = _as_text(portfolio.get("fee_rate_bps"), default="-")
    cancel_latency_ticks = _as_text(latency.get("cancel_ticks"), default="-")
    mark_method = _as_text(portfolio.get("mark_method"), default="-")

    orders = _count_non_empty_lines(artifact_dir / "orders.jsonl")
    fills = _coerce_int(run_manifest.get("fills_count"))
    if fills <= 0:
        fills = _count_non_empty_lines(artifact_dir / "fills.jsonl")

    metric_rows = [
        ("net_profit", _as_text(summary.get("net_profit", run_manifest.get("net_profit")), default="-")),
        ("decisions", str(_coerce_int(run_manifest.get("decisions_count")))),
        ("orders", str(orders)),
        ("fills", str(fills)),
        ("scenarios_with_trades", "1" if fills > 0 else "0"),
    ]

    rejection_counts = _extract_rejection_counts(run_manifest)
    dominant_rejections = _sorted_count_items(rejection_counts)

    summary_rows: list[tuple[str, str]] = []
    if summary:
        for key in (
            "starting_cash",
            "final_cash",
            "final_equity",
            "realized_pnl",
            "unrealized_pnl",
            "total_fees",
            "net_profit",
        ):
            summary_rows.append((key, _as_text(summary.get(key), default="-")))

    files = sorted(
        [p.name for p in artifact_dir.iterdir() if p.is_file()],
        key=lambda name: name.lower(),
    )
    files_rows = "".join(
        f'<tr><td><a href="./{html.escape(name)}">{html.escape(name)}</a></td></tr>'
        for name in files
    )
    files_table = (
        '<section><h2>Artifact Files</h2>'
        '<table><thead><tr><th>file</th></tr></thead>'
        f"<tbody>{files_rows}</tbody></table></section>"
    )

    sections: list[str] = []
    if summary_rows:
        sections.append(
            "<section><h2>Run Summary</h2>"
            f"{_render_key_value_table(summary_rows)}"
            "</section>"
        )
    sections.append(files_table)

    return _ReportView(
        artifact_type="run",
        artifact_id=artifact_id,
        header_rows=_load_header_rows(artifact_dir),
        metric_rows=metric_rows,
        dominant_rejections=dominant_rejections,
        sections_html=sections,
    )


def _build_sweep_view(artifact_dir: Path) -> _ReportView:
    sweep_summary = _read_json_dict(artifact_dir / "sweep_summary.json")
    sweep_manifest = _read_json_dict(artifact_dir / "sweep_manifest.json")

    artifact_id = _as_text(
        sweep_summary.get("sweep_id", sweep_manifest.get("sweep_id", artifact_dir.name)),
        default=artifact_dir.name,
    )
    quickrun_context = (
        sweep_manifest.get("quickrun_context")
        if isinstance(sweep_manifest.get("quickrun_context"), dict)
        else {}
    )
    market_slug = _as_text(quickrun_context.get("selected_slug"), default="-")

    created_at = _as_text(quickrun_context.get("selected_at"), default="-")
    if created_at == "-":
        created_at = _extract_timestamp_from_text(artifact_id) or "-"

    base_config = (
        sweep_manifest.get("base_config")
        if isinstance(sweep_manifest.get("base_config"), dict)
        else {}
    )
    scenarios = (
        sweep_manifest.get("scenarios")
        if isinstance(sweep_manifest.get("scenarios"), list)
        else []
    )

    fee_values: set[str] = set()
    cancel_values: set[str] = set()
    mark_values: set[str] = set()

    if "fee_rate_bps" in base_config and base_config.get("fee_rate_bps") is not None:
        fee_values.add(str(base_config.get("fee_rate_bps")))
    if "latency_cancel_ticks" in base_config and base_config.get("latency_cancel_ticks") is not None:
        cancel_values.add(str(base_config.get("latency_cancel_ticks")))
    if "mark_method" in base_config and base_config.get("mark_method") is not None:
        mark_values.add(str(base_config.get("mark_method")))

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        overrides = scenario.get("overrides")
        if not isinstance(overrides, dict):
            continue
        if "fee_rate_bps" in overrides and overrides.get("fee_rate_bps") is not None:
            fee_values.add(str(overrides.get("fee_rate_bps")))
        if (
            "cancel_latency_ticks" in overrides
            and overrides.get("cancel_latency_ticks") is not None
        ):
            cancel_values.add(str(overrides.get("cancel_latency_ticks")))
        if "mark_method" in overrides and overrides.get("mark_method") is not None:
            mark_values.add(str(overrides.get("mark_method")))

    aggregate = (
        sweep_summary.get("aggregate")
        if isinstance(sweep_summary.get("aggregate"), dict)
        else {}
    )
    metric_rows = [
        ("net_profit", _as_text(aggregate.get("best_net_profit"), default="-")),
        ("decisions", str(_coerce_int(aggregate.get("total_decisions")))),
        ("orders", str(_coerce_int(aggregate.get("total_orders")))),
        ("fills", str(_coerce_int(aggregate.get("total_fills")))),
        (
            "scenarios_with_trades",
            str(_coerce_int(aggregate.get("scenarios_with_trades"))),
        ),
    ]

    dominant_rejections = _dominant_rejections_from_summary(aggregate)

    scenario_rows: list[list[str]] = []
    summary_scenarios = (
        sweep_summary.get("scenarios")
        if isinstance(sweep_summary.get("scenarios"), list)
        else []
    )
    for row in summary_scenarios:
        if not isinstance(row, dict):
            continue
        scenario_id = _as_text(row.get("scenario_id"), default="-")
        run_dir = _resolve_scenario_run_dir(artifact_dir, row, scenario_id)
        run_manifest = _read_json_dict(run_dir / "run_manifest.json")

        orders = _count_non_empty_lines(run_dir / "orders.jsonl")
        fills = _coerce_int(run_manifest.get("fills_count"))
        if fills <= 0:
            fills = _count_non_empty_lines(run_dir / "fills.jsonl")

        scenario_rejections = _extract_rejection_counts(run_manifest)
        top_key, top_count = _dominant_count_entry(scenario_rejections)
        if top_key:
            top_rejection = f"{top_key} ({top_count})"
        else:
            top_rejection = "-"

        scenario_rows.append(
            [
                scenario_id,
                _as_text(row.get("net_profit"), default="-"),
                str(orders),
                str(fills),
                top_rejection,
            ]
        )

    scenario_table = (
        "<section><h2>Scenarios</h2>"
        f"{_render_sortable_table(['scenario_id', 'net_profit', 'orders', 'fills', 'top_rejection_reason'], scenario_rows)}"
        "</section>"
    )

    return _ReportView(
        artifact_type="sweep",
        artifact_id=artifact_id,
        header_rows=_load_header_rows(artifact_dir),
        metric_rows=metric_rows,
        dominant_rejections=dominant_rejections,
        sections_html=[scenario_table],
    )


def _build_batch_view(artifact_dir: Path) -> _ReportView:
    batch_summary = _read_json_dict(artifact_dir / "batch_summary.json")
    batch_manifest = _read_json_dict(artifact_dir / "batch_manifest.json")

    artifact_id = _as_text(
        batch_summary.get("batch_id", batch_manifest.get("batch_id", artifact_dir.name)),
        default=artifact_dir.name,
    )
    created_at = _as_text(
        batch_manifest.get("created_at", batch_summary.get("created_at")),
        default="-",
    )

    markets = (
        batch_summary.get("markets")
        if isinstance(batch_summary.get("markets"), list)
        else []
    )
    market_slug = f"multiple ({len(markets)})"

    aggregate = (
        batch_summary.get("aggregate")
        if isinstance(batch_summary.get("aggregate"), dict)
        else {}
    )

    market_rows: list[list[str]] = []
    total_scenarios_with_trades = 0
    rejection_totals: Counter[str] = Counter()

    for row in markets:
        if not isinstance(row, dict):
            continue
        slug = _as_text(row.get("slug"), default="-")
        market_dir = artifact_dir / "markets" / slug
        scenarios_with_trades = _count_market_scenarios_with_trades(market_dir)
        if scenarios_with_trades == 0 and _coerce_int(row.get("total_fills")) > 0:
            scenarios_with_trades = 1
        total_scenarios_with_trades += scenarios_with_trades

        dominant_key = _as_text(row.get("dominant_rejection_key"), default="")
        dominant_count = _coerce_int(row.get("dominant_rejection_count"))
        if dominant_key and dominant_count > 0:
            rejection_totals[dominant_key] += dominant_count
            dominant_value = f"{dominant_key} ({dominant_count})"
        else:
            dominant_value = "-"

        market_rows.append(
            [
                slug,
                str(scenarios_with_trades),
                _as_text(row.get("median_net_profit"), default="-"),
                dominant_value,
            ]
        )

    metric_rows = [
        ("net_profit", _as_text(aggregate.get("best_net_profit"), default="-")),
        ("decisions", str(_coerce_int(aggregate.get("total_decisions")))),
        ("orders", str(_coerce_int(aggregate.get("total_orders")))),
        ("fills", str(_coerce_int(aggregate.get("total_fills")))),
        ("scenarios_with_trades", str(total_scenarios_with_trades)),
    ]

    dominant_rejections = sorted(
        rejection_totals.items(),
        key=lambda item: (-item[1], item[0]),
    )

    markets_table = (
        "<section><h2>Markets</h2>"
        f"{_render_sortable_table(['slug', 'scenarios_with_trades', 'median_net_profit', 'dominant_rejection'], market_rows)}"
        "</section>"
    )

    return _ReportView(
        artifact_type="batch",
        artifact_id=artifact_id,
        header_rows=_load_header_rows(artifact_dir),
        metric_rows=metric_rows,
        dominant_rejections=dominant_rejections,
        sections_html=[markets_table],
    )


def _render_page(view: _ReportView) -> str:
    title = f"SimTrader {view.artifact_type} report: {view.artifact_id}"
    generated_at = datetime.now(timezone.utc).isoformat()

    style = """
body {
  margin: 0;
  padding: 0;
  background: #f4f5f8;
  color: #1f2430;
  font-family: "Segoe UI", Tahoma, Arial, sans-serif;
}
main {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px;
}
h1 {
  margin: 0 0 6px 0;
  font-size: 1.8rem;
}
h2 {
  margin: 0 0 12px 0;
  font-size: 1.15rem;
}
section {
  background: #ffffff;
  border: 1px solid #d6dbe6;
  border-radius: 10px;
  padding: 14px 16px;
  margin: 14px 0;
}
.muted {
  margin: 0 0 16px 0;
  color: #5a6475;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  border-bottom: 1px solid #e8ebf2;
  text-align: left;
  padding: 8px 10px;
  vertical-align: top;
}
thead th {
  background: #f7f8fb;
  font-weight: 600;
}
table.sortable thead th {
  cursor: pointer;
}
table.sortable thead th[data-sort-dir="asc"]::after {
  content: "  ^";
  color: #586787;
}
table.sortable thead th[data-sort-dir="desc"]::after {
  content: "  v";
  color: #586787;
}
a {
  color: #1e5ec8;
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
"""

    script = """
(function () {
  function parseNumber(value) {
    var cleaned = value.replace(/[^0-9.+-]/g, "");
    if (!cleaned || cleaned === "-" || cleaned === "." || cleaned === "+") {
      return null;
    }
    var n = Number(cleaned);
    return Number.isFinite(n) ? n : null;
  }

  function compareValues(a, b) {
    var an = parseNumber(a);
    var bn = parseNumber(b);
    if (an !== null && bn !== null) {
      return an - bn;
    }
    return a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
  }

  function sortTable(table, colIndex) {
    var thead = table.tHead;
    if (!thead || !table.tBodies.length) {
      return;
    }
    var headerRow = thead.rows[0];
    var th = headerRow.cells[colIndex];
    var current = th.getAttribute("data-sort-dir") || "none";
    var next = current === "asc" ? "desc" : "asc";

    for (var i = 0; i < headerRow.cells.length; i += 1) {
      headerRow.cells[i].removeAttribute("data-sort-dir");
    }
    th.setAttribute("data-sort-dir", next);

    var tbody = table.tBodies[0];
    var rows = Array.prototype.slice.call(tbody.rows);
    rows.sort(function (ra, rb) {
      var va = (ra.cells[colIndex].getAttribute("data-sort-value") || ra.cells[colIndex].textContent || "").trim();
      var vb = (rb.cells[colIndex].getAttribute("data-sort-value") || rb.cells[colIndex].textContent || "").trim();
      var cmp = compareValues(va, vb);
      return next === "asc" ? cmp : -cmp;
    });
    rows.forEach(function (row) { tbody.appendChild(row); });
  }

  var tables = document.querySelectorAll("table.sortable");
  tables.forEach(function (table) {
    var headers = table.querySelectorAll("thead th");
    headers.forEach(function (th, idx) {
      th.addEventListener("click", function () { sortTable(table, idx); });
    });
  });
})();
"""

    sections = "\n".join(view.sections_html)
    return (
        "<!doctype html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        f"  <title>{html.escape(title)}</title>\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        f"  <style>{style}</style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        f"    <h1>{html.escape(title)}</h1>\n"
        f"    <p class=\"muted\">Generated at {html.escape(generated_at)}</p>\n"
        "    <section>\n"
        "      <h2>Header</h2>\n"
        f"      {_render_key_value_table(view.header_rows)}\n"
        "    </section>\n"
        "    <section>\n"
        "      <h2>Key Metrics</h2>\n"
        f"      {_render_key_value_table(view.metric_rows)}\n"
        "    </section>\n"
        "    <section>\n"
        "      <h2>dominant_rejection_counts</h2>\n"
        f"      {_render_rejection_table(view.dominant_rejections)}\n"
        "    </section>\n"
        f"    {sections}\n"
        "  </main>\n"
        f"  <script>{script}</script>\n"
        "</body>\n"
        "</html>\n"
    )


def _render_key_value_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        "<tr>"
        f"<th>{html.escape(key)}</th>"
        f"<td>{html.escape(value)}</td>"
        "</tr>"
        for key, value in rows
    )
    return f"<table><tbody>{body}</tbody></table>"


def _render_rejection_table(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return "<p>No rejection counts found.</p>"
    body = "".join(
        "<tr>"
        f"<td>{html.escape(key)}</td>"
        f"<td data-sort-value=\"{count}\">{count}</td>"
        "</tr>"
        for key, count in rows
    )
    return (
        "<table class=\"sortable\">"
        "<thead><tr><th>key</th><th>count</th></tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
    )


def _render_sortable_table(headers: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "<p>No rows available.</p>"
    header_html = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_html = "".join(
        "<tr>"
        + "".join(
            f"<td data-sort-value=\"{html.escape(cell)}\">{html.escape(cell)}</td>"
            for cell in row
        )
        + "</tr>"
        for row in rows
    )
    return (
        "<table class=\"sortable\">"
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody>"
        "</table>"
    )


def _dominant_rejections_from_summary(aggregate: dict[str, Any]) -> list[tuple[str, int]]:
    raw = aggregate.get("dominant_rejection_counts")
    if not isinstance(raw, list):
        return []
    rows: list[tuple[str, int]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        key = _as_text(entry.get("key"), default="")
        count = _coerce_int(entry.get("count"))
        if key and count > 0:
            rows.append((key, count))
    return sorted(rows, key=lambda item: (-item[1], item[0]))


def _count_market_scenarios_with_trades(market_dir: Path) -> int:
    runs_dir = market_dir / "runs"
    if not runs_dir.exists():
        return 0

    count = 0
    for manifest_path in runs_dir.glob("*/run_manifest.json"):
        run_manifest = _read_json_dict(manifest_path)
        fills = _coerce_int(run_manifest.get("fills_count"))
        if fills <= 0:
            fills = _count_non_empty_lines(manifest_path.parent / "fills.jsonl")
        if fills > 0:
            count += 1
    return count


def _resolve_scenario_run_dir(
    artifact_dir: Path,
    row: dict[str, Any],
    scenario_id: str,
) -> Path:
    local_run_dir = artifact_dir / "runs" / scenario_id
    if local_run_dir.exists():
        return local_run_dir
    artifact_path = row.get("artifact_path")
    if isinstance(artifact_path, str) and artifact_path.strip():
        candidate = Path(artifact_path)
        if candidate.exists():
            return candidate
    return local_run_dir


def _extract_rejection_counts(run_manifest: dict[str, Any]) -> dict[str, int]:
    for container_key in ("strategy_debug", "modeled_arb_summary"):
        container = run_manifest.get(container_key)
        if not isinstance(container, dict):
            continue
        counts = container.get("rejection_counts")
        if isinstance(counts, dict):
            return _normalize_counts(counts)
    return {}


def _normalize_counts(raw_counts: dict[str, Any]) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for key, value in raw_counts.items():
        name = _as_text(key, default="")
        count = _coerce_int(value)
        if name and count > 0:
            normalized[name] = count
    return normalized


def _sorted_count_items(counts: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def _dominant_count_entry(counts: dict[str, int]) -> tuple[str, int]:
    if not counts:
        return "", 0
    key, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return key, count


def _format_set_values(values: set[str], default: str) -> str:
    cleaned = sorted(
        [v for v in values if str(v).strip()],
        key=lambda item: _set_sort_key(item),
    )
    if not cleaned:
        return default
    return ", ".join(cleaned)


def _set_sort_key(value: str) -> tuple[int, float | str]:
    try:
        return (0, float(value))
    except (TypeError, ValueError):
        return (1, value)


def _market_slug_from_tape_meta(run_manifest: dict[str, Any]) -> str:
    """Return market slug from tape meta.json via tape_dir or tape_path."""
    tape_dir_str = run_manifest.get("tape_dir")
    if not tape_dir_str:
        tape_path_str = run_manifest.get("tape_path")
        if tape_path_str:
            tape_dir_str = str(Path(tape_path_str).parent)
    if not tape_dir_str:
        return ""
    meta_path = Path(tape_dir_str) / "meta.json"
    meta = _read_json_dict(meta_path)
    for context_key in ("quickrun_context", "shadow_context"):
        ctx = meta.get(context_key)
        if isinstance(ctx, dict):
            slug = _as_text(ctx.get("selected_slug"), default="")
            if slug:
                return slug
    return ""


def _extract_timestamp_from_text(text: str) -> str:
    match = re.search(r"(20\d{6}T\d{6}Z)", text)
    return match.group(1) if match else ""


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _count_non_empty_lines(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    count += 1
    except Exception:  # noqa: BLE001
        return 0
    return count


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}
