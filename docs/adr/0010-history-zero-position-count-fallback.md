# ADR-0010: Scan Fallback for History Count/Body Position Mismatch

Date: 2026-02-18  
Status: Accepted

## Context

`scan` hydrates dossier artifacts using:

- `/api/export/user_dossier`
- `/api/export/user_dossier/history` (with `include_body=true`) when local/latest payload is empty or export indicates empty

We observed history rows where:

- row-level `positions_count` was `0`
- but `dossier_json` declared positions and included non-empty position rows

Without a fallback policy, coverage/audit could be computed from empty inputs.

## Decision

When history row count metadata conflicts with dossier body content:

- Prefer history rows that contain actual position rows (`positions_len > 0`) over count-only rows.
- If history reports `positions_count=0` but dossier body declares positions and contains rows, use dossier body rows for coverage inputs.
- Always emit a warning in coverage warnings and stderr that includes:
  - both endpoints used
  - export/history counts
  - dossier declared count and row count

## Rationale

- The dossier body is the concrete payload consumed by coverage and audit.
- Count metadata can drift independently during regressions.
- Explicit warning keeps failures visible and actionable, so fallback does not hide upstream bugs.

## Consequences

- Coverage/audit stay usable when body rows exist despite count mismatch.
- Operators still see a high-signal warning to investigate export lifecycle/schema issues.
