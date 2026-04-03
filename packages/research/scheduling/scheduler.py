"""RIS v1 APScheduler background scheduler.

Registers named periodic jobs for all active RIS ingestion pipelines.
Twitter/X ingestion is explicitly NOT scheduled (deferred -- no live
fetcher exists yet; see RIS_02 social ingestion spec).

Job callables are thin wrappers around existing CLI main() functions.
They accept no arguments (APScheduler calls them with no args).

Usage (programmatic):
    from packages.research.scheduling.scheduler import start_research_scheduler
    scheduler = start_research_scheduler()
    # runs in background; call scheduler.shutdown() to stop

Usage (injectable/testable):
    scheduler = start_research_scheduler(
        _scheduler_factory=lambda: FakeScheduler(),
        _job_runner=my_runner,
    )
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URL lists for batch-fetch jobs
# ---------------------------------------------------------------------------

_REDDIT_OTHERS_URLS = [
    "https://www.reddit.com/r/PredictionMarkets/",
    "https://www.reddit.com/r/Kalshi/",
]

_BLOG_FEED_URLS = [
    "https://polymarket.com/blog",
    "https://manifold.markets/blog",
    "https://blog.metaculus.com",
]

_GITHUB_REPO_URLS = [
    "https://github.com/Polymarket/py-clob-client",
    "https://github.com/Polymarket/polymarket-clob-client",
]

# ---------------------------------------------------------------------------
# JOB_REGISTRY
# ---------------------------------------------------------------------------

JOB_REGISTRY: list[dict] = [
    {
        "id": "academic_ingest",
        "name": "ArXiv academic ingestion",
        "trigger_description": "every 12h at 06:00 and 18:00",
        "callable_name": "_job_run_academic_ingestion",
    },
    {
        "id": "reddit_polymarket",
        "name": "r/polymarket ingestion",
        "trigger_description": "every 6h at 00:00, 06:00, 12:00, 18:00",
        "callable_name": "_job_run_reddit_polymarket",
    },
    {
        "id": "reddit_others",
        "name": "Other subreddits ingestion",
        "trigger_description": "daily at 03:00",
        "callable_name": "_job_run_reddit_others",
    },
    {
        "id": "blog_ingest",
        "name": "Blog/RSS ingestion",
        "trigger_description": "every 4h at 02:00, 06:00, 10:00, 14:00, 18:00, 22:00",
        "callable_name": "_job_run_blog_ingestion",
    },
    {
        "id": "youtube_ingest",
        "name": "YouTube transcript ingestion",
        "trigger_description": "Mondays at 04:00",
        "callable_name": "_job_run_youtube_ingestion",
    },
    {
        "id": "github_ingest",
        "name": "GitHub README ingestion",
        "trigger_description": "Wednesdays at 04:00",
        "callable_name": "_job_run_github_ingestion",
    },
    {
        "id": "freshness_refresh",
        "name": "Freshness tier recalculation",
        "trigger_description": "Sundays at 02:00",
        "callable_name": "_job_run_freshness_refresh",
    },
    {
        "id": "weekly_digest",
        "name": "Weekly research digest",
        "trigger_description": "Sundays at 08:00",
        "callable_name": "_job_run_weekly_digest",
    },
]

# Build a fast lookup: id -> callable_name
_JOB_CALLABLE_MAP: dict[str, str] = {j["id"]: j["callable_name"] for j in JOB_REGISTRY}

# ---------------------------------------------------------------------------
# Job callables
# ---------------------------------------------------------------------------


def _job_run_academic_ingestion() -> None:
    """Run academic ingestion for two prediction-market queries."""
    import tools.cli.research_acquire as research_acquire  # lazy import

    research_acquire.main(
        [
            "--search",
            "prediction markets microstructure",
            "--source-family",
            "academic",
            "--no-eval",
        ]
    )
    research_acquire.main(
        [
            "--search",
            "market microstructure liquidity",
            "--source-family",
            "academic",
            "--no-eval",
        ]
    )


def _job_run_reddit_polymarket() -> None:
    """Ingest r/polymarket subreddit."""
    import tools.cli.research_acquire as research_acquire  # lazy import

    research_acquire.main(
        [
            "--url",
            "https://www.reddit.com/r/polymarket/",
            "--source-family",
            "reddit",
            "--no-eval",
        ]
    )


def _job_run_reddit_others() -> None:
    """Ingest other prediction-market subreddits."""
    import tools.cli.research_acquire as research_acquire  # lazy import

    for url in _REDDIT_OTHERS_URLS:
        research_acquire.main(
            [
                "--url",
                url,
                "--source-family",
                "reddit",
                "--no-eval",
            ]
        )


def _job_run_blog_ingestion() -> None:
    """Ingest prediction-market blog/RSS feeds."""
    import tools.cli.research_acquire as research_acquire  # lazy import

    for url in _BLOG_FEED_URLS:
        research_acquire.main(
            [
                "--url",
                url,
                "--source-family",
                "blog",
                "--no-eval",
            ]
        )


def _job_run_youtube_ingestion() -> None:
    """Ingest YouTube transcripts for prediction-market content."""
    import tools.cli.research_acquire as research_acquire  # lazy import

    research_acquire.main(
        [
            "--url",
            "https://www.youtube.com/results?search_query=prediction+markets",
            "--source-family",
            "youtube",
            "--no-eval",
        ]
    )


def _job_run_github_ingestion() -> None:
    """Ingest GitHub README files for relevant repos."""
    import tools.cli.research_acquire as research_acquire  # lazy import

    for url in _GITHUB_REPO_URLS:
        research_acquire.main(
            [
                "--url",
                url,
                "--source-family",
                "github",
                "--no-eval",
            ]
        )


def _job_run_freshness_refresh() -> None:
    """Lightweight freshness refresh: re-scans recent academic content."""
    import tools.cli.research_acquire as research_acquire  # lazy import

    research_acquire.main(
        [
            "--search",
            "prediction markets 2026",
            "--source-family",
            "academic",
            "--no-eval",
        ]
    )


def _job_run_weekly_digest() -> None:
    """Generate weekly research digest."""
    from tools.cli.research_report import main as report_main  # lazy import

    report_main(["digest", "--window", "7"])


# Map callable name -> actual function object
_JOB_FN_MAP: dict[str, Callable[[], None]] = {
    "_job_run_academic_ingestion": _job_run_academic_ingestion,
    "_job_run_reddit_polymarket": _job_run_reddit_polymarket,
    "_job_run_reddit_others": _job_run_reddit_others,
    "_job_run_blog_ingestion": _job_run_blog_ingestion,
    "_job_run_youtube_ingestion": _job_run_youtube_ingestion,
    "_job_run_github_ingestion": _job_run_github_ingestion,
    "_job_run_freshness_refresh": _job_run_freshness_refresh,
    "_job_run_weekly_digest": _job_run_weekly_digest,
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_job(job_id: str, _run_log_fn: Optional[Callable] = None) -> int:
    """Invoke a single job callable by id.

    Returns 0 on success, 1 on unknown id or exception.

    Parameters
    ----------
    job_id:
        Registered job id (e.g. "academic_ingest").
    _run_log_fn:
        Optional callable that receives a RunRecord after each execution.
        When None, defaults to the real append_run from run_log module
        (lazy import — no coupling at module import time).
        Provide a replacement for offline testing.
    """
    callable_name = _JOB_CALLABLE_MAP.get(job_id)
    if callable_name is None:
        logger.error("run_job: unknown job id %r. Known ids: %s", job_id, list(_JOB_CALLABLE_MAP))
        return 1

    fn = _JOB_FN_MAP.get(callable_name)
    if fn is None:
        logger.error("run_job: callable %r not found in _JOB_FN_MAP", callable_name)
        return 1

    started_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    t0 = time.monotonic()
    exit_status = "ok"
    exit_code = 0

    try:
        fn()
    except Exception:
        logger.exception("run_job: job %r raised an exception", job_id)
        exit_status = "error"
        exit_code = 1
    finally:
        duration_s = time.monotonic() - t0

        # Lazy import of RunRecord and append_run to avoid coupling at module load.
        try:
            from packages.research.monitoring.run_log import RunRecord, append_run  # noqa: PLC0415

            record = RunRecord(
                pipeline=job_id,
                started_at=started_at,
                duration_s=duration_s,
                accepted=0,
                rejected=0,
                errors=0,
                exit_status=exit_status,  # type: ignore[arg-type]
            )
            log_fn = _run_log_fn if _run_log_fn is not None else append_run
            log_fn(record)
        except Exception:
            logger.warning("run_job: failed to write run log for job %r (non-fatal)", job_id)

    return exit_code


def start_research_scheduler(
    _scheduler_factory: Optional[Callable[[], Any]] = None,
    _job_runner: Optional[Callable[[str], None]] = None,
    _run_log_fn: Optional[Callable] = None,
) -> Any:
    """Start the RIS background scheduler with all 8 registered jobs.

    Parameters
    ----------
    _scheduler_factory:
        Optional factory callable that returns a scheduler-like object.
        When provided, used instead of ``BackgroundScheduler()``.
        Useful for offline testing without APScheduler installed.
    _job_runner:
        Optional callable that receives a job_id string and is used as the
        APScheduler job function (instead of the real job callable).
        Useful for offline testing to intercept job registrations.
    _run_log_fn:
        Optional callable that receives a RunRecord after each job execution.
        Threaded through to run_job() in the real background path (else branch).
        When None, run_job() uses the real append_run from run_log module.
        Provide a replacement for offline testing without filesystem side-effects.

    Returns
    -------
    The started scheduler instance.
    """
    # Guard APScheduler import inside function so JOB_REGISTRY is always importable.
    if _scheduler_factory is None:
        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.cron import CronTrigger
        except ImportError as exc:
            raise ImportError(
                "APScheduler is not installed. Install it with: "
                "pip install 'polytool[ris]'  or  pip install 'apscheduler>=3.10.0,<4.0'"
            ) from exc
        scheduler = BackgroundScheduler()
    else:
        # Inject fake scheduler for testing; still need CronTrigger stub if used.
        # When _scheduler_factory is provided we skip real APScheduler entirely.
        try:
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            CronTrigger = None  # type: ignore[assignment,misc]
        scheduler = _scheduler_factory()

    # Build trigger -> schedule mapping
    _triggers = {
        "academic_ingest": {"hour": "6,18"},
        "reddit_polymarket": {"hour": "0,6,12,18"},
        "reddit_others": {"hour": 3},
        "blog_ingest": {"hour": "2,6,10,14,18,22"},
        "youtube_ingest": {"day_of_week": "mon", "hour": 4},
        "github_ingest": {"day_of_week": "wed", "hour": 4},
        "freshness_refresh": {"day_of_week": "sun", "hour": 2},
        "weekly_digest": {"day_of_week": "sun", "hour": 8},
    }

    for job_entry in JOB_REGISTRY:
        jid = job_entry["id"]
        jname = job_entry["name"]
        callable_name = job_entry["callable_name"]

        if _job_runner is not None:
            # Replace job function with the injected runner (passes job_id)
            # Capture jid in default arg to avoid late-binding closure issue
            job_fn: Callable[[], None] = (lambda _jid=jid: _job_runner(_jid))
        else:
            # Always route through run_job() so every background execution is logged.
            # Capture jid and _run_log_fn in default args to avoid late-binding closure.
            job_fn = (lambda _jid=jid, _rlf=_run_log_fn: run_job(_jid, _run_log_fn=_rlf))

        trigger_kwargs = _triggers.get(jid, {})

        if CronTrigger is not None:
            trigger = CronTrigger(**trigger_kwargs)
        else:
            # No APScheduler available (fake scheduler path with no trigger class)
            trigger = trigger_kwargs  # pass dict; fake scheduler ignores it

        scheduler.add_job(job_fn, trigger, id=jid, name=jname)

    scheduler.start()
    return scheduler
