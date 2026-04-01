# Dev Log: RIS v1 Evaluation Gate and Precheck Workflow

**Date:** 2026-04-01  
**Task:** 260401-m8y — Implement RIS v1 Ingestion Evaluation  
**Status:** Complete

---

## What Was Built

### Evaluation Gate Library (`packages/research/evaluation/`)

A fully offline document quality gate that prevents low-quality content from entering the knowledge base.

**`types.py`** — Core dataclasses:
- `EvalDocument` — normalized document representation (doc_id, title, author, source_type, source_url, source_publish_date, body, metadata)
- `HardStopResult` — pre-screening result (passed, reason, stop_type)
- `ScoringResult` — 4-dimension scoring result with `gate` property (ACCEPT/REVIEW/REJECT based on total)
- `GateDecision` — final gate decision including scores, hard stop info, and timestamp
- `SOURCE_FAMILIES` — dict mapping source_type strings to family names (arxiv→academic, reddit→forum_social, etc.)
- `SOURCE_FAMILY_GUIDANCE` — family → credibility/scoring guidance string

**`hard_stops.py`** — Universal pre-screening before LLM scoring:
- `empty_body` — body is None, empty, or whitespace-only
- `too_short` — stripped body < 50 chars
- `encoding_garbage` — >80% non-ASCII characters
- `spam_malformed` — uppercase alpha ratio >60%, or same URL repeated 4+ times

**`providers.py`** — LLM provider abstraction:
- `EvalProvider` ABC with `score(doc, prompt) -> str` and `name` property
- `ManualProvider` — hardcoded placeholder (all dims=3, total=12, ACCEPT), zero external dependencies
- `OllamaProvider` — local Ollama LLM via `urllib.request` (stdlib only, no requests)
- `get_provider(name)` factory — supports "manual" and "ollama"

**`scoring.py`** — 4-dimension rubric and prompt construction:
- `build_scoring_prompt(doc)` — full prompt with domain context, source-family guidance, rubric (1-5 scale), epistemic type instructions
- `parse_scoring_response(raw_json, model_name)` — graceful parsing with defaults (score=1) on malformed JSON
- `score_document(doc, provider)` — end-to-end scoring call

**`evaluator.py`** — Pipeline orchestrator:
- `DocumentEvaluator.evaluate(doc)` — hard stops → if fail return REJECT, else score → return GateDecision
- `evaluate_document(doc, provider_name)` — module-level convenience function

### Synthesis Layer (`packages/research/synthesis/`)

**`precheck.py`** — Pre-development check runner:
- `PrecheckResult` dataclass — recommendation (GO/CAUTION/STOP), idea, supporting/contradicting evidence, risk_factors, stale_warning, timestamp, provider_used, raw_response
- `build_precheck_prompt(idea)` — explicit contradiction detection instructions ("MUST include contradicting evidence even for promising ideas")
- `parse_precheck_response(raw_json, idea, model_name)` — falls back to CAUTION on parse failure or missing precheck fields
- `check_stale_evidence(result)` — stub (TODO: wire to RAG query for document dates)
- `find_contradictions(idea)` — stub (TODO: wire to query_index() for semantic contradiction detection)
- `run_precheck(idea, provider_name, ledger_path)` — full pipeline: prompt → score → parse → stale check → ledger append

**`precheck_ledger.py`** — JSONL append-only ledger:
- `LEDGER_SCHEMA_VERSION = "precheck_ledger_v0"`
- `DEFAULT_LEDGER_PATH = Path("artifacts/research/prechecks/precheck_ledger.jsonl")`
- `append_precheck(result, ledger_path)` — serializes PrecheckResult, adds schema_version + event_type, creates dirs
- `list_prechecks(ledger_path)` — reads all entries, returns empty list if file missing
- Pattern reused directly from `packages/research/hypotheses/registry.py`

### CLI Commands (`tools/cli/`)

**`research_eval.py`** — Document evaluation CLI:
- `--file PATH` — read from file (stem as title, content as body)
- `--title TEXT --body TEXT --source-type TYPE` — inline content
- `--provider manual|ollama`
- `--json` — JSON output mode
- Output format: `Gate: ACCEPT | Total: 12/20 | R:3 N:3 A:3 C:3 | Model: manual_placeholder`
- Hard-stop output: `Gate: REJECT | Hard stop: empty_body -- body is empty`

**`research_precheck.py`** — Precheck CLI:
- `--idea TEXT` (required)
- `--no-ledger` — skip ledger write (dry-run)
- `--ledger PATH` — custom ledger path
- `--json` — JSON output mode
- Formatted output: Recommendation, Supporting, Contradicting, Risks, Stale warning

### Configuration

**`config/research_eval_prompt.md`** — Full evaluation rubric:
- Domain context (3 strategy tracks)
- 4-dimension rubric with 1-5 scale descriptions
- Source family guidance for all 7 families
- Epistemic type tagging instructions (EMPIRICAL/THEORETICAL/ANECDOTAL/SPECULATIVE)
- 3 example evaluations (accept, reject, borderline)
- Expected JSON output format

---

## Architectural Decisions

