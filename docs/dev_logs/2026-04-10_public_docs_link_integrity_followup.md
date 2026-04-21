# 2026-04-10 public docs link integrity followup

## Files changed and why

| Path | Why |
|------|-----|
| `docs/INDEX.md` | Fixed a stale public-nav link left behind after `roadmap3_completion.md` was moved into `docs/archive/` |
| `docs/README.md` | Removed a dead nav link to `PROJECT_TREE_FULL.txt`, which no longer exists and has no tracked replacement |
| `docs/CURRENT_STATE.md` | Corrected a stale inline runbook path to the current Wallet Discovery operator runbook filename |
| `docs/dev_logs/2026-04-10_public_docs_link_integrity_followup.md` | Recorded this scoped follow-up pass and verification outputs |

## Broken/stale links found

| Source | Broken/stale target | Problem |
|--------|---------------------|---------|
| `docs/INDEX.md` | `roadmap3_completion.md` | Old root path no longer exists after cleanup; current file lives at `docs/archive/roadmap3_completion.md` |
| `docs/README.md` | `PROJECT_TREE_FULL.txt` | Linked file no longer exists anywhere tracked in the repo |
| `docs/CURRENT_STATE.md` | `docs/runbooks/WALLET_DISCOVERY_V1_RUNBOOK.md` | Stale runbook path; current file is `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` |

## Fixes applied

- Updated `docs/INDEX.md` to point `Roadmap 3 Completion` at `archive/roadmap3_completion.md`.
- Removed the dead `Project tree (full)` bullet from `docs/README.md` instead of inventing a replacement target.
- Updated `docs/CURRENT_STATE.md` to reference `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md`.
- Left wording and document structure otherwise unchanged.

## Commands run + output

### Scoped public-doc link/path check before edits

Command:

```powershell
@'
import re
from pathlib import Path

files = [
    Path('docs/INDEX.md'),
    Path('docs/README.md'),
    Path('README.md'),
    Path('docs/CURRENT_STATE.md'),
    Path('docs/PROJECT_OVERVIEW.md'),
    Path('docs/PROJECT_CONTEXT_PUBLIC.md'),
]
pat = re.compile(r'\[[^\]]+\]\(([^)]+)\)')
for f in files:
    print(f'FILE {f}')
    text = f.read_text(encoding='utf-8', errors='replace')
    found = False
    for m in pat.finditer(text):
        if m.start() > 0 and text[m.start()-1] == '!':
            continue
        raw = m.group(1)
        target = raw.split('#', 1)[0].strip()
        if not target or '://' in target or target.startswith('mailto:'):
            continue
        p = (f.parent / target).resolve()
        if not p.exists():
            print(f'  MISSING {target}')
            found = True
    if not found:
        print('  OK')
    print()
'@ | python -
```

Output:

```text
FILE docs\INDEX.md
  MISSING roadmap3_completion.md

FILE docs\README.md
  MISSING PROJECT_TREE_FULL.txt

FILE README.md
  OK

FILE docs\CURRENT_STATE.md
  OK

FILE docs\PROJECT_OVERVIEW.md
  OK

FILE docs\PROJECT_CONTEXT_PUBLIC.md
  OK
```

### Target existence check for replacements

Command:

```powershell
git ls-files | Select-String 'PROJECT_TREE_FULL.txt|roadmap3_completion|WALLET_DISCOVERY_V1_RUNBOOK|WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK'
Test-Path docs/archive/roadmap3_completion.md
Test-Path docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md
Test-Path docs/runbooks/WALLET_DISCOVERY_V1_RUNBOOK.md
Test-Path docs/PROJECT_TREE_FULL.txt
```

Output:

```text
docs/archive/roadmap3_completion.md
docs/dev_logs/2026-04-10_wallet_discovery_v1_operator_runbook.md
docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md

True
True
False
False
```

### Scoped public-doc link/path check after edits

Command:

```powershell
@'
import re
from pathlib import Path

files = [
    Path('docs/INDEX.md'),
    Path('docs/README.md'),
]
pat = re.compile(r'\[[^\]]+\]\(([^)]+)\)')
failed = False
for f in files:
    text = f.read_text(encoding='utf-8', errors='replace')
    missing = []
    for m in pat.finditer(text):
        if m.start() > 0 and text[m.start()-1] == '!':
            continue
        raw = m.group(1)
        target = raw.split('#', 1)[0].strip()
        if not target or '://' in target or target.startswith('mailto:'):
            continue
        p = (f.parent / target).resolve()
        if not p.exists():
            missing.append(target)
    if missing:
        failed = True
        print(f'{f}: FAIL')
        for target in missing:
            print(f'  MISSING {target}')
    else:
        print(f'{f}: OK')
print(f'docs/CURRENT_STATE.md inline runbook path exists={Path(\"docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md\").exists()}')
raise SystemExit(1 if failed or not Path(\"docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md\").exists() else 0)
'@ | python -
```

Output:

```text
docs\INDEX.md: OK
docs\README.md: OK
docs/CURRENT_STATE.md inline runbook path exists=True
```

### Required repo diff/status commands

Commands:

```powershell
git diff --stat
git status --short
git diff --stat -- docs/README.md docs/INDEX.md docs/CURRENT_STATE.md docs/dev_logs/2026-04-10_public_docs_link_integrity_followup.md
git status --short -- docs/README.md docs/INDEX.md docs/CURRENT_STATE.md docs/dev_logs/2026-04-10_public_docs_link_integrity_followup.md
```

Relevant output after edits:

```text
docs/CURRENT_STATE.md |   8 ++--
docs/INDEX.md         |  83 ++++++++++++++++++++++++++-------------
docs/README.md        | 105 +++++++++++++++++++++++++++++++++-----------------
3 files changed, 129 insertions(+), 67 deletions(-)

 M docs/CURRENT_STATE.md
 M docs/INDEX.md
 M docs/README.md
?? docs/dev_logs/2026-04-10_public_docs_link_integrity_followup.md
```

Note: `git diff --stat` shows tracked file edits only, so the new dev log is
visible in `git status --short` rather than the diff stat. Full-repo
`git diff --stat` and `git status --short` also ran successfully but were noisy
because the worktree already contained many unrelated modifications before this
pass.

## Deferred link issues and why

- No additional broken relative links remained in the touched public docs after the fix pass.
- I did not chase references inside `docs/dev_logs/**`, `docs/archive/**`,
  `docs/specs/**`, `docs/features/**`, `docs/obsidian-vault/**`, or broader
  authority/history surfaces, because this follow-up was explicitly limited to
  the curated public navigation surface and directly affected public docs.
