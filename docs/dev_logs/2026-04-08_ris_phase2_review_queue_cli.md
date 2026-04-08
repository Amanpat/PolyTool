# RIS Phase 2 Review Queue CLI

## Files changed and why

- `packages/polymarket/rag/knowledge_store.py`
  Added durable `pending_review` storage plus append-only `pending_review_history`, along with enqueue/list/inspect/resolve helpers.
- `tools/cli/research_review.py`
  Added operator CLI for `list`, `inspect`, `accept`, `reject`, and `defer`.
- `polytool/__main__.py`
  Registered the new `research-review` command and added it to top-level usage text.
- `tests/test_knowledge_store.py`
  Updated schema expectations because the KnowledgeStore now owns two additional review-queue tables.
- `tests/test_ris_review_queue.py`
  Added focused offline coverage for schema upgrade, queue insert, list/inspect, resolve actions, and CLI persistence.
- `docs/dev_logs/2026-04-08_ris_phase2_review_queue_cli.md`
  Recorded implementation details, commands run, results, and open questions.

## Commands run + output

1. `pytest -q tests/test_knowledge_store.py tests/test_ris_review_queue.py`
   Result: failed once.
   Output summary: `1 failed, 43 passed`.
   Failure: legacy schema-count test still expected 4 app tables after adding review-queue tables.

2. `pytest -q tests/test_knowledge_store.py tests/test_ris_review_queue.py`
   Result: passed.
   Output summary: `44 passed in 0.78s`.

3. `python -m polytool research-review --help`
   Result: passed.
   Output summary: showed `list`, `inspect`, `accept`, `reject`, and `defer` subcommands with the RIS review-queue description.

4. `python -c "from packages.polymarket.rag.knowledge_store import KnowledgeStore; ... enqueue_pending_review(...)"` against `.tmp\ris_review_cli.sqlite3`
   Result: passed.
   Output summary: no stdout; created a temp KnowledgeStore DB with one pending review item.

5. `python -m polytool research-review list --db .tmp\ris_review_cli.sqlite3 --json`
   Result: passed.
   Output summary: returned one pending item with `gate="REVIEW"`, `weighted_score=2.9`, `simple_sum_score=12.0`, and persisted source metadata fields.

## Test results

- Focused pytest after fix: `44 passed`, `0 failed`.
- CLI help smoke: passed.
- CLI list smoke against temp DB: passed.

## Decisions made

- Kept schema expansion tight by adding two SQLite tables in the existing KnowledgeStore path:
  `pending_review` for the current queue state and `pending_review_history` for append-only audit events.
- Stored both the full gate snapshot JSON and explicit scalar diagnostics (`weighted_score`, `simple_sum_score`) for easy operator inspection and later pipeline consumption.
- Treated `accept` and `reject` as terminal states with idempotent repeat handling for the same decision.
- Treated `defer` as unresolved queue state, not a final disposition.
- Did not wire queue insertion into evaluator or provider flow yet; only the storage/API and operator CLI contract were added.
- Kept wording and CLI description aligned with the spec constraint that scores describe ingestion/research usefulness only, not trading recommendations.

## Open questions for next prompt

- When the evaluator/pipeline is wired in, should `REVIEW` documents be persisted to `source_documents` before queueing, or should queue rows be allowed to exist without a stored source document until operator acceptance?
- On future operator `accept`, should the queue action itself trigger downstream promotion/workflow hooks, or should later integration consume accepted rows asynchronously from `pending_review`?
- Should deferred items eventually support an explicit `defer_until` or expiry policy, or is status/history-only sufficient for the next phase?
