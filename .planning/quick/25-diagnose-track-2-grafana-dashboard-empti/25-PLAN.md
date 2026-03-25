---
phase: quick-025
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json
  - docs/features/FEATURE-crypto-pair-grafana-panels-v1.md
  - docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md
autonomous: true
requirements: [PHASE1A-OPS-VISIBILITY]
must_haves:
  truths:
    - "Operator knows definitively whether emptiness is caused by zero rows vs broken infrastructure"
    - "Dashboard panels display a clear human-readable message when no Track 2 events exist"
    - "A dev log records all diagnostic findings and the path to seeing live data"
  artifacts:
    - path: "infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json"
      provides: "Updated dashboard with noDataText on all 12 panels"
    - path: "docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md"
      provides: "Root-cause diagnosis and operator remediation steps"
  key_links:
    - from: "docker-compose.yml volumes"
      to: "infra/grafana/dashboards/ -> /var/lib/grafana/dashboards:ro"
      via: "bind mount"
      pattern: "grafana/dashboards.*dashboards:ro"
    - from: "infra/grafana/provisioning/dashboards/dashboards.yaml"
      to: "path: /var/lib/grafana/dashboards"
      via: "Grafana file provider"
      pattern: "path: /var/lib/grafana/dashboards"
    - from: "Dashboard panels"
      to: "polytool.crypto_pair_events"
      via: "datasource uid clickhouse-polytool"
      pattern: "clickhouse-polytool"
---

<objective>
Diagnose why the Crypto Pair Paper Soak Grafana dashboard is empty and improve operator experience when no Track 2 data exists.

Purpose: Distinguish infrastructure failure from expected no-data state; give the operator actionable messaging instead of silent blank panels.
Output: Dev log with root-cause verdict, updated dashboard JSON with noDataText on all 12 panels, updated feature doc noting the limitation.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json
@D:/Coding Projects/Polymarket/PolyTool/docs/features/FEATURE-crypto-pair-grafana-panels-v1.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/SPEC-crypto-pair-clickhouse-event-schema-v0.md
@D:/Coding Projects/Polymarket/PolyTool/infra/clickhouse/initdb/26_crypto_pair_events.sql

## Pre-Planning Diagnostic Findings (read before executing tasks)

### Infrastructure chain — VERIFIED CORRECT
The provisioning chain from the JSON file to Grafana is intact and requires no changes:

1. `docker-compose.yml` bind-mounts `./infra/grafana/dashboards` -> `/var/lib/grafana/dashboards:ro`
2. `./infra/grafana/provisioning` -> `/etc/grafana/provisioning:ro`
3. `infra/grafana/provisioning/dashboards/dashboards.yaml` configures `type: file`, `path: /var/lib/grafana/dashboards`, `updateIntervalSeconds: 30`
4. All 12 panels use `datasource.uid: "clickhouse-polytool"` which exactly matches `infra/grafana/provisioning/datasources/clickhouse.yaml` uid field
5. `infra/clickhouse/initdb/26_crypto_pair_events.sql` is in the initdb directory that the migrate service runs at startup
6. The table DDL creates `polytool.crypto_pair_events` with `ReplacingMergeTree` and GRANTs SELECT to `grafana_ro`
7. Datasource authenticates as `grafana_ro` with password `grafana_readonly_local` — matches the GRANT in the DDL

### Root cause — CONFIRMED: Zero rows (not broken infrastructure)
- Quick-022: Binance HTTP 451 geo-block; sink was enabled but run aborted before finalization
- Quick-023: Coinbase feed confirmed working but Polymarket had zero active BTC/ETH/SOL 5m/15m markets; runner exited before any pairs could be observed; sink enabled but no events written
- Quick-024: Market availability watcher only — no paper run executed
- Result: `polytool.crypto_pair_events` table exists (created by migrate service) but contains zero rows

### What the dashboard looks like right now
All 12 panels silently show blank / "No data" in Grafana's default grey message. No panel explains WHY there is no data. An operator cannot distinguish:
- "ClickHouse is unreachable"
- "Table does not exist"
- "Table exists but sink was disabled / no eligible markets"

### What needs to change
Add `noDataText` to every panel's `options` block. Grafana table and timeseries panels support this field. The text should tell the operator: no Track 2 events have been written yet, the most likely causes, and the fastest remediation.

Suggested noDataText (use verbatim or close):
```
No Track 2 events yet. Causes: (1) sink disabled — rerun with --sink-enabled, (2) no eligible BTC/ETH/SOL 5m-15m markets — run crypto-pair-watch --watch, (3) Docker not running. Table: polytool.crypto_pair_events
```

