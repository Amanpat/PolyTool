# 2026-04-09 Obsidian Vault Sync to Shipped Phase 2 RIS + n8n Truth

## Summary
Synced 6 existing Obsidian vault notes and created 1 new decision note to reflect the Phase 2 RIS conditional close, shipped n8n pilot, Discord embed alerting, and canonical workflow locations as of 2026-04-09.

## Files changed

### Updated
- `docs/obsidian-vault/00-Index/Dashboard.md` — Phase 2 status changed from "partial" to "conditionally closed"
- `docs/obsidian-vault/02-Modules/RIS.md` — Added n8n pilot section, Phase 2 shipped capabilities, decision note cross-reference
- `docs/obsidian-vault/02-Modules/Notifications.md` — Added n8n Discord alerting distinction section
- `docs/obsidian-vault/05-Roadmap/Phase-2-Discovery-Engine.md` — Status changed to conditionally-closed, added shipped/deferred breakdown
- `docs/obsidian-vault/05-Roadmap/Phase-3-Hybrid-RAG-Kalshi-n8n.md` — Expanded n8n pilot context, added decision note link
- `docs/obsidian-vault/08-Research/00-INDEX.md` — Added Phase 2 conditional close decision log entry

### Created
- `docs/obsidian-vault/09-Decisions/Decision - RIS n8n Pilot Scope.md` — Pilot boundary, canonical paths, APScheduler default, migration rationale

## Source of truth
All updates sourced from:
- `docs/CURRENT_STATE.md` lines 1667-1684 (RIS Phase 2 conditional close)
- `docs/runbooks/RIS_N8N_OPERATOR_SOP.md` (canonical operator flow)
- `docs/runbooks/RIS_DISCORD_ALERTS.md` (embed format)
- `docs/dev_logs/2026-04-09_docs_and_ops_final_reconcile.md` (reconcile pass)

## Codex review
- Tier: Skip (vault docs only, no execution code)
