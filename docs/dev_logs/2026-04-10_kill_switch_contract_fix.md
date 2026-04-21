# Kill Switch Contract Fix

## Files changed and why

- `docker-compose.yml`: removed the stale `./kill_switch.json:/app/kill_switch.json:ro` bind mount from the `polytool` service.
- `.dockerignore`: removed the stale root `kill_switch.json` exclusion.
- `docs/CURRENT_STATE.md`: removed the stale current-state note that still listed `kill_switch.json` in the active `.dockerignore` contract.
- `docs/PARTNER_DEPLOYMENT_GUIDE_docker.md`: replaced empty-file `touch` guidance with the real `artifacts/crypto_pairs/kill_switch.txt` truthy-content contract and noted there is no dedicated crypto-pair kill CLI in that flow.
- `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`: replaced `New-Item`/`touch` guidance with truthy-content writes for `artifacts/crypto_pairs/kill_switch.txt`.
- `docs/runbooks/GATE3_SHADOW_RUNBOOK.md`: corrected the stale troubleshooting path from `artifacts/kill_switch` to `artifacts/kill_switch.txt` and clarified that resetting the file to a falsy value clears it.
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`: kept `python -m polytool simtrader kill` as the preferred operator action and corrected the manual fallback to a truthy-content write instead of `touch`.
- Removed root `kill_switch.json/`: the directory was empty and had no runtime owner after the stale compose mount was removed.
- `docs/dev_logs/2026-04-10_kill_switch_contract_fix.md`: recorded this fix, its evidence, and validation.

## Evidence confirming the real contract

- `packages/polymarket/simtrader/execution/kill_switch.py`
  - Module docstring says the file trips only when it exists and contains truthy text.
  - `_TRUTHY = {"1", "true", "yes", "on"}`
  - `is_tripped()` returns `False` for absent files and for empty content.
- `tools/cli/simtrader.py`
  - `DEFAULT_KILL_SWITCH_PATH = Path("artifacts/kill_switch.txt")`
  - `_kill()` creates parent directories and writes `"1"` to the kill-switch file.
- `packages/polymarket/crypto_pairs/paper_runner.py`
  - `DEFAULT_KILL_SWITCH_PATH = Path("artifacts/crypto_pairs/kill_switch.txt")`

These reads confirmed that the real runtime contract was already artifacts-based and truthy-content-based; only compose/docs/root-directory hygiene were stale.

## Commands run + output

### Contract confirmation reads

```text
packages/polymarket/simtrader/execution/kill_switch.py
- "A FileBasedKillSwitch trips when a file exists and contains truthy text"
- "An absent or empty file is not tripped"
- _TRUTHY = {"1", "true", "yes", "on"}

tools/cli/simtrader.py
- DEFAULT_KILL_SWITCH_PATH = Path("artifacts/kill_switch.txt")
- _kill() writes "1"

