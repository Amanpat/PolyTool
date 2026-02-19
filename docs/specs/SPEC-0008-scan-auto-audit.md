# SPEC-0008 - Scan Auto Audit

## Overview

`scan` always emits `audit_coverage_report.md` in-process, without shelling out
to `audit-coverage`.

This spec adds:
- auto-audit (always-on) on `python -m polytool scan`
- auto-audit flags to control sampling
- run manifest wiring for the emitted audit artifact
- fee-sanity hardening in audit quick stats and red flags

`SPEC-0007` remains the base contract for audit report structure; this spec
defines the delta.

---

## CLI Changes

Canonical command (always emits audit with all positions):

```bash
python -m polytool scan --user "@example"
```

To limit the audit to N positions (deterministic sample):

```bash
python -m polytool scan --user "@example" --audit-sample 25 --audit-seed 1337
```

New optional flags:

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--audit-sample` | int | No | Limit audit to N positions. **Omit = all positions (default).** |
| `--audit-seed` | int | No | Deterministic sample seed used with `--audit-sample` (default `1337`). |

Validation:
- `--audit-sample` must be a non-negative integer when provided.
- `--audit-seed` must be an integer when provided.

---

## Artifact Emission

`scan` always writes the audit report into the run root:

```
artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/audit_coverage_report.md
```

Implementation requirement:
- call the existing audit report generator logic in-process
- do not shell out to a subprocess

---

## Manifest Contract

When auto-audit runs, `run_manifest.json` must include:

```json
{
  "output_paths": {
    "audit_coverage_report_md": "artifacts/dossiers/users/<slug>/<wallet>/<YYYY-MM-DD>/<run_id>/audit_coverage_report.md"
  }
}
```

Path must be POSIX-normalized.

---

## Fee-Sanity Hardening

Audit quick stats must include:

- `positive_pnl_with_zero_fee_count`

Definition:
- count of positions where `gross_pnl > 0` and raw `fees_estimated == 0`

Audit red flags must include a warning when the count is greater than zero.

Audit markdown must include a short explanatory note:
- fees are estimated only when `gross_pnl > 0`
- losses, zero-PnL, and pending rows intentionally show `fees_estimated = 0`

---

## Determinism

For a fixed input run and seed, sampled positions in the audit report must be
stable across repeated runs.

---

## Non-Goals

- adding network dependencies to audit generation
- changing coverage reconciliation schema
