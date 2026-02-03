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

6) Evaluate retrieval quality
```
python -m polyttool rag-eval --suite docs/eval/sample_queries.jsonl
```
Reports are written to `kb/rag/eval/reports/<timestamp>/` with a `report.json` and `summary.md`.

7) Rerank hybrid results (optional)

Cross-encoder reranking improves precision by rescoring the top-N fused results with a more powerful model. This is opt-in and runs fully offline.

```
python -m polyttool rag-query --question "What strategies did Alice use?" --hybrid --rerank --k 8
```

Specify a custom reranker model or rerank depth:
```
python -m polyttool rag-query --question "..." --hybrid --rerank \
    --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2 \
    --rerank-top-n 50 --k 8
```

Model files are cached under `kb/rag/models/` (gitignored). First run downloads the model; subsequent runs load from cache.

To include reranking in eval:
```
python -m polyttool rag-eval --suite docs/eval/sample_queries.jsonl \
    --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2
```

This adds a `hybrid+rerank` column to the eval report alongside vector, lexical, and hybrid.

## Notes
- The index is stored under `kb/rag/index/` (gitignored).
- Default roots are `kb/` and `artifacts/`; `docs/archive/` can be added optionally (see step 4).
- Save any LLM memo outputs under `kb/users/<slug>/llm_outputs/`.
- Paste retrieved snippets into Opus 4.5 (or another offline model) for memo drafting.
- Cross-encoder model cache lives in `kb/rag/models/` (gitignored). Delete this directory to force re-download.
- **External / manual LLM UIs**: if you paste into a hosted model (Opus 4.5 web, ChatGPT, etc.),
  upload only the memo + minimal dossier excerpts you are comfortable sharing externally.
