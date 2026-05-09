"""Marker Canonical Academic Parse Queue v0.

File-backed queue for async Marker parsing of arXiv papers. Keeps Marker models
warm by processing multiple papers sequentially within a single long-running process.

Artifacts (gitignored):
  artifacts/research/marker_parse_queue/queue.jsonl   -- mutable queue state
  artifacts/research/marker_parse_queue/results.jsonl -- append-only results log

Status flow:
  pending -> processing -> done
                       -> pending  (retryable failure, attempts < MAX_ATTEMPTS)
                       -> failed   (terminal after MAX_ATTEMPTS)

RAG-ready rule (canonical):
  marker_ready = body_source == "marker" AND body_length >= MIN_MARKER_BODY_LENGTH
  pdfplumber, pdfplumber_fallback, abstract_fallback, marker_failed: NOT marker_ready.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)

_DEFAULT_QUEUE_DIR = Path("artifacts/research/marker_parse_queue")

MAX_ATTEMPTS = 3
MIN_MARKER_BODY_LENGTH = 5000  # chars; below this even a "marker" parse is not rag-ready

_ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate_id_from_arxiv(arxiv_id: str) -> str:
    return f"arxiv:{arxiv_id}"


def extract_arxiv_id(url_or_id: str) -> Optional[str]:
    """Extract arXiv ID from URL or bare ID string. Returns None if not found."""
    m = _ARXIV_ID_RE.search(url_or_id)
    return m.group(1) if m else None


def is_marker_ready(body_source: str, body_length: int) -> bool:
    """Return True only when parse result is Marker-quality and meets size threshold.

    This is the canonical RAG-readiness guard. pdfplumber, pdfplumber_fallback,
    abstract_fallback, and marker_failed all return False regardless of length.
    """
    return body_source == "marker" and body_length >= MIN_MARKER_BODY_LENGTH


class MarkerParseQueue:
    """File-backed queue for async Marker PDF parsing of arXiv papers.

    One instance = one queue directory. Not thread-safe; intended for use
    by a single long-running worker process.

    Parameters
    ----------
    queue_dir:
        Directory for queue.jsonl and results.jsonl. Defaults to
        artifacts/research/marker_parse_queue relative to cwd.
    """

    def __init__(self, queue_dir: Optional[Path] = None) -> None:
        self.queue_dir = Path(queue_dir) if queue_dir else _DEFAULT_QUEUE_DIR
        self._queue_path = self.queue_dir / "queue.jsonl"
        self._results_path = self.queue_dir / "results.jsonl"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_dir(self) -> None:
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def _read_queue(self) -> list[dict]:
        if not self._queue_path.exists():
            return []
        records: list[dict] = []
        with open(self._queue_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return records

    def _write_queue(self, records: list[dict]) -> None:
        self._ensure_dir()
        with open(self._queue_path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def _append_result(self, result: dict) -> None:
        self._ensure_dir()
        with open(self._results_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(result, separators=(",", ":")) + "\n")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self, url_or_id: str, title: str = "", force: bool = False, pdf_url: str = ""
    ) -> dict:
        """Enqueue one arXiv paper for Marker parsing.

        Parameters
        ----------
        url_or_id:
            arXiv URL or bare arXiv ID (e.g. "2604.24366").
        title:
            Optional title hint. Fetcher will resolve from API if empty.
        force:
            Re-enqueue even if candidate already exists (resets to pending/0 attempts).
        pdf_url:
            Optional direct PDF URL or local path. When set, warm-process skips the
            arXiv metadata API and downloads/reads the PDF directly. Useful when the
            arXiv Atom API is rate-limited. Does not affect candidate_id derivation.

        Returns
        -------
        dict: candidate_id, status, action ("added"|"skipped"|"reset")
        """
        arxiv_id = extract_arxiv_id(url_or_id)
        if arxiv_id is None:
            raise ValueError(f"Cannot extract arXiv ID from: {url_or_id!r}")

        source_url = f"https://arxiv.org/abs/{arxiv_id}"
        cid = _candidate_id_from_arxiv(arxiv_id)

        records = self._read_queue()
        existing_idx = next(
            (i for i, r in enumerate(records) if r.get("candidate_id") == cid), None
        )

        if existing_idx is not None:
            existing = records[existing_idx]
            if not force:
                return {
                    "candidate_id": cid,
                    "status": existing["status"],
                    "action": "skipped",
                    "reason": f"already in queue with status={existing['status']!r}",
                }
            now = _now_iso()
            records[existing_idx] = {
                **existing,
                "status": "pending",
                "attempts": 0,
                "updated_at": now,
            }
            self._write_queue(records)
            return {"candidate_id": cid, "status": "pending", "action": "reset"}

        now = _now_iso()
        record: dict = {
            "candidate_id": cid,
            "source_url": source_url,
            "arxiv_id": arxiv_id,
            "title": title,
            "status": "pending",
            "attempts": 0,
            "created_at": now,
            "updated_at": now,
        }
        if pdf_url:
            record["pdf_url"] = pdf_url
        records.append(record)
        self._write_queue(records)
        return {"candidate_id": cid, "status": "pending", "action": "added"}

    def list_queue(self, status_filter: Optional[str] = None) -> list[dict]:
        """Return queue records, optionally filtered by status.

        Parameters
        ----------
        status_filter:
            One of "pending", "processing", "done", "failed", or None / "all".
        """
        records = self._read_queue()
        if status_filter and status_filter != "all":
            records = [r for r in records if r.get("status") == status_filter]
        return records

    def get_counts(self) -> dict:
        """Return item counts grouped by status."""
        records = self._read_queue()
        counts: dict = {
            "pending": 0,
            "processing": 0,
            "done": 0,
            "failed": 0,
            "total": 0,
        }
        for r in records:
            s = r.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
            counts["total"] += 1
        return counts

    def process_next(
        self,
        max_items: int = 1,
        marker_timeout: float = 900.0,
        _fetcher=None,
        _extra_result_fields: Optional[dict] = None,
    ) -> list[dict]:
        """Process up to *max_items* pending items using LiveAcademicFetcher.

        Items are processed sequentially within one call.

        Warm-worker behaviour depends on platform:
        - **Windows (thread mode)**: Marker model weights are pre-loaded once before
          the first paper using ``create_warm_thread_worker()``, then reused for every
          subsequent paper in the batch.  This amortizes the cold-load cost (~80 s)
          across all items.
        - **Linux/Docker (subprocess mode)**: a fresh Marker process is spawned for
          each paper and ``create_model_dict()`` runs per extraction.  For warm model
          reuse across subprocess boundaries use ``process_next_ipc()`` instead.

        Parameters
        ----------
        max_items:
            Maximum number of pending queue items to process this call.
        marker_timeout:
            Marker extraction timeout in seconds.
        _fetcher:
            Injectable fetcher (for tests). Must have a .fetch(url) -> dict method.
            If None, a LiveAcademicFetcher is created automatically.

        Returns
        -------
        list of result dicts (one per processed item, in order).
        """
        if _fetcher is None:
            from packages.research.ingestion.fetchers import (
                LiveAcademicFetcher,
                _MARKER_DEFAULT_USE_PROCESS,
            )
            if not _MARKER_DEFAULT_USE_PROCESS and max_items > 1:
                # Thread mode (Windows): pre-load Marker model once for the whole batch
                try:
                    fetcher = LiveAcademicFetcher.create_warm_thread_worker(
                        _marker_timeout_seconds=marker_timeout
                    )
                    _logger.info(
                        "marker_queue: warm thread worker created; model pre-loaded"
                    )
                except Exception as exc:
                    _logger.warning(
                        "marker_queue: warm pre-load failed (%s); using cold fetcher", exc
                    )
                    fetcher = LiveAcademicFetcher(_marker_timeout_seconds=marker_timeout)
            else:
                # Subprocess mode (Linux/Docker): each paper spawns a new process.
                # Model reloads per extraction. For warm IPC reuse, call process_next_ipc().
                fetcher = LiveAcademicFetcher(_marker_timeout_seconds=marker_timeout)
        else:
            fetcher = _fetcher

        processed: list[dict] = []
        items_done = 0

        while items_done < max_items:
            records = self._read_queue()
            pending = [r for r in records if r.get("status") == "pending"]
            if not pending:
                break

            item = pending[0]
            cid = item["candidate_id"]
            now = _now_iso()

            # Mark as processing
            for r in records:
                if r.get("candidate_id") == cid:
                    r["status"] = "processing"
                    r["updated_at"] = now
                    break
            self._write_queue(records)

            result = self._process_item(item, fetcher)

            # Determine final queue status
            records = self._read_queue()
            attempts = item.get("attempts", 0) + 1
            if not result["rejected"]:
                final_status = "done"
            elif attempts >= MAX_ATTEMPTS:
                final_status = "failed"
            else:
                final_status = "pending"  # retryable

            now2 = _now_iso()
            for r in records:
                if r.get("candidate_id") == cid:
                    r["status"] = final_status
                    r["attempts"] = attempts
                    r["updated_at"] = now2
                    if result.get("title"):
                        r["title"] = result["title"]
                    break
            self._write_queue(records)

            result_record = {
                **result,
                "processed_at": now2,
                "attempt": attempts,
                "queue_status": final_status,
                **(_extra_result_fields if _extra_result_fields else {}),
            }
            self._append_result(result_record)
            processed.append(result_record)
            items_done += 1

            _logger.info(
                "marker_queue: %s → status=%s body_source=%s marker_ready=%s",
                cid,
                final_status,
                result.get("body_source"),
                result.get("marker_ready"),
            )

        return processed

    def process_next_ipc(
        self,
        max_items: int = 1,
        marker_timeout: float = 900.0,
        _ipc_worker=None,
        _fetcher=None,
    ) -> list[dict]:
        """Process pending items using MarkerIPCWorker (warm IPC, Linux/Docker).

        One MarkerIPCWorker is created for the entire batch — models cold-loaded
        once and kept warm across all papers in the session.

        On Windows (thread mode) falls back to create_warm_thread_worker().

        L1 production readiness rollout COMPLETE 2026-05-09. IPC warm-worker
        validated 2026-05-08 (Feature 3 closed). See
        docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md.

        Parameters
        ----------
        max_items:
            Maximum number of pending queue items to process.
        marker_timeout:
            Marker extraction timeout in seconds.
        _ipc_worker:
            Injectable MarkerIPCWorker for tests (bypasses real subprocess spawn).
            None = create MarkerIPCWorker on Linux/Docker.
        _fetcher:
            Injectable fetcher (for tests). When provided, bypasses worker lifecycle
            management entirely and delegates directly to process_next().

        Returns
        -------
        list of result dicts, each containing ``ipc_warm_worker_used`` bool.
        """
        if _fetcher is not None:
            ipc_flag = _ipc_worker is not None
            return self.process_next(
                max_items=max_items,
                marker_timeout=marker_timeout,
                _fetcher=_fetcher,
                _extra_result_fields={"ipc_warm_worker_used": ipc_flag},
            )

        from packages.research.ingestion.fetchers import (
            LiveAcademicFetcher,
            _MARKER_DEFAULT_USE_PROCESS,
        )

        owns_worker = False
        worker = _ipc_worker

        try:
            if worker is None and _MARKER_DEFAULT_USE_PROCESS:
                from packages.research.ingestion.marker_ipc_worker import MarkerIPCWorker
                worker = MarkerIPCWorker()
                worker.start()
                owns_worker = True
                _logger.info("marker_queue: IPC warm worker started for batch of %d", max_items)

            if worker is not None:
                fetcher: object = LiveAcademicFetcher(
                    _marker_timeout_seconds=marker_timeout,
                    _ipc_worker=worker,
                )
                ipc_used = True
            else:
                # Windows: warm thread worker
                try:
                    fetcher = LiveAcademicFetcher.create_warm_thread_worker(
                        _marker_timeout_seconds=marker_timeout
                    )
                    _logger.info("marker_queue: warm thread worker created (Windows path)")
                except Exception as exc:
                    _logger.warning(
                        "marker_queue: warm pre-load failed (%s); cold fetcher used", exc
                    )
                    fetcher = LiveAcademicFetcher(_marker_timeout_seconds=marker_timeout)
                ipc_used = False

            results = self.process_next(
                max_items=max_items,
                marker_timeout=marker_timeout,
                _fetcher=fetcher,
                _extra_result_fields={"ipc_warm_worker_used": ipc_used},
            )
            return results

        finally:
            if owns_worker and worker is not None:
                try:
                    worker.shutdown()
                    _logger.info("marker_queue: IPC warm worker shut down")
                except Exception as exc:
                    _logger.warning("marker_queue: IPC worker shutdown error: %s", exc)

    def _process_item(self, item: dict, fetcher) -> dict:
        """Fetch and parse one queue item. Returns a result dict."""
        import time as _time

        t0 = _time.monotonic()
        cid = item["candidate_id"]
        source_url = item.get("source_url", "")

        result: dict = {
            "candidate_id": cid,
            "source_url": source_url,
            "arxiv_id": item.get("arxiv_id", ""),
            "title": item.get("title", ""),
            "body_source": "unknown",
            "body_length": 0,
            "parse_seconds": 0.0,
            "failure_reason": None,
            "rejected": False,
            "exit_code": 0,
            "marker_ready": False,
        }

        try:
            pdf_url = item.get("pdf_url", "")
            if pdf_url and hasattr(fetcher, "fetch_pdf_direct"):
                raw = fetcher.fetch_pdf_direct(pdf_url, title=item.get("title", ""))
            else:
                raw = fetcher.fetch(source_url)
            result["title"] = raw.get("title", "") or result["title"]
            result["body_source"] = raw.get("body_source", "unknown")
            result["body_length"] = int(raw.get("body_length", 0) or 0)
            result["parse_seconds"] = float(raw.get("parse_seconds", 0.0) or 0.0)

            if result["body_source"] != "marker":
                result["failure_reason"] = (
                    raw.get("failure_reason")
                    or raw.get("fallback_reason")
                    or f"non-marker output: body_source={result['body_source']!r}"
                )
                result["rejected"] = True
                result["exit_code"] = 1
            elif result["body_length"] < MIN_MARKER_BODY_LENGTH:
                result["failure_reason"] = (
                    f"marker_body_too_short: {result['body_length']} chars < "
                    f"{MIN_MARKER_BODY_LENGTH} threshold"
                )
                result["rejected"] = True
                result["exit_code"] = 1

        except Exception as exc:
            result["body_source"] = "error"
            result["failure_reason"] = str(exc)[:300]
            result["rejected"] = True
            result["exit_code"] = 1

        result["marker_ready"] = is_marker_ready(result["body_source"], result["body_length"])
        result["total_seconds"] = round(_time.monotonic() - t0, 2)
        return result
