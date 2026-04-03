"""RIS v1 operational layer — alert routing abstraction.

Provides a simple AlertSink interface with two implementations:
- LogSink: default, writes to logging (no network, no config required)
- WebhookSink: optional, POSTs to a webhook URL (requires requests)

Usage::

    from packages.research.monitoring.alert_sink import LogSink, fire_alerts
    from packages.research.monitoring.health_checks import evaluate_health

    sink = LogSink()
    results = evaluate_health(runs)
    count = fire_alerts(results, sink)
"""

from __future__ import annotations

import logging
from typing import List, Protocol, runtime_checkable

from packages.research.monitoring.health_checks import HealthCheckResult

_log = logging.getLogger("ris.alerts")


@runtime_checkable
class AlertSink(Protocol):
    """Protocol for alert routing adapters.

    Implementations must be callable with a single HealthCheckResult
    and return True on success, False on failure. They must never raise.
    """

    def fire(self, result: HealthCheckResult) -> bool:
        """Fire an alert for the given health check result.

        Returns:
            True if the alert was delivered, False otherwise.
            Must never raise.
        """
        ...


class LogSink:
    """Default alert sink — writes to logging, no network calls required.

    All YELLOW results log at WARNING level.
    All RED results log at ERROR level.
    Always returns True.
    """

    def fire(self, result: HealthCheckResult) -> bool:
        """Log the health check result.

        Args:
            result: The HealthCheckResult to log.

        Returns:
            Always True.
        """
        if result.status == "RED":
            _log.error(
                "[RIS ALERT] %s | %s | %s",
                result.status,
                result.check_name,
                result.message,
            )
        else:
            _log.warning(
                "[RIS ALERT] %s | %s | %s",
                result.status,
                result.check_name,
                result.message,
            )
        return True


class WebhookSink:
    """Optional alert sink — POSTs JSON payload to a webhook URL.

    Designed for Discord or generic HTTP webhooks. The ``requests`` library
    is imported lazily inside ``fire()`` so it is not a hard dependency.

    Args:
        webhook_url: Full URL to POST alerts to.
        timeout:     Request timeout in seconds (default 5).
    """

    def __init__(self, webhook_url: str, timeout: float = 5.0) -> None:
        self._url = webhook_url
        self._timeout = timeout

    def fire(self, result: HealthCheckResult) -> bool:
        """POST the health check result as JSON to the webhook URL.

        Args:
            result: The HealthCheckResult to send.

        Returns:
            True if the webhook returned HTTP 200, False on any failure.
            Never raises.
        """
        try:
            import requests  # lazy import — keep optional

            payload = {
                "check_name": result.check_name,
                "status": result.status,
                "message": result.message,
                "data": result.data,
            }
            resp = requests.post(self._url, json=payload, timeout=self._timeout)
            return resp.ok
        except Exception:
            return False


def fire_alerts(
    results: List[HealthCheckResult],
    sink: AlertSink,
    *,
    min_level: str = "YELLOW",
) -> int:
    """Fire alerts for all non-GREEN check results.

    GREEN results are always skipped. YELLOW and RED results are routed to
    ``sink.fire()``.

    Args:
        results:   List of HealthCheckResult objects from evaluate_health().
        sink:      AlertSink implementation to route alerts through.
        min_level: Minimum level to fire (default "YELLOW"). Currently only
                   "YELLOW" is meaningful — all non-GREEN results fire.

    Returns:
        Count of alerts fired (YELLOW + RED results).
    """
    _skip = {"GREEN"}
    fired = 0
    for result in results:
        if result.status not in _skip:
            sink.fire(result)
            fired += 1
    return fired
