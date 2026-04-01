---
phase: quick
plan: 260401-m8y
subsystem: research
tags: [ris, evaluation, scoring, hard-stops, precheck, jsonl-ledger, ollama, offline-first, cli]

# Dependency graph
requires:
  - phase: quick-260401-m8q
    provides: RIS v1 knowledge store (external_knowledge Chroma partition, ingest pipeline)
provides:
  - Offline document quality gate with 4-dimension scoring (relevance, novelty, actionability, credibility)
  - Hard stop pre-screening (empty_body, too_short, encoding_garbage, spam_malformed)
  - Source-family-aware credibility guidance injected into scoring prompts
  - ManualProvider (zero-dependency) and OllamaProvider (stdlib urllib.request only)
  - Precheck runner: GO/CAUTION/STOP recommendations with evidence + contradiction hook
  - JSONL append-only ledger at artifacts/research/prechecks/precheck_ledger.jsonl
  - CLI commands: research-eval, research-precheck
  - 62 new offline tests (37 evaluation + 25 precheck)
affects: [ris-academic-pipeline, ris-social-pipeline, ris-v2-cloud-providers, rag-contradiction-detection]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "JSONL append-only ledger (precheck_ledger.py mirrors hypotheses/registry.py pattern)"
    - "Provider ABC pattern: EvalProvider with score(doc, prompt) -> str"
    - "Hard-stop-first pipeline: pre-screen before any LLM call"
    - "ManualProvider fallback: zero external deps, all dims=3 total=12 ACCEPT"
    - "Source-family guidance injection via SOURCE_FAMILY_GUIDANCE[family] into scoring prompt"

key-files:
  created:
    - packages/research/evaluation/types.py
    - packages/research/evaluation/hard_stops.py
    - packages/research/evaluation/scoring.py
    - packages/research/evaluation/providers.py
    - packages/research/evaluation/evaluator.py
    - packages/research/evaluation/__init__.py
    - packages/research/synthesis/precheck.py
    - packages/research/synthesis/precheck_ledger.py
    - packages/research/synthesis/__init__.py
    - tools/cli/research_eval.py
    - tools/cli/research_precheck.py
    - config/research_eval_prompt.md
    - tests/test_ris_evaluation.py
    - tests/test_ris_precheck.py
    - docs/dev_logs/2026-04-01_ris_v1_evaluation_precheck.md
  modified:
    - polytool/__main__.py

key-decisions:
  - "ManualProvider returns all dims=3 (total=12, ACCEPT) as zero-dependency default — pipeline runs with no cloud API keys"
  - "OllamaProvider uses stdlib urllib.request only — no new external dependencies added"
  - "JSONL precheck ledger mirrors hypothesis registry pattern directly — consistent append-only design"
  - "find_contradictions() and check_stale_evidence() are explicit stubs with TODO pointers to query_index() — interfaces defined without RAG dependency"
  - "Cloud providers (gemini, deepseek) deferred to RIS v2 with ValueError and comment pointing to RIS_03 spec"
  - "ManualProvider precheck fallback: detect empty evidence lists post-parse, inject manual-mode messages in run_precheck()"

patterns-established:
  - "EvalProvider ABC: score(doc, prompt) -> str (raw JSON); callers always handle parse failure"
  - "Hard-stop-first gate: check_hard_stops() before any provider.score() call in DocumentEvaluator.evaluate()"
  - "Gate thresholds: ACCEPT >= 12, REVIEW 8-11, REJECT < 8 on /20 scale"
  - "Precheck ledger JSONL schema_version='precheck_ledger_v0', event_type='precheck_run'"

requirements-completed: []

# Metrics
duration: ~90min
completed: 2026-04-01
---

# Quick 260401-m8y: Implement the RIS v1 Ingestion Evaluation Summary

**Offline document quality gate (hard stops + 4-dimension LLM scoring) and GO/CAUTION/STOP precheck runner with JSONL ledger and two CLI commands**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-04-01T00:00:00Z
- **Completed:** 2026-04-01T00:00:00Z
- **Tasks:** 2 (both TDD)
- **Files modified:** 16 (15 created, 1 modified)

## Accomplishments

- Evaluation gate pipeline works end-to-end offline with ManualProvider (no cloud API keys required)
- 4 hard stop checks (empty_body, too_short, encoding_garbage, spam_malformed) reject bad documents before scoring
- Source-family credibility guidance (7 families: academic, forum_social, github, blog, news, dossier_report, manual) injected into scoring prompts
- Precheck runner returns GO/CAUTION/STOP with supporting/contradicting evidence; every run appended to JSONL ledger
- CLI commands `research-eval` and `research-precheck` registered and functional; appear in `polytool --help`
- 62 new offline tests added (37 evaluation + 25 precheck); full suite 2887 passed, 0 failed

## Task Commits

Each task was committed atomically:

1. **Task 1: Core evaluation gate library** - `6f0f3f7` (feat)
2. **Task 2: Precheck runner, synthesis, CLI** - `10f075c` (feat)

**Plan metadata:** _(created after)_

_Note: Both tasks used TDD execution — tests written first (RED), then implementation (GREEN)._

## Files Created/Modified

