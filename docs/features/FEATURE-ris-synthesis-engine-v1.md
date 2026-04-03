# FEATURE: RIS Synthesis Engine v1 -- Deterministic Report and Precheck Synthesis

**Status:** Shipped  
**Date:** 2026-04-03  
**Module:** `packages/research/synthesis/report.py`  
**Requirement:** RIS_05_synthesis_report, RIS_05_synthesis_precheck  

---

## What Was Built

The RIS Synthesis Engine v1 adds a deterministic synthesis layer on top of the
enriched claim retrieval pipeline. It bridges the gap between the retriever
(`query_knowledge_store_enriched()`) and actionable research artifacts.

### New Module: `packages/research/synthesis/report.py`

Exports: `ReportSynthesizer`, `ResearchBrief`, `EnhancedPrecheck`, `CitedEvidence`,
`format_citation`, `format_research_brief`, `format_enhanced_precheck`

### Key Design Decisions

1. **Deterministic, no LLM calls** -- All synthesis logic operates on structured
   evidence metadata (confidence, trust_tier, staleness_note, is_contradicted,
   provenance_docs). LLM-based synthesis (DeepSeek V3) is a v2 feature deferred
   per RIS_05 spec.

2. **Parallel output type, not replacement** -- `EnhancedPrecheck` is a parallel
   output type to `PrecheckResult`. The existing `run_precheck()` function and
   `PrecheckResult` dataclass are unchanged. `EnhancedPrecheck` is produced by
   `ReportSynthesizer.synthesize_precheck()` from enriched KnowledgeStore claims.

3. **Citation traceability** -- Every evidence item is wrapped in `CitedEvidence`
   which carries `source_doc_id`, `source_title`, `source_type`, `trust_tier`,
   and `provenance_url` from provenance_docs in the enriched claim.

---

## Output Contracts

### `CitedEvidence`

A single piece of cited evidence extracted from an enriched claim dict.

| Field | Type | Description |
|-------|------|-------------|
| `claim_text` | str | The claim text |
| `source_doc_id` | str | ID of the source document |
| `source_title` | str | Title of the source document |
| `source_type` | str | Type (arxiv, reddit, twitter, etc.) |
| `trust_tier` | str | Trust tier (tier_1_primary, tier_2_community, etc.) |
| `confidence` | float | Claim confidence score (0.0 - 1.0) |
| `freshness_note` | str | STALE, AGING, or empty string |
| `provenance_url` | str | URL of the source document |

### `ResearchBrief`

Structured research brief matching RIS_05 report format.

| Field | Type | Description |
|-------|------|-------------|
| `topic` | str | Research topic |
| `generated_at` | str | ISO UTC timestamp |
| `sources_queried` | int | Number of claims passed in |
| `sources_cited` | int | Number of unique sources cited |
| `overall_confidence` | str | HIGH, MEDIUM, or LOW |
| `summary` | str | Deterministic synthesis of top findings |
| `key_findings` | list[dict] | Top non-contradicted claims with source attribution |
| `contradictions` | list[dict] | Contradicted claim pairs with both sides cited |
| `actionability` | dict | Strategy track relevance and next steps |
| `knowledge_gaps` | list[str] | Stale claims and sparse coverage gaps |
| `cited_sources` | list[CitedEvidence] | All unique cited sources |

**key_findings dict keys:** `title`, `description`, `source` (CitedEvidence), `confidence_tier`

**contradictions dict keys:** `claim_a`, `claim_b`, `sources` (list[CitedEvidence]), `unresolved`

**actionability dict keys:** `can_inform_strategy` (bool), `target_track` (str),
`suggested_next_step` (str), `estimated_impact` (str)

### `EnhancedPrecheck`

Enhanced precheck with cited evidence, parallel to `PrecheckResult`.

| Field | Type | Description |
|-------|------|-------------|
| `recommendation` | str | GO, CAUTION, or STOP |
| `idea` | str | The idea being evaluated |
| `supporting` | list[CitedEvidence] | Supporting evidence (not contradicted, confidence >= 0.6) |
| `contradicting` | list[CitedEvidence] | Contradicting evidence with source citations |
| `risk_factors` | list[str] | Risk factor texts from contradicting claims |
| `past_failures` | list[str] | Past failed strategies (deferred to v2) |
| `knowledge_gaps` | list[str] | Sparse or stale evidence notes |
| `validation_approach` | str | Recommended validation path |
| `timestamp` | str | ISO UTC timestamp |
| `overall_confidence` | str | HIGH, MEDIUM, or LOW |
| `stale_warning` | bool | True when all relevant evidence is STALE |
| `evidence_gap` | str | Non-empty when no relevant claims found |
| `precheck_id` | str | SHA256-derived 12-char stable ID |

---

## Format Functions

### `format_citation(evidence: CitedEvidence) -> str`

Produces: `[doc_id] (source_type, trust_tier)`

Example: `[doc_abc123] (arxiv, tier_1_primary)`

### `format_research_brief(brief: ResearchBrief) -> str`

Produces full markdown with all RIS_05 sections:
- `# Research Brief: {topic}`
- Header metadata (generated_at, sources_queried, sources_cited, overall_confidence)
- `## Summary`
- `## Key Findings` (numbered list with source citations)
- `## Contradictions & Unresolved Questions` (paired claims with citations)
- `## Actionability Assessment` (strategy track relevance)
- `## Knowledge Gaps` (stale/sparse evidence)
- `## Sources Cited` (markdown table with all unique sources)

