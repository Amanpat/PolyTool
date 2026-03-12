# Architecture

PolyTool keeps the public documentation and code clean while routing all user/private data into
local-only storage.

Master Roadmap v4 (`docs/reference/POLYTOOL_MASTER_ROADMAP_v4.md`) is the
governing roadmap document as of 2026-03-12 and supersedes v3. This file
describes the current implemented architecture; treat the v4 north-star diagram
as target-state architecture unless the components below say otherwise.

## Roadmap Authority and Open Deltas

| Area | Master Roadmap v4 north star | Current architecture truth |
|------|-------------------------------|----------------------------|
| Control plane | n8n orchestrates workflows through a thin FastAPI wrapper layer. | The repo is still CLI-first and local-first. `services/api/` exists, but the broad v4 wrapper surface and n8n control plane are not current architecture truth. |
| Knowledge inputs | Research scraper and signals/news ingestion feed the RAG brain continuously. | Current RAG flows are driven by local docs, `kb/`, artifacts, and manually triggered source caching. Scraper and signals pipelines are not shipped architecture components here. |
| Operator UI | PolyTool Studio v2 becomes a unified Next.js operator dashboard. | Current surfaces remain Grafana plus the existing Studio/CLI workflows. Do not read the v4 Studio rebuild as implemented architecture. |
| RAG layout | One hybrid brain with partitions such as `user_data`, `research`, `signals`, `market_data`, and `external_knowledge`. | Current RAG metadata filters and storage locations are documented below; the full partitioned v4 brain is roadmap intent, not current topology. |

## Components (current implementation)
- `services/api/`: FastAPI service that ingests and computes analytics.
- `infra/clickhouse/`: ClickHouse schemas + migrations.
- `packages/polymarket/`: Shared clients + analytics logic.
  - `simtrader/execution/`: KillSwitch, RateLimiter, RiskManager, LiveExecutor, LiveRunner, OrderManager
  - `simtrader/strategies/`: MarketMakerV0 (+ CopyWalletReplay, BinaryComplementArb)
- `packages/research/hypotheses/`: Offline hypothesis registry and experiment skeleton.
- `tools/cli/`: Local CLI utilities (scan, dossier export, clickhouse export, RAG, simtrader, hypotheses).
- `docs/`: Public truth source + ADRs.
- `kb/` + `artifacts/`: Private local data (gitignored).
  - `artifacts/research/hypothesis_registry/registry.jsonl`: append-only hypothesis lifecycle events
  - `artifacts/research/experiments/<hypothesis_id>/`: experiment skeleton directories

## Data flow (local-only)
```
Polymarket APIs -> API ingest -> ClickHouse
                              -> dossier export -> artifacts/
                              -> clickhouse export -> kb/
kb/ + artifacts/ -> local embeddings -> Chroma index (kb/rag/index)
kb/ + artifacts/ -> lexical index (SQLite FTS5: kb/rag/lexical/lexical.sqlite3)
Chroma/lexical -> rag-query -> snippets for offline memos
```

## Research loop (Track B)
```
wallets.txt (handles + wallet addresses)
  -> wallet-scan (per-user scan loop)
       -> per user: polytool scan -> artifacts/dossiers/users/<slug>/...
                                      coverage_reconciliation_report.json
                                      segment_analysis.json
  -> artifacts/research/wallet_scan/<date>/<run_id>/
       leaderboard.json          (ranked by net PnL)
       per_user_results.jsonl    (all entries, including failures)
       leaderboard.md            (human-readable table)

  -> alpha-distill (reads leaderboard + each user's segment_analysis.json)
  -> alpha_candidates.json       (ranked cross-user edge hypothesis candidates)
       per candidate: sample_size gates, friction_risk_flags, next_test, stop_condition

  -> manual review -> llm-bundle -> paste into LLM UI -> llm-save
       kb/users/<slug>/llm_bundles/<date>/<run_id>/bundle.md
       kb/users/<slug>/reports/<date>/<run_id>_report.md  (blank stub for operator)
```

Track B foundation status (2026-03-05): complete (`wallet-scan` v0,
`alpha-distill` v0, and RAG/hypothesis scaffolding baseline).

## Optional execution loop (Track A, gated)
Track A is in-scope as an optional module and is never default-on.

```
operator strategy (manual, explicit)
  -> replay validation       (simtrader run --strategy market_maker_v0)
  -> scenario sweeps         (simtrader quickrun --sweep quick)
  -> shadow                  (simtrader shadow --strategy market_maker_v0)
  -> LiveRunner --dry-run    (simtrader live --strategy market_maker_v0 [default])
  -> optional capital stage  (manual operator enable only, --live)
```

