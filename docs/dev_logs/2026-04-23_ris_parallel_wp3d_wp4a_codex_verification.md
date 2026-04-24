# RIS Parallel WP3-D / WP4-A Codex Verification

**Date:** 2026-04-23  
**Scope:** Read-only verification of two active Phase 2A lanes after landing/presence in the workspace.  
**Mutation made by Codex:** This verification log only.

## Files Inspected

- `infra/n8n/workflows/ris-unified-dev.json`
- `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`
- `infra/clickhouse/initdb/26_crypto_pair_events.sql`
- `infra/clickhouse/initdb/27_wallet_discovery.sql`
- `docs/dev_logs/2026-04-23_ris_wp3d_discord_embeds.md`
- `docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md`

Note: the prompt referenced `infra/clickhouse/initdb/n8n_execution_metrics.sql`; that exact unnumbered path does not exist. The present WP4-A file is `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`, which matches the existing numbered ClickHouse initdb convention.

## Commands Run and Results

```powershell
git status --short
```

Result:

```text
?? docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md
?? infra/clickhouse/initdb/28_n8n_execution_metrics.sql
```

```powershell
git log --oneline -5
```

Result:

```text
2eaefd8 feat(ris): WP3-D - Discord embed enrichment with per-pipeline fields
129d376 RIS improvement
a610f18 Hermes Agent containerization
05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts
0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix
```

```powershell
python -m polytool --help
```

Result: exit 0. CLI rendered the PolyTool help surface beginning with `PolyTool - Polymarket analysis toolchain` and no traceback/import error.

```powershell
Test-Path infra/clickhouse/initdb/n8n_execution_metrics.sql
```

Result:

```text
False
```

```powershell
Get-ChildItem -Name infra/clickhouse/initdb | Sort-Object
```

Result: showed existing numbered init scripts from `01_init.sql` through `28_n8n_execution_metrics.sql`.

```powershell
git show --stat --name-only --oneline HEAD -- infra/n8n/workflows/ris-unified-dev.json docs/dev_logs/2026-04-23_ris_wp3d_discord_embeds.md
```

Result:

```text
2eaefd8 feat(ris): WP3-D - Discord embed enrichment with per-pipeline fields
docs/dev_logs/2026-04-23_ris_wp3d_discord_embeds.md
infra/n8n/workflows/ris-unified-dev.json
```

```powershell
git diff --stat
git diff --name-only
git diff -- infra/n8n/workflows/ris-unified-dev.json
```

Result: all three commands produced no output; no tracked working-tree diff was present for the workflow after the WP3-D commit.

```powershell
git show --stat HEAD -- infra/n8n/workflows/ris-unified-dev.json
```

Result:

```text
infra/n8n/workflows/ris-unified-dev.json | 14 +++++++-------
1 file changed, 7 insertions(+), 7 deletions(-)
```

```powershell
@'
import json
import subprocess
from pathlib import Path

p = 'infra/n8n/workflows/ris-unified-dev.json'
old = json.loads(subprocess.check_output(['git', 'show', f'HEAD^:{p}'], text=True, encoding='utf-8'))
new = json.loads(Path(p).read_text(encoding='utf-8'))
old_nodes = {n['id']: n for n in old['nodes']}
new_nodes = {n['id']: n for n in new['nodes']}
changed_js = []
changed_nodes = []
for nid in sorted(set(old_nodes) & set(new_nodes)):
    if old_nodes[nid] != new_nodes[nid]:
        changed_nodes.append((nid, new_nodes[nid].get('name')))
    old_js = (old_nodes[nid].get('parameters') or {}).get('jsCode')
    new_js = (new_nodes[nid].get('parameters') or {}).get('jsCode')
    if old_js != new_js:
        changed_js.append((nid, new_nodes[nid].get('name')))
print(f"old_nodes={len(old_nodes)} new_nodes={len(new_nodes)}")
print(f"old_connections={len(old.get('connections', {}))} new_connections={len(new.get('connections', {}))}")
print(f"added_nodes={sorted(set(new_nodes) - set(old_nodes))}")
print(f"removed_nodes={sorted(set(old_nodes) - set(new_nodes))}")
print(f"connections_changed={old.get('connections') != new.get('connections')}")
print('changed_nodes=' + '; '.join(f'{nid} ({name})' for nid, name in changed_nodes))
print('changed_js=' + '; '.join(f'{nid} ({name})' for nid, name in changed_js))
'@ | python -
```

