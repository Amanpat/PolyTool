"""Execution layer for SimTrader live trading.

Exports the primary public surface for the execution package.
"""

from packages.polymarket.simtrader.execution.kill_switch import (
    FileBasedKillSwitch,
    KillSwitch,
)
from packages.polymarket.simtrader.execution.live_executor import (
    LiveExecutor,
    OrderRequest,
    OrderResult,
)
from packages.polymarket.simtrader.execution.live_runner import (
    LiveRunConfig,
    LiveRunner,
)
from packages.polymarket.simtrader.execution.rate_limiter import TokenBucketRateLimiter
from packages.polymarket.simtrader.execution.risk_manager import RiskConfig, RiskManager
from packages.polymarket.simtrader.execution.wallet import build_client, derive_and_print_creds

__all__ = [
    "FileBasedKillSwitch",
    "KillSwitch",
    "LiveExecutor",
    "LiveRunConfig",
    "LiveRunner",
    "OrderRequest",
    "OrderResult",
    "RiskConfig",
    "RiskManager",
    "TokenBucketRateLimiter",
    "build_client",
    "derive_and_print_creds",
]
