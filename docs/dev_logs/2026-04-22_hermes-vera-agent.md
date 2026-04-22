# 2026-04-22 Hermes Vera Agent Profile Setup

## Scope

- Objective: create a dedicated Hermes profile named `vera-hermes-agent`, clone current config into it, activate it, verify base chat, and leave gateway/cron unconfigured.
- Repo changes: this dev log only.
- Non-goals respected: no app code changes, no live bot wiring, no gateway setup, no cron setup, no secrets added to git.

## Files Changed And Why

- `docs/dev_logs/2026-04-22_hermes-vera-agent.md` - records the Hermes profile setup and verification results for handoff.

## Commands Run And Output Summary

1. `git status --short`
   - Result: repo already had extensive unrelated modified and untracked files in `config/`, `docs/`, and `docs/obsidian-vault/`.
   - Action taken: did not modify or revert unrelated work.

2. `git log --oneline -5`
   - Result:
     - `05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts`
     - `0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix`
     - `2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)`
     - `5962d46 docs(simtrader): PMXT Deliverable B docs close-out`
     - `efb6f01 feat(simtrader): PMXT Deliverable B -- merge-ready sports strategies`

3. `python -m polytool --help`
   - Result: CLI loaded successfully and printed the PolyTool command list.

4. `hermes --version`
5. `hermes profile list`
   - Result on Windows PowerShell: `hermes` was not on Windows `PATH`.

6. `wsl bash -lc "command -v hermes && hermes --version"`
   - Result:
     - Hermes binary found at `/home/patel/.local/bin/hermes`
     - Version: `Hermes Agent v0.10.0 (2026.4.16)`

7. `wsl bash -lc "hermes profile list"`
   - Result before changes:
     - Only `default` existed
     - Gateway state for `default`: `stopped`

8. `wsl bash -lc "hermes profile show default"`
   - Result:
     - Profile: `default`
     - Model: `deepseek-v3.2 (ollama-cloud)`
     - Gateway: `stopped`
     - Skills: `72`
     - `.env`: `exists`
     - `SOUL.md`: `exists`

9. `wsl bash -lc "hermes profile create vera-hermes-agent --clone && hermes profile use vera-hermes-agent && hermes profile show vera-hermes-agent"`
   - Result:
     - Profile created at `/home/patel/.hermes/profiles/vera-hermes-agent`
     - Clone summary: `Cloned config, .env, SOUL.md from default.`
     - Bundled skills synced: `72`
     - Wrapper created: `/home/patel/.local/bin/vera-hermes-agent`
     - Active profile switched to `vera-hermes-agent`
     - New profile show output:
       - Model: `deepseek-v3.2 (ollama-cloud)`
       - Gateway: `stopped`
       - Skills: `72`
       - `.env`: `exists`
       - `SOUL.md`: `exists`
       - Alias: `/home/patel/.local/bin/vera-hermes-agent`

10. `wsl bash -lc "hermes profile list"`
    - Result after changes:
      - `default`
      - `vera-hermes-agent`
      - Active marker on `vera-hermes-agent`

11. `wsl bash -lc "hermes -p vera-hermes-agent gateway status"`
    - Result: `Gateway is not running`

12. `wsl bash -lc "hermes -p vera-hermes-agent cron list"`
    - Result: `No scheduled jobs.`

13. `docker version`
    - Result:
      - Docker client available: `29.0.1`
      - Docker Desktop server available: `4.52.0`
      - Conclusion: Docker is available and should be the preferred backend later if Hermes backend work is added.

14. `wsl bash -lc "hermes -p vera-hermes-agent chat -Q -q 'Reply with exactly: vera hermes agent ready'"`
    - Result:
      - Exit code `1`
      - Session created: `20260422_180321_1cc4a7`
      - Follow-up log check showed: `Non-retryable client error: Error code: 400`

15. `wsl bash -lc "hermes auth list"`
    - Result:
      - `ollama-cloud (1 credentials)`
      - Credential source shown as `env:OLLAMA_API_KEY`

16. `wsl bash -lc "hermes -p default chat -Q -q 'Reply with exactly: default ready'"`
    - Result:
      - Successful reply: `default ready`
      - This confirmed the inherited model/provider path was generally usable on the machine.

17. `wsl bash -lc "vera-hermes-agent chat -Q -q 'Reply with exactly: vera hermes agent ready'"`
    - Result:
      - Successful reply: `vera hermes agent ready`
      - Session id: `20260422_180434_f134fb`

## Clone Result

- Clone succeeded: yes.
- Config-only clone requirement respected: yes. Used `--clone`, not `--clone-all`.
- Active profile after setup: `vera-hermes-agent`.

## First Successful Reply

- Exact reply: `vera hermes agent ready`
- Command used: `wsl bash -lc "vera-hermes-agent chat -Q -q 'Reply with exactly: vera hermes agent ready'"`

## Docker Availability

- Docker is available on this machine.
- Recommended future backend choice: prefer Docker when backend isolation is configured later.

## Decisions Made

- Used the existing WSL Hermes installation because `hermes` was not on Windows `PATH`, but Hermes was installed and working in Ubuntu WSL.
- Kept the work strictly at profile/config level.
- Left messaging gateway unconfigured and stopped.
- Left cron empty and did not create scheduled tasks.

## Open Questions Or Blockers

- No blocker remains for the profile-creation objective.
- The first direct `hermes -p vera-hermes-agent chat ...` attempt returned a transient/non-retryable `400`, but the profile wrapper `vera-hermes-agent chat ...` succeeded immediately after.

## Recommended Next Step

- Gateway later if remote messaging access is needed.
- Cron later if scheduled Hermes tasks are needed.
- If either is added, prefer Docker as the backend on this machine.
