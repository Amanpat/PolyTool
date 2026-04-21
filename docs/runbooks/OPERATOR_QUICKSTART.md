# Operator Quickstart — End-to-End Guide

A practical, opinionated guide to using PolyTool from first run to live trading.
All commands use `python -m polytool <command>` (or the `polytool` console script).

---

## What PolyTool Is

PolyTool is a local-first research + trading infrastructure for Polymarket:

| Component | What it does |
|-----------|-------------|
| **Research loop (Track B)** | Batch-scan profitable wallets → distill edge patterns → build hypothesis registry |
| **Analysis & evidence** | Scan individual users, compute PnL/CLV, produce dossiers and LLM bundles |
| **Local RAG** | Index your private KB + artifacts so you can query them instantly |
| **Market scanner** | Score and rank active markets before any trade decision |
| **SimTrader (Track A)** | Record tapes, run sweeps, shadow mode, dry-run live — all gated before real capital |
| **SimTrader Studio** | Browser UI for sessions, tapes, reports, and OnDemand replay |
| **Grafana** | Analytics dashboards for trades, PnL, strategy signals, arb feasibility |

Everything runs locally. No external LLM API calls. Private data stays under
`artifacts/` and `kb/` — both gitignored.

---

## 1. Start Services

```bash
docker compose up -d
docker compose ps   # Both services should show "Up"
```

- **Grafana**: http://localhost:3000 (login: admin / admin)
- **ClickHouse**: http://localhost:8123

---

## 2. Research Loop (Track B)

This is the primary workflow. Run it first. It produces the signal that feeds
everything else.

### Step 1 — Batch wallet scan

Create `wallets.txt` with Polymarket handles or wallet addresses, one per line:
```
@TopTrader1
@AnotherOne
0xabc123...
```

```bash
python -m polytool wallet-scan --input wallets.txt --profile lite
```

Output: `artifacts/research/wallet_scan/<YYYY-MM-DD>/<run_id>/`
- `leaderboard.md` — ranked table of top performers
- `leaderboard.json` — machine-readable rank
- `per_user_results.jsonl` — full per-wallet detail

### Step 2 — Distill edge patterns

```bash
python -m polytool alpha-distill \
  --wallet-scan-run artifacts/research/wallet_scan/YYYY-MM-DD/<run_id>
```

Output: `alpha_candidates.json` in the same run directory.
Candidates are ranked by cross-wallet persistence — the strongest signal of
real edge, not just one lucky wallet.

### Step 3 — Register a hypothesis

```bash
python -m polytool hypothesis-register \
  --candidate-file artifacts/research/wallet_scan/YYYY-MM-DD/<run_id>/alpha_candidates.json \
  --rank 1 \
  --registry artifacts/research/hypothesis_registry/registry.jsonl
```

Prints a `hypothesis_id` (e.g. `hyp_a1b2c3d4`). This ID tracks the hypothesis
through its entire lifecycle: proposed → testing → validated / rejected / parked.

### Step 4 — Create an experiment

```bash
python -m polytool experiment-run \
  --id hyp_<your_id> \
  --registry artifacts/research/hypothesis_registry/registry.jsonl \
  --outdir artifacts/research/experiments/hyp_<your_id>
```

Creates a structured `experiment.json` skeleton for manual validation.

### Step 5 — Update hypothesis status

```bash
python -m polytool hypothesis-status \
  --id hyp_<your_id> \
  --status testing \
  --reason "starting manual replay validation" \
  --registry artifacts/research/hypothesis_registry/registry.jsonl
```

Statuses: `proposed | testing | validated | rejected | parked`

---

## 3. Single-User Examination

For a deep dive on one wallet:

```bash
python -m polytool scan --user "@DrPufferfish"
```

Open these first from the run root (`artifacts/dossiers/users/<slug>/.../`):
- `coverage_reconciliation_report.md` — data quality summary
- `segment_analysis.json` — breakdown by category/tier/market type
- `hypothesis_candidates.json` — ranked signal candidates for this user
- `audit_coverage_report.md` — offline trust sanity check

Then build an LLM bundle for evidence-grounded analysis:

```bash
python -m polytool llm-bundle --user "@DrPufferfish"
```

