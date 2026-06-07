"""WI-4 promotion-criteria + evidence-summary module.

Pure, deterministic functions that turn a wallet's deep-scan evidence into:

1. ``summarize_evidence(evidence) -> str`` — a short, human-readable reason
   string (e.g. ``"+$24.0k PnL, 64% win / 180 trades, CLV 72%, churn-triggered"``).
   Same evidence in => byte-identical string out (no clock, no RNG, no I/O).
   This is the WI-5 contract: the Discord approval message (WP-5) imports this
   function to render its candidate card. Keep the signature stable.

2. ``Evidence`` — a small typed container normalising the fields the discovery
   pipeline already produces (wallet_scan ``_extract_user_metrics`` +
   ``mvf.compute_mvf`` dimensions + Loop-A churn flag). Construct it from a raw
   dict with ``Evidence.from_dict`` so callers (worker, CLI, WP-5) do not need
   to know the field plumbing.

3. ``is_candidate(evidence, thresholds) -> bool`` — does this wallet qualify for
   the system-owned *candidate* tier? (OR semantics across gates.)

4. ``is_promotion_eligible(evidence, thresholds) -> bool`` — does it clear the
   stronger *promotion-eligibility* bar? ADVISORY ONLY — this NEVER advances
   lifecycle_state. Promotion to reviewed/promoted/watched still requires a human
   setting ``review_status='approved'`` through ``validate_transition``. There is
   deliberately no auto-promote path in this module.

No ClickHouse, no network, no LLM. Importable from both the CLI and WP-5.

SPEC: docs/specs/SPEC-wallet-discovery-v1.md ; WI-4 work packet.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# Repo root is four parents up: packages/polymarket/discovery/<file>
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "watchlist_promotion.json"

# Hardcoded fallbacks — mirror config/watchlist_promotion.json so behaviour is
# identical whether or not the file (or a key) is present.
_DEFAULT_CANDIDATE_THRESHOLDS: dict[str, Any] = {
    "min_positions": 20,
    "min_realized_net_pnl": 5000.0,
    "min_win_rate": 0.58,
    "min_clv_coverage_rate": 0.50,
    "churn_qualifies": True,
}
_DEFAULT_PROMOTION_ELIGIBILITY: dict[str, Any] = {
    "min_positions": 50,
    "min_realized_net_pnl": 10000.0,
    "min_win_rate": 0.60,
}


# ---------------------------------------------------------------------------
# Config loading (defensive — every key has a fallback default)
# ---------------------------------------------------------------------------


def load_promotion_config(config_path: Optional[Path] = None) -> dict:
    """Load candidate + promotion-eligibility thresholds defensively.

    Missing file or missing keys fall back to the module defaults — never raises
    on a bad/absent config.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    raw: dict = {}
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:  # pragma: no cover - defensive
        raw = {}

    def _merge(section: str, defaults: dict) -> dict:
        merged = dict(defaults)
        section_val = raw.get(section)
        if isinstance(section_val, dict):
            for k, v in section_val.items():
                if str(k).startswith("_"):
                    continue
                merged[k] = v
        return merged

    return {
        "candidate_thresholds": _merge("candidate_thresholds", _DEFAULT_CANDIDATE_THRESHOLDS),
        "promotion_eligibility": _merge("promotion_eligibility", _DEFAULT_PROMOTION_ELIGIBILITY),
    }


# ---------------------------------------------------------------------------
# Evidence container
# ---------------------------------------------------------------------------


def _coerce_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        v = float(value)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_str(value: Any) -> Optional[str]:
    """Return a stripped non-empty string, or None for empty/None."""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


# Resolved-outcome buckets per the coverage report's outcome_counts schema
# (polytool/reports/coverage.py KNOWN_OUTCOMES). PENDING is "open"; the four
# below are "resolved"; UNKNOWN_RESOLUTION is neither (excluded from both).
_RESOLVED_OUTCOMES = ("WIN", "LOSS", "PROFIT_EXIT", "LOSS_EXIT")
_OPEN_OUTCOME = "PENDING"


