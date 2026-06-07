# Dossier Schema Recon — for per-dossier LLM analysis prompt design

**Date:** 2026-06-05
**Mode:** Read-only reconnaissance. No code/dossier/config modified. Denylist untouched.
**Goal:** Ground-truth the per-user dossier schema, the LLM-packet path, field population
reality, inventory, and token budget against the **current** codebase + the most recent
wallet-scan run, since WI-1/WI-2 schema work landed 2026-05-31.

**Reference run used throughout (full schema sample):**
`artifacts/dossiers/users/unknown/0xb7a63200d44c67c3bb44d8bda9f8e40b138189b2/2026-06-04/735ddc1d-b87e-444f-a273-47a4ecb97e69/`
(33 lifecycle rows, `--lite`, git_commit `a2ea5be`, schema `LLM Research Packet v1`).

> **Key caveat up front:** every dossier in the latest run was produced by
> `scan --user <wallet> --lite` (top-200 batch seed). `header.max_trades=200`,
> `window_days=30`. A non-`--lite` run may populate more (liquidity snapshots,
> category mapping). The schema is identical; population differs.

---

## 1. PER-USER DOSSIER CONTENTS

### 1a. Files in a per-user run dir

Inventory of the reference run dir (`<slug>/<wallet>/<date>/<run_id>/`):

| File | Bytes | LLM-relevant? | Purpose |
|---|---|---|---|
| `dossier.json` | 125,836 | **YES (primary)** | The "LLM Research Packet v1" — all structured signal |
| `segment_analysis.json` | 35,821 | **YES (pre-aggregated)** | Per-segment CLV/PnL stats (the routing-friendly view) |
| `hypothesis_candidates.json` | 10,293 | **YES** | Ranked segment hypotheses w/ falsification plans |
| `memo.md` | 5,623 | **YES (template)** | Markdown packet — **TODO-skeleton meant for an LLM to fill** |
| `audit_coverage_report.md` | 39,240 | diagnostic | Human coverage/QA report |
| `coverage_reconciliation_report.json` | 54,051 | diagnostic | Per-position close-ts/CLV reconciliation trace |
| `coverage_reconciliation_report.md` | 7,491 | diagnostic | MD version of above |
| `notional_weight_debug.json` | 3,577 | diagnostic | Notional-weighting denominators |
| `resolution_parity_debug.json` | 1,954 | diagnostic | Resolution-source parity |
| `clv_preflight.json` | 519 | diagnostic | CLV endpoint preflight (also echoed in run_manifest) |
| `run_manifest.json` | 3,307 | provenance | argv, git_commit, output_paths, timings, clv diagnostics |

There is **no** `positions.jsonl`, **no** `detectors.json`, **no** `alpha_candidates.json`
in scan dossiers. Positions + detectors live *inside* `dossier.json`. (See §6 for alpha_candidates.)

### 1b. `dossier.json` top-level schema

`packages/polymarket/llm_research_packets.py:1667` builds it. Top-level keys:

```
schema_version : "LLM Research Packet v1"
header         : dict(9)   # identity + window
coverage       : dict(10)  # data-availability counts
pnl_summary    : dict(4)   # bucketed realized/mtm/exposure + pricing_confidence
positions      : dict{count:int, positions:list}   # lifecycle rows, list HARD-CAPPED at 50
detectors      : dict{bucket_type, latest:list, trend:dict}
distributions  : dict(10)  # buy/sell ratio, notional histogram, top_markets/categories, hold_time
anchors        : dict(6)   # last_trades[], outliers[], top_notional[], anchor_trade_uids[]
liquidity_summary : dict(7)  # exec-cost percentiles, status_counts (0 on --lite)
```

Trimmed real samples (reference run):

