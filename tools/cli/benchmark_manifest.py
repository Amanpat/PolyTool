"""Benchmark v1 tape manifest curation from local inventory.

Discovers locally recorded Gold tapes and reconstructed Silver tapes from the
canonical tape roots, classifies them into the roadmap benchmark buckets, and
either:

1. Writes ``config/benchmark_v1.tape_manifest`` plus a companion audit file
   when all quotas are satisfiable, or
2. Writes a machine-readable gap report and exits non-zero when inventory is
   insufficient.

The manifest is intentionally fixed-shape: a JSON array of 50 tape event-file
paths. The companion audit / gap files carry the richer provenance.
"""

from __future__ import annotations

import argparse
import heapq
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from packages.polymarket.market_selection.regime_policy import (
    POLITICS,
    SPORTS,
    classify_market_regime,
)

BENCHMARK_VERSION = "benchmark_v1"
MANIFEST_SCHEMA_VERSION = "benchmark_tape_manifest_v1"
AUDIT_SCHEMA_VERSION = "benchmark_tape_inventory_audit_v1"
GAP_SCHEMA_VERSION = "benchmark_tape_gap_report_v1"
BUCKET_ORDER = (
    "politics",
    "sports",
    "crypto",
    "near_resolution",
    "new_market",
)
QUOTAS: dict[str, int] = {
    "politics": 10,
    "sports": 15,
    "crypto": 10,
    "near_resolution": 10,
    "new_market": 5,
}
TIER_ORDER = {"gold": 2, "silver": 1}
TAIL_PRICE_THRESHOLD = 0.10
NEAR_RESOLUTION_MAX_HOURS = 24.0
NEW_MARKET_MAX_HOURS = 48.0
_CRYPTO_KEYWORDS = (
    "bitcoin",
    "btc",
    "crypto",
    "cryptocurrency",
    "doge",
    "dogecoin",
    "ethereum",
    "eth",
    "sol",
    "solana",
    "xrp",
)
_POLITICS_FALLBACK_KEYWORDS = (
    "biden",
    "deport",
    "deportation",
    "desantis",
    "harris",
    "immigration",
    "kamala",
    "tariff",
    "trump",
    "white house",
)
_TEXT_KEYS = (
    "slug",
    "market_slug",
    "title",
    "question",
    "category",
    "subcategory",
    "event_slug",
    "event_title",
    "tags",
)
_CREATED_AT_KEYS = (
    "created_at",
    "createdAt",
    "listed_at",
    "listedAt",
    "published_at",
    "publishedAt",
)
_CAPTURED_AT_KEYS = (
    "selected_at",
    "started_at",
    "generated_at",
    "window_start",
    "ended_at",
)
_AGE_HOURS_KEYS = ("age_hours", "ageHours")
_HOURS_TO_RESOLUTION_KEYS = ("hours_to_resolution", "hoursToResolution")
_RESOLUTION_TIME_KEYS = (
    "end_date_iso",
    "endDate",
    "end_date",
    "close_time",
    "closeTime",
    "closedTime",
    "resolution_time",
    "resolutionTime",
    "resolutionTimestamp",
)
_SLUG_KEYS = (
    "market_slug",
    "slug",
    "selected_slug",
    "market",
    "event_slug",
)
_YES_KEYS = ("yes_asset_id", "yes_token_id", "yes_id", "token_id")
_NO_KEYS = ("no_asset_id", "no_token_id", "no_id")


@dataclass
class TapeCandidate:
    tape_path: str
    tape_dir: str
    tier: str
    slug: str
    metadata_sources: list[str] = field(default_factory=list)
    category: str = ""
    question: str = ""
    title: str = ""
    event_count: int = 0
    primary_asset_id: str = ""
    price_sample_count: int = 0
    price_low: Optional[float] = None
    price_high: Optional[float] = None
    price_span: float = 0.0
    near_tail_observed: bool = False
    age_hours: Optional[float] = None
    hours_to_resolution: Optional[float] = None
    candidate_buckets: list[str] = field(default_factory=list)
    classification_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tape_path": self.tape_path,
            "tape_dir": self.tape_dir,
            "tier": self.tier,
            "slug": self.slug,
            "metadata_sources": list(self.metadata_sources),
            "category": self.category,
            "question": self.question,
            "title": self.title,
            "event_count": self.event_count,
            "primary_asset_id": self.primary_asset_id,
            "price_sample_count": self.price_sample_count,
            "price_low": self.price_low,
            "price_high": self.price_high,
            "price_span": round(self.price_span, 6),
            "near_tail_observed": self.near_tail_observed,
            "age_hours": self.age_hours,
            "hours_to_resolution": self.hours_to_resolution,
            "candidate_buckets": list(self.candidate_buckets),
            "classification_notes": list(self.classification_notes),
        }