### `format_enhanced_precheck(precheck: EnhancedPrecheck) -> str`

Produces markdown precheck report:
- `# Pre-Development Check: {idea}`
- `## Recommendation: GO / CAUTION / STOP`
- Stale warning and evidence gap alerts (if applicable)
- `### Supporting evidence` (with inline citations)
- `### Contradicting evidence` (with inline citations)
- `## Risk Assessment`
- `## Knowledge Gaps`
- `## If proceeding, recommended validation approach`

---

## Evidence Flow

```
query_knowledge_store_enriched()
    returns list[enriched_claim_dict]
    each claim has: claim_text, confidence, trust_tier,
                    provenance_docs[], contradiction_summary[],
                    is_contradicted, staleness_note, effective_score
          |
          v
ReportSynthesizer._extract_cited_evidence(claim)
    extracts first provenance_doc -> CitedEvidence
    falls back to claim metadata if no provenance_docs
          |
          v
ReportSynthesizer.synthesize_brief(topic, claims)
    sort by effective_score desc
    non-contradicted top-N -> key_findings
    is_contradicted=True -> contradictions (both sides)
    staleness_note=STALE/AGING -> knowledge_gaps
    strategy keywords -> actionability
    _compute_overall_confidence() -> HIGH/MEDIUM/LOW
    returns ResearchBrief

ReportSynthesizer.synthesize_precheck(idea, claims)
    _idea_relevance_score() -> filter by keyword overlap
    confidence >= 0.6 and not contradicted -> supporting
    is_contradicted or contradiction_summary -> contradicting
    GO/CAUTION/STOP decision rules
    returns EnhancedPrecheck
```

---

## Trust Tier Handling

Claims are sorted by `effective_score` (already computed by `query_knowledge_store_enriched()`).
The KnowledgeStore applies a 0.5x penalty to contradicted claims, so tier_1_primary claims
naturally rank higher in key_findings. The `trust_tier` field from provenance_docs is
preserved in `CitedEvidence` for full traceability in citations and the sources table.

---

## Contradiction and Staleness Behavior

### Contradictions

- Claims with `is_contradicted=True` are moved to the `contradictions` section, not key_findings
- Each contradiction entry has `claim_a` (the contradicted claim) and `claim_b` (the contradiction text)
- Deduplication is applied using a pair key to avoid showing the same contradiction twice
- Unresolved contradictions are flagged with `"unresolved": True`

### Staleness

- Claims with `staleness_note="STALE"` produce knowledge_gap entries with freshness warning
- Claims with `staleness_note="AGING"` are also noted in knowledge_gaps
- `CitedEvidence.freshness_note` carries the staleness state for inline display
- When all relevant claims are STALE: `EnhancedPrecheck.stale_warning=True`, `overall_confidence="LOW"`

---

## Overall Confidence Derivation

`_compute_overall_confidence(claims)`:

| avg confidence | STALE count | Result |
|----------------|-------------|--------|
| >= 0.8 | 0 | HIGH |
| < 0.5 OR stale_ratio > 0.5 | any | LOW |
| otherwise | any | MEDIUM |

---

## Precheck Recommendation Logic

`synthesize_precheck()` recommendation rules (applied in order):

1. If all relevant claims are STALE: `recommendation="CAUTION"`, `stale_warning=True`
2. If contradicting > 2 * supporting: `recommendation="STOP"`
3. If supporting > 0 and contradicting == 0 and not all_stale: `recommendation="GO"`
4. Otherwise: `recommendation="CAUTION"`

---

## What Is NOT Built (Deferred)

The following features from RIS_05 spec are deferred to v2:

- **LLM-based synthesis (DeepSeek V3)** -- `ReportSynthesizer` is deterministic only.
  The v2 implementation will use `llm.generate()` for prose synthesis with citations.
- **Multi-model citation verification** -- The "smaller models can't lie" pattern where
  Gemini Flash verifies each citation against source documents.
- **Iterative orchestrator loop** -- Query planner + gap detection + re-retrieval cycle.
- **Weekly digest** -- Automated Sunday digest sent via Discord webhook.
- **CLI commands for report generation** -- `polytool research report --topic ...` and
  `polytool research precheck --idea ...` are not yet wired to CLI.
- **Report storage/catalog** -- Reports are not saved to `artifacts/research/reports/`.
- **ClickHouse report indexing** -- The `research_reports` CH table is not created.
- **Past failures search** -- `EnhancedPrecheck.past_failures` is always empty (v2 feature).
- **HyDE expansion integration** -- `ReportSynthesizer` takes pre-retrieved claims,
  not raw query strings. HyDE expansion is handled upstream in `synthesis/hyde.py`.

---

## Tests

`tests/test_ris_report_synthesis.py` -- 21 offline deterministic tests.
All tests use fixture data (hardcoded enriched claim dicts). No network, no LLM,
no KnowledgeStore instantiation.

Test coverage:
- ResearchBrief and CitedEvidence dataclass shapes
- format_research_brief markdown with all sections
- EnhancedPrecheck dataclass shape and format_enhanced_precheck
- synthesize_brief: population, provenance, contradictions, staleness, empty case
- synthesize_precheck: return type, supporting/contradicting separation, stale warning, no-evidence case
- format_citation string format
- Sources cited table content
- Contradiction handling (both sides, unresolved flagging)
- Trust tier ordering in key_findings
- Confidence derivation (HIGH/MEDIUM/LOW from claim quality)