```json
"header": {
  "export_id": "735ddc1d-b87e-444f-a273-47a4ecb97e69",
  "generated_at": "2026-06-04T23:25:55Z",
  "max_trades": 200,
  "proxy_wallet": "0xb7a63200d44c67c3bb44d8bda9f8e40b138189b2",
  "user_input": "0xb7a63200d44c67c3bb44d8bda9f8e40b138189b2",
  "username": "abUser123",
  "window_days": 30,
  "window_start": "2026-05-05T23:25:55Z",
  "window_end": "2026-06-04T23:25:55Z"
}

"pnl_summary": {
  "pricing_confidence": "LOW",
  "pricing_snapshot_ratio": 0.0,
  "latest_bucket": {"bucket_start":"2026-06-04T00:00:00Z","exposure_notional_estimate":8749.81,
                    "mtm_pnl_estimate":-16499.65,"realized_pnl":0.0},
  "trend_30d": {"bucket_count":30,"start":"2026-05-06T00:00:00Z","end":"2026-06-04T00:00:00Z",
                "exposure_avg":974.50,"mtm_avg":-1581.32,"mtm_total":-47439.50,
                "realized_avg":0.124,"realized_total":3.72}
}

"coverage": {
  "trades_count": 13, "activity_count": 0, "mapped_trades": 0, "mapping_coverage": 0.0,
  "positions_count": 82, "positions_snapshot_ts": "2026-06-04T23:25:32Z",
  "category_source": "none_available", "category_source_table": "market_tokens",
  "category_source_run_probe_token_count": 33
}

"detectors": {
  "bucket_type": "day",
  "latest": [
    {"detector":"MARKET_SELECTION_BIAS","label":"CONCENTRATED","score":1.0,"bucket_start":"2026-05-29T00:00:00Z"},
    {"detector":"COMPLETE_SET_ARBISH","label":"INSUFFICIENT_DATA","score":0.0,...},
    {"detector":"DCA_LADDERING","label":"INSUFFICIENT_DATA","score":0.0,...},
    {"detector":"HOLDING_STYLE","label":"UNKNOWN","score":0.0,...}
  ],
  "trend": {"COMPLETE_SET_ARBISH":[...],"DCA_LADDERING":[...],"HOLDING_STYLE":[...],"MARKET_SELECTION_BIAS":[...]}
}

"distributions": {
  "active_days":4,"buys_count":5,"sells_count":8,"buy_sell_ratio":0.625,
  "trades_per_active_day":3.25,"trades_per_window_day":0.4333,
  "hold_time_approx":{"available":...,"median_hours":...,"p90_hours":...,"samples":...},
  "notional_histogram":[6 buckets],"top_markets":[5],"top_categories":[0]
}
```

> **`coverage.positions_count` (82) ≠ `positions.count` (33).** `coverage.positions_count`
> is the raw open-positions snapshot from the Data API. `positions.count` is the count of
> **resolved/lifecycle rows** the exporter could build. The LLM only ever sees the
> lifecycle rows (§1c), and the embedded list is capped at 50.

### 1c. Position-rows exporter — `llm_research_packets.py:1610-1664`

The base `position_row` dict is assembled at **lines 1610-1654**, then passed through
`normalize_position_for_export()` (1656). The dossier slice is built at **1662-1665**:

```python
positions_summary = {
    "count": len(positions_lifecycle_rows),
    "positions": positions_lifecycle_rows[:50],  # Limit to 50 in dossier
}
```

**Full position-row field schema** (real row, reference run, `nba-sas-okc-2026-05-30`).
The base exporter writes the first block; `normalize_position_for_export` + the CLV ladder
add the `closing_*`, `clv*`, `beat_close*`, `movement_*`, `open_price*`, `price_*`,
`minutes_to_close*`, `realized_pnl_net_estimated_fees` family:

