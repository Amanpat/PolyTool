"""Tests for research-prefetch-svm-train CLI.

All tests are offline: no model weights are downloaded, no sklearn or
sentence-transformers calls are made. Core module and ML deps are
monkeypatched throughout.

Acceptance gates covered:
  - Graceful failure when ML deps missing (returns 1, clear stderr)
  - Graceful failure when core module missing (returns 1, clear stderr)
  - Graceful failure when labels file missing (returns 1, clear stderr)
  - Graceful failure when insufficient labels (returns 1, clear stderr)
  - --dry-run validates without training; does NOT call train_and_evaluate_svm
  - --dry-run --json returns parseable JSON with expected keys
  - Full training path returns 0 with JSON output containing expected keys
  - Full training path returns 0 with human-readable output
  - --help exits 0
  - No real artifacts written during any test (uses tmp_path fixtures)
  - research-acquire existing tests unaffected (no imports from this module)
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers — fake core module and result
# ---------------------------------------------------------------------------


class _FakeSvmResult:
    """Minimal stand-in for the result returned by train_and_evaluate_svm."""

    label_count: int = 61
    allow_count: int = 30
    reject_count: int = 31
    random_state: int = 42
    metrics: dict = {
        "precision_allow": 0.90,
        "recall_allow": 0.85,
        "f1_allow": 0.875,
        "precision_reject": 0.88,
        "recall_reject": 0.91,
        "f1_reject": 0.895,
        "macro_f1": 0.885,
        "baseline_scenario_b": 0.0588,
    }
    confusion_matrix: list = [[15, 2], [3, 14]]
    model_artifact_path: Optional[str] = "/tmp/fake_model.pkl"
    metadata_path: Optional[str] = "/tmp/fake_metadata.json"
    lexical_baseline_note: str = "Lexical v1.1 Scenario B: 5.88% off-topic rate"


class _FakeSvmResultNoArtifact(_FakeSvmResult):
    """Variant where model_artifact_path is None (dry-run-like core result)."""

    model_artifact_path = None
    metadata_path = None


def _make_fake_svm_module(
    result: Optional[_FakeSvmResult] = None,
    raise_on_train: Optional[Exception] = None,
) -> types.ModuleType:
    """Build a fake packages.research.relevance_filter.svm_training module.

    Parameters
    ----------
    result:
        Object returned by train_and_evaluate_svm. Defaults to _FakeSvmResult().
    raise_on_train:
        If set, train_and_evaluate_svm raises this exception instead.
    """
    fake = types.ModuleType("packages.research.relevance_filter.svm_training")

    class FakeSvmTrainingConfig:
        def __init__(
            self,
            label_path,
            output_dir,
            embedding_cache_dir,
            model_name,
            random_state,
            test_size,
        ):
            self.label_path = label_path
            self.output_dir = output_dir
            self.embedding_cache_dir = embedding_cache_dir
            self.model_name = model_name
            self.random_state = random_state
            self.test_size = test_size

    if raise_on_train is not None:
        exc_to_raise = raise_on_train

        def _train(config):
            raise exc_to_raise

    else:
        _result = result if result is not None else _FakeSvmResult()

        def _train(config):
            return _result

    fake.SvmTrainingConfig = FakeSvmTrainingConfig
    fake.train_and_evaluate_svm = _train
    return fake


def _write_labels(path: Path, allow: int = 30, reject: int = 31) -> None:
    """Write a minimal labels.jsonl fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    records = []
    for i in range(allow):
        records.append(
            {
                "candidate_id": f"allow_{i:04d}",
                "source_url": f"https://arxiv.org/abs/allow.{i:04d}",
                "title": f"Allow paper {i}",
                "label": "allow",
                "note": "",
                "labeled_at": "2026-05-01T00:00:00+00:00",
            }
        )
    for i in range(reject):
        records.append(
            {
                "candidate_id": f"reject_{i:04d}",
                "source_url": f"https://arxiv.org/abs/reject.{i:04d}",
                "title": f"Reject paper {i}",
                "label": "reject",
                "note": "",
                "labeled_at": "2026-05-01T00:00:00+00:00",
            }
        )
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r) + "\n")


