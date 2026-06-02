---
type: index
tags: [index, status/todo]
created: 2026-04-08
---

# Todo Items

All pending work items and notes tagged `#status/todo`.

---

## Dataview — All Todo Notes

```dataview
LIST
FROM ""
WHERE contains(tags, "status/todo")
SORT file.name ASC
```

---

## Manually Curated Pending Work Items

Source: `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` and `docs/CURRENT_STATE.md`.

### Critical Path — Gate 2

- [ ] Pass Gate 2 — Parameter sweep (≥70% positive PnL across 50 tapes)
  - Current status: FAILED — 7/50 positive (14%), gate threshold 70%
  - Root cause: Silver tapes (10) produce zero fills; politics/sports tapes mostly negative
  - Three path-forward options documented in `docs/dev_logs/2026-03-29_crypto_watch_and_capture.md`
- [ ] Complete Silver tape generation end-to-end (pmxt + Jon-Becker + polymarket-apis)
- [ ] DuckDB setup and integration with Parquet data

### Phase 0 — Remaining

- [ ] Polymarket account setup (KYC, wallet, fund with USDC)
- [ ] Kalshi account setup (backup jurisdiction-safe path)
- [ ] USDC funding path (fiat → USDC → Polygon → Polymarket)
- [ ] Wallet architecture (cold + hot wallets, derive API key)
- [ ] Canadian dev partner environment setup
- [ ] Windows development gotchas document
- [ ] Document external data paths in CLAUDE.md

### Phase 1A — Crypto Pair Bot

- [ ] Polymarket 5-min/15-min market discovery (BLOCKED — no active markets)
- [ ] Asymmetric pair accumulation engine
- [ ] Risk controls for crypto pair bot
- [ ] Grafana dashboard — crypto pair bot panels
- [ ] Paper mode testing (24-48 hours)
- [ ] Live deployment on Canadian partner's machine

### Phase 1B — Market Maker Gate Closure

- [ ] Begin Gate 3 — Shadow run (3-5 live markets)
- [ ] Stage 0 — Paper live dry-run (72 hours)
- [ ] Stage 1 — $500 live deployment
- [ ] Bulk data import (pmxt + Jon-Becker via DuckDB)
- [ ] Tape Recorder rewrite using pmxt.watchOrderBook()
- [ ] Auto-redeem for settled positions
- [ ] Multi-window OFI (60min, 4hr, 24hr)
- [ ] News Governor risk layer
- [ ] Parallel SimTrader (multiprocessing.Pool)
- [ ] Universal Market Discovery (NegRisk + Events + Sports)
- [ ] Seed Jon-Becker findings into RAG external_knowledge
- [ ] Grafana live-bot panels

### Phase 1C — Sports Model

- [ ] Historical sports data ingestion (NBA via nba_api, NFL via nfl_data_py)
- [ ] Probability model v1 — NBA
- [ ] Polymarket price comparison pipeline
- [ ] Paper prediction tracker (ClickHouse logs)
- [ ] Grafana sports model dashboard
- [ ] Live deployment (after paper validation)

### Phase 2 and Beyond

- [ ] Candidate Scanner CLI (9 signals, conviction score)
- [ ] APScheduler scheduling for automated workflows
- [ ] Local LLM integration (DeepSeek V3 + Ollama fallback)
- [ ] Wallet Watchlist — real-time alert following
- [ ] Market Obituary System Stage 1
- [ ] Discord bot — two-way approval system
- [ ] LLM-assisted Research Scraper
- [ ] Domain Specialization Layer

### Known Issues to Fix

- [ ] Fix ClickHouse auth violations in examine.py, export_dossier.py, export_clickhouse.py, reconstruct_silver.py
- [ ] Consolidate dual fee modules (float vs Decimal)
- [ ] Fix pyproject.toml packaging gap (5 research subpackages missing)
- [ ] Clean up dead code: cache_source.py, examine.py, opus_bundle.py
