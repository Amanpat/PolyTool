---
phase: quick-260408-oyu
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/research/metrics.py
  - packages/research/monitoring/health_checks.py
  - tools/cli/research_health.py
  - tools/cli/research_stats.py
  - tests/test_ris_monitoring.py
  - docs/RIS_OPERATOR_GUIDE.md
  - docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "research-stats summary --json includes provider_route_distribution, provider_failure_counts, review_queue_depth, and disposition_distribution fields"
    - "research-health --json includes real model_unavailable check driven by eval artifact provider failure data, not a stub"
    - "research-health --json includes review_queue_backlog check driven by pending_review table, not a stub"
    - "research-health output distinguishes healthy, degraded, blocked_on_setup, and failure states in the overall summary"
    - "research-stats export writes metrics_snapshot.json with Phase 2 routing/queue/disposition fields"
    - "All existing tests pass with no regressions"
  artifacts:
    - path: "packages/research/metrics.py"
      provides: "Phase 2 metrics aggregation including routing, failures, queue depth, dispositions"
    - path: "packages/research/monitoring/health_checks.py"
      provides: "Real model_unavailable and review_queue_backlog health checks"
    - path: "tools/cli/research_health.py"
      provides: "Operator health output with status categories"
    - path: "tools/cli/research_stats.py"
      provides: "Stats export with Phase 2 fields"
    - path: "docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md"
      provides: "Dev log for this work"
  key_links:
    - from: "packages/research/metrics.py"
      to: "packages/research/evaluation/artifacts.py"
      via: "load_eval_artifacts() to extract routing_decision and provider_events"
      pattern: "routing_decision|provider_events"
    - from: "packages/research/metrics.py"
      to: "packages/polymarket/rag/knowledge_store.py"
      via: "sqlite3 query on pending_review table"
      pattern: "pending_review"
    - from: "packages/research/monitoring/health_checks.py"
      to: "packages/research/metrics.py"
      via: "Uses new metrics fields for real health evaluation"
      pattern: "provider_failure|review_queue"
---

<objective>
Finish Phase 2 RIS monitoring truth: expand metrics collection, wire deferred health checks,
improve operator-facing output clarity, and update stats export.

Purpose: Turn Phase 2 monitoring from "basic counts" into "operator-usable truth" so that
research-health and research-stats reflect real evaluator routing, provider failures,
review queue state, and disposition breakdowns without overbuilding dashboards.

Output: Updated metrics.py, health_checks.py, CLI tools, tests, operator guide, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@packages/research/metrics.py
@packages/research/monitoring/health_checks.py
@packages/research/monitoring/run_log.py
@packages/research/evaluation/artifacts.py
@packages/research/evaluation/evaluator.py
@packages/research/ingestion/review_integration.py
@packages/polymarket/rag/knowledge_store.py
@tools/cli/research_health.py
@tools/cli/research_stats.py
@tests/test_ris_monitoring.py
@docs/RIS_OPERATOR_GUIDE.md
@docs/specs/SPEC-ris-phase2-operational-contracts.md

<interfaces>
<!-- Key types and contracts the executor needs. -->

From packages/research/evaluation/artifacts.py:
```python
@dataclass
class ProviderEvent:
    provider_name: str
    model_id: str
    route_role: str        # "primary" | "escalation" | "fallback"
    status: str            # "success" | "error" | "invalid"
    selected: bool
    attempt_number: int
    failure_reason: Optional[str]  # "rate_limited" | "provider_unavailable" | "timeout" | ...
    error_message: Optional[str]

@dataclass
class RoutingDecision:
    mode: str
    primary_provider: str
    escalation_provider: Optional[str]
    fallback_provider: Optional[str]
    selected_provider: Optional[str]
    selected_model: Optional[str]
    final_reason: str
    attempts: int
    escalated: bool
    used_fallback: bool

@dataclass
class EvalArtifact:
    doc_id: str
    gate: str              # "ACCEPT" | "REVIEW" | "REJECT"
    provider_events: list[dict]
    routing_decision: Optional[dict]
    source_family: str
    scores: Optional[dict]
    # ... other fields
```

From packages/research/monitoring/health_checks.py:
```python
HealthStatus = Literal["GREEN", "YELLOW", "RED"]

@dataclass
class HealthCheckResult:
    check_name: str
    status: HealthStatus
    message: str
    data: dict

def evaluate_health(runs, *, window_hours=48, audit_disagreement_rate=None) -> List[HealthCheckResult]
```

