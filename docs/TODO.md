# TODO: Deferred Items

Items that are out of MVP scope but should be considered for future versions.

## Track A — Gate 2 Blocker (updated 2026-03-21)

**Status: BLOCKED — edge scarcity, not missing plumbing or tapes**

- **`benchmark_v1.tape_manifest` now exists (Phase 1 closed 2026-03-21).**
  50 tapes across 5 buckets (`politics=10, sports=15, crypto=10,
  near_resolution=10, new_market=5`). The Gate 2 scenario sweep tooling can
  now be run against this manifest. Missing tapes are no longer the blocker.
- Gate 2 (Scenario Sweep) is blocked on edge scarcity: 0 eligible tapes
  with `executable_ticks > 0`; all pre-manifest candidates were DEPTH_ONLY
  with negative best_edge. The benchmark manifest may contain tapes with
  better edge — sweep first, then assess.
- Gate 2 tooling is complete (scan-gate2-candidates, prepare-gate2,
  watch-arb-candidates, tape-manifest, gate2-preflight, close_sweep_gate.py).
  No code work is needed to attempt the sweep.
- Gate 3, Stage 0, and Stage 1 remain blocked behind Gate 2.
- See `docs/dev_logs/2026-03-11_gate2_blocker_report.md` for original
  operator evidence and `docs/dev_logs/2026-03-21_phase1_docs_closeout.md`
  for Phase 1 completion record.

## High Priority (Post-MVP)

### Agent Hygiene

- [ ] Agent hygiene: dirty tree protocol (.claude/*)
  - [ ] don't stage unrelated changes
  - [ ] show `git status --short` + `git diff --stat`
  - [ ] list exact files touched

## Future Feature

- [] find users who are highly likely to be placing insider trades (new account, hundreds of thousands placed on odd bet)

### Wallet Anomaly Alerts / Flow Discrepancy Alerts [DEFERRED — Track B Research]

**Not part of the arb watcher. Not in current scope.**

Deferred until the current usability + workflow streamlining pass is complete
(end-to-end usability, UI clarity, command clarity, one-command RAG workflows,
better documentation, cleaner user-facing experience).

Intended future scope:
- [ ] Detect unusually large bets relative to a wallet's own history
  (e.g. wallet normally bets $50-200, suddenly places $50k)
- [ ] Detect unusually large bets relative to market-level or user-bucket baselines
  (e.g. position size is a statistical outlier vs. all participants on that market)
- [ ] Abnormal conviction alerts: extreme YES/NO skew, one-sided position building
  in a short window before a resolution event
- [ ] Treat this as **suspicious flow detection**, not proven insider detection —
  flag anomalies for human review, not automated trading action

Future integration points (when implemented):
- May feed market selection / watchlists as a signal lane
- May surface in research alerts or LLM bundle context
- Should live under a separate Track B signal pipeline, not inside the arb watcher

**Do not implement until current streamlining milestone is complete.**

### Resolution Enrichment

- [ ] On-chain resolution provider (read settlement from blockchain)
- [ ] Batch resolution fetching for performance
- [ ] Resolution caching with TTL
- [ ] Handle multi-outcome markets with partial resolution

### Fee Calculation

- [ ] Fetch actual fee_rate_bps from /fee-rate endpoint at trade time
- [ ] Store fee_rate_bps per trade in ClickHouse
- [ ] Calculate fees_actual from stored rate instead of estimating

### Hypothesis Validation Loop v0 [CLOSED 2026-03-12]

- [x] Schema-backed validation on `llm-save --hypothesis-path` with `validation_result.json`
- [x] `hypothesis-validate`, `hypothesis-diff`, and `hypothesis-summary` are shipped
- Next focus: Gate 2 scenario sweep against `config/benchmark_v1.tape_manifest` (Phase 2 / Phase 1B); `candidate-scan` is not the immediate priority.

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
- [ ] Align legacy `examine` trust artifact behavior with `scan` hydration/zero-position diagnostics
- [ ] Add targeted tests that enforce parity of trust artifact semantics between `scan` and `examine`

## Low Priority / Nice-to-Have

### CLI Improvements

- [ ] Progress bars for long operations
- [ ] JSON output mode for all commands
- [ ] Tab completion for bash/zsh
- [ ] Config file hot-reload
- [ ] Add a runtime warning when users invoke legacy `examine`, pointing to canonical `scan`

### Documentation Hygiene

- [ ] Rename `RUNBOOK_MANUAL_EXAMINE.md` to a scan-first filename (keep legacy alias note)
- [ ] Add a short troubleshooting snippet in runbooks for `scan --debug-export` (empty export triage flow)
- [ ] Add a docs guard/check so new non-deprecation `python -m polytool` command examples fail CI

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
