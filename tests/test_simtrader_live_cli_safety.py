from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch
from packages.polymarket.simtrader.execution.live_executor import (
    LiveExecutor as RealLiveExecutor,
    OrderRequest,
)
from packages.polymarket.simtrader.execution.rate_limiter import TokenBucketRateLimiter
from tools.cli import simtrader


def test_live_cli_defaults_to_dry_run_and_never_calls_client(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    mock_client = MagicMock()
    mock_client.place_order.return_value = {"status": "ok"}
    mock_client.cancel_order.return_value = {"status": "ok"}

    class InjectedLiveExecutor(RealLiveExecutor):
        def __init__(
            self,
            clob_client,
            rate_limiter,
            kill_switch,
            dry_run=True,
            real_client=None,
        ) -> None:
            super().__init__(
                clob_client=mock_client,
                rate_limiter=rate_limiter,
                kill_switch=kill_switch,
                dry_run=dry_run,
                real_client=real_client,
            )

    class ProbingLiveRunner:
        def __init__(self, config, *, executor=None, risk_manager=None) -> None:
            self.config = config
            self._executor = executor or InjectedLiveExecutor(
                clob_client=None,
                rate_limiter=TokenBucketRateLimiter(config.rate_limit_per_min),
                kill_switch=FileBasedKillSwitch(config.kill_switch_path),
                dry_run=config.dry_run,
            )

        def run_once(self, strategy_fn):
            place_result = self._executor.place_order(
                OrderRequest(
                    asset_id="tok_yes",
                    side="BUY",
                    price=Decimal("0.50"),
                    size=Decimal("10"),
                )
            )
            cancel_result = self._executor.cancel_order("order-123")
            return {
                "attempted": 2,
                "submitted": int(place_result.submitted) + int(cancel_result.submitted),
                "rejected": 0,
                "dry_run": self.config.dry_run,
                "reasons": [place_result.reason, cancel_result.reason],
            }

    from packages.polymarket.simtrader.execution import live_runner as live_runner_module

    monkeypatch.setattr(live_runner_module, "LiveRunner", ProbingLiveRunner)

    exit_code = simtrader.main(
        [
            "live",
            "--kill-switch",
            str(tmp_path / "kill_switch.txt"),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert '"dry_run": true' in captured.out
    assert "[simtrader live] mode          : DRY-RUN" in captured.err
    mock_client.place_order.assert_not_called()
    mock_client.cancel_order.assert_not_called()
