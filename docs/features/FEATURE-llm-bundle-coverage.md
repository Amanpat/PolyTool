# FEATURE: LLM Bundle Coverage Section

**Shipped**: 2026-02-16
**Roadmap**: 4.1

## What shipped

`polytool llm-bundle --user "@X"` now automatically includes a "Coverage & Reconciliation"
section in the generated `bundle.md`. This section contains the coverage report from the
latest scan run, giving the LLM data-quality context alongside the dossier evidence.

## How it works

- The bundle locates the latest scan run (`command_name="scan"`) under
  `artifacts/dossiers/users/<slug>/`.
- If `coverage_reconciliation_report.md` exists, it is included verbatim.
- If only the `.json` version exists, a deterministic summary is generated.
- If no coverage data is found, a clear note is shown.

## RAG is now optional

RAG imports are lazy-loaded. On a travel laptop without RAG dependencies installed,
`llm-bundle` still runs successfully:
- Coverage section is populated normally.
- RAG excerpts section notes "RAG unavailable; excerpts omitted."
- All output artifacts (`bundle.md`, `rag_queries.json`, `bundle_manifest.json`) are written.

## Related docs

- `docs/specs/SPEC-0002-llm-bundle-coverage.md` - full specification
- `docs/adr/0005-llm-bundle-rag-optional.md` - decision record
- `docs/LLM_BUNDLE_WORKFLOW.md` - updated workflow
