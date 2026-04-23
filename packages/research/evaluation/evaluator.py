"""RIS evaluation gate — document evaluation pipeline.

DocumentEvaluator runs hard stops first, then optional dedup check, then
feature extraction, then scores with the configured provider, and finally
persists a structured artifact if artifacts_dir is set.

Phase 3 additions (backward compatible):
- Near-duplicate detection before LLM scoring (skipped if no existing_hashes provided)
- Per-family feature extraction (always runs, stored in artifact)
- Structured JSONL artifact persistence (skipped if no artifacts_dir provided)

Phase 2 additions (backward compatible):
- priority_tier parameter: sets priority tier on ScoringResult (default: config default)
- Fail-closed scoring: any exception from provider.score() returns REJECT with
  reject_reason="scorer_failure" instead of propagating the exception.

WP2-H additions (backward compatible):
- routing_mode="route" enables Gemini-primary / DeepSeek-escalation for yellow-band
  (REVIEW gate) results. Direct single-provider mode is unchanged.
- provider_events in artifacts records every scoring attempt in order (primary first,
  then escalation if triggered).

WP2-I additions (backward compatible):
- budget_tracker_path: optional path to artifacts/research/budget_tracker.json.
  When set, per-provider daily caps from config are enforced before each API call.
  Exhausted primary in route mode falls through to escalation immediately.
  Exhausted provider in direct mode returns REJECT with reject_reason="budget_exhausted".
  Local providers (manual, ollama) are always uncapped.
  When budget_tracker_path is None (default), all budget logic is skipped.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from packages.research.evaluation.types import (
    EvalDocument,
    GateDecision,
    HardStopResult,
    ScoringResult,
    SOURCE_FAMILIES,
)
from packages.research.evaluation.hard_stops import check_hard_stops
from packages.research.evaluation.providers import EvalProvider, get_provider


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class _ProviderStub:
    """Minimal duck-typed provider stub used when escalation construction fails.

    Satisfies the get_provider_metadata() duck-type contract so a ProviderEvent
    can still be recorded for the failed escalation attempt.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_id(self) -> str:
        return "construction_failed"

    @property
    def generation_params(self) -> dict:
        return {}


