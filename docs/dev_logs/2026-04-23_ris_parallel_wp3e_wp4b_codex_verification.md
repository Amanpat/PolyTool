# RIS Parallel WP3-E / WP4-B Codex Verification

**Date:** 2026-04-23  
**Scope:** Read-only verification of the two active RIS Phase 2A lanes after landing.  
**Mutation made by Codex:** This verification log only.

## Files Inspected

- `infra/n8n/workflows/ris-unified-dev.json`
- `infra/n8n/workflows/ris-n8n-metrics-collector.json`
- `docs/dev_logs/2026-04-23_ris_wp3e_daily_summary.md`
- `docs/dev_logs/2026-04-23_ris_wp4b_metrics_collector.md`

## Commands Run and Results

```powershell
git status --short
```

Result:

```text
?? docs/dev_logs/2026-04-23_ris_parallel_wp3d_wp4a_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md
?? infra/clickhouse/initdb/28_n8n_execution_metrics.sql
```

```powershell
git log --oneline -5
```

Result:

```text
d9e9f8b feat(ris): WP3-E — daily digest path at 09:00 UTC with WP3-C structured embed
b2ad984 feat(ris): WP4-B -- hourly n8n execution metrics collector workflow
2eaefd8 feat(ris): WP3-D — Discord embed enrichment with per-pipeline fields
129d376 RIS improvement
a610f18 Hermes Agent containerization
```

```powershell
python -m polytool --help
```

Result: exit `0`. CLI rendered the PolyTool help surface beginning with `PolyTool - Polymarket analysis toolchain` and no traceback/import error.

```powershell
git show --stat --summary d9e9f8b -- infra/n8n/workflows/ris-unified-dev.json docs/dev_logs/2026-04-23_ris_wp3e_daily_summary.md
```

Result:

```text
commit d9e9f8be6505936d0bde71e534903deb9f931f66
Author: Amanpat <patelamanst@gmail.com>
Date:   Thu Apr 23 11:31:12 2026 -0400

    feat(ris): WP3-E — daily digest path at 09:00 UTC with WP3-C structured embed

 docs/dev_logs/2026-04-23_ris_wp3e_daily_summary.md | 180 +++++++++++++++++++++
 infra/n8n/workflows/ris-unified-dev.json           |   6 +-
 2 files changed, 183 insertions(+), 3 deletions(-)
 create mode 100644 docs/dev_logs/2026-04-23_ris_wp3e_daily_summary.md
```

```powershell
git show --stat --summary b2ad984 -- infra/n8n/workflows/ris-n8n-metrics-collector.json docs/dev_logs/2026-04-23_ris_wp4b_metrics_collector.md
```

Result:

```text
commit b2ad98412f074247749fa89244cbc70e61d49456
Author: Amanpat <patelamanst@gmail.com>
Date:   Thu Apr 23 11:24:43 2026 -0400

    feat(ris): WP4-B -- hourly n8n execution metrics collector workflow

 .../2026-04-23_ris_wp4b_metrics_collector.md       | 172 +++++++++++++++++++++
 infra/n8n/workflows/ris-n8n-metrics-collector.json | 136 ++++++++++++++++
 2 files changed, 308 insertions(+)
 create mode 100644 docs/dev_logs/2026-04-23_ris_wp4b_metrics_collector.md
 create mode 100644 infra/n8n/workflows/ris-n8n-metrics-collector.json
```

```powershell
@'
import json, subprocess
path = 'infra/n8n/workflows/ris-unified-dev.json'
old = json.loads(subprocess.check_output(['git','show','d9e9f8b^:' + path], text=True, encoding='utf-8'))
new = json.loads(subprocess.check_output(['git','show','d9e9f8b:' + path], text=True, encoding='utf-8'))
old_nodes = {n['name']: n for n in old['nodes']}
new_nodes = {n['name']: n for n in new['nodes']}
changed = []
for name in sorted(set(old_nodes) | set(new_nodes)):
    if name not in old_nodes:
        changed.append((name, 'added'))
    elif name not in new_nodes:
        changed.append((name, 'removed'))
    elif old_nodes[name] != new_nodes[name]:
        changed.append((name, 'modified'))
print('WP3-E changed nodes:')
for item in changed:
    print(item)
print('old_counts', len(old['nodes']), len(old['connections']))
print('new_counts', len(new['nodes']), len(new['connections']))
print('connections_equal', old['connections'] == new['connections'])
'@ | python -
```

Result:

```text
WP3-E changed nodes:
('S8: Summary - Label', 'modified')
('Summary: Format Message', 'modified')
('Summary: Schedule', 'modified')
old_counts 76 56
new_counts 76 56
connections_equal True
```

