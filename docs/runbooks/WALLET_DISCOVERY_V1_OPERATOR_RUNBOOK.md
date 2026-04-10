# Wallet Discovery v1 Operator Runbook

**Scope:** Loop A leaderboard discovery, quick scan with MVF fingerprint, human review gate.
**Last verified:** 2026-04-10

---

## 0. Purpose

Wallet Discovery v1 automates the process of finding high-performing Polymarket wallets
from the public leaderboard, fingerprinting them with a deterministic multi-variate vector
(MVF), and routing them through a human review gate before any operational tracking begins.

The end-to-end v1 path: **Loop A fetch → churn detection → scan queue → quick scan with
MVF → human review → promoted state.** No LLM calls occur at any step. No wallet reaches
`promoted` state without operator approval.

This runbook covers the four shipped v1 capabilities: Loop A, ClickHouse tables, `--quick`
scan, and MVF. For what is NOT in v1, see Section 6.

---

## What Is Shipped

Wallet Discovery v1 ships four integrated capabilities:

1. **Loop A leaderboard discovery** — 24h-scheduled fetch of the Polymarket public
   leaderboard, churn detection (new wallets, rank movement, reappearance), and
   automatic scan queue population.
2. **ClickHouse table contracts** — three tables with enforced schemas:
   `watchlist` (ReplacingMergeTree, lifecycle state machine),
   `leaderboard_snapshots` (MergeTree append-only, raw payload preservation),
   `scan_queue` (ReplacingMergeTree, dedup + lease semantics).
3. **`python -m polytool scan <address> --quick`** — unified scan with a hard
   no-LLM guarantee: zero cloud API calls at any stage. Produces MVF fingerprint
   + existing detectors + PnL in a single dossier.
4. **MVF (Multi-Variate Fingerprint)** — 11-dimensional deterministic vector
   computed from trade history using Python math only (no external dependencies).

**Test coverage**: 118 discovery-area tests (54 Loop A + 37 MVF + 15 scan-quick +
12 integrated acceptance), 3908 full suite.

**What is explicitly NOT in v1**: see Section 6.

---

## 1. Prerequisites

Run these checks before any discovery operation.

**1. Docker running:**
```bash
docker compose ps
```
All services should show `Up` or `running`.

**2. ClickHouse accessible:**
```bash
curl "http://localhost:8123/?query=SELECT%201"
```
Should return `1`.

**3. `CLICKHOUSE_PASSWORD` env var set:**
```bash
echo $CLICKHOUSE_PASSWORD
```
Must be non-empty. Set from `.env` if needed:
```bash
export CLICKHOUSE_PASSWORD=$(grep CLICKHOUSE_PASSWORD .env | cut -d= -f2)
```

**4. CLI loads:**
```bash
python -m polytool --help
```
Should print the help text with no import errors.

**5. The 3 discovery tables exist:**
```bash
curl "http://localhost:8123/" --data \
  "SELECT name FROM system.tables WHERE database='polytool' AND name IN ('watchlist','leaderboard_snapshots','scan_queue')"
```
Expected output: three lines — `leaderboard_snapshots`, `scan_queue`, `watchlist`.

If the query returns fewer than 3 names, the DDL has not been applied. Fix:
```bash
# Option A: restart ClickHouse (applies initdb scripts on startup)
docker compose restart clickhouse

# Option B: apply the DDL manually
cat infra/clickhouse/initdb/27_wallet_discovery.sql | \
  curl "http://localhost:8123/" --data-binary @-
```

---

## 2. Loop A: Leaderboard Discovery

Loop A fetches the Polymarket leaderboard, detects wallet churn (new, rising, dropped),
and populates the `scan_queue` with newly discovered wallets.

**Step 1 — Dry run (safe, no ClickHouse writes):**
```bash
python -m polytool discovery run-loop-a --dry-run
```

Expected output:
```
Loop A: order_by=PNL time_period=DAY category=OVERALL max_pages=5 dry_run=True

--- Loop A Result ---
  fetch_run_id  : <uuid>
  snapshot_ts   : 2026-04-10T17:24:21.599873+00:00
  rows_fetched  : 250
  new_wallets   : 0
  dropped_wallets: 0
  rising_wallets : 0
  rows_enqueued : 0
  dry_run       : True

  (dry-run: no ClickHouse writes performed)
```

