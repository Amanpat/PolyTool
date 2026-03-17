# Architect Context Pack

**Generated:** 2026-03-05
**Tests:** sprint-end handoff reports 1188 passing total
**Pre-push guard:** not run for this docs update

---

## 1. One-Line Summary

Local-first Polymarket analysis toolchain: data ingestion to ClickHouse, Grafana visualization, private dossier exports, and offline hybrid RAG for evidence retrieval.

---

## Current Sprint Status

TRACK A - CODE STATUS: COMPLETE
All execution layer code is shipped and tested (1188 tests passing).
The only remaining work is operational: close 3 gates, then flip `--live` flag.

WHAT TO DO NEXT (in order):

### Step 1 - IMMEDIATE (needs live Polymarket connection, ~30 min)

Close Gate 1 (Replay):

```bash
python tools/gates/close_replay_gate.py
```

Close Gate 2 (Sweep):

```bash
python tools/gates/close_sweep_gate.py
```

### Step 2 - IMMEDIATE (needs Administrator PowerShell, ~10 min)

Complete Gate 3 (Shadow) - shadow run is already recorded, just needs reconnect test:

```powershell
# In elevated PowerShell:
netsh advfirewall firewall add rule name="block_poly" dir=out action=block remoteip=188.0.0.0/8
Start-Sleep -Seconds 10
netsh advfirewall firewall delete rule name="block_poly"
# Then manually write artifacts/gates/shadow_gate/gate_passed.json
# See tools/gates/shadow_gate_checklist.md for exact artifact format
```

### Step 3 - VERIFY (after steps 1 and 2)

```bash
python tools/gates/gate_status.py
# Expected output: all 4 gates PASSED, exit code 0
```

### Step 4 - STAGE 0 PAPER LIVE (72 hours, $0 capital)

```bash
python -m polytool market-scan --top 5
# Pick top market with mid_price in [0.30, 0.70]
python -m polytool simtrader live \
  --strategy market_maker_v0 \
  --asset-id <TOKEN_ID_FROM_MARKET_SCAN>
# Monitor Grafana. Watch for errors. Kill switch: python -m polytool simtrader kill
```

### Step 5 - INFRASTRUCTURE (provision in parallel with Stage 0)

Provision VPS: QuantVPS or Vultr NJ datacenter (~$30-100/month)
Provision Polygon RPC: Chainstack or Alchemy dedicated node (~$50-100/month)
These are required BEFORE Stage 1 capital ($500 USDC)

### Step 6 - STAGE 1 LIVE ($500 USDC, after 72h Stage 0 clean + infrastructure ready)

```bash
python -m polytool simtrader live \
  --live \
  --strategy market_maker_v0 \
  --asset-id <TOKEN_ID> \
  --max-position-usd 500 \
  --daily-loss-cap-usd 100 \
  --max-order-usd 200
# Will require typing "CONFIRM" to proceed
# Prerequisites: PK env var set, all 4 gates passed, USDC in wallet
```

TRACK B - NEXT CODE SPRINT
After gates close and Stage 0 is stable, the next code work is:
alpha-distill upgrade: add composite wallet scoring formula + StrategySpec JSON output
This is PDF Construction Manual Section 5.2 - estimated 5 days of dev work
Prompt the architect to start Track B with a fresh Codex prompt.

---

## 2. Domain Model (Concepts & Relationships)

```
User (proxy_wallet, username)
  └── Trades (token_id, side, price, size, timestamp)
  └── Activity (event_type, timestamp)
  └── Positions (token_id, size, snapshot_ts)
  └── PnL Buckets (realized_pnl, mtm_pnl, bucket_start)
  └── Detector Results (detector_name, label, score, evidence)

Market (condition_id)
  └── Market Tokens (token_id, outcome_index, clob_token_id)
  └── Orderbook Snapshots (best_bid, best_ask, spread_bps, depth)

Token Aliases (alias_token_id -> canonical_clob_token_id)

RAG Chunks (doc_type, user_slug, is_private, created_at)
  └── Vector Index (Chroma)
  └── Lexical Index (SQLite FTS5)
```

