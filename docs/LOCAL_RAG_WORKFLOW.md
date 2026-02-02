# Local RAG Workflow

This workflow is fully local/offline. It never uses external LLM APIs.

## Install (local only)
```
pip install -r requirements-rag.txt
```

Windows note: for CUDA builds of `torch`, follow the official PyTorch install selector. CPU-only works fine.

## Workflow steps
1) Run scan (ingest data into ClickHouse)
```
python -m polyttool scan
```

2) Export dossier (private artifacts)
```
python -m polyttool export-dossier --user "@Pimping"
```

3) Export ClickHouse datasets (private KB)
```
python -m polyttool export-clickhouse --user "@Pimping"
```
Outputs land under `kb/users/<slug>/exports/<YYYY-MM-DD>/` by default.

4) Build the local RAG index (kb + artifacts only)
```
python -m polyttool rag-index --roots "kb,artifacts" --rebuild
```

Optional — include archived docs (useful when you want RAG to surface past design decisions):
```
python -m polyttool rag-index --roots "kb,artifacts,docs/archive" --rebuild
```

5) Query the local RAG index
```
python -m polyttool rag-query --question "Summarize recent strategy shifts" --k 8
```

Optional (limit to a user):
```
python -m polyttool rag-query --user "@Pimping" --question "What's the most recent evidence?" --k 8
```

## Notes
- The index is stored under `kb/rag/index/` (gitignored).
- Default roots are `kb/` and `artifacts/`; `docs/archive/` can be added optionally (see step 4).
- Save any LLM memo outputs under `kb/users/<slug>/llm_outputs/`.
- Paste retrieved snippets into Opus 4.5 (or another offline model) for memo drafting.
- **External / manual LLM UIs**: if you paste into a hosted model (Opus 4.5 web, ChatGPT, etc.),
  upload only the memo + minimal dossier excerpts you are comfortable sharing externally.
