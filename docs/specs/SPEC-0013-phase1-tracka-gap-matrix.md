# SPEC-0013: Phase 1 Track A Gap Matrix

**Status:** Accepted — Read-only audit
**Created:** 2026-03-08
**Authors:** PolyTool Contributors

---

## Executive Verdict

**Gate 2 is the primary bottleneck to Stage 1 capital.** The gate failed with
0/24 scenarios profitable because the only sweep tape (`bitboy-convicted`) had
insufficient order book depth on both legs. Every other blocker (Gate 3 manual
sign-off, Stage 0 not started, Stage 1 not started) cascades from this single
gate failure.

The execution infrastructure (6 modules, 883+ tests, all passing) is
production-ready at the API level. The code is not the bottleneck.
The blockers are operational: finding an eligible tape, running Gate 3 shadow
sessions on diverse markets, and completing Stage 0 paper-live.

**Do not deploy Stage 1 capital.** The kill path is clear; the gates are not.

---

## 1. Audit Method

**Audit date:** 2026-03-08
**Branch audited:** `simtrader`
**Audit type:** Read-only. No code or docs were modified.

**Documents read:**
- `docs/PLAN_OF_RECORD.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `docs/CURRENT_STATE.md`
- `docs/OPERATOR_QUICKSTART.md`
- `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`
- `docs/specs/SPEC-0011-live-execution-layer.md`
- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md`
- `docs/features/FEATURE-trackA-live-clob-wiring.md`

**Repo paths inspected:**
- `packages/polymarket/simtrader/execution/` (all 7 modules)
- `packages/polymarket/simtrader/strategies/` (3 strategies)
- `packages/polymarket/market_selection/` (3 modules)
- `tools/gates/` (4 gate scripts + checklist)
- `tools/cli/` (simtrader.py, market_scan.py, scan_gate2_candidates.py)
- `services/api/main.py` (FastAPI service)
- `infra/` (docker-compose.yml, grafana dashboards)
- `artifacts/gates/` (gate artifact files)
- `artifacts/simtrader/tapes/` (tape inventory)
- `tests/` (5 targeted test files)
- `.env.example`

**Evidence standard applied:** Every status claim in this document is backed by
a specific file path. "Partial" is not "done." "Script exists" is not
"operationally ready."

---

## 2. Repo Evidence Inventory

### 2.1 Execution Layer — `packages/polymarket/simtrader/execution/`

| Module | Size (est.) | Implementation | Test Coverage |
|--------|-------------|----------------|---------------|
| `kill_switch.py` | Small | `FileBasedKillSwitch` reads `artifacts/kill_switch.txt`; truthy content trips it; OSError → safe False | `tests/test_live_execution.py` |
| `rate_limiter.py` | Small | `TokenBucketRateLimiter(max_per_minute=30)`; `try_acquire()` / `acquire()`; injected clock | `tests/test_live_execution.py` |
| `risk_manager.py` | Medium | 5 pre-trade guards (order notional, position notional, inventory units, inventory skew, daily loss); sticky `_halt_reason` | `tests/test_live_execution.py`, `tests/test_wallet_integration.py` |
| `live_executor.py` | Medium | `LiveExecutor`: kill-switch-first → dry-run check → rate-limit → client call; `OrderRequest` / `OrderResult` dataclasses | `tests/test_live_execution.py` |
| `order_manager.py` | Medium | `reconcile_once()`: diffs desired vs. open by `(asset_id, side)` slot; sliding 60-second rate window; `min_order_lifetime_seconds` age guard | `tests/test_order_manager.py` |
| `live_runner.py` | Medium | Top-level orchestrator: wires strategy → RiskManager → OrderManager → LiveExecutor; gate-aware startup; dry-run default | `tests/test_live_execution.py` |
| `wallet.py` | Small | `build_client()` reads `PK` + CLOB creds from env; `derive_and_print_creds()` for one-time setup | `tests/test_wallet_integration.py` |

**Source files confirmed at:** `packages/polymarket/simtrader/execution/__init__.py` (7 exports).

### 2.2 Strategies — `packages/polymarket/simtrader/strategies/`

| Strategy | Phase 1 Role | Key implementation |
|----------|-------------|-------------------|
| `market_maker_v0.py` | **Phase 1 mainline live strategy** | Avellaneda-Stoikov; microprice; rolling σ estimate; resolution guard; bounded spreads and quote clamps |
| `binary_complement_arb.py` | Gate 2 scouting vehicle only (not live) | Detects `sum_ask < 1 - buffer`; dual-leg legging; `ASSUMPTION` key on merge_full_set records |
| `copy_wallet_replay.py` | Legacy — not used in Phase 1 | Replay-copies a reference wallet |

