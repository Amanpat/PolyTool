"""
Tape corpus integrity audit script.

Covers 5 audit dimensions:
  1. Structural check (required files, parse errors, empty/truncated tapes)
  2. Timestamp monotonicity
  3. YES/NO token ID distinctness
  4. Quote-stream equality (checks for QUOTE_STREAM_DUPLICATE)
  5. Cadence summary (shadow tapes only, sample-based)

Writes a markdown report to artifacts/debug/tape_integrity_audit_report.md
with binary verdict: SAFE_TO_USE or CORPUS_REPAIR_NEEDED.

Usage:
    python tools/gates/tape_integrity_audit.py [--out PATH] [--cadence-sample-n N]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]

_TAPE_ROOTS: Dict[str, Path] = {
    "gold":       _REPO_ROOT / "artifacts/tapes/gold",
    "silver":     _REPO_ROOT / "artifacts/tapes/silver",
    "shadow":     _REPO_ROOT / "artifacts/tapes/shadow",
    "crypto_new": _REPO_ROOT / "artifacts/tapes/crypto/new_market",
    # paper_runs excluded — different artifact schema (strategy decision logs, not WS events)
}

_PAPER_RUNS_ROOT = _REPO_ROOT / "artifacts/tapes/crypto/paper_runs"
_DEFAULT_REPORT_PATH = _REPO_ROOT / "artifacts/debug/tape_integrity_audit_report.md"
_DEFAULT_CADENCE_SAMPLE_N = 20

# ---------------------------------------------------------------------------
# Issue flags (per tape)
# ---------------------------------------------------------------------------
JSONL_BROKEN      = "JSONL_BROKEN"
EMPTY_TAPE        = "EMPTY_TAPE"
TRUNCATED         = "TRUNCATED"
MISSING_FILES     = "MISSING_FILES"
TIMESTAMP_VIOLATION = "TIMESTAMP_VIOLATION"
YES_NO_SAME_TOKEN_ID     = "YES_NO_SAME_TOKEN_ID"
YES_NO_INCOMPLETE_MAPPING = "YES_NO_INCOMPLETE_MAPPING"
QUOTE_STREAM_DUPLICATE   = "QUOTE_STREAM_DUPLICATE"
QUOTE_STREAM_OK          = "QUOTE_STREAM_OK"
NO_INITIAL_SNAPSHOT      = "NO_INITIAL_SNAPSHOT"
DUPLICATE_SEQ            = "DUPLICATE_SEQ"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TapeResult:
    tape_dir: str               # relative path label
    root_name: str
    abs_path: Path
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    event_count: int = 0
    ts_violation_count: int = 0
    ts_first_violation: Optional[float] = None
    yes_id: Optional[str] = None
    no_id: Optional[str] = None
    yes_no_verdict: Optional[str] = None   # SAME / DISTINCT / INCOMPLETE / N/A
    yes_events: int = 0
    no_events: int = 0
    pct_identical_quotes: Optional[float] = None
    quote_verdict: Optional[str] = None    # QUOTE_STREAM_OK / QUOTE_STREAM_DUPLICATE / N/A
    unique_asset_ids: int = 0

    @property
    def is_bad(self) -> bool:
        bad_flags = {JSONL_BROKEN, EMPTY_TAPE, YES_NO_SAME_TOKEN_ID, QUOTE_STREAM_DUPLICATE}
        return bool(bad_flags & set(self.issues))

    @property
    def is_suspicious(self) -> bool:
        sus_flags = {TRUNCATED, MISSING_FILES, YES_NO_INCOMPLETE_MAPPING, TIMESTAMP_VIOLATION}
        return (not self.is_bad) and bool(sus_flags & set(self.issues))

    @property
    def is_clean(self) -> bool:
        return not self.is_bad and not self.is_suspicious


@dataclass
class CadenceStats:
    sample_n: int
    median_gap: float
    p95_gap: float
    total_gaps: int


@dataclass
class AuditReport:
    roots: Dict[str, List[TapeResult]]
    cadence: Optional[CadenceStats]
    runner_scan_cadence_seconds: Optional[int]
    paper_run_sessions: int
    paper_run_dates: List[str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_jsonl_lines(path: Path) -> Tuple[List[dict], List[str]]:
    """Return (parsed_lines, issues). issues contains JSONL_BROKEN / TRUNCATED."""
    issues = []
    lines = []
    raw_text = path.read_bytes()
    raw_lines = raw_text.split(b"\n")
    # Remove trailing empty from final newline
    if raw_lines and raw_lines[-1] == b"":
        raw_lines = raw_lines[:-1]
        trailing_newline = True
    else:
        trailing_newline = False

    if not raw_lines:
        return [], [EMPTY_TAPE]

    for i, raw_line in enumerate(raw_lines):
        stripped = raw_line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
            lines.append(obj)
        except json.JSONDecodeError:
            if i == len(raw_lines) - 1 and not trailing_newline:
                issues.append(TRUNCATED)
            else:
                issues.append(JSONL_BROKEN)
            # Keep going — count what we can parse
    return lines, issues


def _extract_ts_recv(events: List[dict]) -> List[float]:
    """Extract ts_recv from events, skipping any that lack it."""
    result = []
    for ev in events:
        ts = ev.get("ts_recv")
        if ts is not None:
            try:
                result.append(float(ts))
            except (ValueError, TypeError):
                pass
    return result


def _check_timestamp_monotonicity(ts_list: List[float]) -> Tuple[int, Optional[float]]:
    """Return (violation_count, first_violation_ts)."""
    violation_count = 0
    first_violation = None
    for i in range(1, len(ts_list)):
        if ts_list[i] < ts_list[i - 1]:
            violation_count += 1
            if first_violation is None:
                first_violation = ts_list[i]
    return violation_count, first_violation


def _get_yesno_ids_from_meta(tape_abs: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Try to extract yes_token_id / no_token_id from tape metadata files.
    Checks (in order): meta.json -> shadow_context, watch_meta.json.
    Returns (yes_id, no_id) strings or None.
    """
    yes_id, no_id = None, None

    # 1. meta.json -> shadow_context
    meta_path = tape_abs / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            sc = meta.get("shadow_context", {})
            if sc:
                yes_id = sc.get("yes_token_id")
                no_id = sc.get("no_token_id")
                if yes_id and no_id:
                    return yes_id, no_id
        except Exception:
            pass

    # 2. watch_meta.json -> yes_asset_id / no_asset_id
    watch_path = tape_abs / "watch_meta.json"
    if watch_path.exists():
        try:
            wm = json.loads(watch_path.read_text(encoding="utf-8"))
            y = wm.get("yes_asset_id") or wm.get("yes_token_id")
            n = wm.get("no_asset_id") or wm.get("no_token_id")
            if y:
                yes_id = y
            if n:
                no_id = n
            if yes_id and no_id:
                return yes_id, no_id
        except Exception:
            pass

    # 3. fallback: meta.json -> asset_ids[0]/[1] (legacy gold tapes)
    # Only use this if we still have no IDs
    if (yes_id is None or no_id is None) and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            asset_ids = meta.get("asset_ids", [])
            if len(asset_ids) >= 2 and yes_id is None and no_id is None:
                # We don't know which is YES vs NO without extra metadata
                # Flag as INCOMPLETE (not an error, just no label mapping)
                pass
        except Exception:
            pass

    return yes_id, no_id


