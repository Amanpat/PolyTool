---
type: phase
phase: 0
status: partial
tags: [phase, status/partial]
created: 2026-04-08
---

# Phase 0 — Accounts and Setup

Source: roadmap v5.1 Phase 0 — Context Rebuild and Operator Setup.

---

## Checklist

- [x] **Write `docs/OPERATOR_SETUP_GUIDE.md`** — account setup, wallet architecture, fund flow, capital allocation rules, tax tracking, infrastructure setup
- [ ] **Polymarket account setup** — fund account, test withdrawal cycle, document fees and steps
- [ ] **Wallet architecture setup** — cold wallet (capital storage) and hot wallet (trading only) with API key derivation
- [ ] **Canadian dev partner environment setup** — clone, install, Docker, dry-run verification
- [ ] **Windows development gotchas document** — PowerShell encoding, Docker WSL2 permissions, path separators, `.env` encoding
- [ ] **Document external data paths in CLAUDE.md** — Jon-Becker (36GB) and pmxt archive paths

---

## Key Notes

- Phase 0 is never fully "done" — setup tasks can be completed in any order
- Operator setup guide written; wallet and account items remain open
- CLAUDE.md documents known Windows gotchas

---

## Cross-References

- [[System-Overview]] — Infrastructure requirements
- [[Database-Rules]] — ClickHouse auth pattern required from setup