class DocumentEvaluator:
    """Multi-provider evaluation gate for incoming research documents.

    Phase 3 pipeline: hard_stops -> dedup -> feature_extraction -> scoring -> artifact

    Uses ManualProvider by default — the pipeline works offline with no
    cloud API keys required. Pass a different provider for LLM-based scoring.

    Args:
        provider: EvalProvider instance. Defaults to ManualProvider.
        artifacts_dir: If set, persist a structured EvalArtifact JSONL record
            after each evaluation. Directory is created if it does not exist.
        existing_hashes: Set of content hashes for exact-duplicate detection.
            If None or empty, dedup check is skipped.
        existing_shingles: List of (doc_id, shingle_frozenset) pairs for
            near-duplicate detection. If None, shingle comparison is skipped.
        priority_tier: Priority tier for gate thresholds (default: config default).
        routing_mode: "direct" (default) uses provider only. "route" escalates
            yellow-band REVIEW results to escalation_provider.
        escalation_provider: Provider to use for escalation in "route" mode.
            If None and routing_mode is "route", constructed lazily from config.
        budget_tracker_path: Path to the daily budget tracker JSON file. When set,
            per-provider caps from config are enforced. When None (default), all
            budget logic is skipped for full backward compatibility.
    """

    def __init__(
        self,
        provider: Optional[EvalProvider] = None,
        artifacts_dir: Optional[Path] = None,
        existing_hashes: Optional[set] = None,
        existing_shingles: Optional[list] = None,
        priority_tier: Optional[str] = None,
        routing_mode: str = "direct",
        escalation_provider: Optional[EvalProvider] = None,
        budget_tracker_path: Optional[Path] = None,
    ):
        from packages.research.evaluation.providers import ManualProvider
        self._provider = provider if provider is not None else ManualProvider()
        self._artifacts_dir = Path(artifacts_dir) if artifacts_dir is not None else None
        self._existing_hashes: set = existing_hashes if existing_hashes is not None else set()
        self._existing_shingles: list = existing_shingles if existing_shingles is not None else []
        # priority_tier: None means use the config default (resolved at evaluation time)
        self._priority_tier = priority_tier
        self._routing_mode = routing_mode
        self._escalation_provider = escalation_provider
        self._budget_tracker_path = Path(budget_tracker_path) if budget_tracker_path is not None else None

    def evaluate(self, doc: EvalDocument) -> GateDecision:
        """Evaluate a document through the quality gate.

        Steps:
        1. Hard stops — if any fail, return REJECT immediately (no scoring).
        2. Near-duplicate check — if existing_hashes provided and match found,
           return REJECT with dedup hard_stop (no scoring).
        3. Feature extraction — extract per-family features (always runs).
        4. LLM scoring — score with provider, with optional routing escalation.
        5. Artifact persistence — if artifacts_dir is set, write JSONL record.
        6. Return GateDecision.

        Backward compatible: without artifacts_dir/existing_hashes/existing_shingles,
        behavior is identical to Phase 2.

        Args:
            doc: The document to evaluate.

        Returns:
            GateDecision with gate (ACCEPT|REVIEW|REJECT), scores, and metadata.
        """
        from packages.research.evaluation.feature_extraction import extract_features
        from packages.research.evaluation.dedup import check_near_duplicate
        from packages.research.evaluation.artifacts import (
            EvalArtifact,
            persist_eval_artifact,
            generate_event_id,
        )
        from packages.research.evaluation.providers import get_provider_metadata

        now = _iso_utc(_utcnow())
        source_family = SOURCE_FAMILIES.get(doc.source_type, "manual")

        # Step 1: hard stops
        hard_stop_result = check_hard_stops(doc)
        if not hard_stop_result.passed:
            decision = GateDecision(
                gate="REJECT",
                scores=None,
                hard_stop=hard_stop_result,
                doc_id=doc.doc_id,
                timestamp=now,
            )
            if self._artifacts_dir is not None:
                features_result = extract_features(doc)
                artifact = EvalArtifact(
                    doc_id=doc.doc_id,
                    timestamp=now,
                    gate="REJECT",
                    hard_stop_result=dataclasses.asdict(hard_stop_result),
                    near_duplicate_result=None,
                    family_features=features_result.features,
                    scores=None,
                    source_family=source_family,
                    source_type=doc.source_type,
                    provider_events=None,
                    event_id=None,
                )
                persist_eval_artifact(artifact, self._artifacts_dir)
            return decision

        # Step 2: near-duplicate check (only if we have existing hashes to compare)
        near_dup_result = None
        if self._existing_hashes:
            near_dup_result = check_near_duplicate(
                doc, self._existing_hashes, self._existing_shingles
            )
            if near_dup_result.is_duplicate:
                dedup_stop = HardStopResult(
                    passed=False,
                    reason=f"Document is a {near_dup_result.duplicate_type} duplicate.",
                    stop_type=f"{near_dup_result.duplicate_type}_duplicate",
                )
                decision = GateDecision(
                    gate="REJECT",
                    scores=None,
                    hard_stop=dedup_stop,
                    doc_id=doc.doc_id,
                    timestamp=now,
                )
                if self._artifacts_dir is not None:
                    features_result = extract_features(doc)
                    artifact = EvalArtifact(
                        doc_id=doc.doc_id,
                        timestamp=now,
                        gate="REJECT",
                        hard_stop_result=dataclasses.asdict(dedup_stop),
                        near_duplicate_result=dataclasses.asdict(near_dup_result),
                        family_features=features_result.features,
                        scores=None,
                        source_family=source_family,
                        source_type=doc.source_type,
                        provider_events=None,
                        event_id=None,
                    )
                    persist_eval_artifact(artifact, self._artifacts_dir)
                return decision

        # Step 3: feature extraction
        features_result = extract_features(doc)

        # Step 4: score with provider (with optional routing escalation).
        # Returns final scores and a call log: [(provider, raw_output, prompt_hash), ...]
        scores, provider_calls = self._score_with_routing(doc)

        # Step 5: persist artifact (Phase 5: includes ProviderEvent metadata per call)
        if self._artifacts_dir is not None:
            scores_dict = {
                "relevance": scores.relevance,
                "novelty": scores.novelty,
                "actionability": scores.actionability,
                "credibility": scores.credibility,
                "total": scores.total,
                "epistemic_type": scores.epistemic_type,
                "summary": scores.summary,
                "key_findings": scores.key_findings,
                "eval_model": scores.eval_model,
                # Phase 2 fields
                "composite_score": scores.composite_score,
                "simple_sum_score": scores.simple_sum_score,
                "priority_tier": scores.priority_tier,
                "reject_reason": scores.reject_reason,
            }
            near_dup_dict = dataclasses.asdict(near_dup_result) if near_dup_result else None

            provider_events = [
                dataclasses.asdict(self._build_provider_event(doc, p, raw, ph, now))
                for p, raw, ph in provider_calls
            ]
            primary_meta = get_provider_metadata(self._provider)
            event_id = generate_event_id(doc.doc_id, now, primary_meta["provider_name"])

            artifact = EvalArtifact(
                doc_id=doc.doc_id,
                timestamp=now,
                gate=scores.gate,
                hard_stop_result=None,
                near_duplicate_result=near_dup_dict,
                family_features=features_result.features,
                scores=scores_dict,
                source_family=source_family,
                source_type=doc.source_type,
                provider_events=provider_events,
                event_id=event_id,
            )
            persist_eval_artifact(artifact, self._artifacts_dir)

        # Step 6: return decision
        return GateDecision(
            gate=scores.gate,
            scores=scores,
            hard_stop=hard_stop_result,
            doc_id=doc.doc_id,
            timestamp=now,
        )

    # ------------------------------------------------------------------
    # Private routing helpers
    # ------------------------------------------------------------------

    def _score_with_routing(
        self, doc: EvalDocument
    ) -> Tuple[ScoringResult, List[Tuple[EvalProvider, str, str]]]:
        """Score with optional escalation routing and budget enforcement.

        Returns:
            (final_scores, call_log) where call_log is a list of
            (provider, raw_output, prompt_hash) tuples in call order.
            Direct mode always produces one entry. Route mode appends a
            second entry if the primary result is yellow-band (REVIEW).
            Budget-exhausted or construction-failed stubs produce a
            (_ProviderStub, "", "") entry so artifacts record the attempt.
        """
        from packages.research.evaluation.config import get_eval_config
        from packages.research.evaluation.scoring import _compute_composite
        cfg = get_eval_config()
        calls: List[Tuple[EvalProvider, str, str]] = []

        # Load budget tracker once (None → enforcement disabled, full backward compat).
        tracker = None
        if self._budget_tracker_path is not None:
            from packages.research.evaluation.budget import load_budget_tracker
            tracker = load_budget_tracker(self._budget_tracker_path)

        primary_name = self._provider.name

        # --- Budget check: primary provider ---
        if not self._check_budget(primary_name, tracker, cfg):
            calls.append((_ProviderStub(primary_name), "", ""))
            if self._routing_mode != "route":
                return self._make_budget_exhausted_result(primary_name, cfg), calls
            # Route mode: primary exhausted → attempt escalation immediately.
            try:
                escalation = self._get_escalation_provider()
            except Exception:
                esc_name = cfg.routing.escalation_provider
                calls.append((_ProviderStub(esc_name), "", ""))
                return self._make_budget_exhausted_result(esc_name, cfg), calls
            esc_name = escalation.name
            if not self._check_budget(esc_name, tracker, cfg):
                calls.append((_ProviderStub(esc_name), "", ""))
                return self._make_budget_exhausted_result(esc_name, cfg), calls
            esc_scores, esc_raw, esc_ph = self._call_provider_once(escalation, doc)
            esc_scores = self._apply_priority_tier(esc_scores)
            calls.append((escalation, esc_raw, esc_ph))
            if esc_scores.reject_reason != "scorer_failure":
                self._increment_and_save(esc_name, tracker)
            return esc_scores, calls

        # --- Call primary ---
        scores, raw_output, prompt_hash = self._call_provider_once(self._provider, doc)
        scores = self._apply_priority_tier(scores)
        calls.append((self._provider, raw_output, prompt_hash))
        if scores.reject_reason != "scorer_failure":
            self._increment_and_save(primary_name, tracker)

        # --- Route mode: escalate on REVIEW gate ---
        if self._routing_mode == "route" and scores.gate == "REVIEW":
            try:
                escalation = self._get_escalation_provider()
            except Exception:
                # Construction failed — fail closed (same behavior as WP2-H).
                esc_name = cfg.routing.escalation_provider
                composite = _compute_composite(1, 1, 1, 1)
                esc_scores = ScoringResult(
                    relevance=1, novelty=1, actionability=1, credibility=1,
                    total=4,
                    composite_score=composite,
                    priority_tier=self._priority_tier or cfg.default_priority_tier,
                    reject_reason="scorer_failure",
                    epistemic_type="UNKNOWN",
                    summary="Escalation provider construction failed.",
                    key_findings=[],
                    eval_model=esc_name,
                )
                calls.append((_ProviderStub(esc_name), "", ""))
                scores = esc_scores
            else:
                esc_name = escalation.name
                if not self._check_budget(esc_name, tracker, cfg):
                    calls.append((_ProviderStub(esc_name), "", ""))
                    scores = self._make_budget_exhausted_result(esc_name, cfg)
                else:
                    esc_scores, esc_raw, esc_ph = self._call_provider_once(escalation, doc)
                    esc_scores = self._apply_priority_tier(esc_scores)
                    calls.append((escalation, esc_raw, esc_ph))
                    if esc_scores.reject_reason != "scorer_failure":
                        self._increment_and_save(esc_name, tracker)
                    scores = esc_scores

        return scores, calls

    def _check_budget(self, provider_name: str, tracker: Optional[dict], cfg) -> bool:
        """Return True if provider_name has remaining daily budget (or enforcement disabled)."""
        if tracker is None:
            return True
        from packages.research.evaluation.budget import is_budget_available
        cap = cfg.budget.per_provider.get(provider_name)
        return is_budget_available(provider_name, cap, tracker)

    def _increment_and_save(self, provider_name: str, tracker: Optional[dict]) -> None:
        """Increment provider call count and persist tracker (no-op when tracker is None)."""
        if tracker is None:
            return
        from packages.research.evaluation.budget import increment_provider_count, save_budget_tracker
        increment_provider_count(provider_name, tracker)
        save_budget_tracker(tracker, self._budget_tracker_path)

    def _make_budget_exhausted_result(self, provider_name: str, cfg) -> ScoringResult:
        """Return a fail-closed REJECT result for a budget-exhausted provider."""
        from packages.research.evaluation.scoring import _compute_composite
        composite = _compute_composite(1, 1, 1, 1)
        return ScoringResult(
            relevance=1, novelty=1, actionability=1, credibility=1,
            total=4,
            composite_score=composite,
            priority_tier=self._priority_tier or cfg.default_priority_tier,
            reject_reason="budget_exhausted",
            epistemic_type="UNKNOWN",
            summary=f"Provider {provider_name} daily budget exhausted.",
            key_findings=[],
            eval_model=provider_name,
        )

    def _call_provider_once(
        self, provider: EvalProvider, doc: EvalDocument
    ) -> Tuple[ScoringResult, str, str]:
        """Call a single provider fail-closed.

        Returns (ScoringResult, raw_output, prompt_hash). On any exception
        returns a fail-closed REJECT result (scorer_failure) rather than
        propagating — never escalates a failed primary call.
        """
        from packages.research.evaluation.scoring import (
            score_document_with_metadata,
            _compute_composite,
        )
        from packages.research.evaluation.config import get_eval_config
        try:
            return score_document_with_metadata(doc, provider)
        except Exception:
            composite = _compute_composite(1, 1, 1, 1)
            failure_scores = ScoringResult(
                relevance=1, novelty=1, actionability=1, credibility=1,
                total=4,
                composite_score=composite,
                priority_tier=self._priority_tier or get_eval_config().default_priority_tier,
                reject_reason="scorer_failure",
                epistemic_type="UNKNOWN",
                summary="Provider exception — could not evaluate document.",
                key_findings=[],
                eval_model=provider.name,
            )
            return failure_scores, "", ""

    def _apply_priority_tier(self, scores: ScoringResult) -> ScoringResult:
        """Apply the configured priority tier to scores.

        Must be called before checking scores.gate so the gate uses the
        correct threshold for the configured tier.
        """
        from packages.research.evaluation.config import get_eval_config
        if self._priority_tier is not None:
            return dataclasses.replace(scores, priority_tier=self._priority_tier)
        elif scores.priority_tier == "priority_3":
            cfg_default = get_eval_config().default_priority_tier
            if cfg_default != "priority_3":
                return dataclasses.replace(scores, priority_tier=cfg_default)
        return scores

    def _build_provider_event(
        self,
        doc: EvalDocument,
        provider: EvalProvider,
        raw_output: str,
        prompt_hash: str,
        now: str,
    ):
        """Build a ProviderEvent for one scoring attempt."""
        from packages.research.evaluation.artifacts import ProviderEvent, compute_output_hash
        from packages.research.evaluation.providers import get_provider_metadata
        from packages.research.evaluation.scoring import SCORING_PROMPT_TEMPLATE_ID
        meta = get_provider_metadata(provider)
        return ProviderEvent(
            provider_name=meta["provider_name"],
            model_id=meta["model_id"],
            prompt_template_id=SCORING_PROMPT_TEMPLATE_ID,
            prompt_template_version=prompt_hash,
            generation_params=meta["generation_params"],
            source_chunk_refs=[doc.doc_id],
            timestamp=now,
            output_hash=compute_output_hash(raw_output),
            raw_output=None,  # keep artifacts lightweight by default
        )

    def _get_escalation_provider(self) -> EvalProvider:
        """Return the escalation provider, constructing from config if needed."""
        if self._escalation_provider is not None:
            return self._escalation_provider
        from packages.research.evaluation.config import get_eval_config
        cfg = get_eval_config()
        return get_provider(cfg.routing.escalation_provider)


