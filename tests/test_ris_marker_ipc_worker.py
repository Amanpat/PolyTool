"""Offline unit tests for MarkerIPCWorker IPC warm-worker.

All tests are fully offline:
- No real Marker models loaded, no GPU, no Docker, no network.
- _process_factory injects a threading.Thread wrapper so no real subprocess spawn occurs.
- _queue_factory injects stdlib queue.Queue to avoid multiprocessing queues.
- Mock extractor classes provide a synthetic Marker interface with call counters.

Tests prove:
- create_model_dict is called once for multiple parse requests (warm reuse)
- multiple parse requests reuse the same worker without a new cold load
- per-paper worker errors propagate as structured error dicts
- timeout returns a structured error dict and marks the worker as not running
- restart() after timeout restores parse capability via a new cold load
- shutdown is idempotent (safe to call multiple times or when not running)
- no real Marker model / PDF download / GPU access is needed anywhere
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Optional

import pytest

from packages.research.ingestion.marker_ipc_worker import (
    MarkerIPCWorker,
    _marker_ipc_worker_main,
    _SENTINEL,
)


# ---------------------------------------------------------------------------
# Thread-based process substitute for offline tests
# ---------------------------------------------------------------------------


class _ThreadProcess:
    """Mimics multiprocessing.Process API using threading.Thread.

    Required because spawn-mode subprocesses require picklable args.
    Mock extractor classes are not picklable, but when the 'process' is a
    thread, args are passed by reference — no pickling involved.

    terminate() and kill() are no-ops — threads cannot be externally killed.
    The worker loop exits via poison pill (_SENTINEL) or test teardown.
    daemon=True matches subprocess behaviour: thread dies when the test exits.
    """

    def __init__(self, target, args=(), daemon=True):
        self._thread = threading.Thread(target=target, args=args, daemon=daemon)
        self.pid = None  # threads do not have OS PIDs

    def start(self) -> None:
        self._thread.start()

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def join(self, timeout=None) -> None:
        self._thread.join(timeout=timeout)

    def terminate(self) -> None:
        pass  # no-op

    def kill(self) -> None:
        pass  # no-op


def _thread_process_factory(target, args=(), daemon=False) -> _ThreadProcess:
    # Always create daemon threads regardless of the daemon argument.
    # Reason: offline tests leave threads running after simulated timeouts;
    # non-daemon threads would prevent pytest from exiting cleanly.
    # The daemon argument is accepted to match the real factory signature
    # (MarkerIPCWorker._make_process passes daemon=False after the fix).
    return _ThreadProcess(target=target, args=args, daemon=True)


# ---------------------------------------------------------------------------
# Mock extractor machinery (module-level for reuse across test classes)
# ---------------------------------------------------------------------------


class _MockDoc:
    """Minimal ExtractedDocument-like stand-in."""

    def __init__(self, body: str = "x" * 5000, metadata: Optional[dict] = None) -> None:
        self.body = body
        self.metadata = metadata or {
            "body_source": "marker",
            "page_count": 10,
            "content_hash": "deadbeef",
        }


def _make_mock_extractor(
    body: str = "# Fake Paper\n\n" + "Content word. " * 500,
    raise_on_extract: Optional[Exception] = None,
    raise_on_model_load: Optional[Exception] = None,
    extract_delay: float = 0.0,
) -> "tuple[type, list]":
    """Build a mock extractor class plus a shared create_model_dict call log.

    The call_log list grows by 1 each time create_model_dict() is invoked.
    Because tests run the worker in a thread (not a subprocess), the list is
    shared by reference with no pickling or synchronisation overhead.

    Returns
    -------
    (MockExtractorClass, call_log)
    """
    call_log: list = []

    class _MockExtractor:
        def __init__(self, _marker_modules=None, _preloaded_model_dict=None):
            self._preloaded_model_dict = _preloaded_model_dict

        def _load_marker(self) -> dict:
            def _create_model_dict():
                if raise_on_model_load is not None:
                    raise raise_on_model_load
                call_log.append(1)
                return {"model": "fake_weights"}

            return {
                "create_model_dict": _create_model_dict,
                "PdfConverter": None,
                "text_from_rendered": None,
            }

        def extract(self, path, **kwargs) -> _MockDoc:
            if extract_delay > 0:
                time.sleep(extract_delay)
            if raise_on_extract is not None:
                raise raise_on_extract
            return _MockDoc(body=body)

    return _MockExtractor, call_log


# ---------------------------------------------------------------------------
# Shared worker factory helper
# ---------------------------------------------------------------------------


def _make_worker(
    extractor_cls=None,
    terminate_grace: float = 0.1,
    kill_grace: float = 0.1,
    shutdown_join: float = 2.0,
) -> MarkerIPCWorker:
    """Build a MarkerIPCWorker wired to thread-based process and stdlib queues."""
    return MarkerIPCWorker(
        _extractor_cls=extractor_cls,
        _process_factory=_thread_process_factory,
        _queue_factory=queue.Queue,
        _terminate_grace_seconds=terminate_grace,
        _kill_grace_seconds=kill_grace,
        _shutdown_join_timeout=shutdown_join,
    )


# ---------------------------------------------------------------------------
# Tests: MarkerIPCWorker public interface (presence and pre-start state)
# ---------------------------------------------------------------------------


class TestMarkerIPCWorkerInterface:
    def test_class_has_expected_methods(self) -> None:
        w = MarkerIPCWorker()
        for method in ("start", "parse", "extract", "is_alive", "restart", "shutdown"):
            assert callable(getattr(w, method)), f"missing callable: {method}"

    def test_not_alive_before_start(self) -> None:
        w = MarkerIPCWorker()
        assert w.is_alive() is False

    def test_extract_raises_runtime_error_before_start(self) -> None:
        w = MarkerIPCWorker()
        with pytest.raises(RuntimeError, match="not started"):
            w.extract("/fake/path.pdf", timeout=1.0)

    def test_parse_returns_error_dict_before_start(self) -> None:
        w = _make_worker()
        result = w.parse("/fake/path.pdf", timeout=1.0)
        assert result["status"] == "error"
        assert "worker_not_running" in result["failure_reason"]


# ---------------------------------------------------------------------------
# Tests: _marker_ipc_worker_main — function-level, run directly in a thread
# ---------------------------------------------------------------------------


class TestMarkerIPCWorkerMain:
    """Low-level tests for the module-level worker entry point.

    Calls _marker_ipc_worker_main directly in a daemon thread with stdlib
    queue.Queue instances, bypassing MarkerIPCWorker orchestration.
    """

    def _run_worker_thread(self, req_q, res_q, extractor_cls) -> threading.Thread:
        t = threading.Thread(
            target=_marker_ipc_worker_main,
            args=(req_q, res_q, extractor_cls),
            daemon=True,
        )
        t.start()
        return t

    def test_single_request_returns_ok(self) -> None:
        cls, _ = _make_mock_extractor()
        req_q, res_q = queue.Queue(), queue.Queue()
        t = self._run_worker_thread(req_q, res_q, cls)

        req_q.put({"tmp_path": "/fake/paper.pdf"})
        result = res_q.get(timeout=5.0)

        assert result["status"] == "ok"
        assert len(result["body"]) >= 200
        assert "parse_seconds" in result
        assert isinstance(result["meta"], dict)

        req_q.put(_SENTINEL)
        t.join(timeout=2.0)
        assert not t.is_alive()

    def test_model_loaded_once_across_three_papers(self) -> None:
        """create_model_dict() must be called exactly once regardless of paper count."""
        cls, call_log = _make_mock_extractor()
        req_q, res_q = queue.Queue(), queue.Queue()
        t = self._run_worker_thread(req_q, res_q, cls)

        for i in range(3):
            req_q.put({"tmp_path": f"/fake/paper{i}.pdf"})

        results = [res_q.get(timeout=5.0) for _ in range(3)]

        req_q.put(_SENTINEL)
        t.join(timeout=2.0)

        assert all(r["status"] == "ok" for r in results), results
        assert len(call_log) == 1, (
            f"create_model_dict called {len(call_log)} times; "
            "expected exactly 1 (models stay warm across papers)"
        )

    def test_poison_pill_exits_worker_cleanly(self) -> None:
        cls, _ = _make_mock_extractor()
        req_q, res_q = queue.Queue(), queue.Queue()
        t = self._run_worker_thread(req_q, res_q, cls)

        req_q.put(_SENTINEL)
        t.join(timeout=5.0)
        assert not t.is_alive(), "Worker thread should have exited after poison pill"

    def test_extraction_error_returns_error_status(self) -> None:
        cls, _ = _make_mock_extractor(
            raise_on_extract=RuntimeError("simulated extraction failure")
        )
        req_q, res_q = queue.Queue(), queue.Queue()
        t = self._run_worker_thread(req_q, res_q, cls)

        req_q.put({"tmp_path": "/fake/paper.pdf"})
        result = res_q.get(timeout=5.0)

        assert result["status"] == "error"
        assert "simulated extraction failure" in result["error"]
        assert "parse_seconds" in result

        req_q.put(_SENTINEL)
        t.join(timeout=2.0)

    def test_startup_failure_emits_startup_error_and_exits(self) -> None:
        cls, _ = _make_mock_extractor(
            raise_on_model_load=RuntimeError("simulated model load failure")
        )
        req_q, res_q = queue.Queue(), queue.Queue()
        t = self._run_worker_thread(req_q, res_q, cls)

        result = res_q.get(timeout=5.0)
        t.join(timeout=2.0)

        assert result["status"] == "startup_error"
        assert "simulated model load failure" in result["error"]
        assert not t.is_alive(), "Worker should exit after startup failure"

    def test_worker_continues_serving_after_per_paper_error(self) -> None:
        """A single paper error does not kill the worker — next paper succeeds."""
        fail_once = [False]

        class _TransientCls:
            def __init__(self, _marker_modules=None, _preloaded_model_dict=None):
                self._preloaded_model_dict = _preloaded_model_dict

            def _load_marker(self) -> dict:
                def cmd(): return {"model": "ok"}
                return {"create_model_dict": cmd}

            def extract(self, path, **kwargs) -> _MockDoc:
                if not fail_once[0]:
                    fail_once[0] = True
                    raise ValueError("first paper error")
                return _MockDoc()

        req_q, res_q = queue.Queue(), queue.Queue()
        t = threading.Thread(
            target=_marker_ipc_worker_main,
            args=(req_q, res_q, _TransientCls),
            daemon=True,
        )
        t.start()

        req_q.put({"tmp_path": "/fake/p1.pdf"})
        r1 = res_q.get(timeout=5.0)
        assert r1["status"] == "error"

        req_q.put({"tmp_path": "/fake/p2.pdf"})
        r2 = res_q.get(timeout=5.0)
        assert r2["status"] == "ok"

        req_q.put(_SENTINEL)
        t.join(timeout=2.0)

    def test_meta_filters_non_primitive_values(self) -> None:
        """Worker must filter metadata to queue-safe primitive types only."""

        class _RichMetaCls:
            def __init__(self, _marker_modules=None, _preloaded_model_dict=None):
                self._preloaded_model_dict = _preloaded_model_dict

            def _load_marker(self) -> dict:
                def cmd(): return {"model": "ok"}
                return {"create_model_dict": cmd}

            def extract(self, path, **kwargs) -> _MockDoc:
                return _MockDoc(
                    body="x" * 5000,
                    metadata={
                        "page_count": 5,
                        "score": 0.95,
                        "tags": ["a", "b"],   # list — must be filtered
                        "obj": object(),       # non-primitive — must be filtered
                        "flag": True,
                        "note": None,
                        "body_source": "marker",
                    },
                )

        req_q, res_q = queue.Queue(), queue.Queue()
        t = threading.Thread(
            target=_marker_ipc_worker_main,
            args=(req_q, res_q, _RichMetaCls),
            daemon=True,
        )
        t.start()

        req_q.put({"tmp_path": "/fake/paper.pdf"})
        result = res_q.get(timeout=5.0)

        req_q.put(_SENTINEL)
        t.join(timeout=2.0)

        meta = result["meta"]
        assert "tags" not in meta, "list should be filtered from meta"
        assert "obj" not in meta, "non-primitive should be filtered from meta"
        assert meta["page_count"] == 5
        assert meta["flag"] is True
        assert meta["note"] is None
        assert meta["body_source"] == "marker"

    def test_five_sequential_papers_all_ok(self) -> None:
        cls, _ = _make_mock_extractor()
        req_q, res_q = queue.Queue(), queue.Queue()
        t = self._run_worker_thread(req_q, res_q, cls)

        for i in range(5):
            req_q.put({"tmp_path": f"/fake/{i}.pdf"})

        results = [res_q.get(timeout=5.0) for _ in range(5)]

        req_q.put(_SENTINEL)
        t.join(timeout=2.0)

        assert all(r["status"] == "ok" for r in results)
        assert len(results) == 5


# ---------------------------------------------------------------------------
# Tests: MarkerIPCWorker — lifecycle
# ---------------------------------------------------------------------------


class TestMarkerIPCWorkerLifecycle:

    def test_not_alive_before_start(self) -> None:
        worker = _make_worker()
        assert not worker.is_alive()

    def test_alive_after_start(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        try:
            worker.start()
            assert worker.is_alive()
        finally:
            worker.shutdown()

    def test_start_raises_if_already_running(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                worker.start()
        finally:
            worker.shutdown()

    def test_shutdown_when_not_started_is_noop(self) -> None:
        worker = _make_worker()
        worker.shutdown()  # must not raise
        assert not worker.is_alive()

    def test_shutdown_is_idempotent(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        worker.shutdown()
        worker.shutdown()  # second call must not raise
        assert not worker.is_alive()

    def test_not_alive_after_shutdown(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        assert worker.is_alive()
        worker.shutdown()
        assert not worker.is_alive()

    def test_restart_when_not_running_acts_as_start(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        assert not worker.is_alive()
        worker.restart()
        assert worker.is_alive()
        worker.shutdown()

    def test_restart_when_running_spawns_new_process(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        old_proc = worker._proc
        worker.restart()
        assert worker._proc is not old_proc, "restart() must spawn a new process"
        assert worker.is_alive()
        worker.shutdown()


# ---------------------------------------------------------------------------
# Tests: MarkerIPCWorker — parse()
# ---------------------------------------------------------------------------


class TestMarkerIPCWorkerParse:

    def test_parse_single_paper_ok(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            result = worker.parse("/fake/paper.pdf", timeout=5.0)
            assert result["status"] == "ok"
            assert len(result["body"]) > 100
            assert result["failure_reason"] is None
            assert result["parse_seconds"] >= 0.0
        finally:
            worker.shutdown()

    def test_parse_result_has_required_keys(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            result = worker.parse("/fake/paper.pdf", timeout=5.0)
            for key in ("status", "body", "meta", "parse_seconds", "failure_reason"):
                assert key in result, f"missing key: {key!r}"
        finally:
            worker.shutdown()

    def test_parse_meta_body_source_is_marker(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            result = worker.parse("/fake/paper.pdf", timeout=5.0)
            assert result["status"] == "ok"
            assert result["meta"].get("body_source") == "marker"
        finally:
            worker.shutdown()

    def test_parse_multiple_papers_reuse_worker(self) -> None:
        """Three parse() calls reuse the same worker — create_model_dict called once."""
        cls, call_log = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            for i in range(3):
                result = worker.parse(f"/fake/p{i}.pdf", timeout=5.0)
                assert result["status"] == "ok", f"paper {i} failed: {result}"

            # Warm reuse proof: model dict created exactly once across all papers.
            assert len(call_log) == 1, (
                f"create_model_dict called {len(call_log)} times across 3 papers; "
                "expected exactly 1 (IPC warm worker reuse)"
            )
        finally:
            worker.shutdown()

    def test_parse_when_not_started_returns_error(self) -> None:
        worker = _make_worker()
        result = worker.parse("/fake/paper.pdf", timeout=5.0)
        assert result["status"] == "error"
        assert "worker_not_running" in result["failure_reason"]

    def test_worker_extract_error_propagates_as_error_dict(self) -> None:
        cls, _ = _make_mock_extractor(
            raise_on_extract=RuntimeError("PDF parser crashed badly")
        )
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            result = worker.parse("/fake/paper.pdf", timeout=5.0)
            assert result["status"] == "error"
            assert "PDF parser crashed badly" in result["failure_reason"]
            assert result["body"] == ""
        finally:
            worker.shutdown()

    def test_per_paper_error_does_not_kill_worker(self) -> None:
        """After one paper fails, the next paper still succeeds on the same worker."""
        fail_once = [False]

        class _FailOnceCls:
            def __init__(self, _marker_modules=None, _preloaded_model_dict=None):
                self._preloaded_model_dict = _preloaded_model_dict

            def _load_marker(self) -> dict:
                def cmd(): return {"model": "ok"}
                return {"create_model_dict": cmd}

            def extract(self, path, **kwargs) -> _MockDoc:
                if not fail_once[0]:
                    fail_once[0] = True
                    raise ValueError("first paper transient error")
                return _MockDoc()

        worker = _make_worker(extractor_cls=_FailOnceCls)
        worker.start()
        try:
            r1 = worker.parse("/fake/p1.pdf", timeout=5.0)
            assert r1["status"] == "error"
            assert "first paper transient error" in r1["failure_reason"]

            r2 = worker.parse("/fake/p2.pdf", timeout=5.0)
            assert r2["status"] == "ok"
        finally:
            worker.shutdown()

    def test_timeout_returns_error_and_marks_not_alive(self) -> None:
        """When parse() times out, _terminate_worker() sets _proc=None → is_alive() False."""
        cls, _ = _make_mock_extractor(extract_delay=60.0)  # effectively hangs
        worker = _make_worker(
            extractor_cls=cls,
            terminate_grace=0.05,
            kill_grace=0.05,
        )
        worker.start()

        result = worker.parse("/fake/paper.pdf", timeout=0.05)

        assert result["status"] == "error"
        assert "marker_timeout" in result["failure_reason"]
        # _terminate_worker() sets self._proc = None, so is_alive() is False.
        assert not worker.is_alive()

        worker.shutdown()  # idempotent no-op after timeout

    def test_restart_after_timeout_restores_parse(self) -> None:
        """After a timeout, restart() + parse() succeeds with a new cold load."""
        slow_cls, _ = _make_mock_extractor(extract_delay=60.0)
        normal_cls, call_log = _make_mock_extractor()

        worker = _make_worker(
            extractor_cls=slow_cls,
            terminate_grace=0.05,
            kill_grace=0.05,
        )
        worker.start()

        result1 = worker.parse("/fake/p1.pdf", timeout=0.05)
        assert result1["status"] == "error"
        assert not worker.is_alive()

        # Swap extractor and restart.
        worker._extractor_cls = normal_cls
        worker.restart()
        assert worker.is_alive()

        result2 = worker.parse("/fake/p2.pdf", timeout=5.0)
        assert result2["status"] == "ok"
        assert len(call_log) == 1  # new cold load for the restarted worker

        worker.shutdown()

    def test_no_pdfplumber_fallback_on_error(self) -> None:
        """Error results never have body_source=pdfplumber_fallback."""
        cls, _ = _make_mock_extractor(raise_on_extract=ValueError("Marker failed"))
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            result = worker.parse("/fake/paper.pdf", timeout=5.0)
            assert result["status"] == "error"
            assert result["meta"].get("body_source") != "pdfplumber_fallback"
            assert result["meta"].get("body_source") != "pdfplumber"
        finally:
            worker.shutdown()


# ---------------------------------------------------------------------------
# Tests: MarkerIPCWorker — extract() raw IPC call
# ---------------------------------------------------------------------------


class TestMarkerIPCWorkerExtractRaw:

    def test_extract_raises_runtime_error_when_not_started(self) -> None:
        worker = _make_worker()
        with pytest.raises(RuntimeError, match="not started"):
            worker.extract("/fake/paper.pdf", timeout=1.0)

    def test_extract_returns_raw_result_dict(self) -> None:
        cls, _ = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            result = worker.extract("/fake/paper.pdf", timeout=5.0)
            assert result["status"] == "ok"
            assert "body" in result
        finally:
            worker.shutdown()

    def test_extract_raises_queue_empty_on_timeout(self) -> None:
        """extract() propagates queue.Empty — caller is responsible for handling it."""
        cls, _ = _make_mock_extractor(extract_delay=60.0)
        worker = _make_worker(extractor_cls=cls, terminate_grace=0.05, kill_grace=0.05)
        worker.start()
        try:
            with pytest.raises(queue.Empty):
                worker.extract("/fake/paper.pdf", timeout=0.05)
        finally:
            worker._terminate_worker()  # force-clean the hanging thread


# ---------------------------------------------------------------------------
# Tests: LiveAcademicFetcher._marker_ipc_worker_extract() restart-after-timeout
#
# These tests verify that when parse() returns a marker_timeout error the fetcher
# calls restart() on the IPC worker, so subsequent papers in the same session can
# proceed rather than immediately failing with worker_not_running.
# ---------------------------------------------------------------------------


class _MockIPCWorker:
    """Minimal mock of MarkerIPCWorker for fetcher integration tests.

    Tracks calls to parse() and restart() via lists.  parse() returns items from
    _parse_results in order; if exhausted, returns a generic error dict.
    """

    def __init__(self, parse_results: "list[dict]") -> None:
        self._results = list(parse_results)
        self.parse_calls: "list[str]" = []
        self.restart_calls: "list[int]" = []
        self._restart_count = 0
        self._raise_on_restart: "Optional[Exception]" = None

    def parse(self, pdf_path: str, timeout: float = 900.0) -> dict:
        self.parse_calls.append(pdf_path)
        if self._results:
            return self._results.pop(0)
        return {
            "status": "error",
            "body": "",
            "meta": {},
            "parse_seconds": 0.0,
            "failure_reason": "worker_not_running: call start() before parse()",
        }

    def restart(self) -> None:
        self._restart_count += 1
        self.restart_calls.append(self._restart_count)
        if self._raise_on_restart is not None:
            raise self._raise_on_restart


def _make_timeout_result(timeout_secs: float = 900.0) -> dict:
    return {
        "status": "error",
        "body": "",
        "meta": {},
        "parse_seconds": timeout_secs,
        "failure_reason": f"marker_timeout: extraction timed out after {timeout_secs}s",
    }


def _make_ok_result(body: str = "x" * 5000) -> dict:
    return {
        "status": "ok",
        "body": body,
        "meta": {"body_source": "marker", "page_count": 10, "parse_seconds": 6.0},
        "parse_seconds": 6.0,
        "failure_reason": None,
    }


def _fetcher_with_mock_worker(mock_worker: _MockIPCWorker) -> "object":
    """Return a LiveAcademicFetcher wired to the given mock IPC worker."""
    from packages.research.ingestion.fetchers import LiveAcademicFetcher
    return LiveAcademicFetcher(
        _marker_timeout_seconds=900.0,
        _ipc_worker=mock_worker,
    )


class TestFetcherIPCWorkerRestartAfterTimeout:
    """Verify that _marker_ipc_worker_extract() calls restart() after a timeout.

    Covers the fix for the live-validation blocker: after a paper times out and
    kills the IPC worker, subsequent papers in the same process_next_ipc() call
    must not fail immediately with worker_not_running.
    """

    def test_timeout_triggers_restart(self) -> None:
        """After a marker_timeout result, restart() must be called on the worker."""
        mock = _MockIPCWorker([_make_timeout_result()])
        fetcher = _fetcher_with_mock_worker(mock)

        body, meta = fetcher._marker_ipc_worker_extract("/fake/p1.pdf")

        assert body == ""
        assert meta["body_source"] == "marker_failed"
        assert "marker_timeout" in meta["failure_reason"]
        assert len(mock.restart_calls) == 1, (
            "restart() must be called once after a timeout"
        )

    def test_timeout_does_not_set_marker_disabled(self) -> None:
        """The IPC path must never set _MARKER_DISABLED — that flag is for the thread path."""
        from packages.research.ingestion.fetchers import _MARKER_DISABLED
        _MARKER_DISABLED.clear()

        mock = _MockIPCWorker([_make_timeout_result()])
        fetcher = _fetcher_with_mock_worker(mock)
        fetcher._marker_ipc_worker_extract("/fake/p1.pdf")

        assert not _MARKER_DISABLED.is_set(), (
            "_MARKER_DISABLED must not be set by the IPC worker path"
        )

    def test_second_paper_succeeds_after_timeout_and_restart(self) -> None:
        """After restart(), the next parse() call returns ok — not worker_not_running."""
        mock = _MockIPCWorker([_make_timeout_result(), _make_ok_result()])
        fetcher = _fetcher_with_mock_worker(mock)

        # Paper 1 times out — restart() called
        body1, meta1 = fetcher._marker_ipc_worker_extract("/fake/p1.pdf")
        assert body1 == ""
        assert "marker_timeout" in meta1["failure_reason"]
        assert len(mock.restart_calls) == 1

        # Paper 2 — worker was restarted, parse succeeds
        body2, meta2 = fetcher._marker_ipc_worker_extract("/fake/p2.pdf")
        assert len(body2) >= 200
        assert meta2.get("body_source") == "marker"
        # No second restart triggered (success path)
        assert len(mock.restart_calls) == 1

    def test_no_restart_on_non_timeout_error(self) -> None:
        """restart() must NOT be called for non-timeout worker errors."""
        non_timeout_result = {
            "status": "error",
            "body": "",
            "meta": {},
            "parse_seconds": 1.5,
            "failure_reason": "marker model load failed: CUDA OOM",
        }
        mock = _MockIPCWorker([non_timeout_result])
        fetcher = _fetcher_with_mock_worker(mock)

        body, meta = fetcher._marker_ipc_worker_extract("/fake/p1.pdf")

        assert body == ""
        assert meta["body_source"] == "marker_failed"
        assert len(mock.restart_calls) == 0, (
            "restart() must not be called for non-timeout errors"
        )

    def test_restart_failure_does_not_raise(self) -> None:
        """If restart() raises, the method must still return the error dict cleanly."""
        mock = _MockIPCWorker([_make_timeout_result()])
        mock._raise_on_restart = RuntimeError("cannot restart: GPU OOM")
        fetcher = _fetcher_with_mock_worker(mock)

        body, meta = fetcher._marker_ipc_worker_extract("/fake/p1.pdf")

        assert body == ""
        assert meta["body_source"] == "marker_failed"
        assert "marker_timeout" in meta["failure_reason"]
        # restart was attempted (the exception was caught internally)
        assert len(mock.restart_calls) == 1

    def test_worker_not_running_result_does_not_trigger_restart(self) -> None:
        """worker_not_running is not a timeout — no restart should be attempted."""
        not_running_result = {
            "status": "error",
            "body": "",
            "meta": {},
            "parse_seconds": 0.0,
            "failure_reason": "worker_not_running: call start() before parse()",
        }
        mock = _MockIPCWorker([not_running_result])
        fetcher = _fetcher_with_mock_worker(mock)

        body, meta = fetcher._marker_ipc_worker_extract("/fake/p1.pdf")

        assert body == ""
        assert meta["body_source"] == "marker_failed"
        assert len(mock.restart_calls) == 0


# ---------------------------------------------------------------------------
# Tests: daemon=False fix — process factory must receive daemon=False
#
# Root cause of live-validation failure: start() passed daemon=True to the
# process factory. Daemon processes cannot spawn child processes. Marker's
# ONNX/torch pipeline spawns internal workers during extraction. Paper 1
# succeeded (cold-load path avoided child spawning); paper 2 failed
# immediately with "daemonic processes are not allowed to have children"
# (parse_seconds=0.0, total_seconds=0.24s — error before any Marker inference).
#
# Fix: start() and restart() pass daemon=False so the worker process can
# spawn its own children. Lifecycle cleanup is explicit (shutdown/_terminate).
# ---------------------------------------------------------------------------


class TestMarkerIPCWorkerDaemonSafety:

    def test_start_passes_daemon_false_to_factory(self) -> None:
        """MarkerIPCWorker.start() must pass daemon=False to the process factory."""
        captured: list[bool] = []

        def _capturing_factory(target, args=(), daemon=False) -> _ThreadProcess:
            captured.append(daemon)
            return _ThreadProcess(target=target, args=args, daemon=True)

        cls, _ = _make_mock_extractor()
        worker = MarkerIPCWorker(
            _extractor_cls=cls,
            _process_factory=_capturing_factory,
            _queue_factory=queue.Queue,
            _terminate_grace_seconds=0.1,
            _kill_grace_seconds=0.1,
            _shutdown_join_timeout=2.0,
        )
        worker.start()
        try:
            assert len(captured) == 1
            assert captured[0] is False, (
                f"start() must pass daemon=False to the process factory, got {captured[0]!r}. "
                "Daemon processes cannot spawn children — Marker's ONNX/torch workers fail "
                "with 'daemonic processes are not allowed to have children'."
            )
        finally:
            worker.shutdown()

    def test_restart_passes_daemon_false_to_factory(self) -> None:
        """restart() must also create the new process with daemon=False."""
        captured: list[bool] = []

        def _capturing_factory(target, args=(), daemon=False) -> _ThreadProcess:
            captured.append(daemon)
            return _ThreadProcess(target=target, args=args, daemon=True)

        cls, _ = _make_mock_extractor()
        worker = MarkerIPCWorker(
            _extractor_cls=cls,
            _process_factory=_capturing_factory,
            _queue_factory=queue.Queue,
            _terminate_grace_seconds=0.1,
            _kill_grace_seconds=0.1,
            _shutdown_join_timeout=2.0,
        )
        worker.start()
        worker.restart()
        try:
            assert len(captured) == 2, f"Factory called {len(captured)} times; expected 2 (start + restart)"
            for i, flag in enumerate(captured):
                assert flag is False, (
                    f"Factory call {i + 1} used daemon={flag!r}; restart must also use daemon=False"
                )
        finally:
            worker.shutdown()

    def test_multi_parse_paper1_ok_paper2_ok(self) -> None:
        """Paper 1 then paper 2 must both succeed — the core live-failure scenario."""
        cls, call_log = _make_mock_extractor()
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            r1 = worker.parse("/fake/p1.pdf", timeout=5.0)
            assert r1["status"] == "ok", f"Paper 1 failed: {r1}"

            r2 = worker.parse("/fake/p2.pdf", timeout=5.0)
            assert r2["status"] == "ok", (
                f"Paper 2 failed: {r2}. "
                "If failure_reason contains 'daemonic', daemon=False fix was not applied."
            )

            # Model loaded once across both papers (warm reuse)
            assert len(call_log) == 1
        finally:
            worker.shutdown()

    def test_daemonic_error_from_extractor_surfaced_as_structured_error(self) -> None:
        """If Marker internals raise the daemonic AssertionError, it surfaces as error dict.

        With daemon=False, the worker process itself can spawn children. But if
        Marker's code raises this error for an unrelated reason, the worker loop
        must catch it and return a structured error dict — not crash the loop.
        """
        cls, _ = _make_mock_extractor(
            raise_on_extract=AssertionError(
                "daemonic processes are not allowed to have children"
            )
        )
        worker = _make_worker(extractor_cls=cls)
        worker.start()
        try:
            result = worker.parse("/fake/paper.pdf", timeout=5.0)
            assert result["status"] == "error"
            assert "daemonic" in result["failure_reason"]
            # Worker must still be alive — a per-paper error does not kill the loop
            assert worker.is_alive()
        finally:
            worker.shutdown()

    def test_worker_survives_daemonic_error_and_next_paper_succeeds(self) -> None:
        """After daemonic error on paper 1, paper 2 succeeds on the same warm worker."""
        fail_once = [False]

        class _DaemonicOnce:
            def __init__(self, _marker_modules=None, _preloaded_model_dict=None):
                self._preloaded_model_dict = _preloaded_model_dict

            def _load_marker(self) -> dict:
                def cmd(): return {"model": "ok"}
                return {"create_model_dict": cmd}

            def extract(self, path, **kwargs) -> _MockDoc:
                if not fail_once[0]:
                    fail_once[0] = True
                    raise AssertionError(
                        "daemonic processes are not allowed to have children"
                    )
                return _MockDoc()

        worker = _make_worker(extractor_cls=_DaemonicOnce)
        worker.start()
        try:
            r1 = worker.parse("/fake/p1.pdf", timeout=5.0)
            assert r1["status"] == "error"
            assert "daemonic" in r1["failure_reason"]

            r2 = worker.parse("/fake/p2.pdf", timeout=5.0)
            assert r2["status"] == "ok"
        finally:
            worker.shutdown()
