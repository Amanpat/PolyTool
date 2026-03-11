# Technology Stack

**Analysis Date:** 2026-03-05

## Languages

**Primary:**
- Python 3.10+ - All application code (CLI tools, packages, services, simtrader engine)
- SQL - ClickHouse migrations and queries (`infra/clickhouse/initdb/*.sql`)

**Secondary:**
- HTML/JavaScript - SimTrader Studio frontend (`packages/polymarket/simtrader/studio/static/index.html`)

## Runtime

**Environment:**
- Python 3.10+ (minimum; development uses Python 3.12.10)
- Docker for infrastructure services (ClickHouse, Grafana)

**Package Manager:**
- pip with setuptools build backend
- Lockfile: Not present (no `requirements.lock` or `pip.lock`)
- Editable install: `pip install -e ".[all]"` using `pyproject.toml`

## Frameworks

**Core:**
- No application framework for CLI tools - raw Python with `argparse`
- FastAPI `>=0.100.0` - SimTrader Studio web backend (`packages/polymarket/simtrader/studio/app.py`, `services/api/main.py`)
- Uvicorn `>=0.23.0` - ASGI server for FastAPI apps

**MCP Integration:**
- `mcp>=1.0.0` (FastMCP) - Claude Desktop integration server (`tools/cli/mcp_server.py`)

**Testing:**
- pytest `>=7.0.0` - Test runner; config in `pyproject.toml` `[tool.pytest.ini_options]`
- pytest-cov `>=4.0.0` - Coverage reporting

**Build/Dev:**
- setuptools `>=61.0` / wheel - Package build
- Docker Compose - Local infrastructure orchestration (`docker-compose.yml`)

## Key Dependencies

**Critical:**
- `requests>=2.28.0` - HTTP client for all Polymarket API calls (Gamma, Data, CLOB, Subgraph, Polygon RPC)
- `clickhouse-connect>=0.6.0` - ClickHouse analytics database client
- `websocket-client>=1.6` - WebSocket client for live market data streaming (optional dep `simtrader`)

**RAG Stack (optional dep `rag`):**
- `sentence-transformers>=2.2.0` - Local text embedding; default model `BAAI/bge-large-en-v1.5` (`packages/polymarket/rag/embedder.py`)
- `chromadb>=0.4.0` - Local vector database for semantic search (`packages/polymarket/rag/index.py`)
- `torch` - Required by sentence-transformers (included in `requirements-rag.txt`)
- `numpy` - Array operations for embeddings

**Infrastructure:**
- `pydantic>=2.5.0` - Data validation in API service (`services/api/requirements.txt`)
- SQLite (stdlib) with FTS5 - Lexical search index (`packages/polymarket/rag/lexical.py`, stored at `kb/rag/lexical/lexical.sqlite3`)

## Configuration

**Environment:**
- `.env` file at project root (gitignored); `.env.example` documents all variables
- Key env vars: `CLICKHOUSE_HOST`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DB`
- API endpoints: `GAMMA_API_BASE`, `DATA_API_BASE`, `CLOB_API_BASE`
- Blockchain: `POLYGON_RPC_URL`, `POLYMARKET_SUBGRAPH_URL`
- Operational: `HTTP_TIMEOUT_SECONDS`, `INGEST_MAX_PAGES_DEFAULT`, `PNL_*`, `BOOK_SNAPSHOT_*`

**Build:**
- `pyproject.toml` - Single source of truth for package metadata, dependencies, optional extras, and pytest config
- `Dockerfile` - Production image uses `python:3.11-slim`; installs `.[simtrader,studio]` extras

## Platform Requirements

**Development:**
- Python 3.10 or higher
- Docker + Docker Compose for infrastructure services
- Optional: FTS5-enabled SQLite build (for lexical RAG search)

**Production:**
- Docker Compose for all services: `clickhouse`, `grafana`, `api`, `polytool` (SimTrader Studio)
- ClickHouse HTTP port 8123, native port 9000
- Grafana port 3000
- API port 8000
- SimTrader Studio port 8765

---

*Stack analysis: 2026-03-05*