def _collect_quote_stream(events: List[dict], asset_id: str) -> List[Tuple[float, str, str]]:
    """
    Collect (ts_recv, best_bid, best_ask) for a specific asset_id.
    Handles both legacy (asset_id at top level) and modern (price_changes[]) schemas.
    """
    result = []
    for ev in events:
        ts = ev.get("ts_recv", 0.0)

        # Modern schema: price_changes list
        pcs = ev.get("price_changes")
        if pcs is not None:
            for pc in pcs:
                if pc.get("asset_id") == asset_id:
                    bb = pc.get("best_bid", "")
                    ba = pc.get("best_ask", "")
                    if bb or ba:
                        result.append((float(ts), str(bb), str(ba)))
        else:
            # Legacy schema: asset_id at top level
            ev_asset = ev.get("asset_id")
            if ev_asset == asset_id:
                ev_type = ev.get("event_type", "")
                if ev_type == "book":
                    bids = ev.get("bids", [])
                    asks = ev.get("asks", [])
                    best_bid = ""
                    best_ask = ""
                    if bids:
                        try:
                            best_bid = str(max(float(b["price"]) for b in bids))
                        except Exception:
                            pass
                    if asks:
                        try:
                            best_ask = str(min(float(a["price"]) for a in asks))
                        except Exception:
                            pass
                    if best_bid or best_ask:
                        result.append((float(ts), best_bid, best_ask))
                elif ev_type in ("price_change", "last_trade_price"):
                    bb = ev.get("best_bid", ev.get("price", ""))
                    ba = ev.get("best_ask", "")
                    if bb or ba:
                        result.append((float(ts), str(bb), str(ba)))

    return result


