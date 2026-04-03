# Dev Log: RIS Final Bridge CLI and MCP Fix (2026-04-03)

**Task:** quick-260403-lir — Close the bridge MCP gaps in RIS-07 done
**Branch:** feat/ws-clob-feed
**Author:** Claude Code (quick task executor)

---

## Objective

Close the two remaining gaps in RIS v1 that were blocking the "done" declaration in RIS-07:

1. No CLI entry points for `register_research_hypothesis` and `record_validation_outcome` —
   the core logic existed in `packages/research/integration/` but had no `polytool` commands.
2. `mcp_server.polymarket_rag_query` was vector-only; it did not use hybrid KnowledgeStore
   retrieval when the default KS DB was present.

---

## Work Performed

### Task 1: research-bridge CLI

Created `tools/cli/research_bridge.py` with two subcommands:

- `register-hypothesis` — accepts candidate JSON (file or inline string), validates `name` key,
  calls `register_research_hypothesis()`, emits JSON with `hypothesis_id` to stdout
- `record-outcome` — accepts claim IDs (comma-separated or repeatable `--claim-id`), calls
  `record_validation_outcome()`, emits JSON with `claims_updated` count to stdout

Wired into `polytool/__main__.py`:
- Added `research_bridge_main = _command_entrypoint("tools.cli.research_bridge")`
- Added both commands to `_COMMAND_HANDLER_NAMES` and `_FULL_ARGV_COMMANDS`
- Added both to `print_usage()` under the Research Intelligence section

The `KnowledgeStore` class is imported at module level in `research_bridge.py` (not lazy) so
that test patches via `patch("tools.cli.research_bridge.KnowledgeStore", ...)` work correctly.

### Task 2: MCP KnowledgeStore routing

Updated `polymarket_rag_query` in `tools/cli/mcp_server.py`:

- Added lazy import of `DEFAULT_KNOWLEDGE_DB_PATH` from `polymarket.rag.knowledge_store`
- Checks `ks_path.exists()` at call time (not module load time)
- When DB exists: `query_index(..., hybrid=True, top_k_vector=25, top_k_lexical=25, knowledge_store_path=ks_path)`
- When DB absent: falls back to existing vector-only call
- Added `ks_active` bool to the JSON response

All `polymarket.rag.*` imports remain lazy (inside the function body) to preserve MCP subprocess
safety — module-level imports that fail would crash the subprocess before the MCP handshake.

### Task 3: Tests, feature doc, dev log

Created `tests/test_ris_bridge_cli_and_mcp.py` — 11 offline tests:
- `TestBridgeCLI_RegisterHypothesis` (5): file input, string input, missing name key, no input,
  evidence_doc_ids preservation
- `TestBridgeCLI_RecordOutcome` (3): confirmed outcome, invalid outcome (argparse exits 2),
  empty claim_ids
- `TestMCPKnowledgeStoreRouting` (3): ks active path, ks absent path, result structure

Key fix for MCP tests: the autouse fixture adds `packages/` to `sys.path` before patching.
Without this, `patch("polymarket.rag.embedder.SentenceTransformerEmbedder", ...)` fails with
`ModuleNotFoundError: No module named 'polymarket'` because `polymarket` lives under `packages/`
which is not on sys.path by default in the test runner context.

---

## Commits

| Hash | Description |
|------|-------------|
| `6de368b` | feat(quick-260403-lir-01): add research-bridge CLI and wire into polytool |
| `9c40dc8` | feat(quick-260403-lir-02): add KnowledgeStore hybrid retrieval path to mcp_server |
| `35e5997` | test(quick-260403-lir-03): add 11-test suite for research-bridge CLI and MCP KS routing |

---

## Test Results

```
tests/test_ris_bridge_cli_and_mcp.py: 11 passed
Full suite: 3689 passed, 0 failed, 3 deselected, 25 warnings
```

---

## Smoke Tests

```bash
# CLI smoke test
python -m polytool --help | grep research-register  # shows command
python -m polytool research-register-hypothesis --help  # shows usage

# MCP import smoke test
python -c "from tools.cli.mcp_server import polymarket_rag_query; print('mcp import ok')"
```

---

## Key Design Decisions

1. **Lazy vs. module-level imports in mcp_server**: kept lazy. Module-level imports risk
   crashing the MCP subprocess if optional deps (sentence-transformers, sqlite3 path) aren't
   present. The test patching challenge was solved in the test layer (sys.path fix in fixture),
   not by changing the production code.

2. **`KnowledgeStore` at module level in research_bridge**: not lazy. The `_cmd_record_outcome`
   handler patches `tools.cli.research_bridge.KnowledgeStore` in tests, which requires the
   class to be importable at module scope. research_bridge.py is not a subprocess — it's a
   normal CLI module so this is safe.

3. **`argparse` exits with code 2 for invalid choices**: the `test_record_outcome_invalid`
   test asserts `rc != 0` (not `rc == 1`) because argparse's `choices` validation calls
   `sys.exit(2)` directly. Documented in test docstring.

---

## Codex Review

- Tier: Skip (CLI formatting + tests)
- No adversarial review required: no execution, risk, or signing code touched

---

## Open Items

None. All RIS-07 bridge gaps closed.
