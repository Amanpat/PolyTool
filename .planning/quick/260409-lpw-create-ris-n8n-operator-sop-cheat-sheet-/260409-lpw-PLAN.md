---
phase: quick-260409-lpw
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/runbooks/RIS_N8N_OPERATOR_SOP.md
  - docs/dev_logs/2026-04-09_ris_n8n_operator_sop_cheatsheet.md
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/README.md
  - infra/n8n/README.md
  - docs/runbooks/RIS_N8N_SMOKE_TEST.md
autonomous: true
must_haves:
  truths:
    - "Operator can find a single compact cheat sheet with exact commands for all RIS+n8n operator tasks"
    - "Cheat sheet covers startup, import, health, ingest, review queue, monitoring, Discord alert troubleshooting, and common mistakes"
    - "Active docs (RIS_OPERATOR_GUIDE, infra/n8n/README, docs/README, RIS_N8N_SMOKE_TEST) reference the new SOP instead of duplicating instructions"
    - "Scoped-pilot boundary (ADR 0013) is explicitly stated in the cheat sheet"
  artifacts:
    - path: "docs/runbooks/RIS_N8N_OPERATOR_SOP.md"
      provides: "Compact one-page operator SOP cheat sheet for RIS+n8n pilot"
    - path: "docs/dev_logs/2026-04-09_ris_n8n_operator_sop_cheatsheet.md"
      provides: "Mandatory dev log for this work unit"
  key_links:
    - from: "docs/RIS_OPERATOR_GUIDE.md"
      to: "docs/runbooks/RIS_N8N_OPERATOR_SOP.md"
      via: "Cross-reference link in n8n RIS Pilot section"
    - from: "docs/README.md"
      to: "docs/runbooks/RIS_N8N_OPERATOR_SOP.md"
      via: "Entry in Workflows section"
    - from: "infra/n8n/README.md"
      to: "docs/runbooks/RIS_N8N_OPERATOR_SOP.md"
      via: "Cross-reference in Related Docs section"
---

<objective>
Create a concise one-page RIS+n8n operator SOP cheat sheet and align active docs to reference it.

Purpose: The RIS+n8n pilot has detailed instructions scattered across RIS_OPERATOR_GUIDE.md (890 lines), infra/n8n/README.md, and RIS_N8N_SMOKE_TEST.md. Operators need a single compact command-driven reference they can keep open during daily work. Active docs should point to this SOP rather than duplicating drift-prone instructions.

Output: One new cheat sheet runbook, one dev log, and minimal cross-reference edits in 4 existing docs.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/RIS_OPERATOR_GUIDE.md (lines 596-845: "n8n RIS Pilot" section — source of truth for all n8n commands)
@infra/n8n/README.md (canonical n8n infrastructure reference)
@docs/runbooks/RIS_N8N_SMOKE_TEST.md (pre-import validation runbook)
@docs/README.md (documentation hub — Workflows section needs new entry)
@docs/features/FEATURE-ris-phase2-closeout.md (Phase 2 closeout status — context for what is shipped)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create RIS_N8N_OPERATOR_SOP.md cheat sheet</name>
  <files>docs/runbooks/RIS_N8N_OPERATOR_SOP.md</files>
  <action>
Create a new file `docs/runbooks/RIS_N8N_OPERATOR_SOP.md` — a compact, command-driven operator SOP cheat sheet for the RIS+n8n pilot.

Structure the cheat sheet with these exact sections (use H2 headings):

1. **Header** — Title: "RIS + n8n Operator SOP Cheat Sheet". One-line scope note: "Scoped to RIS ingestion only per ADR 0013. NOT Phase 3 automation." Include "Last verified: 2026-04-09".

2. **Startup** — Exact commands to bring up the default stack and n8n sidecar:
   - `docker compose up -d` (default stack with APScheduler)
   - `docker compose --profile ris-n8n up -d n8n` (n8n sidecar)
   - `curl -s http://localhost:5678/healthz` (verify n8n up, expect `{"status":"ok"}`)
   - Note: APScheduler and n8n run side-by-side by default. Only stop APScheduler if you enable n8n schedule triggers (`docker compose stop ris-scheduler`).

