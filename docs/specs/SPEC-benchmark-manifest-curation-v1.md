# SPEC: Benchmark Manifest Curation v1

**Status:** Implemented - 2026-03-16
**Branch:** `phase-1`
**Implements:** `python -m polytool benchmark-manifest`

---

## 1. Purpose

`benchmark_v1` is the fixed 50-tape benchmark set required by the Master
Roadmap v4.2. The curation path must be deterministic and honest:

- If real local inventory satisfies the roadmap quotas, write
  `config/benchmark_v1.tape_manifest`.
- If inventory is insufficient, do not fabricate paths. Write a
  machine-readable gap report and leave the manifest absent.

The manifest itself is a JSON array of tape event-file paths. The richer
inventory and selection provenance lives in the companion audit / gap JSON.

---

## 2. Roadmap Quotas

`benchmark_v1` is fixed at 50 unique tape paths with these quotas:

- `politics`: 10
- `sports`: 15
- `crypto`: 10
- `near_resolution`: 10
- `new_market`: 5

The benchmark version is immutable mid-series. If the set changes materially,
the next version must be `benchmark_v2`.

---

## 3. Inventory Discovery

Default roots:

- `artifacts/simtrader/tapes`
- `artifacts/silver`
- Optional external root: `D:\PolyToolData\tapes` or `$POLYTOOL_DATA_ROOT/tapes`
  when present

Recognized tape shapes:

- Gold: directory containing `events.jsonl`
- Silver: directory containing `silver_events.jsonl`

Metadata sources are file-first:

- `watch_meta.json`
- `prep_meta.json`
- `meta.json` (`shadow_context` / `quickrun_context` first, then top-level)
- `silver_meta.json` for Silver tapes

Empty tape files are skipped as invalid inventory.

Paths written into outputs are repo-relative when the tape lives inside the
workspace; otherwise they are absolute.

---

## 4. Bucket Classification

Classification uses only on-disk metadata and tape contents. No live API
lookups are performed.

### Politics / Sports

- Primary path: shared `classify_market_regime()` from
  `packages/polymarket/market_selection/regime_policy.py`
- Politics fallback: obvious political slugs still count if they contain
  fallback keywords such as `trump`, `biden`, `kamala`, `immigration`, or
  `deport`

### Crypto

- Metadata keyword match on slug/title/question/category/tags
- Examples: `crypto`, `bitcoin`, `btc`, `ethereum`, `eth`, `solana`, `doge`

### New Market

Threshold: `< 48h`

Detection order:

1. Explicit `age_hours`
2. `created_at` / `listed_at` / similar fields relative to tape capture time

Capture time is taken from `selected_at`, `started_at`, `generated_at`,
`window_start`, `ended_at`, or the tape-directory timestamp prefix.

### Near Resolution

Threshold: `<= 24h`

Detection order:

1. Explicit `hours_to_resolution`
2. `close_time` / `resolution_time` / `end_date_iso` style fields relative to
   tape capture time
3. Price-tail fallback: primary asset observed at `<= 0.10` or `>= 0.90`

This fallback is intentional because many existing tapes carry no explicit
resolution timestamp metadata but still represent the strategy's
near-resolution stress regime.

### Overlap Policy

A tape may qualify for multiple buckets, but the final manifest uses each path
at most once.

---

## 5. Deterministic Selection

Selection is two-stage:

1. Rank candidates within each bucket deterministically.
2. Solve the unique-path assignment with min-cost max-flow so overlaps do not
   cause a false shortage.

Bucket-specific ranking rules:

- `politics`: higher price-span first (high-volatility preference), then Gold
- `sports`: Gold first, then higher event count
- `crypto`: Gold first, then higher price span
- `near_resolution`: explicit resolution-time evidence first, then smaller
  `hours_to_resolution`, then Gold
- `new_market`: smaller `age_hours` first, then Gold

If quotas are satisfiable, the manifest order is grouped by roadmap bucket
order: politics, sports, crypto, near-resolution, new-market.

---

## 6. Outputs

### Success

- `config/benchmark_v1.tape_manifest`
- `config/benchmark_v1.audit.json`
- Process exit code: `0`

`benchmark_v1.tape_manifest` is a JSON array of 50 tape event-file paths.

### Failure

- No manifest write
- `config/benchmark_v1.gap_report.json`
- Process exit code: `2`

The gap report includes:

- discovered inventory by tier
- candidate counts by bucket
- selected counts by bucket
- exact shortages by bucket
- selected assignment preview
- skipped invalid tapes

---

## 7. Known Limitation

Current Silver reconstruction metadata does not yet persist category, age, or
resolution-time fields. Silver tapes can still be discovered structurally, but
they may remain unclassified unless sidecar metadata is present or the tape
contents make the bucket obvious (for example, near-resolution via price tails).
