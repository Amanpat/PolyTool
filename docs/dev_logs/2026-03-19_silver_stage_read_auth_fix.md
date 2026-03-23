# Dev Log: Silver Stage Read-Auth Fix (2026-03-19)

## Problem

After the 2026-03-19 auth-propagation fixes (which removed the `"polytool_admin"` silent
fallback from all three `main()` guards), a live run of:

```
python -m polytool close-benchmark-v1 --skip-new-market ...
```

still produced a misleading preflight warning:

```
[WARN] ClickHouse not reachable — Silver stage metadata writes will use JSONL fallback
```

even though ClickHouse was running correctly with authentication.  The Silver stage itself
proceeded and made authenticated connections fine; only the preflight CH probe was wrong.

Additionally, when Silver targets did fail, the orchestrator artifact only surfaced aggregate
counts (`failure_count`) — not *which* targets failed or why — making post-mortem analysis
require digging into the full batch artifact.

## Root Cause (two-part)

### 1. Unauthenticated preflight CH probe

`_check_clickhouse` in `close_benchmark_v1.py` made plain HTTP requests with no
`Authorization` header.  On a ClickHouse instance configured to require credentials, every
unauthenticated request returns HTTP 401 or a connection error, so the probe always reported
"not available" regardless of actual CH health.

Worse, `run_preflight` did not accept `clickhouse_user`/`clickhouse_password` parameters at
all, so even when `run_closure` had resolved the correct credentials, they were never forwarded
to the probe.  The preflight CH check was structurally inconsistent with Stage 2's authenticated
access.

### 2. No per-target failure evidence in orchestrator artifact

`run_batch_from_targets` returns a full `outcomes[]` array with `status`, `token_id`, `bucket`,
`slug`, and `error` per target.  `run_silver_gap_fill_stage` only propagated aggregate counts
(`tapes_created`, `failure_count`, `skip_count`) into the `batch_reconstruct` key of the
orchestrator artifact, discarding individual failure details.

## Fix

### `tools/cli/close_benchmark_v1.py` — 5 changes

**1. `_check_clickhouse` now sends HTTP Basic Auth:**

```python
# BEFORE:
def _check_clickhouse(host: str = "localhost", port: int = 8123) -> dict:
    url = f"http://{host}:{port}/?query=SELECT+1"
    with urllib.request.urlopen(url, timeout=5) as resp:
        ...

# AFTER:
def _check_clickhouse(
    host: str = "localhost",
    port: int = 8123,
    user: str = "polytool_admin",
    password: str = "",
) -> dict:
    import base64
    req = urllib.request.Request(url)
    if user or password:
        creds = base64.b64encode(f"{user}:{password}".encode()).decode()
        req.add_header("Authorization", f"Basic {creds}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        ...
```

**2. `run_preflight` signature** — added `clickhouse_user` and `clickhouse_password` params.

**3. `_check_clickhouse` call inside `run_preflight`** — now passes `user=clickhouse_user, password=clickhouse_password`.

**4. `run_preflight` call inside `run_closure`** — now forwards `clickhouse_user` and `clickhouse_password`.

**5. `failed_targets` bubbled into `recon_outcome`** inside `run_silver_gap_fill_stage`:

```python
# BEFORE:
recon_outcome = {
    "schema_version": ..., "targets_attempted": ...,
    "tapes_created": ..., "failure_count": ..., "skip_count": ...,
}

# AFTER:
failed = [
    {"token_id": o.get("token_id"), "bucket": o.get("bucket"),
     "slug": o.get("slug"), "error": o.get("error")}
    for o in batch_result.get("outcomes", [])
    if o.get("status") == "failure"
]
recon_outcome = {
    ...,
    "failed_targets": failed,
}
```

## Tests Added

### `tests/test_close_benchmark_v1.py` — `TestPreflightCredentialConsistency` (3 tests)

- `test_check_clickhouse_sends_auth_header` — patches `urllib.request.urlopen`, verifies
  that the `Authorization: Basic <base64(user:password)>` header is attached to the request.

- `test_run_preflight_forwards_credentials_to_check_clickhouse` — patches `_check_clickhouse`
  as a mock, calls `run_preflight(clickhouse_user="myuser", clickhouse_password="s3cr3t", ...)`,
  asserts `_check_clickhouse` was called with `user="myuser", password="s3cr3t"`.

- `test_silver_stage_failed_targets_in_recon_outcome` — provides a `batch_result` with two
  failure outcomes, asserts `batch_reconstruct["failed_targets"]` contains exactly those two
  tokens with correct `bucket` and `error` fields; success outcome not included.

## Test Results

```
116 passed in 4.94s
```

All 116 tests across the three affected files pass with no regressions.

## Next Step — Live Rerun

From a real-user shell with Docker running:

```bash
export CLICKHOUSE_PASSWORD=<real_password>
docker compose up -d
python -m polytool close-benchmark-v1 \
  --skip-new-market \
  --pmxt-root /path/to/pmxt_archive \
  --jon-root  /path/to/jon_becker \
  --clickhouse-password "$CLICKHOUSE_PASSWORD" \
  --out artifacts/benchmark_closure/$(date +%Y-%m-%d)/run.json
```

The preflight CH probe will now report correctly.  If any Silver targets fail, their
`token_id`, `bucket`, `slug`, and `error` will appear in `run.json` under
`silver_gap_fill.batch_reconstruct.failed_targets` for direct triage.