```powershell
@'
import json, pathlib
path = pathlib.Path('infra/n8n/workflows/ris-unified-dev.json')
data = json.loads(path.read_text(encoding='utf-8'))
by_name = {node['name']: node for node in data['nodes']}
for name in ['Summary: Schedule', 'S8: Summary - Label', 'Summary: Format Message']:
    node = by_name[name]
    print(f'NODE: {name}')
    if name == 'Summary: Schedule':
        print(f"  rule={node['parameters'].get('rule')}")
    elif name == 'S8: Summary - Label':
        print(f"  content={node['parameters'].get('content')!r}")
    else:
        code = node['parameters'].get('jsCode', '')
        for marker in ['pipelineStatuses', 'knowledgeStore', 'reviewQueueDepth', 'overallCategory', 'derivedStatus', 'actionableChecks', 'providerRouting', 'RIS Daily Digest', 'daily-summary', 'Summary: Run research-health', 'Summary: Run research-stats']:
            print(f"  marker[{marker}]={'yes' if marker in code else 'no'}")
'@ | python -
```

Result:

```text
NODE: Summary: Schedule
  rule={'interval': [{'field': 'cronExpression', 'expression': '0 0 9 * * *'}]}
NODE: S8: Summary - Label
  content='## Section 8: Daily Summary -- 09:00 UTC (disabled by default)\nRuns RIS health + stats, then sends one compact operator summary when a webhook is configured.'
NODE: Summary: Format Message
  marker[pipelineStatuses]=yes
  marker[knowledgeStore]=yes
  marker[reviewQueueDepth]=yes
  marker[overallCategory]=yes
  marker[derivedStatus]=yes
  marker[actionableChecks]=yes
  marker[providerRouting]=yes
  marker[RIS Daily Digest]=yes
  marker[daily-summary]=yes
  marker[Summary: Run research-health]=yes
  marker[Summary: Run research-stats]=yes
```

```powershell
@'
import json, pathlib
for path in [
    pathlib.Path('infra/n8n/workflows/ris-unified-dev.json'),
    pathlib.Path('infra/n8n/workflows/ris-n8n-metrics-collector.json'),
]:
    data = json.loads(path.read_text(encoding='utf-8'))
    print(f'PASS JSON {path} nodes={len(data.get("nodes", []))} connections={len(data.get("connections", {}))}')
'@ | python -
```

Result:

```text
PASS JSON infra\n8n\workflows\ris-unified-dev.json nodes=76 connections=56
PASS JSON infra\n8n\workflows\ris-n8n-metrics-collector.json nodes=4 connections=3
```

```powershell
@'
import json, pathlib
path = pathlib.Path('infra/n8n/workflows/ris-n8n-metrics-collector.json')
data = json.loads(path.read_text(encoding='utf-8'))
by_name = {node['name']: node for node in data['nodes']}
for name in ['Schedule: Every Hour', 'API: GET Executions', 'Transform: To ClickHouse Rows', 'ClickHouse: INSERT Rows']:
    node = by_name[name]
    print(f'NODE: {name}')
    print(f"  type={node.get('type')}")
    params = node.get('parameters', {})
    if name == 'Schedule: Every Hour':
        print(f"  rule={params.get('rule')}")
    elif name == 'API: GET Executions':
        print(f"  method={params.get('method')} url={params.get('url')!r}")
        print(f"  query={params.get('sendQuery', False)} limit={params.get('queryParameters', {}).get('parameters', [])}")
    elif name == 'Transform: To ClickHouse Rows':
        code = params.get('jsCode', '')
        for marker in ['workflow_id', 'workflow_name', 'status', 'mode', 'started_at', 'stopped_at', 'duration_seconds', 'clickhouse_body', 'dashboard', 'alert', 'grafana']:
            print(f"  marker[{marker}]={'yes' if marker in code else 'no'}")
    elif name == 'ClickHouse: INSERT Rows':
        print(f"  method={params.get('method')} url={params.get('url')!r}")
print('top_level_active', data.get('active'))
'@ | python -
```

Result:

```text
NODE: Schedule: Every Hour
  type=n8n-nodes-base.scheduleTrigger
  rule={'interval': [{'field': 'hours', 'hoursInterval': 1}]}
NODE: API: GET Executions
  type=n8n-nodes-base.httpRequest
  method=GET url='http://localhost:5678/api/v1/executions'
  query=True limit=[{'name': 'limit', 'value': '250'}, {'name': 'includeData', 'value': 'false'}]
NODE: Transform: To ClickHouse Rows
  marker[workflow_id]=yes
  marker[workflow_name]=yes
  marker[status]=yes
  marker[mode]=yes
  marker[started_at]=yes
  marker[stopped_at]=yes
  marker[duration_seconds]=yes
  marker[clickhouse_body]=yes
  marker[dashboard]=no
  marker[alert]=no
  marker[grafana]=no
NODE: ClickHouse: INSERT Rows
  type=n8n-nodes-base.httpRequest
  method=POST url='http://clickhouse:8123/'
top_level_active False
```

