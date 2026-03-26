"""Tests for tools/gates/corpus_audit.py (TDD RED -> GREEN).

Six tests covering admission rules, quota caps, shortage detection, and
manifest writing as specified in SPEC-phase1b-corpus-recovery-v1.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_tape_dir(
    tmp_path: Path,
    *,
    slug: str,
    effective_events: int = 60,
    bucket: str | None = "sports",
    tier: str = "silver",
    yes_asset_id: str = "1234567890",
) -> Path:
    """Create a minimal tape directory with events.jsonl and appropriate metadata."""
    tape_dir = tmp_path / slug
    tape_dir.mkdir(parents=True, exist_ok=True)

    # Write events.jsonl with enough events
    events_path = tape_dir / "events.jsonl"
    lines = []
    for i in range(effective_events):
        lines.append(json.dumps({"asset_id": yes_asset_id, "type": "price_change", "seq": i}))
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Write metadata based on tier
    if tier == "gold":
        watch_meta = {
            "market_slug": slug,
            "bucket": bucket,
            "yes_asset_id": yes_asset_id,
        }
        (tape_dir / "watch_meta.json").write_text(
            json.dumps(watch_meta), encoding="utf-8"
        )
        meta = {"recorded_by": "shadow", "asset_ids": [yes_asset_id]}
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    elif tier == "silver":
        silver_meta = {"token_id": yes_asset_id}
        (tape_dir / "silver_meta.json").write_text(
            json.dumps(silver_meta), encoding="utf-8"
        )
        if bucket is not None:
            market_meta = {
                "slug": slug,
                "category": bucket,
                "benchmark_bucket": bucket,
                "platform": "silver",
                "token_id": yes_asset_id,
            }
            (tape_dir / "market_meta.json").write_text(
                json.dumps(market_meta), encoding="utf-8"
            )

    return tape_dir


def _run_audit(
    tmp_path: Path,
    tape_dirs: list[Path],
    *,
    min_events: int = 50,
    manifest_out: Path | None = None,
    out_dir: Path | None = None,
) -> tuple[int, Path]:
    """
    Run corpus_audit.run_corpus_audit() with the given tape dirs.

    Returns (exit_code, out_dir).
    """
    from tools.gates.corpus_audit import run_corpus_audit

    if out_dir is None:
        out_dir = tmp_path / "corpus_audit_out"
    if manifest_out is None:
        manifest_out = tmp_path / "recovery_corpus_v1.tape_manifest"

    exit_code = run_corpus_audit(
        tape_roots=tape_dirs,
        out_dir=out_dir,
        min_events=min_events,
        manifest_out=manifest_out,
    )
    return exit_code, out_dir


# ---------------------------------------------------------------------------
# Test 1: qualified tape with enough events and valid bucket is ACCEPTED
# ---------------------------------------------------------------------------


def test_qualified_tape_accepted(tmp_path: Path) -> None:
    """A tape with effective_events >= 50 and valid bucket is ACCEPTED in audit results."""
    from tools.gates.corpus_audit import audit_tape_candidates

    tape_dir = _make_tape_dir(
        tmp_path,
        slug="accepted-sports-market",
        effective_events=60,
        bucket="sports",
        tier="silver",
    )

    results = audit_tape_candidates(
        tape_dirs=[tape_dir],
        min_events=50,
    )

    # Should have exactly one result
    assert len(results) == 1
    result = results[0]
    assert result["tape_dir"] == str(tape_dir)
    assert result["status"] == "ACCEPTED"
    assert result["effective_events"] >= 50
    assert result["bucket"] == "sports"
    assert result.get("reject_reason") is None


# ---------------------------------------------------------------------------
# Test 2: tape with effective_events < min_events is REJECTED with "too_short"
# ---------------------------------------------------------------------------


def test_too_short_tape_rejected(tmp_path: Path) -> None:
    """A tape with effective_events < 50 is REJECTED with reason 'too_short'."""
    from tools.gates.corpus_audit import audit_tape_candidates

    tape_dir = _make_tape_dir(
        tmp_path,
        slug="short-market",
        effective_events=20,
        bucket="crypto",
        tier="silver",
    )

    results = audit_tape_candidates(
        tape_dirs=[tape_dir],
        min_events=50,
    )

    assert len(results) == 1
    result = results[0]
    assert result["status"] == "REJECTED"
    assert result["reject_reason"] == "too_short"
    assert result["effective_events"] < 50


# ---------------------------------------------------------------------------
# Test 3: tape with no bucket label is REJECTED with "no_bucket_label"
# ---------------------------------------------------------------------------


def test_no_bucket_label_rejected(tmp_path: Path) -> None:
    """A tape with no bucket metadata is REJECTED with reason 'no_bucket_label'."""
    from tools.gates.corpus_audit import audit_tape_candidates

    # Create a tape dir with events but no metadata that yields a bucket
    tape_dir = tmp_path / "no-bucket-market"
    tape_dir.mkdir(parents=True, exist_ok=True)
    events_path = tape_dir / "events.jsonl"
    lines = [
        json.dumps({"asset_id": "9999", "type": "price_change", "seq": i})
        for i in range(60)
    ]
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Write silver_meta but NO market_meta (no bucket label)
    (tape_dir / "silver_meta.json").write_text(
        json.dumps({"token_id": "9999"}), encoding="utf-8"
    )

    results = audit_tape_candidates(
        tape_dirs=[tape_dir],
        min_events=50,
    )

    assert len(results) == 1
    result = results[0]
    assert result["status"] == "REJECTED"
    assert result["reject_reason"] == "no_bucket_label"


# ---------------------------------------------------------------------------
# Test 4: quota cap per bucket — excess tapes REJECTED with "over_quota"
# ---------------------------------------------------------------------------


def test_quota_cap_per_bucket(tmp_path: Path) -> None:
    """More tapes than the per-bucket quota causes excess tapes REJECTED with 'over_quota'."""
    from tools.gates.corpus_audit import audit_tape_candidates

    # sports quota is 15; create 17 sports tapes all qualifying
    tape_dirs = []
    for i in range(17):
        td = _make_tape_dir(
            tmp_path,
            slug=f"sports-market-{i:02d}",
            effective_events=60 + i,
            bucket="sports",
            tier="silver",
        )
        tape_dirs.append(td)

    results = audit_tape_candidates(
        tape_dirs=tape_dirs,
        min_events=50,
    )

    accepted = [r for r in results if r["status"] == "ACCEPTED"]
    over_quota = [r for r in results if r.get("reject_reason") == "over_quota"]

    # Exactly 15 sports tapes accepted, 2 rejected as over_quota
    assert len(accepted) == 15
    assert len(over_quota) == 2
    assert all(r["bucket"] == "sports" for r in over_quota)


# ---------------------------------------------------------------------------
# Test 5: shortage when corpus has fewer than 50 qualified tapes
# ---------------------------------------------------------------------------


def test_shortage_when_below_50(tmp_path: Path) -> None:
    """With only 5 qualified tapes, audit exits 1, shortage_report.md is written, manifest NOT written."""
    from tools.gates.corpus_audit import run_corpus_audit

    # Create 5 tapes from different buckets (not enough for 50-tape total)
    tape_dirs = []
    for bucket in ["sports", "crypto", "politics", "near_resolution", "new_market"]:
        td = _make_tape_dir(
            tmp_path,
            slug=f"tape-{bucket}",
            effective_events=60,
            bucket=bucket,
            tier="silver",
        )
        tape_dirs.append(td)

    out_dir = tmp_path / "audit_out"
    manifest_out = tmp_path / "recovery_corpus_v1.tape_manifest"

    exit_code = run_corpus_audit(
        tape_roots=tape_dirs,
        out_dir=out_dir,
        min_events=50,
        manifest_out=manifest_out,
    )

    # Must exit 1 (shortage)
    assert exit_code == 1

    # Shortage report must exist
    shortage_report = out_dir / "shortage_report.md"
    assert shortage_report.exists(), "shortage_report.md must be written on insufficient corpus"

    # Manifest must NOT be written
    assert not manifest_out.exists(), (
        "recovery_corpus_v1.tape_manifest must NOT be written when corpus is insufficient"
    )


# ---------------------------------------------------------------------------
# Test 6: manifest written when corpus has >= 50 tapes across all 5 buckets
# ---------------------------------------------------------------------------


def test_qualified_manifest_written_when_sufficient(tmp_path: Path) -> None:
    """With 50+ tapes across all 5 buckets, manifest is written and audit exits 0."""
    from tools.gates.corpus_audit import run_corpus_audit

    # Bucket quotas: politics=10, sports=15, crypto=10, near_resolution=10, new_market=5
    bucket_counts = {
        "politics": 10,
        "sports": 15,
        "crypto": 10,
        "near_resolution": 10,
        "new_market": 5,
    }

    tape_dirs = []
    for bucket, count in bucket_counts.items():
        for i in range(count):
            td = _make_tape_dir(
                tmp_path,
                slug=f"tape-{bucket}-{i:02d}",
                effective_events=60,
                bucket=bucket,
                tier="silver",
                yes_asset_id=f"{hash(bucket + str(i)) % 10000000000:010d}",
            )
            tape_dirs.append(td)

    out_dir = tmp_path / "audit_out"
    manifest_out = tmp_path / "recovery_corpus_v1.tape_manifest"

    exit_code = run_corpus_audit(
        tape_roots=tape_dirs,
        out_dir=out_dir,
        min_events=50,
        manifest_out=manifest_out,
    )

    # Must exit 0 (qualified)
    assert exit_code == 0

    # Manifest must exist and contain exactly 50 entries
    assert manifest_out.exists(), "recovery_corpus_v1.tape_manifest must be written"
    manifest_data = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert isinstance(manifest_data, list)
    assert len(manifest_data) == 50

    # Audit report must also exist
    audit_report = out_dir / "recovery_corpus_audit.md"
    assert audit_report.exists(), "recovery_corpus_audit.md must be written on success"

    # Shortage report must NOT exist (or must not be present)
    shortage_report = out_dir / "shortage_report.md"
    assert not shortage_report.exists(), (
        "shortage_report.md must NOT be written when corpus qualifies"
    )