def evaluate_document(
    doc: EvalDocument,
    provider_name: Optional[str] = None,
    artifacts_dir: Optional[Path] = None,
    priority_tier: Optional[str] = None,
    budget_tracker_path: Optional[Path] = None,
    **kwargs,
) -> GateDecision:
    """Module-level convenience function for one-shot document evaluation.

    When provider_name is None (the default), routing config is honored:
    route mode uses cfg.routing.primary_provider; direct mode falls back to
    "manual". An explicit provider_name always uses direct mode (no escalation).

    Budget enforcement is active by default: per-provider daily caps from config
    are enforced using the standard tracker at
    artifacts/research/budget_tracker.json. Local providers (manual, ollama) are
    always uncapped regardless of this setting.

    Args:
        doc: The document to evaluate.
        provider_name: Provider identifier. If None, selected from routing config.
        artifacts_dir: Optional path for artifact persistence.
        priority_tier: Priority tier for gate thresholds (default: config default).
            Use "priority_1" for trusted/high-signal documents (lower threshold).
            Use "priority_4" for low-trust sources (higher threshold).
        budget_tracker_path: Path to per-provider daily budget tracker JSON. When
            None (the default), the standard path
            artifacts/research/budget_tracker.json is used and caps are enforced.
            Pass an explicit Path to redirect (e.g., in tests). Use
            DocumentEvaluator directly with budget_tracker_path=None to bypass
            enforcement entirely.
        **kwargs: Passed to get_provider() (e.g., model= for OllamaProvider).

    Returns:
        GateDecision with gate (ACCEPT|REVIEW|REJECT), scores, and metadata.
    """
    from packages.research.evaluation.config import get_eval_config
    from packages.research.evaluation.budget import _DEFAULT_TRACKER_PATH
    cfg = get_eval_config()

    if budget_tracker_path is None:
        budget_tracker_path = _DEFAULT_TRACKER_PATH

    if provider_name is None:
        # Auto-select: honor routing config.
        routing_mode = cfg.routing.mode
        provider_name = cfg.routing.primary_provider if routing_mode == "route" else "manual"
    else:
        # Explicit provider: caller owns the provider choice; use direct mode.
        routing_mode = "direct"

    provider = get_provider(provider_name, **kwargs)
    evaluator = DocumentEvaluator(
        provider=provider,
        artifacts_dir=artifacts_dir,
        priority_tier=priority_tier,
        routing_mode=routing_mode,
        budget_tracker_path=budget_tracker_path,
    )
    return evaluator.evaluate(doc)