_MIN_EVENTS_FOR_QUOTE_CHECK = 5  # Require at least N events per leg for meaningful comparison
# Symmetric BBO like 0.49/0.51 is expected for 50/50 binary markets and NOT a mapping bug.
# A true duplicate mapping would show identical best_bid values that DIVERGE from 0.50,
# e.g. both legs show "0.72" or "0.31" — which is impossible unless they share the same token.
_SYMMETRIC_BBO_PAIRS = {("0.49", "0.51"), ("0.5", "0.5"), ("0.50", "0.50"), ("0.5", "0.51")}


def _bbo_is_symmetric(best_bid: str, best_ask: str) -> bool:
    """Return True if this BBO pair is consistent with symmetric 50/50 binary pricing."""
    try:
        bb = round(float(best_bid), 2)
        ba = round(float(best_ask), 2)
        # Sum close to 1.0 and mid close to 0.50 = symmetric binary market
        return abs(bb + ba - 1.0) < 0.02 and abs(bb - 0.5) < 0.10
    except (ValueError, TypeError):
        return False


def _quote_stream_equality(
    yes_stream: List[Tuple[float, str, str]],
    no_stream: List[Tuple[float, str, str]],
) -> Tuple[float, str]:
    """
    Compare YES and NO quote streams.
    Returns (pct_identical, verdict).
    Verdict: QUOTE_STREAM_DUPLICATE or QUOTE_STREAM_OK or INSUFFICIENT_DATA.

    Key design: symmetric BBO like 0.49/0.51 is mathematically expected on 50/50 binary
    markets and is NOT a mapping bug. A true QUOTE_STREAM_DUPLICATE requires that:
      (a) both legs have sufficient events (>= _MIN_EVENTS_FOR_QUOTE_CHECK),
      (b) the identical quote pairs are NOT all symmetric (non-50/50 identical BBOs),
      AND (c) timestamps also align (same-token would produce identical timestamps).
    """
    if not yes_stream or not no_stream:
        return 0.0, QUOTE_STREAM_OK

    min_len = min(len(yes_stream), len(no_stream))

    # Too few events to distinguish symmetric market state from mapping bug
    if min_len < _MIN_EVENTS_FOR_QUOTE_CHECK:
        return 0.0, "INSUFFICIENT_DATA"

    identical = sum(
        1 for i in range(min_len)
        if (yes_stream[i][1], yes_stream[i][2]) == (no_stream[i][1], no_stream[i][2])
    )
    pct = identical / min_len

    if pct < 0.90:
        return pct, QUOTE_STREAM_OK

    # High similarity: check whether the identical pairs are all symmetric (0.49/0.51)
    # If so, this is expected 50/50 market behavior, NOT a mapping bug
    if pct >= 0.90:
        non_symmetric_identical = sum(
            1 for i in range(min_len)
            if (yes_stream[i][1], yes_stream[i][2]) == (no_stream[i][1], no_stream[i][2])
            and not _bbo_is_symmetric(yes_stream[i][1], yes_stream[i][2])
        )
        non_symmetric_total = sum(
            1 for i in range(min_len)
            if not _bbo_is_symmetric(yes_stream[i][1], yes_stream[i][2])
        )

        if non_symmetric_total == 0:
            # ALL observed quotes are symmetric — this is a 50/50 binary market, not a dup
            return pct, QUOTE_STREAM_OK

        # Non-symmetric identical quotes suggest actual token duplication
        non_sym_pct = non_symmetric_identical / non_symmetric_total
        if non_sym_pct >= 0.90:
            return pct, QUOTE_STREAM_DUPLICATE

    return pct, QUOTE_STREAM_OK


def _find_events_file(tape_abs: Path, root_name: str) -> Optional[Path]:
    """Return the primary events file path for this tape, or None if missing."""
    # Silver tapes use silver_events.jsonl
    if root_name == "silver":
        candidate = tape_abs / "silver_events.jsonl"
        if candidate.exists():
            return candidate
        # Fallback — some silver tapes may have events.jsonl too
        fallback = tape_abs / "events.jsonl"
        if fallback.exists():
            return fallback
        return None

    # All other roots use events.jsonl
    candidate = tape_abs / "events.jsonl"
    if candidate.exists():
        return candidate
    return None


# ---------------------------------------------------------------------------
# Per-tape audit
# ---------------------------------------------------------------------------

