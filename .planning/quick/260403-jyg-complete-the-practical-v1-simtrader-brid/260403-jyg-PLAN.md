---
phase: quick-260403-jyg
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/research/integration/__init__.py
  - packages/research/integration/hypothesis_bridge.py
  - packages/research/integration/validation_feedback.py
  - packages/polymarket/rag/knowledge_store.py
  - tests/test_ris_simtrader_bridge.py
  - docs/features/FEATURE-ris-simtrader-bridge-v1.md
  - docs/dev_logs/2026-04-03_ris_r5_simtrader_bridge.md
  - docs/CURRENT_STATE.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "A ResearchBrief or EnhancedPrecheck can be converted into a structured hypothesis candidate dict"
    - "A hypothesis candidate can be registered into the existing hypothesis registry with evidence provenance"
    - "Validation outcomes (CONSISTENT_WITH_RESULTS, CONTRADICTED) can update claim validation_status in KnowledgeStore"
    - "The full path from research finding to hypothesis to feedback is exercised by tests"
  artifacts:
    - path: "packages/research/integration/hypothesis_bridge.py"
      provides: "Research-to-hypothesis bridge: brief_to_candidate(), register_research_hypothesis()"
      min_lines: 80
    - path: "packages/research/integration/validation_feedback.py"
      provides: "Validation feedback hook: record_validation_outcome() updates KnowledgeStore claim statuses"
      min_lines: 50
    - path: "packages/polymarket/rag/knowledge_store.py"
      provides: "New update_claim_validation_status() method on KnowledgeStore"
      contains: "def update_claim_validation_status"
    - path: "tests/test_ris_simtrader_bridge.py"
      provides: "Deterministic offline tests for bridge and feedback"
      min_lines: 100
  key_links:
    - from: "packages/research/integration/hypothesis_bridge.py"
      to: "packages/research/hypotheses/registry.py"
      via: "append_event() and stable_hypothesis_id()"
      pattern: "from packages\\.research\\.hypotheses\\.registry import"
    - from: "packages/research/integration/hypothesis_bridge.py"
      to: "packages/research/synthesis/report.py"
      via: "ResearchBrief / CitedEvidence dataclasses"
      pattern: "from packages\\.research\\.synthesis\\.report import"
    - from: "packages/research/integration/validation_feedback.py"
      to: "packages/polymarket/rag/knowledge_store.py"
      via: "update_claim_validation_status()"
      pattern: "KnowledgeStore"
---

<objective>
Complete the practical v1 SimTrader bridge side of RIS_07 Integration. Build the
smallest real, honest bridge between RIS research outputs and the hypothesis
registry / simulator workflow, plus a feedback hook so validation outcomes can
update claim statuses in the knowledge store.

Purpose: RIS findings currently dead-end at ResearchBrief / EnhancedPrecheck
dataclasses. This plan connects them to the hypothesis registry (existing) and
adds a feedback path so simulator validation results can mark cited evidence as
CONSISTENT_WITH_RESULTS or CONTRADICTED -- closing the research-to-validation
loop described in RIS_07 Section 3 at the v1 / practical level.

Output:
- `packages/research/integration/` module with hypothesis_bridge.py and validation_feedback.py
- New `update_claim_validation_status()` method on KnowledgeStore
- Deterministic test suite
- Feature doc, dev log, CURRENT_STATE update
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/reference/RAGfiles/RIS_07_INTEGRATION.md (sections 3 and 6 -- SimTrader bridge spec)
@packages/research/hypotheses/registry.py (existing registry: stable_hypothesis_id, append_event, register_from_candidate, update_status, experiment_init, experiment_run)
@packages/research/synthesis/report.py (ResearchBrief, EnhancedPrecheck, CitedEvidence dataclasses)
@packages/research/synthesis/__init__.py (public synthesis exports)
@packages/polymarket/rag/knowledge_store.py (KnowledgeStore: add_claim, query_claims, derived_claims table with validation_status column)
@packages/research/hypotheses/__init__.py
@packages/research/__init__.py

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From packages/research/synthesis/report.py:
```python
@dataclass
class CitedEvidence:
    claim_text: str
    source_doc_id: str
    source_title: str
    source_type: str
    trust_tier: str
    confidence: float
    freshness_note: str
    provenance_url: str

@dataclass
class ResearchBrief:
    topic: str
    generated_at: str
    sources_queried: int
    sources_cited: int
    overall_confidence: str          # HIGH | MEDIUM | LOW
    summary: str
    key_findings: list               # list[dict] keys: title, description, source, confidence_tier
    contradictions: list             # list[dict] keys: claim_a, claim_b, sources
    actionability: dict              # keys: can_inform_strategy, target_track, suggested_next_step, estimated_impact
    knowledge_gaps: list             # list[str]
    cited_sources: list              # list[CitedEvidence]

@dataclass
class EnhancedPrecheck:
    recommendation: str              # GO | CAUTION | STOP
    idea: str
    supporting: list                 # list[CitedEvidence]
    contradicting: list              # list[CitedEvidence]
    risk_factors: list               # list[str]
    past_failures: list              # list[str]
    knowledge_gaps: list             # list[str]
    validation_approach: str
    timestamp: str
    overall_confidence: str          # HIGH | MEDIUM | LOW
    stale_warning: bool = False
    evidence_gap: str = ""
    precheck_id: str = ""
```

