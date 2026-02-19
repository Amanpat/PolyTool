# ADR-0011 — Audit Default: All Positions

**Date:** 2026-02-18
**Status:** Accepted

---

## Context

Prior to this change:

- `audit-coverage` defaulted to `--sample 25` — only 25 positions were included
  in the report.
- `scan` only emitted an audit report when `--audit-sample N` was explicitly
  passed; no audit was produced by default.

This meant that ad-hoc scans produced no audit artifact, and the default
`audit-coverage` invocation was opaque — the "25" was arbitrary and users did
not know positions were being silently dropped.

---

## Decision

1. **`audit-coverage` defaults to ALL positions.**
   The `--sample` flag now defaults to `None`.  When omitted, every position in
   the dossier is included, ordered by the stable sort key
   `(token_id, condition_id, created_at)` with resolved positions first.
   The report heading changes from `## Samples (N)` to `## All Positions (N)`.

2. **`scan` always emits an audit report.**
   The conditional `if config.get("audit_sample") is not None` guard is removed.
   The audit report is written unconditionally at the end of every `scan` run.
   `output_paths.audit_coverage_report_md` is always present in the manifest.

3. **Explicit `--sample` / `--audit-sample` still work.**
   Passing an explicit integer limits the report to `min(N, total)` positions via
   the existing deterministic sampler, and the heading remains `## Samples (N)`.

4. **Seed is irrelevant in all-mode.**
   When all positions are included, the RNG is not invoked.  The `--seed` /
   `--audit-seed` flag is accepted but has no effect.

---

## Consequences

- Every `scan` run now produces an audit artifact without extra flags.
- `audit-coverage` without `--sample` shows the full position set, making it
  easier to spot outliers that a small sample would miss.
- Existing callers that pass explicit `--sample N` / `--audit-sample N` are
  unaffected — they still get `## Samples (N)`.
- JSON format: `samples.n_requested` is `null` in all-mode; `samples.all_mode`
  is `true`.

---

## Alternatives Considered

- **Keep default at 25, add `--all` flag.**  Rejected: `--all` is less
  discoverable and a 25-position default silently under-represents portfolios
  with hundreds of positions.
- **Default to ALL in `audit-coverage` only, keep scan gated.**  Rejected:
  inconsistent — a scan with no audit flag produced no audit artifact, leaving a
  gap in the trust trail.
