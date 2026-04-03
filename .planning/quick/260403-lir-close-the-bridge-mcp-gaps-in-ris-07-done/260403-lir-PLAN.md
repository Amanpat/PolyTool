---
phase: quick-260403-lir
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/cli/research_bridge.py
  - polytool/__main__.py
  - tools/cli/mcp_server.py
  - tests/test_ris_bridge_cli_and_mcp.py
  - docs/features/FEATURE-ris-bridge-cli-and-mcp-v1.md
  - docs/dev_logs/2026-04-03_ris_final_bridge_and_mcp_fix.md
autonomous: true
requirements:
  - RIS-BRIDGE-CLI
  - RIS-MCP-KS-ROUTING

must_haves:
  truths:
    - "Operator can register a research hypothesis from a JSONL brief file via CLI"
    - "Operator can record a validation outcome (confirmed/contradicted/inconclusive) via CLI"
    - "MCP polymarket_rag_query includes KnowledgeStore-backed claims when the default DB exists"
    - "All new CLI paths exit 0 on valid inputs and emit parseable JSON output"
    - "Tests prove bridge CLI end-to-end and MCP KS routing without network calls"
  artifacts:
    - path: "tools/cli/research_bridge.py"
      provides: "research-register-hypothesis and research-record-outcome CLI subcommands"
      exports: ["main"]
    - path: "tests/test_ris_bridge_cli_and_mcp.py"
      provides: "offline tests for bridge CLI and MCP KS routing"
    - path: "docs/features/FEATURE-ris-bridge-cli-and-mcp-v1.md"
      provides: "operator-facing documentation for the two new surfaces"
    - path: "docs/dev_logs/2026-04-03_ris_final_bridge_and_mcp_fix.md"
      provides: "dev log for this work packet"
  key_links:
    - from: "tools/cli/research_bridge.py"
      to: "packages/research/integration/hypothesis_bridge.py"
      via: "direct import of register_research_hypothesis"
      pattern: "register_research_hypothesis"
    - from: "tools/cli/research_bridge.py"
      to: "packages/research/integration/validation_feedback.py"
      via: "direct import of record_validation_outcome"
      pattern: "record_validation_outcome"
    - from: "tools/cli/mcp_server.py polymarket_rag_query"
      to: "packages/polymarket/rag/knowledge_store.py"
      via: "KnowledgeStore instantiation when default DB path exists"
      pattern: "KnowledgeStore"
---

<objective>
Close the two remaining RIS_07 gaps: (1) add an operator-usable CLI bridge surface for
registering research hypotheses and recording validation feedback, and (2) fix MCP
polymarket_rag_query to include the KnowledgeStore-backed retrieval path.

Purpose: The bridge functions exist in packages/ but are unreachable by the operator without
writing Python. The MCP tool routes around the KnowledgeStore entirely, so Claude Code
sessions cannot benefit from RIS claims when querying via MCP. Both gaps block the
"RIS_07 done" milestone defined in the planning context.

Output:
- tools/cli/research_bridge.py — two subcommands: register-hypothesis, record-outcome
- polytool/__main__.py — two new command entries
- tools/cli/mcp_server.py — polymarket_rag_query updated to include KS path
- tests/test_ris_bridge_cli_and_mcp.py — offline tests for both surfaces
- docs/features/FEATURE-ris-bridge-cli-and-mcp-v1.md
- docs/dev_logs/2026-04-03_ris_final_bridge_and_mcp_fix.md
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/quick/260403-lir-close-the-bridge-mcp-gaps-in-ris-07-done/260403-lir-PLAN.md
@docs/CURRENT_STATE.md
@CLAUDE.md

<!-- Bridge implementation (already exists — use directly, do not re-implement) -->
@packages/research/integration/hypothesis_bridge.py
@packages/research/integration/validation_feedback.py
@packages/research/integration/__init__.py

<!-- MCP server to patch -->
@tools/cli/mcp_server.py