Verify `rows_fetched > 0` before running live. If `rows_fetched = 0`, see Troubleshooting.

**Step 2 — Live run (writes to ClickHouse):**
```bash
python -m polytool discovery run-loop-a
```

`CLICKHOUSE_PASSWORD` must be set. The live run inserts rows into `leaderboard_snapshots`
and `scan_queue`, and updates `watchlist` for newly discovered wallets.

**Customization flags:**

| Flag | Default | Options | Purpose |
|------|---------|---------|---------|
| `--order-by` | `PNL` | `PNL`, `VOL` | Leaderboard sort field |
| `--time-period` | `DAY` | `DAY`, `WEEK`, `MONTH`, `ALL` | Time window |
| `--category` | `OVERALL` | `OVERALL`, `POLITICS`, `SPORTS`, `CRYPTO` | Market category |
| `--max-pages` | `5` | any int | Max pages to fetch (50 entries/page) |

Example — fetch weekly crypto leaders by volume:
```bash
python -m polytool discovery run-loop-a \
  --order-by VOL --time-period WEEK --category CRYPTO
```

**Verify rows landed in ClickHouse:**
```bash
# How many leaderboard snapshot rows total
curl "http://localhost:8123/" --data \
  "SELECT count() FROM polytool.leaderboard_snapshots"

# How many wallets pending scan
curl "http://localhost:8123/" --data \
  "SELECT count() FROM polytool.scan_queue WHERE queue_state='pending'"
```

---

## 3. Quick Scan with MVF

Once wallets are in the `scan_queue`, scan them individually using `--quick`. This flag
produces MVF fingerprint + existing detectors + PnL data with zero cloud LLM calls.
The no-LLM guarantee is absolute — it is not a configuration option.

**Command:**
```bash
python -m polytool scan <WALLET_ADDRESS> --quick
```

Replace `<WALLET_ADDRESS>` with a real 0x-prefixed Polymarket wallet address. Example:
```bash
python -m polytool scan 0x1234567890abcdef1234567890abcdef12345678 --quick
```

**What `--quick` does vs normal scan:**
- `--quick` = lite pipeline stages (positions + PnL + resolutions + CLV) plus MVF
  fingerprint written to `dossier.json`. Zero cloud LLM endpoint calls under any
  condition.
- Without `--quick`: existing scan behavior unchanged (may invoke LLM stages
  depending on config and flags).

**Expected artifacts:**

The scan writes a `dossier.json` to the artifact output directory. When `--quick` is
used, the dossier contains an `"mvf"` block.

**Confirm MVF was appended:**
```bash
python -c "
import json, pathlib, sys
d = json.loads(pathlib.Path(sys.argv[1]).read_text())
print(json.dumps(d.get('mvf', {}), indent=2))
" path/to/dossier.json
```

Or open `dossier.json` directly and search for the `"mvf"` key.

**The 11 MVF dimensions (what to expect):**

| Dimension | Type | Description |
|-----------|------|-------------|
| `win_rate` | float | Fraction of resolved positions that are WIN or PROFIT_EXIT |
| `avg_hold_duration_hours` | float | Mean position hold time in hours |
| `median_entry_price` | float | Median entry price across all positions |
| `market_concentration` | float | Herfindahl index over market slugs (1=one market, 0=diversified) |
| `category_entropy` | float | Shannon entropy of trades across Polymarket categories |
| `avg_position_size_usdc` | float | Mean notional size per position in USDC |
| `trade_frequency_per_day` | float | Total trades divided by observation window in days |
| `late_entry_rate` | float or null | Fraction of positions entered in final 20% of market life |
| `dca_score` | float | Fraction of markets where more than one entry was made |
| `resolution_coverage_rate` | float | Fraction of positions with non-UNKNOWN resolution |
| `maker_taker_ratio` | float or null | Fraction of trades that are maker-side |

