# External Integrations

**Analysis Date:** 2026-03-05

## APIs & External Services

**Polymarket Gamma API:**
- Service: Gamma API - market metadata, user/handle resolution, token-to-market mapping
- Base URL: `https://gamma-api.polymarket.com` (default)
- SDK/Client: `requests` via `packages/polymarket/http_client.py`; wrapped in `packages/polymarket/gamma.py`
- Auth: None required (public API)
- Env var: `GAMMA_API_BASE`

**Polymarket Data API:**
- Service: Trade history ingestion, user activity
- Base URL: `https://data-api.polymarket.com` (default)
- SDK/Client: `requests` via `packages/polymarket/http_client.py`; wrapped in `packages/polymarket/data_api.py`
- Auth: None required (public API)
- Env var: `DATA_API_BASE`

**Polymarket CLOB API:**
- Service: Order book snapshots, price history for PnL calculations
- Base URL: `https://clob.polymarket.com` (default)
- SDK/Client: `requests` via `packages/polymarket/clob.py`
- Auth: None required (public API)
- Env var: `CLOB_API_BASE`

**Polymarket WebSocket (Live Market Data):**
- Service: Real-time market data streaming for SimTrader shadow mode, activeness probe, tape recording
- URL: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- SDK/Client: `websocket-client>=1.6` (optional dep); used in `packages/polymarket/simtrader/activeness_probe.py`, `packages/polymarket/simtrader/shadow/runner.py`, `packages/polymarket/simtrader/tape/recorder.py`
- Auth: None required (public WebSocket)

**The Graph (Polymarket Subgraph):**
- Service: CTF condition resolution fallback via GraphQL
- URL: `https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic` (default)
- SDK/Client: `requests` (raw HTTP POST with GraphQL body) in `packages/polymarket/subgraph.py`
- Auth: None required
- Env var: `POLYMARKET_SUBGRAPH_URL`

**Polygon Blockchain (JSON-RPC):**
- Service: On-chain CTF contract resolution state; queries `payoutDenominator` and `payoutNumerators`
- RPC URL: `https://polygon-rpc.com` (default)
- SDK/Client: Raw `requests` HTTP JSON-RPC calls (no web3.py); implemented in `packages/polymarket/on_chain_ctf.py`
- Contract: CTF at `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045` on Polygon
- Auth: None required (public RPC)
- Env var: `POLYGON_RPC_URL`

## Data Storage

**Databases:**

- ClickHouse (Analytics)
  - Purpose: Primary analytics store; trade data, PnL, market metadata, arb tables, LLM research packets
  - Connection: `CLICKHOUSE_HOST`, `CLICKHOUSE_PORT` (8123 HTTP, 9000 native), `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DB`
  - Client: `clickhouse-connect>=0.6.0`
  - Schema: 20 migration files in `infra/clickhouse/initdb/` (numbered `01_init.sql` through `20_clv_price_snapshots.sql`)
  - Users: `polytool_admin` (full access), `grafana_ro` (SELECT only for Grafana)

- SQLite (Lexical Search)
  - Purpose: FTS5 full-text search index for RAG lexical queries
  - Location: `kb/rag/lexical/lexical.sqlite3` (local filesystem, not Docker)
  - Client: Python stdlib `sqlite3`
  - Code: `packages/polymarket/rag/lexical.py`

**Vector Database:**
- ChromaDB `>=0.4.0`
  - Purpose: Semantic embedding store for local RAG pipeline
  - Default persist dir: configured via `RAG_DEFAULT_PERSIST_DIR` in `packages/polymarket/rag/defaults.py`
  - Client: `chromadb` Python package
  - Code: `packages/polymarket/rag/index.py`, `packages/polymarket/rag/query.py`

**File Storage:**
- Local filesystem (`artifacts/`, `kb/`) for run artifacts, tapes, sweep outputs, embeddings
- No remote object storage (S3, GCS, etc.) detected

**Caching:**
- In-memory caching via `CachedResolutionProvider` in `packages/polymarket/resolution.py`
- No Redis or external cache layer

## Authentication & Identity

**Auth Provider:**
- None - no user authentication system
- All Polymarket APIs are public (no auth keys required)
- Local infrastructure uses hardcoded dev credentials (documented in `.env.example`)

**Identity Resolution:**
- `packages/polymarket/resolution.py` - 4-stage cascade: ClickHouse -> OnChainCTF -> Subgraph -> Gamma
- `polytool/user_context.py` - Resolves handles/wallets to market slugs

## Monitoring & Observability

**Visualization:**
- Grafana `11.4.0` - Dashboard UI at `http://localhost:3000`
- Plugin: `grafana-clickhouse-datasource` (auto-installed)
- Dashboards: `infra/grafana/dashboards/` (JSON files committed)
- Provisioning: `infra/grafana/provisioning/` (auto-configured datasource)

**Error Tracking:**
- None (no Sentry, Datadog, or similar)

**Logs:**
- Python stdlib `logging` throughout; configured via `logging.basicConfig`
- MCP server routes all diagnostic output to stderr to avoid polluting MCP JSON-RPC stdout

## CI/CD & Deployment

**Hosting:**
- Local-first; all services run via Docker Compose
- No cloud deployment configuration detected

**CI Pipeline:**
- None detected (no `.github/workflows/`, no CircleCI, no GitLab CI)

## Environment Configuration

**Required env vars (from `.env.example`):**
- `CLICKHOUSE_DB`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD` - ClickHouse auth
- `CLICKHOUSE_HTTP_PORT`, `CLICKHOUSE_NATIVE_PORT` - ClickHouse ports
- `GRAFANA_CH_USER`, `GRAFANA_CH_PASSWORD` - Grafana read-only ClickHouse user
- `GAMMA_API_BASE`, `DATA_API_BASE`, `CLOB_API_BASE` - Polymarket API endpoints
- `POLYGON_RPC_URL` - Polygon JSON-RPC endpoint
- `POLYMARKET_SUBGRAPH_URL` - The Graph subgraph URL

**Optional env vars:**
- `INGEST_MAX_PAGES_DEFAULT`, `HTTP_TIMEOUT_SECONDS` - Ingest tuning
- `PNL_BUCKET_DEFAULT`, `PNL_ORDERBOOK_CACHE_SECONDS`, `PNL_MAX_TOKENS_PER_RUN` - PnL config
- `BOOK_SNAPSHOT_*` - Order book snapshot tuning
- `TARGET_USER`, `SCAN_*` - Scan runner defaults

**Secrets location:**
- `.env` file at project root (gitignored); never committed
- Template at `.env.example` (committed, no secret values)

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- None detected

## MCP Integration (Claude Desktop)

**Protocol:**
- MCP SDK `>=1.0.0` (FastMCP) via stdio transport
- Server: `tools/cli/mcp_server.py`
- Tools exposed: `polymarket_export_dossier`, `polymarket_llm_bundle`, `polymarket_rag_query`, `polymarket_save_hypothesis`
- Usage: `polytool mcp` - runs locally, no external data upload

---

*Integration audit: 2026-03-05*