- `packages/research/evaluation/types.py` — EvalDocument, HardStopResult, ScoringResult (with gate property), GateDecision, SOURCE_FAMILIES, SOURCE_FAMILY_GUIDANCE
- `packages/research/evaluation/hard_stops.py` — check_hard_stops() with 4 stop types in order
- `packages/research/evaluation/scoring.py` — build_scoring_prompt(), parse_scoring_response(), score_document()
- `packages/research/evaluation/providers.py` — EvalProvider ABC, ManualProvider, OllamaProvider, get_provider()
- `packages/research/evaluation/evaluator.py` — DocumentEvaluator, evaluate_document() convenience function
- `packages/research/evaluation/__init__.py` — package exports
- `packages/research/synthesis/precheck.py` — PrecheckResult, build_precheck_prompt(), parse_precheck_response(), run_precheck()
- `packages/research/synthesis/precheck_ledger.py` — append_precheck(), list_prechecks(), JSONL schema v0
- `packages/research/synthesis/__init__.py` — package exports
- `tools/cli/research_eval.py` — document evaluation CLI (--file / --title + --body / --json / --provider)
- `tools/cli/research_precheck.py` — precheck CLI (--idea / --no-ledger / --ledger / --json)
- `config/research_eval_prompt.md` — full evaluation rubric for operator calibration
- `tests/test_ris_evaluation.py` — 37 offline tests: hard stops, scoring, gate, providers, evaluator
- `tests/test_ris_precheck.py` — 25 offline tests: precheck, ledger, CLI smoke
- `docs/dev_logs/2026-04-01_ris_v1_evaluation_precheck.md` — full dev log
- `polytool/__main__.py` — added research_eval_main, research_precheck_main, CLI registration, --help section

## Decisions Made

- **ManualProvider as zero-dependency default.** All dims=3, total=12 (ACCEPT). Pipeline runs with no LLM, no cloud keys. This is the critical offline-first guarantee.
- **OllamaProvider uses stdlib urllib.request.** No `requests` dependency added. Ollama integration tested via monkeypatching.
- **JSONL ledger pattern reused directly from hypothesis registry.** Consistent schema versioning, append-only design, empty-list-on-missing-file behavior.
- **Contradiction and stale-evidence hooks defined as stubs.** `find_contradictions()` and `check_stale_evidence()` return empty / passthrough with explicit TODO comments pointing to `query_index()`. Interfaces are stable so future RAG wiring does not change the precheck API.
- **Cloud providers deferred to RIS v2.** `get_provider("gemini")` raises ValueError with a comment pointing to RIS_03 spec. Intentional scope boundary.
- **ManualProvider precheck fallback injected in run_precheck().** ManualProvider returns evaluation-format JSON (not precheck format), so evidence lists are empty after parse. run_precheck() detects this and replaces with human-readable manual-mode messages, keeping CAUTION recommendation with useful context.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ManualProvider precheck response format mismatch**
- **Found during:** Task 2 TDD GREEN phase (test_manual_provider_returns_caution_with_fallback_message)
- **Issue:** ManualProvider.score() returns evaluation-format JSON (relevance/novelty/actionability/credibility keys). parse_precheck_response() parsed it successfully as valid JSON but found no supporting_evidence/risk_factors fields, returning CAUTION with all empty evidence lists. Test expected manual-mode fallback messages in the risk_factors or supporting_evidence fields.
- **Fix:** Added post-parse check in run_precheck(): if all three evidence lists are empty after parsing, replace result with a new PrecheckResult containing manual-mode fallback messages (supporting_evidence=["Manual evaluation — no LLM analysis performed."], risk_factors=["No automated analysis available — manual review recommended."]).
- **Files modified:** packages/research/synthesis/precheck.py
- **Verification:** test_manual_provider_returns_caution_with_fallback_message passes; ManualProvider precheck path returns CAUTION with human-readable context.
- **Committed in:** 10f075c (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** Fix required for correct behavior of ManualProvider path. No scope creep.

## Issues Encountered

- ManualProvider format mismatch surfaced during TDD GREEN phase (documented above as deviation). Fixed inline without architectural changes.

## User Setup Required

None - all functionality works offline with ManualProvider. To use OllamaProvider:
1. Install Ollama locally: https://ollama.com
2. Pull a model: `ollama pull qwen3:30b` (or `llama3`)
3. Use: `python -m polytool research-eval --provider ollama --title "..." --body "..."`

## Known Stubs

- `packages/research/synthesis/precheck.py:find_contradictions()` — always returns `[]`. TODO: wire to `query_index()` once knowledge base has sufficient content.
- `packages/research/synthesis/precheck.py:check_stale_evidence()` — returns result unchanged. TODO: wire to RAG query for document dates.

## Next Phase Readiness

- Evaluation gate is ready for source pipelines to feed through (RIS_01 arxiv/ssrn, RIS_02 reddit/twitter)
- Precheck runner is ready for operator use via CLI
- Cloud providers (gemini, deepseek) require API key management — defer to RIS v2
- Contradiction detection requires populated knowledge base — wire `find_contradictions()` to `query_index()` when ready
- Calibration session recommended: score 20 manually reviewed documents to validate gate thresholds and update `config/research_eval_prompt.md`

---
*Phase: quick*
*Completed: 2026-04-01*

## Self-Check: PASSED

- FOUND: packages/research/evaluation/evaluator.py
- FOUND: packages/research/evaluation/hard_stops.py
- FOUND: packages/research/evaluation/scoring.py
- FOUND: packages/research/evaluation/providers.py
- FOUND: packages/research/evaluation/types.py
- FOUND: packages/research/synthesis/precheck.py
- FOUND: packages/research/synthesis/precheck_ledger.py
- FOUND: tools/cli/research_eval.py
- FOUND: tools/cli/research_precheck.py
- FOUND: tests/test_ris_evaluation.py (37 tests)
- FOUND: tests/test_ris_precheck.py (25 tests)
- FOUND: docs/dev_logs/2026-04-01_ris_v1_evaluation_precheck.md
- COMMIT 6f0f3f7: feat(quick-260401-m8y): implement RIS v1 evaluation gate library — FOUND
- COMMIT 10f075c: feat(quick-260401-m8y): implement RIS v1 precheck, synthesis, and CLI — FOUND
