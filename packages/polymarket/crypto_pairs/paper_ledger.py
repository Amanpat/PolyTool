"""Deterministic paper-ledger primitives for Track 2 / Phase 1A."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

from .config_models import CryptoPairPaperModeConfig


PAPER_LEDGER_SCHEMA_VERSION = "crypto_pair_paper_ledger_v0"
LEG_YES = "YES"
LEG_NO = "NO"
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"

_VALID_LEGS = frozenset({LEG_YES, LEG_NO})
_VALID_SIDES = frozenset({SIDE_BUY, SIDE_SELL})
_ZERO = Decimal("0")
_ONE = Decimal("1")


class PaperLedgerValidationError(ValueError):
    """Raised when a paper-ledger record or computation input is invalid."""


def _coerce_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaperLedgerValidationError(
            f"{field_name} must be a decimal-compatible value, got {value!r}"
        ) from exc


def _coerce_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise PaperLedgerValidationError(f"{field_name} must be an integer, got bool")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise PaperLedgerValidationError(
            f"{field_name} must be an integer-compatible value, got {value!r}"
        ) from exc


def _require_text(value: Any, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise PaperLedgerValidationError(f"{field_name} must be a non-empty string")
    return text


def _normalize_optional_decimal(
    value: Optional[Decimal],
    field_name: str,
) -> Optional[Decimal]:
    if value is None:
        return None
    return _coerce_decimal(value, field_name)


def _normalize_assumptions(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    normalized = []
    for raw_value in values:
        value = str(raw_value).strip()
        if not value:
            raise PaperLedgerValidationError("assumptions cannot contain empty strings")
        normalized.append(value)
    return tuple(normalized)


def _decimal_ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == _ZERO:
        return _ZERO
    return numerator / denominator


def _serialize_decimal(value: Decimal) -> str:
    return str(value)


@dataclass(frozen=True)
class PaperOpportunityObservation:
    """Observed pair quote snapshot before any paper order intent is created."""

    opportunity_id: str
    run_id: str
    observed_at: str
    market_id: str
    condition_id: str
    slug: str
    symbol: str
    duration_min: int
    yes_token_id: str
    no_token_id: str
    yes_quote_price: Decimal
    no_quote_price: Decimal
    quote_age_seconds: int = 0
    source: str = "scanner"
    assumptions: tuple[str, ...] = ()
    # Directional momentum fields (populated when evaluate_directional_entry fires)
    reference_price: Optional[float] = None
    price_change_pct: Optional[float] = None
    signal_direction: str = "NONE"
    favorite_side: Optional[str] = None
    hedge_side: Optional[str] = None
    entry_timing_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        yes_quote_price = _coerce_decimal(self.yes_quote_price, "yes_quote_price")
        no_quote_price = _coerce_decimal(self.no_quote_price, "no_quote_price")
        quote_age_seconds = _coerce_int(self.quote_age_seconds, "quote_age_seconds")

        for field_name, value in (
            ("opportunity_id", self.opportunity_id),
            ("run_id", self.run_id),
            ("observed_at", self.observed_at),
            ("market_id", self.market_id),
            ("condition_id", self.condition_id),
            ("slug", self.slug),
            ("symbol", self.symbol),
            ("yes_token_id", self.yes_token_id),
            ("no_token_id", self.no_token_id),
            ("source", self.source),
        ):
            object.__setattr__(self, field_name, _require_text(value, field_name))

        if yes_quote_price < _ZERO or yes_quote_price > _ONE:
            raise PaperLedgerValidationError("yes_quote_price must be within [0, 1]")
        if no_quote_price < _ZERO or no_quote_price > _ONE:
            raise PaperLedgerValidationError("no_quote_price must be within [0, 1]")
        if quote_age_seconds < 0:
            raise PaperLedgerValidationError("quote_age_seconds must be >= 0")

        object.__setattr__(self, "duration_min", _coerce_int(self.duration_min, "duration_min"))
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "yes_quote_price", yes_quote_price)
        object.__setattr__(self, "no_quote_price", no_quote_price)
        object.__setattr__(self, "quote_age_seconds", quote_age_seconds)
        object.__setattr__(self, "assumptions", _normalize_assumptions(self.assumptions))

    @property
    def paired_quote_cost(self) -> Decimal:
        return self.yes_quote_price + self.no_quote_price

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "paper_opportunity_observed",
            "schema_version": PAPER_LEDGER_SCHEMA_VERSION,
            "opportunity_id": self.opportunity_id,
            "run_id": self.run_id,
            "observed_at": self.observed_at,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "slug": self.slug,
            "symbol": self.symbol,
            "duration_min": self.duration_min,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "yes_quote_price": _serialize_decimal(self.yes_quote_price),
            "no_quote_price": _serialize_decimal(self.no_quote_price),
            "paired_quote_cost": _serialize_decimal(self.paired_quote_cost),
            "quote_age_seconds": self.quote_age_seconds,
            "source": self.source,
            "assumptions": list(self.assumptions),
            "reference_price": self.reference_price,
            "price_change_pct": self.price_change_pct,
            "signal_direction": self.signal_direction,
            "favorite_side": self.favorite_side,
            "hedge_side": self.hedge_side,
            "entry_timing_seconds": self.entry_timing_seconds,
        }


@dataclass(frozen=True)
class PaperOrderIntent:
    """Paper-mode order intent derived from an observed opportunity."""

    intent_id: str
    opportunity_id: str
    run_id: str
    created_at: str
    market_id: str
    condition_id: str
    slug: str
    symbol: str
    duration_min: int
    yes_token_id: str
    no_token_id: str
    pair_size: Decimal
    intended_yes_price: Decimal
    intended_no_price: Decimal
    max_capital_per_market_usdc: Decimal
    max_open_paired_notional_usdc: Decimal
    maker_rebate_bps: Decimal
    maker_fee_bps: Decimal
    taker_fee_bps: Decimal
    stale_quote_timeout_seconds: int
    quote_age_seconds: int

    def __post_init__(self) -> None:
        for field_name, value in (
            ("intent_id", self.intent_id),
            ("opportunity_id", self.opportunity_id),
            ("run_id", self.run_id),
            ("created_at", self.created_at),
            ("market_id", self.market_id),
            ("condition_id", self.condition_id),
            ("slug", self.slug),
            ("symbol", self.symbol),
            ("yes_token_id", self.yes_token_id),
            ("no_token_id", self.no_token_id),
        ):
            object.__setattr__(self, field_name, _require_text(value, field_name))

        pair_size = _coerce_decimal(self.pair_size, "pair_size")
        intended_yes_price = _coerce_decimal(self.intended_yes_price, "intended_yes_price")
        intended_no_price = _coerce_decimal(self.intended_no_price, "intended_no_price")
        max_capital_per_market_usdc = _coerce_decimal(
            self.max_capital_per_market_usdc,
            "max_capital_per_market_usdc",
        )
        max_open_paired_notional_usdc = _coerce_decimal(
            self.max_open_paired_notional_usdc,
            "max_open_paired_notional_usdc",
        )
        maker_rebate_bps = _coerce_decimal(self.maker_rebate_bps, "maker_rebate_bps")
        maker_fee_bps = _coerce_decimal(self.maker_fee_bps, "maker_fee_bps")
        taker_fee_bps = _coerce_decimal(self.taker_fee_bps, "taker_fee_bps")
        stale_quote_timeout_seconds = _coerce_int(
            self.stale_quote_timeout_seconds,
            "stale_quote_timeout_seconds",
        )
        quote_age_seconds = _coerce_int(self.quote_age_seconds, "quote_age_seconds")

        if pair_size <= _ZERO:
            raise PaperLedgerValidationError("pair_size must be > 0")
        if intended_yes_price < _ZERO or intended_yes_price > _ONE:
            raise PaperLedgerValidationError("intended_yes_price must be within [0, 1]")
        if intended_no_price < _ZERO or intended_no_price > _ONE:
            raise PaperLedgerValidationError("intended_no_price must be within [0, 1]")
        if max_capital_per_market_usdc <= _ZERO:
            raise PaperLedgerValidationError("max_capital_per_market_usdc must be > 0")
        if max_open_paired_notional_usdc <= _ZERO:
            raise PaperLedgerValidationError(
                "max_open_paired_notional_usdc must be > 0"
            )
        if maker_rebate_bps < _ZERO or maker_fee_bps < _ZERO or taker_fee_bps < _ZERO:
            raise PaperLedgerValidationError("fee bps values must all be >= 0")
        if stale_quote_timeout_seconds <= 0:
            raise PaperLedgerValidationError("stale_quote_timeout_seconds must be > 0")
        if quote_age_seconds < 0:
            raise PaperLedgerValidationError("quote_age_seconds must be >= 0")

        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "duration_min", _coerce_int(self.duration_min, "duration_min"))
        object.__setattr__(self, "pair_size", pair_size)
        object.__setattr__(self, "intended_yes_price", intended_yes_price)
        object.__setattr__(self, "intended_no_price", intended_no_price)
        object.__setattr__(
            self,
            "max_capital_per_market_usdc",
            max_capital_per_market_usdc,
        )
        object.__setattr__(
            self,
            "max_open_paired_notional_usdc",
            max_open_paired_notional_usdc,
        )
        object.__setattr__(self, "maker_rebate_bps", maker_rebate_bps)
        object.__setattr__(self, "maker_fee_bps", maker_fee_bps)
        object.__setattr__(self, "taker_fee_bps", taker_fee_bps)
        object.__setattr__(
            self,
            "stale_quote_timeout_seconds",
            stale_quote_timeout_seconds,
        )
        object.__setattr__(self, "quote_age_seconds", quote_age_seconds)

    @property
    def intended_pair_cost(self) -> Decimal:
        return self.intended_yes_price + self.intended_no_price

    @property
    def intended_paired_notional_usdc(self) -> Decimal:
        return self.intended_pair_cost * self.pair_size

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "paper_order_intent_generated",
            "schema_version": PAPER_LEDGER_SCHEMA_VERSION,
            "intent_id": self.intent_id,
            "opportunity_id": self.opportunity_id,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "slug": self.slug,
            "symbol": self.symbol,
            "duration_min": self.duration_min,
            "yes_token_id": self.yes_token_id,
            "no_token_id": self.no_token_id,
            "pair_size": _serialize_decimal(self.pair_size),
            "intended_yes_price": _serialize_decimal(self.intended_yes_price),
            "intended_no_price": _serialize_decimal(self.intended_no_price),
            "intended_pair_cost": _serialize_decimal(self.intended_pair_cost),
            "intended_paired_notional_usdc": _serialize_decimal(
                self.intended_paired_notional_usdc
            ),
            "max_capital_per_market_usdc": _serialize_decimal(
                self.max_capital_per_market_usdc
            ),
            "max_open_paired_notional_usdc": _serialize_decimal(
                self.max_open_paired_notional_usdc
            ),
            "maker_rebate_bps": _serialize_decimal(self.maker_rebate_bps),
            "maker_fee_bps": _serialize_decimal(self.maker_fee_bps),
            "taker_fee_bps": _serialize_decimal(self.taker_fee_bps),
            "stale_quote_timeout_seconds": self.stale_quote_timeout_seconds,
            "quote_age_seconds": self.quote_age_seconds,
        }


@dataclass(frozen=True)
class PaperLegFill:
    """One deterministic paper fill record for a YES or NO leg."""

    fill_id: str
    run_id: str
    intent_id: str
    market_id: str
    condition_id: str
    slug: str
    symbol: str
    duration_min: int
    leg: str
    token_id: str
    side: str
    filled_at: str
    price: Decimal
    size: Decimal
    fee_adjustment_usdc: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        for field_name, value in (
            ("fill_id", self.fill_id),
            ("run_id", self.run_id),
            ("intent_id", self.intent_id),
            ("market_id", self.market_id),
            ("condition_id", self.condition_id),
            ("slug", self.slug),
            ("symbol", self.symbol),
            ("leg", self.leg),
            ("token_id", self.token_id),
            ("side", self.side),
            ("filled_at", self.filled_at),
        ):
            object.__setattr__(self, field_name, _require_text(value, field_name))

        price = _coerce_decimal(self.price, "price")
        size = _coerce_decimal(self.size, "size")
        fee_adjustment_usdc = _coerce_decimal(
            self.fee_adjustment_usdc,
            "fee_adjustment_usdc",
        )

        if self.leg.upper() not in _VALID_LEGS:
            raise PaperLedgerValidationError(f"leg must be one of {_VALID_LEGS}")
        if self.side.upper() not in _VALID_SIDES:
            raise PaperLedgerValidationError(f"side must be one of {_VALID_SIDES}")
        if price < _ZERO or price > _ONE:
            raise PaperLedgerValidationError("price must be within [0, 1]")
        if size <= _ZERO:
            raise PaperLedgerValidationError("size must be > 0")

        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "duration_min", _coerce_int(self.duration_min, "duration_min"))
        object.__setattr__(self, "leg", self.leg.upper())
        object.__setattr__(self, "side", self.side.upper())
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "size", size)
        object.__setattr__(self, "fee_adjustment_usdc", fee_adjustment_usdc)

    @property
    def notional_usdc(self) -> Decimal:
        return self.price * self.size

    @property
    def net_cash_delta_usdc(self) -> Decimal:
        signed_notional = -self.notional_usdc if self.side == SIDE_BUY else self.notional_usdc
        return signed_notional + self.fee_adjustment_usdc

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "paper_leg_fill_recorded",
            "schema_version": PAPER_LEDGER_SCHEMA_VERSION,
            "fill_id": self.fill_id,
            "run_id": self.run_id,
            "intent_id": self.intent_id,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "slug": self.slug,
            "symbol": self.symbol,
            "duration_min": self.duration_min,
            "leg": self.leg,
            "token_id": self.token_id,
            "side": self.side,
            "filled_at": self.filled_at,
            "price": _serialize_decimal(self.price),
            "size": _serialize_decimal(self.size),
            "notional_usdc": _serialize_decimal(self.notional_usdc),
            "fee_adjustment_usdc": _serialize_decimal(self.fee_adjustment_usdc),
            "net_cash_delta_usdc": _serialize_decimal(self.net_cash_delta_usdc),
        }


@dataclass(frozen=True)
class PaperLegPosition:
    """Aggregated buy-side fill state for a single leg."""

    leg: str
    token_id: str
    filled_size: Decimal
    average_fill_price: Optional[Decimal]
    gross_notional_usdc: Decimal
    fee_adjustment_usdc: Decimal
    net_cash_delta_usdc: Decimal
    fill_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "leg", _require_text(self.leg, "leg").upper())
        object.__setattr__(self, "token_id", _require_text(self.token_id, "token_id"))
        filled_size = _coerce_decimal(self.filled_size, "filled_size")
        average_fill_price = _normalize_optional_decimal(
            self.average_fill_price,
            "average_fill_price",
        )
        gross_notional_usdc = _coerce_decimal(
            self.gross_notional_usdc,
            "gross_notional_usdc",
        )
        fee_adjustment_usdc = _coerce_decimal(
            self.fee_adjustment_usdc,
            "fee_adjustment_usdc",
        )
        net_cash_delta_usdc = _coerce_decimal(
            self.net_cash_delta_usdc,
            "net_cash_delta_usdc",
        )
        fill_count = _coerce_int(self.fill_count, "fill_count")

        if self.leg not in _VALID_LEGS:
            raise PaperLedgerValidationError(f"leg must be one of {_VALID_LEGS}")
        if filled_size < _ZERO:
            raise PaperLedgerValidationError("filled_size must be >= 0")
        if average_fill_price is not None and (
            average_fill_price < _ZERO or average_fill_price > _ONE
        ):
            raise PaperLedgerValidationError("average_fill_price must be within [0, 1]")
        if filled_size == _ZERO and average_fill_price is not None:
            raise PaperLedgerValidationError(
                "average_fill_price must be None when filled_size is 0"
            )
        if filled_size > _ZERO and average_fill_price is None:
            raise PaperLedgerValidationError(
                "average_fill_price is required when filled_size is > 0"
            )
        if gross_notional_usdc < _ZERO:
            raise PaperLedgerValidationError("gross_notional_usdc must be >= 0")
        if fill_count < 0:
            raise PaperLedgerValidationError("fill_count must be >= 0")

        object.__setattr__(self, "filled_size", filled_size)
        object.__setattr__(self, "average_fill_price", average_fill_price)
        object.__setattr__(self, "gross_notional_usdc", gross_notional_usdc)
        object.__setattr__(self, "fee_adjustment_usdc", fee_adjustment_usdc)
        object.__setattr__(self, "net_cash_delta_usdc", net_cash_delta_usdc)
        object.__setattr__(self, "fill_count", fill_count)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leg": self.leg,
            "token_id": self.token_id,
            "filled_size": _serialize_decimal(self.filled_size),
            "average_fill_price": (
                _serialize_decimal(self.average_fill_price)
                if self.average_fill_price is not None
                else None
            ),
            "gross_notional_usdc": _serialize_decimal(self.gross_notional_usdc),
            "fee_adjustment_usdc": _serialize_decimal(self.fee_adjustment_usdc),
            "net_cash_delta_usdc": _serialize_decimal(self.net_cash_delta_usdc),
            "fill_count": self.fill_count,
        }


@dataclass(frozen=True)
class PaperExposureState:
    """Terminal per-intent exposure state after deterministic fill aggregation."""

    run_id: str
    intent_id: str
    market_id: str
    condition_id: str
    slug: str
    symbol: str
    duration_min: int
    as_of: str
    yes_position: PaperLegPosition
    no_position: PaperLegPosition
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
    exposure_status: str

    def __post_init__(self) -> None:
        for field_name, value in (
            ("run_id", self.run_id),
            ("intent_id", self.intent_id),
            ("market_id", self.market_id),
            ("condition_id", self.condition_id),
            ("slug", self.slug),
            ("symbol", self.symbol),
            ("as_of", self.as_of),
            ("exposure_status", self.exposure_status),
        ):
            object.__setattr__(self, field_name, _require_text(value, field_name))

        if not isinstance(self.yes_position, PaperLegPosition):
            raise PaperLedgerValidationError("yes_position must be a PaperLegPosition")
        if not isinstance(self.no_position, PaperLegPosition):
            raise PaperLedgerValidationError("no_position must be a PaperLegPosition")

        paired_size = _coerce_decimal(self.paired_size, "paired_size")
        paired_cost_usdc = _coerce_decimal(self.paired_cost_usdc, "paired_cost_usdc")
        paired_fee_adjustment_usdc = _coerce_decimal(
            self.paired_fee_adjustment_usdc,
            "paired_fee_adjustment_usdc",
        )
        paired_net_cash_outflow_usdc = _coerce_decimal(
            self.paired_net_cash_outflow_usdc,
            "paired_net_cash_outflow_usdc",
        )
        unpaired_size = _coerce_decimal(self.unpaired_size, "unpaired_size")
        unpaired_average_fill_price = _normalize_optional_decimal(
            self.unpaired_average_fill_price,
            "unpaired_average_fill_price",
        )
        unpaired_notional_usdc = _coerce_decimal(
            self.unpaired_notional_usdc,
            "unpaired_notional_usdc",
        )
        unpaired_fee_adjustment_usdc = _coerce_decimal(
            self.unpaired_fee_adjustment_usdc,
            "unpaired_fee_adjustment_usdc",
        )
        unpaired_net_cash_outflow_usdc = _coerce_decimal(
            self.unpaired_net_cash_outflow_usdc,
            "unpaired_net_cash_outflow_usdc",
        )
        unpaired_max_loss_usdc = _coerce_decimal(
            self.unpaired_max_loss_usdc,
            "unpaired_max_loss_usdc",
        )
        unpaired_max_gain_usdc = _coerce_decimal(
            self.unpaired_max_gain_usdc,
            "unpaired_max_gain_usdc",
        )

        if paired_size < _ZERO or unpaired_size < _ZERO:
            raise PaperLedgerValidationError("paired_size and unpaired_size must be >= 0")
        if paired_cost_usdc < _ZERO or unpaired_notional_usdc < _ZERO:
            raise PaperLedgerValidationError(
                "paired_cost_usdc and unpaired_notional_usdc must be >= 0"
            )
        if self.unpaired_leg is not None and self.unpaired_leg not in _VALID_LEGS:
            raise PaperLedgerValidationError(f"unpaired_leg must be one of {_VALID_LEGS}")
        if unpaired_size == _ZERO and self.unpaired_leg is not None:
            raise PaperLedgerValidationError("unpaired_leg must be None when unpaired_size is 0")
        if unpaired_size > _ZERO and self.unpaired_leg is None:
            raise PaperLedgerValidationError("unpaired_leg is required when unpaired_size > 0")

        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "duration_min", _coerce_int(self.duration_min, "duration_min"))
        object.__setattr__(self, "paired_size", paired_size)
        object.__setattr__(self, "paired_cost_usdc", paired_cost_usdc)
        object.__setattr__(
            self,
            "paired_fee_adjustment_usdc",
            paired_fee_adjustment_usdc,
        )
        object.__setattr__(
            self,
            "paired_net_cash_outflow_usdc",
            paired_net_cash_outflow_usdc,
        )
        object.__setattr__(self, "unpaired_size", unpaired_size)
        object.__setattr__(
            self,
            "unpaired_average_fill_price",
            unpaired_average_fill_price,
        )
        object.__setattr__(self, "unpaired_notional_usdc", unpaired_notional_usdc)
        object.__setattr__(
            self,
            "unpaired_fee_adjustment_usdc",
            unpaired_fee_adjustment_usdc,
        )
        object.__setattr__(
            self,
            "unpaired_net_cash_outflow_usdc",
            unpaired_net_cash_outflow_usdc,
        )
        object.__setattr__(self, "unpaired_max_loss_usdc", unpaired_max_loss_usdc)
        object.__setattr__(self, "unpaired_max_gain_usdc", unpaired_max_gain_usdc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "paper_exposure_state",
            "schema_version": PAPER_LEDGER_SCHEMA_VERSION,
            "run_id": self.run_id,
            "intent_id": self.intent_id,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "slug": self.slug,
            "symbol": self.symbol,
            "duration_min": self.duration_min,
            "as_of": self.as_of,
            "yes_position": self.yes_position.to_dict(),
            "no_position": self.no_position.to_dict(),
            "paired_size": _serialize_decimal(self.paired_size),
            "paired_cost_usdc": _serialize_decimal(self.paired_cost_usdc),
            "paired_fee_adjustment_usdc": _serialize_decimal(
                self.paired_fee_adjustment_usdc
            ),
            "paired_net_cash_outflow_usdc": _serialize_decimal(
                self.paired_net_cash_outflow_usdc
            ),
            "unpaired_leg": self.unpaired_leg,
            "unpaired_size": _serialize_decimal(self.unpaired_size),
            "unpaired_average_fill_price": (
                _serialize_decimal(self.unpaired_average_fill_price)
                if self.unpaired_average_fill_price is not None
                else None
            ),
            "unpaired_notional_usdc": _serialize_decimal(self.unpaired_notional_usdc),
            "unpaired_fee_adjustment_usdc": _serialize_decimal(
                self.unpaired_fee_adjustment_usdc
            ),
            "unpaired_net_cash_outflow_usdc": _serialize_decimal(
                self.unpaired_net_cash_outflow_usdc
            ),
            "unpaired_max_loss_usdc": _serialize_decimal(self.unpaired_max_loss_usdc),
            "unpaired_max_gain_usdc": _serialize_decimal(self.unpaired_max_gain_usdc),
            "exposure_status": self.exposure_status,
        }


@dataclass(frozen=True)
class PaperPairSettlement:
    """Settled PnL for the paired portion of an intent."""

    settlement_id: str
    run_id: str
    intent_id: str
    market_id: str
    condition_id: str
    slug: str
    symbol: str
    duration_min: int
    resolved_at: str
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

    def __post_init__(self) -> None:
        for field_name, value in (
            ("settlement_id", self.settlement_id),
            ("run_id", self.run_id),
            ("intent_id", self.intent_id),
            ("market_id", self.market_id),
            ("condition_id", self.condition_id),
            ("slug", self.slug),
            ("symbol", self.symbol),
            ("resolved_at", self.resolved_at),
            ("winning_leg", self.winning_leg),
        ):
            object.__setattr__(self, field_name, _require_text(value, field_name))

        if self.winning_leg.upper() not in _VALID_LEGS:
            raise PaperLedgerValidationError(f"winning_leg must be one of {_VALID_LEGS}")

        paired_size = _coerce_decimal(self.paired_size, "paired_size")
        paired_cost_usdc = _coerce_decimal(self.paired_cost_usdc, "paired_cost_usdc")
        paired_fee_adjustment_usdc = _coerce_decimal(
            self.paired_fee_adjustment_usdc,
            "paired_fee_adjustment_usdc",
        )
        paired_net_cash_outflow_usdc = _coerce_decimal(
            self.paired_net_cash_outflow_usdc,
            "paired_net_cash_outflow_usdc",
        )
        settlement_value_usdc = _coerce_decimal(
            self.settlement_value_usdc,
            "settlement_value_usdc",
        )
        gross_pnl_usdc = _coerce_decimal(self.gross_pnl_usdc, "gross_pnl_usdc")
        net_pnl_usdc = _coerce_decimal(self.net_pnl_usdc, "net_pnl_usdc")
        unpaired_size = _coerce_decimal(self.unpaired_size, "unpaired_size")

        if paired_size <= _ZERO:
            raise PaperLedgerValidationError("paired_size must be > 0")
        if paired_cost_usdc < _ZERO or settlement_value_usdc < _ZERO:
            raise PaperLedgerValidationError(
                "paired_cost_usdc and settlement_value_usdc must be >= 0"
            )
        if self.unpaired_leg is not None and self.unpaired_leg not in _VALID_LEGS:
            raise PaperLedgerValidationError(f"unpaired_leg must be one of {_VALID_LEGS}")
        if unpaired_size < _ZERO:
            raise PaperLedgerValidationError("unpaired_size must be >= 0")

        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "duration_min", _coerce_int(self.duration_min, "duration_min"))
        object.__setattr__(self, "winning_leg", self.winning_leg.upper())
        object.__setattr__(self, "paired_size", paired_size)
        object.__setattr__(self, "paired_cost_usdc", paired_cost_usdc)
        object.__setattr__(
            self,
            "paired_fee_adjustment_usdc",
            paired_fee_adjustment_usdc,
        )
        object.__setattr__(
            self,
            "paired_net_cash_outflow_usdc",
            paired_net_cash_outflow_usdc,
        )
        object.__setattr__(self, "settlement_value_usdc", settlement_value_usdc)
        object.__setattr__(self, "gross_pnl_usdc", gross_pnl_usdc)
        object.__setattr__(self, "net_pnl_usdc", net_pnl_usdc)
        object.__setattr__(self, "unpaired_size", unpaired_size)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "paper_pair_settlement",
            "schema_version": PAPER_LEDGER_SCHEMA_VERSION,
            "settlement_id": self.settlement_id,
            "run_id": self.run_id,
            "intent_id": self.intent_id,
            "market_id": self.market_id,
            "condition_id": self.condition_id,
            "slug": self.slug,
            "symbol": self.symbol,
            "duration_min": self.duration_min,
            "resolved_at": self.resolved_at,
            "winning_leg": self.winning_leg,
            "paired_size": _serialize_decimal(self.paired_size),
            "paired_cost_usdc": _serialize_decimal(self.paired_cost_usdc),
            "paired_fee_adjustment_usdc": _serialize_decimal(
                self.paired_fee_adjustment_usdc
            ),
            "paired_net_cash_outflow_usdc": _serialize_decimal(
                self.paired_net_cash_outflow_usdc
            ),
            "settlement_value_usdc": _serialize_decimal(self.settlement_value_usdc),
            "gross_pnl_usdc": _serialize_decimal(self.gross_pnl_usdc),
            "net_pnl_usdc": _serialize_decimal(self.net_pnl_usdc),
            "unpaired_leg": self.unpaired_leg,
            "unpaired_size": _serialize_decimal(self.unpaired_size),
        }


@dataclass(frozen=True)
class PaperMarketRollup:
    """Per-market activity summary for one paper-mode run."""

    run_id: str
    market_id: str
    slug: str
    symbol: str
    duration_min: int
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

    def __post_init__(self) -> None:
        for field_name, value in (
            ("run_id", self.run_id),
            ("market_id", self.market_id),
            ("slug", self.slug),
            ("symbol", self.symbol),
        ):
            object.__setattr__(self, field_name, _require_text(value, field_name))
        object.__setattr__(self, "symbol", self.symbol.upper())
        object.__setattr__(self, "duration_min", _coerce_int(self.duration_min, "duration_min"))

        for field_name in (
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
                raise PaperLedgerValidationError(f"{field_name} must be >= 0")
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "paper_market_rollup",
            "schema_version": PAPER_LEDGER_SCHEMA_VERSION,
            "run_id": self.run_id,
            "market_id": self.market_id,
            "slug": self.slug,
            "symbol": self.symbol,
            "duration_min": self.duration_min,
            "opportunities_observed": self.opportunities_observed,
            "threshold_pass_count": self.threshold_pass_count,
            "threshold_miss_count": self.threshold_miss_count,
            "order_intents_generated": self.order_intents_generated,
            "paired_exposure_count": self.paired_exposure_count,
            "partial_exposure_count": self.partial_exposure_count,
            "settled_pair_count": self.settled_pair_count,
            "intended_paired_notional_usdc": _serialize_decimal(
                self.intended_paired_notional_usdc
            ),
            "open_unpaired_notional_usdc": _serialize_decimal(
                self.open_unpaired_notional_usdc
            ),
            "gross_pnl_usdc": _serialize_decimal(self.gross_pnl_usdc),
            "net_pnl_usdc": _serialize_decimal(self.net_pnl_usdc),
        }


@dataclass(frozen=True)
class PaperRunSummary:
    """Per-run aggregate summary across all markets."""

    run_id: str
    generated_at: str
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

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "generated_at",
            _require_text(self.generated_at, "generated_at"),
        )

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
                raise PaperLedgerValidationError(f"{field_name} must be >= 0")
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_type": "paper_run_summary",
            "schema_version": PAPER_LEDGER_SCHEMA_VERSION,
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "markets_seen": self.markets_seen,
            "opportunities_observed": self.opportunities_observed,
            "threshold_pass_count": self.threshold_pass_count,
            "threshold_miss_count": self.threshold_miss_count,
            "order_intents_generated": self.order_intents_generated,
            "paired_exposure_count": self.paired_exposure_count,
            "partial_exposure_count": self.partial_exposure_count,
            "settled_pair_count": self.settled_pair_count,
            "intended_paired_notional_usdc": _serialize_decimal(
                self.intended_paired_notional_usdc
            ),
            "open_unpaired_notional_usdc": _serialize_decimal(
                self.open_unpaired_notional_usdc
            ),
            "gross_pnl_usdc": _serialize_decimal(self.gross_pnl_usdc),
            "net_pnl_usdc": _serialize_decimal(self.net_pnl_usdc),
        }


def get_order_intent_block_reason(
    observation: PaperOpportunityObservation,
    config: CryptoPairPaperModeConfig,
    *,
    pair_size: Decimal | str | float,
    current_market_open_notional_usdc: Decimal | str | float = Decimal("0"),
    current_open_paired_notional_usdc: Decimal | str | float = Decimal("0"),
    has_open_unpaired_exposure: bool = False,
) -> Optional[str]:
    """Return the deterministic reason an order intent is blocked, else ``None``."""

    if not config.allows_market(observation.symbol, observation.duration_min):
        return "filter_miss"
    if (
        config.safety.require_fresh_quotes
        and observation.quote_age_seconds > config.safety.stale_quote_timeout_seconds
    ):
        return "stale_quote"
    if config.safety.block_new_intents_with_open_unpaired and has_open_unpaired_exposure:
        return "open_unpaired_exposure"

    pair_size_decimal = _coerce_decimal(pair_size, "pair_size")
    current_market_open_notional = _coerce_decimal(
        current_market_open_notional_usdc,
        "current_market_open_notional_usdc",
    )
    current_open_paired_notional = _coerce_decimal(
        current_open_paired_notional_usdc,
        "current_open_paired_notional_usdc",
    )

    if pair_size_decimal <= _ZERO:
        raise PaperLedgerValidationError("pair_size must be > 0")
    if current_market_open_notional < _ZERO:
        raise PaperLedgerValidationError(
            "current_market_open_notional_usdc must be >= 0"
        )
    if current_open_paired_notional < _ZERO:
        raise PaperLedgerValidationError(
            "current_open_paired_notional_usdc must be >= 0"
        )

    proposed_notional = observation.paired_quote_cost * pair_size_decimal
    if current_market_open_notional + proposed_notional > config.max_capital_per_market_usdc:
        return "market_cap_exceeded"
    if (
        current_open_paired_notional + proposed_notional
        > config.max_open_paired_notional_usdc
    ):
        return "run_cap_exceeded"
    return None


def generate_order_intent(
    observation: PaperOpportunityObservation,
    config: CryptoPairPaperModeConfig,
    *,
    intent_id: str,
    created_at: str,
    pair_size: Decimal | str | float,
    current_market_open_notional_usdc: Decimal | str | float = Decimal("0"),
    current_open_paired_notional_usdc: Decimal | str | float = Decimal("0"),
    has_open_unpaired_exposure: bool = False,
) -> Optional[PaperOrderIntent]:
    """Create a paper intent when the observation survives all deterministic gates."""

    block_reason = get_order_intent_block_reason(
        observation,
        config,
        pair_size=pair_size,
        current_market_open_notional_usdc=current_market_open_notional_usdc,
        current_open_paired_notional_usdc=current_open_paired_notional_usdc,
        has_open_unpaired_exposure=has_open_unpaired_exposure,
    )
    if block_reason is not None:
        return None

    return PaperOrderIntent(
        intent_id=intent_id,
        opportunity_id=observation.opportunity_id,
        run_id=observation.run_id,
        created_at=created_at,
        market_id=observation.market_id,
        condition_id=observation.condition_id,
        slug=observation.slug,
        symbol=observation.symbol,
        duration_min=observation.duration_min,
        yes_token_id=observation.yes_token_id,
        no_token_id=observation.no_token_id,
        pair_size=_coerce_decimal(pair_size, "pair_size"),
        intended_yes_price=observation.yes_quote_price,
        intended_no_price=observation.no_quote_price,
        max_capital_per_market_usdc=config.max_capital_per_market_usdc,
        max_open_paired_notional_usdc=config.max_open_paired_notional_usdc,
        maker_rebate_bps=config.fees.maker_rebate_bps,
        maker_fee_bps=config.fees.maker_fee_bps,
        taker_fee_bps=config.fees.taker_fee_bps,
        stale_quote_timeout_seconds=config.safety.stale_quote_timeout_seconds,
        quote_age_seconds=observation.quote_age_seconds,
    )


def summarize_leg_fills(
    fills: Iterable[PaperLegFill],
    *,
    leg: str,
    token_id: str,
) -> PaperLegPosition:
    """Aggregate buy-side fills for one leg into a deterministic summary."""

    normalized_leg = _require_text(leg, "leg").upper()
    normalized_token_id = _require_text(token_id, "token_id")
    if normalized_leg not in _VALID_LEGS:
        raise PaperLedgerValidationError(f"leg must be one of {_VALID_LEGS}")

    fill_list = list(fills)
    if not fill_list:
        return PaperLegPosition(
            leg=normalized_leg,
            token_id=normalized_token_id,
            filled_size=_ZERO,
            average_fill_price=None,
            gross_notional_usdc=_ZERO,
            fee_adjustment_usdc=_ZERO,
            net_cash_delta_usdc=_ZERO,
            fill_count=0,
        )

    total_size = _ZERO
    total_notional = _ZERO
    total_fee_adjustment = _ZERO
    total_net_cash_delta = _ZERO

    for fill in fill_list:
        if not isinstance(fill, PaperLegFill):
            raise PaperLedgerValidationError("fills must contain only PaperLegFill records")
        if fill.leg != normalized_leg:
            raise PaperLedgerValidationError(
                f"fill {fill.fill_id} belongs to leg {fill.leg}, expected {normalized_leg}"
            )
        if fill.token_id != normalized_token_id:
            raise PaperLedgerValidationError(
                f"fill {fill.fill_id} token_id mismatch for leg {normalized_leg}"
            )
        if fill.side != SIDE_BUY:
            raise PaperLedgerValidationError(
                "Phase 1A leg summaries only support BUY fills"
            )
        total_size += fill.size
        total_notional += fill.notional_usdc
        total_fee_adjustment += fill.fee_adjustment_usdc
        total_net_cash_delta += fill.net_cash_delta_usdc

    average_fill_price = total_notional / total_size if total_size > _ZERO else None
    return PaperLegPosition(
        leg=normalized_leg,
        token_id=normalized_token_id,
        filled_size=total_size,
        average_fill_price=average_fill_price,
        gross_notional_usdc=total_notional,
        fee_adjustment_usdc=total_fee_adjustment,
        net_cash_delta_usdc=total_net_cash_delta,
        fill_count=len(fill_list),
    )


def compute_partial_leg_exposure(
    intent: PaperOrderIntent,
    fills: Iterable[PaperLegFill],
    *,
    as_of: str,
) -> PaperExposureState:
    """Compute paired and unpaired exposure from the fills attached to one intent."""

    if not isinstance(intent, PaperOrderIntent):
        raise PaperLedgerValidationError("intent must be a PaperOrderIntent")

    fill_list = list(fills)
    for fill in fill_list:
        if fill.intent_id != intent.intent_id:
            raise PaperLedgerValidationError(
                f"fill {fill.fill_id} does not belong to intent {intent.intent_id}"
            )

    yes_fills = [fill for fill in fill_list if fill.leg == LEG_YES]
    no_fills = [fill for fill in fill_list if fill.leg == LEG_NO]
    yes_position = summarize_leg_fills(
        yes_fills,
        leg=LEG_YES,
        token_id=intent.yes_token_id,
    )
    no_position = summarize_leg_fills(
        no_fills,
        leg=LEG_NO,
        token_id=intent.no_token_id,
    )

    paired_size = min(yes_position.filled_size, no_position.filled_size)
    paired_yes_cost = (
        yes_position.average_fill_price * paired_size
        if yes_position.average_fill_price is not None
        else _ZERO
    )
    paired_no_cost = (
        no_position.average_fill_price * paired_size
        if no_position.average_fill_price is not None
        else _ZERO
    )
    paired_cost_usdc = paired_yes_cost + paired_no_cost

    yes_paired_ratio = _decimal_ratio(paired_size, yes_position.filled_size)
    no_paired_ratio = _decimal_ratio(paired_size, no_position.filled_size)
    paired_fee_adjustment_usdc = (
        yes_position.fee_adjustment_usdc * yes_paired_ratio
        + no_position.fee_adjustment_usdc * no_paired_ratio
    )
    paired_net_cash_outflow_usdc = paired_cost_usdc - paired_fee_adjustment_usdc

    unpaired_leg: Optional[str] = None
    unpaired_size = _ZERO
    unpaired_average_fill_price: Optional[Decimal] = None
    unpaired_notional_usdc = _ZERO
    unpaired_fee_adjustment_usdc = _ZERO
    unpaired_net_cash_outflow_usdc = _ZERO

    if yes_position.filled_size > no_position.filled_size:
        unpaired_leg = LEG_YES
        unpaired_size = yes_position.filled_size - paired_size
        unpaired_average_fill_price = yes_position.average_fill_price
        if unpaired_average_fill_price is not None:
            unpaired_notional_usdc = unpaired_average_fill_price * unpaired_size
        unpaired_fee_adjustment_usdc = (
            yes_position.fee_adjustment_usdc
            * _decimal_ratio(unpaired_size, yes_position.filled_size)
        )
    elif no_position.filled_size > yes_position.filled_size:
        unpaired_leg = LEG_NO
        unpaired_size = no_position.filled_size - paired_size
        unpaired_average_fill_price = no_position.average_fill_price
        if unpaired_average_fill_price is not None:
            unpaired_notional_usdc = unpaired_average_fill_price * unpaired_size
        unpaired_fee_adjustment_usdc = (
            no_position.fee_adjustment_usdc
            * _decimal_ratio(unpaired_size, no_position.filled_size)
        )

    if unpaired_size > _ZERO:
        unpaired_net_cash_outflow_usdc = (
            unpaired_notional_usdc - unpaired_fee_adjustment_usdc
        )

    if paired_size > _ZERO and unpaired_size == _ZERO:
        exposure_status = "paired"
    elif unpaired_leg == LEG_YES:
        exposure_status = "partial_yes"
    elif unpaired_leg == LEG_NO:
        exposure_status = "partial_no"
    else:
        exposure_status = "flat"

    unpaired_max_loss_usdc = unpaired_net_cash_outflow_usdc
    unpaired_max_gain_usdc = (
        unpaired_size - unpaired_net_cash_outflow_usdc
        if unpaired_size > _ZERO
        else _ZERO
    )

    return PaperExposureState(
        run_id=intent.run_id,
        intent_id=intent.intent_id,
        market_id=intent.market_id,
        condition_id=intent.condition_id,
        slug=intent.slug,
        symbol=intent.symbol,
        duration_min=intent.duration_min,
        as_of=_require_text(as_of, "as_of"),
        yes_position=yes_position,
        no_position=no_position,
        paired_size=paired_size,
        paired_cost_usdc=paired_cost_usdc,
        paired_fee_adjustment_usdc=paired_fee_adjustment_usdc,
        paired_net_cash_outflow_usdc=paired_net_cash_outflow_usdc,
        unpaired_leg=unpaired_leg,
        unpaired_size=unpaired_size,
        unpaired_average_fill_price=unpaired_average_fill_price,
        unpaired_notional_usdc=unpaired_notional_usdc,
        unpaired_fee_adjustment_usdc=unpaired_fee_adjustment_usdc,
        unpaired_net_cash_outflow_usdc=unpaired_net_cash_outflow_usdc,
        unpaired_max_loss_usdc=unpaired_max_loss_usdc,
        unpaired_max_gain_usdc=unpaired_max_gain_usdc,
        exposure_status=exposure_status,
    )


def compute_pair_settlement_pnl(
    exposure: PaperExposureState,
    *,
    settlement_id: str,
    resolved_at: str,
    winning_leg: str,
) -> PaperPairSettlement:
    """Compute settled PnL for the paired portion of an exposure."""

    if not isinstance(exposure, PaperExposureState):
        raise PaperLedgerValidationError("exposure must be a PaperExposureState")
    if exposure.paired_size <= _ZERO:
        raise PaperLedgerValidationError("paired_size must be > 0 to settle a pair")

    normalized_winning_leg = _require_text(winning_leg, "winning_leg").upper()
    if normalized_winning_leg not in _VALID_LEGS:
        raise PaperLedgerValidationError(f"winning_leg must be one of {_VALID_LEGS}")

    settlement_value_usdc = exposure.paired_size
    gross_pnl_usdc = settlement_value_usdc - exposure.paired_cost_usdc
    net_pnl_usdc = settlement_value_usdc - exposure.paired_net_cash_outflow_usdc

    return PaperPairSettlement(
        settlement_id=settlement_id,
        run_id=exposure.run_id,
        intent_id=exposure.intent_id,
        market_id=exposure.market_id,
        condition_id=exposure.condition_id,
        slug=exposure.slug,
        symbol=exposure.symbol,
        duration_min=exposure.duration_min,
        resolved_at=_require_text(resolved_at, "resolved_at"),
        winning_leg=normalized_winning_leg,
        paired_size=exposure.paired_size,
        paired_cost_usdc=exposure.paired_cost_usdc,
        paired_fee_adjustment_usdc=exposure.paired_fee_adjustment_usdc,
        paired_net_cash_outflow_usdc=exposure.paired_net_cash_outflow_usdc,
        settlement_value_usdc=settlement_value_usdc,
        gross_pnl_usdc=gross_pnl_usdc,
        net_pnl_usdc=net_pnl_usdc,
        unpaired_leg=exposure.unpaired_leg,
        unpaired_size=exposure.unpaired_size,
    )


def build_market_rollups(
    observations: Iterable[PaperOpportunityObservation],
    intents: Iterable[PaperOrderIntent],
    exposures: Iterable[PaperExposureState],
    settlements: Iterable[PaperPairSettlement],
) -> list[PaperMarketRollup]:
    """Roll up final per-market metrics across one run.

    ``exposures`` should contain the final exposure state per intent for the run.
    """

    grouped: dict[
        tuple[str, str, str, int, str],
        dict[str, Any],
    ] = {}

    def _bucket(
        *,
        run_id: str,
        market_id: str,
        slug: str,
        symbol: str,
        duration_min: int,
    ) -> dict[str, Any]:
        key = (run_id, market_id, slug, int(duration_min), symbol.upper())
        if key not in grouped:
            grouped[key] = {
                "run_id": run_id,
                "market_id": market_id,
                "slug": slug,
                "symbol": symbol.upper(),
                "duration_min": int(duration_min),
                "observations": [],
                "intents": [],
                "exposures": [],
                "settlements": [],
            }
        return grouped[key]

    for observation in observations:
        _bucket(
            run_id=observation.run_id,
            market_id=observation.market_id,
            slug=observation.slug,
            symbol=observation.symbol,
            duration_min=observation.duration_min,
        )["observations"].append(observation)

    for intent in intents:
        _bucket(
            run_id=intent.run_id,
            market_id=intent.market_id,
            slug=intent.slug,
            symbol=intent.symbol,
            duration_min=intent.duration_min,
        )["intents"].append(intent)

    for exposure in exposures:
        _bucket(
            run_id=exposure.run_id,
            market_id=exposure.market_id,
            slug=exposure.slug,
            symbol=exposure.symbol,
            duration_min=exposure.duration_min,
        )["exposures"].append(exposure)

    for settlement in settlements:
        _bucket(
            run_id=settlement.run_id,
            market_id=settlement.market_id,
            slug=settlement.slug,
            symbol=settlement.symbol,
            duration_min=settlement.duration_min,
        )["settlements"].append(settlement)

    rollups: list[PaperMarketRollup] = []
    for _, bucket in sorted(grouped.items(), key=lambda item: item[0]):
        observations_list = bucket["observations"]
        intents_list = bucket["intents"]
        exposures_list = bucket["exposures"]
        settlements_list = bucket["settlements"]

        rollups.append(
            PaperMarketRollup(
                run_id=bucket["run_id"],
                market_id=bucket["market_id"],
                slug=bucket["slug"],
                symbol=bucket["symbol"],
                duration_min=bucket["duration_min"],
                opportunities_observed=len(observations_list),
                threshold_pass_count=len(observations_list),
                threshold_miss_count=0,
                order_intents_generated=len(intents_list),
                paired_exposure_count=sum(
                    1 for exposure in exposures_list if exposure.paired_size > _ZERO
                ),
                partial_exposure_count=sum(
                    1 for exposure in exposures_list if exposure.unpaired_size > _ZERO
                ),
                settled_pair_count=len(settlements_list),
                intended_paired_notional_usdc=sum(
                    (intent.intended_paired_notional_usdc for intent in intents_list),
                    start=_ZERO,
                ),
                open_unpaired_notional_usdc=sum(
                    (exposure.unpaired_notional_usdc for exposure in exposures_list),
                    start=_ZERO,
                ),
                gross_pnl_usdc=sum(
                    (settlement.gross_pnl_usdc for settlement in settlements_list),
                    start=_ZERO,
                ),
                net_pnl_usdc=sum(
                    (settlement.net_pnl_usdc for settlement in settlements_list),
                    start=_ZERO,
                ),
            )
        )
    return rollups


def build_run_summary(
    *,
    run_id: str,
    generated_at: str,
    market_rollups: Iterable[PaperMarketRollup],
) -> PaperRunSummary:
    """Aggregate final per-run metrics from per-market rollups."""

    rollups = list(market_rollups)
    if any(not isinstance(rollup, PaperMarketRollup) for rollup in rollups):
        raise PaperLedgerValidationError(
            "market_rollups must contain only PaperMarketRollup records"
        )

    return PaperRunSummary(
        run_id=_require_text(run_id, "run_id"),
        generated_at=_require_text(generated_at, "generated_at"),
        markets_seen=len(rollups),
        opportunities_observed=sum(
            (rollup.opportunities_observed for rollup in rollups),
            start=0,
        ),
        threshold_pass_count=sum(
            (rollup.threshold_pass_count for rollup in rollups),
            start=0,
        ),
        threshold_miss_count=sum(
            (rollup.threshold_miss_count for rollup in rollups),
            start=0,
        ),
        order_intents_generated=sum(
            (rollup.order_intents_generated for rollup in rollups),
            start=0,
        ),
        paired_exposure_count=sum(
            (rollup.paired_exposure_count for rollup in rollups),
            start=0,
        ),
        partial_exposure_count=sum(
            (rollup.partial_exposure_count for rollup in rollups),
            start=0,
        ),
        settled_pair_count=sum(
            (rollup.settled_pair_count for rollup in rollups),
            start=0,
        ),
        intended_paired_notional_usdc=sum(
            (rollup.intended_paired_notional_usdc for rollup in rollups),
            start=_ZERO,
        ),
        open_unpaired_notional_usdc=sum(
            (rollup.open_unpaired_notional_usdc for rollup in rollups),
            start=_ZERO,
        ),
        gross_pnl_usdc=sum(
            (rollup.gross_pnl_usdc for rollup in rollups),
            start=_ZERO,
        ),
        net_pnl_usdc=sum(
            (rollup.net_pnl_usdc for rollup in rollups),
            start=_ZERO,
        ),
    )