### 2.3 Market Selection — `packages/polymarket/market_selection/`

| Module | What it does |
|--------|-------------|
| `filters.py` | 5 pre-filters: mid-price 10–90%, resolution > 3 days, volume > $5k, reward config present, not recently resolved |
| `scorer.py` | Composite score: 35% reward APR, 25% spread, 20% fill, 15% competition, 5% age factor |
| `api_client.py` | `fetch_active_markets()`, `fetch_orderbook()`, `fetch_reward_config()` |

### 2.4 Gate Scripts — `tools/gates/`

| Script | What it runs | Artifact written |
|--------|-------------|-----------------|
| `close_replay_gate.py` | Tape → replay twice → diff summaries | `artifacts/gates/replay_gate/gate_passed.json` or `gate_failed.json` |
| `close_sweep_gate.py` | 24-scenario sweep → ≥70% profitable criterion | `artifacts/gates/sweep_gate/gate_passed.json` or `gate_failed.json` |
| `shadow_gate_checklist.md` | Manual operator checklist | Operator writes `artifacts/gates/shadow_gate/gate_passed.json` by hand |
| `run_dry_run_gate.py` | `simtrader live --dry-run` → verify `submitted=0` | `artifacts/gates/dry_run_gate/gate_passed.json` or `gate_failed.json` |
| `gate_status.py` | Reads all 4 gate artifacts; exits 0 iff all passed | None (reporter only) |

### 2.5 Gate Artifacts — `artifacts/gates/`

| Gate | Artifact present | Status | Timestamp |
|------|-----------------|--------|-----------|
| Gate 1 — Replay | `replay_gate/gate_passed.json` | **PASSED** | 2026-03-06T04:44:35Z |
| Gate 2 — Sweep | `sweep_gate/gate_failed.json` | **FAILED** | 2026-03-06T00:36:25Z |
| Gate 3 — Shadow | `shadow_gate/shadow_pid.txt`, `shadow_stderr.log`, `shadow_stdout.log` | **PENDING** (no gate_passed or gate_failed) | — |
| Gate 4 — Dry-Run | `dry_run_gate/gate_passed.json` | **PASSED** | 2026-03-05T21:50:10Z |

**Gate 2 failure detail** (`artifacts/gates/sweep_gate/gate_failed.json`):
- `profitable_scenarios: 0` out of 24
- `profitable_fraction: 0.0` (need ≥ 0.70)
- `scenarios_with_trades: 0`
- Dominant rejections: `insufficient_depth_no: 144`, `insufficient_depth_yes: 120`, `no_bbo: 24`, `stale_or_missing_snapshot: 24`
- Tape used: `bitboy-convicted_64fd7c95` — market lacked liquidity for either leg under any parameter combo

### 2.6 Tape Inventory — `artifacts/simtrader/tapes/`

**Total directories: 13**

| Market slug / ID | Count | Category | Suitable for Gate 2? |
|-----------------|-------|----------|---------------------|
| `bitboy-convicted_64fd7c95` | 5 | Crypto/legal | No — insufficient depth confirmed |
| `will-the-oklahoma-city-thunder-win-t_fde7b16a` | 2 (shadow) | Sports / NBA | Unknown — shadow mode, not sweep-validated |
| `will-the-toronto-map*` | 1 | Sports / NHL (partial slug) | Unknown |
| `will-the-vancouver-c*` | 1 | Sports / NHL (partial slug) | Unknown |
| `will-the-calgary-fla*` | 1 | Sports / NHL (partial slug) | Unknown |
| Unknown token IDs (97449340, 10167699) | 2 (shadow) | Unknown category | Unknown |

**Politics tapes:** 0
**Tapes with confirmed depth (Gate 2 eligible):** 0
**Total with identifiable market category:** ~8 of 13

### 2.7 Infrastructure — `infra/` and root

| File | Status | What it contains |
|------|--------|-----------------|
| `docker-compose.yml` | Present | 5 services: clickhouse (8123/9000), grafana (3000), api (8000), migrate, polytool/studio (8765) |
| `.env.example` | Present | ~64 env var templates including ClickHouse, Grafana, Polymarket APIs, CLOB credentials placeholder |
| `infra/grafana/dashboards/` | 7 JSON files | Infrastructure smoke, PnL, user trades, strategy detectors, arb feasibility, liquidity snapshots, user overview |

