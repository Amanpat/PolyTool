"""Helpers for consistent human-readable SimTrader display names."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping

_SHORT_TS_RE = re.compile(r"(20\d{6}T\d{6}Z)")


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _parse_utc_datetime(raw: Any) -> datetime | None:
    if isinstance(raw, datetime):
        dt = raw
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    text = _as_text(raw)
    if text is None:
        return None

    short_match = _SHORT_TS_RE.search(text)
    if short_match is not None:
        short_ts = short_match.group(1)
        try:
            return datetime.strptime(short_ts, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            pass

    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_timestamp_short(timestamp: Any, fallback_id: str | None = None) -> str:
    dt = _parse_utc_datetime(timestamp)
    if dt is None and fallback_id is not None:
        dt = _parse_utc_datetime(fallback_id)
    if dt is None:
        return "unknown-time"
    return dt.strftime("%Y-%m-%d %H:%MZ")


def build_display_name(
    *,
    kind: str,
    timestamp: Any,
    fallback_id: str | None = None,
    market_slug: str | None = None,
    strategy: str | None = None,
    strategy_preset: str | None = None,
) -> str:
    kind_text = (_as_text(kind) or "run").lower()
    parts = [_format_timestamp_short(timestamp, fallback_id=fallback_id), kind_text]

    slug_text = _as_text(market_slug)
    if slug_text is not None:
        parts.append(f"market={slug_text}")

    strategy_text = _as_text(strategy)
    if strategy_text is not None:
        parts.append(f"strategy={strategy_text}")

    preset_text = _as_text(strategy_preset)
    if preset_text is not None:
        parts.append(f"preset={preset_text}")

    return " | ".join(parts)


def _market_slug_from_run_manifest(manifest: Mapping[str, Any]) -> str | None:
    direct_slug = _as_text(manifest.get("market_slug"))
    if direct_slug is not None:
        return direct_slug

    market_context = manifest.get("market_context")
    if isinstance(market_context, Mapping):
        context_slug = _as_text(market_context.get("market_slug"))
        if context_slug is not None:
            return context_slug

    for context_key in ("quickrun_context", "shadow_context"):
        context = manifest.get(context_key)
        if not isinstance(context, Mapping):
            continue
        selected_slug = _as_text(context.get("selected_slug"))
        if selected_slug is not None:
            return selected_slug
    return None


def derive_run_display_name(
    manifest: Mapping[str, Any],
    *,
    artifact_id: str | None = None,
    default_kind: str | None = None,
) -> str:
    mode = (_as_text(manifest.get("mode")) or "").lower()
    command = (_as_text(manifest.get("command")) or "").lower()
    if default_kind is not None:
        kind = default_kind
    elif mode == "shadow" or command.startswith("simtrader shadow"):
        kind = "shadow"
    elif mode == "ondemand" or command.startswith("simtrader ondemand"):
        kind = "ondemand"
    elif _as_text(manifest.get("session_id")) is not None and _as_text(
        manifest.get("run_id")
    ) is None:
        kind = "ondemand"
    else:
        kind = "run"

    run_id = _as_text(manifest.get("run_id")) or _as_text(manifest.get("session_id"))
    fallback_id = run_id or _as_text(artifact_id)
    timestamp = (
        _as_text(manifest.get("started_at"))
        or _as_text(manifest.get("created_at"))
        or _as_text(manifest.get("ended_at"))
    )
    market_slug = _market_slug_from_run_manifest(manifest)
    strategy = _as_text(manifest.get("strategy"))
    strategy_preset = _as_text(manifest.get("strategy_preset"))
    return build_display_name(
        kind=kind,
        timestamp=timestamp,
        fallback_id=fallback_id,
        market_slug=market_slug,
        strategy=strategy,
        strategy_preset=strategy_preset,
    )


def derive_sweep_display_name(
    manifest: Mapping[str, Any],
    *,
    artifact_id: str | None = None,
) -> str:
    sweep_id = _as_text(manifest.get("sweep_id")) or _as_text(artifact_id)
    quickrun_context = (
        manifest.get("quickrun_context")
        if isinstance(manifest.get("quickrun_context"), Mapping)
        else {}
    )
    timestamp = (
        _as_text(manifest.get("created_at"))
        or _as_text(quickrun_context.get("selected_at"))
    )
    market_slug = _as_text(manifest.get("market_slug")) or _as_text(
        quickrun_context.get("selected_slug")
    )
    return build_display_name(
        kind="sweep",
        timestamp=timestamp,
        fallback_id=sweep_id,
        market_slug=market_slug,
        strategy=_as_text(manifest.get("strategy")),
        strategy_preset=_as_text(manifest.get("strategy_preset")),
    )


def _batch_market_slug(manifest: Mapping[str, Any]) -> str | None:
    direct = _as_text(manifest.get("market_slug"))
    if direct is not None:
        return direct

    markets = manifest.get("markets")
    if not isinstance(markets, list):
        return None

    slugs: set[str] = set()
    for row in markets:
        if not isinstance(row, Mapping):
            continue
        slug = _as_text(row.get("slug"))
        if slug is not None:
            slugs.add(slug)
    if not slugs:
        return None
    if len(slugs) == 1:
        return next(iter(slugs))
    return f"multiple({len(slugs)})"


def derive_batch_display_name(
    manifest: Mapping[str, Any],
    *,
    artifact_id: str | None = None,
) -> str:
    batch_id = _as_text(manifest.get("batch_id")) or _as_text(artifact_id)
    return build_display_name(
        kind="batch",
        timestamp=_as_text(manifest.get("created_at")),
        fallback_id=batch_id,
        market_slug=_batch_market_slug(manifest),
        strategy=_as_text(manifest.get("strategy")),
        strategy_preset=_as_text(manifest.get("strategy_preset")),
    )


def _arg_value(args: Any, flag: str) -> str | None:
    if not isinstance(args, list):
        return None
    for idx, token in enumerate(args):
        if str(token) != flag:
            continue
        if idx + 1 >= len(args):
            return None
        return _as_text(args[idx + 1])
    return None


def derive_session_display_name(session: Mapping[str, Any]) -> str:
    kind = _as_text(session.get("kind")) or "ondemand"
    session_id = _as_text(session.get("session_id"))
    args = session.get("args")

    market_slug = _as_text(session.get("market_slug")) or _arg_value(args, "--market")
    strategy = _as_text(session.get("strategy")) or _arg_value(args, "--strategy")
    strategy_preset = _as_text(session.get("strategy_preset")) or _arg_value(
        args, "--strategy-preset"
    )

    return build_display_name(
        kind=kind,
        timestamp=_as_text(session.get("started_at")),
        fallback_id=session_id,
        market_slug=market_slug,
        strategy=strategy,
        strategy_preset=strategy_preset,
    )


def derive_artifact_display_name(
    *,
    artifact_type: str,
    artifact_id: str,
    manifest: Mapping[str, Any] | None = None,
) -> str:
    payload = manifest or {}
    explicit = _as_text(payload.get("display_name"))
    if explicit is not None:
        return explicit

    kind = artifact_type.strip().lower()
    if kind in {"run", "shadow"}:
        return derive_run_display_name(
            payload,
            artifact_id=artifact_id,
            default_kind=kind,
        )
    if kind == "sweep":
        return derive_sweep_display_name(payload, artifact_id=artifact_id)
    if kind == "batch":
        return derive_batch_display_name(payload, artifact_id=artifact_id)
    return build_display_name(
        kind=kind or "artifact",
        timestamp=None,
        fallback_id=artifact_id,
    )