**Key Entities:**
- `proxy_wallet`: Primary identifier for Polymarket users (0x address)
- `condition_id`: Market identifier; normalized to `0x` prefix lowercase
- `token_id`: Outcome token; may have aliases needing resolution
- `bucket_type`: Temporal aggregation (day/hour/week)

---

## 3. Tech Stack (Verified)

| Layer | Technology | Version/Details | File Path |
|-------|------------|-----------------|-----------|
| **API** | FastAPI + Uvicorn | Python 3.11 | `services/api/main.py:81-85` |
| **Storage** | ClickHouse | Latest (Docker) | `docker-compose.yml:2-22` |
| **Viz** | Grafana | 11.4.0 | `docker-compose.yml:24-46` |
| **RAG Vector** | Chroma + Sentence-Transformers | chromadb, sentence-transformers | `requirements-rag.txt:1-3` |
| **RAG Lexical** | SQLite FTS5 | Built-in Python | `packages/polymarket/rag/lexical.py` |
| **Reranker** | Cross-Encoder | sentence-transformers | `packages/polymarket/rag/reranker.py` |
| **CLI** | argparse | Python stdlib | `polytool/__main__.py` |
| **Container** | Docker Compose | N/A | `docker-compose.yml` |

**External APIs (Polymarket):**
- Gamma API: `https://gamma-api.polymarket.com` - User profiles, markets
- Data API: `https://data-api.polymarket.com` - Trades, activity
- CLOB API: `https://clob.polymarket.com` - Orderbooks, fees

---

## 4. Directory Tree (Key Paths)

```
PolyTool/
├── docs/               # Public truth source
│   ├── adr/            # Architecture Decision Records
│   ├── archive/        # Historical docs (superseded)
│   ├── eval/           # RAG evaluation suites
│   ├── features/       # Feature documentation
│   └── specs/          # Canonical specs (read-only)
├── infra/
│   ├── clickhouse/initdb/  # 16 SQL migration files
│   └── grafana/
│       ├── dashboards/     # 7 dashboard JSONs
│       └── provisioning/   # Datasource config
├── packages/polymarket/
│   ├── rag/            # RAG pipeline (9 modules)
│   │   ├── chunker.py
│   │   ├── embedder.py
│   │   ├── index.py
│   │   ├── lexical.py
│   │   ├── query.py
│   │   ├── reranker.py
│   │   ├── eval.py
│   │   ├── manifest.py
│   │   └── metadata.py
│   ├── detectors.py    # 4 strategy detectors
│   ├── pnl.py          # P&L calculations
│   ├── arb.py          # Arbitrage analysis
│   └── ...             # 27 Python modules total
├── polytool/           # CLI entrypoint (canonical)
│   └── __main__.py     # 12 subcommands
├── services/api/       # FastAPI service
│   ├── main.py         # ~900 lines
│   ├── Dockerfile
│   └── requirements.txt
├── tests/              # 13 test files, 131 tests
├── tools/
│   ├── cli/            # 8 CLI command implementations
│   ├── guard/          # Pre-push/pre-commit guards
│   └── smoke/          # API contract tests
├── kb/                 # Private KB (gitignored)
├── artifacts/          # Private exports (gitignored)
├── docker-compose.yml
├── .env.example
└── requirements-rag.txt
```

**File Counts (excluding .git/.claude):**
- Python: 61 files
- SQL: 16 files
- JSON: 23 files
- Markdown: 58 files

---

## 5. Execution Surfaces

### CLI Commands (`python -m polytool <command>`)