<!-- CLI routing to extend -->
@polytool/__main__.py

<!-- KnowledgeStore public API for MCP fix -->
@packages/polymarket/rag/knowledge_store.py

<!-- Reference: how rag_query.py handles --knowledge-store path -->
@tools/cli/rag_query.py
</context>

<interfaces>
<!-- Key interfaces the executor needs. Extracted from the codebase. -->

From packages/research/integration/hypothesis_bridge.py:
```python
def brief_to_candidate(brief: ResearchBrief) -> dict:
    """Convert a ResearchBrief into a hypothesis candidate dict."""

def precheck_to_candidate(precheck: EnhancedPrecheck) -> dict:
    """Convert an EnhancedPrecheck into a hypothesis candidate dict."""

def register_research_hypothesis(
    registry_path: str | Path,
    candidate: dict,
) -> str:
    """Write candidate to JSONL registry; returns hypothesis_id (hyp_<16hex>)."""
```

From packages/research/integration/validation_feedback.py:
```python
OUTCOME_MAP: dict[str, str] = {
    "confirmed": "CONSISTENT_WITH_RESULTS",
    "contradicted": "CONTRADICTED",
    "inconclusive": "INCONCLUSIVE",
}

def record_validation_outcome(
    store: KnowledgeStore,
    hypothesis_id: str,
    claim_ids: list[str],
    outcome: str,   # "confirmed" | "contradicted" | "inconclusive"
    reason: str,
) -> dict:
    """Returns summary dict with claims_updated, claims_not_found, claims_failed."""
```

From packages/polymarket/rag/knowledge_store.py:
```python
DEFAULT_KNOWLEDGE_DB_PATH = Path("kb") / "rag" / "knowledge" / "knowledge.sqlite3"

class KnowledgeStore:
    def __init__(self, db_path: str | Path = DEFAULT_KNOWLEDGE_DB_PATH): ...
    def query_claims(self, *, include_archived=False, include_superseded=False,
                     apply_freshness=True) -> list[dict]: ...
    def update_claim_validation_status(self, claim_id, status, actor): ...
```

From tools/cli/mcp_server.py (current — the part to patch):
```python
@mcp_app.tool()
def polymarket_rag_query(question: str, user: str = "", k: int = 8) -> str:
    from polymarket.rag.embedder import DEFAULT_EMBED_MODEL, SentenceTransformerEmbedder
    from polymarket.rag.query import query_index
    with _suppress_stdout():
        embedder = SentenceTransformerEmbedder(model_name=DEFAULT_EMBED_MODEL)
        results = query_index(
            question=question, embedder=embedder, k=k,
            user_slug=user or None, private_only=True,
        )
    # BUG: no hybrid=True, no knowledge_store_path — KnowledgeStore is never queried
    return json.dumps({"success": True, "question": question,
                       "results": results, "count": len(results)})
```