Result:

```text
old_nodes=76 new_nodes=76
old_connections=56 new_connections=56
added_nodes=[]
removed_nodes=[]
connections_changed=False
changed_nodes=s1-format-alert (Health: Format Alert); s2-format-err (Academic: Format Error); s3-format-err (Reddit: Format Error); s4-format-err (Blog: Format Error); s5-format-err (YouTube: Format Error); s6-format-err (GitHub: Format Error); s7-format-err (Freshness: Format Error)
changed_js=s1-format-alert (Health: Format Alert); s2-format-err (Academic: Format Error); s3-format-err (Reddit: Format Error); s4-format-err (Blog: Format Error); s5-format-err (YouTube: Format Error); s6-format-err (GitHub: Format Error); s7-format-err (Freshness: Format Error)
```

```powershell
$p = 'infra/n8n/workflows/ris-unified-dev.json'
$wf = Get-Content -Raw -LiteralPath $p | ConvertFrom-Json
Write-Output ("JSON OK: {0}; nodes={1}" -f $p, $wf.nodes.Count)
```

Result:

```text
JSON OK: infra/n8n/workflows/ris-unified-dev.json; nodes=76
```

```powershell
@'
const fs = require('fs');
const wf = JSON.parse(fs.readFileSync('infra/n8n/workflows/ris-unified-dev.json', 'utf8'));
const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
const targetIds = [
  's1-format-alert',
  's2-format-err',
  's3-format-err',
  's4-format-err',
  's5-format-err',
  's6-format-err',
  's7-format-err',
];
let failures = 0;
for (const id of targetIds) {
  const node = wf.nodes.find((n) => n.id === id);
  if (!node) {
    console.log(`JS MISSING: ${id}`);
    failures += 1;
    continue;
  }
  try {
    new AsyncFunction('$input', '$json', '$node', '$items', 'items', 'item', node.parameters.jsCode || '');
    console.log(`JS OK: ${id} (${node.name})`);
  } catch (err) {
    console.log(`JS FAIL: ${id} (${node.name}): ${err.message}`);
    failures += 1;
  }
}
if (failures > 0) process.exit(1);
'@ | node -
```

Result:

```text
JS OK: s1-format-alert (Health: Format Alert)
JS OK: s2-format-err (Academic: Format Error)
JS OK: s3-format-err (Reddit: Format Error)
JS OK: s4-format-err (Blog: Format Error)
JS OK: s5-format-err (YouTube: Format Error)
JS OK: s6-format-err (GitHub: Format Error)
JS OK: s7-format-err (Freshness: Format Error)
```

```powershell
@'
import json
from pathlib import Path
wf = json.loads(Path('infra/n8n/workflows/ris-unified-dev.json').read_text(encoding='utf-8'))
for node_id in ['s1-format-alert','s2-format-err','s3-format-err','s4-format-err','s5-format-err','s6-format-err','s7-format-err']:
    node = next(n for n in wf['nodes'] if n['id'] == node_id)
    js = node['parameters']['jsCode']
    has_embeds = 'embeds: [embed]' in js
    has_webhook = 'webhookUrl' in js and 'notifyEnabled' in js
    if node_id == 's1-format-alert':
        details = [
            'Pipelines' if "name: 'Pipelines'" in js else 'missing Pipelines',
            'Knowledge Store' if "name: 'Knowledge Store'" in js else 'missing Knowledge Store',
            'Review Queue' if "name: 'Review Queue'" in js else 'missing Review Queue',
            'overallCategory' if 'overallCategory' in js else 'missing overallCategory',
        ]
    else:
        details = [
            'partialAccepted' if 'partialAccepted' in js else 'missing partialAccepted',
            'partialRejected' if 'partialRejected' in js else 'missing partialRejected',
            'status_label' if 'status_label' in js else 'missing status_label',
        ]
    print(f"{node_id}: embeds={has_embeds}; webhook={has_webhook}; " + ', '.join(details))
'@ | python -
```

Result:

```text
s1-format-alert: embeds=True; webhook=True; Pipelines, Knowledge Store, Review Queue, overallCategory
s2-format-err: embeds=True; webhook=True; partialAccepted, partialRejected, status_label
s3-format-err: embeds=True; webhook=True; partialAccepted, partialRejected, status_label
s4-format-err: embeds=True; webhook=True; partialAccepted, partialRejected, status_label
s5-format-err: embeds=True; webhook=True; partialAccepted, partialRejected, status_label
s6-format-err: embeds=True; webhook=True; partialAccepted, partialRejected, status_label
s7-format-err: embeds=True; webhook=True; partialAccepted, partialRejected, status_label
```

