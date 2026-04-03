"""RIS dossier extraction pipeline.

Parses existing wallet-scan dossier artifacts (dossier.json, memo.md,
hypothesis_candidates.json, segment_analysis.json) into structured research
findings for ingestion into the KnowledgeStore as source_family="dossier_report".

Public API:
    _parse_dossier_json(path) -> dict
    _parse_memo(path) -> str
    _parse_hypothesis_candidates(path) -> list[dict]
    extract_dossier_findings(dossier_dir) -> list[dict]
    batch_extract_dossiers(base_dir) -> list[dict]
    ingest_dossier_findings(findings, store, post_extract_claims=False) -> list[IngestResult]
    DossierAdapter   — re-exported from packages.research.ingestion.adapters

Dossier directory layout:
    {base}/users/{user_slug}/{wallet}/{date}/{run_id}/
    Each run directory contains:
    - dossier.json: header, detectors, pnl_summary, etc.
    - memo.md: LLM research packet (may contain TODO placeholders)
    - hypothesis_candidates.json: ranked hypothesis candidates with metrics
    - segment_analysis.json: segment breakdown (optional)
    - run_manifest.json: run metadata (optional)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

from packages.research.ingestion.adapters import DossierAdapter

if TYPE_CHECKING:
    from packages.polymarket.rag.knowledge_store import KnowledgeStore


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------


def _parse_dossier_json(path: "str | Path") -> dict:
    """Load and parse dossier.json into a normalized dict.

    Extracts:
    - header fields: export_id, proxy_wallet, user_input, generated_at,
      window_days, window_start, window_end
    - detectors.latest -> detector_labels {detector: label}
    - pnl_summary -> pricing_confidence, pnl_trend_30d

    Parameters
    ----------
    path:
        Path to dossier.json.

    Returns
    -------
    dict with normalized fields.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"dossier.json not found: {path}")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    header = raw.get("header", {})
    result = {
        "export_id": header.get("export_id", ""),
        "generated_at": header.get("generated_at", ""),
        "max_trades": header.get("max_trades", 0),
        "proxy_wallet": header.get("proxy_wallet", ""),
        "user_input": header.get("user_input", ""),
        "window_days": header.get("window_days", 0),
        "window_start": header.get("window_start", ""),
        "window_end": header.get("window_end", ""),
    }

    # Extract detector labels from detectors.latest
    detector_labels: dict[str, str] = {}
    detectors = raw.get("detectors", {})
    for entry in detectors.get("latest", []):
        det_name = entry.get("detector", "")
        det_label = entry.get("label", "")
        if det_name:
            # Keep the highest-scored label per detector (latest list may have multiple buckets)
            if det_name not in detector_labels:
                detector_labels[det_name] = det_label
    result["detector_labels"] = detector_labels

    # Extract pnl_summary
    pnl = raw.get("pnl_summary", {})
    result["pricing_confidence"] = pnl.get("pricing_confidence", "")
    result["pricing_snapshot_ratio"] = pnl.get("pricing_snapshot_ratio", None)
    result["pnl_trend_30d"] = pnl.get("trend_30d", "")
    result["pnl_latest_bucket"] = pnl.get("latest_bucket", "")

    return result


def _parse_memo(path: "str | Path") -> str:
    """Read memo.md and return usable body text with TODOs stripped.

    Sections that are entirely TODO placeholders are removed.
    If the resulting text is essentially empty (< 50 characters of real
    content), returns an empty string.

    Parameters
    ----------
    path:
        Path to memo.md.

    Returns
    -------
    str — cleaned body text, or "" if file missing or all-TODO.
    """
    path = Path(path)
    if not path.exists():
        return ""

    content = path.read_text(encoding="utf-8")

    # Strip lines that are TODO markers (pure or with trailing text)
    lines = content.splitlines()
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip bullet/list items that start with TODO (with or without trailing text)
        # Matches: "- TODO", "- TODO: some text", "* TODO: ..."
        if re.match(r"^[-*]\s*TODO\b", stripped, re.IGNORECASE):
            continue
        # Skip table rows where ANY cell is TODO (e.g., "| TODO | TODO |")
        if re.match(r"^\|", stripped) and re.search(r"\|\s*TODO\s*\|", stripped, re.IGNORECASE):
            continue
        # Skip standalone TODO lines
        if re.match(r"^TODO\b", stripped, re.IGNORECASE):
            continue
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()

    # Check if remaining content is substantive (more than header/metadata boilerplate)
    # Remove header metadata lines (User input:, Proxy wallet:, Generated at:, etc.)
    boilerplate_pattern = re.compile(
        r"^(#\s+LLM Research Packet.*|User input:.*|Proxy wallet:.*|Window:.*|"
        r"Generated at:.*|Export id:.*|##\s+.*|---\s*)$",
        re.IGNORECASE | re.MULTILINE,
    )
    content_only = boilerplate_pattern.sub("", cleaned).strip()

    if len(content_only) < 50:
        return ""

    return cleaned