From packages/research/hypotheses/registry.py:
```python
SCHEMA_VERSION = "hypothesis_registry_v0"
VALID_STATUSES = ("proposed", "testing", "validated", "rejected", "parked")

def stable_hypothesis_id(candidate: dict) -> str: ...
def append_event(path: str | Path, event: dict) -> None: ...
def get_latest(path: str | Path, hypothesis_id: str) -> dict: ...
def register_from_candidate(registry_path, candidate_file, rank, title=None, notes=None) -> str: ...
def update_status(registry_path, hypothesis_id, status, reason) -> None: ...
def experiment_init(outdir, hypothesis_id, registry_snapshot) -> Path: ...
def experiment_run(outdir, hypothesis_id, registry_snapshot) -> Path: ...
```

From packages/polymarket/rag/knowledge_store.py:
```python
class KnowledgeStore:
    def __init__(self, db_path: str | Path = DEFAULT_KNOWLEDGE_DB_PATH) -> None: ...
    def add_claim(self, *, claim_text, claim_type, confidence, trust_tier,
                  validation_status="UNTESTED", lifecycle="active", actor, ...) -> str: ...
    def get_claim(self, claim_id: str) -> Optional[dict]: ...
    def query_claims(self, *, include_archived=False, include_superseded=False,
                     apply_freshness=True) -> list[dict]: ...
    # NOTE: No update_claim_validation_status() method exists yet -- Task 1 adds it.
    # derived_claims table has: validation_status TEXT NOT NULL DEFAULT 'UNTESTED'
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: KnowledgeStore update method + hypothesis bridge + validation feedback</name>
  <files>
    packages/polymarket/rag/knowledge_store.py
    packages/research/integration/__init__.py
    packages/research/integration/hypothesis_bridge.py
    packages/research/integration/validation_feedback.py
  </files>
  <behavior>
    - Test: KnowledgeStore.update_claim_validation_status(claim_id, new_status, actor) updates the validation_status and updated_at columns for an existing claim
    - Test: update_claim_validation_status raises ValueError for unknown claim_id
    - Test: update_claim_validation_status rejects invalid status strings (only UNTESTED, CONSISTENT_WITH_RESULTS, CONTRADICTED, INCONCLUSIVE are valid)
    - Test: brief_to_candidate(brief) converts a ResearchBrief into a structured hypothesis candidate dict with fields: name, source_brief_topic, hypothesis_text, evidence_doc_ids, suggested_parameters, strategy_type, overall_confidence, generated_at
    - Test: brief_to_candidate preserves all evidence_doc_ids from the brief's cited_sources
    - Test: precheck_to_candidate(precheck) converts an EnhancedPrecheck into a hypothesis candidate dict
    - Test: register_research_hypothesis(registry_path, candidate) writes to the JSONL registry with event_type="registered", source.origin="research_bridge", and preserves evidence_doc_ids
    - Test: record_validation_outcome(store, hypothesis_id, claim_ids, outcome, reason) updates validation_status for all specified claim_ids in the KnowledgeStore
    - Test: record_validation_outcome with outcome="confirmed" sets CONSISTENT_WITH_RESULTS; outcome="contradicted" sets CONTRADICTED; outcome="inconclusive" sets INCONCLUSIVE
    - Test: record_validation_outcome returns a summary dict with counts of updated/failed/not_found claims
  </behavior>
  <action>
    **Step 1: Add update_claim_validation_status() to KnowledgeStore (knowledge_store.py)**

    Add a new method to the KnowledgeStore class after get_claim():
    ```python
    VALID_VALIDATION_STATUSES = ("UNTESTED", "CONSISTENT_WITH_RESULTS", "CONTRADICTED", "INCONCLUSIVE")

    def update_claim_validation_status(
        self,
        claim_id: str,
        validation_status: str,
        actor: str,
    ) -> None:
    ```
    - Validate status is in VALID_VALIDATION_STATUSES, raise ValueError if not.
    - Check claim exists via get_claim(claim_id), raise ValueError("claim not found: {claim_id}") if None.
    - Execute UPDATE derived_claims SET validation_status=?, updated_at=? WHERE id=?
    - Commit.

    These validation status values match RIS_07 Section 3 (CONSISTENT_WITH_RESULTS for KEEP, CONTRADICTED for AUTO_DISABLE) plus INCONCLUSIVE as a safe middle ground. UNTESTED remains the default for never-validated claims.

    **Step 2: Create packages/research/integration/__init__.py**

    Re-export public API:
    - brief_to_candidate, precheck_to_candidate, register_research_hypothesis from hypothesis_bridge
    - record_validation_outcome from validation_feedback

    **Step 3: Create hypothesis_bridge.py**

    Module: `packages/research/integration/hypothesis_bridge.py`

    Constants:
    - BRIDGE_ACTOR = "research_bridge_v1"
    - BRIDGE_SCHEMA_VERSION = "research_hypothesis_v0"

    Function `brief_to_candidate(brief: ResearchBrief) -> dict`:
    - Extract evidence_doc_ids from brief.cited_sources (list of CitedEvidence) -- deduplicated, non-empty source_doc_id values.
    - Derive name from topic (slugify: lowercase, replace spaces with underscores, truncate to 60 chars) + "_v1".
    - Derive hypothesis_text from brief.summary (or first key_finding description if summary is the "Insufficient evidence" fallback).
    - Extract strategy_type from brief.actionability["target_track"] (default "general").
    - Extract suggested_parameters from brief.actionability (can_inform_strategy, estimated_impact, suggested_next_step).
    - Return dict with keys: name, source_brief_topic, hypothesis_text, evidence_doc_ids, suggested_parameters, strategy_type, overall_confidence, generated_at.

    Function `precheck_to_candidate(precheck: EnhancedPrecheck) -> dict`:
    - Similar to brief_to_candidate but extracts from precheck fields.
    - evidence_doc_ids from precheck.supporting CitedEvidence list.
    - hypothesis_text from precheck.idea + recommendation context.
    - Return same dict shape.

    Function `register_research_hypothesis(registry_path: str | Path, candidate: dict) -> str`:
    - Build a hypothesis_id using stable_hypothesis_id() from registry.py. The candidate dict needs a "kind" key for the identity payload -- use kind="research_candidate" with "name" as the identity field. Build a small identity dict: {"kind": "research_candidate", "name": candidate["name"]} and compute sha256[:16] -> "hyp_{digest}".
    - Actually: do NOT reuse stable_hypothesis_id() directly (it expects candidate_id or dimension_key structures). Instead compute the ID inline: `hyp_{sha256(json.dumps({"kind":"research_candidate","name":candidate["name"]}, sort_keys=True))[:16]}`.
    - Build the registry event dict with: schema_version=BRIDGE_SCHEMA_VERSION, hypothesis_id, title=candidate["name"], created_at, status="proposed", source={"origin":"research_bridge", "brief_topic": candidate["source_brief_topic"], "evidence_doc_ids": candidate["evidence_doc_ids"]}, assumptions=[candidate["hypothesis_text"]], metrics_plan={"strategy_type": candidate["strategy_type"], "suggested_parameters": candidate["suggested_parameters"]}, stop_conditions=[], notes=[], status_reason=None, event_type="registered", event_at=created_at.
    - Call append_event(registry_path, event).
    - Return hypothesis_id.

    **Step 4: Create validation_feedback.py**

    Module: `packages/research/integration/validation_feedback.py`

    OUTCOME_MAP = {"confirmed": "CONSISTENT_WITH_RESULTS", "contradicted": "CONTRADICTED", "inconclusive": "INCONCLUSIVE"}

    Function `record_validation_outcome(store: KnowledgeStore, hypothesis_id: str, claim_ids: list[str], outcome: str, reason: str) -> dict`:
    - Validate outcome is in OUTCOME_MAP.keys(), raise ValueError if not.
    - Map outcome to validation_status via OUTCOME_MAP.
    - actor = f"validation_feedback:{hypothesis_id}"
    - For each claim_id in claim_ids: try store.update_claim_validation_status(claim_id, validation_status, actor). Track updated/failed/not_found counts.
    - Return {"hypothesis_id": hypothesis_id, "outcome": outcome, "validation_status": validation_status, "reason": reason, "claims_updated": N, "claims_not_found": N, "claims_failed": N, "claim_ids": claim_ids}.

    Do NOT build an auto-test orchestration loop. This is a manual feedback function the operator or a future orchestrator calls after reviewing SimTrader results.
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_simtrader_bridge.py -x -v --tb=short</automated>
  </verify>
  <done>
    - KnowledgeStore has update_claim_validation_status() that correctly updates the SQLite row
    - brief_to_candidate() produces a well-shaped candidate dict from any ResearchBrief
    - precheck_to_candidate() produces a well-shaped candidate dict from any EnhancedPrecheck
    - register_research_hypothesis() writes a valid registry event to JSONL with evidence provenance
    - record_validation_outcome() updates all specified claim_ids in the knowledge store
    - All functions have no network calls, no LLM calls
  </done>
</task>

<task type="auto">
  <name>Task 2: Regression + docs + dev log</name>
  <files>
    docs/features/FEATURE-ris-simtrader-bridge-v1.md
    docs/dev_logs/2026-04-03_ris_r5_simtrader_bridge.md
    docs/CURRENT_STATE.md
  </files>
  <action>
    **Step 1: Run full regression suite.**
    ```
    python -m pytest tests/ -q --tb=line
    ```
    Confirm zero new failures. Report exact counts.

    **Step 2: Run import smoke test.**
    ```
    python -c "from packages.research.integration import brief_to_candidate, precheck_to_candidate, register_research_hypothesis, record_validation_outcome; print('bridge imports OK')"
    ```

    **Step 3: Run CLI smoke test.**
    ```
    python -m polytool --help
    ```
    Confirm no import errors.

    **Step 4: Create docs/features/FEATURE-ris-simtrader-bridge-v1.md.**

    Document:
    - What the bridge does (research finding -> hypothesis candidate -> registry entry)
    - What the feedback hook does (validation outcome -> claim status update)
    - Functions and their signatures
    - Example flow: create a brief, convert to candidate, register, then record feedback
    - What is shipped (v1 practical bridge) vs what is deferred (full R5/v2 autonomous orchestration: auto-test loop, auto-promotion, Discord approval integration)

    **Step 5: Create docs/dev_logs/2026-04-03_ris_r5_simtrader_bridge.md.**

    Include: files changed and why, commands run + output, test results, what bridge behavior is truly shipped now (manual bridge functions -- no auto-loop), what remains deferred (full R5/v2 automation: auto-test orchestration, auto-hypothesis promotion, Discord approval flow, scheduled re-validation).

    **Step 6: Update docs/CURRENT_STATE.md.**

    Add a section under the RIS heading (or create one if needed) noting:
    - RIS SimTrader bridge v1 shipped: research findings can be converted to hypothesis candidates and registered
    - Validation feedback hook shipped: simulator outcomes can update claim validation_status (CONSISTENT_WITH_RESULTS / CONTRADICTED / INCONCLUSIVE)
    - Full autonomous R5/v2 orchestration remains deferred
    - New module: packages/research/integration/
  </action>
  <verify>
    <automated>python -m pytest tests/ -q --tb=line 2>&1 | tail -5</automated>
  </verify>
  <done>
    - Full regression suite passes with zero new failures
    - Import smoke test passes
    - CLI smoke test passes
    - Feature doc exists at docs/features/FEATURE-ris-simtrader-bridge-v1.md
    - Dev log exists at docs/dev_logs/2026-04-03_ris_r5_simtrader_bridge.md with honest accounting of what shipped vs deferred
    - docs/CURRENT_STATE.md updated with bridge status
  </done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_ris_simtrader_bridge.py -x -v --tb=short` -- all bridge tests pass
2. `python -m pytest tests/ -q --tb=line` -- full suite, zero new failures
3. `python -c "from packages.research.integration import brief_to_candidate, register_research_hypothesis, record_validation_outcome; print('OK')"` -- imports work
4. `python -m polytool --help` -- CLI loads without import errors
</verification>

<success_criteria>
- A ResearchBrief can be converted to a hypothesis candidate and registered in one function-call chain
- An EnhancedPrecheck can be converted to a hypothesis candidate and registered
- Validation outcomes update claim validation_status in the KnowledgeStore (SQLite)
- Evidence provenance (doc_ids) flows through from brief -> candidate -> registry event
- No network calls, no LLM calls, no fake autonomous loop
- All existing tests still pass
- Docs honestly state what is v1 practical bridge vs what is deferred to R5/v2
</success_criteria>

<output>
After completion, create `.planning/quick/260403-jyg-complete-the-practical-v1-simtrader-brid/260403-jyg-SUMMARY.md`
</output>
