# Project Context (Public)

This document captures the project goals, constraints, data model, and methodology
so that planning context is preserved in-repo rather than in chat history. It
contains no private data (no wallets, dossier excerpts, or user-specific outputs).

## Problem Statement

Polymarket publishes rich public trading data but no first-party analytics toolkit
for systematic evaluation of trader behavior. PolyTool fills this gap with a
local-first, privacy-respecting toolchain that:

1. Ingests public Polymarket data (trades, activity, positions, markets, orderbooks).
2. Computes analytics (strategy detectors, PnL, arb feasibility).
3. Exports structured evidence packages (dossiers) for offline LLM analysis.
4. Provides local RAG retrieval over private research artifacts.

## Goals

- **Local-first**: All data stays on the user's machine. No external LLM API calls.
- **Reproducible evidence**: Every claim in an LLM report must cite a specific file
  and path. Dossiers are point-in-time snapshots.
- **Composable pipeline**: Each CLI command does one thing; `examine` orchestrates
  the full workflow.
- **Auditable methodology**: Strategy playbook and hypothesis schema enforce
  falsification and evidence standards.

## Non-Goals

- Trading signals, recommendations, or alpha claims.
- Real-time monitoring or alerting.
- Multi-tenant hosting or SaaS deployment.
- Mobile app or web UI.
- Backtesting infrastructure (deferred to post-Roadmap 3).

## Critical Data Gaps

These are known limitations in the data available from Polymarket's public APIs:

| Gap | Impact | Mitigation |
|-----|--------|------------|
| **Resolution / settlement data** | Cannot definitively determine WIN/LOSS for held-to-resolution positions | `UNKNOWN_RESOLUTION` fallback; on-chain provider planned (Roadmap 2) |
| **Realized PnL (exact)** | FIFO approximation only; no exchange-provided cost basis | Clearly labeled as approximate in dossier |
| **Pre-trade context** | No data on what information trader saw before entering | Note as limitation in every hypothesis |
| **Microstructure data** | No historical orderbook depth; only current snapshots | Slippage estimates use current book, flagged as non-historical |
| **Market categorization** | Category mapping depends on Gamma API data quality | Keyword heuristics as fallback; noted in detectors |
| **Position history** | Positions are point-in-time snapshots, not continuous | Snapshot cadence depends on ingestion frequency |

## Outcome Taxonomy

Every position must have exactly one resolution outcome:

| Outcome | Description | Determination |
|---------|-------------|---------------|
| `WIN` | Held to resolution, outcome won | settlement_price = 1.0 + position remaining > 0 |
| `LOSS` | Held to resolution, outcome lost | settlement_price = 0.0 + position remaining > 0 |
| `PROFIT_EXIT` | Exited before resolution at profit | position remaining <= 0 + gross_pnl > 0 |
| `LOSS_EXIT` | Exited before resolution at loss | position remaining <= 0 + gross_pnl <= 0 |
| `PENDING` | Market not yet resolved | settlement_price is NULL |
| `UNKNOWN_RESOLUTION` | Resolution data unavailable | Fallback when data missing |

Win rate calculation excludes PENDING and UNKNOWN_RESOLUTION:

```
win_rate = (WIN + PROFIT_EXIT) / (WIN + LOSS + PROFIT_EXIT + LOSS_EXIT)
```

## Strategy Validation Framework

From `docs/STRATEGY_PLAYBOOK.md`:

- **Expected value**: `EV = P(correct) * avg_payout - P(incorrect) * avg_loss`
- **Segmentation**: Segment by category, hold duration, position size, timing.
- **Falsification**: Every hypothesis must include a falsification method.
- **Evidence threshold**: At least 3 supporting trade_uids per claim.
- **Confidence levels**: high / medium / low with explicit justification.

See the full playbook for the validation checklist and metrics reference.

## Artifact Contract

The pipeline produces these artifacts in canonical locations:

| Artifact | Path Pattern | Contents |
|----------|-------------|----------|
| **Dossier** | `artifacts/dossiers/users/<slug>/<wallet>/<date>/<run_id>/` | `memo.md`, `dossier.json`, `manifest.json` |
| **LLM Bundle** | `kb/users/<slug>/llm_bundles/<date>/<run_id>/` | `bundle.md`, `prompt.txt`, `examine_manifest.json` |
| **LLM Report** | `kb/users/<slug>/llm_reports/<date>/<model>_<run_id>/` | `report.md`, `hypothesis.md`, `hypothesis.json`, `inputs_manifest.json` |
| **LLM Notes** | `kb/users/<slug>/notes/LLM_notes/` | Summary notes auto-created by `llm-save` |
| **ClickHouse Export** | `kb/users/<slug>/exports/<date>/` | CSV/JSON datasets from ClickHouse |
| **Cached Sources** | `kb/sources/` | Markdown + metadata from `cache-source` |

All `kb/` and `artifacts/` paths are gitignored. Only `docs/` is committed.

## Primary Workflow

The **manual workflow** (non-MCP) is the primary and default path:

```
scan -> Grafana review -> examine (dossier + bundle + prompt)
     -> paste into LLM -> save report via llm-save
     -> rag-index -> rag-query for follow-up research
```

See `docs/RUNBOOK_MANUAL_EXAMINE.md` for the step-by-step runbook.

**MCP** is an optional, secondary integration path for Claude Desktop. It exposes
the same underlying tools via the Model Context Protocol. It is tracked separately
and is not required for the core workflow.
