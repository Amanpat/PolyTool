---
quick_id: 260402-qud
title: "RIS Phase 4 claim extraction hardening"
type: execute
autonomous: true
files_modified:
  - packages/research/ingestion/claim_extractor.py
  - tests/test_ris_claim_extraction.py
  - tests/test_research_extract_claims_cli.py
  - docs/dev_logs/2026-04-02_ris_phase4_claim_extraction_hardening.md
---

<objective>
Harden RIS Phase 4 claim extraction so relation behavior, evidence linking,
deterministic IDs, and CLI coverage are tested with exact assertions, and
broad exception swallowing is narrowed to only expected cases.

Purpose: Codex review flagged three risk areas -- relation tests that only
assert non-negative counts instead of exact SUPPORTS/CONTRADICTS rows,
broad `except Exception: pass` that hides real DB errors, and zero CLI
test coverage. This plan addresses all three.

Output: Strengthened tests with exact assertions, narrowed exception
handling in `build_intra_doc_relations`, new CLI smoke tests, dev log.
</objective>

<context>
@packages/research/ingestion/claim_extractor.py
@packages/polymarket/rag/knowledge_store.py  (add_relation, get_relations, claim_relations schema)
@tests/test_ris_claim_extraction.py
@tools/cli/research_extract_claims.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Narrow exception handling in build_intra_doc_relations</name>
  <files>packages/research/ingestion/claim_extractor.py</files>
  <action>
In `build_intra_doc_relations()` (line 538-542), the bare `except Exception: pass`
silently swallows ALL errors from `store.add_relation()`. The claim_relations table
has NO UNIQUE constraint on (source_claim_id, target_claim_id, relation_type), so
duplicate-row IntegrityError cannot actually occur. The CHECK constraint on
relation_type can only fire if code passes an invalid type, which is a real bug
that should propagate.

Changes to make:

1. Replace the bare `except Exception: pass` with `import sqlite3` at the top
   of the module and `except sqlite3.IntegrityError: pass` in the try block.
   This catches only real SQLite constraint violations (FK misses, CHECK failures
   on unexpected relation types), while letting programming errors (TypeError,
   AttributeError), connection errors (OperationalError), and other unexpected
   exceptions propagate up.

2. Add a logging import (`import logging`) and a module-level
   `_log = logging.getLogger(__name__)` at the top. In the except block,
   change to:
   ```python
   except sqlite3.IntegrityError:
       _log.debug("Duplicate or constraint violation for relation %s->%s (%s), skipping",
                   cid_i, cid_j, relation_type)
   ```

3. Do NOT change the function signature or return type. The count should still
   only count successfully inserted relations.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_ris_claim_extraction.py -x -q --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
The `except` block in `build_intra_doc_relations` catches only
`sqlite3.IntegrityError`, not bare `Exception`. A debug log line is emitted
on skip. All existing tests still pass.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add exact-assertion relation and evidence tests</name>
  <files>tests/test_ris_claim_extraction.py</files>
  <action>
The current relation tests only assert `count >= 0` and wrap checks in
`if len(claim_ids) >= 2` (silently passing when extraction yields fewer
claims). The evidence tests check partial location JSON shape but miss
`section_heading`. The idempotency test does not verify evidence-row
stability.

Add/rewrite these test methods inside the existing test classes:

### A. In `TestBuildIntraDocRelations`:

1. **Replace `test_supports_relation_between_shared_term_claims`:**
   Use a purpose-built fixture with exactly 2 sentences that share 3+ key
   terms and have NO negation:
   ```
   RELATION_SUPPORTS_DOC = """\
   ## Market Momentum

   The market momentum algorithm detects strong patterns in order flow data signals across multiple exchanges.
   Statistical analysis confirms that market momentum patterns generate consistent order flow data signals.
   """
   ```
   Extract claims, assert `len(claim_ids) == 2` (fail loudly if not).
   Call `build_intra_doc_relations`. Assert `count == 1`.
   Fetch relations via `store.get_relations(claim_ids[0])`.
   Assert exactly 1 relation row exists. Assert its `relation_type == "SUPPORTS"`.
   Assert that `source_claim_id` and `target_claim_id` are both in `claim_ids`.

2. **Replace `test_contradicts_relation_for_negation_pair`:**
   Use a purpose-built fixture with exactly 2 sentences sharing 3+ key
   terms where one has negation and the other does not:
   ```
   RELATION_CONTRADICTS_DOC = """\
   ## Contradicting Evidence

   The market momentum algorithm detects strong patterns in order flow data signals across exchanges.
   The market momentum algorithm does not detect reliable patterns in order flow data signals.
   """
   ```
   Extract claims, assert `len(claim_ids) == 2`.
   Call `build_intra_doc_relations`. Assert `count == 1`.
   Fetch relations via `store.get_relations(claim_ids[0], relation_type="CONTRADICTS")`.
   Assert exactly 1 CONTRADICTS relation. Assert source/target are the two claim IDs.

