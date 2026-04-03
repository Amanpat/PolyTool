---
phase: quick-260402-xbo
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/research/synthesis/report.py
  - packages/research/synthesis/precheck.py
  - packages/research/synthesis/__init__.py
  - tests/test_ris_report_synthesis.py
  - docs/features/FEATURE-ris-synthesis-engine-v1.md
  - docs/dev_logs/2026-04-03_ris_r3_report_and_precheck_synthesis.md
  - docs/CURRENT_STATE.md
autonomous: true
requirements: [RIS_05_synthesis_report, RIS_05_synthesis_precheck]
must_haves:
  truths:
    - "ReportSynthesizer can produce a structured research brief from a list of enriched evidence claims"
    - "ReportSynthesizer can produce an enhanced precheck with GO/CAUTION/STOP backed by explicit cited evidence"
    - "Reports include all RIS_05 sections: summary, key_findings, contradictions, actionability, knowledge_gaps, sources_cited"
    - "Citations are traceable to source documents via provenance data"
    - "Evidence tiers and staleness are reflected in synthesis output"
    - "Precheck output carries supporting and contradicting evidence with source attribution"
  artifacts:
    - path: "packages/research/synthesis/report.py"
      provides: "ReportSynthesizer class and dataclasses for structured report/precheck output"
      exports: ["ReportSynthesizer", "ResearchBrief", "EnhancedPrecheck", "CitedEvidence", "format_research_brief", "format_enhanced_precheck"]
    - path: "tests/test_ris_report_synthesis.py"
      provides: "Deterministic offline tests for report shape, citation formatting, contradiction handling, precheck contract"
      min_lines: 150
  key_links:
    - from: "packages/research/synthesis/report.py"
      to: "packages/research/ingestion/retriever.py"
      via: "consumes enriched claim dicts from query_knowledge_store_enriched()"
      pattern: "provenance_docs|contradiction_summary|staleness_note|effective_score"
    - from: "packages/research/synthesis/report.py"
      to: "packages/research/synthesis/precheck.py"
      via: "EnhancedPrecheck wraps/extends PrecheckResult output"
      pattern: "PrecheckResult|recommendation|supporting_evidence|contradicting_evidence"
---

<objective>
Build the report synthesis and enhanced precheck layers of the RIS_05 Synthesis Engine.

Purpose: RIS currently has a precheck runner that produces GO/CAUTION/STOP recommendations
and a retriever that returns enriched claims with provenance and contradictions, but there
is no module that synthesizes retrieved evidence into structured, cited research briefs or
into enhanced precheck outputs with explicit source attribution. This plan bridges that gap
so that RIS can turn retrieved evidence into actionable research artifacts.

Output:
- `packages/research/synthesis/report.py` — ReportSynthesizer class + dataclasses
- Enhanced precheck generation in the same module
- Deterministic test suite
- Feature doc + dev log + CURRENT_STATE update
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/reference/RAGfiles/RIS_05_SYNTHESIS_ENGINE.md
@D:/Coding Projects/Polymarket/PolyTool/packages/research/synthesis/precheck.py
@D:/Coding Projects/Polymarket/PolyTool/packages/research/synthesis/calibration.py
@D:/Coding Projects/Polymarket/PolyTool/packages/research/synthesis/__init__.py
@D:/Coding Projects/Polymarket/PolyTool/packages/research/ingestion/retriever.py
@D:/Coding Projects/Polymarket/PolyTool/packages/research/evaluation/types.py
@D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/rag/knowledge_store.py

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->
<!-- Executor should use these directly -- no codebase exploration needed. -->

From packages/research/evaluation/types.py:
```python
@dataclass
class EvalDocument:
    doc_id: str
    title: str
    author: str
    source_type: str
    source_url: str
    source_publish_date: Optional[str]
    body: str
    metadata: dict = field(default_factory=dict)

@dataclass
class ScoringResult:
    relevance: int
    novelty: int
    actionability: int
    credibility: int
    total: int
    epistemic_type: str
    summary: str
    key_findings: list
    eval_model: str
```

