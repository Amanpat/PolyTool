# RIS Phase 2 Audit - Part 1: Evaluation Gate

Requested files missing from this workspace: `packages/research/evaluation/models.py`, `packages/research/evaluation/batch.py`, `packages/research/evaluation/prompts.py`, `packages/research/evaluation/cache.py`.

### Question 1: Providers
**Status:** MISSING
**Evidence:** `packages/research/evaluation/providers.py:35,58,96` defines only `EvalProvider`, `ManualProvider`, and `OllamaProvider`; `packages/research/evaluation/providers.py:178-189` recognizes `gemini` and `deepseek` names but raises `ValueError` after the cloud guard passes; `tools/cli/research_eval.py:512-515` still labels `gemini`, `deepseek`, `openai`, and `anthropic` as "not yet implemented". No `GeminiFlashProvider`, `DeepSeekV3Provider`, `OpenAICompatibleProvider`, or Gemini `response_schema` call exists in the current evaluation source.
**Code snippet:**
```python
    elif name in _CLOUD_PROVIDERS:
        # Known cloud provider: require explicit operator opt-in
        if os.environ.get(_CLOUD_GUARD_ENV_VAR, "") != "1":
            raise PermissionError(
                f"Cloud provider '{name}' requires {_CLOUD_GUARD_ENV_VAR}=1 to be set. "
                "Local providers (manual, ollama) work without this flag."
            )
        # Env var is set - recognized but not yet implemented
        raise ValueError(
            f"Cloud provider '{name}' is recognized but not yet implemented. "
```

### Question 2: Fail-closed
**Status:** PARTIAL
**Evidence:** `packages/research/evaluation/evaluator.py:188-205` converts provider exceptions into `ScoringResult(... reject_reason="scorer_failure")`; `packages/research/evaluation/types.py:82-84` forces `scorer_failure` to gate `REJECT`; `packages/research/ingestion/pipeline.py:148-162` rejects any `GateDecision.gate == "REJECT"` before storage, so scorer failure cannot auto-accept a document; `packages/research/ingestion/review_integration.py:10-13,35-39` and `packages/research/metrics.py:171,221-224` define downstream `blocked/BLOCKED` dispositions, but `packages/research/evaluation/types.py:70-100,104-110` exposes gate values only as `ACCEPT | REVIEW | REJECT`. There is no multi-provider chain, so "all providers fail" currently collapses to a single-provider fail-closed reject.
**Code snippet:**
```python
            scores, raw_output, prompt_hash = score_document_with_metadata(doc, self._provider)
        except Exception:
            composite = _compute_composite(1, 1, 1, 1)
            from packages.research.evaluation.types import ScoringResult
            scores = ScoringResult(
                relevance=1, novelty=1, actionability=1, credibility=1,
                total=4,
                composite_score=composite,
                priority_tier=self._priority_tier or get_eval_config().default_priority_tier,
                reject_reason="scorer_failure",
```

### Question 3: Scoring
**Status:** PARTIAL
**Evidence:** `packages/research/evaluation/scoring.py:40-55` computes `relevance*0.30 + novelty*0.25 + actionability*0.25 + credibility*0.20`, not the requested `relevance*0.30 + credibility*0.30 + novelty*0.20 + actionability*0.20`; `packages/research/evaluation/config.py:39-42,106-112` loads floors only for `relevance` and `credibility` at `2`; `packages/research/evaluation/types.py:90-100` enforces only configured floors before thresholding; `packages/research/evaluation/types.py:64-67` exposes `simple_sum_score` as a diagnostic alias for `total`.
**Code snippet:**
```python
    return (
        relevance * w.get("relevance", 0.30)
        + novelty * w.get("novelty", 0.25)
        + actionability * w.get("actionability", 0.25)
        + credibility * w.get("credibility", 0.20)
    )
```

### Question 4: Routing
**Status:** MISSING
**Evidence:** `packages/research/evaluation/evaluator.py:61-75` stores a single provider on `self._provider`; `packages/research/evaluation/evaluator.py:188-205` performs one `score_document_with_metadata(doc, self._provider)` call and fail-closes on exception instead of escalating or falling back; `packages/research/evaluation/types.py:104-110` defines `GateDecision` without any `routing` field; `packages/research/evaluation/artifacts.py:65-98` stores only a singular `provider_event`, not `provider_events` or `routing_decision`; `packages/research/ingestion/review_integration.py:64,111-145` and `packages/research/metrics.py:190-213` expect routing metadata that the evaluator does not currently produce. No score range triggers escalation, and no provider exception triggers fallback; provider failure goes directly to fail-closed `REJECT`.
**Code snippet:**
```python
@dataclass
class GateDecision:
    """Final gate decision for a document."""
    gate: str  # ACCEPT | REVIEW | REJECT
    scores: Optional[ScoringResult]
    hard_stop: Optional[HardStopResult]
    doc_id: str
    timestamp: str
```

### Question 5: Review queue
**Status:** CONFIRMED
**Evidence:** `packages/polymarket/rag/knowledge_store.py:187-229` creates `pending_review` and `pending_review_history`; `packages/polymarket/rag/knowledge_store.py:616-736` enqueues review items; `packages/polymarket/rag/knowledge_store.py:807-905` resolves them with `accept`, `reject`, or `defer`; `tools/cli/research_review.py:7-12,223-297` implements a `research-review` CLI with `list`, `inspect`, `accept`, `reject`, and `defer`; `tests/test_ris_review_queue.py:257-287` verifies operator accept/reject behavior.
**Code snippet:**
```python
Usage:
  python -m polytool research-review list
  python -m polytool research-review list --status all --json
  python -m polytool research-review inspect <REVIEW_ITEM_ID>
  python -m polytool research-review accept <REVIEW_ITEM_ID> --by analyst --notes "Reviewed and approved"
  python -m polytool research-review reject <REVIEW_ITEM_ID> --by analyst --notes "Low usefulness"
  python -m polytool research-review defer <REVIEW_ITEM_ID> --by analyst --notes "Need more context"
```

### Question 6: Budget
**Status:** PARTIAL
**Evidence:** `config/ris_eval_config.json:22-35` contains a placeholder `budget` section with `daily_global_cap`, `manual_reserve`, and `per_source`; `packages/research/evaluation/config.py:59-69` defines `EvalConfig` without any budget fields; `packages/research/evaluation/config.py:97-128` loads only `scoring`, `acceptance_gates`, and `defaults`; source search under `packages/research/evaluation/*.py` found no daily request counters, per-source cap enforcement, or manual reserve logic. The config values exist, but they are not wired into runtime evaluation behavior.
**Code snippet:**
```json
  "budget": {
    "_comment": "Budget caps placeholder -- implemented in a later Phase 2 plan.",
    "daily_global_cap": 200,
    "manual_reserve": 10,
    "per_source": {
      "academic": 50,
      "reddit": 40,
      "twitter": 30,
```