| field | type | sample |
|---|---|---|
| `resolved_token_id` | str | "578814797048...049" |
| `market_slug` | str | "nba-sas-okc-2026-05-30" |
| `question` | str | "Spurs vs. Thunder" |
| `outcome_name` | str | "Spurs" |
| `category` | str | "" (empty on --lite) |
| `entry_ts` | str(iso) | "2026-05-29T22:07:59Z" |
| `entry_price` | float | 0.43 |
| `total_bought` | float | 5000.0 |
| `total_cost` | float | 2150.0 |
| `exit_ts` | str/None | **null** (no sell) |
| `exit_price` | float/None | **null** |
| `total_sold` | float | 0.0 |
| `total_proceeds` | float | 0.0 |
| `position_remaining` | float | 5000.0 |
| `hold_duration_seconds` | int | 104209 |
| `trade_count` / `buy_count` / `sell_count` | int | 1 / 1 / 0 |
| `settlement_price` | float/None | 1.0 |
| `resolved_at` | str/None | "2026-05-31T03:04:48Z" |
| `resolution_source` | str | "gamma" |
| `resolution_outcome` | str | WIN / LOSS / PROFIT_EXIT / LOSS_EXIT / PENDING |
| `gross_pnl` | float | 2850.0 |
| `realized_pnl_net` | float | 2850.0 |
| `realized_pnl_net_estimated_fees` | float | 2793.0 |
| `fees_actual` / `fees_estimated` | float | 0.0 / 57.0 |
| `fees_source` | str | "estimated" |
| `clv` | float/None | 0.5695 |
| `clv_pct` | float/None | 1.324419 |
| `clv_source` | str | "prices_history\|onchain_resolved_at" |
| `clv_missing_reason` | str/None | null |
| `clv` / `clv_pct` / `clv_source` / `clv_missing_reason` **`_pre_event`** and **`_settlement`** variants | — | dual-ladder CLV |
| `closing_price` (+ `_pre_event`,`_settlement`) | float | 0.9995 |
| `closing_ts_observed` (+ `_pre_event`,`_settlement`) | str | "2026-05-31T03:04:04+00:00" |
| `beat_close` (+ `_pre_event`,`_settlement`) | bool | true |
| `movement_direction` | str | "flat" / "up" / "down" |
| `open_price` / `open_price_ts` | float / str | 0.44 / ... |
| `price_at_entry` / `price_1h_before_entry` (+ `_ts`) | float/str | 0.425 / 0.425 |
| `minutes_to_close` | int | 1736 |
| `close_ts` / `close_date_iso` / `close_ts_source` | str | onchain_resolved_at |
| `close_ts_attempted_sources` | list[str] | [onchain_resolved_at, gamma_closedTime, gamma_endDate, gamma_umaEndDate] |
| `gamma_close_date_iso` / `gamma_end_date_iso` / `gamma_start_date_iso` / `gamma_uma_end_date` (+ non-gamma aliases `end_date_iso`,`start_date_iso`,`uma_end_date`) | str/None | close-ts fallback ladder |
| `*_missing_reason` mirrors (`open_price_`, `price_at_entry_`, `price_1h_before_entry_`, `minutes_to_close_`, `movement_direction_`, `close_ts_failure_reason`) | str/None | provenance for nulls |

**A position row is ~2.5 KB of JSON (~620 tokens).** ~62 fields. There is **NO `side`,
`maker`, `taker`, or `side_type`** on a position row (see §3).

### 1d. `segment_analysis.json` full schema

`segment_analysis.json` top-level: `generated_at`, `run_id`, `user_slug`, `wallet`,
`segment_analysis`. The `segment_analysis` block has exactly these keys:

```
by_category, by_entry_price_tier, by_league, by_market_slug, by_market_type, by_sport,
entry_price_tiers, hypothesis_meta
```

- `entry_price_tiers` (definition): `[{name:"deep_underdog",max:0.3},{name:"underdog",min:0.3,max:0.45},
  {name:"coinflip",min:0.45,max:0.55},{name:"favorite",min:0.55}]`
- `hypothesis_meta`: `{min_count_threshold:5, notional_weight_total_global:76264.66}`
- `by_*` are dicts keyed by segment name → per-segment stat block. **Full real segment**
  (`by_entry_price_tier["coinflip"]`):

```json
{
 "count": 3, "wins": 0, "losses": 3, "win_rate": 0.0, "profit_exits": 0, "loss_exits": 0,
 "total_pnl_gross": -3645.9096, "total_pnl_net": -3645.9096,
 "avg_clv_pct": -0.998972, "median_clv_pct": -0.99898, "trimmed_mean_clv_pct": -0.998972,
 "p25_clv_pct": -0.999, "p75_clv_pct": -0.998936,
 "avg_clv_pct_pre_event": -0.998972, "avg_clv_pct_settlement": -0.998972,
 "notional_weighted_avg_clv_pct": -0.998986, "notional_w_total_weight_used": 3645.9096,
 "notional_weighted_avg_clv_pct_pre_event": -0.998986, "notional_weighted_avg_clv_pct_settlement": -0.998986,
 "beat_close_rate": 0.0, "beat_close_rate_pre_event": 0.0, "beat_close_rate_settlement": 0.0,
 "notional_weighted_beat_close_rate": 0.0,
 "avg_entry_drift_pct": 0.000592, "median_entry_drift_pct": 0.0,
 "p25_entry_drift_pct": -0.020202, "p75_entry_drift_pct": 0.021978,
 "trimmed_mean_entry_drift_pct": 0.000592, "notional_weighted_avg_entry_drift_pct": 0.000964,
 "avg_minutes_to_close": 485.33, "median_minutes_to_close": 525.0, "minutes_to_close_count_used": 3,
 "movement_up_rate": 0.333, "movement_down_rate": 0.333, "movement_flat_rate": 0.333, "movement_unknown_rate": 0.0,
 "*_count_used" / "*_weight_used": <coverage denominators on each metric>
}
```

