# Dev Log: RIS Phase 2 Operational Spec

**Date:** 2026-04-07
**Task:** Create a focused implementation spec for RIS Phase 2 operational contracts
**Scope:** Docs-only. No code, tests, configs, workflows, docker, or migrations changed.

---

## Files changed and why

| File | Why |
|------|-----|
| `docs/specs/SPEC-ris-phase2-operational-contracts.md` | New implementation contract covering the locked Phase 2 rules for fail-closed evaluation, weighted composite gating, novelty dedup ordering, review queue schema, budgets, retrieval benchmark reporting, idempotency, config precedence, and priority acceptance gates. |
| `docs/dev_logs/2026-04-07_ris_phase2_operational_spec.md` | Mandatory session log recording files changed, commands run, verification results, decisions made, and follow-up questions. |

---

## Commands run + output

```powershell
Get-Content docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md -TotalCount 260
```

Output summary:

- Confirmed fail-closed behavior with `reject_reason = "scorer_failure"`.
- Confirmed weighted composite formula `0.30 / 0.25 / 0.25 / 0.20`.
- Confirmed standard floors `relevance >= 2` and `credibility >= 2`.
- Confirmed acceptance thresholds `2.5 / 3.0 / 3.2 / 3.5`.
- Confirmed `pending_review` as the review queue and canonical dedup on `doc_id` / `source_url`.

```powershell
Get-Content docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md -TotalCount 260
```

Output summary:

- Confirmed global daily cap `200`.
- Confirmed per-source caps: academic `50`, reddit `40`, twitter `30`, blog `30`, youtube `20`, github `20`, manual `10`.
- Confirmed manual reserve `10`.
- Confirmed env-var-first config precedence and optional n8n Variables.
- Confirmed ClickHouse idempotency contract: `execution_id`, `ReplacingMergeTree`, and code-side prefilter.

```powershell
Get-Content docs/reference/RAGfiles/RIS_OVERVIEW.md -TotalCount 220
```

Output summary:

- Confirmed the Director-approved Phase 2 decision list.
- Confirmed the RIS research-only posture statement.

```powershell
Get-Content packages/polymarket/rag/eval.py -TotalCount 260
Get-Content packages/polymarket/rag/eval.py | Select-Object -Last 220
```

Output summary:

- Confirmed retrieval benchmark metric names already used by the repo:
  `mean_recall_at_k`, `mean_mrr_at_k`, `total_scope_violations`,
  `queries_with_violations`, and `mean_latency_ms`.
- Confirmed report artifacts are `report.json` and `summary.md`.
- Confirmed benchmark artifacts are timestamped under `kb/rag/eval/reports/`.

```powershell
Test-Path docs/specs/SPEC-ris-phase2-operational-contracts.md -PathType Leaf
```

Output:

```text
True
```

```powershell
Select-String -Path docs/specs/SPEC-ris-phase2-operational-contracts.md -Pattern 'pending_review|weighted composite|manual reserve|ReplacingMergeTree|query class'
```

Output summary:

- Matches found for all required contract terms:
  `pending_review`, `weighted composite`, `manual reserve`,
  `ReplacingMergeTree`, and `query class`.

Note:

- `rg.exe` was not executable in this environment (`Access is denied`), so PowerShell
  `Select-String` was used as the equivalent verification command.

---

## Test results

Verification checks run: 2

- Passed: 2
- Failed: 0

Checks:

1. Spec file existence check: PASS
2. Required contract-term coverage check: PASS

---

## Decisions made

- Used RIS v1.1 reference docs and the existing retrieval eval harness as the authority
  for thresholds, budget defaults, config precedence, and benchmark artifact names.
- Mapped the accepted source tiers into explicit `priority_1` through `priority_4`
  labels with human-readable aliases so later coding prompts can implement them atomically.
- Treated escalation budget as accounting within the approved daily and per-source caps,
  not as a new extra allowance.
- Required an append-only audit trail for review actions while deliberately leaving the
  exact audit storage shape open for the implementation prompt.
- Kept the spec implementation-ready but avoided full SQL, migrations, workflow JSON,
  or code pseudocode beyond the minimum formula and field names.

---

## Open questions for next prompt

1. Should the review audit trail live in a companion SQLite table (for example
   `pending_review_audit`) or in a separate append-only artifact tied to the same DB path?
2. What exact CLI surface should `research-review` expose for deferred items
   (`--defer`, `--defer-until`, batch review, notes)?
3. How should `budget_exhausted` items surface operationally: skip-only logging, a retry
   queue, or both?
4. How should existing retrieval eval suites be backfilled with `query_class`
   (`factual`, `analytical`, `exploratory`) so segmented reporting can start cleanly?
