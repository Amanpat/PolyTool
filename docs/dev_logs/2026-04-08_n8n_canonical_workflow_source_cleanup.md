# 2026-04-08 n8n canonical workflow source cleanup

## Summary

Minimal cleanup to remove workflow-path drift for the RIS n8n pilot.

Final repo truth after this change:

- Canonical active workflow source: `workflows/n8n/`
- Canonical active workflow file: `workflows/n8n/ris-unified-dev.json`
- Runtime tooling location: `infra/n8n/`
- Legacy/reference-only workflow JSONs: `infra/n8n/workflows/`

This remains a scoped RIS pilot only, not broad n8n orchestration.

## Files changed and why

- `infra/n8n/import-workflows.sh`
  - Changed the default import source from `infra/n8n/workflows/` to `workflows/n8n/`
  - Restricted the default import set to the active canonical file `ris-unified-dev.json`
  - Added explicit legacy/reference-only note for `infra/n8n/workflows/`
- `workflows/n8n/README.md`
  - Added a canonical-source section
  - Documented that `bash infra/n8n/import-workflows.sh` imports `ris-unified-dev.json`
  - Marked the historical JSONs in the folder as reference-only by default
- `workflows/n8n/workflow_ids.env`
  - Added a comment naming the canonical import file
- `infra/n8n/README.md`
  - Reframed `infra/n8n/` as runtime tooling only
  - Marked `infra/n8n/workflows/*.json` as legacy/reference-only
  - Pointed the import command at the canonical active source under `workflows/n8n/`
- `docs/RIS_OPERATOR_GUIDE.md`
  - Replaced the stale 11-workflow import narrative with the current single unified workflow
  - Updated webhook path from the legacy multi-workflow naming to `/webhook/ris-ingest`
  - Added explicit legacy/reference-only wording for `infra/n8n/workflows/`
- `docs/CURRENT_STATE.md`
  - Updated repo truth so the active workflow source is `workflows/n8n/ris-unified-dev.json`
  - Marked `infra/n8n/workflows/` as legacy reference only
- `docs/adr/0013-ris-n8n-pilot-scoped.md`
  - Replaced the stale initial 11-template layout with the current unified workflow source
  - Preserved the RIS-only pilot scope while clarifying which locations are now legacy

## Commands run and output

### Source inspection

```powershell
Get-ChildItem -Recurse -File workflows\n8n | Select-Object FullName
Get-ChildItem -Recurse -File infra\n8n | Select-Object FullName
```

Observed:

- `workflows/n8n/` contains `ris-unified-dev.json`, `workflow_ids.env`, and older multi-workflow reference JSONs
- `infra/n8n/workflows/` still contains the initial 11-template pilot set

### Canonical set check

```powershell
@'
import json, pathlib
for path in sorted(pathlib.Path("workflows/n8n").glob("*.json")):
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"{path.name}\t{data.get('name')}\tactive={data.get('active')}\tnodes={len(data.get('nodes', []))}")
'@ | python -
```

Key output:

```text
ris-unified-dev.json    RIS — Research Intelligence System    active=None    nodes=81
ris_global_error_watcher.json    RIS Global Error Watcher    active=None    nodes=4
ris_orchestrator.json    RIS Orchestrator    active=None    nodes=29
...
```

Conclusion: the active workflow set is a single canonical file, `workflows/n8n/ris-unified-dev.json`. The rest are historical reference artifacts.

### Shell syntax validation

Requested command:

```powershell
bash -n infra/n8n/import-workflows.sh
```

Output in this environment:

```text
<3>WSL (...) ERROR: CreateProcessCommon:800: execvpe(/bin/bash) failed: No such file or directory
```

Equivalent local validation using Git Bash:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' -n infra/n8n/import-workflows.sh
```

Output:

```text
[no output, exit 0]
```

### Canonical JSON parse validation

```powershell
@'
import json
from pathlib import Path
path = Path("workflows/n8n/ris-unified-dev.json")
json.loads(path.read_text(encoding="utf-8"))
print(f"JSON OK: {path}")
'@ | python -
```

Output:

```text
JSON OK: workflows\n8n\ris-unified-dev.json
```

### Stale-reference search

```powershell
Get-ChildItem -Recurse -File docs,infra,workflows |
  Select-String -Pattern 'infra/n8n/workflows' |
  ForEach-Object { "{0}:{1}:{2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() }
```

Result summary:

- Scoped active docs now reference `infra/n8n/workflows/` only as legacy/reference-only
- Remaining stale active-source claims still exist in historical files under `docs/dev_logs/**`
- `docs/runbooks/RIS_N8N_SMOKE_TEST.md` also still references `infra/n8n/workflows/` as the active validation target; this file was outside the allowed touch set for this cleanup

## Test results

- `bash -n infra/n8n/import-workflows.sh`
  - Direct Windows `bash.exe` launcher failed because `/bin/bash` is unavailable in this environment
  - Equivalent Git Bash syntax check passed with exit 0
- Canonical workflow JSON parse:
  - PASS for `workflows/n8n/ris-unified-dev.json`
- Repo search for stale references:
  - PASS for scoped active docs updated in this cleanup
  - Residual historical references remain in out-of-scope dev logs and one out-of-scope runbook

## Final decision

- Canonical folder: `workflows/n8n`
- Canonical active import target: `workflows/n8n/ris-unified-dev.json`
- Legacy/reference-only folder: `infra/n8n/workflows`

Why:

- `workflows/n8n/README.md` and `workflows/n8n/workflow_ids.env` already describe the repo's current unified single-canvas workflow
- `infra/n8n/` is still the correct home for Docker image, compose/runtime wiring, and import tooling
- Keeping `infra/n8n/workflows/` in place but non-default is the lowest-risk cleanup because it preserves historical JSON exports without letting them drive current imports

## Open questions for runtime debugging

- `docs/runbooks/RIS_N8N_SMOKE_TEST.md` still assumes `infra/n8n/workflows/` is the active validation target. If operators use that runbook, it should be reconciled in a follow-up change.
- Historical dev logs still contain contradictory path claims. They are useful as history, but they will continue to show up in repo-wide searches until explicitly annotated or archived.
- This cleanup did not run a live n8n import against a running container. If runtime debugging is needed, the next check should be a real import using `bash infra/n8n/import-workflows.sh [container]` with `polytool-n8n` running.
