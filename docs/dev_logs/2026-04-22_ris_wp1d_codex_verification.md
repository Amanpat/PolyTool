---
date: 2026-04-22
work_packet: WP1-D
phase: RIS Phase 2A
slug: ris_wp1d_codex_verification
---

# WP1-D Read-Only Verification

## Scope

Read-only verification of the WP1-D foundational seed result using the existing WP1-D
dev log and current CLI state. No code, config, workflows, infra, or store contents
were modified. The only new file created is this verification log.

## Files Inspected

- `docs/dev_logs/2026-04-22_ris_wp1d_foundational_seed.md`

## Commands Run

### Session hygiene

Command:
```powershell
git status --short
```

Result:
```text
 M config/ris_eval_config.json
 M docs/CURRENT_DEVELOPMENT.md
 M docs/obsidian-vault/.obsidian/graph.json
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M packages/research/evaluation/artifacts.py
 M packages/research/evaluation/config.py
 M packages/research/evaluation/evaluator.py
 M packages/research/evaluation/replay.py
 M packages/research/evaluation/scoring.py
 M packages/research/metrics.py
 M tests/test_ris_evaluation.py
 M tests/test_ris_phase2_weighted_gate.py
 M tests/test_ris_phase5_provider_enablement.py
 M tools/cli/research_eval.py
?? docs/dev_logs/2026-04-22_ris_phase2a_activation_override.md
?? docs/dev_logs/2026-04-22_ris_wp1_context_fetch.md
?? docs/dev_logs/2026-04-22_ris_wp1a_scoring_weights.md
?? docs/dev_logs/2026-04-22_ris_wp1b_codex_verification.md
?? docs/dev_logs/2026-04-22_ris_wp1b_dimension_floors.md
?? docs/dev_logs/2026-04-22_ris_wp1b_prompt_drift_codex_verification.md
?? docs/dev_logs/2026-04-22_ris_wp1b_prompt_floor_drift_fix.md
?? docs/dev_logs/2026-04-22_ris_wp1c_provider_events_contract.md
?? docs/dev_logs/2026-04-22_ris_wp1d_foundational_seed.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_08-Research_10-Roadmap-v6_0-Master-Draft_md.ajson
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Roadmap_v6_0_Slim_Master_Restructure_md.ajson
?? "docs/obsidian-vault/Claude Desktop/08-Research/10-Roadmap-v6.0-Master-Draft.md"
?? "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Roadmap v6.0 Slim Master Restructure.md"
?? tests/test_ris_wp1a_scoring_weights.py
?? tests/test_ris_wp1b_dimension_floors.py
?? tests/test_ris_wp1b_prompt_floor_drift.py
```

Command:
```powershell
git log --oneline -5
```

Result:
```text
a610f18 Hermes Agent containerization
05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts
0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix
2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)
5962d46 docs(simtrader): PMXT Deliverable B docs close-out
```

### Required verification commands

Command:
```powershell
python -m polytool --help
```