**Notes on null dimensions:**
- `late_entry_rate` will be `null` in v1. This is a known gap (Gap E): market
  `open_ts` / `close_timestamp` are not in the current dossier export schema. Expected
  behavior, not a bug.
- `maker_taker_ratio` will be `null` if maker/taker data is unavailable for the wallet.

---

## No-LLM Guarantee

`scan --quick` makes **zero HTTP calls** to any cloud LLM endpoint (Gemini, DeepSeek,
OpenAI, Anthropic, or any other).

- This is an absolute guarantee enforced by test AT-06 (request-intercepting fixtures,
  not inspection of config values).
- Without `--quick`, the existing scan behavior is unchanged and may use LLM stages
  if the user's config enables them.
- The no-LLM guarantee applies only to the `--quick` path.

---

## 4. Human Review Gate

**v1 lifecycle path:**
```
discovered -> queued -> scanned -> reviewed -> promoted
```

**Critical rule:** `scanned -> promoted` is an **invalid transition** and is rejected
by application-level validation. The correct path is `scanned -> reviewed -> promoted`,
where `reviewed -> promoted` requires `review_status = 'approved'` set by a human
operator.

**v1 has no auto-promotion.** There is no code path that bypasses this gate.

**What to review in the scan output:**

| Signal | What to look for |
|--------|-----------------|
| `win_rate` | Above 0.55 is worth attention; above 0.70 is strong |
| `avg_hold_duration_hours` | Short (< 6h) may indicate informed trading; very long may be passive |
| `dca_score` | High score (> 0.4) suggests deliberate position building |
| `trade_frequency_per_day` | Context-dependent; very high may indicate noise |
| `market_concentration` | Near 1.0 = single-market specialist; near 0 = diversified |
| PnL data | Net profit after fees; compare gross vs net |
| Detector outputs | Holding style, DCA laddering, market-selection bias |

**Current v1 limitation:** There is no CLI command for lifecycle state transitions.
The operator reviews dossier.json output and records decisions manually. State
transitions are enforced by application-level validation in the discovery package.

---

## 5. ClickHouse Tables Reference

| Table | Engine | Purpose | Quick Query |
|-------|--------|---------|-------------|
| `watchlist` | ReplacingMergeTree | Wallet lifecycle state (one row per wallet) | `SELECT * FROM polytool.watchlist LIMIT 5` |
| `leaderboard_snapshots` | MergeTree | Append-only raw leaderboard facts per fetch run | `SELECT count() FROM polytool.leaderboard_snapshots` |
| `scan_queue` | ReplacingMergeTree | Discovery work queue with lease/expiry semantics | `SELECT * FROM polytool.scan_queue WHERE queue_state='pending' LIMIT 5` |

**Inspect pending queue items:**
```bash
curl "http://localhost:8123/" --data \
  "SELECT wallet_address, queue_state, priority, created_at FROM polytool.scan_queue WHERE queue_state='pending' LIMIT 10 FORMAT Pretty"
```

**Inspect watchlist lifecycle states:**
```bash
curl "http://localhost:8123/" --data \
  "SELECT wallet_address, lifecycle_state, review_status, updated_at FROM polytool.watchlist LIMIT 10 FORMAT Pretty"
```

**Full DDL reference:** `infra/clickhouse/initdb/27_wallet_discovery.sql`

---

## 6. What Is Explicitly Not Shipped

The following are explicitly out of scope for v1:

- **Loop B** — live wallet monitoring via Alchemy WebSocket
- **Loop C** — deep analysis and cloud LLM hypothesis generation for wallets
- **Loop D** — platform-wide anomaly detection via CLOB WebSocket
- **Insider scoring** — binomial test and pre-event trading score (requires per-bucket
  calibration; current statistical model identified as incorrect in architect review 2026-04-09)
- **Exemplar selection** — trade annotation for LLM context window
- **Cloud LLM calls for wallet analysis** — policy not yet authorized beyond RIS
- **Auto-promotion to watchlist** — requires human review gate removal justification and
  operator sign-off (not yet defined)
- **n8n workflow integration for discovery** — broad n8n orchestration is Phase 3 target
- **Docker service definitions for Loop B / Loop D**
- **Copy-trading system**
- **SimTrader closed-loop testing of discovery hypotheses**

