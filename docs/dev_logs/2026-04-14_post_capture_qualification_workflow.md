# Post-Capture Qualification Workflow

**Date:** 2026-04-14
**Task:** quick-260414-qrt
**Status:** COMPLETE

---

## Summary

This work packet adds `tools/gates/qualify_gold_batch.py`, a focused, read-only CLI tool that
fills a gap in the Gold capture campaign loop: after an operator records new Gold shadow tapes
via `simtrader shadow`, there was previously no single command to answer "which tapes qualify,
which bucket shortages do they reduce, and which are ready for Gate 2?" The new tool accepts
a batch of tape directories, qualifies each against the same admission rules used by `corpus_audit.py`,
computes a before/after shortage delta against the existing corpus, and produces a clear actionable
report — without writing any files or mutating any manifests.

The tool imports directly from `corpus_audit.py` (bucket detection, tier detection, quota constants)
and `capture_status.py` (existing corpus baseline snapshot), so there is no logic duplication and no
risk of the qualification tool diverging from the corpus audit rules it shadows.

---

## Problem Statement

After capturing Gold tapes via `simtrader shadow`, the operator had no single command to
answer: "which tapes qualify, which bucket shortages do they reduce, and which are ready
for Gate 2?" The existing `corpus_audit.py` does full-corpus scanning and writes files.
The existing `capture_status.py` shows current status but not what changed. The gap is a
focused batch-level qualification report with before/after delta.

---

## Solution: qualify_gold_batch.py

### CLI Interface

```
python tools/gates/qualify_gold_batch.py \
    --tape-dirs <dir1> [<dir2> ...] \
    [--tape-roots <corpus_root> ...]   # defaults to artifacts/tapes/{gold,silver,}
    [--json]                           # machine-readable JSON output
```

### Core Function

`qualify_batch(batch_dirs, tape_roots, *, min_events=50) -> dict`

1. Computes "before" corpus snapshot via `compute_status(tape_roots)`.
2. For each batch tape: counts effective events, detects tier and bucket.
3. Applies admission rules in order: too_short -> no_bucket_label -> over_quota -> QUALIFIED.
4. Quota caps account for the existing corpus "have" count per bucket, so only the remaining
   shortage is available to the batch.
5. Returns `{batch_results, shortage_delta, gate2_ready, summary}`.

### Output Format (human-readable)

```
=== Batch Qualification Report ===

Per-tape results:
  [QUALIFIED]  artifacts/tapes/gold/slug1  bucket=sports  tier=gold  events=87
  [REJECTED]   artifacts/tapes/gold/slug2  bucket=politics  tier=gold  events=30  reason=too_short
  [QUALIFIED]  artifacts/tapes/gold/slug3  bucket=politics  tier=gold  events=62

Shortage delta:
  Bucket              Before  After  Delta
  ------------------  ------  -----  -----
  sports                  15     14     -1
  politics                 9      8     -1

Summary: 2 qualified, 1 rejected, 2 bucket shortages reduced

Gate 2 ready tapes (feed to corpus_audit.py):
  artifacts/tapes/gold/slug1
  artifacts/tapes/gold/slug3
```

### Integration with the Capture Campaign Loop

The tool fits directly into the loop described in `SPEC-phase1b-gold-capture-campaign.md`:

1. Check current corpus shortage:
   ```
   python tools/gates/capture_status.py
   ```

2. Capture Gold tapes for a shortage bucket:
   ```
   python -m polytool simtrader shadow --market <slug> --duration 300
   ```
   Tapes land in `artifacts/tapes/gold/<slug>/`.

3. Qualify the new batch:
   ```
   python tools/gates/qualify_gold_batch.py \
       --tape-dirs artifacts/tapes/gold/<slug1> artifacts/tapes/gold/<slug2>
   ```
   Report shows which tapes qualify and what the updated shortage looks like.

4. When ready, feed gate2_ready tapes to corpus audit:
   ```
   python tools/gates/corpus_audit.py \
       --tape-roots artifacts/tapes/gold \
       --tape-roots artifacts/tapes/silver \
       --tape-roots artifacts/tapes \
       --out-dir artifacts/corpus_audit \
       --manifest-out config/recovery_corpus_v1.tape_manifest
   ```
   When corpus_audit exits 0, proceed to Gate 2 sweep.

---

## What Was NOT Changed (Scope Discipline)

- No fill-model changes
- No benchmark_v1 manifest modifications (`config/benchmark_v1.tape_manifest`, `config/benchmark_v1.lock.json`, `config/benchmark_v1.audit.json` untouched)
- No policy or gate threshold changes
- No changes to `corpus_audit.py` or `capture_status.py` (read-only consumer)
- No wallet discovery
- No cloud LLM routing
- No BrokerSim changes
- No benchmark_v2 work

---

## Test Results

### qualify_gold_batch tests (9 tests)

```
tests/test_qualify_gold_batch.py::test_single_tape_qualifies PASSED
tests/test_qualify_gold_batch.py::test_tape_too_short PASSED
tests/test_qualify_gold_batch.py::test_tape_no_bucket PASSED
tests/test_qualify_gold_batch.py::test_batch_mixed PASSED
tests/test_qualify_gold_batch.py::test_over_quota_detection PASSED
tests/test_qualify_gold_batch.py::test_baseline_awareness PASSED
tests/test_qualify_gold_batch.py::test_json_output PASSED
tests/test_qualify_gold_batch.py::test_empty_batch PASSED
tests/test_qualify_gold_batch.py::test_gate2_ready_list PASSED

9 passed in 0.64s
```

### Full regression suite

```
2479 passed, 1 failed (pre-existing: test_gemini_provider_success -- unrelated to this work),
3 deselected, 19 warnings in 66.52s
```

The pre-existing failure (`test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success`)
is an attribute error in the cloud provider routing module (`_post_json` attribute missing) and
is entirely unrelated to this work packet.

---

## Files Changed

| File | Action |
|------|--------|
| `tools/gates/qualify_gold_batch.py` | Created -- post-capture batch qualification tool |
| `tests/test_qualify_gold_batch.py` | Created -- 9 deterministic offline tests |
| `docs/dev_logs/2026-04-14_post_capture_qualification_workflow.md` | Created -- this file |

---

## Codex Review

Tier: Skip (read-only reporting tool, no execution paths, no order placement, no live-capital
logic, no ClickHouse writes, no fill model).
