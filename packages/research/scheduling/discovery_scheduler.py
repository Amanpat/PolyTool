"""WI-3 Wallet-Discovery APScheduler background scheduler.

Schedules the three discovery cadences by REUSING the exact RIS scheduler
pattern (``packages.research.scheduling.scheduler``): a JOB_REGISTRY of named
jobs, thin no-arg job callables, a ``run_*_job`` dispatcher, and a
``start_*_scheduler(_scheduler_factory=..., _job_runner=...)`` injectable
launcher. No second scheduler framework is introduced (gate 1). The existing
RIS ``JOB_REGISTRY`` / ``start_research_scheduler`` are NOT modified (gate 2);
this is a parallel registration path living in its own module + its own
DISCOVERY_JOB_REGISTRY.

Jobs
----
- ``discovery_loop_a``  : invoke Loop A (leaderboard fetch -> churn -> enqueue).
- ``watchlist_rescan``  : enqueue stale watchlist members by resolved tier,
                          applying tier-aware skip-if-recent.
- ``queue_drain``       : run ONE bounded ScanWorker tick draining the queue.

Drain model (single-worker safety)
-----------------------------------
``queue_drain`` runs a single bounded ``ScanWorker.run(max_items=N)`` per fire
-- NOT a long-lived continuous worker. WI-1's ScanWorker explicitly documents a
single-worker assumption: ClickHouse leases are not an atomic compare-and-set,
so two concurrent drainers can double-grab a dedup_key. One scheduled tick =
one bounded drain = exactly one drainer alive at a time, which keeps us inside
WI-1's safety envelope without adding lease atomicity (that remains a future
concern if continuous/multi-worker drain is ever needed).

Tier resolution (forward-compatible; full tiers land in WI-4)
-------------------------------------------------------------
WI-3's packet references watchlist *tiers* (locked / candidate) for both
skip-if-recent windows and scan-queue priority. Those tier/locked columns are
NOT built yet -- they are WI-4, which runs AFTER WI-3. ``resolve_tier`` therefore
reads tier/locked columns IF they exist (column-presence guarded) and ELSE
falls back to the existing ``lifecycle_state`` / ``source`` fields. When WI-4
adds real ``tier`` / ``locked`` columns + populates them, the SAME resolver
starts honoring them with no rework here.

Config
------
All cadences, skip-if-recent windows, and tier->priority mapping are loaded
defensively from ``config/discovery_scheduler.json`` (operator-tunable, no code
change). Missing keys fall back to the documented defaults below.

Usage (programmatic):
    from packages.research.scheduling.discovery_scheduler import start_discovery_scheduler
    scheduler = start_discovery_scheduler(ch_password=os.environ["CLICKHOUSE_PASSWORD"])

Usage (injectable/testable):
    scheduler = start_discovery_scheduler(
        _scheduler_factory=lambda: FakeScheduler(),
        _job_runner=my_runner,
    )

OUT OF SCOPE (WI-3 guards): no Alchemy/WebSocket/real-time (deferred Loop B);
no n8n; no Kalshi; does not touch kill switch / signing / execution / risk.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cooperative drain-stop signal (DR-0-FIX bounded shutdown)
# ---------------------------------------------------------------------------
#
# A process-wide Event the SIGTERM/SIGINT handler sets so an in-flight
# ``queue_drain`` tick (running on an APScheduler job thread) stops leasing new
# wallets BETWEEN wallets and returns promptly. ScanWorker.run(should_stop=...)
# polls ``drain_stop_requested``. The scheduler and the drain job share one
# process, so a module-level Event is the correct scope.
_DRAIN_STOP = threading.Event()


def request_drain_stop() -> None:
    """Signal any in-flight drain tick to stop between wallets (idempotent)."""
    _DRAIN_STOP.set()


def clear_drain_stop() -> None:
    """Reset the drain-stop flag (called when (re)starting the scheduler)."""
    _DRAIN_STOP.clear()


def drain_stop_requested() -> bool:
    """True once a graceful stop has been requested."""
    return _DRAIN_STOP.is_set()

# ---------------------------------------------------------------------------
# Config loading (defensive — every key has a fallback default)
# ---------------------------------------------------------------------------

# Repo root is four parents up from this file: packages/research/scheduling/<file>
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "discovery_scheduler.json"

# Hardcoded fallbacks used only when the config file / a key is missing.
# These mirror config/discovery_scheduler.json so behavior is identical whether
# or not the file is present.
_DEFAULT_CADENCES: dict[str, dict] = {
    "discovery_loop_a": {"hour": "*/6"},
    "watchlist_rescan": {"hour": "1,13"},
    "queue_drain": {"minute": "*/15"},
}
_DEFAULT_SKIP_IF_RECENT: dict[str, int] = {
    "locked_hours": 6,
    "candidate_hours": 24,
    "discovered_hours": 336,  # 14 days
    "rest_hours": 720,        # 30 days
}
_DEFAULT_TIER_PRIORITY: dict[str, int] = {
    "locked": 1,
    "candidate": 2,
    "discovered": 3,
    "rest": 4,
}
_DEFAULT_QUEUE_DRAIN: dict[str, Any] = {
    "max_items": 10,
    "max_attempts": 5,
    "lease_seconds": 300,
    "owner": "discovery-scheduler",
    # DR-0-FIX: drain-scoped per-request HTTP timeout (seconds). Well under the
    # Docker stop grace so an in-flight wallet's scan cannot run for minutes on a
    # slow/hung endpoint (the global scan default is 120s). Only the scheduler
    # drain process sets this; the foreground `wallet-scan` path is unaffected.
    "request_timeout_seconds": 15,
}
_DEFAULT_RESCAN: dict[str, Any] = {
    "max_enqueue": 200,
    "source": "loop_a",
}


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load discovery scheduler config defensively.

    Returns a dict with all sections present (cadences, skip_if_recent,
    tier_priority, queue_drain, rescan). Missing file or missing keys fall
    back to the module defaults — never raises on a bad/absent config.
    """
    path = config_path or DEFAULT_CONFIG_PATH
    raw: dict = {}
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("discovery_scheduler: could not parse %s (%s); using defaults", path, exc)
        raw = {}

    def _merge(section: str, defaults: dict) -> dict:
        merged = dict(defaults)
        section_val = raw.get(section)
        if isinstance(section_val, dict):
            for k, v in section_val.items():
                if k.startswith("_"):
                    continue  # skip _comment keys
                merged[k] = v
        return merged

    return {
        "cadences": _merge("cadences", _DEFAULT_CADENCES),
        "skip_if_recent": _merge("skip_if_recent", _DEFAULT_SKIP_IF_RECENT),
        "tier_priority": _merge("tier_priority", _DEFAULT_TIER_PRIORITY),
        "queue_drain": _merge("queue_drain", _DEFAULT_QUEUE_DRAIN),
        "rescan": _merge("rescan", _DEFAULT_RESCAN),
    }