For the named prerequisite (blocker) for each deferred capability, see
`docs/specs/SPEC-wallet-discovery-v1.md` section "Blockers for Phases Beyond v1".

---

## Known Non-Blocking Issues

These are pre-existing issues that do **not** affect Wallet Discovery v1 functionality:

| Issue | Scope | Impact |
|-------|-------|--------|
| `test_ris_phase2_cloud_provider_routing.py` — 8 tests fail with `AttributeError` on `_post_json` | RIS Phase 2 cloud provider routing feature | Zero impact on discovery. These tests were failing before v1 was implemented. Owned by RIS Phase 2. |
| `late_entry_rate` MVF dimension returns `null` | Gap E in spec (market `open_ts` / `close_timestamp` absent from dossier export) | Expected behavior per spec. Not a bug. Will be addressed in a future packet. |

---

## Go/No-Go Checklist

Run through this checklist before using Wallet Discovery v1 in a research workflow:

```
[ ] ClickHouse responding:
    curl "http://localhost:8123/?query=SELECT%201"   # must return "1"

[ ] All 3 DDL tables exist:
    curl "http://localhost:8123/" --data \
      "SELECT name FROM system.tables WHERE database='polytool' AND name IN ('watchlist','leaderboard_snapshots','scan_queue')"
    # must return 3 lines

[ ] CLICKHOUSE_PASSWORD env var set:
    echo $CLICKHOUSE_PASSWORD   # must be non-empty

[ ] CLI loads without errors:
    python -m polytool --help   # must show discovery and scan commands

[ ] Discovery area tests pass:
    python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py \
      tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py \
      -v --tb=short
    # expected: 118 passing, 0 failed

[ ] Operator understands: no auto-promotion — human review gate is mandatory
    before any wallet reaches promoted/watched state.

[ ] Operator understands: scan --quick has no LLM calls;
    scan without --quick is unchanged and may call LLM stages.
```

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Error: CLICKHOUSE_PASSWORD is required` | Env var not set | `export CLICKHOUSE_PASSWORD=$(grep CLICKHOUSE_PASSWORD .env \| cut -d= -f2)` |
| Discovery tables not found (prereq query returns < 3 rows) | DDL not applied | `docker compose restart clickhouse` or run `infra/clickhouse/initdb/27_wallet_discovery.sql` manually |
| Loop A returns `rows_fetched: 0` | Polymarket API unreachable or rate-limited | Check internet connectivity; retry after 60s |
| `scan_queue` shows 0 pending after Loop A | No new wallets vs. previous snapshot (all seen before) | Normal — leaderboard is stable. Try `--time-period WEEK` or `--category CRYPTO` for different coverage |
| `--quick` scan produces no `mvf` block in dossier.json | Wallet has 0 resolved positions | MVF requires at least 1 position with trade data |
| `late_entry_rate` is null in MVF output | Gap E: market timestamps not in dossier export schema | Expected in v1 — not a bug; will be addressed in a future packet |
| `maker_taker_ratio` is null in MVF output | Maker/taker data unavailable for wallet | Expected — null is a valid v1 output for this dimension |
| `ImportError: discovery` or `ImportError: mvf` | Package path issue | Run from project root; verify `python -m polytool --help` works first |
| Loop A dry-run succeeds but live run fails | Password not set or CH unreachable | Confirm `echo $CLICKHOUSE_PASSWORD` is non-empty; check `docker compose ps` |

---

## 8. Related Docs

| Doc | Purpose |
|-----|---------|
| `docs/specs/SPEC-wallet-discovery-v1.md` | Frozen v1 contract: table DDL, lifecycle state machine, acceptance tests, blockers |
| `docs/features/wallet-discovery-v1.md` | Feature doc with implementation status and packet history |
| `infra/clickhouse/initdb/27_wallet_discovery.sql` | ClickHouse DDL for the 3 discovery tables |
| `docs/dev_logs/2026-04-10_wallet_discovery_v1_integration.md` | Integration dev log (Packet A + B + hardening) |
| `docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md` | Dev log for this runbook |
