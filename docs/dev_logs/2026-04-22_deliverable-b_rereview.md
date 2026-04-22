# 2026-04-22 PMXT Deliverable B - Re-review

## Objective

Re-review PMXT Deliverable B after the narrow fix pass and decide whether the
sports strategy pack is merge-ready.

## Files Changed And Why

- `docs/dev_logs/2026-04-22_deliverable-b_rereview.md` - review handoff log for
  this work unit.

## Files Inspected

- `packages/polymarket/simtrader/strategies/sports_momentum.py`
- `packages/polymarket/simtrader/strategies/sports_favorite.py`
- `packages/polymarket/simtrader/strategies/sports_vwap.py`
- `packages/polymarket/simtrader/strategy/facade.py`
- `tests/test_sports_strategies.py`
- `docs/dev_logs/2026-04-22_deliverable-b_fix-pass.md`
- `docs/dev_logs/2026-04-22_deliverable-b_validation-pack.md`
- `docs/dev_logs/2026-04-21_deliverable-b_reference-extract.md`

## Commands Run

### Workspace safety checks

Command:

```powershell
git status --short
```

Output:

```text
M docs/obsidian-vault/.obsidian/workspace.json
M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
D docs/obsidian-vault/00-Index/Dashboard.md
D docs/obsidian-vault/00-Index/Done.md
D docs/obsidian-vault/00-Index/Issues.md
D docs/obsidian-vault/00-Index/Todo.md
D docs/obsidian-vault/00-Index/Vault-System-Guide.md
D docs/obsidian-vault/01-Architecture/Data-Stack.md
D docs/obsidian-vault/01-Architecture/Database-Rules.md
D docs/obsidian-vault/01-Architecture/LLM-Policy.md
D docs/obsidian-vault/01-Architecture/Risk-Framework.md
D docs/obsidian-vault/01-Architecture/System-Overview.md
D docs/obsidian-vault/01-Architecture/Tape-Tiers.md
D docs/obsidian-vault/01-Architecture/Visual-Maps.md
D docs/obsidian-vault/02-Modules/Core-Library.md
D docs/obsidian-vault/02-Modules/Crypto-Pairs.md
D docs/obsidian-vault/02-Modules/FastAPI-Service.md
D docs/obsidian-vault/02-Modules/Gates.md
D docs/obsidian-vault/02-Modules/Historical-Import.md
D docs/obsidian-vault/02-Modules/Hypothesis-Registry.md
D docs/obsidian-vault/02-Modules/Market-Selection.md
D docs/obsidian-vault/02-Modules/Notifications.md
D docs/obsidian-vault/02-Modules/RAG.md
D docs/obsidian-vault/02-Modules/RIS.md
D docs/obsidian-vault/02-Modules/SimTrader.md
D docs/obsidian-vault/03-Strategies/Track-1A-Crypto-Pair-Bot.md
D docs/obsidian-vault/03-Strategies/Track-1B-Market-Maker.md
D docs/obsidian-vault/03-Strategies/Track-1C-Sports-Directional.md
D docs/obsidian-vault/04-CLI/CLI-Reference.md
D docs/obsidian-vault/05-Roadmap/Phase-0-Accounts-Setup.md
D docs/obsidian-vault/05-Roadmap/Phase-1A-Crypto-Pair-Bot.md
D docs/obsidian-vault/05-Roadmap/Phase-1B-Market-Maker-Gates.md
D docs/obsidian-vault/05-Roadmap/Phase-1C-Sports-Model.md
D docs/obsidian-vault/05-Roadmap/Phase-2-Discovery-Engine.md
D docs/obsidian-vault/05-Roadmap/Phase-3-Hybrid-RAG-Kalshi-n8n.md
D docs/obsidian-vault/05-Roadmap/Phase-4-Autoresearch.md
D docs/obsidian-vault/05-Roadmap/Phase-5-Advanced-Strategies.md
D docs/obsidian-vault/05-Roadmap/Phase-6-Closed-Loop.md
D docs/obsidian-vault/05-Roadmap/Phase-7-Unified-UI.md
D docs/obsidian-vault/05-Roadmap/Phase-8-Scale-Platform.md
D docs/obsidian-vault/06-Dev-Log/README.md
D docs/obsidian-vault/07-Issues/Issue-CH-Auth-Violations.md
D docs/obsidian-vault/07-Issues/Issue-Dead-Opportunities-Stub.md
D docs/obsidian-vault/07-Issues/Issue-Dual-Fee-Modules.md
D docs/obsidian-vault/07-Issues/Issue-Duplicate-Hypothesis-Registry.md
D docs/obsidian-vault/07-Issues/Issue-Duplicate-WebSocket-Code.md
D docs/obsidian-vault/07-Issues/Issue-FastAPI-Island.md
D docs/obsidian-vault/07-Issues/Issue-Multiple-Config-Loaders.md
D docs/obsidian-vault/07-Issues/Issue-Multiple-HTTP-Clients.md
D docs/obsidian-vault/07-Issues/Issue-Pyproject-Packaging-Gap.md
D docs/obsidian-vault/08-Research/00-INDEX.md
D docs/obsidian-vault/08-Research/01-Wallet-Discovery-Pipeline.md
D docs/obsidian-vault/08-Research/02-Metrics-Engine-MVF.md
D docs/obsidian-vault/08-Research/03-Insider-Detection.md
D docs/obsidian-vault/08-Research/04-Loop-B-Live-Monitoring.md
D docs/obsidian-vault/08-Research/05-LLM-Chunking-Strategy.md
D docs/obsidian-vault/08-Research/06-Wallet-Discovery-Roadmap.md
D docs/obsidian-vault/08-Research/07-Backtesting-Repo-Deep-Dive.md
D docs/obsidian-vault/08-Research/08-Copy-Trader-Deep-Dive.md
D docs/obsidian-vault/08-Research/08-Copy-Trader-and-Risk-Free-Bot-Deep-Dive.md
D docs/obsidian-vault/08-Research/09-Hermes-PMXT-Deep-Dive.md
D docs/obsidian-vault/09-Decisions/Decision - Loop A Leaderboard API.md
D docs/obsidian-vault/09-Decisions/Decision - Loop D Managed CLOB Subscription.md
D docs/obsidian-vault/09-Decisions/Decision - RIS Evaluation Gate Model Swappability.md
D docs/obsidian-vault/09-Decisions/Decision - RIS Evaluation Scoring Policy.md
D docs/obsidian-vault/09-Decisions/Decision - RIS n8n Pilot Scope.md
D docs/obsidian-vault/09-Decisions/Decision - Roadmap Narrowed to V1.md
D docs/obsidian-vault/09-Decisions/Decision - Two-Feed Architecture.md
D docs/obsidian-vault/09-Decisions/Decision - Two-Zone Vault Architecture.md
D docs/obsidian-vault/09-Decisions/Decision - Watchlist ClickHouse Storage.md
D docs/obsidian-vault/09-Decisions/Decision - Workflow Harness Refresh 2026-04.md
D docs/obsidian-vault/09-Decisions/Decision-Log.md
D docs/obsidian-vault/10-Session-Notes/2026-04-09 Architect Review Assessment.md
D docs/obsidian-vault/10-Session-Notes/2026-04-09 RIS n8n Workflows and Phase 2 Roadmap.md
D docs/obsidian-vault/10-Session-Notes/2026-04-09 Wallet Discovery Pipeline Design.md
D docs/obsidian-vault/10-Session-Notes/2026-04-10 Open Source Repo Integration Final Review.md
D docs/obsidian-vault/10-Session-Notes/2026-04-10 RIS Phase 2 Audit Results.md
D docs/obsidian-vault/10-Session-Notes/2026-04-21 Workflow Harness Refresh.md
D docs/obsidian-vault/10-Session-Notes/Session-Index.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 Claude - Architect Response.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 Codex - RIS Phase 2 Audit.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - CLOB WebSocket and Alchemy CU.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - Gemini Flash Structured Evaluation.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - Polymarket Event Volume.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - Polymarket Leaderboard API.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - RAG Retrieval Quality Testing.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - n8n Advanced Patterns.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - n8n ClickHouse Grafana Metrics.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-10 GLM5 - Unified Gap Fill Open Source Integration.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-10 GLM5 - n8n Claude Code Tooling.md
D docs/obsidian-vault/11-Prompt-Archive/2026-04-21 Architect Custom Instructions v2.md
D docs/obsidian-vault/11-Prompt-Archive/Archive-Index.md
D docs/obsidian-vault/12-Ideas/Idea - Cross-Platform Price Divergence as RIS Signal.md
D docs/obsidian-vault/12-Ideas/Idea - Graphify Pattern Adoption.md
D docs/obsidian-vault/12-Ideas/Idea - pmxt Sidecar Architecture Evaluation.md
D docs/obsidian-vault/12-Ideas/Ideas-Index.md
D docs/obsidian-vault/12-Ideas/Work-Packet - Fee Model Maker-Taker + Kalshi.md
D docs/obsidian-vault/12-Ideas/Work-Packet - Unified Open Source Integration Sprint.md
D docs/obsidian-vault/12-Ideas/Work-Packet - Unified Open Source Integration.md
?? docs/dev_logs/2026-04-22_deliverable-b_rereview.md
?? docs/obsidian-vault/.smart-env/multi/...
?? docs/obsidian-vault/Claude Desktop/
?? docs/obsidian-vault/PolyTool/
```