**Live-bot Grafana panels:** 0 of 7 dashboards contain live bot metrics (order submission rate, kill-switch state, risk manager violations, inventory skew, daily loss progression).

### 2.8 FastAPI Service — `services/api/main.py`

- File size: ~110KB
- Imports: FastAPI, ClickHouse connect, Gamma client, DataApi client, CLOB client, StudioSessionManager
- No Discord webhook integration visible
- No gate-triggering automation endpoints visible in first 80 lines
- No live bot order/fill ingestion endpoint visible

### 2.9 Discord / n8n

**Discord webhook:** 0 occurrences of `discord` or `webhook` in any `.py` file in the repo.
**n8n:** 0 occurrences of `n8n` in any `.py`, `.yml`, or `.yaml` file in the source tree (matches found only in `.claude/`, `.planning/` artifact dirs — not source).

### 2.10 Test Coverage

| Test file | Test scope | Passes? |
|-----------|-----------|---------|
| `tests/test_live_execution.py` | KillSwitch, RateLimiter, RiskManager, LiveExecutor, LiveRunner | Yes (883+ total) |
| `tests/test_order_manager.py` | Reconciliation, rate caps, age hold, ActionPlan | Yes |
| `tests/test_wallet_integration.py` | `build_client()`, real_client wiring, inventory skew | Yes |
| `tests/test_market_maker_v0.py` | Avellaneda-Stoikov model, tick rounding, quote bounds | Yes |
| `tests/test_market_selection.py` | Filters (5 gates), scorer weights | Yes |

---

## 3. Phase 1 Requirements Matrix

### Row definitions

| Status | Meaning |
|--------|---------|
| **SHIPPED** | Fully implemented and verified with file evidence |
| **PARTIAL** | Code exists but operationally incomplete; not ready to use in production |
| **MISSING** | No implementation whatsoever |
| **BLOCKED** | Cannot proceed; depends on an unmet prerequisite |

---

### Requirement 1: 15+ diverse market tapes (politics, sports, new markets)

**Status: PARTIAL → effectively MISSING**

**Evidence:**
- 13 tapes total at `artifacts/simtrader/tapes/` (not 15+)
- Politics market tapes: **0**
- Sports tapes: 7 (NBA + 3 NHL + 2 unidentified shadow)
- "New market" category tapes: **0** (no tapes explicitly from markets < 48 hours old)
- Confirmed Gate-2-eligible tapes (depth verified): **0**
- Tapes used for Gate 1: 1 (`bitboy-convicted_64fd7c95`)
- Gate 2 ran on `bitboy-convicted_64fd7c95` and failed due to insufficient depth

**Gap:** Need ≥ 15 tapes covering politics, sports, and new markets with confirmed depth; 0 confirmed eligible tapes exist now.

---

### Requirement 2: Gate 2 sweep ≥70% profitable (2% fee model)

**Status: BLOCKED**

**Evidence:**
- `artifacts/gates/sweep_gate/gate_failed.json` — `profitable_fraction: 0.0`, `profitable_scenarios: 0/24`
- Dominant rejections: `insufficient_depth_no: 144`, `insufficient_depth_yes: 120`
- Strategy (`binary_complement_arb`, `sane` preset): correctly implemented; failure is market depth, not code
- `tools/gates/close_sweep_gate.py` — gate script is implemented and works
- `packages/polymarket/simtrader/strategies/binary_complement_arb.py` — strategy implemented and tested

**Gap:** Gate 2 needs a tape with `executable_ticks > 0`. No eligible tape exists. Finding one requires live market observation during a complement-arb dislocation event.

---

### Requirement 3: Gate 3 shadow readiness on 3–5 live markets

**Status: MISSING**

**Evidence:**
- `artifacts/gates/shadow_gate/`: only `shadow_pid.txt` (empty), `shadow_stderr.log` (177 bytes, no signal), `shadow_stdout.log` (empty)
- No `gate_passed.json` at `artifacts/gates/shadow_gate/gate_passed.json`
- `tools/gates/shadow_gate_checklist.md` — checklist exists (127 lines) but has not been executed
- Shadow tapes at `artifacts/simtrader/tapes/`: 5 exist, but they were from earlier experiments; Gate 3 sign-off requires a deliberate operator run following the checklist