def _parse_hypothesis_candidates(path: "str | Path") -> list[dict]:
    """Load hypothesis_candidates.json and extract top candidate summaries.

    Parameters
    ----------
    path:
        Path to hypothesis_candidates.json.

    Returns
    -------
    list of candidate summary dicts with keys:
        segment_key, clv_variant_used, rank, avg_clv_pct, beat_close_rate,
        count, win_rate, median_clv_pct
    Empty list if file missing or malformed.
    """
    path = Path(path)
    if not path.exists():
        return []

    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    candidates = raw.get("candidates", [])
    results = []
    for cand in candidates:
        metrics = cand.get("metrics", {})
        summary = {
            "segment_key": cand.get("segment_key", ""),
            "clv_variant_used": cand.get("clv_variant_used", ""),
            "rank": cand.get("rank", 0),
            "avg_clv_pct": metrics.get("avg_clv_pct"),
            "beat_close_rate": metrics.get("beat_close_rate"),
            "count": metrics.get("count"),
            "win_rate": metrics.get("win_rate"),
            "median_clv_pct": metrics.get("median_clv_pct"),
            "notional_weighted_avg_clv_pct": metrics.get("notional_weighted_avg_clv_pct"),
            "notional_weighted_beat_close_rate": metrics.get("notional_weighted_beat_close_rate"),
        }
        results.append(summary)
    return results


def _infer_user_slug(dossier_dir: Path, parsed_dossier: dict) -> str:
    """Infer user slug from dossier header or directory structure.

    Priority: user_input from header -> grandparent dir name (slug from path).
    """
    user_input = parsed_dossier.get("user_input", "")
    if user_input:
        # Strip @ prefix
        slug = user_input.lstrip("@").strip()
        if slug:
            return slug

    # Fall back to path: .../users/{user_slug}/{wallet}/{date}/{run_id}/
    parts = dossier_dir.parts
    # Find "users" in path and take the next component
    try:
        users_idx = [p.lower() for p in parts].index("users")
        if users_idx + 1 < len(parts):
            return parts[users_idx + 1]
    except ValueError:
        pass

    # Last fallback: grandparent directory name
    return dossier_dir.parent.parent.name


def _infer_run_id(dossier_dir: Path) -> str:
    """Infer run_id from the directory name (last path component)."""
    return dossier_dir.name


