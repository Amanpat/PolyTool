---
date: 2026-04-23
slug: ris_phase2a_operator_guide
type: docs
scope: docs-only
feature: RIS Operational Readiness — Phase 2A
---

# RIS Phase 2A — Operator Guide Creation

**Date:** 2026-04-23
**Type:** Documentation-only
**Operator:** Aman

---

## Objective

Create a single operator-facing runbook for RIS Phase 2A (WP1–WP5) that answers
"How do I use what we built?" and link it from docs/INDEX.md.

---

## Files Changed and Why

| File | Change | Reason |
|---|---|---|
| `docs/runbooks/RIS_PHASE2A_OPERATOR_GUIDE.md` | Created | New runbook covering activation, validation, daily use, monitoring, and deferred items |
| `docs/INDEX.md` | Added one row in the Runbooks table | Discoverable link to the new guide |
| `docs/dev_logs/2026-04-23_ris_phase2a_operator_guide.md` | Created (this file) | Mandatory dev log per repo policy |

---

## Sections Added to the Runbook

| Section | Source of truth used |
|---|---|
| What Phase 2A Includes | `docs/features/ris_operational_readiness_phase2a.md`, `docs/dev_logs/2026-04-23_ris_phase2a_acceptance_pass.md` |
| Prerequisites | `docs/dev_logs/2026-04-23_ris_phase2a_acceptance_pass.md` (Step prerequisites block) |
| First-Time Activation (Steps 1–6) | `2026-04-23_ris_wp4b_activation_plumbing.md` (exact 7-step operator procedure), `2026-04-23_ris_wp4c_grafana_dashboard.md` (auto-provisioning), `2026-04-23_ris_wp4d_stale_pipeline_alert.md` (Grafana restart + contact point steps) |
| Validation Run (V1–V7) | `2026-04-23_ris_phase2a_acceptance_pass.md` (Steps 1–11 condensed to the 7 verification checks) |
| Day-to-Day Usage | `docs/runbooks/RIS_OPERATOR_GUIDE.md` (existing commands); `2026-04-23_ris_wp2j_cli_truth_sync.md` (compare, list-providers); `2026-04-23_ris_wp5d_baseline_save.md` (--save-baseline) |
| Monitoring Surfaces | `2026-04-23_ris_wp4c_grafana_dashboard.md` (4 panels); `2026-04-23_ris_wp4d_stale_pipeline_alert.md` (alert rule); `ris_operational_readiness_phase2a.md` (WP3 Discord embeds) |
| Key Files | `docs/features/ris_operational_readiness_phase2a.md` (Key Files table) |
| Deferred / Not in Phase 2A | `2026-04-23_ris_phase2a_acceptance_pass.md` (Deferred / Non-Blocking Items table) |
| Troubleshooting | Derived from known activation prerequisites documented in WP4-B activation log |

---

## Commands Verified for Inclusion

All commands verified by checking they appear in current dev logs or existing runbooks:

| Command | Verification source |
|---|---|
| `python -m polytool research-health` | Acceptance pass Step 9; existing RIS_OPERATOR_GUIDE.md |
| `python -m polytool research-stats summary` | Existing RIS_OPERATOR_GUIDE.md |
| `python -m polytool research-eval --provider gemini --enable-cloud` | Acceptance pass Step 8; WP2-J log |
| `python -m polytool research-eval list-providers` | WP2-J dev log |
| `python -m polytool research-eval compare --provider-a gemini --provider-b deepseek` | WP2-J dev log |
| `python -m polytool rag-eval --suite ... --save-baseline` | Acceptance pass Step 7; WP5-D dev log |
| `python -m polytool research-review list/accept/reject` | Existing RIS_OPERATOR_GUIDE.md |
| `python -m polytool research-precheck run --idea "..."` | Existing RIS_OPERATOR_GUIDE.md |
| `python infra/n8n/import_workflows.py --no-activate` | WP4-B activation plumbing log |
| `docker compose up -d` / `docker compose restart grafana` | WP4-D dev log |

---

## Commands Run + Exact Results

```
python -m polytool --help
```
**Result:** Exit 0. CLI loads cleanly. `rag-eval`, `research-eval`, `research-health`, `research-stats` all visible.

---

## Remaining Doc Gaps

None identified. The following items are explicitly called out as deferred in the runbook itself:

- Phase 2B provider runbook (OpenRouter, Groq, Ollama) — not yet needed
- WP6 friend contribution guide — Phase 2B trigger condition not yet met

---

**Codex review tier:** Skip — documentation-only, no application code changed.
