# 2026-04-22 Deliverable C Content Plan

## Scope

Read-only content planning for Deliverable C from `Work-Packet - Unified Open Source Integration Sprint.md`.
Objective: convert the packet's 7 target `external_knowledge` documents into concise, ingestion-friendly briefs for a later seeding pass.

No code changes were made. No RIS logic changes were proposed. This note is the only repo change.

## Repo State Note

- The worktree was already dirty at session start, primarily under `docs/obsidian-vault/` with many deleted and generated files unrelated to this task.
- Those pre-existing changes were not modified.
- Because several packet source files were deleted in the current worktree, they were inspected read-only from `HEAD` via `git show`.

## Files Inspected

- `docs/obsidian-vault/12-Ideas/Work-Packet - Unified Open Source Integration Sprint.md` (read via `git show HEAD:...`)
- `docs/obsidian-vault/12-Ideas/Work-Packet - Unified Open Source Integration.md` (read via `git show HEAD:...`)
- `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md`
- `docs/obsidian-vault/11-Prompt-Archive/2026-04-10 GLM5 - Unified Gap Fill Open Source Integration.md` (read via `git show HEAD:...`)
- `docs/obsidian-vault/08-Research/09-Hermes-PMXT-Deep-Dive.md` (read via `git show HEAD:...`)
- `docs/obsidian-vault/08-Research/07-Backtesting-Repo-Deep-Dive.md` (read via `git show HEAD:...`)
- `docs/obsidian-vault/08-Research/08-Copy-Trader-Deep-Dive.md` (read via `git show HEAD:...`)
- `docs/obsidian-vault/12-Ideas/Idea - Cross-Platform Price Divergence as RIS Signal.md` (read via `git show HEAD:...`)

## Commands Run

### Safety and context checks

Command:

```powershell
git log --oneline -5
```

Output:

```text
5962d46 docs(simtrader): PMXT Deliverable B docs close-out
efb6f01 feat(simtrader): PMXT Deliverable B -- merge-ready sports strategies
504e7b7 Fee Model Overhaul
42d9985 docs: add AGENTS.md and CURRENT_DEVELOPMENT.md for workflow refresh
2dc03a7 docs(quick-260415-rdy): complete Loop D feasibility -- add plan artifact and update STATE.md
```

Command:

```powershell
python -m polytool --help
```

Output:

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

### Read-only inspection commands

The following commands were used to read packet and research notes. Outputs were reviewed live in the terminal and summarized below rather than reproduced verbatim because they were the source documents themselves.

- `git show HEAD:"docs/obsidian-vault/12-Ideas/Work-Packet - Unified Open Source Integration Sprint.md"`
- `git show HEAD:"docs/obsidian-vault/12-Ideas/Work-Packet - Unified Open Source Integration.md"`
- `Get-Content "docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md"`
- `git show HEAD:"docs/obsidian-vault/11-Prompt-Archive/2026-04-10 GLM5 - Unified Gap Fill Open Source Integration.md"`
- `git show HEAD:"docs/obsidian-vault/08-Research/09-Hermes-PMXT-Deep-Dive.md"`
- `git show HEAD:"docs/obsidian-vault/08-Research/07-Backtesting-Repo-Deep-Dive.md"`
- `git show HEAD:"docs/obsidian-vault/08-Research/08-Copy-Trader-Deep-Dive.md"`
- `git show HEAD:"docs/obsidian-vault/12-Ideas/Idea - Cross-Platform Price Divergence as RIS Signal.md"`
- `git grep -n "Levenshtein\|Jaccard\|matcher.js\|AhaSignals\|cross-platform" HEAD -- "docs/obsidian-vault"`

## Decisions Made

- Treat the Deliverable C section of `Work-Packet - Unified Open Source Integration Sprint.md` as the metadata source of truth when it differs from the older unified packet.
- Keep all 7 planned documents implementation-neutral and ready for `partition: external_knowledge`.
- Preserve the packet's intended metadata pattern: `freshness_tier: CURRENT`, `validation_status: UNTESTED`, and packet-specific `confidence_tier`.
- Add explicit cautions where the local repo only contains secondary references or mixed-license extraction notes.

## Document Briefs

### 1. Polymarket Fee Structure (April 2026)

**Metadata**

```yaml
title: Polymarket Fee Structure (April 2026)
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
partition: external_knowledge
```

**Content outline**