Result:
```text
PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]

--- Research Loop (Track B) -------------------------------------------
  wallet-scan           Batch-scan many wallets/handles -> ranked leaderboard
  alpha-distill         Distill wallet-scan data -> ranked edge candidates (no LLM)
  hypothesis-register   Register a candidate in the offline hypothesis registry
  hypothesis-status     Update lifecycle status for a registered hypothesis
  hypothesis-diff       Compare two saved hypothesis.json artifacts
  hypothesis-summary    Extract a deterministic summary from hypothesis.json
  experiment-init       Create an experiment.json skeleton for a hypothesis
  experiment-run        Create a generated experiment attempt for a hypothesis
  hypothesis-validate   Validate a hypothesis JSON file against schema_v1

--- Analysis & Evidence -----------------------------------------------
  scan                  Run a one-shot scan via the PolyTool API
  batch-run             Batch-run scans and aggregate a hypothesis leaderboard
  audit-coverage        Offline accuracy + trust sanity check from scan artifacts
  export-dossier        Export an LLM Research Packet dossier + memo
  export-clickhouse     Export ClickHouse datasets for a user

--- RAG & Knowledge ---------------------------------------------------
  rag-refresh           Rebuild the local RAG index (one-command, use this first)
  rag-index             Build or rebuild the RAG index (full control)
  rag-query             Query the local RAG index
  rag-run               Re-execute bundle rag_queries.json and write results back
  rag-eval              Evaluate retrieval quality
  cache-source          Cache a trusted web source for RAG indexing
  llm-bundle            Build an LLM evidence bundle from dossier + RAG excerpts
  llm-save              Save an LLM report run into the private KB

--- Research Intelligence (RIS v1/v2) -----------------------------------
  research-eval             Evaluate a document through the RIS quality gate
  research-precheck         Pre-development check: GO / CAUTION / STOP recommendation
  research-ingest           Ingest a document into the RIS knowledge store
  research-seed             Seed the RIS knowledge store from a manifest
  research-benchmark        Compare extractor outputs on a fixture set
  research-calibration      Inspect precheck calibration health over the ledger
  research-extract-claims   Extract structured claims from ingested documents (no LLM)
  research-acquire          Acquire a source from URL and ingest into knowledge store
  research-report           Save, list, search reports and generate weekly digests
  research-scheduler        Manage the RIS background ingestion scheduler
  research-stats            Operator metrics snapshot and local-first export for RIS pipeline
  research-health           Print RIS health status summary from stored run data
  research-review           Inspect and resolve RIS review-queue items
  research-dossier-extract  Parse dossier artifacts -> KnowledgeStore (source_family=dossier_report)
  research-register-hypothesis  Register a research hypothesis candidate in the JSONL registry
  research-record-outcome       Record a validation outcome for KnowledgeStore claims

--- Crypto Pair Bot (Track 2 / Phase 1A - standalone) -----------------
  crypto-pair-scan      Dry-run: discover BTC/ETH/SOL 5m/15m pair markets, compute edge
  crypto-pair-run       Paper by default; live scaffold behind --live with explicit safety gates
  crypto-pair-backtest  Replay historical/synthetic pair observations, emit eval artifacts
  crypto-pair-report    Summarize one completed paper run into rubric-backed markdown + JSON
  crypto-pair-review    One-screen post-soak review: verdict, metrics, risk controls, promote-band fit
  crypto-pair-watch     Check whether eligible BTC/ETH/SOL 5m/15m markets exist; poll with --watch
  crypto-pair-await-soak Wait for eligible markets, then launch the standard Coinbase paper smoke soak
  crypto-pair-seed-demo-events Seed dev-only synthetic Track 2 rows into ClickHouse for dashboard checks

--- SimTrader / Execution (Track A, gated) ----------------------------
  simtrader             Record/replay/shadow/live trading - run 'simtrader --help'
  market-scan           Rank active Polymarket markets by reward/spread/fill quality
  scan-gate2-candidates Rank markets by Gate 2 binary_complement_arb executability
  prepare-gate2         Scan -> record -> check eligibility for Gate 2 (orchestrator)
  watch-arb-candidates  Watch a market list and auto-record on near-edge dislocation
  tape-manifest         Scan tape corpus, check eligibility, emit acquisition manifest
  gate2-preflight       Check whether Gate 2 sweep is ready and why it may be blocked
  make-session-pack     Create exact watchlist + watcher-compatible session plan for a capture session

--- Data Import (Phase 1 / Bulk Historical Foundation) ----------------
  import-historical     Validate and document local historical dataset layout
  smoke-historical      DuckDB smoke - validate pmxt/Jon raw files directly (no ClickHouse)
  fetch-price-2min      Fetch 2-min price history from CLOB API -> polytool.price_2min (ClickHouse)
  reconstruct-silver    Reconstruct a Silver tape (pmxt anchor + Jon fills + price_2min midpoint guide)
  batch-reconstruct-silver Batch-reconstruct Silver tapes for multiple tokens over one window
  benchmark-manifest    Build or validate the frozen benchmark_v1 tape manifest contract
  new-market-capture    Discover newly listed markets (<48h) and plan Gold tape capture
  capture-new-market-tapes  Record Gold tapes for benchmark_v1 new_market targets (batch)
  close-benchmark-v1        End-to-end benchmark closure: preflight + Silver + new-market + manifest
  summarize-gap-fill        Read-only diagnostic summary for gap_fill_run.json artifacts

--- Wallet Discovery (v1 / Loop A) ------------------------------------
  discovery             Wallet discovery commands - run 'discovery --help'
    run-loop-a          Fetch leaderboard -> churn detection -> enqueue new wallets

--- Integrations & Utilities ------------------------------------------
  mcp                   Start the MCP server for Claude Desktop integration
  examine               Legacy examination orchestrator (scan -> bundle -> prompt)
  agent-run             Run an agent task (internal)

Options:
  -h, --help        Show this help message
  --version         Show version information

Common workflows:
  # Research loop
  polytool wallet-scan --input wallets.txt --profile lite
  polytool alpha-distill --wallet-scan-run artifacts/research/wallet_scan/YYYY-MM-DD/<id>
  polytool rag-refresh              # rebuild RAG index (one command)
  polytool rag-query --question "strategy patterns" --hybrid --rerank

  # Single user examination
  polytool scan --user "@DrPufferfish"
  polytool llm-bundle --user "@DrPufferfish"

  # SimTrader (gated)
  polytool market-scan --top 5
  polytool simtrader shadow --market <slug> --strategy market_maker_v1 --duration 300

For more information, see:
  docs/runbooks/OPERATOR_QUICKSTART.md   (end-to-end guide)
  docs/runbooks/LOCAL_RAG_WORKFLOW.md    (RAG details)
  docs/runbooks/README_SIMTRADER.md      (SimTrader operator guide)
```

