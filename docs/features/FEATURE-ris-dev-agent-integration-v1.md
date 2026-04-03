# RIS Dev Agent Integration v1

**Status:** Shipped (2026-04-03)
**Task:** quick-260403-jyl
**Covers:** CLAUDE.md RIS section, fast-research preservation workflow, operator recipes

---

## Purpose

Dev agents (Claude Code, Codex, Gemini CLI) previously had no in-repo guidance about
the Research Intelligence System. CLAUDE.md lacked any RIS section. Operators had no
documented workflow for preserving fast-research findings from LLM sessions, web
searches, or paper reads into RIS.

This feature closes RIS_07 at practical v1 scope by:

1. Adding a "Research Intelligence System (RIS)" section to CLAUDE.md with the dev-agent
   pre-build workflow (precheck -> query -> build).
2. Documenting the fast-research preservation loop so operators can feed findings from
   ad-hoc sessions into the persistent knowledge store.
3. Adding integration tests that prove the documented round-trips actually work.

---

## Dev Agent Workflow

Before starting any feature or strategy implementation, a dev agent should:

**Step 1 — Precheck the idea:**
```bash
python -m polytool research-precheck run --idea "description of planned work" --no-ledger
```

**Step 2 — Act on the recommendation:**
- STOP: surface to operator before continuing
- CAUTION: note concerns, proceed with awareness
- GO: no blockers, proceed

**Step 3 — Query for deeper context if needed:**
```bash
python -m polytool rag-query --question "relevant topic" --hybrid --knowledge-store default
```

**Step 4 — Inspect contradictions if precheck flagged any:**
```bash
python -m polytool research-precheck inspect --db kb/rag/knowledge/knowledge.sqlite3
```

---

## Fast-Research Preservation Loop

When an operator or agent has a productive research session (LLM chat, web search,
reading a paper), the findings should be preserved in RIS for permanent queryability.

### Why this matters

LLM sessions are ephemeral. Chat context disappears. The RIS is persistent and
domain-specific. Findings that go through the preservation loop are permanently
queryable by all future sessions and included in precheck contradictions.

### Preservation triggers

- Found a useful academic paper or blog post
- A ChatGPT / Gemini / Claude session produced a valuable insight
- A web search surfaced a relevant research finding
- Manual analysis yielded a key conclusion worth keeping

### Preservation commands

All commands use `--no-eval` to skip LLM scoring and ingest with manual trust:

```bash
# Save a URL (paper, GitHub repo, blog post)
python -m polytool research-acquire --url URL --source-family FAMILY --no-eval

# Save a manual summary (from any LLM session or manual analysis)
python -m polytool research-ingest --text "finding text" --title "Finding Title" \
  --source-type manual --no-eval

# Save from a file (notes, exported doc)
python -m polytool research-ingest --file path/to/notes.md --source-type manual --no-eval
```

---

## Operator Recipes

### Recipe A: "I found a useful paper"

```bash
python -m polytool research-acquire \
  --url https://arxiv.org/abs/2301.12345 \
  --source-family academic \
  --no-eval
```

For a non-academic paper (blog, book):
```bash
python -m polytool research-acquire \
  --url https://theblog.example/market-making-insights \
  --source-family blog \
  --no-eval
```

### Recipe B: "I learned something from a ChatGPT/Gemini session"

```bash
python -m polytool research-ingest \
  --text "Avellaneda-Stoikov spread formula uses gamma (risk aversion) and sigma-squared (volatility). Wider spreads near p=0.5 are mathematically justified. Source: GPT-4 session 2026-04-03." \
  --title "A-S Spread Formula Notes from GPT-4 Session" \
  --source-type manual \
  --no-eval
```

### Recipe C: "I want to check if RIS knows about X before building"

```bash
python -m polytool research-precheck run \
  --idea "Implement momentum signal for 5m BTC crypto pair bot" \
  --no-ledger
```

If the result is GO and you want deeper context:
```bash
python -m polytool rag-query \
  --question "crypto pair bot momentum signal" \
  --hybrid \
  --knowledge-store default
```

### Recipe D: "I want to save my notes file after research"

```bash
python -m polytool research-ingest \
  --file docs/research_notes/2026-04-03_market_maker_analysis.md \
  --source-type manual \
  --no-eval
```

### Recipe E: Check pipeline health after a batch ingest

```bash
python -m polytool research-health
python -m polytool research-stats summary
```

---

## Integration Test Coverage

`tests/test_ris_integration_workflow.py` provides round-trip tests:

| Test | What it covers |
|------|----------------|
| `test_precheck_round_trip` | Ingest doc, run precheck on related topic, verify exit 0 and verdict |
| `test_ingest_text_then_query_ks` | Ingest via --text, query KS directly, verify retrieval |
| `test_acquire_dry_run` | research-acquire --dry-run exits 0 without writing to KS |
| `test_ingest_file_round_trip` | Write temp .md, ingest via --file, query KS for retrieval |
| `test_precheck_contradiction_best_effort` | Ingest contradicting docs, verify precheck exits 0 and produces output |

---

## v2 Deferred Items

These items are explicitly out of scope for v1. They require additional infrastructure
or are dependent on Phase 3+ roadmap items:

- **Dossier-to-external-knowledge extraction (RIS_07 Section 1):** Auto-extract key
  findings from wallet dossiers into `external_knowledge` partition. Requires LLM
  extraction prompt and integration with `wallet-scan` / `alpha-distill`.

- **Auto-discovery -> knowledge loop (RIS_07 Section 2):** Candidate scanner discovers
  wallet -> dossier_extractor pulls findings -> external_knowledge grows automatically.
  Requires Section 1 as prerequisite.

- **SimTrader bridge / auto-hypothesis generation (RIS_07 Section 3):** Synthesis engine
  generates hypothesis candidates for the hypothesis registry when HIGH-confidence
  findings are identified. Phase R5 / v2 deliverable.

- **ChatGPT architect integration via Google Drive (RIS_07 Section 4):** ChatGPT Google
  Drive connector reads `artifacts/research/reports/` to ground specs in empirical
  evidence. Requires manual drive sync setup.

- **MCP polymarket_rag_query auto-routing (not yet wired to KS):** The existing MCP tool
  queries Chroma but does not include the KnowledgeStore as a retrieval source. A v2
  task should wire `knowledge_store_path=default` into the MCP tool's `query_index` call.

---

*End of FEATURE-ris-dev-agent-integration-v1.md*
