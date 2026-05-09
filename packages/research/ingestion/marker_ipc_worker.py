"""Marker Docker/Linux IPC warm-worker — persistent subprocess, models loaded once.

Platform: Linux/Docker only.
  Windows uses LiveAcademicFetcher.create_warm_thread_worker() (thread mode).
  This module is NOT used on Windows. Do not call from Windows paths.

Problem solved: on Linux/Docker, each subprocess spawn cold-loads Marker models
(~80-270s on RTX 2070 Super), adding cold-start overhead for every paper.
This warm-worker loads models once and serves parse requests via multiprocessing
queues across the subprocess boundary. Per-paper inference time (~45-70s on RTX
2070 Super) is a hardware constant; the warm-worker eliminates the cold-load
overhead for papers 2+. Validated 2026-05-08: paper 2 delta=0.13s, paper 3
delta=0.22s. Original ≤10s/paper target was rejected as unrealistic.

Integration contract (for queue consumer — implemented separately):

    worker = MarkerIPCWorker()
    worker.start()                              # cold load once (~80-270s)
    try:
        result = worker.parse(pdf_path)         # warm parse, ~45-70s inference (delta ≤1s papers 2+)
        # result: {
        #   "status": "ok" | "error",
        #   "body": str,
        #   "meta": dict,          # body_source, page_count, parse_seconds, ...
        #   "parse_seconds": float,
        #   "failure_reason": str | None,
        # }
        if result["status"] == "error":
            worker.restart()  # or worker.shutdown()
    finally:
        worker.shutdown()

Does NOT set _MARKER_DISABLED. Does NOT fall back to pdfplumber.
Returns structured error dicts instead of raising on failure.
"""

from __future__ import annotations

import logging
import multiprocessing
import time
from typing import Optional

_logger = logging.getLogger(__name__)

# Poison pill: sent to request_queue to signal the worker subprocess to exit cleanly.
_SENTINEL = None


# ---------------------------------------------------------------------------
# Module-level worker entry point — MUST stay at module level for spawn pickling.
# Moving this into a class or closure breaks multiprocessing spawn.
# ---------------------------------------------------------------------------

def _marker_ipc_worker_main(
    request_queue,
    result_queue,
    _extractor_cls=None,
) -> None:
    """Warm-worker subprocess entry point.

    Loads Marker models exactly once via create_model_dict(), then serves parse
    requests from request_queue until the sentinel (None) is received.

    On model load failure, puts a startup_error result in result_queue and exits.
    The first parse() call on the parent will surface this error rather than
    hanging until timeout.

    Parameters
    ----------
    request_queue:
        Source of parse requests. Each item: {"tmp_path": str} | None (sentinel).
    result_queue:
        Destination for results. Each item is a dict with a "status" key:
        - {"status": "startup_error", "error": str, "parse_seconds": 0.0}
        - {"status": "ok", "body": str, "meta": dict, "parse_seconds": float}
        - {"status": "error", "error": str, "parse_seconds": float}
    _extractor_cls:
        Injectable extractor class for offline tests. None = MarkerPDFExtractor.
        Must be picklable when using real multiprocessing.Process (spawn mode).
        Thread-based test injection bypasses the pickling requirement.
    """
    import time as _t

    if _extractor_cls is None:
        from packages.research.ingestion.extractors import MarkerPDFExtractor
        _extractor_cls = MarkerPDFExtractor

    # Cold-load models ONCE — expensive, amortized across all papers in session.
    try:
        probe = _extractor_cls()
        mods = probe._load_marker()
        model_dict = mods["create_model_dict"]()
        warm_extractor = _extractor_cls(_preloaded_model_dict=model_dict)
    except Exception as exc:
        # Signal startup failure so the parent's first parse() call gets an error
        # dict rather than hanging until timeout.
        result_queue.put({
            "status": "startup_error",
            "error": f"marker model load failed: {str(exc)[:300]}",
            "parse_seconds": 0.0,
        })
        return

    # Serve parse requests until sentinel.
    while True:
        try:
            req = request_queue.get()
        except Exception:
            break

        if req is _SENTINEL:
            break

        tmp_path = req.get("tmp_path", "")
        t0 = _t.monotonic()
        try:
            doc = warm_extractor.extract(tmp_path)
            parse_s = round(_t.monotonic() - t0, 2)
            # Filter metadata to picklable primitive types only — matches the
            # existing _marker_process_worker pattern to stay queue-safe.
            meta = {
                k: v for k, v in doc.metadata.items()
                if isinstance(v, (str, int, float, bool, type(None)))
            }
            meta["parse_seconds"] = parse_s
            result_queue.put({
                "status": "ok",
                "body": doc.body or "",
                "meta": meta,
                "parse_seconds": parse_s,
            })
        except Exception as exc:
            result_queue.put({
                "status": "error",
                "error": str(exc)[:300],
                "parse_seconds": round(_t.monotonic() - t0, 2),
            })