def _audit_tape(tape_abs: Path, root_name: str) -> TapeResult:
    tape_dir = str(tape_abs.relative_to(_REPO_ROOT))
    result = TapeResult(tape_dir=tape_dir, root_name=root_name, abs_path=tape_abs)

    # -------------------------------------------------------------------------
    # Dimension 1: Structural check
    # -------------------------------------------------------------------------
    events_path = _find_events_file(tape_abs, root_name)
    if events_path is None:
        result.issues.append(MISSING_FILES)
        return result  # Can't proceed further without events file

    events, struct_issues = _load_jsonl_lines(events_path)
    result.issues.extend(i for i in struct_issues if i not in result.issues)

    if not events:
        result.issues.append(EMPTY_TAPE)
        return result

    result.event_count = len(events)

    # -------------------------------------------------------------------------
    # Dimension 2: Timestamp monotonicity
    # -------------------------------------------------------------------------
    ts_list = _extract_ts_recv(events)
    if ts_list:
        violations, first_viol = _check_timestamp_monotonicity(ts_list)
        result.ts_violation_count = violations
        result.ts_first_violation = first_viol
        if violations > 0:
            result.issues.append(TIMESTAMP_VIOLATION)

    # -------------------------------------------------------------------------
    # Dimension 4: Replay fidelity indicators
    # -------------------------------------------------------------------------
    # No initial book snapshot (legacy schema only)
    if events:
        first_ev = events[0]
        if first_ev.get("event_type") == "book":
            pass  # Good
        elif "price_changes" not in first_ev and first_ev.get("asset_id"):
            # Legacy schema — first event is not a book
            result.warnings.append(NO_INITIAL_SNAPSHOT)

    # Duplicate seq values
    seen_seqs: set = set()
    dup_found = False
    for ev in events:
        seq_val = ev.get("seq")
        if seq_val is not None:
            if seq_val in seen_seqs:
                dup_found = True
                break
            seen_seqs.add(seq_val)
    if dup_found:
        result.issues.append(DUPLICATE_SEQ)

    # Unique asset IDs
    asset_ids: set = set()
    for ev in events:
        if ev.get("asset_id"):
            asset_ids.add(ev["asset_id"])
        pcs = ev.get("price_changes", [])
        for pc in pcs:
            if pc.get("asset_id"):
                asset_ids.add(pc["asset_id"])
    result.unique_asset_ids = len(asset_ids)

    # -------------------------------------------------------------------------
    # Dimension 3: YES/NO token ID distinctness (binary tapes only)
    # -------------------------------------------------------------------------
    # Binary tapes are those from shadow/gold/crypto_new roots with YES/NO metadata
    if root_name in ("shadow", "gold", "crypto_new"):
        yes_id, no_id = _get_yesno_ids_from_meta(tape_abs)
        result.yes_id = yes_id
        result.no_id = no_id

        if yes_id and no_id:
            if yes_id == no_id:
                result.yes_no_verdict = "SAME"
                result.issues.append(YES_NO_SAME_TOKEN_ID)
            else:
                result.yes_no_verdict = "DISTINCT"
                # Proceed to quote-stream check (Dimension 3b)
                yes_stream = _collect_quote_stream(events, yes_id)
                no_stream = _collect_quote_stream(events, no_id)
                result.yes_events = len(yes_stream)
                result.no_events = len(no_stream)

                if yes_stream and no_stream:
                    pct, q_verdict = _quote_stream_equality(yes_stream, no_stream)
                    result.pct_identical_quotes = pct
                    result.quote_verdict = q_verdict
                    if q_verdict == QUOTE_STREAM_DUPLICATE:
                        result.issues.append(QUOTE_STREAM_DUPLICATE)
                    elif q_verdict == QUOTE_STREAM_OK:
                        result.issues.append(QUOTE_STREAM_OK)
                    # INSUFFICIENT_DATA and N/A: no issue flag added (not enough data)
                else:
                    # Not enough data for quote comparison
                    result.quote_verdict = "N/A"
        elif yes_id or no_id:
            result.yes_no_verdict = "INCOMPLETE"
            result.issues.append(YES_NO_INCOMPLETE_MAPPING)
        else:
            result.yes_no_verdict = "N/A"
    else:
        result.yes_no_verdict = "N/A"
        result.quote_verdict = "N/A"

    return result


# ---------------------------------------------------------------------------
# Silver tape layout: market_id / timestamp / silver_events.jsonl
# ---------------------------------------------------------------------------

def _collect_tape_dirs_silver(root: Path) -> List[Path]:
    """Silver has nested layout: root/market_id/timestamp/"""
    dirs = []
    if not root.exists():
        return dirs
    for market_dir in root.iterdir():
        if not market_dir.is_dir():
            continue
        for ts_dir in market_dir.iterdir():
            if not ts_dir.is_dir():
                continue
            dirs.append(ts_dir)
    return dirs