- Define the taker fee formula as `fee = C * feeRate * p * (1 - p)` with `C` as filled shares and `p` as fill price on the 0-1 scale.
- List category fee rates called out in the packet: crypto `0.072`, sports `0.03`, finance/politics/mentions/tech `0.04`, economics/culture/weather/other `0.05`, geopolitics `0`.
- State that geopolitics is fee-free and therefore has no ordinary taker fee burden.
- State clearly that makers do not pay per-fill fees.
- Describe maker rebates as a separate daily market-level redistribution funded from a share of taker fees, not as an immediate negative fee on each fill.
- Describe rebate allocation in terms of `fee_equivalent = C * feeRate * p * (1 - p)` so the same curve is used for allocation weighting.
- Note the packet's rebate-share split: crypto markets redistribute 20% of taker fees; other fee-paying categories redistribute 25%.
- Keep Q-score or liquidity rewards separate from maker rebates so retrieval does not conflate two distinct incentive programs.
- Note that token-specific `/fee-rate` responses may differ from broad category tables and should be cited carefully, especially for crypto markets.

**Retrieval keywords**

- `Polymarket fee formula`
- `maker rebate pool`
- `fee equivalent p(1-p)`
- `/fee-rate base_fee`
- `crypto 0.072 feeRate`
- `Q-score vs maker rebates`

**Source-quality caution**

- Extra care required at seeding time: use an exact Polymarket primary source or archived docs snapshot for the category table, maker rebate mechanics, and `/fee-rate` behavior. The local notes contain corrections to prior assumptions, so precise attribution matters.

### 2. Kalshi Fee Structure (April 2026)

**Metadata**

```yaml
title: Kalshi Fee Structure (April 2026)
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
partition: external_knowledge
```

**Content outline**

- Define the standard fee formula as `fee = round_up(0.07 * C * P * (1 - P))`.
- Clarify that `C` is contracts and `P` is price in dollars on the `0.01` to `0.99` scale.
- State that the formula uses the same `P * (1 - P)` shape as Polymarket but with a fixed `0.07` multiplier instead of a category table.
- State that fees round up to the nearest cent, which matters for small trades and examples.
- Note that maker/taker distinctions exist and some markets may expose `fee_waiver` fields or special treatment.
- Separate the standard fee schedule from fee-waived markets and from the Liquidity Incentive Program so those concepts are not merged.
- Mention the packet's pointer to fee-change history and per-market fee metadata as implementation-time attribution targets.
- Include at least one worked example in the eventual seed doc so retrieval can anchor on the formula as well as its practical interpretation.
- Note that cross-platform comparisons must normalize Kalshi's cents-and-contracts framing against Polymarket's shares-and-probabilities framing.

**Retrieval keywords**

- `Kalshi fee formula`
- `0.07 C P 1-P`
- `round up nearest cent`
- `Kalshi fee waiver`
- `fee_changes`
- `maker taker Kalshi`

**Source-quality caution**

- Extra care required at seeding time: the local packet evidence is secondary. Use official Kalshi docs, API docs, or filing text for the exact fee formula, fee-waiver handling, and maker/taker treatment.

### 3. pmxt SDK Operational Gotchas

**Metadata**

```yaml
title: pmxt SDK Operational Gotchas
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
partition: external_knowledge
```

**Content outline**

- Frame the document as a distilled list of empirical pmxt usage pitfalls from `LEARNINGS.md`, not as an official SDK specification.
- Note that `server.status()` returns a dictionary-like object and should be treated accordingly.
- Record that `fetch_market(market_id=...)` was reported as unreliable or broken in the cited notes.
- Record that slug-based lookups may time out or return empty results and that keyword-based search was the more reliable path in the cited notes.
- Note that order creation requires both `market_id` and `outcome_id`, with outcome identifiers described as long opaque strings.
- State that pmxt normalizes prices to the 0-1 scale across exchanges even when a venue natively uses cents.
- Summarize sidecar behavior: default port `3847`, auto-start on first call, shared singleton behavior across Python processes, and lock/log file locations under `~/.pmxt`.
- Note the practical market-matching baseline from the repo notes: Jaccard word similarity at a 40% threshold.
- Preserve the empirical caution that "true arbitrage is rare" so the document captures not only SDK mechanics but the observed limits of the scan pattern.
- Note that direct Polymarket profile endpoints can sometimes replace pmxt for other-wallet analytics.

**Retrieval keywords**

- `pmxt fetch_market broken`
- `pmxt slug lookup`
- `server.status dict`
- `outcome_id long string`
- `pmxt sidecar 3847`
- `true arbitrage is rare`

**Source-quality caution**

- Extra care required at seeding time: this is practitioner guidance tied to one repo snapshot and contributor notes. Attribute it to `LEARNINGS.md` or the corresponding repo note, not to pmxt documentation in general.

### 4. Sports Strategy Catalogue

**Metadata**

```yaml
title: Sports Strategy Catalogue
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
partition: external_knowledge
```

**Content outline**