Every metric carries a parallel `_count_used` / `_weight_used` so the consumer can see how
many positions actually backed it. `by_entry_price_tier` keys observed:
`{coinflip, deep_underdog, favorite, underdog, unknown}`. `by_category` here is just
`{"Unknown": {...}}` because category mapping was unavailable on this `--lite` run.

---

## 2. EXISTING LLM PACKET PATH — DETERMINISTIC, NOT LLM

**Definitive finding: Detectors, Hypothesis Candidates, and the Memo are produced by
deterministic templates/rules. There is no LLM call anywhere in the scan/packet path.**
A grep for `openai|anthropic|claude|chat.completion|llm.complete|.generate(` across
`llm_research_packets.py` and `tools/cli/scan.py` returns nothing.

**Detectors** — `packages/polymarket/detectors.py`, threshold rules. E.g. `HOLDING_STYLE`
(detectors.py:164-179):

```python
label = "UNKNOWN"; score = 0.0
if median_hold < self.SCALPER_MAX_MINUTES:
    label = "SCALPER"; score = 1.0 - (median_hold / self.SCALPER_MAX_MINUTES)
elif median_hold < self.SWING_MAX_MINUTES:
    label = "SWING"; ...
else:
    label = "HOLDER"; score = min(1.0, median_hold / (self.SWING_MAX_MINUTES * 2))
```
`DCA_LADDERING`: `label = "DCA_LIKELY" if score > 0.3 else "RANDOM"`. Packet wrapper:
`_build_detectors_payload()` (llm_research_packets.py:660) just shapes the rows.

**Hypothesis Candidates** — built deterministically from segment stats. `scan.py:1668`:
```python
hypothesis_candidates_path = write_hypothesis_candidates(
    candidates=coverage_report.get("hypothesis_candidates", []), ...)
```
They are ranked segments with a fixed `falsification_plan`
(`min_sample_size:30, min_coverage_rate:0.8, stop_conditions:[...]`) — no model in the loop.

**Memo** — `_build_research_memo()` (llm_research_packets.py:694). It is a **TODO skeleton**.
Real reference `memo.md`:
```markdown
## Executive Summary
- TODO: Summarize the strategy in 2-3 sentences.
## Key Observations
- TODO: Bullet observations backed by metrics/trade_uids.
## Hypotheses
| claim | evidence (metrics/trade_uids) | confidence | how to falsify | next feature needed |
| --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO |
```
Only the deterministic header / coverage / anchor-table sections are filled. **The memo is
literally the slot your per-dossier LLM prompt is meant to fill** — there is no existing
prompt template to inherit; you are designing the first one.

A real hypothesis candidate (rank 1, reference run):
```json
{
  "rank": 1, "segment_key": "entry_price_tier:favorite", "clv_variant_used": "pre_event",
  "denominators": {"count_used": 8, "weight_used": 41254.05, "weighting": "notional"},
  "metrics": {"count": 8, "win_rate": 0.875, "beat_close_rate": 0.875,
              "avg_clv_pct": 0.049357, "median_clv_pct": 0.094121,
              "notional_weighted_avg_clv_pct": 0.095925, "avg_minutes_to_close": 314.25, ...},
  "falsification_plan": {"min_sample_size": 30, "min_coverage_rate": 0.8,
    "stop_conditions": ["notional_weighted_avg_clv_pct < 0 for 2 consecutive future periods",
                        "count drops below 5 in a future run"]}
}
```

---

## 3. FIELD POPULATION REALITY

Latest run (2026-06-04). Extremes by `coverage.positions_count` (raw snapshot):

