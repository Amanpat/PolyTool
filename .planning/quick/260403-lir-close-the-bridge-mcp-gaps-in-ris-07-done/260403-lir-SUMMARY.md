---
phase: quick
plan: 260403-lir
subsystem: ris
tags: [ris, cli, mcp, knowledge-store, hybrid-retrieval, research-bridge]
dependency_graph:
  requires: [packages/research/integration/hypothesis_bridge.py, packages/research/integration/validation_feedback.py, packages/polymarket/rag/knowledge_store.py]
  provides: [tools/cli/research_bridge.py, polytool research-register-hypothesis, polytool research-record-outcome, mcp_server ks_active routing]
  affects: [polytool/__main__.py, tools/cli/mcp_server.py]
tech_stack:
  added: []
  patterns: [FULL_ARGV_COMMANDS routing, lazy imports for MCP subprocess safety, sys.path fixture for test patching]
key_files:
  created: [tools/cli/research_bridge.py, tests/test_ris_bridge_cli_and_mcp.py, docs/features/FEATURE-ris-bridge-cli-and-mcp-v1.md, docs/dev_logs/2026-04-03_ris_final_bridge_and_mcp_fix.md]
  modified: [polytool/__main__.py, tools/cli/mcp_server.py]
decisions:
  - Keep polymarket.rag.* imports lazy in mcp_server (subprocess safety); fix test patching in test layer by adding packages/ to sys.path in fixture
  - KnowledgeStore imported at module level in research_bridge.py for test patchability (not a subprocess)
  - assert rc != 0 for argparse invalid-choice test (argparse exits with code 2, not 1)
metrics:
  duration_minutes: 45
  completed_date: "2026-04-03"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
  files_modified: 2
---

# Quick Task 260403-lir: Close the Bridge MCP Gaps in RIS-07 Done — Summary

**One-liner:** `polytool research-register-hypothesis` + `research-record-outcome` CLI commands added; `polymarket_rag_query` MCP tool now uses hybrid KnowledgeStore retrieval when default DB exists.

---

## What Was Built

### Task 1 — research-bridge CLI (GREEN)

Created `tools/cli/research_bridge.py` with argparse-based CLI bridge for RIS v1:

- `register-hypothesis`: loads candidate JSON (file or inline), validates `name` key, calls
  `register_research_hypothesis()`, emits `{"hypothesis_id": "hyp_...", "registry_path": "...", "candidate_name": "..."}` to stdout
- `record-outcome`: merges claim IDs, calls `record_validation_outcome()`, emits
  `{"claims_updated": N, "validation_status": "..."}` to stdout

Wired into `polytool/__main__.py` via `_FULL_ARGV_COMMANDS` so both commands receive the full
argv[0] as subcommand name. Visible in `python -m polytool --help`.

### Task 2 — MCP KnowledgeStore hybrid routing (GREEN)

Updated `polymarket_rag_query` in `tools/cli/mcp_server.py`:

- Checks `DEFAULT_KNOWLEDGE_DB_PATH.exists()` at call time
- When DB exists: `query_index(..., hybrid=True, top_k_vector=25, top_k_lexical=25, knowledge_store_path=ks_path)`
- When absent: vector-only fallback (original behavior preserved)
- Response JSON includes `ks_active: bool`
- All imports remain lazy inside function body (MCP subprocess transport safety)

### Task 3 — Tests, feature doc, dev log (DONE)

- `tests/test_ris_bridge_cli_and_mcp.py`: 11 offline tests across 3 classes
- `docs/features/FEATURE-ris-bridge-cli-and-mcp-v1.md`: full usage reference
- `docs/dev_logs/2026-04-03_ris_final_bridge_and_mcp_fix.md`: design decisions and commit log

---

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `6de368b` | feat | research-bridge CLI + __main__.py wiring |
| `9c40dc8` | feat | mcp_server KS hybrid routing |
| `35e5997` | test | 11-test suite for bridge CLI and MCP |
| `a961bc0` | docs | feature doc + dev log |

---

## Test Results

```
tests/test_ris_bridge_cli_and_mcp.py: 11 passed
Full regression suite: 3689 passed, 0 failed, 3 deselected, 25 warnings
```

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] argparse exits 2 (not 1) for invalid choice**
- **Found during:** Task 3 (TDD RED/GREEN)
- **Issue:** `test_record_outcome_invalid` asserted `rc == 1` but argparse's `choices` validation calls `sys.exit(2)` directly
- **Fix:** Changed assertion to `rc != 0`
- **Files modified:** `tests/test_ris_bridge_cli_and_mcp.py`

**2. [Rule 1 - Bug] MCP tests failed with `ModuleNotFoundError: No module named 'polymarket'`**
- **Found during:** Task 3 (TDD RED)
- **Issue:** `patch("polymarket.rag.embedder.SentenceTransformerEmbedder", ...)` requires `polymarket` to be importable; `packages/` was not on sys.path in test context
- **Fix:** Added `packages/` to sys.path in `_import_mcp_server` autouse fixture before patching runs
- **Files modified:** `tests/test_ris_bridge_cli_and_mcp.py`

**3. [Rule 1 - Rejected approach] Module-level imports in mcp_server**
- **Explored during:** Task 2
- **Issue:** Moving `polymarket.rag.*` to module level would simplify patching but breaks the MCP subprocess (`test_mcp_initialize_and_list_tools` failed)
- **Resolution:** Kept lazy imports; solved patching challenge in the test fixture instead

---

## Known Stubs

None. All data flows are wired end-to-end.

---

## Self-Check: PASSED

- `tools/cli/research_bridge.py` — exists
- `tests/test_ris_bridge_cli_and_mcp.py` — exists
- `docs/features/FEATURE-ris-bridge-cli-and-mcp-v1.md` — exists
- `docs/dev_logs/2026-04-03_ris_final_bridge_and_mcp_fix.md` — exists
- Commits `6de368b`, `9c40dc8`, `35e5997`, `a961bc0` — all exist in git log
- `python -m polytool --help | grep research-register` — shows both new commands
- `python -c "from tools.cli.mcp_server import polymarket_rag_query; print('ok')"` — ok