| Command | Purpose | Key Flag |
|---------|---------|----------|
| `scan` | Ingest user data to ClickHouse | `--compute-pnl` |
| `export-dossier` | Generate evidence package | `--user "@slug"` |
| `export-clickhouse` | Export CH data to KB | `--user "@slug"` |
| `rag-index` | Build/rebuild RAG index | `--roots "kb,artifacts"` |
| `rag-query` | Retrieve evidence | `--hybrid --rerank` |
| `rag-eval` | Evaluate retrieval quality | `--suite path.jsonl` |
| `llm-bundle` | Generate LLM evidence bundle | `--user "@slug"` |
| `llm-save` | Store LLM report runs | `--model "local-llm"` |

### API Endpoints (`http://localhost:8000`)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/api/resolve` | POST | Resolve username/wallet |
| `/api/ingest/trades` | POST | Fetch trade history |
| `/api/ingest/activity` | POST | Fetch activity feed |
| `/api/ingest/positions` | POST | Snapshot positions |
| `/api/ingest/markets` | POST | Fetch market metadata |
| `/api/run/detectors` | POST | Run strategy detectors |
| `/api/compute/pnl` | POST | Compute P&L buckets |
| `/api/compute/arb_feasibility` | POST | Analyze arb costs |

### Grafana Dashboards (`http://localhost:3000`)

- PolyTool - User Trades
- PolyTool - Strategy Detectors
- PolyTool - PnL
- PolyTool - User Overview
- PolyTool - Liquidity Snapshots
- PolyTool - Arb Feasibility
- PolyTool - Infra Smoke

---

## 6. Privacy & Guardrails

### What's Enforced

| Control | Location | Mechanism |
|---------|----------|-----------|
| Private paths blocked | `tools/guard/pre_push_guard.py` | Checks staged files for `kb/`, `artifacts/` |
| Secrets patterns blocked | `tools/guard/guardlib.py` | Regex for `.env`, `response_*.json`, credentials |
| Gitignore enforced | `.gitignore` | `kb/**`, `artifacts/**`, `chroma/` |
| Pre-commit hook | `tools/guard/pre_commit_guard.py` | Same checks as pre-push |
| RAG default scope | `packages/polymarket/rag/query.py` | `is_private=true` default |

### How to Enable

```bash
git config core.hooksPath .githooks
```

### Testing Safety

```bash
python tools/guard/pre_push_guard.py  # Should exit 0
```

---

## 7. How to Run Locally

```bash
# 1. Clone and setup
git clone <repo>
cd PolyTool
cp .env.example .env
# Edit .env and set CLICKHOUSE_PASSWORD before the first docker compose up.

# 2. Start infrastructure
docker compose up -d --build
docker compose ps  # All healthy

# 3. Verify ClickHouse
curl "http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}/?query=SELECT%201&user=${CLICKHOUSE_USER:-polytool_admin}&password=${CLICKHOUSE_PASSWORD}"

# 4. Run a scan
python -m polytool scan  # Uses TARGET_USER from .env

# 5. View in Grafana
open http://localhost:3000  # admin/admin

# 6. Build RAG index (after scanning/exporting)
pip install -r requirements-rag.txt
python -m polytool rag-index --roots "kb,artifacts" --rebuild

# 7. Query RAG
python -m polytool rag-query --question "strategy patterns" --hybrid --rerank --k 8

# 8. Run tests
python -m pytest tests/ -v
```

---

## 8. Known Gaps & Risks (Top 10)