# ---------------------------------------------------------------------------
# Fixture: inject fake svm_training into sys.modules for the test scope
# ---------------------------------------------------------------------------


@pytest.fixture()
def patch_svm_module(monkeypatch):
    """Inject a working fake svm_training module and return its call tracker.

    Usage:
        def test_foo(patch_svm_module):
            fake_mod, call_tracker = patch_svm_module()
    """

    def _factory(
        result=None,
        raise_on_train=None,
    ):
        fake_mod = _make_fake_svm_module(result=result, raise_on_train=raise_on_train)
        calls = []
        original_train = fake_mod.train_and_evaluate_svm

        def _tracking_train(config):
            calls.append(config)
            return original_train(config)

        fake_mod.train_and_evaluate_svm = _tracking_train

        monkeypatch.setitem(
            sys.modules,
            "packages.research.relevance_filter.svm_training",
            fake_mod,
        )
        return fake_mod, calls

    return _factory


# ---------------------------------------------------------------------------
# Test: --help exits 0
# ---------------------------------------------------------------------------


class TestHelpFlag:
    def test_help_exits_zero(self, capsys):
        from tools.cli.research_prefetch_svm_train import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # Should mention the command name and key flags
        assert "research-prefetch-svm-train" in captured.out
        assert "--labels" in captured.out
        assert "--dry-run" in captured.out
        assert "--json" in captured.out


# ---------------------------------------------------------------------------
# Test: missing ML dependencies — graceful exit 1 with clear message
# ---------------------------------------------------------------------------


