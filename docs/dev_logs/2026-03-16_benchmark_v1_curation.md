# Dev Log: Benchmark v1 Curation

**Date:** 2026-03-16
**Branch:** `phase-1`
**Status:** blocked honestly; no `config/benchmark_v1.tape_manifest` written

## Files changed and why

| File | Why |
|---|---|
| `tools/cli/benchmark_manifest.py` | New deterministic inventory audit + curation CLI. Discovers Gold/Silver tape files, classifies roadmap buckets from local metadata, solves unique-path quota assignment, and writes either a manifest+audit or a gap report. |
| `polytool/__main__.py` | Registered `benchmark-manifest` on the shared CLI surface and added help text. |
| `tests/test_benchmark_manifest.py` | Added focused offline tests for shortage reporting, overlap-aware assignment, Gold-vs-Silver preference, politics fallback classification, and the full 50-path success path. |
| `docs/specs/SPEC-benchmark-manifest-curation-v1.md` | New spec for discovery roots, bucket heuristics, deterministic selection, and failure behavior. |
| `docs/CURRENT_STATE.md` | Recorded the shipped CLI and the current blocked benchmark status from the real local audit. |
| `config/benchmark_v1.gap_report.json` | Machine-readable failure artifact from the real local inventory audit on this machine. |

Note: `polytool/__main__.py` and `docs/CURRENT_STATE.md` were already locally dirty in this worktree. The benchmark-manifest updates were applied on top without reverting unrelated changes.

## Real inventory counts found

Command run against local canonical roots:

- `artifacts/simtrader/tapes`
- `artifacts/silver`

Observed inventory:

- Discovered tapes: 12
- Gold tapes: 12
- Silver tapes: 0
- Skipped invalid tapes: 0

Bucket candidate counts:

- Politics: 1
- Sports: 4
- Crypto: 0
- Near-resolution: 5
- New-market: 0

Best-effort unique assignment from real inventory:

- Selected total: 6
- Selected politics: 1
- Selected sports: 4
- Selected crypto: 0
- Selected near-resolution: 1
- Selected new-market: 0

Exact shortages:

- Politics: 9
- Sports: 11
- Crypto: 10
- Near-resolution: 9
- New-market: 5

## benchmark_v1 result

- `config/benchmark_v1.tape_manifest`: not created
- `config/benchmark_v1.gap_report.json`: created
- Block reason: roadmap quotas are not satisfiable from real local inventory

## Commands run + output

```bash
python -m py_compile tools/cli/benchmark_manifest.py polytool/__main__.py
```

Output:

```text
(no output; compile passed)
```

```bash
pytest -q tests/test_benchmark_manifest.py
```

Output:

```text
5 passed in 0.63s
```

```bash
pytest -q tests/test_hypotheses_cli.py
```

Output:

```text
18 passed in 1.83s
```

```bash
pytest -q tests/test_experiment_run.py
```

Output:

```text
2 passed in 1.72s
```

```bash
python -m polytool benchmark-manifest --help
```

Output (key lines):

```text
usage: benchmark-manifest [-h] [--root DIR] [--manifest-out PATH]
Audit local tape inventory and build config/benchmark_v1.tape_manifest when
all roadmap quotas are satisfiable. Otherwise writes a machine-readable gap
report and exits non-zero.
```

```bash
python -m polytool benchmark-manifest
```

Output:

```text
[benchmark-manifest] blocked: wrote gap report config\benchmark_v1.gap_report.json
[benchmark-manifest] shortages: politics=9, sports=11, crypto=10, near_resolution=9, new_market=5
EXIT:2
```

## Test results

- New benchmark tests: passed
- Existing `polytool.__main__` regression coverage (`tests/test_hypotheses_cli.py`, `tests/test_experiment_run.py`): passed
- Real local audit: executed successfully, returned the expected blocked state and emitted the gap report

## Open gaps for next prompt

- Capture or reconstruct real politics inventory beyond the single currently classifiable tape.
- Produce any real crypto tapes; current local inventory has zero crypto candidates.
- Capture or retain metadata for market age (`age_hours` / `created_at`) so new-market tapes can be classified.
- Persist category and time-to-resolution metadata alongside Silver outputs; current Silver tape plumbing discovers files but does not yet make them easy to bucket.
- Once enough real inventory exists, rerun `python -m polytool benchmark-manifest` to replace the gap report with `config/benchmark_v1.tape_manifest` and `config/benchmark_v1.audit.json`.
