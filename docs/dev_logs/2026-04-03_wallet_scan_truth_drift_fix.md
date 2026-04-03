# wallet-scan truth-drift doc fix

**Date**: 2026-04-03
**Plan**: quick-260403-nra
**Type**: Documentation / help-text correction only (no implementation logic changed)

---

## What

Fixed 3 truth-drift blockers in the wallet-scan feature docs and CLI help text, identified
by Codex as the final RIS truth-drift items after quick-260403-n2o shipped the dossier
extraction feature.

### Blocker 1 — docs/features/wallet-scan-v0.md: post_ingest_extract flag

**Old text (incorrect):**
```
derived claims are automatically extracted (`post_ingest_extract=True`), making findings
```

**New text (accurate):**
```
derived claims are automatically extracted (`post_extract_claims=True` in `ingest_dossier_findings()`,
which calls `extract_and_link()` directly after patching metadata), making findings
```

**Why**: `post_ingest_extract=True` was the pipeline flag approach that was NOT used.
The shipped code in wallet_scan.py calls `ingest_dossier_findings(findings, store, post_extract_claims=True)`,
which calls `extract_and_link()` directly. This was documented correctly in the STATE.md decision
from quick-260403-n2o but the feature doc was not updated.

### Blocker 2 — docs/features/wallet-scan-v0.md: rag-query example missing --hybrid

**Old text (broken at runtime):**
```bash
# Standard vector-only retrieval
python -m polytool rag-query --question "MOMENTUM strategy wallets" --knowledge-store default
```

**New text (accurate):**
```bash
# Vector-only retrieval (omit --hybrid and --knowledge-store to search source_documents only; derived_claims are not searched)
python -m polytool rag-query --question "MOMENTUM strategy wallets"
```

**Why**: Confirmed in `tools/cli/rag_query.py` lines 210-212: `--knowledge-store` requires
`--hybrid` and returns `Error: --knowledge-store requires --hybrid mode.` without it.
The old example would fail at runtime. The fix replaces it with a plain vector-only query
that actually works, with a comment explaining what is and is not searched.

### Blocker 3 — tools/cli/wallet_scan.py: research-query in help text

**Old text (references non-existent command):**
```
"are queryable via rag-query / research-query commands."
```

**New text (accurate):**
```
"are queryable via rag-query command (use --hybrid --knowledge-store default for derived claims)."
```

**Why**: `research-query` is not an exposed CLI command (confirmed: not registered in
`polytool/__main__.py`). Referencing it in help text would mislead operators.
The fix replaces it with the correct `rag-query` command and includes the required
flags for derived claim retrieval.

---

## Files changed

- `docs/features/wallet-scan-v0.md` — 2 corrections in the Dossier Extraction section
- `tools/cli/wallet_scan.py` — 1 help string correction on the `--extract-dossier` argument

---

## Testing

```bash
# Smoke test: CLI still loads, help text shows corrected content
python -m polytool wallet-scan --help

# Doc assertions
python -c "text=open('docs/features/wallet-scan-v0.md').read(); \
  assert 'post_ingest_extract=True' not in text; \
  assert 'post_extract_claims=True' in text; \
  print('OK')"

python -c "text=open('tools/cli/wallet_scan.py').read(); \
  assert 'research-query' not in text; \
  print('OK')"
```

All assertions pass. `python -m polytool wallet-scan --help` runs without errors.

---

## Codex review

Tier: Skip (docs-only change, no implementation code modified).
No Codex review required per CLAUDE.md policy.
