---
phase: quick-260407-lpr
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/PLAN_OF_RECORD.md
  - docs/reference/RAGfiles/RIS_OVERVIEW.md
  - docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md
  - docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md
  - docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "RIS_OVERVIEW.md header reads Version 1.1 and contains a changelog section listing all additions"
    - "PLAN_OF_RECORD.md LLM/signals row authorizes Tier 1 free APIs for RIS evaluation only"
    - "RIS_03 specifies fail-closed rule, weighted composite gate, novelty dedup pre-step, review queue contract, and per-priority acceptance gates"
    - "RIS_06 specifies budget controls, env-var-primary n8n config, and ClickHouse idempotency"
    - "RIS_OVERVIEW.md contains a research-only posture statement"
    - "Dev log at docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md exists and lists every file edited"
  artifacts:
    - path: "docs/reference/RAGfiles/RIS_OVERVIEW.md"
      provides: "RIS roadmap v1.1 with changelog, posture statement, budget controls summary"
      contains: "Version.*1\\.1"
    - path: "docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md"
      provides: "Fail-closed rule, weighted composite, novelty dedup, review queue, acceptance gates"
      contains: "fail-closed"
    - path: "docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md"
      provides: "Budget controls, env-var primary, ClickHouse idempotency"
      contains: "execution_id"
    - path: "docs/PLAN_OF_RECORD.md"
      provides: "Narrow LLM policy reconciliation for RIS evaluation"
      contains: "Tier 1.*RIS"
    - path: "docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md"
      provides: "Reconciliation dev log"
  key_links:
    - from: "docs/PLAN_OF_RECORD.md"
      to: "docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md"
      via: "LLM Policy table Tier 1 row"
      pattern: "Tier 1.*Free cloud APIs"
    - from: "docs/reference/RAGfiles/RIS_OVERVIEW.md"
      to: "docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md"
      via: "companion file reference"
      pattern: "RIS_03"
---

<objective>
Freeze the RIS Phase 2 documentation contract before implementation by bumping the canonical
RIS roadmap suite from v1.0 to v1.1, reconciling PLAN_OF_RECORD.md LLM policy, and writing
the mandatory dev log.

Purpose: Lock down the ten Director-accepted additions so implementation work can reference
a stable contract. No code, no workflows, no schemas are touched.

Output: Updated RIS_OVERVIEW.md (v1.1), RIS_03_EVALUATION_GATE.md, RIS_06_INFRASTRUCTURE.md,
PLAN_OF_RECORD.md, and a dev log documenting every edit.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/PLAN_OF_RECORD.md
@docs/reference/RAGfiles/RIS_OVERVIEW.md
@docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md
@docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md
@docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Reconcile PLAN_OF_RECORD + bump RIS_OVERVIEW to v1.1</name>
  <files>docs/PLAN_OF_RECORD.md, docs/reference/RAGfiles/RIS_OVERVIEW.md</files>
  <action>
**PLAN_OF_RECORD.md** — In the Section 0 "Roadmap Authority and Open Deltas" table, update
the "LLM / signals" row's "Current implementation-policy truth" cell. Keep the existing
text and APPEND a single sentence:

"Exception: Tier 1 free cloud APIs (Gemini Flash, DeepSeek V3) are authorized for RIS
evaluation gate scoring only, per Master Roadmap v5.1 LLM Policy table."

Do NOT change any other cell or section. Do NOT broaden the exception beyond RIS evaluation.

**RIS_OVERVIEW.md** — Make these edits:
1. Change header metadata line from `**Version:** 1.0` to `**Version:** 1.1`.
2. Change `**Date:** March 2026` to `**Date:** April 2026`.
3. Add a `## Changelog` section immediately after the `**Companion Files:**` metadata line
   and before `## Why This System Exists`. Content:

```
## Changelog

### v1.1 (2026-04-07) — Phase 2 Contract Freeze

Additions accepted by Director before implementation:

1. **Fail-closed evaluation rule** — documents that fail LLM scoring default to REJECT, never silent pass-through. (RIS_03)
2. **Weighted composite gate** — canonical gate uses dimension weights (relevance=0.30, novelty=0.25, actionability=0.25, credibility=0.20); simple sum retained as diagnostic only. Per-dimension floor of 2 on relevance and credibility. (RIS_03)
3. **Novelty dedup pre-step** — deduplicate by canonical doc_id / source_url before nearest-neighbor embedding injection into the evaluation prompt. (RIS_03)
4. **Review queue contract** — KnowledgeStore SQLite `pending_review` table + CLI `research-review` flow for YELLOW-zone documents. (RIS_03, RIS_04)
5. **Budget controls** — global daily cap, per-source daily cap, manual-reserve hold-back for operator-submitted URLs. (RIS_06)
6. **Per-priority acceptance gates** — explicit pass/fail thresholds per source priority tier. (RIS_03)
7. **Segmented retrieval benchmark** — benchmark metrics reported by query class (factual, analytical, exploratory). (RIS_05)
8. **n8n env-var-primary config** — environment variables are the primary config source; n8n Variables are optional convenience only. (RIS_06)
9. **ClickHouse idempotency** — `execution_id` column + ReplacingMergeTree at storage level; code-level prefilter before INSERT. (RIS_06)
10. **Research-only posture statement** — added to Overview. (RIS_OVERVIEW)
```

4. Add a `## Posture Statement` section immediately before `## System Architecture`.
   Content:

```
## Posture Statement

RIS is a research-only system. It ingests, evaluates, and organizes knowledge.
It does NOT generate trading signals, place orders, or recommend positions.
Outputs from RIS (research reports, precheck verdicts, knowledge-base entries)
are informational inputs to human decision-making and strategy design processes.
No RIS output should be interpreted as a trading recommendation.
```

5. In the `## Development Phases` section, after `### Phase R1` and before `### Phase R2`,
   add a note:

```
> **v1.1 note:** Phase R1 deliverables now include the weighted composite gate,
> fail-closed rule, novelty dedup pre-step, review queue contract, per-priority
> acceptance gates, and budget controls. See RIS_03 and RIS_06 for full specifications.
```

Do NOT rewrite unrelated sections. Do NOT change the companion file index table.
  </action>
  <verify>
    <automated>grep -c "Version.*1\.1" docs/reference/RAGfiles/RIS_OVERVIEW.md && grep -c "Tier 1.*RIS" docs/PLAN_OF_RECORD.md && grep -c "Posture Statement" docs/reference/RAGfiles/RIS_OVERVIEW.md && grep -c "Changelog" docs/reference/RAGfiles/RIS_OVERVIEW.md</automated>
  </verify>
  <done>
    RIS_OVERVIEW.md reads v1.1, has Changelog with all 10 items, has Posture Statement,
    has v1.1 note in Development Phases. PLAN_OF_RECORD.md LLM/signals row includes the
    narrow Tier 1 RIS evaluation exception. No other PLAN_OF_RECORD sections changed.
  </done>
</task>

<task type="auto">
  <name>Task 2: Update RIS_03 (Evaluation Gate) and RIS_06 (Infrastructure) with contract specifics</name>
  <files>docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md, docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md</files>
  <action>
**RIS_03_EVALUATION_GATE.md** — Add or amend the following sections. Keep all existing
content; append or insert new subsections as specified.

1. **Fail-closed rule.** Insert a new subsection `### Fail-Closed Rule` immediately after
   the `## Architecture` section (after the ASCII diagram). Content:

   "If the LLM scorer returns an unparseable response, times out, or raises an exception,
   the document defaults to REJECT and is logged to the rejection JSONL with
   `reason: 'scorer_failure'`. Documents never silently pass through the gate.
   The only path to the knowledge store is a valid, parsed score above the acceptance
   threshold."

2. **Weighted composite gate.** In the `### Thresholds` subsection, add a note ABOVE the
   existing table:

   "**v1.1 canonical gate:** The primary acceptance gate uses a weighted composite score:
   `composite = relevance * 0.30 + novelty * 0.25 + actionability * 0.25 + credibility * 0.20`.
   Composite range is 1.0 to 5.0. Acceptance threshold: composite >= 3.0.
   Per-dimension floors: relevance >= 2 AND credibility >= 2 (a document scoring 1 on
   either dimension is auto-rejected regardless of composite).
   The simple-sum /20 score is retained as a diagnostic metric in evaluation output but
   is NOT the decision gate."