def _open_resolved_from_outcome_counts(
    outcome_counts: Any,
) -> tuple[Optional[int], Optional[int]]:
    """Split ``outcome_counts`` into ``(open, resolved)``.

    - ``open``     = PENDING
    - ``resolved`` = WIN + LOSS + PROFIT_EXIT + LOSS_EXIT

    UNKNOWN_RESOLUTION is excluded from both (it is neither cleanly open nor
    cleanly resolved). Returns ``(None, None)`` when no usable counts are present
    so the summary omits the split rather than fabricate a "0 open / 0 resolved".
    This reads from the metrics dict the discovery pipeline already produces
    (``_extract_user_metrics`` carries ``outcome_counts``) -- no extractor change.
    """
    if not isinstance(outcome_counts, dict) or not outcome_counts:
        return None, None

    def _n(key: str) -> int:
        return _coerce_int(outcome_counts.get(key)) or 0

    open_ = _n(_OPEN_OUTCOME)
    resolved = sum(_n(k) for k in _RESOLVED_OUTCOMES)
    return open_, resolved


@dataclass(frozen=True)
class Evidence:
    """Normalised deep-scan evidence for one wallet.

    All numeric fields are Optional: a wallet may be missing any dimension (the
    summary + gates handle nulls gracefully and never fabricate values).

    Fields
    ------
    wallet_address:        proxy wallet (0x..) or handle, for display only.
    realized_net_pnl:      net realized PnL in USDC (wallet_scan metrics).
    win_rate:              fraction [0,1] (MVF dimension or metrics).
    trades:                position/trade count (wallet_scan positions_total).
    clv_coverage_rate:     fraction [0,1] of positions with CLV captured.
    churn_triggered:       True if Loop-A churn detection flagged this wallet.
    open_positions:        # of still-open (PENDING) positions.
    resolved_positions:    # of resolved (WIN+LOSS+PROFIT_EXIT+LOSS_EXIT) positions.
    category_focus:        dominant *known* Polymarket category (None when all
                           positions are uncategorised -- never "Unknown").
    source:                discovery origin from the watchlist row
                           (loop_a / manual / loop_d), for display only.
    """

    wallet_address: str = ""
    realized_net_pnl: Optional[float] = None
    win_rate: Optional[float] = None
    trades: Optional[int] = None
    clv_coverage_rate: Optional[float] = None
    churn_triggered: bool = False
    open_positions: Optional[int] = None
    resolved_positions: Optional[int] = None
    category_focus: Optional[str] = None
    source: Optional[str] = None
    # Display-only signals surfaced for the pending-review card (WP-3). None when
    # the scan data does not carry them (handle: pseudonymous wallet; last_active
    # / recent_form: no parseable per-trade data). recent_form is a small dict
    # ``{"trades": [{"close": iso, "pnl": float}], "sample_size": int,
    # "sample_cap": int|None}`` consumed by the embed builder under the honesty
    # rule; it is read-only (never mutated) so the frozen dataclass stays safe.
    handle: Optional[str] = None
    win_count: Optional[int] = None
    last_active: Optional[str] = None
    recent_form: Optional[dict] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        """Build Evidence from a raw evidence dict.

        Accepts the field names produced by the discovery pipeline today and
        common aliases, so the worker / CLI / WP-5 can pass through whatever
        they have on hand:

        - realized_net_pnl   <- realized_net_pnl | realized_pnl_net | pnl
        - win_rate           <- win_rate (already [0,1])
        - trades             <- trades | positions_total | input_trade_count
        - clv_coverage_rate  <- clv_coverage_rate | clv
        - churn_triggered    <- churn_triggered (bool)
        - open/resolved      <- open_positions/resolved_positions, else derived
                                from outcome_counts (PENDING vs WIN/LOSS/*_EXIT)
        - category_focus     <- category_focus (dominant known category, or None)
        - source             <- source (loop_a/manual/loop_d; from the row)
        """
        if not isinstance(data, dict):
            data = {}

        # open/resolved: prefer explicit counts, else derive from outcome_counts
        # (which _extract_user_metrics already carries -- no extractor change).
        open_p = _coerce_int(data.get("open_positions"))
        resolved_p = _coerce_int(data.get("resolved_positions"))
        if open_p is None and resolved_p is None:
            open_p, resolved_p = _open_resolved_from_outcome_counts(
                data.get("outcome_counts")
            )

        return cls(
            wallet_address=str(data.get("wallet_address") or data.get("wallet") or ""),
            realized_net_pnl=_coerce_float(
                data.get("realized_net_pnl")
                if data.get("realized_net_pnl") is not None
                else (data.get("realized_pnl_net") if data.get("realized_pnl_net") is not None
                      else data.get("pnl"))
            ),
            win_rate=_coerce_float(data.get("win_rate")),
            trades=_coerce_int(
                data.get("trades")
                if data.get("trades") is not None
                else (data.get("positions_total") if data.get("positions_total") is not None
                      else data.get("input_trade_count"))
            ),
            clv_coverage_rate=_coerce_float(
                data.get("clv_coverage_rate")
                if data.get("clv_coverage_rate") is not None
                else data.get("clv")
            ),
            churn_triggered=bool(data.get("churn_triggered", False)),
            open_positions=open_p,
            resolved_positions=resolved_p,
            category_focus=_clean_str(data.get("category_focus")),
            source=_clean_str(data.get("source")),
            handle=_clean_str(data.get("handle")),
            win_count=_coerce_int(data.get("win_count")),
            last_active=_clean_str(data.get("last_active")),
            recent_form=(
                data.get("recent_form")
                if isinstance(data.get("recent_form"), dict)
                else None
            ),
        )


