# Plan of Record

This is the durable plan-of-record for the PolyTool project. It captures every
material design decision so future work does not depend on chat history. It
contains no private data (no wallets, dossier excerpts, or user-specific outputs).

---

## 1. Mission and Constraints

### Mission

Build a local-first toolchain that ingests public Polymarket data, computes
explainable analytics, and exports structured evidence packages for offline
LLM-assisted examination of individual trader behavior.

### Constraints

| Constraint | Rationale |
|------------|-----------|
| **Sports-first MVP** | Polymarket prediction markets skew heavily toward sports events. The MVP focuses on sports/event markets where resolution is deterministic and verifiable. |
| **Explainability** | Every analytic output (detector label, PnL bucket, hypothesis) must include evidence fields that trace back to specific trades or data points. No black-box scores. |
| **Local-first** | All data stays on the operator's machine. No external LLM API calls from the toolchain. RAG, embedding, and reranking run locally. |
| **AWS later** | Cloud deployment (AWS) is a future consideration but not in scope for any current roadmap milestone. Architecture should not preclude it but must not require it. |
| **No multi-account** | Analysis is single-user-at-a-time. Multi-user comparison is deferred to Roadmap 6. No portfolio aggregation until then. |
| **No trading signals** | PolyTool is a research and reverse-engineering tool. It does NOT provide trading recommendations, claim alpha, or make predictions. |

---

## 2. Workflow Overview

The canonical end-to-end workflow (manual, non-MCP):

```
scan
  -> ingest trades, activity, positions, markets into ClickHouse
  -> (optional) compute PnL, run detectors
  -> emit trust artifacts under artifacts/dossiers/.../<run_id>/
     (coverage_reconciliation_report.* + run_manifest.json)

export-dossier --user "@handle"
  -> artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id>/

llm-bundle --user "@handle"
  -> kb/users/<slug>/llm_bundles/<date>/<run_id>/
  -> write prompt.txt + bundle_manifest.json

[manual step] paste prompt + bundle into LLM UI
  -> LLM produces hypothesis.md + hypothesis.json

llm-save --user "@handle" --model "model-name" --report-path hypothesis.md
  -> kb/users/<slug>/llm_reports/<date>/<model>_<run_id>/
  -> kb/users/<slug>/notes/LLM_notes/  (auto-generated summary)

rag-index --roots "kb,artifacts" --rebuild
  -> updates Chroma + FTS5 index

rag-query --question "..." --hybrid --rerank --k 8
  -> retrieves evidence for follow-up research

Grafana (http://localhost:3000)
  -> visual review of trades, detectors, PnL
```

Each CLI command is invoked as `python -m polytool <command>`. See
`docs/RUNBOOK_MANUAL_EXAMINE.md` for the step-by-step runbook and
`docs/TRUST_ARTIFACTS.md` for trust artifact interpretation.

`examine` remains available as a legacy orchestration wrapper but is not the
canonical path for trust artifact validation.

---

## 3. Critical Data Gaps

These gaps are inherent to the data available from Polymarket's public APIs and
fundamentally shape what the toolchain can and cannot conclude.

### Gap A: Resolution Outcomes

**Problem**: Polymarket does not expose a direct "this token won/lost" field in
the public trade or positions APIs. Settlement data must be inferred from Gamma
API (`closed=true` + `winningOutcome`) or fetched on-chain.

**Current mitigation**: `packages/polymarket/resolution.py` implements a
`CachedResolutionProvider` that tries ClickHouse cache first, then Gamma API.
Positions that cannot be resolved fall to `UNKNOWN_RESOLUTION`.

**Roadmap 3 target**: On-chain resolution provider reading settlement transactions
directly from the blockchain.

### Gap B: Settlement Price

**Problem**: For binary markets, settlement is 1.0 or 0.0. For multi-outcome
markets, partial settlement may apply. Gamma API does not always expose the
settlement price directly; it must be inferred from `winningOutcome` index.

**Current mitigation**: Binary markets only in MVP. `settlement_price` is set to
1.0 or 0.0 based on `winningOutcome` index matching.

### Gap C: Realized PnL

**Problem**: Polymarket does not provide a cost-basis or realized PnL figure.
PolyTool computes FIFO-matched PnL, which is an approximation.

**Current mitigation**: `realized_pnl` is labeled as approximate in all exports.
MTM PnL uses current CLOB best bid/ask. Both are clearly flagged.