From packages/research/ingestion/retriever.py (query_knowledge_store_enriched return contract):
```python
# Each enriched claim dict contains:
# - id: str (claim ID)
# - claim_text: str
# - claim_type: str (empirical | normative | structural)
# - confidence: float
# - trust_tier: str
# - source_document_id: Optional[str]
# - freshness_modifier: float
# - effective_score: float
# - provenance_docs: list[dict]  # source_document rows
#     Each provenance doc: {id, title, author, source_type, source_url,
#                           source_publish_date, source_family, trust_tier, ...}
# - contradiction_summary: list[str]  # claim texts that CONTRADICT this claim
# - is_contradicted: bool
# - staleness_note: str  # "STALE" | "AGING" | ""
# - lifecycle: str  # "active" | "archived" | "superseded"
```

From packages/research/synthesis/precheck.py:
```python
@dataclass
class PrecheckResult:
    recommendation: str           # GO | CAUTION | STOP
    idea: str
    supporting_evidence: list     # list[str]
    contradicting_evidence: list  # list[str]
    risk_factors: list            # list[str]
    timestamp: str
    provider_used: str
    stale_warning: bool = False
    raw_response: str = ""
    precheck_id: str = ""
    reason_code: str = ""
    evidence_gap: str = ""
    review_horizon: str = ""
```

