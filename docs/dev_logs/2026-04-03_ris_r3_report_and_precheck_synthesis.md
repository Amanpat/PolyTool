# Dev Log: RIS R3 -- Report and Precheck Synthesis Engine v1

**Date:** 2026-04-03  
**Quick task:** 260402-xbo  
**Author:** Claude Code (agent-af423307)  
**Branch:** feat/ws-clob-feed  

---

## Objective

Build the deterministic report synthesis and enhanced precheck layers of the RIS_05
Synthesis Engine. The precheck runner (`run_precheck()`) and enriched retriever
(`query_knowledge_store_enriched()`) already existed. This work adds the layer that
turns retrieved evidence into structured, cited research artifacts.

---

## Files Changed

### Created

- `packages/research/synthesis/report.py` (400 lines)
  - `CitedEvidence` dataclass -- single piece of cited evidence with source attribution
  - `ResearchBrief` dataclass -- structured report matching RIS_05 format
  - `EnhancedPrecheck` dataclass -- parallel to PrecheckResult, with cited evidence lists
  - `ReportSynthesizer` class -- deterministic synthesis from enriched claim dicts
  - `format_citation()` -- inline citation string `[doc_id] (source_type, trust_tier)`
  - `format_research_brief()` -- full RIS_05 markdown with all sections
  - `format_enhanced_precheck()` -- markdown precheck with GO/CAUTION/STOP
  - Helper functions: `_extract_cited_evidence`, `_compute_overall_confidence`,
    `_detect_strategy_relevance`, `_idea_relevance_score`

- `tests/test_ris_report_synthesis.py` (390 lines)
  - 21 deterministic offline tests
  - `_make_enriched_claim()` and `_make_provenance_doc()` fixture helpers

- `docs/features/FEATURE-ris-synthesis-engine-v1.md`

- `docs/dev_logs/2026-04-03_ris_r3_report_and_precheck_synthesis.md` (this file)

### Modified

- `packages/research/synthesis/__init__.py`
  - Added exports: `CitedEvidence`, `EnhancedPrecheck`, `ResearchBrief`,
    `ReportSynthesizer`, `format_citation`, `format_enhanced_precheck`,
    `format_research_brief`

---

## Commands Run

```
# RED phase -- tests fail before implementation
python -m pytest tests/test_ris_report_synthesis.py -x -q
# Result: 1 failed (ModuleNotFoundError: No module named 'packages.research.synthesis.report')

# GREEN phase -- tests pass after implementation
python -m pytest tests/test_ris_report_synthesis.py -x -v --tb=short
# Result: 21 passed in 0.13s

# Regression check
python -m pytest tests/ -q --tb=line
# Result: 3474 passed, 3 deselected, 25 warnings in 91.16s

# Import contract verification
python -c "from packages.research.synthesis import ReportSynthesizer, ResearchBrief, EnhancedPrecheck, CitedEvidence, format_research_brief, format_enhanced_precheck; print('imports OK')"
# Result: imports OK

# CLI smoke test
python -m polytool --help
# Result: CLI loads, no import errors
```

---

## Key Design Decisions

### 1. Deterministic synthesis, no LLM

`ReportSynthesizer` operates purely on structured evidence metadata. The RIS_05 spec
describes a DeepSeek V3 LLM synthesis step, but this is deferred to v2. The v1
implementation is valuable on its own because it:

- Assembles evidence into the RIS_05 output format
- Provides citation traceability from every output item to a source document
- Handles trust tier ordering (tier_1_primary ranks higher than tier_2_community)
- Surfaces contradictions and staleness in structured form

The summary field is a deterministic concatenation of top findings, not LLM prose.
This is explicitly documented in the feature doc and CURRENT_STATE update.

### 2. EnhancedPrecheck is parallel to PrecheckResult, not a replacement

`PrecheckResult` is produced by `run_precheck()` which calls an LLM provider
(`get_provider()`) to score the idea. `EnhancedPrecheck` is produced by
`ReportSynthesizer.synthesize_precheck()` which works offline from enriched claims.
They serve different use cases and both remain in the codebase.

### 3. Idea relevance filtering via keyword overlap

