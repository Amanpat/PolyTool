---
type: index
tags: [index, issues]
created: 2026-04-08
---

# Issues Index

All known code issues from `docs/CODEBASE_AUDIT.md` Section 7. Nine findings mapped 1:1 to individual issue notes in `07-Issues/`.

---

## Summary

The audit identified 9 structural issues: 2 high severity, 5 medium severity, and 2 low severity. None are blockers for Phase 1A/1B progress but should be addressed before live capital deployment.

---

## Dataview — All Issue Notes

```dataview
TABLE severity, affected-modules
FROM "07-Issues"
SORT severity DESC
```

---

## Quick Reference

| Issue | Severity | Summary |
|-------|----------|---------|
| [[Issue-CH-Auth-Violations]] | high | Silent password fallback violates CLAUDE.md auth rule |
| [[Issue-Dual-Fee-Modules]] | medium | Float vs Decimal fee formula duplication — risk of drift |
| [[Issue-Duplicate-WebSocket-Code]] | medium | Four independent WS reconnect loops, no shared base class |
| [[Issue-Duplicate-Hypothesis-Registry]] | medium | JSON-backed and SQLite-backed registries both exist |
| [[Issue-Pyproject-Packaging-Gap]] | medium | 5 research subpackages not in pyproject.toml packages list |
| [[Issue-Multiple-HTTP-Clients]] | low | Three HTTP client approaches coexist |
| [[Issue-Multiple-Config-Loaders]] | low | Three config loading patterns coexist |
| [[Issue-Dead-Opportunities-Stub]] | low | 22-line stub dataclass unused |
| [[Issue-FastAPI-Island]] | low | 3054-line FastAPI service with zero tests |

---

## Prioritization Notes

- **Fix before live capital:** [[Issue-CH-Auth-Violations]] — a silent auth fallback could cause live trading commands to run against the wrong ClickHouse database.
- **Fix before strategy scaling:** [[Issue-Dual-Fee-Modules]] — fee model drift between core and SimTrader portfolio will cause PnL discrepancies at scale.
- **Fix before clean install deployment:** [[Issue-Pyproject-Packaging-Gap]] — research subpackages won't install correctly without project root on sys.path.
