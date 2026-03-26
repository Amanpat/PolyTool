# SPEC-phase1b-corpus-recovery-v1 — Recovery Corpus Contract for Gate 2

**Version:** v1.0
**Status:** Active
**Created:** 2026-03-26
**Governs:** `tools/gates/corpus_audit.py`, `config/recovery_corpus_v1.tape_manifest`

---

## 1. Purpose

Gate 2 (market-maker scenario sweep) requires a minimum of 50 tapes with at
least 50 effective events each. The `benchmark_v1` corpus is finalized and
immutable. The 41/50 tapes in that corpus with fewer than 50 effective events
block Gate 2 from producing a valid verdict.

This spec defines:

1. The preservation rule for `benchmark_v1` (never modified).
2. Admission rules for a separate **recovery corpus** built from tape inventory.
3. The manifest versioning policy.
4. Gate 2 rerun preconditions against the recovery corpus.
5. Success/failure artifact contracts.
6. A pointer to the Gold tape capture flow for operators.

---

## 2. Benchmark v1 Preservation Rule

`config/benchmark_v1.tape_manifest`, `config/benchmark_v1.lock.json`, and
`config/benchmark_v1.audit.json` are **immutable reference artifacts**.

**Never modify them.** They represent the finalized benchmark corpus as of
2026-03-21. Any replay or sweep result derived from these files is reproducible
and comparable across sessions. If the audit or lock files differ from their
known hashes, treat the corpus as tampered.

Recovery corpus work is conducted entirely in separate files and directories.
No tool in this specification writes to any `benchmark_v1.*` file.

---

## 3. Recovery Corpus Admission Rules

### 3.1 Minimum effective_events

Every tape in the recovery corpus must have `effective_events >= 50`.

This threshold must never be softened. The same threshold governs Gate 2's
`--min-events` parameter. Admitting shorter tapes would silently weaken the
Gate 2 corpus requirement without updating the gate itself.

**Rejection reason code:** `too_short`

### 3.2 Accepted Tiers

- **Gold**: tapes recorded by the live tape recorder (shadow mode, `watch_meta.json`
  present, or `recorded_by` field in `meta.json` set to `"shadow"` or
  `"tape_recorder"`). Gold is always preferred when a bucket is oversubscribed.
- **Silver-with-fills**: reconstructed tapes where `silver_meta.json` is present
  and `effective_events >= 50`. Price-2min-only Silver tapes with zero fills and
  sub-50 effective_events are not admitted separately — they simply fail the
  min_events check.

Tier preference for quota selection (when oversubscribed per bucket):
1. Gold (highest priority)
2. Silver (any confidence level, as long as effective_events >= 50)

Within the same tier, prefer higher `effective_events` (more data is better).

### 3.3 Bucket Quotas

Bucket quotas match the `benchmark_v1` target distribution:

| Bucket          | Quota |
|-----------------|------:|
| politics        |    10 |
| sports          |    15 |
| crypto          |    10 |
| near_resolution |    10 |
| new_market      |     5 |
| **Total**       |**50** |

- A tape with no bucket label is rejected with reason `no_bucket_label`.
- Accepted tapes per bucket are capped at the quota. Excess tapes are rejected
  with reason `over_quota` (so the audit report accounts for all candidates).
- Bucket labels are extracted from tape metadata in this priority order:
  `watch_meta.json["bucket"]`, `market_meta.json["benchmark_bucket"]`,
  `manifest_entry["bucket"]`, directory path inference.

### 3.4 Duplicate Elimination

If two candidate paths resolve to the same canonical `events.jsonl` path, the
second occurrence is skipped. Canonical path comparison uses `Path.resolve()`.

---

## 4. Manifest Versioning Policy

### 4.1 Recovery manifest

**File:** `config/recovery_corpus_v1.tape_manifest`

Format: JSON array of relative `events.jsonl` path strings (same format as
`benchmark_v1.tape_manifest`). Paths are relative to the repository root.

Example:
```json
[
  "artifacts/simtrader/tapes/20260307T195039Z_will-the-toronto-map/events.jsonl",
  "artifacts/silver/5500958648222024/2026-03-15T10-00-00Z/silver_events.jsonl"
]
```

This file is **only written when the corpus qualifies** (>= 50 tapes, all 5
buckets represented). A partial manifest is never written; a partial manifest
would be invalid for Gate 2.

