# TODO: Deferred Items

Items that are out of MVP scope but should be considered for future versions.

## High Priority (Post-MVP)

### Resolution Enrichment
- [ ] On-chain resolution provider (read settlement from blockchain)
- [ ] Batch resolution fetching for performance
- [ ] Resolution caching with TTL
- [ ] Handle multi-outcome markets with partial resolution

### Fee Calculation
- [ ] Fetch actual fee_rate_bps from /fee-rate endpoint at trade time
- [ ] Store fee_rate_bps per trade in ClickHouse
- [ ] Calculate fees_actual from stored rate instead of estimating

### Hypothesis Validation
- [ ] Automatic schema validation on llm-save
- [ ] Extract summary bullets from report for LLM_notes
- [ ] Hypothesis diff comparison across runs

## Medium Priority

### RAG Sources Caching
- [ ] Full robots.txt parsing (currently basic)
- [ ] Crawl depth support (follow links within domain)
- [ ] PDF/DOCX support for cached sources
- [ ] Automatic refresh based on TTL
- [ ] Cache eviction for expired content

### MCP Server
- [ ] HTTP transport (currently stdio only)
- [ ] Authentication for multi-user scenarios
- [ ] Resource endpoints for direct file access
- [ ] Streaming for large responses

### Multi-User Support
- [ ] Compare users side-by-side
- [ ] Portfolio-level aggregation
- [ ] User clustering by strategy similarity

### Code Quality (found during Roadmap 2)
- [ ] Migrate `datetime.utcnow()` to `datetime.now(timezone.utc)` across codebase
- [ ] DRY the `load_env_file` / `apply_env_defaults` helpers (duplicated in scan.py and examine.py)
- [ ] Add type stubs or Protocol for ClickHouse client to improve static analysis
- [ ] Coverage report: add Markdown table for PnL-by-outcome breakdown
- [ ] Run manifest: add `platform` and `python_version` fields for reproducibility

## Low Priority / Nice-to-Have

### CLI Improvements
- [ ] Progress bars for long operations
- [ ] JSON output mode for all commands
- [ ] Tab completion for bash/zsh
- [ ] Config file hot-reload

### Grafana Dashboards
- [ ] User comparison dashboard
- [ ] Category breakdown panel
- [ ] Win rate trend over time
- [ ] Position lifecycle visualization

### Testing
- [ ] Integration tests for full examine workflow
- [ ] Mock ClickHouse for CI
- [ ] Property-based tests for fee calculation
- [ ] Load testing for RAG index

## Out of Scope (Not Planned)

- Backtesting infrastructure
- Real-time trade monitoring
- External LLM API calls (remains local-only)
- Mobile app / web UI
- Multi-tenant hosting

## Spec Stubs (Need Full Design)

### SPEC-0002: Fee Enrichment
- Design for storing per-trade fee_rate_bps
- Migration strategy for existing trades
- Fallback logic when rate unavailable

### SPEC-0003: Multi-Outcome Resolution
- Settlement semantics for 3+ outcome markets
- Partial resolution handling
- UI representation in dossier

### SPEC-0004: Crawl Configuration
- Domain-specific crawl rules
- Link extraction patterns
- Content extraction selectors
