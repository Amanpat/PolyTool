# Phase 0 Operator Docs v5

**Date**: 2026-03-21
**Type**: Docs-only
**Scope guard**: Only `docs/OPERATOR_SETUP_GUIDE.md`,
`docs/WINDOWS_DEVELOPMENT_GOTCHAS.md`, and this dev log were created.

---

## Purpose

Create the missing Phase 0 operator docs called for by roadmap v5:

- `docs/OPERATOR_SETUP_GUIDE.md`
- `docs/WINDOWS_DEVELOPMENT_GOTCHAS.md`

Both docs were written as practical setup references, using only grounded repo
guidance plus clearly labeled `Operator Decision Needed` placeholders where the
repo cannot know the final operator-specific value.

---

## Files Changed And Why

| File | Why it changed |
|------|----------------|
| `docs/OPERATOR_SETUP_GUIDE.md` | Added the missing Phase 0 setup guide covering account setup, cold-vs-hot wallet architecture, funding flow, `py-clob-client` credential derivation, reserves, tax tracking, capital allocation, and the Canadian partner machine checklist. |
| `docs/WINDOWS_DEVELOPMENT_GOTCHAS.md` | Added the missing Windows-specific operating guide covering the observed cp1252 Unicode failure, Docker Desktop / WSL2 sandbox-vs-real-user mismatch, path separator and quoting issues, `.env` encoding notes, PowerShell-safe command tips, and a short troubleshooting checklist. |
| `docs/dev_logs/2026-03-21_phase0_operator_docs_v5.md` | Recorded sources, commands, outputs, test results, and the remaining operator-owned placeholders. |

No code, tests, config files, runbooks, roadmap files, or branches were edited.

---

## Sources Used

Required source docs and logs reviewed:

- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`
- `docs/OPERATOR_QUICKSTART.md`
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`
- `docs/dev_logs/2026-03-17_fetch_price_2min_windows_stdout_fix.md`
- `docs/dev_logs/2026-03-18_docker_desktop_engine_recovery_attempt.md`
- `docs/dev_logs/2026-03-18_benchmark_closure_after_docker_recovery.md`
- `docs/dev_logs/2026-03-21_phase1_docs_closeout.md`

Additional repo-grounding used for exact env names and PowerShell behavior:

- `packages/polymarket/simtrader/execution/wallet.py`
- `.env.example`
- `docs/features/FEATURE-trackA-live-clob-wiring.md`
- `docs/README_SIMTRADER.md`
- `docs/RUNBOOK_MANUAL_EXAMINE.md`
- `docs/dev_logs/2026-03-16_silver_reconstructor_operational_v1.md`
- `docs/specs/SPEC-0002-llm-bundle-coverage.md`
- `docs/adr/0004-clickhouse-host-defaults.md`
- `README.md`
- `tools/cli/examine.py`

---

## Commands Run + Output

### 1. Read the required source docs and dev logs

```powershell
Get-Content docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md
Get-Content docs/OPERATOR_QUICKSTART.md
Get-Content docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md
Get-Content docs/dev_logs/2026-03-17_fetch_price_2min_windows_stdout_fix.md
Get-Content docs/dev_logs/2026-03-18_docker_desktop_engine_recovery_attempt.md
Get-Content docs/dev_logs/2026-03-18_benchmark_closure_after_docker_recovery.md
Get-Content docs/dev_logs/2026-03-21_phase1_docs_closeout.md
```

Output summary:

- Confirmed roadmap v5 explicitly calls for both missing docs.
- Confirmed the required operator topics: account setup, hot/cold wallet split,
  funding flow, `py-clob-client` credential derivation, reserves, tax logging,
  and the Canadian host checklist.
- Confirmed the Windows issues already observed in-repo: cp1252 Unicode
  failures, Docker Desktop / WSL2 access differing by Windows user context,
  and path-separator problems.

### 2. Read exact credential and env references

```powershell
Get-Content packages/polymarket/simtrader/execution/wallet.py
Get-Content .env.example
Get-Content docs/features/FEATURE-trackA-live-clob-wiring.md
Get-Content docs/README_SIMTRADER.md | Select-Object -Index (260..320)
```

Output summary:

- Confirmed live credential names are `PK`, `CLOB_API_KEY`,
  `CLOB_API_SECRET`, and `CLOB_API_PASSPHRASE`.
- Confirmed the repo already exposes `derive_and_print_creds()` for one-time
  credential bootstrap using `py-clob-client`.
- Confirmed the repo documents `Copy-Item .env.example .env` and Docker
  bring-up commands for local setup.

### 3. Read Windows-specific supporting references

```powershell
Get-Content docs/dev_logs/2026-03-16_silver_reconstructor_operational_v1.md | Select-Object -Index (72..92)
Get-Content docs/specs/SPEC-0002-llm-bundle-coverage.md | Select-Object -Index (46..55)
Get-Content docs/README_SIMTRADER.md | Select-Object -Index (124..138)
Get-Content docs/RUNBOOK_MANUAL_EXAMINE.md | Select-Object -Index (170..180)
Get-Content tools/cli/examine.py | Select-Object -Index (132..160)
Get-Content docs/adr/0004-clickhouse-host-defaults.md | Select-Object -First 80
```

Output summary:

- Confirmed a real Windows backslash-vs-forward-slash bug had already occurred.
- Confirmed serialized path guidance already prefers forward slashes.
- Confirmed PowerShell JSON quoting guidance already exists in repo docs.
- Confirmed `--user "@name"` quoting guidance already exists in repo docs.
- Confirmed `.env` loaders read UTF-8 and do not strip a BOM.
- Confirmed Windows host-side ClickHouse guidance uses `localhost`, not Docker
  service name `clickhouse`.

### 4. Requested validation command

```powershell
python -m polytool --help
```

Output summary:

- Command succeeded.
- Printed the top-level PolyTool help surface, including the Research, RAG,
  SimTrader, and Data Import command groups.
- No code changes were needed to make the help command run for this docs task.

### 5. Requested diff review command

```powershell
git diff -- docs/OPERATOR_SETUP_GUIDE.md docs/WINDOWS_DEVELOPMENT_GOTCHAS.md
```

Output summary:

- Output was empty because both docs were newly created and remained untracked.
- No code files appeared in the requested docs diff.

### 6. Status confirmation for the new docs

```powershell
git status --short -- docs/OPERATOR_SETUP_GUIDE.md docs/WINDOWS_DEVELOPMENT_GOTCHAS.md docs/dev_logs/2026-03-21_phase0_operator_docs_v5.md
```

Output:

```text
?? docs/OPERATOR_SETUP_GUIDE.md
?? docs/WINDOWS_DEVELOPMENT_GOTCHAS.md
?? docs/dev_logs/2026-03-21_phase0_operator_docs_v5.md
```

Meaning:

- The two new docs and the required dev log exist as new docs-only files.
- Nothing in this check indicated code or test-file edits.

---

## Test Results

| Check | Result |
|------|--------|
| `python -m polytool --help` | Passed |
| `git diff -- docs/OPERATOR_SETUP_GUIDE.md docs/WINDOWS_DEVELOPMENT_GOTCHAS.md` | Ran successfully; empty output because the docs are new and untracked |
| `git status --short -- docs/OPERATOR_SETUP_GUIDE.md docs/WINDOWS_DEVELOPMENT_GOTCHAS.md docs/dev_logs/2026-03-21_phase0_operator_docs_v5.md` | Passed; confirmed the three new docs files exist |
| Code changes made | None |

---

## Open Placeholders Requiring Operator Input

These were intentionally left as `Operator Decision Needed` placeholders in the
new guide because the repo cannot know them truthfully:

- Primary live platform
- Primary exchange
- Cold wallet custody method
- Hot wallet product and address
- Stage 1 funding target
- MATIC gas reserve amount
- USDC withdrawal buffer amount
- Tax reserve account / wallet
- Compute budget account
- Allocation cadence for the 50/30/20 rule
- Tax ledger / accountant owner
- Reporting time zone
- Canadian host owner and backup access path
- Primary alert channel
- Polygon RPC provider

---

## Final Result

The missing Phase 0 operator docs were added as docs-only changes. They are
repo-aware, practical, and limited to grounded guidance plus clearly labeled
operator-owned placeholders.