### Gap D: Pre-Trade Context

**Problem**: There is no data about what information the trader had access to
before entering a position (news, odds movements, social signals).

**Current mitigation**: Every hypothesis must explicitly list this as a limitation.
No hypothesis should claim to explain *why* a trader entered a position.

### Gap E: Game Context / Event Timing

**Problem**: Event start times, game schedules, and real-time event state are not
available from Polymarket APIs. `minutes_before_start` is only available when
the market description or metadata contains timing information.

**Current mitigation**: Noted as "if available" in metrics. Sports data providers
(Sportradar, The Odds API) are in the research source allowlist for future
enrichment.

### Gap F: Position Lifecycle

**Problem**: Positions are point-in-time snapshots, not a continuous history.
The ingestion cadence determines how much lifecycle data is captured.

**Current mitigation**: Multiple snapshot ingestions over time build a coarse
history. Dossier exports include the latest snapshot only.

### Gap G: Timing Granularity

**Problem**: Trade timestamps are available but sub-second ordering within a
block may not reflect true execution order. Latency between blocks and API
polling introduces noise.

**Current mitigation**: Analysis uses minute-level or coarser granularity.
Timing-sensitive hypotheses must note this limitation.

### Gap H: Microstructure and Categorization

**Problem**: Historical orderbook depth is not available (only current snapshots).
Market categorization depends on Gamma API tags which are incomplete.

**Current mitigation**: Slippage estimates use current orderbook, flagged as
non-historical. Category mapping uses keyword heuristics as fallback.
Both limitations are documented in every relevant detector and dossier.

---

## 4. Outcome Taxonomy Semantics

Every position must be assigned exactly one resolution outcome. The taxonomy is
implemented in `packages/polymarket/resolution.py:ResolutionOutcome`.

| Outcome | Semantics | Determination Logic |
|---------|-----------|-------------------|
| `WIN` | Held to resolution; the outcome token won | `settlement_price == 1.0` AND `position_remaining > 0` |
| `LOSS` | Held to resolution; the outcome token lost | `settlement_price == 0.0` AND `position_remaining > 0` |
| `PROFIT_EXIT` | Closed position before resolution at a profit | `position_remaining <= 0` AND `gross_pnl > 0` |
| `LOSS_EXIT` | Closed position before resolution at a loss | `position_remaining <= 0` AND `gross_pnl <= 0` |
| `PENDING` | Market has not yet resolved | `settlement_price IS NULL` |
| `UNKNOWN_RESOLUTION` | Resolution data unavailable | Fallback when none of the above apply |

**Win rate** excludes PENDING and UNKNOWN_RESOLUTION:

```
win_rate = (WIN + PROFIT_EXIT) / (WIN + LOSS + PROFIT_EXIT + LOSS_EXIT)
```

**Important**: WIN/LOSS require that the position was held through resolution.
A trader who sold before resolution at a profit gets PROFIT_EXIT, not WIN, even
if the market later resolved in their favor.

---

## 5. Deterministic trade_uid Rule

Trade UIDs are generated deterministically to ensure deduplication and
reproducibility. The rule is implemented in
`packages/polymarket/resolution.py:generate_trade_uid`:

```
trade_uid = sha256(f"{tx_hash}:{log_index}").hexdigest()
```

Where:
- `tx_hash`: The on-chain transaction hash (0x-prefixed, lowercase).
- `log_index`: The event log index within the transaction (integer).

If `tx_hash` is empty or unavailable (e.g., off-chain API trades without
on-chain settlement), `trade_uid` falls back to the API-provided `id` field
or a hash of available identifying fields.

This ensures:
- The same trade always produces the same UID across re-ingestions.
- ClickHouse ReplacingMergeTree can deduplicate on `(proxy_wallet, trade_uid)`.
- Hypothesis evidence can reference specific trades by UID.

---

## 6. Fees Handling Policy

### Principle

`realized_pnl` reported by PolyTool is **net of estimated fees**. The fee
estimation method is tracked per trade via a `fees_source` flag.

### Fee Sources

| fees_source | Meaning | Accuracy |
|-------------|---------|----------|
| `actual` | Fee rate fetched from `/fee-rate` endpoint at compute time | High (but rate may change) |
| `estimated` | Fee computed using the quadratic fee curve formula with cached rate | Medium |
| `unknown` | Fee could not be determined; assumed zero | Low |

### Fee Curve Formula

