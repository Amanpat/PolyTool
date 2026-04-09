# 2026-04-09 RIS Discord Alert Ops Documentation

## Summary

Created `docs/runbooks/RIS_DISCORD_ALERTS.md` — a compact operator reference for RIS Discord alert formats and verification procedure. Added minimal cross-links from `docs/runbooks/RIS_N8N_OPERATOR_SOP.md` and `infra/n8n/README.md`.

## Motivation

The 2026-04-09 Discord alert integration debug session (see `docs/dev_logs/2026-04-09_discord_alert_integration_debug.md`) established that:

1. The import-time placeholder injection is now working correctly.
2. The ingest failure path is the easiest alert to force and verify.
3. The `EAI_AGAIN` transient DNS error pattern is known and benign.

Without a locked reference doc, future workflow changes could silently regress alert message formats without any operator noticing until an actual incident. The new runbook locks in the intended formats as explicit golden examples and gives operators exact verification steps.

## Files created

- `docs/runbooks/RIS_DISCORD_ALERTS.md` — 157 lines; all 4 alert types, severity table, verification procedure, common failures

## Files modified

- `docs/runbooks/RIS_N8N_OPERATOR_SOP.md` — added cross-link in Discord Alert Troubleshooting section and Related Docs table
- `infra/n8n/README.md` — added bullet in Related Docs section

## Codex review

Not applicable — docs-only change with no code, no secrets, no runtime behavior.

## Open questions

None. Alert integration is confirmed working as of 2026-04-09.
