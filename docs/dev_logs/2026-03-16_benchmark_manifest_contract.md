# Benchmark Manifest Contract - 2026-03-16

## Scope

Objective: harden the `benchmark_v1` manifest contract so operators can validate
the file, freeze it for an experiment series, and get clear failures on shape,
quota, duplicate, missing-file, or drift violations.

Authority: `docs/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md`

## Files changed and why

| File | Why |
| --- | --- |
| `packages/polymarket/benchmark_manifest_contract.py` | New validation + lock module. Enforces shape, roadmap quotas, canonical ordering, and freeze drift checks. |
| `tools/cli/benchmark_manifest.py` | Added reusable tape analysis helper, freeze-aware build behavior, lock writing, and `validate` subcommand. |
| `tools/gates/mm_sweep.py` | Added the smallest opt-in benchmark manifest hook for future Gate 2 work. |
| `tools/cli/simtrader.py` | Added `sweep-mm --benchmark-manifest PATH` plumbing. |
| `polytool/__main__.py` | Updated top-level help text and normalized two help strings to ASCII for Windows console safety. |
| `tests/test_benchmark_manifest.py` | Added focused offline contract tests and CLI validation smoke. |
| `tests/test_mm_sweep_gate.py` | Added explicit benchmark-manifest hook coverage and asserted default behavior is unchanged. |
| `tests/test_polytool_main_module_smoke.py` | Added `benchmark-manifest validate --help` smoke coverage. |
| `docs/specs/SPEC-benchmark-manifest-contract-v1.md` | New short spec for the contract and lock behavior. |
| `docs/dev_logs/2026-03-16_benchmark_manifest_contract.md` | Mandatory implementation log. |

## Validation rules enforced

- Manifest root must be a JSON array.
- Manifest must contain exactly 50 entries.
- Every entry must be a non-empty string path.
- Every entry must use canonical normalized path form.
- Every path must exist and point to a tape file.
- Duplicate resolved paths are rejected.
- Listed tapes are reclassified with the same benchmark bucket logic used by
  curation.
- Required quotas must still be satisfiable:
  - politics = 10
  - sports = 15
  - crypto = 10
  - near_resolution = 10
  - new_market = 5
- Manifest order must match the deterministic canonical bucket order emitted by
  the curation solver.

## Fingerprint / freeze mechanism

Chosen mechanism: `config/benchmark_v1.lock.json`

Fields recorded:

- `schema_version = benchmark_tape_lock_v1`
- `benchmark_version`
- `manifest_schema_version`
- canonical manifest SHA-256
- tape count
- bucket counts
- ordered tape paths
- per-tape SHA-256 fingerprints

Behavior:

- First successful curation writes the lock automatically.
- `benchmark-manifest validate` verifies the lock when it exists.
- Manifest content changes and tape-content changes both fail as fingerprint
  drift.
- Once `benchmark_v1` exists, `benchmark-manifest` validates the frozen file
  instead of rewriting it.

## Tiny hook for later Gate 2 work

Added opt-in support for:

```bash
python -m polytool simtrader sweep-mm --benchmark-manifest PATH
```

Behavior:

- Default `sweep-mm` discovery is unchanged.
- When the flag is present, the sweep validates the benchmark manifest first
  and then loads that explicit tape list instead of ad hoc tape discovery.

## Commands run and output

```bash
python -m py_compile packages/polymarket/benchmark_manifest_contract.py \
  tools/cli/benchmark_manifest.py tools/gates/mm_sweep.py \
  tools/cli/simtrader.py polytool/__main__.py
```

Output: none. Exit code `0`.

```bash
pytest -q tests/test_benchmark_manifest.py tests/test_mm_sweep_gate.py \
  tests/test_polytool_main_module_smoke.py
```

Output:

```text
25 passed in 9.86s
```

Fixture CLI validation smoke:

```text
[benchmark-manifest] valid: D:\Coding Projects\Polymarket\PolyTool\.sandboxtmp\benchmark_contract_smoke\config\benchmark_v1.tape_manifest
[benchmark-manifest] bucket counts: politics=10, sports=15, crypto=10, near_resolution=10, new_market=5
[benchmark-manifest] manifest sha256: 0f2370b6f172e0e9e0d249b85c2d47c6682032a9c89394e4ff884cdc1f8feb8c
[benchmark-manifest] lock written: D:\Coding Projects\Polymarket\PolyTool\.sandboxtmp\benchmark_contract_smoke\config\benchmark_v1.lock.json
```

Return code: `0`

Real manifest check:

```text
REAL_MANIFEST_ABSENT
```

Meaning: no real `config/benchmark_v1.tape_manifest` currently exists in this
worktree, so there was nothing real to validate beyond the fixture smoke.

## Test results

Focused contract coverage added:

- valid manifest passes
- underfilled manifest fails
- duplicate path fails
- missing file fails
- fingerprint drift fails
- CLI validation smoke writes lock
- `sweep-mm` explicit benchmark-manifest hook works
- top-level `polytool` help exposes the validation command

## Notes

- While adding the help smoke, `polytool --help` exposed a pre-existing Windows
  console encoding hazard caused by non-ASCII help text. The touched help lines
  were normalized to ASCII as part of this packet.
