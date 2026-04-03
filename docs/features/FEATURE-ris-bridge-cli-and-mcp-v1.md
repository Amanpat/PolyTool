# Feature: RIS Bridge CLI and MCP KnowledgeStore Routing (v1)

**Status:** Shipped (2026-04-03)
**Spec:** RIS-07
**Branch:** feat/ws-clob-feed (quick task 260403-lir)

---

## Overview

Two capability additions that close the final gaps in RIS v1:

1. **`research-register-hypothesis` and `research-record-outcome` CLI commands** — expose the
   `packages/research/integration/` hypothesis registration and validation feedback layer as
   first-class `polytool` subcommands, enabling CLI-driven and agent-driven RIS workflows.

2. **KnowledgeStore hybrid retrieval in `mcp_server.polymarket_rag_query`** — when the default
   KnowledgeStore DB exists at `kb/rag/knowledge/knowledge.sqlite3`, the MCP RAG query
   automatically uses hybrid retrieval (vector + lexical + KS claims) rather than vector-only.

---

## CLI Commands

### `python -m polytool research-register-hypothesis`

Registers a research hypothesis candidate in the JSONL hypothesis registry.

```
python -m polytool research-register-hypothesis \
    --candidate-json path/to/candidate.json \
    --registry-path kb/research/hypothesis_registry.jsonl
```

Or pass the candidate inline:

```
python -m polytool research-register-hypothesis \
    --candidate-json-string '{"name":"momentum_v1","hypothesis_text":"BTC momentum predicts direction","evidence_doc_ids":["doc_abc"]}' \
    --registry-path kb/research/hypothesis_registry.jsonl
```

**Required candidate fields:** `name` (string)
**Optional fields:** `hypothesis_text`, `evidence_doc_ids` (list of doc IDs)

**Output (stdout, JSON):**
```json
{
  "hypothesis_id": "hyp_a1b2c3d4e5f60000",
  "registry_path": "kb/research/hypothesis_registry.jsonl",
  "candidate_name": "momentum_v1"
}
```

**Exit codes:** 0 on success, 1 on validation or registration error.

**Provenance:** `evidence_doc_ids` flow through unchanged into the JSONL registry event under
`source.evidence_doc_ids`, preserving the D-01 provenance chain required by the RIS-07 spec.

---

### `python -m polytool research-record-outcome`

Records a SimTrader validation outcome for a set of KnowledgeStore claims, updating each
claim's `validation_status` field.

```
python -m polytool research-record-outcome \
    --hypothesis-id hyp_a1b2c3d4e5f60000 \
    --claim-ids claim_abc,claim_def \
    --outcome confirmed \
    --reason "Replay run showed positive PnL across all scenarios"
```

**Outcome values:** `confirmed`, `contradicted`, `inconclusive`

**Output (stdout, JSON):**
```json
{
  "claims_updated": 2,
  "claims_not_found": 0,
  "claims_failed": 0,
  "validation_status": "CONSISTENT_WITH_RESULTS"
}
```

`validation_status` reflects the full outcome label stored in KnowledgeStore:
- `confirmed` → `CONSISTENT_WITH_RESULTS`
- `contradicted` → `CONTRADICTED`
- `inconclusive` → `INCONCLUSIVE`

**Flags:**
- `--claim-ids ID1,ID2,...` — comma-separated list of claim IDs
- `--claim-id ID` (repeatable) — additional IDs, merged with `--claim-ids`
- `--knowledge-store PATH` — override the default KS SQLite path

---

## MCP Tool: `polymarket_rag_query`

### KnowledgeStore Routing (new behavior)

The `polymarket_rag_query` MCP tool now checks for the default KnowledgeStore DB at startup:

```
kb/rag/knowledge/knowledge.sqlite3
```

**When DB exists (`ks_active=true`):**
- Calls `query_index()` with `hybrid=True`, `top_k_vector=25`, `top_k_lexical=25`,
  and `knowledge_store_path=<db_path>`
- Returns vector, lexical, and KS claim results merged and ranked

**When DB absent (`ks_active=false`):**
- Falls back to vector-only private retrieval (original behavior)
- No error — graceful degradation

**Response JSON now includes `ks_active` bool:**
```json
{
  "success": true,
  "question": "...",
  "results": [...],
  "count": 8,
  "ks_active": true
}
```

### Implementation note

All `polymarket.rag.*` imports remain lazy (inside the function body). This is required because
the MCP server runs as a subprocess using stdio transport — any module-level import that fails
(e.g., missing `sentence-transformers`) would crash the subprocess before the MCP handshake
completes, causing silent failures in Claude Desktop.

---

## File Locations

| File | Purpose |
|------|---------|
| `tools/cli/research_bridge.py` | CLI handler (register-hypothesis + record-outcome) |
| `polytool/__main__.py` | Routes commands via `_FULL_ARGV_COMMANDS` |
| `tools/cli/mcp_server.py` | MCP server with KS routing in `polymarket_rag_query` |
| `packages/research/integration/hypothesis_bridge.py` | Core hypothesis registration logic |
| `packages/research/integration/validation_feedback.py` | Core validation feedback logic |
| `packages/polymarket/rag/knowledge_store.py` | KnowledgeStore + `DEFAULT_KNOWLEDGE_DB_PATH` |
| `tests/test_ris_bridge_cli_and_mcp.py` | 11-test offline suite |

---

## Tests

```
tests/test_ris_bridge_cli_and_mcp.py — 11 tests
  TestBridgeCLI_RegisterHypothesis   — 5 tests
  TestBridgeCLI_RecordOutcome        — 3 tests
  TestMCPKnowledgeStoreRouting       — 3 tests
```

All tests are offline (no network, no LLM, no ClickHouse). MCP tests use `unittest.mock.patch`
against `polymarket.rag.*` module paths; the test fixture ensures `packages/` is on `sys.path`
before patching runs.

Run:
```
python -m pytest tests/test_ris_bridge_cli_and_mcp.py -v --tb=short
```
