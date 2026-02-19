# Feature: Scan Auto Audit

## What this does

`scan` always emits `audit_coverage_report.md` as part of every run — no extra
flags required.  By default the report includes **all positions** (see
[ADR-0011](../adr/0011-audit-default-all-positions.md) for the decision record).

The audit is generated in-process from local artifacts. No shell-out, no
network calls.

---

## Usage

```bash
# All positions (default — always emitted):
python -m polytool scan \
  --user "@example" \
  --ingest-positions \
  --compute-pnl \
  --enrich-resolutions

# Limit audit to 25 positions (deterministic sample):
python -m polytool scan \
  --user "@example" \
  --ingest-positions \
  --compute-pnl \
  --enrich-resolutions \
  --audit-sample 25 \
  --audit-seed 1337
```

Result:
- `audit_coverage_report.md` is written into the scan run root (always)
- `run_manifest.json` includes `output_paths.audit_coverage_report_md` (always)

---

## Fee-Sanity Improvement

Audit quick stats now include:
- `positive_pnl_with_zero_fee_count`

When this count is non-zero, the Red Flags section includes a warning so fee
estimation gaps are visible immediately.

The report also includes a short note clarifying fee semantics:
- fees are estimated only for positive `gross_pnl`
- losses/zero/pending rows intentionally keep `fees_estimated=0`

---

## Related Spec

- `docs/specs/SPEC-0008-scan-auto-audit.md`
- `docs/specs/SPEC-0007-audit-coverage-cli.md`