**Gap:** Gate 3 has never been executed and signed off. The requirement is 3–5 live markets; zero have been shadow-validated with formal sign-off. Blocked behind Gate 2 per promotion ladder.

---

### Requirement 4: Thin FastAPI wrapper for automation endpoints

**Status: PARTIAL**

**Evidence:**
- `services/api/main.py` (~110KB) — comprehensive FastAPI service with ClickHouse integration, Polymarket API clients, StudioSessionManager, trade ingestion, detector endpoints, PnL endpoints
- `services/api/Dockerfile` — containerized; included in `docker-compose.yml` on port 8000
- `services/api/requirements.txt` — dependencies declared

**What exists:** Data ingestion and analytics API. Studio session management.

**What is missing for Phase 1 automation:**
- No `/gates/status` endpoint (gate pass/fail readable via HTTP)
- No `/bot/health` endpoint (live runner state, kill-switch status, current PnL)
- No `/bot/start` or `/bot/stop` endpoints for automation hooks
- No Discord webhook call-out in any visible endpoint
- `services/worker/` and `services/studio/` directories exist but are empty

**Gap:** FastAPI exists but does not expose live-bot control or health surface. It is a data analytics API, not a live-bot automation API.

---

### Requirement 5: Local n8n setup (market scan + bot health workflows)

**Status: MISSING**

**Evidence:**
- Grep of `**/*.py`, `**/*.yml`, `**/*.yaml` for "n8n": zero matches in source files
- `docker-compose.yml`: no n8n service defined
- No n8n workflow JSON/YAML files anywhere in repo

**Gap:** n8n is entirely absent. No service, no workflow definitions, no configuration.

---

### Requirement 6: Market Selection Engine (reward/spread/volume/competition/new-market logic)

**Status: PARTIAL**

**Evidence — implemented:**
- `packages/polymarket/market_selection/filters.py` — 5 filters including volume (>$5k), resolution horizon (>3 days), mid-price range, reward config presence, recency guard
- `packages/polymarket/market_selection/scorer.py` — composite score: 35% reward APR, 25% spread, 20% fill, 15% competition, 5% age factor
- `packages/polymarket/market_selection/api_client.py` — `fetch_active_markets()`, `fetch_orderbook()`, `fetch_reward_config()`
- `tools/cli/market_scan.py` — `python -m polytool market-scan --top N` works
- `tests/test_market_selection.py` — filters and scoring tested

**Gap — new-market logic:**
- The 5% `age_factor` weakly approximates new-market preference but is not dedicated new-market logic
- Phase 1 requirement calls for explicit new-market scoring (markets < 48h old behave differently: wider spreads, lower competition, potentially higher reward APR volatility)
- No filter or scorer component specifically targets or accounts for new-market spread dynamics
- "New markets" filter (SPEC-0012 §4 and §5) is a validation-corpus requirement and a live-deployment selection criterion — it does not appear as an explicit filter gate in `filters.py`

**Gap is real but bounded:** The engine works for general market selection; only new-market-specific logic is missing.

---

### Requirement 7: VPS/RPC/secrets operational readiness

**Status: MISSING**

**Evidence:**
- `.env.example` — present; contains placeholder slots for `PK`, `CLOB_API_KEY`, `CLOB_API_SECRET`, `CLOB_API_PASSPHRASE`, Polygon RPC URL, ClickHouse credentials
- `packages/polymarket/simtrader/execution/wallet.py` — reads `PK` and CLOB creds from environment; `build_client()` points to `https://clob.polymarket.com`, `chain_id=137`
- No VPS provisioning scripts, no Ansible/Terraform config, no SSH deployment runbook in repo
- No Polygon RPC endpoint configuration file or validation script in repo
- No secrets rotation policy or vault integration

**Gap:** The `.env.example` template defines what's needed, but there is no evidence that:
- A VPS exists or has the repo deployed
- A Polygon RPC endpoint is configured and tested
- Real CLOB credentials have been derived and loaded
- Operational readiness has been verified end-to-end

The code supports it; the operator setup is unverified and undocumented.

---

### Requirement 8: Grafana live-bot panels

**Status: MISSING**