# ---------------------------------------------------------------------------
# Tier resolution (forward-compatible — full locked/candidate tiering = WI-4)
# ---------------------------------------------------------------------------

# Canonical resolved tiers used by skip-if-recent windows + priority mapping.
TIER_LOCKED = "locked"
TIER_CANDIDATE = "candidate"
TIER_DISCOVERED = "discovered"
TIER_REST = "rest"


def resolve_tier(row: dict) -> str:
    """Resolve a watchlist row to a canonical tier: locked|candidate|discovered|rest.

    FORWARD-COMPATIBLE (WI-4): if the row carries WI-4's future tier/locked
    columns, they win. Pre-WI-4 those columns do not exist, so we fall back to
    the columns that DO exist today (``lifecycle_state`` / ``source``).

    Resolution order:
      1. Explicit ``locked`` truthy           -> 'locked'              (WI-4)
      2. Explicit ``tier`` column value        -> that tier            (WI-4)
      3. Fallback via lifecycle_state/source   -> mapping below        (pre-WI-4)

    Pre-WI-4 fallback mapping (documented in the dev log):
      - lifecycle_state in {promoted, watched}        -> 'locked'
        (operator-approved, actively tracked wallets = highest-value)
      - lifecycle_state == 'reviewed' OR review_status approved-ish, OR
        source == 'manual'                            -> 'candidate'
      - lifecycle_state in {discovered, queued, scanned, stale} -> 'discovered'
      - anything else / unknown                       -> 'rest'

    The row is a plain dict (column name -> value) so this works against both a
    ClickHouse JSONEachRow result and a WatchlistRow.__dict__.
    """
    # --- WI-4 path (only fires once those columns exist + are populated) ---
    locked_val = row.get("locked")
    if locked_val in (1, "1", True, "true", "True"):
        return TIER_LOCKED
    tier_val = row.get("tier")
    if isinstance(tier_val, str) and tier_val.strip().lower() in (
        TIER_LOCKED,
        TIER_CANDIDATE,
        TIER_DISCOVERED,
        TIER_REST,
    ):
        return tier_val.strip().lower()

    # --- pre-WI-4 fallback via existing fields ---
    lifecycle = str(row.get("lifecycle_state", "") or "").strip().lower()
    source = str(row.get("source", "") or "").strip().lower()
    review = str(row.get("review_status", "") or "").strip().lower()

    if lifecycle in ("promoted", "watched"):
        return TIER_LOCKED
    if lifecycle == "reviewed" or review == "approved" or source == "manual":
        return TIER_CANDIDATE
    if lifecycle in ("discovered", "queued", "scanned", "stale"):
        return TIER_DISCOVERED
    return TIER_REST


