# Codebase Concerns

**Analysis Date:** 2026-03-05

---

## Tech Debt

**Deprecated `datetime.utcnow()` used throughout:**
- Issue: Python 3.12 deprecated `datetime.utcnow()` — produces `DeprecationWarning` on every invocation. All modules wrap it in a local `_utcnow()` helper rather than fixing the root cause.
- Files: `tools/cli/agent_run.py`, `tools/cli/batch_run.py`, `tools/cli/cache_source.py`, `tools/cli/examine.py`, `tools/cli/export_clickhouse.py`, `tools/cli/llm_bundle.py`, `tools/cli/llm_save.py`, `tools/cli/mcp_server.py`, `packages/polymarket/arb.py`, `packages/polymarket/backfill.py`, `packages/polymarket/data_api.py`, `packages/polymarket/detectors.py`
- Impact: Warning noise in all Python 3.12+ runs; will become an error in a future Python version.
- Fix approach: Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` throughout. The `_utcnow()` wrappers make this a one-location-per-file change.

**ClickHouse connection helpers copy-pasted across four CLI files:**
- Issue: `_resolve_clickhouse_host()`, `_resolve_clickhouse_port()`, `_resolve_clickhouse_database()`, and the `DEFAULT_CLICKHOUSE_USER/PASSWORD` constants are duplicated verbatim in four files with no shared source of truth.
- Files: `tools/cli/scan.py`, `tools/cli/examine.py`, `tools/cli/export_clickhouse.py`, `tools/cli/export_dossier.py` (and `tools/smoke/smoke_liquidity_integrity.py`)
- Impact: Any change to ClickHouse connection logic (e.g., new env var, port change) must be applied in four places. Easy to miss one.
- Fix approach: Extract to `polytool/db.py` (or `packages/polymarket/clickhouse_client.py`) and import from all CLI modules.

**`sys.path.insert` hacks in every CLI tool:**
- Issue: Most `tools/cli/*.py` files prepend `../..` and `../../packages` to `sys.path` at module load time to resolve imports. This works when run directly but is fragile, pollutes the path globally, and is redundant when installed via `pip install -e .`.
- Files: `tools/cli/audit_coverage.py`, `tools/cli/examine.py`, `tools/cli/export_clickhouse.py`, `tools/cli/export_dossier.py`, `tools/cli/llm_bundle.py`, `tools/cli/llm_save.py`, `tools/cli/rag_eval.py`, `tools/cli/rag_index.py`, `tools/cli/rag_run.py`
- Impact: Import order is sensitive; in some environments imports silently resolve from the wrong location.
- Fix approach: Rely on the `pip install -e .` editable install (already set up in `pyproject.toml`). Remove all `sys.path.insert` stubs.

**Several `packages.polymarket.simtrader` sub-packages missing from `pyproject.toml`:**
- Issue: The following directories exist under `packages/polymarket/simtrader/` but are **not listed** in `[tool.setuptools] packages`:
  - `packages.polymarket.simtrader.batch`
  - `packages.polymarket.simtrader.strategy`
  - `packages.polymarket.simtrader.strategies`
  - `packages.polymarket.simtrader.portfolio`
  - `packages.polymarket.simtrader.shadow`
  - `packages.polymarket.simtrader.sweeps`
- Files: `pyproject.toml` (lines 63-69)
- Impact: Installed package builds (`pip install .`) will be missing these modules entirely. Only works because the project is run from source root with editable install or path hacks.
- Fix approach: Add the missing entries to `[tool.setuptools] packages` in `pyproject.toml`.

**`simtrader.py` CLI entry point is extremely large:**
- Issue: `tools/cli/simtrader.py` is 4,655 lines — the single largest source file. It contains argument parsing, business logic, output formatting, sweep orchestration, and Studio launch in a single file.
- Files: `tools/cli/simtrader.py`
- Impact: Hard to navigate, test in isolation, or extend without side effects. The file handles `quickrun`, `run`, `shadow`, `sweep`, `batch`, `studio`, `record`, `replay`, `browse`, `diff`, `report`, `clean`, and more.
- Fix approach: Split into command-specific handlers following the pattern already used elsewhere (e.g., `tools/cli/batch_run.py`).

**`services/api/main.py` is 3,054 lines with no test coverage:**
- Issue: The FastAPI service under `services/api/main.py` is the second-largest file and has **zero test coverage** — no test file covers it (confirmed by absence of any `services` import in `tests/`).
- Files: `services/api/main.py`
- Impact: Any regression in the API layer is invisible until runtime.
- Fix approach: Add a `tests/test_api.py` using `httpx.AsyncClient` and `TestClient` from FastAPI test utilities.

**`clv.py` bypasses `HttpClient` and uses raw `requests` directly:**
- Issue: `packages/polymarket/clv.py` imports `requests` directly rather than using the shared `HttpClient` wrapper (`packages/polymarket/http_client.py`). This means CLV calls get none of the retry/backoff/rate-limit logic the wrapper provides.
- Files: `packages/polymarket/clv.py` (line 11), `packages/polymarket/http_client.py`
- Impact: CLV lookups silently fail or raise on transient errors or rate-limit responses instead of retrying gracefully.
- Fix approach: Replace raw `requests` calls in `clv.py` with `HttpClient` or factor out its retry logic for reuse.

**Duplicate hardcoded WebSocket URL constant:**
- Issue: `WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"` is defined independently in two packages, plus a `DEFAULT_WS_URL` constant in the CLI.
- Files: `packages/polymarket/simtrader/activeness_probe.py` (line 25), `packages/polymarket/simtrader/tape/recorder.py` (line 23), `tools/cli/simtrader.py` (line 51)
- Impact: If the WebSocket endpoint changes, three locations need updating.
- Fix approach: Define once in `packages/polymarket/simtrader/__init__.py` or a `constants.py` and import everywhere.

---

## Known Bugs

**`test_user_context.py::TestGetSlugForUser::test_wallet_only` — pre-existing failure:**
- Symptoms: Test asserts `result in ("wallet_db27bf2a", "drpufferfish")` but fails because a `profile.json` leftover from a previous test run maps the wallet `0xdb27bf2a...` to `drpufferfish`, causing a different code path.
- Files: `tests/test_user_context.py` (line 305), `polytool/user_context.py` (`_find_slug_by_wallet` reads `kb/users/*/profile.json`)
- Trigger: Run on a developer machine that has previously scanned `@DrPufferfish` — the `kb/` directory retains the mapping.
- Workaround: Delete `kb/users/drpufferfish/profile.json` before running the test suite; or run in a clean temp directory.
- Fix approach: Patch `_find_slug_by_wallet` in the test to inject a mock KB path, or add a `tmp_path` fixture to isolate the KB directory.

---

## Security Considerations

**Hardcoded default ClickHouse credentials committed to source:**
- Risk: `polytool_admin` / `polytool_admin` is the admin credential for the ClickHouse instance. It's committed as `DEFAULT_CLICKHOUSE_USER` / `DEFAULT_CLICKHOUSE_PASSWORD` constants in four production Python files.
- Files: `tools/cli/scan.py` (lines 85-86), `tools/cli/examine.py` (lines 53-54), `tools/cli/export_clickhouse.py` (lines 21-22), `tools/cli/export_dossier.py` (lines 28-29), `tools/smoke/smoke_liquidity_integrity.py` (line 33)
- Current mitigation: Credentials are local-only (ClickHouse not publicly exposed), and the `CLAUDE.md` notes they are local dev credentials. A `guardlib.py` (`tools/guard/guardlib.py`) blocks committing secrets-like file names but does not scan file contents.
- Recommendation: Move defaults to `.env.example` with a required override. Add a pre-commit content scan for the literal string `polytool_admin` in `.py` files.

**Grafana datasource password committed in YAML:**
- Risk: `grafana_readonly_local` is committed in plaintext to `infra/grafana/provisioning/datasources/clickhouse.yaml` (line 16) and the ClickHouse init SQL `infra/clickhouse/initdb/01_init.sql` (line 11).
- Files: `infra/grafana/provisioning/datasources/clickhouse.yaml`, `infra/clickhouse/initdb/01_init.sql`
- Current mitigation: Local-only infrastructure. The `CLAUDE.md` explicitly documents these as local dev credentials.
- Recommendation: Use Docker Compose env-var substitution (`${GRAFANA_CH_PASSWORD}`) so the files contain no literal password.

**`BinaryComplementArb` merge_full_set operations are modelled assumptions, not real fills:**
- Risk: The strategy labels certain records `"ASSUMPTION"` because on-chain full-set merge timing and partial resolution are not modelled. Users may interpret output artifacts as confirmed P&L.
- Files: `packages/polymarket/simtrader/strategies/binary_complement_arb.py` (lines 15-23, 109, 534, 873)
- Current mitigation: Every affected output record includes an explicit `"ASSUMPTION"` key with a disclaimer string.
- Recommendation: The disclaimer is adequate; this is a known modelling limitation. No code fix needed, but should be surfaced prominently in the Studio UI.

---

## Performance Bottlenecks

**RAG index load is synchronous and blocks CLI startup:**
- Problem: `packages/polymarket/rag/index.py` and `packages/polymarket/rag/lexical.py` initialise Chroma and SQLite at import time or first use. SentenceTransformer model loading is slow (~2-8s depending on hardware) and happens on the critical path for any `llm_bundle` or `rag_query` invocation.
- Files: `packages/polymarket/rag/embedder.py`, `packages/polymarket/rag/index.py`
- Cause: Model is instantiated eagerly in `SentenceTransformerEmbedder.__init__`.
- Improvement path: Lazy-load the model on first encode call. Add a `--warm-up` flag for scenarios where latency matters.

**`simtrader.py` CLI imports all sub-systems on every invocation:**
- Problem: Even `python -m polytool simtrader --help` triggers all imports including `packages/polymarket/simtrader/studio/app.py` (FastAPI, 1,422 lines), `packages/polymarket/simtrader/batch/runner.py`, and all strategy modules.
- Files: `tools/cli/simtrader.py` (top-level imports)
- Cause: Monolithic file structure — all commands in one module.
- Improvement path: Convert subcommands to lazy imports triggered only when the specific subcommand is invoked.

---

## Fragile Areas

**`scan.py` argparse internals patched in `batch_run.py`:**
- Files: `tools/cli/batch_run.py` (lines 98, 107)
- Why fragile: `batch_run.py` iterates `scan_parser._actions` (a private argparse attribute) to clone scan flags. Any argparse API change or scan flag refactoring silently breaks batch cloning.
- Safe modification: When modifying `scan.py` argument definitions, verify `batch_run.py` still builds correctly; run `tests/test_batch_run.py`.
- Test coverage: `tests/test_batch_run.py` exists and covers the wiring.

**`studio_sessions.py` threading model — log reader thread outlives session:**
- Files: `packages/polymarket/simtrader/studio_sessions.py` (lines 251, 354-364)
- Why fragile: Worker threads read subprocess stdout via blocking `readline()`. If the session subprocess hangs, the reader thread blocks indefinitely. The `_lock` (`threading.RLock`) protects `_processes` dict but not the per-session log buffer writes.
- Safe modification: Add a `timeout` parameter to the readline loop and document the thread lifecycle. Do not add per-session state outside the lock.
- Test coverage: `tests/test_simtrader_studio_sessions.py` exists.

**`user_context.py` profile resolution reads from the live `kb/` directory:**
- Files: `polytool/user_context.py` (lines 128, 174-187)
- Why fragile: `_find_slug_by_wallet` and `_load_profile` walk `kb/users/*/profile.json` relative to the current working directory. Tests that invoke this code without mocking are affected by real KB state (see Known Bug above).
- Safe modification: Pass `kb_root: Path` explicitly rather than computing it from cwd. Inject a temp path in tests.

**`packages/polymarket/rag/lexical.py` SQLite FTS5 availability check is fragile:**
- Files: `packages/polymarket/rag/lexical.py` (lines 34-36)
- Why fragile: FTS5 availability is probed at import time by running a test query against `:memory:`. If FTS5 is absent the module emits a warning and silently disables lexical search for the entire process lifetime. No retry or explicit error surface at query time.
- Safe modification: Raise `ImportError` or a custom `LexicalIndexUnavailable` at the call site rather than silently degrading.

---

## Scaling Limits

**Chroma vector DB is single-process, file-based:**
- Current capacity: Local ChromaDB persisted to `kb/rag/chroma/`. No concurrency controls.
- Limit: Concurrent writes from multiple processes (e.g., parallel `rag-index` runs) will corrupt the index.
- Scaling path: Use a single indexing process, or migrate to a server-mode Chroma instance with the `chromadb[server]` extra.

**`StudioSessionManager` has no cap on concurrent subprocess sessions:**
- Current capacity: Unbounded. Each session spawns a subprocess with `subprocess.PIPE` stdout.
- Limit: On resource-constrained machines, many simultaneous SimTrader runs (each loading tape files and running strategies) will exhaust RAM and file descriptors.
- Files: `packages/polymarket/simtrader/studio_sessions.py`
- Scaling path: Add a `max_concurrent_sessions` config option and return a `429`-equivalent error when the cap is reached.

---

## Dependencies at Risk

**`chromadb>=0.4.0` pin is very broad:**
- Risk: ChromaDB has had breaking API changes between minor versions (e.g., the `EmbeddingFunction` interface and collection metadata APIs changed between 0.4.x and 0.5.x). The pin `>=0.4.0` allows pip to install a version that breaks `packages/polymarket/rag/`.
- Files: `pyproject.toml` (line — rag optional deps), `packages/polymarket/rag/index.py`
- Impact: `rag-index`, `rag-query`, and `llm-bundle` silently fail or produce wrong results after an auto-upgrade.
- Migration plan: Pin to `chromadb>=0.4.0,<1.0` and add an integration smoke test that exercises `query_index`.

**`sentence-transformers>=2.2.0` pin allows major version upgrades:**
- Risk: `sentence-transformers` 3.x introduced breaking changes to `SentenceTransformer` constructor args and `encode()` return types.
- Files: `pyproject.toml`, `packages/polymarket/rag/embedder.py`, `packages/polymarket/rag/reranker.py`
- Impact: RAG embeddings silently produce wrong-shaped vectors after upgrade.
- Migration plan: Pin to `sentence-transformers>=2.2.0,<4.0` and test after upgrade.

---

## Missing Critical Features

**No input validation on `services/api/main.py` endpoints:**
- Problem: The 3,054-line FastAPI service has no Pydantic models or request validation for most endpoints — request bodies are typed as `dict` or `Any`.
- Files: `services/api/main.py`
- Blocks: Safe production deployment; structured error responses.

**No coverage configuration or enforcement:**
- Problem: `pyproject.toml` configures `pytest-cov` as a dev dependency but sets no minimum coverage threshold and no `--cov` option in `addopts`. Coverage is opt-in and untracked.
- Files: `pyproject.toml`
- Blocks: Regressions in untested code paths are invisible in CI.

---

## Test Coverage Gaps

**`services/api/main.py` — zero test coverage:**
- What's not tested: All 3,054 lines of the FastAPI service (endpoints, middleware, error handlers).
- Files: `services/api/main.py`
- Risk: Any endpoint regression is caught only at manual runtime.
- Priority: High

**`packages/polymarket/arb.py` and `packages/polymarket/backfill.py` — no dedicated tests:**
- What's not tested: Arbitrage detection logic and historical data backfill pipeline.
- Files: `packages/polymarket/arb.py`, `packages/polymarket/backfill.py`
- Risk: Silent failures in data ingestion; incorrect arb signals written to ClickHouse.
- Priority: High

**`packages/polymarket/simtrader/studio/ondemand.py` (884 lines) — partially tested:**
- What's not tested: On-demand session lifecycle edge cases, error paths in `ondemand_step`, session expiry.
- Files: `packages/polymarket/simtrader/studio/ondemand.py`
- Risk: OnDemand sessions silently stall or corrupt state in the Studio UI.
- Priority: Medium

**`tools/cli/cache_source.py` — broad `except Exception: pass` blocks:**
- What's not tested: The `except Exception: pass` handlers at lines 169, 327-328 silently swallow errors in cache read and write paths.
- Files: `tools/cli/cache_source.py`
- Risk: Cache corruption or network errors are silently ignored, causing stale data to be used without warning.
- Priority: Medium

---

*Concerns audit: 2026-03-05*
