"""Config models for Track 2 / Phase 1A crypto-pair paper mode.

The scanner packet can later populate these models, but the config contract is
kept independent from scanner implementation details so the paper ledger can be
fed by any deterministic upstream source.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


CONFIG_SCHEMA_VERSION = "crypto_pair_paper_mode_v0"
SUPPORTED_SYMBOLS = frozenset({"BTC", "ETH", "SOL"})
SUPPORTED_DURATIONS_MIN = frozenset({5, 15})


class CryptoPairPaperConfigError(ValueError):
    """Raised when Phase 1A paper-mode config is invalid."""


def _coerce_decimal(value: Any, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CryptoPairPaperConfigError(
            f"{field_name} must be a decimal-compatible value, got {value!r}"
        ) from exc


def _coerce_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise CryptoPairPaperConfigError(f"{field_name} must be an integer, got bool")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise CryptoPairPaperConfigError(
            f"{field_name} must be an integer-compatible value, got {value!r}"
        ) from exc


def _coerce_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise CryptoPairPaperConfigError(f"{field_name} must be a bool, got {value!r}")
    return value


def _normalize_symbols(symbols: Any) -> tuple[str, ...]:
    if symbols is None:
        symbols = ("BTC", "ETH", "SOL")
    if not isinstance(symbols, (list, tuple)):
        raise CryptoPairPaperConfigError("filters.symbols must be a list or tuple")

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_symbol in symbols:
        symbol = str(raw_symbol).strip().upper()
        if not symbol:
            raise CryptoPairPaperConfigError("filters.symbols cannot contain empty values")
        if symbol not in SUPPORTED_SYMBOLS:
            raise CryptoPairPaperConfigError(
                f"filters.symbols contains unsupported symbol {symbol!r}"
            )
        if symbol not in seen:
            normalized.append(symbol)
            seen.add(symbol)

    if not normalized:
        raise CryptoPairPaperConfigError("filters.symbols must contain at least one symbol")
    return tuple(normalized)


def _normalize_durations(durations_min: Any) -> tuple[int, ...]:
    if durations_min is None:
        durations_min = (5, 15)
    if not isinstance(durations_min, (list, tuple)):
        raise CryptoPairPaperConfigError(
            "filters.durations_min must be a list or tuple"
        )

    normalized: list[int] = []
    seen: set[int] = set()
    for raw_duration in durations_min:
        duration = _coerce_int(raw_duration, "filters.durations_min[]")
        if duration not in SUPPORTED_DURATIONS_MIN:
            raise CryptoPairPaperConfigError(
                f"filters.durations_min contains unsupported duration {duration!r}"
            )
        if duration not in seen:
            normalized.append(duration)
            seen.add(duration)

    if not normalized:
        raise CryptoPairPaperConfigError(
            "filters.durations_min must contain at least one duration"
        )
    return tuple(normalized)


def _ensure_mapping(raw: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(raw, Mapping):
        raise CryptoPairPaperConfigError(f"{field_name} must be an object-like mapping")
    return raw


@dataclass(frozen=True)
class CryptoPairFilterConfig:
    """Symbol and duration filters for the paper-mode decision surface."""

    symbols: tuple[str, ...] = ("BTC", "ETH", "SOL")
    durations_min: tuple[int, ...] = (5, 15)

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbols", _normalize_symbols(self.symbols))
        object.__setattr__(self, "durations_min", _normalize_durations(self.durations_min))

    def matches(self, symbol: str, duration_min: int) -> bool:
        return str(symbol).upper() in self.symbols and int(duration_min) in self.durations_min

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbols": list(self.symbols),
            "durations_min": list(self.durations_min),
        }

    @classmethod
    def from_dict(cls, raw: Any | None) -> "CryptoPairFilterConfig":
        if raw is None:
            return cls()
        data = _ensure_mapping(raw, "filters")
        return cls(
            symbols=tuple(data.get("symbols", ("BTC", "ETH", "SOL"))),
            durations_min=tuple(data.get("durations_min", (5, 15))),
        )


@dataclass(frozen=True)
class CryptoPairFeeAssumptionConfig:
    """Explicit fee and rebate assumptions.

    These are strategy assumptions only. They are not proof of current
    exchange behavior.
    """

    maker_rebate_bps: Decimal = Decimal("20")
    maker_fee_bps: Decimal = Decimal("0")
    taker_fee_bps: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        maker_rebate_bps = _coerce_decimal(self.maker_rebate_bps, "fees.maker_rebate_bps")
        maker_fee_bps = _coerce_decimal(self.maker_fee_bps, "fees.maker_fee_bps")
        taker_fee_bps = _coerce_decimal(self.taker_fee_bps, "fees.taker_fee_bps")

        if maker_rebate_bps < 0:
            raise CryptoPairPaperConfigError("fees.maker_rebate_bps must be >= 0")
        if maker_fee_bps < 0:
            raise CryptoPairPaperConfigError("fees.maker_fee_bps must be >= 0")
        if taker_fee_bps < 0:
            raise CryptoPairPaperConfigError("fees.taker_fee_bps must be >= 0")
        if maker_rebate_bps > 0 and maker_fee_bps > 0:
            raise CryptoPairPaperConfigError(
                "fees.maker_rebate_bps and fees.maker_fee_bps cannot both be positive"
            )

        object.__setattr__(self, "maker_rebate_bps", maker_rebate_bps)
        object.__setattr__(self, "maker_fee_bps", maker_fee_bps)
        object.__setattr__(self, "taker_fee_bps", taker_fee_bps)

    @property
    def maker_adjustment_bps(self) -> Decimal:
        return self.maker_rebate_bps - self.maker_fee_bps

    def to_dict(self) -> dict[str, Any]:
        return {
            "maker_rebate_bps": str(self.maker_rebate_bps),
            "maker_fee_bps": str(self.maker_fee_bps),
            "taker_fee_bps": str(self.taker_fee_bps),
            "maker_adjustment_bps": str(self.maker_adjustment_bps),
        }

    @classmethod
    def from_dict(cls, raw: Any | None) -> "CryptoPairFeeAssumptionConfig":
        if raw is None:
            return cls()
        data = _ensure_mapping(raw, "fees")
        return cls(
            maker_rebate_bps=data.get("maker_rebate_bps", Decimal("20")),
            maker_fee_bps=data.get("maker_fee_bps", Decimal("0")),
            taker_fee_bps=data.get("taker_fee_bps", Decimal("0")),
        )


@dataclass(frozen=True)
class CryptoPairSafetyConfig:
    """Safety knobs for paper-mode gating."""

    stale_quote_timeout_seconds: int = 15
    max_unpaired_exposure_seconds: int = 120
    block_new_intents_with_open_unpaired: bool = True
    require_fresh_quotes: bool = True

    def __post_init__(self) -> None:
        stale_quote_timeout_seconds = _coerce_int(
            self.stale_quote_timeout_seconds,
            "safety.stale_quote_timeout_seconds",
        )
        max_unpaired_exposure_seconds = _coerce_int(
            self.max_unpaired_exposure_seconds,
            "safety.max_unpaired_exposure_seconds",
        )
        if stale_quote_timeout_seconds <= 0:
            raise CryptoPairPaperConfigError(
                "safety.stale_quote_timeout_seconds must be > 0"
            )
        if max_unpaired_exposure_seconds <= 0:
            raise CryptoPairPaperConfigError(
                "safety.max_unpaired_exposure_seconds must be > 0"
            )

        object.__setattr__(
            self,
            "stale_quote_timeout_seconds",
            stale_quote_timeout_seconds,
        )
        object.__setattr__(
            self,
            "max_unpaired_exposure_seconds",
            max_unpaired_exposure_seconds,
        )
        object.__setattr__(
            self,
            "block_new_intents_with_open_unpaired",
            _coerce_bool(
                self.block_new_intents_with_open_unpaired,
                "safety.block_new_intents_with_open_unpaired",
            ),
        )
        object.__setattr__(
            self,
            "require_fresh_quotes",
            _coerce_bool(self.require_fresh_quotes, "safety.require_fresh_quotes"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "stale_quote_timeout_seconds": self.stale_quote_timeout_seconds,
            "max_unpaired_exposure_seconds": self.max_unpaired_exposure_seconds,
            "block_new_intents_with_open_unpaired": (
                self.block_new_intents_with_open_unpaired
            ),
            "require_fresh_quotes": self.require_fresh_quotes,
        }

    @classmethod
    def from_dict(cls, raw: Any | None) -> "CryptoPairSafetyConfig":
        if raw is None:
            return cls()
        data = _ensure_mapping(raw, "safety")
        return cls(
            stale_quote_timeout_seconds=data.get("stale_quote_timeout_seconds", 15),
            max_unpaired_exposure_seconds=data.get("max_unpaired_exposure_seconds", 120),
            block_new_intents_with_open_unpaired=data.get(
                "block_new_intents_with_open_unpaired",
                True,
            ),
            require_fresh_quotes=data.get("require_fresh_quotes", True),
        )


@dataclass(frozen=True)
class MomentumConfig:
    """Directional momentum strategy parameters for Phase 1A crypto pair bot.

    These parameters control the momentum signal and entry sizing for the
    gabagool22-modeled directional strategy.
    """

    momentum_window_seconds: int = 30
    momentum_threshold: float = 0.003   # 0.3% price change triggers a signal
    max_favorite_entry: float = 0.75    # don't buy favorite leg above this price
    max_hedge_price: float = 0.20       # max price for hedge leg limit order
    favorite_leg_size_usdc: float = 8.0
    hedge_leg_size_usdc: float = 2.0

    def __post_init__(self) -> None:
        momentum_window_seconds = _coerce_int(
            self.momentum_window_seconds, "momentum.momentum_window_seconds"
        )
        if momentum_window_seconds <= 0:
            raise CryptoPairPaperConfigError(
                "momentum.momentum_window_seconds must be > 0"
            )
        object.__setattr__(self, "momentum_window_seconds", momentum_window_seconds)

        for float_field, name in (
            (self.momentum_threshold, "momentum.momentum_threshold"),
            (self.max_favorite_entry, "momentum.max_favorite_entry"),
            (self.max_hedge_price, "momentum.max_hedge_price"),
            (self.favorite_leg_size_usdc, "momentum.favorite_leg_size_usdc"),
            (self.hedge_leg_size_usdc, "momentum.hedge_leg_size_usdc"),
        ):
            try:
                val = float(float_field)
            except (TypeError, ValueError) as exc:
                raise CryptoPairPaperConfigError(
                    f"{name} must be a float-compatible value"
                ) from exc
            object.__setattr__(self, name.split(".")[-1], val)

        if self.momentum_threshold <= 0:
            raise CryptoPairPaperConfigError(
                "momentum.momentum_threshold must be > 0"
            )
        if not (0 < self.max_favorite_entry < 1):
            raise CryptoPairPaperConfigError(
                "momentum.max_favorite_entry must be in (0, 1)"
            )
        if not (0 < self.max_hedge_price < 1):
            raise CryptoPairPaperConfigError(
                "momentum.max_hedge_price must be in (0, 1)"
            )
        if self.favorite_leg_size_usdc <= 0:
            raise CryptoPairPaperConfigError(
                "momentum.favorite_leg_size_usdc must be > 0"
            )
        if self.hedge_leg_size_usdc <= 0:
            raise CryptoPairPaperConfigError(
                "momentum.hedge_leg_size_usdc must be > 0"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "momentum_window_seconds": self.momentum_window_seconds,
            "momentum_threshold": self.momentum_threshold,
            "max_favorite_entry": self.max_favorite_entry,
            "max_hedge_price": self.max_hedge_price,
            "favorite_leg_size_usdc": self.favorite_leg_size_usdc,
            "hedge_leg_size_usdc": self.hedge_leg_size_usdc,
        }

    @classmethod
    def from_dict(cls, raw: Any | None) -> "MomentumConfig":
        if raw is None:
            return cls()
        data = _ensure_mapping(raw, "momentum")
        return cls(
            momentum_window_seconds=data.get("momentum_window_seconds", 30),
            momentum_threshold=data.get("momentum_threshold", 0.003),
            max_favorite_entry=data.get("max_favorite_entry", 0.75),
            max_hedge_price=data.get("max_hedge_price", 0.20),
            favorite_leg_size_usdc=data.get("favorite_leg_size_usdc", 8.0),
            hedge_leg_size_usdc=data.get("hedge_leg_size_usdc", 2.0),
        )


@dataclass(frozen=True)
class CryptoPairPaperModeConfig:
    """Phase 1A paper-mode config contract."""

    filters: CryptoPairFilterConfig = field(default_factory=CryptoPairFilterConfig)
    max_capital_per_market_usdc: Decimal = Decimal("250")
    max_open_paired_notional_usdc: Decimal = Decimal("500")
    edge_buffer_per_leg: Decimal = Decimal("0.04")
    max_pair_completion_pct: Decimal = Decimal("0.80")
    min_projected_profit: Decimal = Decimal("0.03")
    fees: CryptoPairFeeAssumptionConfig = field(
        default_factory=CryptoPairFeeAssumptionConfig
    )
    safety: CryptoPairSafetyConfig = field(default_factory=CryptoPairSafetyConfig)
    momentum: MomentumConfig = field(default_factory=MomentumConfig)

    def __post_init__(self) -> None:
        filters = (
            CryptoPairFilterConfig.from_dict(self.filters)
            if isinstance(self.filters, Mapping)
            else self.filters
        )
        fees = (
            CryptoPairFeeAssumptionConfig.from_dict(self.fees)
            if isinstance(self.fees, Mapping)
            else self.fees
        )
        safety = (
            CryptoPairSafetyConfig.from_dict(self.safety)
            if isinstance(self.safety, Mapping)
            else self.safety
        )
        momentum = (
            MomentumConfig.from_dict(self.momentum)
            if isinstance(self.momentum, Mapping)
            else self.momentum
        )

        if not isinstance(filters, CryptoPairFilterConfig):
            raise CryptoPairPaperConfigError("filters must be a CryptoPairFilterConfig")
        if not isinstance(fees, CryptoPairFeeAssumptionConfig):
            raise CryptoPairPaperConfigError("fees must be a CryptoPairFeeAssumptionConfig")
        if not isinstance(safety, CryptoPairSafetyConfig):
            raise CryptoPairPaperConfigError(
                "safety must be a CryptoPairSafetyConfig"
            )
        if not isinstance(momentum, MomentumConfig):
            raise CryptoPairPaperConfigError(
                "momentum must be a MomentumConfig"
            )

        max_capital_per_market_usdc = _coerce_decimal(
            self.max_capital_per_market_usdc,
            "max_capital_per_market_usdc",
        )
        max_open_paired_notional_usdc = _coerce_decimal(
            self.max_open_paired_notional_usdc,
            "max_open_paired_notional_usdc",
        )
        edge_buffer_per_leg = _coerce_decimal(
            self.edge_buffer_per_leg,
            "edge_buffer_per_leg",
        )
        max_pair_completion_pct = _coerce_decimal(
            self.max_pair_completion_pct,
            "max_pair_completion_pct",
        )
        min_projected_profit = _coerce_decimal(
            self.min_projected_profit,
            "min_projected_profit",
        )

        if max_capital_per_market_usdc <= 0:
            raise CryptoPairPaperConfigError("max_capital_per_market_usdc must be > 0")
        if max_open_paired_notional_usdc <= 0:
            raise CryptoPairPaperConfigError(
                "max_open_paired_notional_usdc must be > 0"
            )
        if max_capital_per_market_usdc > max_open_paired_notional_usdc:
            raise CryptoPairPaperConfigError(
                "max_capital_per_market_usdc cannot exceed max_open_paired_notional_usdc"
            )
        if edge_buffer_per_leg < 0 or edge_buffer_per_leg >= Decimal("0.5"):
            raise CryptoPairPaperConfigError(
                "edge_buffer_per_leg must be >= 0 and < 0.5"
            )
        if max_pair_completion_pct <= 0 or max_pair_completion_pct > 1:
            raise CryptoPairPaperConfigError(
                "max_pair_completion_pct must be > 0 and <= 1"
            )
        if min_projected_profit < 0:
            raise CryptoPairPaperConfigError("min_projected_profit must be >= 0")

        object.__setattr__(self, "filters", filters)
        object.__setattr__(self, "fees", fees)
        object.__setattr__(self, "safety", safety)
        object.__setattr__(self, "momentum", momentum)
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
        object.__setattr__(self, "edge_buffer_per_leg", edge_buffer_per_leg)
        object.__setattr__(self, "max_pair_completion_pct", max_pair_completion_pct)
        object.__setattr__(self, "min_projected_profit", min_projected_profit)

    def allows_market(self, symbol: str, duration_min: int) -> bool:
        return self.filters.matches(symbol, duration_min)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "filters": self.filters.to_dict(),
            "max_capital_per_market_usdc": str(self.max_capital_per_market_usdc),
            "max_open_paired_notional_usdc": str(self.max_open_paired_notional_usdc),
            "edge_buffer_per_leg": str(self.edge_buffer_per_leg),
            "max_pair_completion_pct": str(self.max_pair_completion_pct),
            "min_projected_profit": str(self.min_projected_profit),
            "fees": self.fees.to_dict(),
            "safety": self.safety.to_dict(),
            "momentum": self.momentum.to_dict(),
        }

    @classmethod
    def from_dict(cls, raw: Any | None) -> "CryptoPairPaperModeConfig":
        if raw is None:
            return cls()
        data = _ensure_mapping(raw, "config")
        # Silently ignore legacy target_pair_cost_threshold key for backward compat
        return cls(
            filters=CryptoPairFilterConfig.from_dict(data.get("filters")),
            max_capital_per_market_usdc=data.get("max_capital_per_market_usdc", "250"),
            max_open_paired_notional_usdc=data.get(
                "max_open_paired_notional_usdc",
                "500",
            ),
            edge_buffer_per_leg=data.get("edge_buffer_per_leg", "0.04"),
            max_pair_completion_pct=data.get("max_pair_completion_pct", "0.80"),
            min_projected_profit=data.get("min_projected_profit", "0.03"),
            fees=CryptoPairFeeAssumptionConfig.from_dict(data.get("fees")),
            safety=CryptoPairSafetyConfig.from_dict(data.get("safety")),
            momentum=MomentumConfig.from_dict(data.get("momentum")),
        )
