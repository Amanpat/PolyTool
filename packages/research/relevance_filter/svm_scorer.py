"""SVM runtime scorer for the L3 v1 RIS topic filter.

Loads a trained sklearn Pipeline (.joblib) + metadata JSON, then scores
CandidateInput objects offline.

All heavy imports (joblib, sklearn, sentence-transformers) are deferred to
first use so the module can be imported without those deps installed.

Decision-function calibration note
------------------------------------
LinearSVC does not expose predict_proba().  We derive an "allow confidence"
by applying sigmoid to the negated decision-function value:

    allow_confidence = sigmoid(-df)

where ``df`` is the raw LinearSVC decision-function output.  With sklearn's
alphabetical class ordering (['allow', 'reject']), positive df → predicts
'reject' and negative df → predicts 'allow'.  This means:

  * df << 0 (strong allow prediction):  allow_confidence → 1.0
  * df ≈ 0  (on the decision boundary): allow_confidence ≈ 0.5
  * df >> 0 (strong reject prediction): allow_confidence → 0.0

The result is NOT a calibrated probability; it is a monotone confidence-like
value suitable for thresholding.  Use CalibratedClassifierCV if true
probability calibration is required.

Public API:
    SvmRuntimeConfig      — configuration dataclass
    SvmRelevanceScorer    — scorer class
    SvmModelLoadError     — raised for missing / corrupt model or metadata
    SvmMissingDepsError   — re-exported; raised when optional deps absent
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

from packages.research.relevance_filter.scorer import CandidateInput, FilterDecision
from packages.research.relevance_filter.svm_training import SvmMissingDepsError


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------

class SvmModelLoadError(RuntimeError):
    """Raised when the SVM model or metadata file cannot be loaded."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class SvmRuntimeConfig:
    """Runtime configuration for the SVM scorer.

    Parameters
    ----------
    model_path:
        Path to the .joblib sklearn Pipeline artifact.
    metadata_path:
        Path to the metadata JSON ledger.  If None, inferred from model_path
        by replacing the ``svm_model_`` prefix with ``svm_metadata_`` and the
        ``.joblib`` extension with ``.json``.
    threshold_allow:
        allow_confidence >= threshold_allow → "allow"
    threshold_review:
        threshold_review <= allow_confidence < threshold_allow → "review"
        allow_confidence < threshold_review → "reject"
    """

    model_path: str
    metadata_path: Optional[str] = None
    threshold_allow: float = 0.50
    threshold_review: float = 0.35


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_metadata_path(model_path: Path) -> Path:
    """Derive the metadata path from a model path.

    Converts ``svm_model_{tag}.joblib`` → ``svm_metadata_{tag}.json`` in the
    same directory.  Falls back to ``{stem}_metadata.json`` for paths that do
    not follow the convention.
    """
    stem = model_path.stem
    if stem.startswith("svm_model_"):
        meta_name = "svm_metadata_" + stem[len("svm_model_"):] + ".json"
    else:
        meta_name = stem + "_metadata.json"
    return model_path.parent / meta_name


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class SvmRelevanceScorer:
    """Runtime SVM relevance scorer.

    Loads the .joblib artifact and metadata lazily on the first ``score()``
    call.  Subsequent calls reuse the loaded pipeline.

    Parameters
    ----------
    config:
        SvmRuntimeConfig with paths and thresholds.
    embedding_provider:
        Callable ``(texts: list[str]) -> list[list[float]]`` injected for
        offline tests.  When None, sentence-transformers is used with the
        model name recorded in the metadata.
    """

    def __init__(
        self,
        config: SvmRuntimeConfig,
        embedding_provider: Optional[Callable[[List[str]], List[List[float]]]] = None,
    ) -> None:
        self._config = config
        self._embedding_provider = embedding_provider
        self._pipeline: object = None
        self._metadata: dict = {}
        self._loaded: bool = False
        self._default_provider: Optional[Callable[[List[str]], List[List[float]]]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(self, candidate: CandidateInput) -> FilterDecision:
        """Score a single candidate using the loaded SVM pipeline.

        Parameters
        ----------
        candidate:
            CandidateInput with at least a title.

        Returns
        -------
        FilterDecision
            scorer="svm" is set; SVM audit fields are populated from
            the metadata ledger.

        Raises
        ------
        SvmModelLoadError
            If the model or metadata file is missing or corrupt.
        SvmMissingDepsError
            If joblib / numpy / sentence-transformers are not installed.
        """
        self._load()

        # Build embedding text: title + abstract + source_url
        # Training used title + operator_note + source_url; notes are unavailable
        # at inference time so abstract substitutes.
        parts: List[str] = [candidate.title]
        if candidate.abstract:
            parts.append(candidate.abstract)
        if candidate.source_url:
            parts.append(candidate.source_url)
        text = " ".join(parts)

        # Embed
        provider = self._get_provider()
        try:
            import numpy as np
        except ImportError as exc:
            raise SvmMissingDepsError(
                "numpy is required for SVM scoring. "
                "Install with: pip install polytool[ris-svm]"
            ) from exc

        vectors = provider([text])
        X = np.array(vectors)

        # Predict
        prediction: str = str(self._pipeline.predict(X)[0])  # type: ignore[union-attr]

        # Decision-function → allow_confidence
        df_value = float(self._pipeline.decision_function(X)[0])  # type: ignore[union-attr]
        classes = list(self._pipeline.classes_)  # type: ignore[union-attr]
        allow_idx = classes.index("allow") if "allow" in classes else 0
        if allow_idx == 0:
            # positive df → classes[1] = "reject"
            allow_confidence = _sigmoid(-df_value)
        else:
            # positive df → classes[1] = "allow"
            allow_confidence = _sigmoid(df_value)

        # Threshold mapping
        cfg = self._config
        if allow_confidence >= cfg.threshold_allow:
            decision = "allow"
        elif allow_confidence >= cfg.threshold_review:
            decision = "review"
        else:
            decision = "reject"

        # Audit metadata from ledger
        model_name = self._metadata.get("embedding_model", "")
        random_state = int(self._metadata.get("seed", 0))
        model_type = self._metadata.get("model_type", "LinearSVC")
        lexical_baseline_note = self._metadata.get("lexical_baseline_note", "")

        reason_codes = [
            f"svm_prediction:{prediction}",
            f"svm_df:{round(df_value, 4)}",
            f"svm_allow_confidence:{round(allow_confidence, 4)}",
        ]

        input_fields_used: List[str] = ["title"]
        if candidate.abstract:
            input_fields_used.append("abstract")
        if candidate.source_url:
            input_fields_used.append("source_url")

        return FilterDecision(
            decision=decision,
            score=round(allow_confidence, 6),
            raw_score=round(df_value, 6),
            reason_codes=reason_codes,
            matched_terms={},
            candidate_title=candidate.title,
            source_id=candidate.source_id,
            allow_threshold=cfg.threshold_allow,
            review_threshold=cfg.threshold_review,
            config_version=model_type,
            input_fields_used=input_fields_used,
            scorer="svm",
            svm_model_name=model_name,
            svm_model_path=str(Path(self._config.model_path).resolve()),
            svm_random_state=random_state,
            svm_lexical_baseline_note=lexical_baseline_note,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Lazily load the joblib pipeline and metadata JSON."""
        if self._loaded:
            return

        try:
            import joblib
        except ImportError as exc:
            raise SvmMissingDepsError(
                "joblib is required for SVM scoring. "
                "Install with: pip install polytool[ris-svm]"
            ) from exc

        model_path = Path(self._config.model_path)
        if not model_path.exists():
            raise SvmModelLoadError(
                f"SVM model file not found: {model_path}"
            )

        if self._config.metadata_path is not None:
            meta_path = Path(self._config.metadata_path)
        else:
            meta_path = _infer_metadata_path(model_path)

        if not meta_path.exists():
            raise SvmModelLoadError(
                f"SVM metadata file not found: {meta_path}"
            )

        try:
            self._pipeline = joblib.load(model_path)
        except Exception as exc:
            raise SvmModelLoadError(
                f"Failed to load SVM model from {model_path}: {exc}"
            ) from exc

        try:
            self._metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SvmModelLoadError(
                f"Failed to load SVM metadata from {meta_path}: {exc}"
            ) from exc

        self._loaded = True

    def _get_provider(self) -> Callable[[List[str]], List[List[float]]]:
        """Return the active embedding provider, initialising default if needed."""
        if self._embedding_provider is not None:
            return self._embedding_provider
        if self._default_provider is None:
            self._default_provider = self._make_default_provider()
        return self._default_provider

    def _make_default_provider(self) -> Callable[[List[str]], List[List[float]]]:
        """Create a sentence-transformers provider from the metadata embedding_model."""
        model_name = self._metadata.get("embedding_model", "")
        if not model_name:
            raise SvmModelLoadError(
                "Cannot initialise default embedding provider: "
                "'embedding_model' key missing from SVM metadata"
            )
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:
            raise SvmMissingDepsError(
                "sentence-transformers is required for SVM scoring without an "
                "embedding_provider. Install with: pip install polytool[ris-svm]"
            ) from exc

        model = SentenceTransformer(model_name)

        def _provider(texts: List[str]) -> List[List[float]]:
            return model.encode(texts, show_progress_bar=False).tolist()

        return _provider