def _build_finding_documents(
    dossier_dir: Path,
    parsed_dossier: dict,
    parsed_memo: str,
    parsed_candidates: list[dict],
) -> list[dict]:
    """Combine parsed outputs into finding dicts ready for IngestPipeline.

    Produces 1-3 documents per dossier run:
    1. "Dossier Detectors: {user_slug}" — strategy classification + detector labels
    2. "Dossier Hypothesis Candidates: {user_slug}" — if candidates exist
    3. "Dossier Memo: {user_slug}" — if memo has non-TODO content

    Each document dict has:
        title, body, source_url (file:// URI), source_family ("dossier_report"),
        author (user_slug), publish_date, metadata (wallet, run_id, dossier_path,
        detector_labels, provenance).
    """
    user_slug = _infer_user_slug(dossier_dir, parsed_dossier)
    run_id = _infer_run_id(dossier_dir)
    wallet = parsed_dossier.get("proxy_wallet", "")
    generated_at = parsed_dossier.get("generated_at", "")
    # Build publish_date as a date string (YYYY-MM-DD) from generated_at ISO timestamp
    publish_date = generated_at[:10] if generated_at else None

    # Convert to file:// URI (forward slashes for cross-platform compat)
    dossier_path_str = str(dossier_dir).replace("\\", "/")
    source_url = f"file://{dossier_path_str}"

    base_metadata = {
        "wallet": wallet,
        "run_id": run_id,
        "dossier_path": dossier_path_str,
        "user_slug": user_slug,
        "export_id": parsed_dossier.get("export_id", ""),
        "window_days": parsed_dossier.get("window_days", 0),
        "generated_at": generated_at,
        "detector_labels": parsed_dossier.get("detector_labels", {}),
    }

    documents = []

    # --- Document 1: Detector classification ---
    detector_labels = parsed_dossier.get("detector_labels", {})
    detector_lines = []
    for det_name, det_label in detector_labels.items():
        detector_lines.append(f"  {det_name}: {det_label}")

    pricing_conf = parsed_dossier.get("pricing_confidence", "")
    pnl_trend = parsed_dossier.get("pnl_trend_30d", "")

    detector_body_parts = [
        f"Wallet Analysis — Strategy Detectors for {user_slug}",
        f"Wallet: {wallet}",
        f"Analysis window: {parsed_dossier.get('window_days', 0)} days",
        f"Generated: {generated_at}",
        "",
        "Strategy detector labels:",
    ]
    detector_body_parts.extend(detector_lines or ["  (no detector data)"])
    if pricing_conf:
        detector_body_parts.append(f"\nPricing confidence: {pricing_conf}")
    if pnl_trend:
        detector_body_parts.append(f"PnL trend (30d): {pnl_trend}")

    detector_meta = dict(base_metadata)
    detector_meta["document_type"] = "dossier_detectors"

    documents.append({
        "title": f"Dossier Detectors: {user_slug}",
        "body": "\n".join(detector_body_parts),
        "source_url": source_url,
        "source_family": "dossier_report",
        "author": user_slug,
        "publish_date": publish_date,
        "metadata": detector_meta,
    })

    # --- Document 2: Hypothesis candidates (only if candidates exist) ---
    if parsed_candidates:
        cand_lines = [
            f"Wallet Analysis — Hypothesis Candidates for {user_slug}",
            f"Wallet: {wallet}",
            f"Generated: {generated_at}",
            "",
            "Top hypothesis candidates by CLV:",
        ]
        for cand in parsed_candidates[:5]:  # Top 5
            cand_lines.append(
                f"  [{cand.get('rank', '?')}] {cand.get('segment_key', 'unknown')} "
                f"(clv_variant={cand.get('clv_variant_used', 'unknown')}): "
                f"avg_clv={cand.get('avg_clv_pct', 'N/A')}%, "
                f"beat_close={cand.get('beat_close_rate', 'N/A')}, "
                f"count={cand.get('count', 'N/A')}"
            )

        cand_meta = dict(base_metadata)
        cand_meta["document_type"] = "dossier_hypothesis_candidates"
        cand_meta["candidate_count"] = len(parsed_candidates)

        documents.append({
            "title": f"Dossier Hypothesis Candidates: {user_slug}",
            "body": "\n".join(cand_lines),
            "source_url": source_url,
            "source_family": "dossier_report",
            "author": user_slug,
            "publish_date": publish_date,
            "metadata": cand_meta,
        })

    # --- Document 3: Memo (only if has non-TODO content) ---
    if parsed_memo:
        memo_meta = dict(base_metadata)
        memo_meta["document_type"] = "dossier_memo"

        documents.append({
            "title": f"Dossier Memo: {user_slug}",
            "body": parsed_memo,
            "source_url": source_url,
            "source_family": "dossier_report",
            "author": user_slug,
            "publish_date": publish_date,
            "metadata": memo_meta,
        })

    return documents


