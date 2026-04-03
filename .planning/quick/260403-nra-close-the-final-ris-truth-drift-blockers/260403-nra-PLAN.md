---
phase: quick-260403-nra
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/features/wallet-scan-v0.md
  - tools/cli/wallet_scan.py
  - docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md
autonomous: true
requirements: [TRUTH-DRIFT-01, TRUTH-DRIFT-02, TRUTH-DRIFT-03]

must_haves:
  truths:
    - "wallet-scan-v0.md accurately describes the shipped claim extraction mechanism (post_extract_claims=True + direct extract_and_link)"
    - "wallet-scan-v0.md rag-query examples include --hybrid when using --knowledge-store"
    - "wallet_scan.py help text references only rag-query (not the non-existent research-query command)"
  artifacts:
    - path: "docs/features/wallet-scan-v0.md"
      provides: "Corrected dossier extraction docs"
      contains: "post_extract_claims=True"
    - path: "tools/cli/wallet_scan.py"
      provides: "Corrected help text"
      contains: "rag-query"
    - path: "docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md"
      provides: "Dev log for this fix"
  key_links:
    - from: "docs/features/wallet-scan-v0.md"
      to: "tools/cli/wallet_scan.py"
      via: "Docs describe what shipped code actually does"
      pattern: "post_extract_claims"
---

<objective>
Fix 3 documentation/help-text truth-drift blockers in wallet-scan so that docs and CLI help
accurately reflect shipped behavior from quick-260403-n2o.

Purpose: Codex identified these as the final RIS truth-drift items. Closing them ensures
developer trust in docs and prevents confusion when operators run wallet-scan --extract-dossier.

Output: Corrected wallet-scan-v0.md, corrected wallet_scan.py help string, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docs/features/wallet-scan-v0.md
@tools/cli/wallet_scan.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix wallet-scan-v0.md truth drift (2 blockers)</name>
  <files>docs/features/wallet-scan-v0.md</files>
  <action>
Two corrections in the "Dossier Extraction (--extract-dossier)" section:

**Blocker 1 — Line 133:** Replace the sentence:
  `derived claims are automatically extracted (`post_ingest_extract=True`), making findings`
with:
  `derived claims are automatically extracted (`post_extract_claims=True` in `ingest_dossier_findings()`, which calls `extract_and_link()` directly after patching metadata), making findings`

The shipped code in wallet_scan.py line 95 calls `ingest_dossier_findings(findings, store, post_extract_claims=True)`. The old doc text referenced `post_ingest_extract=True` which was the pipeline flag approach that was NOT used (per STATE.md decision in quick-260403-n2o: "call extract_and_link directly after patch (not via post_ingest_extract=True pipeline flag)").

**Blocker 2 — Lines 156-159 (rag-query examples):** The first example already correctly shows `--hybrid --knowledge-store default`. The second example on line 159 shows:
  `python -m polytool rag-query --question "MOMENTUM strategy wallets" --knowledge-store default`
This is missing `--hybrid`. However, this example intentionally demonstrates "standard vector-only retrieval" as a contrast. Verify the query layer: if `--knowledge-store` truly requires `--hybrid`, update the second example to also use `--hybrid` and remove the "Standard vector-only retrieval" comment OR add a note that vector-only retrieval on the knowledge-store is also valid. Based on the task description ("the query layer requires --hybrid with --knowledge-store"), update the second example to:
  ```
  # Vector-only retrieval (omit --hybrid to skip derived_claims; searches source_documents only)
  python -m polytool rag-query --question "MOMENTUM strategy wallets" --knowledge-store default
  ```
If the query layer truly errors without --hybrid, instead replace the second block entirely with a note:
  ```
  # Note: --hybrid is required when using --knowledge-store to search derived_claims.
  # Without --hybrid, only source_documents are searched (no derived claim retrieval).
  ```

To determine the correct fix: check `packages/polymarket/rag/` for the rag-query implementation. If `--knowledge-store default` works without `--hybrid` (just skips derived_claims), keep the second example but clarify the comment. If it errors, remove it.

Do NOT change anything outside the "Dossier Extraction" section. Leave the rest of wallet-scan-v0.md untouched.
  </action>
  <verify>
    <automated>python -c "text=open('docs/features/wallet-scan-v0.md').read(); assert 'post_ingest_extract=True' not in text, 'old flag still present'; assert 'post_extract_claims=True' in text, 'new flag missing'; print('OK: wallet-scan-v0.md truth drift fixed')"</automated>
  </verify>
  <done>
  - "post_ingest_extract=True" no longer appears in wallet-scan-v0.md
  - "post_extract_claims=True" appears, accurately describing shipped behavior
  - rag-query examples are accurate (either both use --hybrid, or the non-hybrid path is correctly documented)
  </done>
</task>

<task type="auto">
  <name>Task 2: Fix wallet_scan.py help text (1 blocker) + dev log</name>
  <files>tools/cli/wallet_scan.py, docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md</files>
  <action>
**Blocker 3 — wallet_scan.py line 602:** The help text for `--extract-dossier` currently says:
  `"are queryable via rag-query / research-query commands."`
`research-query` is NOT an exposed CLI command (confirmed: not in polytool/__main__.py). Change to:
  `"are queryable via rag-query command (use --hybrid --knowledge-store default for derived claims)."`

This is a single string change on line 602 of tools/cli/wallet_scan.py. Do not touch any other code in the file.

**Dev log:** Create `docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md` with:
- Title: "wallet-scan truth-drift doc fix"
- What: Fixed 3 truth-drift blockers (post_ingest_extract -> post_extract_claims in feature doc, --hybrid clarification in rag-query examples, removed non-existent research-query from help text)
- Why: Codex review identified these as final RIS truth-drift items
- Files changed: docs/features/wallet-scan-v0.md, tools/cli/wallet_scan.py
- Testing: `python -m polytool wallet-scan --help` shows corrected help text
  </action>
  <verify>
    <automated>python -c "text=open('tools/cli/wallet_scan.py').read(); assert 'research-query' not in text, 'research-query still in help text'; print('OK: help text fixed')" && python -m polytool wallet-scan --help 2>&1 | head -5</automated>
  </verify>
  <done>
  - "research-query" no longer appears anywhere in wallet_scan.py
  - Help text for --extract-dossier correctly references only rag-query
  - Dev log created at docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md
  </done>
</task>

</tasks>

<verification>
All three truth-drift blockers resolved:
1. wallet-scan-v0.md: post_ingest_extract=True -> post_extract_claims=True (matches shipped code)
2. wallet-scan-v0.md: rag-query examples clarified for --hybrid / --knowledge-store usage
3. wallet_scan.py: help text references only rag-query (not non-existent research-query)

Run: `python -m polytool --help` to confirm CLI still loads without errors.
</verification>

<success_criteria>
- grep -r "post_ingest_extract" docs/features/wallet-scan-v0.md returns empty
- grep -r "research-query" tools/cli/wallet_scan.py returns empty
- python -m polytool wallet-scan --help runs without error and shows corrected help
- Dev log exists at docs/dev_logs/2026-04-03_wallet_scan_truth_drift_fix.md
</success_criteria>

<output>
After completion, create `.planning/quick/260403-nra-close-the-final-ris-truth-drift-blockers/260403-nra-SUMMARY.md`
</output>