**Evidence:**
- `infra/grafana/dashboards/` — 7 dashboard JSON files:
  - `polyttool_infra_smoke.json`
  - `polyttool_pnl.json`
  - `polyttool_user_trades.json`
  - `polyttool_strategy_detectors.json`
  - `polyttool_arb_feasibility.json`
  - `polyttool_liquidity_snapshots.json`
  - `polyttool_user_overview.json`
- Grep of all 7 dashboard files for "kill_switch", "live_bot", "submitted", "risk_manager": zero matches
- None of the 7 dashboards contain panels for live bot operations

**Missing panels:**
- Order submission rate vs. dry-run WOULD-PLACE rate
- Kill-switch state (armed / clear)
- RiskManager daily loss progression vs. cap
- Inventory skew vs. limit
- Order manager actions per minute (places, cancels, skipped)
- Rate limiter token level
- Live session timeline (start/stop events)

**There is also no ClickHouse schema for live bot telemetry** — so even if panels were added, there would be no data source.

---

### Requirement 9: Discord alerting

**Status: MISSING**

**Evidence:**
- Grep across all `.py` files in repo for "discord": 0 matches
- Grep across all `.py` files in repo for "webhook": 0 matches
- `.env.example`: no `DISCORD_WEBHOOK_URL` or equivalent
- `docker-compose.yml`: no Discord-related environment variable
- `services/api/main.py` (first 80 lines): no Discord import

**Gap:** Discord alerting is entirely absent. No webhook, no notification module, no integration point in the execution layer, gates, or FastAPI service.

**Required integration points (from SPEC-0012 §6):**
- Gate pass/fail
- Live session start/stop
- Kill-switch trip
- Daily loss cap exceeded
- Runtime errors

---

### Requirement 10: Stage 0 — 72-hour paper-live readiness

**Status: BLOCKED**

**Evidence:**
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` — Stage 0 procedure documented (72h dry-run soak)
- `tools/cli/simtrader.py` — `simtrader live` supports dry-run default (confirmed by Gate 4 pass)
- `artifacts/gates/dry_run_gate/gate_passed.json` — Gate 4 PASSED
- `artifacts/gates/sweep_gate/gate_failed.json` — Gate 2 FAILED
- `gate_status.py` — exits non-zero when any gate is not passed

**Blocker:** SPEC-0012 §8 and `docs/ROADMAP.md` (Validation Pipeline) require all four gates to have `gate_passed.json` before Stage 0 can start. Gate 2 is failed; Gate 3 has no artifact. `python tools/gates/gate_status.py` currently exits non-zero, blocking Stage 0.

**Gap:** Readiness is 2/4 gates. Stage 0 cannot start until Gates 2 and 3 pass.

---

### Requirement 11: Stage 1 — $500 live deployment readiness

**Status: BLOCKED**

**Evidence:**
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` — runbook exists with prerequisites documented
- `tools/cli/simtrader.py` — `--live` flag implemented with gate checks and `CONFIRM` prompt
- `packages/polymarket/simtrader/execution/live_executor.py` — live order submission implemented
- `packages/polymarket/simtrader/execution/risk_manager.py` — Stage-0 conservative caps in place (`max_order_notional_usd = 25`, `max_position_notional_usd = 100`, `daily_loss_cap_usd = 15`)

**Blockers:**
1. Stage 0 not started (blocked by Gates 2 and 3)
2. Risk caps set to Stage-0 values — Stage 1 caps (`max_position_usd=500`, `daily_loss_cap_usd=100`) are CLI flags but default RiskManager is Stage-0 conservative
3. No VPS operational (Req 7)
4. No Discord alerting (Req 9)
5. No live-bot Grafana monitoring (Req 8)
6. No evidence of real CLOB credentials tested against live API

**Gap:** Stage 1 is the terminal gate. All upstream gaps propagate here.

---

## 4. Per-Item Status Summary

| # | Requirement | Status | Blocking on |
|---|-------------|--------|-------------|
| 1 | 15+ diverse tapes (politics/sports/new) | **PARTIAL → MISSING** | No politics tapes; no confirmed-eligible tapes |
| 2 | Gate 2 sweep ≥70% profitable | **BLOCKED** | Eligible tape with depth |
| 3 | Gate 3 shadow on 3–5 markets | **MISSING** | Gates 2 (promotion ladder) + operator action |
| 4 | Thin FastAPI automation wrapper | **PARTIAL** | Live-bot health/control endpoints not built |
| 5 | Local n8n setup | **MISSING** | Not started |
| 6 | Market selection with new-market logic | **PARTIAL** | New-market-specific logic absent |
| 7 | VPS/RPC/secrets operational readiness | **MISSING** | Undocumented, unverified |
| 8 | Grafana live-bot panels | **MISSING** | No schema, no panels |
| 9 | Discord alerting | **MISSING** | Not started |
| 10 | Stage 0 72h paper-live readiness | **BLOCKED** | Gates 2 and 3 |
| 11 | Stage 1 $500 live deployment | **BLOCKED** | All of the above |

