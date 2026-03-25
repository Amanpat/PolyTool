"""Track 2 ClickHouse-ready event models for crypto-pair runner artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, ClassVar, Mapping, Optional, Sequence

from .paper_ledger import (
    PaperExposureState,
    PaperLegFill,
    PaperOpportunityObservation,
    PaperOrderIntent,
    PaperPairSettlement,
    PaperRunSummary,
)


CRYPTO_PAIR_EVENT_SCHEMA_VERSION = "crypto_pair_clickhouse_event_schema_v0"
CRYPTO_PAIR_EVENT_RECORD_TYPE = "crypto_pair_event"
CRYPTO_PAIR_EVENT_SOURCE = "crypto_pair_runner_v0"
CRYPTO_PAIR_EVENTS_TABLE = "polytool.crypto_pair_events"

EVENT_TYPE_OPPORTUNITY_OBSERVED = "opportunity_observed"
EVENT_TYPE_INTENT_GENERATED = "intent_generated"
EVENT_TYPE_SIMULATED_FILL_RECORDED = "simulated_fill_recorded"
EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED = "partial_exposure_updated"
EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED = "pair_settlement_completed"
EVENT_TYPE_SAFETY_STATE_TRANSITION = "safety_state_transition"
EVENT_TYPE_RUN_SUMMARY = "run_summary"

CRYPTO_PAIR_EVENT_TYPES = (
    EVENT_TYPE_OPPORTUNITY_OBSERVED,
    EVENT_TYPE_INTENT_GENERATED,
    EVENT_TYPE_SIMULATED_FILL_RECORDED,
    EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED,
    EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED,
    EVENT_TYPE_SAFETY_STATE_TRANSITION,
    EVENT_TYPE_RUN_SUMMARY,
)

_DEFAULT_CLICKHOUSE_ROW: dict[str, Any] = {
    "event_id": "",
    "event_type": "",
    "schema_version": "",
    "event_ts": "",
    "recorded_at": "",
    "run_id": "",
    "mode": "",
    "source": "",
    "market_id": "",
    "condition_id": "",
    "slug": "",
    "symbol": "",
    "duration_min": 0,
    "opportunity_id": "",
    "intent_id": "",
    "fill_id": "",
    "settlement_id": "",
    "transition_id": "",
    "leg": "",
    "token_id": "",
    "side": "",
    "state_key": "",
    "from_state": "",
    "to_state": "",
    "reason": "",
    "exposure_status": "",
    "winning_leg": "",
    "yes_token_id": "",
    "no_token_id": "",
    "yes_quote_price": None,
    "no_quote_price": None,
    "pair_quote_cost": None,
    "target_pair_cost_threshold": None,
    "threshold_edge_usdc": None,
    "pair_size": None,
    "intended_yes_price": None,
    "intended_no_price": None,
    "intended_pair_cost": None,
    "intended_paired_notional_usdc": None,
    "fill_price": None,
    "fill_size": None,
    "fill_notional_usdc": None,
    "fee_adjustment_usdc": None,
    "net_cash_delta_usdc": None,
    "paired_size": None,
    "paired_cost_usdc": None,
    "paired_fee_adjustment_usdc": None,
    "paired_net_cash_outflow_usdc": None,
    "unpaired_size": None,
    "unpaired_notional_usdc": None,
    "unpaired_max_loss_usdc": None,
    "unpaired_max_gain_usdc": None,
    "settlement_value_usdc": None,
    "gross_pnl_usdc": None,
    "net_pnl_usdc": None,
    "markets_seen": None,
    "opportunities_observed": None,
    "threshold_pass_count": None,
    "threshold_miss_count": None,
    "order_intents_generated": None,
    "paired_exposure_count": None,
    "partial_exposure_count": None,
    "settled_pair_count": None,
    "open_unpaired_notional_usdc": None,
    "quote_age_seconds": None,
    "threshold_passed": None,
    "assumptions_json": "[]",
    "event_payload_json": "{}",
}

CLICKHOUSE_EVENT_COLUMNS = tuple(_DEFAULT_CLICKHOUSE_ROW.keys())


class CryptoPairEventModelError(ValueError):
    """Raised when a Track 2 event model contains invalid data."""


def _require_text(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise CryptoPairEventModelError(f"{field_name} must be a non-empty string")
    return text


def _optional_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise CryptoPairEventModelError(f"{field_name} must be an integer, got bool")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CryptoPairEventModelError(
            f"{field_name} must be integer-compatible, got {value!r}"
        ) from exc


def _coerce_optional_int(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    return _coerce_int(value, field_name)


def _coerce_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CryptoPairEventModelError(
            f"{field_name} must be decimal-compatible, got {value!r}"
        ) from exc


def _coerce_optional_decimal(value: Any, field_name: str) -> Optional[Decimal]:
    if value is None:
        return None
    return _coerce_decimal(value, field_name)


def _normalize_mode(value: Any) -> str:
    mode = _require_text(value, "mode").lower()
    return mode


def _normalize_symbol(value: Any) -> str:
    symbol = _optional_text(value)
    return symbol.upper() if symbol else ""


def _normalize_assumptions(values: Sequence[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    normalized: list[str] = []
    for raw_value in values:
        value = str(raw_value).strip()
        if not value:
            raise CryptoPairEventModelError("assumptions cannot contain empty strings")
        normalized.append(value)
    return tuple(normalized)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(_json_ready(value), sort_keys=True, allow_nan=False)


def _decimal_str(value: Decimal | None) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _decimal_float(value: Decimal | None) -> Optional[float]:
    if value is None:
        return None
    return float(value)


@dataclass(frozen=True, kw_only=True)
class CryptoPairEventBase:
    """Common envelope for Track 2 event records."""

    event_id: str
    event_ts: str
    run_id: str
    mode: str = "paper"
    source: str = CRYPTO_PAIR_EVENT_SOURCE
    recorded_at: Optional[str] = None
    market_id: str = ""
    condition_id: str = ""
    slug: str = ""
    symbol: str = ""
    duration_min: int = 0

    EVENT_TYPE: ClassVar[str] = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _require_text(self.event_id, "event_id"))
        object.__setattr__(self, "event_ts", _require_text(self.event_ts, "event_ts"))
        object.__setattr__(self, "run_id", _require_text(self.run_id, "run_id"))
        object.__setattr__(self, "mode", _normalize_mode(self.mode))
        object.__setattr__(self, "source", _require_text(self.source, "source"))

        recorded_at = self.recorded_at if self.recorded_at is not None else self.event_ts
        object.__setattr__(self, "recorded_at", _require_text(recorded_at, "recorded_at"))
        object.__setattr__(self, "market_id", _optional_text(self.market_id))
        object.__setattr__(self, "condition_id", _optional_text(self.condition_id))
        object.__setattr__(self, "slug", _optional_text(self.slug))
        object.__setattr__(self, "symbol", _normalize_symbol(self.symbol))

        duration_min = _coerce_int(self.duration_min, "duration_min")
        if duration_min < 0:
            raise CryptoPairEventModelError("duration_min must be >= 0")
        object.__setattr__(self, "duration_min", duration_min)

        if self.EVENT_TYPE not in CRYPTO_PAIR_EVENT_TYPES:
            raise CryptoPairEventModelError(
                f"unsupported event type {self.EVENT_TYPE!r}"
            )

    @property
    def event_type(self) -> str:
        return self.EVENT_TYPE

    def _event_fields(self) -> dict[str, Any]:
        raise NotImplementedError

    def _clickhouse_updates(self) -> dict[str, Any]:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "record_type": CRYPTO_PAIR_EVENT_RECORD_TYPE,
            "schema_version": CRYPTO_PAIR_EVENT_SCHEMA_VERSION,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "event_ts": self.event_ts,
            "recorded_at": self.recorded_at,
            "run_id": self.run_id,
            "mode": self.mode,
            "source": self.source,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "slug": self.slug,
            "symbol": self.symbol,
            "duration_min": self.duration_min,
        }
        payload.update(self._event_fields())
        return _json_ready(payload)

    def to_clickhouse_row(self) -> dict[str, Any]:
        row = dict(_DEFAULT_CLICKHOUSE_ROW)
        row.update(
            {
                "event_id": self.event_id,
                "event_type": self.event_type,
                "schema_version": CRYPTO_PAIR_EVENT_SCHEMA_VERSION,
                "event_ts": self.event_ts,
                "recorded_at": self.recorded_at,
                "run_id": self.run_id,
                "mode": self.mode,
                "source": self.source,
                "market_id": self.market_id,
                "condition_id": self.condition_id,
                "slug": self.slug,
                "symbol": self.symbol,
                "duration_min": self.duration_min,
                "event_payload_json": _json_dumps(self.to_dict()),
            }
        )
        row.update(self._clickhouse_updates())
        return row

    def to_clickhouse_values(self) -> list[Any]:
        row = self.to_clickhouse_row()
        return [row[column_name] for column_name in CLICKHOUSE_EVENT_COLUMNS]


@dataclass(frozen=True, kw_only=True)
class OpportunityObservedEvent(CryptoPairEventBase):
    """Observed Track 2 opportunity before intent generation."""

    opportunity_id: str
    yes_token_id: str
    no_token_id: str
    yes_quote_price: Decimal
    no_quote_price: Decimal
    target_pair_cost_threshold: Decimal
    threshold_edge_usdc: Decimal
    threshold_passed: bool
    quote_age_seconds: int = 0
    assumptions: tuple[str, ...] = ()

    EVENT_TYPE: ClassVar[str] = EVENT_TYPE_OPPORTUNITY_OBSERVED

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(
            self,
            "opportunity_id",
            _require_text(self.opportunity_id, "opportunity_id"),
        )
        object.__setattr__(
            self,
            "yes_token_id",
            _require_text(self.yes_token_id, "yes_token_id"),
        )
        object.__setattr__(
            self,
            "no_token_id",
            _require_text(self.no_token_id, "no_token_id"),
        )

        yes_quote_price = _coerce_decimal(self.yes_quote_price, "yes_quote_price")
        no_quote_price = _coerce_decimal(self.no_quote_price, "no_quote_price")
        target_pair_cost_threshold = _coerce_decimal(
            self.target_pair_cost_threshold,
            "target_pair_cost_threshold",
        )
        threshold_edge_usdc = _coerce_decimal(
            self.threshold_edge_usdc,
            "threshold_edge_usdc",
        )
        quote_age_seconds = _coerce_int(self.quote_age_seconds, "quote_age_seconds")
        if quote_age_seconds < 0:
            raise CryptoPairEventModelError("quote_age_seconds must be >= 0")

        object.__setattr__(self, "yes_quote_price", yes_quote_price)
        object.__setattr__(self, "no_quote_price", no_quote_price)
        object.__setattr__(
            self,
            "target_pair_cost_threshold",
            target_pair_cost_threshold,
        )
        object.__setattr__(self, "threshold_edge_usdc", threshold_edge_usdc)
        object.__setattr__(self, "quote_age_seconds", quote_age_seconds)
        object.__setattr__(self, "assumptions", _normalize_assumptions(self.assumptions))

    @property
    def pair_quote_cost(self) -> Decimal:
        return self.yes_quote_price + self.no_quote_price

    @classmethod
    def from_observation(
        cls,
        observation: PaperOpportunityObservation,
        *,
        mode: str = "paper",
        source: str = CRYPTO_PAIR_EVENT_SOURCE,
    ) -> "OpportunityObservedEvent":
        return cls(
            event_id=observation.opportunity_id,
            event_ts=observation.observed_at,
            run_id=observation.run_id,
            mode=mode,
            source=source,
            market_id=observation.market_id,
            condition_id=observation.condition_id,
            slug=observation.slug,
            symbol=observation.symbol,
            duration_min=observation.duration_min,
            opportunity_id=observation.opportunity_id,
            yes_token_id=observation.yes_token_id,
            no_token_id=observation.no_token_id,
            yes_quote_price=observation.yes_quote_price,
            no_quote_price=observation.no_quote_price,
            target_pair_cost_threshold=observation.target_pair_cost_threshold,
            threshold_edge_usdc=observation.threshold_edge_usdc,
            threshold_passed=observation.threshold_passed,
            quote_age_seconds=observation.quote_age_seconds,
            assumptions=observation.assumptions,
        )

    def _event_fields(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "yes_quote_price": _decimal_str(self.yes_quote_price),
            "no_quote_price": _decimal_str(self.no_quote_price),
            "pair_quote_cost": _decimal_str(self.pair_quote_cost),
            "target_pair_cost_threshold": _decimal_str(
                self.target_pair_cost_threshold
            ),
            "threshold_edge_usdc": _decimal_str(self.threshold_edge_usdc),
            "threshold_passed": bool(self.threshold_passed),
            "quote_age_seconds": self.quote_age_seconds,
            "assumptions": list(self.assumptions),
        }

    def _clickhouse_updates(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "yes_quote_price": _decimal_float(self.yes_quote_price),
            "no_quote_price": _decimal_float(self.no_quote_price),
            "pair_quote_cost": _decimal_float(self.pair_quote_cost),
            "target_pair_cost_threshold": _decimal_float(
                self.target_pair_cost_threshold
            ),
            "threshold_edge_usdc": _decimal_float(self.threshold_edge_usdc),
            "quote_age_seconds": self.quote_age_seconds,
            "threshold_passed": bool(self.threshold_passed),
            "assumptions_json": _json_dumps(list(self.assumptions)),
        }


@dataclass(frozen=True, kw_only=True)
class IntentGeneratedEvent(CryptoPairEventBase):
    """Intent generated after an opportunity survives Track 2 gating."""

    intent_id: str
    opportunity_id: str
    yes_token_id: str
    no_token_id: str
    pair_size: Decimal
    intended_yes_price: Decimal
    intended_no_price: Decimal
    target_pair_cost_threshold: Decimal
    intended_paired_notional_usdc: Decimal
    max_capital_per_market_usdc: Decimal
    max_open_paired_notional_usdc: Decimal
    maker_rebate_bps: Decimal
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    stale_quote_timeout_seconds: int
    quote_age_seconds: int

    EVENT_TYPE: ClassVar[str] = EVENT_TYPE_INTENT_GENERATED

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "intent_id", _require_text(self.intent_id, "intent_id"))
        object.__setattr__(
            self,
            "opportunity_id",
            _require_text(self.opportunity_id, "opportunity_id"),
        )
        object.__setattr__(
            self,
            "yes_token_id",
            _require_text(self.yes_token_id, "yes_token_id"),
        )
        object.__setattr__(
            self,
            "no_token_id",
            _require_text(self.no_token_id, "no_token_id"),
        )

        object.__setattr__(self, "pair_size", _coerce_decimal(self.pair_size, "pair_size"))
        object.__setattr__(
            self,
            "intended_yes_price",
            _coerce_decimal(self.intended_yes_price, "intended_yes_price"),
        )
        object.__setattr__(
            self,
            "intended_no_price",
            _coerce_decimal(self.intended_no_price, "intended_no_price"),
        )
        object.__setattr__(
            self,
            "target_pair_cost_threshold",
            _coerce_decimal(
                self.target_pair_cost_threshold,
                "target_pair_cost_threshold",
            ),
        )
        object.__setattr__(
            self,
            "intended_paired_notional_usdc",
            _coerce_decimal(
                self.intended_paired_notional_usdc,
                "intended_paired_notional_usdc",
            ),
        )
        object.__setattr__(
            self,
            "max_capital_per_market_usdc",
            _coerce_decimal(
                self.max_capital_per_market_usdc,
                "max_capital_per_market_usdc",
            ),
        )
        object.__setattr__(
            self,
            "max_open_paired_notional_usdc",
            _coerce_decimal(
                self.max_open_paired_notional_usdc,
                "max_open_paired_notional_usdc",
            ),
        )
        object.__setattr__(
            self,
            "maker_rebate_bps",
            _coerce_decimal(self.maker_rebate_bps, "maker_rebate_bps"),
        )
        object.__setattr__(
            self,
            "maker_fee_bps",
            _coerce_decimal(self.maker_fee_bps, "maker_fee_bps"),
        )
        object.__setattr__(
            self,
            "taker_fee_bps",
            _coerce_decimal(self.taker_fee_bps, "taker_fee_bps"),
        )

        stale_quote_timeout_seconds = _coerce_int(
            self.stale_quote_timeout_seconds,
            "stale_quote_timeout_seconds",
        )
        quote_age_seconds = _coerce_int(self.quote_age_seconds, "quote_age_seconds")
        if stale_quote_timeout_seconds < 0:
            raise CryptoPairEventModelError(
                "stale_quote_timeout_seconds must be >= 0"
            )
        if quote_age_seconds < 0:
            raise CryptoPairEventModelError("quote_age_seconds must be >= 0")
        object.__setattr__(
            self,
            "stale_quote_timeout_seconds",
            stale_quote_timeout_seconds,
        )
        object.__setattr__(self, "quote_age_seconds", quote_age_seconds)

    @property
    def intended_pair_cost(self) -> Decimal:
        return self.intended_yes_price + self.intended_no_price

    @classmethod
    def from_intent(
        cls,
        intent: PaperOrderIntent,
        *,
        mode: str = "paper",
        source: str = CRYPTO_PAIR_EVENT_SOURCE,
    ) -> "IntentGeneratedEvent":
        return cls(
            event_id=intent.intent_id,
            event_ts=intent.created_at,
            run_id=intent.run_id,
            mode=mode,
            source=source,
            market_id=intent.market_id,
            condition_id=intent.condition_id,
            slug=intent.slug,
            symbol=intent.symbol,
            duration_min=intent.duration_min,
            intent_id=intent.intent_id,
            opportunity_id=intent.opportunity_id,
            yes_token_id=intent.yes_token_id,
            no_token_id=intent.no_token_id,
            pair_size=intent.pair_size,
            intended_yes_price=intent.intended_yes_price,
            intended_no_price=intent.intended_no_price,
            target_pair_cost_threshold=intent.target_pair_cost_threshold,
            intended_paired_notional_usdc=intent.intended_paired_notional_usdc,
            max_capital_per_market_usdc=intent.max_capital_per_market_usdc,
            max_open_paired_notional_usdc=intent.max_open_paired_notional_usdc,
            maker_rebate_bps=intent.maker_rebate_bps,
            maker_fee_bps=intent.maker_fee_bps,
            taker_fee_bps=intent.taker_fee_bps,
            stale_quote_timeout_seconds=intent.stale_quote_timeout_seconds,
            quote_age_seconds=intent.quote_age_seconds,
        )

    def _event_fields(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "opportunity_id": self.opportunity_id,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "pair_size": _decimal_str(self.pair_size),
            "intended_yes_price": _decimal_str(self.intended_yes_price),
            "intended_no_price": _decimal_str(self.intended_no_price),
            "intended_pair_cost": _decimal_str(self.intended_pair_cost),
            "intended_paired_notional_usdc": _decimal_str(
                self.intended_paired_notional_usdc
            ),
            "target_pair_cost_threshold": _decimal_str(
                self.target_pair_cost_threshold
            ),
            "max_capital_per_market_usdc": _decimal_str(
                self.max_capital_per_market_usdc
            ),
            "max_open_paired_notional_usdc": _decimal_str(
                self.max_open_paired_notional_usdc
            ),
            "maker_rebate_bps": _decimal_str(self.maker_rebate_bps),
            "maker_fee_bps": _decimal_str(self.maker_fee_bps),
            "taker_fee_bps": _decimal_str(self.taker_fee_bps),
            "stale_quote_timeout_seconds": self.stale_quote_timeout_seconds,
            "quote_age_seconds": self.quote_age_seconds,
        }

    def _clickhouse_updates(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "intent_id": self.intent_id,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "pair_size": _decimal_float(self.pair_size),
            "intended_yes_price": _decimal_float(self.intended_yes_price),
            "intended_no_price": _decimal_float(self.intended_no_price),
            "intended_pair_cost": _decimal_float(self.intended_pair_cost),
            "intended_paired_notional_usdc": _decimal_float(
                self.intended_paired_notional_usdc
            ),
            "target_pair_cost_threshold": _decimal_float(
                self.target_pair_cost_threshold
            ),
            "quote_age_seconds": self.quote_age_seconds,
        }


@dataclass(frozen=True, kw_only=True)
class SimulatedFillRecordedEvent(CryptoPairEventBase):
    """Simulated fill record written for one YES or NO leg."""

    fill_id: str
    intent_id: str
    leg: str
    token_id: str
    side: str
    fill_price: Decimal
    fill_size: Decimal
    fee_adjustment_usdc: Decimal = Decimal("0")
    net_cash_delta_usdc: Optional[Decimal] = None

    EVENT_TYPE: ClassVar[str] = EVENT_TYPE_SIMULATED_FILL_RECORDED

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "fill_id", _require_text(self.fill_id, "fill_id"))
        object.__setattr__(self, "intent_id", _require_text(self.intent_id, "intent_id"))
        object.__setattr__(self, "leg", _require_text(self.leg, "leg").upper())
        object.__setattr__(self, "token_id", _require_text(self.token_id, "token_id"))
        object.__setattr__(self, "side", _require_text(self.side, "side").upper())
        object.__setattr__(
            self,
            "fill_price",
            _coerce_decimal(self.fill_price, "fill_price"),
        )
        object.__setattr__(
            self,
            "fill_size",
            _coerce_decimal(self.fill_size, "fill_size"),
        )
        object.__setattr__(
            self,
            "fee_adjustment_usdc",
            _coerce_decimal(self.fee_adjustment_usdc, "fee_adjustment_usdc"),
        )
        net_cash_delta_usdc = (
            _coerce_optional_decimal(self.net_cash_delta_usdc, "net_cash_delta_usdc")
            if self.net_cash_delta_usdc is not None
            else None
        )
        object.__setattr__(self, "net_cash_delta_usdc", net_cash_delta_usdc)

    @property
    def fill_notional_usdc(self) -> Decimal:
        return self.fill_price * self.fill_size

    @classmethod
    def from_fill(
        cls,
        fill: PaperLegFill,
        *,
        mode: str = "paper",
        source: str = CRYPTO_PAIR_EVENT_SOURCE,
    ) -> "SimulatedFillRecordedEvent":
        return cls(
            event_id=fill.fill_id,
            event_ts=fill.filled_at,
            run_id=fill.run_id,
            mode=mode,
            source=source,
            market_id=fill.market_id,
            condition_id=fill.condition_id,
            slug=fill.slug,
            symbol=fill.symbol,
            duration_min=fill.duration_min,
            fill_id=fill.fill_id,
            intent_id=fill.intent_id,
            leg=fill.leg,
            token_id=fill.token_id,
            side=fill.side,
            fill_price=fill.price,
            fill_size=fill.size,
            fee_adjustment_usdc=fill.fee_adjustment_usdc,
            net_cash_delta_usdc=fill.net_cash_delta_usdc,
        )

    def _event_fields(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "intent_id": self.intent_id,
            "leg": self.leg,
            "token_id": self.token_id,
            "side": self.side,
            "fill_price": _decimal_str(self.fill_price),
            "fill_size": _decimal_str(self.fill_size),
            "fill_notional_usdc": _decimal_str(self.fill_notional_usdc),
            "fee_adjustment_usdc": _decimal_str(self.fee_adjustment_usdc),
            "net_cash_delta_usdc": _decimal_str(self.net_cash_delta_usdc),
        }

    def _clickhouse_updates(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "fill_id": self.fill_id,
            "leg": self.leg,
            "token_id": self.token_id,
            "side": self.side,
            "fill_price": _decimal_float(self.fill_price),
            "fill_size": _decimal_float(self.fill_size),
            "fill_notional_usdc": _decimal_float(self.fill_notional_usdc),
            "fee_adjustment_usdc": _decimal_float(self.fee_adjustment_usdc),
            "net_cash_delta_usdc": _decimal_float(self.net_cash_delta_usdc),
        }


@dataclass(frozen=True, kw_only=True)
class PartialExposureUpdatedEvent(CryptoPairEventBase):
    """Per-intent exposure snapshot after simulated fills are aggregated."""

    intent_id: str
    exposure_status: str
    yes_position: Mapping[str, Any]
    no_position: Mapping[str, Any]
    paired_size: Decimal
    paired_cost_usdc: Decimal
    paired_fee_adjustment_usdc: Decimal
    paired_net_cash_outflow_usdc: Decimal
    unpaired_leg: Optional[str]
    unpaired_size: Decimal
    unpaired_average_fill_price: Optional[Decimal]
    unpaired_notional_usdc: Decimal
    unpaired_fee_adjustment_usdc: Decimal
    unpaired_net_cash_outflow_usdc: Decimal
    unpaired_max_loss_usdc: Decimal
    unpaired_max_gain_usdc: Decimal

    EVENT_TYPE: ClassVar[str] = EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "intent_id", _require_text(self.intent_id, "intent_id"))
        object.__setattr__(
            self,
            "exposure_status",
            _require_text(self.exposure_status, "exposure_status"),
        )
        object.__setattr__(self, "yes_position", dict(self.yes_position))
        object.__setattr__(self, "no_position", dict(self.no_position))
        object.__setattr__(
            self,
            "paired_size",
            _coerce_decimal(self.paired_size, "paired_size"),
        )
        object.__setattr__(
            self,
            "paired_cost_usdc",
            _coerce_decimal(self.paired_cost_usdc, "paired_cost_usdc"),
        )
        object.__setattr__(
            self,
            "paired_fee_adjustment_usdc",
            _coerce_decimal(
                self.paired_fee_adjustment_usdc,
                "paired_fee_adjustment_usdc",
            ),
        )
        object.__setattr__(
            self,
            "paired_net_cash_outflow_usdc",
            _coerce_decimal(
                self.paired_net_cash_outflow_usdc,
                "paired_net_cash_outflow_usdc",
            ),
        )
        object.__setattr__(
            self,
            "unpaired_leg",
            _optional_text(self.unpaired_leg).upper() or None,
        )
        object.__setattr__(
            self,
            "unpaired_size",
            _coerce_decimal(self.unpaired_size, "unpaired_size"),
        )
        object.__setattr__(
            self,
            "unpaired_average_fill_price",
            _coerce_optional_decimal(
                self.unpaired_average_fill_price,
                "unpaired_average_fill_price",
            ),
        )
        object.__setattr__(
            self,
            "unpaired_notional_usdc",
            _coerce_decimal(self.unpaired_notional_usdc, "unpaired_notional_usdc"),
        )
        object.__setattr__(
            self,
            "unpaired_fee_adjustment_usdc",
            _coerce_decimal(
                self.unpaired_fee_adjustment_usdc,
                "unpaired_fee_adjustment_usdc",
            ),
        )
        object.__setattr__(
            self,
            "unpaired_net_cash_outflow_usdc",
            _coerce_decimal(
                self.unpaired_net_cash_outflow_usdc,
                "unpaired_net_cash_outflow_usdc",
            ),
        )
        object.__setattr__(
            self,
            "unpaired_max_loss_usdc",
            _coerce_decimal(self.unpaired_max_loss_usdc, "unpaired_max_loss_usdc"),
        )
        object.__setattr__(
            self,
            "unpaired_max_gain_usdc",
            _coerce_decimal(self.unpaired_max_gain_usdc, "unpaired_max_gain_usdc"),
        )

    @classmethod
    def from_exposure(
        cls,
        exposure: PaperExposureState,
        *,
        mode: str = "paper",
        source: str = CRYPTO_PAIR_EVENT_SOURCE,
    ) -> "PartialExposureUpdatedEvent":
        return cls(
            event_id=f"{exposure.intent_id}:{exposure.as_of}:exposure",
            event_ts=exposure.as_of,
            run_id=exposure.run_id,
            mode=mode,
            source=source,
            market_id=exposure.market_id,
            condition_id=exposure.condition_id,
            slug=exposure.slug,
            symbol=exposure.symbol,
            duration_min=exposure.duration_min,
            intent_id=exposure.intent_id,
            exposure_status=exposure.exposure_status,
            yes_position=exposure.yes_position.to_dict(),
            no_position=exposure.no_position.to_dict(),
            paired_size=exposure.paired_size,
            paired_cost_usdc=exposure.paired_cost_usdc,
            paired_fee_adjustment_usdc=exposure.paired_fee_adjustment_usdc,
            paired_net_cash_outflow_usdc=exposure.paired_net_cash_outflow_usdc,
            unpaired_leg=exposure.unpaired_leg,
            unpaired_size=exposure.unpaired_size,
            unpaired_average_fill_price=exposure.unpaired_average_fill_price,
            unpaired_notional_usdc=exposure.unpaired_notional_usdc,
            unpaired_fee_adjustment_usdc=exposure.unpaired_fee_adjustment_usdc,
            unpaired_net_cash_outflow_usdc=exposure.unpaired_net_cash_outflow_usdc,
            unpaired_max_loss_usdc=exposure.unpaired_max_loss_usdc,
            unpaired_max_gain_usdc=exposure.unpaired_max_gain_usdc,
        )

    def _event_fields(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "exposure_status": self.exposure_status,
            "yes_position": dict(self.yes_position),
            "no_position": dict(self.no_position),
            "paired_size": _decimal_str(self.paired_size),
            "paired_cost_usdc": _decimal_str(self.paired_cost_usdc),
            "paired_fee_adjustment_usdc": _decimal_str(
                self.paired_fee_adjustment_usdc
            ),
            "paired_net_cash_outflow_usdc": _decimal_str(
                self.paired_net_cash_outflow_usdc
            ),
            "unpaired_leg": self.unpaired_leg,
            "unpaired_size": _decimal_str(self.unpaired_size),
            "unpaired_average_fill_price": _decimal_str(
                self.unpaired_average_fill_price
            ),
            "unpaired_notional_usdc": _decimal_str(self.unpaired_notional_usdc),
            "unpaired_fee_adjustment_usdc": _decimal_str(
                self.unpaired_fee_adjustment_usdc
            ),
            "unpaired_net_cash_outflow_usdc": _decimal_str(
                self.unpaired_net_cash_outflow_usdc
            ),
            "unpaired_max_loss_usdc": _decimal_str(self.unpaired_max_loss_usdc),
            "unpaired_max_gain_usdc": _decimal_str(self.unpaired_max_gain_usdc),
        }

    def _clickhouse_updates(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "leg": self.unpaired_leg or "",
            "exposure_status": self.exposure_status,
            "paired_size": _decimal_float(self.paired_size),
            "paired_cost_usdc": _decimal_float(self.paired_cost_usdc),
            "paired_fee_adjustment_usdc": _decimal_float(
                self.paired_fee_adjustment_usdc
            ),
            "paired_net_cash_outflow_usdc": _decimal_float(
                self.paired_net_cash_outflow_usdc
            ),
            "unpaired_size": _decimal_float(self.unpaired_size),
            "unpaired_notional_usdc": _decimal_float(self.unpaired_notional_usdc),
            "unpaired_max_loss_usdc": _decimal_float(self.unpaired_max_loss_usdc),
            "unpaired_max_gain_usdc": _decimal_float(self.unpaired_max_gain_usdc),
        }


@dataclass(frozen=True, kw_only=True)
class PairSettlementCompletedEvent(CryptoPairEventBase):
    """Completed settlement event for the paired portion of an intent."""

    settlement_id: str
    intent_id: str
    winning_leg: str
    paired_size: Decimal
    paired_cost_usdc: Decimal
    paired_fee_adjustment_usdc: Decimal
    paired_net_cash_outflow_usdc: Decimal
    settlement_value_usdc: Decimal
    gross_pnl_usdc: Decimal
    net_pnl_usdc: Decimal
    unpaired_leg: Optional[str]
    unpaired_size: Decimal

    EVENT_TYPE: ClassVar[str] = EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(
            self,
            "settlement_id",
            _require_text(self.settlement_id, "settlement_id"),
        )
        object.__setattr__(self, "intent_id", _require_text(self.intent_id, "intent_id"))
        object.__setattr__(
            self,
            "winning_leg",
            _require_text(self.winning_leg, "winning_leg").upper(),
        )
        object.__setattr__(
            self,
            "paired_size",
            _coerce_decimal(self.paired_size, "paired_size"),
        )
        object.__setattr__(
            self,
            "paired_cost_usdc",
            _coerce_decimal(self.paired_cost_usdc, "paired_cost_usdc"),
        )
        object.__setattr__(
            self,
            "paired_fee_adjustment_usdc",
            _coerce_decimal(
                self.paired_fee_adjustment_usdc,
                "paired_fee_adjustment_usdc",
            ),
        )
        object.__setattr__(
            self,
            "paired_net_cash_outflow_usdc",
            _coerce_decimal(
                self.paired_net_cash_outflow_usdc,
                "paired_net_cash_outflow_usdc",
            ),
        )
        object.__setattr__(
            self,
            "settlement_value_usdc",
            _coerce_decimal(self.settlement_value_usdc, "settlement_value_usdc"),
        )
        object.__setattr__(
            self,
            "gross_pnl_usdc",
            _coerce_decimal(self.gross_pnl_usdc, "gross_pnl_usdc"),
        )
        object.__setattr__(
            self,
            "net_pnl_usdc",
            _coerce_decimal(self.net_pnl_usdc, "net_pnl_usdc"),
        )
        object.__setattr__(
            self,
            "unpaired_leg",
            _optional_text(self.unpaired_leg).upper() or None,
        )
        object.__setattr__(
            self,
            "unpaired_size",
            _coerce_decimal(self.unpaired_size, "unpaired_size"),
        )

    @classmethod
    def from_settlement(
        cls,
        settlement: PaperPairSettlement,
        *,
        mode: str = "paper",
        source: str = CRYPTO_PAIR_EVENT_SOURCE,
    ) -> "PairSettlementCompletedEvent":
        return cls(
            event_id=settlement.settlement_id,
            event_ts=settlement.resolved_at,
            run_id=settlement.run_id,
            mode=mode,
            source=source,
            market_id=settlement.market_id,
            condition_id=settlement.condition_id,
            slug=settlement.slug,
            symbol=settlement.symbol,
            duration_min=settlement.duration_min,
            settlement_id=settlement.settlement_id,
            intent_id=settlement.intent_id,
            winning_leg=settlement.winning_leg,
            paired_size=settlement.paired_size,
            paired_cost_usdc=settlement.paired_cost_usdc,
            paired_fee_adjustment_usdc=settlement.paired_fee_adjustment_usdc,
            paired_net_cash_outflow_usdc=settlement.paired_net_cash_outflow_usdc,
            settlement_value_usdc=settlement.settlement_value_usdc,
            gross_pnl_usdc=settlement.gross_pnl_usdc,
            net_pnl_usdc=settlement.net_pnl_usdc,
            unpaired_leg=settlement.unpaired_leg,
            unpaired_size=settlement.unpaired_size,
        )

    def _event_fields(self) -> dict[str, Any]:
        return {
            "settlement_id": self.settlement_id,
            "intent_id": self.intent_id,
            "winning_leg": self.winning_leg,
            "paired_size": _decimal_str(self.paired_size),
            "paired_cost_usdc": _decimal_str(self.paired_cost_usdc),
            "paired_fee_adjustment_usdc": _decimal_str(
                self.paired_fee_adjustment_usdc
            ),
            "paired_net_cash_outflow_usdc": _decimal_str(
                self.paired_net_cash_outflow_usdc
            ),
            "settlement_value_usdc": _decimal_str(self.settlement_value_usdc),
            "gross_pnl_usdc": _decimal_str(self.gross_pnl_usdc),
            "net_pnl_usdc": _decimal_str(self.net_pnl_usdc),
            "unpaired_leg": self.unpaired_leg,
            "unpaired_size": _decimal_str(self.unpaired_size),
        }

    def _clickhouse_updates(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "settlement_id": self.settlement_id,
            "winning_leg": self.winning_leg,
            "paired_size": _decimal_float(self.paired_size),
            "paired_cost_usdc": _decimal_float(self.paired_cost_usdc),
            "paired_fee_adjustment_usdc": _decimal_float(
                self.paired_fee_adjustment_usdc
            ),
            "paired_net_cash_outflow_usdc": _decimal_float(
                self.paired_net_cash_outflow_usdc
            ),
            "unpaired_size": _decimal_float(self.unpaired_size),
            "settlement_value_usdc": _decimal_float(self.settlement_value_usdc),
            "gross_pnl_usdc": _decimal_float(self.gross_pnl_usdc),
            "net_pnl_usdc": _decimal_float(self.net_pnl_usdc),
        }


@dataclass(frozen=True, kw_only=True)
class SafetyStateTransitionEvent(CryptoPairEventBase):
    """Disconnect or safety-state transition for operator visibility."""

    transition_id: str
    state_key: str
    from_state: str
    to_state: str
    reason: str = ""
    cycle: Optional[int] = None
    details: Mapping[str, Any] = field(default_factory=dict)

    EVENT_TYPE: ClassVar[str] = EVENT_TYPE_SAFETY_STATE_TRANSITION

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(
            self,
            "transition_id",
            _require_text(self.transition_id, "transition_id"),
        )
        object.__setattr__(self, "state_key", _require_text(self.state_key, "state_key"))
        object.__setattr__(self, "from_state", _optional_text(self.from_state))
        object.__setattr__(self, "to_state", _require_text(self.to_state, "to_state"))
        object.__setattr__(self, "reason", _optional_text(self.reason))
        object.__setattr__(self, "cycle", _coerce_optional_int(self.cycle, "cycle"))
        object.__setattr__(self, "details", dict(self.details))

    @classmethod
    def from_feed_state_change(
        cls,
        *,
        transition_id: str,
        event_ts: str,
        run_id: str,
        mode: str,
        symbol: str,
        from_state: Optional[str],
        to_state: str,
        market_id: str = "",
        condition_id: str = "",
        slug: str = "",
        duration_min: int = 0,
        source: str = "runtime_event",
        reason: str = "",
        cycle: Optional[int] = None,
        details: Optional[Mapping[str, Any]] = None,
    ) -> "SafetyStateTransitionEvent":
        return cls(
            event_id=transition_id,
            event_ts=event_ts,
            run_id=run_id,
            mode=mode,
            source=source,
            market_id=market_id,
            condition_id=condition_id,
            slug=slug,
            symbol=symbol,
            duration_min=duration_min,
            transition_id=transition_id,
            state_key="reference_feed",
            from_state=from_state or "",
            to_state=to_state,
            reason=reason,
            cycle=cycle,
            details=details or {},
        )

    def _event_fields(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "state_key": self.state_key,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "reason": self.reason,
            "cycle": self.cycle,
            "details": dict(self.details),
        }

    def _clickhouse_updates(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "state_key": self.state_key,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "reason": self.reason,
        }


@dataclass(frozen=True, kw_only=True)
class RunSummaryEvent(CryptoPairEventBase):
    """Per-run aggregate summary event for Grafana and future persistence."""

    markets_seen: int
    opportunities_observed: int
    threshold_pass_count: int
    threshold_miss_count: int
    order_intents_generated: int
    paired_exposure_count: int
    partial_exposure_count: int
    settled_pair_count: int
    intended_paired_notional_usdc: Decimal
    open_unpaired_notional_usdc: Decimal
    gross_pnl_usdc: Decimal
    net_pnl_usdc: Decimal
    stopped_reason: str = ""

    EVENT_TYPE: ClassVar[str] = EVENT_TYPE_RUN_SUMMARY

    def __post_init__(self) -> None:
        super().__post_init__()
        for field_name in (
            "markets_seen",
            "opportunities_observed",
            "threshold_pass_count",
            "threshold_miss_count",
            "order_intents_generated",
            "paired_exposure_count",
            "partial_exposure_count",
            "settled_pair_count",
        ):
            value = _coerce_int(getattr(self, field_name), field_name)
            if value < 0:
                raise CryptoPairEventModelError(f"{field_name} must be >= 0")
            object.__setattr__(self, field_name, value)

        for field_name in (
            "intended_paired_notional_usdc",
            "open_unpaired_notional_usdc",
            "gross_pnl_usdc",
            "net_pnl_usdc",
        ):
            object.__setattr__(
                self,
                field_name,
                _coerce_decimal(getattr(self, field_name), field_name),
            )
        object.__setattr__(self, "stopped_reason", _optional_text(self.stopped_reason))

    @classmethod
    def from_summary(
        cls,
        summary: PaperRunSummary,
        *,
        mode: str = "paper",
        source: str = CRYPTO_PAIR_EVENT_SOURCE,
        stopped_reason: str = "",
    ) -> "RunSummaryEvent":
        return cls(
            event_id=f"{summary.run_id}:{summary.generated_at}:run_summary",
            event_ts=summary.generated_at,
            run_id=summary.run_id,
            mode=mode,
            source=source,
            markets_seen=summary.markets_seen,
            opportunities_observed=summary.opportunities_observed,
            threshold_pass_count=summary.threshold_pass_count,
            threshold_miss_count=summary.threshold_miss_count,
            order_intents_generated=summary.order_intents_generated,
            paired_exposure_count=summary.paired_exposure_count,
            partial_exposure_count=summary.partial_exposure_count,
            settled_pair_count=summary.settled_pair_count,
            intended_paired_notional_usdc=summary.intended_paired_notional_usdc,
            open_unpaired_notional_usdc=summary.open_unpaired_notional_usdc,
            gross_pnl_usdc=summary.gross_pnl_usdc,
            net_pnl_usdc=summary.net_pnl_usdc,
            stopped_reason=stopped_reason,
        )

    def _event_fields(self) -> dict[str, Any]:
        return {
            "markets_seen": self.markets_seen,
            "opportunities_observed": self.opportunities_observed,
            "threshold_pass_count": self.threshold_pass_count,
            "threshold_miss_count": self.threshold_miss_count,
            "order_intents_generated": self.order_intents_generated,
            "paired_exposure_count": self.paired_exposure_count,
            "partial_exposure_count": self.partial_exposure_count,
            "settled_pair_count": self.settled_pair_count,
            "intended_paired_notional_usdc": _decimal_str(
                self.intended_paired_notional_usdc
            ),
            "open_unpaired_notional_usdc": _decimal_str(
                self.open_unpaired_notional_usdc
            ),
            "gross_pnl_usdc": _decimal_str(self.gross_pnl_usdc),
            "net_pnl_usdc": _decimal_str(self.net_pnl_usdc),
            "stopped_reason": self.stopped_reason,
        }

    def _clickhouse_updates(self) -> dict[str, Any]:
        return {
            "markets_seen": self.markets_seen,
            "opportunities_observed": self.opportunities_observed,
            "threshold_pass_count": self.threshold_pass_count,
            "threshold_miss_count": self.threshold_miss_count,
            "order_intents_generated": self.order_intents_generated,
            "paired_exposure_count": self.paired_exposure_count,
            "partial_exposure_count": self.partial_exposure_count,
            "settled_pair_count": self.settled_pair_count,
            "intended_paired_notional_usdc": _decimal_float(
                self.intended_paired_notional_usdc
            ),
            "open_unpaired_notional_usdc": _decimal_float(
                self.open_unpaired_notional_usdc
            ),
            "gross_pnl_usdc": _decimal_float(self.gross_pnl_usdc),
            "net_pnl_usdc": _decimal_float(self.net_pnl_usdc),
            "reason": self.stopped_reason,
        }


CryptoPairTrack2Event = (
    OpportunityObservedEvent
    | IntentGeneratedEvent
    | SimulatedFillRecordedEvent
    | PartialExposureUpdatedEvent
    | PairSettlementCompletedEvent
    | SafetyStateTransitionEvent
    | RunSummaryEvent
)


def project_clickhouse_rows(events: Sequence[CryptoPairTrack2Event]) -> list[list[Any]]:
    """Project Track 2 events into ClickHouse row values in schema order."""

    return [event.to_clickhouse_values() for event in events]


def serialize_events(events: Sequence[CryptoPairTrack2Event]) -> list[dict[str, Any]]:
    """Serialize Track 2 events into JSON-friendly dictionaries."""

    return [event.to_dict() for event in events]


def build_events_from_paper_records(
    *,
    observations: Sequence[PaperOpportunityObservation] = (),
    intents: Sequence[PaperOrderIntent] = (),
    fills: Sequence[PaperLegFill] = (),
    exposures: Sequence[PaperExposureState] = (),
    settlements: Sequence[PaperPairSettlement] = (),
    run_summary: Optional[PaperRunSummary] = None,
    mode: str = "paper",
    source: str = CRYPTO_PAIR_EVENT_SOURCE,
    stopped_reason: str = "",
) -> list[CryptoPairTrack2Event]:
    """Build the Track 2 event batch from existing paper-ledger records."""

    events: list[CryptoPairTrack2Event] = []
    events.extend(
        OpportunityObservedEvent.from_observation(
            observation,
            mode=mode,
            source=source,
        )
        for observation in observations
    )
    events.extend(
        IntentGeneratedEvent.from_intent(
            intent,
            mode=mode,
            source=source,
        )
        for intent in intents
    )
    events.extend(
        SimulatedFillRecordedEvent.from_fill(
            fill,
            mode=mode,
            source=source,
        )
        for fill in fills
    )
    events.extend(
        PartialExposureUpdatedEvent.from_exposure(
            exposure,
            mode=mode,
            source=source,
        )
        for exposure in exposures
    )
    events.extend(
        PairSettlementCompletedEvent.from_settlement(
            settlement,
            mode=mode,
            source=source,
        )
        for settlement in settlements
    )
    if run_summary is not None:
        events.append(
            RunSummaryEvent.from_summary(
                run_summary,
                mode=mode,
                source=source,
                stopped_reason=stopped_reason,
            )
        )
    return events


__all__ = [
    "CLICKHOUSE_EVENT_COLUMNS",
    "CRYPTO_PAIR_EVENT_RECORD_TYPE",
    "CRYPTO_PAIR_EVENT_SCHEMA_VERSION",
    "CRYPTO_PAIR_EVENTS_TABLE",
    "CRYPTO_PAIR_EVENT_SOURCE",
    "CRYPTO_PAIR_EVENT_TYPES",
    "CryptoPairEventBase",
    "CryptoPairEventModelError",
    "CryptoPairTrack2Event",
    "EVENT_TYPE_INTENT_GENERATED",
    "EVENT_TYPE_OPPORTUNITY_OBSERVED",
    "EVENT_TYPE_PAIR_SETTLEMENT_COMPLETED",
    "EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED",
    "EVENT_TYPE_RUN_SUMMARY",
    "EVENT_TYPE_SAFETY_STATE_TRANSITION",
    "EVENT_TYPE_SIMULATED_FILL_RECORDED",
    "IntentGeneratedEvent",
    "OpportunityObservedEvent",
    "PairSettlementCompletedEvent",
    "PartialExposureUpdatedEvent",
    "RunSummaryEvent",
    "SafetyStateTransitionEvent",
    "SimulatedFillRecordedEvent",
    "build_events_from_paper_records",
    "project_clickhouse_rows",
    "serialize_events",
]
