# Dev Log: RIS Phase 2 Operational Contract Spec

**Date:** 2026-04-07
**Task:** Create a concise RIS Phase 2 implementation contract spec with no code changes
**Scope:** Docs only under `docs/specs/` and `docs/dev_logs/`

## Files changed and why

| File | Why |
|---|---|
| `docs/specs/SPEC-ris-phase2-operational-contracts.md` | Rewrote the existing draft at the requested path into a tighter implementation contract that matches the locked Phase 2 decisions, references current repo truth, and is short enough for atomic follow-on prompts. |
| `docs/dev_logs/2026-04-07_ris_phase2_operational_contract_spec.md` | Mandatory session log with files changed, commands run, verification results, decisions made, and open questions for the next prompt. |

## Commands run + output

```powershell
Get-Content packages\research\evaluation\providers.py -TotalCount 220
```

Output summary:

- Confirmed only `manual` and `ollama` are implemented today.
- Confirmed cloud providers are recognized but not implemented.

```powershell
Get-Content packages\research\evaluation\evaluator.py -TotalCount 220
```

Output summary:

- Confirmed near-duplicate detection already exists and runs before scoring in the current evaluator path.

```powershell
Get-Content packages\research\scheduling\scheduler.py -TotalCount 140
```

Output summary:

- Confirmed the default scheduler surface is APScheduler-based.

```powershell
Get-Content docs\adr\0013-ris-n8n-pilot-scoped.md -TotalCount 220
```

Output summary:

- Confirmed n8n is a scoped opt-in pilot.
- Confirmed APScheduler remains the default stack assumption.

```powershell
Get-Content tools\cli\research_health.py -TotalCount 160
Get-Content tools\cli\research_stats.py -TotalCount 160
```

Output summary:

- Confirmed `research-health` and `research-stats` CLI surfaces already exist.

```powershell
Test-Path packages\research\evaluation\ris_eval_config.json
Test-Path docs\specs\ris_eval_config.json
Test-Path kb\rag\eval\ris_eval_config.json
```

Output:

```text
False
False
False
```

```powershell
Test-Path docs/specs/SPEC-ris-phase2-operational-contracts.md -PathType Leaf
```

Output:

```text
True
```

```powershell
cmd /c rg -n "weighted composite|pending_review|manual reserve|execution_id|research usefulness" docs/specs/SPEC-ris-phase2-operational-contracts.md
```

Output:

```text
Access is denied.
```

```powershell
Select-String -Path docs/specs/SPEC-ris-phase2-operational-contracts.md -Pattern 'weighted composite|pending_review|manual reserve|execution_id|research usefulness' | ForEach-Object { "{0}:{1}:{2}" -f $_.Path, $_.LineNumber, $_.Line.Trim() }
```

Output summary:

- Matches found for all required coverage terms: `weighted composite`, `pending_review`, `manual reserve`, `execution_id`, and `research usefulness`.

## Test results

Verification checks run: 2

- Passed: 2
- Failed: 0

Checks:

1. Spec existence check: PASS
2. Required coverage-term check: PASS

Note:

- Direct `rg` execution is blocked in this shell with `Access is denied`, so equivalent coverage verification was completed with PowerShell `Select-String`.

## Decisions made

- Replaced the earlier draft at the requested spec path instead of adding a second overlapping RIS Phase 2 contract file.
- Kept the spec concrete but non-code-heavy by locking formulas, thresholds, queue intent, budget behavior, reporting requirements, and idempotency rules without adding pseudocode, migrations, or workflow detail.
- Referenced current repo truth directly: provider support is `manual` and `ollama` only, near-duplicate detection already exists, `research-health` and `research-stats` already exist, APScheduler is the default scheduler, n8n is opt-in only, and `ris_eval_config.json` is still absent.
- Kept Phase 2 monitoring scope operational only and explicitly separated ingestion quality and research usefulness from any strategy recommendation scope.

## Open questions for next prompt

1. What exact storage shape should the `pending_review` audit trail use: companion SQLite table or another append-only artifact in the same operational area?
2. Where should `execution_id` be minted for retry semantics: acquire step, ingest step, or evaluation orchestration boundary?
3. What exact env var names should map to the future `ris_eval_config.json` defaults for thresholds, budgets, and reporting?
4. What exact nearest-neighbor count and similarity threshold should be used after canonical and near-duplicate checks for novelty context injection?
