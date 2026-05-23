"""CLI entrypoint for Marker Canonical Academic Parse Queue v0.

Subcommands:
  enqueue    Add one arXiv paper URL / ID to the parse queue
  list       Show queue items (optionally filtered by status)
  process    Process next N pending items using the Marker worker
  counts     Show item counts by status

Usage:
  python -m polytool research-marker-queue enqueue --url 2604.24366
  python -m polytool research-marker-queue enqueue --url https://arxiv.org/abs/2604.24366
  python -m polytool research-marker-queue list
  python -m polytool research-marker-queue list --status pending
  python -m polytool research-marker-queue process --max-items 5 --marker-timeout 900
  python -m polytool research-marker-queue counts
  python -m polytool research-marker-queue counts --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _cmd_enqueue(args: argparse.Namespace) -> int:
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    try:
        outcome = q.enqueue(
            args.url,
            title=args.title or "",
            force=args.force,
            pdf_url=getattr(args, "pdf_url", "") or "",
            ingest_tier=getattr(args, "tier", 2),
        )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "exit_code": 1}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(outcome, indent=2))
    else:
        action = outcome.get("action", "?")
        cid = outcome.get("candidate_id", "?")
        status = outcome.get("status", "?")
        if action == "added":
            print(f"Enqueued: {cid}  (status=pending)")
        elif action == "reset":
            print(f"Reset:    {cid}  (status=pending, attempts=0)")
        else:
            reason = outcome.get("reason", "")
            print(f"Skipped:  {cid}  ({reason})")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    status_filter = args.status if args.status != "all" else None
    records = q.list_queue(status_filter=status_filter)

    if args.json:
        print(json.dumps(records, indent=2))
        return 0

    if not records:
        print("Queue is empty." if not status_filter else f"No items with status={status_filter!r}.")
        return 0

    col_cid = 28
    col_status = 12
    col_att = 5
    col_title = 40
    header = (
        f"  {'candidate_id':<{col_cid}} {'status':<{col_status}} "
        f"{'att':<{col_att}} {'title':<{col_title}}"
    )
    print(header)
    print("  " + "-" * (col_cid + col_status + col_att + col_title + 6))
    for r in records:
        cid = r.get("candidate_id", "?")[:col_cid]
        st = r.get("status", "?")[:col_status]
        att = str(r.get("attempts", 0))[:col_att]
        title = (r.get("title", "") or "")[:col_title]
        print(f"  {cid:<{col_cid}} {st:<{col_status}} {att:<{col_att}} {title:<{col_title}}")
    print()
    print(f"Total: {len(records)} item(s)")
    return 0


def _cmd_process(args: argparse.Namespace) -> int:
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    counts_before = q.get_counts()
    pending = counts_before.get("pending", 0)
    if pending == 0:
        if args.json:
            print(json.dumps({"processed": [], "exit_code": 0, "message": "no pending items"}))
        else:
            print("No pending items in queue.")
        return 0

    max_items: int = args.max_items
    marker_timeout: float = args.marker_timeout

    if not args.json:
        to_process = min(max_items, pending)
        print(
            f"Processing up to {to_process} item(s) "
            f"(marker_timeout={marker_timeout}s, MAX_ATTEMPTS=3)"
        )

    results = q.process_next(max_items=max_items, marker_timeout=marker_timeout)

    if args.json:
        print(json.dumps({"processed": results, "exit_code": 0}, indent=2))
        return 0

    for r in results:
        status_tag = "PASS" if r.get("marker_ready") else "FAIL"
        cid = r.get("candidate_id", "?")
        bs = r.get("body_source", "?")
        bl = r.get("body_length", 0)
        ps = r.get("parse_seconds", 0.0)
        qs = r.get("queue_status", "?")
        print(f"[{status_tag}] {cid}")
        print(f"       body_source:  {bs}")
        if bl:
            print(f"       body_length:  {bl:,} chars")
        if ps:
            print(f"       parse_seconds:{ps:.1f}s")
        if r.get("failure_reason"):
            print(f"       failure:      {r['failure_reason']}")
        print(f"       queue_status: {qs}  marker_ready={r.get('marker_ready')}")

    done_count = sum(1 for r in results if r.get("queue_status") == "done")
    fail_count = len(results) - done_count
    print()
    print(f"Processed {len(results)} item(s): {done_count} done, {fail_count} failed/retried.")
    return 0


def _cmd_warm_process(args: argparse.Namespace) -> int:
    import sys as _sys
    from packages.research.ingestion.marker_queue import (
        MarkerParseQueue,
        auto_timeout_from_file_size,
        _FILE_SIZE_TIMEOUT_DEFAULT,
    )

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    counts_before = q.get_counts()
    pending = counts_before.get("pending", 0)
    if pending == 0:
        if args.json:
            print(json.dumps({
                "processed": [],
                "exit_code": 0,
                "message": "no pending items",
                "ipc_warm_worker_used": False,
            }))
        else:
            print("No pending items in queue.")
        return 0

    max_items: int = args.max_items
    auto_timeout: bool = getattr(args, "auto_timeout", False)
    platform_note = (
        "Linux/Docker IPC warm-worker" if _sys.platform != "win32"
        else "Windows warm thread"
    )

    if auto_timeout:
        # Compute recommended timeout from prefetch manifest file sizes.
        # Uses the MAX across all pending items so the single-batch timeout
        # is safe for the worst case.
        # Fails with exit code 1 when any item lacks cached PDF size data
        # (prefetch not run). Use --allow-uncached to override.
        manifest = q._read_prefetch_manifest()
        pending_records = q.list_queue(status_filter="pending")
        timeouts: list[float] = []
        uncached_ids: list[str] = []
        for r in pending_records:
            cid = r.get("candidate_id", "")
            m_entry = manifest.get(cid, {})
            file_size = m_entry.get("file_size", 0) if m_entry.get("status") == "cached" else 0
            if file_size > 0:
                timeouts.append(auto_timeout_from_file_size(file_size))
            else:
                uncached_ids.append(cid)
                timeouts.append(_FILE_SIZE_TIMEOUT_DEFAULT)

        allow_uncached = getattr(args, "allow_uncached", False)
        if uncached_ids and not allow_uncached:
            err_lines = [
                f"--auto-timeout: {len(uncached_ids)} pending item(s) lack cached prefetch data.",
                "Run 'prefetch' first so PDF file sizes are known, then retry.",
                "Uncached items:",
            ]
            for cid in uncached_ids:
                err_lines.append(f"  {cid}")
            err_lines.append(
                f"Use --allow-uncached to proceed anyway "
                f"(falls back to {_FILE_SIZE_TIMEOUT_DEFAULT:.0f}s for uncached items)."
            )
            if args.json:
                print(json.dumps({
                    "error": "uncached items found for --auto-timeout",
                    "uncached_ids": uncached_ids,
                    "exit_code": 1,
                }))
            else:
                for line in err_lines:
                    print(line, file=sys.stderr)
            return 1

        if uncached_ids and not args.json:
            print(
                f"WARNING --allow-uncached: {len(uncached_ids)} item(s) have no prefetch data; "
                f"using {_FILE_SIZE_TIMEOUT_DEFAULT:.0f}s for them.",
                file=sys.stderr,
            )

        marker_timeout = max(timeouts) if timeouts else _FILE_SIZE_TIMEOUT_DEFAULT
        if not args.json:
            uncached_note = (
                f" ({len(uncached_ids)} used default timeout)" if uncached_ids else ""
            )
            print(
                f"Auto-timeout: {marker_timeout:.0f}s (max across {len(timeouts)} pending item(s))"
                f"{uncached_note}"
            )
    else:
        marker_timeout = args.marker_timeout

    if not args.json:
        to_process = min(max_items, pending)
        print(
            f"Processing up to {to_process} item(s) via {platform_note} "
            f"(marker_timeout={marker_timeout:.0f}s, MAX_ATTEMPTS=3)"
        )

    results = q.process_next_ipc(max_items=max_items, marker_timeout=marker_timeout)

    if args.json:
        any_ipc = any(r.get("ipc_warm_worker_used") for r in results)
        print(json.dumps({
            "processed": results,
            "exit_code": 0,
            "ipc_warm_worker_used": any_ipc,
        }, indent=2))
        return 0

    for r in results:
        status_tag = "PASS" if r.get("marker_ready") else "FAIL"
        cid = r.get("candidate_id", "?")
        bs = r.get("body_source", "?")
        bl = r.get("body_length", 0)
        ps = r.get("parse_seconds", 0.0)
        qs = r.get("queue_status", "?")
        ipc = r.get("ipc_warm_worker_used", False)
        print(f"[{status_tag}] {cid}")
        print(f"       body_source:          {bs}")
        if bl:
            print(f"       body_length:          {bl:,} chars")
        if ps:
            print(f"       parse_seconds:        {ps:.1f}s")
        if r.get("failure_reason"):
            print(f"       failure:              {r['failure_reason']}")
        print(f"       queue_status:         {qs}  marker_ready={r.get('marker_ready')}")
        print(f"       ipc_warm_worker_used: {ipc}")

    done_count = sum(1 for r in results if r.get("queue_status") == "done")
    fail_count = len(results) - done_count
    print()
    print(
        f"Processed {len(results)} item(s): {done_count} done, {fail_count} failed/retried."
    )
    return 0


def _cmd_index_done(args: argparse.Namespace) -> int:
    """Index all marker-ready done queue items into the KnowledgeStore."""
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)
    ks_path = Path(args.ks_path) if getattr(args, "ks_path", None) else None
    extract_claims = not getattr(args, "no_extract_claims", False)

    if not args.json:
        force_note = " (force=True: re-indexing all)" if args.force else ""
        extract_note = "" if extract_claims else " (--no-extract-claims: skipping extraction)"
        print(f"Indexing marker-ready done items into KnowledgeStore{force_note}{extract_note}...")

    try:
        summary = q.index_done_items(
            ks_path=ks_path, force=args.force, extract_claims=extract_claims
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "exit_code": 1}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2))
        return 0

    indexed = summary.get("indexed", [])
    skipped_dup = summary.get("skipped_already_indexed", [])
    skipped_no_body = summary.get("skipped_no_body", [])
    failed = summary.get("failed", [])
    total_claims = summary.get("total_claims_extracted", 0)

    if indexed:
        print(f"\nIndexed {len(indexed)} paper(s):")
        for item in indexed:
            claims_note = f"  claims={item.get('claims_extracted', 0)}" if extract_claims else ""
            print(
                f"  [OK] {item['candidate_id']}  doc_id={item['doc_id']}"
                f"  chunks={item['chunk_count']}{claims_note}"
            )
    if skipped_dup:
        print(f"\nSkipped {len(skipped_dup)} already-indexed paper(s):")
        for cid in skipped_dup:
            print(f"  [skip] {cid}")
    if skipped_no_body:
        print(f"\nSkipped {len(skipped_no_body)} paper(s) — body file missing:")
        for cid in skipped_no_body:
            print(f"  [no-body] {cid}  (re-enqueue with --force to re-process)")
    if failed:
        print(f"\nFailed {len(failed)} paper(s):")
        for item in failed:
            print(f"  [FAIL] {item.get('candidate_id', '?')}  {item.get('error', '')}")

    total = len(indexed) + len(skipped_dup) + len(skipped_no_body) + len(failed)
    claims_summary = f", {total_claims} claim(s) extracted" if extract_claims else ""
    print(
        f"\nTotal: {total} done item(s) examined — "
        f"{len(indexed)} indexed, {len(skipped_dup)} already-indexed, "
        f"{len(skipped_no_body)} no-body, {len(failed)} failed{claims_summary}."
    )
    # rc=1 only when there are hard failures; empty/skipped results are valid outcomes
    return 1 if failed else 0


def _cmd_prefetch(args: argparse.Namespace) -> int:
    """Download PDFs for pending queue items to local cache before warm-process."""
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    counts = q.get_counts()
    pending = counts.get("pending", 0)

    if pending == 0:
        if args.json:
            print(
                json.dumps(
                    {
                        "cached": [],
                        "skipped_already_cached": [],
                        "failed": [],
                        "total": 0,
                        "message": "no pending items",
                    }
                )
            )
        else:
            print("No pending items to prefetch.")
        return 0

    max_items: Optional[int] = args.max_items  # None = all
    delay_seconds: float = args.delay_seconds
    effective = min(max_items, pending) if max_items is not None else pending

    if not args.json:
        print(f"Prefetching PDFs for up to {effective} pending item(s)")
        print(f"  delay between downloads: {delay_seconds}s")
        cache_note = (
            str(q.queue_dir / "pdf_cache")
            if not args.queue_dir
            else str(Path(args.queue_dir) / "pdf_cache")
        )
        print(f"  cache dir: {cache_note}")
        print()

    try:
        result = q.prefetch_pdfs(
            max_items=max_items,
            delay_seconds=delay_seconds,
        )
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "exit_code": 1}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    cached = result.get("cached", [])
    skipped = result.get("skipped_already_cached", [])
    failed = result.get("failed", [])

    for item in cached:
        size_kb = item.get("file_size", 0) // 1024
        print(f"  [OK]   {item['candidate_id']}  ({size_kb} KB)")
    for cid in skipped:
        print(f"  [skip] {cid}  already cached")
    for item in failed:
        print(f"  [FAIL] {item['candidate_id']}  {item.get('error', '')[:80]}")

    print()
    print(
        f"Prefetch complete: {len(cached)} downloaded, "
        f"{len(skipped)} already cached, {len(failed)} failed "
        f"(total pending considered: {result.get('total', 0)})"
    )
    if failed:
        print(
            "Tip: re-run prefetch to retry failed items. "
            "Failed items still go through live arXiv fetch during warm-process."
        )
    return 0


def _cmd_status_report(args: argparse.Namespace) -> int:
    """Print a structured status report for the queue with stuck-item detection."""
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)

    try:
        report = q.get_status_report()
    except Exception as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "exit_code": 1}))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    counts = report.get("counts", {})
    print("Marker Queue Status Report")
    print("=" * 40)
    print(f"  pending:    {counts.get('pending', 0)}")
    print(f"  processing: {counts.get('processing', 0)}", end="")
    if report.get("stuck_warning"):
        print("  <-- likely stuck; no active warm-process")
    else:
        print()
    print(f"  done:       {counts.get('done', 0)}")
    print(f"  failed:     {counts.get('failed', 0)}")
    print(f"  total:      {counts.get('total', 0)}")

    ps = report.get("prefetch_stats", {})
    if ps.get("total_manifest_entries", 0) > 0:
        print(
            f"\nPrefetch cache: {ps.get('cached', 0)} cached, "
            f"{ps.get('failed', 0)} failed "
            f"({ps.get('total_manifest_entries', 0)} total entries in manifest)"
        )

    processing_items = report.get("processing_items", [])
    if processing_items:
        print("\nStuck/processing items (reset with --force):")
        queue_dir_arg = f"--queue-dir {args.queue_dir} " if args.queue_dir else ""
        for cid in processing_items:
            arxiv_id = cid.replace("arxiv:", "")
            print(f"  {cid}")
            print(
                f"    -> python -m polytool research-marker-queue "
                f"{queue_dir_arg}enqueue --url {arxiv_id} --force"
            )

    failed_details = report.get("failed_details", [])
    if failed_details:
        print(f"\nFailed items ({len(failed_details)} — all retries exhausted):")
        for item in failed_details:
            reason = (item.get("failure_reason") or "unknown")[:80]
            print(
                f"  {item.get('candidate_id', '?')}  "
                f"[{item.get('attempts', 0)} attempts]  {reason}"
            )
        print(
            "\nTip: run `prefetch` before `warm-process` to avoid arXiv rate-limit failures."
        )
        print(
            "     Then re-enqueue failed items with --force when ready to retry."
        )

    # Sidecar / indexed progress
    sidecar_count = report.get("sidecar_count", 0)
    indexed_count = report.get("indexed_count", 0)
    total_done = counts.get("done", 0)
    print(f"\nPipeline progress:")
    print(f"  done (warm-process):   {total_done}")
    print(f"  body sidecars written: {sidecar_count}  (of {total_done} done)")
    print(f"  indexed into KS:       {indexed_count}  (of {sidecar_count} sidecar(s))")

    # Timeout-risk classification for pending items
    timeout_risk_items = report.get("timeout_risk_items", [])
    if timeout_risk_items:
        tier3 = [i for i in timeout_risk_items if i.get("tier3_flag")]
        known_risk = [i for i in timeout_risk_items if i.get("is_known_timeout_risk")]
        print(f"\nPending timeout classification ({len(timeout_risk_items)} item(s)):")
        if tier3:
            print(f"  *** {len(tier3)} Tier-3 item(s) — operator approval required before full batch run ***")
        for item in timeout_risk_items:
            cid = item.get("candidate_id", "?")
            bucket = item.get("size_bucket", "unknown")
            kb = item.get("file_size_kb")
            kb_str = f"{kb} KB" if kb is not None else "size unknown"
            rec_t = item.get("recommended_timeout_seconds")
            rec_str = f"{rec_t:.0f}s" if rec_t is not None else "no prefetch data"
            risk_tag = " [KNOWN TIMEOUT RISK]" if item.get("is_known_timeout_risk") else ""
            tier3_tag = " [TIER-3]" if item.get("tier3_flag") else ""
            tier = item.get("ingest_tier", 2)
            print(
                f"  {cid}  {kb_str}  bucket={bucket}  "
                f"rec_timeout={rec_str}  tier={tier}{tier3_tag}{risk_tag}"
            )
        if known_risk:
            print(
                "\n  Note: KNOWN TIMEOUT RISK papers (1011.6402, 2307.14129, 2409.02025)"
                "\n  require --tier 3 and operator approval. Exclude from automated batches."
            )

    pending_ids = report.get("pending_ids", [])
    if pending_ids:
        non_risk_pending = [
            cid for cid in pending_ids
            if not any(i.get("candidate_id") == cid and i.get("tier3_flag") for i in timeout_risk_items)
        ]
        print(f"\nPending ({len(pending_ids)} total):")
        shown = pending_ids[:10]
        for cid in shown:
            print(f"  {cid}")
        if len(pending_ids) > 10:
            print(f"  ... and {len(pending_ids) - 10} more")

    return 0


def _cmd_counts(args: argparse.Namespace) -> int:
    from packages.research.ingestion.marker_queue import MarkerParseQueue

    queue_dir = Path(args.queue_dir) if args.queue_dir else None
    q = MarkerParseQueue(queue_dir=queue_dir)
    counts = q.get_counts()

    if args.json:
        print(json.dumps(counts, indent=2))
        return 0

    print("Marker Parse Queue — Item Counts")
    print(f"  pending:    {counts.get('pending', 0)}")
    print(f"  processing: {counts.get('processing', 0)}")
    print(f"  done:       {counts.get('done', 0)}")
    print(f"  failed:     {counts.get('failed', 0)}")
    print(f"  total:      {counts.get('total', 0)}")
    return 0


def _cmd_jit_cache_check(args: argparse.Namespace) -> int:
    """Print JIT cache persistence diagnostic instructions and current env state."""
    import os

    torchinductor_dir = os.environ.get("TORCHINDUCTOR_CACHE_DIR", "")
    triton_dir = os.environ.get("TRITON_CACHE_DIR", "")

    lines = [
        "JIT Cache Persistence Diagnostic",
        "=" * 50,
        "",
        "Background:",
        "  Marker uses Surya OCR which compiles TorchInductor/Triton kernels on first",
        "  use of a new 'format group' (distinct page layout / equation density class).",
        "  Cold-start compilation takes 27-50 min per format group. If the cache does",
        "  not persist across Docker restarts, every new container pays this cost again.",
        "",
        "  TORCHINDUCTOR_CACHE_DIR confirmed empty after batch runs (2026-05-23).",
        "  TRITON_CACHE_DIR is the suspected correct env var for Surya's kernel cache.",
        "",
        "Current environment:",
        f"  TORCHINDUCTOR_CACHE_DIR = {repr(torchinductor_dir) if torchinductor_dir else '(not set)'}",
        f"  TRITON_CACHE_DIR        = {repr(triton_dir) if triton_dir else '(not set)'}",
        "",
        "Diagnostic steps (run inside the Docker container):",
        "",
        "  Step 1 — Locate kernel cache before run:",
        "    find ~/.triton -name '*.cubin' -o -name '*.ptx' 2>/dev/null | head -20",
        "    find /tmp -name '*.cubin' 2>/dev/null | head -5",
        "",
        "  Step 2 — Create a timestamp marker BEFORE processing (required for Step 4):",
        "    touch /tmp/before_marker",
        "",
        "  Step 3 — Process one warm paper, note parse_seconds:",
        "    python -m polytool research-marker-queue warm-process --max-items 1",
        "",
        "  Step 4 — Record kernel cache location after run:",
        "    find ~/.triton -newer /tmp/before_marker -name '*.cubin' 2>/dev/null | head -20",
        "    ls -la ~/.triton/  # or /root/.triton/ in Docker",
        "",
        "  Step 5 — Restart Docker container (do NOT rm -v the volume):",
        "    docker restart <container_name>",
        "",
        "  Step 6 — Process the SAME paper (re-enqueue with --force), check parse_seconds:",
        "    If parse_seconds < 120s: cache IS persistent (cold-start paid once).",
        "    If parse_seconds >= 1800s: cache NOT persistent (JIT recompiles every run).",
        "",
        "  Step 7 — If cache is NOT persistent, mount a host volume for the cache dir:",
        "    docker run -v /host/triton_cache:/root/.triton <image>",
        "    Then set TRITON_CACHE_DIR=/root/.triton in the container environment.",
        "",
        "Known timeout-risk papers (do NOT include in automated batch until resolved):",
        "  arxiv:1011.6402  — confirmed timeout at 3600s (eq-heavy, large)",
        "  arxiv:2307.14129 — confirmed timeout at 2947s (eq-heavy)",
        "  arxiv:2409.02025 — HTTP 429 / fetch failures in multiple runs",
        "",
        "See docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md §JIT Cache Persistence for full runbook.",
    ]

    if args.json:
        print(json.dumps({
            "torchinductor_cache_dir": torchinductor_dir or None,
            "triton_cache_dir": triton_dir or None,
            "instructions": lines,
        }, indent=2))
    else:
        print("\n".join(lines))

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="polytool research-marker-queue",
        description=(
            "Marker Canonical Academic Parse Queue v0. "
            "Enqueue arXiv papers, process them with Marker, "
            "and track which papers are RAG-ready (marker_ready=true). "
            "On Windows, Marker models are pre-loaded once per batch (warm). "
            "On Linux/Docker, use warm-process for the validated IPC warm-worker path."
        ),
    )
    parser.add_argument(
        "--queue-dir",
        default=None,
        metavar="PATH",
        help="Override artifact queue directory (default: artifacts/research/marker_parse_queue)",
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # enqueue
    p_enqueue = subparsers.add_parser(
        "enqueue",
        help="Add one arXiv paper to the parse queue",
    )
    p_enqueue.add_argument(
        "--url",
        required=True,
        metavar="URL_OR_ID",
        help="arXiv URL or bare arXiv ID (e.g. 2604.24366)",
    )
    p_enqueue.add_argument(
        "--title",
        default="",
        metavar="TITLE",
        help="Optional title hint (fetcher resolves from API if omitted)",
    )
    p_enqueue.add_argument(
        "--pdf-url",
        default="",
        metavar="PDF_URL_OR_PATH",
        dest="pdf_url",
        help=(
            "Direct PDF URL or local file path. When set, warm-process skips the "
            "arXiv metadata API (no export.arxiv.org query) and fetches/reads the PDF "
            "directly. Useful when the Atom API is rate-limited. --url still determines "
            "candidate_id."
        ),
    )
    p_enqueue.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-enqueue even if the paper already exists (resets to pending)",
    )
    p_enqueue.add_argument(
        "--tier",
        type=int,
        default=2,
        choices=[2, 3],
        metavar="{2,3}",
        help=(
            "Ingest tier: 2 (default) = canonical Marker GPU parse; "
            "3 = extended-timeout Marker parse requiring operator approval. "
            "Tier 0/1 are not accepted (conflict with canonical RAG gate)."
        ),
    )
    p_enqueue.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output result as JSON",
    )

    # list
    p_list = subparsers.add_parser(
        "list",
        help="Show queue items",
    )
    p_list.add_argument(
        "--status",
        default="all",
        choices=["all", "pending", "processing", "done", "failed"],
        help="Filter by status (default: all)",
    )
    p_list.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON array",
    )

    # process
    p_process = subparsers.add_parser(
        "process",
        help=(
            "Process next N pending items using Marker. "
            "Warm batch on Windows (thread mode); cold per paper on Linux/Docker."
        ),
    )
    p_process.add_argument(
        "--max-items",
        type=int,
        default=1,
        dest="max_items",
        metavar="N",
        help="Maximum number of pending items to process (default: 1)",
    )
    p_process.add_argument(
        "--marker-timeout",
        type=float,
        default=900.0,
        dest="marker_timeout",
        metavar="SECONDS",
        help="Marker extraction subprocess timeout in seconds (default: 900)",
    )
    p_process.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON",
    )

    # warm-process
    p_warm = subparsers.add_parser(
        "warm-process",
        help=(
            "Process next N pending items using MarkerIPCWorker (warm IPC, Linux/Docker). "
            "On Windows, falls back to warm thread worker. "
            "L1 production path — IPC warm-worker validated 2026-05-08 (Feature 3 closed)."
        ),
    )
    p_warm.add_argument(
        "--max-items",
        type=int,
        default=1,
        dest="max_items",
        metavar="N",
        help="Maximum number of pending items to process (default: 1)",
    )
    p_warm.add_argument(
        "--marker-timeout",
        type=float,
        default=900.0,
        dest="marker_timeout",
        metavar="SECONDS",
        help=(
            "Marker extraction timeout in seconds (default: 900). "
            "Ignored when --auto-timeout is set."
        ),
    )
    p_warm.add_argument(
        "--auto-timeout",
        action="store_true",
        default=False,
        dest="auto_timeout",
        help=(
            "Compute timeout automatically from prefetch manifest PDF file sizes. "
            "Uses the maximum recommended timeout across all pending items: "
            "<=600KB->3600s, 601-1500KB->7200s, >1500KB->14400s. "
            "Requires prefetch to have run first (file sizes must be in manifest)."
        ),
    )
    p_warm.add_argument(
        "--allow-uncached",
        action="store_true",
        default=False,
        dest="allow_uncached",
        help=(
            "When --auto-timeout is set, allow pending items that lack cached prefetch "
            "manifest data to proceed using the conservative default timeout "
            f"({int(14400)}s). Default: fail with exit code 1 and list the uncached "
            "items so the operator can run 'prefetch' first."
        ),
    )
    p_warm.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output results as JSON",
    )

    # index-done
    p_index = subparsers.add_parser(
        "index-done",
        help=(
            "Index all marker-ready done items into the KnowledgeStore. "
            "Reads body from bodies/{candidate_id}.body.txt (written by warm-process). "
            "Idempotent: skips already-indexed items unless --force."
        ),
    )
    p_index.add_argument(
        "--ks-path",
        default=None,
        dest="ks_path",
        metavar="PATH",
        help="Override KnowledgeStore SQLite path (default: project default)",
    )
    p_index.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Re-index even items already recorded in indexed.jsonl",
    )
    p_index.add_argument(
        "--no-extract-claims",
        action="store_true",
        default=False,
        dest="no_extract_claims",
        help=(
            "Skip automatic claim extraction after indexing. "
            "Default: extract claims from each indexed paper via body_file sidecar."
        ),
    )
    p_index.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output summary as JSON",
    )

    # counts
    p_counts = subparsers.add_parser(
        "counts",
        help="Show item counts by status",
    )
    p_counts.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output counts as JSON",
    )

    # prefetch
    p_prefetch = subparsers.add_parser(
        "prefetch",
        help=(
            "Pre-download PDFs for pending queue items to a local cache. "
            "Run this BEFORE warm-process to separate arXiv PDF fetching from "
            "GPU Marker parsing. Warm-process then reads local files and makes "
            "no arXiv network calls during the parse phase. "
            "Idempotent: already-cached PDFs are skipped."
        ),
    )
    p_prefetch.add_argument(
        "--max-items",
        type=int,
        default=None,
        dest="max_items",
        metavar="N",
        help="Max pending items to prefetch (default: all pending)",
    )
    p_prefetch.add_argument(
        "--delay-seconds",
        type=float,
        default=10.0,
        dest="delay_seconds",
        metavar="SECONDS",
        help=(
            "Seconds to sleep between successive PDF downloads (default: 10.0). "
            "Keep >= 5s to avoid arXiv rate limits under sustained load."
        ),
    )
    p_prefetch.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output result as JSON",
    )

    # status-report
    p_status = subparsers.add_parser(
        "status-report",
        help=(
            "Print a structured status report: counts, stuck items (processing "
            "with no active worker), failed-item failure reasons, and prefetch "
            "cache stats."
        ),
    )
    p_status.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output report as JSON",
    )

    # jit-cache-check
    p_jit = subparsers.add_parser(
        "jit-cache-check",
        help=(
            "Print JIT cache persistence diagnostic instructions and current env state. "
            "Guides operator through TRITON_CACHE_DIR investigation to determine whether "
            "TorchInductor/Triton kernel cache persists across Docker restarts."
        ),
    )
    p_jit.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output diagnostic data as JSON",
    )

    return parser


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main(argv: Optional[list] = None) -> int:
    """CLI entrypoint. Returns int exit code."""
    if argv is None:
        argv = sys.argv[1:]

    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.subcommand is None:
        parser.print_help()
        return 1

    if args.subcommand == "enqueue":
        return _cmd_enqueue(args)
    elif args.subcommand == "list":
        return _cmd_list(args)
    elif args.subcommand == "process":
        return _cmd_process(args)
    elif args.subcommand == "warm-process":
        return _cmd_warm_process(args)
    elif args.subcommand == "index-done":
        return _cmd_index_done(args)
    elif args.subcommand == "counts":
        return _cmd_counts(args)
    elif args.subcommand == "prefetch":
        return _cmd_prefetch(args)
    elif args.subcommand == "status-report":
        return _cmd_status_report(args)
    elif args.subcommand == "jit-cache-check":
        return _cmd_jit_cache_check(args)
    else:
        print(f"Unknown subcommand: {args.subcommand}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
