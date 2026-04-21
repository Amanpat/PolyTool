# 2026-04-08 n8n operator path cleanup

## Objective

Finish the minimum operator-facing n8n cleanup so real operators have one truthful path:

- canonical workflow: `workflows/n8n/ris-unified-dev.json`
- canonical import command: `python infra/n8n/import_workflows.py`
- smoke path: `GET /webhook/ris-health` and `POST /webhook/ris-ingest`
- APScheduler remains the default scheduler
- n8n Execute Command nodes use `polytool-ris-scheduler` as the exec bridge

## Files changed and why

| File | Why |
|------|-----|
| `infra/n8n/README.md` | Added the single compact operator quickstart and aligned import/activation wording with the Python importer and unified workflow set. |
| `workflows/n8n/README.md` | Pointed operators to the canonical quickstart, kept workflow-structure detail, and demoted manual REST deployment to LEGACY / REFERENCE-ONLY. |
| `docs/runbooks/RIS_N8N_SMOKE_TEST.md` | Rewrote the stale smoke runbook around the real operator path and explicitly marked the old repo-side smoke script / legacy workflow directory as reference-only. |
| `docs/RIS_OPERATOR_GUIDE.md` | Reconciled the n8n section to the current import/start/smoke path and clarified that APScheduler remains the default unless schedule triggers are intentionally enabled in n8n. |
| `docs/README.md` | Added an obvious docs-hub pointer to the canonical n8n operator path. |

## Commands run + output

| Command | Output / result |
|---------|-----------------|
| `git status --short` | Dirty worktree already present in unrelated research/test files; avoided touching unrelated changes. |
| `git grep -n -I -E "..." -- README.md docs/*.md docs/runbooks/*.md infra/n8n/*.md workflows/n8n/*.md` | Found the active stale operator references in `docs/RIS_OPERATOR_GUIDE.md`, `docs/runbooks/RIS_N8N_SMOKE_TEST.md`, and `workflows/n8n/README.md`; final search left only intentional non-operator references in `docs/CURRENT_STATE.md` and ADR-0013. |
| `python infra/n8n/import_workflows.py --help` | Exit 0. Printed usage for `--base-url`, `--api-key`, and `--no-activate`; confirms the canonical import command is present and documented correctly. |
| `git diff -- infra/n8n/README.md workflows/n8n/README.md docs/runbooks/RIS_N8N_SMOKE_TEST.md docs/RIS_OPERATOR_GUIDE.md docs/README.md` | Confirmed the change set stayed doc-only and limited to the operator-facing n8n surface. |

## Test results

| Check | Result |
|------|--------|
| Active operator docs searched for stale n8n instructions | PASS |
| Canonical importer command exists and is helpable | PASS |
| Final docs all point to `workflows/n8n/ris-unified-dev.json` + `python infra/n8n/import_workflows.py` + `/webhook/ris-health` + `/webhook/ris-ingest` | PASS |
| Live import / live webhook smoke rerun in this task | NOT RUN |

Notes:

- Live n8n runtime was not re-executed in this docs-only cleanup.
- The current verified runtime state remained the one already established in `docs/dev_logs/2026-04-08_n8n_runtime_debug_and_smoke.md`.

## Final canonical operator path

1. `docker compose up -d`
2. `docker compose --profile ris-n8n up -d n8n`
3. `python infra/n8n/import_workflows.py`
4. `curl http://localhost:5678/healthz`
5. `curl http://localhost:5678/webhook/ris-health`
6. `curl -X POST http://localhost:5678/webhook/ris-ingest -H "Content-Type: application/json" -d '{"url":"https://arxiv.org/abs/2106.01345","source_family":"academic"}'`

Operator intent:

- Leave APScheduler running for the normal path.
- n8n uses `polytool-ris-scheduler` as the exec bridge.
- Only stop `ris-scheduler` if you intentionally enable n8n schedule triggers and want n8n to own recurring scheduling.

## Intentionally unpatched legacy references

| Location | Why left alone |
|----------|----------------|
| `docs/CURRENT_STATE.md` | Status/history document, not the operator quickstart or runbook surface. It still mentions the older shell helper and legacy workflow directory; outside the minimum operator-facing cleanup requested here. |
| `docs/adr/0013-ris-n8n-pilot-scoped.md` | ADR / decision record, not the active operator runbook. It preserves historical startup/import wording from the original pilot decision. |
| `scripts/smoke_ris_n8n.py` | Script itself still validates the superseded `infra/n8n/workflows/` surface. Updating runtime tooling was explicitly out of scope; the active smoke runbook now marks it LEGACY / REFERENCE-ONLY instead of treating it as current truth. |