---

## 5. Risk Ranking

Ranked by: (dependency criticality × revenue impact). Items that block other items rank higher.

| Rank | Item | Why it ranks here |
|------|------|--------------------|
| 🔴 1 | **Gate 2 eligible tape** | Primary blocker. Every stage gate and capital stage depends on it. Without a tape with `executable_ticks > 0`, the sweep gate cannot pass, Gate 3 cannot start, Stage 0 cannot start, Stage 1 is impossible. |
| 🔴 2 | **Gate 3 shadow sign-off** | Second cascading blocker after Gate 2. Requires live market sessions and manual operator verification. Cannot start until Gate 2 passes. 3–5 markets required; 0 done. |
| 🟠 3 | **Diverse tape corpus (15+ markets)** | Gate 2 and Gate 3 both require evidence across multiple market regimes (SPEC-0012 §4). A single tape (even eligible) is insufficient for the mixed-regime corpus requirement. |
| 🟠 4 | **VPS/RPC/secrets readiness** | Unblocks Stage 0 and Stage 1. Without a stable environment, paper-live cannot run 72 hours without interruption. Missing completely. |
| 🟡 5 | **Discord alerting** | Required before Stage 0 per SPEC-0012 §8 prerequisites. Low build cost; high operational safety value. Missing completely. |
| 🟡 6 | **Grafana live-bot panels** | Required for Stage 0 and Stage 1 monitoring. Depends on ClickHouse live-bot schema (also missing). Medium build cost. |
| 🟡 7 | **FastAPI live-bot endpoints** | Required for n8n automation and health monitoring. Medium build cost. Enhances operator visibility but doesn't directly block a gate. |
| 🟢 8 | **n8n automation** | Nice-to-have for operations. Can be deferred past Stage 0 without blocking capital deployment. Missing entirely, but low immediate risk. |
| 🟢 9 | **New-market scorer logic** | Market selection engine works for standard markets. New-market logic adds precision but is not a hard gate requirement. |

---

## 6. Recommended Implementation Order (Next 5–8 Packets)

Ordered by dependency chain. Each packet is a self-contained unit of work.

---

### Packet 1: Eligible Tape Acquisition ← START HERE

**Goal:** Capture at least one tape with `executable_ticks > 0` for a liquid binary market.

**Steps:**
1. Run `python -m polytool scan-gate2-candidates --all --top 20` to rank live markets by depth
2. For top candidates: `python -m polytool watch-arb-candidates --markets <slug1,slug2,...> --duration 1800 --poll-interval 30`
3. If dislocation detected: auto-recorded tape lands in `artifacts/simtrader/tapes/`
4. Run `python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --all` to check eligibility
5. If eligible: proceed to Packet 2

**Success criterion:** At least one tape with `executable_ticks > 0` and `max_size >= sane_preset_min`

**Files involved:** `tools/cli/scan_gate2_candidates.py`, `tools/cli/watch_arb_candidates.py`

**Blocks Packets 2, 3, 4, 5+**

---

### Packet 2: Gate 2 Close

**Goal:** Run scenario sweep on eligible tape; write `gate_passed.json`.

**Prerequisite:** Packet 1 complete.

**Steps:**
1. `python tools/gates/close_sweep_gate.py` (auto-selects most recent eligible tape)
2. Verify `artifacts/gates/sweep_gate/gate_passed.json` written with `profitable_fraction >= 0.70`
3. Run `python tools/gates/gate_status.py` — should show Gate 2 PASSED

**Files involved:** `tools/gates/close_sweep_gate.py`, `artifacts/gates/sweep_gate/`

**Blocks Packets 3, 4, 5+**

---

### Packet 3: Gate 3 Shadow Sign-off (3–5 markets, mixed regimes)

**Goal:** Shadow-validate `market_maker_v0` on 3–5 live markets covering politics, sports, and a new market; create `gate_passed.json`.

**Prerequisite:** Gate 2 passed.

