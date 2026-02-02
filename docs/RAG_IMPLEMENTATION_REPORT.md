# RAG Implementation Report

## Trees

### RAG modules

```text
packages/polymarket/rag/
  __init__.py
  chunker.py
  embedder.py
  index.py
  manifest.py
  query.py
```

### CLI entrypoints (rag-index, rag-query)

```text
polyttool/__main__.py
tools/cli/
  rag_index.py
  rag_query.py
```

### Config/constants for roots + private paths

```text
packages/polymarket/rag/index.py
tools/cli/rag_index.py
tools/cli/rag_query.py
.gitignore
tools/guard/pre_push_guard.py
.githooks/pre-push
tools/guard/run_guard.ps1
```

## rag-index

### Chunking

Chunking is performed in `chunk_text` and invoked from `build_index`.

```python
# packages/polymarket/rag/chunker.py

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[TextChunk]:
```

```python
# packages/polymarket/rag/index.py

chunks: List[TextChunk] = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
```

### Metadata stored per chunk

Each chunk is stored with file and span metadata plus a top-level root tag.

```python
# packages/polymarket/rag/index.py

metadatas.append(
    {
        "file_path": rel_path,
        "chunk_id": chunk.chunk_id,
        "start_word": chunk.start_word,
        "end_word": chunk.end_word,
        "root": rel_path.split("/", 1)[0],
    }
)
```

### Chroma persistence + collection naming

Persistence defaults to `kb/rag/index` and the collection defaults to `polyttool_rag`.

```python
# packages/polymarket/rag/index.py

DEFAULT_COLLECTION = "polyttool_rag"
DEFAULT_PERSIST_DIR = Path("kb") / "rag" / "index"

client = chromadb.PersistentClient(path=str(persist_path))
collection = client.get_or_create_collection(
    name=collection_name,
    metadata={"hnsw:space": "cosine"},
)
```

CLI defaults align with the same values.

```python
# tools/cli/rag_index.py

parser.add_argument("--roots", default="kb,artifacts")
parser.add_argument("--persist-dir", default="kb/rag/index")
parser.add_argument("--collection", default="polyttool_rag")
```

### Doc IDs and chunk IDs

Chunk IDs are sequential per file from the chunker; doc IDs are derived from the repo-relative path.

```python
# packages/polymarket/rag/index.py

ids.append(f"{rel_path}::chunk_{chunk.chunk_id}")
```

## rag-query

### Retrieval call sites + top-k

Retrieval is performed in `query_index` with a candidate pool of `max(k * 4, k)` and then trimmed to `k`.

```python
# packages/polymarket/rag/query.py

search_k = max(k * 4, k)
result = collection.query(
    query_embeddings=[query_embedding.tolist()],
    n_results=search_k,
    include=["documents", "metadatas", "distances"],
)
```

CLI default k is 8.

```python
# tools/cli/rag_query.py

parser.add_argument("--k", type=int, default=8)
```

### Filtering support

The only filtering today is path-prefix filtering in `query_index` plus a user-scoped prefix list in the CLI.

```python
# packages/polymarket/rag/query.py

if filter_prefixes:
    if not any(file_path.startswith(prefix) for prefix in filter_prefixes):
        continue
```

```python
# tools/cli/rag_query.py

def _build_user_prefixes(user: str) -> List[str]:
    return [
        f"kb/users/{slug}/",
        f"artifacts/dossiers/{slug}/",
        f"artifacts/dossiers/users/{slug}/",
    ]
```

### Output format

`rag-query` prints JSON with `question`, `k`, `filters`, and `results`. Each result includes file path, chunk id, score, snippet, and metadata.

```python
# packages/polymarket/rag/query.py

outputs.append(
    {
        "file_path": file_path,
        "chunk_id": metadata.get("chunk_id", doc_id),
        "score": score,
        "snippet": snippet,
        "metadata": metadata or {},
    }
)
```

```python
# tools/cli/rag_query.py

payload = {
    "question": args.question,
    "k": args.k,
    "filters": prefixes or [],
    "results": results,
}
print(json.dumps(payload, indent=2))
```

## Repo safety

### .gitignore (private KB + artifacts + indexes/caches)

```text
# Artifacts (never commit)
/artifacts/
/artifacts/dossiers/
/artifacts/dossiers/**
/artifacts/**

# Private KB (keep only README + .gitkeep)
kb/**
!kb/README.md
!kb/.gitkeep
kb/rag/index/
kb/rag/index/**
kb/rag/manifests/
kb/rag/manifests/**
chroma/

# Python caches
__pycache__/
.pytest_cache/
```

### Guard scripts

The repo ships a pre-push guard; no pre-commit guard was found.

```bash
# .githooks/pre-push
python tools/guard/pre_push_guard.py
```

```python
# tools/guard/pre_push_guard.py

if lower.startswith("kb/"):
    return True, "private kb path"
if lower.startswith("artifacts/"):
    return True, "artifacts path"
```

Optional wrapper:

```powershell
# tools/guard/run_guard.ps1
python tools/guard/pre_push_guard.py
```

## Recommended insertion points

### Metadata filters

- `packages/polymarket/rag/index.py`: extend per-chunk `metadatas` with richer fields (owner, source_type, date).
- `packages/polymarket/rag/query.py`: pass a structured `where` clause into `collection.query(...)` instead of (or in addition to) prefix filtering.
- `tools/cli/rag_query.py`: add CLI flags for filters and map them to the `where` clause.

### Lexical index (BM25 / keyword)

- `packages/polymarket/rag/index.py`: after chunking, feed `(doc_id, text)` into a new `rag/lexical.py` builder and persist under `kb/rag/lexical/`.
- `packages/polymarket/rag/manifest.py`: record lexical index metadata (version, tokenizer, doc count).

### Fusion (vector + lexical)

- `packages/polymarket/rag/query.py`: retrieve vector + lexical candidates, normalize scores, and fuse before trimming to `k`.
- New helper (e.g., `rag/fusion.py`) called just before the `outputs` list is finalized.

### Rerank

- `packages/polymarket/rag/query.py`: after candidate assembly (pre-trim), run a cross-encoder reranker and then apply `k`.
- `tools/cli/rag_query.py`: add flags for rerank model and candidate pool size.