```
fee_usdc = shares * price * (fee_rate_bps / 10000) * (price * (1 - price))^2
```

- `fee_rate_bps`: Fetched per-token from `GET /fee-rate?token_id=...`
- Exponent: 2.0 (quadratic) - fees are lower at extreme prices
- At price=0.5: maximum curve factor (0.0625)
- At price=0.1 or 0.9: lower curve factor (0.0081)

### Roadmap 3 Improvement

Store `fee_rate_bps` per trade at ingestion time in ClickHouse. This enables
historical fee reconstruction rather than relying on current rates. The
`fees_source` flag will distinguish between trades with stored vs estimated fees.

---

## 7. Strategy Validation Framework

See also `docs/STRATEGY_PLAYBOOK.md` for the full methodology.

### Win Rate vs Implied Probability

The core analysis compares a trader's empirical win rate against the market's
implied probability at entry:

```
edge = win_rate - avg_entry_price
```

Where `avg_entry_price` for binary markets approximates the implied probability.
Positive edge suggests the trader is systematically beating the market.

### EV Formulas

For a binary market position:

```
EV_per_trade = P(win) * (1.0 - entry_price) - P(loss) * entry_price
```

Across a portfolio:

```
EV_total = sum(position_size * EV_per_trade) for all resolved positions
```

### Signal Extraction and Falsification

Every hypothesis must include:

1. **Claim**: A specific, testable statement about trader behavior.
2. **Evidence**: At least 3 supporting trade_uids with metrics.
3. **Confidence**: high / medium / low with explicit justification.
4. **Falsification method**: How to disprove the hypothesis.

See `docs/HYPOTHESIS_STANDARD.md` for the full quality rubric.

### Segmentation Axes

Hypotheses should be tested across these dimensions:

| Axis | Examples |
|------|----------|
| **Price tier** | Entry price buckets: [0.01-0.20], [0.20-0.40], [0.40-0.60], [0.60-0.80], [0.80-0.99] |
| **Market type** | Binary vs multi-outcome |
| **Sport / league** | NFL, NBA, soccer, politics, crypto, other |
| **Timing** | Minutes before event start; hour of day; day of week |
| **Size buckets** | Position size quartiles relative to the trader's own history |
| **Hold duration** | Scalper (<1h), swing (1h-7d), holder (>7d) |
| **Resolution outcome** | WIN, LOSS, PROFIT_EXIT, LOSS_EXIT |

Segmentation prevents Simpson's paradox: aggregate win rate may look profitable
while every sub-segment is unprofitable (or vice versa).

---

## 8. Hypothesis Artifact Contract

Every LLM examination run must produce two artifacts:

### hypothesis.md (Markdown report)

Required sections:
- Executive summary (3-6 bullets)
- Key observations with `[file_path: ...]` and `[trade_uid: ...]` citations
- Hypotheses table: claim, evidence, confidence, falsification method
- Limitations section (what the evidence does not show)
- Missing data for backtest section

### hypothesis.json (Structured data)

Must conform to `docs/specs/hypothesis_schema_v1.json`. Key fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | `"hypothesis_v1"` | yes | Schema identifier |
| `metadata.user_slug` | string | yes | User being analyzed |
| `metadata.run_id` | string | yes | Unique run identifier |
| `metadata.created_at_utc` | ISO-8601 | yes | Timestamp |
| `metadata.model` | string | yes | Model that generated the output |
| `metadata.window_days` | integer | no | Analysis lookback window |
| `executive_summary.bullets` | string[] | yes | 3-6 bullet summary |
| `executive_summary.overall_assessment` | enum | no | profitable/unprofitable/mixed/insufficient_data |
| `hypotheses[]` | array | yes | Each with claim, evidence[], confidence, falsification |
| `observations[]` | array | no | Evidence-backed observations |
| `limitations` | string[] | no | What the evidence does not show |
| `missing_data_for_backtest` | string[] | no | Data needed for backtesting |
| `next_features_needed` | string[] | no | Suggested features to compute |

### backtest_ready Flag

A hypothesis is `backtest_ready = true` only when:
- `missing_data_for_backtest` is empty.
- All evidence trade_uids reference trades with resolution outcomes != UNKNOWN_RESOLUTION.
- The sample size is >= 30 resolved positions.

Until Roadmap 3 (Hypothesis Validation Loop), no hypotheses will be backtest_ready.
This field exists to signal future readiness.

See `docs/HYPOTHESIS_STANDARD.md` for the full prompt template and quality rubric.