Output: `kb/users/<slug>/llm_bundles/<YYYY-MM-DD>/<run_id>/bundle.md`
Paste this into your LLM UI. After reviewing, save the report:

```bash
python -m polytool llm-save --user "@DrPufferfish" --model "local-llm" \
  --report-path path/to/report.md --prompt-path path/to/prompt.md
```

---

## 4. RAG — One Command

After any scan, wallet-scan, or llm-save, rebuild the RAG index so the new
content is immediately searchable:

```bash
python -m polytool rag-refresh
```

This is a thin alias for `rag-index --rebuild --roots kb,artifacts`. Run it
any time you've added new content to `kb/` or `artifacts/`.

Then query:

```bash
python -m polytool rag-query \
  --question "what strategies did top wallets use?" \
  --hybrid --rerank --k 8
```

Scope to a specific user:

```bash
python -m polytool rag-query --user "@DrPufferfish" \
  --question "most recent evidence" --hybrid --rerank --k 8
```

For full RAG details: `docs/runbooks/LOCAL_RAG_WORKFLOW.md`

---

## 5. Market Scanner

Before any SimTrader run, find which markets are worth trading:

```bash
python -m polytool market-scan --top 10
```

What to look for in top results:
- `mid_price` between 0.25 and 0.75 (not near resolution)
- `spread_score` > 1.5 (wide enough after fees)
- `age_hours` < 48 (new markets have best spreads)

Note the `token_id` and market `slug` for the commands below.

---

## 6. SimTrader — Validation Gates

Before real capital, the strategy must pass 4 gates. Check current status first:

```bash
python tools/gates/gate_status.py
```

### Gate 1 — Replay Determinism

```bash
python tools/gates/close_replay_gate.py
```

Records a short tape, replays it twice, confirms identical output.
**Status as of 2026-03-07: PASSED**

### Gate 2 — Scenario Sweep (≥70% profitable)

```bash
python tools/gates/close_sweep_gate.py
```

**Status as of 2026-03-07: NOT PASSED — tooling ready, needs eligible tape.**

Current operator path for Gate 2:
```bash
# Watch markets for a dislocation
python -m polytool watch-arb-candidates \
  --watchlist-file artifacts/watchlists/report_watchlist.json \
  --poll-interval 30 --duration 300

# Scan any new tapes
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --all

# If an eligible tape appears, run the gate
python tools/gates/close_sweep_gate.py
```

### Gate 3 — Shadow Mode (manual)

**Status: BLOCKED behind Gate 2.**
Follow `tools/gates/shadow_gate_checklist.md` after Gate 2 passes.

### Gate 4 — Dry-Run Live

**Status: PASSED** — artifact at `artifacts/gates/dry_run_gate/gate_passed.json`

---

## 7. SimTrader — Daily Dev Loop

Fast iteration workflow (2–5 min):

```bash
# 1. Pick a market
python -m polytool simtrader quickrun --dry-run --list-candidates 10

# 2. Shadow run (live simulated, no real orders)
python -m polytool simtrader shadow \
  --market <slug> --duration 180 \
  --strategy market_maker_v0 --strategy-preset loose

# 3. Replay the tape
python -m polytool simtrader run \
  --tape artifacts/simtrader/tapes/<tape_id>/events.jsonl \
  --strategy binary_complement_arb --strategy-preset loose

# 4. Open the HTML report
python -m polytool simtrader browse --open
```

For full SimTrader documentation: `docs/runbooks/README_SIMTRADER.md`

---

## 8. SimTrader Studio (Browser UI)

Launch the Studio:
```bash
pip install "polytool[studio]"
python -m polytool simtrader studio --open
# Opens http://localhost:8765
```

| Tab | Use it for |
|-----|-----------|
| **Dashboard** | Command launcher, recent sessions, Grafana deep links |
| **Sessions** | Live log view and simulation viewer for any session |
| **Cockpit** | Workspace grid — attach sessions, replays, or artifact views |
| **Tapes** | Browse recorded WS tapes |
| **Reports** | Browse and open HTML run/sweep/batch reports |
| **OnDemand** | Interactive tape replay — scrub, adjust config, restart |
| **Settings** | Export/import workspace layout JSON |

