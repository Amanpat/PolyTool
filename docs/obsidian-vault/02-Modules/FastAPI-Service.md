---
type: module
status: partial
tags: [module, status/partial, fastapi]
lines: 3054
test-coverage: none
created: 2026-04-08
---

# FastAPI Service

Source: audit Section 1.8 — `services/api/main.py` (3054 lines).

Thin HTTP wrapper over the core Python library. The largest single file in the project after `simtrader.py` CLI.

**Status: ISLAND** — code exists, no test coverage, no CLI routing, not integrated into standard workflows. See [[Issue-FastAPI-Island]].

---

## Key Facts

- Location: `services/api/main.py`
- Lines: 3054
- Test coverage: zero tests
- No test file in `tests/` references this module
- Not reachable from `python -m polytool` CLI

---

## Design Principle (from CLAUDE.md)

FastAPI is intended as a thin HTTP layer for automation (Phase 3). No business logic should live in FastAPI handlers — all logic belongs in the Python core library.

**The FastAPI layer is a Phase 3 deliverable.** Do not build frontend or API layers before the raw CLI paths work end-to-end and the project is profitable.

---

## Cross-References

- [[Issue-FastAPI-Island]] — Zero test coverage issue
- [[Core-Library]] — Core library that FastAPI wraps
- [[System-Overview]] — Layer roles description

