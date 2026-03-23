# Runbook: Benchmark v1 Real Closure

**Purpose:** Step-by-step operator guide to close `config/benchmark_v1.tape_manifest`
for real, enabling the Gate 2 scenario sweep.

**Done condition:** `config/benchmark_v1.tape_manifest` exists and exit 0 from
`python -m polytool close-benchmark-v1`.

---

## Check current state first

```bash
python -m polytool close-benchmark-v1 --status
```

Read the output top-to-bottom. Each line tells you what exists and what is
missing. The "Suggested next step" at the bottom tells you exactly where to
start. If `Manifest: CREATED` appears → you are done, skip this entire runbook.

---

## Step 0 — Prerequisites

What you need locally before starting:

- `data/raw/pmxt_archive/` — pmxt Parquet files (full batch imported 2026-03-15)
- `data/raw/jon_becker/` — Jon-Becker Parquet files (sample imported 2026-03-16)
- Docker + Docker Compose installed and functional

**If already done:** confirm with `ls data/raw/pmxt_archive/ | head -3` and
`ls data/raw/jon_becker/ | head -3`. If files exist, proceed to Step 1.

---

## Step 1 — Start Docker / ClickHouse

```bash
docker compose up -d
docker compose ps          # all services should show "healthy" or "running"
curl "http://localhost:8123/?query=SELECT%201"  # should print: 1
```

**If already done:** `curl http://localhost:8123/?query=SELECT+1` returns `1`.
If yes, skip to Step 2.

**If ClickHouse is not reachable:** the Silver stage will still run but
metadata writes fall back to JSONL files in `artifacts/silver/`. That is
acceptable for closure purposes.

---

## Step 2 — Export priority-1 token IDs

```bash
python -m polytool close-benchmark-v1 --export-tokens
```

Expected output:
```
[close-benchmark-v1] Exported 39 priority-1 token IDs
  source: config/benchmark_v1_gap_fill.targets.json
  txt:    config/benchmark_v1_priority1_tokens.txt
  json:   config/benchmark_v1_priority1_tokens.json
```

Writes:
- `config/benchmark_v1_priority1_tokens.txt` — 39 token IDs, one per line
- `config/benchmark_v1_priority1_tokens.json` — same as JSON array

**If already done:** `config/benchmark_v1_priority1_tokens.txt` exists and has
39 lines (`wc -l config/benchmark_v1_priority1_tokens.txt`). Skip to Step 3.

---

## Step 3 — Fetch 2-min price history for priority-1 tokens

The Silver reconstructor requires `price_2min` data in ClickHouse for each
token. Run `fetch-price-2min` for all 39 priority-1 tokens.

```bash
# Fetch price history for all 39 priority-1 tokens in one batch:
while IFS= read -r token_id; do
    python -m polytool fetch-price-2min --token-id "$token_id"
done < config/benchmark_v1_priority1_tokens.txt
```

Or pass all IDs at once (if `fetch-price-2min` supports multiple `--token-id`):

```bash
ARGS=()
while IFS= read -r tid; do ARGS+=(--token-id "$tid"); done \
    < config/benchmark_v1_priority1_tokens.txt
python -m polytool fetch-price-2min "${ARGS[@]}"
```

**Expected:** each token prints rows fetched and written to ClickHouse.

**If already done:** check ClickHouse:
```bash
curl "http://localhost:8123/?query=SELECT+COUNT(*)+FROM+polytool.price_2min"
```
If the count is > 0 and `--status` shows CH available, proceed to Step 4.

**If ClickHouse is unavailable:** Silver reconstruction still runs but without
`price_2min` midpoint guidance. Tapes may have lower quality. You can skip
this step with `--skip-price-2min` on Step 4.

---

## Step 4 — Silver closure run (politics / sports / crypto / near_resolution)

This step reconstructs Silver tapes for the 39 priority-1 tokens across the
four coverable buckets. It will skip the `new_market` bucket (no JB candidates
exist; that requires live Gold recording in Step 5).

```bash
python -m polytool close-benchmark-v1 \
    --skip-new-market \
    --pmxt-root data/raw/pmxt_archive \
    --jon-root  data/raw/jon_becker
```

Expected console output summary:
```
[close-benchmark-v1] Stage 1: Preflight
  [OK] preflight passed
[close-benchmark-v1] Stage 2: Silver gap-fill
  status: completed
[close-benchmark-v1] Stage 3: New-market — skipped (--skip-new-market)
[close-benchmark-v1] Stage 4: Finalization
  final_status: blocked        ← expected; new_market bucket not yet filled
  [BLOCKER] bucket 'new_market': shortage=5
```

Exit code 1 is **expected** at this point (new_market bucket still open).

Artifacts written to:
- `artifacts/silver/<YYYY-MM-DD>/<run_id>/` per token
- `artifacts/benchmark_closure/<YYYY-MM-DD>/<run_id>/benchmark_closure_run_v1.json`

**If ClickHouse is unavailable:** add `--skip-price-2min` to the command above.
Silver tapes will be reconstructed but without price midpoint guidance.

**If this step was already run:** check `--status`. If "Residual blockers" only
lists `new_market`, Silver is done. Proceed to Step 5.

---

## Step 5 — New-market Gold tape capture

