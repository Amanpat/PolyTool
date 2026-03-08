"""LiveRunner: top-level orchestrator for the live execution layer.

Wires strategy -> risk manager -> executor for a single execution tick.
Dry-run is the default; real order submission requires explicit opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Optional

from packages.polymarket.simtrader.execution.kill_switch import (
    FileBasedKillSwitch,
    KillSwitch,
)
from packages.polymarket.simtrader.execution.live_executor import (
    LiveExecutor,
    OrderRequest,
    OrderResult,
)
from packages.polymarket.simtrader.execution.rate_limiter import TokenBucketRateLimiter
from packages.polymarket.simtrader.execution.risk_manager import RiskConfig, RiskManager


@dataclass
class LiveRunConfig:
    """Configuration for LiveRunner.

    All defaults are Stage-0 conservative values.

    Attributes:
        dry_run:              Never submit real orders when True (default: True).
        rate_limit_per_min:   Max API calls per minute (default: 30, well under 60).
        kill_switch_path:     Path to the kill-switch sentinel file.
        risk_config:          Risk limits; uses RiskConfig defaults if not provided.
        clob_client:          Optional authenticated py_clob_client instance for
                              live order placement.
    """

    dry_run: bool = True
    rate_limit_per_min: int = 30
    kill_switch_path: Path = field(default_factory=lambda: Path("artifacts/kill_switch.txt"))
    risk_config: RiskConfig = field(default_factory=RiskConfig)
    clob_client: Any = None


# A strategy_fn receives no arguments and returns a list of OrderRequests.
StrategyFn = Callable[[], list[OrderRequest]]


class LiveRunner:
    """Orchestrates a single strategy tick with risk + executor integration.

    Args:
        config:   LiveRunConfig instance.
        executor: Optional pre-built LiveExecutor (for testing/injection).
        risk_manager: Optional pre-built RiskManager (for testing/injection).
    """

    def __init__(
        self,
        config: Optional[LiveRunConfig] = None,
        *,
        executor: Optional[LiveExecutor] = None,
        risk_manager: Optional[RiskManager] = None,
    ) -> None:
        self.config = config or LiveRunConfig()

        self._risk = risk_manager or RiskManager(self.config.risk_config)

        if executor is not None:
            self._executor = executor
        else:
            ks: KillSwitch = FileBasedKillSwitch(self.config.kill_switch_path)
            limiter = TokenBucketRateLimiter(self.config.rate_limit_per_min)
            real_client = (
                self.config.clob_client
                if self.config.clob_client is not None and not self.config.dry_run
                else None
            )
            self._executor = LiveExecutor(
                clob_client=None,  # No client in dry-run mode
                rate_limiter=limiter,
                kill_switch=ks,
                dry_run=self.config.dry_run,
                real_client=real_client,
            )

    def run_once(self, strategy_fn: StrategyFn) -> dict[str, Any]:
        """Execute one tick of strategy_fn and return a summary dict.

        The kill switch is checked once before calling the strategy.  Each
        order returned by strategy_fn is validated by the RiskManager before
        being forwarded to the LiveExecutor.

        Args:
            strategy_fn: Zero-argument callable returning list[OrderRequest].

        Returns:
            Summary dict with keys:
                attempted  — total orders from strategy
                submitted  — orders sent to exchange (0 in dry-run)
                rejected   — orders blocked by risk
                dry_run    — whether dry_run mode was active
                reasons    — list of rejection reason strings
        """
        # Kill-switch check before strategy is called.
        self._executor._ks.check_or_raise()

        requests: list[OrderRequest] = strategy_fn()

        attempted = len(requests)
        submitted = 0
        rejected = 0
        reasons: list[str] = []
        results: list[OrderResult] = []

        for req in requests:
            allowed, reason = self._risk.check_order(
                asset_id=req.asset_id,
                side=req.side,
                price=req.price,
                size=req.size,
            )
            if not allowed:
                rejected += 1
                reasons.append(reason)
                continue

            result = self._executor.place_order(req)
            results.append(result)

            if result.submitted:
                submitted += 1

        return {
            "attempted": attempted,
            "submitted": submitted,
            "rejected": rejected,
            "dry_run": self.config.dry_run,
            "reasons": reasons,
        }