Command:
```powershell
python -m polytool research-stats summary --json
```

Result:
```json
{
  "generated_at": "2026-04-22T23:44:43+00:00",
  "total_docs": 59,
  "total_claims": 146,
  "docs_by_family": {
    "academic": 16,
    "blog": 16,
    "book": 1,
    "book_foundational": 11,
    "external_knowledge": 7,
    "github": 5,
    "manual": 3
  },
  "gate_distribution": {},
  "ingestion_by_family": {},
  "precheck_decisions": {
    "GO": 0,
    "CAUTION": 1,
    "STOP": 0
  },
  "reports_by_type": {
    "weekly_digest": 1
  },
  "total_reports": 1,
  "acquisition_new": 5,
  "acquisition_cached": 43,
  "acquisition_errors": 6,
  "provider_route_distribution": {},
  "provider_failure_counts": {},
  "review_queue": {
    "queue_depth": 1,
    "by_status": {
      "pending": 1
    },
    "by_gate": {
      "REVIEW": 1
    }
  },
  "disposition_distribution": {
    "ACCEPT": 0,
    "REVIEW": 0,
    "REJECT": 0,
    "BLOCKED": 0
  },
  "routing_summary": {
    "escalation_count": 0,
    "fallback_count": 0,
    "direct_count": 0,
    "total_routed": 0
  }
}
```

## Comparison Against WP1-D Seed Log

The inspected WP1-D seed log recorded:

- Pre-seed baseline: `total_docs: 48`, `total_claims: 146`, no `book_foundational`,
  `external_knowledge: 7`
- Dry run: `total: 11`
- Seed execution: `ingested: 11`, `failed: 0`, `skipped: 0`
- Post-seed verification: `total_docs: 59`, `book_foundational: 11`,
  `external_knowledge: 7`

Current CLI state matches that post-seed snapshot exactly:

- `total_docs` is still `59`
- `book_foundational` is still `11`
- `external_knowledge` is still `7`
- `total_claims` is still `146`

This is consistent with the intended 11-entry foundational manifest expectation:

- Logged dry run count was `11`
- Logged post-seed increase was `48 -> 59` (`+11`)
- Current live count for `docs_by_family.book_foundational` is exactly `11`

## Verification Result

- WP1-D verified complete: Yes
- `book_foundational >= 11`: Yes (`11`)
- Consistent with 11-entry foundational manifest expectation: Yes
- Hidden drift suggesting wrong DB or wrong manifest: No evidence

Why this looks real:

- The current store totals match the logged post-run totals exactly rather than only
  loosely.
- The family split is specific: `book_foundational` appears at exactly `11`, not `0`
  and not an inflated number that would suggest reseed drift.
- `external_knowledge` remains `7`, matching the logged post-seed state and arguing
  against the CLI pointing at a different local store.

## WP1-E Assessment

Current `external_knowledge` count is `7`.

Assessment:

- WP1-E appears already satisfied for a 5-doc minimum.
- No reseed work is indicated by the current store state.
- A separate reproducibility-only verification pass is optional if the operator wants
  an explicit WP1-E audit artifact, but it is not required to treat WP1-E as complete.

## Recommendation

Do not block progress on a separate WP1-E reseed or verification pass. Treat WP1-E as
already satisfied from current store state and proceed beyond WP1 unless a dedicated
reproducibility artifact is explicitly required.

## Codex Review

Tier: Skip. Verification-only work. No application code changed.
