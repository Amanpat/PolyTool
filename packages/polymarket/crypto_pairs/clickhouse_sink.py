"""Optional ClickHouse writer for Track 2 crypto-pair events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence

from .event_models import (
    CLICKHOUSE_EVENT_COLUMNS,
    CRYPTO_PAIR_EVENT_SCHEMA_VERSION,
    CRYPTO_PAIR_EVENTS_TABLE,
    CRYPTO_PAIR_EVENT_TYPES,
    CryptoPairTrack2Event,
    project_clickhouse_rows,
)


class CHInsertClient(Protocol):
    """Minimal ClickHouse client contract used by the event sink."""

    def insert_rows(self, table: str, column_names: list[str], rows: list[list[Any]]) -> int:
        ...


@dataclass(frozen=True)
class CryptoPairClickHouseSinkConfig:
    """Opt-in config for the future Track 2 ClickHouse event sink."""

    enabled: bool = False
    table_name: str = CRYPTO_PAIR_EVENTS_TABLE
    clickhouse_host: str = "localhost"
    clickhouse_port: int = 8123
    clickhouse_user: str = "polytool_admin"
    clickhouse_password: str = ""
    soft_fail: bool = True


@dataclass(frozen=True)
class ClickHouseSinkContract:
    """Manifest- and doc-friendly description of the optional sink contract."""

    interface_name: str = "CryptoPairClickHouseSink.write_events"
    enabled: bool = False
    activation_state: str = "disabled_by_default"
    table_name: str = CRYPTO_PAIR_EVENTS_TABLE
    schema_version: str = CRYPTO_PAIR_EVENT_SCHEMA_VERSION
    event_types: tuple[str, ...] = CRYPTO_PAIR_EVENT_TYPES
    notes: tuple[str, ...] = (
        "Track 2 remains JSONL-first until a later packet wires the sink into the runner/store.",
        "The ClickHouse writer is opt-in and does not activate Docker or network use by default.",
        "Event rows target one Grafana-ready table so future dashboards can read from a single source.",
    )

    @classmethod
    def from_config(
        cls,
        config: Optional[CryptoPairClickHouseSinkConfig] = None,
    ) -> "ClickHouseSinkContract":
        resolved = config or CryptoPairClickHouseSinkConfig()
        activation_state = "enabled_opt_in" if resolved.enabled else "disabled_by_default"
        return cls(
            enabled=resolved.enabled,
            activation_state=activation_state,
            table_name=resolved.table_name,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "interface_name": self.interface_name,
            "enabled": self.enabled,
            "activation_state": self.activation_state,
            "table_name": self.table_name,
            "schema_version": self.schema_version,
            "event_types": list(self.event_types),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class ClickHouseWriteResult:
    """Outcome for one attempted event write batch."""

    enabled: bool
    table_name: str
    attempted_events: int
    written_rows: int
    skipped_reason: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "table_name": self.table_name,
            "attempted_events": self.attempted_events,
            "written_rows": self.written_rows,
            "skipped_reason": self.skipped_reason,
            "error": self.error,
        }


class CryptoPairClickHouseEventWriter(Protocol):
    """Writer contract for Track 2 events."""

    def write_events(
        self,
        events: Sequence[CryptoPairTrack2Event],
    ) -> ClickHouseWriteResult:
        ...

    def write_event(self, event: CryptoPairTrack2Event) -> ClickHouseWriteResult:
        ...

    def contract(self) -> ClickHouseSinkContract:
        ...


class DisabledCryptoPairClickHouseSink:
    """Explicit no-op sink used by the default Track 2 path."""

    def __init__(
        self,
        config: Optional[CryptoPairClickHouseSinkConfig] = None,
    ) -> None:
        self.config = config or CryptoPairClickHouseSinkConfig(enabled=False)

    def contract(self) -> ClickHouseSinkContract:
        return ClickHouseSinkContract.from_config(self.config)

    def write_events(
        self,
        events: Sequence[CryptoPairTrack2Event],
    ) -> ClickHouseWriteResult:
        return ClickHouseWriteResult(
            enabled=False,
            table_name=self.config.table_name,
            attempted_events=len(list(events)),
            written_rows=0,
            skipped_reason="disabled",
        )

    def write_event(self, event: CryptoPairTrack2Event) -> ClickHouseWriteResult:
        return self.write_events([event])


class CryptoPairClickHouseSink:
    """Lazy, opt-in ClickHouse writer for Track 2 event batches."""

    def __init__(
        self,
        config: Optional[CryptoPairClickHouseSinkConfig] = None,
        *,
        client: Optional[CHInsertClient] = None,
        max_consecutive_failures: int = 5,
    ) -> None:
        self.config = config or CryptoPairClickHouseSinkConfig()
        self._client = client
        self._consecutive_fail_count: int = 0
        self._max_consecutive_failures: int = max_consecutive_failures

    def contract(self) -> ClickHouseSinkContract:
        return ClickHouseSinkContract.from_config(self.config)

    def write_events(
        self,
        events: Sequence[CryptoPairTrack2Event],
    ) -> ClickHouseWriteResult:
        event_list = list(events)
        if not self.config.enabled:
            return ClickHouseWriteResult(
                enabled=False,
                table_name=self.config.table_name,
                attempted_events=len(event_list),
                written_rows=0,
                skipped_reason="disabled",
            )

        if not event_list:
            return ClickHouseWriteResult(
                enabled=True,
                table_name=self.config.table_name,
                attempted_events=0,
                written_rows=0,
            )

        rows = project_clickhouse_rows(event_list)
        try:
            inserted = self._get_client().insert_rows(
                self.config.table_name,
                list(CLICKHOUSE_EVENT_COLUMNS),
                rows,
            )
        except Exception as exc:
            if not self.config.soft_fail:
                raise
            return ClickHouseWriteResult(
                enabled=True,
                table_name=self.config.table_name,
                attempted_events=len(event_list),
                written_rows=0,
                skipped_reason="write_failed",
                error=str(exc),
            )

        return ClickHouseWriteResult(
            enabled=True,
            table_name=self.config.table_name,
            attempted_events=len(event_list),
            written_rows=inserted,
        )

    def write_event(self, event: CryptoPairTrack2Event) -> ClickHouseWriteResult:
        if self._consecutive_fail_count >= self._max_consecutive_failures:
            return ClickHouseWriteResult(
                enabled=True,
                table_name=self.config.table_name,
                attempted_events=1,
                written_rows=0,
                skipped_reason="consecutive_fail_limit",
            )
        result = self.write_events([event])
        if result.error:
            self._consecutive_fail_count += 1
        else:
            self._consecutive_fail_count = 0
        return result

    def _get_client(self) -> CHInsertClient:
        if self._client is None:
            from packages.polymarket.historical_import.importer import ClickHouseClient

            self._client = ClickHouseClient(
                host=self.config.clickhouse_host,
                port=self.config.clickhouse_port,
                user=self.config.clickhouse_user,
                password=self.config.clickhouse_password,
            )
        return self._client


def build_clickhouse_sink(
    config: Optional[CryptoPairClickHouseSinkConfig] = None,
    *,
    client: Optional[CHInsertClient] = None,
) -> CryptoPairClickHouseEventWriter:
    """Return the default no-op sink unless the caller explicitly enables writes."""

    resolved = config or CryptoPairClickHouseSinkConfig()
    if not resolved.enabled:
        return DisabledCryptoPairClickHouseSink(resolved)
    return CryptoPairClickHouseSink(resolved, client=client)


__all__ = [
    "CHInsertClient",
    "ClickHouseSinkContract",
    "ClickHouseWriteResult",
    "CryptoPairClickHouseEventWriter",
    "CryptoPairClickHouseSink",
    "CryptoPairClickHouseSinkConfig",
    "DisabledCryptoPairClickHouseSink",
    "build_clickhouse_sink",
]
