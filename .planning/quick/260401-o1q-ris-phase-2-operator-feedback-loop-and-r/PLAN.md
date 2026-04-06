# PLAN: RIS Phase 2 -- Operator Feedback Loop and Richer Query Integration

## Goal

Add lifecycle event recording (override, outcome) to the precheck ledger, expose new CLI subcommands for operator feedback, enhance query/report output with provenance/contradiction/staleness/lifecycle summaries, and downweight contradicted/superseded evidence by default.

## Existing State Summary

- **Precheck ledger** (`packages/research/synthesis/precheck_ledger.py`): append-only JSONL, schema `precheck_ledger_v1`, event_type `precheck_run`. Has `_iter_events()`, `append_precheck()`, `list_prechecks()`. Fields include `precheck_id`, `reason_code`, `evidence_gap`, `review_horizon`.
- **Precheck runner** (`packages/research/synthesis/precheck.py`): `PrecheckResult` dataclass, `run_precheck()`, `find_contradictions()`, `check_stale_evidence()`. Enriched fields: `precheck_id`, `reason_code`, `evidence_gap`, `review_horizon`. No lifecycle fields yet.
- **CLI** (`tools/cli/research_precheck.py`): single `main()` with `--idea`, `--provider`, `--ledger`, `--no-ledger`, `--json`. No subcommands.
- **Retriever** (`packages/research/ingestion/retriever.py`): `query_knowledge_store()` (filters by source_family, min_freshness, top_k) and `format_provenance()` (claim + confidence + freshness + sources). No contradiction/lifecycle summaries.
- **KnowledgeStore** (`packages/polymarket/rag/knowledge_store.py`): `query_claims()` already applies freshness modifier and 0.5x contradiction penalty to `effective_score`. Claims have `lifecycle` field (`active`, `archived`, `superseded`). Has `get_relations()`, `get_provenance()`.
- **CLI registration** (`polytool/__main__.py`): `research-precheck` routes to `tools.cli.research_precheck.main`.

## Files to Change

| File | What Changes |
|------|-------------|
| `packages/research/synthesis/precheck_ledger.py` | Bump to `precheck_ledger_v2`. Add `append_override()` and `append_outcome()` functions that write `event_type="override"` / `event_type="outcome"` records. Add `get_precheck_history()` to retrieve all events for a given `precheck_id` sorted by `written_at`. Add `list_prechecks_by_window()` to filter by time range. |
| `packages/research/synthesis/precheck.py` | Add `was_overridden`, `override_reason`, `outcome_label`, `outcome_date` fields to `PrecheckResult` dataclass (defaults: `False`, `""`, `""`, `""`). These are populated only when reading back from the ledger, not during `run_precheck()`. |
| `packages/research/ingestion/retriever.py` | Add `format_enriched_report()` function that produces a structured report string including: provenance summary per claim, contradiction summary (from `get_relations()` with type CONTRADICTS), freshness/staleness notes, lifecycle state. Add `query_knowledge_store_enriched()` that returns claims augmented with `contradiction_summary`, `provenance_docs`, `is_contradicted` fields. |
| `tools/cli/research_precheck.py` | Refactor to use subcommands via `argparse` subparsers: `run` (current behavior), `override`, `outcome`, `history`, `inspect`. Register help text for the `research-precheck` section. |
| `polytool/__main__.py` | No changes needed -- `research-precheck` already routes to the module, and the module accepts `argv` which will include subcommand tokens. |
| `tests/test_ris_phase2_operator_loop.py` | New test file with offline deterministic tests for all new functionality. |
| `docs/dev_logs/2026-04-01_ris_phase2_operator_loop_and_query_integration.md` | Dev log. |
| `docs/CURRENT_STATE.md` | Update RIS section. |

## Task Breakdown

### Task 1: Ledger Schema v2 -- Override and Outcome Events

**Files:** `packages/research/synthesis/precheck_ledger.py`, `packages/research/synthesis/precheck.py`

**Actions:**