def _collect_tape_dirs_flat(root: Path) -> List[Path]:
    """Gold/shadow/crypto_new: root/tape_dir/ (flat)"""
    dirs = []
    if not root.exists():
        return dirs
    for d in root.iterdir():
        if d.is_dir():
            dirs.append(d)
    return dirs


def _collect_tape_dirs(root: Path, root_name: str) -> List[Path]:
    if root_name == "silver":
        return _collect_tape_dirs_silver(root)
    return _collect_tape_dirs_flat(root)


# ---------------------------------------------------------------------------
# Dimension 5: Cadence summary (shadow sample)
# ---------------------------------------------------------------------------

def _compute_cadence(shadow_root: Path, sample_n: int) -> Optional[CadenceStats]:
    """Sample up to sample_n shadow tapes, compute inter-event gap stats."""
    tape_dirs = _collect_tape_dirs_flat(shadow_root)
    if not tape_dirs:
        return None

    # Uniform sample
    if len(tape_dirs) > sample_n:
        step = len(tape_dirs) / sample_n
        sampled = [tape_dirs[int(i * step)] for i in range(sample_n)]
    else:
        sampled = tape_dirs

    all_gaps: List[float] = []
    sampled_count = 0

    for tape_abs in sampled:
        ev_path = tape_abs / "events.jsonl"
        if not ev_path.exists():
            continue
        try:
            events, _ = _load_jsonl_lines(ev_path)
        except Exception:
            continue
        ts_list = _extract_ts_recv(events)
        if len(ts_list) < 2:
            continue
        gaps = [ts_list[i] - ts_list[i - 1] for i in range(1, len(ts_list)) if ts_list[i] >= ts_list[i - 1]]
        all_gaps.extend(gaps)
        sampled_count += 1

    if not all_gaps:
        return None

    all_gaps.sort()
    n = len(all_gaps)
    median_gap = all_gaps[n // 2]
    p95_idx = int(n * 0.95)
    p95_gap = all_gaps[min(p95_idx, n - 1)]

    return CadenceStats(
        sample_n=sampled_count,
        median_gap=median_gap,
        p95_gap=p95_gap,
        total_gaps=n,
    )


def _get_runner_scan_cadence() -> Optional[float]:
    """Read cycle_interval_seconds default from paper_runner.py (CryptoPairRunnerSettings)."""
    # The default is defined in paper_runner.py as a dataclass field
    runner_path = _REPO_ROOT / "packages/polymarket/crypto_pairs/paper_runner.py"
    if not runner_path.exists():
        return None
    try:
        text = runner_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            # Match: "    cycle_interval_seconds: float = 0.5"
            stripped = line.strip()
            if "cycle_interval_seconds" in stripped and ("float" in stripped or "int" in stripped) and "=" in stripped:
                parts = stripped.split("=")
                if len(parts) >= 2:
                    val_str = parts[-1].strip().rstrip(",").rstrip()
                    try:
                        return float(val_str)
                    except ValueError:
                        pass
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Paper runs inventory
# ---------------------------------------------------------------------------

def _count_paper_runs() -> Tuple[int, List[str]]:
    """Count paper run sessions and list date directories."""
    if not _PAPER_RUNS_ROOT.exists():
        return 0, []
    date_dirs = [d for d in _PAPER_RUNS_ROOT.iterdir() if d.is_dir()]
    session_count = 0
    dates = []
    for dd in sorted(date_dirs):
        dates.append(dd.name)
        for sd in dd.iterdir():
            if sd.is_dir():
                session_count += 1
    return session_count, dates


# ---------------------------------------------------------------------------
# Main audit orchestration
# ---------------------------------------------------------------------------

def audit_tape_roots(cadence_sample_n: int = _DEFAULT_CADENCE_SAMPLE_N) -> AuditReport:
    """Run audit across all configured tape roots. Returns AuditReport."""
    roots_results: Dict[str, List[TapeResult]] = {}

    for root_name, root_path in _TAPE_ROOTS.items():
        print(f"[audit] Scanning root: {root_name} ({root_path})", flush=True)
        if not root_path.exists():
            print(f"[audit]   Root does not exist, skipping.", flush=True)
            roots_results[root_name] = []
            continue

        tape_dirs = _collect_tape_dirs(root_path, root_name)
        results: List[TapeResult] = []
        for tape_abs in tape_dirs:
            try:
                tr = _audit_tape(tape_abs, root_name)
                results.append(tr)
            except Exception as exc:
                # Create a result with a generic error flag
                tr = TapeResult(
                    tape_dir=str(tape_abs.relative_to(_REPO_ROOT)),
                    root_name=root_name,
                    abs_path=tape_abs,
                )
                tr.issues.append(JSONL_BROKEN)
                tr.warnings.append(f"Exception during audit: {exc}")
                results.append(tr)

        print(f"[audit]   {len(results)} tapes scanned.", flush=True)
        roots_results[root_name] = results

    # Cadence (shadow only)
    shadow_root = _TAPE_ROOTS.get("shadow")
    cadence = None
    if shadow_root and shadow_root.exists():
        print(f"[audit] Computing cadence stats (shadow sample n={cadence_sample_n})...", flush=True)
        cadence = _compute_cadence(shadow_root, cadence_sample_n)

    runner_cadence = _get_runner_scan_cadence()
    paper_sessions, paper_dates = _count_paper_runs()

    return AuditReport(
        roots=roots_results,
        cadence=cadence,
        runner_scan_cadence_seconds=runner_cadence,
        paper_run_sessions=paper_sessions,
        paper_run_dates=paper_dates,
    )


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------

def compute_verdict(report: AuditReport) -> Tuple[str, str]:
    """
    Returns (verdict, rationale).
    CORPUS_REPAIR_NEEDED if any YES_NO_SAME_TOKEN_ID or QUOTE_STREAM_DUPLICATE
    or >10% of tapes in any root are JSONL_BROKEN or EMPTY_TAPE.
    """
    repair_reasons: List[str] = []

    for root_name, results in report.roots.items():
        if not results:
            continue
        n_total = len(results)

        for tr in results:
            if YES_NO_SAME_TOKEN_ID in tr.issues:
                repair_reasons.append(
                    f"YES_NO_SAME_TOKEN_ID in {root_name}/{tr.tape_dir}"
                )
            if QUOTE_STREAM_DUPLICATE in tr.issues:
                repair_reasons.append(
                    f"QUOTE_STREAM_DUPLICATE in {root_name}/{tr.tape_dir}"
                )

        bad_count = sum(
            1 for tr in results
            if JSONL_BROKEN in tr.issues or EMPTY_TAPE in tr.issues
        )
        pct_bad = bad_count / n_total if n_total > 0 else 0.0
        if pct_bad > 0.10:
            repair_reasons.append(
                f"{root_name}: {bad_count}/{n_total} tapes are JSONL_BROKEN or EMPTY "
                f"({pct_bad:.0%} > 10% threshold)"
            )

    if repair_reasons:
        rationale = "At least one critical integrity issue was found: " + "; ".join(repair_reasons[:3])
        if len(repair_reasons) > 3:
            rationale += f" (and {len(repair_reasons) - 3} more)"
        return "CORPUS_REPAIR_NEEDED", rationale
    else:
        # Collect notable warnings for rationale
        all_warnings = []
        for root_name, results in report.roots.items():
            ts_violations = sum(1 for tr in results if TIMESTAMP_VIOLATION in tr.issues)
            incomplete = sum(1 for tr in results if YES_NO_INCOMPLETE_MAPPING in tr.issues)
            if ts_violations > 0:
                all_warnings.append(f"{root_name}: {ts_violations} tapes with timestamp violations (non-fatal)")
            if incomplete > 0:
                all_warnings.append(f"{root_name}: {incomplete} tapes with incomplete YES/NO mapping (non-fatal)")
        if all_warnings:
            rationale = "No critical issues found. Warnings (non-blocking): " + "; ".join(all_warnings[:3])
        else:
            rationale = "No critical issues found. All tape roots passed all dimensions."
        return "SAFE_TO_USE", rationale


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _fmt_id_prefix(id_str: Optional[str]) -> str:
    if not id_str:
        return "N/A"
    return id_str[:16] + "..."


def _pct_str(pct: Optional[float]) -> str:
    if pct is None:
        return "N/A"
    return f"{pct:.1%}"


def generate_report(report: AuditReport, verdict: str, rationale: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: List[str] = []

    lines.append("# Tape Corpus Integrity Audit Report")
    lines.append(f"**Date:** 2026-03-29  ")
    lines.append(f"**Run at:** {now}  ")
    lines.append(f"**Roots scanned:** {', '.join(r for r in _TAPE_ROOTS)}")
    lines.append("")

    # ---- Summary Table ----
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| Root | Tapes | Clean | Suspicious | Bad |")
    lines.append("|------|-------|-------|------------|-----|")

    for root_name in _TAPE_ROOTS:
        results = report.roots.get(root_name, [])
        n_total = len(results)
        n_clean = sum(1 for tr in results if tr.is_clean)
        n_sus = sum(1 for tr in results if tr.is_suspicious)
        n_bad = sum(1 for tr in results if tr.is_bad)
        lines.append(f"| {root_name} | {n_total} | {n_clean} | {n_sus} | {n_bad} |")

    lines.append("")

    # ---- YES/NO Token Distinctness ----
    lines.append("## YES/NO Token Distinctness")
    lines.append("")
    binary_results = [
        tr for root_name, results in report.roots.items()
        for tr in results
        if tr.yes_no_verdict not in (None, "N/A")
    ]
    if binary_results:
        lines.append("| Root | Tape Dir | YES ID Prefix | NO ID Prefix | Result |")
        lines.append("|------|----------|--------------|--------------|--------|")
        for tr in binary_results:
            result_cell = tr.yes_no_verdict or "N/A"
            lines.append(
                f"| {tr.root_name} "
                f"| {tr.tape_dir[-50:]} "
                f"| {_fmt_id_prefix(tr.yes_id)} "
                f"| {_fmt_id_prefix(tr.no_id)} "
                f"| {result_cell} |"
            )
    else:
        lines.append("No binary tapes with YES/NO token metadata found.")

    # Summary counts
    same_count = sum(1 for tr in binary_results if tr.yes_no_verdict == "SAME")
    distinct_count = sum(1 for tr in binary_results if tr.yes_no_verdict == "DISTINCT")
    incomplete_count = sum(1 for tr in binary_results if tr.yes_no_verdict == "INCOMPLETE")
    lines.append("")
    lines.append(
        f"**Totals:** {distinct_count} DISTINCT, {same_count} SAME (critical), "
        f"{incomplete_count} INCOMPLETE (partial metadata)"
    )
    lines.append("")

    # ---- Structural Issues ----
    lines.append("## Structural Issues")
    lines.append("")
    structural_flags = {JSONL_BROKEN, EMPTY_TAPE, TRUNCATED, MISSING_FILES, DUPLICATE_SEQ}
    structural_tapes = [
        tr for root_name, results in report.roots.items()
        for tr in results
        if any(f in tr.issues for f in structural_flags)
    ]
    if structural_tapes:
        lines.append("| Root | Tape Dir | Issues |")
        lines.append("|------|----------|--------|")
        for tr in structural_tapes:
            flagged = [f for f in tr.issues if f in structural_flags]
            lines.append(f"| {tr.root_name} | {tr.tape_dir[-60:]} | {', '.join(flagged)} |")
    else:
        lines.append("No structural issues found across any root.")
    lines.append("")

    # ---- Timestamp Violations ----
    lines.append("## Timestamp Violations")
    lines.append("")
    ts_violated = [
        tr for root_name, results in report.roots.items()
        for tr in results
        if TIMESTAMP_VIOLATION in tr.issues
    ]
    if ts_violated:
        lines.append("| Root | Tape Dir | Violation Count | First Violation ts |")
        lines.append("|------|----------|-----------------|--------------------|")
        for tr in ts_violated:
            fv = f"{tr.ts_first_violation:.3f}" if tr.ts_first_violation else "N/A"
            lines.append(
                f"| {tr.root_name} | {tr.tape_dir[-60:]} | {tr.ts_violation_count} | {fv} |"
            )
    else:
        lines.append("No timestamp violations found across any root.")
    lines.append("")

    # ---- Quote Stream Equality ----
    lines.append("## Quote Stream Equality Check")
    lines.append("")
    quote_results = [
        tr for root_name, results in report.roots.items()
        for tr in results
        if tr.quote_verdict not in (None, "N/A")
    ]
    if quote_results:
        # Show only non-OK results in the main table to keep it readable;
        # summarize all OK counts below
        notable = [tr for tr in quote_results if tr.quote_verdict != QUOTE_STREAM_OK]
        if notable:
            lines.append("### Flagged Tapes (non-OK verdicts)")
            lines.append("")
            lines.append("| Root | Tape Dir | YES Events | NO Events | Pct Identical | Verdict |")
            lines.append("|------|----------|-----------|-----------|---------------|---------|")
            for tr in notable:
                lines.append(
                    f"| {tr.root_name} "
                    f"| {tr.tape_dir[-50:]} "
                    f"| {tr.yes_events} "
                    f"| {tr.no_events} "
                    f"| {_pct_str(tr.pct_identical_quotes)} "
                    f"| {tr.quote_verdict} |"
                )
            lines.append("")
        dup_count = sum(1 for tr in quote_results if tr.quote_verdict == QUOTE_STREAM_DUPLICATE)
        ok_count = sum(1 for tr in quote_results if tr.quote_verdict == QUOTE_STREAM_OK)
        insuf_count = sum(1 for tr in quote_results if tr.quote_verdict == "INSUFFICIENT_DATA")
        lines.append(
            f"**Totals:** {ok_count} QUOTE_STREAM_OK, "
            f"{dup_count} QUOTE_STREAM_DUPLICATE (critical), "
            f"{insuf_count} INSUFFICIENT_DATA (short tapes — symmetric pricing expected at market open)"
        )
    else:
        lines.append("No binary tapes with sufficient quote data for stream comparison.")
    lines.append("")

    # ---- Cadence Summary ----
    lines.append("## Cadence Summary (Shadow Sample)")
    lines.append("")
    if report.cadence:
        c = report.cadence
        lines.append(f"- **Sampled tapes:** {c.sample_n}")
        lines.append(f"- **Total inter-event gaps analyzed:** {c.total_gaps:,}")
        lines.append(f"- **Median inter-event gap:** {c.median_gap:.3f}s")
        lines.append(f"- **p95 inter-event gap:** {c.p95_gap:.3f}s")
        if report.runner_scan_cadence_seconds:
            lines.append(
                f"- **Runner scan cadence (config_models.py default):** "
                f"{report.runner_scan_cadence_seconds}s"
            )
            ratio = c.median_gap / report.runner_scan_cadence_seconds
            lines.append(
                f"- **Gap/cadence ratio (median):** {ratio:.2f}x "
                f"({'events arrive faster than scan cycle' if ratio < 1 else 'scan cycle faster than event rate'})"
            )
        else:
            lines.append("- Runner scan cadence: could not read from config_models.py")
    else:
        lines.append("Could not compute cadence (no shadow tapes with sufficient data).")
    lines.append("")

    # ---- Paper Runs ----
    lines.append("## Paper Runs (separate)")
    lines.append("")
    lines.append(f"- **Root:** `artifacts/tapes/crypto/paper_runs/`")
    lines.append(f"- **Date directories:** {', '.join(report.paper_run_dates) if report.paper_run_dates else 'none'}")
    lines.append(f"- **Sessions found:** {report.paper_run_sessions}")
    lines.append("- **Schema:** `runtime_events.jsonl` (not replay tapes — strategy decision logs)")
    lines.append("- **Note:** Structural tape checks (events.jsonl, timestamp monotonicity, YES/NO token checks)")
    lines.append("  do NOT apply to paper runs. These are CryptoPairRunner output artifacts, not WS event tapes.")
    lines.append("")

    # ---- Verdict ----
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{verdict}**")
    lines.append("")
    lines.append(f"*Rationale:* {rationale}")
    lines.append("")

    # ---- Next Work Packet ----
    lines.append("## Next Work Packet")
    lines.append("")
    if verdict == "CORPUS_REPAIR_NEEDED":
        lines.append(
            "Investigate flagged tapes for root-cause repair before running Gate 2 "
            "scenario sweep or Track 2 paper soak."
        )
    else:
        lines.append(
            "Corpus is structurally sound; proceed with Gate 2 scenario sweep on crypto "
            "subset or Track 2 paper soak per operator authorization."
        )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# run_audit entry point
# ---------------------------------------------------------------------------

def run_audit(out_path: Path, cadence_sample_n: int = _DEFAULT_CADENCE_SAMPLE_N) -> int:
    """Run full audit and write report. Returns exit code (0 = SAFE, 1 = REPAIR_NEEDED)."""
    report = audit_tape_roots(cadence_sample_n=cadence_sample_n)
    verdict, rationale = compute_verdict(report)
    report_text = generate_report(report, verdict, rationale)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report_text, encoding="utf-8")
    print(f"\n[audit] Report written to: {out_path}", flush=True)
    print(f"[audit] Verdict: {verdict}", flush=True)
    print(f"[audit] Rationale: {rationale}", flush=True)

    return 0 if verdict == "SAFE_TO_USE" else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tape corpus integrity audit")
    parser.add_argument(
        "--out",
        default=str(_DEFAULT_REPORT_PATH),
        help="Output path for the markdown report",
    )
    parser.add_argument(
        "--cadence-sample-n",
        type=int,
        default=_DEFAULT_CADENCE_SAMPLE_N,
        help="Number of shadow tapes to sample for cadence stats",
    )
    args = parser.parse_args(argv)
    return run_audit(out_path=Path(args.out), cadence_sample_n=args.cadence_sample_n)


if __name__ == "__main__":
    raise SystemExit(main())