| # | Gap/Risk | Impact | File Evidence |
|---|----------|--------|---------------|
| 1 | **STRATEGY_PLAYBOOK.md missing** | No unified strategy documentation for users | Not found anywhere |
| 2 | **RAG_IMPLEMENTATION_REPORT.md stale** | Lists lexical/rerank as "recommended" but already implemented | `docs/RAG_IMPLEMENTATION_REPORT.md:243-261` |
| 3 | **datetime.utcnow() deprecated** | Python deprecation warnings in tests | `packages/polymarket/backfill.py:91,338` |
| 4 | **opus-bundle deprecated** | Still in CLI but marked deprecated | `polytool/__main__.py:135-140` |
| 5 | **No integration tests for API** | Only unit tests; API smoke tests exist | `tests/`, `tools/smoke/` |
| 6 | **FIFO matching approximate** | Hold time calculations may be inaccurate | `README.md:579` |
| 7 | **Category mapping depends on Gamma** | Data quality dependency on external API | `README.md:580` |
| 8 | **Slippage from current orderbook only** | Not historical depth at trade time | `README.md:585` |
| 9 | **No docs/specs/ content** | Specs directory empty | `docs/specs/` |
| 10 | **Fee curve parameters may change** | Hardcoded exponent=2.0 assumption | `README.md:407-412` |

---

## 9. Next 3 Recommended Milestones

### Milestone 1: Documentation Hygiene

**Acceptance Criteria:**
- [ ] Create `docs/STRATEGY_PLAYBOOK.md` consolidating detector info
- [ ] Update `docs/RAG_IMPLEMENTATION_REPORT.md` to reflect lexical/rerank implementation
- [ ] Remove `opus-bundle` deprecated command or document deprecation path
- [ ] Fix `datetime.utcnow()` deprecation warnings

**Kill Condition:** Other features blocked by documentation confusion

---

### Milestone 2: API Integration Testing

**Acceptance Criteria:**
- [ ] Add pytest integration tests for `/api/ingest/*` endpoints
- [ ] Add pytest integration tests for `/api/compute/*` endpoints
- [ ] CI runs tests against docker-compose stack

**Kill Condition:** Manual testing sufficient for current usage

---

### Milestone 3: Historical Orderbook Support

**Acceptance Criteria:**
- [ ] Store orderbook snapshots with trade timestamps
- [ ] Update slippage calculations to use historical depth
- [ ] Add backfill command for historical orderbooks

**Kill Condition:** Historical data not available from Polymarket APIs

---

## 10. Truth Matrix

| Claim | Doc Says | Code Says | Verdict |
|-------|----------|-----------|---------|
| 4 strategy detectors | Yes (`README.md:355-394`) | Yes (`detectors.py` has 4 classes) | **ALIGNED** |
| Hybrid retrieval supported | Yes (`LOCAL_RAG_WORKFLOW.md:110-116`) | Yes (`lexical.py`, RRF in `query.py`) | **ALIGNED** |
| Reranker supported | Yes (`LOCAL_RAG_WORKFLOW.md:115-116`) | Yes (`reranker.py`) | **ALIGNED** |
| Lexical/rerank "recommended" | Yes (`RAG_IMPLEMENTATION_REPORT.md:243-261`) | Already implemented | **DRIFT** |
| opus-bundle works | Deprecated (`__main__.py:29`) | Code exists but deprecated | **ALIGNED** |
| Pre-commit guard exists | Yes (`RISK_POLICY.md:24-30`) | Yes (`pre_commit_guard.py`) | **ALIGNED** |
| specs/ has content | Implied (`CLAUDE.md:7`) | Empty directory | **DRIFT** |
| 131 tests pass | N/A | Verified run | **VERIFIED** |
| RAG private-only default | Yes (`ARCHITECTURE.md:70-76`) | Yes (`query.py` uses `is_private=true`) | **ALIGNED** |
| STRATEGY_PLAYBOOK exists | Referenced nowhere | Not found | **MISSING** |

---

## Appendix: Commands Run

```bash
# Tests
python -m pytest tests/ -v --tb=short

# Guard verification
python tools/guard/pre_push_guard.py

# Git status/log
git status
git log --oneline -20

# File counts
python -c "...count files..."
```

---

## Appendix: Test Results Summary

```
131 tests collected
131 passed
0 failed
0 errors

Warnings: 4 (datetime.utcnow deprecation in backfill.py)
```