```powershell
@'
from pathlib import Path
sql = Path('infra/clickhouse/initdb/28_n8n_execution_metrics.sql').read_text(encoding='utf-8')
checks = {
    'create_table': 'CREATE TABLE IF NOT EXISTS polytool.n8n_execution_metrics' in sql,
    'engine_replacing': 'ENGINE = ReplacingMergeTree(collected_at)' in sql,
    'order_by_execution_id': 'ORDER BY execution_id' in sql,
    'partition_by_month': 'PARTITION BY toYYYYMM(started_at)' in sql,
    'ttl_90_days': 'TTL started_at + INTERVAL 90 DAY' in sql,
    'grafana_grant': 'GRANT SELECT ON polytool.n8n_execution_metrics TO grafana_ro' in sql,
    'no_insert': 'INSERT ' not in sql.upper(),
    'no_view': 'CREATE VIEW' not in sql.upper(),
}
for key, value in checks.items():
    print(f"{key}={value}")
'@ | python -
```

Result:

```text
create_table=True
engine_replacing=True
order_by_execution_id=True
partition_by_month=True
ttl_90_days=True
grafana_grant=True
no_insert=True
no_view=True
```

Validation note: two earlier `python -c` one-liners failed with `SyntaxError` because PowerShell stripped nested quotes before Python received them. Those were replaced by the stdin Python/Node validation commands above and did not indicate a workflow or code issue.

## WP3-D Verification

Blocking issues: none.

Non-blocking issues: none found.

Findings:

- Workflow update is in place: `ris-unified-dev.json` remained at 76 nodes and 56 connections.
- No nodes were added or removed, and workflow connections are unchanged.
- Only seven existing code nodes changed: `s1-format-alert` plus `s2-format-err` through `s7-format-err`.
- Discord payloads remain embed-style: changed nodes return `embeds: [embed]`, `webhookUrl`, and `notifyEnabled`.
- `s1-format-alert` now includes per-pipeline/status embed fields for `Pipelines`, `Knowledge Store`, `Review Queue`, and `overallCategory`.
- Error-format nodes only enrich formatting text with partial accepted/rejected counts and preserve `status_label`.
- JSON parse validation passed.
- JS syntax validation passed for all seven edited code nodes.
- No WP3-E daily summary trigger, monitoring infrastructure, collector work, dashboard work, or workflow structural change was pulled into WP3-D.

## WP4-A Verification

Blocking issues: none for DDL correctness/scope.

Non-blocking handoff notes:

- The DDL and Claude dev log are present as untracked files at verification time. Codex did not stage or commit them because this task was read-only.
- The prompt referenced an unnumbered SQL path, but the lane created `28_n8n_execution_metrics.sql`. This appears consistent with repo initdb ordering, not a design defect, but any downstream automation should use the numbered path.

Findings:

- DDL exists at `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`.
- Scope is limited to one ClickHouse table and a Grafana read-only grant: no `INSERT`, no collector, no view, no dashboard JSON, no alert rule.
- Table is scoped to execution metrics via `polytool.n8n_execution_metrics` and fields for execution id, workflow id/name, status, mode, started/stopped times, duration, and collection timestamp.
- Idempotent ingestion intent is represented by `ENGINE = ReplacingMergeTree(collected_at)` and `ORDER BY execution_id`.
- Retention intent is represented by `TTL started_at + INTERVAL 90 DAY`.
- Monthly retention/query scoping is represented by `PARTITION BY toYYYYMM(started_at)`.
- `GRANT SELECT ON polytool.n8n_execution_metrics TO grafana_ro` matches the nearby telemetry/table convention.
- Comments mention WP4-B/WP4-C only as downstream consumers; no collector or dashboard implementation was pulled in.

## Recommendation for Next 2-Lane Split

Recommended split: WP3-E daily Discord summary in one lane and WP4-B n8n execution metrics collector in the other.

Do not pair WP4-B and WP4-C as the next parallel split unless the dashboard lane is explicitly read-only/query-design only. The dashboard should ideally follow real or fixture rows from WP4-B so it can choose `FINAL` versus `argMax` query patterns against the `ReplacingMergeTree` table with less rework.