def tier_to_priority(tier: str, tier_priority: Optional[dict] = None) -> int:
    """Map a resolved tier to a scan_queue priority int (1=highest..5=lowest)."""
    mapping = tier_priority if tier_priority is not None else _DEFAULT_TIER_PRIORITY
    return int(mapping.get(tier, mapping.get(TIER_REST, 4)))


def tier_freshness_hours(tier: str, skip_if_recent: Optional[dict] = None) -> float:
    """Return the skip-if-recent freshness window (hours) for a resolved tier."""
    windows = skip_if_recent if skip_if_recent is not None else _DEFAULT_SKIP_IF_RECENT
    key = f"{tier}_hours"
    return float(windows.get(key, windows.get("rest_hours", 720)))


def is_recently_scanned(
    last_scanned_at: Optional[datetime],
    tier: str,
    *,
    now: Optional[datetime] = None,
    skip_if_recent: Optional[dict] = None,
) -> bool:
    """True if the wallet was scanned within its tier's freshness window.

    A True result means SKIP (do not re-enqueue). A wallet with no recorded
    last-scan timestamp (never scanned) is NOT recent -> returns False ->
    eligible for enqueue.
    """
    if last_scanned_at is None:
        return False
    now = now or datetime.now(timezone.utc)
    if last_scanned_at.tzinfo is None:
        last_scanned_at = last_scanned_at.replace(tzinfo=timezone.utc)
    window = timedelta(hours=tier_freshness_hours(tier, skip_if_recent))
    return (now - last_scanned_at) < window


# ---------------------------------------------------------------------------
# DISCOVERY_JOB_REGISTRY (mirrors RIS JOB_REGISTRY shape exactly)
# ---------------------------------------------------------------------------

DISCOVERY_JOB_REGISTRY: list[dict] = [
    {
        "id": "discovery_loop_a",
        "name": "Loop A leaderboard discovery",
        "trigger_description": "every 6h",
        "callable_name": "_job_run_discovery_loop_a",
    },
    {
        "id": "watchlist_rescan",
        "name": "Watchlist tier-aware rescan enqueue",
        "trigger_description": "daily at 01:00 and 13:00",
        "callable_name": "_job_run_watchlist_rescan",
    },
    {
        "id": "queue_drain",
        "name": "Scan-queue bounded drain (single worker tick)",
        "trigger_description": "every 15 minutes",
        "callable_name": "_job_run_queue_drain",
    },
]

_JOB_CALLABLE_MAP: dict[str, str] = {
    j["id"]: j["callable_name"] for j in DISCOVERY_JOB_REGISTRY
}


# ---------------------------------------------------------------------------
# Watchlist read helper (for the rescan job)
# ---------------------------------------------------------------------------