# ---------------------------------------------------------------------------
# Evidence summary (WI-5 contract — deterministic reason string)
# ---------------------------------------------------------------------------


def _fmt_pnl(value: float) -> str:
    """Format a USDC PnL with a sign and a compact magnitude suffix.

    Deterministic: rounds to 1 decimal in the chosen unit, fixed thresholds.
        1234567 -> '+$1.2m' ; 24000 -> '+$24.0k' ; -350 -> '-$350'
    """
    sign = "+" if value >= 0 else "-"
    mag = abs(value)
    if mag >= 1_000_000:
        return f"{sign}${mag / 1_000_000:.1f}m"
    if mag >= 1_000:
        return f"{sign}${mag / 1_000:.1f}k"
    return f"{sign}${mag:.0f}"


def summarize_evidence(evidence: "Evidence | dict") -> str:
    """Return a short, human-readable reason string for a wallet's evidence.

    DETERMINISTIC: same evidence => byte-identical output. No clock, no RNG, no
    I/O. This is the WI-5 contract — WP-5's Discord card calls this verbatim.

    Parameters
    ----------
    evidence:
        An ``Evidence`` instance, or a raw dict (coerced via ``Evidence.from_dict``).

    Returns
    -------
    A single line such as::

        "+$24.0k PnL, 64% win / 180 trades, 10 open / 40 resolved, CLV 72%,
         churn-triggered, focus: Politics, via loop_a"

    Missing dimensions are omitted (never fabricated). If no dimension is
    available, returns ``"no evidence available"``.

    Field order is fixed (PnL, win/trades, open/resolved, CLV, churn, category
    focus, source) so the string is stable.
    """
    ev = evidence if isinstance(evidence, Evidence) else Evidence.from_dict(evidence)

    parts: list[str] = []

    if ev.realized_net_pnl is not None:
        parts.append(f"{_fmt_pnl(ev.realized_net_pnl)} PnL")

    if ev.win_rate is not None and ev.trades is not None:
        parts.append(f"{round(ev.win_rate * 100)}% win / {ev.trades} trades")
    elif ev.win_rate is not None:
        parts.append(f"{round(ev.win_rate * 100)}% win")
    elif ev.trades is not None:
        parts.append(f"{ev.trades} trades")

    # open-vs-resolved split: the honest explanation for a "$0 PnL / no win"
    # wallet whose positions are all still open (e.g. "50 open / 0 resolved").
    if ev.open_positions is not None or ev.resolved_positions is not None:
        parts.append(
            f"{ev.open_positions or 0} open / {ev.resolved_positions or 0} resolved"
        )

    # "CLV coverage" — this is clv_coverage_rate, a DATA-COMPLETENESS metric (what
    # fraction of positions have a CLV value captured), NOT a closing-line-value
    # edge signal. Label it honestly so it never reads as a skill metric.
    if ev.clv_coverage_rate is not None:
        parts.append(f"CLV coverage {round(ev.clv_coverage_rate * 100)}%")

    if ev.churn_triggered:
        parts.append("churn-triggered")

    if ev.category_focus:
        parts.append(f"focus: {ev.category_focus}")

    if ev.source:
        parts.append(f"via {ev.source}")

    if not parts:
        return "no evidence available"
    return ", ".join(parts)


