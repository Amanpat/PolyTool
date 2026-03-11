import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.rag.defaults import RAG_DEFAULT_COLLECTION
from polymarket.rag.index import DEFAULT_MAX_BYTES
from tools.cli import llm_bundle, rag_index, rag_query, rag_run


def test_defaults_are_consistent():
    assert RAG_DEFAULT_COLLECTION == "polytool_rag"
    assert rag_index.build_parser().get_default("collection") == RAG_DEFAULT_COLLECTION
    assert rag_query.build_parser().get_default("collection") == RAG_DEFAULT_COLLECTION
    assert rag_index.build_parser().get_default("max_bytes") == DEFAULT_MAX_BYTES
    assert llm_bundle.RagSettings().collection == RAG_DEFAULT_COLLECTION
    assert rag_run._load_bundle_settings(None)["collection"] == RAG_DEFAULT_COLLECTION


def test_rag_run_manifest_collection_overrides_default(tmp_path):
    manifest_path = tmp_path / "bundle_manifest.json"
    manifest_path.write_text(
        json.dumps({"rag_query_settings": {"collection": "bundle_specific_collection"}}),
        encoding="utf-8",
    )

    settings = rag_run._load_bundle_settings(manifest_path)
    assert settings["collection"] == "bundle_specific_collection"
    assert settings["collection"] != rag_run._DEFAULT_COLLECTION
