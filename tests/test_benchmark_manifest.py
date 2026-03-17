from __future__ import annotations

import json
from pathlib import Path

from packages.polymarket.benchmark_manifest_contract import (
    BenchmarkManifestValidationError,
    validate_benchmark_manifest,
)
from tools.cli.benchmark_manifest import (
    BUCKET_ORDER,
    QUOTAS,
    TapeCandidate,
    discover_inventory,
    main,
    select_manifest,
)


def _book_event(asset_id: str, price: float) -> dict:
    bid = max(price - 0.01, 0.001)
    ask = min(price + 0.01, 0.999)
    return {
        "event_type": "book",
        "asset_id": asset_id,
        "bids": [{"price": f"{bid:.3f}", "size": "100"}],
        "asks": [{"price": f"{ask:.3f}", "size": "100"}],
        "last_trade_price": f"{price:.3f}",
    }


def _write_gold_tape(
    root: Path,
    name: str,
    *,
    category: str,
    yes_prices: list[float],
    age_hours: float | None = None,
    hours_to_resolution: float | None = None,
) -> Path:
    tape_dir = root / name
    tape_dir.mkdir(parents=True, exist_ok=True)
    yes_id = f"yes-{name}"
    no_id = f"no-{name}"
    meta = {
        "market_slug": name,
        "category": category,
        "title": name,
        "question": name,
        "yes_asset_id": yes_id,
        "no_asset_id": no_id,
    }
    if age_hours is not None:
        meta["age_hours"] = age_hours
    if hours_to_resolution is not None:
        meta["hours_to_resolution"] = hours_to_resolution
    (tape_dir / "watch_meta.json").write_text(json.dumps(meta), encoding="utf-8")

    events = []
    for price in yes_prices:
        events.append(_book_event(yes_id, price))
        events.append(_book_event(no_id, max(min(1.0 - price, 0.999), 0.001)))

    with (tape_dir / "events.jsonl").open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    return tape_dir / "events.jsonl"


def _write_silver_tape(
    root: Path,
    name: str,
    *,
    category: str,
    prices: list[float],
) -> Path:
    tape_dir = root / name
    tape_dir.mkdir(parents=True, exist_ok=True)
    token_id = f"token-{name}"
    watch_meta = {
        "market_slug": name,
        "category": category,
        "title": name,
        "question": name,
        "token_id": token_id,
    }
    (tape_dir / "watch_meta.json").write_text(json.dumps(watch_meta), encoding="utf-8")
    silver_meta = {
        "schema_version": "silver_tape_v0",
        "run_id": f"run-{name}",
        "token_id": token_id,
        "window_start": "2026-03-01T00:00:00+00:00",
        "window_end": "2026-03-01T01:00:00+00:00",
        "generated_at": "2026-03-01T01:00:00+00:00",
        "event_count": len(prices),
    }
    (tape_dir / "silver_meta.json").write_text(json.dumps(silver_meta), encoding="utf-8")
    with (tape_dir / "silver_events.jsonl").open("w", encoding="utf-8") as handle:
        for seq, price in enumerate(prices):
            handle.write(
                json.dumps(
                    {
                        "event_type": "last_trade_price",
                        "seq": seq,
                        "asset_id": token_id,
                        "price": f"{price:.3f}",
                    }
                )
                + "\n"
            )
    return tape_dir / "silver_events.jsonl"


def _zero_quotas(**overrides: int) -> dict[str, int]:
    quotas = {bucket: 0 for bucket in BUCKET_ORDER}
    quotas.update(overrides)
    return quotas


def _populate_full_inventory(root: Path) -> None:
    for idx in range(10):
        _write_gold_tape(
            root,
            f"politics-{idx}",
            category="Politics",
            yes_prices=[0.20, 0.75],
        )
    for idx in range(15):
        _write_gold_tape(
            root,
            f"sports-{idx}",
            category="Sports",
            yes_prices=[0.40, 0.46],
        )
    for idx in range(10):
        _write_silver_tape(
            root,
            f"crypto-{idx}",
            category="Crypto",
            prices=[0.35, 0.58],
        )
    for idx in range(10):
        _write_gold_tape(
            root,
            f"resolution-{idx}",
            category="Science",
            yes_prices=[0.52, 0.55],
            hours_to_resolution=6.0,
        )
    for idx in range(5):
        _write_gold_tape(
            root,
            f"fresh-{idx}",
            category="Science",
            yes_prices=[0.48, 0.50],
            age_hours=12.0,
        )