3. **Novelty dedup pre-step.** In the `## Deduplication` section, add a paragraph at the
   TOP of that section:

   "**v1.1 addition — canonical-ID dedup pre-step:** Before computing embedding similarity,
   check the incoming document's `doc_id` and `source_url` against existing entries in the
   knowledge store. If either matches an existing document, skip evaluation entirely and
   log as `reason: 'canonical_id_duplicate'`. This catches exact re-submissions (same URL
   fetched twice, same doc_id from re-run) without incurring an embedding computation.
   The embedding-based near-duplicate check (>0.92 cosine similarity) remains as the
   second dedup layer for content-similar documents from different sources."

4. **Review queue contract.** Add a new section `## Review Queue Contract` immediately
   after `## Rejection Review System`. Content:

   "YELLOW-zone documents (composite < 3.0 but not floor-rejected, or scorer disagreement)
   are written to a `pending_review` table in the KnowledgeStore SQLite database
   (`kb/rag/knowledge/knowledge.sqlite3`). Schema:

   ```sql
   CREATE TABLE IF NOT EXISTS pending_review (
       doc_id TEXT PRIMARY KEY,
       source_url TEXT,
       source_type TEXT,
       title TEXT,
       scores_json TEXT,        -- full scorer output
       eval_model TEXT,
       queued_at TEXT,           -- ISO-8601
       reviewed_at TEXT,         -- NULL until reviewed
       disposition TEXT          -- NULL | 'accept' | 'reject'
   );
   ```

   Operator action path: `python -m polytool research-review [--pending] [--accept DOC_ID] [--reject DOC_ID]`.
   Accepted documents are promoted to the knowledge store with `validation_status: 'human_accepted'`.
   Rejected documents are moved to the rejection log with `reason: 'human_rejected'`.
   Unreviewed items older than 30 days are auto-expired to rejection log with
   `reason: 'review_expired'`."

5. **Per-priority acceptance gates.** Add a new subsection `### Per-Priority Acceptance Gates`
   inside the Thresholds area, after the weighted composite note. Content:

   "Source priority tiers have explicit pass/fail thresholds:

   | Priority | Composite Threshold | Floor Override | Rationale |
   |----------|--------------------:|----------------|-----------|
   | Critical (operator-submitted) | >= 2.5 | None | Operator intent presumed; lower bar |
   | High (academic, curated blogs) | >= 3.0 | Standard floors | Default quality bar |
   | Medium (Reddit, Twitter, RSS) | >= 3.2 | Standard floors | Noisier sources need higher bar |
   | Low (auto-discovered) | >= 3.5 | Standard floors | Highest bar for unsupervised intake |

   If a source does not have an assigned priority, it defaults to Medium."

**RIS_06_INFRASTRUCTURE.md** — Add or amend the following. Keep all existing content.

1. **Budget controls.** Add a new section `## Ingestion Budget Controls` at the end of
   the file (before any closing line). Content:

   "### Global Daily Cap
   Maximum documents evaluated per calendar day across all sources. Default: 200.
   Configurable via `RIS_DAILY_EVAL_CAP` env var or `polytool.yaml` key
   `ris.budget.daily_cap`.

   ### Per-Source Daily Cap
   Maximum documents per source type per day. Defaults:
   - academic: 50
   - reddit: 40
   - twitter: 30
   - blog: 30
   - youtube: 20
   - github: 20
   - manual: 10 (see Manual Reserve below)

   Configurable via `polytool.yaml` key `ris.budget.per_source.<source_type>`.

   ### Manual Reserve
   Of the global daily cap, 10 slots are reserved for operator-submitted URLs
   (`research-acquire --url ...`). These slots cannot be consumed by automated
   ingestion. If the global cap is reached but manual reserve is not exhausted,
   manual submissions still proceed. Configurable via `RIS_MANUAL_RESERVE` env var
   or `polytool.yaml` key `ris.budget.manual_reserve`."

2. **n8n env-var-primary config.** Add a new subsection `### n8n Configuration Hierarchy`
   in the scheduling or n8n section (wherever n8n migration is discussed). Content:

   "Environment variables are the primary configuration source for RIS n8n workflows.
   n8n Variables (set via n8n UI or API) are an optional convenience layer that may
   mirror env vars for operator visibility but are NEVER the source of truth.

   Resolution order: `process.env.RIS_*` -> n8n Variables (if set) -> hardcoded defaults.

   This ensures that `docker compose` env files and `.env` remain the single config
   surface. Operators who prefer the n8n UI can set Variables, but code must always
   read env vars first."