The `new_market` bucket requires 5 fresh Gold tapes from Polymarket listings
that are <48h old. This step requires:
- Live Gamma API connectivity
- Live WS connectivity to `wss://clob.polymarket.com/`

**When to run:** best run during a window when Polymarket has freshly listed
markets (check https://polymarket.com/activity for recent listings).

```bash
python -m polytool close-benchmark-v1 --skip-silver
```

This runs:
1. `new-market-capture` planner — discovers candidates via live Gamma API
2. `capture-new-market-tapes --benchmark-refresh` — records Gold tapes

Expected when candidates exist:
```
[close-benchmark-v1] Stage 3: New-market closure
  status: completed
  [OK] benchmark manifest written: config/benchmark_v1.tape_manifest
[close-benchmark-v1] Stage 4: Finalization
  final_status: manifest_created
```

Exit code 0 = `config/benchmark_v1.tape_manifest` created. Closure achieved.

**If insufficient candidates:** planner returns exit 2. Re-run later when
fresh markets appear. Check `config/benchmark_v1_new_market_capture.insufficiency.json`
for the exact reason.

---

## Step 6 — Full closure run (once Silver + new-market data are ready)

After Steps 4 and 5 have both populated their respective data:

```bash
python -m polytool close-benchmark-v1 \
    --pmxt-root data/raw/pmxt_archive \
    --jon-root  data/raw/jon_becker
```

Expected:
```
Stage 4: Finalization
  final_status: manifest_created
  manifest: config/benchmark_v1.tape_manifest
```

Exit code 0. `config/benchmark_v1.tape_manifest` now exists.

---

## Step 7 — Validate the manifest

```bash
python -m polytool benchmark-manifest --validate
```

Expected: prints tape inventory summary, all 5 buckets at quota, exit 0.

Also confirm via status:
```bash
python -m polytool close-benchmark-v1 --status
# Should show:  Manifest: CREATED
```

---

## Resumability

Each step is independently resumable:

| Step | Already-done check | Skip condition |
|------|-------------------|----------------|
| 0 — Prerequisites | `ls data/raw/pmxt_archive/ \| head -3` has files | skip |
| 1 — Docker up | `curl http://localhost:8123/?query=SELECT+1` returns `1` | skip |
| 2 — Export tokens | `wc -l config/benchmark_v1_priority1_tokens.txt` == 39 | skip |
| 3 — Fetch price_2min | CH price_2min COUNT(*) > 0 | skip or use `--skip-price-2min` |
| 4 — Silver run | `--status` shows only `new_market` as blocker | skip (use `--skip-silver`) |
| 5 — New-market capture | `--status` shows `Manifest: CREATED` | done |
| 6 — Full run | exit 0; `config/benchmark_v1.tape_manifest` exists | done |
| 7 — Validate | `benchmark-manifest --validate` exits 0 | done |

---

## Troubleshooting

**ClickHouse unavailable during Silver run:**
Silver tapes will be reconstructed but `tape_metadata` writes fall back to
JSONL files in `artifacts/silver/`. Add `--skip-price-2min` to skip the price
fetch step.

**`batch-reconstruct-silver` errors for some tokens:**
Per-target failures are isolated — the batch continues. Check
`artifacts/benchmark_closure/<date>/<run_id>/benchmark_closure_run_v1.json`
under `silver_gap_fill.batch_reconstruct.failure_count`. A non-zero failure
count is acceptable as long as enough tapes are created to satisfy quotas.

**new_market planner returns 0 candidates:**
JB dataset snapshot is ~2026-02-03 (40 days stale). New-market candidates
require markets created <48h ago via the live Gamma API. This step must be
run when fresh Polymarket listings exist. The only path is real-time capture.

**Benchmark curation still blocked after Silver run:**
Silver tapes may not have been accepted by the curation logic (eligibility
check). Check `config/benchmark_v1.gap_report.json` for per-bucket counts.
Re-run with different token windows if needed.

---

## Artifacts produced

| File | When created | Purpose |
|------|-------------|---------|
| `config/benchmark_v1_priority1_tokens.txt` | Step 2 | 39 token IDs for price fetch |
| `config/benchmark_v1_priority1_tokens.json` | Step 2 | Same, JSON format |
| `artifacts/silver/<date>/*/silver_events.jsonl` | Step 4 | Reconstructed Silver tapes |
| `artifacts/benchmark_closure/<date>/<run_id>/benchmark_closure_run_v1.json` | Steps 4, 5, 6 | Closure run audit |
| `config/benchmark_v1.tape_manifest` | Step 5 or 6 | Final manifest — closure complete |

---

## Related CLIs

```bash
# Check current status at any time:
python -m polytool close-benchmark-v1 --status

# Dry-run (no mutations, shows what would happen):
python -m polytool close-benchmark-v1 --dry-run

# Export tokens only:
python -m polytool close-benchmark-v1 --export-tokens

# Silver only (skip new-market):
python -m polytool close-benchmark-v1 --skip-new-market --pmxt-root ... --jon-root ...

# New-market only (skip Silver — use after Silver is done):
python -m polytool close-benchmark-v1 --skip-silver

# Full run:
python -m polytool close-benchmark-v1 --pmxt-root ... --jon-root ...
```