def _read_watchlist_rows(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
) -> list[dict]:
    """Read current watchlist rows from ClickHouse as plain dicts.

    Uses ``SELECT * ... FINAL`` so the resolver sees every column that exists
    (including WI-4's future tier/locked columns automatically — no hardcoded
    column list to update). Returns [] on any error.
    """
    import base64
    import urllib.parse
    import urllib.request

    sql = (
        "SELECT * FROM polytool.watchlist FINAL "
        "WHERE lifecycle_state != 'retired' FORMAT JSONEachRow"
    )
    url = f"http://{host}:{port}/?query={urllib.parse.quote(sql)}"
    credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
    req = urllib.request.Request(
        url, headers={"Authorization": f"Basic {credentials}"}, method="GET"
    )
    rows: list[dict] = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        logger.error("discovery_scheduler: watchlist read failed: %s", exc)
        return []
    for line in raw.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            logger.warning("discovery_scheduler: skipping malformed watchlist row")
    return rows


def _parse_ch_dt(value: Any) -> Optional[datetime]:
    """Parse a ClickHouse DateTime string (or None) to an aware datetime."""
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Rescan planning (pure, testable — no I/O)
# ---------------------------------------------------------------------------


def plan_rescan_enqueues(
    watchlist_rows: list[dict],
    config: dict,
    *,
    now: Optional[datetime] = None,
) -> list[dict]:
    """Decide which watchlist wallets to (re)enqueue and at what priority.

    Pure function: takes watchlist rows + config, returns a list of enqueue
    plans ``{wallet_address, tier, priority, source}`` for wallets that are NOT
    within their tier's freshness window (skip-if-recent applied). Capped at
    ``rescan.max_enqueue``; ordered by priority so the most valuable wallets are
    enqueued first if the cap bites.
    """
    now = now or datetime.now(timezone.utc)
    skip_cfg = config.get("skip_if_recent", _DEFAULT_SKIP_IF_RECENT)
    prio_cfg = config.get("tier_priority", _DEFAULT_TIER_PRIORITY)
    rescan_cfg = config.get("rescan", _DEFAULT_RESCAN)
    max_enqueue = int(rescan_cfg.get("max_enqueue", 200))
    source = str(rescan_cfg.get("source", "loop_a"))

    plans: list[dict] = []
    for row in watchlist_rows:
        wallet = row.get("wallet_address")
        if not wallet:
            continue
        tier = resolve_tier(row)
        last_scanned = _parse_ch_dt(row.get("last_scanned_at"))
        if is_recently_scanned(last_scanned, tier, now=now, skip_if_recent=skip_cfg):
            continue  # skip-if-recent: still fresh, do not re-enqueue
        plans.append(
            {
                "wallet_address": wallet,
                "tier": tier,
                "priority": tier_to_priority(tier, prio_cfg),
                "source": source,
            }
        )

    # Highest-value (lowest priority int) first, then stable by wallet.
    plans.sort(key=lambda p: (p["priority"], p["wallet_address"]))
    return plans[:max_enqueue]


# ---------------------------------------------------------------------------
# Job callables (thin wrappers; no-arg — APScheduler calls them with no args)
# ---------------------------------------------------------------------------
#
# Each callable resolves ClickHouse credentials from the CLICKHOUSE_PASSWORD
# env var with fail-fast behavior (CLAUDE.md ClickHouse auth rule). They are
# parameterized only via module-level _RUNTIME (set by start_discovery_scheduler
# / the CLI) so they remain no-arg for APScheduler.

_RUNTIME: dict[str, Any] = {
    "ch_host": "localhost",
    "ch_port": 8123,
    "ch_user": "polytool_admin",
    "config_path": None,
}


def _ch_password() -> str:
    pw = os.environ.get("CLICKHOUSE_PASSWORD", "")
    if not pw:
        # Fail-fast per CLAUDE.md ClickHouse auth rule. Raising here surfaces in
        # run_discovery_job's exception handler -> exit_code 1 + logged.
        raise RuntimeError(
            "CLICKHOUSE_PASSWORD not set; discovery scheduler jobs require it "
            "(fail-fast per CLAUDE.md ClickHouse auth rule)."
        )
    return pw