### Offline-first, ManualProvider default
ManualProvider returns all dims=3 (total=12 → ACCEPT gate) with zero external dependencies. This ensures the pipeline runs without any cloud API keys, which is critical for offline development and testing.

### Source-family credibility guidance
SOURCE_FAMILY_GUIDANCE is injected into the scoring prompt based on doc.source_type → family mapping. This prevents the LLM from applying the same credibility standard to an arxiv paper and a Reddit post.

### JSONL ledger pattern reuse
The precheck ledger directly mirrors the append-only JSONL pattern from `packages/research/hypotheses/registry.py`. Consistent pattern reduces cognitive overhead and makes the ledger format predictable.

### Contradiction hook as stub
`find_contradictions(idea)` and `check_stale_evidence(result)` exist as explicit stubs with TODO comments pointing to `packages/polymarket/rag/query.py`. The interfaces are defined so future RAG integration doesn't require changing the precheck API.

### Graceful ManualProvider precheck fallback
ManualProvider returns evaluation-format JSON (not precheck-format). `parse_precheck_response` parses it successfully but finds no `supporting_evidence`/`risk_factors` fields. `run_precheck` detects empty evidence lists and injects manual-mode fallback messages, keeping the CAUTION recommendation with useful human-readable context.

### OllamaProvider uses stdlib urllib.request
No new dependencies added. The `requests` library is not required. Ollama integration is tested via monkeypatching in tests.

### Cloud providers deferred to RIS v2
`get_provider()` raises ValueError for "gemini", "deepseek", etc. with a comment pointing to the RIS_03 spec. This is intentional — cloud providers require API key management that is out of scope for v1.

---

## Files Created

| File | Type | Purpose |
|------|------|---------|
| `packages/research/evaluation/__init__.py` | Package | Exports EvalDocument, DocumentEvaluator, etc. |
| `packages/research/evaluation/types.py` | Library | Core dataclasses and source-family dicts |
| `packages/research/evaluation/hard_stops.py` | Library | Pre-screening checks (4 stop types) |
| `packages/research/evaluation/scoring.py` | Library | Prompt builder, response parser, score_document() |
| `packages/research/evaluation/providers.py` | Library | ManualProvider, OllamaProvider, get_provider() |
| `packages/research/evaluation/evaluator.py` | Library | DocumentEvaluator, evaluate_document() |
| `packages/research/synthesis/__init__.py` | Package | Exports run_precheck, PrecheckResult, etc. |
| `packages/research/synthesis/precheck.py` | Library | PrecheckResult, run_precheck(), prompt builder |
| `packages/research/synthesis/precheck_ledger.py` | Library | JSONL ledger: append_precheck(), list_prechecks() |
| `tools/cli/research_eval.py` | CLI | Document evaluation entrypoint |
| `tools/cli/research_precheck.py` | CLI | Precheck runner entrypoint |
| `config/research_eval_prompt.md` | Config | Full evaluation rubric for operator calibration |
| `tests/test_ris_evaluation.py` | Tests | 37 offline tests for evaluation gate |
| `tests/test_ris_precheck.py` | Tests | 25 offline tests for precheck and ledger |

**Files modified:**
- `polytool/__main__.py` — added research_eval_main, research_precheck_main, CLI registration, --help section

---

## Test Results

```
tests/test_ris_evaluation.py:  37 passed
tests/test_ris_precheck.py:    25 passed
Total new tests:               62

Full suite: 2887 passed, 25 warnings, 0 failed
(was 2787 before this task; 100 net new tests)
```

---

## Known Limitations

1. **Cloud providers deferred** — Gemini Flash and DeepSeek V3 providers are not implemented. ManualProvider and OllamaProvider are the only available options. RIS v2 scope.

2. **Contradiction detection is a stub** — `find_contradictions(idea)` always returns `[]`. Will require `query_index()` integration once the RAG knowledge base is populated with relevant research.

3. **Stale-evidence check is a stub** — `check_stale_evidence(result)` returns the result unchanged. Will require querying document publish dates from RAG metadata.

4. **No Chroma integration** — The evaluation gate does not check for duplicate documents against the knowledge base (deduplication step from RIS_03 architecture). That requires the full `external_knowledge` partition to be populated.

5. **OllamaProvider tested via mock only** — No live Ollama integration test; requires local Ollama installation. The urllib.request implementation is correct but untested end-to-end.

---

## Next Steps

1. **Wire Ollama for real scoring** — Install `qwen3:30b` or `llama-3-8b`, test against real documents
2. **Connect RAG for contradiction detection** — Wire `find_contradictions()` to `query_index()` once knowledge base has sufficient content
3. **Build academic source pipeline** — RIS_01 (arxiv/ssrn ingestion) to feed documents through the evaluation gate
4. **Build social source pipeline** — RIS_02 (reddit/twitter ingestion) with pre-filtering
5. **Calibration session** — Score 20 manually reviewed documents, adjust thresholds, populate calibration notes in `config/research_eval_prompt.md`
6. **Add rejected_log.jsonl** — Wire DocumentEvaluator to log REJECT decisions per RIS_03 spec

---

## Codex Review

**Tier:** Skip (no execution/, kill_switch, risk_manager, or CLOB client code touched)  
**Review run:** Not required per CLAUDE.md policy for this file set.
