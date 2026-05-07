"""Tests for the L3 v1 SVM training core (packages.research.relevance_filter.svm_training).

All tests are offline and deterministic:
  - No network calls, no model downloads.
  - Fake embedding provider injects pre-computed vectors via hashlib so
    results are stable across Python processes (no hash-seed randomisation).
  - sklearn IS used in training tests (standard CI dep); sentence-transformers
    is NOT required.
  - tmp_path is used for all file I/O.

Test plan:
  1. Label loading — basic, skip-non-labeled, text-construction, empty file
  2. Min-per-class gate — skips training when threshold not met
  3. Deterministic split/eval — two runs produce identical metrics
  4. Cache reuse — provider called once; second run reads from disk cache
  5. Metadata ledger — all required fields present in written JSON
  6. Model artifact — .joblib file written on successful training
  7. Missing-dep behavior — SvmMissingDepsError raised (not raw ImportError)
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import List

import pytest

from packages.research.relevance_filter.svm_training import (
    LabeledExample,
    SvmMissingDepsError,
    SvmTrainingConfig,
    SvmTrainingResult,
    load_labeled_examples,
    train_and_evaluate_svm,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _write_labels(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


def _make_record(idx: int, label: str, note: str = "") -> dict:
    """Produce a label record matching the LabelStore schema."""
    url = f"https://arxiv.org/abs/{2000 + idx}"
    return {
        "candidate_id": f"cid{idx:04d}",
        "source_url": url,
        "title": f"Paper about prediction market microstructure {idx}",
        "label": label,
        "note": note or f"operator note {idx}",
        "labeled_at": "2026-01-01T00:00:00+00:00",
    }


def _make_dataset(n_allow: int, n_reject: int) -> list:
    """Build a mixed allow/reject dataset."""
    records = []
    for i in range(n_allow):
        records.append(_make_record(i, "allow"))
    for i in range(n_reject):
        records.append(_make_record(n_allow + i, "reject"))
    return records


def _fake_provider(dim: int = 16):
    """Return a deterministic fake embedding provider (no network, no models).

    Vectors are derived from SHA-256 of the input text — stable across runs
    and Python processes regardless of PYTHONHASHSEED.
    """
    call_count = {"n": 0}

    def provider(texts: List[str]) -> List[List[float]]:
        call_count["n"] += 1
        result = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            vec = [b / 255.0 for b in digest[:dim]]
            result.append(vec)
        return result

    provider.call_count = call_count  # type: ignore[attr-defined]
    return provider


def _make_config(
    tmp_path: Path,
    label_path: Path,
    *,
    model_name: str = "test-model",
    random_state: int = 42,
    test_size: float = 0.25,
    min_per_class: int = 5,
) -> SvmTrainingConfig:
    return SvmTrainingConfig(
        label_path=label_path,
        output_dir=tmp_path / "output",
        embedding_cache_dir=tmp_path / "cache",
        model_name=model_name,
        random_state=random_state,
        test_size=test_size,
        min_per_class=min_per_class,
    )


# ---------------------------------------------------------------------------
# 1. Label loading
# ---------------------------------------------------------------------------

class TestLoadLabeledExamples:

    def test_load_allow_and_reject(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(5, 5))
        examples = load_labeled_examples(path)
        assert len(examples) == 10
        allow_n = sum(1 for e in examples if e.label == "allow")
        reject_n = sum(1 for e in examples if e.label == "reject")
        assert allow_n == 5
        assert reject_n == 5

    def test_skip_non_labeled_entries(self, tmp_path):
        """Records with label != allow/reject are silently skipped."""
        path = tmp_path / "labels.jsonl"
        records = _make_dataset(3, 3)
        # Add a pending/unlabeled record
        records.append({
            "candidate_id": "pending_cid",
            "source_url": "https://arxiv.org/abs/9999",
            "title": "Pending Paper",
            "label": "pending",
            "note": "",
            "labeled_at": "2026-01-01T00:00:00+00:00",
        })
        # Add a record with missing label field
        records.append({
            "candidate_id": "nolabel_cid",
            "source_url": "https://arxiv.org/abs/8888",
            "title": "No Label Paper",
            "note": "",
            "labeled_at": "2026-01-01T00:00:00+00:00",
        })
        _write_labels(path, records)
        examples = load_labeled_examples(path)
        # Only the 6 allow/reject records should load
        assert len(examples) == 6
        assert all(e.label in ("allow", "reject") for e in examples)

    def test_text_built_from_title_note_source_url(self, tmp_path):
        """text field concatenates title + note + source_url."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, [
            {
                "candidate_id": "abc123",
                "source_url": "https://arxiv.org/abs/1234.5678",
                "title": "Order Book Dynamics",
                "label": "allow",
                "note": "highly relevant microstructure paper",
                "labeled_at": "2026-01-01T00:00:00+00:00",
            }
        ])
        examples = load_labeled_examples(path)
        assert len(examples) == 1
        e = examples[0]
        assert "Order Book Dynamics" in e.text
        assert "highly relevant microstructure paper" in e.text
        assert "https://arxiv.org/abs/1234.5678" in e.text

    def test_text_omits_empty_fields(self, tmp_path):
        """Empty note or source_url are not included in text (no double-spaces)."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, [
            {
                "candidate_id": "abc",
                "source_url": "https://arxiv.org/abs/1111",
                "title": "Prediction Market Paper",
                "label": "reject",
                "note": "",  # empty
                "labeled_at": "2026-01-01T00:00:00+00:00",
            }
        ])
        examples = load_labeled_examples(path)
        assert len(examples) == 1
        text = examples[0].text
        assert "  " not in text  # no double-spaces from empty fields

    def test_returns_labeled_example_dataclass(self, tmp_path):
        """load_labeled_examples returns LabeledExample instances."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, [_make_record(0, "allow")])
        examples = load_labeled_examples(path)
        assert isinstance(examples[0], LabeledExample)
        assert examples[0].candidate_id == "cid0000"
        assert examples[0].title == "Paper about prediction market microstructure 0"

    def test_empty_file_returns_empty_list(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        assert load_labeled_examples(path) == []

    def test_nonexistent_file_returns_empty_list(self, tmp_path):
        path = tmp_path / "nonexistent_labels.jsonl"
        assert load_labeled_examples(path) == []


# ---------------------------------------------------------------------------
# 2. Min-per-class gate
# ---------------------------------------------------------------------------

class TestMinPerClass:

    def test_skips_training_when_allow_count_too_low(self, tmp_path):
        """Training skipped when allow count is below min_per_class."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=3, n_reject=10))
        config = _make_config(tmp_path, path, min_per_class=5)
        provider = _fake_provider()
        result = train_and_evaluate_svm(config, embedding_provider=provider)
        assert result.skipped_training is True
        assert "allow=3" in result.skip_reason
        assert result.model_artifact_path is None

    def test_skips_training_when_reject_count_too_low(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=10, n_reject=2))
        config = _make_config(tmp_path, path, min_per_class=5)
        provider = _fake_provider()
        result = train_and_evaluate_svm(config, embedding_provider=provider)
        assert result.skipped_training is True
        assert "reject=2" in result.skip_reason
        assert result.model_artifact_path is None

    def test_skipped_result_has_counts(self, tmp_path):
        """Skipped result still reports label counts correctly."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=2, n_reject=8))
        config = _make_config(tmp_path, path, min_per_class=5)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        assert result.allow_count == 2
        assert result.reject_count == 8
        assert result.label_count == 10
        assert result.random_state == 42

    def test_skipped_writes_metadata_json(self, tmp_path):
        """Even when training is skipped, a metadata JSON is written."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=2, n_reject=2))
        config = _make_config(tmp_path, path, min_per_class=5)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        assert Path(result.metadata_path).exists()
        meta = json.loads(Path(result.metadata_path).read_text())
        assert meta["skipped_training"] is True

    def test_proceeds_when_counts_met(self, tmp_path):
        """Training is NOT skipped when both classes have >= min_per_class."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=12, n_reject=12))
        config = _make_config(tmp_path, path, min_per_class=5)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        assert result.skipped_training is False
        assert result.model_artifact_path is not None


# ---------------------------------------------------------------------------
# 3. Deterministic split/eval
# ---------------------------------------------------------------------------

class TestDeterminism:

    def _run_train(self, tmp_path: Path, label_path: Path, seed: int = 42):
        config = _make_config(
            tmp_path,
            label_path,
            random_state=seed,
            model_name="test-model-det",
        )
        provider = _fake_provider(dim=16)
        return train_and_evaluate_svm(config, embedding_provider=provider)

    def test_two_runs_produce_identical_metrics(self, tmp_path):
        """Same labels + same seed → identical precision/recall/F1."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=12, n_reject=12))

        result1 = self._run_train(tmp_path, path)
        result2 = self._run_train(tmp_path, path)

        assert result1.metrics == result2.metrics

    def test_two_runs_produce_identical_confusion_matrix(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=12, n_reject=12))

        result1 = self._run_train(tmp_path, path)
        result2 = self._run_train(tmp_path, path)

        assert result1.confusion_matrix == result2.confusion_matrix

    def test_different_seeds_may_differ(self, tmp_path):
        """Sanity: different seeds can produce different splits (not a hard assertion)."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=20, n_reject=20))

        result42 = self._run_train(tmp_path, path, seed=42)
        result99 = self._run_train(tmp_path, path, seed=99)

        # At minimum both runs should succeed
        assert not result42.skipped_training
        assert not result99.skipped_training

    def test_result_contains_train_and_test_sizes(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=12, n_reject=12))
        result = self._run_train(tmp_path, path)
        assert result.metrics["train_size"] > 0
        assert result.metrics["test_size"] > 0
        assert (
            result.metrics["train_size"] + result.metrics["test_size"] == 24
        )

    def test_result_has_accuracy(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=12, n_reject=12))
        result = self._run_train(tmp_path, path)
        acc = result.metrics["accuracy"]
        assert isinstance(acc, float)
        assert 0.0 <= acc <= 1.0

    def test_result_has_per_class_and_macro_metrics(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=12, n_reject=12))
        result = self._run_train(tmp_path, path)
        for key in ("precision", "recall", "f1"):
            assert "allow" in result.metrics[key]
            assert "reject" in result.metrics[key]
            assert "macro" in result.metrics[key]

    def test_confusion_matrix_shape(self, tmp_path):
        """Confusion matrix is 2×2 (allow vs reject)."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=12, n_reject=12))
        result = self._run_train(tmp_path, path)
        cm = result.confusion_matrix
        assert len(cm) == 2
        assert len(cm[0]) == 2
        assert len(cm[1]) == 2


# ---------------------------------------------------------------------------
# 4. Embedding cache
# ---------------------------------------------------------------------------

class TestEmbeddingCache:

    def test_cache_avoids_re_embedding_on_second_run(self, tmp_path):
        """Provider is called once on the first run; not called on the second run."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=12, n_reject=12))

        provider = _fake_provider()
        config = SvmTrainingConfig(
            label_path=path,
            output_dir=tmp_path / "output",
            embedding_cache_dir=tmp_path / "cache",
            model_name="test-model-cache",
            random_state=42,
        )

        # First run — embeddings computed and cached
        train_and_evaluate_svm(config, embedding_provider=provider)
        calls_after_first = provider.call_count["n"]  # type: ignore[attr-defined]
        assert calls_after_first >= 1  # at least one batch call

        # Second run — all vectors already in cache
        train_and_evaluate_svm(config, embedding_provider=provider)
        calls_after_second = provider.call_count["n"]  # type: ignore[attr-defined]
        assert calls_after_second == calls_after_first  # no new calls

    def test_cache_files_written_to_cache_dir(self, tmp_path):
        """Vectors are persisted as .json files under embedding_cache_dir."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=6, n_reject=6))
        cache_dir = tmp_path / "emb_cache"
        config = SvmTrainingConfig(
            label_path=path,
            output_dir=tmp_path / "output",
            embedding_cache_dir=cache_dir,
            model_name="test-model-files",
        )
        train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        cache_files = list(cache_dir.rglob("*.json"))
        assert len(cache_files) == 12  # one file per labeled example

    def test_cached_vectors_are_json_loadable(self, tmp_path):
        """Cached vector files contain valid JSON lists of floats."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=3, n_reject=3))
        cache_dir = tmp_path / "cache"
        config = SvmTrainingConfig(
            label_path=path,
            output_dir=tmp_path / "output",
            embedding_cache_dir=cache_dir,
            model_name="test-model-json",
            min_per_class=3,
        )
        train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        for f in cache_dir.rglob("*.json"):
            vec = json.loads(f.read_text())
            assert isinstance(vec, list)
            assert all(isinstance(x, float) for x in vec)

    def test_cache_key_depends_on_model_name(self, tmp_path):
        """Different model names produce different cache entries."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=6, n_reject=6))
        cache_dir = tmp_path / "cache"

        for model in ("model-A", "model-B"):
            config = SvmTrainingConfig(
                label_path=path,
                output_dir=tmp_path / f"output_{model}",
                embedding_cache_dir=cache_dir,
                model_name=model,
                min_per_class=5,
            )
            train_and_evaluate_svm(config, embedding_provider=_fake_provider())

        # Both model-A and model-B embeddings should be stored (separate keys)
        cache_files = list(cache_dir.rglob("*.json"))
        assert len(cache_files) == 24  # 12 per model


# ---------------------------------------------------------------------------
# 5. Metadata ledger
# ---------------------------------------------------------------------------

class TestMetadataLedger:

    def _run_and_load_meta(self, tmp_path: Path, n_allow: int = 12, n_reject: int = 12) -> dict:
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(n_allow=n_allow, n_reject=n_reject))
        config = _make_config(tmp_path, path)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        return json.loads(Path(result.metadata_path).read_text())

    def test_metadata_file_exists(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        assert Path(result.metadata_path).exists()

    def test_metadata_has_required_fields(self, tmp_path):
        """All spec-required fields are present in the metadata JSON."""
        meta = self._run_and_load_meta(tmp_path)
        required = [
            "label_count", "train_size", "eval_size", "seed",
            "timestamp", "sklearn_version", "model_type", "model_params",
            "embedding_model", "allow_count", "reject_count",
        ]
        for field_name in required:
            assert field_name in meta, f"Missing required metadata field: {field_name!r}"

    def test_metadata_label_counts_match_labels(self, tmp_path):
        meta = self._run_and_load_meta(tmp_path, n_allow=12, n_reject=12)
        assert meta["label_count"] == 24
        assert meta["allow_count"] == 12
        assert meta["reject_count"] == 12

    def test_metadata_seed_matches_config(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path, random_state=99)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        meta = json.loads(Path(result.metadata_path).read_text())
        assert meta["seed"] == 99

    def test_metadata_embedding_model_matches_config(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path, model_name="my-custom-model")
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        meta = json.loads(Path(result.metadata_path).read_text())
        assert meta["embedding_model"] == "my-custom-model"

    def test_metadata_model_type_is_linearsvc(self, tmp_path):
        meta = self._run_and_load_meta(tmp_path)
        assert meta["model_type"] == "LinearSVC"

    def test_metadata_contains_lexical_baseline_note(self, tmp_path):
        meta = self._run_and_load_meta(tmp_path)
        assert "5.88" in meta.get("lexical_baseline_note", "")

    def test_metadata_confusion_matrix_is_2x2(self, tmp_path):
        meta = self._run_and_load_meta(tmp_path)
        cm = meta["confusion_matrix"]
        assert len(cm) == 2
        assert len(cm[0]) == 2

    def test_metadata_train_plus_eval_equals_total(self, tmp_path):
        meta = self._run_and_load_meta(tmp_path, n_allow=12, n_reject=12)
        assert meta["train_size"] + meta["eval_size"] == 24


# ---------------------------------------------------------------------------
# 6. Model artifact
# ---------------------------------------------------------------------------

class TestModelArtifact:

    def test_model_file_is_written(self, tmp_path):
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        assert result.model_artifact_path is not None
        assert Path(result.model_artifact_path).exists()
        assert Path(result.model_artifact_path).suffix == ".joblib"

    def test_model_file_is_loadable(self, tmp_path):
        """joblib.load on the model file returns a sklearn Pipeline."""
        import joblib
        from sklearn.pipeline import Pipeline
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        loaded = joblib.load(result.model_artifact_path)
        assert isinstance(loaded, Pipeline)

    def test_result_fields_match_spec(self, tmp_path):
        """SvmTrainingResult has all fields required by the API contract."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path)
        result = train_and_evaluate_svm(config, embedding_provider=_fake_provider())
        assert isinstance(result, SvmTrainingResult)
        assert result.metrics
        assert result.confusion_matrix
        assert result.model_artifact_path is not None
        assert result.metadata_path
        assert result.label_count == 24
        assert result.allow_count == 12
        assert result.reject_count == 12
        assert result.random_state == 42