```powershell
@'
import json, pathlib, subprocess, sys
checks = [
    ('infra/n8n/workflows/ris-unified-dev.json', 'Summary: Format Message'),
    ('infra/n8n/workflows/ris-n8n-metrics-collector.json', 'Transform: To ClickHouse Rows'),
]
for file_path, node_name in checks:
    data = json.loads(pathlib.Path(file_path).read_text(encoding='utf-8'))
    node = next(n for n in data['nodes'] if n['name'] == node_name)
    code = node.get('parameters', {}).get('jsCode') or node.get('parameters', {}).get('functionCode') or ''
    proc = subprocess.run(
        ['node', '-e', "const fs=require('fs'); const src=fs.readFileSync(0,'utf8'); new Function(src); console.log('JS syntax OK');"],
        input=code,
        text=True,
        capture_output=True,
        encoding='utf-8'
    )
    label = f'{file_path} :: {node_name}'
    if proc.returncode == 0:
        print(f'PASS JS {label} -> {proc.stdout.strip()}')
    else:
        print(f'FAIL JS {label} -> {proc.stderr.strip()}')
        sys.exit(proc.returncode)
'@ | python -
```

Result:

```text
PASS JS infra/n8n/workflows/ris-unified-dev.json :: Summary: Format Message -> JS syntax OK
PASS JS infra/n8n/workflows/ris-n8n-metrics-collector.json :: Transform: To ClickHouse Rows -> JS syntax OK
```

```powershell
@'
import json, pathlib
checks = [
    ('infra/n8n/workflows/ris-unified-dev.json', ['clickhouse', 'grafana', 'dashboard', 'n8n_execution_metrics']),
    ('infra/n8n/workflows/ris-n8n-metrics-collector.json', ['grafana', 'dashboard', 'discord', 'webhook', 'alert']),
]
for file_path, markers in checks:
    text = pathlib.Path(file_path).read_text(encoding='utf-8').lower()
    print(file_path)
    for marker in markers:
        print(f'  {marker}: {text.count(marker)}')
'@ | python -
```

Result:

```text
infra/n8n/workflows/ris-unified-dev.json
  clickhouse: 0
  grafana: 0
  dashboard: 0
  n8n_execution_metrics: 0
infra/n8n/workflows/ris-n8n-metrics-collector.json
  grafana: 0
  dashboard: 0
  discord: 0
  webhook: 0
  alert: 0
```

## WP3-E Verification

Blocking issues: none.

Non-blocking issues: none found.

Findings:

- The daily-summary path was added in place inside `ris-unified-dev.json`.
- The commit-level node diff shows exactly three modified existing nodes: `Summary: Schedule`, `S8: Summary - Label`, and `Summary: Format Message`.
- Workflow structure remained stable at `76` nodes and `56` connections, with `connections_equal True`.
- `Summary: Schedule` is now set to cron `0 0 9 * * *`, which matches the requested 09:00 UTC daily run.
- The S8 sticky note content also reflects `09:00 UTC`.
- `Summary: Format Message` contains the expected WP3-C structured markers: `pipelineStatuses`, `knowledgeStore`, `reviewQueueDepth`, `overallCategory`, `derivedStatus`, `actionableChecks`, `providerRouting`, `RIS Daily Digest`, and `daily-summary`.
- Workflow JSON parse passed.
- The edited JS code node passed syntax validation.
- No WP4 scope creep was found in the modified S8 node or the workflow text scan: `clickhouse`, `grafana`, `dashboard`, and `n8n_execution_metrics` all occurred `0` times in `ris-unified-dev.json`.

## WP4-B Verification

Blocking issues: none.

Non-blocking issues: none found.

Findings:

- The collector exists as a separate workflow file at `infra/n8n/workflows/ris-n8n-metrics-collector.json`.
- The file is a standalone `4`-node linear workflow with `3` connection entries and `active False`.
- The workflow is scoped to execution-metric collection only:
  - hourly schedule trigger
  - GET `http://localhost:5678/api/v1/executions`
  - code transform to ClickHouse rows
  - POST `http://clickhouse:8123/`
- The transform code contains only execution-metric fields: `workflow_id`, `workflow_name`, `status`, `mode`, `started_at`, `stopped_at`, `duration_seconds`, and `clickhouse_body`.
- The transform code contains no dashboard or alert terms: `dashboard=no`, `alert=no`, `grafana=no`.
- Whole-file text scan also found `0` occurrences of `grafana`, `dashboard`, `discord`, `webhook`, and `alert`.
- Workflow JSON parse passed.
- The new JS code node passed syntax validation.
- No dashboards, alerts, or operator-notification behavior were pulled into the collector workflow.

## Recommendation for Next 2-Lane Split

Recommended next split: keep WP4-B frozen and split `WP4-C` dashboard work from `WP4-D` stale-pipeline alerting, so one lane owns visualization/query design and the other owns alert-rule logic without reopening the collector.