3. **Import / Re-import Workflows** — Single canonical command:
   - `python infra/n8n/import_workflows.py`
   - Note what it does: imports ris-unified-dev.json + ris-health-webhook.json, updates workflow_ids.env, activates both. Requires N8N_API_KEY in .env.

4. **Health Check** — Two paths:
   - Webhook: `curl http://localhost:5678/webhook/ris-health`
   - CLI: `python -m polytool research-health`
   - Stats: `python -m polytool research-stats summary`

5. **Ingest Test** — Webhook ingest smoke:
   - `curl -X POST "http://localhost:5678/webhook/ris-ingest" -H "Content-Type: application/json" -d '{"url":"https://arxiv.org/abs/2106.01345","source_family":"academic"}'`
   - Valid source_family values: academic, github, blog, news, book, reddit, youtube

6. **Review Queue** — CLI commands:
   - `python -m polytool research-review list`
   - `python -m polytool research-review accept <doc_id>`
   - `python -m polytool research-review reject <doc_id>`
   - `python -m polytool research-review defer <doc_id>`

7. **Monitoring Commands** — Table format:
   - research-health, research-stats summary, research-scheduler status
   - n8n UI at http://localhost:5678

8. **Discord Alert Troubleshooting**:
   - Discord alerting is NOT wired to RIS alert sink by default. RIS uses LogSink.
   - To use Discord: configure WebhookSink manually. Set DISCORD_WEBHOOK_URL in .env.
   - n8n workflow failure alerts go through n8n's built-in error handling (settings.errorWorkflow), not the polytool Discord module.

9. **Common Mistakes** — Bullet list:
   - Running both APScheduler and n8n schedule triggers = double-scheduling
   - Missing N8N_API_KEY in .env = import_workflows.py fails
   - Bare `python -m polytool` inside n8n container = fails (no Python). All nodes must use `docker exec polytool-ris-scheduler python -m polytool ...`
   - Invalid --source-family value on webhook ingest
   - n8n not started (profile not activated) = curl connection refused on port 5678
   - First-time n8n: must complete owner setup at http://localhost:5678/setup

10. **Related Docs** — Links table:
    - docs/RIS_OPERATOR_GUIDE.md (full guide)
    - infra/n8n/README.md (n8n infrastructure)
    - docs/runbooks/RIS_N8N_SMOKE_TEST.md (pre-import repo validation)
    - docs/adr/0013-ris-n8n-pilot-scoped.md (scope decision)

Keep the whole file under 120 lines. Use code blocks for every command. No prose paragraphs — bullet points and tables only. The operator should be able to scan this in under 2 minutes.
  </action>
  <verify>
    <automated>python -c "p='docs/runbooks/RIS_N8N_OPERATOR_SOP.md'; f=open(p); lines=f.readlines(); f.close(); sections=['Startup','Import','Health','Ingest','Review Queue','Monitoring','Discord','Common Mistakes','Related Docs']; found=[s for s in sections if any(s.lower() in l.lower() for l in lines)]; missing=[s for s in sections if s not in found]; lc=len(lines); assert lc>0, 'File empty'; assert lc<=150, f'Too long: {lc} lines'; assert len(missing)==0, f'Missing sections: {missing}'; print(f'OK: {lc} lines, all {len(found)} sections present')"</automated>
  </verify>
  <done>docs/runbooks/RIS_N8N_OPERATOR_SOP.md exists, is under 150 lines, and contains all 9 required sections with exact operator commands</done>
</task>

<task type="auto">
  <name>Task 2: Cross-reference active docs and create dev log</name>
  <files>docs/RIS_OPERATOR_GUIDE.md, docs/README.md, infra/n8n/README.md, docs/runbooks/RIS_N8N_SMOKE_TEST.md, docs/dev_logs/2026-04-09_ris_n8n_operator_sop_cheatsheet.md</files>
  <action>
Make minimal edits to 4 existing docs to cross-reference the new SOP. Do NOT rewrite sections — add only a cross-reference line or bullet.

**docs/RIS_OPERATOR_GUIDE.md:**
- At the top of the "n8n RIS Pilot (Opt-In)" section (line ~596, after the scope boundary note), add a callout line:
  `> **Quick reference:** For a compact command cheat sheet, see [RIS + n8n Operator SOP](runbooks/RIS_N8N_OPERATOR_SOP.md).`

