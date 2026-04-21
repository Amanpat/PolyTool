# Bulk Historical Import v0 — Operator Runbook

> **v4.2 NOTE — LEGACY / OPTIONAL TOOLING**: Under Master Roadmap v4.2, this
> runbook is **off the critical path**. DuckDB reads pmxt and Jon-Becker Parquet
> files directly from `/data/raw/` without any ClickHouse import step. The
> ClickHouse bulk import implemented here is useful as an optional cache/index
> layer but is **not required** for Silver tape reconstruction or Gate 2 passage.
> See `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` (Database Architecture).
> The v4.2 primary path is: DuckDB setup → Silver reconstruction → Gate 2 sweep.

**Status**: Packet 2 shipped (2026-03-13). Steps 1-6 are operational but
off the critical path under v4.2. Use this runbook if you want a ClickHouse
cache/index of historical data; skip it if you are following the v4.2 DuckDB path.

**Spec**: `docs/specs/SPEC-0018-bulk-historical-import-foundation-v0.md`

**Purpose (legacy/optional)**: Import pmxt archive + Jon-Becker dataset +
2-minute price history into ClickHouse tables as a cache/index layer. Under
v4.2, Silver tape reconstruction uses DuckDB on the raw Parquet files directly
instead. pmxt full import (78,264,878 rows) and Jon-Becker sample import are
complete; their artifacts are in `artifacts/imports/`.

Gate 2 is NOT passed by this runbook. Silver tape reconstruction (blocked on
DuckDB setup under v4.2) is required before the sweep can run.

---

## Prerequisites

- Python environment with PolyTool installed: `pip install -e .`
- Sufficient disk space:
  - pmxt archive: ~50-200 GB depending on date range
  - Jon-Becker dataset: ~10-30 GB (compressed), ~40-100 GB extracted
  - 2-minute price history: ~1-5 GB per 1000 tokens
- `zstd` installed for decompressing Jon-Becker: `brew install zstd` (macOS) or
  `apt install zstd` (Linux)
- For Step 6 (deferred): ClickHouse running (`docker compose up -d`)

---

## Step 1: Download pmxt Archive

Visit https://archive.pmxt.dev and download the Polymarket snapshot files.

Expected layout after download:

```
/data/pmxt/
  Polymarket/
    2026-01/
      snapshot_2026-01-01T00.parquet
      snapshot_2026-01-01T01.parquet
      ...
    2026-02/
      ...
  Kalshi/       (optional)
  Opinion/      (optional)
```

The exact subdirectory structure under `Polymarket/` may vary. The validator
only requires that `Polymarket/` exists and contains at least one `.parquet` file
somewhere in the tree.

---

## Step 2: Download Jon-Becker Dataset

```bash
# Download the compressed archive (~10-30 GB)
curl -O https://s3.jbecker.dev/data.tar.zst

# Move to your data directory
mkdir -p /data/jbecker
mv data.tar.zst /data/jbecker/

# Extract (requires zstd)
cd /data/jbecker
tar --use-compress-program=zstd -xf data.tar.zst
```

Expected layout after extraction:

```
/data/jbecker/
  data.tar.zst          (keep for provenance)
  data/
    polymarket/
      trades/
        *.parquet       (or *.csv)
    kalshi/             (optional)
      trades/
        *.parquet
```

License: MIT (see prediction-market-analysis repository).

---

## Step 3: Pull 2-Minute Price History

Use the `polymarket-apis` PyPI package to fetch price history per token.

```bash
pip install polymarket-apis

python - <<'EOF'
import os
from pathlib import Path
from polymarket_apis import PolymarketClient

# Configure output directory
outdir = Path("/data/price_history_2min")
outdir.mkdir(parents=True, exist_ok=True)

client = PolymarketClient()

# Fetch price history for each token of interest
token_ids = [
    "YOUR_TOKEN_ID_HERE",
    # ... add more token IDs
]

for token_id in token_ids:
    history = client.get_all_price_history_by_token_id(token_id)
    out_file = outdir / f"{token_id}.jsonl"
    with open(out_file, "w") as f:
        for record in history:
            import json
            f.write(json.dumps(record) + "\n")
    print(f"Wrote {out_file}")
EOF
```

Expected layout:

```
/data/price_history_2min/
  <token_id_1>.jsonl
  <token_id_2>.jsonl
  ...
```