3. **Add `test_no_relation_when_insufficient_shared_terms`:**
   Use a fixture with 2 sentences that share < 3 key terms:
   ```
   RELATION_NO_MATCH_DOC = """\
   ## Disjoint Topics

   The cryptocurrency exchange processes thousands of transactions every single second continuously.
   Weather patterns indicate significant rainfall amounts expected throughout the coming spring season.
   """
   ```
   Extract claims, assert >= 2. Call `build_intra_doc_relations`. Assert `count == 0`.

4. **Add `test_relation_idempotent_on_rerun`:**
   Use the SUPPORTS fixture. Extract, build relations (count == 1).
   Call `build_intra_doc_relations` again with same claim_ids.
   Assert count == 1 again (second batch inserts another row since there is
   no UNIQUE constraint -- document this as a known limitation if so, OR
   assert count == 1 if the second run produces a new row, verifying the
   relation_count reflects new inserts accurately).
   Query all relations for claim_ids[0] and assert total row count.

### B. In `TestExtractClaimsFromDocument`:

5. **Strengthen `test_evidence_has_excerpt_and_location`:**
   After the existing assertions, add:
   - Assert `loc["section_heading"]` is a non-empty string (the fixture has
     section headings so this should always be populated for the first claim).
   - Assert `loc["document_id"] == doc_id`.
   - Assert `row["excerpt"]` length is > 0 and <= 500 (the code truncates
     to 500 chars).

6. **Add `test_idempotent_extraction_evidence_not_doubled`:**
   Use FIXTURE_MARKDOWN via tmp_path. Extract once, count evidence rows
   for each claim. Extract again. Count evidence rows again. Assert counts
   are identical (the extraction code has an EXISTS check before inserting
   evidence, so this should hold).
   ```python
   def _count_evidence(store, claim_id):
       return store._conn.execute(
           "SELECT COUNT(*) as c FROM claim_evidence WHERE claim_id = ?",
           (claim_id,)
       ).fetchone()["c"]
   ```

### C. In `TestExtractAndLink`:

7. **Strengthen `test_returns_summary_dict`:**
   Assert `result["claims_extracted"] >= 3` (the FIXTURE_MARKDOWN has at
   least 3 clearly assertive sentences). This catches regressions where
   extraction silently produces 0 claims.

### Implementation notes:
- Each new fixture string must produce EXACTLY the expected number of claims.
  Before writing the test, mentally verify: the sentence must be >= 30 chars,
  not code/table/heading, and not all-caps. Both sentences in the SUPPORTS
  and CONTRADICTS fixtures share "market", "momentum", "algorithm", "patterns",
  "order", "flow", "data", "signals" -- well above the 3-term threshold.
- Use `_add_doc_with_file(store, tmp_path, DOC, filename="unique_name.md")`
  for each fixture to avoid path collisions.
- All new tests must be offline and deterministic.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_ris_claim_extraction.py -x -v --tb=short 2>&1 | tail -30</automated>
  </verify>
  <done>
Relation tests assert exact SUPPORTS/CONTRADICTS row types and counts, not
just `>= 0`. Evidence tests verify full location JSON shape including
`section_heading`. Idempotency test covers evidence rows. No test uses
`if len(...) >= N` to silently skip assertions. All tests pass.
  </done>
</task>

<task type="auto">
  <name>Task 3: Add CLI smoke tests for research-extract-claims</name>
  <files>tests/test_research_extract_claims_cli.py</files>
  <action>
Create a new test file `tests/test_research_extract_claims_cli.py` with
offline smoke tests for the CLI entrypoint. All tests use
`KnowledgeStore(":memory:")` via monkeypatch or by calling `main(argv)`
with a tmp_path SQLite file.

Tests to write:

1. **`test_main_help_returns_zero`:**
   Call `main(["--help"])` inside a `pytest.raises(SystemExit)` and assert
   the exit code is 0. (argparse calls `sys.exit(0)` on --help.)

2. **`test_main_no_args_returns_error`:**
   Call `main([])` inside `pytest.raises(SystemExit)` and assert exit
   code is 2 (argparse error for missing required group).

3. **`test_main_doc_id_not_found`:**
   Create a tmp SQLite KnowledgeStore, pass its path via `--db-path`.
   Call `main(["--doc-id", "nonexistent", "--db-path", str(db_path)])`.
   Assert return code is 0 (processes 0 claims, no error).

4. **`test_main_all_empty_store`:**
   Create an empty KnowledgeStore SQLite file via tmp_path.
   Call `main(["--all", "--db-path", str(db_path)])`.
   Assert return code is 0. Capture stdout and assert "No source documents"
   appears OR (if --json) `"documents_processed": 0`.

5. **`test_main_all_json_output_shape`:**
   Create a KnowledgeStore with one doc (use the _add_doc_with_file helper
   pattern: write FIXTURE_MARKDOWN to tmp_path, register in store, close
   store, then call main with --all --json --db-path). Parse stdout as JSON.
   Assert keys: `documents_processed`, `total_claims`, `total_relations`,
   `per_doc_results`. Assert `total_claims >= 1`.