**infra/n8n/README.md:**
- In the "Related Docs" section at the bottom (line ~96), add a new bullet:
  `- Operator SOP cheat sheet: \`docs/runbooks/RIS_N8N_OPERATOR_SOP.md\``

**docs/README.md:**
- In the "Workflows" section (around line 53-59), add a new entry after the "RIS n8n operator path" line:
  `- [RIS + n8n Operator SOP cheat sheet](runbooks/RIS_N8N_OPERATOR_SOP.md) - Compact command reference for daily RIS+n8n operations`

**docs/runbooks/RIS_N8N_SMOKE_TEST.md:**
- In the "Related Documentation" section at the bottom (line ~170), add:
  `- \`docs/runbooks/RIS_N8N_OPERATOR_SOP.md\` -- Compact operator SOP cheat sheet`

**Dev log (NEW):**
Create `docs/dev_logs/2026-04-09_ris_n8n_operator_sop_cheatsheet.md` with:
- Title: "RIS + n8n Operator SOP Cheat Sheet"
- Date: 2026-04-09
- Scope: docs-only, no code/workflow/test changes
- What was created: new SOP cheat sheet at docs/runbooks/RIS_N8N_OPERATOR_SOP.md
- What was updated: 4 docs received cross-reference links (list them)
- Source material: distilled from RIS_OPERATOR_GUIDE.md (n8n section), infra/n8n/README.md, RIS_N8N_SMOKE_TEST.md
- Design decision: cheat sheet is command-driven, under 150 lines, references full docs for detail. Does not duplicate instructions — references them.
  </action>
  <verify>
    <automated>python -c "import os; files=['docs/RIS_OPERATOR_GUIDE.md','docs/README.md','infra/n8n/README.md','docs/runbooks/RIS_N8N_SMOKE_TEST.md','docs/dev_logs/2026-04-09_ris_n8n_operator_sop_cheatsheet.md']; missing=[f for f in files if not os.path.exists(f)]; assert not missing, f'Missing: {missing}'; sop_ref_count=0; check_files=files[:4]; [sop_ref_count:=sop_ref_count+1 for f in check_files if 'RIS_N8N_OPERATOR_SOP' in open(f).read()]; assert sop_ref_count==4, f'Only {sop_ref_count}/4 docs reference the SOP'; print(f'OK: dev log exists, {sop_ref_count}/4 docs cross-reference SOP')"</automated>
  </verify>
  <done>All 4 active docs contain a cross-reference to docs/runbooks/RIS_N8N_OPERATOR_SOP.md and the dev log exists at docs/dev_logs/2026-04-09_ris_n8n_operator_sop_cheatsheet.md</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries — this is a docs-only change with no code, no secrets, and no runtime impact.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-lpw-01 | I (Information Disclosure) | SOP cheat sheet | accept | Cheat sheet contains only localhost URLs and public CLI commands; no secrets, no webhook auth tokens. The existing smoke test runbook already notes that full webhook URLs contain auth tokens and should not be shared. |
</threat_model>

<verification>
- docs/runbooks/RIS_N8N_OPERATOR_SOP.md exists and is under 150 lines
- All 9 required sections are present in the cheat sheet
- docs/RIS_OPERATOR_GUIDE.md, docs/README.md, infra/n8n/README.md, docs/runbooks/RIS_N8N_SMOKE_TEST.md all contain cross-references to the new SOP
- docs/dev_logs/2026-04-09_ris_n8n_operator_sop_cheatsheet.md exists
- No code, workflow JSON, test, or Docker files were modified
</verification>

<success_criteria>
- One compact cheat sheet exists at docs/runbooks/RIS_N8N_OPERATOR_SOP.md with exact commands for all 9 operator task categories
- Active docs point to the SOP rather than duplicating drift-prone instructions
- Scoped-pilot boundary (ADR 0013) is clearly stated
- Dev log documents the work unit
</success_criteria>

<output>
After completion, create `.planning/quick/260409-lpw-create-ris-n8n-operator-sop-cheat-sheet-/260409-lpw-SUMMARY.md`
</output>
