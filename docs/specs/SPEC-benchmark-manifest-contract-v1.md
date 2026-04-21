# SPEC: Benchmark Manifest Contract v1

**Status:** Implemented - 2026-03-16  
**Branch:** `phase-1`  
**Authority:** `docs/archive/reference/POLYTOOL_MASTER_ROADMAP_v4.2.md` (superseded; retained for historical context)

---

## 1. Purpose

`benchmark_v1` is the frozen benchmark tape set for experiment comparability.
This spec hardens the manifest file itself after curation:

- validate the file shape
- validate the roadmap quotas
- reject duplicates and missing files
- detect post-freeze drift

If `benchmark_v1` needs to change materially, the next file must be
`benchmark_v2.*`, not a mutated `benchmark_v1`.

---

## 2. Manifest Contract

`benchmark_v1.tape_manifest` remains a plain JSON array. The contract is:

- root value must be a JSON array
- exactly 50 entries
- every entry must be a non-empty string path
- every path must use canonical normalized form
- every path must point to an existing `events.jsonl` or `silver_events.jsonl`
- duplicate resolved paths are forbidden

Validation reclassifies the listed tapes with the same bucket logic used by the
curation command. A manifest is valid only if the 50 listed tapes still support
this exact assignment:

- `politics`: 10
- `sports`: 15
- `crypto`: 10
- `near_resolution`: 10
- `new_market`: 5

The manifest order is also fixed. The array must match the deterministic
canonical bucket order emitted by the curation solver.

---

## 3. Freeze Lock

Success writes `config/benchmark_v1.lock.json` with:

- `schema_version = "benchmark_tape_lock_v1"`
- benchmark version + manifest schema version
- canonical manifest SHA-256
- tape count
- bucket counts
- ordered tape path list
- per-tape file SHA-256 fingerprints

Validation compares the manifest against the lock when the lock is present.
Any manifest edit, path substitution, reorder, or tape-content mutation is
reported as fingerprint drift.

`python -m polytool benchmark-manifest` is freeze-aware:

- if `benchmark_v1` is absent, it may curate and write the manifest
- if `benchmark_v1` already exists, it validates the frozen file instead of
  rewriting it

---

## 4. Operator CLI

Build or confirm the frozen manifest:

```bash
python -m polytool benchmark-manifest
```

Validate an existing manifest:

```bash
python -m polytool benchmark-manifest validate \
  --manifest config/benchmark_v1.tape_manifest
```

Write a lock after validation:

```bash
python -m polytool benchmark-manifest validate \
  --manifest config/benchmark_v1.tape_manifest \
  --write-lock
```

Exit codes:

- `0`: valid / success
- `2`: blocked curation or invalid manifest contract

---

## 5. Minimal Sweep Hook

`python -m polytool simtrader sweep-mm` now accepts:

```bash
python -m polytool simtrader sweep-mm --benchmark-manifest PATH
```

This is an opt-in hook only. Existing tape discovery remains the default. When
the flag is used, the sweep validates the benchmark manifest first and then
loads that explicit tape list instead of relying on ad hoc tape discovery.