@dataclass
class SkippedTape:
    tape_path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "tape_path": self.tape_path,
            "reason": self.reason,
        }


@dataclass
class SelectionResult:
    assignments: dict[str, list[TapeCandidate]]
    shortages: dict[str, int]
    candidate_counts: dict[str, int]

    @property
    def success(self) -> bool:
        return all(shortage == 0 for shortage in self.shortages.values())

    @property
    def selected_paths(self) -> list[str]:
        ordered: list[str] = []
        for bucket in BUCKET_ORDER:
            ordered.extend(candidate.tape_path for candidate in self.assignments[bucket])
        return ordered


@dataclass
class _Edge:
    to: int
    rev: int
    capacity: int
    cost: int


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_path(path: Path) -> str:
    resolved = path.resolve()
    repo_root = _repo_root().resolve()
    try:
        return resolved.relative_to(repo_root).as_posix()
    except ValueError:
        return str(resolved)


def _parse_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result != result:
        return None
    return result


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000.0
        try:
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        text = str(value).strip()
        if not text:
            return None
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            numeric = _parse_float(text)
            if numeric is None:
                return None
            if numeric > 1_000_000_000_000:
                numeric /= 1000.0
            try:
                dt = datetime.fromtimestamp(numeric, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_dir_timestamp(name: str) -> Optional[datetime]:
    token = name.split("_", 1)[0].strip()
    if len(token) < 16:
        return None
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y-%m-%dT%H-%M-%SZ"):
        try:
            return datetime.strptime(token, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _string_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        values: list[str] = []
        for key in ("label", "name", "slug", "title", "value"):
            values.extend(_string_values(value.get(key)))
        return values
    if isinstance(value, (list, tuple, set, frozenset)):
        values: list[str] = []
        for item in value:
            values.extend(_string_values(item))
        return values
    return [str(value)]


def _normalize_text(text: str) -> str:
    cleaned = []
    for ch in text.lower():
        cleaned.append(ch if ch.isalnum() else " ")
    return " ".join("".join(cleaned).split())


def _collect_text(metadata: dict[str, Any]) -> str:
    values: list[str] = []
    for key in _TEXT_KEYS:
        values.extend(_string_values(metadata.get(key)))
    return _normalize_text(" ".join(values))


def _first_text(metadata: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        values = _string_values(metadata.get(key))
        for value in values:
            text = str(value).strip()
            if text:
                return text
    return ""


def _first_float(metadata: dict[str, Any], keys: Iterable[str]) -> Optional[float]:
    for key in keys:
        parsed = _parse_float(metadata.get(key))
        if parsed is not None:
            return parsed
    return None


def _first_datetime(metadata: dict[str, Any], keys: Iterable[str]) -> Optional[datetime]:
    for key in keys:
        parsed = _parse_datetime(metadata.get(key))
        if parsed is not None:
            return parsed
    return None


def _merge_if_missing(target: dict[str, Any], source: dict[str, Any], keys: Iterable[str]) -> None:
    for key in keys:
        if key not in target and key in source and source.get(key) not in (None, ""):
            target[key] = source[key]


def _load_metadata(tape_dir: Path, tier: str) -> tuple[dict[str, Any], list[str]]:
    merged: dict[str, Any] = {}
    sources: list[str] = []
    candidate_files = (
        "market_meta.json",
        "watch_meta.json",
        "prep_meta.json",
        "meta.json",
        "silver_meta.json" if tier == "silver" else "",
    )
    keys = set(
        _TEXT_KEYS
        + _SLUG_KEYS
        + _YES_KEYS
        + _NO_KEYS
        + _CREATED_AT_KEYS
        + _CAPTURED_AT_KEYS
        + _AGE_HOURS_KEYS
        + _HOURS_TO_RESOLUTION_KEYS
        + _RESOLUTION_TIME_KEYS
        + ("event_count", "token_id", "window_start", "window_end", "generated_at")
    )

    for name in candidate_files:
        if not name:
            continue
        path = tape_dir / name
        payload = _read_json(path)
        if payload is None:
            continue
        sources.append(name)
        if name == "meta.json":
            for ctx_key in ("shadow_context", "quickrun_context"):
                ctx = payload.get(ctx_key)
                if isinstance(ctx, dict):
                    _merge_if_missing(merged, ctx, keys)
        _merge_if_missing(merged, payload, keys)

    if "slug" not in merged:
        merged["slug"] = _first_text(merged, _SLUG_KEYS)

    return merged, sources


def _best_book_price(levels: Any, *, side: str) -> Optional[float]:
    if not isinstance(levels, list):
        return None
    prices: list[float] = []
    for level in levels:
        if not isinstance(level, dict):
            continue
        price = _parse_float(level.get("price"))
        if price is not None:
            prices.append(price)
    if not prices:
        return None
    return min(prices) if side == "ask" else max(prices)


def _mid_price(best_bid: Optional[float], best_ask: Optional[float]) -> Optional[float]:
    if best_bid is None and best_ask is None:
        return None
    if best_bid is None:
        return best_ask
    if best_ask is None:
        return best_bid
    return (best_bid + best_ask) / 2.0


def _extract_primary_sample(event: dict[str, Any], primary_asset_id: str) -> tuple[str, list[float]]:
    if "price_changes" in event and isinstance(event.get("price_changes"), list):
        resolved_primary = primary_asset_id
        samples: list[float] = []
        for entry in event["price_changes"]:
            if not isinstance(entry, dict):
                continue
            asset_id = str(entry.get("asset_id") or "").strip()
            if not resolved_primary and asset_id:
                resolved_primary = asset_id
            if asset_id != resolved_primary or not asset_id:
                continue
            price = _mid_price(
                _parse_float(entry.get("best_bid")),
                _parse_float(entry.get("best_ask")),
            )
            if price is None:
                price = _parse_float(entry.get("price"))
            if price is not None:
                samples.append(price)
        return resolved_primary, samples

    asset_id = str(event.get("asset_id") or "").strip()
    resolved_primary = primary_asset_id or asset_id
    if asset_id and asset_id != resolved_primary:
        return resolved_primary, []

    price = _parse_float(event.get("price"))
    if price is None:
        price = _parse_float(event.get("last_trade_price"))
    if price is None:
        price = _mid_price(
            _best_book_price(event.get("bids"), side="bid"),
            _best_book_price(event.get("asks"), side="ask"),
        )
    if price is None:
        price = _mid_price(
            _parse_float(event.get("best_bid")),
            _parse_float(event.get("best_ask")),
        )
    return resolved_primary, ([] if price is None else [price])


def _scan_event_metrics(events_path: Path, primary_asset_hint: str) -> tuple[int, str, int, Optional[float], Optional[float]]:
    event_count = 0
    primary_asset_id = primary_asset_hint
    sample_count = 0
    price_low: Optional[float] = None
    price_high: Optional[float] = None

    with events_path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            event_count += 1
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            primary_asset_id, samples = _extract_primary_sample(event, primary_asset_id)
            for sample in samples:
                sample_count += 1
                if price_low is None or sample < price_low:
                    price_low = sample
                if price_high is None or sample > price_high:
                    price_high = sample

    return event_count, primary_asset_id, sample_count, price_low, price_high


def _tier_from_events_path(events_path: Path) -> Optional[str]:
    if events_path.name == "events.jsonl":
        return "gold"
    if events_path.name == "silver_events.jsonl":
        return "silver"
    return None


def _analyze_events_path(events_path: Path, *, tier: Optional[str] = None) -> TapeCandidate | SkippedTape:
    detected_tier = tier or _tier_from_events_path(events_path)
    normalized = _normalize_path(events_path)

    if detected_tier is None:
        return SkippedTape(
            tape_path=normalized,
            reason="unrecognized tape filename (expected events.jsonl or silver_events.jsonl)",
        )
    if not events_path.exists():
        return SkippedTape(
            tape_path=normalized,
            reason="tape file does not exist",
        )

    tape_dir = events_path.parent
    metadata, metadata_sources = _load_metadata(tape_dir, detected_tier)
    yes_keys = _YES_KEYS if detected_tier == "gold" else ("token_id",) + _YES_KEYS
    primary_hint = _first_text(metadata, yes_keys)
    try:
        event_count, primary_asset_id, sample_count, price_low, price_high = _scan_event_metrics(
            events_path,
            primary_hint,
        )
    except OSError as exc:
        return SkippedTape(tape_path=normalized, reason=f"could not read tape file: {exc}")

    if event_count <= 0:
        return SkippedTape(tape_path=normalized, reason="tape file is empty")

    return _classify_candidate(
        metadata,
        tier=detected_tier,
        tape_path=normalized,
        tape_dir=_normalize_path(tape_dir),
        metadata_sources=metadata_sources,
        event_count=event_count,
        primary_asset_id=primary_asset_id,
        price_sample_count=sample_count,
        price_low=price_low,
        price_high=price_high,
    )


def _discover_event_files(root: Path) -> Iterable[tuple[Path, str]]:
    if not root.exists():
        return []
    seen: set[Path] = set()
    discovered: list[tuple[Path, str]] = []
    for pattern, tier in (("events.jsonl", "gold"), ("silver_events.jsonl", "silver")):
        for path in sorted(root.rglob(pattern)):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            discovered.append((path, tier))
    return discovered


def discover_candidates_from_paths(event_paths: Iterable[Path]) -> tuple[list[TapeCandidate], list[SkippedTape]]:
    candidates: list[TapeCandidate] = []
    skipped: list[SkippedTape] = []
    seen: set[str] = set()

    for raw_path in event_paths:
        events_path = Path(raw_path)
        normalized = _normalize_path(events_path)
        if normalized in seen:
            continue
        seen.add(normalized)

        analyzed = _analyze_events_path(events_path)
        if isinstance(analyzed, SkippedTape):
            skipped.append(analyzed)
        else:
            candidates.append(analyzed)

    candidates.sort(key=lambda candidate: candidate.tape_path)
    skipped.sort(key=lambda item: item.tape_path)
    return candidates, skipped


def default_inventory_roots() -> list[Path]:
    artifacts_root = Path(os.getenv("POLYTOOL_ARTIFACTS_ROOT", "artifacts"))
    roots = [
        artifacts_root / "simtrader" / "tapes",
        artifacts_root / "silver",
    ]
    external_root = Path(os.getenv("POLYTOOL_DATA_ROOT", r"D:\PolyToolData")) / "tapes"
    if external_root.exists():
        roots.append(external_root)
    deduped: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root.resolve()) if root.exists() else str(root)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(root)
    return deduped


def _classify_candidate(
    metadata: dict[str, Any],
    *,
    tier: str,
    tape_path: str,
    tape_dir: str,
    metadata_sources: list[str],
    event_count: int,
    primary_asset_id: str,
    price_sample_count: int,
    price_low: Optional[float],
    price_high: Optional[float],
) -> TapeCandidate:
    slug = _first_text(metadata, _SLUG_KEYS) or Path(tape_dir).name
    category = _first_text(metadata, ("category",))
    question = _first_text(metadata, ("question",))
    title = _first_text(metadata, ("title", "event_title"))

    captured_at = _first_datetime(metadata, _CAPTURED_AT_KEYS)
    if captured_at is None:
        captured_at = _parse_dir_timestamp(Path(tape_dir).name)
    created_at = _first_datetime(metadata, _CREATED_AT_KEYS)
    age_hours = _first_float(metadata, _AGE_HOURS_KEYS)
    if age_hours is None and created_at is not None and captured_at is not None:
        delta_hours = (captured_at - created_at).total_seconds() / 3600.0
        if delta_hours >= 0.0:
            age_hours = delta_hours

    hours_to_resolution = _first_float(metadata, _HOURS_TO_RESOLUTION_KEYS)
    if hours_to_resolution is None:
        resolution_dt = _first_datetime(metadata, _RESOLUTION_TIME_KEYS)
        if resolution_dt is not None and captured_at is not None:
            delta_hours = (resolution_dt - captured_at).total_seconds() / 3600.0
            if delta_hours >= 0.0:
                hours_to_resolution = delta_hours

    price_span = 0.0
    if price_low is not None and price_high is not None:
        price_span = max(price_high - price_low, 0.0)
    near_tail = (
        (price_low is not None and price_low <= TAIL_PRICE_THRESHOLD)
        or (price_high is not None and price_high >= 1.0 - TAIL_PRICE_THRESHOLD)
    )

    market_regime = classify_market_regime(
        metadata,
        reference_time=captured_at,
        new_market_max_age_hours=NEW_MARKET_MAX_HOURS,
    )
    text = _collect_text(metadata)
    candidate_buckets: list[str] = []
    notes: list[str] = []

    if market_regime == POLITICS:
        candidate_buckets.append("politics")
        notes.append("politics via regime classifier")
    if market_regime == SPORTS:
        candidate_buckets.append("sports")
        notes.append("sports via regime classifier")
    if market_regime not in (POLITICS, SPORTS) and any(keyword in text for keyword in _POLITICS_FALLBACK_KEYWORDS):
        candidate_buckets.append("politics")
        notes.append("politics via fallback keywords")
    if any(keyword in text for keyword in _CRYPTO_KEYWORDS):
        candidate_buckets.append("crypto")
        notes.append("crypto via metadata keywords")

    if age_hours is not None and 0.0 <= age_hours < NEW_MARKET_MAX_HOURS:
        candidate_buckets.append("new_market")
        notes.append(f"new_market via age_hours={age_hours:.2f}")

    if hours_to_resolution is not None and 0.0 <= hours_to_resolution <= NEAR_RESOLUTION_MAX_HOURS:
        candidate_buckets.append("near_resolution")
        notes.append(f"near_resolution via hours_to_resolution={hours_to_resolution:.2f}")
    elif near_tail:
        candidate_buckets.append("near_resolution")
        notes.append("near_resolution via price-tail inference")

    candidate_buckets = [bucket for bucket in BUCKET_ORDER if bucket in set(candidate_buckets)]

    return TapeCandidate(
        tape_path=tape_path,
        tape_dir=tape_dir,
        tier=tier,
        slug=slug,
        metadata_sources=list(metadata_sources),
        category=category,
        question=question,
        title=title,
        event_count=event_count,
        primary_asset_id=primary_asset_id,
        price_sample_count=price_sample_count,
        price_low=price_low,
        price_high=price_high,
        price_span=price_span,
        near_tail_observed=near_tail,
        age_hours=age_hours,
        hours_to_resolution=hours_to_resolution,
        candidate_buckets=candidate_buckets,
        classification_notes=notes,
    )


def discover_inventory(roots: Iterable[Path]) -> tuple[list[TapeCandidate], list[SkippedTape]]:
    candidates: list[TapeCandidate] = []
    skipped: list[SkippedTape] = []
    seen: set[str] = set()

    for root in roots:
        for events_path, tier in _discover_event_files(root):
            normalized = _normalize_path(events_path)
            if normalized in seen:
                continue
            seen.add(normalized)
            analyzed = _analyze_events_path(events_path, tier=tier)
            if isinstance(analyzed, SkippedTape):
                skipped.append(analyzed)
            else:
                candidates.append(analyzed)

    candidates.sort(key=lambda candidate: candidate.tape_path)
    skipped.sort(key=lambda item: item.tape_path)
    return candidates, skipped


def _bucket_sort_key(bucket: str, candidate: TapeCandidate) -> tuple[Any, ...]:
    tier_priority = -TIER_ORDER.get(candidate.tier, 0)
    event_priority = -candidate.event_count
    span_priority = -round(candidate.price_span, 6)

    if bucket == "politics":
        return (
            span_priority,
            tier_priority,
            event_priority,
            candidate.tape_path,
        )
    if bucket == "sports":
        return (
            tier_priority,
            event_priority,
            span_priority,
            candidate.tape_path,
        )
    if bucket == "crypto":
        return (
            tier_priority,
            span_priority,
            event_priority,
            candidate.tape_path,
        )
    if bucket == "near_resolution":
        return (
            0 if candidate.hours_to_resolution is not None else 1,
            candidate.hours_to_resolution if candidate.hours_to_resolution is not None else 1e12,
            0 if candidate.near_tail_observed else 1,
            tier_priority,
            event_priority,
            candidate.tape_path,
        )
    if bucket == "new_market":
        return (
            0 if candidate.age_hours is not None else 1,
            candidate.age_hours if candidate.age_hours is not None else 1e12,
            tier_priority,
            event_priority,
            candidate.tape_path,
        )
    raise ValueError(f"Unknown bucket {bucket!r}")


def _add_edge(graph: list[list[_Edge]], src: int, dst: int, capacity: int, cost: int) -> None:
    graph[src].append(_Edge(to=dst, rev=len(graph[dst]), capacity=capacity, cost=cost))
    graph[dst].append(_Edge(to=src, rev=len(graph[src]) - 1, capacity=0, cost=-cost))


def _min_cost_max_flow(
    graph: list[list[_Edge]],
    *,
    source: int,
    sink: int,
    max_flow: int,
) -> int:
    node_count = len(graph)
    flow = 0
    potential = [0] * node_count

    while flow < max_flow:
        dist = [10**18] * node_count
        prev_node = [-1] * node_count
        prev_edge = [-1] * node_count
        dist[source] = 0
        heap: list[tuple[int, int]] = [(0, source)]

        while heap:
            current_dist, node = heapq.heappop(heap)
            if current_dist != dist[node]:
                continue
            for edge_index, edge in enumerate(graph[node]):
                if edge.capacity <= 0:
                    continue
                next_dist = current_dist + edge.cost + potential[node] - potential[edge.to]
                if next_dist < dist[edge.to]:
                    dist[edge.to] = next_dist
                    prev_node[edge.to] = node
                    prev_edge[edge.to] = edge_index
                    heapq.heappush(heap, (next_dist, edge.to))

        if dist[sink] == 10**18:
            break

        for node in range(node_count):
            if dist[node] < 10**18:
                potential[node] += dist[node]

        augment = max_flow - flow
        node = sink
        while node != source:
            edge = graph[prev_node[node]][prev_edge[node]]
            augment = min(augment, edge.capacity)
            node = prev_node[node]

        node = sink
        while node != source:
            edge = graph[prev_node[node]][prev_edge[node]]
            edge.capacity -= augment
            reverse = graph[node][edge.rev]
            reverse.capacity += augment
            node = prev_node[node]

        flow += augment

    return flow


def select_manifest(
    candidates: list[TapeCandidate],
    *,
    quotas: dict[str, int] = QUOTAS,
) -> SelectionResult:
    ordered_by_bucket: dict[str, list[TapeCandidate]] = {}
    candidate_counts: dict[str, int] = {}
    candidate_index = {candidate.tape_path: idx for idx, candidate in enumerate(candidates)}

    for bucket in BUCKET_ORDER:
        bucket_candidates = [
            candidate for candidate in candidates
            if bucket in candidate.candidate_buckets
        ]
        bucket_candidates.sort(key=lambda candidate: _bucket_sort_key(bucket, candidate))
        ordered_by_bucket[bucket] = bucket_candidates
        candidate_counts[bucket] = len(bucket_candidates)

    bucket_nodes = {bucket: idx + 1 for idx, bucket in enumerate(BUCKET_ORDER)}
    tape_offset = len(BUCKET_ORDER) + 1
    sink = tape_offset + len(candidates)
    graph: list[list[_Edge]] = [[] for _ in range(sink + 1)]

    for bucket in BUCKET_ORDER:
        _add_edge(graph, 0, bucket_nodes[bucket], quotas[bucket], 0)
        for rank, candidate in enumerate(ordered_by_bucket[bucket]):
            tape_node = tape_offset + candidate_index[candidate.tape_path]
            _add_edge(graph, bucket_nodes[bucket], tape_node, 1, rank)

    for idx in range(len(candidates)):
        _add_edge(graph, tape_offset + idx, sink, 1, 0)

    _min_cost_max_flow(
        graph,
        source=0,
        sink=sink,
        max_flow=sum(quotas.values()),
    )

    assignments: dict[str, list[TapeCandidate]] = {bucket: [] for bucket in BUCKET_ORDER}
    shortages: dict[str, int] = {}

    for bucket in BUCKET_ORDER:
        source_edge = next(edge for edge in graph[0] if edge.to == bucket_nodes[bucket])
        shortages[bucket] = source_edge.capacity
        bucket_assignments: list[TapeCandidate] = []
        for edge in graph[bucket_nodes[bucket]]:
            if edge.to < tape_offset or edge.to >= sink:
                continue
            reverse = graph[edge.to][edge.rev]
            if reverse.capacity > 0:
                bucket_assignments.append(candidates[edge.to - tape_offset])
        bucket_assignments.sort(key=lambda candidate: _bucket_sort_key(bucket, candidate))
        assignments[bucket] = bucket_assignments

    return SelectionResult(
        assignments=assignments,
        shortages=shortages,
        candidate_counts=candidate_counts,
    )


def _tier_counts(candidates: Iterable[TapeCandidate]) -> dict[str, int]:
    counts = {"gold": 0, "silver": 0}
    for candidate in candidates:
        counts[candidate.tier] = counts.get(candidate.tier, 0) + 1
    return counts


def _bucket_summary(
    candidates: list[TapeCandidate],
    selection: SelectionResult,
    quotas: dict[str, int],
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for bucket in BUCKET_ORDER:
        candidate_bucket = [candidate for candidate in candidates if bucket in candidate.candidate_buckets]
        selected_bucket = selection.assignments[bucket]
        summary[bucket] = {
            "quota": quotas[bucket],
            "candidate_count": selection.candidate_counts[bucket],
            "selected_count": len(selected_bucket),
            "shortage": selection.shortages[bucket],
            "candidate_by_tier": _tier_counts(candidate_bucket),
            "selected_by_tier": _tier_counts(selected_bucket),
        }
    return summary


def build_audit_payload(
    *,
    roots: Iterable[Path],
    candidates: list[TapeCandidate],
    skipped: list[SkippedTape],
    selection: SelectionResult,
    quotas: dict[str, int] = QUOTAS,
) -> dict[str, Any]:
    selected_candidates = [
        candidate
        for bucket in BUCKET_ORDER
        for candidate in selection.assignments[bucket]
    ]
    return {
        "schema_version": AUDIT_SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": _utcnow(),
        "inventory_roots": [_normalize_path(root) for root in roots],
        "discovered_count": len(candidates),
        "skipped_count": len(skipped),
        "selected_count": len(selected_candidates),
        "inventory_by_tier": _tier_counts(candidates),
        "selected_by_tier": _tier_counts(selected_candidates),
        "bucket_summary": _bucket_summary(candidates, selection, quotas),
        "selected_assignments": {
            bucket: [candidate.to_dict() for candidate in selection.assignments[bucket]]
            for bucket in BUCKET_ORDER
        },
        "discovered_tapes": [candidate.to_dict() for candidate in candidates],
        "skipped_tapes": [item.to_dict() for item in skipped],
    }


def build_gap_payload(
    *,
    roots: Iterable[Path],
    candidates: list[TapeCandidate],
    skipped: list[SkippedTape],
    selection: SelectionResult,
    manifest_path: Path,
    quotas: dict[str, int] = QUOTAS,
) -> dict[str, Any]:
    selected_candidates = [
        candidate
        for bucket in BUCKET_ORDER
        for candidate in selection.assignments[bucket]
    ]
    return {
        "schema_version": GAP_SCHEMA_VERSION,
        "benchmark_version": BENCHMARK_VERSION,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "generated_at": _utcnow(),
        "manifest_path": _normalize_path(manifest_path),
        "manifest_exists": manifest_path.exists(),
        "inventory_roots": [_normalize_path(root) for root in roots],
        "required_total": sum(quotas.values()),
        "selected_total": len(selected_candidates),
        "shortages_by_bucket": dict(selection.shortages),
        "inventory_by_tier": _tier_counts(candidates),
        "selected_by_tier": _tier_counts(selected_candidates),
        "bucket_summary": _bucket_summary(candidates, selection, quotas),
        "selected_assignments": {
            bucket: [candidate.to_dict() for candidate in selection.assignments[bucket]]
            for bucket in BUCKET_ORDER
        },
        "discovered_tapes": [candidate.to_dict() for candidate in candidates],
        "skipped_tapes": [item.to_dict() for item in skipped],
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_manifest(path: Path, selected_paths: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(selected_paths, indent=2) + "\n", encoding="utf-8")


def _build_build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark-manifest",
        description=(
            "Audit local tape inventory and build config/benchmark_v1.tape_manifest "
            "when all roadmap quotas are satisfiable. Once benchmark_v1 exists, "
            "the command treats it as frozen and will validate/verify the lock "
            "instead of rewriting it."
        ),
        epilog=(
            "Validation: benchmark-manifest validate --manifest "
            "config/benchmark_v1.tape_manifest"
        ),
    )
    parser.add_argument(
        "--root",
        action="append",
        default=None,
        metavar="DIR",
        help="Inventory root to scan. Repeatable. Defaults to canonical local roots.",
    )
    parser.add_argument(
        "--manifest-out",
        default=str(Path("config") / "benchmark_v1.tape_manifest"),
        metavar="PATH",
        help="Manifest path to write on success.",
    )
    parser.add_argument(
        "--audit-out",
        default=str(Path("config") / "benchmark_v1.audit.json"),
        metavar="PATH",
        help="Audit artifact path to write on success.",
    )
    parser.add_argument(
        "--gap-out",
        default=str(Path("config") / "benchmark_v1.gap_report.json"),
        metavar="PATH",
        help="Gap report path to write on shortage.",
    )
    parser.add_argument(
        "--lock-out",
        default=None,
        metavar="PATH",
        help=(
            "Freeze-lock path to write on success. Defaults to the manifest-derived "
            "benchmark_v1 lock path."
        ),
    )
    return parser


def _build_validate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark-manifest validate",
        description=(
            "Validate an existing benchmark manifest against the roadmap contract, "
            "and optionally write or verify the freeze lock."
        ),
    )
    parser.add_argument(
        "--manifest",
        default=str(Path("config") / "benchmark_v1.tape_manifest"),
        metavar="PATH",
        help="Manifest path to validate.",
    )
    parser.add_argument(
        "--lock-path",
        default=None,
        metavar="PATH",
        help=(
            "Lock path to verify or write. Defaults to the manifest-derived "
            "benchmark_v1 lock path."
        ),
    )
    parser.add_argument(
        "--write-lock",
        action="store_true",
        help="Write the lock file after successful validation.",
    )
    return parser


def _resolve_lock_path(manifest_path: Path, lock_path: Optional[str]) -> Path:
    from packages.polymarket.benchmark_manifest_contract import (
        default_lock_path_for_manifest,
    )

    if lock_path:
        return Path(lock_path)
    return default_lock_path_for_manifest(manifest_path)


def _run_build(argv: Optional[list[str]] = None) -> int:
    from packages.polymarket.benchmark_manifest_contract import (
        BenchmarkManifestValidationError,
        validate_benchmark_manifest,
        write_benchmark_manifest_lock,
    )

    parser = _build_build_parser()
    args = parser.parse_args(argv)

    roots = [Path(value) for value in args.root] if args.root else default_inventory_roots()
    manifest_out = Path(args.manifest_out)
    audit_out = Path(args.audit_out)
    gap_out = Path(args.gap_out)
    lock_out = _resolve_lock_path(manifest_out, args.lock_out)

    if manifest_out.exists() or lock_out.exists():
        if not manifest_out.exists():
            print(
                "[benchmark-manifest] freeze lock exists but manifest is missing: "
                f"{lock_out}",
                file=sys.stderr,
            )
            return 2
        try:
            validation = validate_benchmark_manifest(
                manifest_out,
                lock_path=lock_out if lock_out.exists() else None,
            )
        except BenchmarkManifestValidationError as exc:
            print(
                f"[benchmark-manifest] existing manifest is invalid: "
                f"{_normalize_path(manifest_out)}",
                file=sys.stderr,
            )
            for issue in exc.issues:
                print(f"  - {issue}", file=sys.stderr)
            return 2

        if not lock_out.exists():
            write_benchmark_manifest_lock(lock_out, validation)
            print(f"[benchmark-manifest] manifest already frozen: {manifest_out}")
            print(f"[benchmark-manifest] lock written: {lock_out}")
            return 0

        print(f"[benchmark-manifest] manifest already frozen: {manifest_out}")
        print(f"[benchmark-manifest] lock verified: {lock_out}")
        return 0

    candidates, skipped = discover_inventory(roots)
    selection = select_manifest(candidates)

    if selection.success:
        _write_manifest(manifest_out, selection.selected_paths)
        _write_json(
            audit_out,
            build_audit_payload(
                roots=roots,
                candidates=candidates,
                skipped=skipped,
                selection=selection,
            ),
        )
        validation = validate_benchmark_manifest(manifest_out)
        write_benchmark_manifest_lock(lock_out, validation)
        if gap_out.exists():
            gap_out.unlink()
        print(
            f"[benchmark-manifest] manifest written: {manifest_out} "
            f"({len(selection.selected_paths)} paths)",
        )
        print(f"[benchmark-manifest] audit written: {audit_out}")
        print(f"[benchmark-manifest] lock written: {lock_out}")
        return 0

    _write_json(
        gap_out,
        build_gap_payload(
            roots=roots,
            candidates=candidates,
            skipped=skipped,
            selection=selection,
            manifest_path=manifest_out,
        ),
    )
    shortages = ", ".join(
        f"{bucket}={selection.shortages[bucket]}"
        for bucket in BUCKET_ORDER
        if selection.shortages[bucket] > 0
    )
    print(f"[benchmark-manifest] blocked: wrote gap report {gap_out}", file=sys.stderr)
    print(f"[benchmark-manifest] shortages: {shortages}", file=sys.stderr)
    return 2


def _run_validate(argv: Optional[list[str]] = None) -> int:
    from packages.polymarket.benchmark_manifest_contract import (
        BenchmarkManifestValidationError,
        validate_benchmark_manifest,
        write_benchmark_manifest_lock,
    )

    parser = _build_validate_parser()
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    lock_path = _resolve_lock_path(manifest_path, args.lock_path)

    try:
        validation = validate_benchmark_manifest(
            manifest_path,
            lock_path=lock_path if lock_path.exists() else None,
        )
    except BenchmarkManifestValidationError as exc:
        print(
            f"[benchmark-manifest] invalid manifest: {_normalize_path(Path(args.manifest))}",
            file=sys.stderr,
        )
        for issue in exc.issues:
            print(f"  - {issue}", file=sys.stderr)
        return 2

    if args.write_lock:
        write_benchmark_manifest_lock(lock_path, validation)
        lock_message = f"written: {lock_path}"
    elif lock_path.exists():
        lock_message = f"verified: {lock_path}"
    else:
        lock_message = f"not present: {lock_path}"

    bucket_counts = ", ".join(
        f"{bucket}={validation.bucket_counts[bucket]}"
        for bucket in BUCKET_ORDER
    )
    print(f"[benchmark-manifest] valid: {manifest_path}")
    print(f"[benchmark-manifest] bucket counts: {bucket_counts}")
    print(f"[benchmark-manifest] manifest sha256: {validation.manifest_sha256}")
    print(f"[benchmark-manifest] lock {lock_message}")
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if argv and argv[0] == "validate":
        return _run_validate(argv[1:])
    return _run_build(argv)


if __name__ == "__main__":
    raise SystemExit(main())