def _ch_kwargs() -> dict:
    return {
        "host": _RUNTIME["ch_host"],
        "port": _RUNTIME["ch_port"],
        "user": _RUNTIME["ch_user"],
        "password": _ch_password(),
    }


def _job_run_discovery_loop_a() -> None:
    """Run one Loop A discovery cycle (leaderboard -> churn -> enqueue)."""
    from packages.polymarket.discovery.loop_a import run_loop_a  # lazy import

    kwargs = _ch_kwargs()
    run_loop_a(
        ch_host=kwargs["host"],
        ch_port=kwargs["port"],
        ch_user=kwargs["user"],
        ch_password=kwargs["password"],
        dry_run=False,
    )


def _job_run_watchlist_rescan() -> None:
    """Enqueue stale watchlist members by resolved tier (skip-if-recent applied)."""
    from packages.polymarket.discovery.clickhouse_writer import write_scan_queue_rows
    from packages.polymarket.discovery.scan_queue import ScanQueueManager

    config = load_config(_RUNTIME.get("config_path"))
    kwargs = _ch_kwargs()

    rows = _read_watchlist_rows(**kwargs)
    plans = plan_rescan_enqueues(rows, config)
    if not plans:
        logger.info("discovery_scheduler: watchlist_rescan — nothing to enqueue")
        return

    queue = ScanQueueManager()
    for plan in plans:
        queue.enqueue(
            plan["wallet_address"],
            source=plan["source"],
            priority=plan["priority"],
        )
    queue_rows = list(queue._items.values())  # noqa: SLF001 - same package idiom
    ok = write_scan_queue_rows(queue_rows, **kwargs)
    if not ok:
        logger.error("discovery_scheduler: watchlist_rescan — failed to write scan_queue rows")
    else:
        logger.info("discovery_scheduler: watchlist_rescan — enqueued %d wallets", len(queue_rows))


def _job_run_queue_drain() -> None:
    """Run ONE bounded ScanWorker tick (single-worker safety; see module docstring)."""
    from packages.polymarket.discovery.scan_queue import ScanQueueManager
    from packages.polymarket.discovery.scan_worker import (
        ScanWorker,
        make_clickhouse_watchlist_advancer,
    )

    config = load_config(_RUNTIME.get("config_path"))
    drain_cfg = config.get("queue_drain", _DEFAULT_QUEUE_DRAIN)
    kwargs = _ch_kwargs()

    # DR-0-FIX: bound each scan HTTP request for the drain path so an in-flight
    # wallet cannot run for minutes on a slow endpoint and blow past the Docker
    # stop grace. scan.py reads SCAN_HTTP_TIMEOUT_SECONDS; setting it here scopes
    # the tighter timeout to the scheduler process only (foreground wallet-scan,
    # a separate process, keeps the 120s default).
    req_timeout = drain_cfg.get("request_timeout_seconds")
    if req_timeout:
        os.environ["SCAN_HTTP_TIMEOUT_SECONDS"] = str(req_timeout)

    queue = ScanQueueManager()
    queue.load_from_clickhouse(**kwargs)

    advancer = make_clickhouse_watchlist_advancer(**kwargs)
    worker = ScanWorker(
        queue,
        watchlist_advancer=advancer,
        owner=str(drain_cfg.get("owner", "discovery-scheduler")),
        lease_seconds=int(drain_cfg.get("lease_seconds", 300)),
        max_attempts=int(drain_cfg.get("max_attempts", 5)),
    )
    # Cooperative shutdown: the worker checks drain_stop_requested between wallets
    # so a SIGTERM mid-tick halts without starting a new wallet. The post-run
    # flush still persists lease/complete/fail state for whatever finished.
    worker.run(
        max_items=int(drain_cfg.get("max_items", 10)),
        should_stop=drain_stop_requested,
    )
    queue.flush_to_clickhouse(**kwargs)


_JOB_FN_MAP: dict[str, Callable[[], None]] = {
    "_job_run_discovery_loop_a": _job_run_discovery_loop_a,
    "_job_run_watchlist_rescan": _job_run_watchlist_rescan,
    "_job_run_queue_drain": _job_run_queue_drain,
}