class TestMissingMlDeps:
    def test_missing_sklearn_returns_1(self, monkeypatch, tmp_path, capsys):
        """When scikit-learn is absent, CLI exits 1 with clear message."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: ["scikit-learn"])

        from tools.cli.research_prefetch_svm_train import main

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        rc = main(["--labels", str(labels_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "scikit-learn" in captured.err
        assert "pip install" in captured.err

    def test_missing_sentence_transformers_returns_1(
        self, monkeypatch, tmp_path, capsys
    ):
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(
            cli_mod, "_check_ml_deps", lambda: ["sentence-transformers"]
        )

        from tools.cli.research_prefetch_svm_train import main

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        rc = main(["--labels", str(labels_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "sentence-transformers" in captured.err

    def test_missing_both_deps_returns_1(self, monkeypatch, tmp_path, capsys):
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(
            cli_mod,
            "_check_ml_deps",
            lambda: ["scikit-learn", "sentence-transformers"],
        )

        from tools.cli.research_prefetch_svm_train import main

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        rc = main(["--labels", str(labels_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "scikit-learn" in captured.err
        assert "sentence-transformers" in captured.err

    def test_missing_joblib_returns_1(self, monkeypatch, tmp_path, capsys):
        """When joblib is absent, CLI exits 1 with a clear message naming joblib."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: ["joblib"])

        from tools.cli.research_prefetch_svm_train import main

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        rc = main(["--labels", str(labels_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "joblib" in captured.err
        assert "pip install" in captured.err

    def test_missing_deps_no_traceback_in_stderr(
        self, monkeypatch, tmp_path, capsys
    ):
        """Error message should not contain a Python traceback."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: ["scikit-learn"])

        from tools.cli.research_prefetch_svm_train import main

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)
        main(["--labels", str(labels_path)])
        captured = capsys.readouterr()
        assert "Traceback" not in captured.err


# ---------------------------------------------------------------------------
# Test: missing core module — graceful exit 1 with clear message
# ---------------------------------------------------------------------------


class TestMissingCoreModule:
    def test_missing_svm_training_module_returns_1(
        self, monkeypatch, tmp_path, capsys
    ):
        """When svm_training.py is absent, CLI exits 1 with a clear message."""
        # Suppress any dep failures first
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])

        # Force ImportError for the core module
        monkeypatch.setitem(
            sys.modules,
            "packages.research.relevance_filter.svm_training",
            None,
        )

        from tools.cli.research_prefetch_svm_train import main

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        rc = main(["--labels", str(labels_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not available" in captured.err or "svm_training" in captured.err

    def test_missing_core_module_no_traceback(self, monkeypatch, tmp_path, capsys):
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        monkeypatch.setitem(
            sys.modules,
            "packages.research.relevance_filter.svm_training",
            None,
        )

        from tools.cli.research_prefetch_svm_train import main

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)
        main(["--labels", str(labels_path)])
        captured = capsys.readouterr()
        assert "Traceback" not in captured.err


# ---------------------------------------------------------------------------
# Test: labels file not found
# ---------------------------------------------------------------------------


class TestLabelsNotFound:
    def test_missing_labels_file_returns_1(
        self, monkeypatch, tmp_path, capsys
    ):
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(tmp_path / "nonexistent.jsonl")])
        assert rc == 1
        captured = capsys.readouterr()
        assert "not found" in captured.err.lower() or "error" in captured.err.lower()


# ---------------------------------------------------------------------------
# Test: insufficient labels
# ---------------------------------------------------------------------------


class TestInsufficientLabels:
    def test_too_few_allow_labels_returns_1(
        self, monkeypatch, tmp_path, capsys
    ):
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path, allow=3, reject=30)  # allow below _MIN_LABELS_PER_CLASS

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "insufficient" in captured.err.lower() or "allow" in captured.err.lower()

    def test_too_few_reject_labels_returns_1(
        self, monkeypatch, tmp_path, capsys
    ):
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path, allow=30, reject=2)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "insufficient" in captured.err.lower()


# ---------------------------------------------------------------------------
# Test: --dry-run validates without training
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_returns_0(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """--dry-run exits 0 when labels + deps + core module are valid."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        _fake_mod, calls = patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path), "--dry-run"])
        assert rc == 0

    def test_dry_run_does_not_call_train(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """--dry-run must NOT invoke train_and_evaluate_svm."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        _fake_mod, calls = patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path), "--dry-run"])
        assert calls == [], f"train_and_evaluate_svm was called unexpectedly: {calls}"

    def test_dry_run_human_readable_output(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """--dry-run human-readable output mentions key fields."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path), "--dry-run"])
        assert rc == 0
        captured = capsys.readouterr()
        assert "[dry-run]" in captured.out
        assert "ready_to_train" in captured.out or "ready" in captured.out.lower()

    def test_dry_run_json_output_has_expected_keys(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """--dry-run --json returns valid JSON with expected validation keys."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path), "--dry-run", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        expected_keys = {
            "dry_run",
            "labels_path",
            "label_count",
            "allow_count",
            "reject_count",
            "model_name",
            "random_state",
            "test_size",
            "output_dir",
            "embedding_cache_dir",
            "deps_ok",
            "core_module_ok",
            "ready_to_train",
        }
        assert expected_keys.issubset(set(data.keys()))
        assert data["dry_run"] is True
        assert data["deps_ok"] is True
        assert data["core_module_ok"] is True
        assert data["ready_to_train"] is True

    def test_dry_run_json_label_counts_correct(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """--dry-run --json label counts match fixture."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path, allow=15, reject=20)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path), "--dry-run", "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["allow_count"] == 15
        assert data["reject_count"] == 20
        assert data["label_count"] == 35

    def test_dry_run_does_not_write_artifacts(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """--dry-run must not create any files under output-dir."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        output_dir = tmp_path / "models"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main([
            "--labels", str(labels_path),
            "--output-dir", str(output_dir),
            "--dry-run",
        ])
        assert not output_dir.exists(), "output-dir must not be created in dry-run"


# ---------------------------------------------------------------------------
# Test: full training path with monkeypatched core
# ---------------------------------------------------------------------------


class TestFullTrainingPath:
    def test_train_returns_0(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Full training path returns 0."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path)])
        assert rc == 0

    def test_train_calls_train_and_evaluate_svm_once(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Training path calls train_and_evaluate_svm exactly once."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        _fake_mod, calls = patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path)])
        assert len(calls) == 1

    def test_train_config_has_correct_args(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """SvmTrainingConfig receives the CLI args."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        _fake_mod, calls = patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        output_dir = tmp_path / "models"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main([
            "--labels", str(labels_path),
            "--output-dir", str(output_dir),
            "--random-state", "99",
            "--test-size", "0.3",
            "--model-name", "allenai/specter2",
        ])
        assert len(calls) == 1
        cfg = calls[0]
        assert cfg.random_state == 99
        assert cfg.test_size == pytest.approx(0.3)
        assert cfg.model_name == "allenai/specter2"
        assert Path(cfg.label_path) == labels_path

    def test_train_json_output_has_expected_keys(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Full training --json output has all expected result keys."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path), "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        expected_keys = {
            "label_count",
            "allow_count",
            "reject_count",
            "random_state",
            "metrics",
            "confusion_matrix",
            "model_artifact_path",
            "metadata_path",
        }
        assert expected_keys.issubset(set(data.keys()))

    def test_train_json_metrics_parseable(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Metrics in JSON output are numeric and parseable."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path), "--json"])
        data = json.loads(capsys.readouterr().out)
        metrics = data["metrics"]
        assert isinstance(metrics, dict)
        assert len(metrics) > 0
        for key, val in metrics.items():
            assert isinstance(val, (int, float)), f"{key}={val!r} is not numeric"

    def test_train_json_confusion_matrix_present(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Confusion matrix is present in JSON output."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path), "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["confusion_matrix"] is not None

    def test_train_json_model_artifact_path_string_or_null(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """model_artifact_path in JSON output is a string or null."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path), "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["model_artifact_path"] is None or isinstance(
            data["model_artifact_path"], str
        )

    def test_train_json_null_artifact_when_core_returns_none(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """When core result has model_artifact_path=None, JSON output is null."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module(result=_FakeSvmResultNoArtifact())

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path), "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["model_artifact_path"] is None
        assert data["metadata_path"] is None

    def test_train_human_readable_output(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Human-readable output includes metric names and label counts."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Training Complete" in captured.out or "training" in captured.out.lower()
        # Must show label counts
        assert "allow" in captured.out.lower()
        assert "reject" in captured.out.lower()

    def test_train_json_has_lexical_baseline_note(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """JSON output includes lexical_baseline_note containing '5.88' or 'Scenario B'."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path), "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert "lexical_baseline_note" in data
        note = data["lexical_baseline_note"]
        assert "5.88" in note or "Scenario B" in note

    def test_train_human_readable_has_lexical_baseline_note(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Human-readable output includes lexical baseline note with '5.88' or 'Scenario B'."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "5.88" in captured.out or "Scenario B" in captured.out

    def test_train_runtime_error_returns_2(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """When train_and_evaluate_svm raises, CLI exits 2 with message."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module(raise_on_train=RuntimeError("embedding failed"))

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path)])
        assert rc == 2
        captured = capsys.readouterr()
        assert "embedding failed" in captured.err or "error" in captured.err.lower()


# ---------------------------------------------------------------------------
# Test: default argument values
# ---------------------------------------------------------------------------


class TestDefaultArgs:
    def test_default_model_name(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Default model name is allenai/specter2 or another reasonable SPECTER2 name."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        _fake_mod, calls = patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path)])
        assert len(calls) == 1
        # Default model should be a SPECTER2/S2FOS-compatible name
        assert "specter" in calls[0].model_name.lower() or "s2" in calls[0].model_name.lower()

    def test_default_random_state_42(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        _fake_mod, calls = patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path)])
        assert calls[0].random_state == 42

    def test_default_test_size_0_25(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        _fake_mod, calls = patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        main(["--labels", str(labels_path)])
        assert calls[0].test_size == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Test: command registered in polytool __main__
# ---------------------------------------------------------------------------


class TestCommandRegistration:
    def test_command_in_handler_names(self):
        """research-prefetch-svm-train must be registered in _COMMAND_HANDLER_NAMES."""
        from polytool.__main__ import _COMMAND_HANDLER_NAMES

        assert "research-prefetch-svm-train" in _COMMAND_HANDLER_NAMES

    def test_handler_name_resolves(self):
        """The handler name must resolve to a callable via globals()."""
        import polytool.__main__ as main_mod

        handler_name = main_mod._COMMAND_HANDLER_NAMES["research-prefetch-svm-train"]
        handler = getattr(main_mod, handler_name, None)
        assert handler is not None, f"{handler_name} not found in __main__"
        assert callable(handler)

    def test_help_from_main_entrypoint(self, capsys):
        """python -m polytool --help output mentions the new command."""
        from polytool.__main__ import print_usage

        print_usage()
        captured = capsys.readouterr()
        assert "research-prefetch-svm-train" in captured.out


# ---------------------------------------------------------------------------
# Test: no side-effects on research-acquire or research-prefetch-discover
# ---------------------------------------------------------------------------


class TestNoSideEffectsOnExistingCLIs:
    def test_acquire_help_unaffected(self, capsys):
        """research-acquire --help still works after importing svm-train CLI."""
        import tools.cli.research_prefetch_svm_train  # noqa: F401 — import side-effect check

        from tools.cli.research_acquire import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_discover_help_unaffected(self, capsys):
        """research-prefetch-discover --help still works after importing svm-train CLI."""
        import tools.cli.research_prefetch_svm_train  # noqa: F401

        from tools.cli.research_prefetch_discover import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_acquire_dry_run_unaffected(self, monkeypatch, tmp_path, capsys):
        """research-acquire --dry-run is not affected by the svm-train module."""
        import packages.research.ingestion.fetchers as fetchers_mod

        monkeypatch.setenv("RIS_PDF_PARSER", "pdfplumber")

        def _fake_arxiv(url, timeout, headers):
            xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.11111v1</id>
    <title>No SVM Side Effect Paper</title>
    <summary>Testing acquire is unaffected.</summary>
    <author><name>Test</name></author>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""
            return xml

        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _fake_arxiv)

        from tools.cli.research_acquire import main

        rc = main([
            "--url", "https://arxiv.org/abs/2301.11111",
            "--source-family", "academic",
            "--dry-run",
            "--no-eval",
            "--json",
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["dry_run"] is True
        assert data["source_family"] == "academic"


# ---------------------------------------------------------------------------
# Test: real SvmTrainingConfig signature (regression against label_path mismatch)
# ---------------------------------------------------------------------------


class TestRealConfigSignature:
    def test_label_path_kwarg_accepted(self, tmp_path):
        """Real SvmTrainingConfig accepts label_path=, not labels_path=."""
        from packages.research.relevance_filter.svm_training import SvmTrainingConfig

        config = SvmTrainingConfig(
            label_path=tmp_path / "labels.jsonl",
            output_dir=tmp_path / "output",
            embedding_cache_dir=tmp_path / "cache",
            model_name="allenai/specter2",
        )
        assert config.label_path == tmp_path / "labels.jsonl"

    def test_labels_path_kwarg_rejected(self, tmp_path):
        """Real SvmTrainingConfig rejects labels_path= (catches CLI regression)."""
        from packages.research.relevance_filter.svm_training import SvmTrainingConfig

        with pytest.raises(TypeError, match="labels_path"):
            SvmTrainingConfig(
                labels_path=tmp_path / "labels.jsonl",
                output_dir=tmp_path / "output",
                embedding_cache_dir=tmp_path / "cache",
                model_name="allenai/specter2",
            )

    def test_config_signature_has_label_path_not_labels_path(self):
        """Introspect SvmTrainingConfig signature to confirm field name."""
        import inspect
        from packages.research.relevance_filter.svm_training import SvmTrainingConfig

        sig = inspect.signature(SvmTrainingConfig)
        assert "label_path" in sig.parameters
        assert "labels_path" not in sig.parameters


# ---------------------------------------------------------------------------
# Test: default embedding cache dir path
# ---------------------------------------------------------------------------


class TestDefaultEmbeddingCacheDir:
    def test_default_embedding_cache_under_models_dir(
        self, monkeypatch, tmp_path, capsys, patch_svm_module
    ):
        """Default embedding cache dir is under svm_filter_models/embeddings."""
        import tools.cli.research_prefetch_svm_train as cli_mod

        monkeypatch.setattr(cli_mod, "_check_ml_deps", lambda: [])
        patch_svm_module()

        labels_path = tmp_path / "labels.jsonl"
        _write_labels(labels_path)

        from tools.cli.research_prefetch_svm_train import main

        rc = main(["--labels", str(labels_path), "--dry-run", "--json"])
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        cache_dir = data["embedding_cache_dir"]
        assert "svm_filter_models" in cache_dir
        assert cache_dir.endswith("embeddings") or cache_dir.endswith("embeddings\\") or cache_dir.endswith("embeddings/")
