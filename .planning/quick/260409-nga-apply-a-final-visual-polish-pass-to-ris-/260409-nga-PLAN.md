---
phase: quick-260409-nga
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/n8n/workflows/ris-unified-dev.json
  - docs/runbooks/RIS_DISCORD_ALERTS.md
  - docs/dev_logs/2026-04-09_discord_embed_final_polish.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "No embed ever shows 'n/a' or empty placeholder values"
    - "Exit code field only appears when a real exit code exists"
    - "Ingest failure title communicates severity and what failed"
    - "Pipeline error title communicates severity and section name"
    - "Health alert title includes severity level indicator"
    - "URLs in ingest failures are presented cleanly, not as a dominant raw line"
    - "Footer is compact and consistent across all alert types"
    - "Daily summary retains digest tone, not alarm tone"
  artifacts:
    - path: "infra/n8n/workflows/ris-unified-dev.json"
      provides: "Polished embed formatting in all 10 format nodes"
    - path: "docs/runbooks/RIS_DISCORD_ALERTS.md"
      provides: "Updated format reference matching new embed style"
    - path: "docs/dev_logs/2026-04-09_discord_embed_final_polish.md"
      provides: "Change record with before/after and test results"
  key_links:
    - from: "infra/n8n/workflows/ris-unified-dev.json"
      to: "Discord webhook"
      via: "Operator: Send Webhook node posts embeds array"
      pattern: "embeds.*webhookUrl"
---

<objective>
Apply final visual polish to all Discord embed format nodes in the RIS unified n8n workflow.

Purpose: Eliminate noisy placeholders (`n/a`, `none`), improve severity signaling in titles, clean up URL presentation in ingest failures, make fields denser and more professional across health, pipeline error, ingest failure, and daily summary embeds.

Output: Patched `ris-unified-dev.json` with cleaner embeds, updated alert style guide, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@infra/n8n/workflows/ris-unified-dev.json
@infra/n8n/import_workflows.py
@docs/runbooks/RIS_DISCORD_ALERTS.md
@docs/dev_logs/2026-04-09_discord_alert_layout_refinement.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Polish all embed format nodes in ris-unified-dev.json</name>
  <files>infra/n8n/workflows/ris-unified-dev.json</files>
  <action>
Write a Python patch script (`infra/n8n/_patch_polish.py`) that loads the workflow JSON, locates each format node by ID, and replaces its `jsCode` with the polished version. Delete the script after running it. Apply these changes to each node category:

**A. Ingest failure node (`s9-fmt-err` / "Ingest: Format Fail"):**

Current problems: description shows `Exit: n/a` when exitCode is absent, URL is a dominant full-width field, title is generic.

Polished jsCode logic:
- Title: Use severity-prefixed format. Change from `'RIS Ingest Failed'` to a template that includes the source family: `'Ingest Failed: {source_family}'` (capitalize family, e.g. "Ingest Failed: Blog").
- Description: Drop the `Exit: n/a` pattern entirely. Build description conditionally:
  - If exitCode exists and is not null/undefined: `"Exit code ${exitCode} | Family: ${family}"`
  - Otherwise just: `"Family: ${family}"`
  - This eliminates the noisy `n/a`.
- URL field: Instead of a full-width non-inline field with name "URL", make it a masked markdown link in the description or a shorter field. Use: `{ name: 'Source', value: urlDisplay, inline: true }` where `urlDisplay` truncates URLs over 60 chars to show domain + `...` + last 20 chars (e.g. `arxiv.org/abs/...01345`). For very short URLs (<=60 chars), show the full URL.
- Error field: Keep as non-inline but rename from `'Error'` to `'Detail'`.
- Footer: Keep `'RIS | ingest'` (drop `ris-unified-dev` from footer -- it adds no operator value).
- IMPORTANT: Preserve the `...statusPayload` spread in the return so `Ingest: Respond 500` still gets its fields.

**B. Pipeline error nodes (6 nodes: `s2-format-err` through `s7-format-err`):**

Current problems: title is plain, `'none'` fallback is noisy, stderr/stdout labels are bare technical names.

