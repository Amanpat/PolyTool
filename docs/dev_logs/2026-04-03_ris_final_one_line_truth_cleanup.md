# 2026-04-03 RIS Final One-Line Truth Cleanup

**Date:** 2026-04-03
**Task:** quick-260403-o5h
**Scope:** Doc-only — no code changes

## Objective

Remove the last stale operator-facing `rag-query` example in the RIS dev logs that was
missing the `--hybrid` flag when used with `--knowledge-store`.

## What Changed

**File:** `docs/dev_logs/2026-04-03_ris_final_dossier_operationalization.md`, line 167

Before (stale, fails at runtime):
```bash
python -m polytool rag-query --question "MOMENTUM strategy wallets" --knowledge-store default
```

After (correct):
```bash
python -m polytool rag-query --question "MOMENTUM strategy wallets" --hybrid --knowledge-store default
```

## Why

The `--knowledge-store` flag requires `--hybrid` mode at runtime. Omitting it produces:

```
Error: --knowledge-store requires --hybrid mode.
```

This was confirmed in `tools/cli/rag_query.py` lines 210-212. The fix was previously applied
to several other dev logs (wallet_scan_truth_drift_fix, ris_final_dossier_queryability_fix,
ris_final_truth_reconciliation) and to CLAUDE.md, but one instance remained in the dossier
operationalization log under the "What the first-class dossier flow now looks like" section.

## Scan Confirmation

All remaining `--knowledge-store` usages in the RIS dev logs either:
- Now include `--hybrid` (this fix), or
- Are inside clearly-marked historical "old text (broken at runtime)" sections and are
  intentionally left untouched as historical record.

## Codex Review

Tier: Skip (doc-only). No review required.