def _build_valid_manifest(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "inventory"
    _populate_full_inventory(root)

    manifest_out = tmp_path / "config" / "benchmark_v1.tape_manifest"
    audit_out = tmp_path / "config" / "benchmark_v1.audit.json"
    gap_out = tmp_path / "config" / "benchmark_v1.gap_report.json"
    lock_out = tmp_path / "config" / "benchmark_v1.lock.json"

    exit_code = main(
        [
            "--root",
            str(root),
            "--manifest-out",
            str(manifest_out),
            "--audit-out",
            str(audit_out),
            "--gap-out",
            str(gap_out),
            "--lock-out",
            str(lock_out),
        ]
    )

    assert exit_code == 0
    assert manifest_out.exists()
    assert audit_out.exists()
    assert not gap_out.exists()
    assert lock_out.exists()
    return manifest_out, audit_out, gap_out, lock_out


def _manifest_entry_to_path(entry: str, manifest_out: Path) -> Path:
    path = Path(entry)
    if path.is_absolute():
        return path
    del manifest_out
    return Path(__file__).resolve().parents[1] / path


def test_gap_report_written_when_inventory_is_short(tmp_path: Path) -> None:
    root = tmp_path / "inventory"
    _write_gold_tape(root, "sports-1", category="Sports", yes_prices=[0.41, 0.44])

    manifest_out = tmp_path / "config" / "benchmark_v1.tape_manifest"
    gap_out = tmp_path / "config" / "benchmark_v1.gap_report.json"

    exit_code = main(
        [
            "--root",
            str(root),
            "--manifest-out",
            str(manifest_out),
            "--gap-out",
            str(gap_out),
        ]
    )

    assert exit_code == 2
    assert not manifest_out.exists()
    assert gap_out.exists()

    gap = json.loads(gap_out.read_text(encoding="utf-8"))
    assert gap["shortages_by_bucket"]["sports"] == QUOTAS["sports"] - 1
    assert gap["shortages_by_bucket"]["politics"] == QUOTAS["politics"]
    assert gap["selected_total"] == 1


def test_overlap_assignment_uses_unique_tapes_to_fill_sparse_bucket() -> None:
    overlapping = TapeCandidate(
        tape_path="A",
        tape_dir="A",
        tier="gold",
        slug="A",
        candidate_buckets=["sports", "new_market"],
    )
    sports_only = TapeCandidate(
        tape_path="B",
        tape_dir="B",
        tier="silver",
        slug="B",
        candidate_buckets=["sports"],
    )

    selection = select_manifest(
        [overlapping, sports_only],
        quotas=_zero_quotas(sports=1, new_market=1),
    )

    assert selection.success is True
    assert [candidate.tape_path for candidate in selection.assignments["sports"]] == ["B"]
    assert [candidate.tape_path for candidate in selection.assignments["new_market"]] == ["A"]


def test_gold_candidate_is_preferred_to_silver_for_same_bucket() -> None:
    gold = TapeCandidate(
        tape_path="gold",
        tape_dir="gold",
        tier="gold",
        slug="gold",
        event_count=10,
        candidate_buckets=["sports"],
    )
    silver = TapeCandidate(
        tape_path="silver",
        tape_dir="silver",
        tier="silver",
        slug="silver",
        event_count=10,
        candidate_buckets=["sports"],
    )

    selection = select_manifest([gold, silver], quotas=_zero_quotas(sports=1))

    assert selection.success is True
    assert [candidate.tape_path for candidate in selection.assignments["sports"]] == ["gold"]


def test_trump_slug_falls_back_to_politics_bucket(tmp_path: Path) -> None:
    root = tmp_path / "inventory"
    _write_gold_tape(
        root,
        "will-trump-deport-less-than-250000",
        category="",
        yes_prices=[0.12, 0.88],
    )

    candidates, skipped = discover_inventory([root])

    assert skipped == []
    assert len(candidates) == 1
    assert "politics" in candidates[0].candidate_buckets


def test_success_path_writes_manifest_audit_and_lock(tmp_path: Path) -> None:
    manifest_out, audit_out, gap_out, lock_out = _build_valid_manifest(tmp_path)

    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    assert len(manifest) == 50
    assert len(set(manifest)) == 50

    audit = json.loads(audit_out.read_text(encoding="utf-8"))
    for bucket, quota in QUOTAS.items():
        assert audit["bucket_summary"][bucket]["selected_count"] == quota

    lock_payload = json.loads(lock_out.read_text(encoding="utf-8"))
    assert lock_payload["schema_version"] == "benchmark_tape_lock_v1"
    assert lock_payload["tape_count"] == 50
    assert not gap_out.exists()


def test_validate_manifest_accepts_valid_manifest(tmp_path: Path) -> None:
    manifest_out, _, _, lock_out = _build_valid_manifest(tmp_path)

    validation = validate_benchmark_manifest(manifest_out, lock_path=lock_out)

    assert validation.bucket_counts == QUOTAS
    assert len(validation.manifest_entries) == 50
    assert len(validation.tape_fingerprints) == 50


def test_validate_manifest_rejects_underfilled_manifest(tmp_path: Path) -> None:
    manifest_out, _, _, _ = _build_valid_manifest(tmp_path)
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    manifest_out.write_text(json.dumps(manifest[:-1], indent=2) + "\n", encoding="utf-8")

    try:
        validate_benchmark_manifest(manifest_out)
    except BenchmarkManifestValidationError as exc:
        assert any("exactly 50 tape paths" in issue for issue in exc.issues)
    else:
        raise AssertionError("expected underfilled manifest validation failure")


def test_validate_manifest_rejects_duplicate_paths(tmp_path: Path) -> None:
    manifest_out, _, _, _ = _build_valid_manifest(tmp_path)
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    manifest[1] = manifest[0]
    manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    try:
        validate_benchmark_manifest(manifest_out)
    except BenchmarkManifestValidationError as exc:
        assert any("duplicate tape path" in issue for issue in exc.issues)
    else:
        raise AssertionError("expected duplicate-path validation failure")


def test_validate_manifest_rejects_missing_files(tmp_path: Path) -> None:
    manifest_out, _, _, _ = _build_valid_manifest(tmp_path)
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    missing_path = _manifest_entry_to_path(manifest[0], manifest_out)
    missing_path.unlink()

    try:
        validate_benchmark_manifest(manifest_out)
    except BenchmarkManifestValidationError as exc:
        assert any("missing tape file" in issue for issue in exc.issues)
    else:
        raise AssertionError("expected missing-file validation failure")


def test_validate_manifest_rejects_fingerprint_drift(tmp_path: Path) -> None:
    manifest_out, _, _, lock_out = _build_valid_manifest(tmp_path)
    manifest = json.loads(manifest_out.read_text(encoding="utf-8"))
    drift_path = _manifest_entry_to_path(manifest[0], manifest_out)
    with drift_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_book_event("drift-asset", 0.55)) + "\n")

    try:
        validate_benchmark_manifest(manifest_out, lock_path=lock_out)
    except BenchmarkManifestValidationError as exc:
        assert any("fingerprint drift" in issue for issue in exc.issues)
    else:
        raise AssertionError("expected fingerprint-drift validation failure")


def test_validate_cli_smoke_writes_lock(tmp_path: Path) -> None:
    manifest_out, _, _, lock_out = _build_valid_manifest(tmp_path)
    lock_out.unlink()

    exit_code = main(
        [
            "validate",
            "--manifest",
            str(manifest_out),
            "--lock-path",
            str(lock_out),
            "--write-lock",
        ]
    )

    assert exit_code == 0
    assert lock_out.exists()
