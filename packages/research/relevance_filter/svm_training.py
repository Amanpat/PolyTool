"""SVM training and evaluation core for the L3 v1 topic filter.

All SVM and embedding dependencies are imported lazily so that the module
can be imported safely even when scikit-learn / sentence-transformers are not
installed.  A clear SvmMissingDepsError is raised at call time rather than
at import time.

Public API (consumed by the CLI layer / Prompt B):
    SvmTrainingConfig      — configuration dataclass
    SvmTrainingResult      — result dataclass
    LabeledExample         — single labeled training example
    SvmMissingDepsError    — raised when optional deps are absent
    train_and_evaluate_svm(config, embedding_provider) -> SvmTrainingResult
    load_labeled_examples(label_path) -> list[LabeledExample]
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from packages.research.relevance_filter.queue_store import _read_jsonl


# ---------------------------------------------------------------------------
# Domain error
# ---------------------------------------------------------------------------

class SvmMissingDepsError(RuntimeError):
    """Raised when scikit-learn or sentence-transformers are not installed."""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SvmTrainingConfig:
    """Configuration for one SVM train/eval run."""

    label_path: Path
    output_dir: Path
    embedding_cache_dir: Path
    model_name: str
    random_state: int = 42
    test_size: float = 0.25
    min_per_class: int = 5


@dataclass
class LabeledExample:
    """One labeled training example derived from the label store."""

    candidate_id: str
    text: str       # title + note + source_url, joined with spaces
    label: str      # "allow" | "reject"
    source_url: str
    title: str


@dataclass
class SvmTrainingResult:
    """Result returned by train_and_evaluate_svm()."""

    metrics: dict                   # precision/recall/f1/accuracy per class + macro
    confusion_matrix: list          # [[TP_allow, FN_allow], [FP_allow, TN_allow]]
    model_artifact_path: Optional[str]  # path to .joblib file, or None if skipped
    metadata_path: str              # path to metadata JSON ledger
    label_count: int
    allow_count: int
    reject_count: int
    random_state: int
    lexical_baseline_note: str = "Lexical v1.1 Scenario B: 5.88% off-topic rate"
    skipped_training: bool = False
    skip_reason: str = ""


# ---------------------------------------------------------------------------
# Label loading
# ---------------------------------------------------------------------------

def load_labeled_examples(label_path: Path) -> List[LabeledExample]:
    """Read a labels.jsonl and return only allow/reject entries.

    Records whose label field is absent or not 'allow'/'reject' (e.g.,
    pending or unlabeled) are silently skipped.

    Parameters
    ----------
    label_path:
        Path to the JSONL file produced by LabelStore.  May not exist yet
        (returns an empty list in that case).

    Returns
    -------
    List[LabeledExample]
    """
    records = _read_jsonl(Path(label_path))
    examples: List[LabeledExample] = []
    for r in records:
        label = r.get("label", "")
        if label not in ("allow", "reject"):
            continue
        title = r.get("title", "")
        note = r.get("note", "")
        source_url = r.get("source_url", "")
        parts = [p for p in (title, note, source_url) if p]
        text = " ".join(parts)
        examples.append(
            LabeledExample(
                candidate_id=r.get("candidate_id", ""),
                text=text,
                label=label,
                source_url=source_url,
                title=title,
            )
        )
    return examples


# ---------------------------------------------------------------------------
# Embedding cache
# ---------------------------------------------------------------------------

def _cache_key(model_name: str, text: str) -> str:
    """Stable SHA-256 key from model name and text content."""
    return hashlib.sha256(f"{model_name}:{text}".encode("utf-8")).hexdigest()


def _load_cached_vector(cache_dir: Path, key: str) -> Optional[List[float]]:
    path = cache_dir / key[:2] / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _save_cached_vector(cache_dir: Path, key: str, vector: List[float]) -> None:
    path = cache_dir / key[:2] / f"{key}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(vector), encoding="utf-8")


def _embed_with_cache(
    texts: List[str],
    model_name: str,
    cache_dir: Path,
    provider: Callable[[List[str]], List[List[float]]],
) -> List[List[float]]:
    """Embed texts, loading from disk cache to avoid re-embedding."""
    cache_dir = Path(cache_dir)
    keys = [_cache_key(model_name, t) for t in texts]
    results: List[Optional[List[float]]] = [None] * len(texts)
    uncached: List[int] = []

    for i, key in enumerate(keys):
        vec = _load_cached_vector(cache_dir, key)
        if vec is not None:
            results[i] = vec
        else:
            uncached.append(i)

    if uncached:
        new_vecs = provider([texts[i] for i in uncached])
        for list_pos, orig_idx in enumerate(uncached):
            vec = [float(v) for v in new_vecs[list_pos]]  # coerce numpy floats
            results[orig_idx] = vec
            _save_cached_vector(cache_dir, keys[orig_idx], vec)

    return results  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Default embedding provider (sentence-transformers)
# ---------------------------------------------------------------------------

def _make_default_embedding_provider(
    model_name: str,
) -> Callable[[List[str]], List[List[float]]]:
    """Create a sentence-transformers provider.

    Raises SvmMissingDepsError if the library is not installed.
    """
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError as exc:
        raise SvmMissingDepsError(
            "sentence-transformers is required for SVM training without an "
            "embedding_provider. Install with: pip install polytool[ris-svm]"
        ) from exc

    model = SentenceTransformer(model_name)

    def _provider(texts: List[str]) -> List[List[float]]:
        return model.encode(texts, show_progress_bar=False).tolist()

    return _provider


# ---------------------------------------------------------------------------
# Main train/eval entry point
# ---------------------------------------------------------------------------

def train_and_evaluate_svm(
    config: SvmTrainingConfig,
    embedding_provider: Optional[Callable[[List[str]], List[List[float]]]] = None,
) -> SvmTrainingResult:
    """Train an SVM classifier on labeled examples and evaluate it.

    Parameters
    ----------
    config:
        SvmTrainingConfig specifying paths, model name, seed, and split params.
    embedding_provider:
        Callable ``(texts: list[str]) -> list[list[float]]`` that returns one
        vector per text.  If *None*, falls back to sentence-transformers with
        ``config.model_name``.  Inject a mock here in offline tests.

    Returns
    -------
    SvmTrainingResult
        Contains metrics, confusion matrix, artifact paths, and counts.
        If training is skipped (too few labels), ``skipped_training=True``
        and ``model_artifact_path=None``.

    Raises
    ------
    SvmMissingDepsError
        If scikit-learn is not installed, or (when embedding_provider is None)
        sentence-transformers is not installed.
    """
    # Lazy imports — fail with a domain error, not a raw ImportError traceback
    try:
        import numpy as np
        from sklearn.svm import LinearSVC
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import (
            precision_recall_fscore_support,
            accuracy_score,
            confusion_matrix as sk_confusion_matrix,
        )
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline
        import sklearn as _sklearn
    except ImportError as exc:
        raise SvmMissingDepsError(
            "scikit-learn is required for SVM training. "
            "Install with: pip install polytool[ris-svm]"
        ) from exc
    try:
        import joblib
    except ImportError as exc:
        raise SvmMissingDepsError(
            "joblib is required for SVM training. "
            "Install with: pip install polytool[ris-svm]"
        ) from exc

    label_path = Path(config.label_path)
    output_dir = Path(config.output_dir)
    cache_dir = Path(config.embedding_cache_dir)

    examples = load_labeled_examples(label_path)
    allow_count = sum(1 for e in examples if e.label == "allow")
    reject_count = sum(1 for e in examples if e.label == "reject")
    label_count = len(examples)

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(tz=timezone.utc).isoformat()
    safe_model = config.model_name.replace("/", "_").replace("\\", "_")
    metadata_filename = f"svm_metadata_{safe_model}_{config.random_state}.json"
    metadata_path = output_dir / metadata_filename

    # Skip training when minimum class counts are not met
    if allow_count < config.min_per_class or reject_count < config.min_per_class:
        skip_reason = (
            f"Insufficient labels: allow={allow_count}, reject={reject_count}, "
            f"min_per_class={config.min_per_class}"
        )
        _write_metadata(
            metadata_path,
            label_count=label_count,
            allow_count=allow_count,
            reject_count=reject_count,
            train_size=0,
            eval_size=0,
            seed=config.random_state,
            timestamp=timestamp,
            sklearn_version=_sklearn.__version__,
            model_name=config.model_name,
            model_params={},
            metrics={},
            confusion_matrix=[],
            skipped_training=True,
            skip_reason=skip_reason,
        )
        return SvmTrainingResult(
            metrics={},
            confusion_matrix=[],
            model_artifact_path=None,
            metadata_path=str(metadata_path),
            label_count=label_count,
            allow_count=allow_count,
            reject_count=reject_count,
            random_state=config.random_state,
            skipped_training=True,
            skip_reason=skip_reason,
        )

    # Resolve embedding provider (may raise SvmMissingDepsError for sent-transformers)
    if embedding_provider is None:
        embedding_provider = _make_default_embedding_provider(config.model_name)

    # Embed (cache-aware)
    texts = [e.text for e in examples]
    labels_list = [e.label for e in examples]
    vectors = _embed_with_cache(texts, config.model_name, cache_dir, embedding_provider)
    X = np.array(vectors)
    y = np.array(labels_list)

    # Train/test split with stratification
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=config.test_size,
        random_state=config.random_state,
        stratify=y,
    )

    # Build and fit SVM pipeline
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("svm", LinearSVC(random_state=config.random_state, max_iter=2000)),
        ]
    )
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)

    # Evaluation metrics
    label_order = ["allow", "reject"]
    precision_arr, recall_arr, f1_arr, _ = precision_recall_fscore_support(
        y_test, y_pred, labels=label_order, zero_division=0
    )
    accuracy = float(accuracy_score(y_test, y_pred))
    cm = sk_confusion_matrix(y_test, y_pred, labels=label_order).tolist()

    macro_p = float(np.mean(precision_arr))
    macro_r = float(np.mean(recall_arr))
    macro_f1 = float(np.mean(f1_arr))

    metrics: dict = {
        "accuracy": accuracy,
        "precision": {
            "allow": float(precision_arr[0]),
            "reject": float(precision_arr[1]),
            "macro": macro_p,
        },
        "recall": {
            "allow": float(recall_arr[0]),
            "reject": float(recall_arr[1]),
            "macro": macro_r,
        },
        "f1": {
            "allow": float(f1_arr[0]),
            "reject": float(f1_arr[1]),
            "macro": macro_f1,
        },
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
    }

    # Save model artifact
    svm_params = {k: _to_json_safe(v) for k, v in pipeline.named_steps["svm"].get_params().items()}
    model_filename = f"svm_model_{safe_model}_{config.random_state}.joblib"
    model_path = output_dir / model_filename
    joblib.dump(pipeline, model_path)

    _write_metadata(
        metadata_path,
        label_count=label_count,
        allow_count=allow_count,
        reject_count=reject_count,
        train_size=int(len(X_train)),
        eval_size=int(len(X_test)),
        seed=config.random_state,
        timestamp=timestamp,
        sklearn_version=_sklearn.__version__,
        model_name=config.model_name,
        model_params=svm_params,
        metrics=metrics,
        confusion_matrix=cm,
        skipped_training=False,
        skip_reason="",
    )

    return SvmTrainingResult(
        metrics=metrics,
        confusion_matrix=cm,
        model_artifact_path=str(model_path),
        metadata_path=str(metadata_path),
        label_count=label_count,
        allow_count=allow_count,
        reject_count=reject_count,
        random_state=config.random_state,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_json_safe(v: object) -> object:
    """Convert numpy scalars / booleans to JSON-serializable Python types."""
    try:
        import numpy as np
        if isinstance(v, np.integer):
            return int(v)
        if isinstance(v, np.floating):
            return float(v)
        if isinstance(v, np.bool_):
            return bool(v)
    except ImportError:
        pass
    return v


def _write_metadata(
    path: Path,
    *,
    label_count: int,
    allow_count: int,
    reject_count: int,
    train_size: int,
    eval_size: int,
    seed: int,
    timestamp: str,
    sklearn_version: str,
    model_name: str,
    model_params: dict,
    metrics: dict,
    confusion_matrix: list,
    skipped_training: bool,
    skip_reason: str,
) -> None:
    record = {
        "label_count": label_count,
        "allow_count": allow_count,
        "reject_count": reject_count,
        "train_size": train_size,
        "eval_size": eval_size,
        "seed": seed,
        "timestamp": timestamp,
        "sklearn_version": sklearn_version,
        "model_type": "LinearSVC",
        "model_params": model_params,
        "embedding_model": model_name,
        "metrics": metrics,
        "confusion_matrix": confusion_matrix,
        "lexical_baseline_note": "Lexical v1.1 Scenario B: 5.88% off-topic rate",
        "skipped_training": skipped_training,
        "skip_reason": skip_reason,
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
