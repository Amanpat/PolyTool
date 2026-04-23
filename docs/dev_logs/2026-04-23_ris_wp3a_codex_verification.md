# RIS WP3-A Codex Verification

Date: 2026-04-23
Scope: read-only verification, except this dev log

## Files Inspected

- `infra/n8n/workflows/ris-unified-dev.json`
- `docs/dev_logs/2026-04-22_ris_wp3a_structured_output.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `infra/n8n/import_workflows.py`
- `infra/n8n/README.md`
- `tests/` targeted search for WP3-A workflow coverage
- `infra/grafana/` and `infra/clickhouse/` status check for WP4 scope creep

## What Matched

- The existing RIS workflow source was updated in place. Node count stayed `76 -> 76`, connection entry count stayed `56 -> 56`, and there were no added or removed node IDs.
- Only the six targeted Parse Metrics Code nodes changed:
  - `s2-parse|Academic: Parse Metrics|n8n-nodes-base.code`
  - `s3-parse|Reddit: Parse Metrics|n8n-nodes-base.code`
  - `s4-parse|Blog: Parse Metrics|n8n-nodes-base.code`
  - `s5-parse|YouTube: Parse Metrics|n8n-nodes-base.code`
  - `s6-parse|GitHub: Parse Metrics|n8n-nodes-base.code`
  - `s7-parse|Freshness: Parse Metrics|n8n-nodes-base.code`
- The intended structured output shape is visible and coherent for all six sections: `pipeline`, `docs_fetched`, `docs_evaluated`, `docs_accepted`, `docs_rejected`, `docs_review`, `new_claims`, `duration_seconds`, `errors`, `exit_code`, `timestamp`.
- No WP3-B/WP4 scope creep was found in the workflow diff. Search for `Discord|embed|daily|summary|Grafana|ClickHouse|monitor|health` in the workflow diff returned no matches.
- `git status --short -- infra/grafana infra/clickhouse` returned no changes.
- Targeted test search for `WP3-A|structured output|Parse Metrics|ris-unified-dev` returned no matches, so no workflow-specific tests were found for this work unit.

## Blocking Issues

- WP3-A is not complete: all six updated Code node `jsCode` strings fail JavaScript syntax validation after JSON decoding. The decoded code contains an actual line feed inside the single-quoted split argument:

```text
stdout.split('<LF>');<LF>const timestamp = new
```

Expected fix direction: encode the newline split so the JavaScript source remains valid after JSON decoding, for example by preserving a JS escape sequence such as `stdout.split('\\n')` or using a regex literal if appropriate.

## Non-Blocking Issues

- None.

## Commands Run

```powershell
git status --short -- infra/n8n/workflows/ris-unified-dev.json docs/CURRENT_DEVELOPMENT.md docs/dev_logs/2026-04-22_ris_wp3a_structured_output.md infra/grafana infra/clickhouse
```

Output:

```text
 M docs/CURRENT_DEVELOPMENT.md
 M infra/n8n/workflows/ris-unified-dev.json
?? docs/dev_logs/2026-04-22_ris_wp3a_structured_output.md
```

```powershell
python -m polytool --help > $null; if ($LASTEXITCODE -eq 0) { 'polytool_help_exit=0' } else { "polytool_help_exit=$LASTEXITCODE"; exit $LASTEXITCODE }
```

Output:

```text
polytool_help_exit=0
```

```powershell
python -c "import json; p='infra/n8n/workflows/ris-unified-dev.json'; data=json.load(open(p,encoding='utf-8')); print('json_valid=1'); print('nodes=' + str(len(data.get('nodes', [])))); print('connections=' + str(len(data.get('connections', {}))))"
```

Output:

```text
json_valid=1
nodes=76
connections=56
```

```powershell
@'
import json, subprocess
path = 'infra/n8n/workflows/ris-unified-dev.json'
current = json.load(open(path, encoding='utf-8'))
head = json.loads(subprocess.check_output(['git', 'show', f'HEAD:{path}'], text=True, encoding='utf-8'))
cur_ids = {n['id'] for n in current['nodes']}
head_ids = {n['id'] for n in head['nodes']}
print(f"nodes {len(head_ids)} -> {len(cur_ids)}")
print(f"connections {len(head.get('connections', {}))} -> {len(current.get('connections', {}))}")
print('added', sorted(cur_ids - head_ids))
print('removed', sorted(head_ids - cur_ids))
changed = []
head_by_id = {n['id']: n for n in head['nodes']}
for n in current['nodes']:
    if n['id'] in head_by_id and n != head_by_id[n['id']]:
        changed.append(f"{n['id']}|{n.get('name')}|{n.get('type')}")
print('changed')
for item in changed:
    print(item)
'@ | python -
```

Output:

```text
nodes 76 -> 76
connections 56 -> 56
added []
removed []
changed
s2-parse|Academic: Parse Metrics|n8n-nodes-base.code
s3-parse|Reddit: Parse Metrics|n8n-nodes-base.code
s4-parse|Blog: Parse Metrics|n8n-nodes-base.code
s5-parse|YouTube: Parse Metrics|n8n-nodes-base.code
s6-parse|GitHub: Parse Metrics|n8n-nodes-base.code
s7-parse|Freshness: Parse Metrics|n8n-nodes-base.code
```

```powershell
@'
const fs = require('fs');
const data = JSON.parse(fs.readFileSync('infra/n8n/workflows/ris-unified-dev.json', 'utf8'));
let failures = 0;
for (const n of data.nodes) {
  if (['s2-parse','s3-parse','s4-parse','s5-parse','s6-parse','s7-parse'].includes(n.id)) {
    try { new Function(n.parameters.jsCode); console.log(n.id + '=syntax_ok'); }
    catch (err) { failures++; console.log(n.id + '=syntax_error:' + err.message); }
  }
}
process.exitCode = failures ? 1 : 0;
'@ | node
```

Output:

```text
s2-parse=syntax_error:Invalid or unexpected token
s3-parse=syntax_error:Invalid or unexpected token
s4-parse=syntax_error:Invalid or unexpected token
s5-parse=syntax_error:Invalid or unexpected token
s6-parse=syntax_error:Invalid or unexpected token
s7-parse=syntax_error:Invalid or unexpected token
```

```powershell
git diff -- infra/n8n/workflows/ris-unified-dev.json | Select-String -Pattern 'Discord|embed|daily|summary|Grafana|ClickHouse|monitor|health' | ForEach-Object { $_.Line }
git status --short infra/grafana infra/clickhouse
Get-ChildItem -Recurse -File tests -Include *.py | Select-String -Pattern 'WP3-A|structured output|Parse Metrics|ris-unified-dev'
```

Output:

```text
<no output>
```

## Recommendation

Do not mark WP3-A complete yet. The next WP3 substep should be a narrow WP3-A fix to correct the JSON-encoded JavaScript newline escaping in `s2-parse` through `s7-parse`, followed by the same JSON and `new Function(jsCode)` validation. After that passes, proceed to WP3-B Discord embeds; do not start WP4 monitoring from this work packet.
