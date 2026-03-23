"""Tests for packages/polymarket/historical_import/provenance.py."""

from __future__ import annotations

import pytest

from packages.polymarket.historical_import.provenance import (
    build_deterministic_import_manifest_id,
    build_deterministic_provenance_hash,
    validate_required_provenance_fields,
)


def _base_provenance(tmp_path, **overrides):
    payload = {
        "source_kind": "pmxt_archive",
        "source_path": str(tmp_path),
        "dataset_version_or_snapshot": "2026-03-13",
        "import_mode": "dry-run",
        "destination_reference": "polytool.pmxt_l2_snapshots",
        "source_state": "complete",
    }
    payload.update(overrides)
    return payload


def test_validate_required_provenance_fields_accepts_manifest_aliases(tmp_path):
    result = validate_required_provenance_fields(
        {
            "source_kind": "jon_becker",
            "local_path": str(tmp_path),
            "snapshot_version": "2026-03",
            "import_mode": "sample",
            "destination_tables": ["polytool.jb_trades"],
            "source_state": "complete",
        }
    )

    assert result.valid
    assert result.import_ready
    assert result.normalized["source_path"] == str(tmp_path.resolve())
    assert result.normalized["destination_references"] == ["polytool.jb_trades"]


def test_validate_required_provenance_fields_requires_explicit_source_state(tmp_path):
    result = validate_required_provenance_fields(
        _base_provenance(tmp_path, source_state=None)
    )

    assert not result.valid
    assert any("source completeness" in error for error in result.errors)


def test_validate_required_provenance_fields_marks_partial_source_not_ready(tmp_path):
    result = validate_required_provenance_fields(
        _base_provenance(tmp_path, source_state=None, partial_source=True)
    )

    assert result.valid
    assert not result.import_ready
    assert result.normalized["source_state"] == "partial"
    assert any("partial" in warning for warning in result.warnings)


def test_validate_required_provenance_fields_marks_missing_source_not_ready(tmp_path):
    result = validate_required_provenance_fields(
        _base_provenance(tmp_path, source_state=None, source_missing=True)
    )

    assert result.valid
    assert not result.import_ready
    assert result.normalized["source_state"] == "missing"
    assert any("missing" in warning for warning in result.warnings)


def test_validate_required_provenance_fields_explicit_partial_state_not_ready(tmp_path):
    result = validate_required_provenance_fields(
        _base_provenance(tmp_path, source_state="partial")
    )

    assert result.valid
    assert not result.import_ready
    assert result.normalized["source_state"] == "partial"
    assert any("partial" in warning for warning in result.warnings)


def test_validate_required_provenance_fields_explicit_missing_state_not_ready(tmp_path):
    result = validate_required_provenance_fields(
        _base_provenance(tmp_path, source_state="missing")
    )

    assert result.valid
    assert not result.import_ready
    assert result.normalized["source_state"] == "missing"
    assert any("missing" in warning for warning in result.warnings)


def test_validate_required_provenance_fields_rejects_invalid_import_mode(tmp_path):
    result = validate_required_provenance_fields(
        _base_provenance(tmp_path, import_mode="preview")
    )

    assert not result.valid
    assert any("import_mode" in error for error in result.errors)


def test_validate_required_provenance_fields_rejects_conflicting_source_flags(tmp_path):
    result = validate_required_provenance_fields(
        _base_provenance(
            tmp_path,
            source_state=None,
            partial_source=True,
            source_missing=True,
        )
    )

    assert not result.valid
    assert any("both partial and missing" in error for error in result.errors)


def test_build_deterministic_provenance_hash_sorts_destination_references(tmp_path):
    left = build_deterministic_provenance_hash(
        _base_provenance(
            tmp_path,
            destination_reference=[
                "artifacts/imports/pmxt_manifest.json",
                "polytool.pmxt_l2_snapshots",
            ],
        )
    )
    right = build_deterministic_provenance_hash(
        _base_provenance(
            tmp_path,
            destination_reference=[
                "polytool.pmxt_l2_snapshots",
                "artifacts/imports/pmxt_manifest.json",
            ],
        )
    )

    assert left == right


def test_build_deterministic_provenance_hash_changes_with_import_mode(tmp_path):
    dry_run_hash = build_deterministic_provenance_hash(
        _base_provenance(tmp_path, import_mode="dry-run")
    )
    full_hash = build_deterministic_provenance_hash(
        _base_provenance(tmp_path, import_mode="full")
    )

    assert dry_run_hash != full_hash


def test_build_deterministic_import_manifest_id_is_prefixed(tmp_path):
    manifest_id = build_deterministic_import_manifest_id(_base_provenance(tmp_path))

    assert manifest_id.startswith("import_manifest_")
    assert len(manifest_id) == len("import_manifest_") + 64


def test_build_deterministic_provenance_hash_rejects_missing_required_fields(tmp_path):
    with pytest.raises(ValueError, match="dataset_version_or_snapshot"):
        build_deterministic_provenance_hash(
            _base_provenance(tmp_path, dataset_version_or_snapshot="")
        )
