# RIS n8n Truth Docs Closeout -- 2026-04-06

**Quick ID:** 260406-mnu
**Scope:** Docs-only. No code, config, workflow JSON, or docker-compose runtime changes.

## Why This Was Needed

Several high-authority project docs (CLAUDE.md, ARCHITECTURE.md, PLAN_OF_RECORD.md,
CURRENT_STATE.md) contained blanket statements like "No n8n orchestration until Phase 3"
that became false once the RIS n8n pilot (ADR 0013) was shipped and runtime-verified on
n8n 2.14.2. README.md also directed users to the dead `simtrader` branch, which was
consolidated into main on 2026-04-06.

These stale statements would mislead future Claude sessions and human operators into
thinking no n8n tooling existed in the repo.

---

## Contradictions Found and Resolved

| File | Line(s) | Old Statement | Problem | New Statement |
|------|---------|---------------|---------|---------------|
| CLAUDE.md | 41 | "No n8n orchestration until Phase 3." | False -- RIS n8n pilot is shipped (ADR 0013, n8n 2.14.2) | Broad orchestration deferred to Phase 3; scoped pilot shipped and opt-in via `--profile ris-n8n` |
| CLAUDE.md | 119 | "Phase 1 uses cron / APScheduler; Phase 3 may add n8n." | Stale -- n8n already handles RIS ingestion scheduling | APScheduler is default scheduler; scoped n8n pilot handles RIS workflows (opt-in, see ADR 0013); broad n8n is Phase 3 target |
| docs/ARCHITECTURE.md | 15 | Control plane row: "The repo is still CLI-first and local-first. `services/api/` exists, but the broad v4 wrapper surface and n8n control plane are not current architecture truth." | Omits the RIS n8n pilot entirely | Row now mentions RIS n8n pilot (ADR 0013, n8n 2.14.2) via `--profile ris-n8n` while preserving "broad v4 wrapper surface and full n8n control plane are not current architecture truth" |
| docs/PLAN_OF_RECORD.md | 18 | "the broader automation stack is not current-state truth yet" | Omits that RIS n8n IS truth for the RIS subsystem specifically | Acknowledges scoped RIS pilot (ADR 0013) for RIS ingestion workflows only; broader stack (full control plane, Discord ops, AWS) still not truth |
| docs/CURRENT_STATE.md | 18 | "no n8n orchestration layer" | Contradicted by RIS n8n sections elsewhere in same file | Qualified to "no broad n8n orchestration layer" plus parenthetical exception for scoped RIS pilot (ADR 0013) |
| README.md | 71-78 | "git checkout simtrader" / "Do not use main -- it is behind." | simtrader branch is dead; repo consolidated to main-only on 2026-04-06 | Removed branch checkout; added main-only note |
| docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md | 679 | "n8n is deferred to Phase 3" with no exception or qualification | True for broad orchestration, but misleading without pilot footnote | Added blockquote note referencing ADR 0013 pilot (shipped, opt-in, RIS-only) and clarifying it does not constitute Phase 3 broad orchestration |

---

## Final Truth Statement

```
RIS n8n pilot (ADR 0013) status as of 2026-04-06:

- SHIPPED: 11 workflow templates, n8n 2.14.2, docker-beside-docker bridge pattern
- SCOPE: RIS ingestion workflows only (research-scheduler run-job, health, status, manual acquire)
- ACTIVATION: opt-in via --profile ris-n8n (never starts in default compose stack)
- DEFAULT SCHEDULER: APScheduler remains the default for all scheduling
- NOT SHIPPED: broad Phase 3 n8n control plane, Discord approval, strategy automation, full FastAPI wrapper
- OPERATOR GUIDE: docs/RIS_OPERATOR_GUIDE.md
- ADR: docs/adr/0013-ris-n8n-pilot-scoped.md
```

---

## Files Changed

### Task 1: Contradiction fixes (7 files, commit 3433ef5)

1. `CLAUDE.md` -- 2 edits (lines 41 and 119)
2. `docs/ARCHITECTURE.md` -- 1 edit (control plane row)
3. `docs/PLAN_OF_RECORD.md` -- 1 edit (automation/hosting row)
4. `docs/CURRENT_STATE.md` -- 1 edit (Roadmap Items Not Yet Implemented bullet)
5. `README.md` -- 1 edit (Step 1.2 clone block)
6. `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` -- 1 addition (pilot footnote after line 679)

### Task 2: This dev log

7. `docs/dev_logs/2026-04-06_ris_n8n_truth_docs_closeout.md` -- created

---

## Verification Commands Run

```
grep -c "No n8n orchestration until Phase 3" CLAUDE.md
# Result: 0  (GOOD -- stale phrase removed)

grep -c "Phase 3 may add n8n" CLAUDE.md
# Result: 0  (GOOD -- stale phrase removed)

grep -c "git checkout simtrader" README.md
# Result: 0  (GOOD -- dead branch reference removed)

grep -c "scoped RIS n8n pilot" CLAUDE.md docs/ARCHITECTURE.md docs/PLAN_OF_RECORD.md docs/CURRENT_STATE.md
# Result: CLAUDE.md:1, docs/ARCHITECTURE.md:1, docs/PLAN_OF_RECORD.md:1, docs/CURRENT_STATE.md:1  (GOOD)

grep -c "ADR 0013" CLAUDE.md docs/ARCHITECTURE.md
# Result: CLAUDE.md:2, docs/ARCHITECTURE.md:1  (GOOD)
```

---

## What Was NOT Changed

- `docs/adr/0013-ris-n8n-pilot-scoped.md` -- already correct per prior reconciliation passes
- `docs/RIS_OPERATOR_GUIDE.md` -- already reconciled in quick-260404-uav and quick-260405-g4j
- `.claude/*` -- out of scope per constraints
- Code files, infra/n8n workflow JSON, docker-compose.yml -- out of scope
- Roadmap phase structure and strategy -- preserved as-is; only a footnote added to v5_1.md

---

## Codex Review

Tier: Skip (docs-only, no execution/strategy/risk logic).