Polished jsCode logic for ALL 6 nodes (same pattern, different section name):
- Title: Change from `'RIS Pipeline Error: {section}'` to `'Pipeline Error: {section}'` with section name title-cased (e.g., `'Pipeline Error: Academic'` not `'Pipeline Error: academic_ingest'`). Use a clean display name mapping: `academic_ingest`->`Academic`, `reddit_polymarket`->`Reddit`, `blog_ingest`->`Blog`, `youtube_ingest`->`YouTube`, `github_ingest`->`GitHub`, `freshness_refresh`->`Freshness`.
- Description: Change from `'Exit code: ${exitCode}'` to `'Exit ${exitCode}'` (shorter).
- Fields: Only include stderr field if stderr is non-empty after trimming (eliminate `'none'` fallback). Only include stdout tail field if stdoutTail is non-empty. Rename field names from bare `'stderr'` to `'Error Output'` and from `'stdout (tail)'` to `'Last Output'`.
- Footer: Shorten to `'RIS | {section_display}'` (drop `ris-unified-dev`).

**C. Health alert node (`s1-format-alert` / "Health: Format Alert"):**

Current problems: `n/a` in stats fields, description repeats field data, title is plain.

Polished jsCode logic:
- Title: Keep `'RIS Health: ${status}'` -- this already communicates severity well.
- Description: Simplify to just the actionable summary. Instead of `"${runCount} runs | ${totalDocs} docs | ${errors} ingest errors"`, use a shorter problem-first line: If there are actionable checks, show the top check name. Otherwise just show the status. E.g. `"pipeline_error detected"` or `"2 checks need attention"`.
- Fields: Remove `n/a` fallbacks. For each stat field, only include it if the value is a real number (not null/undefined). Specifically: `if (stats.totalDocs != null)` before adding the Docs field, etc. This means when stats command fails, you get fewer but cleaner fields instead of a wall of `n/a`.
- Actionable Checks field: Prefix each check line with a severity marker: `"[RED]"` or `"[YLW]"` instead of bare status text.
- Command Exit field: Already conditional -- keep as-is.
- Footer: Shorten to `'RIS | health'`.

**D. Daily summary format node (`s8-parse` / "Summary: Format Message"):**

Current problems: description repeats field data redundantly.

Polished jsCode logic:
- Title: Keep `'RIS Daily Summary'` for digest tone.
- Description: Simplify to just health status: `"Health: ${healthSummary}"`. Drop the redundant `| ${totalDocs} docs | ${runCount} runs` since those are in fields.
- Fields: Keep current field set, it is already good. No `n/a` values appear here since this branch only runs when stats command succeeds.
- Footer: Shorten to `'RIS | daily-summary'`.

**E. Summary error node (`s8-format-err` / "Summary: Format Error"):**

Polished jsCode logic:
- Title: Keep `'RIS Summary Error'`.
- Rename field from bare `'stderr'` to `'Error Output'`.
- Footer: Shorten to `'RIS | daily-summary'`.

**Implementation approach:**
1. Write `infra/n8n/_patch_polish.py` that:
   - Loads `infra/n8n/workflows/ris-unified-dev.json`
   - For each node ID listed above, finds the node in the `nodes` array
   - Replaces the `jsCode` in `parameters` with the polished version
   - Writes the file back with `json.dumps(data, indent=2)` + trailing newline
   - Prints each patched node name for confirmation
2. Run the script: `python infra/n8n/_patch_polish.py`
3. Validate JSON: `python -m json.tool infra/n8n/workflows/ris-unified-dev.json > /dev/null`
4. Delete the script: `rm infra/n8n/_patch_polish.py`
  </action>
  <verify>
    <automated>python -m json.tool infra/n8n/workflows/ris-unified-dev.json > /dev/null 2>&1 && echo "JSON valid" || echo "JSON INVALID"</automated>
    After patching, grep the workflow JSON to confirm:
    - No remaining literal `'n/a'` in any jsCode field value assignments
    - No remaining literal `'none'` as a field value fallback
    - Footer strings no longer contain `ris-unified-dev`
    - Ingest node description does not contain `Exit: n/a` pattern
  </verify>
  <done>
    All 10 format nodes patched. No `n/a` placeholders in field values. Exit code shown only when present. Titles communicate severity/section clearly. URLs truncated cleanly. Footers compact. JSON validates.
  </done>