- Introduce the catalogue as three reference signal patterns: Final Period Momentum, Late Favorite Limit Hold, and VWAP Reversion.
- For Final Period Momentum, include the verified defaults: `final_period_minutes=30`, `entry_price=0.80`, `take_profit_price=0.92`, `stop_loss_price=0.50`, and `trade_size=100` for tick variants.
- Describe Final Period Momentum as an activation-window strategy that enters on a below-to-above threshold cross during the final pre-close window.
- For Late Favorite Limit Hold, include the verified defaults: `entry_price=0.90`, `trade_size=25`, optional activation window, and hold-to-resolution behavior.
- Describe Late Favorite Limit Hold as a limit-entry favorite thesis with no in-strategy take-profit or stop-loss.
- For VWAP Reversion, include the verified defaults: `vwap_window=80`, `entry_threshold=0.008`, `exit_threshold=0.002`, `take_profit=0.015`, and `stop_loss=0.02`.
- Describe VWAP Reversion as a rolling, tick-based mean-reversion pattern that depends on recent price-size observations rather than a clock window.
- Note that quote and trade variants differ in signal inputs and execution references but preserve the same high-level parameter semantics.
- Note that upstream position sizing is quantity-based and constrained by visible liquidity and affordability rather than fixed dollar notional.
- State explicitly that no published backtest results were found, so the catalogue should be stored as a pattern-and-parameters reference rather than validated alpha.

**Retrieval keywords**

- `final period momentum`
- `late favorite limit hold`
- `sports VWAP reversion`
- `entry_price 0.80 0.90`
- `vwap_window 80`
- `prediction market sports strategies`

**Source-quality caution**

- Extra care required at seeding time: the local repo notes indicate mixed-license provenance for the upstream strategy files. Seed only behavioral descriptions, parameter values, and implementation-neutral summaries. Do not copy source expression, and do not present the strategies as proven profitable.

### 5. Cross-Platform Price Divergence Empirics

**Metadata**

```yaml
title: Cross-Platform Price Divergence Empirics
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
partition: external_knowledge
```

**Content outline**

- Describe the document as an empirics summary for matched-market price gaps across venues rather than a trading playbook.
- Preserve the packet's core headline claim: gaps above 5% were reported roughly 15-20% of the time in the cited March 2026 tracker.
- Note that some divergences reportedly converge within minutes when quickly arbitraged or repriced.
- Note that some gaps reportedly persist for weeks or months when caused by structural differences, liquidity conditions, or slower repricing.
- State that no stable directional bias was reported, so the observed gaps should not be framed as one-way predictive evidence.
- State that divergence is more useful as an inefficiency or triage signal than as proof of risk-free arbitrage.
- Note that matching quality materially affects divergence statistics; poor cross-platform matching can create fake gaps.
- Note that venue conventions must be normalized before comparison, including price units, contract framing, and resolution language.
- Keep the document focused on empirical patterns and caveats rather than implementation details about scanners or bots.

**Retrieval keywords**

- `cross-platform price divergence`
- `Polymarket Kalshi 5% gap`
- `15-20% matched markets`
- `convergence within minutes`
- `no directional bias`
- `structural gaps persist`

**Source-quality caution**

- Highest-priority attribution caution in this plan: the local repo only contains secondary references to an AhaSignals March 2026 tracker. Do not seed this document until the exact tracker source, URL, date, and preferably an archived snapshot are captured.

### 6. SimTrader Known Limitations (Verified)

**Metadata**

```yaml
title: SimTrader Known Limitations (Verified)
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
partition: external_knowledge
```

**Content outline**

- Describe the document as a consolidated execution-model limitations note with both internal verification and external corroboration.
- State that passive-order queue position is not modeled.
- State that L3 or individual order-add/cancel visibility is not modeled; only aggregated depth is available.
- State that endogenous market impact and participant reaction are not modeled.
- State that alpha decay or behavioral response after a strategy acts is not modeled.
- Distinguish external repo assumptions about zero latency from PolyTool's own latency handling so the document does not overstate parity.
- Preserve the verified local limitation that fills do not deplete the book for subsequent same-snapshot orders, even though walk-the-book matching logic exists.
- Note that these constraints matter most for high-frequency, passive-maker, or multi-order replay scenarios and less for sparse single-order tests.
- Note that the purpose of the document is realism boundary-setting, not criticism of the simulator architecture.

**Retrieval keywords**

- `SimTrader queue position`
- `no L3 data`
- `no market impact`
- `fills do not deplete book`
- `latency modeling`
- `execution modeling limitations`

**Source-quality caution**

- Extra care required at seeding time: this is a composite document. Separate claims verified internally from claims corroborated by the external backtesting repo analysis so the final seeded document does not imply a single source covers all limitations.

### 7. Cross-Platform Market Matching

**Metadata**

```yaml
title: Cross-Platform Market Matching
freshness_tier: CURRENT
confidence_tier: COMMUNITY
validation_status: UNTESTED
partition: external_knowledge
```