1. In `precheck_ledger.py`:
   - Change `LEDGER_SCHEMA_VERSION` to `"precheck_ledger_v2"`.
   - Add `append_override(precheck_id, override_reason, ledger_path=None)`:
     - Writes a JSONL line with `event_type="override"`, `schema_version="precheck_ledger_v2"`, `precheck_id`, `was_overridden=True`, `override_reason`, `written_at`.
     - Validates `precheck_id` is non-empty string, raises `ValueError` otherwise.
   - Add `append_outcome(precheck_id, outcome_label, outcome_date=None, ledger_path=None)`:
     - Writes a JSONL line with `event_type="outcome"`, `schema_version="precheck_ledger_v2"`, `precheck_id`, `outcome_label`, `outcome_date` (defaults to current UTC ISO if None), `written_at`.
     - `outcome_label` must be one of `"successful"`, `"failed"`, `"partial"`, `"not_tried"` -- raises `ValueError` otherwise.
   - Add `get_precheck_history(precheck_id, ledger_path=None) -> list[dict]`:
     - Returns all events (precheck_run, override, outcome) matching `precheck_id`, sorted by `written_at` ascending.
   - Add `list_prechecks_by_window(start_iso, end_iso, ledger_path=None) -> list[dict]`:
     - Returns all events whose `written_at` falls within `[start_iso, end_iso]` inclusive. ISO string comparison is sufficient since all timestamps are UTC ISO-8601.
   - Keep `append_precheck()` writing `precheck_ledger_v2` (new entries). Old v0/v1 entries remain readable.

2. In `precheck.py`:
   - Add four fields to `PrecheckResult` dataclass:
     ```
     was_overridden: bool = False
     override_reason: str = ""
     outcome_label: str = ""
     outcome_date: str = ""
     ```
   - These fields are NOT populated by `run_precheck()` -- they exist so that downstream code can hydrate a `PrecheckResult` from ledger history with lifecycle state.

**Verify:** `python -m pytest tests/test_ris_phase2_operator_loop.py -x -q --tb=short` -- tests for append_override, append_outcome, get_precheck_history, list_prechecks_by_window all pass.

**Done:** Override and outcome events can be appended to the ledger. History retrieval by precheck_id and time window works. Old ledger entries remain readable. `PrecheckResult` has the four new fields with backward-compatible defaults.

---

### Task 2: Enriched Query Output -- Provenance, Contradictions, Staleness, Lifecycle

**Files:** `packages/research/ingestion/retriever.py`

**Actions:**