### Panel types in the dashboard
- Panels 1, 2, 3, 4, 5, 8, 12: `"type": "table"` — use `options.noDataText`
- Panels 7, 9, 10, 11: `"type": "timeseries"` — use `options.noDataText`
- Panel 6: `"type": "barchart"` — use `options.noDataText`

All 12 panels have an `options` object already. Add `"noDataText": "..."` to each.
</context>

<tasks>

<task type="auto">
  <name>Task 1: Run ClickHouse diagnostic and confirm row count</name>
  <files>docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md</files>
  <action>
Run the following ClickHouse diagnostic commands via curl (HTTP interface, port 8123). If Docker is not running, note that in the dev log — that itself is a finding.

```bash
# Check if ClickHouse is reachable
curl -s "http://localhost:8123/?query=SELECT%201" --user grafana_ro:grafana_readonly_local

# Check if table exists
curl -s "http://localhost:8123/?query=SELECT%20name%20FROM%20system.tables%20WHERE%20database%3D'polytool'%20AND%20name%3D'crypto_pair_events'" --user grafana_ro:grafana_readonly_local

# Count rows
curl -s "http://localhost:8123/?query=SELECT%20count()%20FROM%20polytool.crypto_pair_events" --user grafana_ro:grafana_readonly_local

# If rows exist, show distinct run_ids and event_types
curl -s "http://localhost:8123/?query=SELECT%20run_id%2C%20event_type%2C%20count()%20FROM%20polytool.crypto_pair_events%20GROUP%20BY%20run_id%2C%20event_type%20ORDER%20BY%20run_id" --user grafana_ro:grafana_readonly_local
```

Write the dev log at `docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md` with:

1. **Diagnostic Summary** — date, scope, what was checked
2. **Infrastructure Findings** (for each item below, state PASS/FAIL and actual result):
   - ClickHouse HTTP reachability (port 8123)
   - Table `polytool.crypto_pair_events` existence
   - Row count in table
   - Datasource UID match: `clickhouse-polytool` (provisioning vs dashboard JSON)
   - Dashboard provisioning path: `infra/grafana/dashboards/` -> `/var/lib/grafana/dashboards:ro`
   - `dashboards.yaml` provider path matches Docker mount
3. **Root Cause Verdict** — one sentence: "The dashboard is empty because [reason]."
4. **Soak History** — brief timeline of quick-022, quick-023, quick-024 with why no rows landed
5. **Path to Live Data** — exact sequence:
   a. Wait for BTC/ETH/SOL 5m-15m markets (use `python -m polytool crypto-pair-watch --watch --timeout 3600`)
   b. Launch paper run with `--sink-enabled` flag
   c. Run must reach finalization (not abort mid-run)
   d. After finalization, check `run_manifest.json["sink_write_result"]`
   e. Reload Grafana dashboard (auto-reloads every 30s already)
6. **What Was Changed** — note that `noDataText` was added to all 12 panels (Task 2)
7. **Open Questions / Next Steps** — none expected; leave blank if none

If Docker is not running: record that finding, skip the curl commands, note the infrastructure chain is correct by code review, and proceed to Task 2.
  </action>
  <verify>
File `docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md` exists and contains a "Root Cause Verdict" section with a verdict sentence.
  </verify>
  <done>Dev log exists with diagnostic findings, root cause verdict (confirmed: zero rows due to no eligible markets + sink not enabled during successful runs), and path to live data steps.</done>
</task>

<task type="auto">
  <name>Task 2: Add noDataText to all 12 dashboard panels</name>
  <files>infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json</files>
  <action>
Read `infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json` in full. For every panel object (there are 12, with `"id"` values 1 through 12), add the following field to the existing `options` object:

```json
"noDataText": "No Track 2 events yet. Causes: (1) sink disabled — rerun with --sink-enabled, (2) no eligible BTC/ETH/SOL 5m-15m markets — run crypto-pair-watch --watch, (3) Docker not running. Table: polytool.crypto_pair_events"
```

Rules:
- Add `noDataText` as a key inside the existing `"options": { ... }` block on each panel — do NOT create a new options block
- Do not modify any SQL in `rawSql` fields
- Do not change panel types, grid positions, datasource references, titles, or any other field
- Do not add or remove panels
- The JSON must remain valid (use a JSON validator mentally — no trailing commas, proper quoting)
- Write the complete updated file back to `infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json`

After writing, verify the JSON is syntactically valid by running:
```bash
python -c "import json; json.load(open('infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json'))" && echo "JSON valid"
```

