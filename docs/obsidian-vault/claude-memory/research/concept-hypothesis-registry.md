---
title: "Hypothesis Registry"
type: concept
status: superseded
superseded_by: repo-docs/specs/spec-hypothesis-registry-v0.md
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: stale
tags: [module, status/done, hypothesis]
---

# Hypothesis Registry

Source: audit Section 1.1 — two separate registries coexist. See [[legacy/PolyTool/07-Issues/Issue-Duplicate-Hypothesis-Registry]].

---

## Two Registries

| Registry | Location | Backend | Purpose |
|----------|----------|---------|---------|
| Polymarket hypothesis registry | `packages/polymarket/hypotheses/` | JSON-backed | Strategy and wallet behavior hypotheses |
| Research hypothesis registry | `packages/research/hypotheses/registry.py` (409 lines) | SQLite-backed | Research finding hypotheses |

These registries overlap conceptually. The JSON-backed one is used by the `hypothesis` CLI commands. The SQLite-backed one is part of RIS.

---

## CLI Commands (JSON-backed registry)

| Command | Description |
|---------|-------------|
| `hypothesis register` | Register new hypothesis |
| `hypothesis status` | Show hypothesis status |
| `hypothesis experiment-init` | Initialize experiment |
| `hypothesis experiment-run` | Run experiment |
| `hypothesis validate` | Validate hypothesis results |
| `hypothesis diff` | Diff hypothesis versions |
| `hypothesis summary` | Hypothesis summary |

Note: hypothesis subcommands use `_FULL_ARGV_COMMANDS` in `polytool/__main__.py` — full `sys.argv` is passed through.

---

## Cross-References

- [[legacy/PolyTool/02-Modules/RIS]] — Research Intelligence System contains the SQLite-backed registry
- [[legacy/PolyTool/07-Issues/Issue-Duplicate-Hypothesis-Registry]] — Duplication issue details

## Connections

- [[claude-memory/research/_index]]
- [[index|Vault Home]]
- [[repo-docs/_index]]