The Dashboard tab includes direct links to all Grafana dashboards.

---

## 9. Grafana Dashboards

Open http://localhost:3000 (admin / admin) after `docker compose up -d`.

| Dashboard | URL | Use it for |
|-----------|-----|-----------|
| User Trades | http://localhost:3000/d/polytool-user-trades | Trade history, fill analysis |
| PnL | http://localhost:3000/d/polytool-pnl | Realized/unrealized PnL, equity curve |
| Strategy Detectors | http://localhost:3000/d/polytool-strategy-detectors | HOLDING_STYLE, DCA, COMPLETE_SET_ARBISH |
| User Overview | http://localhost:3000/d/polytool-user-overview | High-level wallet summary |
| Arb Feasibility | http://localhost:3000/d/polytool-arb-feasibility | Complement arb edge + fees |
| Liquidity Snapshots | http://localhost:3000/d/polytool-liquidity-snapshots | Orderbook health over time |

**Integration decision**: Grafana and Studio serve different purposes.
Grafana shows analytics after data ingestion (run `scan` first). Studio manages
live and replay sessions. The practical integration is the Dashboard tab in
Studio, which has deep links to all key Grafana dashboards. No iframe embedding
is needed — both tools open in the browser and complement each other cleanly.

---

## 10. Stage 0 → Stage 1 (Live Capital)

Only after all 4 gates pass:

```bash
# Stage 0 — 72 hour paper-live (zero capital)
python -m polytool simtrader live \
  --strategy market_maker_v0 --asset-id <TOKEN_ID>
# Default is dry-run. Watch Grafana for 72h. Look for positive simulated PnL.

# Stage 1 — real capital ($500 USDC)
# Requires: .env with PK + CLOB credentials, VPS, Polygon RPC
python -m polytool simtrader live --live \
  --strategy market_maker_v0 --asset-id <TOKEN_ID> \
  --max-position-usd 500 --daily-loss-cap-usd 100 \
  --max-order-usd 200 --inventory-skew-limit-usd 400
```

Emergency stop:
```bash
python -m polytool simtrader kill
```

---

## Quick Command Reference

```bash
# Research
python -m polytool wallet-scan --input wallets.txt --profile lite
python -m polytool alpha-distill --wallet-scan-run <path>
python -m polytool hypothesis-register --candidate-file <path>/alpha_candidates.json --rank 1 --registry artifacts/research/hypothesis_registry/registry.jsonl

# Single user
python -m polytool scan --user "@handle"
python -m polytool llm-bundle --user "@handle"

# RAG (one command)
python -m polytool rag-refresh
python -m polytool rag-query --question "..." --hybrid --rerank

# Market selection
python -m polytool market-scan --top 10

# SimTrader
python -m polytool simtrader shadow --market <slug> --strategy market_maker_v0 --duration 300
python -m polytool simtrader browse --open

# Gates
python tools/gates/gate_status.py
```

---

## Key Constraints (always apply)

- **No market orders** — limit orders only.
- **Kill switch is always checked** — even in dry-run mode.
- **No live capital before gates** — `replay → sweeps → shadow → dry-run → Stage 0 → Stage 1`.
- **Research outputs are not signals** — validate through SimTrader gates.
- **No secrets in committed files** — use `.env` (gitignored).

---

## Reference Docs

| Topic | Document |
|-------|---------|
| Research loop details | `docs/CURRENT_STATE.md` |
| RAG workflow details | `docs/runbooks/LOCAL_RAG_WORKFLOW.md` |
| LLM bundle workflow | `docs/runbooks/LLM_BUNDLE_WORKFLOW.md` |
| SimTrader full guide | `docs/runbooks/README_SIMTRADER.md` |
| Live execution spec | `docs/specs/SPEC-0011-live-execution-layer.md` |
| Stage 1 runbook | `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` |
| Track 2 paper soak runbook | `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md` |
| Track 2 paper soak rubric | `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md` |
| Track 2 Grafana panel pack | `docs/features/FEATURE-crypto-pair-grafana-panels-v0.md` |
| Roadmap router | `docs/ROADMAP.md` (non-governing) |
| Architecture | `docs/ARCHITECTURE.md` |