If invalid, fix the JSON before proceeding.
  </action>
  <verify>
    <automated>python -c "import json; data=json.load(open('D:/Coding Projects/Polymarket/PolyTool/infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json')); panels=data['panels']; assert len(panels)==12, f'Expected 12 panels, got {len(panels)}'; missing=[p['id'] for p in panels if 'noDataText' not in p.get('options',{})]; assert not missing, f'Missing noDataText on panel ids: {missing}'; print(f'All 12 panels have noDataText. JSON valid.')"</automated>
  </verify>
  <done>All 12 panels have `noDataText` in their options block. JSON parses cleanly. Dashboard still provisions correctly (provisioning is file-based with 30s reload — no restart needed).</done>
</task>

<task type="auto">
  <name>Task 3: Update feature doc with no-data operator guidance</name>
  <files>docs/features/FEATURE-crypto-pair-grafana-panels-v1.md</files>
  <action>
Read `docs/features/FEATURE-crypto-pair-grafana-panels-v1.md`. Add a new section after the existing "Limitations" section titled `## No-Data Operator Guide`. Do not modify any existing content — only append this new section.

Content for the new section:

```markdown
## No-Data Operator Guide

If the dashboard shows blank panels or the "No Track 2 events yet" message,
work through this checklist in order:

**1. Confirm Docker is running**
```bash
docker compose ps
```
All services (clickhouse, grafana) must show `healthy`.

**2. Confirm the table exists and has rows**
```bash
curl -s "http://localhost:8123/?query=SELECT%20count()%20FROM%20polytool.crypto_pair_events" \
  --user grafana_ro:grafana_readonly_local
```
Expected: `0` (table exists, no rows yet) vs an error (table missing or
ClickHouse unreachable). If the table is missing, the migrate service did
not run — restart with `docker compose up migrate`.

**3. Understand why rows are absent**

The sink writes events only at paper run finalization, and only when:
- The paper run was launched with `--sink-enabled`
- At least one market was observed (non-zero eligible markets)
- The run reached finalization without aborting

Track 2 soaks as of 2026-03-25 had zero eligible BTC/ETH/SOL 5m-15m markets.
No rows will appear until markets are available and a complete soak finishes.

**4. Wait for markets, then re-soak**

```bash
# Poll until markets are available (exits 0 when found)
python -m polytool crypto-pair-watch --watch --timeout 3600

# Then run a paper soak with sink enabled
python -m polytool crypto-pair-run --sink-enabled [other flags]
```

After finalization, check `run_manifest.json["sink_write_result"]` for the
write outcome. The Grafana dashboard reloads automatically every 30 seconds.

**5. Time range**

The default dashboard range is `now-7d`. If the soak ran more than 7 days
ago, widen the time picker.
```

Write the updated file back to `docs/features/FEATURE-crypto-pair-grafana-panels-v1.md`.
  </action>
  <verify>File contains "## No-Data Operator Guide" section and the word "crypto-pair-watch".</verify>
  <done>Feature doc updated with operator remediation guide. No existing content removed or altered.</done>
</task>

</tasks>

<verification>
```bash
# 1. Dev log exists
ls -la "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md"

# 2. Dashboard JSON is valid and has noDataText on all 12 panels
python -c "
import json
data = json.load(open('D:/Coding Projects/Polymarket/PolyTool/infra/grafana/dashboards/polyttool_crypto_pair_paper_soak.json'))
panels = data['panels']
assert len(panels) == 12
missing = [p['id'] for p in panels if 'noDataText' not in p.get('options', {})]
assert not missing, f'Missing noDataText on panel ids: {missing}'
print(f'PASS: All 12 panels have noDataText. JSON valid.')
"

# 3. Feature doc has new section
grep -c "No-Data Operator Guide" "D:/Coding Projects/Polymarket/PolyTool/docs/features/FEATURE-crypto-pair-grafana-panels-v1.md"
```
</verification>

<success_criteria>
- Root cause diagnosed and recorded: `polytool.crypto_pair_events` table exists but has zero rows because all soaks either aborted early (Binance 451, zero eligible markets) or ran without `--sink-enabled`
- All 12 Grafana panels display `noDataText` explaining the no-data state and pointing to remediation steps
- Dashboard JSON passes Python JSON parse validation
- Feature doc includes the operator no-data checklist
- Dev log written at `docs/dev_logs/2026-03-25_phase1a_grafana_no_data_diagnostics.md`
- No trading logic, Gate 2 files, or market-maker code touched
</success_criteria>

<output>
After completion, create `.planning/quick/25-diagnose-track-2-grafana-dashboard-empti/25-SUMMARY.md` following the summary template.
</output>