| | wallet | cov.positions_count | exported rows |
|---|---|---|---|
| SMALLEST | `0x132f78...453b` | 0 | 1 |
| MEDIAN | `0xe40ecf...9770` | 21 | 25 |
| LARGEST | `0xfe787d...0319` | 100 | 50 (capped) |

Population per field (present / nonzero-nonnull, out of exported rows):

| field | SMALLEST (1) | MEDIAN (25) | LARGEST (50) |
|---|---|---|---|
| `realized_pnl_net` | 1/1 real (33418.4) | 25/25 real | 50 present, **38 nonzero** (12 PENDING→0) |
| `gross_pnl` | 1/1 real | 25/25 real | 50 present, 38 nonzero |
| `clv` / `clv_pct` | 1/1 | 24/25 | 44/50 |
| `resolution_outcome` | WIN | WIN×14 LOSS×9 PROFIT_EXIT×2 | PENDING×12 LOSS×20 WIN×18 |
| `entry_ts` | 1/1 | 24/25 | 50/50 |
| `exit_ts` | **null** | **3/25 only** | **0/50** |
| `resolved_at` | 1/1 | 24/25 | 38/50 (null on PENDING) |
| `hold_duration_seconds` | 16920 | 24/25 | 50/50 |
| `settlement_price` | 1.0 | 14/25 | 18/50 (null on PENDING/exits) |

### Is `realized_net_pnl` real? — **YES, it is real.** (Note: the field is named
**`realized_pnl_net`**, not `realized_net_pnl`.)

For resolved positions it carries genuine signed dollar PnL (e.g. +33418.44, +2850.0,
-3645.91). It is **0.0 only by design** for `PENDING` positions that have no sells —
`llm_research_packets.py:1600-1608`:
```python
if resolution_outcome == "PENDING":
    settlement_price = None; resolved_at = None
    if sell_count_val == 0:
        gross_pnl = 0.0; realized_pnl_net = 0.0  # avoid fabricating losses on open positions
```
So the 12 zero-PnL rows in the largest dossier are open positions, not a broken pipeline.
**Drift flag:** the 2026-05-29 audit predates WI PnL/CLV enrichment; any "realized PnL is
0/null across the board" impression from that era is now **stale** — PnL and dual-ladder
CLV are populated for resolved rows.

**Pipeline-wide caveat that DOES hold:** `pnl_summary.pricing_confidence = "LOW"` and
`pricing_snapshot_ratio = 0.0` on every sampled dossier. The bucketed `pnl_summary.*_mtm`
(mark-to-market) values are low-confidence estimates; the *per-position* `realized_pnl_net`
(from resolution) is the trustworthy PnL, not the bucketed mtm.

### maker/taker / side_type on position rows? — **NO.**

Confirmed against the row schema (§1c) — no `side`, `maker`, `taker`, or `side_type` key
exists on `positions.positions[]`. This matches the audit
(`2026-05-29_wallet-ingestion-audit.md:134,203`) and CLAUDE.md WI-1 note: maker/taker is
not available from the Data API and is deferred to the raw-Jon/DuckDB path.

> **However** — directional `side` ("BUY"/"SELL") **does** exist at the **trade** level in
> `anchors.last_trades[]` and `anchors.anchor_trade_uids`. `last_trades[]` row keys:
> `market_slug, notional, outcome_name, price, question, resolved_token_id, side, size,
> token_id, trade_uid, ts, tx_hash`. So if your prompt needs entry/exit direction, pull it
> from `anchors`, not from position rows. (Still no maker/taker even there.)

---

## 4. DOSSIER INVENTORY

`artifacts/dossiers/users/` — **99 `dossier.json` files** across 23 distinct slugs and 6
run-dates (2026-02-20, 02-21, 03-29, 05-31, 06-01, **06-04**).

- **unknown slug: 72** dossiers · **named slugs: 27** dossiers.
- The latest run (2026-06-04) is **69 dossiers, all under `unknown`** (top-200 batch seed
  of bare wallets — no handle resolved).

**Position-count histogram (by `coverage.positions_count`, raw snapshot, all 99 runs):**

| bucket | count |
|---|---|
| 0 | 10 |
| 1–9 | 27 |
| 10–49 | 24 |
| 50–199 | 38 |
| 200–999 | 0 |
| 1000+ | 0 |