6. **`test_main_dry_run_does_not_write`:**
   Create a KnowledgeStore with one doc. Call main with
   `["--all", "--dry-run", "--db-path", str(db_path)]`.
   Assert return code is 0. Re-open the store and assert
   `store.query_claims(apply_freshness=False)` returns 0 claims (dry run
   did not write).

7. **`test_main_all_json_dry_run`:**
   Same as dry run but with `--json`. Parse stdout, assert `"dry_run": true`
   and `"total_claims_estimate"` key exists and is >= 1.

Implementation pattern:
```python
import json, sys, pytest
from pathlib import Path
from io import StringIO
from tools.cli.research_extract_claims import main
from packages.polymarket.rag.knowledge_store import KnowledgeStore

FIXTURE_MARKDOWN = "..."  # Copy the same multi-section fixture

def _create_store_with_doc(tmp_path, body=FIXTURE_MARKDOWN):
    db_path = tmp_path / "test_kb.sqlite3"
    store = KnowledgeStore(str(db_path))
    # add doc using the helper pattern from the existing test file
    import hashlib
    content_hash = hashlib.sha256(body.encode()).hexdigest()
    fpath = tmp_path / "doc.md"
    fpath.write_text(body, encoding="utf-8")
    store.add_source_document(
        title="Test", source_url=f"file://{fpath.as_posix()}",
        source_family="blog", content_hash=content_hash,
        chunk_count=0, confidence_tier="PRACTITIONER",
        metadata_json="{}",
    )
    store.close()
    return str(db_path)
```

Use `capsys` or monkeypatch `sys.stdout` to capture printed output.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_research_extract_claims_cli.py -x -v --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>
7 CLI smoke tests exist and pass. Coverage includes: help, missing args,
missing doc, empty store, JSON output shape, dry-run non-destructiveness,
and JSON dry-run output. All offline, no network.
  </done>
</task>

<task type="auto">
  <name>Task 4: Dev log and final regression run</name>
  <files>docs/dev_logs/2026-04-02_ris_phase4_claim_extraction_hardening.md</files>
  <action>
Write `docs/dev_logs/2026-04-02_ris_phase4_claim_extraction_hardening.md` with:

1. **Summary:** One paragraph: what was hardened and why (Codex review findings).

2. **Changes made:**
   - `claim_extractor.py`: Narrowed `except Exception` to `except sqlite3.IntegrityError`
     with debug logging. No functional change to happy path.
   - `test_ris_claim_extraction.py`: Replaced weak `>= 0` relation assertions with
     exact SUPPORTS/CONTRADICTS row checks. Added evidence shape assertions
     (section_heading, excerpt length cap). Added evidence idempotency test.
     Added no-relation test for insufficient shared terms.
   - `test_research_extract_claims_cli.py`: New file, 7 smoke tests for CLI.

3. **Test results:** Paste exact `pytest` output (count passed/failed/skipped).

4. **Known limitations:**
   - `claim_relations` table has no UNIQUE constraint on (source, target, type).
     Running `build_intra_doc_relations` twice on same claim set inserts duplicate
     rows. This is a schema concern for a future ticket, not addressed here.
   - Relation type assignment (SUPPORTS vs CONTRADICTS) uses simple negation
     heuristic, not semantic analysis. False positives/negatives are expected
     for nuanced text.

5. **Codex review tier:** Skip (tests and docs only, per CLAUDE.md policy).

After writing the dev log, run the full regression suite:
```bash
cd "D:/Coding Projects/Polymarket/PolyTool"
python -m pytest tests/test_ris_claim_extraction.py tests/test_research_extract_claims_cli.py -v --tb=short
```
Then run the broader project smoke:
```bash
python -m polytool --help
```
Report exact pass/fail counts.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_ris_claim_extraction.py tests/test_research_extract_claims_cli.py -v --tb=short 2>&1 | tail -5</automated>
  </verify>
  <done>
Dev log exists at the expected path. All tests pass. `python -m polytool --help`
loads without error.
  </done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_ris_claim_extraction.py tests/test_research_extract_claims_cli.py -v --tb=short` -- all pass, zero failures
2. `python -m pytest tests/ -x -q --tb=short` -- full suite still passes (no regressions)
3. `python -m polytool --help` -- CLI loads
4. `grep -n "except Exception" packages/research/ingestion/claim_extractor.py` -- returns NO matches (broad catch removed)
5. `grep -n "except sqlite3.IntegrityError" packages/research/ingestion/claim_extractor.py` -- returns 1 match (narrowed catch)
6. `grep -c "SUPPORTS\|CONTRADICTS" tests/test_ris_claim_extraction.py` -- count is significantly higher than before (exact type assertions added)
</verification>

<success_criteria>
- Zero `except Exception` in claim_extractor.py (replaced with specific sqlite3.IntegrityError)
- Relation tests assert exact relation_type strings (SUPPORTS, CONTRADICTS) on exact row counts, not >= 0
- Evidence tests assert full location JSON shape including section_heading key
- Idempotency test covers both claim rows AND evidence rows
- 7 new CLI smoke tests exist and pass (help, args error, missing doc, empty store, JSON shape, dry-run, JSON dry-run)
- All pre-existing tests still pass
- Dev log written
</success_criteria>
