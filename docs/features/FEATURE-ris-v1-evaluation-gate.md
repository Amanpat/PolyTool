# FEATURE: RIS v1 Evaluation Gate and Precheck Subsystem

**Shipped:** quick-260401-m8y (evaluation gate + precheck runner), quick-260401-n1s (KnowledgeStore wiring + enriched ledger)
**Status:** Complete (offline-first; cloud LLM providers deferred to RIS v2)
**Data foundation:** See [FEATURE-ris-v1-data-foundation.md](./FEATURE-ris-v1-data-foundation.md)

## Overview

The RIS v1 evaluation gate provides a quality-first filter for research documents
before they enter the knowledge base. Documents pass through hard-stop pre-screening,
then 4-dimension LLM scoring. Ideas are evaluated for development readiness via the
precheck runner, which now integrates with the KnowledgeStore for contradiction
detection and freshness-aware staleness warnings.

## Modules

| Module | Purpose |
|--------|---------|
| `packages/research/evaluation/types.py` | EvalDocument, HardStopResult, ScoringResult, GateDecision, SOURCE_FAMILIES, SOURCE_FAMILY_GUIDANCE |
| `packages/research/evaluation/hard_stops.py` | 4 hard stop pre-checks |
| `packages/research/evaluation/scoring.py` | 4-dimension LLM scoring prompt + parse |
| `packages/research/evaluation/providers.py` | EvalProvider ABC, ManualProvider, OllamaProvider, get_provider() |
| `packages/research/evaluation/evaluator.py` | DocumentEvaluator, evaluate_document() |
| `packages/research/synthesis/precheck.py` | PrecheckResult, run_precheck(), find_contradictions(), check_stale_evidence() |
| `packages/research/synthesis/precheck_ledger.py` | JSONL append-only ledger (v1 schema) |
| `tools/cli/research_eval.py` | research-eval CLI |
| `tools/cli/research_precheck.py` | research-precheck CLI |
| `config/research_eval_prompt.md` | Full evaluation rubric for operator calibration |

## Hard Stops (pre-scoring filter)

Documents are rejected before any LLM call if they trigger a hard stop:

| Stop Type | Condition |
|-----------|-----------|
| `empty_body` | Body is None or whitespace-only |
| `too_short` | Body < 50 characters |
| `encoding_garbage` | Body contains replacement characters or null bytes |
| `spam_malformed` | ALL-CAPS body or repeated URL pattern |

Hard stops produce a `REJECT` gate decision with `hard_stop_reason` set. Scoring
is not performed.

## 4-Dimension Scoring

Documents that pass hard stops are scored on four dimensions (1-5 each, total /20):

| Dimension | What it measures |
|-----------|-----------------|
| Relevance (R) | How relevant to prediction market trading and PolyTool strategy |
| Novelty (N) | How new or unique is the information vs. what we already know |
| Actionability (A) | Does it suggest concrete actions or code changes |
| Credibility (C) | How credible is the source given its family and methodology |

### Gate Thresholds

| Score | Decision |
|-------|----------|
| >= 12 | ACCEPT |
| 8-11 | REVIEW |
| < 8 | REJECT |

## Source-Family Guidance

The scoring prompt injects source-family-specific credibility guidance to help
the LLM calibrate the Credibility dimension:

| Source Family (SOURCE_FAMILIES key) | Guidance |
|--------------------------------------|----------|
| `arxiv`, `ssrn` | academic — weight methodology, sample sizes |
| `reddit`, `twitter` | forum/social — weight specificity and data references |
| `github` | open-source — weight activity, adoption, stars |
| `blog` | blog — weight author credentials and data backing |
| `news` | news — weight recency and primary source proximity |
| `polymarket_wallet_analysis` | dossier/report — weight sample size and strategy specificity |
| `manual` | manual/operator — evaluate on content merit alone |

Source type to family mapping is in `SOURCE_FAMILIES` in `packages/research/evaluation/types.py`.

## LLM Providers

### ManualProvider (zero-dependency default)

All dimensions return 3 (total=12, ACCEPT). No network calls, no API keys.
This is the default provider — the pipeline works fully offline out of the box.

### OllamaProvider

Uses `stdlib urllib.request` only — no new external dependencies. Connects to
a locally running Ollama instance. Configure via environment variable or CLI flag.

```bash
# Requires Ollama running locally with a model pulled
python -m polytool research-eval --provider ollama --title "Test" --body "..."
```

### Cloud Providers (deferred)

Gemini, DeepSeek, and other cloud providers are deferred to RIS v2. Calling
`get_provider("gemini")` raises `ValueError` with a message pointing to RIS_03.

## Precheck Runner

The precheck runner evaluates ideas for development readiness before a development
work packet is started.

### PrecheckResult fields

| Field | Type | Description |
|-------|------|-------------|
| `recommendation` | str | GO, CAUTION, or STOP |
| `idea` | str | The original idea text |
| `supporting_evidence` | list[str] | Evidence supporting the idea |
| `contradicting_evidence` | list[str] | Evidence against the idea |
| `risk_factors` | list[str] | Risks that could prevent success |
| `stale_warning` | bool | True when all KnowledgeStore source docs are stale |
| `provider_used` | str | Provider identifier |
| `precheck_id` | str | Deterministic SHA-256[:12] of idea text |
| `reason_code` | str | STRONG_SUPPORT, MIXED_EVIDENCE, or FUNDAMENTAL_BLOCKER |
| `evidence_gap` | str | Set when no contradicting evidence + recommendation != GO |
| `review_horizon` | str | Suggested review date: 7d (CAUTION), 30d (STOP), empty (GO) |

### Recommendation to reason_code mapping