3. **ClickHouse idempotency.** Add a new section `## ClickHouse Write Idempotency`
   (near the end, after budget controls). Content:

   "RIS writes to ClickHouse (evaluation metrics, ingestion events) must be idempotent.

   **Storage-level:** Tables receiving RIS writes use `ReplacingMergeTree` with
   `execution_id` (UUID, set per pipeline run) as the dedup key. ClickHouse will
   eventually merge duplicates on the same `execution_id + doc_id` pair.

   **Code-level prefilter:** Before issuing an INSERT batch, query ClickHouse for
   existing `execution_id` values from the current run. Skip rows already present.
   This prevents duplicate rows from accumulating between ReplacingMergeTree merges
   and avoids relying solely on eventual merge timing.

   This dual-layer approach follows the same pattern used by the existing trade
   dedup pipeline (`trade_uid` + ReplacingMergeTree)."

Do NOT rewrite existing sections. Append or insert only.
  </action>
  <verify>
    <automated>grep -c "fail-closed\|Fail-Closed" docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md && grep -c "weighted composite\|Weighted composite" docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md && grep -c "canonical_id_duplicate\|canonical-ID" docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md && grep -c "pending_review" docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md && grep -c "Per-Priority" docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md && grep -c "DAILY_EVAL_CAP\|daily_cap" docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md && grep -c "execution_id" docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md && grep -c "env-var\|Environment variables are the primary" docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md</automated>
  </verify>
  <done>
    RIS_03 contains fail-closed rule, weighted composite gate definition, canonical-ID
    dedup pre-step, review queue contract with pending_review schema, and per-priority
    acceptance gates table. RIS_06 contains budget controls (global/per-source/manual-reserve),
    n8n env-var-primary hierarchy, and ClickHouse write idempotency with execution_id +
    ReplacingMergeTree + code-level prefilter. No existing content removed.
  </done>
</task>

<task type="auto">
  <name>Task 3: Write mandatory dev log</name>
  <files>docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md</files>
  <action>
Create `docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md` with the following content:

```markdown
# Dev Log: RIS Phase 2 Documentation Contract Freeze (v1.1)

**Date:** 2026-04-07
**Task:** Freeze RIS Phase 2 documentation contract before implementation
**Scope:** DOCS-ONLY — no code, no workflows, no schemas, no migrations

## What Was Done

Bumped the RIS roadmap suite from v1.0 to v1.1, incorporating ten Director-accepted
additions into the canonical specification documents. Reconciled PLAN_OF_RECORD.md
LLM policy to authorize Tier 1 free APIs for RIS evaluation.

## Files Edited

| File | Change |
|------|--------|
| `docs/PLAN_OF_RECORD.md` | Added narrow Tier 1 free-API exception for RIS evaluation in LLM/signals row |
| `docs/reference/RAGfiles/RIS_OVERVIEW.md` | Bumped to v1.1, added Changelog, Posture Statement, v1.1 note in Development Phases |
| `docs/reference/RAGfiles/RIS_03_EVALUATION_GATE.md` | Added: fail-closed rule, weighted composite gate, canonical-ID dedup pre-step, review queue contract (pending_review table), per-priority acceptance gates |
| `docs/reference/RAGfiles/RIS_06_INFRASTRUCTURE.md` | Added: ingestion budget controls (global/per-source/manual-reserve), n8n env-var-primary config hierarchy, ClickHouse write idempotency (execution_id + ReplacingMergeTree + prefilter) |

## Additions Included (all 10)

1. Fail-closed evaluation rule
2. Weighted composite gate (relevance=0.30, novelty=0.25, actionability=0.25, credibility=0.20) + per-dimension floor (relevance>=2, credibility>=2); simple sum /20 retained as diagnostic only
3. Novelty dedup by canonical doc_id / source_url before embedding similarity check
4. Review queue contract: KnowledgeStore SQLite pending_review table + CLI research-review flow
5. Budget controls: global daily cap (200), per-source caps, manual-reserve hold-back (10)
6. Explicit per-priority acceptance gates (Critical>=2.5, High>=3.0, Medium>=3.2, Low>=3.5)
7. Segmented retrieval benchmark metrics by query class (factual, analytical, exploratory) — noted in changelog; detailed spec deferred to RIS_05 update
8. n8n env-var fallback as primary config source; Variables optional convenience only
9. ClickHouse idempotency: execution_id + ReplacingMergeTree + code-level prefilter
10. Research-only posture statement added to RIS_OVERVIEW

## PLAN_OF_RECORD Reconciliation

The LLM/signals row previously read: "no external LLM API calls."
This conflicted with the Master Roadmap v5.1 LLM Policy table which explicitly lists
Tier 1 free cloud APIs (DeepSeek V3, Gemini Flash) for automated evaluation.

Resolution: appended a single-sentence exception scoped to RIS evaluation gate scoring only.
The exception does not authorize Tier 1 APIs for trading signals, order placement, or
any non-RIS use case. This aligns PLAN_OF_RECORD with the already-governing Master Roadmap v5.1.

## Cross-Reference Conflict Check

- `docs/ARCHITECTURE.md` — No conflict. Architecture doc defers to Master Roadmap v5.1 for
  LLM policy; does not repeat the "no external LLM API calls" restriction.
- `CLAUDE.md` — No conflict. References PLAN_OF_RECORD as authoritative. The "no external
  LLM API calls" text in CLAUDE.md's constraints section refers to "shipped outputs" and
  "trading recommendations", not to RIS evaluation scoring.
- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5_1.md` — No conflict. v5.1 already authorizes
  Tier 1 free APIs for "scraper evaluation" and "signal classification."