**Steps:**
1. Select 3–5 markets: at least 1 politics, 1 sports, 1 new (< 48h old)
2. For each: `python -m polytool simtrader shadow --market <slug> --strategy market_maker_v0 --duration 300`
3. Verify for each: `run_manifest["mode"] == "shadow"`, `events_received > 0`, `fills_count == 0`
4. Follow `tools/gates/shadow_gate_checklist.md`
5. Operator writes `artifacts/gates/shadow_gate/gate_passed.json` manually

**Files involved:** `tools/gates/shadow_gate_checklist.md`, `packages/polymarket/simtrader/shadow/runner.py`

**Blocks Packets 4, 5+**

---

### Packet 4: Discord Alerting

**Goal:** Wire Discord webhook into gate events and live session lifecycle.

**Prerequisite:** None (can build in parallel with Packets 1–3).

**Steps:**
1. Add `DISCORD_WEBHOOK_URL` to `.env.example`
2. Create `packages/polymarket/notifications/discord.py` — simple `post_message(text)` using `requests.post()`
3. Add alert calls to:
   - `tools/gates/close_*.py` — gate pass/fail
   - `packages/polymarket/simtrader/execution/live_runner.py` — session start/stop
   - `packages/polymarket/simtrader/execution/kill_switch.py` — trip event
   - `packages/polymarket/simtrader/execution/risk_manager.py` — halt trigger
4. Verify: `python -m polytool simtrader live --strategy market_maker_v0` sends a start alert; kill-switch trip sends a halt alert

**Success criterion:** SPEC-0012 §8 Stage 0 prerequisites include "Discord alerts wired and confirmed active."

---

### Packet 5: VPS/RPC/Secrets Operational Readiness

**Goal:** Verify end-to-end environment on the deployment machine before Stage 0.

**Prerequisite:** None (can start before Stage 0 but must complete before it).

**Steps:**
1. Provision VPS (document provider, region, specs)
2. Deploy repo to VPS at intended release commit
3. Configure `.env` with real credentials: `PK`, `CLOB_API_KEY`, `CLOB_API_SECRET`, `CLOB_API_PASSPHRASE`, Polygon RPC URL
4. Run `python -m polytool simtrader live --strategy market_maker_v0 --asset-id <TOKEN_ID>` (dry-run) on VPS — verify no auth errors
5. Run `python tools/gates/gate_status.py` on VPS — confirm all 4 artifacts present
6. Write ops readiness doc at `artifacts/gates/stage0/vps_readiness.md`

**Success criterion:** VPS runs dry-run live session without auth errors or WS failures for 30+ minutes.

---

### Packet 6: Grafana Live-Bot Panels

**Goal:** Operational visibility into live session health.

**Prerequisite:** Packet 5 complete (need confirmed ClickHouse connection on VPS).

**Steps:**
1. Add ClickHouse schema for live bot ops: `infra/clickhouse/initdb/10_live_bot_schema.sql`
   - Tables: `live_orders`, `live_fills`, `live_risk_violations`, `live_kill_switch_events`, `live_session_events`
2. Add telemetry emission from `live_runner.py` (write to ClickHouse after each tick)
3. Create `infra/grafana/dashboards/polyttool_live_bot.json` with panels:
   - Order submission rate vs. cap
   - Kill-switch state (armed/clear)
   - Daily loss vs. cap
   - Inventory skew vs. limit
   - Order manager actions per minute

**Success criterion:** After a dry-run session, Grafana shows populated panels.

---

### Packet 7: Stage 0 — 72-Hour Paper-Live

**Goal:** Continuous 72h dry-run soak; operator sign-off.

**Prerequisites:** Packets 1–6 complete (all four gates passed, Discord wired, VPS ready, Grafana panels active).

**Steps:**
1. Verify `python tools/gates/gate_status.py` exits 0
2. Run on VPS: `python -m polytool simtrader live --strategy market_maker_v0 --asset-id <TOKEN_ID>` (no `--live` flag)
3. Monitor Discord alerts for 72 hours
4. Review Grafana daily: loss cap, inventory skew, order rate
5. Review `ledger.jsonl` and `equity_curve.jsonl` at hour 24, 48, 72
6. If clean: operator writes `artifacts/gates/stage0/stage0_passed.json` with sign-off

**Success criterion:** 72 continuous hours, no unhandled exceptions, no kill-switch bug trips, simulated PnL not consistently negative.

---

### Packet 8: Stage 1 — $500 Live Deployment

