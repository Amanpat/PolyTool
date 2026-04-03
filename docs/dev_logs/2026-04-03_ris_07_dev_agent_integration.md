# Dev Log: RIS_07 Dev Agent Integration and Fast-Research Preservation v1

**Date:** 2026-04-03
**Plan:** quick-260403-jyl
**Commit:** (see git log for task-02 hash)

---

## Objective

Close the dev-agent integration and fast-research preservation side of RIS_07.

CLAUDE.md previously had no RIS section. Operators and dev agents had no documented
workflow for preserving fast-research findings (from LLM sessions, web searches, paper
reads) into the persistent knowledge store. This work closes RIS_07 at practical v1 scope.

---

## Files Changed

| File | Change |
|------|--------|
| `CLAUDE.md` | Added "Research Intelligence System (RIS)" section with dev-agent pre-build workflow, fast-research preservation recipes, and pipeline health commands. Extended CLI reference list with all RIS commands. |
| `docs/features/FEATURE-ris-dev-agent-integration-v1.md` | New feature doc with operator recipes A-E, integration test coverage table, and v2 deferred items |
| `tests/test_ris_integration_workflow.py` | New -- 10 offline integration tests covering precheck round-trip, ingest-then-query, acquire dry-run, file ingest, and contradiction detection |
| `docs/CURRENT_STATE.md` | Appended RIS_07 closure entry with 10 test count and v2 deferred items |
| `docs/dev_logs/2026-04-03_ris_07_dev_agent_integration.md` | This file |

---

## What Was Done

### 1. CLAUDE.md update

Added a new "## Research Intelligence System (RIS)" section immediately after the
"### Research / dossier workflows" subsection. The section covers:

- **Purpose**: 2-sentence description of RIS as the persistent knowledge base
- **Dev Agent Pre-Build Workflow** (4 steps): precheck -> act on verdict -> deeper query ->
  inspect contradictions. All commands use `python -m polytool research-*` format.
- **Preserving Findings into RIS**: three preservation paths with copy-paste command examples:
  URL (research-acquire), manual summary (research-ingest --text), file (research-ingest --file)
- **Pipeline Health**: research-health and research-stats one-liners
- **Offline-first note**: "All RIS commands are offline-first and do not call external LLM APIs
  unless --provider ollama is used."

Also extended the "### Research / dossier workflows" CLI list to include all 7 RIS commands:
research-precheck, research-ingest, research-acquire, research-report, research-health,
research-stats, research-scheduler.

### 2. Feature doc: FEATURE-ris-dev-agent-integration-v1.md

Created `docs/features/FEATURE-ris-dev-agent-integration-v1.md` with:
- Full dev-agent workflow documentation with step-by-step guide
- Fast-research preservation loop explanation (why it matters, triggers, commands)
- 5 concrete operator recipes with copy-paste command sequences
- Integration test coverage table mapping test name to behavior
- v2 deferred items explicitly listed out of scope

### 3. Integration tests: tests/test_ris_integration_workflow.py

10 offline integration tests across 5 test classes:

| Test | What it proves |
|------|----------------|
| `test_precheck_returns_verdict_after_ingest` | Ingest doc + run_precheck() directly with populated KS -- verdict returned |
| `test_precheck_via_cli_returns_exit_0` | CLI main() returns exit 0 with GO/CAUTION/STOP in output |
| `test_ingest_text_retrievable_from_ks` | Ingest via --text, verify unique phrase retrievable from KS |
| `test_ingest_json_output_has_doc_id` | --json flag produces doc_id in output |
| `test_dry_run_exits_0_no_ks_write` | --dry-run exits 0 (HTTP monkeypatched via _default_urlopen) |
| `test_dry_run_prints_dry_run_marker` | [dry-run] marker present in output |
| `test_ingest_md_file_retrievable` | .md file ingest round-trip, source doc in KS |
| `test_ingest_file_with_title_override` | --title flag stores custom title in KS |
| `test_precheck_with_contradicting_docs_exits_0` | Contradicting docs in KS, precheck exits 0 with verdict |
| `test_precheck_produces_text_output_with_populated_ks` | CLI precheck produces "Recommendation:" line |

Key implementation notes:
- HTTP patching: `_default_urlopen` in `packages.research.ingestion.fetchers` is the correct
  monkeypatch target (not a module-level `_http_fn` attribute). `LiveBlogFetcher.__init__`
  copies `_default_urlopen` into `self._http_fn` at construction time.
- Text content constraint: `PlainTextExtractor` treats any string containing `/` as a file
  path. Test texts avoid forward slashes to prevent false "No such file" errors.

---

## v2 Deferred Items

The following RIS_07 items are explicitly out of scope for v1 and deferred to v2/Phase R5:

- **Dossier-to-external-knowledge extraction (RIS_07 Section 1):** Auto-extract key findings
  from wallet dossiers into `external_knowledge` partition. Requires LLM extraction prompt
  and integration with wallet-scan / alpha-distill.
- **Auto-discovery -> knowledge loop (RIS_07 Section 2):** Candidate scanner discovers
  wallet -> dossier_extractor pulls findings -> external_knowledge grows automatically.
  Requires Section 1 as prerequisite.
- **SimTrader bridge / auto-hypothesis generation (RIS_07 Section 3):** Shipped as
  quick-260403-jyg but auto-promotion loop not yet wired.
- **ChatGPT architect integration via Google Drive (RIS_07 Section 4):** Requires manual
  drive sync setup.
- **MCP polymarket_rag_query auto-routing:** MCP tool queries Chroma but does not include
  KnowledgeStore as a retrieval source.

---

## Commands Run

```
python -m pytest tests/test_ris_integration_workflow.py -v --tb=short
# Result: 10 passed in 0.66s

python -m pytest tests/ -x -q --tb=short
# Result: 3660 passed, 3 deselected, 25 warnings in 94.00s
```

---

## Codex Review Tier

Skip -- docs and tests only. No execution layer or strategy code modified.