`_idea_relevance_score()` splits the idea into words (min length 4) and checks how
many appear in the claim text (case-insensitive). This is intentionally simple --
semantic similarity filtering (embeddings) is a v2 feature. If keyword filtering
yields no matches, all claims are used (broad topic fallback).

### 4. Recommendation rules

The GO/CAUTION/STOP decision follows a rule hierarchy:
1. All stale -> CAUTION + stale_warning (uncertainty about freshness overrides everything)
2. Contradicting > 2x supporting -> STOP
3. Supporting > 0 and contradicting == 0 and not all stale -> GO
4. Otherwise -> CAUTION (safe default)

---

## What in RIS_05 Is Now Complete vs Deferred

### Complete (v1 shipped)

- [x] `CitedEvidence` dataclass with source attribution
- [x] `ResearchBrief` dataclass with all RIS_05 sections
- [x] `EnhancedPrecheck` dataclass with cited evidence lists
- [x] `ReportSynthesizer.synthesize_brief()` -- deterministic synthesis
- [x] `ReportSynthesizer.synthesize_precheck()` -- GO/CAUTION/STOP from evidence
- [x] `format_research_brief()` -- full RIS_05 markdown
- [x] `format_enhanced_precheck()` -- precheck markdown with citations
- [x] Trust tier ordering in key_findings
- [x] Contradiction detection and surfacing with both sides cited
- [x] Staleness notes in knowledge_gaps
- [x] Overall confidence derivation (HIGH/MEDIUM/LOW)
- [x] Exports added to `packages/research/synthesis/__init__.py`
- [x] 21 offline deterministic tests

### Deferred (v2)

- [ ] LLM-based synthesis (DeepSeek V3) for prose summaries
- [ ] Multi-model citation verification (Gemini Flash checker)
- [ ] Iterative orchestrator loop with gap detection
- [ ] Weekly digest generation + Discord webhook
- [ ] CLI commands: `polytool research report --topic ...`
- [ ] Report storage: `artifacts/research/reports/`
- [ ] ClickHouse `research_reports` table
- [ ] Past failures search for `EnhancedPrecheck.past_failures`
- [ ] HyDE expansion integration into `ReportSynthesizer`

---

## Architecture Diagram: Evidence Flow

```
KnowledgeStore
    |
    v
query_knowledge_store_enriched()
    returns list[dict] with:
    - claim_text, confidence, trust_tier
    - provenance_docs[]: {id, title, source_type, trust_tier, source_url, ...}
    - contradiction_summary[]: list of contradicting claim texts
    - is_contradicted: bool
    - staleness_note: "STALE" | "AGING" | ""
    - effective_score: float (KS applies 0.5x penalty for contradicted)
    |
    v
ReportSynthesizer
    |
    +-- synthesize_brief(topic, claims)
    |       sort by effective_score desc
    |       non-contradicted top-N -> key_findings (CitedEvidence per finding)
    |       is_contradicted -> contradictions (both sides)
    |       staleness -> knowledge_gaps
    |       keywords -> actionability
    |       _compute_overall_confidence() -> HIGH/MEDIUM/LOW
    |       -> ResearchBrief
    |
    +-- synthesize_precheck(idea, claims)
            _idea_relevance_score() filter
            confidence >= 0.6 and not contradicted -> supporting (CitedEvidence)
            is_contradicted or contradiction_summary -> contradicting (CitedEvidence)
            GO/CAUTION/STOP decision rules
            -> EnhancedPrecheck

        format_research_brief(brief) -> markdown
        format_enhanced_precheck(precheck) -> markdown
```

---

## Codex Review

Tier: Skip (synthesis logic only, no execution/trading code touched).
No mandatory review files changed.

---

## Open Questions / Next Steps

1. Wire `ReportSynthesizer` into CLI (`polytool research report`, `polytool research precheck`)
   when v1B CLI work begins.
2. Decide if `EnhancedPrecheck` should be persisted to a ledger (similar to `precheck_ledger.py`).
3. When LLM-based synthesis is added in v2, the `summary` field can be replaced with
   DeepSeek V3 output while keeping all other fields deterministic.
4. Consider adding `source_publish_date` to `CitedEvidence` for the sources table in
   `format_research_brief` (currently shows freshness_note, not the actual date).