**Content outline**

- Define cross-platform market matching as a heuristic normalization problem, not an exact-slug lookup problem.
- Record the simple baseline from the hermes-pmxt notes: Jaccard word similarity with a 40% threshold.
- Record the packet's recommended robust direction: hybrid Jaccard plus Levenshtein matching.
- Note the key failure mode of pure Jaccard: shared-keyword collisions across different events.
- Note that matching quality must account for differing venue wording, outcome naming, and resolution-condition semantics.
- State that no published accuracy metrics, benchmark set, or precision/recall study were cited for the matcher approach.
- State that poor matching can contaminate downstream divergence studies and arbitrage scans with false positives.
- Position the algorithm family as a candidate-generation heuristic that still needs later structural or human validation.
- Keep the document focused on matching logic and known failure modes rather than on a specific implementation file.

**Retrieval keywords**

- `Jaccard Levenshtein market matching`
- `40% threshold`
- `matcher.js`
- `shared keyword false matches`
- `cross-platform arbitrage matching`
- `Polymarket Kalshi event matching`

**Source-quality caution**

- Extra care required at seeding time: the local notes describe `matcher.js` second-hand and do not include benchmark evidence. Keep the confidence tier at `COMMUNITY` and explicitly mention the lack of published accuracy metrics.

## Consolidated Retrieval Keyword List

- `Polymarket fee formula`
- `maker rebate pool`
- `/fee-rate base_fee`
- `Kalshi fee formula`
- `0.07 C P 1-P`
- `fee_changes`
- `pmxt fetch_market broken`
- `pmxt sidecar 3847`
- `true arbitrage is rare`
- `final period momentum`
- `late favorite limit hold`
- `sports VWAP reversion`
- `cross-platform price divergence`
- `Polymarket Kalshi 5% gap`
- `SimTrader queue position`
- `fills do not deplete book`
- `Jaccard Levenshtein market matching`
- `40% threshold`

## Source-Quality Cautions

- `Polymarket Fee Structure (April 2026)`: use primary or archived official Polymarket materials for formula, category table, maker rebate mechanics, and `/fee-rate` details.
- `Kalshi Fee Structure (April 2026)`: use primary Kalshi docs, API docs, or filing text for formula, rounding, fee-waiver semantics, and maker/taker behavior.
- `pmxt SDK Operational Gotchas`: treat as repo-scoped practitioner guidance from `LEARNINGS.md`, not stable SDK doctrine.
- `Sports Strategy Catalogue`: use behavior and parameter summaries only; local notes indicate mixed-license provenance for the upstream strategy files.
- `Cross-Platform Price Divergence Empirics`: do not seed until the exact AhaSignals tracker citation is captured.
- `SimTrader Known Limitations (Verified)`: preserve source separation between internal verification and external corroboration.
- `Cross-Platform Market Matching`: keep `COMMUNITY` confidence and mention that no published accuracy metrics were found.

## Implementation Notes for the Seeding Pass

- Use the exact titles and metadata blocks above unless a primary-source retrieval step forces a documented correction.
- The sprint packet is the metadata source of truth when it differs from the older unified packet, especially for `confidence_tier`.
- Keep all 7 documents in `partition: external_knowledge` with `validation_status: UNTESTED`.
- Prefer compact, factual prose organized around formulas, parameter tables, behavioral summaries, and known caveats.
- For the fee documents, capture primary-source URLs or archived copies before ingestion so the seeded documents are not based only on secondary packet notes.
- For `Sports Strategy Catalogue`, seed behavior and parameters only; do not include code excerpts or code-shaped pseudocode from the upstream files.
- For `Cross-Platform Price Divergence Empirics`, block ingestion until the exact AhaSignals source is available.
- For `SimTrader Known Limitations (Verified)`, use multiple citations or clearly labeled sub-sections so internal and external validation evidence remain distinguishable.
- For `Cross-Platform Market Matching`, retain the lack-of-benchmark caveat in the body so retrieval does not overstate matcher reliability.
- Do not overwrite existing `external_knowledge` documents with materially different titles unless duplicate-handling is explicitly planned in the seed pass.

## Open Questions / Blockers For The Next Work Unit

- What exact primary source should back `Cross-Platform Price Divergence Empirics` if the AhaSignals tracker is unavailable or not archivable?
- Should the seeded `Sports Strategy Catalogue` cite only the reference extract dev log, or should the seeding pass also capture direct upstream file references with explicit licensing notes?
- For fee documents, should the seeding pass store both category-level summaries and token-level `/fee-rate` nuance in one document or split those details later?

## Local Repo Change Summary

- Added this dev log only.
- No code files changed.
- No config files changed.
- No tests were modified.

## Codex Review Summary

- Not applicable. This session produced a read-only content plan and a dev log only.