Note: The polymarket-apis API is public and does not require an API key.
Rate limit to avoid being blocked (add `time.sleep(0.5)` between calls).

---

## Step 4: Validate Each Layout

Run the dry-run validator for each source before any import:

```bash
# Validate pmxt archive layout
python -m polytool import-historical validate-layout \
    --source-kind pmxt_archive \
    --local-path /data/pmxt

# Validate Jon-Becker layout
python -m polytool import-historical validate-layout \
    --source-kind jon_becker \
    --local-path /data/jbecker

# Validate 2-minute price history layout
python -m polytool import-historical validate-layout \
    --source-kind price_history_2min \
    --local-path /data/price_history_2min
```

Expected output for a valid layout:

```
[import-historical validate-layout]
  source_kind: pmxt_archive
  path:        /data/pmxt
  status:      OK
  file_count:  1247
  checksum:    a3f9b2c1d4e8f012...

Layout valid. Run 'show-manifest' to generate a provenance record.
```

If status is `FAILED`, fix the errors listed before proceeding.

---

## Step 5: Generate Provenance Manifests

After each source passes validation, generate a manifest:

```bash
mkdir -p artifacts/imports

# pmxt archive manifest
python -m polytool import-historical show-manifest \
    --source-kind pmxt_archive \
    --local-path /data/pmxt \
    --snapshot-version "2026-03" \
    --notes "Full Polymarket snapshot archive, downloaded 2026-03-13" \
    --out artifacts/imports/pmxt_manifest.json

# Jon-Becker manifest
python -m polytool import-historical show-manifest \
    --source-kind jon_becker \
    --local-path /data/jbecker \
    --snapshot-version "2024-12" \
    --notes "Jon-Becker 72M-trade dataset, MIT license, downloaded 2026-03-13" \
    --out artifacts/imports/jbecker_manifest.json

# 2-minute price history manifest
python -m polytool import-historical show-manifest \
    --source-kind price_history_2min \
    --local-path /data/price_history_2min \
    --notes "2-min price history for Gate 2 candidate tokens, pulled 2026-03-13" \
    --out artifacts/imports/price_history_manifest.json
```

Commit the manifest files as provenance records:

```bash
git add artifacts/imports/
git commit -m "chore: add bulk historical import provenance manifests v0"
```

---

## Step 6: ClickHouse Import (now available in Packet 2)

The destination tables are created by migrations `21_pmxt_archive.sql`,
`22_jon_becker_trades.sql`, and `23_price_history_2min.sql`. Ensure
ClickHouse is running before any non-dry-run import:

```bash
# Copy .env.example to .env and set CLICKHOUSE_PASSWORD before first boot.
docker compose up -d
```

After running Steps 1-5, execute the actual import:

```bash
mkdir -p artifacts/imports

# Dry-run first (validates layout, counts files, no CH writes)
python -m polytool import-historical import \
    --source-kind pmxt_archive \
    --local-path /data/pmxt \
    --import-mode dry-run \
    --snapshot-version "2026-03" \
    --out artifacts/imports/pmxt_run_record.json

# Sample import (first 1000 rows from first file, for validation)
python -m polytool import-historical import \
    --source-kind pmxt_archive \
    --local-path /data/pmxt \
    --import-mode sample \
    --sample-rows 1000 \
    --snapshot-version "2026-03" \
    --out artifacts/imports/pmxt_sample_run.json

# Full import (all rows, all files)
python -m polytool import-historical import \
    --source-kind pmxt_archive \
    --local-path /data/pmxt \
    --import-mode full \
    --snapshot-version "2026-03" \
    --out artifacts/imports/pmxt_full_run.json
```

Repeat with `--source-kind jon_becker` and `--source-kind price_history_2min`
for the other two datasets.

**Note**: Parquet files require `pyarrow`. Install it with:
```bash
pip install polytool[historical-import]
# or: pip install pyarrow>=12.0.0
```

CSV and JSONL files import without any additional dependencies.

Each import writes a JSON run record with a `provenance_hash` field for
audit traceability. Commit run records to `artifacts/imports/` as evidence.