# ---------------------------------------------------------------------------
# Public API (mirrors RIS run_job / start_research_scheduler signatures)
# ---------------------------------------------------------------------------


def run_discovery_job(job_id: str) -> int:
    """Invoke a single discovery job callable by id. 0 on success, 1 otherwise."""
    callable_name = _JOB_CALLABLE_MAP.get(job_id)
    if callable_name is None:
        logger.error(
            "run_discovery_job: unknown job id %r. Known ids: %s",
            job_id,
            list(_JOB_CALLABLE_MAP),
        )
        return 1
    fn = _JOB_FN_MAP.get(callable_name)
    if fn is None:  # pragma: no cover - defensive
        logger.error("run_discovery_job: callable %r not found", callable_name)
        return 1
    try:
        fn()
    except Exception:
        logger.exception("run_discovery_job: job %r raised an exception", job_id)
        return 1
    return 0


def start_discovery_scheduler(
    *,
    ch_host: str = "localhost",
    ch_port: int = 8123,
    ch_user: str = "polytool_admin",
    config_path: Optional[Path] = None,
    _scheduler_factory: Optional[Callable[[], Any]] = None,
    _job_runner: Optional[Callable[[str], None]] = None,
    exclude_job_ids: Optional[list] = None,
) -> Any:
    """Start the discovery background scheduler with the three discovery jobs.

    Mirrors ``start_research_scheduler`` exactly: guarded APScheduler import,
    injectable ``_scheduler_factory`` / ``_job_runner`` for offline tests,
    ``exclude_job_ids`` to skip jobs. Does NOT touch the RIS scheduler.

    Cadences come from ``config/discovery_scheduler.json`` (defensive load).
    """
    # Stash runtime context so no-arg job callables can reach ClickHouse + config.
    _RUNTIME["ch_host"] = ch_host
    _RUNTIME["ch_port"] = ch_port
    _RUNTIME["ch_user"] = ch_user
    _RUNTIME["config_path"] = config_path

    # Fresh start: clear any stop request left over from a prior run in-process.
    clear_drain_stop()

    config = load_config(config_path)
    cadences = config.get("cadences", _DEFAULT_CADENCES)

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
        try:
            from apscheduler.triggers.cron import CronTrigger
        except ImportError:
            CronTrigger = None  # type: ignore[assignment,misc]
        scheduler = _scheduler_factory()

    _excluded = set(exclude_job_ids) if exclude_job_ids else set()

    for job_entry in DISCOVERY_JOB_REGISTRY:
        jid = job_entry["id"]
        jname = job_entry["name"]

        if jid in _excluded:
            logger.info("start_discovery_scheduler: skipping excluded job %r", jid)
            continue

        if _job_runner is not None:
            job_fn: Callable[[], None] = (lambda _jid=jid: _job_runner(_jid))
        else:
            job_fn = (lambda _jid=jid: run_discovery_job(_jid))

        trigger_kwargs = cadences.get(jid, {})
        # Drop any _comment keys defensively before handing to CronTrigger.
        trigger_kwargs = {
            k: v for k, v in trigger_kwargs.items() if not str(k).startswith("_")
        }

        if CronTrigger is not None:
            trigger = CronTrigger(**trigger_kwargs)
        else:
            trigger = trigger_kwargs  # fake scheduler ignores it

        scheduler.add_job(job_fn, trigger, id=jid, name=jname)

    scheduler.start()
    return scheduler