</task>

<task type="auto">
  <name>Task 2: Re-import workflow + update docs + create dev log</name>
  <files>docs/runbooks/RIS_DISCORD_ALERTS.md, docs/dev_logs/2026-04-09_discord_embed_final_polish.md</files>
  <action>
**A. Re-import the workflow:**
```
python infra/n8n/import_workflows.py
```
Confirm output shows `updated` for `ris-unified-dev.json`.

**B. Test ingest failure path:**
```
curl -s -X POST "http://localhost:5678/webhook/ris-ingest" \
  -H "Content-Type: application/json" \
  -d '{"url":"http://127.0.0.1:9/final-polish-test","source_family":"blog"}'
```
Capture the response JSON. Verify:
- Title is `"Ingest Failed: Blog"` (not `"RIS Ingest Failed"`)
- Description does NOT contain `Exit: n/a`
- Source field shows cleaned URL
- Footer is `"RIS | ingest"` (not `"RIS | ris-unified-dev | ingest"`)

**C. Update `docs/runbooks/RIS_DISCORD_ALERTS.md`:**
Update the Message Format Reference section to reflect the new embed styling:
- Ingest failure format: new title pattern, conditional exit, cleaner URL
- Pipeline error format: title-cased section name, conditional fields, renamed labels
- Health alert format: problem-first description, conditional stats fields
- Daily summary format: simplified description
- Update the footer pattern description to note `ris-unified-dev` was dropped

Keep changes minimal -- just update the format examples and field descriptions to match reality. Do NOT restructure the document.

**D. Create dev log `docs/dev_logs/2026-04-09_discord_embed_final_polish.md`:**
Include:
- Summary of what changed (visual polish pass on Discord embeds)
- Files changed list
- Design choices (no n/a, conditional fields, severity in titles, shorter footers, URL truncation)
- Before/after comparison for each alert type (ingest, pipeline, health, summary)
- Commands run and output (patch script, JSON validation, import, curl test)
- Test results table
- Codex review: Skip (workflow JSON + docs only, no execution code)
  </action>
  <verify>
    <automated>python -c "import json; d=json.load(open('infra/n8n/workflows/ris-unified-dev.json')); print('nodes:', len(d.get('nodes',[]))); print('JSON OK')"</automated>
    Import completes without error. Curl test response shows new embed format. Dev log exists at expected path. Alert style guide format examples match actual node output.
  </verify>
  <done>
    Workflow re-imported and active. Ingest failure test confirms cleaner embed format in Discord. RIS_DISCORD_ALERTS.md format reference updated. Dev log created with before/after and test results.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

No trust boundaries affected. This change modifies only Discord embed formatting (cosmetic). No new inputs, no auth changes, no data flow changes.

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | I (Information Disclosure) | Discord embed URL field | accept | URLs sent to Discord are already public/operator-visible; truncation reduces visual noise but does not hide content |
</threat_model>

<verification>
1. `python -m json.tool infra/n8n/workflows/ris-unified-dev.json > /dev/null` -- JSON valid
2. `python infra/n8n/import_workflows.py` -- import succeeds
3. Ingest failure curl test shows new embed format (no `n/a`, cleaner title/footer)
4. Grep workflow JSON for remaining `n/a` in field value assignments -- none found
</verification>

<success_criteria>
- All 10 embed format nodes polished (no `n/a`, no `none`, conditional fields, severity in titles)
- Workflow re-imported and active in n8n
- At least one alert path tested via curl with cleaner output confirmed
- RIS_DISCORD_ALERTS.md updated to match new format
- Dev log created with before/after and test results
</success_criteria>

<output>
After completion, create `.planning/quick/260409-nga-apply-a-final-visual-polish-pass-to-ris-/260409-nga-SUMMARY.md`
</output>