packages/polymarket/crypto_pairs/paper_runner.py
- DEFAULT_KILL_SWITCH_PATH = Path("artifacts/crypto_pairs/kill_switch.txt")
```

### Requested validation commands

```powershell
git grep -n "kill_switch\.json"
```

Output:

```text
.planning/quick/260404-jfz-polytool-docker-readiness-full-stack-con/260404-jfz-PLAN.md:129:   - Volumes: `./artifacts:/app/artifacts`, `./config:/app/config:ro`, `./kb:/app/kb`, `./kill_switch.json:/app/kill_switch.json:ro` (mount artifacts read-write, config and kill_switch read-only, kb read-write for RAG)
.planning/quick/260404-jfz-polytool-docker-readiness-full-stack-con/260404-jfz-SUMMARY.md:101:4. `kill_switch.json` volume mount may fail if file does not exist on host — consider optional mount or default file
.planning/quick/260405-j2t-docker-build-performance-hygiene-smaller/260405-j2t-PLAN.md:97:The current .dockerignore is minimal (only .git, .venv, .pytest_cache, __pycache__, artifacts/, .tmp/, kb/tmp_tests/, node_modules/, dist/, build/, mcp stdout/stderr). The root Dockerfile does `COPY . .` so ALL of these go into context: docs/ (~MB), tests/ (~MB), kb/ (can be large — RAG knowledge store), .planning/, docker_data/, infra/ (only needed by n8n which has its own context), scripts/, config/, polytool.egg-info/, .claude/ (worktrees can be huge), *.md root files, .env* files, kill_switch.json (mounted as volume anyway).
.planning/quick/260405-j2t-docker-build-performance-hygiene-smaller/260405-j2t-PLAN.md:149:kill_switch.json
.planning/quick/260405-j2t-docker-build-performance-hygiene-smaller/260405-j2t-PLAN.md:345:| T-quick-01 | Information Disclosure | .dockerignore | mitigate | Exclude .env, .env.*, kill_switch.json from build context so secrets never enter image layers |
.planning/quick/260405-j2t-docker-build-performance-hygiene-smaller/260405-j2t-SUMMARY.md:52:- `kill_switch.json`, `*.log`, `logs/`, `tmp/`, `LICENSE`, `README.md`, `CLAUDE.md`
docs/dev_logs/2026-04-04_docker-full-stack.md:38:- Volume mounts: `artifacts` (rw), `config` (ro), `kb` (rw), `kill_switch.json` (ro)
docs/dev_logs/2026-04-04_docker-full-stack.md:102:4. **kill_switch.json volume** — the polytool CLI service mounts `./kill_switch.json:ro`.
docs/dev_logs/2026-04-05_docker_perf_hygiene.md:45:| Root `.env`, `*.log`, `kill_switch.json`, `LICENSE`, etc. | small | Secrets + misc |
docs/dev_logs/2026-04-05_docker_perf_hygiene.md:252:| `.dockerignore` | Rewrote: 20+ new exclusions (docs/, tests/, kb/, .planning/, infra/, scripts/, config/, docker_data/, .claude/, .env*, kill_switch.json, *.log, logs/, tmp/, LICENSE, README.md, CLAUDE.md) |
```

Interpretation: remaining `kill_switch.json` hits are limited to internal planning files and preserved historical dev logs. There are no active `docker-compose.yml`, `.dockerignore`, or current operator-doc references left.

```powershell
git grep -n "touch .*kill_switch\.txt\|kill_switch\.txt" docs README.md
```

Output:

```text
docs/PARTNER_DEPLOYMENT_GUIDE_docker.md:55:| Kill switch | `artifacts/crypto_pairs/kill_switch.txt` |
docs/PARTNER_DEPLOYMENT_GUIDE_docker.md:103:`yes`, or `on`) to `artifacts/crypto_pairs/kill_switch.txt`. An empty file
docs/PARTNER_DEPLOYMENT_GUIDE_docker.md:107:printf '1\n' > artifacts/crypto_pairs/kill_switch.txt
docs/PARTNER_DEPLOYMENT_GUIDE_docker.md:115:printf '1\n' > artifacts/crypto_pairs/kill_switch.txt
docs/PARTNER_DEPLOYMENT_GUIDE_docker.md:147:    kill_switch.txt          <- write 1/true/yes/on here to halt the bot
docs/dev_logs/2026-03-25_phase1a_first_real_paper_soak.md:255:- kill_switch_path: `artifacts/crypto_pairs/kill_switch.txt`
docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md:83:DEFAULT_KILL_SWITCH_PATH = Path("artifacts/crypto_pairs/kill_switch.txt")
docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md:91:touch artifacts/crypto_pairs/kill_switch.txt
docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md:97:New-Item artifacts/crypto_pairs/kill_switch.txt -Force
docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md:195:touch artifacts/crypto_pairs/kill_switch.txt
docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md:214:New-Item artifacts/crypto_pairs/kill_switch.txt -Force
docs/features/FEATURE-trackA-week1-execution-primitives.md:33:  --kill-switch artifacts/kill_switch.txt \
docs/features/FEATURE-trackA-week2-market-maker-v0.md:88:  --kill-switch artifacts/kill_switch.txt \
docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md:111:into `artifacts/crypto_pairs/kill_switch.txt`. Empty file creation alone does
docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md:118:Set-Content -Path artifacts/crypto_pairs/kill_switch.txt -Value 1
docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md:124:printf '1\n' > artifacts/crypto_pairs/kill_switch.txt
docs/runbooks/GATE3_SHADOW_RUNBOOK.md:235:| Kill switch trips immediately | Stale kill-switch file | Remove `artifacts/kill_switch.txt` or reset its value to `0` |
docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md:43:- `Ctrl+C` stops the current process. The file kill switch blocks new orders on the next check when `artifacts/kill_switch.txt` contains a truthy value.
docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md:53:- Arm the file kill switch immediately (preferred helper; it writes `1` to `artifacts/kill_switch.txt`):
docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md:62:printf '1\n' > artifacts/kill_switch.txt
docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md:214:| Manual kill switch arm | `touch artifacts/kill_switch.txt` |
docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md:307:- Kill switch file present (`artifacts/kill_switch.txt`): no new orders submitted.
docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md:327:touch artifacts/kill_switch.txt
docs/specs/SPEC-0013-phase1-tracka-gap-matrix.md:68:| `kill_switch.py` | Small | `FileBasedKillSwitch` reads `artifacts/kill_switch.txt`; truthy content trips it; OSError -> safe False | `tests/test_live_execution.py` |
```

Interpretation: current operator docs now describe truthy-content writes or the `simtrader kill` helper; remaining `touch` hits are preserved historical specs/dev logs outside this scope.

```powershell
git grep -n "touch .*kill_switch\.txt\|New-Item .*kill_switch\.txt" -- docs/PARTNER_DEPLOYMENT_GUIDE_docker.md docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md docs/runbooks/GATE3_SHADOW_RUNBOOK.md docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md
```

Output:

```text
(no matches; command exited 1)
```

```powershell
if (Test-Path kill_switch.json) { "kill_switch.json exists" } else { "kill_switch.json missing" }
```

Output:

```text
kill_switch.json missing
```

### Worktree-state commands

`git status --short` and `git diff --stat` were also run exactly as requested. Their full outputs were dominated by pre-existing unrelated worktree changes. Relevant lines for this kill-switch fix are recorded below in the focused validation block.

## Validation results

- `docker-compose.yml` no longer mounts a bogus root `kill_switch.json`.
- `.dockerignore` no longer treats root `kill_switch.json` as a live artifact.
- Root `kill_switch.json/` is gone.
- Current operator docs no longer tell operators that empty `touch`/`New-Item` is sufficient.
- `simtrader` docs now prefer `python -m polytool simtrader kill`; crypto-pair docs now tell operators to write truthy content directly because no dedicated kill helper exists there.
- Runtime code and path defaults were not changed.

## Focused worktree diff for this fix

```text
git status --short -- docker-compose.yml .dockerignore docs/CURRENT_STATE.md docs/PARTNER_DEPLOYMENT_GUIDE_docker.md docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md docs/runbooks/GATE3_SHADOW_RUNBOOK.md docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md docs/dev_logs/2026-04-10_kill_switch_contract_fix.md
 M .dockerignore
 M docker-compose.yml
 M docs/CURRENT_STATE.md
 M docs/PARTNER_DEPLOYMENT_GUIDE_docker.md
 M docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md
 M docs/runbooks/GATE3_SHADOW_RUNBOOK.md
 M docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md
