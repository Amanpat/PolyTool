# FEATURE: RIS SimTrader Bridge v1

**Status:** Shipped (2026-04-03)
**Module:** `packages/research/integration/`
**Plan:** quick-260403-jyg

---

## What it does

The RIS SimTrader Bridge v1 closes the gap between research outputs and the
simulation/validation workflow. Before this feature, ResearchBrief and
EnhancedPrecheck objects were dead-end dataclasses -- they contained rich
cited evidence but had no path into the hypothesis registry or the
KnowledgeStore feedback loop.

This bridge provides two connection paths:

### 1. Research Finding -> Hypothesis Registry

Research findings can now be converted to hypothesis candidates and registered
in the existing JSONL hypothesis registry in a single function-call chain:

```python
from packages.research.integration import (
    brief_to_candidate,
    register_research_hypothesis,
)
from packages.research.synthesis import ReportSynthesizer

# Synthesize a brief from research
synthesizer = ReportSynthesizer()
brief = synthesizer.synthesize_brief("market maker spread capture", enriched_claims)

# Convert to candidate and register
candidate = brief_to_candidate(brief)
hyp_id = register_research_hypothesis("config/hypothesis_registry.jsonl", candidate)
# Returns: "hyp_a3f7c9d1e2b48f00" (stable deterministic ID)
```

### 2. Validation Outcome -> KnowledgeStore Feedback

After running SimTrader replay experiments, validation outcomes can update the
cited evidence claims in the KnowledgeStore:

```python
from packages.research.integration import record_validation_outcome
from packages.polymarket.rag.knowledge_store import KnowledgeStore

ks = KnowledgeStore()
result = record_validation_outcome(
    store=ks,
    hypothesis_id="hyp_a3f7c9d1e2b48f00",
    claim_ids=["claim_id_1", "claim_id_2"],
    outcome="confirmed",           # or "contradicted" | "inconclusive"
    reason="Gate 2 sweep: 8/10 tapes showed positive net PnL.",
)
# result: {"claims_updated": 2, "claims_not_found": 0, "claims_failed": 0, ...}
```

---

## Functions

### `brief_to_candidate(brief: ResearchBrief) -> dict`

Converts a ResearchBrief into a hypothesis candidate dict suitable for
`register_research_hypothesis()`.

**Extracts:**
- `name`: slugified topic + "_v1" (e.g., `market_maker_spread_capture_v1`)
- `source_brief_topic`: original topic string
- `hypothesis_text`: brief summary (or first key finding if summary is the
  empty-brief fallback)
- `evidence_doc_ids`: deduplicated, non-empty source_doc_ids from cited_sources
- `strategy_type`: from `actionability["target_track"]` (default `"general"`)
- `suggested_parameters`: structured dict with can_inform_strategy,
  estimated_impact, suggested_next_step
- `overall_confidence`: HIGH / MEDIUM / LOW
- `generated_at`: brief.generated_at

### `precheck_to_candidate(precheck: EnhancedPrecheck) -> dict`

Same dict shape as `brief_to_candidate`. Extracts from precheck fields:
- `evidence_doc_ids`: from precheck.supporting CitedEvidence list only
- `hypothesis_text`: `"[{recommendation}] {idea}. Validation: {validation_approach}"`
- `strategy_type`: inferred from keyword matching in idea text

### `register_research_hypothesis(registry_path: str | Path, candidate: dict) -> str`

Writes a JSONL event to the registry with:
- `event_type: "registered"`
- `status: "proposed"`
- `source.origin: "research_bridge"`
- `source.evidence_doc_ids`: propagated from candidate
- `hypothesis_id`: deterministic `hyp_{sha256[:16]}` from candidate name

The registry is append-only. Calling this function twice with the same
candidate appends a second event but does not raise an error.

**Returns:** hypothesis_id string.

### `record_validation_outcome(store, hypothesis_id, claim_ids, outcome, reason) -> dict`

Maps a SimTrader validation result to KnowledgeStore claim status updates.

