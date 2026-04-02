---
phase: quick-260402-qsq
plan: "01"
type: execute
wave: 1
depends_on: []
files_modified:
  - .planning/STATE.md
autonomous: true
requirements: [truth-alignment]
must_haves:
  truths:
    - "STATE.md entry for 260402-ogu accurately describes shipped CLI surface (research-ingest --from-adapter, not research-acquire)"
    - "STATE.md entry for 260402-ogu accurately describes cache format (per-source .json keyed by source_id, not JSONL keyed by acquisition_id)"
    - "No document in the repo claims research-acquire CLI, acquire-fixture subcommand, or acquisition_id exist"
  artifacts:
    - path: ".planning/STATE.md"
      provides: "Corrected quick-task table entry for 260402-ogu"
      contains: "research-ingest --from-adapter"
  key_links:
    - from: ".planning/STATE.md"
      to: "docs/features/FEATURE-ris-phase4-source-acquisition.md"
      via: "matching terminology: source_id, per-source JSON cache, --from-adapter"
      pattern: "from-adapter|source_id"
---

<objective>
Fix the single source-of-truth mismatch in STATE.md for RIS Phase 4 source acquisition.

Purpose: Codex verification found that STATE.md line 141 (quick-task 260402-ogu entry)
contains three factual errors that contradict the shipped code, tests, feature doc, dev log,
SUMMARY.md, and CURRENT_STATE.md. All other documentation is internally consistent and
accurate. This plan corrects STATE.md to match the true implementation.

Output: Corrected STATE.md with accurate 260402-ogu entry.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md (line 141 — the single incorrect entry)
@docs/features/FEATURE-ris-phase4-source-acquisition.md (ground truth — accurate)
@docs/dev_logs/2026-04-02_ris_phase4_source_acquisition.md (ground truth — accurate)
@.planning/quick/260402-ogu-ris-phase-4-external-source-acquisition-/260402-ogu-SUMMARY.md (ground truth — accurate)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Correct STATE.md 260402-ogu entry to match shipped reality</name>
  <files>.planning/STATE.md</files>
  <action>
Read .planning/STATE.md and locate the quick-task table row for 260402-ogu (around line 141).

The CURRENT (incorrect) text reads:
"RIS Phase 4 external source acquisition: raw-source cache (JSONL keyed by acquisition_id), metadata normalization + canonical IDs (DOI/arXiv/SSRN/repo URL dedup), 3 adapters (academic/github/blog-news), fixture-backed offline fixtures, research-acquire CLI (acquire-fixture subcommand, --family/--source-url/--dry-run); 49 new tests; 2009 passing"

Replace with this CORRECTED text that matches the shipped code, feature doc, dev log, and SUMMARY.md:
"RIS Phase 4 external source acquisition: raw-source cache (per-source JSON keyed by source_id=sha256[:16]), metadata normalization + canonical IDs (DOI/arXiv/SSRN/repo URL extraction), 3 adapters (academic/github/blog-news), fixture-backed offline fixtures, research-ingest --from-adapter CLI path (--source-family/--cache-dir flags); 49 new tests; 2009 passing"

Three specific corrections:
1. "JSONL keyed by acquisition_id" -> "per-source JSON keyed by source_id=sha256[:16]" (cache is individual .json files per source, not append-only JSONL; the key is source_id, not acquisition_id)
2. "research-acquire CLI (acquire-fixture subcommand, --family/--source-url/--dry-run)" -> "research-ingest --from-adapter CLI path (--source-family/--cache-dir flags)" (no research-acquire command exists; the feature was added as flags on the existing research-ingest command)
3. "dedup" -> "extraction" (canonical IDs are extracted and stored, but not yet wired to dedup — the feature doc explicitly lists dedup integration as deferred)

Do NOT change any other row in the table. Do NOT change any other file. This is the only mismatch.
  </action>
  <verify>
    <automated>grep -n "260402-ogu" .planning/STATE.md | grep -v "JSONL\|acquisition_id\|research-acquire\|acquire-fixture"</automated>
  </verify>
  <done>
STATE.md 260402-ogu entry says "per-source JSON keyed by source_id" (not "JSONL keyed by acquisition_id"), says "research-ingest --from-adapter" (not "research-acquire"), and says "extraction" (not "dedup"). The corrected entry matches the shipped code in source_cache.py, the CLI flags in research_ingest.py, the feature doc, and the SUMMARY.md.
  </done>
</task>

</tasks>

<verification>
1. `grep "acquisition_id" .planning/STATE.md` returns zero matches (term does not exist in the codebase)
2. `grep "research-acquire" .planning/STATE.md` returns zero matches (no such CLI command)
3. `grep "acquire-fixture" .planning/STATE.md` returns zero matches (no such subcommand)
4. `grep "260402-ogu" .planning/STATE.md` returns one row mentioning "research-ingest --from-adapter" and "per-source JSON keyed by source_id"
5. Existing tests still pass: `python -m pytest tests/test_ris_phase4_source_acquisition.py -x -q --tb=short`
</verification>

<success_criteria>
- STATE.md 260402-ogu entry is factually accurate and consistent with:
  - packages/research/ingestion/source_cache.py (per-source .json, source_id)
  - tools/cli/research_ingest.py (--from-adapter, --source-family, --cache-dir)
  - docs/features/FEATURE-ris-phase4-source-acquisition.md
  - .planning/quick/260402-ogu-*/260402-ogu-SUMMARY.md
- No other files changed
- Zero grep hits for "acquisition_id", "research-acquire", or "acquire-fixture" in STATE.md
</success_criteria>

<output>
After completion, create `.planning/quick/260402-qsq-resolve-codex-mismatches-for-ris-phase-4/260402-qsq-SUMMARY.md`
</output>
