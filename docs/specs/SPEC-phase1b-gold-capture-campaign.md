# SPEC-phase1b-gold-capture-campaign — Phase 1B Gold Capture Campaign

**Version:** v1.0
**Status:** Active
**Created:** 2026-03-27
**Governs:** Operator Gold tape capture campaign for Phase 1B Gate 2

---

## 1. Campaign Context

`benchmark_v1` is finalized and immutable. Its 50 tapes fail the 50-event
minimum threshold at a rate that makes the corpus insufficient for Gate 2.

As of 2026-03-27:
- **10 / 50** tapes qualify (9 near_resolution Silver + 1 politics Gold)
- **40 more tapes** are needed via live Gold shadow capture
- All Silver reconstruction routes are exhausted
- No gate-core or strategy changes are required
- The Market Maker V1 strategy logic is unchanged

Gate 2 is in **NOT_RUN** state (corpus gap is informational, not a gate failure).
The sole blocker is corpus count. This campaign spec covers the operator workflow
to capture the remaining tapes.

---

## 2. Starting shortage table

| Bucket          | Quota | Have | Need |
|-----------------|------:|-----:|-----:|
| sports          |    15 |    0 |   15 |
| politics        |    10 |    1 |    9 |
| crypto          |    10 |    0 |   10 |
| new_market      |     5 |    0 |    5 |
| near_resolution |    10 |    9 |    1 |
| **Total**       |**50** |**10**|**40**|

These counts are as of 2026-03-27. Run `python tools/gates/capture_status.py`
for the current shortage — counts change as tapes are captured.

---

## 3. Bucket Quotas and Completion Rules

For the formal contract see `docs/specs/SPEC-phase1b-corpus-recovery-v1.md`.
This section summarizes the key constraints that are **immutable**:

- **min_events = 50**: Every tape must have at least 50 effective events.
  Never weaken this threshold.
- **effective_events >= 50** is required for admission. The audit counts
  `price_change` and `last_trade_price` events; `book` events are excluded.
- **All 5 buckets must be represented**: politics, sports, crypto,
  near_resolution, new_market. A corpus missing any bucket cannot qualify
  even if total count >= 50.
- **`corpus_audit.py` is the authoritative counter**: its exit code and
  shortage_report.md are the ground truth. Do not eyeball directories.
- **Gate 2 threshold >= 70%**: once corpus qualifies, the sweep must show
  >= 70% positive net PnL across all tapes. Never weaken this threshold.

---

## 4. Campaign Loop

The capture campaign follows a simple iterative loop:

1. **Check current shortage:**
   ```
   python tools/gates/capture_status.py
   ```
   Read the Bucket table. Focus on the bucket with the largest "Need" value.

2. **Shadow-record one or more tapes** for the highest-shortage bucket.
   Minimum 600 seconds per tape. See `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`
   for the exact command.

3. **Validate the tape** by re-running the full corpus audit:
   ```
   python tools/gates/corpus_audit.py \
       --tape-roots artifacts/simtrader/tapes \
       --tape-roots artifacts/silver \
       --tape-roots artifacts/tapes \
       --out-dir artifacts/corpus_audit \
       --manifest-out config/recovery_corpus_v1.tape_manifest
   ```
   Read the bucket counts. If the new tape was accepted, its bucket count
   increments. If rejected, check shortage_report.md for the reason.

4. **Repeat** — capture more tapes, re-run the audit, check status — until
   `corpus_audit.py` exits 0.

5. **Run Gate 2** once corpus_audit exits 0:
   ```
   python tools/gates/close_mm_sweep_gate.py \
       --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
       --out artifacts/gates/mm_sweep_gate
   ```

---

## 5. Resumability Rules

Each shadow session writes to a new timestamped tape directory under
`artifacts/simtrader/tapes/`. No prior capture session is overwritten.

`corpus_audit.py` always scans from scratch — it is fully idempotent. Rerunning
after each session is safe and required to confirm admission.

Any step in the loop is safe to restart:
- If a shadow session is interrupted, the partial tape dir is usually rejected
  as too_short (fewer than 50 events). Start a new session.
- If corpus_audit is interrupted, rerun it. No state is lost.
- If Gate 2 is interrupted after corpus qualifies, rerun close_mm_sweep_gate.py.

---

## 6. Success Artifacts

When the capture campaign completes:

- `corpus_audit.py` exits **0**
- `config/recovery_corpus_v1.tape_manifest` written (JSON array of events paths)
- `artifacts/corpus_audit/recovery_corpus_audit.md` written (per-tape breakdown)
- Gate 2 sweep is **unblocked**: run `close_mm_sweep_gate.py` against the manifest

Gate 2 PASS condition: >= 70% of tapes show positive net PnL after fees and
realistic-retail assumptions.

---

## 7. Failure Artifacts

When `corpus_audit.py` exits 1 (shortage still exists):

- `artifacts/corpus_audit/shortage_report.md` written with exact per-bucket gaps
- `config/recovery_corpus_v1.tape_manifest` is **NOT** written until corpus qualifies
- Continue the campaign loop (capture more tapes)

---

## 8. Constraints

The following constraints are **non-negotiable** throughout this campaign:

- **No live capital**: Shadow mode never submits real orders. All sessions are safe.
- **min_events=50 is immutable**: Do not pass `--min-events` values below 50 to any tool.
- **Gate 2 threshold >= 70% is immutable**: Do not weaken the sweep pass condition.
- **benchmark_v1 is immutable**: Do not modify any `config/benchmark_v1.*` file.
- **No strategy tuning**: MarketMakerV1 parameters are not changed during this campaign.
- **capture_status.py is read-only**: It must never write any file.

---

## 9. Tool Reference

| Tool | Purpose |
|------|---------|
| `tools/gates/capture_status.py` | Quick shortage status (one command, no file writes) |
| `tools/gates/corpus_audit.py` | Full scan + manifest writer (authoritative counter) |
| `python -m polytool simtrader shadow ...` | Live Gold tape capture |
| `tools/gates/close_mm_sweep_gate.py` | Gate 2 sweep (after corpus qualifies) |

The detailed capture command and prerequisites are in:
`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`