From packages/research/synthesis/precheck_ledger.py:
```python
LEDGER_SCHEMA_VERSION = "precheck_ledger_v2"
def append_precheck(result: PrecheckResult, ledger_path: Path | None = None) -> None
def list_prechecks(ledger_path: Path | None = None) -> list[dict]
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Build ReportSynthesizer module with dataclasses and deterministic tests</name>
  <files>
    packages/research/synthesis/report.py,
    packages/research/synthesis/__init__.py,
    tests/test_ris_report_synthesis.py
  </files>
  <behavior>
    --- ResearchBrief dataclass ---
    - Test 1: ResearchBrief has required fields: topic, generated_at, sources_queried, sources_cited, overall_confidence, summary, key_findings, contradictions, actionability, knowledge_gaps, cited_sources
    - Test 2: CitedEvidence dataclass has: claim_text, source_doc_id, source_title, source_type, trust_tier, confidence, freshness_note, provenance_url
    - Test 3: format_research_brief() returns non-empty markdown string with all section headings (Summary, Key Findings, Contradictions, Actionability Assessment, Knowledge Gaps, Sources Cited)
    --- EnhancedPrecheck dataclass ---
    - Test 4: EnhancedPrecheck has: recommendation, idea, supporting (list[CitedEvidence]), contradicting (list[CitedEvidence]), risk_factors, past_failures, knowledge_gaps, validation_approach, timestamp, overall_confidence
    - Test 5: format_enhanced_precheck() returns markdown with GO/CAUTION/STOP and cited evidence sections
    --- ReportSynthesizer.synthesize_brief() ---
    - Test 6: Given a list of enriched claims (matching retriever contract), synthesize_brief() returns a ResearchBrief with correct section population
    - Test 7: Claims with provenance_docs produce CitedEvidence entries with source attribution
    - Test 8: Contradicted claims (is_contradicted=True) appear in the contradictions section
    - Test 9: Stale claims (staleness_note="STALE") appear in knowledge_gaps with freshness warning
    - Test 10: Empty evidence list produces a brief with "insufficient evidence" in summary and empty key_findings
    --- ReportSynthesizer.synthesize_precheck() ---
    - Test 11: Given enriched claims + idea, synthesize_precheck() returns EnhancedPrecheck with recommendation
    - Test 12: Claims supporting the idea (high confidence, not contradicted) populate supporting list
    - Test 13: Claims contradicting the idea populate contradicting list with source citations
    - Test 14: When all evidence is stale, stale_warning is set and overall_confidence is LOW
    - Test 15: When no evidence exists, recommendation is CAUTION with evidence_gap flagged
    --- Citation formatting ---
    - Test 16: format_citation(CitedEvidence) produces "[doc_id] (source_type, trust_tier)" format
    - Test 17: Sources cited table in format_research_brief includes all unique sources with correct columns
    --- Contradiction handling ---
    - Test 18: When claims have both SUPPORTS and CONTRADICTS relations, contradictions section lists both sides with citations
    - Test 19: Unresolved contradictions are surfaced as unresolved questions
    --- Trust tier differentiation ---
    - Test 20: tier_1_primary claims rank higher in key_findings than tier_2_community claims
    - Test 21: Evidence confidence is reflected in overall_confidence (all high -> HIGH, mixed -> MEDIUM, all low -> LOW)
  </behavior>
  <action>
    Create `packages/research/synthesis/report.py` with:

    1. **Dataclasses:**
       - `CitedEvidence(claim_text, source_doc_id, source_title, source_type, trust_tier, confidence, freshness_note, provenance_url)` — a single piece of cited evidence
       - `ResearchBrief(topic, generated_at, sources_queried, sources_cited, overall_confidence, summary, key_findings, contradictions, actionability, knowledge_gaps, cited_sources)` — structured report matching RIS_05 format. key_findings is list[dict] with keys: title, description, source (CitedEvidence), confidence_tier. contradictions is list[dict] with keys: claim_a, claim_b, sources. actionability is dict with keys: can_inform_strategy (bool), target_track (str), suggested_next_step (str), estimated_impact (str). knowledge_gaps is list[str]. cited_sources is list[CitedEvidence].
       - `EnhancedPrecheck(recommendation, idea, supporting, contradicting, risk_factors, past_failures, knowledge_gaps, validation_approach, timestamp, overall_confidence, stale_warning, evidence_gap, precheck_id)` — enhanced precheck with cited evidence lists

    2. **ReportSynthesizer class:**
       - `__init__(self)` — no external dependencies, purely deterministic synthesis
       - `synthesize_brief(self, topic: str, enriched_claims: list[dict]) -> ResearchBrief` — takes enriched claims from `query_knowledge_store_enriched()` and produces a structured brief. Logic:
         - Extract CitedEvidence from each claim's provenance_docs
         - Sort claims by effective_score descending
         - Top N non-contradicted claims become key_findings
         - Contradicted claims (is_contradicted=True) go to contradictions section with both sides cited
         - Stale claims flagged in knowledge_gaps
         - overall_confidence derived from evidence quality: HIGH if avg confidence >= 0.8 and no stale, MEDIUM if mixed, LOW if mostly stale or low confidence
         - summary is a concatenation of top findings (not LLM-generated -- this is deterministic synthesis)
         - actionability assessment based on whether claims reference strategy tracks (market_maker, crypto, sports keywords in claim_text)
       - `synthesize_precheck(self, idea: str, enriched_claims: list[dict]) -> EnhancedPrecheck` — produces enhanced precheck. Logic:
         - Filter claims by keyword relevance to idea (case-insensitive substring match of idea keywords in claim_text)
         - Separate into supporting (not contradicted, confidence >= 0.6) and contradicting (is_contradicted or has contradiction_summary entries)
         - recommendation: GO if supporting > contradicting and no stale, STOP if contradicting > 2x supporting, CAUTION otherwise
         - Populate risk_factors from contradicting evidence
         - Flag knowledge_gaps when evidence is sparse (< 3 relevant claims)
         - Set stale_warning when all relevant evidence is STALE
         - Set evidence_gap when no relevant claims found

    3. **Format functions:**
       - `format_citation(evidence: CitedEvidence) -> str` — produces `[doc_id] (source_type, trust_tier)` string
       - `format_research_brief(brief: ResearchBrief) -> str` — produces full markdown with all RIS_05 sections and a sources cited table
       - `format_enhanced_precheck(precheck: EnhancedPrecheck) -> str` — produces markdown precheck with recommendation, evidence sections, and citations

    4. **Helper functions:**
       - `_extract_cited_evidence(claim: dict) -> CitedEvidence` — extracts from enriched claim dict
       - `_compute_overall_confidence(claims: list[dict]) -> str` — HIGH/MEDIUM/LOW from claim quality metrics
       - `_detect_strategy_relevance(claim_text: str) -> tuple[bool, str]` — keyword detection for actionability
       - `_idea_relevance_score(idea: str, claim_text: str) -> float` — simple keyword overlap score for precheck filtering

    Update `packages/research/synthesis/__init__.py` to export:
    `ReportSynthesizer, ResearchBrief, EnhancedPrecheck, CitedEvidence, format_research_brief, format_enhanced_precheck`

    Create `tests/test_ris_report_synthesis.py` with the 21 tests above. All tests use fixture data (hardcoded enriched claim dicts matching the retriever contract). No network, no LLM, no KnowledgeStore instantiation. Build fixture helper `_make_enriched_claim(claim_text, confidence, trust_tier, source_family, is_contradicted, staleness_note, provenance_docs)` that returns a dict matching the enriched claim contract.

    IMPORTANT: This is deterministic synthesis -- NO LLM calls. The synthesizer operates purely on the structured enriched claim data. LLM-based synthesis (DeepSeek V3) is a v2 feature deferred per RIS_05 spec. The current implementation assembles structured outputs from evidence metadata.

    IMPORTANT: Do not modify existing precheck.py run_precheck() or its tests. The EnhancedPrecheck is a parallel output type, not a replacement. Existing PrecheckResult remains unchanged.
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_report_synthesis.py -x -v --tb=short 2>&1 | head -80</automated>
  </verify>
  <done>
    - report.py exists with ReportSynthesizer, dataclasses, and format functions
    - __init__.py exports the new symbols
    - All 21+ tests pass
    - No existing tests broken (run full regression)
  </done>
</task>

<task type="auto">
  <name>Task 2: Docs, dev log, regression, and CURRENT_STATE update</name>
  <files>
    docs/features/FEATURE-ris-synthesis-engine-v1.md,
    docs/dev_logs/2026-04-03_ris_r3_report_and_precheck_synthesis.md,
    docs/CURRENT_STATE.md
  </files>
  <action>
    1. Run full regression: `python -m pytest tests/ -x -q --tb=short` and record exact counts.

    2. Run smoke test: `python -m polytool --help` to confirm CLI still loads.

    3. Create `docs/features/FEATURE-ris-synthesis-engine-v1.md` documenting:
       - What was built: ReportSynthesizer, ResearchBrief, EnhancedPrecheck, CitedEvidence
       - Output contracts: field-level documentation for each dataclass
       - Format functions: what markdown they produce
       - Evidence flow: enriched claims -> CitedEvidence -> structured sections
       - Trust tier handling in synthesis
       - Contradiction and staleness behavior
       - What is NOT built (deferred): LLM-based synthesis (DeepSeek V3), multi-model citation verification, iterative orchestrator loop, weekly digest, CLI commands for report generation, report storage/catalog, ClickHouse report indexing

    4. Create `docs/dev_logs/2026-04-03_ris_r3_report_and_precheck_synthesis.md` with:
       - Files changed and why
       - Commands run and output (test counts)
       - Output contract decisions (deterministic vs LLM, parallel vs replacement for PrecheckResult)
       - What in RIS_05 is now complete vs deferred
       - Architecture diagram showing evidence flow

    5. Update `docs/CURRENT_STATE.md`: add a section after the RIS entries noting that RIS_05 Synthesis Engine v1 is shipped (deterministic report/precheck synthesis from enriched evidence). Note deferred items.
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
    - Full regression passes with zero new failures
    - Feature doc exists at docs/features/FEATURE-ris-synthesis-engine-v1.md
    - Dev log exists at docs/dev_logs/2026-04-03_ris_r3_report_and_precheck_synthesis.md
    - CURRENT_STATE.md updated with RIS_05 synthesis status
  </done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_ris_report_synthesis.py -x -v --tb=short` — all synthesis tests pass
2. `python -m pytest tests/test_ris_precheck.py -x -v --tb=short` — existing precheck tests still pass (no regression)
3. `python -m pytest tests/ -x -q --tb=short` — full suite passes
4. `python -m polytool --help` — CLI loads without import errors
5. `python -c "from packages.research.synthesis import ReportSynthesizer, ResearchBrief, EnhancedPrecheck, CitedEvidence, format_research_brief, format_enhanced_precheck; print('imports OK')"` — all exports resolve
</verification>

<success_criteria>
- ReportSynthesizer.synthesize_brief() produces ResearchBrief with all RIS_05 sections from enriched evidence
- ReportSynthesizer.synthesize_precheck() produces EnhancedPrecheck with GO/CAUTION/STOP backed by cited evidence
- CitedEvidence traces every finding to a source document
- Contradictions are surfaced with both sides cited
- Evidence tiers and staleness are reflected in output confidence and warnings
- All new tests pass, all existing tests pass
- Feature doc and dev log document shipped behavior and deferred items
</success_criteria>

<output>
After completion, create `.planning/quick/260402-xbo-complete-the-report-precheck-synthesis-s/SUMMARY.md`
</output>
