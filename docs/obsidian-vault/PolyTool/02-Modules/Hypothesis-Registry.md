---
type: module
status: done
tags: [module, status/done, hypothesis]
lines: ~450
test-coverage: partial
created: 2026-04-08
---

# Hypothesis Registry

Source: audit Section 1.1 — two separate registries coexist. See [[Issue-Duplicate-Hypothesis-Registry]].

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

- [[RIS]] — Research Intelligence System contains the SQLite-backed registry
- [[Issue-Duplicate-Hypothesis-Registry]] — Duplication issue details

