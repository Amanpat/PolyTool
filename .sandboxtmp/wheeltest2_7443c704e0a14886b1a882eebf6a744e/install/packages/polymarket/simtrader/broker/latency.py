"""Latency model for SimTrader broker simulation.

Uses event-tick-based latency (number of tape events elapsed) rather than
wall-clock time.  This keeps replay fully deterministic regardless of event
arrival-rate variations and makes tests trivially reproducible.

Example::

    cfg = LatencyConfig(submit_ticks=2, cancel_ticks=1)
    # Order submitted at seq 10 becomes active at seq 12.
    assert cfg.effective_seq(10) == 12
    # Cancel submitted at seq 15 takes effect at seq 16.
    assert cfg.cancel_effective_seq(15) == 16
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LatencyConfig:
    """Event-tick-based latency configuration.

    Attributes:
        submit_ticks: Number of tape events that must elapse after order
                      submission before the order becomes eligible for fills.
                      0 = order is active on the very same event it is submitted.
        cancel_ticks: Number of tape events that must elapse after a cancel
                      request before the cancel takes effect.
                      0 = cancel is effective on the same event it is requested.
    """

    submit_ticks: int = 0
    cancel_ticks: int = 0

    def effective_seq(self, submit_seq: int) -> int:
        """First tape seq at which this order is eligible for fills."""
        return submit_seq + self.submit_ticks

    def cancel_effective_seq(self, cancel_seq: int) -> int:
        """First tape seq at which a cancel request takes effect."""
        return cancel_seq + self.cancel_ticks


#: Convenience singleton: no latency at all.
ZERO_LATENCY = LatencyConfig(submit_ticks=0, cancel_ticks=0)