**Goal:** Enable `--live` with real capital under Stage 1 risk caps.

**Prerequisite:** Packet 7 complete (Stage 0 signed off).

**Steps:**
1. Confirm wallet funded with ≥ $500 USDC
2. Confirm Discord alerts still active
3. Run: `python -m polytool simtrader live --live --strategy market_maker_v0 --asset-id <TOKEN_ID> --max-position-usd 500 --daily-loss-cap-usd 100 --max-order-usd 200 --inventory-skew-limit-usd 400`
4. Enter `CONFIRM` at banner
5. Monitor via Grafana + Discord; daily review per `LIVE_DEPLOYMENT_STAGE1.md`

---

## 7. Explicit "Do Not Build Yet" Items

The following are in-scope eventually but must not be started before their trigger conditions are met:

| Item | Trigger condition | Rationale |
|------|-----------------|-----------|
| **Opportunity Radar** (automated dislocation monitor) | First clean Gate 2 → Gate 3 progression | Building before Gate 2 adds infrastructure without unblocking anything; documented as DEFERRED in `docs/ROADMAP.md` |
| **n8n automation workflows** | Stage 0 complete and Discord confirmed working | n8n is valuable for automation but Stage 0 proves the manual path first; automating an unvalidated path adds noise |
| **Multi-market concurrent quoting** | Stage 1 review cycle complete | One market at a time per SPEC-0012 §5. Parallelism is Phase 2+. |
| **Stage 2+ capital caps** | Clean Stage 1 review covering PnL, fill quality, inventory | Cap increases require documented evidence from prior stage; SPEC-0012 §8 |
| **Backtesting** | Hypothesis validation loop shipped; historical orderbook data available | `docs/PLAN_OF_RECORD.md` §11; deferred indefinitely until kill conditions are met |
| **Multi-tenant / cloud deployment** | Explicitly out of scope for current roadmap | `docs/PLAN_OF_RECORD.md` §1 constraints |
| **Market orders** | Explicitly prohibited — no trigger condition | Hard constraint in SPEC-0011 §4 and SPEC-0012 §2 |

---

## 8. Open Questions That Require Repo Investigation

These cannot be answered from the current audit without additional inspection or live environment access:

1. **What markets are currently eligible for Gate 2?**
   Running `python -m polytool scan-gate2-candidates --all --top 20` against the live API is required. No cached result exists in the repo.

2. **Is the shadow runner's WS disconnect/reconnect path tested on the actual VPS network conditions?**
   `packages/polymarket/simtrader/shadow/runner.py` has reconnect logic. Whether it handles VPS-specific firewall or NAT timeout behavior is unknown without a live session on the deployment host.

3. **Do the three NHL tapes (`toronto`, `vancouver`, `calgary`) have sufficient depth for Gate 2?**
   These tapes were recorded 2026-03-07 and have not been scanned for eligibility. Running `scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes` would answer this.

4. **What are the actual CLOB API rate limits and do they match `TokenBucketRateLimiter(max_per_minute=30)`?**
   The rate limiter default is 30 orders/minute. The live Polymarket CLOB rate limit is not documented in the repo. A rate mismatch could cause silent throttling or order rejections in Stage 1.

5. **Does `services/api/main.py` have a health endpoint suitable for n8n polling?**
   The full 110KB file was not read in this audit. There may be a `/health` or `/status` endpoint already. Confirming this changes the build scope for Packet 4 (FastAPI live-bot endpoints).

6. **What commit are the three newest NHL tapes from, and do they span a complete market lifecycle?**
   The 2026-03-07 tapes have partial slugs (`toronto-map`, `vancouver-c`, `calgary-fla`). Full market IDs and event durations are unknown without reading `meta.json` inside each tape directory.

---

## References

- `docs/specs/SPEC-0011-live-execution-layer.md` — gate model and interfaces
- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` — canonical Phase 1 program
- `docs/ROADMAP.md` — gate evidence table and kill conditions
- `docs/CURRENT_STATE.md` — current gate status (2026-03-07)
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` — Stage 1 runbook
- `artifacts/gates/sweep_gate/gate_failed.json` — Gate 2 failure details
- `artifacts/gates/replay_gate/gate_passed.json` — Gate 1 pass details
- `artifacts/gates/dry_run_gate/gate_passed.json` — Gate 4 pass details
- `tools/gates/shadow_gate_checklist.md` — Gate 3 manual procedure