Command:

```powershell
git log --oneline -5
```

Output:

```text
efb6f01 feat(simtrader): PMXT Deliverable B -- merge-ready sports strategies
504e7b7 Fee Model Overhaul
42d9985 docs: add AGENTS.md and CURRENT_DEVELOPMENT.md for workflow refresh
2dc03a7 docs(quick-260415-rdy): complete Loop D feasibility -- add plan artifact and update STATE.md
b01c80a docs(quick-260415-rdp): complete Loop B phase 0 feasibility -- add plan artifact and update STATE.md
```

Command:

```powershell
python -m polytool --help
```

Output excerpt:

```text
PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]
```

Exit status: `0`

### Review verification

Command:

```powershell
python -m pytest tests/test_sports_strategies.py -q --tb=short
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 20 items

tests\test_sports_strategies.py ....................                     [100%]

============================= 20 passed in 0.40s ==============================
```

Command:

```powershell
python -m pytest tests/test_simtrader_strategy.py tests/test_simtrader_portfolio.py tests/test_market_maker_v1.py -q --tb=short
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 186 items

tests\test_simtrader_strategy.py ....................................... [ 20%]
..............                                                           [ 28%]
tests\test_simtrader_portfolio.py ...................................... [ 48%]
.......................................................                  [ 78%]
tests\test_market_maker_v1.py ........................................   [100%]

============================= 186 passed in 1.61s =============================
```