Max `coverage.positions_count` observed = **130**.

> **Critical routing fact:** the embedded `positions.positions[]` list is **hard-capped at
> 50** (`llm_research_packets.py:1664`). Across all 99 dossiers `positions.count` never
> exceeds 50, and `count == len(list)` in every file. So no matter how active the wallet,
> an LLM consuming `dossier.json` sees **≤ 50 lifecycle rows**. A "low-count" routing
> threshold should key off `coverage.positions_count` (raw, uncapped) and/or
> `coverage.trades_count`, not the embedded row count. Suggested low-signal cutoff:
> `coverage.positions_count < 10` (37 of 99 dossiers — the 0 and 1–9 buckets) are likely
> too thin for confident per-wallet strategy inference.

---

## 5. SIZE / TOKEN BUDGET

Largest latest-run dossier (`0xfe787d...0319`, 50 rows). Token estimate ≈ bytes/4:

| artifact | bytes | ~tokens |
|---|---|---|
| `dossier.json` | 325,644 | ~81,400 |
| `segment_analysis.json` | 43,148 | ~10,800 |
| `hypothesis_candidates.json` | 10,317 | ~2,600 |
| `memo.md` | 62,974 | ~15,700 |
| **TOTAL LLM-relevant** | **442,083** | **~110,500** |

Within `dossier.json`: **positions block alone = 128,525 B (~32,100 tok)** for 50 rows
(~640 tok/row); the rest of the dossier (anchors `last_trades`, distributions, detector
trend) = ~132,000 B (~33,000 tok). `memo.md` is large only because its deterministic
anchor table embeds full trade rows.

**Budget verdict:**
- A single large dossier's **raw `dossier.json` (~81K tok)** fits comfortably in a 200K /
  1M context window — so per-dossier raw ingestion is feasible **one at a time**.
- At fleet scale (69 dossiers/run) raw ingestion is ~5.6M tokens/run — wasteful.
- **Recommended:** drive the analysis from **`segment_analysis.json` + `hypothesis_candidates.json`**
  (~13K tok combined, already pre-aggregated and CLV-weighted) as the default, and only
  pull raw `positions.positions[]` (the ≤50 rows) when the wallet passes the low-count gate
  and the segment view flags something worth drilling into. Skip `memo.md` as input — it is
  an output slot, and its anchor table duplicates `anchors.last_trades`. Skip the
  `*_reconciliation_*` / `*_debug` / `audit_coverage_report.md` files entirely (diagnostics).

---

## 6. alpha_candidates.json

**Not generated in scan dossiers.** No `alpha_candidates.json` exists anywhere under
`artifacts/dossiers/`. The name belongs to a **separate** CLI path — `tools/cli/alpha_distill.py`
and `tools/cli/hypotheses.py` — not to `scan`/`wallet-scan`. The scan dossier's analogous
artifact is `hypothesis_candidates.json` (schema + real candidate shown in §2). If you want
alpha-distill output, it must be run as its own command; the latest wallet-scan run did not
produce it.

---

## Summary for prompt design

1. **Primary input** = `segment_analysis.json` (pre-aggregated, ~11K tok) +
   `hypothesis_candidates.json` (ranked, ~2.6K tok). Add the ≤50 `positions.positions[]`
   rows only for wallets above a `coverage.positions_count >= 10` gate.
2. The **memo.md TODO skeleton is the output contract** — your prompt fills Executive
   Summary / Key Observations / Hypotheses(table) / What changed / Next features.
3. **PnL is real** per-position (`realized_pnl_net`, signed); 0.0 only on open PENDING-no-sell
   rows. Trust per-position resolution PnL, distrust bucketed `pnl_summary` mtm
   (`pricing_confidence=LOW`).
4. **No maker/taker/side_type** anywhere; directional `side` only at trade level in
   `anchors.last_trades[]`. Don't ask the model to infer maker/taker.
5. **Hard 50-row cap** on embedded positions — route on `coverage.positions_count`, not the
   embedded count. 37/99 dossiers are <10 positions (thin).
6. Everything upstream is **deterministic** — the LLM is the *first* interpretive layer; it
   must cite `trade_uid`s / segment metrics (the existing falsification discipline) rather
   than invent.
