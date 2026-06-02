---
title: "Issue: Duplicate Hypothesis Registry"
type: reference
status: archived
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: archived
tags: [issue, hypothesis, status/open]
---

# Issue: Duplicate Hypothesis Registry

Source: audit Section 7.6.

Two hypothesis registry modules coexist with different backends.

---

## Affected Files

| Registry | Location | Backend | Lines |
|----------|----------|---------|-------|
| Polymarket hypothesis registry | `packages/polymarket/hypotheses/registry.py` | JSON-backed | — |
| Research hypothesis registry | `packages/research/hypotheses/registry.py` | SQLite-backed | 409 |

---

## Current Usage

The CLI (`tools/cli/hypothesis.py`) appears to use the research package (SQLite-backed) version. The polymarket package version may be legacy or parallel.

---

## Risk

- Two code paths for hypothesis management create confusion about which is authoritative
- If the JSON-backed version is legacy, it may have diverged in API contract
- New code may accidentally use the wrong registry

---

## Resolution

1. Determine which registry the CLI actually uses (inspect `tools/cli/hypothesis.py`)
2. If the JSON-backed version is legacy, deprecate and remove it
3. If both are active, document their distinct purposes clearly

---

## Cross-References

- [[legacy/PolyTool/02-Modules/Hypothesis-Registry]] — Hypothesis registry module detail
- [[legacy/PolyTool/02-Modules/RIS]] — Research package containing SQLite-backed registry

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