?? docs/dev_logs/2026-04-10_kill_switch_contract_fix.md

git diff --stat -- docker-compose.yml .dockerignore docs/CURRENT_STATE.md docs/PARTNER_DEPLOYMENT_GUIDE_docker.md docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md docs/runbooks/GATE3_SHADOW_RUNBOOK.md docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md docs/dev_logs/2026-04-10_kill_switch_contract_fix.md
 .dockerignore                                   |  1 -
 docker-compose.yml                              |  1 -
 docs/CURRENT_STATE.md                           | 15 ++++++++++-----
 docs/PARTNER_DEPLOYMENT_GUIDE_docker.md         | 11 +++++++----
 docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md | 11 +++++++----
 docs/runbooks/GATE3_SHADOW_RUNBOOK.md           |  2 +-
 docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md         |  8 ++++----
 7 files changed, 29 insertions(+), 20 deletions(-)

Note: the new dev log is untracked, so it appears in `git status --short` but not in `git diff --stat`.
```

## Historical/internal docs intentionally left untouched

- `.planning/**` references to the old root mount were left unchanged because the task explicitly excluded hidden tool roots.
- Historical dev logs such as `docs/dev_logs/2026-04-04_docker-full-stack.md` and `docs/dev_logs/2026-04-05_docker_perf_hygiene.md` were left intact to preserve the record of what was true when those logs were written.
- Historical specs/dev logs that still show old `touch` examples, such as `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` and `docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md`, were left unchanged because current operator docs no longer point operators to them for active procedures.