Hard rule: no live capital before `replay -> scenario sweeps -> shadow ->
dry-run live` gates are complete.

Safety defaults (enforced at all stages including dry-run):
- Dry-run is the default: `simtrader live` never submits orders unless `--live` is passed.
- Kill switch checked before every place/cancel action, even in dry-run.
- No market orders; limit orders only.
- Conservative Stage-0 risk caps: order, position, daily-loss, and inventory notional limits.

Current Track A primitives (as of 2026-03-05):
- Week 1: KillSwitch, RateLimiter, RiskManager, LiveExecutor, LiveRunner, `simtrader live` CLI
- Week 2: OrderManager reconciliation loop, MarketMakerV0 strategy, `--strategy` CLI flag, gated `--live` path

Research outputs are not signals. The execution layer may run only
operator-supplied strategies that passed validation gates and risk controls.
Interfaces are specified in `docs/specs/SPEC-0011-live-execution-layer.md`.

### Research artifacts layout

```
artifacts/
  research/
    wallet_scan/
      <YYYY-MM-DD>/
        <run_id>/
          wallet_scan_manifest.json
          per_user_results.jsonl
          leaderboard.json
          leaderboard.md
          alpha_candidates.json   (written by alpha-distill, same run_id dir)
  dossiers/
    users/
      <slug>/
        <run_id>/
          coverage_reconciliation_report.json
          segment_analysis.json
          audit_coverage_report.md
          ...
```

RAG storage locations:
- `kb/rag/index/` - Chroma vector index
- `kb/rag/lexical/lexical.sqlite3` - SQLite FTS5 lexical index
- `kb/rag/models/` - embedding + reranker model cache
- `kb/rag/eval/reports/` - retrieval eval outputs

## Local RAG boundary
The RAG pipeline indexes by default:
- `kb/`
- `artifacts/`

Optionally, `docs/archive/` can be added when you want RAG to surface past design decisions:
```
polytool rag-index --roots "kb,artifacts,docs/archive" --rebuild
```

**External / manual LLM UIs**: if you paste retrieved snippets into a hosted model (Opus 4.5 web,
ChatGPT, etc.), upload only the memo + minimal dossier excerpts you are comfortable sharing.

## Hybrid retrieval (vector + lexical)

PolyTool supports offline hybrid retrieval: vector search (Chroma) + keyword search (SQLite FTS5),
combined with Reciprocal Rank Fusion (RRF). The lexical DB lives at:

```
kb/rag/lexical/lexical.sqlite3
```

**Fusion method**: RRF with default *k=60* (configurable via `--rrf-k`).

## RAG metadata filter schema

Each indexed chunk carries structured metadata used by Chroma `where`-filters at
query time.  This replaces the earlier path-prefix post-filtering with database-level
enforcement.

| Field | Type | Nullable | Source |
|-------|------|----------|--------|
| `doc_type` | string | no | Path pattern: `user_kb`, `dossier`, `kb`, `artifact`, `docs`, `archive` |
| `user_slug` | string | yes | Extracted from `kb/users/<slug>/` or `artifacts/dossiers/<slug>/` |
| `proxy_wallet` | string | yes | 0x-address parsed from path (if present) |
| `is_private` | bool | no | `true` for `kb/` and `artifacts/`, `false` for `docs/` |
| `created_at` | ISO-8601 | yes | Date from path pattern, else file mtime |

### Safe defaults

- **Default query scope is private-only** (`is_private = true`).  Public `docs/`
  content is never returned unless `--public-only` is explicitly passed.
- **Archive documents excluded by default** (`doc_type != "archive"`).  Pass
  `--include-archive` to include them.
- **User isolation**: passing `--user <slug>` adds `user_slug = <slug>` to the
  Chroma where-clause.  Chunks without a matching `user_slug` are excluded at
  the database level.
- Path-prefix post-filtering is retained as a **defensive backstop** only;
  correctness comes from the metadata where-clause.

### CLI flags (rag-query)

```
--user <slug>             Scope to a single user
--doc-type <value>        Filter by doc_type (repeatable / comma-separated)
--private-only            (default) Only private content
--public-only             Only public content
--date-from YYYY-MM-DD    Created on or after
--date-to   YYYY-MM-DD    Created on or before
--include-archive         Include archive documents
--hybrid                  Use vector + lexical retrieval with RRF fusion
--lexical-only            Use lexical (FTS5) retrieval only
--top-k-vector <n>         Vector candidates for hybrid fusion (default 25)
--top-k-lexical <n>        Lexical candidates for hybrid fusion (default 25)
--rrf-k <n>                RRF constant (default 60)
```

## Safety
A pre-push guard blocks committing private or secrets-like files. See `docs/RISK_POLICY.md`.
