"""Gate 2 tape acquisition manifest generator.

Scans a tape directory, runs eligibility checks on every tape, reads regime
metadata, and produces a structured ``acquisition_manifest.json`` with
per-tape evidence signals and a corpus coverage summary.

Purpose
-------
The Gate 2 blocker is the absence of a tape with ``executable_ticks > 0``.
This command makes the corpus state visible: which tapes exist, which are
eligible, which regimes are covered, and what diagnostic evidence each tape
provides.  The output is designed to make later gate decisions easier, not
murkier.

Eligibility label contract (hard invariant)
-------------------------------------------
  - A tape is marked ``eligible: true`` ONLY if
    ``ticks_with_depth_and_edge > 0`` per ``check_binary_arb_tape_eligibility``
    in ``packages/polymarket/simtrader/sweeps/eligibility.py``.
  - ``executable_ticks`` is always taken from
    ``stats["ticks_with_depth_and_edge"]``; the label and the count must agree.
  - Ineligible tapes always carry a ``reject_reason``.
  - "Could be tradable" is not enough — the check uses the same depth+edge
    gate the strategy uses.

Regime labels
-------------
Tapes are labelled with one of: ``politics``, ``sports``, ``new_market``,
``unknown``.  The label is read from tape metadata written by the recording
tool (``watch-arb-candidates`` or ``prepare-gate2``).  Tapes without a
regime label default to ``unknown``.

Usage
-----
  # Scan default tapes directory and print summary:
  python -m polytool tape-manifest

  # Scan a custom directory and write manifest:
  python -m polytool tape-manifest --tapes-dir artifacts/tapes/gold

  # Write manifest to a specific path:
  python -m polytool tape-manifest --out artifacts/gate2_tape_manifest.json

  # Verbose (shows per-tape eligibility check progress):
  python -m polytool tape-manifest -v
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from packages.polymarket.market_selection.regime_policy import (
    TapeRegimeIntegrity,
    coverage_from_classified_regimes,
    derive_tape_regime,
)

logger = logging.getLogger(__name__)

_DEFAULT_TAPES_DIR = Path("artifacts/tapes/gold")
_DEFAULT_OUT = Path("artifacts/gates/manifests/gate2_tape_manifest.json")
_VALID_REGIMES = frozenset({"politics", "sports", "new_market", "unknown"})
_DEFAULT_MAX_SIZE: float = 50.0
_DEFAULT_BUFFER: float = 0.01
_SNAPSHOT_FIELD_MAP = (
    ("market_slug", "market_slug"),
    ("slug", "slug"),
    ("question", "question"),
    ("title", "title"),
    ("tags", "tags"),
    ("tag_names", "tag_names"),
    ("tagNames", "tagNames"),
    ("category", "category"),
    ("subcategory", "subcategory"),
    ("event_slug", "event_slug"),
    ("event_title", "event_title"),
    ("created_at", "created_at"),
    ("createdAt", "created_at"),
    ("age_hours", "age_hours"),
    ("ageHours", "age_hours"),
    ("captured_at", "captured_at"),
)

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TapeRecord:
    """Evidence record for one tape directory."""

    tape_dir: str
    slug: str
    regime: str                  # = final_regime; kept for backward compatibility
    recorded_by: str             # watch-arb-candidates | prepare-gate2 | simtrader-* | unknown
    eligible: bool
    executable_ticks: int        # ticks_with_depth_and_edge from eligibility stats
    reject_reason: str
    evidence: dict[str, Any] = field(default_factory=dict)
    # Regime integrity fields (added for SPEC-0016)
    derived_regime: str = ""     # from classify_market_regime; "other" = weak/no signal
    operator_regime: str = ""    # label from tape metadata; "unknown" if absent
    final_regime: str = ""       # authoritative regime; same as regime for new records
    regime_source: str = ""      # "derived" | "operator" | "fallback_unknown"
    regime_mismatch: bool = False  # True when derived and operator disagree (both named)
    # Diagnostic enrichment (populated by enrich_tape_diagnostics)
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass
class CorpusSummary:
    """Corpus-level coverage summary."""

    total_tapes: int
    eligible_count: int
    ineligible_count: int
    by_regime: dict[str, dict[str, int]]
    mixed_regime_eligible: bool        # at least one eligible tape exists and corpus spans >= 2 named regimes
    gate2_eligible_tapes: list[str]    # tape_dirs with eligible=True
    generated_at: str
    corpus_note: str = ""
    regime_coverage: dict = field(default_factory=dict)  # from coverage_from_classified_regimes


# ---------------------------------------------------------------------------
# Diagnostic classification helpers
# ---------------------------------------------------------------------------

# Confidence tier thresholds
_GOLD_SOURCES = frozenset({"watch-arb-candidates", "simtrader-shadow"})
_SILVER_SOURCES = frozenset({"prepare-gate2", "simtrader-quickrun"})
_GOLD_MIN_EVENTS = 50
_GOLD_MIN_BBO = 20
_SILVER_MIN_EVENTS = 20


def classify_tape_confidence(
    recorded_by: str,
    events_scanned: int,
    ticks_with_both_bbo: int,
) -> str:
    """Classify tape fidelity tier from source tool and event density.

    Tiers:
      GOLD   — live recording with adequate density (watch-arb-candidates or
               simtrader-shadow, >=50 events, >=20 BBO ticks)
      SILVER — Silver-reconstruction source OR live source with thin density
               (>=50 events OR Silver source with >=20 events)
      BRONZE — Some events and BBO ticks but below Silver threshold
      UNKNOWN — No events or no density data

    Args:
        recorded_by:        Source tool identifier from tape metadata.
        events_scanned:     Total events seen in the tape.
        ticks_with_both_bbo: Ticks where both YES and NO had BBO quotes.

    Returns:
        One of "GOLD", "SILVER", "BRONZE", "UNKNOWN".
    """
    if events_scanned <= 0:
        return "UNKNOWN"

    is_gold_source = recorded_by in _GOLD_SOURCES
    is_silver_source = recorded_by in _SILVER_SOURCES

    if (
        is_gold_source
        and events_scanned >= _GOLD_MIN_EVENTS
        and ticks_with_both_bbo >= _GOLD_MIN_BBO
    ):
        return "GOLD"

    if events_scanned >= _GOLD_MIN_EVENTS:
        return "SILVER"

    if is_silver_source and events_scanned >= _SILVER_MIN_EVENTS:
        return "SILVER"

    if ticks_with_both_bbo > 0:
        return "BRONZE"

    return "UNKNOWN"


def classify_reject_code(evidence: dict, reject_reason: str = "") -> str:
    """Map eligibility evidence stats to a structured reject code.

    Codes:
      ELIGIBLE         — tape has executable ticks (should not appear for rejected tapes)
      NO_OVERLAP       — depth_ok and edge_ok both seen but never simultaneously
      DEPTH_ONLY       — depth_ok ticks exist, but no edge_ok ticks
      EDGE_ONLY        — edge_ok ticks exist, but no depth_ok ticks
      NO_DEPTH_NO_EDGE — neither condition satisfied
      NO_EVENTS        — reject_reason indicates no events found
      NO_ASSETS        — reject_reason indicates asset IDs could not be determined
      UNKNOWN          — no evidence stats and no recognisable reject_reason substring

    Args:
        evidence:       The stats dict from EligibilityResult (may be empty).
        reject_reason:  The human-readable reject reason string.

    Returns:
        One of the code strings above.
    """
    # If evidence has scan stats, classify from them directly.
    if evidence:
        depth_ok = int(evidence.get("ticks_with_depth_ok", 0))
        edge_ok = int(evidence.get("ticks_with_edge_ok", 0))
        both = int(evidence.get("ticks_with_depth_and_edge", 0))

        if both > 0:
            return "ELIGIBLE"
        if depth_ok > 0 and edge_ok > 0:
            return "NO_OVERLAP"
        if depth_ok > 0:
            return "DEPTH_ONLY"
        if edge_ok > 0:
            return "EDGE_ONLY"
        return "NO_DEPTH_NO_EDGE"

    # No evidence — fall back to reject_reason substring matching.
    reason_lower = reject_reason.lower()
    if "no events" in reason_lower or "no events.jsonl" in reason_lower:
        return "NO_EVENTS"
    if "asset id" in reason_lower or "asset_id" in reason_lower:
        return "NO_ASSETS"
    return "UNKNOWN"


def enrich_tape_diagnostics(record: "TapeRecord") -> dict:
    """Compute a diagnostics dict for one TapeRecord.

    Reads evidence stats and regime/source fields already on the record,
    derives classification tiers and human-facing proxies, and returns a
    dict suitable for storing in ``TapeRecord.diagnostics`` and the manifest
    JSON.

    Fields returned:
        confidence_class:  GOLD / SILVER / BRONZE / UNKNOWN
        reject_code:       Structured reject code (or "ELIGIBLE")
        events_scanned:    Raw event count from evidence
        ticks_with_bbo:    Ticks where both legs had a quote
        best_edge_gap:     (required_edge_threshold - min_sum_ask_seen); positive
                           means the edge condition WAS triggered at some point;
                           None when not available
        max_depth_yes:     Peak best-ask size for the YES leg (shares)
        max_depth_no:      Peak best-ask size for the NO leg (shares)

    Args:
        record: A fully-populated TapeRecord (evidence may be empty dict).

    Returns:
        Dict of diagnostic fields.
    """
    ev = record.evidence
    events_scanned = int(ev.get("events_scanned", 0))
    ticks_with_bbo = int(ev.get("ticks_with_both_bbo", 0))

    confidence_class = classify_tape_confidence(
        record.recorded_by,
        events_scanned,
        ticks_with_bbo,
    )

    if record.eligible:
        reject_code = "ELIGIBLE"
    else:
        reject_code = classify_reject_code(ev, record.reject_reason)

    # Edge-gap proxy: positive when the complement sum was below threshold at least once.
    best_edge_gap: Optional[float] = None
    min_sum_ask_raw = ev.get("min_sum_ask_seen")
    req_edge_raw = ev.get("required_edge_threshold")
    if min_sum_ask_raw is not None and req_edge_raw is not None:
        try:
            min_sum_ask = float(min_sum_ask_raw)
            req_edge = float(req_edge_raw)
            best_edge_gap = round(req_edge - min_sum_ask, 6)
        except (TypeError, ValueError):
            pass

    # Depth proxies (stored as "min ask size seen" in the eligibility scanner,
    # which represents peak depth observed across the tape for each leg).
    max_depth_yes: Optional[float] = None
    max_depth_no: Optional[float] = None
    yes_raw = ev.get("min_yes_ask_size_seen")
    no_raw = ev.get("min_no_ask_size_seen")
    if yes_raw is not None:
        try:
            max_depth_yes = float(yes_raw)
        except (TypeError, ValueError):
            pass
    if no_raw is not None:
        try:
            max_depth_no = float(no_raw)
        except (TypeError, ValueError):
            pass

    return {
        "confidence_class": confidence_class,
        "reject_code": reject_code,
        "events_scanned": events_scanned,
        "ticks_with_bbo": ticks_with_bbo,
        "best_edge_gap": best_edge_gap,
        "max_depth_yes": max_depth_yes,
        "max_depth_no": max_depth_no,
    }


# ---------------------------------------------------------------------------
# Metadata readers
# ---------------------------------------------------------------------------


def _merge_market_metadata(dst: dict[str, Any], src: Mapping[str, Any]) -> dict[str, Any]:
    for src_key, dst_key in _SNAPSHOT_FIELD_MAP:
        value = src.get(src_key)
        if value not in (None, "") and dst_key not in dst:
            dst[dst_key] = value
    return dst


def _read_regime(tape_dir: Path) -> str:
    """Read regime label from tape metadata files.

    Search order:
      1. ``watch_meta.json`` → ``regime`` field
      2. ``prep_meta.json``  → ``regime`` field
      3. ``meta.json``       → shadow_context or quickrun_context → ``regime``
      4. Falls back to ``"unknown"``
    """
    for meta_name in ("watch_meta.json", "prep_meta.json"):
        meta_path = tape_dir / meta_name
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                regime = str(data.get("regime", "")).lower().strip()
                if regime in _VALID_REGIMES:
                    return regime
            except Exception:
                pass

    meta_path = tape_dir / "meta.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            for ctx_key in ("shadow_context", "quickrun_context"):
                ctx = data.get(ctx_key)
                if isinstance(ctx, dict):
                    regime = str(ctx.get("regime", "")).lower().strip()
                    if regime in _VALID_REGIMES:
                        return regime
        except Exception:
            pass

    return "unknown"


def _read_recorded_by(tape_dir: Path) -> str:
    """Infer the tool that recorded this tape from metadata files."""
    if (tape_dir / "watch_meta.json").exists():
        return "watch-arb-candidates"
    if (tape_dir / "prep_meta.json").exists():
        return "prepare-gate2"
    if (tape_dir / "meta.json").exists():
        try:
            data = json.loads((tape_dir / "meta.json").read_text(encoding="utf-8"))
            if "shadow_context" in data:
                return "simtrader-shadow"
            if "quickrun_context" in data:
                return "simtrader-quickrun"
        except Exception:
            pass
    return "unknown"


def _read_tape_market_metadata(tape_dir: Path) -> dict:
    """Read all available market metadata from tape files for regime derivation.

    Prefers additive ``market_snapshot`` blocks from ``watch_meta.json`` or
    ``prep_meta.json`` when present. This keeps regime/new-market derivation
    tied to capture-time evidence rather than later mutable metadata sources.

    When no snapshot exists, falls back to the legacy top-level fields in
    ``watch_meta.json`` / ``prep_meta.json``, then ``meta.json``
    shadow/quickrun context.

    Returns a dict suitable for passing to :func:`derive_tape_regime`.
    At minimum returns ``{"market_slug": slug_or_dir_name}``.
    """
    metadata: dict = {}
    snapshot_found = False

    # 1. Prefer additive snapshot metadata from watch/prep artifacts.
    for meta_name in ("watch_meta.json", "prep_meta.json"):
        meta_path = tape_dir / meta_name
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                snapshot = data.get("market_snapshot")
                if isinstance(snapshot, Mapping):
                    snapshot_found = True
                    _merge_market_metadata(metadata, snapshot)
                if isinstance(data, Mapping):
                    _merge_market_metadata(metadata, data)
            except Exception:
                pass

    # 2. Legacy fallback: meta.json shadow/quickrun context only when no snapshot exists.
    if not snapshot_found:
        meta_path = tape_dir / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                for ctx_key in ("shadow_context", "quickrun_context"):
                    ctx = meta.get(ctx_key)
                    if not isinstance(ctx, Mapping):
                        continue
                    if "market" in ctx and "market_slug" not in metadata:
                        metadata["market_slug"] = ctx["market"]
                    _merge_market_metadata(metadata, ctx)
                    break
            except Exception:
                pass

    # 3. Fallback: directory name as slug
    if "market_slug" not in metadata and "slug" not in metadata:
        metadata["market_slug"] = tape_dir.name

    return metadata


def _read_slug(tape_dir: Path) -> str:
    """Read the market slug from tape metadata; fall back to directory name."""
    for meta_name in ("watch_meta.json", "prep_meta.json"):
        meta_path = tape_dir / meta_name
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                slug = str(data.get("market_slug", "")).strip()
                if slug:
                    return slug
            except Exception:
                pass

    meta_path = tape_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for ctx_key in ("shadow_context", "quickrun_context"):
                ctx = meta.get(ctx_key)
                if isinstance(ctx, dict):
                    market = ctx.get("market") or ctx.get("market_slug")
                    if market:
                        return str(market)
        except Exception:
            pass

    return tape_dir.name


def _read_asset_ids(tape_dir: Path) -> tuple[str, str]:
    """Return (yes_id, no_id) from tape metadata; falls back to event stream."""
    for meta_name, yes_key, no_key in [
        ("watch_meta.json", "yes_asset_id", "no_asset_id"),
        ("prep_meta.json", "yes_asset_id", "no_asset_id"),
    ]:
        meta_path = tape_dir / meta_name
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                yes_id = str(data.get(yes_key, "")).strip()
                no_id = str(data.get(no_key, "")).strip()
                if yes_id and no_id:
                    return yes_id, no_id
            except Exception:
                pass

    meta_path = tape_dir / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            for ctx_key in ("shadow_context", "quickrun_context"):
                ctx = meta.get(ctx_key)
                if isinstance(ctx, dict):
                    yes_id = str(ctx.get("yes_asset_id", "") or "").strip()
                    no_id = str(ctx.get("no_asset_id", "") or "").strip()
                    if yes_id and no_id:
                        return yes_id, no_id
        except Exception:
            pass

    # Last resort: discover from event stream.
    events_path = tape_dir / "events.jsonl"
    if events_path.exists():
        seen: list[str] = []
        try:
            with open(events_path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        evt = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(evt, dict):
                        continue
                    et = evt.get("event_type", "")
                    if et == "book":
                        aid = str(evt.get("asset_id") or "")
                        if aid and aid not in seen:
                            seen.append(aid)
                    elif et == "price_change" and "price_changes" in evt:
                        for entry in evt.get("price_changes", []):
                            if isinstance(entry, dict):
                                aid = str(entry.get("asset_id") or "")
                                if aid and aid not in seen:
                                    seen.append(aid)
                    if len(seen) >= 2:
                        break
        except OSError:
            pass
        if len(seen) >= 2:
            return seen[0], seen[1]

    return "", ""


# ---------------------------------------------------------------------------
# Core: scan one tape
# ---------------------------------------------------------------------------


def scan_one_tape(
    tape_dir: Path,
    *,
    max_size: float = _DEFAULT_MAX_SIZE,
    buffer: float = _DEFAULT_BUFFER,
) -> TapeRecord:
    """Produce a TapeRecord for one tape directory.

    Eligibility invariant:
      ``eligible`` is True ONLY if ``executable_ticks > 0``.
      This is enforced explicitly after the eligibility check returns.
      Non-executable tapes are NEVER labeled eligible.

    Regime integrity:
      ``regime`` (backward compat) = ``final_regime`` = the authoritative regime
      for corpus counting.  ``derived_regime`` shows what the machine classifier
      concluded; ``operator_regime`` shows what the operator labeled;
      ``regime_mismatch`` is True when both are named and they disagree.
    """
    from packages.polymarket.simtrader.sweeps.eligibility import (
        check_binary_arb_tape_eligibility,
    )

    slug = _read_slug(tape_dir)
    operator_regime = _read_regime(tape_dir)
    recorded_by = _read_recorded_by(tape_dir)
    tape_metadata = _read_tape_market_metadata(tape_dir)

    # Compute regime integrity from shared classification logic.
    integrity = derive_tape_regime(
        tape_metadata,
        operator_regime=operator_regime,
        reference_time=tape_metadata.get("captured_at"),
    )

    events_path = tape_dir / "events.jsonl"
    if not events_path.exists():
        return TapeRecord(
            tape_dir=str(tape_dir),
            slug=slug,
            regime=integrity.final_regime,
            recorded_by=recorded_by,
            eligible=False,
            executable_ticks=0,
            reject_reason="no events.jsonl found in tape directory",
            derived_regime=integrity.derived_regime,
            operator_regime=integrity.operator_regime,
            final_regime=integrity.final_regime,
            regime_source=integrity.regime_source,
            regime_mismatch=integrity.regime_mismatch,
        )

    yes_id, no_id = _read_asset_ids(tape_dir)
    if not yes_id or not no_id:
        return TapeRecord(
            tape_dir=str(tape_dir),
            slug=slug,
            regime=integrity.final_regime,
            recorded_by=recorded_by,
            eligible=False,
            executable_ticks=0,
            reject_reason="could not determine YES/NO asset IDs from tape metadata",
            derived_regime=integrity.derived_regime,
            operator_regime=integrity.operator_regime,
            final_regime=integrity.final_regime,
            regime_source=integrity.regime_source,
            regime_mismatch=integrity.regime_mismatch,
        )

    cfg = {
        "yes_asset_id": yes_id,
        "no_asset_id": no_id,
        "max_size": str(max_size),
        "buffer": str(buffer),
    }
    try:
        result = check_binary_arb_tape_eligibility(events_path, cfg)
    except Exception as exc:
        return TapeRecord(
            tape_dir=str(tape_dir),
            slug=slug,
            regime=integrity.final_regime,
            recorded_by=recorded_by,
            eligible=False,
            executable_ticks=0,
            reject_reason=f"eligibility check error: {exc}",
            derived_regime=integrity.derived_regime,
            operator_regime=integrity.operator_regime,
            final_regime=integrity.final_regime,
            regime_source=integrity.regime_source,
            regime_mismatch=integrity.regime_mismatch,
        )

    executable_ticks = int(result.stats.get("ticks_with_depth_and_edge", 0))

    # Hard invariant: eligible iff executable_ticks > 0.
    # The eligibility check guarantees this; we enforce it explicitly to
    # ensure non-executable tapes are NEVER mislabeled eligible.
    eligible = result.eligible and executable_ticks > 0

    record = TapeRecord(
        tape_dir=str(tape_dir),
        slug=slug,
        regime=integrity.final_regime,
        recorded_by=recorded_by,
        eligible=eligible,
        executable_ticks=executable_ticks,
        reject_reason=result.reason if not eligible else "",
        evidence=result.stats,
        derived_regime=integrity.derived_regime,
        operator_regime=integrity.operator_regime,
        final_regime=integrity.final_regime,
        regime_source=integrity.regime_source,
        regime_mismatch=integrity.regime_mismatch,
    )
    record.diagnostics = enrich_tape_diagnostics(record)
    return record


# ---------------------------------------------------------------------------
# Core: scan tapes directory
# ---------------------------------------------------------------------------


def scan_tapes_dir(
    tapes_dir: Path,
    *,
    max_size: float = _DEFAULT_MAX_SIZE,
    buffer: float = _DEFAULT_BUFFER,
) -> list[TapeRecord]:
    """Scan all subdirectories under *tapes_dir* and return TapeRecords."""
    tape_dirs = sorted(p for p in tapes_dir.iterdir() if p.is_dir())
    logger.debug("Found %d directories under %s", len(tape_dirs), tapes_dir)

    records: list[TapeRecord] = []
    for td in tape_dirs:
        record = scan_one_tape(td, max_size=max_size, buffer=buffer)
        records.append(record)
        logger.debug(
            "Tape %s: eligible=%s executable_ticks=%d regime=%s",
            td.name, record.eligible, record.executable_ticks, record.regime,
        )
    return records


# ---------------------------------------------------------------------------
# Corpus summary
# ---------------------------------------------------------------------------


def build_corpus_summary(records: list[TapeRecord]) -> CorpusSummary:
    """Compute corpus-level coverage from a list of TapeRecords.

    Mixed-regime coverage is computed via the shared
    ``coverage_from_classified_regimes`` helper from ``regime_policy``
    using the authoritative ``final_regime`` from every classified tape.
    Eligibility stays a separate concern: it still controls
    ``eligible_count`` and ``gate2_eligible_tapes``, but it does not erase
    regime coverage evidence from classified ineligible tapes.
    """
    by_regime: dict[str, dict[str, int]] = {
        r: {"total": 0, "eligible": 0}
        for r in ("politics", "sports", "new_market", "unknown")
    }
    gate2_eligible_tapes: list[str] = []
    eligible_count = 0
    classified_final_regimes: list[str] = []

    for rec in records:
        # Use final_regime when populated (new records); fall back to regime
        # for legacy TapeRecord objects that don't have final_regime set.
        effective_regime = rec.final_regime if rec.final_regime else rec.regime
        regime_key = effective_regime if effective_regime in by_regime else "unknown"
        by_regime[regime_key]["total"] += 1
        classified_final_regimes.append(effective_regime)
        if rec.eligible:
            by_regime[regime_key]["eligible"] += 1
            eligible_count += 1
            gate2_eligible_tapes.append(rec.tape_dir)

    # Use shared regime policy helper for corpus coverage from all classified tapes.
    # coverage_from_classified_regimes only counts politics/sports/new_market.
    coverage = coverage_from_classified_regimes(classified_final_regimes)
    # mixed_regime_eligible remains a gate-oriented signal: there must be at
    # least one eligible tape, and the classified corpus must span at least
    # two named regimes.
    mixed_regime_eligible = eligible_count > 0 and len(coverage["covered_regimes"]) >= 2

    corpus_note = _corpus_note(eligible_count, coverage)

    return CorpusSummary(
        total_tapes=len(records),
        eligible_count=eligible_count,
        ineligible_count=len(records) - eligible_count,
        by_regime=by_regime,
        mixed_regime_eligible=mixed_regime_eligible,
        gate2_eligible_tapes=gate2_eligible_tapes,
        generated_at=datetime.now(timezone.utc).isoformat(),
        corpus_note=corpus_note,
        regime_coverage=coverage,
    )


def _corpus_note(
    eligible_count: int,
    coverage: Mapping[str, Any],
) -> str:
    """Human-readable corpus assessment for the operator."""
    if eligible_count == 0:
        return (
            "BLOCKED: No eligible tapes. Gate 2 requires at least one tape with "
            "executable_ticks > 0 (simultaneous depth_ok AND edge_ok). "
            "Silver/Bronze tapes contain only price_2min_guide events and lack L2 "
            "book data — the fill engine always rejects them with book_not_initialized. "
            "Only Gold-tier tapes (live WebSocket recordings via watch-arb-candidates "
            "or simtrader-shadow) can produce executable ticks. "
            "Run scan-gate2-candidates to find markets with edge signal, then capture "
            "Gold tapes with watch-arb-candidates."
        )

    missing_regimes = tuple(str(regime) for regime in coverage.get("missing_regimes") or ())
    if missing_regimes:
        return (
            f"PARTIAL: {eligible_count} eligible tape(s) found, but "
            "mixed-regime corpus is incomplete. "
            f"Missing classified tapes for: {', '.join(missing_regimes)}. "
            "Gate 3 validation requires classified tape coverage across "
            "politics, sports, and new_market."
        )

    return (
        f"OK: {eligible_count} eligible tape(s) found and the classified "
        "corpus covers all three required regimes "
        "(politics, sports, new_market). "
        "Proceed to Gate 2 sweep: python tools/gates/close_sweep_gate.py"
    )


# ---------------------------------------------------------------------------
# Manifest serialization
# ---------------------------------------------------------------------------


def manifest_to_dict(
    records: list[TapeRecord],
    summary: CorpusSummary,
    *,
    max_size: float,
    buffer: float,
) -> dict:
    """Serialize records and summary into a JSON-compatible dict."""
    return {
        "schema_version": "gate2_tape_manifest_v2",
        "generated_at": summary.generated_at,
        "strategy": "binary_complement_arb",
        "eligibility_params": {
            "max_size": max_size,
            "buffer": buffer,
            "threshold": round(1.0 - buffer, 6),
        },
        "corpus_summary": {
            "total_tapes": summary.total_tapes,
            "eligible_count": summary.eligible_count,
            "ineligible_count": summary.ineligible_count,
            "by_regime": summary.by_regime,
            "mixed_regime_eligible": summary.mixed_regime_eligible,
            "gate2_eligible_tapes": summary.gate2_eligible_tapes,
            "regime_coverage": summary.regime_coverage,
            "corpus_note": summary.corpus_note,
        },
        "tapes": [
            {
                "tape_dir": rec.tape_dir,
                "slug": rec.slug,
                "regime": rec.final_regime if rec.final_regime else rec.regime,
                "derived_regime": rec.derived_regime,
                "operator_regime": rec.operator_regime,
                "final_regime": rec.final_regime if rec.final_regime else rec.regime,
                "regime_source": rec.regime_source,
                "regime_mismatch": rec.regime_mismatch,
                "recorded_by": rec.recorded_by,
                "eligible": rec.eligible,
                "executable_ticks": rec.executable_ticks,
                "reject_reason": rec.reject_reason,
                "evidence": rec.evidence,
                "diagnostics": rec.diagnostics if rec.diagnostics else enrich_tape_diagnostics(rec),
            }
            for rec in records
        ],
    }


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

_COL_SLUG = 42
_COL_REGIME = 10
_COL_CONF = 4
_COL_STATUS = 11
_COL_CODE = 18
_COL_EVENTS = 7
_COL_BBO = 6
_COL_EXEC = 9
_COL_EDGE = 9
_COL_DEPTH = 12

# Abbreviations for confidence class in 4-char column
_CONF_ABBREV = {
    "GOLD": "GOLD",
    "SILVER": "SILV",
    "BRONZE": "BRNZ",
    "UNKNOWN": "UNKN",
}


def print_manifest_table(records: list[TapeRecord], summary: CorpusSummary) -> None:
    """Print a compact operator summary table to stdout.

    Columns:
      Tape/Slug | Regime | Conf | Status | Code | Events | BBO | ExecTicks | BestEdge | MaxDepth | Detail
    """
    header = (
        f"{'Tape/Slug':<{_COL_SLUG}} | "
        f"{'Regime':<{_COL_REGIME}} | "
        f"{'Conf':<{_COL_CONF}} | "
        f"{'Status':<{_COL_STATUS}} | "
        f"{'Code':<{_COL_CODE}} | "
        f"{'Events':>{_COL_EVENTS}} | "
        f"{'BBO':>{_COL_BBO}} | "
        f"{'ExecTicks':>{_COL_EXEC}} | "
        f"{'BestEdge':>{_COL_EDGE}} | "
        f"{'MaxDepth':>{_COL_DEPTH}} | "
        f"Detail"
    )
    sep = "-" * len(header)
    print(header)
    print(sep)

    for rec in records:
        diag = rec.diagnostics
        status = "ELIGIBLE" if rec.eligible else "INELIGIBLE"
        conf_raw = diag.get("confidence_class", "UNKNOWN")
        conf = _CONF_ABBREV.get(conf_raw, conf_raw[:4])
        code = diag.get("reject_code", "") if not rec.eligible else "ELIGIBLE"
        events = diag.get("events_scanned", 0)
        bbo = diag.get("ticks_with_bbo", 0)

        edge_gap = diag.get("best_edge_gap")
        if edge_gap is not None:
            edge_str = f"{edge_gap:+.4f}"
        else:
            edge_str = "N/A"

        yes_d = diag.get("max_depth_yes")
        no_d = diag.get("max_depth_no")
        if yes_d is not None and no_d is not None:
            depth_str = f"{yes_d:.0f}/{no_d:.0f}"
        else:
            depth_str = "N/A"

        detail = str(rec.tape_dir) if rec.eligible else rec.reject_reason[:50]
        slug_col = rec.slug[:_COL_SLUG]
        regime_col = rec.regime[:_COL_REGIME]

        print(
            f"{slug_col:<{_COL_SLUG}} | "
            f"{regime_col:<{_COL_REGIME}} | "
            f"{conf:<{_COL_CONF}} | "
            f"{status:<{_COL_STATUS}} | "
            f"{code:<{_COL_CODE}} | "
            f"{events:>{_COL_EVENTS}} | "
            f"{bbo:>{_COL_BBO}} | "
            f"{rec.executable_ticks:>{_COL_EXEC}} | "
            f"{edge_str:>{_COL_EDGE}} | "
            f"{depth_str:>{_COL_DEPTH}} | "
            f"{detail}"
        )

    print(sep)
    print(
        f"Total: {summary.total_tapes}  |  "
        f"Eligible: {summary.eligible_count}  |  "
        f"Ineligible: {summary.ineligible_count}"
    )
    print()
    print(f"Corpus note: {summary.corpus_note}")

    if summary.gate2_eligible_tapes:
        print()
        print("Gate 2 eligible tapes — proceed to sweep:")
        for td in summary.gate2_eligible_tapes:
            print(f"  python tools/gates/close_sweep_gate.py  # tape: {td}")


# ---------------------------------------------------------------------------
# Corpus quality breakdown
# ---------------------------------------------------------------------------


def print_corpus_quality_breakdown(
    records: list[TapeRecord],
    summary: CorpusSummary,
) -> None:
    """Print an aggregate corpus quality breakdown after the per-tape table.

    Outputs:
      1. Reject-code distribution table
      2. Confidence-tier distribution table
      3. Silver/Bronze tape structural warning (when corpus is blocked and such tapes exist)
      4. Operator next-action line
    """
    # 1. Reject-code distribution
    _REJECT_CODES = [
        "ELIGIBLE",
        "NO_OVERLAP",
        "DEPTH_ONLY",
        "EDGE_ONLY",
        "NO_DEPTH_NO_EDGE",
        "NO_EVENTS",
        "NO_ASSETS",
        "UNKNOWN",
    ]
    reject_counts: dict[str, int] = {code: 0 for code in _REJECT_CODES}
    for rec in records:
        diag = rec.diagnostics if rec.diagnostics else enrich_tape_diagnostics(rec)
        code = diag.get("reject_code", "UNKNOWN")
        if code not in reject_counts:
            reject_counts[code] = 0
        reject_counts[code] += 1

    print()
    print("Reject Code Distribution:")
    for code in _REJECT_CODES:
        count = reject_counts.get(code, 0)
        print(f"  {code:<18} {count}")

    # 2. Confidence-tier distribution
    _CONF_TIERS = ["GOLD", "SILVER", "BRONZE", "UNKNOWN"]
    conf_counts: dict[str, int] = {tier: 0 for tier in _CONF_TIERS}
    for rec in records:
        diag = rec.diagnostics if rec.diagnostics else enrich_tape_diagnostics(rec)
        tier = diag.get("confidence_class", "UNKNOWN")
        if tier not in conf_counts:
            conf_counts[tier] = 0
        conf_counts[tier] += 1

    print()
    print("Confidence Tier Distribution:")
    for tier in _CONF_TIERS:
        count = conf_counts.get(tier, 0)
        print(f"  {tier:<8} {count}")

    # 3. Silver/Bronze warning when corpus is blocked and such tapes exist
    silver_bronze_count = conf_counts.get("SILVER", 0) + conf_counts.get("BRONZE", 0)
    if summary.eligible_count == 0 and silver_bronze_count > 0:
        print()
        print("WARNING: Silver/Bronze tapes are structurally unusable for Gate 2.")
        print("Silver tapes contain only price_2min_guide events (2-minute price samples).")
        print("L2 book data is absent, so L2Book never initializes and the fill engine")
        print("always rejects with book_not_initialized. Only Gold-tier tapes (live")
        print("ws-recorded via watch-arb-candidates or simtrader-shadow) can produce")
        print("executable ticks. Capture Gold tapes using:")
        print("  python -m polytool scan-gate2-candidates --enrich --top 10")
        print("  python -m polytool watch-arb-candidates --slugs <top-candidates>")

    # 4. Operator next-action line
    print()
    if summary.eligible_count == 0:
        print(
            "NEXT: Capture Gold tapes for markets with edge signal. "
            "Run scan-gate2-candidates to find targets."
        )
    else:
        missing = list(summary.regime_coverage.get("missing_regimes") or [])
        if missing:
            print(
                f"NEXT: Capture tapes for missing regimes: {', '.join(missing)}."
            )
        else:
            print(
                "NEXT: Run Gate 2 sweep: python tools/gates/close_sweep_gate.py"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tape-manifest",
        description=(
            "Gate 2 tape acquisition manifest generator.\n\n"
            "Scans a tapes directory, checks eligibility on each tape, reads\n"
            "regime metadata, and emits a structured manifest JSON.\n\n"
            "Eligibility invariant: a tape is ONLY marked eligible when\n"
            "executable_ticks > 0 (depth_ok AND edge_ok simultaneously).\n"
            "Non-executable tapes are NEVER labeled eligible."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--tapes-dir",
        default=str(_DEFAULT_TAPES_DIR),
        metavar="DIR",
        help="Directory containing tape subdirectories (default: %(default)s).",
    )
    p.add_argument(
        "--out",
        default=None,
        metavar="PATH",
        help=f"Path to write manifest JSON (default: {_DEFAULT_OUT}).",
    )
    p.add_argument(
        "--max-size",
        type=float,
        default=_DEFAULT_MAX_SIZE,
        metavar="N",
        help="Required depth at best ask per leg in shares (default: %(default)s).",
    )
    p.add_argument(
        "--buffer",
        type=float,
        default=_DEFAULT_BUFFER,
        metavar="F",
        help="Edge buffer: entry when sum_ask < 1 - buffer (default: %(default)s).",
    )
    p.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return p


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entrypoint: python -m polytool tape-manifest [options]."""
    parser = build_parser()
    args = parser.parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    tapes_dir = Path(args.tapes_dir)
    if not tapes_dir.is_dir():
        print(f"Error: --tapes-dir '{tapes_dir}' is not a directory.", file=sys.stderr)
        return 1

    max_size: float = args.max_size
    buffer: float = args.buffer

    if max_size <= 0:
        print("Error: --max-size must be positive.", file=sys.stderr)
        return 1
    if not (0.0 < buffer < 1.0):
        print("Error: --buffer must be between 0 and 1.", file=sys.stderr)
        return 1

    print(
        f"[tape-manifest] Scanning {tapes_dir}  "
        f"max_size={max_size}  buffer={buffer}  threshold={1.0 - buffer:.4f}",
        file=sys.stderr,
    )

    records = scan_tapes_dir(tapes_dir, max_size=max_size, buffer=buffer)
    summary = build_corpus_summary(records)
    manifest = manifest_to_dict(records, summary, max_size=max_size, buffer=buffer)

    out_path = Path(args.out) if args.out else _DEFAULT_OUT
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"[tape-manifest] Manifest written: {out_path}", file=sys.stderr)

    print_manifest_table(records, summary)
    print_corpus_quality_breakdown(records, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
