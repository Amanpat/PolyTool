# LLM Evidence Bundle Workflow

This is a local-first, copy/paste workflow for building a short evidence bundle
for an LLM examination report. It works with any LLM UI and does not assume
any external APIs.

## Preferred: generate the bundle via CLI

Use the dedicated CLI to assemble the dossier + curated RAG excerpts into a
ready-to-paste bundle:

```
polytool llm-bundle --user "@example"
```

The bundle is written to:
`kb/users/<slug>/llm_bundles/<YYYY-MM-DD>/<run_id>/bundle.md`

## Dry run: LLM examination report

### Files to paste (in this order)
Use paths that match your actual dossier output. Do not paste private data into
public docs; keep it local.

1) `artifacts/dossiers/users/<slug>/<proxy_wallet>/<YYYY-MM-DD>/<case-id>/memo.md`
2) `artifacts/dossiers/users/<slug>/<proxy_wallet>/<YYYY-MM-DD>/<case-id>/dossier.json`
   - If the full file is large, paste only the key sections you need.
3) `artifacts/dossiers/users/<slug>/<proxy_wallet>/<YYYY-MM-DD>/<case-id>/manifest.json`
4) `artifacts/dossiers/users/<slug>/<proxy_wallet>/<YYYY-MM-DD>/<case-id>/coverage_reconciliation_report.md`
   (or `.json` fallback) - data quality / trust context from the latest scan run
5) **10 to 18 curated RAG excerpts** with `file_path` headers
   - Each excerpt should be short (1 to 3 sentences).
   - Prefer the highest-signal snippets that directly support your conclusions.

### How to format RAG excerpts
Use this exact header format so citations are unambiguous:
```
[file_path: kb/users/<slug>/notes/2026-02-03.md]
<excerpt text>

[file_path: artifacts/dossiers/users/<slug>/<proxy_wallet>/<YYYY-MM-DD>/<case-id>/dossier.json]
<excerpt text>
```

### Prompt template (ready to paste)
```
You are an LLM assistant. Write a concise examination report grounded ONLY in the
provided files. Every factual claim must include a citation using the exact
file_path in square brackets, e.g. [kb/users/alice/notes/2026-02-03.md].
If a claim is not supported by the pasted evidence, say so explicitly.
Do not invent details. Do not use outside knowledge.

Report requirements:
- Keep the tone neutral and forensic.
- Include a short executive summary (3 to 6 bullets).
- Include a findings section with evidence-backed bullets.
- Include a limitations section (what the evidence does not show).

Inputs (paste in this order):
1) memo.md
2) dossier.json (or key sections)
3) manifest.json
4) coverage_reconciliation_report.md (or json summary)
5) curated RAG excerpts with file_path headers
```

### Tips
- RAG excerpts should reinforce the memo and dossier; avoid redundant snippets.
- If using a hosted LLM UI, paste only content you are comfortable sharing.
- Keep the final report short; evidence quality matters more than length.

## Save the report run (private KB)
After you produce the report, save it into the private KB so Local RAG can retrieve
it later. Prompt text is stored in the devlog entry.

```
polytool llm-save --user "@example" --model "local-llm" --report-path "artifacts/llm/report.md" --prompt-path "artifacts/llm/prompt.md"
```

This writes to:
`kb/users/<slug>/llm_reports/<YYYY-MM-DD>/<model_slug>_<run_id>/`