From polytool/__main__.py (pattern to follow for new commands):
```python
research_health_main = _command_entrypoint("tools.cli.research_health")
# ...
"research-health": "research_health_main",
# ...
print("  research-health           ...")
```
</interfaces>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add research-register-hypothesis and research-record-outcome CLI commands</name>
  <files>tools/cli/research_bridge.py, polytool/__main__.py</files>
  <behavior>
    - register-hypothesis subcommand: reads a candidate JSON file (--candidate-json PATH or
      --candidate-json-string STR), calls register_research_hypothesis(registry_path, candidate),
      prints JSON with hypothesis_id and registry_path, exits 0.
    - register-hypothesis: --registry-path defaults to
      "kb/research/hypothesis_registry.jsonl"; --candidate-json reads file;
      --candidate-json-string accepts raw JSON string.
    - register-hypothesis: exits 1 with error message if candidate JSON is invalid or
      missing required "name" key.
    - record-outcome subcommand: accepts --hypothesis-id STR --claim-ids COMMA_SEP_STR
      --outcome {confirmed,contradicted,inconclusive} --reason STR --knowledge-store PATH
      (defaults to DEFAULT_KNOWLEDGE_DB_PATH). Calls record_validation_outcome(), prints
      JSON summary, exits 0.
    - record-outcome: exits 1 with message if outcome value is invalid.
    - record-outcome: --claim-ids accepts comma-separated or repeated --claim-id flags
      (either form works).
    - polytool/__main__.py: add research_bridge_main entrypoint; register
      "research-register-hypothesis" and "research-record-outcome" both mapping to it;
      add both to help text under "Research / dossier" section.
    - Both subcommands route via sys.argv[0] being the subcommand name (FULL_ARGV_COMMANDS
      pattern already used for hypothesis-register).
  </behavior>
  <action>
    Create tools/cli/research_bridge.py with build_parser() and main(argv) following the
    exact pattern of tools/cli/research_health.py (simple argparse, import bridge functions
    inside main to keep import cost lazy).

    Two subparsers: "register-hypothesis" and "record-outcome".

    For register-hypothesis:
    - Parse --candidate-json (file path) or --candidate-json-string (raw JSON)
    - Load candidate dict from whichever was provided; bail with exit 1 if neither given
    - Validate "name" key present; bail with exit 1 if not
    - Import register_research_hypothesis from packages.research.integration
    - Call register_research_hypothesis(args.registry_path, candidate)
    - Print json.dumps({"hypothesis_id": hyp_id, "registry_path": str(args.registry_path),
        "candidate_name": candidate["name"]})
    - Exit 0

    For record-outcome:
    - Parse --hypothesis-id, --claim-ids (comma-sep), --claim-id (repeatable, merged with
      --claim-ids), --outcome, --reason, --knowledge-store (default: str(DEFAULT_KNOWLEDGE_DB_PATH))
    - Merge all claim IDs into a deduplicated list
    - Import KnowledgeStore from packages.polymarket.rag.knowledge_store
    - Import record_validation_outcome from packages.research.integration
    - Instantiate KnowledgeStore(db_path=args.knowledge_store)
    - Call record_validation_outcome(store, args.hypothesis_id, claim_ids, args.outcome, args.reason)
    - Print json.dumps(result)
    - Exit 0

    In polytool/__main__.py:
    - Add: research_bridge_main = _command_entrypoint("tools.cli.research_bridge")
    - Add to _COMMAND_HANDLER_NAMES: "research-register-hypothesis": "research_bridge_main",
      "research-record-outcome": "research_bridge_main"
    - Add both to _FULL_ARGV_COMMANDS so sys.argv[0] is the subcommand
    - Add help lines near the research-* block

    Evidence chain requirement (per D-01 spec from RIS_07): evidence_doc_ids from the
    candidate dict must flow through to the registry event unchanged. Do not strip this
    field in the CLI layer.
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_bridge_cli_and_mcp.py -k "bridge_cli" -x --tb=short -q</automated>
  </verify>
  <done>
    - research-register-hypothesis exits 0 and prints JSON with hypothesis_id when given valid candidate
    - research-record-outcome exits 0 and prints JSON with claims_updated when given valid params
    - Both commands appear in python -m polytool --help output
    - Both subcommands exit 1 with error message on invalid inputs
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Fix MCP polymarket_rag_query to include KnowledgeStore retrieval path</name>
  <files>tools/cli/mcp_server.py</files>
  <behavior>
    - When DEFAULT_KNOWLEDGE_DB_PATH exists on disk, polymarket_rag_query uses hybrid=True
      and passes knowledge_store_path=DEFAULT_KNOWLEDGE_DB_PATH to query_index.
    - When DEFAULT_KNOWLEDGE_DB_PATH does not exist, polymarket_rag_query falls back to
      the current behavior (no KS, private_only vector query). No error raised.
    - The "ks_active" key is added to the JSON response indicating whether KS was used.
    - The function signature does not change (backward compatible: same args question/user/k).
    - Hybrid mode also sets top_k_vector=25, top_k_lexical=25 (matching rag_query.py defaults).
  </behavior>
  <action>
    In tools/cli/mcp_server.py, update polymarket_rag_query:

    1. Add import at top of function (lazy, inside with _suppress_stdout()):
       from polymarket.rag.knowledge_store import DEFAULT_KNOWLEDGE_DB_PATH

    2. Check if the default DB path exists:
       ks_path = DEFAULT_KNOWLEDGE_DB_PATH
       ks_active = ks_path.exists()

    3. Call query_index with conditional kwargs:
       if ks_active:
           results = query_index(
               question=question, embedder=embedder, k=k,
               user_slug=user or None, private_only=True,
               hybrid=True, top_k_vector=25, top_k_lexical=25,
               knowledge_store_path=ks_path,
           )
       else:
           results = query_index(
               question=question, embedder=embedder, k=k,
               user_slug=user or None, private_only=True,
           )

    4. Add "ks_active": ks_active to the returned JSON dict.

    The module-level docstring already lists "polymarket_rag_query: Query the local RAG
    index" -- update the comment to mention KnowledgeStore routing.

    Do NOT change the function signature or any other tool in the file.
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_bridge_cli_and_mcp.py -k "mcp" -x --tb=short -q</automated>
  </verify>
  <done>
    - polymarket_rag_query returns ks_active=True when default DB exists
    - polymarket_rag_query returns ks_active=False (no error) when default DB absent
    - Existing MCP tool behavior (result list, success key) preserved
    - python -m polytool --help still loads (no import breakage)
  </done>