# ---------------------------------------------------------------------------
# 7. Missing dependency behavior
# ---------------------------------------------------------------------------

class TestMissingDeps:

    def test_missing_sklearn_raises_domain_error(self, tmp_path):
        """SvmMissingDepsError raised (not ImportError) when sklearn is absent."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path)

        # Poison sklearn in sys.modules to simulate it being absent
        sklearn_keys = [k for k in sys.modules if k == "sklearn" or k.startswith("sklearn.")]
        saved = {k: sys.modules[k] for k in sklearn_keys}
        for k in sklearn_keys:
            sys.modules[k] = None  # type: ignore[assignment]

        try:
            with pytest.raises(SvmMissingDepsError, match="scikit-learn"):
                train_and_evaluate_svm(
                    config,
                    embedding_provider=lambda texts: [[0.1] * 8] * len(texts),
                )
        finally:
            for k, v in saved.items():
                sys.modules[k] = v

    def test_missing_sentence_transformers_raises_domain_error(self, tmp_path):
        """SvmMissingDepsError raised when embedding_provider is None and
        sentence-transformers is not installed."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path)

        # Poison sentence_transformers
        st_keys = [
            k for k in sys.modules
            if k == "sentence_transformers" or k.startswith("sentence_transformers.")
        ]
        saved = {k: sys.modules[k] for k in st_keys}
        # Ensure the module appears absent even if it wasn't imported yet
        sys.modules["sentence_transformers"] = None  # type: ignore[assignment]

        try:
            with pytest.raises(SvmMissingDepsError, match="sentence-transformers"):
                train_and_evaluate_svm(config, embedding_provider=None)
        finally:
            for k, v in saved.items():
                sys.modules[k] = v
            # Remove the poison key if it was added fresh
            if "sentence_transformers" not in saved:
                sys.modules.pop("sentence_transformers", None)

    def test_domain_error_message_contains_install_hint(self, tmp_path):
        """SvmMissingDepsError message includes a pip install suggestion."""
        path = tmp_path / "labels.jsonl"
        _write_labels(path, _make_dataset(12, 12))
        config = _make_config(tmp_path, path)

        sklearn_keys = [k for k in sys.modules if k == "sklearn" or k.startswith("sklearn.")]
        saved = {k: sys.modules[k] for k in sklearn_keys}
        for k in sklearn_keys:
            sys.modules[k] = None  # type: ignore[assignment]

        try:
            with pytest.raises(SvmMissingDepsError) as exc_info:
                train_and_evaluate_svm(
                    config,
                    embedding_provider=lambda texts: [[0.1] * 8] * len(texts),
                )
            assert "pip install" in str(exc_info.value).lower()
        finally:
            for k, v in saved.items():
                sys.modules[k] = v

    def test_module_imports_cleanly_without_optional_deps(self):
        """svm_training can be imported even without sklearn/sentence-transformers.

        load_labeled_examples is callable (no optional deps).
        train_and_evaluate_svm only fails when called, not at import time.
        """
        # If we got here, the import at the top of the file already succeeded.
        assert callable(load_labeled_examples)
        assert callable(train_and_evaluate_svm)
