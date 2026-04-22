---
type: issue
severity: low
status: open
tags: [issue, fastapi, testing, status/open]
created: 2026-04-08
---

# Issue: FastAPI Island (Zero Test Coverage)

Source: audit Section 6.2 and audit note 3.

`services/api/main.py` is 3054 lines with zero test coverage and no CLI routing.

---

## Details

| File | Lines | Tests | CLI Route |
|------|-------|-------|-----------|
| `services/api/main.py` | 3054 | ZERO | None |

---

## Why It's an Island

- No test file in `tests/` references this module
- Not reachable from `python -m polytool` CLI
- Appears to be pre-built infrastructure without test coverage
- Per CLAUDE.md: "No custom frontend is needed pre-profit. FastAPI is a Phase 3 deliverable."

---

## Risk

Low for now (not in production, not reachable). Risk increases if it gets deployed before test coverage is added — 3054 lines of untested FastAPI handlers could have silent bugs in auth, routing, or data transformation.

---

## Resolution

- Do not bring this online before Phase 3
- When Phase 3 begins, add test coverage before activating any endpoint
- Per CLAUDE.md: FastAPI handlers should be thin wrappers only — no business logic

---

## Cross-References

- [[FastAPI-Service]] — Module detail
- [[Phase-3-Hybrid-RAG-Kalshi-n8n]] — When FastAPI becomes a Phase 3 deliverable