# ---------------------------------------------------------------------------
# MarkerIPCWorker
# ---------------------------------------------------------------------------

class MarkerIPCWorker:
    """Persistent warm-worker subprocess for Marker PDF extraction on Linux/Docker.

    Holds Marker models loaded in GPU VRAM across multiple parse requests by
    keeping a long-lived subprocess alive and dispatching requests via
    multiprocessing queues (IPC).

    Platform: Linux/Docker only.
      - Windows: use LiveAcademicFetcher.create_warm_thread_worker().
      - Linux/Docker: use this class (created by queue consumer, not this module).

    Lifecycle::

        worker = MarkerIPCWorker()
        worker.start()                    # spawns subprocess, cold load begins
        try:
            result = worker.parse(path)   # papers 2+: warm inference ~45-70s, cold-load delta ≤1s
        finally:
            worker.shutdown()             # poison pill → join → force-kill

    On timeout:
        _MARKER_DISABLED is NOT set. Call restart() to respawn with a fresh cold
        load. Subsequent parse() calls proceed normally on the new worker.

    On per-paper error:
        parse() returns a structured error dict. The worker subprocess stays alive
        and continues serving subsequent requests (worker does not die on one error).

    No pdfplumber fallback in any code path.

    Injectable parameters for offline tests
    ----------------------------------------
    _process_factory   callable(target, args, daemon) → process-like object
    _queue_factory     callable() → queue-like object (put / get(timeout) API)
    _extractor_cls     extractor class passed into the worker subprocess
    _terminate_grace_seconds / _kill_grace_seconds / _shutdown_join_timeout
    """

    def __init__(
        self,
        _extractor_cls=None,
        _process_factory=None,
        _queue_factory=None,
        _mp_context=None,
        _terminate_grace_seconds: float = 5.0,
        _kill_grace_seconds: float = 2.0,
        _shutdown_join_timeout: float = 10.0,
    ) -> None:
        """
        Parameters
        ----------
        _extractor_cls:
            Extractor class injected into the worker subprocess. None = MarkerPDFExtractor.
            Must be picklable when using real multiprocessing.Process (spawn mode).
        _process_factory:
            callable(target, args, daemon) → process-like object with
            start(), is_alive(), join(timeout), terminate(), kill() methods.
            Inject a threading.Thread wrapper for offline tests.
        _queue_factory:
            callable() → queue-like object with put() and get(timeout) methods.
            Inject stdlib queue.Queue for offline tests.
        _mp_context:
            Multiprocessing context (e.g. multiprocessing.get_context("spawn")).
            Ignored when _process_factory / _queue_factory are provided.
        _terminate_grace_seconds:
            Seconds between SIGTERM and SIGKILL escalation.
        _kill_grace_seconds:
            Seconds to wait for exit after SIGKILL.
        _shutdown_join_timeout:
            Seconds to wait for clean shutdown via poison pill before force-kill.
        """
        self._extractor_cls = _extractor_cls
        self._process_factory = _process_factory
        self._queue_factory = _queue_factory
        self._mp_context = _mp_context
        self._terminate_grace_seconds = _terminate_grace_seconds
        self._kill_grace_seconds = _kill_grace_seconds
        self._shutdown_join_timeout = _shutdown_join_timeout

        self._proc: Optional[object] = None
        self._req_q = None
        self._res_q = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_context(self):
        if self._mp_context is not None:
            return self._mp_context
        return multiprocessing.get_context("spawn")

    def _make_queue(self):
        if self._queue_factory is not None:
            return self._queue_factory()
        return self._get_context().Queue()

    def _make_process(self, target, args, daemon=False):
        if self._process_factory is not None:
            return self._process_factory(target=target, args=args, daemon=daemon)
        ctx = self._get_context()
        return ctx.Process(target=target, args=args, daemon=daemon)

    def _terminate_worker(self) -> None:
        """SIGTERM → grace → SIGKILL → grace → reset internal state."""
        if self._proc is None:
            return
        try:
            self._proc.terminate()
            self._proc.join(timeout=self._terminate_grace_seconds)
            if self._proc.is_alive():
                self._proc.kill()
                self._proc.join(timeout=self._kill_grace_seconds)
        except Exception as exc:
            _logger.warning("MarkerIPCWorker: error during terminate/kill: %s", exc)
        finally:
            self._proc = None
            self._req_q = None
            self._res_q = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Spawn the worker subprocess and begin model loading.

        The first parse() call will include cold-load time (~80-270s on RTX 2070 Super).
        Subsequent parse() calls return from warm VRAM (~45-70s inference; cold-load
        overhead eliminated for papers 2+). Original ≤10s/paper target was rejected
        as unrealistic — measured: paper 2 delta=0.13s, paper 3 delta=0.22s.

        Raises
        ------
        RuntimeError
            If the worker is already running. Call shutdown() first.
        """
        if self.is_alive():
            raise RuntimeError(
                "MarkerIPCWorker is already running; call shutdown() first"
            )

        req_q = self._make_queue()
        res_q = self._make_queue()
        self._req_q = req_q
        self._res_q = res_q

        # daemon=False is required: daemon processes cannot spawn child processes,
        # and Marker's ONNX/torch pipeline spawns internal worker processes during
        # extraction. With daemon=True, paper 2+ fail immediately with
        # "daemonic processes are not allowed to have children".
        # Lifecycle cleanup is handled explicitly by shutdown() / _terminate_worker().
        proc = self._make_process(
            target=_marker_ipc_worker_main,
            args=(req_q, res_q, self._extractor_cls),
            daemon=False,
        )
        proc.start()
        self._proc = proc
        _logger.info(
            "MarkerIPCWorker: subprocess started (pid=%s); first parse includes cold load",
            getattr(proc, "pid", "N/A"),
        )

    def is_alive(self) -> bool:
        """Return True if the worker subprocess is running."""
        return self._proc is not None and self._proc.is_alive()

    def parse(self, pdf_path: str, timeout: float = 900.0) -> dict:
        """Parse a PDF using the warm worker subprocess.

        Sends a parse request and waits for the result. On timeout, terminates
        the worker subprocess. Call restart() to continue processing.

        Does NOT set _MARKER_DISABLED. Does NOT fall back to pdfplumber.

        Parameters
        ----------
        pdf_path:
            Absolute path to the PDF file (inside the Docker container).
        timeout:
            Seconds to wait for the parse result before treating worker as stuck.

        Returns
        -------
        dict
            status          "ok" | "error"
            body            str — Markdown text (empty on error)
            meta            dict — body_source, page_count, parse_seconds, ...
            parse_seconds   float
            failure_reason  str | None — None on success
        """
        import queue as _q_mod

        if not self.is_alive():
            return {
                "status": "error",
                "body": "",
                "meta": {},
                "parse_seconds": 0.0,
                "failure_reason": "worker_not_running: call start() before parse()",
            }

        self._req_q.put({"tmp_path": pdf_path})
        t0 = time.monotonic()

        try:
            result = self._res_q.get(timeout=timeout)
        except _q_mod.Empty:
            elapsed = round(time.monotonic() - t0, 2)
            _logger.warning(
                "MarkerIPCWorker: parse timed out after %ss — terminating worker subprocess",
                timeout,
            )
            self._terminate_worker()
            return {
                "status": "error",
                "body": "",
                "meta": {},
                "parse_seconds": elapsed,
                "failure_reason": f"marker_timeout: extraction timed out after {timeout}s",
            }

        status = result.get("status")
        if status in ("error", "startup_error"):
            return {
                "status": "error",
                "body": "",
                "meta": {},
                "parse_seconds": result.get("parse_seconds", 0.0),
                "failure_reason": result.get("error", "unknown worker error")[:300],
            }

        return {
            "status": "ok",
            "body": result.get("body", ""),
            "meta": result.get("meta", {}),
            "parse_seconds": result.get("parse_seconds", 0.0),
            "failure_reason": None,
        }

    def extract(self, tmp_path: str, timeout: float) -> dict:
        """Raw IPC call — send request, return result dict or raise queue.Empty.

        Lower-level than parse(). Callers are responsible for handling
        queue.Empty (timeout) and checking result["status"].

        Prefer parse() for queue-consumer integration — it handles timeout,
        termination, and returns structured error dicts.

        Raises
        ------
        queue.Empty
            If no result arrives within timeout seconds.
        RuntimeError
            If start() has not been called.
        """
        if self._req_q is None or self._res_q is None:
            raise RuntimeError(
                "MarkerIPCWorker.extract: worker not started — call start() first"
            )
        self._req_q.put({"tmp_path": tmp_path})
        return self._res_q.get(timeout=timeout)

    def restart(self) -> None:
        """Terminate the current worker and spawn a fresh one (one new cold load).

        Use after a timeout or startup failure to resume processing.
        If the worker is not running, acts as start().
        """
        _logger.info("MarkerIPCWorker: restarting worker (new cold load follows)")
        if self.is_alive():
            self._terminate_worker()
        else:
            # Clear stale references from a previously terminated worker.
            self._proc = None
            self._req_q = None
            self._res_q = None
        self.start()

    def shutdown(self) -> None:
        """Clean shutdown: poison pill → join → force-kill if needed.

        Idempotent: safe to call when not running or multiple times.
        """
        if not self.is_alive():
            _logger.debug("MarkerIPCWorker.shutdown: not running (no-op)")
            return

        try:
            self._req_q.put(_SENTINEL)
            self._proc.join(timeout=self._shutdown_join_timeout)
        except Exception as exc:
            _logger.warning("MarkerIPCWorker: error during shutdown signal: %s", exc)

        if self.is_alive():
            _logger.warning(
                "MarkerIPCWorker: worker did not exit cleanly — forcing kill"
            )
            self._terminate_worker()
        else:
            self._proc = None
            self._req_q = None
            self._res_q = None

        _logger.info("MarkerIPCWorker: shutdown complete")