1. Add `query_knowledge_store_enriched(store, *, source_family=None, min_freshness=None, top_k=20, include_contradicted=False) -> list[dict]`:
   - Calls `store.query_claims(apply_freshness=True)` then filters like `query_knowledge_store`.
   - For each claim, augments with:
     - `provenance_docs: list[dict]` -- from `store.get_provenance(claim_id)`.
     - `contradiction_summary: list[str]` -- claim texts of claims that CONTRADICT this one (query `store.get_relations(claim_id, relation_type="CONTRADICTS")`, then for each relation, fetch the other claim's `claim_text`).
     - `is_contradicted: bool` -- `len(contradiction_summary) > 0`.
     - `staleness_note: str` -- "STALE" if `freshness_modifier < 0.5`, "AGING" if `< 0.7`, "" otherwise.
     - `lifecycle: str` -- from the claim's own `lifecycle` field.
   - If `include_contradicted=False` (default), contradicted claims still appear in results (they are already downweighted by KnowledgeStore's 0.5x penalty on `effective_score`) but are annotated. Setting `include_contradicted=True` is a no-op on filtering (same result) -- the flag exists as a documentation/extensibility hook. Contradicted claims are NOT hidden by default; they are ANNOTATED and sorted lower.

2. Add `format_enriched_report(claims: list[dict]) -> str`:
   - Produces a structured multi-line report string. For each claim:
     ```
     [N] Claim: {claim_text}
         Confidence: {confidence} | Freshness: {freshness_modifier:.2f} | Score: {effective_score:.3f}
         Lifecycle: {lifecycle} | Status: {validation_status}
         Staleness: {staleness_note or "(fresh)"}
         Contradictions: {contradiction_summary or "(none)"}
         Provenance: {source titles or "(none linked)"}
     ```
   - Separator line between claims.

**Verify:** `python -m pytest tests/test_ris_phase2_operator_loop.py::TestEnrichedQuery -x -q --tb=short` -- all enriched query tests pass.

**Done:** `query_knowledge_store_enriched()` returns claims annotated with provenance, contradiction summary, staleness notes, and lifecycle state. `format_enriched_report()` produces human-readable structured output. Contradicted/superseded evidence is sorted lower by default (via KnowledgeStore's existing `effective_score` mechanism).

---

### Task 3: CLI Subcommands -- Override, Outcome, History, Inspect

**Files:** `tools/cli/research_precheck.py`

**Actions:**

1. Refactor `main(argv)` to use `argparse` subparsers. Subcommands:

   - **`run`** (default if no subcommand given -- backward compat): current behavior unchanged. Args: `--idea`, `--provider`, `--ledger`, `--no-ledger`, `--json`.

   - **`override`**: Record that the operator overrode a precheck recommendation.
     - Args: `--precheck-id TEXT` (required), `--reason TEXT` (required), `--ledger PATH`, `--json`.
     - Calls `append_override(precheck_id, reason, ledger_path)`.
     - Prints confirmation or JSON.

   - **`outcome`**: Record the actual outcome of a precheck'd idea.
     - Args: `--precheck-id TEXT` (required), `--label {successful,failed,partial,not_tried}` (required), `--date ISO` (optional, defaults to now), `--ledger PATH`, `--json`.
     - Calls `append_outcome(precheck_id, label, outcome_date, ledger_path)`.
     - Prints confirmation or JSON.

   - **`history`**: Show all events for a precheck, or all events in a time window.
     - Args: `--precheck-id TEXT` (mutually exclusive with time window), `--start ISO` + `--end ISO` (mutually exclusive with precheck-id), `--ledger PATH`, `--json`.
     - Calls `get_precheck_history()` or `list_prechecks_by_window()`.
     - Prints formatted table (or JSON with `--json`).

   - **`inspect`**: Show enriched query output from the KnowledgeStore.
     - Args: `--source-family TEXT`, `--min-freshness FLOAT`, `--top-k INT`, `--include-contradicted`, `--json`.
     - Calls `query_knowledge_store_enriched()` and prints via `format_enriched_report()` (or JSON).
     - Note: This requires an on-disk KnowledgeStore. If the DB file doesn't exist, print a helpful error and return 1.

2. Backward compatibility: if `argv[0]` is not a known subcommand and `--idea` is present in argv, treat as `run` subcommand (existing callers keep working).

**Verify:** `python -m pytest tests/test_ris_phase2_operator_loop.py::TestCLI -x -q --tb=short` -- all CLI subcommand tests pass. Also: `python -m polytool research-precheck --help` shows subcommands.

**Done:** All four new subcommands work. Existing `research-precheck --idea "..."` syntax still works (backward compat). `--json` flag works on all subcommands.

---

### Task 4: Tests, Dev Log, Docs Update

**Files:** `tests/test_ris_phase2_operator_loop.py`, `docs/dev_logs/2026-04-01_ris_phase2_operator_loop_and_query_integration.md`, `docs/CURRENT_STATE.md`

**Actions:**

1. Create `tests/test_ris_phase2_operator_loop.py` with the following test classes (all offline, :memory: SQLite, tmp_path for JSONL):

   **TestAppendOverride:**
   - `test_append_override_writes_event`: writes override event, reads back, checks event_type/precheck_id/was_overridden/override_reason.
   - `test_append_override_empty_id_raises`: raises ValueError on empty precheck_id.
   - `test_append_override_schema_version`: written event has `precheck_ledger_v2`.

   **TestAppendOutcome:**
   - `test_append_outcome_writes_event`: writes outcome event, reads back, checks event_type/precheck_id/outcome_label/outcome_date.
   - `test_append_outcome_invalid_label_raises`: raises ValueError on "invalid_label".
   - `test_append_outcome_valid_labels`: each of "successful", "failed", "partial", "not_tried" accepted.
   - `test_append_outcome_auto_date`: when outcome_date is None, a valid ISO timestamp is written.

   **TestGetPrecheckHistory:**
   - `test_history_single_run`: one precheck_run event returned.
   - `test_history_run_plus_override`: returns both events in order.
   - `test_history_multiple_ids_filtered`: only events for requested precheck_id returned.

   **TestListPrechecksByWindow:**
   - `test_window_includes_matching`: events within window returned.
   - `test_window_excludes_outside`: events outside window excluded.

   **TestPrecheckResultLifecycleFields:**
   - `test_new_fields_default`: was_overridden=False, override_reason="", outcome_label="", outcome_date="".
   - `test_fields_set_explicitly`: can construct with lifecycle fields.

   **TestEnrichedQuery:**
   - `test_enriched_claims_have_provenance`: provenance_docs populated when evidence linked.
   - `test_enriched_claims_have_contradiction_summary`: contradiction_summary populated for contradicted claims.
   - `test_enriched_claims_staleness_note`: stale doc produces "STALE" note.
   - `test_enriched_claims_lifecycle_present`: lifecycle field present in output.
   - `test_format_enriched_report_structure`: output contains expected section headers.

   **TestCLI:**
   - `test_run_subcommand_backward_compat`: `main(["--idea", "test", "--no-ledger", "--json"])` exits 0 (no subcommand = run).
   - `test_run_explicit_subcommand`: `main(["run", "--idea", "test", "--no-ledger", "--json"])` exits 0.
   - `test_override_subcommand`: `main(["override", "--precheck-id", "abc123", "--reason", "operator override", "--ledger", str(tmp_path/"ledger.jsonl")])` exits 0, ledger has override event.
   - `test_outcome_subcommand`: `main(["outcome", "--precheck-id", "abc123", "--label", "successful", "--ledger", str(tmp_path/"ledger.jsonl")])` exits 0, ledger has outcome event.
   - `test_history_subcommand`: pre-populate a ledger, then `main(["history", "--precheck-id", "abc123", "--ledger", str(tmp_path/"ledger.jsonl"), "--json"])` exits 0 and outputs JSON.
   - `test_help_shows_subcommands`: `main(["--help"])` raises SystemExit(0) and output contains "override" and "outcome".

2. Write dev log at `docs/dev_logs/2026-04-01_ris_phase2_operator_loop_and_query_integration.md`.

3. Update `docs/CURRENT_STATE.md` -- RIS section to note Phase 2 additions: lifecycle events, enriched queries, new CLI subcommands.

**Verify:** `python -m pytest tests/test_ris_phase2_operator_loop.py -x -q --tb=short` all pass. `python -m pytest tests/test_ris_precheck_wiring.py tests/test_ris_ingestion_integration.py -x -q --tb=short` all still pass (no regressions).

**Done:** All new functionality has deterministic offline tests. Dev log written. CURRENT_STATE.md updated. Existing tests pass without regression.

## Test Plan

1. **Unit tests** (Task 4): ~25 tests covering all new functions and CLI subcommands.
2. **Regression**: existing `test_ris_precheck_wiring.py` (35 tests) and `test_ris_ingestion_integration.py` (9 tests) must still pass.
3. **CLI smoke**: `python -m polytool research-precheck --help` shows subcommands. `python -m polytool research-precheck run --idea "test" --no-ledger --json` returns valid JSON.
4. **Full suite**: `python -m pytest tests/ -x -q --tb=short` -- no regressions.

## Risks and Assumptions

1. **Schema version bump from v1 to v2**: `append_precheck()` will write v2; old v0/v1 entries remain readable since `list_prechecks()` and `_iter_events()` just parse raw JSON lines. The only risk is if external code checks `schema_version == "precheck_ledger_v1"` -- grep confirms no such check exists.

2. **Subcommand refactor**: Adding subparsers to argparse could break existing callers who pass `--idea` directly without a subcommand. Mitigated by backward-compat detection: if first arg is not a known subcommand and `--idea` is in argv, route to `run`.

3. **KnowledgeStore inspect command**: Requires on-disk SQLite DB. If no DB exists, the command should fail gracefully with a helpful message rather than crash.

4. **N+1 queries in enriched query**: For each claim, we call `get_provenance()` and `get_relations()`. For small claim sets (top_k=20 default), this is fine. Not a concern at current scale.

5. **Existing tests**: The `PrecheckResult` dataclass gains four new fields with defaults. Existing construction sites (e.g., in tests) do not pass these fields, so they get defaults. No breakage expected because dataclass fields with defaults can be appended.

## Execution Order

Tasks 1 and 2 are independent (ledger changes vs retriever changes). Task 3 depends on both Task 1 and Task 2 (CLI uses both). Task 4 should be written first (TDD-ish) or alongside each task.

Recommended execution: Task 1 -> Task 2 -> Task 3 -> Task 4 (finalize tests, dev log, docs).