## Decisions Made During The Session

- Treated the unrelated `docs/obsidian-vault` changes as pre-existing noise and
  excluded them from the Deliverable B review scope.
- Re-verified blocker 1 through the actual constructor path used by
  `_build_strategy(...)`, not only by reading the fix log.
- Re-verified blocker 2 by checking the implementation branch and the dedicated
  `min_tick_size` tests.
- Re-verified blocker 3 against the clean-room notes in
  `2026-04-21_deliverable-b_reference-extract.md`.
- Re-verified blocker 4 by mapping validation-pack branches M2-M4, F2-F4, and
  V1-V4 to concrete tests in `tests/test_sports_strategies.py`.

## Review Outcome

- Question 1: yes, the documented nanosecond config keys now work for
  `sports_momentum` and `sports_favorite` through the normal strategy build path.
- Question 2: yes, `min_tick_size` now gates accepted trade size, not trade
  price.
- Question 3: yes, the inaccurate MIT wording is gone, and the remaining
  attribution is consistent with the behavior-only / clean-room guidance in the
  reference extract.
- Question 4: yes, the previously missing validation-pack branches are now
  covered well enough for this deliverable review.
- Verdict: MERGE-READY.

## Open Questions Or Blockers For Next Work Unit

- No remaining blockers for Deliverable B based on the requested re-review
  scope.
- Optional future hardening only: add one precedence test per strategy proving
  the `*_ns` field wins over the seconds field when both are provided with
  conflicting values.

## Codex Review Summary

- Tier: Recommended
- Issues found: 0 blocking, 0 non-blocking in the requested re-review scope
- Issues addressed: not applicable in this read-only review