## What Was NOT Done

- No code changes. No workflow JSON. No tests. No Docker config. No schema migrations.
- RIS_05 (Synthesis Engine) was NOT edited. Item 7 (segmented benchmark by query class)
  is noted in the v1.1 changelog but the detailed spec belongs in RIS_05; that file will
  be updated when implementation planning for the synthesis engine begins.
- No changes to RIS_01, RIS_02, RIS_04, or RIS_07 companion files.
- No broadening of LLM policy beyond RIS evaluation.

## Open Questions

None. All ten additions are now frozen in the canonical docs. Implementation can proceed
against this v1.1 contract.
```
  </action>
  <verify>
    <automated>test -f docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md && grep -c "v1.1" docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md</automated>
  </verify>
  <done>
    Dev log exists at docs/dev_logs/2026-04-07_ris_phase2_doc_reconciliation.md, lists all
    5 files edited, all 10 additions, the PLAN_OF_RECORD reconciliation rationale, the
    cross-reference conflict check, and the explicit list of what was NOT done.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| N/A | Documentation-only change; no runtime trust boundaries affected |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-lpr-01 | Information Disclosure | LLM policy broadening | accept | Exception is scoped to RIS evaluation only; dev log documents the narrow scope; PLAN_OF_RECORD wording prevents broader interpretation |
</threat_model>

<verification>
1. RIS_OVERVIEW.md header reads "Version: 1.1" and "Date: April 2026"
2. RIS_OVERVIEW.md has a Changelog section listing all 10 additions
3. RIS_OVERVIEW.md has a Posture Statement section
4. RIS_03 contains fail-closed rule, weighted composite definition, canonical-ID dedup, review queue contract with SQL schema, per-priority acceptance gates table
5. RIS_06 contains budget controls, n8n env-var-primary hierarchy, ClickHouse idempotency
6. PLAN_OF_RECORD LLM/signals row includes Tier 1 RIS exception
7. Dev log exists and is complete
8. No code files, workflow JSON, test files, Docker config, or schema files were modified
</verification>

<success_criteria>
- All 5 documentation files exist and contain the specified additions
- No code, workflow, test, Docker, or schema files were touched
- The PLAN_OF_RECORD LLM policy reconciliation is narrow (RIS evaluation only)
- The dev log documents every edit and the cross-reference conflict check
- Existing content in all edited files is preserved (append/insert only)
</success_criteria>

<output>
After completion, create `.planning/quick/260407-lpr-freeze-ris-phase-2-documentation-contrac/260407-lpr-SUMMARY.md`
</output>