---

## 9. RAG Source Caching Policy

### Allowlist (MVP)

Only URLs matching the configured allowlist are fetched by `cache-source`.
The default allowlist covers:

- `docs.polymarket.com` - Official API and protocol docs
- `learn.polymarket.com` - Learning resources
- `github.com/Polymarket/` - Open-source repos
- `docs.alchemy.com` - Blockchain API docs
- `thegraph.com/docs` - Subgraph indexing docs
- `dune.com/docs` - On-chain analytics docs
- `mlfinlab.readthedocs.io` - ML finance library
- `vectorbt.dev/docs` - Backtesting library
- `arxiv.org` - Academic papers
- `papers.ssrn.com` - Finance working papers
- `nber.org/papers` - Economics research
- `the-odds-api.com/docs` - Sports odds data
- `developer.sportradar.com/docs` - Sports data provider

Custom allowlists can be set in `polytool.yaml` under
`kb_sources_caching.allowlist`.

### TTL Policy

- **Default TTL**: 14 days.
- **Per-domain overrides**: Configurable in `polytool.yaml`.
- **Force refresh**: `--force` bypasses TTL.
- **No auto-refresh**: Sources are not refreshed automatically. Manual
  invocation is required.

### Metadata

Each cached source stores:

```json
{
  "source_url": "https://...",
  "fetched_at": "2026-02-06T12:00:00Z",
  "content_hash": "sha256:...",
  "ttl_days": 14,
  "filename": "safe_filename.md",
  "size_bytes": 12345
}
```

### Deduplication

Content is hashed (SHA256). If the content hash matches the existing cache and
the TTL has not expired, metadata is updated but content is not re-written.

### Storage

Cached content lives in `kb/sources/` (private, gitignored). Only the allowlist
and policy (this document and `docs/RESEARCH_SOURCES.md`) are committed.

---

## 10. MCP Intent

The MCP (Model Context Protocol) server provides a **tool-call automation layer**
that exposes PolyTool CLI commands as MCP tools for Claude Desktop.

**Current state**: stdio transport, basic tool exposure, tested via
`mcp.client.stdio.stdio_client` roundtrip.

**Intent**: Enable Claude Desktop to invoke scan, export, rag-query, and legacy
orchestration commands when needed.
without manual copy-paste. This is a convenience layer, not the primary workflow.

**The manual workflow remains primary** until MCP is fully stable and tested
across multiple real examination runs. MCP is tracked separately in Roadmap 5.

---

## 11. Backtesting: Deferred

Backtesting is explicitly **out of scope** for all current roadmap milestones.

### What "Phase Later" Will Be

When backtesting is eventually implemented (post-Roadmap 3), it will:

1. **Replay historical trades** against historical market state to validate
   hypotheses with out-of-sample data.
2. **Require historical orderbook data** (not currently available).
3. **Use the hypothesis.json `backtest_ready` flag** to determine which
   hypotheses have sufficient data for backtesting.
4. **Produce backtest reports** with metrics: Sharpe ratio, max drawdown,
   win rate by segment, transaction cost impact.

### Why It Is Deferred

- Gap H (historical microstructure data) blocks meaningful backtesting.
- Gap C (exact realized PnL) means backtest results would be approximate.
- The hypothesis validation loop (Roadmap 3) must exist first to standardize
  what "validating a hypothesis" means.
- Premature backtesting encourages overfitting to in-sample data.

### Kill Condition

Do NOT start any backtesting work until:
- Roadmap 3 (Hypothesis Validation Loop) is fully shipped.
- Historical orderbook data is available (either from a provider or on-chain).
- At least 3 complete examination runs have been saved and indexed.

---

## Cross-References

- [Roadmap](ROADMAP.md) - Milestone checklist and kill conditions
- [Runbook: Manual Examine](RUNBOOK_MANUAL_EXAMINE.md) - Step-by-step workflow
- [Hypothesis Standard](HYPOTHESIS_STANDARD.md) - Prompt template and quality rubric
- [Strategy Playbook](STRATEGY_PLAYBOOK.md) - Outcome taxonomy and validation methodology
- [Research Sources](RESEARCH_SOURCES.md) - Curated source domains and caching policy
- [Project Context (Public)](PROJECT_CONTEXT_PUBLIC.md) - Goals, non-goals, artifact contract
- [Architecture](ARCHITECTURE.md) - Components, data flow, RAG schema