From packages/research/monitoring/run_log.py:
```python
@dataclass
class RunRecord:
    pipeline: str
    exit_status: Literal["ok", "error", "partial"]
    accepted: int
    rejected: int
    errors: int
    metadata: dict
```

From packages/research/ingestion/review_integration.py:
```python
DISPOSITION_ACCEPTED = "accepted"
DISPOSITION_QUEUED = "queued_for_review"
DISPOSITION_REJECTED = "rejected"
DISPOSITION_BLOCKED = "blocked"
```

KnowledgeStore pending_review table columns:
```sql
pending_review (
    id TEXT PRIMARY KEY,
    status TEXT CHECK(status IN ('pending','accepted','rejected','deferred')),
    gate TEXT,
    provider_name TEXT,
    eval_model TEXT,
    weighted_score REAL,
    source_family TEXT,
    created_at TEXT,
    updated_at TEXT,
    ...
)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Expand metrics collection and wire deferred health checks</name>
  <files>
    packages/research/metrics.py
    packages/research/monitoring/health_checks.py
    tests/test_ris_monitoring.py
  </files>
  <behavior>
    - Test: collect_ris_metrics returns provider_route_distribution dict counting how many evals used each selected_provider (e.g. {"gemini": 5, "deepseek": 2, "ollama": 1})
    - Test: collect_ris_metrics returns provider_failure_counts dict counting failures by failure_reason (e.g. {"provider_unavailable": 3, "rate_limited": 1})
    - Test: collect_ris_metrics returns review_queue dict with queue_depth (int), by_status (dict), by_gate (dict) from pending_review table
    - Test: collect_ris_metrics returns disposition_distribution dict counting ACCEPT, REVIEW, REJECT, BLOCKED (BLOCKED = gate REJECT with reject_reason scorer_failure)
    - Test: collect_ris_metrics returns routing_summary dict with escalation_count, fallback_count, direct_count from routing_decision data
    - Test: _check_model_unavailable with provider failure data returns YELLOW when any provider has >3 failures in window, RED when all configured providers have failures
    - Test: _check_model_unavailable with no provider failure data returns GREEN with message "No provider failures detected" (not deferred)
    - Test: _check_review_queue_backlog with queue_depth>20 returns YELLOW, queue_depth>50 returns RED, queue_depth<=20 returns GREEN
    - Test: _check_review_queue_backlog with no pending_review data returns GREEN with message "No review queue data available"
    - Test: evaluate_health now returns 7 results (adding review_queue_backlog) instead of 6
  </behavior>
  <action>
    **metrics.py changes:**

    1. Add new fields to RisMetricsSnapshot dataclass:
       - `provider_route_distribution: dict` -- count of evals per selected_provider from routing_decision
       - `provider_failure_counts: dict` -- count of failures per failure_reason from provider_events
       - `review_queue: dict` -- keys: queue_depth (int), by_status (dict), by_gate (dict)
       - `disposition_distribution: dict` -- keys: ACCEPT, REVIEW, REJECT, BLOCKED counts
       - `routing_summary: dict` -- keys: escalation_count, fallback_count, direct_count, total_routed

    2. In collect_ris_metrics(), after existing eval artifacts loop, add:
       - Extract routing_decision from each artifact: count selected_provider occurrences for provider_route_distribution; count escalated=True for escalation_count, used_fallback=True for fallback_count
       - Extract provider_events from each artifact: for events with status != "success", count by failure_reason
       - Compute disposition_distribution: ACCEPT = gate=="ACCEPT", REVIEW = gate=="REVIEW", BLOCKED = gate=="REJECT" and scores.reject_reason=="scorer_failure", REJECT = gate=="REJECT" and not blocked
       - Query pending_review table from KnowledgeStore SQLite at ks_path:
         ```sql
         SELECT status, COUNT(*) FROM pending_review GROUP BY status
         SELECT gate, COUNT(*) FROM pending_review WHERE status='pending' GROUP BY gate
         ```
         Set queue_depth = count where status='pending'. Handle missing table gracefully (table may not exist in fresh DBs -- catch sqlite3.OperationalError).

    3. Update format_metrics_summary() to add sections for the new fields:
       - [Provider Routing] showing route distribution and escalation/fallback counts
       - [Provider Failures] showing failure counts (only if any failures exist)
       - [Review Queue] showing queue depth and status breakdown
       - [Dispositions] showing ACCEPT/REVIEW/REJECT/BLOCKED counts

    **health_checks.py changes:**

    4. Replace _check_model_unavailable() stub:
       - New signature: `_check_model_unavailable(provider_failure_counts: dict, routing_config: Optional[dict] = None) -> HealthCheckResult`
       - If provider_failure_counts is empty: return GREEN "No provider failures detected" with data={"deferred": False}
       - If any single provider has >3 failures: return YELLOW with message listing the provider(s) and failure count(s)
       - If all configured providers (primary + escalation + fallback from routing_config, or all keys in failure counts if no routing_config) have failures: return RED "All providers experiencing failures"
       - Remove the `data={"deferred": True, "check_type": "stub"}` pattern from this check

    5. Add new check `_check_review_queue_backlog(review_queue: dict) -> HealthCheckResult`:
       - If review_queue is empty or queue_depth key missing: GREEN "No review queue data available"
       - queue_depth > 50: RED "Review queue critical backlog: {depth} items pending"
       - queue_depth > 20: YELLOW "Review queue growing: {depth} items pending"
       - Otherwise: GREEN "Review queue manageable: {depth} items pending"
       - Include queue_depth and by_status in data dict

    6. Update ALL_CHECKS list:
       - Update model_unavailable description to remove "stub" language
       - Add review_queue_backlog entry with description "YELLOW when review queue depth > 20, RED when > 50"

    7. Update evaluate_health() signature:
       - Add new keyword args: `provider_failure_counts: Optional[dict] = None`, `review_queue: Optional[dict] = None`, `routing_config: Optional[dict] = None`
       - Pass provider_failure_counts and routing_config to _check_model_unavailable
       - Call _check_review_queue_backlog(review_queue or {})
       - Return 7 results (was 6)

    **tests/test_ris_monitoring.py changes:**

    8. Add test class TestMetricsPhase2 with tests for:
       - provider_route_distribution aggregation from eval artifacts with routing_decision
       - provider_failure_counts aggregation from provider_events
       - review_queue population from pending_review table (use tmp_path SQLite)
       - disposition_distribution with BLOCKED detection
       - routing_summary counts

    9. Update existing TestHealthChecks:
       - Add tests for real model_unavailable check (no failures, some failures, all failures)
       - Add tests for review_queue_backlog (empty, small, medium, critical)
       - Update test_all_green_on_good_runs to pass new kwargs and expect 7 results
       - Update any test that asserts len(results) == 6 to expect 7
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && rtk python -m pytest tests/test_ris_monitoring.py -x -v --tb=short 2>&1 | head -80</automated>
  </verify>
  <done>
    - RisMetricsSnapshot has 5 new fields covering routing, failures, queue, dispositions
    - model_unavailable health check uses real provider failure data (not a stub)
    - review_queue_backlog health check uses pending_review table data
    - evaluate_health returns 7 results
    - All new and existing monitoring tests pass
  </done>
</task>

<task type="auto">
  <name>Task 2: Update CLI tools for Phase 2 operator truth and write dev log</name>
  <files>
    tools/cli/research_health.py
    tools/cli/research_stats.py
    docs/RIS_OPERATOR_GUIDE.md
    docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md
  </files>
  <action>
    **research_health.py changes:**

    1. After loading runs, also collect Phase 2 data to pass to evaluate_health:
       - Call collect_ris_metrics() (from packages.research.metrics) to get the snapshot
       - Extract provider_failure_counts and review_queue from the snapshot
       - Pass these to evaluate_health() as the new kwargs
       - This wires the real data into the health checks

    2. Update _output_table() to add an overall status category line after the summary:
       - Parse the results to determine one of 4 states:
         - "HEALTHY" -- all GREEN, no deferred checks
         - "DEGRADED" -- at least one YELLOW, no RED
         - "BLOCKED_ON_SETUP" -- RED checks that are clearly setup-related (e.g., model_unavailable when no providers configured, shown by checking if all provider failures are "provider_unavailable")
         - "FAILURE" -- at least one RED from real operational issues
       - Print the category as: `Overall: {category}` after the check table
       - For BLOCKED_ON_SETUP, add a hint: "Configure provider API keys to resolve. See docs/RIS_OPERATOR_GUIDE.md"

    3. Update _output_json() to include the same overall_category field alongside existing summary field.

    4. Remove the existing footer note about deferred checks (since model_unavailable is no longer deferred). Keep a footer note only if rejection_audit_disagreement is still deferred.

    **research_stats.py changes:**

    5. The summary and export subcommands already call collect_ris_metrics() and serialize via to_dict(). Since the new fields are added to RisMetricsSnapshot in Task 1, they will automatically appear in both --json and export output. No structural changes needed to research_stats.py for data flow.

    6. Update format_metrics_summary() call path: The formatter in metrics.py was already updated in Task 1 to include the new sections. Verify by running the command.

    **docs/RIS_OPERATOR_GUIDE.md changes:**

    7. Update the "Health Monitoring > research-health" section (around line 230):
       - Replace the sample output showing `model_unavailable: GREEN [stub - deferred]` and `rejection_audit_disagreement: GREEN [stub - deferred]` with updated output showing real check behavior
       - Update "Returns a snapshot of 6 health check results" to "7 health check results"
       - Add brief description of the new review_queue_backlog check
       - Update the note about "The last two checks ... are stubs" to say only rejection_audit_disagreement is deferred
       - Add a brief note about the overall status categories (HEALTHY/DEGRADED/BLOCKED_ON_SETUP/FAILURE)

    8. In the "What Does NOT Work Yet [PLANNED]" section (around line 395):
       - Remove the bullet about "model_unavailable health check -- Returns GREEN stub" (it is now real)
       - Keep the rejection_audit_disagreement bullet as still deferred

    **Dev log:**

    9. Create docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md with:
       - What was done: expanded metrics, wired deferred checks, improved operator output
       - Files changed
       - What was invisible before and is now visible
       - Remaining deferred: rejection_audit_disagreement (needs audit runner)
       - Test results
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && rtk python -m pytest tests/test_ris_monitoring.py -x -v --tb=short 2>&1 | head -60 && python -m polytool research-health --json 2>&1 | head -40 && python -m polytool research-stats summary --json 2>&1 | head -40</automated>
  </verify>
  <done>
    - research-health --json output includes overall_category field (HEALTHY/DEGRADED/BLOCKED_ON_SETUP/FAILURE)
    - research-health table output shows real model_unavailable and review_queue_backlog checks
    - research-stats summary --json includes provider_route_distribution, provider_failure_counts, review_queue, disposition_distribution, routing_summary
    - research-stats export writes all Phase 2 fields to metrics_snapshot.json
    - RIS_OPERATOR_GUIDE.md updated to reflect real check behavior
    - Dev log created at docs/dev_logs/2026-04-08_ris_phase2_monitoring_truth.md
    - All existing tests still pass
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| SQLite reads | metrics.py reads from knowledge.sqlite3 pending_review table -- untrusted data from prior ingestion |
| JSONL reads | metrics.py reads eval_artifacts.jsonl -- untrusted data from prior evaluation runs |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-oyu-01 | T (Tampering) | pending_review SQLite query | accept | Read-only queries; no writes. Data integrity is the ingestion pipeline's responsibility. |
| T-oyu-02 | D (DoS) | collect_ris_metrics large artifact files | accept | Existing pattern already loads full JSONL. For monitoring use, file sizes are bounded by daily budget caps (200/day). |
| T-oyu-03 | I (Information Disclosure) | metrics_snapshot.json export | accept | Contains aggregate counts only, no PII or secrets. Local file, not served. |
</threat_model>

<verification>
1. Run full monitoring test suite: `python -m pytest tests/test_ris_monitoring.py -x -v`
2. Run CLI smoke tests:
   - `python -m polytool research-health --json` -- verify 7 checks, no deferred for model_unavailable, overall_category present
   - `python -m polytool research-stats summary --json` -- verify new fields present
   - `python -m polytool research-stats export` -- verify metrics_snapshot.json has new fields
3. Run full test suite: `python -m pytest tests/ -x -q --tb=short` -- no regressions
</verification>

<success_criteria>
- research-health reports 7 checks (was 6), model_unavailable uses real data, review_queue_backlog is new
- research-stats summary/export includes provider routing, failure counts, queue depth, disposition distribution
- Operator can distinguish HEALTHY / DEGRADED / BLOCKED_ON_SETUP / FAILURE from health output
- All existing tests pass, new tests cover the Phase 2 metrics and health checks
- Dev log and operator guide updated
</success_criteria>

<output>
After completion, create `.planning/quick/260408-oyu-finish-phase-2-ris-monitoring-truth/260408-oyu-SUMMARY.md`
</output>
