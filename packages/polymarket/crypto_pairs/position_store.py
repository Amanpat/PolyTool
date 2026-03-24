"""JSONL-first artifact and position store for crypto-pair runner v0."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Optional

from .clickhouse_sink import (
    ClickHouseSinkContract,
    CryptoPairClickHouseEventWriter,
    DisabledCryptoPairClickHouseSink,
)
from .paper_ledger import (
    PaperExposureState,
    PaperLegFill,
    PaperMarketRollup,
    PaperOpportunityObservation,
    PaperOrderIntent,
    PaperPairSettlement,
    PaperRunSummary,
)


RUN_STORE_SCHEMA_VERSION = "crypto_pair_run_store_v0"

_ZERO = Decimal("0")


@dataclass(frozen=True)
class RunArtifactPaths:
    """Resolved artifact paths for one crypto-pair runner invocation."""

    root_dir: Path
    manifest_path: Path
    config_path: Path
    runtime_events_path: Path
    observations_path: Path
    intents_path: Path
    fills_path: Path
    exposures_path: Path
    settlements_path: Path
    market_rollups_path: Path
    run_summary_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "root_dir": str(self.root_dir),
            "manifest_path": str(self.manifest_path),
            "config_path": str(self.config_path),
            "runtime_events_path": str(self.runtime_events_path),
            "observations_path": str(self.observations_path),
            "intents_path": str(self.intents_path),
            "fills_path": str(self.fills_path),
            "exposures_path": str(self.exposures_path),
            "settlements_path": str(self.settlements_path),
            "market_rollups_path": str(self.market_rollups_path),
            "run_summary_path": str(self.run_summary_path),
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


class CryptoPairPositionStore:
    """Append-only JSONL store plus in-memory position view for one run."""

    def __init__(
        self,
        *,
        mode: str,
        artifact_base_dir: Path,
        run_id: Optional[str] = None,
        started_at: Optional[datetime] = None,
        sink: Optional[CryptoPairClickHouseEventWriter] = None,
    ) -> None:
        self.mode = str(mode).strip().lower()
        if self.mode not in {"paper", "live"}:
            raise ValueError(f"mode must be 'paper' or 'live', got {mode!r}")

        self.started_at = started_at or utc_now()
        self.started_at_iso = iso_utc(self.started_at)
        self.run_id = run_id or new_run_id()
        self.artifact_base_dir = Path(artifact_base_dir)
        self.run_dir = self.artifact_base_dir / self.started_at.date().isoformat() / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.paths = RunArtifactPaths(
            root_dir=self.run_dir,
            manifest_path=self.run_dir / "run_manifest.json",
            config_path=self.run_dir / "config_snapshot.json",
            runtime_events_path=self.run_dir / "runtime_events.jsonl",
            observations_path=self.run_dir / "observations.jsonl",
            intents_path=self.run_dir / "order_intents.jsonl",
            fills_path=self.run_dir / "fills.jsonl",
            exposures_path=self.run_dir / "exposures.jsonl",
            settlements_path=self.run_dir / "settlements.jsonl",
            market_rollups_path=self.run_dir / "market_rollups.jsonl",
            run_summary_path=self.run_dir / "run_summary.json",
        )
        self.sink: CryptoPairClickHouseEventWriter = sink or DisabledCryptoPairClickHouseSink()

        self._observations: list[PaperOpportunityObservation] = []
        self._intents: list[PaperOrderIntent] = []
        self._fills: list[PaperLegFill] = []
        self._settlements: list[PaperPairSettlement] = []
        self._market_rollups: list[PaperMarketRollup] = []
        self._run_summary: Optional[PaperRunSummary] = None

        self._fills_by_intent: dict[str, list[PaperLegFill]] = {}
        self._latest_exposure_by_intent: dict[str, PaperExposureState] = {}
        self._latest_intent_by_market: dict[str, PaperOrderIntent] = {}
        self._settled_intent_ids: set[str] = set()
        self._counts: dict[str, int] = {
            "runtime_events": 0,
            "observations": 0,
            "order_intents": 0,
            "fills": 0,
            "exposures": 0,
            "settlements": 0,
            "market_rollups": 0,
        }
        self._stopped_reason = "completed"

    @property
    def observations(self) -> list[PaperOpportunityObservation]:
        return list(self._observations)

    @property
    def intents(self) -> list[PaperOrderIntent]:
        return list(self._intents)

    @property
    def fills(self) -> list[PaperLegFill]:
        return list(self._fills)

    @property
    def settlements(self) -> list[PaperPairSettlement]:
        return list(self._settlements)

    def latest_exposures(self) -> list[PaperExposureState]:
        return list(self._latest_exposure_by_intent.values())

    def write_config_snapshot(self, payload: Mapping[str, Any]) -> None:
        rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
        self.paths.config_path.write_text(rendered + "\n", encoding="utf-8")

    def record_runtime_event(
        self,
        event_type: str,
        *,
        at: Optional[str] = None,
        **payload: Any,
    ) -> None:
        event = {
            "record_type": "runtime_event",
            "schema_version": RUN_STORE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "mode": self.mode,
            "event_type": str(event_type),
            "recorded_at": at or iso_utc(utc_now()),
            "payload": payload,
        }
        self._append_jsonl(self.paths.runtime_events_path, event)
        self._counts["runtime_events"] += 1

    def record_observation(self, observation: PaperOpportunityObservation) -> None:
        self._observations.append(observation)
        self._append_jsonl(self.paths.observations_path, observation.to_dict())
        self._counts["observations"] += 1

    def record_intent(self, intent: PaperOrderIntent) -> None:
        self._intents.append(intent)
        self._latest_intent_by_market[intent.market_id] = intent
        self._append_jsonl(self.paths.intents_path, intent.to_dict())
        self._counts["order_intents"] += 1

    def record_fill(self, fill: PaperLegFill) -> None:
        self._fills.append(fill)
        self._fills_by_intent.setdefault(fill.intent_id, []).append(fill)
        self._append_jsonl(self.paths.fills_path, fill.to_dict())
        self._counts["fills"] += 1

    def fills_for_intent(self, intent_id: str) -> list[PaperLegFill]:
        return list(self._fills_by_intent.get(intent_id, ()))

    def record_exposure(self, exposure: PaperExposureState) -> None:
        self._latest_exposure_by_intent[exposure.intent_id] = exposure
        self._append_jsonl(self.paths.exposures_path, exposure.to_dict())
        self._counts["exposures"] += 1

    def record_settlement(self, settlement: PaperPairSettlement) -> None:
        self._settlements.append(settlement)
        self._settled_intent_ids.add(settlement.intent_id)
        self._append_jsonl(self.paths.settlements_path, settlement.to_dict())
        self._counts["settlements"] += 1

    def record_market_rollups(self, rollups: list[PaperMarketRollup]) -> None:
        self._market_rollups = list(rollups)
        for rollup in rollups:
            self._append_jsonl(self.paths.market_rollups_path, rollup.to_dict())
            self._counts["market_rollups"] += 1

    def record_run_summary(self, summary: PaperRunSummary) -> None:
        self._run_summary = summary
        self.paths.run_summary_path.write_text(
            json.dumps(summary.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )

    def market_leg_sizes(self, market_id: str) -> tuple[Decimal, Decimal]:
        yes_size = _ZERO
        no_size = _ZERO
        for exposure in self._latest_exposure_by_intent.values():
            if exposure.market_id != market_id or exposure.intent_id in self._settled_intent_ids:
                continue
            yes_size += exposure.yes_position.filled_size
            no_size += exposure.no_position.filled_size
        return yes_size, no_size

    def current_market_open_notional_usdc(self, market_id: str) -> Decimal:
        total = _ZERO
        for exposure in self._latest_exposure_by_intent.values():
            if exposure.market_id != market_id or exposure.intent_id in self._settled_intent_ids:
                continue
            total += exposure.paired_net_cash_outflow_usdc
            total += exposure.unpaired_net_cash_outflow_usdc
        return total

    def current_open_paired_notional_usdc(self) -> Decimal:
        total = _ZERO
        for exposure in self._latest_exposure_by_intent.values():
            if exposure.intent_id in self._settled_intent_ids:
                continue
            total += exposure.paired_net_cash_outflow_usdc
        return total

    def has_open_unpaired_exposure(self) -> bool:
        return any(
            exposure.intent_id not in self._settled_intent_ids and exposure.unpaired_size > _ZERO
            for exposure in self._latest_exposure_by_intent.values()
        )

    def open_pair_count(self) -> int:
        count = 0
        for exposure in self._latest_exposure_by_intent.values():
            if exposure.intent_id in self._settled_intent_ids:
                continue
            if exposure.paired_size > _ZERO or exposure.unpaired_size > _ZERO:
                count += 1
        return count

    def estimated_daily_drawdown_usdc(self) -> Decimal:
        realized_losses = _ZERO
        for settlement in self._settlements:
            if settlement.net_pnl_usdc < _ZERO:
                realized_losses += -settlement.net_pnl_usdc

        open_max_loss = _ZERO
        for exposure in self._latest_exposure_by_intent.values():
            if exposure.intent_id in self._settled_intent_ids:
                continue
            open_max_loss += exposure.unpaired_max_loss_usdc

        return realized_losses + open_max_loss

    def finalize(
        self,
        *,
        stopped_reason: str,
        completed_at: Optional[datetime] = None,
        extra_manifest_fields: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        self._stopped_reason = str(stopped_reason)
        completed_dt = completed_at or utc_now()
        config_sha256 = self._sha256_text(self.paths.config_path.read_text(encoding="utf-8")) if self.paths.config_path.exists() else None
        manifest = {
            "schema_version": RUN_STORE_SCHEMA_VERSION,
            "run_id": self.run_id,
            "mode": self.mode,
            "started_at": self.started_at_iso,
            "completed_at": iso_utc(completed_dt),
            "stopped_reason": self._stopped_reason,
            "artifact_dir": str(self.run_dir),
            "artifacts": self.paths.to_dict(),
            "counts": dict(sorted(self._counts.items())),
            "open_pairs_final": self.open_pair_count(),
            "has_open_unpaired_exposure_final": self.has_open_unpaired_exposure(),
            "estimated_daily_drawdown_usdc": str(self.estimated_daily_drawdown_usdc()),
            "clickhouse_sink": self.sink.contract().to_dict(),
            "config_sha256": config_sha256,
        }
        if self._run_summary is not None:
            manifest["run_summary"] = self._run_summary.to_dict()
        if extra_manifest_fields:
            manifest.update(extra_manifest_fields)
        self.paths.manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        return manifest

    def _append_jsonl(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, sort_keys=True, allow_nan=False) + "\n")

    @staticmethod
    def _sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