**Metric note**: `rows_attempted` in the run record is the number of rows sent
to the ClickHouse `insert()` call, not the number of rows CH persists. Because
`pmxt_l2_snapshots` uses `ReplacingMergeTree`, background merges deduplicate
rows that share the same `(platform, market_id, token_id, side, price, snapshot_ts)`
key. A `SELECT count(*) FROM polytool.pmxt_l2_snapshots` after a full import
will typically return fewer rows than `rows_attempted`. This is expected. To
verify the actual CH count after import:

```bash
curl "http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}/?user=${CLICKHOUSE_USER:-polytool_admin}&password=${CLICKHOUSE_PASSWORD}&query=SELECT+count(*)+FROM+polytool.pmxt_l2_snapshots"
```

To verify ClickHouse auth and then confirm the tables exist:

```bash
curl "http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}/?user=${CLICKHOUSE_USER:-polytool_admin}&password=${CLICKHOUSE_PASSWORD}&query=SELECT+1"
curl "http://localhost:${CLICKHOUSE_HTTP_PORT:-8123}/?user=${CLICKHOUSE_USER:-polytool_admin}&password=${CLICKHOUSE_PASSWORD}&query=SELECT+name+FROM+system.tables+WHERE+database='polytool'+AND+(name+LIKE+'pmxt%25'+OR+name+LIKE+'jb_%25'+OR+name+LIKE+'price_%25')"
```

If you previously started ClickHouse with different `CLICKHOUSE_USER` /
`CLICKHOUSE_PASSWORD` values, recreate the ClickHouse volume before retrying:

```bash
docker compose down -v
docker compose up -d
```

---

## Troubleshooting

### pmxt archive: "Required subdirectory missing: Polymarket/"

The download may have placed files in a nested directory. Check:

```bash
find /data/pmxt -name "*.parquet" | head -5
```

If parquet files are one level deeper, adjust `--local-path` to point to the
directory that directly contains `Polymarket/`.

### Jon-Becker: "data.tar.zst found but data/ directory not extracted"

Run the extraction:

```bash
cd /data/jbecker
tar --use-compress-program=zstd -xf data.tar.zst
```

If `tar` does not support `--use-compress-program`, try:

```bash
zstd -d data.tar.zst -o data.tar && tar -xf data.tar
```

### Jon-Becker: "no trade files" after extraction

Check the actual directory structure:

```bash
find /data/jbecker/data -type f | head -20
```

The expected path is `data/polymarket/trades/`. If the structure differs,
file a bug — the validator may need updating for a new dataset version.

### price_history_2min: "No price history files found"

Confirm the files were downloaded to the correct path and have `.jsonl`, `.csv`,
or `.json` extensions. Files in subdirectories are also found (recursive search).

### Manifest shows status "staged" after validation passes

Re-run `show-manifest` after `validate-layout` returns status `OK`. The manifest
status reflects the validation result at manifest-generation time. If the directory
was empty during `show-manifest`, the status will be `staged`.

---

## Artifact Inventory

After completing Steps 1-6, you should have:

```
/data/pmxt/                      # pmxt archive (large, not committed)
/data/jbecker/                   # Jon-Becker dataset (large, not committed)
/data/price_history_2min/        # 2-min price history (medium, not committed)
artifacts/imports/
  pmxt_manifest.json             # provenance manifest (committed)
  jbecker_manifest.json          # provenance manifest (committed)
  price_history_manifest.json    # provenance manifest (committed)
  pmxt_run_record.json           # import run record with provenance_hash (committed)
  jbecker_run_record.json        # import run record (committed)
  price_history_run_record.json  # import run record (committed)
```

Data directories should be added to `.gitignore` to avoid committing large files.
Manifest and run record JSON files should be committed as provenance records.

---

## Next Steps (v4.2 primary path — supersedes Packet 3)

Under v4.2, Silver tape reconstruction is DuckDB-based, not ClickHouse-based.
The ClickHouse import steps above are complete (pmxt full batch + Jon-Becker
sample) but are no longer required for the reconstruction step.

1. DuckDB setup and integration (reads pmxt + Jon-Becker Parquet files directly)
2. Fetch price_history_2min from polymarket-apis (still required as mid-price constraint)
3. Implement Silver tape reconstruction via DuckDB queries on raw Parquet files
4. Run Gate 2 scenario sweep on Silver-tier tapes
5. If sweep passes (>=70% score), close Gate 2 via `tools/gates/close_sweep_gate.py`