def stop_discovery_scheduler(scheduler: Any, *, wait: bool = True) -> bool:
    """Cleanly shut down the discovery scheduler (DR-0 graceful shutdown).

    Calls ``scheduler.shutdown(wait=wait)`` so APScheduler (a) stops accepting
    and firing new jobs and (b) — when ``wait=True`` — lets any in-flight job
    (e.g. a ``queue_drain`` tick already running) finish before returning. That
    in-flight tick is a single bounded ``ScanWorker.run(...)`` which ends by
    flushing the queue state back to ClickHouse, so a graceful stop preserves
    queue/lease state through the existing flush path (no new flush logic here).

    Never raises: a shutdown error is logged and returns False, so a SIGTERM
    handler can always proceed to exit. ``BackgroundScheduler.shutdown`` accepts
    a ``wait`` kwarg; the injectable test fake's ``shutdown()`` may not, so we
    fall back to a no-arg shutdown for compatibility.

    Returns True if shutdown was invoked without error, else False.
    """
    if scheduler is None:
        return False
    try:
        try:
            scheduler.shutdown(wait=wait)
        except TypeError:
            # Fake/older schedulers expose a no-arg shutdown().
            scheduler.shutdown()
        return True
    except Exception:  # pragma: no cover - defensive; shutdown must never raise out
        logger.exception("stop_discovery_scheduler: scheduler.shutdown raised")
        return False


def run_scheduler_blocking(
    scheduler: Any,
    *,
    poll_seconds: float = 60.0,
    shutdown_wait: bool = False,
    install_signal_handlers: bool = True,
    on_started: Optional[Callable[[], None]] = None,
    heartbeat: Optional[Callable[[], None]] = None,
) -> int:
    """Block until SIGTERM/SIGINT, then perform a bounded cooperative shutdown.

    DR-0-FIX: this is the testable core of the scheduler's blocking wait. It
    replaces the naive ``while True: sleep`` and guarantees a bounded exit:

    1. Trap SIGINT + SIGTERM (and SIGBREAK on Windows). The handler requests a
       cooperative drain stop (so an in-flight ``queue_drain`` halts BETWEEN
       wallets AND the in-flight HTTP request aborts) and sets the wait event.
    2. Block on the event with a short poll (never a busy loop).
    3. On signal, call ``stop_discovery_scheduler(scheduler, wait=shutdown_wait)``
       with ``wait=False`` by default so we never block unbounded on a job. Any
       wallet still in-flight aborts its in-flight request (bounded to ~one
       request timeout via the drain cancel hook); we do not wait for the queue.

    DR-0-FIX-2: ``heartbeat`` (the lock's ``beat``) is refreshed from THIS main
    loop on every poll. There is no background heartbeat thread to die silently —
    while this loop is alive (every <= ``poll_seconds``) the lock stays fresh;
    when this loop exits, the holder is stopping anyway and releases the lock.

    Returns 0 if shutdown reported clean, else 1 (propagated to the process exit
    code so a failed shutdown is not reported as success).
    """
    stop_event = threading.Event()

    def _handle_signal(signum, _frame):  # noqa: ANN001 - stdlib signal signature
        try:
            name = signal.Signals(signum).name
        except Exception:  # pragma: no cover - non-standard signum
            name = str(signum)
        logger.info("discovery scheduler: received %s; shutting down gracefully", name)
        # Cooperative cancel first so an in-flight drain stops between wallets,
        # THEN release the blocking wait.
        request_drain_stop()
        stop_event.set()

    if install_signal_handlers:
        for signame in ("SIGINT", "SIGTERM", "SIGBREAK"):
            sig = getattr(signal, signame, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, _handle_signal)
            except (ValueError, OSError):  # pragma: no cover - non-main-thread / unsupported
                pass

    def _beat() -> None:
        if heartbeat is None:
            return
        try:
            heartbeat()
        except Exception:  # pragma: no cover - heartbeat must never crash the loop
            logger.warning("run_scheduler_blocking: heartbeat refresh failed", exc_info=True)

    _beat()  # refresh immediately so the lock is fresh before the first long wait
    if on_started is not None:
        on_started()

    try:
        while not stop_event.wait(timeout=poll_seconds):
            # A stop can arrive via the signal handler (sets both the drain flag
            # and stop_event) or directly via request_drain_stop(); honor either
            # so the wait is responsive to the same cooperative-stop flag the
            # drain uses. In production the handler sets both together.
            if drain_stop_requested():
                break
            # Main-loop heartbeat (no background thread): proves the holder alive.
            _beat()
    except KeyboardInterrupt:  # pragma: no cover - platform-dependent Ctrl-C race
        request_drain_stop()
        stop_event.set()

    ok = stop_discovery_scheduler(scheduler, wait=shutdown_wait)
    return 0 if ok else 1
