"""CLI for L3 v1 SVM topic filter training and evaluation.

Reads labeled examples from the prefetch SVM label store, trains a
scikit-learn SVM classifier using SPECTER2/S2FOS-compatible embeddings
(via sentence-transformers), evaluates with a fixed-seed train/test split,
and exports the trained model artifact with an embedded metadata ledger.

Integration is **default-off**: this command trains and exports the model;
it does not wire SVM scoring into the acquisition or discovery pipeline.
Existing filter modes (off, dry-run, enforce, hold-review) are unchanged.

Usage:
  python -m polytool research-prefetch-svm-train
  python -m polytool research-prefetch-svm-train --dry-run
  python -m polytool research-prefetch-svm-train --json
  python -m polytool research-prefetch-svm-train \\
    --labels artifacts/research/svm_filter_labels/labels.jsonl \\
    --output-dir artifacts/research/svm_filter_models \\
    --random-state 42
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple


_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_LABELS_PATH = (
    _REPO_ROOT / "artifacts" / "research" / "svm_filter_labels" / "labels.jsonl"
)
_DEFAULT_OUTPUT_DIR = _REPO_ROOT / "artifacts" / "research" / "svm_filter_models"
_DEFAULT_EMBEDDING_CACHE_DIR = _DEFAULT_OUTPUT_DIR / "embeddings"
_DEFAULT_MODEL_NAME = "allenai/specter2"

_MIN_LABELS_PER_CLASS = 5


def _check_ml_deps() -> List[str]:
    """Return a list of missing optional ML dependency names.

    Checks for scikit-learn, joblib, and sentence-transformers without
    importing them into the module namespace (to avoid side-effects on import).
    """
    missing: List[str] = []
    try:
        import sklearn  # noqa: F401
    except ImportError:
        missing.append("scikit-learn")
    try:
        import joblib  # noqa: F401
    except ImportError:
        missing.append("joblib")
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        missing.append("sentence-transformers")
    return missing


def _load_labels(
    labels_path: Path,
) -> Tuple[List[dict], int, int]:
    """Load labels from a JSONL file.

    Returns
    -------
    tuple
        (all_records, allow_count, reject_count)

    Raises
    ------
    FileNotFoundError
        If labels_path does not exist.
    """
    if not labels_path.exists():
        raise FileNotFoundError(f"Labels file not found: {labels_path}")
    records: List[dict] = []
    with labels_path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(
                    f"WARNING: malformed JSONL in {labels_path} at line {lineno}: {exc}",
                    file=sys.stderr,
                )
    allow_count = sum(1 for r in records if r.get("label") == "allow")
    reject_count = sum(1 for r in records if r.get("label") == "reject")
    return records, allow_count, reject_count


def main(argv: Optional[List[str]] = None) -> int:
    """Train and evaluate the L3 v1 SVM topic filter.

    Returns
    -------
    int
        0 on success (including dry-run)
        1 on argument / validation / dependency error
        2 on training runtime error
    """
    parser = argparse.ArgumentParser(
        prog="research-prefetch-svm-train",
        description=(
            "L3 v1 SVM topic filter: train and evaluate a scikit-learn SVM classifier "
            "on labeled prefetch filter examples using SPECTER2/S2FOS embeddings. "
            "Integration is default-off — this command trains and exports the model "
            "artifact; it does not activate SVM scoring in the live pipeline."
        ),
    )
    parser.add_argument(
        "--labels",
        metavar="PATH",
        default=None,
        help=(
            "Labels JSONL file path "
            "(default: artifacts/research/svm_filter_labels/labels.jsonl)."
        ),
    )
    parser.add_argument(
        "--output-dir",
        metavar="PATH",
        dest="output_dir",
        default=None,
        help=(
            "Directory for trained model artifacts "
            "(default: artifacts/research/svm_filter_models)."
        ),
    )
    parser.add_argument(
        "--embedding-cache-dir",
        metavar="PATH",
        dest="embedding_cache_dir",
        default=None,
        help=(
            "Directory for cached embeddings; cached embeddings are re-used on "
            "subsequent runs to avoid re-embedding the same candidates "
            "(default: artifacts/research/svm_filter_models/embeddings)."
        ),
    )
    parser.add_argument(
        "--model-name",
        metavar="NAME",
        dest="model_name",
        default=_DEFAULT_MODEL_NAME,
        help=(
            f"sentence-transformers embedding model name "
            f"(default: {_DEFAULT_MODEL_NAME}). "
            "Model weights are loaded from local cache or downloaded once "
            "by the operator; they are NOT downloaded on every invocation."
        ),
    )
    parser.add_argument(
        "--random-state",
        metavar="INT",
        dest="random_state",
        type=int,
        default=42,
        help=(
            "Random seed for train/test split and SVM classifier (default: 42). "
            "Two runs on the same labels.jsonl with the same seed produce "
            "identical metrics."
        ),
    )
    parser.add_argument(
        "--test-size",
        metavar="FLOAT",
        dest="test_size",
        type=float,
        default=0.25,
        help="Fraction of labels held out for evaluation (default: 0.25).",
    )
    parser.add_argument(
        "--json",
        dest="output_json",
        action="store_true",
        help="Output structured JSON result instead of human-readable text.",
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help=(
            "Validate labels, check ML dependencies, and verify the core module "
            "is importable — without loading model weights or writing artifacts."
        ),
    )

    args = parser.parse_args(argv)

    labels_path = Path(args.labels) if args.labels else _DEFAULT_LABELS_PATH
    output_dir = Path(args.output_dir) if args.output_dir else _DEFAULT_OUTPUT_DIR
    embedding_cache_dir = (
        Path(args.embedding_cache_dir)
        if args.embedding_cache_dir
        else _DEFAULT_EMBEDDING_CACHE_DIR
    )

    # --- Step 1: Check ML dependencies ---
    missing_deps = _check_ml_deps()
    if missing_deps:
        dep_list = ", ".join(f"'{d}'" for d in missing_deps)
        print(
            f"Error: missing required ML dependencies: {dep_list}.\n"
            f"Install with:  pip install scikit-learn sentence-transformers",
            file=sys.stderr,
        )
        return 1

    # --- Step 2: Load and validate labels ---
    try:
        _records, allow_count, reject_count = _load_labels(labels_path)
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    total_count = len(_records)

    if allow_count < _MIN_LABELS_PER_CLASS or reject_count < _MIN_LABELS_PER_CLASS:
        print(
            f"Error: insufficient labels for training. "
            f"Need at least {_MIN_LABELS_PER_CLASS} per class. "
            f"Found: allow={allow_count}, reject={reject_count}.",
            file=sys.stderr,
        )
        return 1

    # --- Step 3: Verify the core SVM training module is importable ---
    try:
        from packages.research.relevance_filter.svm_training import (
            SvmTrainingConfig,
            train_and_evaluate_svm,
        )
    except ImportError as exc:
        print(
            f"Error: SVM training core module not available: {exc}\n"
            f"The module packages/research/relevance_filter/svm_training.py "
            f"must be implemented before training can run.",
            file=sys.stderr,
        )
        return 1

    # --- Dry-run: validation complete, do not train or write artifacts ---
    if args.dry_run:
        validation = {
            "dry_run": True,
            "labels_path": str(labels_path),
            "label_count": total_count,
            "allow_count": allow_count,
            "reject_count": reject_count,
            "model_name": args.model_name,
            "random_state": args.random_state,
            "test_size": args.test_size,
            "output_dir": str(output_dir),
            "embedding_cache_dir": str(embedding_cache_dir),
            "deps_ok": True,
            "core_module_ok": True,
            "ready_to_train": True,
        }
        if args.output_json:
            print(json.dumps(validation, indent=2))
        else:
            print("[dry-run] SVM training validation:")
            print(f"  labels_path     : {labels_path}")
            print(
                f"  label_count     : {total_count}  "
                f"(allow={allow_count}, reject={reject_count})"
            )
            print(f"  model_name      : {args.model_name}")
            print(f"  random_state    : {args.random_state}")
            print(f"  test_size       : {args.test_size}")
            print(f"  output_dir      : {output_dir}")
            print(f"  embedding_cache : {embedding_cache_dir}")
            print(
                f"  deps_ok         : True  (scikit-learn, sentence-transformers)"
            )
            print(f"  core_module_ok  : True")
            print(f"  ready_to_train  : True")
        return 0

    # --- Step 4: Build config and run training ---
    config = SvmTrainingConfig(
        label_path=labels_path,
        output_dir=output_dir,
        embedding_cache_dir=embedding_cache_dir,
        model_name=args.model_name,
        random_state=args.random_state,
        test_size=args.test_size,
    )

    try:
        result = train_and_evaluate_svm(config)
    except Exception as exc:
        print(f"Error: SVM training failed: {exc}", file=sys.stderr)
        return 2

    # --- Step 5: Output results ---
    if args.output_json:
        out = {
            "label_count": result.label_count,
            "allow_count": result.allow_count,
            "reject_count": result.reject_count,
            "random_state": result.random_state,
            "metrics": result.metrics,
            "confusion_matrix": result.confusion_matrix,
            "model_artifact_path": (
                str(result.model_artifact_path)
                if result.model_artifact_path
                else None
            ),
            "metadata_path": (
                str(result.metadata_path) if result.metadata_path else None
            ),
            "lexical_baseline_note": result.lexical_baseline_note,
        }
        print(json.dumps(out, indent=2))
    else:
        metrics = result.metrics or {}
        print("SVM Topic Filter — Training Complete")
        print(
            f"  labels          : {result.label_count}  "
            f"(allow={result.allow_count}, reject={result.reject_count})"
        )
        print(f"  random_state    : {result.random_state}")
        print("")
        print("Evaluation metrics:")
        for key, value in metrics.items():
            if isinstance(value, float):
                print(f"  {key:<24}: {value:.4f}")
            else:
                print(f"  {key:<24}: {value}")
        if result.confusion_matrix:
            print(f"\n  confusion_matrix       : {result.confusion_matrix}")
        if result.model_artifact_path:
            print(f"\n  model artifact  : {result.model_artifact_path}")
        if result.metadata_path:
            print(f"  metadata        : {result.metadata_path}")
        print(f"\n  baseline        : {result.lexical_baseline_note}")

    return 0