| Recommendation | reason_code |
|---------------|-------------|
| GO | STRONG_SUPPORT |
| CAUTION | MIXED_EVIDENCE |
| STOP | FUNDAMENTAL_BLOCKER |

### GO / CAUTION / STOP semantics

- **GO**: Strong evidence for, low risk, actionable next step is clear.
- **CAUTION**: Mixed evidence or significant uncertainty; proceed carefully. Review in 7d.
- **STOP**: Evidence against outweighs support, or fundamental blocker exists. Review in 30d.

### ManualProvider precheck behavior

ManualProvider returns evaluation-format JSON (not precheck format). The precheck
runner detects this by checking if all evidence lists are empty after parsing, and
injects manual-mode fallback messages:

- `supporting_evidence`: ["Manual evaluation — no LLM analysis performed."]
- `risk_factors`: ["No automated analysis available — manual review recommended."]
- `recommendation`: CAUTION

## Contradiction Detection via KnowledgeStore

`find_contradictions(idea, knowledge_store=None)` queries the KnowledgeStore for
claims involved in CONTRADICTS relations:

- When `knowledge_store=None` (default): returns [] — backward compat, no KS dependency.
- When `knowledge_store` is provided: queries all active claims, checks each for
  CONTRADICTS relations (as source or target), returns the claim text strings.
- The `idea` text is NOT used for semantic filtering — embeddings-based matching is
  out of scope for v1. The function returns all CONTRADICTS-related claims as
  candidates; the LLM evaluates relevance in the precheck prompt.
- Returned claims are merged into `result.contradicting_evidence` with deduplication.

## Stale Evidence Detection via Freshness Decay

`check_stale_evidence(result, knowledge_store=None)` applies freshness decay:

- When `knowledge_store=None` (default): returns result unchanged — backward compat.
- When `knowledge_store` is provided: queries all source_documents, computes
  `compute_freshness_modifier(source_family, published_at)` for each.
- If ALL documents have `freshness_modifier < 0.5`, sets `stale_warning=True`.
- If no source documents exist, returns result unchanged (no data = no penalty).
- The freshness decay formula: `modifier = max(floor, 2^(-age_months / half_life))`.
  Threshold 0.5 corresponds to age = 1 half-life for a given source family.

Source-family half-lives (from `config/freshness_decay.json`):

| Family | Half-life | Notes |
|--------|-----------|-------|
| academic_foundational, book_foundational | null (timeless) | No decay |
| academic_empirical | 18 months | |
| preprint, github | 12 months | |
| blog | 9 months | |
| reddit, twitter, youtube, wallet_analysis | 6 months | |
| news | 3 months | Fastest decay |

## JSONL Precheck Ledger

Every precheck run is appended to a JSONL file.

**Default path:** `artifacts/research/prechecks/precheck_ledger.jsonl`

**Schema version:** `precheck_ledger_v1` (bumped from v0 in quick-260401-n1s)

### v1 event fields

All v0 fields plus:

| Field | Description |
|-------|-------------|
| `precheck_id` | SHA-256[:12] of idea text |
| `reason_code` | STRONG_SUPPORT, MIXED_EVIDENCE, or FUNDAMENTAL_BLOCKER |
| `evidence_gap` | Populated when contradicting_evidence empty and rec != GO |
| `review_horizon` | 7d (CAUTION), 30d (STOP), empty (GO) |

### Backward compatibility

v0 entries (missing the new fields) remain fully readable by `list_prechecks()`.
Missing fields are absent from the returned dict; callers should use `.get()` with
a default for new fields.

## CLI Commands

### research-precheck

```bash
# Basic usage (ManualProvider, default ledger)
python -m polytool research-precheck --idea "Is directional momentum viable for BTC 5m?"

# JSON output (includes all enriched fields)
python -m polytool research-precheck --idea "Test idea" --no-ledger --json

# Dry run (skip ledger write)
python -m polytool research-precheck --idea "Test idea" --no-ledger

# Custom ledger path
python -m polytool research-precheck --idea "Test idea" --ledger path/to/custom.jsonl

# Use Ollama provider
python -m polytool research-precheck --idea "Test idea" --provider ollama
```

### research-eval

```bash
# Evaluate from inline body
python -m polytool research-eval --title "Test Doc" --body "..." --source-type arxiv

# Evaluate from file
python -m polytool research-eval --file path/to/document.md

# JSON output mode
python -m polytool research-eval --title "T" --body "..." --json

# Use Ollama provider
python -m polytool research-eval --title "T" --body "..." --provider ollama
```

## Deferred Features (future tasks)

- **Lifecycle fields:** `was_overridden`, `override_reason`, `outcome_label`,
  `outcome_date` — for marking a precheck as overridden by operator decision and
  recording actual outcome after development completes. Requires operator workflow
  for marking prechecks as resolved. Defer to a future "precheck lifecycle" task.

- **Cloud providers:** Gemini, DeepSeek, and other cloud APIs. Defer to RIS v2
  (RIS_03 spec). Requires authority sync between Roadmap v5.1 Tier 1 free APIs
  and PLAN_OF_RECORD no-external-LLM-call policy.

- **Semantic contradiction matching:** Using embeddings to filter contradicting
  claims by relevance to the idea. Defer to a future RIS task when the knowledge
  base has sufficient content to make semantic filtering meaningful.

## Tests

| Test file | Tests | Coverage |
|-----------|-------|----------|
| `tests/test_ris_evaluation.py` | 37 | Hard stops, scoring, gate, providers, evaluator |
| `tests/test_ris_precheck.py` | 25 | PrecheckResult, prompt, parse, run, ledger, CLI |
| `tests/test_ris_precheck_wiring.py` | 35 | KnowledgeStore wiring, freshness wiring, enriched schema, ledger v1 |

All tests are fully offline — no network, no LLM, no Chroma, `:memory:` SQLite only.