# ---------------------------------------------------------------------------
# Gates (candidate membership + promotion eligibility) — NO auto-promote
# ---------------------------------------------------------------------------


def is_candidate(
    evidence: "Evidence | dict",
    thresholds: Optional[dict] = None,
) -> bool:
    """True if a scanned wallet qualifies for the system-owned CANDIDATE tier.

    OR semantics across gates: clearing ANY single gate qualifies, so a wallet
    that is an outlier on one strong dimension is still surfaced. ``min_positions``
    is a floor applied to the metric gates to avoid promoting noise from a few
    trades. A churn-triggered wallet always qualifies when ``churn_qualifies``.

    This only decides candidate-tier MEMBERSHIP — it never touches lifecycle
    state and never promotes.
    """
    ev = evidence if isinstance(evidence, Evidence) else Evidence.from_dict(evidence)
    cfg = thresholds if thresholds is not None else _DEFAULT_CANDIDATE_THRESHOLDS

    if cfg.get("churn_qualifies", True) and ev.churn_triggered:
        return True

    min_positions = _coerce_int(cfg.get("min_positions")) or 0
    enough_trades = ev.trades is not None and ev.trades >= min_positions

    if not enough_trades:
        return False

    min_pnl = _coerce_float(cfg.get("min_realized_net_pnl"))
    if min_pnl is not None and ev.realized_net_pnl is not None and ev.realized_net_pnl >= min_pnl:
        return True

    min_wr = _coerce_float(cfg.get("min_win_rate"))
    if min_wr is not None and ev.win_rate is not None and ev.win_rate >= min_wr:
        return True

    min_clv = _coerce_float(cfg.get("min_clv_coverage_rate"))
    if min_clv is not None and ev.clv_coverage_rate is not None and ev.clv_coverage_rate >= min_clv:
        return True

    return False


def is_promotion_eligible(
    evidence: "Evidence | dict",
    thresholds: Optional[dict] = None,
) -> bool:
    """True if a candidate clears the stronger promotion-ELIGIBILITY bar.

    AND semantics: must clear ALL configured gates. ADVISORY ONLY — used to
    surface a candidate to the operator / WP-5 Discord. It NEVER advances
    lifecycle_state. Promotion still requires a human setting
    ``review_status='approved'`` through ``validate_transition``.
    """
    ev = evidence if isinstance(evidence, Evidence) else Evidence.from_dict(evidence)
    cfg = thresholds if thresholds is not None else _DEFAULT_PROMOTION_ELIGIBILITY

    min_positions = _coerce_int(cfg.get("min_positions"))
    if min_positions is not None:
        if ev.trades is None or ev.trades < min_positions:
            return False

    min_pnl = _coerce_float(cfg.get("min_realized_net_pnl"))
    if min_pnl is not None:
        if ev.realized_net_pnl is None or ev.realized_net_pnl < min_pnl:
            return False

    min_wr = _coerce_float(cfg.get("min_win_rate"))
    if min_wr is not None:
        if ev.win_rate is None or ev.win_rate < min_wr:
            return False

    return True
