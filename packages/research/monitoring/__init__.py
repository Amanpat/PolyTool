"""RIS v1 operational monitoring layer.

Provides pipeline run logs, health condition evaluation, and alert routing
for the Research Intelligence System.

Quick start::

    from packages.research.monitoring import (
        RunRecord, append_run, list_runs, load_last_run,
        evaluate_health, LogSink, fire_alerts,
    )

    # Log a pipeline run
    rec = RunRecord(pipeline="ris_ingest", started_at="...", ...)
    append_run(rec)

    # Evaluate health
    runs = list_runs(window_hours=48)
    results = evaluate_health(runs)

    # Fire alerts for any issues
    sink = LogSink()
    fire_alerts(results, sink)
"""

from packages.research.monitoring.run_log import (
    DEFAULT_RUN_LOG_PATH,
    RunRecord,
    append_run,
    list_runs,
    load_last_run,
)
from packages.research.monitoring.health_checks import (
    ALL_CHECKS,
    HealthCheck,
    HealthCheckResult,
    HealthStatus,
    evaluate_health,
)
from packages.research.monitoring.alert_sink import (
    AlertSink,
    LogSink,
    WebhookSink,
    fire_alerts,
)

__all__ = [
    # run_log
    "DEFAULT_RUN_LOG_PATH",
    "RunRecord",
    "append_run",
    "list_runs",
    "load_last_run",
    # health_checks
    "ALL_CHECKS",
    "HealthCheck",
    "HealthCheckResult",
    "HealthStatus",
    "evaluate_health",
    # alert_sink
    "AlertSink",
    "LogSink",
    "WebhookSink",
    "fire_alerts",
]