### 4.2 Audit artifacts

All audit artifacts go under `artifacts/corpus_audit/`.

- `recovery_corpus_audit.md` — written when corpus qualifies.
- `shortage_report.md` — written when corpus is insufficient.

One and only one of these two files is written per audit run (overwriting any
prior output from the same audit path).

---

## 5. Gate 2 Rerun Preconditions

Before running Gate 2 against the recovery corpus, all of the following must hold:

1. `config/recovery_corpus_v1.tape_manifest` exists (written by `corpus_audit.py`
   with exit code 0).
2. The manifest contains >= 50 tape paths.
3. Each tape path resolves to an existing `events.jsonl` file.
4. All five buckets are represented (>= 1 tape per bucket minimum).
   Recommended: >= 70% bucket fill (i.e., at least 7/10, 10/15, 7/10, 7/10,
   3/5 tapes) before declaring the corpus "ready" for Gate 2.
5. `corpus_audit.py` exited 0 in the most recent run.

Gate 2 rerun command (once preconditions are met):

```bash
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
```

---

## 6. Success and Failure Artifact Contracts

### 6.1 Qualified corpus (exit 0)

Written by `corpus_audit.py` when total qualified >= 50 AND all 5 buckets
have >= 1 tape:

- **`config/recovery_corpus_v1.tape_manifest`** — JSON array of `events.jsonl`
  paths for all accepted tapes.
- **`artifacts/corpus_audit/recovery_corpus_audit.md`** — Markdown report with:
  - Per-tape table: tape_dir, bucket, tier, effective_events, status (ACCEPTED/REJECTED),
    reject_reason
  - Summary: total scanned, accepted, rejected by reason, count by bucket/tier
  - Closing line: `"Qualified manifest written to: config/recovery_corpus_v1.tape_manifest"`

### 6.2 Insufficient corpus (exit 1)

Written by `corpus_audit.py` when total qualified < 50 OR any bucket is empty:

- **`artifacts/corpus_audit/shortage_report.md`** — Markdown report with:
  - Current qualified count per bucket and tier
  - Exact shortage: how many more tapes are needed per bucket
  - Recommended action per bucket (e.g., "Record 8 Gold shadow tapes in sports bucket")
- `config/recovery_corpus_v1.tape_manifest` is **not written**.

### 6.3 Gate 2 rerun artifacts

Gate 2 rerun produces the following in `artifacts/gates/mm_sweep_gate/`:
- `gate_passed.json` — if pass_rate >= 70%
- `gate_failed.json` — if pass_rate < 70%
- `gate_summary.md` — human-readable summary

Per the existing Gate 2 contract (SPEC-phase1b-gate2-shadow-packet.md §2.3),
the gate exit code is 0 for PASS and 1 for FAIL (or NOT_RUN).

---

## 7. Gold Tape Capture Flow

When `corpus_audit.py` exits 1 (shortage), the operator should capture new
Gold shadow tapes to fill the shortage. See:

`docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`

The runbook covers:
- Which markets to target per bucket
- Shadow capture command (minimum 600s duration)
- Per-tape validation
- Stopping condition (run `corpus_audit.py` after each batch; stop when exit 0)

---

## 8. Tool Reference

### `tools/gates/corpus_audit.py`

```
Usage: python tools/gates/corpus_audit.py [OPTIONS]

Options:
  --tape-roots PATH     (repeatable) Tape root directories to scan.
                        Default: artifacts/simtrader/tapes, artifacts/silver,
                                 artifacts/tapes
  --out-dir PATH        Output directory for audit artifacts.
                        Default: artifacts/corpus_audit
  --min-events INT      Minimum effective_events per tape.
                        Default: 50 (never weaken)
  --manifest-out PATH   Path for the output manifest.
                        Default: config/recovery_corpus_v1.tape_manifest

Exit codes:
  0 — corpus qualifies; manifest written
  1 — corpus insufficient; shortage_report.md written
```

---

## 9. Constraints

- Gate 2 threshold `>= 0.70` is not weakened anywhere in this specification.
- `min_events=50` is not softened anywhere in this specification.
- `benchmark_v1` artifacts are never written or modified by any tool described
  in this specification.
- No live capital: shadow capture sessions never submit real orders.
- Gate 3 is not attempted until Gate 2 produces a PASS verdict against the
  recovery corpus.