</task>

<task type="auto">
  <name>Task 3: Tests, feature doc, and dev log</name>
  <files>
    tests/test_ris_bridge_cli_and_mcp.py,
    docs/features/FEATURE-ris-bridge-cli-and-mcp-v1.md,
    docs/dev_logs/2026-04-03_ris_final_bridge_and_mcp_fix.md
  </files>
  <action>
    CREATE tests/test_ris_bridge_cli_and_mcp.py with the following test classes.
    All tests must be offline and deterministic (no network calls, no LLM calls,
    no disk side-effects beyond tmpdir).

    Class TestBridgeCLI_RegisterHypothesis (tag: bridge_cli):
    - test_register_valid_candidate: write minimal candidate JSON to tmp file,
      call main(["register-hypothesis", "--candidate-json", str(path),
      "--registry-path", str(tmpdir/"reg.jsonl")]), assert exit 0,
      assert output JSON has hypothesis_id starting with "hyp_",
      assert reg.jsonl exists and contains one line with "research_bridge".
    - test_register_json_string: same but uses --candidate-json-string with inline JSON.
    - test_register_missing_name_key: candidate JSON without "name", assert exit 1.
    - test_register_no_input: no --candidate-json and no --candidate-json-string, assert exit 1.
    - test_register_evidence_doc_ids_preserved: candidate with evidence_doc_ids=["doc_abc"],
      assert registry JSONL event["source"]["evidence_doc_ids"] == ["doc_abc"].

    Class TestBridgeCLI_RecordOutcome (tag: bridge_cli):
    - test_record_outcome_confirmed: create in-memory KS, add a claim, patch KnowledgeStore
      constructor to return that in-memory instance, call main(["record-outcome",
      "--hypothesis-id", "hyp_test", "--claim-ids", claim_id,
      "--outcome", "confirmed", "--reason", "replay positive"]),
      assert exit 0, assert JSON output has claims_updated=1, validation_status="CONSISTENT_WITH_RESULTS".
    - test_record_outcome_invalid: --outcome "unknown_value", assert exit 1.
    - test_record_outcome_empty_claim_ids: --claim-ids "" (empty), assert exit 0 with claims_updated=0.

    Class TestMCPKnowledgeStoreRouting (tag: mcp):
    - test_mcp_ks_active_when_db_exists: patch DEFAULT_KNOWLEDGE_DB_PATH.exists to return True,
      patch query_index to capture kwargs, call polymarket_rag_query("test question"),
      assert kwargs["hybrid"] is True and kwargs["knowledge_store_path"] is not None,
      assert json.loads(result)["ks_active"] is True.
    - test_mcp_ks_inactive_when_db_absent: patch exists to return False,
      patch query_index to capture kwargs, call polymarket_rag_query("test question"),
      assert "knowledge_store_path" not in kwargs OR kwargs.get("knowledge_store_path") is None,
      assert json.loads(result)["ks_active"] is False.
    - test_mcp_result_structure_unchanged: both ks_active=True and False cases return JSON
      with keys: success, question, results, count, ks_active.

    After writing tests, run full regression suite and report counts:
    python -m pytest tests/test_ris_bridge_cli_and_mcp.py -v --tb=short
    python -m pytest tests/ -x -q --tb=short

    CREATE docs/features/FEATURE-ris-bridge-cli-and-mcp-v1.md documenting:
    - research-register-hypothesis: synopsis, flags, example invocation, output format
    - research-record-outcome: synopsis, flags, example invocation, output format
    - MCP polymarket_rag_query KS routing: when ks_active fires, fallback behavior,
      ks_active field in response
    - evidence_doc_ids provenance chain (brief -> candidate -> registry event)
    - v2 deferred: auto-loop, Discord hooks, scheduled re-validation

    CREATE docs/dev_logs/2026-04-03_ris_final_bridge_and_mcp_fix.md with:
    - Objective
    - Files changed table
    - Design decisions (why subparser approach, why ks_active fallback, provenance chain)
    - Commands run + exact test results
    - v2 deferred items
    - Codex review tier (Skip — no execution/risk code)
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_bridge_cli_and_mcp.py -v --tb=short -q && python -m polytool --help | grep -E "research-register|research-record"</automated>
  </verify>
  <done>
    - All tests in test_ris_bridge_cli_and_mcp.py pass
    - Full regression suite passes with 0 new failures (report exact count)
    - Feature doc and dev log exist at the specified paths
    - python -m polytool --help lists both new commands
  </done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Smoke test bridge CLI:
   echo '{"name":"test_hypothesis_v1","hypothesis_text":"test","evidence_doc_ids":["doc1"]}' > /tmp/cand.json
   python -m polytool research-register-hypothesis --candidate-json /tmp/cand.json --registry-path /tmp/test_reg.jsonl
   # Expect: JSON with hypothesis_id starting "hyp_", exit 0

2. Smoke test MCP server import:
   python -c "from tools.cli.mcp_server import polymarket_rag_query; print('mcp import ok')"

3. Full CLI help loads:
   python -m polytool --help | grep -c "research-"
   # Expect: at least 14 lines (was 12, adding 2 new commands)

4. Regression suite:
   python -m pytest tests/ -x -q --tb=short
   # Expect: 0 new failures vs baseline of 3660 passing
</verification>

<success_criteria>
- research-register-hypothesis CLI: exits 0 on valid input, prints JSON with hypothesis_id,
  appends JSONL event with research_bridge provenance and evidence_doc_ids intact
- research-record-outcome CLI: exits 0 on valid input, prints JSON with claims_updated count,
  validates outcome values and exits 1 on bad input
- MCP polymarket_rag_query: ks_active=True when default DB present (hybrid+KS path used);
  ks_active=False when absent (graceful fallback, no error)
- All new tests pass; full regression suite has 0 new failures
- Feature doc and dev log exist at specified paths
</success_criteria>

<output>
After completion, create .planning/quick/260403-lir-close-the-bridge-mcp-gaps-in-ris-07-done/260403-lir-SUMMARY.md
</output>
