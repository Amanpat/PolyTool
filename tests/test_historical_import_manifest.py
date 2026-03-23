"""Tests for packages/polymarket/historical_import/manifest.py."""

from __future__ import annotations

import json

import pytest

from packages.polymarket.historical_import.manifest import (
    SCHEMA_VERSION,
    SourceKind,
    _manifest_id,
    make_import_manifest,
    make_provenance_record,
)


def test_manifest_id_deterministic():
    a = _manifest_id("pmxt_archive", "/some/path")
    b = _manifest_id("pmxt_archive", "/some/path")
    assert a == b


def test_manifest_id_differs_by_kind():
    a = _manifest_id("pmxt_archive", "/same/path")
    b = _manifest_id("jon_becker", "/same/path")
    assert a != b


def test_manifest_id_differs_by_path():
    a = _manifest_id("pmxt_archive", "/path/a")
    b = _manifest_id("pmxt_archive", "/path/b")
    assert a != b


def test_manifest_id_is_hex64():
    mid = _manifest_id("pmxt_archive", "/x")
    assert len(mid) == 64
    int(mid, 16)


def test_make_provenance_record_all_source_kinds(tmp_path):
    for kind in SourceKind:
        rec = make_provenance_record(kind.value, str(tmp_path))
        assert rec.source_kind == kind.value
        assert rec.manifest_id != ""
        assert rec.schema_version == SCHEMA_VERSION


def test_make_provenance_record_rejects_unknown_kind(tmp_path):
    with pytest.raises(ValueError, match="Unknown source_kind"):
        make_provenance_record("bad_kind", str(tmp_path))


def test_make_provenance_record_deterministic(tmp_path):
    r1 = make_provenance_record("pmxt_archive", str(tmp_path))
    r2 = make_provenance_record("pmxt_archive", str(tmp_path))
    assert r1.manifest_id == r2.manifest_id


def test_make_provenance_record_destination_tables(tmp_path):
    for kind in SourceKind:
        rec = make_provenance_record(kind.value, str(tmp_path))
        assert len(rec.destination_tables) >= 1
        assert all("polytool." in t for t in rec.destination_tables)


def test_make_provenance_record_default_status(tmp_path):
    rec = make_provenance_record("pmxt_archive", str(tmp_path))
    assert rec.status == "staged"


def test_make_provenance_record_custom_status(tmp_path):
    rec = make_provenance_record("pmxt_archive", str(tmp_path), status="validated")
    assert rec.status == "validated"


def test_make_provenance_record_notes(tmp_path):
    rec = make_provenance_record("pmxt_archive", str(tmp_path), notes="test note")
    assert rec.notes == "test note"


def test_make_provenance_record_json_sorted_keys(tmp_path):
    rec = make_provenance_record("pmxt_archive", str(tmp_path))
    parsed = json.loads(rec.to_json())
    assert parsed["manifest_id"] == rec.manifest_id
    assert parsed["schema_version"] == SCHEMA_VERSION


def test_make_import_manifest_empty():
    m = make_import_manifest([])
    assert m.schema_version == SCHEMA_VERSION
    assert m.sources == []
    assert m.generated_at != ""


def test_make_import_manifest_multiple_sources(tmp_path):
    sources = [
        make_provenance_record("pmxt_archive", str(tmp_path)),
        make_provenance_record("jon_becker", str(tmp_path)),
    ]
    m = make_import_manifest(sources)
    assert len(m.sources) == 2


def test_make_import_manifest_to_json_valid(tmp_path):
    sources = [make_provenance_record("pmxt_archive", str(tmp_path))]
    m = make_import_manifest(sources)
    payload = json.loads(m.to_json())
    assert payload["schema_version"] == SCHEMA_VERSION
    assert len(payload["sources"]) == 1
    assert payload["sources"][0]["source_kind"] == "pmxt_archive"


def test_make_import_manifest_to_dict(tmp_path):
    sources = [make_provenance_record("jon_becker", str(tmp_path))]
    m = make_import_manifest(sources)
    d = m.to_dict()
    assert isinstance(d["sources"], list)
    assert d["sources"][0]["manifest_id"] != ""