def extract_dossier_findings(dossier_dir: "str | Path") -> list[dict]:
    """Extract structured findings from a single dossier run directory.

    Reads all known dossier files from *dossier_dir* and combines them into
    a list of document dicts ready for IngestPipeline ingestion.

    Parameters
    ----------
    dossier_dir:
        Path to a run directory containing dossier.json (and optionally
        memo.md, hypothesis_candidates.json, segment_analysis.json).

    Returns
    -------
    list[dict] — one dict per document (1-3 per run).
    Each dict has: title, body, source_url, source_family, author,
    publish_date, metadata.
    """
    dossier_dir = Path(dossier_dir)

    # Parse dossier.json (required)
    parsed_dossier = _parse_dossier_json(dossier_dir / "dossier.json")

    # Parse optional files gracefully
    parsed_memo = _parse_memo(dossier_dir / "memo.md")
    parsed_candidates = _parse_hypothesis_candidates(
        dossier_dir / "hypothesis_candidates.json"
    )

    return _build_finding_documents(
        dossier_dir, parsed_dossier, parsed_memo, parsed_candidates
    )


def batch_extract_dossiers(base_dir: "str | Path") -> list[dict]:
    """Walk a dossier base directory and extract findings from all runs.

    Expected layout:
        {base_dir}/users/{user_slug}/{wallet}/{date}/{run_id}/dossier.json

    Any run directory containing dossier.json is processed. Directories
    without dossier.json are silently skipped.

    Parameters
    ----------
    base_dir:
        Root directory to walk. Typically ``artifacts/dossiers/users/``
        or any parent of that.

    Returns
    -------
    list[dict] — flat list of all finding dicts across all dossier runs.
    """
    base_dir = Path(base_dir)
    all_findings: list[dict] = []

    for dossier_path in base_dir.rglob("dossier.json"):
        run_dir = dossier_path.parent
        try:
            findings = extract_dossier_findings(run_dir)
            all_findings.extend(findings)
        except Exception:
            # Non-fatal: skip corrupt or unreadable dossiers
            pass

    return all_findings


# DossierAdapter is defined in packages.research.ingestion.adapters and
# registered as ADAPTER_REGISTRY["dossier"].  It is re-exported here for
# convenience so callers can do:
#   from packages.research.integration.dossier_extractor import DossierAdapter
# See adapters.py for the full implementation.

# ---------------------------------------------------------------------------
# ingest_dossier_findings
# ---------------------------------------------------------------------------


def ingest_dossier_findings(
    findings: list[dict],
    store: "KnowledgeStore",
    post_extract_claims: bool = False,
) -> list:
    """Ingest a list of finding dicts into the KnowledgeStore.

    Uses IngestPipeline with no eval gate (dossier reports are trusted
    internal content and always pass quality gates).  Content-hash dedup
    prevents duplicate ingestion of the same dossier run.

    Parameters
    ----------
    findings:
        List of finding dicts from extract_dossier_findings / batch_extract_dossiers.
    store:
        KnowledgeStore instance (may be in-memory for tests).
    post_extract_claims:
        If True, run claim extraction after each ingestion (non-fatal).

    Returns
    -------
    list[IngestResult] — one result per finding dict.
    """
    from packages.research.ingestion.pipeline import IngestPipeline

    adapter = DossierAdapter()
    pipeline = IngestPipeline(store=store)
    results = []

    for finding in findings:
        # Adapt finding dict -> ExtractedDocument with content_hash
        doc = adapter.adapt(finding)

        # Check for duplicate via content_hash before calling pipeline
        content_hash = doc.metadata.get("content_hash", "")
        if content_hash:
            existing = store._conn.execute(
                "SELECT id FROM source_documents WHERE content_hash=?",
                (content_hash,),
            ).fetchone()
            if existing:
                # Already ingested — return a synthetic "already exists" result
                from packages.research.ingestion.pipeline import IngestResult
                results.append(IngestResult(
                    doc_id=existing[0],
                    chunk_count=0,
                    gate_decision=None,
                    rejected=False,
                    reject_reason=None,
                ))
                continue

        # Ingest via pipeline using body text + metadata kwargs
        result = pipeline.ingest(
            doc.body,
            source_type="dossier",
            title=doc.title,
            author=doc.author,
            publish_date=doc.publish_date,
            source_family="dossier_report",
            source_url=doc.source_url,
            content_hash=doc.metadata.get("content_hash"),
            post_ingest_extract=post_extract_claims,
        )
        results.append(result)

    return results