**Outcome mapping:**
- `"confirmed"` -> `CONSISTENT_WITH_RESULTS`
- `"contradicted"` -> `CONTRADICTED`
- `"inconclusive"` -> `INCONCLUSIVE`

Claims not found in the store are counted as `claims_not_found` and skipped
silently. Raises `ValueError` if outcome is not one of the three valid strings.

**Returns summary dict:**
```python
{
    "hypothesis_id": "hyp_abc...",
    "outcome": "confirmed",
    "validation_status": "CONSISTENT_WITH_RESULTS",
    "reason": "...",
    "claims_updated": N,
    "claims_not_found": N,
    "claims_failed": N,
    "claim_ids": [...],
}
```

### `KnowledgeStore.update_claim_validation_status(claim_id, validation_status, actor)`

New method on KnowledgeStore. Updates the `validation_status` and `updated_at`
columns for an existing derived claim.

**Valid statuses:** `UNTESTED`, `CONSISTENT_WITH_RESULTS`, `CONTRADICTED`, `INCONCLUSIVE`

Raises `ValueError` for unknown claim_id or invalid status.

---

## Example: Full flow

```python
from packages.polymarket.rag.knowledge_store import KnowledgeStore
from packages.research.synthesis import ReportSynthesizer
from packages.research.integration import (
    brief_to_candidate,
    register_research_hypothesis,
    record_validation_outcome,
)

# Step 1: Build a brief from research (offline, no LLM)
synthesizer = ReportSynthesizer()
brief = synthesizer.synthesize_brief("crypto momentum 5m", enriched_claims)

# Step 2: Convert to hypothesis candidate
candidate = brief_to_candidate(brief)

# Step 3: Register in hypothesis registry
hyp_id = register_research_hypothesis(
    "config/hypothesis_registry.jsonl",
    candidate
)

# Step 4: Run SimTrader experiment (separate workflow, operator decision)
# ... (operator runs Gate 2 sweep, reviews run_manifest.json) ...

# Step 5: Record validation outcome
ks = KnowledgeStore()
claim_ids = [ev.source_doc_id for ev in brief.cited_sources if ev.source_doc_id]
result = record_validation_outcome(
    store=ks,
    hypothesis_id=hyp_id,
    claim_ids=claim_ids,
    outcome="confirmed",
    reason="Gate 2: 7/10 crypto tapes positive net PnL.",
)
print(result["claims_updated"])  # e.g., 2
```

---

## What is shipped (v1 practical bridge)

- Manual bridge functions (no automated loop)
- Deterministic, offline operation (no network, no LLM calls)
- Evidence provenance (doc_ids) flows from brief/precheck -> candidate -> registry event
- Validation feedback updates SQLite claim validation_status
- 37 deterministic tests in `tests/test_ris_simtrader_bridge.py`

## What is deferred (R5 / v2 autonomous orchestration)

The following are explicitly NOT included in v1 and remain deferred:

- **Auto-test orchestration loop**: no automated "register -> run SimTrader -> record feedback" cycle
- **Auto-hypothesis promotion**: no automatic status change from "proposed" to "testing" on Gate 2 pass
- **Discord approval integration**: no approval-flow hooks for the feedback loop
- **Scheduled re-validation**: no cron job that re-evaluates claim statuses against new tape data
- **Full R5 synthesis path**: LLM-enhanced hypothesis generation from DeepSeek V3 (deferred per PLAN_OF_RECORD no-external-LLM policy)

The v1 bridge is a foundation for those features, not a replacement for operator judgment.

---

## Files

| File | Role |
|------|------|
| `packages/research/integration/__init__.py` | Public API re-exports |
| `packages/research/integration/hypothesis_bridge.py` | brief_to_candidate, precheck_to_candidate, register_research_hypothesis |
| `packages/research/integration/validation_feedback.py` | record_validation_outcome |
| `packages/polymarket/rag/knowledge_store.py` | Added update_claim_validation_status() |
| `tests/test_ris_simtrader_bridge.py` | 37 offline deterministic tests |
